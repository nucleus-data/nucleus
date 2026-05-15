"""Lazy-import enforcement for the Nucleus CLI entry point.

Scans ``src/nucleus/cli/main.py`` (and the modules it imports at module
top, transitively) for banned heavy library imports at module-level —
i.e. outside any function/method/class body. A module-level
``import litellm`` (or ``from litellm import ...``) inside ``cli/main.py``
or any module reachable from its top-level import set fails the check.

Why
---
``nucleus --version`` MUST stay below 500 ms cold per
``docs/research/performance_reliability_targets.md`` §2.1 + §10 #4.
Heavy libraries (``litellm`` ~0.5 s, ``dlt`` ~0.3 s, ``dagster`` ~0.4 s,
``pyiceberg`` ~0.2 s, ``polars`` ~0.2 s, ``duckdb`` ~0.2 s, ``s3fs``
~0.1 s, ``psycopg2`` ~0.1 s, ``fastapi`` ~0.15 s, ``uvicorn`` ~0.1 s)
must therefore live inside the command handler bodies that need them
(see :class:`scripts.benchmark_cli_cold_boot` for the empirical check).

Banned set
----------
Per the founder directive 2026-05-15 perf hardening pass + Worker B2
audit. Every entry below is justified inline:

* ``litellm`` — ``nucleus chat`` only; ~0.5 s import cost
* ``dlt`` — ``nucleus ingest`` only; ~0.3 s
* ``dagster`` — ``nucleus run`` (via AMA) only; ~0.4 s
* ``pyiceberg`` — ``nucleus run/query/snapshot`` only; ~0.2 s
* ``polars`` — ``nucleus run/query`` only; ~0.2 s
* ``duckdb`` — ``nucleus run/query/up`` only; ~0.2 s
* ``s3fs`` — ``nucleus ingest`` (S3/GCS sources) only; ~0.1 s
* ``psycopg2`` / ``psycopg`` — ``nucleus ingest`` (Postgres) only; ~0.1 s
* ``fastapi`` — ``nucleus workbench`` only; ~0.15 s
* ``uvicorn`` — ``nucleus workbench`` only; ~0.1 s
* ``sqlalchemy`` — ``nucleus ingest`` (SQL sources via dlt/copy_from) only; ~0.2 s
* ``croniter`` — ``nucleus schedule`` (mini-scheduler daemon) only; ~0.05 s

Allowed at module top
---------------------
``typer``, ``click``, ``rich``, ``yaml``, stdlib, and intra-package
``nucleus.*`` imports that themselves stay light. ``nucleus.errors`` is
fine because every command handler needs it for translation.

Usage
-----
    python scripts/check_lazy_imports.py
    python scripts/check_lazy_imports.py --json
    python scripts/check_lazy_imports.py --target src/nucleus/cli/main.py

Exit codes
----------
    0  No banned top-level imports found in the scanned set
    1  Banned import detected at module top-level
    2  Invocation error (file missing, parse failure, etc.)

Docs:
    https://docs.python.org/3.11/library/ast.html
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"

# Default scan target. Worker B2 owned the CLI entry; we scan from there
# and follow nucleus.* imports transitively up to a small fan-out so the
# script catches "innocent-looking transitive eager import" regressions.
_DEFAULT_TARGET = SRC_ROOT / "nucleus" / "cli" / "main.py"

# See module docstring for per-module rationale.
BANNED_TOP_LEVEL: frozenset[str] = frozenset(
    {
        "litellm",
        "dlt",
        "dagster",
        "pyiceberg",
        "polars",
        "duckdb",
        "s3fs",
        "psycopg2",
        "psycopg",
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "croniter",
    }
)

# Modules that are allowed AT module top because the CLI parser cannot
# function without them. Listed for documentation; never used to grant
# exemptions on banned set.
_ALLOWED_TOP_LEVEL_DOC = (
    "typer (CLI parsing)",
    "click (typer dependency)",
    "rich (typer dependency, ~50ms)",
    "yaml (PyYAML, ~30ms — used by every command for project config)",
    "stdlib (instant)",
    "nucleus.errors (small, every command needs translation)",
    "nucleus.cli._compose (subprocess wrappers; small)",
)


@dataclass
class Violation:
    """One banned-import-at-module-top finding."""

    file: Path
    lineno: int
    module: str
    statement: str

    def render(self) -> str:
        rel = self.file.relative_to(REPO_ROOT)
        return f"{rel}:{self.lineno}  {self.statement}  (banned top-level: {self.module!r})"


@dataclass
class ScanResult:
    """Aggregate scan outcome — files visited + violations found."""

    files_visited: list[Path] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)


def _is_type_checking_block(node: ast.AST) -> bool:
    """Return True if ``node`` is an ``if TYPE_CHECKING:`` guard.

    PEP 484 type hints inside such blocks never execute at runtime, so
    they are safe even for banned modules.
    """
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
        return True
    return False


def _top_level_statements(tree: ast.Module) -> list[ast.stmt]:
    """Yield only statements that execute at module-import time.

    Bodies of ``def``, ``async def``, ``class``, and ``if TYPE_CHECKING``
    blocks are intentionally excluded — they don't contribute to import-
    time module loading. Other ``if`` branches DO execute at import time
    so we descend into them.
    """
    flat: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if _is_type_checking_block(node):
            continue
        if isinstance(node, ast.If) and not _is_type_checking_block(node):
            # Other ``if`` branches (e.g. ``if sys.version_info ...:``) execute
            # at import. Recurse so we don't miss banned imports inside them.
            flat.append(node)
            for inner in node.body + node.orelse:
                flat.append(inner)
            continue
        flat.append(node)
    return flat


def _root_module(name: str) -> str:
    """Return the top-level module name, e.g. ``litellm.utils`` -> ``litellm``."""
    return name.split(".", 1)[0]


def _scan_file_violations(file: Path) -> list[Violation]:
    """Return banned top-level imports inside ``file``.

    Imports inside function/method bodies (== lazy) are not flagged.
    """
    if not file.is_file():
        return []
    source = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file))
    except SyntaxError as exc:
        return [
            Violation(
                file=file,
                lineno=exc.lineno or 0,
                module="<parse-error>",
                statement=f"# parse failed: {exc.msg}",
            )
        ]
    source_lines = source.splitlines()
    violations: list[Violation] = []
    for node in _top_level_statements(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _root_module(alias.name)
                if root in BANNED_TOP_LEVEL:
                    violations.append(
                        Violation(
                            file=file,
                            lineno=node.lineno,
                            module=root,
                            statement=source_lines[node.lineno - 1].strip(),
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:  # ``from . import x`` — relative
                continue
            root = _root_module(node.module)
            if root in BANNED_TOP_LEVEL:
                violations.append(
                    Violation(
                        file=file,
                        lineno=node.lineno,
                        module=root,
                        statement=source_lines[node.lineno - 1].strip(),
                    )
                )
    return violations


def _intra_nucleus_top_level_deps(file: Path) -> list[Path]:
    """Return paths of intra-``nucleus.*`` modules imported at file's top.

    Walks the tree only one statement deep (no function bodies, no
    TYPE_CHECKING). Returns absolute paths under ``src/`` for each
    resolvable module *plus every parent package's ``__init__.py``*
    along the dotted path — Python loads every parent package when
    resolving ``from nucleus.workbench.cli import app``, so we must
    scan those ``__init__.py`` files too (this is exactly how the
    workbench eager-fastapi import was first detected).
    """
    if not file.is_file():
        return []
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    except SyntaxError:
        return []
    deps: list[Path] = []

    def _enqueue_with_parents(dotted: str) -> None:
        """Add ``dotted`` plus every nucleus.* ancestor's __init__.py."""
        if not dotted.startswith("nucleus"):
            return
        parts = dotted.split(".")
        for i in range(1, len(parts) + 1):
            deps.extend(_resolve_nucleus_module(".".join(parts[:i])))

    for node in _top_level_statements(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _enqueue_with_parents(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            module_name = node.module
            _enqueue_with_parents(module_name)
            if module_name.startswith("nucleus"):
                for alias in node.names:
                    _enqueue_with_parents(f"{module_name}.{alias.name}")
    return deps


def _resolve_nucleus_module(name: str) -> list[Path]:
    """Return [<file>] if ``name`` resolves to a ``nucleus.*`` source file.

    Empty list when ``name`` is external, a stdlib module, or unresolvable.
    Both ``nucleus.foo`` (single .py) and ``nucleus.foo.__init__`` packages
    resolve correctly.
    """
    if not name.startswith("nucleus"):
        return []
    parts = name.split(".")
    candidate_module = SRC_ROOT.joinpath(*parts).with_suffix(".py")
    candidate_pkg = SRC_ROOT.joinpath(*parts) / "__init__.py"
    out: list[Path] = []
    if candidate_module.is_file():
        out.append(candidate_module)
    if candidate_pkg.is_file():
        out.append(candidate_pkg)
    return out


def scan(target: Path, *, max_depth: int = 4) -> ScanResult:
    """Scan ``target`` plus transitively reachable ``nucleus.*`` modules.

    Depth-limited to keep the scan fast and deterministic; 4 hops covers
    the cli.main -> commands.* -> intelligence/coordination -> leaves
    chain we care about today.
    """
    result = ScanResult()
    visited: set[Path] = set()
    queue: list[tuple[Path, int]] = [(target.resolve(), 0)]
    while queue:
        file, depth = queue.pop(0)
        if file in visited:
            continue
        visited.add(file)
        result.files_visited.append(file)
        result.violations.extend(_scan_file_violations(file))
        if depth >= max_depth:
            continue
        for dep in _intra_nucleus_top_level_deps(file):
            if dep not in visited:
                queue.append((dep, depth + 1))
    return result


def _render_human(result: ScanResult, target: Path) -> str:
    rel = target.relative_to(REPO_ROOT) if target.is_absolute() else target
    lines = [
        "=" * 72,
        " Lazy-import enforcement for Nucleus CLI",
        f" Target:        {rel}",
        f" Files scanned: {len(result.files_visited)}",
        f" Banned set:    {sorted(BANNED_TOP_LEVEL)}",
        "=" * 72,
    ]
    if not result.violations:
        lines.append("PASS — no banned top-level imports in the scanned module set.")
        lines.append("")
        lines.append("Allowed at module top (per docstring):")
        for note in _ALLOWED_TOP_LEVEL_DOC:
            lines.append(f"  - {note}")
        return "\n".join(lines)
    lines.append(f"FAIL — {len(result.violations)} banned top-level import(s) found:")
    lines.append("")
    for v in result.violations:
        lines.append(f"  {v.render()}")
    lines.append("")
    lines.append(
        "Fix: move the import inside the command handler that needs it. Example:\n"
        "    @app.command()\n"
        "    def chat(...):\n"
        "        import litellm  # Docs: https://docs.litellm.ai/\n"
        "        ..."
    )
    return "\n".join(lines)


def main() -> int:
    """Entry point. Exit 0 if clean, 1 on violations, 2 on invocation errors."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=_DEFAULT_TARGET,
        help=(
            "File to scan as the CLI entry point. Defaults to "
            "src/nucleus/cli/main.py."
        ),
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Transitive nucleus.* import follow depth (default: 4).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the human-readable report.",
    )
    args = parser.parse_args()

    target: Path = args.target.resolve()
    if not target.is_file():
        sys.stderr.write(f"error: target file not found: {target}\n")
        return 2

    result = scan(target, max_depth=args.max_depth)

    if args.json:
        payload = {
            "_schema_version": 1,
            "target": str(target.relative_to(REPO_ROOT)),
            "banned": sorted(BANNED_TOP_LEVEL),
            "files_scanned": [str(p.relative_to(REPO_ROOT)) for p in result.files_visited],
            "violations": [
                {
                    "file": str(v.file.relative_to(REPO_ROOT)),
                    "lineno": v.lineno,
                    "module": v.module,
                    "statement": v.statement,
                }
                for v in result.violations
            ],
            "verdict": "PASS" if not result.violations else "FAIL",
        }
        print(json.dumps(payload, indent=2))
    else:
        print(_render_human(result, target))

    return 0 if not result.violations else 1


if __name__ == "__main__":
    sys.exit(main())
