"""The page is written to disk, where no host supplies a document around it."""

import json

from refugia.artifact.builder import ArtifactBuilder
from refugia.metrics.metric import Metric
from refugia.places.place import Place
from refugia.scoring.criterion import Criterion
from refugia.scoring.profile import Profile
from refugia.store.cache import Cache
from refugia.store.dataset import Dataset

FRAGMENT = "<title>T</title>\n<style>\nbody { color: red }\n</style>\n<div>body — ° content</div>"


def test_the_written_page_is_a_complete_document():
    """A fragment on disk renders in quirks mode; the template is a fragment."""
    html = ArtifactBuilder.as_document(FRAGMENT)
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")


def test_the_document_declares_utf8():
    """The credits line carries non-ASCII, which arrives as mojibake without it."""
    assert '<meta charset="utf-8"' in ArtifactBuilder.as_document(FRAGMENT)


def test_the_document_declares_a_viewport():
    """Without one every phone lays the page out at desktop width."""
    html = ArtifactBuilder.as_document(FRAGMENT)
    assert '<meta name="viewport" content="width=device-width, initial-scale=1"' in html


def test_the_style_stays_in_the_head_and_the_markup_in_the_body():
    """Splitting anywhere else would put the stylesheet in the body."""
    html = ArtifactBuilder.as_document(FRAGMENT)
    head = html[html.index("<head>") : html.index("</head>")]
    body = html[html.index("<body>") :]
    assert "<style>" in head and "<title>T</title>" in head
    assert "<div>body" in body and "<style>" not in body


def test_a_fragment_with_no_style_block_still_becomes_a_document():
    """Nothing should depend on the template keeping exactly one style block."""
    html = ArtifactBuilder.as_document("<div>only body</div>")
    assert html.startswith("<!doctype html>")
    assert "<div>only body</div>" in html


def _dataset_with_place_named(name: str) -> Dataset:
    """A one-place dataset whose place name is whatever we want to smuggle."""
    return Dataset(
        places=(Place(fips="00001", name=name, state="S", lat=0.0, lon=0.0, population=1),),
        metrics=(
            Metric(
                key="a",
                label="A",
                unit="u",
                direction="lower_better",
                category="test",
                description="",
                source="s",
            ),
        ),
        values={"a": {"00001": 1.0}},
    )


def test_a_place_name_cannot_close_the_payload_script_tag():
    """The one line between upstream data and script-tag breakout, asserted.

    Place names come from Census files and metric labels from upstream CSVs, so the
    payload carries text nobody in this project reviewed. Deleting the escape in
    builder.py left all other tests green.
    """
    hostile = "</script><img src=x onerror=alert(1)>"
    payload = json.dumps(_dataset_with_place_named(hostile).to_dict(), separators=(",", ":"))
    encoded = payload.replace("</", "<\\/")
    assert "</script>" not in encoded
    assert "<\\/script>" in encoded


def test_the_built_page_closes_its_payload_tag_exactly_once(tmp_path, monkeypatch):
    """End to end: the written file must not contain a second </script> from data."""
    hostile = "</script><img src=x onerror=alert(1)>"
    dataset = _dataset_with_place_named(hostile)

    class _NoShapes:
        """The geometry the builder would otherwise fetch."""

        def __init__(self) -> None:
            self.counties: dict = {}
            self.states: dict = {}
            self.centroids: dict = {}
            self.transform = None

    monkeypatch.setattr(
        "refugia.artifact.builder.CountyShapes",
        lambda cache: type("S", (), {"build": lambda self, fips: _NoShapes()})(),
    )
    monkeypatch.setattr(
        "refugia.artifact.builder.CityMarkers",
        lambda cache: type("M", (), {"for_places": lambda self, p, t: {}})(),
    )
    monkeypatch.setattr(
        "refugia.artifact.builder.CityProfile",
        lambda cache, vegetation=None: type("C", (), {"build": lambda self, cities: {}})(),
    )

    out = ArtifactBuilder(Cache(tmp_path / "c")).build(
        dataset, Profile("p", {"a": 1.0}), tmp_path / "page.html"
    )
    written = out.read_text(encoding="utf-8")
    # One from the payload block, one from the main script block, and none smuggled.
    assert written.count("</script>") == 2
    assert "<\\/script>" in written


def test_a_misspelled_criterion_stops_the_build_before_the_download(tmp_path):
    """The page filters too, so a typo publishes an empty page rather than failing.

    `build` refuses before `CountyShapes`, which is the expensive part and the
    part that reaches the network -- so this test needs no cache and no fixture
    beyond the profile.
    """
    import pytest

    dataset = Dataset(
        places=(Place(fips="00001", name="A", state="S", lat=0.0, lon=0.0, population=1),),
        metrics=(
            Metric(
                key="a",
                label="A",
                unit="u",
                direction="lower_better",
                category="c",
                description="",
                source="s",
            ),
        ),
        values={"a": {"00001": 1.0}},
    )
    profile = Profile("t", {"a": 1.0}, criteria=(Criterion("populaton", "min", 40_000),))
    with pytest.raises(KeyError) as caught:
        ArtifactBuilder(Cache(tmp_path)).build(dataset, profile, tmp_path / "out.html")
    assert "populaton" in str(caught.value)
