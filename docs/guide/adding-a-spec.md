# Adding a metric with a spec

Three tiers, and this is the middle one. Take the cheapest that can express your
source.

**Tier 1 — already registered.** Nothing to do. See below for what that means.

**Tier 2 — a JSON spec.** No code. This page.

**Tier 3 — [a written adapter](adding-an-adapter.md).** For sources that need real
logic: constructed geometry, pagination, a class crosswalk, retry semantics.

## What a registered metric gets for free

This is the part worth being precise about, because "no presentation code" is easy
to hear as "it appears by magic".

A registered metric arrives in the published page with three things, none of which
you write:

- **a slider**, inside the group named by its `category`
- **a table column**, labelled and formatted by its `label` and `unit`
- **an entry in the map's metric selector**, so the choropleth can shade on it
- **two requirement controls**, under its slider: rule out anywhere worse than home,
  and a floor or ceiling you type, whichever way its `direction` points

All of it comes from iterating the dataset's metric list. There is no per-metric code
anywhere in `src/refugia/artifact/template.html`, and adding one should never
require editing it — `test_the_page_names_no_metric_of_its_own` fails the build if a
registered metric's key ever appears in that file, so this is a check rather than a
promise. It was a promise for a while, and untrue: a maximum home value had a box of
its own, written into the page nine times over.

Two things qualify that.

**It has to be in the saved dataset.** `publish` reads `data/dataset.json`, not the
registry, so a metric you registered but never fetched is simply absent from the
page. `refugia fetch --only <key>` is enough: `--only` narrows which sources run,
but the dataset's metric list is rewritten from the whole registry every time.

**It arrives switched off.** The page shows it dimmed, with its checkbox clear and
its slider parked at 1, unless the profile that built the page weights it. Switching
it on re-ranks everything immediately.

That second one is deliberate rather than an oversight. An unweighted metric stays
visible because a column that disappeared when its weight went to zero took the
evidence with it — a reader could no longer look at the thing they had just decided
not to rank by, which is exactly where an unwelcome surprise hides. Weighting
decides the ranking; it does not decide what can be looked at.

## The whole of it

A spec is one file in `src/refugia/specs/`, named after the metric it declares.
Here is a shipped one, `src/refugia/specs/life_expectancy.json`, in full:

```json
{
  "key": "life_expectancy",
  "label": "Life expectancy",
  "unit": "years",
  "direction": "higher_better",
  "category": "wellbeing",
  "description": "Average number of years a person can expect to live. The broadest single outcome measure of how a place treats the people in it.",
  "source": "County Health Rankings & Roadmaps, 2025 release",
  "url": "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data2025_v2.csv",
  "format": "csv",
  "fips_column": "5-digit FIPS Code",
  "value_column": "Life Expectancy raw value",
  "aggregate": "first",
  "citation": "University of Wisconsin Population Health Institute. County Health Rankings & Roadmaps. www.countyhealthrankings.org — licensed for personal and non-profit use.",
  "terms_url": "https://www.countyhealthrankings.org/terms-use"
}
```

That file is the entire integration. There is no code anywhere that knows this
metric exists.

## The fields

**What the column means**, and what the rest of the project reads:

| Field         | What it does                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------ |
| `key`         | The identifier a profile weights. Lowercase, digits and underscores                              |
| `label`       | Shown on the slider, the column header and the map selector                                      |
| `unit`        | Shown beside values. Free text — `years`, `% of adults`, `ug/m3 annual mean`                     |
| `direction`   | `higher_better` or `lower_better`. **The only place the sign lives**                             |
| `category`    | Groups the sliders. Existing ones: allergen, wellbeing, health, climate, hazard, cost, community |
| `description` | The hint under the slider. Say what it measures and what it does not                             |
| `source`      | Named in the page footer                                                                         |

**Where to get it:**

| Field          | What it does                                                         |
| -------------- | -------------------------------------------------------------------- |
| `url`          | The file. Must be `https`                                            |
| `format`       | `csv`, `json` or `xlsx`                                              |
| `fips_column`  | The column holding a county FIPS, exactly as the publisher spells it |
| `value_column` | The column holding the number                                        |

**Optional, for when the file is not quite shaped like that:**

| Field          | What it does                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------- |
| `aggregate`    | `first` (default), `mean`, `median`, `sum`, `max`, `min` — how to collapse repeated rows for one county |
| `where`        | `{"column": "value"}` — keep only rows matching                                                         |
| `scale`        | Multiply every value, for when a publisher ships a percentage as `0.14`                                 |
| `sheet`        | Which worksheet, for `xlsx`                                                                             |
| `records_path` | Dotted path to the array, for JSON nested under a wrapper                                               |
| `citation`     | Required text, if the publisher requires one. Travels into the page footer                              |
| `terms_url`    | Where those terms are stated                                                                            |

## What is checked, and what is not

A spec is validated when it loads, not when it fetches, so a bad one fails
immediately rather than an hour into a download:

- the URL must be `https`
- `key`, `label`, `unit`, `category`, `description` and `source` may not contain
  angle brackets, because all six are interpolated into the published page
- `format` and `aggregate` must be values the parser knows
- `direction` must be one of the two
- every required field must be present, and the error names the missing ones

Every shipped spec is run through that validator by `tests/test_specs.py`, which
also asserts that a spec citing a source links its terms.

**What is not checked is the URL itself.** Nothing fetches it at review time and
nothing can tell you it is the right file. A spec is a network request in data
clothing — see `SECURITY.md`. Read the URL before merging one.

## Doing it

1. Write the file into `src/refugia/specs/<key>.json`. Inside the package, because
   that is what a wheel carries; a `specs/` beside the project also works and is
   where your own go if you would rather not touch the repository's.
2. `uv run refugia metrics` — your key should be in the list. A spec that fails
   validation does not go quietly missing: it raises, naming the file, and **every**
   command fails until it is fixed. That is deliberate — a metric silently absent is
   the failure this project is most careful about — but it does mean a bad spec
   stops the tool rather than stopping itself.
3. `uv run refugia fetch --only <key>` — fetches just yours, leaving everything
   else cached.
4. **Read the coverage.** `fetch` flags anything under 75%. This is the number that
   decides whether the metric is usable, because the characteristic failure of a
   data source is not an error: it is a tidy set of plausible numbers for the
   places it reached and silence for the rest.
5. `uv run refugia rank --profile profiles/example.json --top 10 --explain` and see
   whether the answer moved in a direction that makes sense.
6. Add an entry to `DATA_SOURCES.md` for the publisher, saying whether you read its
   terms or inferred them.

## When a spec cannot do it

If you find yourself wanting a spec to do arithmetic across columns, follow
pagination, join on a name, or sample geometry — it cannot, and that is deliberate.
Those live in [a written adapter](adding-an-adapter.md), where they can be tested.
