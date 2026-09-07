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

## 2. Why `declined` rows are here

Twelve rows are `declined` — checked and found clean, or raised by an audit lens
and then refuted by its verifier. They are the most re-raisable kind of finding,
which is exactly why they are recorded with their evidence: `fnd-047` says the
cachix cache is publicly readable, `fnd-048` says the tracked `.claude` symlink
does not expose a permissions blob, `fnd-049` says a fresh clone runs the suite
in 0.27s off `uv.lock`. Each cost real verification. None should cost it twice.

## 3. Severity and release gate

`severity` is the project's own scale and says how bad the defect is:

- `P0` — irreversible disclosure, exploitable vulnerability, or crash
- `P1` — bug, plan-property violation, performance, maintainability
- `P2` — style, naming, minor improvement

`release_gate` is a separate axis and says when it must be done relative to the
repo going public. The two do not collapse into each other: a missing `LICENSE`
is `P1` but a `blocker`, and the unescaped `innerHTML` sites are `P1` but only
`important`, because no shipped path reaches them until the first outside spec
PR merges.

## 4. Adopted from `recension`, and what is not here

Adopted: the envelope, permanent ids, the closed status vocabulary, the
evidence-to-close rule, `refs`-as-section-anchor, append-and-amend.

Not here, and deliberately: there is no `tasks.jsonl`, so an `open` finding does
not yet owe a task row; there is no `tests/docs/test_data_integrity.py`, so
these rules are convention rather than enforcement; and there is no
`docs/data/reference/` split, because nothing in this repo's plan layer is
lookup data. Add the integrity test before adding a second stream — a rule that
nothing checks is a rule that drifts.

## 5. `findings.jsonl`

62 rows from `cyc-release-audit`, the public-release readiness audit of
2026-09-07. Seven lenses found; each lens's findings were then adversarially
verified against the repo by a second pass, which corrected severities, merged
duplicates and refuted six. `lens` records which one raised the row:

`personal-data` · `tests` · `user-docs` · `contributor-docs` ·
`reproducibility` · `data-licensing` · `security-quality` · `critique`

## 6. Working with the file

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
