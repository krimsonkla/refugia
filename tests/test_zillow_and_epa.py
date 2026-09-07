"""Two adapters whose whole job is parsing, tested by seeding the cache.

Both fail in the way a parser fails: quietly, on the shape of somebody else's file.
Zillow publishes a column per month and the last one is often blank; the EPA joins
on a county name and pads some of them. Neither shows up as an error — they show up
as a metric with a hole in it, which is the failure the coverage gate exists for.
"""

import csv
import io
import zipfile

import pytest

from refugia.metrics.sources.epa_air_quality import EpaAirQualitySource
from refugia.metrics.sources.zillow_home_value import ZillowHomeValueSource
from refugia.places.place import Place
from refugia.store.cache import Cache


def _places(*rows: tuple[str, str, str]) -> tuple[Place, ...]:
    return tuple(Place(fips=f, name=n, state=s, lat=0.0, lon=0.0, population=1) for f, n, s in rows)


# --- Zillow -----------------------------------------------------------------


def _zhvi(rows: list[dict], months: list[str]) -> bytes:
    header = ["RegionID", "StateCodeFIPS", "MunicipalCodeFIPS", *months]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue().encode("utf-8")


@pytest.fixture
def zillow(tmp_path):
    def _build(rows, months):
        cache = Cache(tmp_path / "z")
        cache.write("zillow-zhvi-county", _zhvi(rows, months), ".csv")
        return ZillowHomeValueSource(cache)

    return _build


def test_the_latest_populated_month_is_taken(zillow):
    """The most recent column is routinely blank; the value is the last real one."""
    source = zillow(
        [
            {
                "RegionID": "1",
                "StateCodeFIPS": "56",
                "MunicipalCodeFIPS": "013",
                "2026-07-31": "300000",
                "2026-08-31": "310000",
                "2026-09-30": "",
            }
        ],
        ["2026-07-31", "2026-08-31", "2026-09-30"],
    )
    assert source.fetch(_places(("56013", "A", "S")))["home_value"] == {"56013": 310000.0}


def test_fips_are_rebuilt_from_the_two_columns_it_publishes(zillow):
    """State and county arrive separately and unpadded; a 5-digit key is the join."""
    source = zillow(
        [{"RegionID": "1", "StateCodeFIPS": "6", "MunicipalCodeFIPS": "37", "2026-01-31": "9"}],
        ["2026-01-31"],
    )
    assert "06037" in source.fetch(_places(("06037", "A", "S")))["home_value"]


def test_a_county_outside_the_universe_is_ignored(zillow):
    source = zillow(
        [{"RegionID": "1", "StateCodeFIPS": "56", "MunicipalCodeFIPS": "013", "2026-01-31": "9"}],
        ["2026-01-31"],
    )
    assert source.fetch(_places(("06037", "A", "S")))["home_value"] == {}


def test_a_row_with_no_month_populated_yields_nothing(zillow):
    """Missing is not zero: the engine has to be able to tell them apart."""
    source = zillow(
        [{"RegionID": "1", "StateCodeFIPS": "56", "MunicipalCodeFIPS": "013", "2026-01-31": ""}],
        ["2026-01-31"],
    )
    assert source.fetch(_places(("56013", "A", "S")))["home_value"] == {}


# --- EPA --------------------------------------------------------------------


def _aqi_zip(rows: list[dict]) -> bytes:
    header = [
        "State",
        "County",
        "Unhealthy for Sensitive Groups Days",
        "Unhealthy Days",
        "Very Unhealthy Days",
        "Hazardous Days",
        "Max AQI",
    ]
    body = io.StringIO()
    writer = csv.DictWriter(body, fieldnames=header)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("annual_aqi_by_county_2026.csv", body.getvalue())
    return buffer.getvalue()


def _aqi_row(state: str, county: str, days: int, peak: int) -> dict:
    return {
        "State": state,
        "County": county,
        "Unhealthy for Sensitive Groups Days": days,
        "Unhealthy Days": 0,
        "Very Unhealthy Days": 0,
        "Hazardous Days": 0,
        "Max AQI": peak,
    }


@pytest.fixture
def epa(tmp_path):
    def _build(per_year: dict[int, list[dict]]):
        cache = Cache(tmp_path / "e")
        source = EpaAirQualitySource(cache, years=tuple(per_year))
        for year, rows in per_year.items():
            url = f"https://aqs.epa.gov/aqsweb/airdata/annual_aqi_by_county_{year}.zip"
            cache.write(url, _aqi_zip(rows), ".zip")
        return source

    return _build


def test_years_are_averaged_rather_than_taking_the_latest(epa):
    """One bad fire season is weather; the mean across years is the climate."""
    source = epa(
        {
            2025: [_aqi_row("Wyoming", "Fremont", 10, 200)],
            2026: [_aqi_row("Wyoming", "Fremont", 20, 100)],
        }
    )
    values = source.fetch(_places(("56013", "Fremont", "Wyoming")))
    assert values["unhealthy_air_days"]["56013"] == 15.0
    assert values["worst_air_day"]["56013"] == 150.0


def test_the_bad_day_columns_are_summed(epa):
    """Four severity columns, and the metric is how many days were any of them."""
    row = _aqi_row("Wyoming", "Fremont", 3, 90)
    row["Unhealthy Days"] = 2
    row["Very Unhealthy Days"] = 1
    row["Hazardous Days"] = 1
    source = epa({2026: [row]})
    assert source.fetch(_places(("56013", "Fremont", "Wyoming")))["unhealthy_air_days"] == {
        "56013": 7.0
    }


def test_a_padded_county_name_still_joins(epa):
    """The EPA pads some names, and the join is on the name — this is a real bug."""
    source = epa({2026: [_aqi_row("Wyoming ", "  Fremont ", 4, 80)]})
    assert "56013" in source.fetch(_places(("56013", "Fremont", "Wyoming")))["unhealthy_air_days"]


def test_a_county_that_never_appears_is_absent_rather_than_zero(epa):
    """Roughly half the counties have no monitor; that is missing, not clean air."""
    source = epa({2026: [_aqi_row("Wyoming", "Fremont", 4, 80)]})
    values = source.fetch(_places(("56013", "Fremont", "Wyoming"), ("06037", "Nowhere", "S")))
    assert "06037" not in values["unhealthy_air_days"]


def test_an_unparseable_row_is_skipped_not_fatal(epa):
    """One malformed row should cost that row, not the year."""
    bad = _aqi_row("Wyoming", "Fremont", 4, 80)
    bad["Max AQI"] = "n/a"
    good = _aqi_row("California", "Los Angeles", 6, 120)
    source = epa({2026: [bad, good]})
    values = source.fetch(
        _places(("56013", "Fremont", "Wyoming"), ("06037", "Los Angeles", "California"))
    )
    assert values["worst_air_day"] == {"06037": 120.0}
