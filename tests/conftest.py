"""Shared fixtures: a small hand-built world with known answers."""

import pytest

from refugia.metrics.metric import Metric
from refugia.places.cbsa import Cbsa
from refugia.places.place import Place


@pytest.fixture
def places() -> tuple[Place, ...]:
    """Four places whose ordering under each metric is obvious by inspection."""
    return (
        Place("00001", "Alpha", "Oregon", 44.0, -121.0, 100_000, Cbsa("1", "Alpha, OR", "metro")),
        Place("00002", "Bravo", "Idaho", 43.0, -116.0, 50_000, Cbsa("2", "Bravo, ID", "micro")),
        Place("00003", "Delta", "Maine", 44.5, -69.0, 20_000, Cbsa("3", "Delta, ME", "micro")),
        Place("00004", "Echo", "Ohio", 40.0, -83.0, 800_000, Cbsa("4", "Echo, OH", "metro")),
    )


@pytest.fixture
def juniper() -> Metric:
    """A lower-is-better allergen metric."""
    return Metric(
        key="juniper_cover",
        label="Juniper cover",
        unit="% of land",
        direction="lower_better",
        category="allergen",
        description="test",
        source="test",
    )


@pytest.fixture
def parks() -> Metric:
    """A higher-is-better amenity metric."""
    return Metric(
        key="parks",
        label="Parks",
        unit="score",
        direction="higher_better",
        category="amenity",
        description="test",
        source="test",
    )
