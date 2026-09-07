"""The fetching half of a metric: the contract every data adapter implements."""

from typing import Protocol, runtime_checkable

from refugia.metrics.metric import Metric
from refugia.places.place import Place


@runtime_checkable
class MetricSource(Protocol):
    """Fetches one or more metrics for a set of places.

    A source returns raw values in their natural units and never normalises or
    weights: those are the scoring engine's job, so that re-weighting costs no
    network traffic. Returning a partial mapping is legitimate -- a place absent
    from the result is missing, not zero, and the engine keeps that distinction.
    """

    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The metrics this source can supply."""

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Return {metric_key: {fips: value}} for the places it can answer for."""
