# The command line

Five commands. `metrics` needs no dataset and is the one to run first. `fetch` is
slow and network-bound, and so is the **first** `publish` — it downloads four more
things `fetch` never touches. After that, everything reads the saved dataset and the
cache, so re-weighting costs nothing.

```bash
uv run refugia fetch                                      # download everything (slow, cached)
uv run refugia rank --profile profiles/example.json --top 20 --explain
uv run refugia publish --profile profiles/example.json    # writes out/refugia.html
uv run refugia ask "cheapest places with almost no juniper"
```

Copy `profiles/example.json` and edit it — the weights are yours, and that is the
point. `rank` never touches the network. `publish` does, but only until its own
downloads are cached: see [What a fetch costs](#what-a-fetch-costs).

`--explain` breaks a place's score into what actually produced it:

```
  #  place                                         score  cover
  1  Lincoln County, South Dakota                   69.2    90%
       populus_cover          +  6.4   raw=0.2
       juniper_cover          +  6.3   raw=0.0
       sagebrush_cover        +  6.3   raw=0.0
       air_pollution          +  6.2   raw=6.5
       poor_mental_health_days +  4.8   raw=3.5
       poor_or_fair_health    +  4.8   raw=9.8
       ...
```

Read down the contributions and you can see whether a result is real or one metric
doing all the work.

## Every option

Each command also takes `--root`, which defaults to the working directory and is
where `data/` lives and where a `specs/` of your own is looked for. It does not
move `out/` — `publish --out` takes the path it writes to.

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

Whichever you choose is recorded in `data/dataset.json` and the published page
says so under its title — "1,906 US counties in a metro or micropolitan area", "in
a metro area", or just "3,144 US counties" for `all`. A dataset saved before that
was recorded still gets the right line: CBSA membership travels with every place,
so the page reads it off the places it holds.

## What a fetch costs

Roughly 55 MB across about 2,100 files under `data/cache/`, and a `data/dataset.json`
of around 1.3 MB. Expect it to take a while: the vegetation layer alone is
thousands of individual samples.

**The first `publish` downloads more.** `fetch` runs the metric sources and nothing
else; the page needs four things none of them provide, so `publish` gets them itself
the first time it runs:

| What                       | From                        | Size   |
| -------------------------- | --------------------------- | ------ |
| County and state outlines  | `us-atlas` on a CDN         | 0.8 MB |
| City names and populations | Census population estimates | 7 MB   |
| City coordinates           | Census 2024 Gazetteer       | 1.2 MB |
| City-level health measures | CDC PLACES place release    | 6 MB   |

Then it resamples the land cover around every mapped town — about 4,800 more
LANDFIRE calls, 19 MB — because a town's vegetation is not its county's. Together
that is another 34 MB and roughly 4,800 files, so a full cache is nearer 90 MB
across 6,900 files than the fetch figure above.

All of it is cached, so the second `publish` and every one after it is offline and
immediate. The first is not: fetching, disconnecting and then publishing fails, and
`publish` says so rather than showing a traceback.

It is cache-first and therefore resumable — interrupt it and run it again and it
picks up where it stopped. `--only wildfire_risk` refreshes one metric without
touching the rest, which is what you want when a single upstream has published a
new year.

A source whose upstream has moved costs its own metrics and nothing else. Nine of
these are pinned to a dated path — a filename with a year in it, a release
directory — so expect it eventually. The run continues, those metrics keep
whatever the last successful fetch saved, and the failure is repeated in red after
the coverage table so an hour of scrollback cannot hide it.

`ask` is the one command with a prerequisite outside `uv sync`: it needs Ollama
running locally and the model pulled (`ollama serve`, then
`ollama pull qwen3:30b-a3b`, about 18 GB). Everything else works without it.

---

Next: [writing a profile](writing-a-profile.md), since `--profile` is the argument
every other command turns on.
