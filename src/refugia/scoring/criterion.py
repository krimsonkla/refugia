"""One hard filter: a condition a place must satisfy to stay in the running."""

from dataclasses import dataclass
from typing import Literal

Comparison = Literal["min", "max", "in", "not_in"]


@dataclass(frozen=True, slots=True)
class Criterion:
    """A pass/fail condition evaluated on a raw metric or place attribute.

    Filters are separate from weights because they answer a different question. A
    weight says "this matters"; a filter says "without this, nothing else matters".
    Folding a disqualifier into a weight lets a place win on everything else and
    surface anyway, which is the failure the two-mechanism design exists to prevent.
    """

    field: str
    comparison: Comparison
    value: float | tuple[str, ...]

    def accepts(self, observed: float | str | None) -> bool:
        """Whether one observed value passes. A missing value never passes."""
        if observed is None:
            return False
        if self.comparison == "min":
            return float(observed) >= float(self.value)  # type: ignore[arg-type]
        if self.comparison == "max":
            return float(observed) <= float(self.value)  # type: ignore[arg-type]
        if self.comparison == "in":
            return str(observed) in self.value
        return str(observed) not in self.value
