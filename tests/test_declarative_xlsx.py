"""Workbook parsing, because much county data is published only as xlsx."""

import openpyxl
import pytest

from refugia.places.place import Place

from refugia.metrics.sources.declarative import DeclarativeSource
from refugia.store.cache import Cache

SPEC = {
    "key": "risk",
    "label": "Risk",
    "unit": "percentile",
    "direction": "lower_better",
    "category": "hazard",
    "description": "d",
    "source": "s",
    "url": "https://example.invalid/x.xlsx",
    "format": "xlsx",
    "sheet": "Counties",
    "fips_column": "GEOID",
    "value_column": "RISK",
}


@pytest.fixture
def workbook_bytes(tmp_path):
    """A two-sheet workbook where the wanted data is not on the first sheet."""
    book = openpyxl.Workbook()
    decoy = book.active
    decoy.title = "States"
    decoy.append(["GEOID", "RISK"])
    decoy.append(["01", 0.99])
    sheet = book.create_sheet("Counties")
    sheet.append(["GEOID", "RISK"])
    sheet.append(["1001", 0.42])
    sheet.append(["2", 0.10])
    path = tmp_path / "wb.xlsx"
    book.save(path)
    return path.read_bytes()


def test_reads_the_named_sheet(tmp_path, places, workbook_bytes):
    """Naming the sheet must select it, not fall through to the first one."""
    cache = Cache(tmp_path / "c")
    cache.write(SPEC["url"], workbook_bytes)
    result = DeclarativeSource(SPEC, cache).fetch((*places, _place("01001"), _place("00002")))
    assert result["risk"]["01001"] == 0.42


def test_pads_unpadded_geoid(tmp_path, places, workbook_bytes):
    """Excel strips leading zeros from a FIPS; the join must survive it."""
    cache = Cache(tmp_path / "c")
    cache.write(SPEC["url"], workbook_bytes)
    result = DeclarativeSource(SPEC, cache).fetch((*places, _place("01001")))
    assert "00002" in result["risk"]


def _place(fips: str) -> Place:
    """A bare place with no CBSA, for join tests."""
    return Place(fips, "x", "State", 40.0, -100.0, 1000)
