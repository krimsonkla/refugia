"""How densely and how widely a raster source samples around a place."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Sampling:
    """Sampling and retry settings for a raster-backed source.

    These five values always travel together and are meaningless apart: a radius
    without a sample count describes no measurement, and the retry pair is the
    other half of the same "how do we ask a flaky raster service" decision.
    """

    radius_km: float = 25.0
    sample_count: int = 500
    workers: int = 8
    retries: int = 4
    backoff: float = 1.5
