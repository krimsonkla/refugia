"""The place universe decides what every later step is even allowed to consider.

Both inputs are Census reference files that change shape between vintages -- a
renamed column, a moved header row, a state code that lost its leading zero -- and
the failure mode is never an exception. It is a smaller universe, or a county
joined to the wrong metro, carried silently through fetch, scoring and the page.

Tested by seeding the cache rather than by stubbing a client, so what runs is the
code that runs in production, parser and join included.
"""

import io

import openpyxl
import pytest

from refugia.places.registry import CENTROIDS_URL, DELINEATION_URL, PlaceRegistry
from refugia.store.cache import Cache

# Real column names and a real row shape, trimmed to the columns the parser reads.
CENTROID_HEADER = "STATEFP,COUNTYFP,COUNAME,STNAME,POPULATION,LATITUDE,LONGITUDE"
CENTROIDS = "\n".join(
    [
        CENTROID_HEADER,
        "6,37,Los Angeles,California,10014009,34.043360,-118.251160",
        "41,17,Deschutes,Oregon,198253,44.077406,-121.348514",
        "30,55,McCone,Montana,1723,47.645537,-105.795530",
    ]
)

DELINEATION_COLUMNS = [
    "CBSA Code",
    "CBSA Title",
    "Metropolitan/Micropolitan Statistical Area",
    "FIPS State Code",
    "FIPS County Code",
]
DELINEATION_ROWS = [
    ["31080", "Los Angeles-Long Beach-Anaheim, CA", "Metropolitan Statistical Area", "06", "037"],
    ["13460", "Bend, OR", "Metropolitan Statistical Area", "41", "017"],
    ["21580", "Elko, NV", "Micropolitan Statistical Area", "32", "007"],
]


def _delineation_bytes(rows=None, preamble: int = 2, columns=None) -> bytes:
    """An xlsx shaped like the real delineation file, header row and all.

    The real file opens with a title and a blank line before the header, which is
    why the parser hunts for the header rather than assuming row one.
    """
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for _ in range(preamble):
        sheet.append(["Core Based Statistical Areas, March 2023"])
    sheet.append(columns or DELINEATION_COLUMNS)
    for row in rows if rows is not None else DELINEATION_ROWS:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture(name="seeded")
def _seeded(tmp_path):
    """A cache already holding both reference files, so nothing reaches out."""

    def seed(centroids: str = CENTROIDS, delineation: bytes | None = None) -> Cache:
        cache = Cache(tmp_path / "cache")
        cache.write("census-cenpop2020-county", centroids.encode("utf-8"))
        cache.write(
            "census-cbsa-list1-2023",
            _delineation_bytes() if delineation is None else delineation,
            ".xlsx",
        )
        return cache

    return seed


def test_the_default_universe_is_the_counties_inside_a_cbsa(seeded):
    """`metro_micro` is the default because a county with no town in it has no
    housing market, no city and no one to be near."""
    places = PlaceRegistry.load(seeded()).places
    assert [p.fips for p in places] == ["06037", "41017"]
    assert all(p.cbsa is not None for p in places)


def test_metro_narrows_further_and_all_keeps_everything(seeded):
    """Each universe is a strict subset of the one before it."""
    micro_too = _delineation_bytes(
        rows=[
            *DELINEATION_ROWS[:1],
            ["13460", "Bend, OR", "Micropolitan Statistical Area", "41", "017"],
        ]
    )
    assert [
        p.fips for p in PlaceRegistry.load(seeded(delineation=micro_too), universe="metro").places
    ] == ["06037"]
    assert [p.fips for p in PlaceRegistry.load(seeded(), universe="all").places] == [
        "06037",
        "30055",
        "41017",
    ]


def test_a_county_outside_every_cbsa_survives_only_in_all(seeded):
    """McCone County is the case the universe exists to decide about."""
    everywhere = PlaceRegistry.load(seeded(), universe="all")
    mccone = everywhere.get("30055")
    assert mccone is not None and mccone.cbsa is None
    assert PlaceRegistry.load(seeded()).get("30055") is None


def test_an_unknown_universe_is_refused_before_anything_is_downloaded(tmp_path):
    """An empty cache would fail on the network; the guard has to come first."""
    with pytest.raises(ValueError, match="universe must be one of"):
        PlaceRegistry.load(Cache(tmp_path), universe="rural")


def test_fips_codes_regain_the_zeros_the_csv_dropped(seeded):
    """The centroid file stores the codes as numbers, so California is 6 and Los
    Angeles County is 37. Every other file in the project keys on 06037, and a join
    against 637 matches nothing at all -- silently, since a missing join is a
    missing metric and a missing metric is only a coverage figure.
    """
    registry = PlaceRegistry.load(seeded())
    assert registry.get("06037") is not None
    assert registry.get("637") is None
    assert registry.get("6037") is None


