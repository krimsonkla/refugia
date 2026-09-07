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
    # single public endpoint, and a public repository multiplies that by however
    # many people run it. Measured over a real cache the pool sits ON this floor at
    # about 15 requests a second, so this is the rate rather than a ceiling above
    # one -- the earlier reasoning that a request takes a second or two and the
    # limit would rarely bind was wrong by roughly threefold. 0.05s buys a cold
    # fetch of about eight minutes; raise it to 0.2 for five a second and twenty
    # minutes if that reads as too brisk for somebody else's service.
    min_interval: float = 0.05
