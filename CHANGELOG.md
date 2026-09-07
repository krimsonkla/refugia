# Changelog

Notable changes, newest first. Dates are the date of the tag; an unreleased
section has none, because nothing has been tagged.

This project is pre-1.0. Two of its formats are things you may come to depend on —
the profile JSON you write, and the `data/dataset.json` a fetch produces — and
neither is frozen yet. A breaking change to either will appear here and move the
minor version until 1.0, after which they will not break without a major.

## Unreleased

Everything below is on `main` and nothing is tagged. A `v0.1.0` tag existed
briefly, nineteen commits back and installing fifteen metrics against a README
that claimed twenty-one; it was dropped rather than moved, so the first tag this
project carries will be the first one that means something.

- Ranks US counties in a Census metro or micropolitan area against a profile of
  weights and hard requirements, across 21 metrics in seven categories.
- `publish` writes one self-contained HTML page: the whole dataset travels with it,
  so the sliders re-rank in the browser with no server.
- `ask` plans a query with a local Ollama model and narrates rows the deterministic
  engine produced, rather than letting the model hold the numbers.
- Metrics register from adapters or from JSON specs in `specs/`, and nothing in
  scoring, the CLI or the page is written per metric.
- Scoring exists twice, in Python and in the page; shared conformance vectors run
  through both and fail the build if they disagree.
