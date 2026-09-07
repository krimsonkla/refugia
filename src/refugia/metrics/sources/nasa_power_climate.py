"""Climate extremes, sunshine and humidity per place, from the NASA POWER climatology."""

import concurrent.futures
import json
import math

import httpx

from refugia import USER_AGENT
from refugia.retry import Retry

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.cache import Cache

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/climatology/regional"
PARAMETERS = ("T2M_MAX", "T2M_MIN", "CLOUD_AMT", "RH2M")

# The service answers a rectangle at a time and accepts exactly one parameter per
# call, so the work is tiles x parameters. Five degrees keeps each response small
# and stays well inside the area limit.
TILE = 5.0

MILDER = (
    " Direction assumes milder is better. Someone who wants real winters should "
    "leave this unweighted and use a requirement instead, which can ask for a "
    "range rather than a preference."
)


class NasaPowerClimateSource:
    """Annual climate normals sampled at each place's population-weighted centre.

    Fetched as a grid rather than a point per county. The service's native
    resolution is half a degree, so eighteen hundred point requests were asking
    the same grid the same question eighteen hundred times; tiling turns an
    eighty-minute crawl into a couple of hundred calls for identical numbers.

    `T2M_MAX` and `T2M_MIN` are the extremes over the climatology rather than
    monthly means, which is what "hottest day" and "coldest day" actually ask: a
    mean July maximum says nothing about whether a place reaches 110F, and it is
    the reachable extreme that decides whether somewhere is liveable.

    Sunshine is reported as clear-sky share rather than counted days. The source
    publishes mean cloud amount, and turning that into a day count would need a
    threshold this project would be inventing.
    """

    def __init__(self, cache: Cache, *, workers: int = 6, retries: int = 4) -> None:
        self._cache = cache
        self._workers = workers
        # ValueError and KeyError are declared transient because this endpoint
        # answers 200 with an error body and with partly-shaped features.
        self._retry = Retry(retries, 1.5, also_transient=(KeyError, ValueError))
        self._failures: list[tuple[str, str]] = []

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The four climate metrics."""
        source = "NASA POWER climatology (satellite reanalysis)"
        return (
            Metric(
                key="sunshine",
                label="Clear sky",
                unit="% of sky clear",
                direction="higher_better",
                category="climate",
                description=(
                    "Annual mean share of the sky free of cloud. A share rather than a "
                    "count of sunny days, because turning cloud cover into a day count "
                    "needs a threshold this project would be inventing."
                ),
                source=source,
            ),
            Metric(
                key="hottest_day",
                label="Hottest day",
                unit="degrees F",
                direction="lower_better",
                category="climate",
                description=(
                    "The highest temperature reached in the climatology, not an average "
                    "summer day." + MILDER
                ),
                source=source,
            ),
            Metric(
                key="coldest_day",
                label="Coldest day",
                unit="degrees F",
                direction="higher_better",
                category="climate",
                description=(
                    "The lowest temperature reached in the climatology, not an average "
                    "winter day." + MILDER
                ),
                source=source,
            ),
            Metric(
                key="humidity",
                label="Humidity",
                unit="% relative",
                direction="lower_better",
                category="climate",
                description=(
                    "Annual mean relative humidity. Carried because damp air is what "
                    "sustains indoor mould, an allergen this project has no direct "
                    "measure of."
                ),
                source=source,
            ),
        )

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Download the covering grid once per parameter, then sample each place."""
        buckets = {
            parameter: _bucket(points) for parameter, points in self._download(places).items()
        }
        return self._assemble(places, buckets)

    def _download(self, places: tuple[Place, ...]) -> dict[str, dict[tuple[float, float], float]]:
        """Every parameter over every tile the places fall in."""
        jobs = [(p, t) for p in PARAMETERS for t in self._tiles(places)]
        grids: dict[str, dict[tuple[float, float], float]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {pool.submit(self._tile, p, t): (p, t) for p, t in jobs}
            for future in concurrent.futures.as_completed(futures):
                parameter, tile = futures[future]
                try:
                    grids.setdefault(parameter, {}).update(future.result())
                except (httpx.HTTPError, OSError, ValueError) as error:
                    self._failures.append((f"{parameter}@{tile}", str(error)))
        return grids

    def _assemble(
        self,
        places: tuple[Place, ...],
        buckets: dict[str, dict[tuple[int, int], list]],
    ) -> dict[str, dict[str, float]]:
        """Sample each place from the grid and convert to the published units."""
        out: dict[str, dict[str, float]] = {
            k: {} for k in ("sunshine", "hottest_day", "coldest_day", "humidity")
        }
        for place in places:
            annual = {}
            for parameter in PARAMETERS:
                value = self._nearest(buckets.get(parameter, {}), place.lat, place.lon)
                if value is None:
                    break
                annual[parameter] = value
            if len(annual) != len(PARAMETERS):
                continue
            out["sunshine"][place.fips] = 100.0 - annual["CLOUD_AMT"]
            out["hottest_day"][place.fips] = annual["T2M_MAX"] * 9 / 5 + 32
            out["coldest_day"][place.fips] = annual["T2M_MIN"] * 9 / 5 + 32
            out["humidity"][place.fips] = annual["RH2M"]
        return out

    @property
    def failures(self) -> tuple[tuple[str, str], ...]:
        """Tiles that could not be retrieved."""
        return tuple(self._failures)

    @staticmethod
    def _tiles(places: tuple[Place, ...]) -> list[tuple[float, float]]:
        """South-west corners of the tiles covering the places, on a fixed lattice."""
        corners = set()
        for place in places:
            corners.add(
                (
                    math.floor(place.lat / TILE) * TILE,
                    math.floor(place.lon / TILE) * TILE,
                )
            )
        return sorted(corners)

    def _tile(
        self, parameter: str, corner: tuple[float, float]
    ) -> dict[tuple[float, float], float]:
        """One parameter over one tile, cached on disk."""
        lat, lon = corner
        key = f"power-{parameter}-{lat:g}-{lon:g}-t{TILE:g}"
        if self._cache.has(key, ".json"):
            stored = json.loads(self._cache.read(key, ".json"))
            return {tuple(map(float, k.split(","))): v for k, v in stored.items()}
        points = self._request(parameter, lat, lon)
        if points:
            self._cache.write(
                key,
                json.dumps({f"{a},{b}": v for (a, b), v in points.items()}).encode(),
                ".json",
            )
        return points

    def _request(self, parameter: str, lat: float, lon: float) -> dict[tuple[float, float], float]:
        """One regional call, retried with backoff."""
        return self._retry.run(lambda: self._request_once(parameter, lat, lon))

    def _request_once(
        self, parameter: str, lat: float, lon: float
    ) -> dict[tuple[float, float], float]:
        """A single unretried regional call."""
        response = httpx.get(
            ENDPOINT,
            headers={"User-Agent": USER_AGENT},
            params={
                "latitude-min": lat,
                "latitude-max": lat + TILE,
                "longitude-min": lon,
                "longitude-max": lon + TILE,
                "community": "ag",
                "parameters": parameter,
                "format": "json",
            },
            timeout=180.0,
        )
        response.raise_for_status()
        body = response.json()
        # A 200 carrying an error payload rather than data: transient, and the
        # reason this source declares ValueError and KeyError retryable.
        if "features" not in body:
            raise ValueError(str(body.get("messages") or body)[:160])
        points = {}
        for feature in body["features"]:
            x, y = feature["geometry"]["coordinates"][:2]
            value = feature["properties"]["parameter"][parameter]["ANN"]
            # POWER marks absent cells, chiefly open ocean, with a fill value.
            if value is not None and value > -900:
                points[(float(y), float(x))] = float(value)
        return points

    @staticmethod
    def _nearest(bucket: dict[tuple[int, int], list], lat: float, lon: float) -> float | None:
        """Closest grid value, searching the surrounding whole-degree cells.

        A county centroid on the coast can sit nearer a cell the grid marks as
        ocean, so the search widens rather than taking the single closest cell and
        reporting no data when it happens to be empty.
        """
        best = None
        best_distance = float("inf")
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for point_lat, point_lon, value in bucket.get(
                    (round(lat) + dy, round(lon) + dx), ()
                ):
                    distance = (point_lat - lat) ** 2 + (point_lon - lon) ** 2
                    if distance < best_distance:
                        best, best_distance = value, distance
        return best


def _bucket(
    points: dict[tuple[float, float], float],
) -> dict[tuple[int, int], list[tuple[float, float, float]]]:
    """Group grid points by whole degree, so the nearest search reads a few cells."""
    out: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for (lat, lon), value in points.items():
        out.setdefault((round(lat), round(lon)), []).append((lat, lon, value))
    return out
