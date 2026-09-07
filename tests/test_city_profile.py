"""The city panel's table: health at the place grain, vegetation resampled per town.

Both halves fail quietly. A place whose health row is absent falls back to its
county's figures, which is correct; a place whose row is *misread* shows a number
that looks like a measurement of the town and is a measurement of nothing. The
vegetation half runs a thread pool over thousands of towns, where one unreachable
sample must not cost the other four thousand.

The health release is cached whole, so it is seeded. The paging tests stub the
endpoint, because paging is the thing being tested.
"""

import json

import httpx
import pytest

from refugia.artifact.city_profile import MAX_PAGES, PLACES_COLUMNS, CityProfile
from refugia.retry import Retry
from refugia.store.cache import Cache

CACHE_KEY = "cdc-places-place-2025"
PAGE = 20000

FORT_COLLINS = {"geoid": "0827425", "lat": 40.5853, "lon": -105.0844}
LOVELAND = {"geoid": "0845255", "lat": 40.4166, "lon": -105.0621}


class _Vegetation:
    """A sampler that answers from a table, and records what it was asked."""

    def __init__(self, answers=None, raises=()):
        self.answers = answers or {}
        self.raises = set(raises)
        self.asked: list[str] = []

    def cover_at(self, identifier: str, lat: float, lon: float) -> dict[str, float]:
        self.asked.append(identifier)
        if identifier in self.raises:
            raise httpx.ConnectError("no route to host")
        return self.answers.get(identifier, {})


def _row(geoid: str, **measures) -> dict:
    """One place row in the shape the release publishes: wide, all strings."""
    inverted = {v: k for k, v in PLACES_COLUMNS.items()}
    return {"placefips": geoid, **{inverted[k]: str(v) for k, v in measures.items()}}


def _full_page() -> list[dict]:
    return [_row(f"41{i:05d}", depression=1.0) for i in range(PAGE)]


