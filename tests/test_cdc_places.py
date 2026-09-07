"""CDC PLACES supplies five of the twenty-one metrics and had no test at all.

It is the adapter most worth covering first: it pages, it is the one a single
dropped connection used to cost outright, and since a failing source now costs only
its own metrics, a silent partial result here is a quiet loss of a quarter of them.
"""

import json

import httpx
import pytest

from refugia.metrics.sources.cdc_places import CdcPlacesSource
from refugia.places.place import Place
from refugia.retry import Retry
from refugia.store.cache import Cache


class _Api:
    """Answers each request with the next queued page, and counts the calls."""

    def __init__(self, *pages) -> None:
        self.pages = list(pages)
        self.offsets: list[int] = []

    def get(self, url, **kwargs):
        self.offsets.append(kwargs["params"]["$offset"])
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return httpx.Response(
            200, json=page, request=httpx.Request("GET", url, params=kwargs["params"])
        )


def _places(*fips: str) -> tuple[Place, ...]:
    """fetch keeps only the places in the universe it was handed."""
    return tuple(Place(fips=f, name=f, state="S", lat=0.0, lon=0.0, population=1) for f in fips)


def _rows(count: int, start: int = 0) -> list[dict]:
    return [{"locationid": f"{i:05d}", "data_value": float(i)} for i in range(start, start + count)]


@pytest.fixture
def api(monkeypatch):
    def _install(*pages) -> _Api:
        stub = _Api(*pages)
        monkeypatch.setattr(httpx, "get", stub.get)
        return stub

    return _install


def _source(tmp_path, **kw) -> CdcPlacesSource:
    return CdcPlacesSource(Cache(tmp_path / "c"), measures=("DEPRESSION",), **kw)


def test_a_measure_is_read_and_keyed_by_fips(tmp_path, api):
    api(_rows(3))
    values = _source(tmp_path).fetch(_places("00000", "00001", "00002"))
    assert values["depression"] == {"00000": 0.0, "00001": 1.0, "00002": 2.0}


def test_paging_continues_until_a_short_page(tmp_path, api):
    """Socrata caps a response at 50,000, so a full page means ask again."""
    stub = api(_rows(50000), _rows(2, start=50000))
    values = _source(tmp_path).fetch(_places("00001", "50001"))
    assert stub.offsets == [0, 50000]
    # One row from each page, so the second page was fetched and merged.
    assert values["depression"] == {"00001": 1.0, "50001": 50001.0}


def test_a_row_with_no_value_is_skipped_rather_than_zeroed(tmp_path, api):
    """Missing is not zero, and the engine keeps that distinction."""
    api([{"locationid": "00001", "data_value": ""}, {"locationid": "00002", "data_value": 4.0}])
    values = _source(tmp_path).fetch(_places("00001", "00002"))
    assert values == {"depression": {"00002": 4.0}}


def test_a_second_fetch_reads_the_cache(tmp_path, api):
    stub = api(_rows(1))
    source = _source(tmp_path)
    source.fetch(_places("00000"))
    source.fetch(_places("00000"))
    assert len(stub.offsets) == 1


def test_an_empty_measure_is_not_cached(tmp_path, api):
    """`{}` is valid JSON and would read back as "nowhere has this"."""
    api([], [])
    source = _source(tmp_path)
    assert source.fetch(_places("00001")) == {"depression": {}}
    assert not source._cache.has("cdc-places-DEPRESSION", ".json")


def test_a_dropped_connection_is_retried_rather_than_costing_the_measure(tmp_path, api):
    """This is the failure the shared retry exists for."""
    api(httpx.ConnectError("reset"), _rows(2))
    source = _source(tmp_path, retry=Retry(sleep=lambda _: None))
    assert len(source.fetch(_places("00000", "00001"))["depression"]) == 2


def test_a_moved_endpoint_is_not_retried(tmp_path, api):
    """A 404 will still be a 404 after ten seconds of backoff."""
    request = httpx.Request("GET", "https://example.invalid/x")
    slept: list[float] = []
    api(
        httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))
    )
    with pytest.raises(httpx.HTTPStatusError):
        _source(tmp_path, retry=Retry(sleep=slept.append)).fetch(_places("00001"))
    assert slept == []


def test_an_unknown_measure_is_refused_at_construction(tmp_path):
    """A typo should not become a metric with no data."""
    with pytest.raises(ValueError, match="unknown PLACES measures"):
        CdcPlacesSource(Cache(tmp_path), measures=("NOT_A_MEASURE",))


def test_the_declared_metrics_match_the_requested_measures(tmp_path):
    source = _source(tmp_path)
    assert [m.key for m in source.metrics] == ["depression"]
    assert json.dumps([m.direction for m in source.metrics])
