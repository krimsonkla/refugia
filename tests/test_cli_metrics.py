"""The profile's vocabulary has to be discoverable from the tool, not just the docs."""

from typer.testing import CliRunner

from refugia.cli import app

runner = CliRunner()


def test_metrics_lists_every_registered_key():
    """A reader writing a profile needs the keys, and they cannot be guessed."""
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 0
    # One from an adapter, one from the CDC measure list, one from specs/ - the
    # three tiers a key can come from, which the reader cannot distinguish.
    for key in ("juniper_cover", "depression", "wildfire_risk"):
        assert key in result.stdout


def test_metrics_says_when_the_spec_tier_is_absent(tmp_path):
    """A short list that looks complete is worse than a short list that says so."""
    result = runner.invoke(app, ["metrics", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "wildfire_risk" not in result.stdout
    assert "no specs/" in result.stdout


def test_metrics_says_which_way_is_better():
    """A weight is never negative, because direction already carries the sign."""
    result = runner.invoke(app, ["metrics"])
    assert "lower is better" in result.stdout
    assert "higher is better" in result.stdout


def test_metrics_needs_no_dataset(tmp_path):
    """It reads the registry, so it works before the first fetch."""
    assert not (tmp_path / "data" / "dataset.json").exists()
    assert runner.invoke(app, ["metrics", "--root", str(tmp_path)]).exit_code == 0
