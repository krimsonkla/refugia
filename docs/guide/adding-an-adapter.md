# Adding a metric with an adapter

The third tier, for sources [a spec](adding-a-spec.md) cannot express: constructed
geometry, pagination, a class crosswalk, a join on something other than a FIPS,
retry semantics of its own. An adapter is code, so it owes tests.

## The contract

One protocol, in `src/refugia/metrics/source.py`, and it is two members:

```python
class MetricSource(Protocol):
    @property
    def metrics(self) -> tuple[Metric, ...]:
        """The metrics this source can supply."""

    def fetch(self, places: tuple[Place, ...]) -> dict[str, dict[str, float]]:
        """Return {metric_key: {fips: value}} for the places it can answer for."""
```

That is the whole of it. There is no base class to inherit and no registration
decorator: `workspace.py` constructs your source and hands it to the registry,
which claims its keys.

Two things the protocol's docstring says that are easy to miss:

**Return raw values in their natural units.** Never normalise, never weight. Those
are the engine's job, which is what makes re-weighting cost no network traffic.

**A partial mapping is legitimate.** A place absent from your result is _missing_,
not zero, and the engine keeps that distinction — it renormalises the weights over
what a place actually has, and drops rows below `min_coverage`. Returning `0.0` for
a place you have no data on is the one genuinely damaging thing you can do here,
because it reads as a real measurement.

## A worked example

`src/refugia/metrics/sources/zillow_home_value.py` is the smallest real one — a
single CSV, one metric, about sixty lines. Read that first.

`src/refugia/metrics/sources/landfire_vegetation.py` is the largest, and is the
argument for why this tier exists. It samples a raster service in a radius around
each county's population-weighted centre, crosswalks vegetation class codes, runs a
worker pool, and survives an endpoint that drops connections under sustained use.
None of that is expressible as data.

## What the project will expect of you

These are conventions the review will hold you to, and most of them exist because
something went wrong once.

**Take your dependencies by injection.** A `Cache`, and a `Retry` if you make
requests. Default them to the obvious construction so the common case stays a
one-liner:

```python
def __init__(self, cache: Cache, *, retry: Retry | None = None) -> None:
    self._cache = cache
    self._retry = retry or Retry()
```

This is not tidiness. It is what makes the adapter testable without a network, and
it is the reason `cdc_places.py` has full coverage and the ones that construct their
own dependencies do not.

**Every request carries the shared `USER_AGENT`** from `refugia/__init__.py`. A
public repository multiplies request volume by however many people run it, and an
operator seeing unfamiliar traffic should be able to find out what it is.
`tests/test_outbound_requests.py` parses the tree and will fail your pull request if
a request identifies nobody.

**If you fan out over a worker pool, take a `Throttle`.** Sleeping inside each
worker bounds one worker and not the pool: eight workers each pausing a tenth of a
second still open eighty connections a second.

**Never cache an empty result.** `Cache.write` refuses an empty payload, which
covers zero bytes. It cannot see an empty _parsed_ result — `{}` and `[]` are
perfectly good JSON — so if you serialise a mapping, guard it yourself:

```python
if values:
    self._cache.write(cache_key, json.dumps(values).encode(), ".json")
```

A cached failure is worse than a failure. It reads back as data, and the run that
would have corrected it never makes the request.

**Let the shared `Retry` decide what is worth repeating.** It repeats dropped
connections, timeouts, 429 and 5xx, and raises everything else at once — a 404 from
an upstream that moved will still be a 404 after ten seconds of backoff. If your
endpoint fails in a shape only you recognise, declare it:

```python
# This endpoint answers 200 with an error body.
Retry(also_transient=(KeyError, ValueError))
```

**No `if metric.key == ...` outside your source.** Scoring, the CLI and the page are
written against the registry. If you find yourself wanting a special case in one of
them, the registration model has failed somewhere and that is the bug.

## Doing it

1. Write the source in `src/refugia/metrics/sources/`, one class per file, named
   after it.
2. Register it in `workspace.py`, which is the only module that knows the full
   source set exists. Adapters register before specs, so a spec cannot silently
   displace one.
3. Write the tests. Seed the cache with a payload rather than stubbing a client
   where you can — `tests/test_zillow_and_epa.py` does exactly that, and it tests
   the real parsing path. Cover the ways a parser actually fails on somebody else's
   file: a blank column, a padded name, a row that will not parse.
4. `uv run refugia fetch --only <key>` and **read the coverage.** Under 75% is
   flagged, and it is the number that decides whether the metric is usable.
5. Add the publisher to `DATA_SOURCES.md`, saying whether you read its terms or
   inferred them. If it requires a citation, put it on the metric's `citation` so it
   travels into the published page rather than living only in a file.

## If the page needs to change

It should not. A registered metric already gets a slider, a column and a map layer
— see [what a registered metric gets for
free](adding-a-spec.md#what-a-registered-metric-gets-for-free), including the two
conditions on that. The page builds itself from the registry, so a new metric arrives
with a slider, a column and a map layer already. If you find yourself editing
`template.html` to accommodate one metric, stop — that is the design failure the
registry exists to prevent, and it is worth raising as an issue instead.

The exception is a change to _scoring semantics_, which lives in two places on
purpose: Python in `scoring/` and JavaScript in `template.html`, because the page
re-ranks with no server to ask. Change both in the same commit and add a case to
`tests/conformance/vectors.json`, which runs the same vectors through both and fails
the build if they disagree.
