# `docs/data` — the tracked state layer

Each stream here is JSONL: one JSON object per line, UTF-8, sorted by `id`.
Prose and reasoning belong in `docs/*.md`; this directory holds the **rows**, so
state can be queried and cross-checked mechanically rather than read out of a
markdown table by eye.

The format follows the one in `krimsonkla/recension`. What differs is recorded in
§4 — this repo has one stream, not fifteen, and no integrity test yet.

## 1. The envelope

| Field          | Type     | Meaning                                                                              |
| -------------- | -------- | ------------------------------------------------------------------------------------ |
| `id`           | string   | Unique across the directory. `fnd-` names the stream                                 |
| `kind`         | string   | The stream's singular name — `finding`                                               |
| `title`        | string   | One line. What the row is                                                            |
| `status`       | string   | `open` · `fixed` · `parked` · `declined` · `plan-change`                             |
| `severity`     | string   | `P0` · `P1` · `P2` (§3)                                                              |
| `release_gate` | string   | `blocker` · `important` · `nice-to-have` · `none` (§3)                               |
| `effort`       | string   | `trivial` · `small` · `medium` · `large`                                             |
| `lens`         | string   | The audit lens that raised it (§5)                                                   |
| `cycle`        | string   | The review cycle that produced it                                                    |
| `refs`         | string[] | Section citations — `README.md#use`, `CLAUDE.md#gotchas`. May be empty               |
| `depends_on`   | string[] | Not startable until these are done. May be empty                                     |
| `blocked_by`   | string[] | Hard block right now. Non-empty ⇒ `status` is `blocked`                              |
| `related`      | string[] | Cross-reference, no dependency implied. May be empty                                 |
| `evidence`     | string[] | File paths with line numbers, commands run, measured output                          |
| `updated`      | string   | `YYYY-MM-DD`, when the row last changed                                              |
| `notes`        | string   | Prose. `""` when there is nothing to add                                             |
| `review_at`    | string   | **`parked` rows only, and required on them.** The condition that brings the row back |

Rules:

- **Ids are permanent.** A row that turns out wrong gets `status: "declined"`,
  never a reused id.
- **Every id in `depends_on` / `blocked_by` / `related` must resolve** to a row
  in this directory.
- **`evidence` is required to close a row.** A finding at `fixed` with an empty
  `evidence` array is not closed, it is asserted.
- Rows are **append-and-amend**: edit in place and bump `updated`. Git carries
  the history.
- A `refs` anchor is a **section identifier, not a URL fragment** — it resolves
  when it is the stable head of a heading, so `#use` matches `## Use`. A prefix
  survives a heading being reworded; a full slug does not.

## 2. Read this before trusting the rows

**3 blockers are open.** fnd-003, fnd-067, fnd-068 — the
pre-rewrite git history is still served by GitHub, so the personal profile it was
rewritten to remove is fetchable today. Nothing else in this file matters until
that is done.

That statement exists here because of how this file failed once. After the first
cycle it recorded four blockers, all fixed, and two open rows, both cosmetic. A
reader running §7's own recommended query would have concluded the repository was
ready. A second cycle then found a blocker and sixteen important items, none of
which existed as rows.

The mechanism is worth naming, because the rule that let it happen is still in §1:
**`evidence` is required to close a row, and that checks presence, never accuracy.**
Every one of the first cycle's 48 closures satisfied it, and the second cycle
contradicted the content of ten. Those ten now carry a correction in `notes` and a
`related` link to the row that disputed them.

So: `verified_by` says who established a row, as distinct from who would fix it. A
row reading `self (the change's author)` is a claim by the person who made the
change. A row reading `cyc-release-audit-2 adversarial verifier` was found by one
agent and reproduced by a second before it was written down. Neither is proof, and
the difference is the most useful thing on the row.

## 3. Why `declined` rows are here

13 declined rows — checked and found clean, or raised by a lens and
then refuted by its verifier. They are the most re-raisable kind of finding, which
is exactly why they are kept with their evidence rather than dropped: `fnd-047`
says the cachix cache is publicly readable, `fnd-049` says a fresh clone runs the
suite off `uv.lock`. Each cost real verification. None should cost it twice — and
note that the second cycle amended three of them, so declined is not immune either.

## 4. Severity and release gate

`severity` is the project's own scale and says how bad the defect is:

- `P0` — irreversible disclosure, exploitable vulnerability, or crash
- `P1` — bug, plan-property violation, performance, maintainability
- `P2` — style, naming, minor improvement

`release_gate` is a separate axis and says when it must be done relative to the
repo going public. The two do not collapse into each other: a missing `LICENSE`
is `P1` but a `blocker`, and the unescaped `innerHTML` sites are `P1` but only
`important`, because no shipped path reaches them until the first outside spec
PR merges.

## 5. Adopted from `recension`, and what is not here

Adopted: the envelope, permanent ids, the closed status vocabulary, the
evidence-to-close rule, `refs`-as-section-anchor, append-and-amend.

Not here, and deliberately: there is no `tasks.jsonl`, so an `open` finding does
not yet owe a task row; there is no `tests/docs/test_data_integrity.py`, so
these rules are convention rather than enforcement; and there is no
`docs/data/reference/` split, because nothing in this repo's plan layer is
lookup data. Add the integrity test before adding a second stream — a rule that
nothing checks is a rule that drifts.

## 6. `findings.jsonl`

**145 rows across 2 cycles and 8 lenses.**
`82 open, 47 fixed, 3 parked, 13 declined.`

- `cyc-release-audit` — the first public-release audit. Seven lenses plus a
  completeness critic, so eight `lens` values appear.
- `cyc-release-audit-2` — a re-audit over the same lenses, told to treat every
  `fixed` row as a claim by whoever made the change and to verify it. Its rows carry
  a `finding_kind`: `fix-overstated` where a closure did not hold, `new-defect`
  where the intervening work introduced something, `still-open` where nothing had
  been claimed.

Both cycles ran the same shape: each lens found, a second agent reproduced or
refuted, then a critic looked for what no lens covered.

## 7. Working with the file

```bash
# What blocks the repo going public, in order
jq -c 'select(.release_gate == "blocker") | {id, severity, effort, title}' docs/data/findings.jsonl

# Everything still open, worst first
jq -c 'select(.status == "open") | [.severity, .release_gate, .id, .title] | @tsv' -r \
  docs/data/findings.jsonl | sort

# The cheap wins
jq -c 'select(.status == "open" and .effort == "trivial") | {id, title}' docs/data/findings.jsonl

# Already checked — do not re-raise
jq -c 'select(.status == "declined") | {id, title, evidence}' docs/data/findings.jsonl

# Everything referencing a given row
jq -c --arg id fnd-004 \
  'select([.depends_on[],.blocked_by[],.related[]] | index($id)) | .id' docs/data/findings.jsonl
```
