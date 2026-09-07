"""County outlines, projected here so the page needs no mapping library.

Every defect this code can have is silent: a county drawn in the wrong place, a
map that does not fill its viewbox, a centroid dragged into the sea by a coastline
carrying ten times the vertices of the inland edge. None of them raise, and none
of them are visible in a diff.

The TopoJSON comes through the cache, so it is seeded. The fixture is hand-built
rather than recorded: the encoding is delta-and-quantised, and a fixture whose
numbers are readable is the only kind that can show the decoder is right.
"""

import json
import math

import httpx
import pytest

from refugia.artifact.geometry import OFF_MAP_STATES, TOPOJSON_URL, CountyShapes, project
from refugia.store.cache import Cache


def _topology(counties, states=None, scale=(0.001, 0.001), translate=(-125.0, 25.0)) -> dict:
    """A TopoJSON in the shape us-atlas publishes: quantised, delta-encoded arcs.

    `counties` and `states` are {id: [arc index, ...]}; arcs are supplied already
    delta-encoded so the decoder is exercised rather than bypassed.
    """
    return {
        "type": "Topology",
        "transform": {"scale": list(scale), "translate": list(translate)},
        "arcs": _ARCS,
        "objects": {
            "counties": {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": "Polygon", "id": i, "arcs": [a]} for i, a in counties.items()
                ],
            },
            "states": {
                "type": "GeometryCollection",
                "geometries": [
                    {"type": "Polygon", "id": i, "arcs": [a]} for i, a in (states or {}).items()
                ],
            },
        },
    }


def _square(x: int, y: int, size: int) -> list[list[int]]:
    """One closed ring, delta-encoded from an absolute starting point."""
    return [[x, y], [size, 0], [0, size], [-size, 0], [0, -size]]


# Two adjacent squares and one far to the east, big enough to survive the
# four-point minimum the ring flattener applies.
_ARCS = [_square(0, 0, 20000), _square(30000, 0, 20000), _square(60000, 30000, 20000)]


@pytest.fixture(name="seeded")
def _seeded(tmp_path):
    def seed(topology: dict) -> Cache:
        cache = Cache(tmp_path / "cache")
        cache.write("us-atlas-counties-10m", json.dumps(topology).encode(), ".json")
        return cache

    return seed


def test_only_the_counties_asked_for_are_projected(seeded):
    """The universe decides the candidates; the map must not widen or narrow it."""
    cache = seeded(_topology({"41017": [0], "41031": [1]}))
    shapes = CountyShapes(cache).build({"41017"})
    assert set(shapes.counties) == {"41017"}


def test_every_state_border_is_drawn_whichever_counties_were_asked_for(seeded):
    """The borders are context. Restricted to the requested counties the map would
    lose the outline of a state the user has ruled out, and stop being a map."""
    cache = seeded(_topology({"41017": [0]}, states={"41": [1]}))
    shapes = CountyShapes(cache).build({"41017"})
    assert set(shapes.states) == {"41"}


def test_alaska_hawaii_and_the_territories_are_left_off_the_map(seeded):
    """The vegetation layer is CONUS-only, so these would render as permanently
    blank shapes. They stay in the table, where the numbers they do have show."""
    cache = seeded(_topology({"02020": [0], "41017": [1]}, states={"15": [2]}))
    shapes = CountyShapes(cache).build({"02020", "41017"})
    assert set(shapes.counties) == {"41017"}
    assert not shapes.states
    assert "02" in OFF_MAP_STATES and "15" in OFF_MAP_STATES


def test_a_path_is_emitted_as_a_closed_svg_ring(seeded):
    """The page sets a fill on these, and an unclosed path fills unpredictably."""
    path = CountyShapes(seeded(_topology({"41017": [0]}))).build({"41017"}).counties["41017"]
    assert path.startswith("M") and path.endswith("Z") and "L" in path


def test_counties_and_borders_share_one_transform(seeded):
    """Fitted separately the two layers land at different scales, and the borders
    stop bounding the counties they are drawn around."""
    # The same ring in both layers: under one transform it lands in one place.
    cache = seeded(_topology({"41017": [0], "41031": [2]}, states={"41": [0]}))
    shapes = CountyShapes(cache).build({"41017", "41031"})
    assert shapes.states["41"] == shapes.counties["41017"]


def _xs(path: str) -> list[float]:
    return [float(p.split(",")[0]) for p in path.replace("M", "").replace("Z", "").split("L")]


def _ys(path: str) -> list[float]:
    return [float(p.split(",")[1]) for p in path.replace("M", "").replace("Z", "").split("L")]


def test_the_drawing_fits_inside_the_viewbox(seeded):
    """Anything outside is clipped by the SVG and simply not there."""
    cache = seeded(_topology({"41017": [0], "41031": [1], "41013": [2]}))
    shapes = CountyShapes(cache, width=400.0, height=300.0).build({"41017", "41031", "41013"})
    for path in shapes.counties.values():
        assert 0 <= min(_xs(path)) and max(_xs(path)) <= 400.0
        assert 0 <= min(_ys(path)) and max(_ys(path)) <= 300.0


