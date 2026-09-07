"""Command line surface: fetch, rank, publish, ask."""

import json
from pathlib import Path
from typing import Annotated

import typer

from refugia.artifact.builder import ArtifactBuilder
from refugia.ask.planner import QueryPlanner
from refugia.scoring.engine import ScoringEngine
from refugia.scoring.profile import Profile
from refugia.store.dataset import Dataset
from refugia.workspace import Workspace

LOW_COVERAGE = 0.75

app = typer.Typer(help="Rank US places to live against a personal profile.", no_args_is_help=True)


def _workspace(root: Path | None, radius_km: float = 25.0) -> Workspace:
    """Build the composition root for a command."""
    return Workspace(root or Path.cwd(), radius_km=radius_km)


def _collect(registry, places, existing, wanted):
    """Run each source that supplies a wanted key and merge its values.

    A source that raises costs its own metrics and nothing else. Nine of these
    upstreams are pinned to a dated path -- a filename with a year in it, a release
    directory -- so one of them moving is a matter of when, and letting that end
    the run would throw away every source registered after it along with the hours
    already spent on the ones before. Returning partial data is the documented
    contract in metrics/source.py; a source returning none of it is the same
    statement, louder.

    Returns the merged values and a list of (source name, reason) for the failures.
    """
    values: dict[str, dict[str, float]] = dict(existing)
    failures: list[tuple[str, str]] = []
    for source in registry.sources:
        keys = {m.key for m in source.metrics}
        if wanted and not keys & wanted:
            continue
        name = type(source).__name__
        typer.echo(f"  fetching {name} -> {', '.join(sorted(keys))}")
        try:
            values.update(source.fetch(places))
        except Exception as error:  # pylint: disable=broad-exception-caught
            # Deliberately broad: an adapter can fail in as many ways as the
            # format it parses, and every one of them should cost one metric
            # rather than the run.
            reason = f"{type(error).__name__}: {error}".strip()
            failures.append((name, reason))
            typer.secho(f"    failed: {reason}", fg="red")
            continue
        _report_source(source)
    return values, failures


def _report_source(source) -> None:
    """Say what a source could not answer for, separating permanent from transient."""
    outside = getattr(source, "outside_coverage", ())
    if outside:
        typer.echo(f"    {len(outside)} place(s) outside this layer's coverage")
    failures = getattr(source, "failures", ())
    if failures:
        typer.echo(f"    {len(failures)} place(s) failed after retries:")
        for fips, reason in failures[:5]:
            typer.echo(f"      {fips}: {reason}")


def _load_dataset(workspace: Workspace) -> Dataset:
    """Read the saved dataset, or say how to make one.

    Every command but `fetch` needs it, and before the first fetch the bare
    FileNotFoundError names a path rather than the thing to do about it.
    """
    if not workspace.dataset_path.exists():
        typer.secho(
            f"no dataset at {workspace.dataset_path}\nrun `refugia fetch` first "
            "-- it downloads every metric and saves them there.",
            fg="red",
        )
        raise typer.Exit(code=1)
    return Dataset.load(workspace.dataset_path)


def _report_failures(failures) -> None:
    """Repeat any source failure at the end, where it will still be on screen."""
    if not failures:
        return
    typer.secho(
        f"\n{len(failures)} source(s) failed and contributed nothing:",
        fg="red",
    )
    for name, reason in failures:
        typer.secho(f"  {name}: {reason}", fg="red")
    typer.secho(
        "Their metrics keep whatever a previous fetch saved. "
        "A dated upstream path that has moved is the usual cause.",
        fg="red",
    )


def _report_coverage(dataset: Dataset) -> None:
    """Print per-metric coverage and flag anything too thin to rank on.

    A half-failing source returns plausible numbers for the places it reached and
    silence for the rest, so it reads as success in a list of percentages unless
    the thin ones are called out.
    """
    thin = []
    for key, share in sorted(dataset.coverage().items()):
        flag = ""
        if share < LOW_COVERAGE:
            flag = "  << LOW"
            thin.append(key)
        typer.echo(f"  {key:22s} {share * 100:5.1f}% of places{flag}")
    if thin:
        typer.secho(
            f"\n{len(thin)} metric(s) below {LOW_COVERAGE:.0%} coverage: "
            f"{', '.join(thin)}.\nRanking on these compares only the places that "
            f"happened to return data.",
            fg="yellow",
        )


