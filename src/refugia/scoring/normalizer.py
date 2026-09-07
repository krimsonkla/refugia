"""Puts metrics measured in different units onto one comparable scale."""

import math
from collections.abc import Mapping

from refugia.metrics.metric import Metric
from refugia.statistics import percentile_rank


class Normalizer:
    """Converts raw metric values to a 0-100 goodness scale.

    Percentile rank rather than min-max or z-score, for one reason that matters to
    this dataset: several metrics have extreme, heavily skewed tails. A single
    county with catastrophic smoke would compress every other county into the top
    few percent of a min-max scale, and the ranking would stop discriminating
    exactly where the candidates actually are. Percentile rank is invariant to that.

    `direction` is applied here and nowhere else, so the rest of the engine can
    treat every normalised value as "higher is better".
    """

    def __init__(self, *, method: str = "percentile") -> None:
        if method not in ("percentile", "minmax"):
            raise ValueError(f"unknown normalisation method {method!r}")
        self._method = method

    def normalize(self, metric: Metric, values: Mapping[str, float]) -> dict[str, float]:
        """Return {fips: 0-100} where 100 is the best value for this metric."""
        usable = {k: v for k, v in values.items() if v is not None and not math.isnan(v)}
        if not usable:
            return {}
        scaled = self._percentile(usable) if self._method == "percentile" else self._minmax(usable)
        if metric.direction == "lower_better":
            return {k: 100.0 - v for k, v in scaled.items()}
        return scaled

    @staticmethod
    def _percentile(values: Mapping[str, float]) -> dict[str, float]:
        """Rank to 0-100, averaging ranks within ties so equal values score equally."""
        return percentile_rank(values)

    @staticmethod
    def _minmax(values: Mapping[str, float]) -> dict[str, float]:
        """Linear rescale to 0-100 between the observed extremes."""
        lowest = min(values.values())
        highest = max(values.values())
        if highest == lowest:
            return dict.fromkeys(values, 50.0)
        span = highest - lowest
        return {k: 100.0 * (v - lowest) / span for k, v in values.items()}
