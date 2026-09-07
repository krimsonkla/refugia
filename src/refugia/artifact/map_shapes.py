"""The two outline layers a choropleth needs: the shapes, and the frame to read them in."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MapShapes:
    """County fills and state borders, projected on one shared transform.

    They must be built together. Projecting each against its own extent would fit
    the two layers to different rectangles, and the borders would sit a few pixels
    off the counties they are supposed to bound.

    `centroids` are in the same projected space, so the page can ask which counties
    fall inside the current view without measuring anything in the browser.
    `transform` is carried so anything added to the map later - city markers, for
    instance - lands on the same coordinates rather than on its own.
    """

    counties: dict[str, str]
    states: dict[str, str]
    centroids: dict[str, tuple[float, float]]
    transform: tuple[float, float, float]
