"""Running refugia is not redistribution; sharing the page it writes is.

The person most likely to send that file to someone is the person who just built
it, and they are the least likely to have read DATA_SOURCES.md. `publish` is the
one moment where saying so reaches them.
"""

from refugia.cli import _sharing_note
from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.scoring.profile import Profile
from refugia.store.dataset import Dataset


def _metric(key: str, citation: str = "") -> Metric:
    return Metric(
        key=key,
        label=key,
        unit="u",
        direction="lower_better",
        category="test",
        description="",
        source="s",
        citation=citation,
    )


def _dataset(*metrics: Metric) -> Dataset:
    places = tuple(
        Place(fips=f"{n:05d}", name=str(n), state="S", lat=0.0, lon=0.0, population=1)
        for n in range(1, 4)
    )
    return Dataset(places=places, metrics=metrics or (_metric("a"),), values={})


def test_it_says_the_page_carries_the_data():
    """A reader who thinks they are sending a link has misunderstood the file."""
    note = _sharing_note(_dataset(), Profile("p"))
    assert "3 places" in note
    assert "redistribution" in note


def test_it_names_the_number_of_sources_requiring_attribution():
    """Counted from the metrics, so dropping a source cannot leave the note lying."""
    note = _sharing_note(_dataset(_metric("a", "Cite A."), _metric("b", "Cite B.")), Profile("p"))
    assert "2 source" in note


def test_it_stays_quiet_about_attribution_when_nothing_requires_any():
    """Most of these sources are public domain and owe nothing."""
    note = _sharing_note(_dataset(_metric("a"), _metric("b")), Profile("p"))
    assert "attribution" not in note
    assert "redistribution" in note


def test_it_warns_that_a_home_county_travels_with_the_page():
    """home_fips is where the reader lives, and the page carries it."""
    note = _sharing_note(_dataset(), Profile("p", home_fips="17031"))
    assert "17031" in note


def test_it_says_nothing_about_home_when_none_was_set():
    """No key, nothing to warn about."""
    assert "home" not in _sharing_note(_dataset(), Profile("p")).lower()


def test_it_points_at_the_terms():
    """The note is a pointer, not a licence summary."""
    assert "DATA_SOURCES.md" in _sharing_note(_dataset(_metric("a", "C.")), Profile("p"))
