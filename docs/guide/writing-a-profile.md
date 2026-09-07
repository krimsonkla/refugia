# Writing a profile

A profile is the whole of your preference, as data. `profiles/example.json` is a
working one to copy.

```json
{
  "name": "Allergens first, cost close behind",
  "normalization": "percentile",
  "min_coverage": 0.8,
  "home_fips": "17031",
  "weights": { "juniper_cover": 5, "home_value": 3, "life_expectancy": 2 },
  "criteria": [{ "field": "population", "comparison": "min", "value": 40000 }]
}
```

**`weights`** — a metric key to a number. Only the ratios matter: they are
rescaled to sum to 1, so `{"a": 5, "b": 1}` and `{"a": 50, "b": 10}` rank
identically. Omitting a metric and weighting it `0` mean the same thing: both
leave it out of the score and out of the coverage denominator, so switching one
off cannot drop a place for missing data it is no longer being judged on. **Never
use a negative weight** — it is read as zero. Each metric already declares whether high
or low is good, so the sign is carried for you, and `refugia metrics` prints it:

```
$ uv run refugia metrics
juniper_cover              lower is better  allergen    % of land
coldest_day                higher is better climate     degrees F
...
21 metrics. Weight any of these in a profile's `weights`.
```

That list comes from the registry rather than from this page, so it cannot drift.
A key that is not in it stops the run and says so.

**`criteria`** — hard filters, each `{field, comparison, value}`. `comparison` is
one of `min`, `max`, `in`, `not_in`; the last two take a list. `field` is either a
metric key or an attribute of the place itself — `population`, `state`, `name`,
`lat`, `lon`, `fips`, or `metro`. A place with no value for the field never
passes, which is deliberate: an unknown is not a pass.

```json
[
  { "field": "population", "comparison": "min", "value": 40000 },
  { "field": "state", "comparison": "not_in", "value": ["Arizona", "Nevada"] },
  { "field": "wildfire_risk", "comparison": "max", "value": 80 }
]
```

Filters and weights are not interchangeable. A weight reorders; a filter removes.
"Nowhere with more juniper than I have now" cannot be said by weighting, however
heavily.

**`normalization`** — `percentile` (the default) or `minmax`. Percentile resists
the long tails that several of these metrics have; min-max lets one extreme county
compress everything else.

**`min_coverage`** — the share of your weighted metrics a place must actually have
data for, default `0.8`. Below it the place is dropped rather than scored on what
is left, because scoring on what is left quietly rewards a place for missing data.

**`home_fips`** — optional, the 5-digit county FIPS of where you live now. Set it
and the page ranks everywhere against home, adds the per-metric comparison panel,
and offers each metric's "rule out anywhere worse than home" cut. Leave it out and
everything else still works.

**`name`** — free text, shown on the page.

---

Next: [reading the numbers](reading-the-numbers.md) to interpret what comes back,
or [adding a metric](adding-a-spec.md) if the thing you want to weight is not in the
list yet.
