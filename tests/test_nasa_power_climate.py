"""Four of the twenty-one metrics come from here, and all four are conversions.

The failure that matters is not an exception. It is a number in the wrong unit, a
fill value scored as a temperature, or a county silently taking the reading of a
grid cell in the sea -- each of which produces a plausible ranking that is wrong.

The adapter is cache-first, so seeding the cache runs the real `fetch`, the real
tiling and the real conversions with nothing reaching the network. Only the tests
that are about the endpoint's own misbehaviour stub a response, because a 200
carrying an error body cannot be expressed as a cached payload.
"""

import json

import httpx
import pytest

from refugia.metrics.sources.nasa_power_climate import (
    PARAMETERS,
    TILE,
    NasaPowerClimateSource,
)
from refugia.places.place import Place
from refugia.store.cache import Cache

BEND = Place(
    fips="41017", name="Deschutes", state="Oregon", lat=44.08, lon=-121.35, population=198253
)
MIAMI = Place(fips="12086", name="Miami-Dade", state="Florida", lat=25.61, lon=-80.5, population=1)


def _seed(cache: Cache, corner: tuple[float, float], values: dict[str, dict]) -> None:
    """Write one tile per parameter, in the shape `_tile` reads back."""
    lat, lon = corner
    for parameter, points in values.items():
        cache.write(
            f"power-{parameter}-{lat:g}-{lon:g}-t{TILE:g}",
            json.dumps({f"{a},{b}": v for (a, b), v in points.items()}).encode(),
            ".json",
        )


def _flat(value: float, at: tuple[float, float] = (44.0, -121.0)) -> dict:
    return {at: value}


def _feature(lon: float, lat: float, parameter: str, value: float) -> dict:
    """One grid point in the shape the service actually answers with."""
    return {
        "geometry": {"coordinates": [lon, lat, 0.0]},
        "properties": {"parameter": {parameter: {"ANN": value}}},
    }


@pytest.fixture(name="cache")
def _cache(tmp_path):
    return Cache(tmp_path)


def test_temperatures_arrive_in_fahrenheit_and_cloud_becomes_clear_sky(cache):
    """POWER answers in Celsius and in cloud amount; the page publishes neither."""
    _seed(
        cache,
        (40.0, -125.0),
        {
            "T2M_MAX": _flat(40.0),
            "T2M_MIN": _flat(-10.0),
            "CLOUD_AMT": _flat(30.0),
            "RH2M": _flat(55.0),
        },
    )
    values = NasaPowerClimateSource(cache).fetch((BEND,))
    assert values["hottest_day"]["41017"] == pytest.approx(104.0)
    assert values["coldest_day"]["41017"] == pytest.approx(14.0)
    # Cloud amount is what the service reports; "clear sky" is its complement.
    assert values["sunshine"]["41017"] == pytest.approx(70.0)
    assert values["humidity"]["41017"] == pytest.approx(55.0)


def test_the_fill_value_never_becomes_a_reading(cache, monkeypatch):
    """POWER marks cells it has no data for, chiefly open ocean, with -999. Scored
    as a temperature it is the coldest place in the country by eight hundred
    degrees, and being lower_better it would win a cold-averse search outright.

    Filtered where the response is parsed rather than where the tile is read back,
    so a fill value never reaches the cache in the first place -- which is the same
    rule as never caching an empty result, for the same reason.
    """
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(
            200,
            json={
                "features": [
                    _feature(-80.5, 25.5, "T2M_MIN", -999.0),
                    _feature(-81.5, 25.5, "T2M_MIN", 12.5),
                ]
            },
            request=httpx.Request("GET", "https://x"),
        ),
    )
    points = NasaPowerClimateSource(cache, retries=1)._request_once("T2M_MIN", 25.0, -85.0)
    assert points == {(25.5, -81.5): 12.5}


def test_a_place_missing_one_parameter_is_reported_for_none_of_them(cache):
    """Three of four would publish a place whose climate is partly described, and
    coverage counts the metric as present. Either the climate is known or it is not.
    """
    _seed(
        cache,
        (40.0, -125.0),
        # T2M_MIN cached as a tile the service had nothing for, which is what an
        # ocean tile looks like on disk.
        {"T2M_MAX": _flat(40.0), "T2M_MIN": {}, "CLOUD_AMT": _flat(30.0), "RH2M": _flat(55.0)},
    )
    values = NasaPowerClimateSource(cache).fetch((BEND,))
    assert all(not v for v in values.values()), values


def test_the_nearest_search_widens_past_an_empty_cell(cache):
    """A coastal centroid's own whole-degree cell can hold nothing but sea, and
    reporting no data there would drop the county rather than read the cell inland.
    """
    inland = (45.4, -122.4)
    _seed(
        cache,
        (40.0, -125.0),
        {p: _flat(20.0 if p != "CLOUD_AMT" else 10.0, inland) for p in PARAMETERS},
    )
    coastal = Place(
        fips="41051", name="Multnomah", state="Oregon", lat=44.6, lon=-121.6, population=1
    )
    assert "41051" in NasaPowerClimateSource(cache).fetch((coastal,))["humidity"]


