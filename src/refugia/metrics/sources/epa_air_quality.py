"""Episodic air quality per county, from the EPA's annual AQI summaries."""

import csv
import io
import statistics
import zipfile
from collections import defaultdict

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.cache import Cache

URL = "https://aqs.epa.gov/aqsweb/airdata/annual_aqi_by_county_{year}.zip"
YEARS = (2019, 2020, 2021, 2022, 2023, 2024, 2025)

BAD_DAY_COLUMNS = (
    "Unhealthy for Sensitive Groups Days",
    "Unhealthy Days",
    "Very Unhealthy Days",
    "Hazardous Days",
)

SPARSE = (
    " Only counties with a monitor appear, which is roughly two in five of the "
    "candidates here, so weighting this drops the rest unless the data-coverage "
    "requirement is lowered."
)


class EpaAirQualitySource:
    """Days of unhealthy air, and the worst day, averaged over several years.

    This is the episodic counterpart to an annual mean concentration. A mean
    describes the air normally breathed and averages smoke away; what a smoke
    season does is a fortnight the index spends above 150, and that only shows in
    a day count and a maximum.

    Averaged across years deliberately: a single year would rank the west on
    whether it happened to burn that summer.

    The join is on state and county name rather than FIPS, because the EPA
    publishes these summaries without one.
    """

    def __init__(self, cache: Cache, *, years: tuple[int, ...] = YEARS) -> None:
        self._cache = cache
        self._years = years

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The two episodic air-quality metrics."""
        source = f"EPA AQS annual AQI by county, {self._years[0]}-{self._years[-1]}"
        return (
            Metric(
                key="unhealthy_air_days",
                label="Unhealthy air days",
                unit="days per year",
                direction="lower_better",
                category="hazard",
                description=(
                    "Days a year the air quality index exceeds 100, averaged across "
                    "years. This is where a wildfire smoke season shows up, which an "
                    "annual mean concentration does not." + SPARSE
                ),
                source=source,
            ),
            Metric(
                key="worst_air_day",
                label="Worst air day",
                unit="peak AQI",
                direction="lower_better",
                category="hazard",
                description=(
                    "The highest air quality index reached in a year, averaged across "
                    "years. A measure of how bad the bad days get." + SPARSE
                ),
                source=source,
            ),
        )

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Read every year, join on name, and average."""
        index = {(p.state.lower(), p.name.lower()): p.fips for p in places}
        bad: dict[str, list[float]] = defaultdict(list)
        peak: dict[str, list[float]] = defaultdict(list)

        for year in self._years:
            for row in self._rows(year):
                # The EPA pads some county names, which silently breaks the join.
                key = (row["State"].strip().lower(), row["County"].strip().lower())
                fips = index.get(key)
                if fips is None:
                    continue
                try:
                    bad[fips].append(sum(float(row[c]) for c in BAD_DAY_COLUMNS))
                    peak[fips].append(float(row["Max AQI"]))
                except (KeyError, ValueError):
                    continue

        return {
            "unhealthy_air_days": {f: statistics.fmean(v) for f, v in bad.items() if v},
            "worst_air_day": {f: statistics.fmean(v) for f, v in peak.items() if v},
        }

    def _rows(self, year: int) -> list[dict]:
        """One year's summary, cached as the published zip."""
        url = URL.format(year=year)
        payload = self._cache.fetch_url(url, key=url, suffix=".zip")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            name = archive.namelist()[0]
            with archive.open(name) as handle:
                text = io.TextIOWrapper(handle, encoding="utf-8-sig")
                return list(csv.DictReader(text))
