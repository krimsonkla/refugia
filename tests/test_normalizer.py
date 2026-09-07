"""The normaliser is where `direction` stops mattering to everything downstream."""

from refugia.scoring.normalizer import Normalizer
from refugia.statistics import percentile_rank


def test_lower_better_inverts_the_scale(juniper):
    """The worst raw value must score 0 and the best 100."""
    scores = Normalizer().normalize(juniper, {"a": 1.0, "b": 5.0, "c": 50.0})
    assert scores["a"] == 100.0
    assert scores["c"] == 0.0
    assert 0 < scores["b"] < 100


def test_higher_better_keeps_the_scale(parks):
    """A higher-is-better metric ranks the largest value best."""
    scores = Normalizer().normalize(parks, {"a": 1.0, "b": 5.0, "c": 50.0})
    assert scores["c"] == 100.0
    assert scores["a"] == 0.0


def test_ties_share_a_score(parks):
    """Equal raw values must not be separated by input order."""
    scores = Normalizer().normalize(parks, {"a": 7.0, "b": 7.0, "c": 1.0})
    assert scores["a"] == scores["b"]
    assert scores["c"] < scores["a"]


def test_percentile_resists_an_outlier(juniper):
    """One catastrophic value must not compress everything else together.

    This is the reason percentile is the default. Under min-max the three low
    values would land within a fraction of a point of each other and the metric
    would stop discriminating between the places actually in contention.
    """
    values = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 10_000.0}
    percentile = Normalizer(method="percentile").normalize(juniper, values)
    minmax = Normalizer(method="minmax").normalize(juniper, values)
    assert percentile["a"] - percentile["c"] > 60
    assert minmax["a"] - minmax["c"] < 1


def test_empty_input_yields_no_scores(parks):
    """A metric nobody has data for produces an empty mapping, not an error."""
    assert Normalizer().normalize(parks, {}) == {}


def test_percentile_rank_of_nothing_is_nothing():
    """A metric no surviving place has data for reaches the normaliser empty."""
    assert percentile_rank({}) == {}


def test_percentile_rank_of_one_value_is_the_midpoint():
    """With nobody to compare against, neither end of the scale is honest."""
    assert percentile_rank({"00001": 7.0}) == {"00001": 50.0}
