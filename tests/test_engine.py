"""Ranking: filters remove, weights reorder, and missing data does neither silently."""

import pytest

from refugia.metrics.registry import MetricRegistry
from refugia.scoring.criterion import Criterion
from refugia.scoring.engine import ScoringEngine
from refugia.scoring.profile import Profile


class _Stub:
    """A source that returns whatever it was handed."""

    def __init__(self, metrics, values):
        self._metrics = tuple(metrics)
        self._values = values

    @property
    def metrics(self):
        return self._metrics

    def fetch(self, places):
        return self._values


@pytest.fixture
def registry(juniper, parks):
    """A registry holding one metric of each direction."""
    reg = MetricRegistry()
    reg.register(_Stub((juniper, parks), {}))
    return reg


def test_weights_reorder(registry, places):
    """Weighting an allergen must put the lowest-allergen place first."""
    values = {
        "juniper_cover": {"00001": 40.0, "00002": 20.0, "00003": 1.0, "00004": 5.0},
        "parks": {"00001": 9.0, "00002": 5.0, "00003": 1.0, "00004": 3.0},
    }
    ranked = ScoringEngine(registry).rank(places, values, Profile("t", {"juniper_cover": 1.0}))
    assert [s.place.fips for s in ranked] == ["00003", "00004", "00002", "00001"]


def test_a_filter_removes_rather_than_penalises(registry, places):
    """A place failing a criterion must be absent, not merely ranked low."""
    values = {"juniper_cover": {p.fips: 1.0 for p in places}}
    profile = Profile(
        "t",
        {"juniper_cover": 1.0},
        criteria=(Criterion("population", "min", 60_000),),
    )
    ranked = ScoringEngine(registry).rank(places, values, profile)
    assert {s.place.fips for s in ranked} == {"00001", "00004"}


def test_state_exclusion_filter(registry, places):
    """`not_in` on a place attribute rules a state out entirely."""
    values = {"juniper_cover": {p.fips: 1.0 for p in places}}
    profile = Profile(
        "t",
        {"juniper_cover": 1.0},
        criteria=(Criterion("state", "not_in", ("Oregon", "Idaho")),),
    )
    ranked = ScoringEngine(registry).rank(places, values, profile)
    assert {s.place.state for s in ranked} == {"Maine", "Ohio"}


def test_normalisation_happens_after_filtering(registry, places):
    """Scores must spread across the survivors, not across the original field.

    If the filtered-out extremes still set the scale, every survivor bunches at
    one end and the metric stops separating them -- which is exactly when the
    user has told us they care about the difference.
    """
    values = {"juniper_cover": {"00001": 1.0, "00002": 2.0, "00003": 3.0, "00004": 900.0}}
    profile = Profile(
        "t",
        {"juniper_cover": 1.0},
        criteria=(Criterion("juniper_cover", "max", 100.0),),
    )
    ranked = ScoringEngine(registry).rank(places, values, profile)
    assert len(ranked) == 3
    assert ranked[0].total == 100.0
    assert ranked[-1].total == 0.0


def test_missing_data_is_reported_not_scored_as_zero(registry, places):
    """A place lacking one metric is judged on the rest, and says so."""
    values = {
        "juniper_cover": {"00001": 1.0, "00002": 2.0, "00003": 3.0, "00004": 4.0},
        "parks": {"00001": 9.0, "00002": 5.0, "00003": 1.0},
    }
    ranked = ScoringEngine(registry).rank(
        places,
        values,
        # min_coverage=0 so the partial place survives to be inspected; the guard
        # that would normally drop it has its own tests below.
        Profile("t", {"juniper_cover": 1.0, "parks": 1.0}, min_coverage=0.0),
    )
    echo = next(s for s in ranked if s.place.fips == "00004")
    assert echo.missing == ("parks",)
    assert echo.coverage == 0.5
    # Scored on juniper alone, where it is worst of four, so it must not lead.
    assert ranked[0].place.fips != "00004"


def test_an_unknown_metric_is_an_error_not_a_silent_zero(registry, places):
    """Weighting a metric nobody supplies must fail loudly."""
    with pytest.raises(KeyError):
        ScoringEngine(registry).rank(places, {}, Profile("t", {"nonexistent": 1.0}))


def test_a_place_missing_weighted_metrics_is_not_ranked(registry, places):
    """Absence must not read as a good score.

    Renormalising weights over the metrics a place actually has means a place
    missing the heaviest metric is judged only on the rest. For an allergen search
    that ranks a county with no vegetation data at the top, on the strength of not
    having the data that would have sunk it.
    """
    values = {
        "juniper_cover": {"00001": 40.0, "00002": 20.0, "00003": 1.0},
        "parks": {p.fips: 5.0 for p in places},
    }
    profile = Profile("t", {"juniper_cover": 1.0, "parks": 1.0}, min_coverage=0.8)
    ranked = ScoringEngine(registry).rank(places, values, profile)
    assert "00004" not in {s.place.fips for s in ranked}


def test_min_coverage_zero_keeps_everything(registry, places):
    """The guard is a default, not a law; a user may ask for partial rows."""
    values = {
        "juniper_cover": {"00001": 40.0, "00002": 20.0, "00003": 1.0},
        "parks": {p.fips: 5.0 for p in places},
    }
    profile = Profile("t", {"juniper_cover": 1.0, "parks": 1.0}, min_coverage=0.0)
    ranked = ScoringEngine(registry).rank(places, values, profile)
    assert "00004" in {s.place.fips for s in ranked}
