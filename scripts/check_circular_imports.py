"""Circular import detector — governance axis H per mass-audit 2026-05-15.

Builds a directed import graph of all ``nucleus.*`` modules under ``src/``
and performs a depth-first cycle detection. Any cycle (e.g. ``ctx.sql``
importing ``coordination.sql_resolver`` AND ``coordination.sql_resolver``
importing ``ctx.sql``) is reported as a FAIL.

Only **intra-nucleus** import edges are included; external library imports
(dagster, duckdb, polars, …) are ignored to keep the graph manageable.

Lazy imports (inside ``if TYPE_CHECKING:`` blocks) are excluded from the
graph since they are not runtime dependencies.

Usage
-----
    python scripts/check_circular_imports.py
    python scripts/check_circular_imports.py --json

Exit codes
----------
    0  no circular imports found
    1  circular import cycle detected
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"

_SKIP = [".venv", "node_modules", ".git", "__pycache__", "site", "build", "dist"]


def _module_name(path: Path) -> str:
    """Convert an absolute path under src/ to a dotted module name."""
    rel = path.relative_to(SRC_ROOT)
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _is_type_checking_block(node: ast.AST) -> bool:
    """Return True if node is ``if TYPE_CHECKING:`` or ``if typing.TYPE_CHECKING:``."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        return True
    return False


def _extract_nucleus_imports(path: Path, content: str) -> list[str]:
    """Return all ``nucleus.*`` module paths imported at MODULE LEVEL only.

    Lazy imports (inside function bodies, methods, or if-blocks) are excluded
    because they are resolved at call-time and cannot cause import-time cycles.
    Only ``if TYPE_CHECKING:`` blocks are also excluded (type stubs only).
    """
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError:
        return []

    results: list[str] = []
    current_pkg = ".".join(_module_name(path).split(".")[:-1])

    # Only iterate top-level statements (not nested inside functions/classes/ifs).
    for node in tree.body:
        # Exclude TYPE_CHECKING guards.
        if _is_type_checking_block(node):
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("nucleus."):
                    results.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level > 0:
                parts = current_pkg.split(".")
                levels = node.level
                base_parts = parts[: max(0, len(parts) - levels + 1)]
                if mod:
                    base_parts.extend(mod.split("."))
                mod = ".".join(base_parts)
            if mod.startswith("nucleus."):
                results.append(mod)
    return results


def build_graph() -> dict[str, list[str]]:
    """Build an adjacency list {module: [imported_nucleus_modules]}."""
    graph: dict[str, list[str]] = defaultdict(list)
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if any(skip in path.parts for skip in _SKIP):
            continue
        mod = _module_name(path)
        if not mod.startswith("nucleus."):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for imported in _extract_nucleus_imports(path, content):
            if imported != mod:
                graph[mod].append(imported)
    return dict(graph)


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """DFS-based cycle detection; returns a list of cycles (each as a path list)."""
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle; extract the cycle from path.
                idx = path.index(neighbor)
                cycle = path[idx:] + [neighbor]
                cycles.append(cycle)
        path.pop()
        rec_stack.discard(node)

    all_nodes = set(graph.keys()) | {n for deps in graph.values() for n in deps}
    for node in sorted(all_nodes):
        if node not in visited:
            _dfs(node, [])

    # Deduplicate cycles by their frozenset of edges.
    seen: set[frozenset[str]] = set()
    unique: list[list[str]] = []
    for cycle in cycles:
        key = frozenset(zip(cycle, cycle[1:]))
        if key not in seen:
            seen.add(key)
            unique.append(cycle)
    return unique


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circular import detector (governance H).")
    parser.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args(argv)

    graph = build_graph()
    cycles = find_cycles(graph)

    if args.json:
        print(json.dumps({"cycles": cycles, "cycle_count": len(cycles)}, indent=2))
        return 1 if cycles else 0

    if not cycles:
        print("Circular import check: PASS (no cycles detected in nucleus.* imports).")
        return 0

    print(f"Circular import check: FAIL — {len(cycles)} cycle(s) detected:\n")
    for i, cycle in enumerate(cycles, 1):
        print(f"  Cycle {i}: {' -> '.join(cycle)}")
    print("\nBreak cycles by moving shared code into a lower layer or using lazy imports.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
