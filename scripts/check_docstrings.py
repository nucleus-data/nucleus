"""Public-symbol docstring enforcer — governance axis H per mass-audit 2026-05-15.

Requires module-level docstrings and docstrings on PUBLIC functions/classes
in the ``ctx.*`` and ``sdk.*`` layers. A symbol is PUBLIC if its name does NOT
start with ``_``. Symbols decorated with ``@property`` that are already covered
by their class docstring are exempt.

AGENTS.md §11.3 says docstrings on public surfaces are required; this script
enforces that at CI time.

Usage
-----
    python scripts/check_docstrings.py
    python scripts/check_docstrings.py --json

Exit codes
----------
    0  all public symbols have docstrings
    1  one or more public symbols are missing docstrings
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "nucleus"

# Layers we enforce docstrings on (ctx = L4 SDK; sdk = SDK contracts/results).
_ENFORCED_LAYERS: frozenset[str] = frozenset({"ctx", "sdk"})

_SKIP = [".venv", "node_modules", ".git", "__pycache__", "site", "build", "dist"]


@dataclass
class Missing:
    file: str
    line: int
    kind: str
    name: str


def _has_docstring(body: list[ast.stmt]) -> bool:
    """Return True if the first statement in ``body`` is a string literal."""
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _scan_file(path: Path, content: str) -> list[Missing]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError:
        return []

    hits: list[Missing] = []

    # Module-level docstring.
    if not _has_docstring(tree.body):
        hits.append(Missing(file=rel, line=1, kind="module", name=rel))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if not _has_docstring(node.body):
                hits.append(Missing(file=rel, line=node.lineno, kind="function", name=node.name))

        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            if not _has_docstring(node.body):
                hits.append(Missing(file=rel, line=node.lineno, kind="class", name=node.name))

    return hits


def scan_all() -> list[Missing]:
    hits: list[Missing] = []
    for layer in _ENFORCED_LAYERS:
        layer_dir = SRC_ROOT / layer
        if not layer_dir.exists():
            continue
        for path in sorted(layer_dir.rglob("*.py")):
            if any(skip in path.parts for skip in _SKIP):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits.extend(_scan_file(path, content))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Public-symbol docstring enforcer (governance H).")
    parser.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args(argv)

    hits = scan_all()

    if args.json:
        print(
            json.dumps(
                {"missing": [h.__dict__ for h in hits], "missing_count": len(hits)}, indent=2
            )
        )
        return 1 if hits else 0

    if not hits:
        print("Docstring check: PASS (all public symbols in ctx.* and sdk.* have docstrings).")
        return 0

    print(f"Docstring check: FAIL — {len(hits)} public symbol(s) missing docstrings:\n")
    for h in hits:
        print(f"  {h.file}:{h.line}  [{h.kind}] {h.name}")
    print("\nAdd a one-line docstring minimum per AGENTS.md §11.3.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
