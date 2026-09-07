"""The declarative source is the tier a model may author, so its guards matter."""

import json

import pytest

from refugia.metrics.sources.declarative import DeclarativeSource
from refugia.store.cache import Cache

SPEC = {
    "key": "example",
    "label": "Example",
    "unit": "score",
    "direction": "lower_better",
    "category": "test",
    "description": "d",
    "source": "s",
    "url": "https://example.invalid/data.csv",
    "format": "csv",
    "fips_column": "GEOID",
    "value_column": "val",
}


def _cache_with(tmp_path, body: bytes, key: str | None = None) -> Cache:
    cache = Cache(tmp_path / "c")
    cache.write(key or SPEC["url"], body)
    return cache


def test_reads_a_declared_csv(tmp_path, places):
    """The whole point: a working metric with no adapter code."""
    cache = _cache_with(tmp_path, b"GEOID,val\n00001,5\n00002,9\n")
    result = DeclarativeSource(SPEC, cache).fetch(places)
    assert result == {"example": {"00001": 5.0, "00002": 9.0}}


def test_aggregates_repeated_rows(tmp_path, places):
    """Many datasets carry one row per year; the spec says how to collapse them."""
    cache = _cache_with(tmp_path, b"GEOID,val\n00001,10\n00001,20\n")
    spec = {**SPEC, "aggregate": "mean"}
    assert DeclarativeSource(spec, cache).fetch(places)["example"]["00001"] == 15.0


def test_where_filters_rows(tmp_path, places):
    """A national file often needs one year or one measure selected."""
    cache = _cache_with(tmp_path, b"GEOID,val,year\n00001,5,2019\n00001,7,2024\n")
    spec = {**SPEC, "where": {"year": "2024"}}
    assert DeclarativeSource(spec, cache).fetch(places)["example"]["00001"] == 7.0


def test_scale_converts_units(tmp_path, places):
    """A source publishing thousands can be rescaled in the spec, not in code."""
    cache = _cache_with(tmp_path, b"GEOID,val\n00001,5\n")
    spec = {**SPEC, "scale": 1000}
    assert DeclarativeSource(spec, cache).fetch(places)["example"]["00001"] == 5000.0


def test_reads_nested_json(tmp_path, places):
    """JSON APIs usually bury the rows under a key."""
    body = json.dumps({"result": {"records": [{"GEOID": "00001", "val": 3}]}}).encode()
    cache = _cache_with(tmp_path, body)
    spec = {**SPEC, "format": "json", "records_path": "result.records"}
    assert DeclarativeSource(spec, cache).fetch(places)["example"]["00001"] == 3.0


@pytest.mark.parametrize(
    "broken,message",
    [
        ({"format": "xml"}, "format must be"),
        ({"direction": "up"}, "direction must be"),
        ({"aggregate": "average"}, "aggregate must be"),
    ],
)
def test_a_malformed_spec_fails_at_construction(broken, message, tmp_path):
    """A model-authored spec must fail immediately, not produce an empty metric."""
    with pytest.raises(ValueError, match=message):
        DeclarativeSource({**SPEC, **broken}, Cache(tmp_path / "c"))


def test_a_spec_missing_fields_names_them(tmp_path):
    """The error has to say what to add."""
    with pytest.raises(ValueError, match="value_column"):
        DeclarativeSource(
            {k: v for k, v in SPEC.items() if k != "value_column"}, Cache(tmp_path / "c")
        )
