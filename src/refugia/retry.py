"""Repeating a request that failed in a way worth repeating."""

import time
from collections.abc import Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

# Asking again could plausibly produce a different answer: the connection dropped,
# the read timed out, the service asked us to slow down, or it fell over. Every
# other status is the service telling us something it will keep telling us.
RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


class Retry:
    """Repeats a call through transient failures, with exponential backoff.

    Two adapters grew their own copy of this loop and the rest of the project had
    none, which meant a dropped connection cost whichever metrics that source
    supplies -- five from CDC PLACES, six from the declarative specs -- while the
    two that did retry recovered from the same blip. Sharing it makes the
    behaviour a property of the project rather than of which file you are in.

    It is also narrower than the loops it replaces. Those caught any HTTPError, so
    a 404 from an upstream that had moved its file spent four attempts and ten
    seconds of backoff re-confirming a fixed fact. A permanent answer is raised at
    once.

    `sleep` is injected so the behaviour can be tested without spending the time
    it exists to spend.
    """

    def __init__(
        self,
        attempts: int = 4,
        backoff: float = 1.5,
        *,
        also_transient: tuple[type[BaseException], ...] = (),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._attempts = max(1, attempts)
        self._backoff = backoff
        # An endpoint may fail in a shape only its own adapter recognises. NASA
        # POWER answers 200 with an error body, so a missing key there means "ask
        # again", the same 200-shaped failure CLAUDE.md records for LANDFIRE. Kept
        # opt-in so one endpoint's quirk does not make every bug retryable.
        self._also = tuple(also_transient)
        self._sleep = sleep

    def is_transient(self, error: BaseException) -> bool:
        """Whether asking again could plausibly give a different answer."""
        if isinstance(error, self._also):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in RETRY_STATUSES
        return isinstance(error, (httpx.TransportError, OSError))

    def run(self, work: Callable[[], T]) -> T:
        """Call `work`, repeating it while it fails transiently."""
        for attempt in range(self._attempts):
            try:
                return work()
            # Deliberately broad: the decision about what is worth repeating is
            # is_transient's, made below on the error itself. Narrowing the catch
            # here would move that decision into two places and let a source's
            # declared shapes escape one of them.
            except Exception as error:  # pylint: disable=broad-exception-caught
                if not self.is_transient(error) or attempt == self._attempts - 1:
                    raise
                self._sleep(self._backoff * (2**attempt))
        raise RuntimeError("unreachable: the loop either returns or raises")
