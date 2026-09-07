## What this changes, and why

<!-- The why is the part the diff cannot carry. What were you working around? -->

## Checks

- [ ] `uv run ruff check . && uv run black --check . && uv run pylint src/refugia && uv run pytest`
- [ ] New behaviour has a test; a bugfix has the failing test that proves it

<!-- Delete any section below that your change does not touch. -->

### Scoring

Scoring exists twice — Python in `scoring/`, JavaScript inside `template.html` —
because the page re-ranks with no server to ask.

- [ ] Both implementations changed, in this commit
- [ ] A vector added to `tests/conformance/vectors.json` for the behaviour that changed
- [ ] The JavaScript half is still pure and still between its `BEGIN`/`END` markers

### A new metric or source

- [ ] Coverage measured, and stated here — `fetch` flags anything under 75%
- [ ] `DATA_SOURCES.md` gains an entry saying whether the terms were read or inferred
- [ ] Any required citation is on the metric's `citation`, so it travels with a page
- [ ] Requests carry `USER_AGENT`; a source that fans out takes a `Throttle`
- [ ] An empty result is not cached — `{}` is valid JSON and reads back as data

### The published page

- [ ] Anything interpolated into markup goes through `esc()`
- [ ] Rebuilt and opened it; no console errors

### Architecture

- [ ] No `if metric.key == ...` outside a source
- [ ] `direction` is still applied only in `Normalizer`
- [ ] Dependencies injected rather than constructed
