"""The three allergen metrics, and the source whose upstream misbehaves the most.

Two quirks shape every test here. The service answers HTTP 200 with an error body,
so `raise_for_status` never sees a failure; and it distinguishes "your extent is
outside the layer", which is permanent geography, from "I am busy", which is not.
Filing the second under coverage records a county as having no vegetation at all,
which on a lower_better metric makes it the best place in the country.

The crosswalk is fetched through the cache, so it is seeded rather than stubbed;
the sampler posts, so the tests about the service's own answers stub the response.
"""

import json
from collections import Counter

import httpx
import pytest

from refugia.metrics.sources.sampling import Sampling
from refugia.metrics.sources.landfire_vegetation import (
    PATTERNS,
    LandfireVegetationSource,
    OutsideCoverage,
)
from refugia.places.place import Place
from refugia.store.cache import Cache

FORT_COLLINS = Place(
    fips="08069", name="Larimer", state="Colorado", lat=40.66, lon=-105.46, population=198253
)

# Real EVT names, including the riparian classes that carry no Populus in the name.
CROSSWALK = "\n".join(
    [
        "VALUE,EVT_NAME",
        "3016,Inter-Mountain Basins Big Sagebrush Shrubland",
        "3060,Columbia Plateau Western Juniper Woodland and Savanna",
        "3122,Rocky Mountain Aspen Forest and Woodland",
        "3208,North-Central Interior and Appalachian Floodplain Forest",
        "3210,Northwestern Great Plains Riparian Woodland",
        "3900,Western Cool Temperate Urban Herbaceous",
        "3901,Laurentian-Acadian Northern Hardwoods Forest",
    ]
)


@pytest.fixture(name="source")
def _source(tmp_path):
    """A source whose crosswalk is already on disk, sampling nothing yet."""

    def build(**sampling) -> LandfireVegetationSource:
        cache = Cache(tmp_path)
        cache.write("landfire-evt-crosswalk", CROSSWALK.encode("utf-8"), ".csv")
        return LandfireVegetationSource(cache, sampling=Sampling(retries=1, **sampling))

    return build


def _seed_samples(
    source: LandfireVegetationSource, identifier: str, counts: dict[int, int]
) -> None:
    """Write a class histogram in the shape `_sample_at` reads back."""
    sampling = source._sampling
    source._cache.write(
        f"landfire-{identifier}-r{sampling.radius_km:g}-n{sampling.sample_count}",
        json.dumps({str(k): v for k, v in counts.items()}).encode(),
        ".json",
    )


def _response(body: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x"))


def test_the_crosswalk_resolves_each_metric_to_class_values(source):
    """The metric is a set of EVT class numbers, and the numbers move between
    vintages. Matching by name is what survives a renumber."""
    classes = source().class_sets()
    assert classes["juniper_cover"] == frozenset({3060})
    assert classes["sagebrush_cover"] == frozenset({3016})


def test_populus_includes_riparian_classes_that_do_not_say_populus(source):
    """LANDFIRE maps no cottonwood type. Matching the name alone finds aspen and
    scores the whole eastern floodplain as clean on the allergen being avoided.
    """
    populus = source().class_sets()["populus_cover"]
    assert 3122 in populus, "aspen matches by name"
    assert 3208 in populus and 3210 in populus, "riparian and floodplain forest"
    assert 3901 not in populus, "northern hardwoods is not a Populus habitat"


def test_a_crosswalk_that_matches_nothing_stops_the_run(tmp_path):
    """A renamed vintage would otherwise report every county as zero cover, which
    reads as good news on three lower_better metrics at once."""
    cache = Cache(tmp_path)
    cache.write("landfire-evt-crosswalk", b"VALUE,EVT_NAME\n1,Open Water", ".csv")
    with pytest.raises(RuntimeError, match="crosswalk may have changed"):
        LandfireVegetationSource(cache).class_sets()


def test_the_crosswalk_is_resolved_once_and_kept(source):
    """`fetch` asks per place; re-parsing a national CSV per county is not free."""
    built = source()
    assert built.class_sets() is built.class_sets()


def test_cover_is_a_share_of_what_was_sampled_not_a_count(source):
    """Sample counts differ between places, so a raw count is not comparable."""
    built = source()
    _seed_samples(built, "08069", {3060: 25, 3016: 25, 3900: 50})
    values = built.fetch((FORT_COLLINS,))
    assert values["juniper_cover"]["08069"] == pytest.approx(25.0)
    assert values["sagebrush_cover"]["08069"] == pytest.approx(25.0)
    assert values["populus_cover"]["08069"] == pytest.approx(0.0)


def test_a_place_with_no_allergen_is_recorded_as_zero_not_as_missing(source):
    """Zero cover is an answer and belongs in coverage; absent is not the same."""
    built = source()
    _seed_samples(built, "08069", {3900: 100})
    values = built.fetch((FORT_COLLINS,))
    assert values["juniper_cover"]["08069"] == pytest.approx(0.0)


def test_a_place_outside_the_layer_is_separated_from_a_place_that_failed(source, monkeypatch):
    """Alaska is permanently outside; a dropped connection is not. Recorded
    together, a transient failure becomes a fixed fact about the geography.
    """
    built = source()
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response({"error": {"code": 400, "message": "extent"}})
    )
    assert built.fetch((FORT_COLLINS,)) == {k: {} for k in PATTERNS}
    assert [fips for fips, _ in built.outside_coverage] == ["08069"]
    assert built.failures == ()


