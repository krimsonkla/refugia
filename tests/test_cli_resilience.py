"""Nine upstreams are pinned to dated paths, so one of them rotting is a when."""

import httpx
import pytest
from typer.testing import CliRunner

from refugia.cli import _collect, app
from refugia.metrics.metric import Metric

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