def test_the_closest_point_wins_when_several_are_in_range(cache):
    """Every parameter is sampled by the same search, so a wrong tie-break moves
    all four metrics for that place at once."""
    _seed(
        cache,
        (40.0, -125.0),
        {p: {(44.1, -121.3): 10.0, (43.2, -120.1): 90.0} for p in PARAMETERS},
    )
    assert NasaPowerClimateSource(cache).fetch((BEND,))["humidity"]["41017"] == pytest.approx(10.0)


def test_places_are_covered_by_tiles_on_a_fixed_lattice():
    """The lattice is what makes the cache reusable between runs: a tile keyed by
    where a county happens to be would never be hit twice."""
    tiles = NasaPowerClimateSource._tiles((BEND, MIAMI))
    assert tiles == sorted(tiles)
    for place in (BEND, MIAMI):
        assert any(
            lat <= place.lat < lat + TILE and lon <= place.lon < lon + TILE for lat, lon in tiles
        ), place.name


def test_two_places_in_one_tile_are_downloaded_once():
    """Eighteen hundred counties over a few hundred tiles is the whole point."""
    neighbour = Place(
        fips="41013", name="Crook", state="Oregon", lat=44.14, lon=-120.36, population=1
    )
    assert len(NasaPowerClimateSource._tiles((BEND, neighbour))) == 1


def test_a_cached_tile_is_never_downloaded_again(cache, monkeypatch):
    """Cache-first is the difference between a re-run and an eighty-minute crawl."""

    def explode(*_args, **_kwargs):
        raise AssertionError("the tile was cached; nothing should reach the network")

    monkeypatch.setattr(httpx, "get", explode)
    _seed(cache, (40.0, -125.0), {p: _flat(20.0) for p in PARAMETERS})
    assert NasaPowerClimateSource(cache).fetch((BEND,))["humidity"]["41017"] == pytest.approx(20.0)


def test_a_two_hundred_carrying_an_error_body_is_not_read_as_data(cache, monkeypatch):
    """The endpoint answers 200 with a messages array instead of features, which
    `raise_for_status` cannot see. Treated as data it yields no points, and an
    empty tile is indistinguishable from a tile genuinely over the sea.
    """
    body = {"messages": ["Parameter T2M_MAX not available for this community"]}
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(200, json=body, request=httpx.Request("GET", "https://x")),
    )
    source = NasaPowerClimateSource(cache, retries=1)
    with pytest.raises(ValueError, match="not available"):
        source._request_once("T2M_MAX", 40.0, -125.0)


def test_a_failing_tile_is_recorded_and_the_others_still_arrive(cache, monkeypatch):
    """One unreachable tile must not cost the rest of the country its climate."""
    _seed(cache, (40.0, -125.0), {p: _flat(20.0) for p in PARAMETERS})

    def only_cached(*_args, **_kwargs):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "get", only_cached)
    source = NasaPowerClimateSource(cache, retries=1)
    values = source.fetch((BEND, MIAMI))
    assert values["humidity"]["41017"] == pytest.approx(20.0)
    assert "12086" not in values["humidity"]
    # One entry per parameter for the tile that could not be had, naming both.
    assert len(source.failures) == len(PARAMETERS)
    assert all("@" in name and message for name, message in source.failures)


def test_an_empty_tile_is_not_written_to_the_cache(cache, monkeypatch):
    """A cached emptiness is indistinguishable from data and survives every later
    run, which is the project's oldest rule and the one that cost the most."""
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *a, **k: httpx.Response(
            200, json={"features": []}, request=httpx.Request("GET", "https://x")
        ),
    )
    source = NasaPowerClimateSource(cache, retries=1)
    assert source._tile("T2M_MAX", (40.0, -125.0)) == {}
    assert not cache.has(f"power-T2M_MAX-40--125-t{TILE:g}", ".json")


def test_every_climate_metric_is_declared_with_a_direction_and_a_source(cache):
    """A metric with no direction cannot be normalised, and one with no source
    cannot be credited in the page footer."""
    metrics = NasaPowerClimateSource(cache).metrics
    assert {m.key for m in metrics} == {"sunshine", "hottest_day", "coldest_day", "humidity"}
    for metric in metrics:
        assert metric.direction in {"higher_better", "lower_better"}
        assert metric.source and metric.unit and metric.description


def test_the_temperature_metrics_say_that_milder_is_an_assumption(cache):
    """Direction is a value judgement here in a way it is not for air pollution,
    and a reader who wants real winters has to be told the ranking disagrees."""
    metrics = {m.key: m for m in NasaPowerClimateSource(cache).metrics}
    assert "milder is better" in metrics["coldest_day"].description
    assert "milder is better" in metrics["hottest_day"].description
