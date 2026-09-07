"""Metrics measured at the city rather than the county."""

import concurrent.futures
import json

import httpx

from refugia import USER_AGENT
from refugia.retry import Retry

from refugia.metrics.sources.landfire_vegetation import LandfireVegetationSource
from refugia.store.cache import Cache

PLACES_ENDPOINT = "https://data.cdc.gov/resource/vgc8-iyc4.json"

# The place release is published wide, a column per measure, keyed on place FIPS -
# which is the same GEOID the city markers already carry.
# 3,143 counties at 20,000 rows a page leaves room for the release to grow
# several times over before this is the thing that stops a fetch.
MAX_PAGES = 50

PLACES_COLUMNS = {
    "depression_crudeprev": "depression",
    "mhlth_crudeprev": "mental_distress",
    "sleep_crudeprev": "short_sleep",
    "casthma_crudeprev": "asthma",
    "phlth_crudeprev": "physical_distress",
    "ghlth_crudeprev": "poor_or_fair_health",
    "isolation_crudeprev": "social_isolation",
}


class CityProfile:
    """Builds the per-city metric table the city panel reads.

    Two things are measurable at this grain without a new kind of source. The
    vegetation sample was always a radius around a point, so a city is the same
    question asked at a sharper coordinate -- and the answer moves: within one
    county the sagebrush share runs from a twentieth to a quarter of the land.
    The health estimates are published per place as well as per county, and the
    place release carries two measures the county release does not.

    Everything else stays county-level, and the panel says which grain each row
    came from rather than presenting a mixture as though it were uniform.
    """

    def __init__(
        self,
        cache: Cache,
        *,
        workers: int = 8,
        vegetation: LandfireVegetationSource | None = None,
        retry: Retry | None = None,
    ) -> None:
        self._cache = cache
        self._workers = workers
        # Injected rather than constructed, so a caller can hand in a source
        # sampling at a different radius and a test can hand in one that answers
        # without a network. The default keeps the common case a one-liner.
        self._vegetation = vegetation or LandfireVegetationSource(cache)
        self._retry = retry or Retry()

    def build(self, cities: dict[str, list[dict]]) -> dict[str, dict[str, float]]:
        """Return {place geoid: {metric key: value}} for every mapped city."""
        flat = [c for group in cities.values() for c in group]
        out: dict[str, dict[str, float]] = {c["geoid"]: {} for c in flat}
        for geoid, values in self._health(list(out)).items():
            out.setdefault(geoid, {}).update(values)
        for geoid, values in self._vegetation_cover(flat).items():
            out.setdefault(geoid, {}).update(values)
        return {g: v for g, v in out.items() if v}

    def _vegetation_cover(self, cities: list[dict]) -> dict[str, dict[str, float]]:
        """Resample the land cover around each city."""
        out: dict[str, dict[str, float]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {
                pool.submit(self._vegetation.cover_at, f"city-{c['geoid']}", c["lat"], c["lon"]): c[
                    "geoid"
                ]
                for c in cities
                if c.get("lat") is not None
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    cover = future.result()
                except Exception:  # pylint: disable=broad-exception-caught
                    # One unreachable city must not lose the other four thousand;
                    # a missing city simply falls back to its county's figures.
                    continue
                if cover:
                    out[futures[future]] = cover
        return out

    def _health(self, geoids: list[str]) -> dict[str, dict[str, float]]:
        """Place-level prevalence estimates, cached whole."""
        key = "cdc-places-place-2025"
        if self._cache.has(key, ".json"):
            rows = json.loads(self._cache.read(key, ".json"))
        else:
            rows = self._download()
            # `[]` is valid JSON and reads back as "no city has any of this".
            if rows:
                self._cache.write(key, json.dumps(rows).encode(), ".json")
        wanted = set(geoids)
        out: dict[str, dict[str, float]] = {}
        for row in rows:
            geoid = row.get("placefips")
            if geoid not in wanted:
                continue
            values = {}
            for column, metric in PLACES_COLUMNS.items():
                raw = row.get(column)
                if raw in (None, ""):
                    continue
                try:
                    values[metric] = float(raw)
                except ValueError:
                    continue
            if values:
                out[geoid] = values
        return out

    def _page(self, columns: str, offset: int) -> list[dict]:
        """One page of the place release."""
        response = httpx.get(
            PLACES_ENDPOINT,
            headers={"User-Agent": USER_AGENT},
            params={"$select": columns, "$limit": 20000, "$offset": offset},
            timeout=180.0,
        )
        response.raise_for_status()
        return response.json()

    def _download(self) -> list[dict]:
        """Page through the place release, taking only the columns used."""
        columns = ",".join(["placefips", *PLACES_COLUMNS])
        rows: list[dict] = []
        offset = 0
        # Bounded, and the page's type is checked: an endpoint answering 200 with a
        # dict envelope would otherwise extend `rows` with its keys and then run the
        # loop until something further down failed on a string.
        for _ in range(MAX_PAGES):
            page = self._retry.run(lambda offset=offset: self._page(columns, offset))
            if not isinstance(page, list):
                raise ValueError(f"expected a list of rows, got {type(page).__name__}")
            rows.extend(page)
            if len(page) < 20000:
                return rows
            offset += 20000
        raise ValueError(f"more than {MAX_PAGES} pages; the query is probably wrong")
