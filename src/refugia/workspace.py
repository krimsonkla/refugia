"""The composition root: builds the registry, the place universe and the cache."""

from pathlib import Path

from refugia.metrics.registry import MetricRegistry
from refugia.metrics.sources.cdc_places import CdcPlacesSource
from refugia.metrics.sources.declarative import DeclarativeSource
from refugia.metrics.sources.epa_air_quality import EpaAirQualitySource
from refugia.metrics.sources.landfire_vegetation import LandfireVegetationSource
from refugia.metrics.sources.nasa_power_climate import NasaPowerClimateSource
from refugia.metrics.sources.sampling import Sampling
from refugia.metrics.sources.zillow_home_value import ZillowHomeValueSource
from refugia.places.registry import PlaceRegistry
from refugia.store.cache import Cache


class Workspace:
    """Wires the object graph for one run.

    Every collaborator is constructed here and injected downward, so no module
    reaches for a global cache, registry or settings object. Adding a source is a
    single registration in `build_registry`, which is the only place that knows the
    full metric set exists.
    """

    def __init__(self, root: Path, *, radius_km: float = 25.0) -> None:
        self._root = root
        self._radius_km = radius_km
        self._cache = Cache(root / "data" / "cache")

    @property
    def cache(self) -> Cache:
        """The shared on-disk cache."""
        return self._cache

    @property
    def dataset_path(self) -> Path:
        """Where `fetch` writes and every other command reads."""
        return self._root / "data" / "dataset.json"

    @property
    def spec_dir(self) -> Path:
        """Where declarative metric specs live."""
        return self._root / "specs"

    def build_registry(self) -> MetricRegistry:
        """Register every built-in source, then every declarative spec on disk.

        Specs are registered last so a written adapter always wins a key collision:
        a spec dropped in by hand or by a model cannot silently displace an adapter
        whose behaviour is covered by tests.
        """
        registry = MetricRegistry()
        registry.register(
            LandfireVegetationSource(self._cache, sampling=Sampling(radius_km=self._radius_km))
        )
        registry.register(CdcPlacesSource(self._cache))
        registry.register(NasaPowerClimateSource(self._cache))
        registry.register(EpaAirQualitySource(self._cache))
        registry.register(ZillowHomeValueSource(self._cache))
        for spec in sorted(self.spec_dir.glob("*.json")) if self.spec_dir.exists() else []:
            registry.register(DeclarativeSource.from_file(spec, self._cache))
        return registry

    def build_places(self, *, universe: str = "metro_micro", refresh: bool = False):
        """Load the candidate place universe."""
        return PlaceRegistry.load(self._cache, universe=universe, refresh=refresh)
