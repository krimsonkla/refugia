"""A floor on the time between outbound requests, shared across worker threads."""

import threading
import time
from collections.abc import Callable


class Throttle:
    """Spaces request starts so a worker pool cannot outrun an endpoint.

    Sleeping inside each worker would bound one worker's rate and not the pool's:
    eight workers each pausing a tenth of a second still open eighty connections a
    second. The interval is therefore held here, between starts, under a lock, so
    the limit is a property of the source rather than of how widely it fans out.

    The clock and sleep are injected so the behaviour can be tested without
    spending the wall time it exists to spend.
    """

    def __init__(
        self,
        min_interval: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_start: float | None = None

    def wait(self) -> None:
        """Block until enough time has passed since the previous request began."""
        if self._min_interval <= 0:
            return
        with self._lock:
            now = self._clock()
            if self._next_start is not None and now < self._next_start:
                self._sleep(self._next_start - now)
                now = self._clock()
            self._next_start = now + self._min_interval
