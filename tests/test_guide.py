"""The guide describes the code, so the code has to be able to fail the guide.

Prose is the one part of a project nothing checks. This repository has already shipped
a Known-gaps line that survived an edit to the bullet directly above it, and a
DATA_SOURCES paragraph asserting a metric could not carry its own citation for
several commits after it could. Both were in files somebody could at least grep.

So: every repository path the guide names must exist, every metric key it names must
be registered, and every link between its pages must resolve.
"""

import json
import re
from pathlib import Path

import pytest

from refugia.places.place import Place
from refugia.places.registry import UNIVERSES
from refugia.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
SRC_PAGE = ROOT / "src" / "refugia" / "artifact" / "template.html"
GUIDE = ROOT / "docs" / "guide"
PAGES = sorted(GUIDE.glob("*.md"))
# Every document that makes claims about this repository, not just the guide. The
# audit found wrong statements in CONTRIBUTING, SECURITY, DATA_SOURCES and CLAUDE.md,
# all of which sat outside what this file was reading.
DOCS = [
    *PAGES,
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CLAUDE.md",
    ROOT / "DATA_SOURCES.md",
    ROOT / "SECURITY.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs" / "data" / "README.md",
]

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
    # A criterion may name a Place attribute, so those are vocabulary too and are
    # read from the class rather than listed.
    place_fields = {f for f in dir(Place) if not f.startswith("_")}
    # The ledger's envelope and the page's tool names are vocabulary too, read from
    # the file and the template so neither can drift out from under this check.
    # Every key the ledger uses, not only the first row's: review_at appears on
    # parked rows alone.
    ledger = {
        k
        for line in (ROOT / "docs/data/findings.jsonl").read_text(encoding="utf-8").splitlines()
        for k in json.loads(line)
    }
    # And anything that appears verbatim in the source. A doc naming
    # `raise_for_status` or `weighted_deficit` is naming a real thing; the check is
    # for invented vocabulary, and a token the code contains is not invented.
    source = " ".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*")
        if path.suffix in {".py", ".html", ".json"}
    )
    # A doc may point at the test that enforces what it claims, which is the
    # strongest form the claim can take. Only names that are actually defined
    # count, so a guide citing a test that was renamed or deleted fails here --
    # narrowed to `def test_...` rather than all of `tests/`, or the guard would
    # accept every local variable in the suite as vocabulary.
    test_names = set(
        re.findall(
            r"^def (test_\w+)",
            "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").rglob("*.py")),
            re.M,
        )
    )
    field_names = (
        set(UNIVERSES)
        | place_fields
        | set(ledger)
        | test_names
        | {
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
    )
    unknown = set()
    for page in DOCS:
        for token in re.findall(
            r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`", page.read_text(encoding="utf-8")
        ):
            if token in field_names or token in keys or token in source:
                continue
            unknown.add(token)
    assert not unknown, (
        "the guide names snake_case tokens that are neither metric keys nor known "
        f"spec/profile fields: {sorted(unknown)}"
    )


def test_the_spec_the_guide_quotes_in_full_is_the_shipped_one():
    """adding-a-spec.md embeds a real file, so it can silently stop being one."""
    quoted = re.search(
        r"`src/refugia/specs/life_expectancy\.json`, in full:\s*```json\n(.*?)```",
        (GUIDE / "adding-a-spec.md").read_text(encoding="utf-8"),
        re.S,
    )
    assert quoted, "the guide no longer quotes the spec where this test expects it"
    shipped = json.loads(
        (ROOT / "src" / "refugia" / "specs" / "life_expectancy.json").read_text(encoding="utf-8")
    )
    assert json.loads(quoted.group(1)) == shipped


def test_the_page_names_no_metric_of_its_own():
    """`adding-a-spec.md` says a registered metric appears in the page without a
    page change. That was untrue for a long time -- the maximum-home-value box was
    written into the template nine times over -- and nothing could tell, because
    the claim lived only in prose. This is the claim as a test: the template may
    not contain any registered metric's key, so the next special case fails here
    rather than in a sentence nobody re-reads.
    """
    from refugia.workspace import Workspace

    keys = sorted(m.key for m in Workspace(ROOT).build_registry().metrics)
    assert keys, "no metrics registered; the check would pass vacuously"
    template = (ROOT / "src" / "refugia" / "artifact" / "template.html").read_text(encoding="utf-8")
    named = {
        key: [n for n, line in enumerate(template.splitlines(), 1) if key in line] for key in keys
    }
    assert not {
        k: v for k, v in named.items() if v
    }, f"template.html names metrics: {({k: v for k, v in named.items() if v})}"
