# `docs/data` — the tracked state layer

Each stream here is JSONL: one JSON object per line, UTF-8, sorted by `id`.
Prose and reasoning belong in the documents above this directory; it holds the
**rows**, so
state can be queried and cross-checked mechanically rather than read out of a
markdown table by eye.

The format was adapted from a sibling project of the author's. What differs is recorded in
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

**No blockers are open.** The three that were — fnd-003, fnd-067, fnd-068 — were
all one fact: a force-push does not remove objects from GitHub, so the pre-rewrite
history stayed fetchable by SHA after the rewrite. The repository was deleted and
re-created on 2026-09-07 and the pre-rewrite tip now returns 422. What is left is
three non-blocking rows, all about the `v0.1.0` tag and about settings that cannot
be turned on while the repository is private.

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
not yet owe a task row, and there is no reference-data split because nothing in
this repository's plan layer is lookup data.

What _is_ here, and was not when this paragraph first said it was missing:
`tests/test_findings_integrity.py` checks the envelope, the cross-references, that
a closed row carries evidence and an author, that this file's counts match the
rows, and that it cannot describe a clean release while a blocker is open. The
paragraph explaining why there was no such test outlived the test.

## 6. `findings.jsonl`

**146 rows across 2 cycles and 8 lenses.**
`3 open, 127 fixed, 3 parked, 13 declined.`

- `cyc-release-audit` — the first public-release audit. Seven lenses plus a
  completeness critic, so eight `lens` values appear.
- `cyc-release-audit-2` — a re-audit over the same lenses, told to treat every
  `fixed` row as a claim by whoever made the change and to verify it. Its rows carry
  a `finding_kind`: `fix-overstated` where a closure did not hold, `new-defect`
  where the intervening work introduced something, `still-open` where nothing had
  been claimed.

Both cycles ran the same shape: each lens found, a second agent reproduced or
refuted, then a critic looked for what no lens covered.

## 7. Batches

Open rows carry a `batch`, so the remaining work can be picked up by theme rather
than by scrolling. The grouping is by what a change touches, not by severity — a
batch is meant to be one sitting with one set of files open in front of you.

### `publish-the-repo` — 3 rows (1 important, 2 nice-to-have)

One sitting, and nothing else matters until it is done. The pre-rewrite history is
still served by GitHub, so the repository has to be deleted and re-created rather
than force-pushed again. Everything else here happens in the same operation or
immediately after it: the tag is re-cut at the new HEAD, the ledger's stale SHA
goes with it, and branch protection, secret scanning and private vulnerability
reporting are all switchable only once the repository is public.

```bash
jq -c 'select(.batch == "publish-the-repo" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

### `scoring-parity` — done

Closed. The page and the CLI ranked differently for the shipped example profile
because the page read half the profile and filtered the other half outside the
kernel markers, where nothing compared it to anything. Everything that removes a
place is now a criterion handed to the kernel — the profile's own, the population
floor, the state exclusion, the cut against home and the per-metric typed limit
that replaced the hard-coded home-value box — so one path does the filtering and
the vectors run it. Direction inversion is one function; the mutants die; the
claim that the page contains no per-metric code is a test rather than a
sentence.

```bash
jq -c 'select(.batch == "scoring-parity" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

### `upstream-resilience` — done

Closed. What happens when a source misbehaves: `fetch` survives one that raises and
one that returns empty, a saved dataset no longer looks identical either way, and
`publish` handles its own failures. The last row here was the docs saying `publish`
touches no network while the first one reaches four more upstreams; the guide now
lists them, and a test counts them so the list cannot rot.

```bash
jq -c 'select(.batch == "upstream-resilience" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

### `prose-guard` — done

Closed. `tests/test_guide.py` was widened first and the corrections followed, which
was the point of the ordering: the reason both audits found a pile of prose defects
is that nothing was checking. It now validates paths, links, vocabulary, the
endpoint table and the claim that the page contains no per-metric code, so the pile
does not rebuild.

```bash
jq -c 'select(.batch == "prose-guard" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

### `attribution` — done

The citation machinery works for the case it was built for and not for its edges: a
dataset saved before the field existed publishes a page with no citations, nothing
forces an attribution-owing source to arrive with one, `terms_url` is collected and
never shown, and `ask --host` is exempt from the User-Agent rule on the grounds it
is local when a flag makes it remote.

```bash
jq -c 'select(.batch == "attribution" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

### `tests-that-bite` — done

Closed. Tests that could not fail: a syntax error anywhere in the page passed the
whole suite, the Throttle's lock could be deleted with nothing noticing, one spec
assertion was a tautology, and the no-network fixture missed async and raw
transports. The large one at the end of the batch was adapter coverage, which was
the reason the total sat at 60%; every module the row named is now tested and the
floor is 90.

```bash
jq -c 'select(.batch == "tests-that-bite" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

### `packaging` — done

The wheel is verified by hand and by nothing else, CI exercises one Python against a
README that promises three, and an install-from-wheel user has no example profile
to run. Cheap, and all of it is about the artifact rather than the source tree.

```bash
jq -c 'select(.batch == "packaging" and .status == "open") | [.id, .effort, .title] | @tsv' -r \
  docs/data/findings.jsonl
```

A row leaves its batch by being closed, not by being reassigned: `batch` describes
what the work touches, and that does not change because somebody did it.

## 8. Working with the file

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
