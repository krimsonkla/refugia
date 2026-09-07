# refugia

Ranks US counties as places to live against a personal profile of allergens,
wellbeing, hazard and cost.

_Refugia_ is the ecological term for the pockets where a species persists through
conditions that eliminated it everywhere else. That is the search.

## Why it works the way it does

**Allergen exposure is structural, not forecast.** Pollen APIs answer "should I go
outside on Thursday". A relocation decision needs "how much of this plant grows
where I would live, every spring, for as long as I live there". So the allergen
metrics are land-cover fractions from LANDFIRE, sampled in a radius around each
county's _population-weighted_ centre — the area centroid of a large western county
sits in rangeland nobody lives in.

**The happiness index everyone cites no longer exists, and its replacements are
worse than they look.** The Gallup-Sharecare Community Well-Being Index last
published metro rankings in 2020 and was never machine-readable. Social-media
derived indexes cover every county and are tempting, but they measure curated
public expression rather than residents' experience, and attribute posts to where
they were sent rather than where the sender lives.

So wellbeing here comes from things that actually ask residents about themselves:
CDC PLACES (depression, frequent mental distress, short sleep) and County Health
Rankings (self-rated poor or fair health, poor mental health days, life
expectancy), plus Social Associations as the administrative proxy for organised
social life. They stay separate and weightable rather than pre-combined, because a
score whose weights you cannot see or change is a black box.

**Filters and weights are different mechanisms.** A weight says "this matters"; a
filter says "without this, nothing else matters". Folding a disqualifier into a
weight lets a place win on everything else and surface anyway.

**Normalisation is percentile rank, after filtering.** Several metrics have extreme
tails — one county with catastrophic smoke would compress every other county into
the top few percent of a min-max scale, exactly where the real candidates are.

**A place missing data is not ranked as though the data were good.** Weights are
renormalised over the metrics a place actually has, which quietly rewards it for
the absence: a county outside the vegetation layer would otherwise top an allergen
search precisely because its allergen data is unknown. `min_coverage` (default 0.8)
drops those rows, and the page shows a Data column so a partial row is visible.

## Use

```bash
devenv shell -- refugia fetch                       # download everything (slow, cached)
devenv shell -- refugia rank --profile profiles/example.json --top 20 --explain
devenv shell -- refugia publish --profile profiles/example.json
devenv shell -- refugia ask "cheapest places with almost no juniper"
```

`fetch` is slow and network-bound; everything else reads the saved dataset, so
re-weighting costs nothing.

## Two grains

Most of what is measured is published per county, and the ranking is a county
ranking. Two things are measurable per city without a new kind of source, and the
city panel uses them:

- **Land cover.** The vegetation sample was always a radius around a point, so a
  city is the same question asked at a sharper coordinate. It moves the answer:
  inside one interior-west county the sagebrush share runs from 5.5% around its
  smallest town to 21% around its largest, and the county figure of 24.7%
  describes neither.
- **Health estimates.** CDC PLACES publishes a place release as well as a county
  one, keyed by the same place GEOID the map markers already carry, and it
  carries two measures the county release does not: self-rated health and social
  isolation.

Everything else stays county-level, including the particulate reading and every
County Health Rankings measure. The city panel marks each row `city` or `county`
rather than presenting the mixture as though it were uniform, because a county
figure is identical for every town in it and saying so is the difference between
a measurement and a repetition.

## Adding a metric

Three tiers, in increasing order of what they can express and of what they cost.

1. **A metric already registered needs no work to visualise.** The page builds its
   sliders, table columns and map layers from the registry, reading each metric's
   `direction`, `unit` and `category`. Nothing is hard-coded per metric.

2. **A tabular source is a JSON spec in `specs/`** — no code. Name the URL, the
   format (`csv`, `json`, `xlsx`), the column holding a county FIPS and the column
   holding the value. `specs/wildfire_risk.json` is a worked example. This tier is
   safe for a model to author: it is schema-validated data, and nothing in it
   executes.

3. **A source needing real logic is a written adapter** in
   `src/refugia/metrics/sources/`, implementing the `MetricSource` protocol.
   Constructed geometry, pagination, class crosswalks and retry semantics live
   here, where they can be tested. `landfire_vegetation.py` is the example, and its
   history is the argument for the boundary: it took several rounds against
   undocumented server behaviour, including a version of the raster that silently
   returns no data across the eastern US.

**Every new source is judged on coverage.** `fetch` flags any metric below 75%
coverage, because the characteristic failure of a data source is not an error — it
is a tidy set of plausible numbers for the places it reached and silence for the
rest.

## Asking questions

Two front ends, because a published page cannot reach a machine on your desk.

**In the page.** The artifact declares the `sample` capability, so the browser asks
Claude on the viewer's own account. The model is not handed a summary — it is given
_functions_ over the live view (`list_states`, `explain_subset`, `top_places`,
`compare_places`) and told to call them and never do arithmetic itself.

That distinction is the design. A precomputed summary can only answer the question
it was built for, and the next question has a different shape: "what drives the west
coast" wants weighted deficits by region, "what would I give up in the mountain west"
wants a trade-off between two subsets, "which cheap places have low juniper" wants a
filtered ranking. Anticipating one means failing the rest.

`explain_subset` returns `weighted_deficit` — the gap from the national mean times
the metric's share of the score — and the model is told to rank on that, not on the
raw gap. Handed raw gaps, a model will name a metric that is severe in one state and
near average in its neighbours and call it a shared cause. The weighting is what
makes the answer correct rather than merely plausible.

The first question asks the viewer for consent, and the usage is theirs.

**On the command line.** `refugia ask` uses a local Ollama model as a _query
planner_ rather than an analyst: it converts a question into a scoring profile, the
deterministic engine ranks, and the model then narrates rows it has been handed. It
never holds the numbers it would otherwise be tempted to invent. Default
`qwen3:30b-a3b` — a mixture-of-experts model, so only ~3B parameters are active per
token: 30B-class quality at speed in about 18GB. Override with `--model`.

## Known gaps

- **Air quality stands in for wildfire smoke.** The smoke-specific county dataset
  (Stanford ECHO, on Harvard Dataverse) was unreachable throughout the build, and
  the better-resolved alternative (Dryad, 2006-2025) is 5.7GB of gridded rasters.
  What is carried instead is `air_pollution` — annual mean PM2.5 from the modelled
  surface, at 95% coverage — plus `unhealthy_air_days` and `worst_air_day` from the
  EPA's county AQI summaries, which are the episodic half a mean averages away.
  The pair works: one interior-west county reads 15.8 ug/m3 against a national
  median of 7.6, which is the smoke season showing through.
- **`populus_cover` is a habitat proxy.** LANDFIRE maps no cottonwood type;
  cottonwood sits inside generic riparian classes. The metric combines aspen
  classes with western riparian and floodplain woodland where cottonwood dominates.
- **Scoring is implemented twice** — Python in `scoring/`, JavaScript in
  `artifact/template.html`, because the sliders re-rank without a round trip.
  Nothing currently executes both to compare them.
- Network adapters are thinly tested; the scoring core is not.
- Alaska and Hawaii appear in the table but not the map: the vegetation layer is
  CONUS-only.