def test_a_busy_service_is_a_failure_rather_than_a_fact_about_the_land(source, monkeypatch):
    """The same 200-with-error-body shape carries both, told apart by the code."""
    built = source()
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response({"error": {"code": 503, "message": "busy"}})
    )
    assert built.fetch((FORT_COLLINS,)) == {k: {} for k in PATTERNS}
    assert [fips for fips, _ in built.failures] == ["08069"]
    assert built.outside_coverage == ()


def test_an_error_body_arrives_with_a_two_hundred(source, monkeypatch):
    """`raise_for_status` never sees this, which is the whole reason for the check."""
    built = source()
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response({"error": {"code": 400, "message": "outside"}})
    )
    with pytest.raises(OutsideCoverage):
        built._request_once(44.0, -121.0)


def test_nodata_samples_are_dropped_rather_than_counted_as_a_class(source, monkeypatch):
    """LF2025 returns NoData across the eastern US. Counted in the denominator it
    dilutes every cover fraction; counted as a class it invents one."""
    body = {
        "samples": [
            {"value": "3060 Juniper"},
            {"value": "NoData"},
            {"value": None},
            {"value": ""},
            {"value": "3900 Urban"},
        ]
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response(body))
    assert source()._request_once(44.0, -121.0) == Counter({3060: 1, 3900: 1})


def test_a_sample_value_carries_a_label_after_the_number(source, monkeypatch):
    """The service answers "3060 Columbia Plateau ...", not 3060."""
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: _response({"samples": [{"value": "3060 Columbia Plateau Juniper"}]}),
    )
    assert source()._request_once(44.0, -121.0) == Counter({3060: 1})


def test_an_extent_with_no_samples_at_all_is_a_failure_not_an_empty_answer(source, monkeypatch):
    """An empty sample set cached is a county permanently recorded as bare ground."""
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response({"samples": []}))
    with pytest.raises(httpx.HTTPError, match="no samples"):
        source()._request_once(44.0, -121.0)


def test_an_empty_sample_set_is_never_written_to_the_cache(source, monkeypatch):
    """A cached failure is indistinguishable from data and survives every run."""
    built = source()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _response({"samples": []}))
    built.fetch((FORT_COLLINS,))
    assert not built._cache.has(
        f"landfire-08069-r{built._sampling.radius_km:g}-n{built._sampling.sample_count}", ".json"
    )


def test_a_cached_place_is_never_sampled_again(source, monkeypatch):
    """Nineteen hundred counties at half a second each is the run this avoids."""
    built = source()
    _seed_samples(built, "08069", {3060: 10, 3900: 90})

    def explode(*_args, **_kwargs):
        raise AssertionError("this place was cached; nothing should reach the network")

    monkeypatch.setattr(httpx, "post", explode)
    assert built.fetch((FORT_COLLINS,))["juniper_cover"]["08069"] == pytest.approx(10.0)


def test_a_city_asks_the_same_question_at_a_sharper_coordinate(source):
    """`cover_at` exists so the city panel does not grow a second sampler that
    drifts from this one. It must produce the same shares from the same counts."""
    built = source()
    _seed_samples(built, "city-0827425", {3060: 20, 3900: 80})
    assert built.cover_at("city-0827425", 44.05, -121.31)["juniper_cover"] == pytest.approx(20.0)


def test_cover_at_returns_nothing_rather_than_dividing_by_zero(source, monkeypatch):
    """A city whose samples all came back NoData has no denominator."""
    built = source()
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _response({"samples": [{"value": "NoData"}]})
    )
    assert built.cover_at("city-1", 44.0, -121.0) == {}


def test_the_sampled_box_widens_with_latitude(source, monkeypatch):
    """A degree of longitude is 111 km at the equator and 50 in northern Maine. A
    fixed box would sample a strip half the intended width in the north, which is
    a different question than the one every southern county was asked.
    """
    built = source()
    boxes = {}

    def capture(*_args, **kwargs):
        geometry = json.loads(kwargs["data"]["geometry"])
        boxes[round(geometry["ymin"], 1)] = geometry["xmax"] - geometry["xmin"]
        return _response({"samples": [{"value": "3900"}]})

    monkeypatch.setattr(httpx, "post", capture)
    built._request_once(25.0, -80.0)
    built._request_once(60.0, -150.0)
    widths = [boxes[k] for k in sorted(boxes)]
    assert widths[0] < widths[-1], boxes


def test_every_vegetation_metric_is_declared_and_says_what_it_measures(source):
    """`populus_cover` in particular is a habitat proxy and has to admit it."""
    metrics = {m.key: m for m in source().metrics}
    assert set(metrics) == set(PATTERNS)
    for metric in metrics.values():
        assert metric.direction == "lower_better"
        assert metric.source and metric.unit
    assert "proxy" in metrics["populus_cover"].description
