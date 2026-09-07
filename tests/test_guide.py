"""The guide describes the code, so the code has to be able to fail the guide.

Prose is the one part of a project nothing checks. This repository has already shipped
a Known-gaps line that survived an edit to the bullet directly above it, and a
DATA_SOURCES paragraph asserting a metric could not carry its own citation for
several commits after it could. Both were in files somebody could at least grep.

So: every repository path the guide names must exist, every metric key it names must
be registered, and every link between its pages must resolve.
"""

import re
from pathlib import Path

import pytest

from refugia.places.registry import UNIVERSES
from refugia.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "guide"
PAGES = sorted(GUIDE.glob("*.md"))
DOCS = [*PAGES, ROOT / "README.md"]

# A backticked token is a path when it looks like one: a known top-level directory,
# or a bare filename with an extension this project actually keeps at its root.
PATHLIKE = re.compile(
    r"`((?:src|tests|docs|profiles|specs|\.github)/[\w./*-]+|[A-Z_]+\.md|pyproject\.toml|uv\.lock|devenv\.nix)`"
)
LINK = re.compile(r"\[[^\]]+\]\((?!https?:)([^)#]+)(#[^)]*)?\)")


def test_the_guide_exists_and_is_indexed():
    """A test that silently matches nothing passes for the wrong reason."""
    assert len(PAGES) >= 6
    index = (GUIDE / "README.md").read_text(encoding="utf-8")
    for page in PAGES:
        if page.name != "README.md":
            assert page.name in index, f"{page.name} is not linked from the guide index"


@pytest.mark.parametrize("doc", DOCS, ids=[d.name for d in DOCS])
def test_every_path_the_docs_name_exists(doc):
    """A guide naming a file that moved is worse than one that says nothing."""
    missing = []
    for match in PATHLIKE.finditer(doc.read_text(encoding="utf-8")):
        named = match.group(1)
        if "*" in named:  # a glob, e.g. src/refugia/specs/*.json
            if not list(ROOT.glob(named)):
                missing.append(named)
        elif not (ROOT / named).exists():
            missing.append(named)
    assert not missing, f"{doc.name} names paths that do not exist: {missing}"


@pytest.mark.parametrize("doc", DOCS, ids=[d.name for d in DOCS])
def test_every_link_between_pages_resolves(doc):
    """Relative links rot silently, and nobody clicks every one of them."""
    broken = [
        target
        for match in LINK.finditer(doc.read_text(encoding="utf-8"))
        if not (doc.parent / (target := match.group(1))).resolve().exists()
    ]
    assert not broken, f"{doc.name} links to missing files: {broken}"


def test_every_metric_key_the_guide_names_is_registered():
    """The vocabulary is printed by `refugia metrics`; prose must not invent one."""
    keys = {m.key for m in Workspace(ROOT).build_registry().metrics}
    # Only look where a key would actually be claimed: a backticked snake_case token
    # that is not a field name, a command, or a Python attribute.
    # Universe names come from the code, so renaming one fails this rather than
    # quietly leaving the guide naming something that no longer exists.
    field_names = set(UNIVERSES) | {
        "key",
        "label",
        "unit",
        "direction",
        "category",
        "description",
        "source",
        "url",
        "format",
        "fips_column",
        "value_column",
        "aggregate",
        "where",
        "scale",
        "sheet",
        "records_path",
        "citation",
        "terms_url",
        "min_coverage",
        "home_fips",
        "normalization",
        "higher_better",
        "lower_better",
        "not_in",
        "also_transient",
        "cov_fail_under",
        "blank_issues_enabled",
    }
    unknown = set()
    for page in PAGES:
        for token in re.findall(
            r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`", page.read_text(encoding="utf-8")
        ):
            if token in field_names or token in keys:
                continue
            unknown.add(token)
    assert not unknown, (
        "the guide names snake_case tokens that are neither metric keys nor known "
        f"spec/profile fields: {sorted(unknown)}"
    )
