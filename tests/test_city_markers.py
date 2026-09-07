"""Town markers, and two Census files whose quirks are the whole implementation.

The population estimates carry one row per place *part* within a county, which is
the only Census product tying a place to a county at all -- and the coordinate on
file is the whole place's centre, not the part's. Take every part and Sioux Falls
gets a marker in the next county over, at a point outside it.

Both files come through the cache, so both are seeded. Nothing here stubs a client.
"""

import csv
import io
import zipfile

import httpx
import pytest

from refugia.artifact.city_markers import (
    GAZETTEER_URL,
    POPULATION_URL,
    CityMarkers,
    _clean,
)
from refugia.places.place import Place
from refugia.store.cache import Cache

LARIMER = Place(
    fips="08069", name="Larimer", state="Colorado", lat=40.66, lon=-105.46, population=198253
)
BOULDER = Place(
    fips="08013", name="Boulder", state="Colorado", lat=40.09, lon=-105.36, population=25000
)

POPULATION_COLUMNS = ["SUMLEV", "STATE", "COUNTY", "PLACE", "NAME", "POPESTIMATE2024"]
# SUMLEV 157 is place-within-county; 162 is the whole place, which double-counts.
POPULATION_ROWS = [
    ["157", "08", "069", "27425", "Fort Collins city", "104557"],
    ["157", "08", "069", "45255", "Loveland city", "39000"],
    ["157", "08", "069", "24785", "Estes Park city", "3500"],
    ["157", "08", "069", "06640", "Berthoud town", "2600"],
    ["162", "08", "000", "27425", "Fort Collins city", "104557"],
]

GAZETTEER_COLUMNS = ["USPS", "GEOID", "NAME", "INTPTLAT", "INTPTLONG    "]
GAZETTEER_ROWS = [
    ["CO", "0827425", "Fort Collins city", "40.5853", "-105.0844"],
    ["CO", "0845255", "Loveland city", "40.4166", "-105.0621"],
    ["CO", "0824785", "Estes Park city", "40.3772", "-105.5217"],
    ["CO", "0806640", "Berthoud town", "40.3083", "-105.0811"],
]

# scale, offset x, offset y -- the same shape CountyShapes hands over.
TRANSFORM = (1.0, 0.0, 0.0)


def _population_csv(rows=None, columns=None) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns or POPULATION_COLUMNS)
    writer.writerows(rows if rows is not None else POPULATION_ROWS)
    return buffer.getvalue().encode("latin-1")


def _gazetteer_zip(rows=None, columns=None) -> bytes:
    body = io.StringIO()
    writer = csv.writer(body, delimiter="\t", lineterminator="\n")
    writer.writerow(columns or GAZETTEER_COLUMNS)
    writer.writerows(rows if rows is not None else GAZETTEER_ROWS)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("2024_Gaz_place_national.txt", body.getvalue())
    return archive.getvalue()


@pytest.fixture(name="seeded")
def _seeded(tmp_path):
    def seed(population: bytes | None = None, gazetteer: bytes | None = None) -> Cache:
        cache = Cache(tmp_path / "cache")
        cache.write(POPULATION_URL, population or _population_csv(), ".csv")
        cache.write(GAZETTEER_URL, gazetteer or _gazetteer_zip(), ".zip")
        return cache

    return seed


def test_the_biggest_towns_in_a_county_come_back_biggest_first(seeded):
    """The page labels the first few, so the order is what is actually shown."""
    markers = CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)
    assert [c["name"] for c in markers["08069"]] == ["Fort Collins", "Loveland", "Estes Park"]


def test_only_the_first_few_towns_per_county_are_kept(seeded):
    """Four towns were seeded for one county; the map cannot label them all."""
    assert len(CityMarkers(seeded(), per_county=2).for_places((LARIMER,), TRANSFORM)["08069"]) == 2


def test_the_legal_type_is_dropped_from_the_label(seeded):
    """ "Fort Collins city" is a Census legal name, not what anyone calls the place."""
    assert (
        CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"][0]["name"]
        == "Fort Collins"
    )


def test_a_county_that_was_not_asked_for_is_not_returned(seeded):
    """The universe decides the candidates, and the markers must not widen it."""
    assert set(CityMarkers(seeded()).for_places((BOULDER,), TRANSFORM)) == set()


def test_a_place_split_across_counties_is_counted_once_in_the_larger_share(seeded):
    """The coordinate on file is the whole place's centre, so keeping both parts
    puts a marker for the smaller share at a point outside its own county."""
    split = [
        ["157", "46", "099", "59020", "Sioux Falls city", "190000"],
        ["157", "46", "083", "59020", "Sioux Falls city", "2000"],
    ]
    gazetteer = _gazetteer_zip(rows=[["SD", "4659020", "Sioux Falls city", "43.5378", "-96.7320"]])
    minnehaha = Place(fips="46099", name="Minnehaha", state="SD", lat=43.6, lon=-96.7, population=1)
    lincoln = Place(fips="46083", name="Lincoln", state="SD", lat=43.2, lon=-96.7, population=1)
    markers = CityMarkers(
        seeded(population=_population_csv(split), gazetteer=gazetteer)
    ).for_places((minnehaha, lincoln), TRANSFORM)
    assert [c["name"] for c in markers["46099"]] == ["Sioux Falls"]
    assert "46083" not in markers


