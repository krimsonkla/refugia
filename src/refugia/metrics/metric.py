"""The declaration half of a metric: what it means, independent of how it is fetched."""

from dataclasses import dataclass
from typing import Literal

Direction = Literal["higher_better", "lower_better"]


@dataclass(frozen=True, slots=True)
class Metric:
    """What a column means.

    `direction` is the field that makes a metric composable. Scoring never needs to
    know that smoke is bad and sunshine is good; it reads `direction` and normalises
    accordingly, which is what lets a metric be added without touching the engine.
    """

    key: str
    label: str
    unit: str
    direction: Direction
    category: str
    description: str
    source: str

    def __post_init__(self) -> None:
        if not self.key.isidentifier():
            raise ValueError(f"metric key {self.key!r} must be a valid identifier")
