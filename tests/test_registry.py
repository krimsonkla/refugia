"""The registry is the extension point, so its guarantees matter."""

import pytest

from refugia.metrics.metric import Metric
from refugia.metrics.registry import MetricRegistry


class _Stub:
    def __init__(self, metrics):
        self._metrics = tuple(metrics)

    @property
    def metrics(self):
        return self._metrics

    def fetch(self, places):
        return {}


def test_two_sources_cannot_claim_one_key(juniper):
    """A duplicate key must raise rather than depend on import order."""
    registry = MetricRegistry()
    registry.register(_Stub((juniper,)))
    with pytest.raises(ValueError, match="already supplied"):
        registry.register(_Stub((juniper,)))


def test_lookup_resolves_metric_and_source(juniper, parks):
    """Both halves of a registration are retrievable by key."""
    registry = MetricRegistry()
    source = _Stub((juniper, parks))
    registry.register(source)
    assert registry.metric("parks") is parks
    assert registry.source_for("juniper_cover") is source
    assert "juniper_cover" in registry


def test_unknown_key_names_what_is_known(juniper):
    """The error has to be actionable, so it lists the valid keys."""
    registry = MetricRegistry()
    registry.register(_Stub((juniper,)))
    with pytest.raises(KeyError, match="juniper_cover"):
        registry.metric("nope")


def test_a_metric_key_must_be_an_identifier():
    """Keys become JSON fields and JS property names, so they are constrained."""
    with pytest.raises(ValueError, match="valid identifier"):
        Metric("not a key", "x", "u", "lower_better", "c", "d", "s")
