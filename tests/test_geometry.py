"""The projection runs at build time, so its errors would ship silently in a picture."""

import math

from refugia.artifact.geometry import OFF_MAP_STATES, project


def test_north_is_up():
    """SVG y grows downward, so a more northerly point must have a smaller y."""
    _, y_north = project(-100.0, 48.0)
    _, y_south = project(-100.0, 30.0)
    assert y_north < y_south


def test_east_is_right():
    """Longitude must increase to the right of the projection origin."""
    x_west, _ = project(-120.0, 40.0)
    x_east, _ = project(-80.0, 40.0)
    assert x_west < x_east


def test_the_origin_meridian_is_centred():
    """A point on the central meridian has no horizontal offset."""
    x, _ = project(-96.0, 39.0)
    assert math.isclose(x, 0.0, abs_tol=1e-9)


def test_equal_area_preserves_relative_size():
    """Two equal-area cells at different latitudes must project to similar areas.

    A conformal projection would inflate the northern cell substantially. On a
    choropleth that reads as the north mattering more, which is a lie the map
    tells without anyone writing it down.
    """

    def cell_area(lat: float) -> float:
        span_lon = 1.0 / math.cos(math.radians(lat))
        corners = [
            project(-100.0, lat),
            project(-100.0 + span_lon, lat),
            project(-100.0 + span_lon, lat + 1.0),
            project(-100.0, lat + 1.0),
        ]
        total = 0.0
        for i in range(4):
            x1, y1 = corners[i]
            x2, y2 = corners[(i + 1) % 4]
            total += x1 * y2 - x2 * y1
        return abs(total) / 2

    assert cell_area(48.0) / cell_area(30.0) < 1.15


def test_non_conus_states_are_off_the_map():
    """Alaska and Hawaii have no CONUS vegetation layer, so they cannot be coloured."""
    assert "02" in OFF_MAP_STATES
    assert "15" in OFF_MAP_STATES
    assert "41" not in OFF_MAP_STATES
