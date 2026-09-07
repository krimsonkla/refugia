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


def _collect(registry, places, existing, wanted) -> dict[str, dict[str, float]]:
    """Run each source that supplies a wanted key and merge its values."""
    values: dict[str, dict[str, float]] = dict(existing)
    for source in registry.sources:
        keys = {m.key for m in source.metrics}
        if wanted and not keys & wanted:
            continue
        typer.echo(f"  fetching {type(source).__name__} -> {', '.join(sorted(keys))}")
        values.update(source.fetch(places))
        _report_source(source)
    return values


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
    values = _collect(registry, places, existing, wanted)

    dataset = Dataset(places=places, metrics=registry.metrics, values=values)
    dataset.save(workspace.dataset_path)
    typer.echo(f"\nsaved {workspace.dataset_path}")
    _report_coverage(dataset)


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
    dataset = Dataset.load(workspace.dataset_path)
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
    dataset = Dataset.load(workspace.dataset_path)
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
    dataset = Dataset.load(workspace.dataset_path)
    planner = QueryPlanner(model=model, host=host)
    plan = planner.plan(question, dataset.metrics)
    typer.echo(f"plan: {json.dumps(plan.to_dict())}\n")
    ranked = ScoringEngine(workspace.build_registry()).rank(dataset.places, dataset.values, plan)
    typer.echo(planner.narrate(question, plan, ranked[:15], dataset.metrics))


if __name__ == "__main__":
    app()
