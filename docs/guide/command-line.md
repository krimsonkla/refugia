# The command line

Four commands. `fetch` is slow and network-bound; everything else reads the saved
dataset, so re-weighting costs nothing.

```bash
uv run refugia fetch                                      # download everything (slow, cached)
uv run refugia rank --profile profiles/example.json --top 20 --explain
uv run refugia publish --profile profiles/example.json    # writes out/refugia.html
uv run refugia ask "cheapest places with almost no juniper"
```

`fetch` is slow and network-bound; everything else reads the saved dataset, so
re-weighting costs nothing. Copy `profiles/example.json` and edit it — the weights
are yours, and that is the point.

`--explain` breaks a place's score into what actually produced it:

```
  #  place                                         score  cover
  1  Lincoln County, South Dakota                   69.2    90%
       populus_cover          +  6.4   raw=0.2
       juniper_cover          +  6.3   raw=0.0
       sagebrush_cover        +  6.3   raw=0.0
       air_pollution          +  6.2   raw=6.5
       poor_mental_health_days +  4.8   raw=3.5
       life_expectancy        +  4.7   raw=83.8
       ...
```

Read down the contributions and you can see whether a result is real or one metric
doing all the work.

## Every option

Each command also takes `--root`, which defaults to the working directory and is
where `data/` and `out/` live, and where a `specs/` of your own is looked for.

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

## What a fetch costs

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

---

Next: [writing a profile](writing-a-profile.md), since `--profile` is the argument
every other command turns on.