def test_the_delineation_file_is_padded_too_whatever_the_vintage_stored(seeded):
    """Both files are joined on FIPS and both store the codes as numbers in some
    vintages and as text in others. Padding one side only is worse than padding
    neither: the join silently matches nothing and every county loses its CBSA,
    which under the default universe empties the candidate set.
    """
    unpadded = _delineation_bytes(
        rows=[
            [
                "31080",
                "Los Angeles-Long Beach-Anaheim, CA",
                "Metropolitan Statistical Area",
                "6",
                "37",
            ]
        ]
    )
    registry = PlaceRegistry.load(seeded(delineation=unpadded))
    los_angeles = registry.get("06037")
    assert los_angeles is not None and los_angeles.cbsa is not None
    assert los_angeles.cbsa.code == "31080"


def test_a_byte_order_mark_does_not_eat_the_first_column(seeded):
    """The Census serves this file with a BOM. Decoded as plain utf-8 the first
    column is named "\\ufeffSTATEFP" and every FIPS lookup raises KeyError."""
    with_bom = "﻿" + CENTROIDS
    assert PlaceRegistry.load(seeded(centroids=with_bom)).get("06037") is not None


def test_the_header_is_found_wherever_the_vintage_put_it(seeded):
    """The delineation file opens with title rows, and how many has changed."""
    for preamble in (0, 1, 5):
        registry = PlaceRegistry.load(seeded(delineation=_delineation_bytes(preamble=preamble)))
        bend = registry.get("41017")
        assert bend is not None and bend.cbsa is not None
        assert bend.cbsa.name == "Bend, OR", f"preamble of {preamble} rows"


def test_metropolitan_and_micropolitan_are_told_apart(seeded):
    """They differ by one word inside one cell, and `metro` depends on the split."""
    registry = PlaceRegistry.load(seeded(), universe="all")
    assert registry.get("06037").cbsa.kind == "metro"
    micro = _delineation_bytes(
        rows=[["21580", "Elko, NV", "Micropolitan Statistical Area", "30", "055"]]
    )
    assert PlaceRegistry.load(seeded(delineation=micro), universe="all").get("30055").cbsa.kind == (
        "micro"
    )


def test_a_delineation_row_missing_its_codes_is_skipped_not_guessed(seeded):
    """The real file ends with footnotes, which arrive as rows with empty cells."""
    ragged = _delineation_bytes(rows=[*DELINEATION_ROWS, ["", "", "", "", ""], [None] * 5])
    assert PlaceRegistry.load(seeded(delineation=ragged)).get("41017") is not None


def test_places_come_back_in_fips_order_however_the_file_was_ordered(seeded):
    """Everything downstream joins on position in places at least once."""
    shuffled = "\n".join(
        [
            CENTROID_HEADER,
            "41,17,Deschutes,Oregon,198253,44.077406,-121.348514",
            "6,37,Los Angeles,California,10014009,34.043360,-118.251160",
        ]
    )
    assert [p.fips for p in PlaceRegistry.load(seeded(centroids=shuffled)).places] == [
        "06037",
        "41017",
    ]


def test_the_centroid_is_the_population_weighted_one(seeded):
    """Vegetation is sampled at this coordinate. The area centroid of a large
    western county sits in rangeland nobody lives in, and would describe a
    landscape the candidate would never breathe -- which is why this file is the
    one used, and why the numbers have to survive the parse as floats.
    """
    deschutes = PlaceRegistry.load(seeded()).get("41017")
    assert (deschutes.lat, deschutes.lon) == (44.077406, -121.348514)
    assert deschutes.population == 198253


def test_length_and_lookup_agree_with_the_places_tuple(seeded):
    """`get` is a different index from `places`, and both are used."""
    registry = PlaceRegistry.load(seeded(), universe="all")
    assert len(registry) == len(registry.places) == 3
    assert registry.get("nope") is None


def test_a_cached_reference_file_is_not_downloaded_again(seeded, monkeypatch):
    """Two Census files on every run, for a universe that changes once a year."""

    def explode(*_args, **_kwargs):
        raise AssertionError("the cache was seeded; nothing should reach the network")

    monkeypatch.setattr("httpx.get", explode)
    assert len(PlaceRegistry.load(seeded())) == 2
    assert CENTROIDS_URL.startswith("https://") and DELINEATION_URL.startswith("https://")
