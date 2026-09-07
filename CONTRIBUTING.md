# Contributing

This is a personal project that happens to be public. Issues and pull requests are
welcome; there is no support promise and no release schedule. `CODE_OF_CONDUCT.md`
asks you to be decent to people, and `SECURITY.md` says where the trust boundaries
are and how to report something exploitable privately. If you are about to
spend a weekend on something, open an issue first so it does not turn out to be a
weekend spent on something I was never going to merge.

The most useful contributions are almost certainly **a new metric** or **a source
that stopped working** — this project is a thin layer over ten public datasets, and
those datasets move.

## Setup

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run pytest
```

That is all of it. There is a `devenv.nix` for [devenv.sh](https://devenv.sh) which
pins the interpreter, installs the git hooks and provides node, but it is a
maintainer convenience — nothing here needs nix, and CI runs the `uv` path
precisely so that it keeps working.

One check behaves differently between the two. The scoring conformance test runs
the published page's JavaScript, so it needs node: devenv provides one, and on the
plain `uv` path that single test skips with a reason. It always runs in CI, so a
divergence cannot reach `main` either way — but if you are touching scoring, use
devenv or install node, because finding out from CI is finding out late.

If you use devenv, entering the shell generates a `.pre-commit-config.yaml`
symlink into the nix store and installs the hooks. A plain clone has no such file at
all — it is gitignored, so there is nothing to see and nothing to fix.

Those hooks are not the same set as CI. They add formatting CI does not run
(prettier, alejandra, whitespace, end-of-file) and they do not run pytest. A pull
request can therefore be green in CI and still be reformatted on merge; running
`prek run --all-files` before you push avoids that.

## The checks

Exactly what CI runs, so you can be green before you push:

```bash
uv run ruff check .
uv run black --check .
uv run pylint src/refugia
uv run pytest --cov=refugia --cov-report=term-missing --cov-fail-under=60
```

The coverage floor is the one thing CI adds that a bare `pytest` does not, and it
is a ratchet: raise it when it is comfortably cleared, never lower it to make a red
build green.

Coverage is deliberately **not** in `addopts`, so a plain `pytest` is fast and a
single-file run does not print a misleading project-wide total. Pass the flags when
you want the number.

## Tests

**The suite is offline by construction and needs no keys.** Every URL in `tests/`
is under `example.invalid`, which is reserved and unroutable, and each test that
mentions one either pre-seeds the cache so the code short-circuits before
requesting, stubs `httpx`, or never gets as far as a request. If a test you write
would touch the network, that is the signal to inject a stub instead — a
contributor on a plane must be able to run this.

New behaviour gets a test. Bug fixes get the failing test first; a fix without one
is a fix nobody can prove stays fixed.

## Adding a metric

Three tiers, cheapest first — the README has the reasoning, this is the mechanics.

**A JSON spec** needs no code. The shipped ones live in `src/refugia/specs/`, inside the package so a wheel carries them; a `specs/` beside the project is where a user's own go, and both are registered. Name the URL, the format (`csv`, `json`,
`xlsx`), the column holding a county FIPS and the column holding the value.
`src/refugia/specs/wildfire_risk.json` is a worked example. Specs are validated on load: the
URL must be `https`, and `key`, `label`, `unit`, `category`, `description` and
`source` may not contain angle brackets, because all six are interpolated into the
published page.

**A written adapter** in `src/refugia/metrics/sources/` implements the
`MetricSource` protocol, and is for sources needing real logic — constructed
geometry, pagination, a class crosswalk, retry semantics. An adapter owes tests.

Either way, **coverage is the number that decides it**. `fetch` flags any metric
below 75%, because the characteristic failure of a data source is not an error: it
is a tidy set of plausible numbers for the places it reached, and silence for the
rest. Say what coverage you measured in the pull request.

If the source requires a citation or attribution, put it in the metric's
`citation` and `terms_url` — a spec may declare both — and the published page will
carry it automatically. Attribution that lives only in a markdown file never
reaches the person who was handed the page.

`DATA_SOURCES.md` gets an entry for any new publisher regardless, including
whether you verified its terms or inferred them. Please do not assert a licence you
have not read.

## Things that will get a pull request sent back

`CLAUDE.md` carries the full set; these are the ones that actually come up.

- **Scoring exists twice** — Python in `scoring/`, JavaScript in
  `artifact/template.html`, because the page's sliders re-rank with no server to
  ask. A change to ranking semantics has to be made in both, in the same commit,
  and `tests/conformance/vectors.json` will fail you if it is not. Add a vector for
  the behaviour you changed. The JavaScript half sits between the `scoring kernel:
BEGIN/END` markers and must stay pure, since the test lifts it out of the file
  and runs it.
- **No `if metric.key == ...` outside a source.** Scoring, the CLI and the page are
  written against the registry. A special case for one metric means the
  registration model has failed somewhere else.
- **`direction` is applied in exactly one place**, `Normalizer`. Nothing else may
  encode whether high or low is good.
- **Never cache an empty result.** `Cache.write` refuses an empty payload; a source
  that serialises a mapping must also refuse to cache an empty one, because `{}`
  is a valid JSON document that reads back next run as real data.
- **Every outbound request carries `USER_AGENT`**, and a source that fans out over
  a worker pool takes a `Throttle`. `tests/test_outbound_requests.py` parses the
  tree and will fail your PR if a request identifies nobody.
- **Anything anyone can publish is a page you render.** Escape it with `esc()`.

## Commits and pull requests

Branch off `main`, open a pull request, keep it focused. CI must be green.

Commit subjects are `<type>(<scope>): <description>` — lowercase, imperative, with
one of `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.
A commit-msg hook enforces this, and also rejects `Co-Authored-By` and
`Signed-off-by` trailers; this project does not use them.

Say **why** in the body, not what — the diff already carries the what. The most
useful commit message here is the one that explains the constraint you were under,
because the next person to touch that code will be under it too.

## Do not commit

Your own profile. `profiles/*.json` is gitignored with `profiles/example.json`
negated, so copy the example to any other name and it stays out of the repository
on its own. `data/` and `out/` are generated and ignored too.
