"""A profile is the serialisable form of a search, shared by every front end."""

import json

from refugia.scoring.criterion import Criterion
from refugia.scoring.profile import Profile


def test_round_trips_through_json(tmp_path):
    """The CLI, the page and the model must all read and write the same shape."""
    profile = Profile(
        "t",
        {"juniper_cover": 2.0},
        criteria=(
            Criterion("population", "min", 40_000),
            Criterion("state", "not_in", ("Texas",)),
        ),
    )
    path = tmp_path / "p.json"
    path.write_text(json.dumps(profile.to_dict()))
    reloaded = Profile.load(path)
    assert reloaded.weights == profile.weights
    assert reloaded.criteria == profile.criteria


def test_weights_are_rescaled_to_sum_to_one():
    """Absolute weight magnitudes must not change the score's range."""
    assert Profile("t", {"a": 3.0, "b": 1.0}).normalized_weights == {"a": 0.75, "b": 0.25}


def test_no_weights_yields_no_shares():
    """An empty profile is legal and produces nothing, rather than dividing by zero."""
    assert Profile("t", {}).normalized_weights == {}


def test_criterion_rejects_a_missing_value():
    """A place with no data cannot be said to satisfy a requirement."""
    assert Criterion("home_value", "max", 400_000).accepts(None) is False
    assert Criterion("home_value", "max", 400_000).accepts(350_000) is True


def test_home_survives_a_round_trip(tmp_path):
    """The reference point is part of the saved search, not a UI setting."""
    path = tmp_path / "p.json"
    path.write_text(json.dumps(Profile("t", {"a": 1.0}, home_fips="17031").to_dict()))
    assert Profile.load(path).home_fips == "17031"


def test_home_is_optional():
    """A profile with nowhere to compare against is still valid."""
    assert Profile("t", {"a": 1.0}).home_fips is None
