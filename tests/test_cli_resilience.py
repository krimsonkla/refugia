"""Nine upstreams are pinned to dated paths, so one of them rotting is a when."""

import httpx
import pytest
from typer.testing import CliRunner

from refugia.cli import _collect, app
from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.store.dataset import Dataset

runner = CliRunner()


def _metric(key: str) -> Metric:
    return Metric(
        key=key,
        label=key,
        unit="u",
        direction="lower_better",
        category="test",
        description="",
        source="s",
    )


class _Working:
    """A source that answers."""

    def __init__(self, key: str) -> None:
        self.metrics = (_metric(key),)
        self._key = key

    def fetch(self, places):
        return {self._key: {"00001": 1.0}}


class _Rotted:
    """A source whose upstream has moved."""

    def __init__(self, key: str) -> None:
        self.metrics = (_metric(key),)

    def fetch(self, places):
        request = httpx.Request("GET", "https://example.invalid/moved.csv")
        raise httpx.HTTPStatusError(
            "404 Not Found", request=request, response=httpx.Response(404, request=request)
        )


class _Registry:
    def __init__(self, *sources):
        self.sources = sources


def test_a_failing_source_does_not_stop_the_ones_after_it():
    """The whole point: a rotted URL costs one metric, not every later one."""
    registry = _Registry(_Working("a"), _Rotted("b"), _Working("c"))
    values, failed = _collect(registry, (), {}, set())
    assert set(values) == {"a", "c"}
    assert [name for name, _ in failed] == ["_Rotted"]


def test_the_failure_is_reported_not_swallowed():
    """Continuing quietly would be worse than crashing."""
    registry = _Registry(_Rotted("b"))
    _, failed = _collect(registry, (), {}, set())
    assert failed and "404" in failed[0][1]


def test_existing_values_survive_a_failure():
    """A refetch that hits a dead upstream must not lose what was already there."""
    registry = _Registry(_Rotted("b"))
    values, _ = _collect(registry, (), {"a": {"00001": 1.0}}, set())
    assert values == {"a": {"00001": 1.0}}


def test_every_source_can_fail_without_raising():
    """Total failure is still a report, not a traceback."""
    registry = _Registry(_Rotted("a"), _Rotted("b"))
    values, failed = _collect(registry, (), {}, set())
    assert values == {}
    assert len(failed) == 2


@pytest.mark.parametrize(
    "command",
    [
        ["rank", "--profile", "profiles/example.json"],
        ["publish", "--profile", "profiles/example.json"],
        ["ask", "anything"],
    ],
)
def test_a_missing_dataset_says_what_to_run(command, tmp_path):
    """Before the first fetch these three all raised FileNotFoundError."""
    result = runner.invoke(app, [*command, "--root", str(tmp_path)])
    assert result.exit_code != 0
    assert "refugia fetch" in result.output
    assert "Traceback" not in result.output


class _Empty:
    """A source whose upstream renamed a column: it answers, with nothing."""

    def __init__(self, key: str) -> None:
        self.metrics = (_metric(key),)
        self._key = key

    def fetch(self, places):
        return {self._key: {}}


def test_an_empty_return_does_not_delete_what_a_previous_fetch_saved():
    """The failure that does not raise, and used to wipe the column silently."""
    registry = _Registry(_Empty("a"))
    values, failed = _collect(registry, (), {"a": {"00001": 79.2}}, set())
    assert values == {"a": {"00001": 79.2}}
    assert failed and "no values" in failed[0][1]


def test_a_source_returning_some_values_still_merges_them():
    """Merging per metric must not stop a good fetch replacing what it covers."""
    registry = _Registry(_Working("a"))
    values, failed = _collect(registry, (), {"a": {"00002": 1.0}}, set())
    assert values["a"] == {"00002": 1.0, "00001": 1.0}
    assert failed == []


def test_publish_reports_an_unreachable_upstream_instead_of_a_traceback(tmp_path, monkeypatch):
    """The first publish downloads the map and city layers, so it can fail too."""
    (tmp_path / "data").mkdir()
    Dataset(
        places=(Place(fips="00001", name="A", state="S", lat=0.0, lon=0.0, population=1),),
        metrics=(_metric("a"),),
        values={"a": {"00001": 1.0}},
    ).save(tmp_path / "data" / "dataset.json")

    def _down(self, dataset, profile, out):
        raise httpx.ConnectError("cdn is down")

    monkeypatch.setattr("refugia.artifact.builder.ArtifactBuilder.build", _down)
    result = runner.invoke(
        app, ["publish", "--profile", "profiles/example.json", "--root", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "could not build the page" in result.output
    assert "Traceback" not in result.output
