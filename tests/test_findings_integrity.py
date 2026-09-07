"""The tracking layer makes claims about this repository, so it gets checked too.

`docs/data/README.md` promised an integrity test and did not have one, and the
consequence was exactly what you would predict: its own summary paragraph miscounted
the file four ways, and a second audit found three open blockers in a file whose
recommended query reported none.

These assertions are deliberately about the file's internal consistency and about
the numbers the README states in prose. They cannot tell you whether a row is true —
nothing can, except somebody checking — but they can stop the record contradicting
itself while a reader is being invited to trust it.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data"
FINDINGS = DATA / "findings.jsonl"
README = DATA / "README.md"

ROWS = [json.loads(line) for line in FINDINGS.read_text(encoding="utf-8").splitlines()]
STATUSES = {"open", "fixed", "parked", "declined", "plan-change"}
GATES = {"blocker", "important", "nice-to-have", "none"}
SEVERITIES = {"P0", "P1", "P2"}
EFFORTS = {"trivial", "small", "medium", "large"}
REQUIRED = (
    "id",
    "kind",
    "title",
    "status",
    "severity",
    "release_gate",
    "effort",
    "lens",
    "cycle",
    "refs",
    "depends_on",
    "blocked_by",
    "related",
    "evidence",
    "updated",
    "notes",
)


def test_there_are_rows_to_check():
    """A suite over an empty file passes by finding nothing."""
    assert len(ROWS) > 100


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_the_envelope_is_complete_and_in_vocabulary(row):
    missing = [f for f in REQUIRED if f not in row]
    assert not missing, f"{row['id']} is missing {missing}"
    assert row["status"] in STATUSES
    assert row["release_gate"] in GATES
    assert row["severity"] in SEVERITIES
    assert row["effort"] in EFFORTS
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["updated"])


def test_ids_are_unique_and_the_file_is_sorted():
    """Ids are permanent, so a reused one silently rewrites history."""
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)


def test_every_cross_reference_resolves():
    ids = {r["id"] for r in ROWS}
    dangling = {
        x
        for r in ROWS
        for key in ("depends_on", "blocked_by", "related")
        for x in r[key]
        if x not in ids
    }
    assert not dangling, f"rows point at ids that do not exist: {sorted(dangling)}"


def test_a_closed_row_carries_evidence():
    """The README's rule: a row at fixed with no evidence is asserted, not closed."""
    bare = [r["id"] for r in ROWS if r["status"] == "fixed" and not r["evidence"]]
    assert not bare, f"closed with no evidence: {bare}"


def test_a_parked_row_says_what_brings_it_back():
    bare = [r["id"] for r in ROWS if r["status"] == "parked" and not r.get("review_at")]
    assert not bare, f"parked with no review_at: {bare}"


def test_a_fixed_row_says_who_established_it():
    """Self-verified and independently verified are different claims.

    The second audit's central complaint: 48 rows said `fixed` on evidence written
    by whoever made the change, and a reader had no way to see that.
    """
    bare = [r["id"] for r in ROWS if r["status"] == "fixed" and not r.get("verified_by")]
    assert not bare, f"fixed with no verified_by: {bare}"


def test_the_readme_counts_match_the_file():
    """The prose in README.md miscounted this file four ways once. Not again."""
    text = README.read_text(encoding="utf-8")
    status = Counter(r["status"] for r in ROWS)
    expectations = {
        f"{len(ROWS)} rows": "the row count",
        f"{status['declined']} declined": "the declined count",
        f"{len({r['lens'] for r in ROWS})} lenses": "the lens count",
        f"{len({r['cycle'] for r in ROWS})} cycles": "the cycle count",
    }
    missing = [why for phrase, why in expectations.items() if phrase not in text]
    assert not missing, (
        f"docs/data/README.md does not state {missing}. Current file: {len(ROWS)} rows, "
        f"{status['declined']} declined, {len({r['lens'] for r in ROWS})} lenses, "
        f"{len({r['cycle'] for r in ROWS})} cycles."
    )


def test_the_readme_does_not_claim_a_clean_release_while_blockers_are_open():
    """The failure that made this file untrustworthy, asserted directly.

    A reader ran the README's own recommended query and was told nothing blocked
    release. Three blockers were open. Whatever the file says about its release
    state has to track the rows.
    """
    open_blockers = [
        r["id"] for r in ROWS if r["status"] == "open" and r["release_gate"] == "blocker"
    ]
    text = README.read_text(encoding="utf-8")
    if open_blockers:
        assert "blocker" in text.lower() and any(i in text for i in open_blockers), (
            "blockers are open and docs/data/README.md names none of them: " f"{open_blockers}"
        )
