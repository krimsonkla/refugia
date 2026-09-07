"""Transient means "ask again and it might work". Most failures are not that."""

import httpx
import pytest

from refugia.retry import Retry


class _Clock:
    """Records what was slept instead of sleeping."""

    def __init__(self) -> None:
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def _status(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid/x")
    return httpx.HTTPStatusError(
        f"{code}", request=request, response=httpx.Response(code, request=request)
    )


def _flaky(errors, result: str | None = "ok"):
    """A callable that raises each given error once, then succeeds."""
    queue = list(errors)

    def work():
        if queue:
            raise queue.pop(0)
        return result

    return work


def test_a_call_that_works_is_not_slept_on():
    clock = _Clock()
    assert Retry(sleep=clock.sleep).run(_flaky([])) == "ok"
    assert clock.slept == []


def test_a_dropped_connection_is_retried():
    """The failure LANDFIRE actually produces under sustained use."""
    clock = _Clock()
    work = _flaky([httpx.ConnectError("reset")])
    assert Retry(sleep=clock.sleep).run(work) == "ok"
    assert len(clock.slept) == 1


def test_backoff_grows():
    """Hammering a service that is already struggling is how you stay blocked."""
    clock = _Clock()
    work = _flaky([httpx.ReadTimeout("t"), httpx.ReadTimeout("t"), httpx.ReadTimeout("t")])
    Retry(attempts=4, backoff=1.5, sleep=clock.sleep).run(work)
    assert clock.slept == [1.5, 3.0, 6.0]


def test_the_last_error_is_raised_when_attempts_run_out():
    """The caller needs the reason, not a generic exhaustion error."""
    clock = _Clock()
    work = _flaky([httpx.ConnectError("first"), httpx.ConnectError("last")], result=None)
    with pytest.raises(httpx.ConnectError, match="last"):
        Retry(attempts=2, sleep=clock.sleep).run(work)


@pytest.mark.parametrize("code", [429, 500, 502, 503])
def test_a_server_saying_try_later_is_retried(code):
    """429 and 5xx are the codes that mean exactly that."""
    clock = _Clock()
    assert Retry(sleep=clock.sleep).run(_flaky([_status(code)])) == "ok"
    assert len(clock.slept) == 1


@pytest.mark.parametrize("code", [400, 401, 403, 404, 410])
def test_a_permanent_answer_is_not_retried(code):
    """A moved file will still be moved in six seconds, and nine after that."""
    clock = _Clock()
    with pytest.raises(httpx.HTTPStatusError):
        Retry(sleep=clock.sleep).run(_flaky([_status(code)], result=None))
    assert clock.slept == []


def test_an_unrelated_error_is_not_retried():
    """Retrying a bug just runs it four times."""
    clock = _Clock()
    with pytest.raises(ValueError):
        Retry(sleep=clock.sleep).run(_flaky([ValueError("a bug")], result=None))
    assert clock.slept == []


def test_a_single_attempt_never_sleeps():
    """attempts=1 is "do not retry", and must not pause before giving up."""
    clock = _Clock()
    with pytest.raises(httpx.ConnectError):
        Retry(attempts=1, sleep=clock.sleep).run(_flaky([httpx.ConnectError("x")], result=None))
    assert clock.slept == []


def test_a_source_can_declare_its_own_transient_shapes():
    """NASA POWER answers 200 with an error body, which is a retryable nothing."""
    clock = _Clock()
    retry = Retry(also_transient=(ValueError,), sleep=clock.sleep)
    assert retry.run(_flaky([ValueError("no features in body")])) == "ok"
    assert len(clock.slept) == 1


def test_declaring_one_shape_does_not_widen_the_others():
    """An opt-in for one endpoint must not make every bug retryable everywhere."""
    clock = _Clock()
    retry = Retry(also_transient=(ValueError,), sleep=clock.sleep)
    with pytest.raises(TypeError):
        retry.run(_flaky([TypeError("a bug")], result=None))
    assert clock.slept == []
