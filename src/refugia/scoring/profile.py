"""A saved search: what matters, how much, and what disqualifies."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from refugia.scoring.criterion import Criterion


@dataclass(frozen=True, slots=True)
class Profile:
    """The whole of a user's preference, as data rather than code.

    Keeping this serialisable is what lets the same object come from a JSON file,
    the CLI, the artifact's sliders, or the local model's query planner. Nothing
    downstream can tell which produced it, so a new front end costs no engine change.
    """

    name: str
    weights: dict[str, float] = field(default_factory=dict)
    criteria: tuple[Criterion, ...] = ()
    normalization: str = "percentile"
    min_coverage: float = 0.8
    home_fips: str | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "Profile":
        """Build from a plain mapping, as parsed from JSON."""
        criteria = tuple(
            Criterion(
                field=c["field"],
                comparison=c["comparison"],
                value=tuple(c["value"]) if isinstance(c["value"], list) else c["value"],
            )
            for c in payload.get("criteria", [])
        )
        return cls(
            name=payload.get("name", "unnamed"),
            weights={k: float(v) for k, v in payload.get("weights", {}).items()},
            criteria=criteria,
            normalization=payload.get("normalization", "percentile"),
            min_coverage=float(payload.get("min_coverage", 0.8)),
            home_fips=payload.get("home_fips"),
        )

    @classmethod
    def load(cls, path: Path) -> "Profile":
        """Read a profile from a JSON file."""
        return cls.from_dict(json.loads(path.read_text()))

    def to_dict(self) -> dict:
        """Round-trip back to a plain mapping."""
        return {
            "name": self.name,
            "weights": self.weights,
            "normalization": self.normalization,
            "min_coverage": self.min_coverage,
            "home_fips": self.home_fips,
            "criteria": [
                {
                    "field": c.field,
                    "comparison": c.comparison,
                    "value": list(c.value) if isinstance(c.value, tuple) else c.value,
                }
                for c in self.criteria
            ],
        }

    @property
    def normalized_weights(self) -> dict[str, float]:
        """Positive weights rescaled to sum to 1, so a total score is always 0-100.

        A weight of zero or less is not a metric weighted lightly, it is a metric
        not asked for. Carrying it kept it in the coverage denominator, so
        switching a metric off could drop a place for missing data it was no longer
        being judged on -- and the page, which drops them, disagreed. Direction
        already encodes whether high or low is good, so a negative weight has no
        meaning left to honour either.
        """
        positive = {k: w for k, w in self.weights.items() if w > 0}
        total = sum(positive.values())
        if total == 0:
            return {}
        return {k: w / total for k, w in positive.items()}
