"""The dataset is the handoff between the slow half and the fast half."""

from refugia.store.dataset import Dataset


def test_round_trips_through_a_file(tmp_path, places, juniper):
    """Fetch writes it, every other command reads it; nothing may be lost."""
    dataset = Dataset(places, (juniper,), {"juniper_cover": {"00001": 12.5}})
    path = tmp_path / "d.json"
    dataset.save(path)
    reloaded = Dataset.load(path)
    assert reloaded.places == dataset.places
    assert reloaded.metrics == dataset.metrics
    assert reloaded.values == dataset.values


def test_coverage_reports_the_share_with_data(places, juniper):
    """Coverage is how a user learns a metric is thin before trusting a ranking."""
    dataset = Dataset(places, (juniper,), {"juniper_cover": {"00001": 1.0, "00002": 2.0}})
    assert dataset.coverage()["juniper_cover"] == 0.5


def test_a_metric_with_no_values_reports_zero_coverage(places, juniper):
    """A source that returned nothing must be visible, not absent."""
    assert Dataset(places, (juniper,), {}).coverage()["juniper_cover"] == 0.0
