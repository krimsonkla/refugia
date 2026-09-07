"""What a criterion is allowed to name, in one place.

Three paths accept criteria and each knew the vocabulary separately: the planner
filtered the model's output against a hand-written subset, the engine did not
check at all, and the page applies criteria in JavaScript. An unchecked field is
not an error anywhere -- it simply matches nothing, so a misspelling looks
exactly like a requirement no county in the country can meet.
"""

from collections.abc import Iterable

from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.scoring.profile import Profile

# Read off the record rather than listed, so a new column or derived property on
# `Place` becomes filterable the day it lands instead of the day someone
# remembers this file. `_observe` reads exactly these by `getattr`.
PLACE_FIELDS = frozenset(f for f in dir(Place) if not f.startswith("_"))


def criterion_fields(metrics: Iterable[Metric]) -> set[str]:
    """Every field name a criterion may use: metric keys plus place attributes."""
    return {m.key for m in metrics} | PLACE_FIELDS


def check_criteria(profile: Profile, metrics: Iterable[Metric]) -> None:
    """Raise on a criterion naming a field that no metric and no place has."""
    allowed = criterion_fields(metrics)
    for criterion in profile.criteria:
        if criterion.field not in allowed:
            raise KeyError(
                f"profile requires an unknown field {criterion.field!r}; "
                "run `refugia metrics` for the metric keys, or name a place "
                f"attribute: {', '.join(sorted(PLACE_FIELDS))}"
            )
