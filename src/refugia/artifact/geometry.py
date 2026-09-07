"""County and state outlines as projected SVG paths, prepared at build time."""

import json
import math

from refugia.artifact.map_shapes import MapShapes
from refugia.store.cache import Cache

TOPOJSON_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"

# Albers equal-area conic, the standard CONUS parameters. Equal-area matters for a
# choropleth: an area-distorting projection makes large western counties look like
# they carry more of the answer than they do.
PARALLEL_ONE = math.radians(29.5)
PARALLEL_TWO = math.radians(45.5)
ORIGIN_LAT = math.radians(37.5)
ORIGIN_LON = math.radians(-96.0)

# Alaska, Hawaii and the territories. The vegetation layer is CONUS-only, so these
# would render as permanently blank shapes; they stay in the table instead.
OFF_MAP_STATES = {"02", "15", "60", "66", "69", "72", "78"}


class CountyShapes:
    """Decodes the county TopoJSON once and yields projected path strings.

    Projecting here rather than in the page is what keeps the artifact free of a
    mapping library: the browser receives path data it can colour, and nothing else.
    """

    def __init__(self, cache: Cache, *, width: float = 960.0, height: float = 600.0) -> None:
        self._cache = cache
        self._width = width
        self._height = height

    def build(self, fips_wanted: set[str]) -> MapShapes:
        """Project the requested counties and every CONUS state border."""
        topology = json.loads(
            self._cache.fetch_url(TOPOJSON_URL, key="us-atlas-counties-10m", suffix=".json")
        )
        arcs = self._decode_arcs(topology)
        counties = self._project_layer(topology, "counties", arcs, fips_wanted)
        states = self._project_layer(topology, "states", arcs, None)
        # One transform over both layers, so the borders bound the counties exactly.
        transform = self._transform(list(counties.values()) + list(states.values()))
        return MapShapes(
            counties=self._to_paths(counties, transform),
            states=self._to_paths(states, transform),
            centroids=self._to_centroids(counties, transform),
            transform=transform,
        )

    def _project_layer(
        self,
        topology: dict,
        layer: str,
        arcs: list[list[tuple[float, float]]],
        wanted: set[str] | None,
    ) -> dict[str, list[list[tuple[float, float]]]]:
        """Project one TopoJSON object layer, dropping anything off the CONUS map."""
        out = {}
        for geometry in topology["objects"][layer]["geometries"]:
            identifier = str(geometry.get("id", ""))
            if identifier[:2] in OFF_MAP_STATES or identifier in OFF_MAP_STATES:
                continue
            if wanted is not None and identifier not in wanted:
                continue
            out[identifier] = [
                [project(x, y) for x, y in ring] for ring in self._rings(geometry, arcs)
            ]
        return out

    @staticmethod
    def _decode_arcs(topology: dict) -> list[list[tuple[float, float]]]:
        """Undo TopoJSON delta encoding and quantisation."""
        scale = topology["transform"]["scale"]
        translate = topology["transform"]["translate"]
        decoded = []
        for arc in topology["arcs"]:
            x = y = 0
            points = []
            for dx, dy in arc:
                x += dx
                y += dy
                points.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
            decoded.append(points)
        return decoded

    @staticmethod
    def _rings(geometry: dict, arcs: list[list[tuple[float, float]]]) -> list[list[tuple]]:
        """Flatten a Polygon or MultiPolygon into a list of coordinate rings."""
        polygons = geometry["arcs"] if geometry["type"] == "MultiPolygon" else [geometry["arcs"]]
        rings = []
        for polygon in polygons:
            for ring_arcs in polygon:
                points: list[tuple[float, float]] = []
                for index in ring_arcs:
                    arc = arcs[~index][::-1] if index < 0 else arcs[index]
                    points.extend(arc if not points else arc[1:])
                if len(points) > 3:
                    rings.append(points)
        return rings

    def _transform(
        self, layers: list[list[list[tuple[float, float]]]]
    ) -> tuple[float, float, float]:
        """Scale and offset that fit every supplied ring into the viewbox."""
        xs = [p[0] for rings in layers for ring in rings for p in ring]
        ys = [p[1] for rings in layers for ring in rings for p in ring]
        if not xs:
            return 1.0, 0.0, 0.0
        span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
        scale = min(self._width / span_x, self._height / span_y) * 0.98
        return (
            scale,
            (self._width - span_x * scale) / 2 - min(xs) * scale,
            (self._height - span_y * scale) / 2 - min(ys) * scale,
        )

    @staticmethod
    def _to_centroids(
        projected: dict[str, list[list[tuple[float, float]]]],
        transform: tuple[float, float, float],
    ) -> dict[str, tuple[float, float]]:
        """Area-weighted centre of each county, in viewbox coordinates."""
        scale, offset_x, offset_y = transform
        out: dict[str, tuple[float, float]] = {}
        for identifier, rings in projected.items():
            centre = _centre_of(rings)
            if centre is not None:
                out[identifier] = (
                    round(centre[0] * scale + offset_x, 1),
                    round(centre[1] * scale + offset_y, 1),
                )
        return out

    @staticmethod
    def _to_paths(
        projected: dict[str, list[list[tuple[float, float]]]],
        transform: tuple[float, float, float],
    ) -> dict[str, str]:
        """Emit SVG path strings under a shared transform."""
        scale, offset_x, offset_y = transform
        paths: dict[str, str] = {}
        for identifier, rings in projected.items():
            parts = []
            for ring in rings:
                coords = [f"{x * scale + offset_x:.1f},{y * scale + offset_y:.1f}" for x, y in ring]
                parts.append("M" + "L".join(coords) + "Z")
            paths[identifier] = "".join(parts)
        return paths


def _centre_of(
    rings: list[list[tuple[float, float]]],
) -> tuple[float, float] | None:
    """Area-weighted centre across a county's rings.

    Weighted by area rather than averaging the vertices, because a coastline
    carries far more points than the inland edge and would drag a plain mean out
    to sea.
    """
    total = 0.0
    cx = cy = 0.0
    for ring in rings:
        area, rx, ry = _ring_area_centroid(ring)
        weight = abs(area) or 1e-9
        total += weight
        cx += rx * weight
        cy += ry * weight
    return (cx / total, cy / total) if total else None


def _ring_area_centroid(ring: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Signed area and area-weighted centroid of one ring."""
    area = 0.0
    cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    area /= 2.0
    if abs(area) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return area, cx / (6.0 * area), cy / (6.0 * area)


def project(lon: float, lat: float) -> tuple[float, float]:
    """Albers equal-area conic; y is flipped so north is up in SVG coordinates."""
    n = (math.sin(PARALLEL_ONE) + math.sin(PARALLEL_TWO)) / 2
    c = math.cos(PARALLEL_ONE) ** 2 + 2 * n * math.sin(PARALLEL_ONE)
    rho = math.sqrt(max(0.0, c - 2 * n * math.sin(math.radians(lat)))) / n
    rho_origin = math.sqrt(max(0.0, c - 2 * n * math.sin(ORIGIN_LAT))) / n
    theta = n * (math.radians(lon) - ORIGIN_LON)
    return rho * math.sin(theta), -(rho_origin - rho * math.cos(theta))
