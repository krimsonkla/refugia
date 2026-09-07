"""Health and wellbeing prevalence per county, from the CDC PLACES release."""

import json

import httpx

from refugia import USER_AGENT
from refugia.retry import Retry

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.cache import Cache

ENDPOINT = "https://data.cdc.gov/resource/swc5-untb.json"

# One measure over every county fits in a page today; the cap is a runaway guard
# rather than a limit anybody should reach.
MAX_PAGES = 50

# measure id -> (metric key, label, direction, category, description)
MEASURES: dict[str, tuple[str, str, str, str, str]] = {
    "DEPRESSION": (
        "depression",
        "Depression",
        "lower_better",
        "wellbeing",
        "Adults reporting a depression diagnosis, crude prevalence.",
    ),
    "MHLTH": (
        "mental_distress",
        "Frequent mental distress",
        "lower_better",
        "wellbeing",
        "Adults reporting 14+ poor mental health days in the last month.",
    ),
    "SLEEP": (
        "short_sleep",
        "Short sleep",
        "lower_better",
        "wellbeing",
        "Adults sleeping under 7 hours a night.",
    ),
    "CASTHMA": (
        "asthma",
        "Current asthma",
        "lower_better",
        "health",
        "Adults with current asthma. A population signal, not a local air-quality one.",
    ),
    "PHLTH": (
        "physical_distress",
        "Frequent physical distress",
        "lower_better",
        "wellbeing",
        "Adults reporting 14+ poor physical health days in the last month.",
    ),
}


class CdcPlacesSource:
    """Model-based prevalence estimates for every US county.

    This is the replacement for the metro happiness indexes that no longer publish.
    It is deliberately exposed as separate measures rather than a single pre-baked
    score: a composite whose weights a user cannot see or change is a black box, and
    the whole design here is that the weighting is the user's to set.
    """

    def __init__(
        self,
        cache: Cache,
        *,
        measures: tuple[str, ...] | None = None,
        retry: Retry | None = None,
    ) -> None:
        self._cache = cache
        self._retry = retry or Retry()
        self._measures = measures or tuple(MEASURES)
        unknown = set(self._measures) - set(MEASURES)
        if unknown:
            raise ValueError(f"unknown PLACES measures: {sorted(unknown)}")

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """One metric per configured PLACES measure."""
        return tuple(
            Metric(
                key=MEASURES[m][0],
                label=MEASURES[m][1],
                unit="% of adults",
                direction=MEASURES[m][2],
                category=MEASURES[m][3],
                description=MEASURES[m][4],
                source="CDC PLACES 2025 release",
            )
            for m in self._measures
        )

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Pull each measure for every county, then keep the ones in the universe."""
        wanted = {p.fips for p in places}
        out: dict[str, dict[str, float]] = {}
        for measure in self._measures:
            key = MEASURES[measure][0]
            out[key] = {
                fips: value for fips, value in self._measure(measure).items() if fips in wanted
            }
        return out

    def _page(self, measure: str, offset: int) -> list[dict]:
        """One page of a measure. Paged because Socrata caps a response at 50,000."""
        response = httpx.get(
            ENDPOINT,
            headers={"User-Agent": USER_AGENT},
            params={
                "$select": "locationid,data_value",
                "$where": (
                    f"measureid='{measure}' AND datavaluetypeid='CrdPrv' "
                    "AND data_value IS NOT NULL"
                ),
                "$limit": 50000,
                "$offset": offset,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()

    def _measure(self, measure: str) -> dict[str, float]:
        """All counties for one measure, cached."""
        cache_key = f"cdc-places-{measure}"
        if self._cache.has(cache_key, ".json"):
            return json.loads(self._cache.read(cache_key, ".json"))
        rows: list[dict] = []
        offset = 0
        # Bounded, and the page's type is checked: an endpoint answering 200 with a
        # dict envelope would otherwise extend `rows` with its keys and then run the
        # loop until something further down failed on a string.
        for _ in range(MAX_PAGES):
            page = self._retry.run(lambda offset=offset: self._page(measure, offset))
            if not isinstance(page, list):
                raise ValueError(f"expected a list of rows, got {type(page).__name__}")
            rows.extend(page)
            if len(page) < 50000:
                break
            offset += 50000
        else:
            raise ValueError(f"more than {MAX_PAGES} pages; the query is probably wrong")
        values = {
            r["locationid"]: float(r["data_value"])
            for r in rows
            if r.get("locationid") and r.get("data_value") not in (None, "")
        }
        # An empty mapping serialises to a perfectly valid `{}`, which the next
        # run would read back as "this measure has no data anywhere".
        if values:
            self._cache.write(cache_key, json.dumps(values).encode(), ".json")
        return values
