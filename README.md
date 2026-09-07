# refugia

Ranks US counties as places to live against a personal profile of allergens,
wellbeing, hazard and cost.

_Refugia_ is the ecological term for the pockets where a species persists through
conditions that eliminated it everywhere else. That is the search.

## The answer is a page, not a table

`refugia publish` writes one self-contained HTML file. The ranking is not baked
into it — the page carries the whole dataset and re-scores in the browser, so the
sliders re-rank as you move them and the map reshades on whichever metric you
pick.

![The refugia page: weighting sliders on the left, a choropleth of the United States on the right](docs/screenshot-map.jpg)

Weights reorder; requirements remove. "Nowhere with more juniper than I already
have" is not a preference you can express by weighting, so each metric carries its
own cut, measured against where you live now.

Click any county and it is compared with home, metric by metric, ordered by how
much each one actually moved the score rather than by the size of the raw gap.

![The comparison panel: Yankton County, South Dakota against Cook County, Illinois, metric by metric](docs/screenshot-compare.jpg)

One file, no server, works offline. You can hand it to someone else and they can
re-weight it to their own priorities without installing anything.

> These are county-wide figures, and several are modelled estimates rather than
> direct measurements. They are ranked against weights you choose, which makes
> this a way to narrow a list — not advice, and not a verdict on these places or
> the people who live in them.

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

## Install

Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/krimsonkla/refugia && cd refugia
uv sync --all-groups
```

That is the whole install. `uv` builds the environment from the committed
`uv.lock` and puts the `refugia` command in it; prefix commands with `uv run`, or
activate the venv once and drop the prefix. No API keys, accounts or registrations
are needed for any data source.

There is also a `devenv.nix` for [devenv.sh](https://devenv.sh), which pins the
interpreter and installs the git hooks. It is a maintainer convenience rather than
a requirement — nothing here needs nix, and the test suite runs identically either
way.

## Use

```bash
uv run refugia fetch                                      # download everything (slow, cached)
uv run refugia rank --profile profiles/example.json --top 20 --explain
uv run refugia publish --profile profiles/example.json    # writes out/refugia.html
uv run refugia ask "cheapest places with almost no juniper"
```

`fetch` is slow and network-bound; everything else reads the saved dataset, so
re-weighting costs nothing. Copy `profiles/example.json` and edit it — the weights
are yours, and that is the point.

### Every option

Each command also takes `--root`, which defaults to the working directory and is
where `data/`, `specs/` and `out/` are looked for.

| Command   | Option        | Default                  | What it does                                 |
| --------- | ------------- | ------------------------ | -------------------------------------------- |
| `fetch`   | `--universe`  | `metro_micro`            | `metro_micro`, `metro` or `all`              |
|           | `--radius-km` | `25.0`                   | Vegetation sampling radius around each place |
|           | `--only`      | every metric             | Comma-separated keys to refresh              |
| `rank`    | `--profile`   | required                 | The profile JSON                             |
|           | `--top`       | `20`                     | How many rows to print                       |
|           | `--explain`   | off                      | Each metric's contribution and the raw value |
| `publish` | `--profile`   | required                 | The profile JSON                             |
|           | `--out`       | `out/refugia.html`       | Where to write the page                      |
| `ask`     | `--model`     | `qwen3:30b-a3b`          | Ollama model tag                             |
|           | `--host`      | `http://localhost:11434` | Ollama host                                  |
| `metrics` | —             | —                        | Prints the registered keys; needs no dataset |

**The universe is not every county.** `metro_micro`, the default, is the 1,906
counties inside a Census metro or micropolitan area — the places with a town in
them. `all` is every US county, and `metro` narrows to metro areas only. It
decides what gets downloaded, so changing it means fetching again.

### What a fetch costs

Roughly 90 MB across about 6,900 files under `data/cache/`, and a `data/dataset.json`
of around 1.3 MB. Expect it to take a while: the vegetation layer alone is
thousands of individual samples.

It is cache-first and therefore resumable — interrupt it and run it again and it
picks up where it stopped. `--only wildfire_risk` refreshes one metric without
touching the rest, which is what you want when a single upstream has published a
new year.

A source whose upstream has moved costs its own metrics and nothing else. Nine of
these are pinned to a dated path — a filename with a year in it, a release
directory — so expect it eventually. The run continues, those metrics keep
whatever the last successful fetch saved, and the failure is repeated in red after
the coverage table so an hour of scrollback cannot hide it.

## Reading the output