def _responds(payload):
    def answer(*_args, **_kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", "https://x"))

    return answer


@pytest.fixture(name="seeded")
def _seeded(tmp_path):
    def seed(rows) -> Cache:
        cache = Cache(tmp_path / "cache")
        cache.write(CACHE_KEY, json.dumps(rows).encode(), ".json")
        return cache

    return seed


def test_health_measures_arrive_per_city_keyed_on_the_marker_geoid(seeded):
    """The place FIPS is the same GEOID the markers carry, which is what lets the
    panel join a town to its own figures without a second identifier."""
    cache = seeded([_row("0827425", depression=21.5, asthma=10.2)])
    built = CityProfile(cache, vegetation=_Vegetation()).build({"08069": [FORT_COLLINS]})
    assert built["0827425"] == {"depression": 21.5, "asthma": 10.2}


def test_a_city_the_release_does_not_cover_is_absent_rather_than_zero(seeded):
    """Absent means the panel falls back to the county, which is honest. Zero
    would read as the healthiest town in the country."""
    cache = seeded([_row("0827425", depression=21.5)])
    built = CityProfile(cache, vegetation=_Vegetation()).build({"08069": [FORT_COLLINS, LOVELAND]})
    assert "0845255" not in built


def test_a_blank_measure_is_skipped_rather_than_read_as_zero(seeded):
    """The release publishes an empty string for a measure it suppressed."""
    cache = seeded(
        [{"placefips": "0827425", "depression_crudeprev": "", "casthma_crudeprev": "9.1"}]
    )
    built = CityProfile(cache, vegetation=_Vegetation()).build({"08069": [FORT_COLLINS]})
    assert built["0827425"] == {"asthma": 9.1}


def test_a_measure_that_will_not_parse_does_not_lose_the_rest_of_the_row(seeded):
    """Every value in this release is a string until it parses."""
    cache = seeded(
        [{"placefips": "0827425", "depression_crudeprev": "n/a", "casthma_crudeprev": "9.1"}]
    )
    built = CityProfile(cache, vegetation=_Vegetation()).build({"08069": [FORT_COLLINS]})
    assert built["0827425"] == {"asthma": 9.1}


def test_a_row_with_nothing_usable_is_left_out_entirely(seeded):
    """An empty dict against a geoid is a city the panel would show as measured."""
    cache = seeded([{"placefips": "0827425"}])
    assert CityProfile(cache, vegetation=_Vegetation()).build({"08069": [FORT_COLLINS]}) == {}


def test_vegetation_is_resampled_at_the_town_rather_than_the_county(seeded):
    """Within one county the sagebrush share runs from a twentieth to a quarter of
    the land, so a town inherits nothing useful from its county here."""
    vegetation = _Vegetation({"city-0827425": {"sagebrush_cover": 4.2}})
    built = CityProfile(seeded([]), vegetation=vegetation).build({"08069": [FORT_COLLINS]})
    assert built["0827425"]["sagebrush_cover"] == pytest.approx(4.2)
    assert vegetation.asked == ["city-0827425"]


def test_the_two_halves_are_merged_onto_one_city(seeded):
    """The panel reads one row per town, not two."""
    cache = seeded([_row("0827425", depression=21.5)])
    vegetation = _Vegetation({"city-0827425": {"juniper_cover": 8.0}})
    built = CityProfile(cache, vegetation=vegetation).build({"08069": [FORT_COLLINS]})
    assert built["0827425"] == {"depression": 21.5, "juniper_cover": 8.0}


def test_one_unreachable_town_does_not_cost_the_others_their_vegetation(seeded):
    """Four thousand samples over a thread pool; one reset must not end the build."""
    vegetation = _Vegetation({"city-0845255": {"juniper_cover": 3.0}}, raises={"city-0827425"})
    built = CityProfile(seeded([]), vegetation=vegetation).build(
        {"08069": [FORT_COLLINS, LOVELAND]}
    )
    assert built == {"0845255": {"juniper_cover": 3.0}}


def test_a_town_with_no_coordinate_is_not_sampled(seeded):
    """A marker can reach here without one; sampling at None is a crash."""
    vegetation = _Vegetation()
    CityProfile(seeded([]), vegetation=vegetation).build(
        {"08069": [{"geoid": "0827425", "lat": None, "lon": None}]}
    )
    assert vegetation.asked == []


def test_towns_from_every_county_are_built_in_one_pass(seeded):
    """The panel is built once for the whole page, not per county."""
    cache = seeded([_row("0827425", depression=1.0), _row("0845255", depression=2.0)])
    built = CityProfile(cache, vegetation=_Vegetation()).build(
        {"08069": [FORT_COLLINS], "08013": [LOVELAND]}
    )
    assert set(built) == {"0827425", "0845255"}


def test_the_cached_release_is_not_downloaded_again(seeded, monkeypatch):
    """Six megabytes, on every publish, for a release that changes once a year."""

    def explode(*_args, **_kwargs):
        raise AssertionError("the release was cached; nothing should reach the network")

    monkeypatch.setattr(httpx, "get", explode)
    cache = seeded([_row("0827425", depression=21.5)])
    assert CityProfile(cache, vegetation=_Vegetation()).build({"08069": [FORT_COLLINS]})


def test_the_release_is_paged_until_a_short_page_arrives(tmp_path, monkeypatch):
    """The endpoint caps a page at 20,000 rows and the release is larger."""
    pages = [_full_page(), [_row("0827425", depression=2.0)]]
    seen = []

    def answer(*_args, **kwargs):
        seen.append(kwargs["params"]["$offset"])
        return httpx.Response(
            200, json=pages[len(seen) - 1], request=httpx.Request("GET", "https://x")
        )

    monkeypatch.setattr(httpx, "get", answer)
    built = CityProfile(Cache(tmp_path), vegetation=_Vegetation(), retry=Retry(1)).build(
        {"08069": [FORT_COLLINS]}
    )
    assert seen == [0, PAGE]
    assert built["0827425"]["depression"] == pytest.approx(2.0)


def test_paging_is_bounded_so_a_wrong_query_cannot_run_forever(tmp_path, monkeypatch):
    """A query that never returns a short page would page until something else broke."""
    monkeypatch.setattr(httpx, "get", _responds(_full_page()))
    profile = CityProfile(Cache(tmp_path), vegetation=_Vegetation(), retry=Retry(1))
    with pytest.raises(ValueError, match=f"more than {MAX_PAGES} pages"):
        profile._download()


def test_an_envelope_instead_of_a_list_is_refused(tmp_path, monkeypatch):
    """A 200 carrying a dict would extend the rows with its keys and then run the
    loop until something further down failed on a string."""
    monkeypatch.setattr(httpx, "get", _responds({"message": "the query was rejected"}))
    profile = CityProfile(Cache(tmp_path), vegetation=_Vegetation(), retry=Retry(1))
    with pytest.raises(ValueError, match="expected a list of rows"):
        profile._download()


def test_an_empty_release_is_never_cached(tmp_path, monkeypatch):
    """`[]` is valid JSON and reads back as "no city has any of this", for good."""
    monkeypatch.setattr(httpx, "get", _responds([]))
    cache = Cache(tmp_path)
    CityProfile(cache, vegetation=_Vegetation(), retry=Retry(1)).build({"08069": [FORT_COLLINS]})
    assert not cache.has(CACHE_KEY, ".json")


def test_only_the_columns_the_panel_uses_are_requested(tmp_path, monkeypatch):
    """The release is wide enough that selecting everything is the difference
    between six megabytes and a hundred."""
    selects = []

    def answer(*_args, **kwargs):
        selects.append(kwargs["params"]["$select"])
        return httpx.Response(200, json=[], request=httpx.Request("GET", "https://x"))

    monkeypatch.setattr(httpx, "get", answer)
    CityProfile(Cache(tmp_path), vegetation=_Vegetation(), retry=Retry(1))._download()
    assert selects[0].split(",") == ["placefips", *PLACES_COLUMNS]
