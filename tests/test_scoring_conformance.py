"""The scoring kernel exists twice; these vectors are what stop it diverging.

The page has to re-rank when a slider moves and it has no server to ask, so the
duplication is forced. What is not forced is the two implementations drifting
apart, and nothing in the type system, the linter or either test suite can notice
when they do -- only running both against the same inputs can.

Every case here runs twice: once through the Python engine, and once through the
kernel lifted out of template.html by run_vectors.mjs.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from refugia.metrics.metric import Metric
from refugia.metrics.registry import MetricRegistry
from refugia.places.place import Place
from refugia.scoring.criterion import Criterion
from refugia.scoring.engine import ScoringEngine
from refugia.scoring.profile import Profile

VECTORS = Path(__file__).parent / "conformance" / "vectors.json"
RUNNER = Path(__file__).parent / "conformance" / "run_vectors.mjs"
CASES = json.loads(VECTORS.read_text(encoding="utf-8"))["cases"]


class _Stub:
    """A source that supplies metrics and no values, to populate a registry."""

    def __init__(self, metrics):
        self.metrics = tuple(metrics)

    def fetch(self, places):
        return {}


def _fips_in(case) -> list[str]:
    if "places" in case:
        return list(case["places"])
    return sorted({f for values in case["values"].values() for f in values})


def _rank(case):
    """Run one vector through the Python engine."""
    metrics = [
        Metric(
            key=m["key"],
            label=m["key"],
            unit="u",
            direction=m["direction"],
            category="test",
            description="",
            source="s",
        )
        for m in case["metrics"]
    ]
    registry = MetricRegistry()
    registry.register(_Stub(metrics))
    places = tuple(
        Place(
            fips=f,
            name=f,
            state=case.get("states", {}).get(f, "Testland"),
            lat=0.0,
            lon=0.0,
            population=case.get("populations", {}).get(f, 100_000),
        )
        for f in _fips_in(case)
    )
    profile = Profile(
        case["name"],
        {k: float(v) for k, v in case["weights"].items()},
        criteria=tuple(
            Criterion(
                field=c["field"],
                comparison=c["comparison"],
                value=tuple(c["value"]) if isinstance(c["value"], list) else c["value"],
            )
            for c in case.get("criteria", [])
        ),
        normalization=case.get("normalization", "percentile"),
        min_coverage=float(case["min_coverage"]),
    )
    return ScoringEngine(registry).rank(places, case["values"], profile)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_python_matches_the_vector(case):
    """The Python engine produces what the shared vectors say it must."""
    ranked = _rank(case)
    got = sorted((s.place.fips, round(s.total, 6), round(s.coverage, 6)) for s in ranked)
    want = sorted(
        (e["fips"], round(float(e["score"]), 6), round(float(e["cover"]), 6))
        for e in case["expect"]
    )
    assert got == want


def test_the_ordering_matches_the_vector():
    """Scores agreeing is not the same as the list coming out in the same order."""
    for case in CASES:
        ranked = _rank(case)
        by_score = [
            f
            for f, _, _ in sorted(
                ((s.place.fips, -s.total, s.place.fips) for s in ranked),
                key=lambda t: (t[1], t[2]),
            )
        ]
        want = [
            f
            for f, _, _ in sorted(
                ((e["fips"], -float(e["score"]), e["fips"]) for e in case["expect"]),
                key=lambda t: (t[1], t[2]),
            )
        ]
        assert by_score == want, case["name"]


def test_the_page_kernel_matches_the_same_vectors():
    """Runs template.html's own scoring against every vector Python just ran.

    devenv provides node for exactly this. On the plain uv path there is none, so
    this skips rather than blocking a contributor who is nowhere near scoring.
    Never skipped in CI, where a divergence reaching main is the thing at stake.
    """
    node = shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("node is required in CI: this is the only cross-check there is")
        pytest.skip("node not on PATH; install node to run the page-side check")

    result = subprocess.run(
        [node, str(RUNNER)], capture_output=True, text=True, check=False, timeout=60
    )
    assert result.returncode == 0, (
        "the page's scoring kernel disagrees with the shared vectors:\n"
        f"{result.stdout}\n{result.stderr}"
    )