@app.command()
def fetch(
    root: Annotated[
        Path | None, typer.Option(help="Project root; defaults to the working directory.")
    ] = None,
    universe: Annotated[str, typer.Option(help="metro_micro | metro | all")] = "metro_micro",
    radius_km: Annotated[
        float, typer.Option(help="Vegetation sampling radius around each place.")
    ] = 25.0,
    only: Annotated[
        str, typer.Option(help="Comma-separated metric keys to refresh; default all.")
    ] = "",
) -> None:
    """Download every metric for the candidate places and save the dataset."""
    workspace = _workspace(root, radius_km)
    registry = workspace.build_registry()
    places = workspace.build_places(universe=universe).places
    typer.echo(f"{len(places)} candidate places ({universe})")

    existing = (
        Dataset.load(workspace.dataset_path).values if workspace.dataset_path.exists() else {}
    )
    wanted = {k.strip() for k in only.split(",") if k.strip()}
    values, failures = _collect(registry, places, existing, wanted)

    dataset = Dataset(places=places, metrics=registry.metrics, values=values)
    dataset.save(workspace.dataset_path)
    typer.echo(f"\nsaved {workspace.dataset_path}")
    _report_coverage(dataset)
    # After the coverage table, not before: a failure scrolled past an hour ago is
    # the one thing a reader must not miss, and this is the last thing printed.
    _report_failures(failures)


@app.command()
def metrics(
    root: Annotated[
        Path | None, typer.Option(help="Project root; defaults to the working directory.")
    ] = None,
) -> None:
    """List every registered metric key, for writing a profile against.

    Printed from the registry rather than a written list, so it cannot drift from
    what the tool actually knows. Reads no dataset, so it works before a fetch.
    """
    workspace = _workspace(root)
    registry = workspace.build_registry()
    if not workspace.spec_dir.exists():
        # The declarative tier lives in files beside the project, so running from
        # anywhere else lists a short registry that looks complete.
        typer.secho(
            f"no specs/ under {workspace.spec_dir.parent}; "
            "the metrics declared there are missing from this list",
            fg="yellow",
        )
    typer.echo(f"{'key':26s} {'direction':16s} {'category':11s} unit")
    for metric in sorted(registry.metrics, key=lambda m: (m.category, m.key)):
        way = "lower is better" if metric.direction == "lower_better" else "higher is better"
        typer.echo(f"{metric.key:26s} {way:16s} {metric.category:11s} {metric.unit}")
    typer.echo(f"\n{len(registry.metrics)} metrics. Weight any of these in a profile's `weights`.")


@app.command()
def rank(
    profile: Annotated[Path, typer.Option(help="Profile JSON with weights and criteria.")],
    root: Annotated[
        Path | None, typer.Option(help="Project root; defaults to the working directory.")
    ] = None,
    top: Annotated[int, typer.Option(help="How many places to print.")] = 20,
    explain: Annotated[bool, typer.Option(help="Show each metric's contribution.")] = False,
) -> None:
    """Score the saved dataset under a profile and print the ranking."""
    workspace = _workspace(root)
    dataset = _load_dataset(workspace)
    registry = workspace.build_registry()
    ranked = ScoringEngine(registry).rank(dataset.places, dataset.values, Profile.load(profile))

    typer.echo(f"{'#':>3}  {'place':44s} {'score':>6}  {'cover':>5}")
    for position, scored in enumerate(ranked[:top], start=1):
        typer.echo(
            f"{position:3d}  {scored.place.label[:44]:44s} "
            f"{scored.total:6.1f}  {scored.coverage * 100:4.0f}%"
        )
        if explain:
            for key, value in sorted(scored.contributions.items(), key=lambda kv: -kv[1]):
                raw = scored.raw.get(key)
                shown = f"{raw:,.1f}" if raw is not None else "n/a"
                typer.echo(f"       {key:22s} +{value:5.1f}   raw={shown}")


@app.command()
def publish(
    profile: Annotated[Path, typer.Option(help="Profile JSON with weights and criteria.")],
    root: Annotated[
        Path | None, typer.Option(help="Project root; defaults to the working directory.")
    ] = None,
    out: Annotated[Path, typer.Option(help="Where to write the page.")] = Path("out/refugia.html"),
) -> None:
    """Build the interactive map and table as a self-contained HTML page."""
    workspace = _workspace(root)
    dataset = _load_dataset(workspace)
    written = ArtifactBuilder(workspace.cache).build(dataset, Profile.load(profile), out)
    typer.echo(f"wrote {written} ({written.stat().st_size / 1e6:.1f} MB)")


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="A question about the data, in plain English.")],
    root: Annotated[
        Path | None, typer.Option(help="Project root; defaults to the working directory.")
    ] = None,
    model: Annotated[str, typer.Option(help="Ollama model tag.")] = "qwen3:30b-a3b",
    host: Annotated[str, typer.Option(help="Ollama host.")] = "http://localhost:11434",
) -> None:
    """Answer a question by planning a query, running it, and narrating the result."""
    workspace = _workspace(root)
    dataset = _load_dataset(workspace)
    planner = QueryPlanner(model=model, host=host)
    plan = planner.plan(question, dataset.metrics)
    typer.echo(f"plan: {json.dumps(plan.to_dict())}\n")
    ranked = ScoringEngine(workspace.build_registry()).rank(dataset.places, dataset.values, plan)
    typer.echo(planner.narrate(question, plan, ranked[:15], dataset.metrics))


if __name__ == "__main__":
    app()
