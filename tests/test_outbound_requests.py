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


def _request_calls(path: Path):
    """Every httpx.get / httpx.post call in one module, as AST nodes."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        target = node.func
        if target.attr in ("get", "post") and getattr(target.value, "id", None) == "httpx":
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
