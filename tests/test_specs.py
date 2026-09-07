"""The shipped specs are six of the twenty-one metrics and nothing validated them.

A spec is data, so nothing here catches a typo at import time. Without these, a
misspelled field or a scheme that slipped past review surfaces as a traceback on
somebody's first `fetch`, an hour into a download.
"""

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from refugia.metrics.sources.declarative import DeclarativeSource
from refugia.store.cache import Cache
from refugia.workspace import Workspace

SPEC_DIR = Path(__file__).resolve().parents[1] / "specs"
SPECS = sorted(SPEC_DIR.glob("*.json"))


def test_there_are_specs_to_check():
    """A parametrised suite over an empty glob passes by finding nothing."""
    assert SPECS, f"no specs found under {SPEC_DIR}"


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_every_shipped_spec_loads(spec, tmp_path):
    """Construction runs the validator, which is where a bad spec should die."""
    source = DeclarativeSource.from_file(spec, Cache(tmp_path / spec.stem))
    assert source.metrics[0].key == spec.stem or source.metrics[0].key


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_a_spec_is_named_after_the_metric_it_declares(spec, tmp_path):
    """Otherwise `--only <key>` and the file on disk disagree about what to edit."""
    source = DeclarativeSource.from_file(spec, Cache(tmp_path / spec.stem))
    assert source.metrics[0].key == spec.stem


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_a_spec_declaring_terms_gives_a_reachable_url(spec):
    """A terms link is the reader's route to what they may do with the page."""
    terms = json.loads(spec.read_text(encoding="utf-8")).get("terms_url", "")
    if terms:
        assert urlparse(terms).scheme == "https", terms


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_a_spec_citing_a_source_also_links_its_terms(spec):
    """A citation without the terms behind it tells a reader half of what they need."""
    payload = json.loads(spec.read_text(encoding="utf-8"))
    if payload.get("citation"):
        assert payload.get("terms_url"), f"{spec.name} cites a source but links no terms"


def test_the_registry_accepts_every_spec_beside_the_adapters():
    """Duplicate keys raise at registration, which is the composition root's job."""
    registry = Workspace(SPEC_DIR.parent).build_registry()
    keys = [m.key for m in registry.metrics]
    assert len(keys) == len(set(keys))
    assert set(s.stem for s in SPECS) <= set(keys)


def test_the_registry_holds_every_metric_the_project_ships():
    """A source silently dropping out is the failure this is here to catch."""
    registry = Workspace(SPEC_DIR.parent).build_registry()
    assert len(registry.metrics) == 21
