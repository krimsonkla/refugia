# refugia

> This file is maintained by AI assistants. Keep it up to date as the project evolves.

## What this is

Ranks US counties as places to live against a personal profile of allergens,
wellbeing, hazard and cost. `README.md` carries the reasoning behind the design;
this file carries the rules for working in the repo.

## Tech Stack

- **Dev Environment**: devenv.sh, configured entirely by this repo's own `devenv.nix`
- **Language**: Python 3.12, dependencies in `pyproject.toml`, pinned in `uv.lock`

## Two ways in, and `uv` is the one everyone has

- `devenv shell -- <command>` is the maintainer path. It pins the interpreter,
  syncs the venv on entry and installs the git hooks.
- `uv sync --all-groups` then `uv run <command>` is the path for anyone without
  nix, and it must keep working — it is what CI runs and what a contributor
  clones into. A change that only works inside the devenv shell is a change that
  works for one person.
- Either way the venv lives under `.devenv/state/venv/` or `.venv/` and the
  project installs editable, so `refugia` and `pytest` resolve by name. `python`
  is the bare interpreter and does not see the project — use the console script.
- To add a dependency, edit `pyproject.toml`, run `uv lock`, and commit
  `uv.lock`. Never `pip install` by hand.
- Non-Python tooling requires a `devenv.nix` change — confirm with the developer first.

## Build & Test

```bash
devenv shell -- pytest                 # suite with coverage
devenv shell -- prek run --all-files   # hooks

uv sync --all-groups && uv run pytest  # the same suite, without nix
```

## Architecture

Four layers, each depending only on the one below.

- `places/` — the candidate universe, built from Census reference files.
- `metrics/` — `Metric` declares what a column _means_; `MetricSource` is the fetch
  contract; `MetricRegistry` binds them. `sources/` holds the adapters.
- `scoring/` — filter, normalise, weight, rank. Knows nothing about any specific metric.
- `artifact/`, `ask/`, `cli.py` — front ends. All read the same `Dataset` and `Profile`.

`workspace.py` is the composition root and the only module that knows the full
source set exists.

## Local Conventions

- **One class per file**, named after it; packages group by theme.
- **Dependencies are injected.** No module reaches for a global cache, clock or
  settings object; `Workspace` constructs and passes them down.
- **`direction` is applied in exactly one place** — `Normalizer`. Nothing else may
  encode whether high or low is good for a metric, or adding a metric stops being
  a registration and starts being an edit.
- **No `if metric.key == ...` outside a source.** Scoring, the CLI and the page are
  written against the registry. A special case for one metric is the design failure.
- **A comment describes the thing as it is**, never how it got there.

## Adding a metric

Prefer the cheapest tier that can express the source; see README "Adding a metric".
A written adapter is for sources needing real logic, and owes tests.

## Gotchas

- **LANDFIRE LF2025 is a partial release** — `identify` returns NoData across the
  eastern US and `getSamples` returns HTTP 400 with a 200-shaped body. Use LF2024,
  which is national and matches the crosswalk CSV. An error body arrives with
  HTTP 200, so `raise_for_status` never sees it; check for an `error` key.
- **Never cache an empty result.** A cached failure is indistinguishable from data
  and survives every later run. `Cache.write` refuses an empty payload, which covers
  the zero-byte case everywhere; an empty _parsed_ result serialises to a valid `{}`
  or `[]` and is not caught there, so each source guards its own write.
- **Scoring exists twice** — Python in `scoring/`, JavaScript in
  `artifact/template.html`, because the page re-ranks with no server to ask. Change
  both together. `tests/conformance/vectors.json` is executed by both and fails if
  they disagree, and the JavaScript half lives between the `scoring kernel:
BEGIN/END` markers in the template and must stay pure — no globals, no DOM — or
  it can no longer be lifted out and run.
- **Every outbound request carries `USER_AGENT`** from `refugia/__init__.py`, and a
  source that fans out over a worker pool takes a `Throttle` so the rate belongs to
  the source rather than to each thread. `tests/test_outbound_requests.py` parses the
  tree and fails on a request that identifies nobody.
- **Coverage is the signal that matters** for a new source. A half-failing source
  returns plausible numbers for what it reached and silence for the rest; `fetch`
  flags anything under 75%.
