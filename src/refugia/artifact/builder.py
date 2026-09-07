"""Renders a dataset and profile into one self-contained HTML page."""

import json
from pathlib import Path

from refugia.artifact.city_markers import CityMarkers
from refugia.artifact.city_profile import CityProfile
from refugia.metrics.city_only import CITY_ONLY
from refugia.artifact.geometry import CountyShapes
from refugia.scoring.profile import Profile
from refugia.store.cache import Cache
from refugia.store.dataset import Dataset

TEMPLATE = Path(__file__).with_name("template.html")
PLACEHOLDER = "__REFUGIA_DATA__"
# The template is a fragment on purpose: a host that publishes it supplies the
# document around it, and a second `<html>` nested inside that one is worse than
# none. A file written to disk has no such host.
HEAD_END = "</style>"
DOCUMENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
{head}
</head>
<body>
{body}
</body>
</html>
"""


class ArtifactBuilder:
    """Bundles places, metrics, values and county outlines into one file.

    The page re-implements scoring rather than receiving a precomputed ranking,
    because the sliders have to re-rank without a round trip. That duplication is
    a real hazard: the JavaScript and the Python engine can drift. Any change to
    ranking semantics has to be made in `scoring/` and in `template.html` together,
    and `tests/conformance/vectors.json` runs the same cases through both --
    including the profile's requirements and normalisation method, which the page
    once ignored while every vector passed.
    """

    def __init__(self, cache: Cache, *, vegetation=None) -> None:
        self._cache = cache
        # Passed through to the city panel so the radius the run was configured
        # with is the radius the city figures are sampled at.
        self._vegetation = vegetation

    def build(self, dataset: Dataset, profile: Profile, out: Path) -> Path:
        """Write the page and return its path."""
        shapes = CountyShapes(self._cache).build({p.fips for p in dataset.places})
        payload = dataset.to_dict()
        payload["paths"] = shapes.counties
        payload["state_paths"] = shapes.states
        payload["centroids"] = shapes.centroids
        cities = CityMarkers(self._cache).for_places(dataset.places, shapes.transform)
        payload["cities"] = cities
        payload["city_metrics"] = CityProfile(self._cache, vegetation=self._vegetation).build(
            cities
        )
        payload["city_only_metrics"] = list(CITY_ONLY)
        payload["profile"] = profile.to_dict()
        payload["subtitle"] = self._subtitle(dataset, profile)

        html = TEMPLATE.read_text(encoding="utf-8")
        # `</script>` inside embedded JSON would close the host tag early.
        encoded = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.as_document(html.replace(PLACEHOLDER, encoded)), encoding="utf-8")
        return out

    @staticmethod
    def as_document(fragment: str) -> str:
        """Wrap the template fragment in the document a browser needs.

        Without a doctype the page renders in quirks mode; without a charset the
        non-ASCII characters in the credits arrive as mojibake; without a viewport
        every phone lays it out at desktop width.
        """
        head, marker, body = fragment.partition(HEAD_END)
        if not marker:
            # No stylesheet to keep out of the body, so all of it is body.
            head, body = "", fragment
        else:
            head += marker
        return DOCUMENT.format(head=head.strip(), body=body.strip())

    @staticmethod
    def _subtitle(dataset: Dataset, profile: Profile) -> str:
        """One line describing what the reader is looking at."""
        weighted = sorted(
            (k for k, w in profile.weights.items() if w > 0),
            key=lambda k: -profile.weights[k],
        )
        labels = {m.key: m.label.lower() for m in dataset.metrics}
        named = ", ".join(labels.get(k, k) for k in weighted[:4])
        return (
            f"{len(dataset.places):,} US counties in a metro or micropolitan area, "
            f"scored on {named}. Move the sliders to change what matters; "
            f"requirements remove places outright."
        )
