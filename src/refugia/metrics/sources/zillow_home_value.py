"""Typical home value per county, from the Zillow Home Value Index."""

import csv
import io

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.cache import Cache

CSV_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)


class ZillowHomeValueSource:
    """The latest smoothed ZHVI for each county.

    Housing is the component of cost of living that varies most between places and
    dominates a relocation budget, so it is carried separately from the broad price
    index rather than folded into it.
    """

    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The single home-value metric."""
        return (
            Metric(
                key="home_value",
                label="Typical home value",
                unit="USD",
                direction="lower_better",
                category="cost",
                description=(
                    "Zillow Home Value Index, mid-tier, seasonally adjusted, most recent "
                    "month available."
                ),
                source="Zillow Home Value Index (ZHVI)",
            ),
        )

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Parse the national county file and take the last populated month."""
        wanted = {p.fips for p in places}
        payload = self._cache.fetch_url(CSV_URL, key="zillow-zhvi-county", suffix=".csv")
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        if reader.fieldnames is None:
            return {"home_value": {}}
        months = [f for f in reader.fieldnames if f[:4].isdigit() and "-" in f]
        values: dict[str, float] = {}
        for row in reader:
            state = str(row.get("StateCodeFIPS", "")).strip().zfill(2)
            county = str(row.get("MunicipalCodeFIPS", "")).strip().zfill(3)
            fips = f"{state}{county}"
            if fips not in wanted:
                continue
            for month in reversed(months):
                raw = row.get(month)
                if raw not in (None, ""):
                    values[fips] = float(raw)
                    break
        return {"home_value": values}