def test_whole_place_rows_are_ignored_so_towns_are_not_counted_twice(seeded):
    """The same file carries a summary row per place with no county on it."""
    names = [c["name"] for c in CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"]]
    assert names.count("Fort Collins") == 1


def test_a_row_whose_population_will_not_parse_is_skipped(seeded):
    """The estimates use (X) for a suppressed figure rather than leaving it blank."""
    rows = [*POPULATION_ROWS[:1], ["157", "08", "069", "45255", "Loveland city", "(X)"]]
    markers = CityMarkers(seeded(population=_population_csv(rows))).for_places(
        (LARIMER,), TRANSFORM
    )
    assert [c["name"] for c in markers["08069"]] == ["Fort Collins"]


def test_a_town_with_no_coordinate_is_left_off_the_map(seeded):
    """A marker at (0, 0) is a town in the Gulf of Guinea."""
    gazetteer = _gazetteer_zip(rows=GAZETTEER_ROWS[1:])
    markers = CityMarkers(seeded(gazetteer=gazetteer)).for_places((LARIMER,), TRANSFORM)
    assert "Fort Collins" not in [c["name"] for c in markers["08069"]]


def test_the_gazetteer_header_is_padded_and_has_to_be_stripped(seeded):
    """The final column arrives as "INTPTLONG    ". Indexed unstripped, every
    lookup raises KeyError and no town gets a coordinate at all."""
    assert GAZETTEER_COLUMNS[-1] != GAZETTEER_COLUMNS[-1].strip(), "the fixture must keep the pad"
    assert CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"]


def test_a_truncated_gazetteer_row_is_skipped_rather_than_raising(seeded):
    """The file ends with a short line often enough to matter."""
    rows = [*GAZETTEER_ROWS, ["CO", "4100000"]]
    assert CityMarkers(seeded(gazetteer=_gazetteer_zip(rows=rows))).for_places(
        (LARIMER,), TRANSFORM
    )["08069"]


def test_an_unparseable_coordinate_is_skipped_rather_than_raising(seeded):
    """Every value in this file is text until it parses."""
    rows = [["CO", "0827425", "Fort Collins city", "", ""], *GAZETTEER_ROWS[1:]]
    names = [
        c["name"]
        for c in CityMarkers(seeded(gazetteer=_gazetteer_zip(rows=rows))).for_places(
            (LARIMER,), TRANSFORM
        )["08069"]
    ]
    assert "Fort Collins" not in names and "Loveland" in names


def test_a_marker_carries_both_the_map_position_and_the_real_coordinate(seeded):
    """x and y draw it; lat and lon are what the city panel resamples at."""
    town = CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"][0]
    assert town["lat"] == pytest.approx(40.5853) and town["lon"] == pytest.approx(-105.0844)
    assert isinstance(town["x"], float) and isinstance(town["y"], float)


def test_the_transform_moves_and_scales_the_projected_point(seeded):
    """The markers and the county outlines have to land in the same coordinate
    space, and they are projected by different code."""
    plain = CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"][0]
    moved = CityMarkers(seeded()).for_places((LARIMER,), (2.0, 100.0, 50.0))["08069"][0]
    assert moved["x"] == pytest.approx(plain["x"] * 2 + 100.0, abs=0.11)
    assert moved["y"] == pytest.approx(plain["y"] * 2 + 50.0, abs=0.11)


def test_the_place_geoid_travels_with_the_marker(seeded):
    """It is the join key for everything published per town, the city panel first."""
    assert CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"][0]["geoid"] == (
        "0827425"
    )


def test_neither_census_file_is_downloaded_twice(seeded, monkeypatch):
    """Eight megabytes between them, for a page that is rebuilt on every publish."""

    def explode(*_args, **_kwargs):
        raise AssertionError("both files were seeded; nothing should reach the network")

    monkeypatch.setattr(httpx, "get", explode)
    assert CityMarkers(seeded()).for_places((LARIMER,), TRANSFORM)["08069"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Fort Collins city", "Fort Collins"),
        # The suffixes stack: a split place is published with both.
        ("Portland city (pt.)", "Portland"),
        ("Athens-Clarke County unified government (balance)", "Athens-Clarke County"),
        # Case is what separates the legal type from the name.
        ("Carson City", "Carson City"),
        # Longest first, or "urban county" loses only its second word.
        ("Lexington-Fayette urban county", "Lexington-Fayette"),
        ("Nashville-Davidson metropolitan government (balance)", "Nashville-Davidson"),
        # A name that is nothing but a suffix keeps the original rather than
        # becoming an empty label on the map.
        ("city", "city"),
    ],
)
def test_the_census_legal_type_is_stripped_without_eating_the_name(raw, expected):
    """These are the real shapes, and each one was a wrong label on the map."""
    assert _clean(raw) == expected
