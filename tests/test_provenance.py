"""When the data arrived, and who it belongs to, have to travel with the data.

`fetch` is cache-first, so "when did this run" and "how old is what it used" are
different questions and only the second one tells you whether a page is stale.
"""

import json
import os

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.cache import Cache
from refugia.store.dataset import Dataset


def _metric(**over) -> Metric:
    base = {
        "key": "a",
        "label": "A",
        "unit": "u",
        "direction": "lower_better",
        "category": "test",
        "description": "",
        "source": "s",
    }
    return Metric(**{**base, **over})


def _dataset(**over) -> Dataset:
    base = {
        "places": (Place(fips="00001", name="A", state="S", lat=0.0, lon=0.0, population=1),),
        "metrics": (_metric(),),
        "values": {"a": {"00001": 1.0}},
    }
    return Dataset(**{**base, **over})


def test_a_metric_carries_its_citation_and_terms():
    """Attribution that lives only in a markdown file rots the first time a source moves."""
    m = _metric(citation="Cite me thus.", terms_url="https://example.invalid/terms")
    assert m.citation == "Cite me thus."
    assert m.terms_url == "https://example.invalid/terms"


def test_citation_and_terms_are_optional():
    """Most sources are public domain and owe nothing; they should stay terse."""
    assert _metric().citation == ""
    assert _metric().terms_url == ""


def test_a_metric_round_trips_its_attribution_through_the_dataset(tmp_path):
    """The page is built from the saved dataset, so anything it must show lives there."""
    path = tmp_path / "d.json"
    _dataset(metrics=(_metric(citation="C", terms_url="https://example.invalid/t"),)).save(path)
    loaded = Dataset.load(path)
    assert loaded.metrics[0].citation == "C"
    assert loaded.metrics[0].terms_url == "https://example.invalid/t"


def test_a_dataset_records_when_it_was_built(tmp_path):
    """A page carries no other clue about its own age."""
    path = tmp_path / "d.json"
    _dataset(built_at="2026-09-07", oldest_response="2026-08-01").save(path)
    loaded = Dataset.load(path)
    assert loaded.built_at == "2026-09-07"
    assert loaded.oldest_response == "2026-08-01"


def test_provenance_is_optional_so_an_older_dataset_still_loads(tmp_path):
    """A dataset saved before these fields existed must not become unreadable."""
    path = tmp_path / "d.json"
    payload = _dataset().to_dict()
    del payload["built_at"]
    del payload["oldest_response"]
    path.write_text(json.dumps(payload))
    assert Dataset.load(path).built_at == ""


def test_an_empty_cache_has_no_oldest_entry(tmp_path):
    """Before the first fetch there is nothing to date."""
    assert Cache(tmp_path).oldest_entry() == ""


def test_the_oldest_cache_entry_is_the_one_reported(tmp_path):
    """Built today from data cached a year ago is the case worth catching."""
    cache = Cache(tmp_path)
    cache.write("new", b"x")
    old = cache.write("old", b"y")
    assert old is not None
    os.utime(old, (1_600_000_000, 1_600_000_000))  # 2020-09-13
    assert cache.oldest_entry() == "2020-09-13"


def test_a_dataset_saved_before_citations_regains_them_from_the_registry():
    """Provenance was made optional on load; attribution was left to rot."""

    class _Registry:
        def __contains__(self, key):
            return key == "a"

        def metric(self, key):
            return _metric(citation="Cite me thus.", terms_url="https://example.invalid/t")

    stale = _dataset().to_dict()
    del stale["metrics"][0]["citation"]
    del stale["metrics"][0]["terms_url"]
    rebuilt = Dataset.from_dict(stale, registry=_Registry())
    assert rebuilt.metrics[0].citation == "Cite me thus."
    # And the values still come from the file, not from anywhere else.
    assert rebuilt.values == {"a": {"00001": 1.0}}
