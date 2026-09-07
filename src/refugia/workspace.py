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
        self._vegetation: LandfireVegetationSource | None = None

    @property
    def cache(self) -> Cache:
        """The shared on-disk cache."""
        return self._cache

    @property
    def dataset_path(self) -> Path:
        """Where `fetch` writes and every other command reads."""
        return self._root / "data" / "dataset.json"

    @property
    def vegetation(self) -> LandfireVegetationSource:
        """The one LANDFIRE sampler, shared by the county metrics and the city panel.

        Constructed here because the radius is a run-level decision: the city panel
        used to build its own with a default Sampling, so `--radius-km 50` sampled
        cities at 25 km while the page's own hint text said 50.
        """
        if self._vegetation is None:
            self._vegetation = LandfireVegetationSource(
                self._cache, sampling=Sampling(radius_km=self._radius_km)
            )
        return self._vegetation

    @property
    def packaged_spec_dir(self) -> Path:
        """The specs that ship with refugia itself.

        Inside the package rather than beside it, because a wheel carries what is
        under `src/refugia/` and nothing else. When they lived at the project root
        an installed copy registered fifteen metrics instead of twenty-one and said
        nothing about the six that had vanished.
        """
        return Path(__file__).parent / "specs"

    @property
    def spec_dir(self) -> Path:
        """Where a user's own specs go, beside the project rather than inside it."""
        return self._root / "specs"

    @property
    def spec_files(self) -> tuple[Path, ...]:
        """Every spec to register: the shipped ones, then any the user added.

        Both, not one or the other. A key declared twice raises at registration,
        which is the right answer -- shadowing a shipped metric with a local file
        of the same name should be loud rather than silent.
        """
        shipped = sorted(self.packaged_spec_dir.glob("*.json"))
        local = sorted(self.spec_dir.glob("*.json")) if self.spec_dir.exists() else []
        return tuple(shipped) + tuple(local)

    def build_registry(self) -> MetricRegistry:
        """Register every built-in source, then every declarative spec on disk.

        Specs are registered last so a written adapter always wins a key collision:
        a spec dropped in by hand or by a model cannot silently displace an adapter
        whose behaviour is covered by tests.
        """
        registry = MetricRegistry()
        registry.register(self.vegetation)
        registry.register(CdcPlacesSource(self._cache))
        registry.register(NasaPowerClimateSource(self._cache))
        registry.register(EpaAirQualitySource(self._cache))
        registry.register(ZillowHomeValueSource(self._cache))
        for spec in self.spec_files:
            try:
                registry.register(DeclarativeSource.from_file(spec, self._cache))
            except ValueError as error:
                # Both sides of a duplicate-key collision are specs, and the bare
                # message names neither file. The one you can act on is this one.
                raise ValueError(f"{spec}: {error}") from error
        return registry

    def build_places(self, *, universe: str = "metro_micro", refresh: bool = False):
        """Load the candidate place universe."""
        return PlaceRegistry.load(self._cache, universe=universe, refresh=refresh)
