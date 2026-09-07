"""Every outbound request identifies itself, including ones not written yet.

This checks the source tree rather than behaviour, which is unusual and deliberate.
The risk is not that today's five adapters lose their header; it is that the sixth
never gets one, and no runtime test of the first five can fail for that.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "refugia"
# The planner talks to an Ollama on the reader's own machine, not to a public
# endpoint that has to tolerate every fork of this project.
EXEMPT = {"ask/planner.py"}


VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request", "stream", "send"}
# Any of these is a way to reach the network that the first version of this check
# did not see: it required the literal receiver `httpx` and only the verbs get and
# post, so `httpx.Client().get(url)` passed unflagged.
CLIENTS = {"Client", "AsyncClient"}
# Other ways to reach the network, which the User-Agent rule cannot police.
FETCHERS = {"urllib.request", "http.client", "socket"}


def _mentions_httpx(node: ast.AST) -> bool:
    """Whether an expression's receiver chain reaches the httpx module.

    Scoped this way rather than by verb alone, because `.get` is also how you read
    a dict and this file would otherwise flag half the project.
    """
    while isinstance(node, (ast.Attribute, ast.Call)):
        node = node.value if isinstance(node, ast.Attribute) else node.func
    return isinstance(node, ast.Name) and node.id == "httpx"


def _request_calls(path: Path):
    """Every call in one module that could reach the network through httpx."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in CLIENTS and _mentions_httpx(node.func):
            yield node
        elif node.func.attr in VERBS and _mentions_httpx(node.func):
            yield node


def _modules_making_requests():
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        if relative in EXEMPT:
            continue
        for call in _request_calls(path):
            yield pytest.param(relative, call.lineno, call, id=f"{relative}:{call.lineno}")


@pytest.mark.parametrize("module,lineno,call", list(_modules_making_requests()))
def test_an_outbound_request_names_this_project(module, lineno, call):
    """A public repo multiplies request volume; an operator should know by whom."""
    headers = [k for k in call.keywords if k.arg == "headers"]
    assert headers, f"{module}:{lineno} makes a request with no headers"
    assert "USER_AGENT" in ast.dump(
        headers[0].value
    ), f"{module}:{lineno} sets headers but not the shared USER_AGENT"


def test_the_check_is_actually_finding_call_sites():
    """A structural test that silently matches nothing passes for the wrong reason."""
    assert len(list(_modules_making_requests())) >= 5


def test_no_module_reaches_for_another_http_library():
    """The User-Agent rule is only enforceable over the one client this project uses."""
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                # By full dotted name: urllib.parse is URL handling and is used
                # deliberately, while urllib.request is a second way to fetch.
                if name in FETCHERS or name.split(".")[0] in {"requests", "aiohttp"}:
                    offenders.append(f"{path.relative_to(SRC)}: {name}")
    assert not offenders, f"reaches for an HTTP client the UA rule cannot see: {offenders}"
