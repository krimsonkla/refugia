"""Allergenic vegetation cover near a place, from LANDFIRE Existing Vegetation Type."""

import concurrent.futures
import csv
import io
import json
import math
import re
from collections import Counter

import httpx

from refugia import USER_AGENT

from refugia.metrics.metric import Metric
from refugia.metrics.sources.sampling import Sampling
from refugia.metrics.sources.throttle import Throttle
from refugia.retry import Retry
from refugia.places.place import Place
from refugia.store.cache import Cache

SERVICE = (
    "https://lfps.usgs.gov/arcgis/rest/services/Landfire_LF2024/"
    "LF2024_EVT_CONUS/ImageServer/getSamples"
)
CROSSWALK_URL = "https://www.landfire.gov/sites/default/files/CSV/2024/LF2024_EVT.csv"

# Matched against EVT_NAME to build the class sets. Kept as patterns rather than
# hard-coded value lists so a LANDFIRE version bump renumbering classes does not
# silently produce zeroes for every place.
PATTERNS = {
    "juniper_cover": r"\bjuniper\b",
    "sagebrush_cover": r"\bsagebrush\b",
    "populus_cover": r"cottonwood|\bpoplar\b|populus|\baspen\b",
}

# LANDFIRE maps no cottonwood type: riparian Populus is inside generic riparian and
# floodplain classes. These are the western ones where cottonwood is the dominant
# canopy, added to the aspen matches to approximate Populus exposure. This is a
# habitat proxy, not a species map, and `populus_cover` is documented as such.
# LANDFIRE maps no cottonwood type: riparian Populus sits inside generic riparian and
# floodplain classes. Eastern cottonwood (Populus deltoides) is a dominant early-
# successional floodplain tree across the whole eastern half of the country, so
# restricting this to western classes would score the Midwest and East as clean on
# the exact allergen being avoided. Forested classes only -- the shrubland and
# herbaceous riparian classes are willow and sedge, not Populus.
RIPARIAN_PROXY = re.compile(
    r"(Floodplain (Forest|Woodland)"
    r"|Riparian (Forest|Woodland)"
    r"|Floodplain Terrace Forest"
    r"|Bottomland\) Forest"
    r"|Bottomlands Forest"
    r")",
    re.I,
)


class OutsideCoverage(Exception):
    """The layer does not cover the requested extent, so retrying cannot help."""