**The score is a position, not a measurement.** `score` in the CLI, `FIT` on the
page, is a 0–100 percentile rank _among the places that survived your filters_. So
it is not comparable between two profiles, and not comparable to itself before and
after you change a requirement — tightening a filter re-spreads everything that is
left. A place at 71 is not "71% good"; it is near the top of this particular
field.

**`cover`** — `Data` on the page — is the share of your weighted metrics that this
place actually has a value for. Anything below `min_coverage` never appears at
all. A row at 90% is scored on nine tenths of what you asked for, and the missing
tenth is not counted against it.

`rank --explain` breaks a place's score into each metric's contribution alongside
the raw value, which is the fastest way to see whether a result is real or an
artefact of one metric doing all the work.

## Writing a profile

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
   holding the value, plus a `citation` and `terms_url` if the publisher requires
   one. `specs/life_expectancy.json` is a worked example. Nothing in a
   spec executes, and it is validated on load — the URL must be `https`, and the
   fields that reach the published page may not contain markup — so a model can
   draft one and the blast radius stays bounded: a wrong spec produces a metric
   with poor coverage, which the coverage gate surfaces, rather than arbitrary
   behaviour. It is still a network request in data clothing, though. Read the URL
   before you merge it.

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

**In the page**, but only where a host offers a model. Nothing is declared at build
time — `publish` substitutes the data into the template and writes a file. The page
asks at runtime: it looks for `window.claude.use`, and if that exists it requests
the `sample` capability. Granted, the Ask panel appears and the viewer's questions
run on their own account, under whatever the host asks them to agree to. Declined,
or opened from disk, or served from anywhere else — the panel stays hidden and the
rest of the page behaves exactly as it does anywhere.

Where it is available, the model is not handed a summary — it is given _functions_
over the live view (`list_states`, `explain_subset`, `top_places`, `compare_places`)
and told to call them and never do arithmetic itself.

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

The page reaches the model only when the viewer asks it to — typing a question, or
pressing "Summarise this comparison". Acquiring the capability is not using it, and
nothing is sent on load. Whether the viewer is prompted first, and on whose account
the usage lands, is the host's to decide; the page only asks, and handles being
told no.

**On the command line.** `refugia ask` uses a local Ollama model as a _query
planner_ rather than an analyst: it converts a question into a scoring profile, the
deterministic engine ranks, and the model then narrates rows it has been handed. It
never holds the numbers it would otherwise be tempted to invent. Default
`qwen3:30b-a3b` — a mixture-of-experts model, so only ~3B parameters are active per
token: 30B-class quality at speed in about 18GB. Override with `--model`.

This is the one part of refugia with a prerequisite outside `uv sync`. It needs
[Ollama](https://ollama.com) installed and running, and the model pulled:

```bash
ollama serve
ollama pull qwen3:30b-a3b        # about 18 GB
uv run refugia ask "cheapest places with almost no juniper"
```

Everything else — `fetch`, `rank`, `publish` — works without it. By default the
model runs on your own machine against a dataset already on disk, so the question
and the rows never leave it; `--host` will point at another Ollama instance if you
want it to, and then they do.

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
  `artifact/template.html`, because the sliders re-rank without a round trip and
  the page has no server to ask. `tests/conformance/vectors.json` runs the same
  cases through both and fails the build if they disagree, so the duplication
  remains but the drift does not.
- Network adapters are thinly tested; the scoring core is not.
- Alaska and Hawaii appear in the table but not the map: the vegetation layer is
  CONUS-only.

## Contributing

`CONTRIBUTING.md` has the setup, the checks CI runs, and the conventions that will
get a pull request sent back. The most useful contributions are a new metric or a
source that has stopped working — this is a thin layer over ten public datasets,
and those datasets move.

## Data and licence

The code is MIT — see `LICENSE`. The data is not the code's to license: refugia
ships none of it and fetches everything at run time, so each source's own terms
govern what you fetch. `DATA_SOURCES.md` has one entry per publisher, and marks
which positions are verified and which are inferred.

Two matter in practice. **County Health Rankings**, which five metrics draw on,
licenses its content for personal and non-profit use only and requires a specific
citation; commercial use needs their prior written consent. **Zillow** requires
clear attribution. Both citations are in the footer of every page `publish`
writes, along with the ISC notice for the county outlines.

That footer matters because a published page embeds the values for every county it
ranks. Running the tool is not redistribution; sharing the page is, and the same
terms travel with it. So does the profile it was built from — including your home
county, if you set one — so a page is a statement about your preferences as well as
about the places. `publish` says as much when it writes one.
