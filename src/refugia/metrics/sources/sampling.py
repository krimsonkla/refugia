"""How densely and how widely a raster source samples around a place."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Sampling:
    """Sampling and retry settings for a raster-backed source.

    These values always travel together and are meaningless apart: a radius
    without a sample count describes no measurement, and the retry pair is the
    other half of the same "how do we ask a flaky raster service" decision.
    """

    radius_km: float = 25.0
    sample_count: int = 500
    workers: int = 8
    retries: int = 4
    backoff: float = 1.5
    # A full county-and-city run is roughly six and a half thousand requests to a
    # single public endpoint. Eight workers with no floor between starts is a rate
    # nobody agreed to, and a public repository multiplies it by however many
    # people run it.
    min_interval: float = 0.05
