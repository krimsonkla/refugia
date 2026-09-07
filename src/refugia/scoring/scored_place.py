"""One place's result: its total, and the contribution behind it."""

from dataclasses import dataclass

from refugia.places.place import Place


@dataclass(frozen=True, slots=True)
class ScoredPlace:
    """A ranked candidate.

    `contributions` is carried alongside the total deliberately: a ranking a user
    cannot interrogate is one they cannot trust or correct. It is what lets the
    artifact explain why a place placed where it did, and what lets the local model
    answer "why is this above that" without re-deriving anything.
    """

    place: Place
    total: float
    normalized: dict[str, float]
    raw: dict[str, float]
    contributions: dict[str, float]
    missing: tuple[str, ...]

    @property
    def coverage(self) -> float:
        """Share of weighted metrics this place actually had data for, 0-1."""
        wanted = len(self.contributions) + len(self.missing)
        return 1.0 if wanted == 0 else len(self.contributions) / wanted
