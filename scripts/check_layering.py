"""Layer-direction check — ``docs/conventions/engineering.md`` §3.1.

Verifies that imports follow the strict directional rule:

    Layer N may import from layer N or LOWER, never higher.

Layer depth (lowest to highest)::

    physics  →  engines  →  coordination  →  intelligence  →  {ctx, cli, workbench}

Layers at the **same depth** are peers and may import freely from each
other. Per ``docs/specs/nucleus_architecture_v4.1.md`` §8.1, ``ctx`` (SDK),
``cli`` (operator surface), and ``workbench`` (GUI surface) are all
Layer 4 (Experience) surfaces, not stacked sub-layers — see ADR-040.

If a file under ``src/nucleus/<layer>/...`` imports from a HIGHER-depth
layer (e.g. ``physics/`` importing from ``ctx/``), the build fails.

Special rules
-------------
- ``_internal/`` may be imported from any layer (it's our shared toolbox).
- ``_internal/`` may NOT import from any layer (it's at the bottom).
- Cross-engine imports forbidden: ``engines/duckdb_engine.py`` may not
  import ``engines/polars_engine.py`` (engineering.md §3.2).

Usage
-----
    python scripts/check_layering.py
    python scripts/check_layering.py --json

Exit codes
----------
    0  layering respected (or src not yet present)
    1  violation detected

Reading guide
-------------
- We use ``ast`` (not regex) so we never miscount comments or strings.
- The walker classifies each file's "home" layer based on its directory.
- For each import, we look up the imported module's layer and compare
  using ``LAYER_DEPTH`` (peer layers share a depth).
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "nucleus"

# Layer depth controls allowed import direction.
# Lower number = lower in the stack (foundational).
# Imports may flow within or down the stack, never up.
# Layers at the SAME depth are peers and may import freely from each
# other (e.g. ``cli ↔ workbench`` per ADR-040 — both Experience-layer
# surfaces per docs/specs/nucleus_architecture_v4.1.md §8.1).
LAYER_DEPTH: dict[str, int] = {
    "_internal": -1,  # shared toolbox; sits below all real layers
    "physics": 0,  # L0
    "engines": 1,  # L1
    "coordination": 2,  # L2
    "intelligence": 3,  # L3
    "ctx": 4,  # L4 — SDK surface
    "cli": 4,  # L4 — operator surface (peer of ctx + workbench)
    "workbench": 4,  # L4 — GUI surface (peer of ctx + cli; ADR-016 + ADR-040)
}
# Membership list (preserves declaration order for deterministic output).
LAYERS: list[str] = list(LAYER_DEPTH.keys())


@dataclass
class Violation:
    file: str
    line: int
    importer_layer: str
    imported_module: str
    imported_layer: str
    reason: str


def _file_layer(file: Path) -> str | None:
    """Determine which layer a source file lives in, or None if outside src/nucleus."""
    try:
        rel = file.relative_to(SRC_ROOT)
    except ValueError:
        return None
    head = rel.parts[0] if rel.parts else ""
    if head in LAYERS:
        return head
    return None


def _module_layer(module: str) -> str | None:
    """For an imported ``nucleus.X.Y`` module, return ``X`` if X is a layer."""
    if not module.startswith("nucleus."):
        return None
    parts = module.split(".")
    if len(parts) < 2:
        return None
    candidate = parts[1]
    return candidate if candidate in LAYERS else None


def _resolve_relative_import(node: ast.ImportFrom, current_file: Path) -> str | None:
    """Resolve ``from . import X`` to a dotted ``nucleus.layer.X`` path."""
    if node.level == 0:
        return node.module
    try:
        rel = current_file.relative_to(SRC_ROOT.parent)  # relative to src/
    except ValueError:
        return None
    parts = list(rel.with_suffix("").parts)
    parts.pop()  # drop filename component
    # Walk up `level` packages.
    if node.level > len(parts):
        return None
    for _ in range(node.level - 1):
        parts.pop()
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts) or None


def _imported_modules_for_node(node: ast.AST, file: Path) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom):
        mod = _resolve_relative_import(node, file) or node.module or ""
        return [mod] if mod else []
    return []


def _violations_for_imported_module(
    *,
    rel_str: str,
    node: ast.AST,
    mod: str,
    importer_layer: str,
    importer_depth: int,
    file: Path,
) -> list[Violation]:
    imported_layer = _module_layer(mod)
    if imported_layer is None:
        return []

    # Rule 1: _internal is below all real layers; it cannot import from any layer.
    if importer_layer == "_internal" and imported_layer != "_internal":
        return [
            Violation(
                file=rel_str,
                line=node.lineno,
                importer_layer=importer_layer,
                imported_module=mod,
                imported_layer=imported_layer,
                reason="_internal/ may not import from any layer",
            )
        ]

    out: list[Violation] = []

    # Rule 2: no upward imports. Peers at the same depth may import freely
    # from each other (ADR-040 — ``cli ↔ workbench`` Experience-layer peers).
    imported_depth = LAYER_DEPTH[imported_layer]
    if imported_depth > importer_depth:
        out.append(
            Violation(
                file=rel_str,
                line=node.lineno,
                importer_layer=importer_layer,
                imported_module=mod,
                imported_layer=imported_layer,
                reason=f"upward import: {importer_layer} -> {imported_layer}",
            )
        )

    # Rule 3: cross-engine imports forbidden.
    if importer_layer == "engines" and imported_layer == "engines" and mod != "nucleus.engines":
        # Same-layer is fine, but engine adapters shouldn't reach into each other.
        # If the module looks like a sibling engine adapter, flag it.
        parts = mod.split(".")
        if len(parts) >= 3:
            importer_engine_dir = (
                file.relative_to(SRC_ROOT).parts[1]
                if len(file.relative_to(SRC_ROOT).parts) > 1
                else ""
            )
            imported_engine_dir = parts[2]
            if (
                importer_engine_dir
                and imported_engine_dir
                and importer_engine_dir != imported_engine_dir
            ):
                out.append(
                    Violation(
                        file=rel_str,
                        line=node.lineno,
                        importer_layer=importer_layer,
                        imported_module=mod,
                        imported_layer=imported_layer,
                        reason="cross-engine import forbidden (engineering.md §3.2)",
                    )
                )
    return out


def _scan_file(file: Path) -> list[Violation]:
    importer_layer = _file_layer(file)
    if importer_layer is None:
        return []
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"), filename=str(file))
    except (SyntaxError, UnicodeDecodeError):
        return []

    rel_str = file.relative_to(REPO_ROOT).as_posix()
    importer_depth = LAYER_DEPTH[importer_layer]
    out: list[Violation] = []

    for node in ast.walk(tree):
        for mod in _imported_modules_for_node(node, file):
            out.extend(
                _violations_for_imported_module(
                    rel_str=rel_str,
                    node=node,
                    mod=mod,
                    importer_layer=importer_layer,
                    importer_depth=importer_depth,
                    file=file,
                )
            )
    return out


def scan_all() -> list[Violation]:
    if not SRC_ROOT.exists():
        return []
    violations: list[Violation] = []
    for file in sorted(SRC_ROOT.rglob("*.py")):
        violations.extend(_scan_file(file))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Layer-direction check (engineering.md §3.1).")
    parser.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args(argv)

    violations = scan_all()

    if args.json:
        print(
            json.dumps(
                {
                    "violations": [v.__dict__ for v in violations],
                    "violation_count": len(violations),
                },
                indent=2,
            )
        )
        return 1 if violations else 0

    if not SRC_ROOT.exists():
        print("Layer-direction check: src/nucleus not present yet — passes vacuously.")
        return 0

    if not violations:
        print("Layer-direction check: PASS.")
        return 0

    print(f"Layer-direction check: FAIL — {len(violations)} violation(s):\n")
    for v in violations:
        print(f"  {v.file}:{v.line}")
        print(f"      {v.importer_layer:>13} imports {v.imported_module} ({v.imported_layer})")
        print(f"      reason: {v.reason}\n")
    print("See docs/conventions/engineering.md §3.1, §3.2.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
