"""The set of metrics known to this run, and the sources that supply them."""

from refugia.metrics.metric import Metric
from refugia.metrics.source import MetricSource


class MetricRegistry:
    """Maps metric keys to the source that produces them.

    Registration is the whole extension point: adding a metric means constructing a
    source and registering it, with no edit to scoring, the CLI or the artifact. A
    key may be claimed by exactly one source, so a second claim is an error rather
    than a silent last-writer-wins that would make results depend on import order.
    """

    def __init__(self) -> None:
        self._sources: list[MetricSource] = []
        self._by_key: dict[str, MetricSource] = {}
        self._metrics: dict[str, Metric] = {}

    def register(self, source: MetricSource) -> None:
        """Add a source, claiming each of the metric keys it declares."""
        for metric in source.metrics:
            if metric.key in self._by_key:
                raise ValueError(
                    f"metric key {metric.key!r} already supplied by "
                    f"{type(self._by_key[metric.key]).__name__}"
                )
            self._by_key[metric.key] = source
            self._metrics[metric.key] = metric
        self._sources.append(source)

    @property
    def sources(self) -> tuple[MetricSource, ...]:
        """Every registered source, in registration order."""
        return tuple(self._sources)

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """Every declared metric, in registration order."""
        return tuple(self._metrics.values())

    def metric(self, key: str) -> Metric:
        """The declaration for one key."""
        if key not in self._metrics:
            raise KeyError(f"unknown metric {key!r}; known: {sorted(self._metrics)}")
        return self._metrics[key]

    def source_for(self, key: str) -> MetricSource:
        """The source that supplies one key."""
        if key not in self._by_key:
            raise KeyError(f"unknown metric {key!r}; known: {sorted(self._metrics)}")
        return self._by_key[key]

    def __contains__(self, key: object) -> bool:
        return key in self._metrics
