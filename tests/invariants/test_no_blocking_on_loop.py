"""SPEC 4.4 / 23.6: nothing blocks the event loop.

A slow AdvancedMD reply MUST NOT delay /health. The real assertion needs
the FastAPI app and the sender loop, which P2 wires; until then the test
is xfail with a reason, and P2 removes the marker rather than rewriting
the test.

The static half below is live now: it fails today if anyone puts a
`time.sleep` or a blocking `requests`-style post into connector/ or into
a copied handler.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Calls that park the whole event loop when made from async code.
BLOCKING_CALLS = {("time", "sleep"), ("os", "system"), ("subprocess", "run"),
                  ("subprocess", "check_output"), ("subprocess", "call")}

SKIP_DIRS = {"__pycache__", ".venv", "tests"}


def _async_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            yield node


def _calls_in(node: ast.AST):
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call):
            yield inner


def _nested_async_defs(node: ast.AST) -> set[int]:
    return {id(n) for n in ast.walk(node) if isinstance(n, ast.AsyncFunctionDef)} - {id(node)}


def python_files() -> list[Path]:
    out: list[Path] = []
    for directory in ("connector", "domains"):
        root = REPO_ROOT / directory
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if SKIP_DIRS.intersection(path.parts):
                continue
            out.append(path)
    return out


@pytest.mark.parametrize(
    "path", python_files(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_no_blocking_sleep_inside_async_code(path: Path):
    """Blocking sleeps/subprocess calls inside `async def` park the loop.

    SPEC 15 also forbids handlers from sleeping at all: pacing belongs to
    the sender loop. Anything genuinely blocking must be wrapped in
    asyncio.to_thread (SPEC 4.4).
    """
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"),
                     filename=str(path))
    rel = path.relative_to(REPO_ROOT)
    for func in _async_functions(tree):
        for call in _calls_in(func):
            target = call.func
            if not isinstance(target, ast.Attribute):
                continue
            owner = target.value
            if not isinstance(owner, ast.Name):
                continue
            if (owner.id, target.attr) in BLOCKING_CALLS:
                pytest.fail(
                    f"{rel}: {owner.id}.{target.attr}() inside async code blocks "
                    "the event loop (SPEC 4.4); wrap it in asyncio.to_thread"
                )


@pytest.mark.xfail(
    reason="P2 wires connector/app.py and the sender loop; this becomes a real "
           "end-to-end assertion then and the marker is removed.",
    strict=False,
)
def test_slow_amd_reply_does_not_delay_health():
    """SPEC 4.4: with an AMD reply parked for seconds, GET /health still
    answers promptly.

    Shape of the eventual test, so P2 fills it in rather than inventing
    one: start the app with a sender whose send() awaits an event that the
    test never sets, submit a tool call, then poll GET /health and assert
    it returns in well under the AMD post timeout.
    """
    from connector import app  # noqa: F401  (does not exist until P2)

    raise AssertionError("P2 implements this")
