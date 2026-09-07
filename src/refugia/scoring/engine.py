"""Turns raw metric values plus a profile into a ranking."""

from collections.abc import Mapping

from refugia.metrics.registry import MetricRegistry
from refugia.places.place import Place
from refugia.scoring.normalizer import Normalizer
from refugia.scoring.profile import Profile
from refugia.scoring.scored_place import ScoredPlace
from refugia.scoring.vocabulary import check_criteria


class ScoringEngine:
    """Applies filters, normalises, weights and ranks.

    Normalisation happens over the places that survive filtering, not over the
    whole country. That is the deliberate choice: once a user rules out everywhere
    above a cost ceiling, "expensive" should mean expensive among the places still
    under consideration, or every survivor bunches at one end of the scale and the
    metric stops separating them.
    """

    def __init__(self, registry: MetricRegistry) -> None:
        self._registry = registry

    def rank(
        self,
        places: tuple[Place, ...],
        values: Mapping[str, Mapping[str, float]],
        profile: Profile,
    ) -> list[ScoredPlace]:
        """Rank `places` best-first under `profile`."""
        check_criteria(profile, self._registry.metrics)
        survivors = self._apply_filters(places, values, profile)
        weights = profile.normalized_weights
        normalizer = Normalizer(method=profile.normalization)

        surviving_fips = {p.fips for p in survivors}
        normalized: dict[str, dict[str, float]] = {}
        for key in weights:
            if key not in self._registry:
                # A typo in a hand-written profile is the likeliest way to get
                # here, and the only useful answer is where to find the real keys.
                raise KeyError(
                    f"profile weights an unknown metric {key!r}; "
                    "run `refugia metrics` for the registered keys"
                )
            observed = {
                fips: value for fips, value in values.get(key, {}).items() if fips in surviving_fips
            }
            normalized[key] = normalizer.normalize(self._registry.metric(key), observed)

        scored = (self._score(p, weights, normalized, values) for p in survivors)
        # A place missing a metric is scored on the rest, which quietly rewards it for
        # the absence: a county outside the vegetation layer would otherwise rank top
        # on an allergen search precisely because its allergen data is unknown.
        ranked = [s for s in scored if s.coverage >= profile.min_coverage]
        return sorted(ranked, key=lambda s: s.total, reverse=True)

    def _apply_filters(
        self,
        places: tuple[Place, ...],
        values: Mapping[str, Mapping[str, float]],
        profile: Profile,
    ) -> tuple[Place, ...]:
        """Drop places failing any criterion."""
        kept = []
        for place in places:
            if all(
                criterion.accepts(self._observe(place, criterion.field, values))
                for criterion in profile.criteria
            ):
                kept.append(place)
        return tuple(kept)

    @staticmethod
    def _observe(
        place: Place,
        field: str,
        values: Mapping[str, Mapping[str, float]],
    ) -> float | str | None:
        """Read a filter field from either the place record or the metric values."""
        if hasattr(place, field):
            return getattr(place, field)
        return values.get(field, {}).get(place.fips)

    @staticmethod
    def _score(
        place: Place,
        weights: Mapping[str, float],
        normalized: Mapping[str, Mapping[str, float]],
        values: Mapping[str, Mapping[str, float]],
    ) -> ScoredPlace:
        """Combine one place's normalised values into a total.

        Weights are renormalised over the metrics this place actually has, so a
        place missing one input is not silently penalised as if it had scored zero
        there. `missing` and `coverage` keep that visible rather than hiding it.
        """
        contributions: dict[str, float] = {}
        present: dict[str, float] = {}
        missing: list[str] = []
        for key, weight in weights.items():
            score = normalized.get(key, {}).get(place.fips)
            if score is None:
                missing.append(key)
                continue
            present[key] = weight
        available = sum(abs(w) for w in present.values())
        total = 0.0
        scores: dict[str, float] = {}
        for key, weight in present.items():
            score = normalized[key][place.fips]
            share = weight / available if available else 0.0
            contributions[key] = share * score
            scores[key] = score
            total += share * score
        return ScoredPlace(
            place=place,
            total=total,
            normalized=scores,
            raw={k: values[k][place.fips] for k in scores if place.fips in values.get(k, {})},
            contributions=contributions,
            missing=tuple(missing),
        )
