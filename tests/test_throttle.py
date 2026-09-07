"""A public repo multiplies request volume across every fork of it."""

import threading
import time
from itertools import pairwise

from refugia.metrics.sources.throttle import Throttle


class _Clock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_the_first_call_does_not_wait():
    """Throttling should cost nothing until there is something to space out."""
    clock = _Clock()
    Throttle(0.5, clock=clock.time, sleep=clock.sleep).wait()
    assert clock.slept == []


def test_consecutive_calls_are_spaced():
    """Two calls back to back must be separated by the interval."""
    clock = _Clock()
    throttle = Throttle(0.5, clock=clock.time, sleep=clock.sleep)
    throttle.wait()
    throttle.wait()
    assert clock.slept == [0.5]


def test_time_already_spent_counts_towards_the_interval():
    """A slow request has already done the waiting; sleeping again is waste."""
    clock = _Clock()
    throttle = Throttle(0.5, clock=clock.time, sleep=clock.sleep)
    throttle.wait()
    clock.now += 2.0
    throttle.wait()
    assert clock.slept == []


def test_a_zero_interval_never_sleeps():
    """Off by default, so nothing pays for a limit it does not need."""
    clock = _Clock()
    throttle = Throttle(0.0, clock=clock.time, sleep=clock.sleep)
    throttle.wait()
    throttle.wait()
    assert clock.slept == []


def test_the_interval_is_measured_between_starts():
    """Spacing starts is what bounds the rate when many workers share one."""
    clock = _Clock()
    throttle = Throttle(0.25, clock=clock.time, sleep=clock.sleep)
    for _ in range(4):
        throttle.wait()
    assert clock.slept == [0.25, 0.25, 0.25]
    assert clock.now == 0.75


def test_the_interval_holds_across_threads():
    """The lock is the whole point, and no single-threaded test can see it.

    Every other test here drives one caller through a fake clock, so removing the
    lock leaves them all green. This one runs the pool the class exists for.
    """
    real = Throttle(0.01)
    starts: list[float] = []
    guard = threading.Lock()

    def worker() -> None:
        real.wait()
        with guard:
            starts.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    starts.sort()
    gaps = [b - a for a, b in pairwise(starts)]
    # Some slack for scheduling, but nothing like twelve simultaneous starts.
    assert all(g >= 0.008 for g in gaps), f"starts were not spaced: {gaps}"
