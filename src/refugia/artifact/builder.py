"""Renders a dataset and profile into one self-contained HTML page."""

import json
from pathlib import Path

from refugia.artifact.city_markers import CityMarkers
from refugia.artifact.city_profile import CITY_ONLY, CityProfile
from refugia.artifact.geometry import CountyShapes
from refugia.scoring.profile import Profile
from refugia.store.cache import Cache
from refugia.store.dataset import Dataset

TEMPLATE = Path(__file__).with_name("template.html")
PLACEHOLDER = "__REFUGIA_DATA__"


class ArtifactBuilder:
    """Bundles places, metrics, values and county outlines into one file.

    The page re-implements scoring rather than receiving a precomputed ranking,
    because the sliders have to re-rank without a round trip. That duplication is
    a real hazard: the JavaScript and the Python engine can drift, and nothing in
    this repo currently executes both to compare them. Any change to ranking
    semantics has to be made in `scoring/` and in `template.html` together.
    """

    def __init__(self, cache: Cache) -> None:
        self._cache = cache

    def build(self, dataset: Dataset, profile: Profile, out: Path) -> Path:
        """Write the page and return its path."""
        shapes = CountyShapes(self._cache).build({p.fips for p in dataset.places})
        payload = dataset.to_dict()
        payload["paths"] = shapes.counties
        payload["state_paths"] = shapes.states
        payload["centroids"] = shapes.centroids
        cities = CityMarkers(self._cache).for_places(dataset.places, shapes.transform)
        payload["cities"] = cities
        payload["city_metrics"] = CityProfile(self._cache).build(cities)
        payload["city_only_metrics"] = list(CITY_ONLY)
        payload["profile"] = profile.to_dict()
        payload["subtitle"] = self._subtitle(dataset, profile)

        html = TEMPLATE.read_text(encoding="utf-8")
        # `</script>` inside embedded JSON would close the host tag early.
        encoded = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html.replace(PLACEHOLDER, encoded), encoding="utf-8")
        return out

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
