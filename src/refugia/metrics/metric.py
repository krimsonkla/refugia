"""The declaration half of a metric: what it means, independent of how it is fetched."""

from dataclasses import dataclass
from typing import Literal

Direction = Literal["higher_better", "lower_better"]


# A frozen record of what one column is. The attribute count is the number of
# things worth saying about a column, not accumulated state -- splitting it to
# satisfy the threshold would buy an indirection and cost the flat shape that
# to_dict, the spec files and the page payload all share.
@dataclass(frozen=True, slots=True)
class Metric:  # pylint: disable=too-many-instance-attributes
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
    # Attribution travels with the metric because the published page is what gets
    # shared, and an obligation recorded only in DATA_SOURCES.md cannot reach it.
    # Empty for the public-domain sources, which owe nothing and should stay terse.
    citation: str = ""
    terms_url: str = ""

    def __post_init__(self) -> None:
        if not self.key.isidentifier():
            raise ValueError(f"metric key {self.key!r} must be a valid identifier")