def test_a_centroid_lands_inside_its_own_county(seeded):
    """The marker for a selected county is drawn here, and a centroid outside the
    shape points at a neighbour."""
    cache = seeded(_topology({"41017": [0]}))
    shapes = CountyShapes(cache).build({"41017"})
    x, y = shapes.centroids["41017"]
    path = shapes.counties["41017"]
    assert min(_xs(path)) <= x <= max(_xs(path))
    assert min(_ys(path)) <= y <= max(_ys(path))


def test_the_centre_is_weighted_by_area_not_by_vertex_count(seeded):
    """A coastline carries far more points than the inland edge, so a plain mean
    of the vertices is dragged out to sea by however finely the coast was traced.
    """
    from refugia.artifact.geometry import _centre_of

    # A unit square whose left edge is traced with many extra points.
    dense = [(0.0, i / 50.0) for i in range(51)]
    ring = [*dense, (1.0, 1.0), (1.0, 0.0)]
    x, _ = _centre_of([ring])
    mean_x = sum(p[0] for p in ring) / len(ring)
    assert x == pytest.approx(0.5, abs=0.02)
    assert mean_x < 0.1, "the fixture has to actually be lopsided"


def test_a_degenerate_ring_falls_back_to_the_mean_of_its_points(seeded):
    """A ring with no area divides by zero in the centroid formula."""
    from refugia.artifact.geometry import _ring_area_centroid

    area, x, y = _ring_area_centroid([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    assert area == 0.0
    assert (x, y) == pytest.approx((1.0, 1.0))


def test_the_delta_encoding_is_undone_before_projecting(seeded):
    """TopoJSON arcs are stored as differences from the previous point. Read as
    absolute coordinates every county collapses towards the origin, and the map
    still renders -- as a smear near one corner."""
    cache = seeded(_topology({"41017": [0], "41013": [2]}))
    shapes = CountyShapes(cache).build({"41017", "41013"})
    east = shapes.centroids["41013"][0]
    west = shapes.centroids["41017"][0]
    assert east > west, "the eastern county must project to the east"


def test_a_negative_arc_index_reverses_that_arc(seeded):
    """TopoJSON shares one arc between neighbours, and the second traverses it
    backwards. Ignoring the sign draws a bow-tie instead of a polygon."""
    topology = _topology({"41017": [0]})
    topology["objects"]["counties"]["geometries"][0]["arcs"] = [[~0]]
    forward = CountyShapes(seeded(_topology({"41017": [0]}))).build({"41017"})
    reversed_ = CountyShapes(seeded(topology)).build({"41017"})
    assert forward.counties["41017"] != reversed_.counties["41017"]
    # Same points, opposite order: the shape it encloses is unchanged.
    assert sorted(_xs(forward.counties["41017"])) == pytest.approx(
        sorted(_xs(reversed_.counties["41017"]))
    )


def test_a_multipolygon_contributes_every_island(seeded):
    """An island dropped is a county drawn with a piece missing."""
    topology = _topology({"41017": [0]})
    topology["objects"]["counties"]["geometries"][0] = {
        "type": "MultiPolygon",
        "id": "41017",
        "arcs": [[[0]], [[1]]],
    }
    path = CountyShapes(seeded(topology)).build({"41017"}).counties["41017"]
    assert path.count("M") == 2


def test_an_empty_map_does_not_divide_by_zero(seeded):
    """Publishing a dataset whose every county is off-map must not crash."""
    shapes = CountyShapes(seeded(_topology({"02020": [0]}))).build({"02020"})
    assert shapes.counties == {} and shapes.transform == (1.0, 0.0, 0.0)


def test_the_projection_is_equal_area(seeded):
    """A choropleth on an area-distorting projection makes the large western
    counties look like they carry more of the answer than they do.

    Two boxes of the same angular size do not cover the same ground: a degree of
    longitude narrows towards the pole by cos(latitude). Equal-area means the
    projected areas keep that ratio rather than the angular one -- which is what
    separates this from Mercator, where the northern box comes out *larger*.
    """
    south, north = _corners(32.0, -100.0, 1.0), _corners(46.0, -100.0, 1.0)
    on_the_ground = math.cos(math.radians(46.5)) / math.cos(math.radians(32.5))
    assert _area(north) / _area(south) == pytest.approx(on_the_ground, rel=0.01)


def _corners(lat: float, lon: float, size: float) -> list[tuple[float, float]]:
    box = [(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size)]
    return [project(x, y) for x, y in box]


def _area(ring: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def test_the_topology_is_not_downloaded_twice(seeded, monkeypatch):
    """Eight hundred kilobytes from a CDN, on every publish."""

    def explode(*_args, **_kwargs):
        raise AssertionError("the topology was cached; nothing should reach the network")

    monkeypatch.setattr(httpx, "get", explode)
    assert CountyShapes(seeded(_topology({"41017": [0]}))).build({"41017"}).counties
    assert TOPOJSON_URL.startswith("https://")