class LandfireVegetationSource:
    """Fraction of land cover near each place that is an allergenic type.

    Structural exposure rather than a pollen forecast. A forecast answers "should I
    go outside on Thursday"; a relocation decision needs "how much of this plant
    grows where I would live, every spring, for as long as I live there". The
    sampling radius is around the population-weighted centroid, so it describes the
    landscape around the inhabited part of a county rather than its empty acreage.
    """

    def __init__(self, cache: Cache, *, sampling: Sampling | None = None) -> None:
        self._cache = cache
        self._sampling = sampling or Sampling()
        # Shared by every worker, so the limit is the source's and not each
        # thread's -- see Throttle.
        self._throttle = Throttle(self._sampling.min_interval)
        self._retry = Retry(self._sampling.retries, self._sampling.backoff)
        self._failures: list[tuple[str, str]] = []
        self._outside: list[tuple[str, str]] = []
        self._classes: dict[str, frozenset[int]] | None = None

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The three vegetation exposure metrics."""
        radius = f"within {self._sampling.radius_km:g} km"
        return (
            Metric(
                key="juniper_cover",
                label="Juniper cover",
                unit="% of land",
                direction="lower_better",
                category="allergen",
                description=f"Share of land {radius} mapped as juniper woodland or savanna.",
                source="LANDFIRE LF2024 EVT",
            ),
            Metric(
                key="sagebrush_cover",
                label="Sagebrush cover",
                unit="% of land",
                direction="lower_better",
                category="allergen",
                description=f"Share of land {radius} mapped as sagebrush shrubland or steppe.",
                source="LANDFIRE LF2024 EVT",
            ),
            Metric(
                key="populus_cover",
                label="Cottonwood / poplar cover",
                unit="% of land",
                direction="lower_better",
                category="allergen",
                description=(
                    f"Share of land {radius} mapped as aspen, or as western riparian and "
                    "floodplain woodland where cottonwood is the dominant canopy. LANDFIRE "
                    "maps no cottonwood type, so this is a habitat proxy, not a species map."
                ),
                source="LANDFIRE LF2024 EVT (riparian proxy)",
            ),
        )

    def class_sets(self) -> dict[str, frozenset[int]]:
        """Resolve each metric to the set of EVT class values that count toward it."""
        if self._classes is not None:
            return self._classes
        payload = self._cache.fetch_url(CROSSWALK_URL, key="landfire-evt-crosswalk", suffix=".csv")
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
        resolved: dict[str, frozenset[int]] = {}
        for key, pattern in PATTERNS.items():
            matched = {int(r["VALUE"]) for r in rows if re.search(pattern, r["EVT_NAME"], re.I)}
            if key == "populus_cover":
                matched |= {int(r["VALUE"]) for r in rows if RIPARIAN_PROXY.search(r["EVT_NAME"])}
            if not matched:
                raise RuntimeError(f"no EVT classes matched {key!r}; crosswalk may have changed")
            resolved[key] = frozenset(matched)
        self._classes = resolved
        return resolved

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Sample vegetation around every place and reduce to cover fractions."""
        classes = self.class_sets()
        out: dict[str, dict[str, float]] = {k: {} for k in PATTERNS}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._sampling.workers) as pool:
            futures = {pool.submit(self._sample, p): p for p in places}
            for future in concurrent.futures.as_completed(futures):
                place = futures[future]
                try:
                    counts = future.result()
                except OutsideCoverage as error:
                    self._outside.append((place.fips, str(error)))
                    continue
                except (httpx.HTTPError, OSError) as error:
                    self._failures.append((place.fips, str(error)))
                    continue
                if not counts:
                    continue
                total = sum(counts.values())
                for key, values in classes.items():
                    hits = sum(n for value, n in counts.items() if value in values)
                    out[key][place.fips] = 100.0 * hits / total
        return out

    @property
    def failures(self) -> tuple[tuple[str, str], ...]:
        """Places whose sampling failed after every retry."""
        return tuple(self._failures)

    @property
    def outside_coverage(self) -> tuple[tuple[str, str], ...]:
        """Places the layer does not cover at all, chiefly Alaska and the territories."""
        return tuple(self._outside)

    def cover_at(self, identifier: str, lat: float, lon: float) -> dict[str, float]:
        """Cover fractions around any point, for callers that are not counties.

        The measurement was always "what grows within a radius of here", so a city
        asks the same question at a sharper coordinate. Exposed rather than copied:
        a second implementation of the sampling would drift from this one.
        """
        counts = self._sample_at(identifier, lat, lon)
        total = sum(counts.values())
        if not total:
            return {}
        return {
            key: 100.0 * sum(n for value, n in counts.items() if value in values) / total
            for key, values in self.class_sets().items()
        }

    def _sample(self, place: Place) -> Counter:
        """Class-value histogram for one county."""
        return self._sample_at(place.fips, place.lat, place.lon)

    def _sample_at(self, identifier: str, lat: float, lon: float) -> Counter:
        """Class-value histogram around one point, cached on disk."""
        key = (
            f"landfire-{identifier}-r{self._sampling.radius_km:g}"
            f"-n{self._sampling.sample_count}"
        )
        if self._cache.has(key, ".json"):
            return Counter(
                {int(k): v for k, v in json.loads(self._cache.read(key, ".json")).items()}
            )
        counts = self._request(lat, lon)
        if counts:
            self._cache.write(
                key, json.dumps({str(k): v for k, v in counts.items()}).encode(), ".json"
            )
        return counts

    def _request(self, lat: float, lon: float) -> Counter:
        """One getSamples call over the bounding box around a point.

        Retried with backoff because the endpoint drops connections under sustained
        use. Without this a single reset ends a run of nineteen hundred requests,
        which is how the whole fetch was lost two places from the end.
        """
        # OutsideCoverage is permanent, and Retry raises anything it does not
        # recognise as transient at once -- so Alaska and the territories no longer
        # spend minutes of backoff on every run re-confirming a fixed fact. Neither
        # does a 404 from a service that has moved, which the old loop retried.
        return self._retry.run(lambda: self._request_once(lat, lon))

    def _request_once(self, lat: float, lon: float) -> Counter:
        """A single unretried getSamples call."""
        lat_span = self._sampling.radius_km / 111.0
        lon_span = self._sampling.radius_km / (111.0 * max(0.15, abs(math.cos(math.radians(lat)))))
        geometry = {
            "xmin": lon - lon_span,
            "ymin": lat - lat_span,
            "xmax": lon + lon_span,
            "ymax": lat + lat_span,
            "spatialReference": {"wkid": 4326},
        }
        self._throttle.wait()
        response = httpx.post(
            SERVICE,
            headers={"User-Agent": USER_AGENT},
            data={
                "geometry": json.dumps(geometry),
                "geometryType": "esriGeometryEnvelope",
                "sampleCount": str(self._sampling.sample_count),
                "returnFirstValueOnly": "true",
                "f": "json",
            },
            timeout=120.0,
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            # A 200 carrying an error body is how this service reports both "your
            # extent is outside the layer", which is permanent geography, and "I am
            # busy", which is not. Filed under coverage, the second becomes a place
            # silently recorded as having no vegetation.
            error = body["error"] if isinstance(body["error"], dict) else {}
            code = error.get("code", 400)
            if code in (429, 500, 502, 503, 504):
                raise httpx.HTTPError(f"LANDFIRE is unavailable: {body['error']}")
            raise OutsideCoverage(f"LANDFIRE rejected the request: {body['error']}")
        samples = body.get("samples") or []
        if not samples:
            raise httpx.HTTPError("LANDFIRE returned no samples for this extent")
        counts: Counter = Counter()
        for sample in samples:
            raw = sample.get("value")
            if raw in (None, "", "NoData"):
                continue
            try:
                counts[int(float(str(raw).split()[0]))] += 1
            except (TypeError, ValueError):
                continue
        return counts
