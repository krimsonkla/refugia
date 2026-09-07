"""Turning a question into a profile, with a local model that answers freely.

The model is the untrusted input here. It invents metric keys, invents filter
fields, and returns weights for things that do not exist -- and every one of those
becomes an empty ranking or a silently different question if it reaches the engine.
The filtering is the whole point of this class, so it is what these test.

Ollama is stubbed rather than seeded: there is no cache in front of it, and the
failure being tested is that it is not running at all.
"""

import json

import httpx
import pytest

from refugia.ask.planner import QueryPlanner
from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.scoring.scored_place import ScoredPlace


def _metric(key: str, direction: str = "lower_better") -> Metric:
    return Metric(
        key=key,
        label=key.replace("_", " ").title(),
        unit="u",
        direction=direction,
        category="test",
        description=f"How much {key}.",
        source="s",
    )


METRICS = (
    _metric("juniper_cover"),
    _metric("home_value"),
    _metric("life_expectancy", "higher_better"),
)


def _ollama(monkeypatch, content, *, capture=None):
    """Stand in for a running Ollama, recording the request body."""

    def answer(*_args, **kwargs):
        if capture is not None:
            capture.append(kwargs["json"])
        body = content if isinstance(content, str) else json.dumps(content)
        return httpx.Response(
            200,
            json={"message": {"content": body}},
            request=httpx.Request("POST", "http://localhost:11434/api/chat"),
        )

    monkeypatch.setattr(httpx, "post", answer)


def test_a_plan_becomes_a_profile_the_engine_can_run(monkeypatch):
    """The whole point: a sentence in, something `rank` accepts out."""
    _ollama(monkeypatch, {"weights": {"juniper_cover": 3, "home_value": 1}})
    profile = QueryPlanner().plan("cheap places with no juniper", METRICS)
    assert profile.weights == {"juniper_cover": 3.0, "home_value": 1.0}


def test_a_metric_the_model_invented_is_dropped(monkeypatch):
    """Models name plausible metrics this project does not have. Passed through,
    `rank` raises on the unknown key and the question fails outright."""
    _ollama(monkeypatch, {"weights": {"juniper_cover": 2, "pollen_index": 5}})
    assert set(QueryPlanner().plan("q", METRICS).weights) == {"juniper_cover"}


def test_a_plan_with_no_usable_weights_is_refused(monkeypatch):
    """An empty weight set ranks every place identically, which reads as an answer."""
    _ollama(monkeypatch, {"weights": {"pollen_index": 5}})
    with pytest.raises(ValueError, match="no usable metric weights"):
        QueryPlanner().plan("q", METRICS)


def test_a_criterion_on_a_metric_key_survives(monkeypatch):
    """Requirements are how "under $400,000" is expressed, and the field is a
    metric key as often as it is a place attribute."""
    _ollama(
        monkeypatch,
        {
            "weights": {"juniper_cover": 1},
            "criteria": [{"field": "home_value", "comparison": "max", "value": 400000}],
        },
    )
    profile = QueryPlanner().plan("q", METRICS)
    assert [c.field for c in profile.criteria] == ["home_value"]


def test_a_criterion_on_a_place_attribute_survives(monkeypatch):
    """`population`, `state` and the rest are filterable and the model uses them."""
    _ollama(
        monkeypatch,
        {
            "weights": {"juniper_cover": 1},
            "criteria": [
                {"field": "population", "comparison": "min", "value": 40000},
                {"field": "state", "comparison": "not_in", "value": ["Texas"]},
            ],
        },
    )
    assert {c.field for c in QueryPlanner().plan("q", METRICS).criteria} == {
        "population",
        "state",
    }


def test_a_criterion_on_an_invented_field_is_dropped(monkeypatch):
    """A field nothing has now stops the run rather than emptying the ranking, so
    letting one through turns a vague question into a hard failure."""
    _ollama(
        monkeypatch,
        {
            "weights": {"juniper_cover": 1},
            "criteria": [
                {"field": "walkability", "comparison": "min", "value": 70},
                {"field": "population", "comparison": "min", "value": 1000},
            ],
        },
    )
    assert [c.field for c in QueryPlanner().plan("q", METRICS).criteria] == ["population"]


def test_the_model_is_told_what_the_metrics_mean(monkeypatch):
    """Given only the keys it weights on the names, and `home_value` and
    `life_expectancy` point in opposite directions."""
    sent = []
    _ollama(monkeypatch, {"weights": {"juniper_cover": 1}}, capture=sent)
    QueryPlanner().plan("q", METRICS)
    system = sent[0]["messages"][0]["content"]
    for metric in METRICS:
        assert metric.key in system and metric.direction in system
        assert metric.description in system


def test_the_plan_turn_asks_for_json(monkeypatch):
    """Without it the model wraps the object in prose and `json.loads` fails."""
    sent = []
    _ollama(monkeypatch, {"weights": {"juniper_cover": 1}}, capture=sent)
    QueryPlanner().plan("q", METRICS)
    assert sent[0]["format"] == "json"
    assert sent[0]["options"]["temperature"] == 0


def test_a_trailing_slash_on_the_host_does_not_double_up(monkeypatch):
    """`http://host//api/chat` is a 404 from Ollama, reported as "not running"."""
    urls = []

    def answer(url, **_kwargs):
        urls.append(url)
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"weights": {"juniper_cover": 1}})}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", answer)
    QueryPlanner(host="http://localhost:11434/").plan("q", METRICS)
    assert urls == ["http://localhost:11434/api/chat"]


def test_ollama_not_running_says_how_to_start_it(monkeypatch):
    """This is the likeliest outcome of running `refugia ask` for the first time,
    and a bare ConnectError names neither the daemon nor the model to pull."""

    def refuse(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", refuse)
    with pytest.raises(RuntimeError) as caught:
        QueryPlanner(model="somemodel").plan("q", METRICS)
    assert "ollama serve" in str(caught.value)
    assert "ollama pull somemodel" in str(caught.value)


def test_narration_describes_a_ranking_it_is_handed(monkeypatch):
    """It must not recompute: the numbers on the page and the numbers in the
    sentence under it would then be produced by two different code paths."""
    sent = []
    _ollama(monkeypatch, "Fort Collins looks best.", capture=sent)
    place = Place(
        fips="08069", name="Larimer", state="Colorado", lat=44.0, lon=-121.0, population=1
    )
    scored = ScoredPlace(
        place=place,
        total=71.4,
        normalized={"juniper_cover": 80.0},
        raw={"juniper_cover": 3.2},
        contributions={"juniper_cover": 71.4},
        missing=(),
    )
    from refugia.scoring.profile import Profile

    text = QueryPlanner().narrate("q", Profile("p", {"juniper_cover": 1.0}), [scored], METRICS)
    assert text == "Fort Collins looks best."
    data = sent[0]["messages"][1]["content"]
    assert "Larimer" in data and "3.2 u" in data
    assert sent[0].get("format") != "json", "prose, not an object"
