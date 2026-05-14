"""API stability-tier check — ADR-005 §Verification plan.

AST-walks ``src/nucleus/__init__.py`` and resolves each public symbol in
``__all__`` to its definition. Every public symbol MUST carry a
``# Stability: <tier>`` marker in its docstring (or a class-level
``__stability__ = "<tier>"`` assignment) where tier is one of::

    Frozen     backward-compat through every minor in a major
    Stable     backward-compat through every minor in v0.x
    Beta       may break minor-to-minor; documented
    Internal   not promised; reserved for ``_internal_*`` namespaces

Frozen-tier symbols additionally snapshot their type signature so future
shape drift is detectable. ``--snapshot`` mode records signatures;
default mode compares the live AST against the recorded snapshot.

Usage
-----
    python scripts/check_api_stability.py
    python scripts/check_api_stability.py --snapshot   # record signatures
    python scripts/check_api_stability.py --json

Exit codes
----------
    0  every public symbol tagged + no Frozen drift
    1  missing tag on a public symbol
    2  Frozen-tier signature drift detected

NEEDS VERIFICATION (AGENTS.md §11.12)
-------------------------------------
Snapshot serialisation format: tentatively ``ast.unparse(args) + return
annotation`` stored as plain text under ``tests/api_stability/snapshots/``
(deterministic, diffable, no pickle attack surface). Format may need to
switch to JSON once Frozen symbols include nested dataclasses or
``TypedDict``s whose textual ordering is not stable across Python minors.
The CI step is wired with ``continue-on-error: true`` until ADR-005 is
ACCEPTED and the v0.5 spec lock annotates ``__all__`` with tier tags.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = REPO_ROOT / "src" / "nucleus"
INIT_FILE = PKG_ROOT / "__init__.py"
SNAPSHOT_DIR = REPO_ROOT / "tests" / "api_stability" / "snapshots"

VALID_TIERS: Final[tuple[str, ...]] = ("Frozen", "Stable", "Beta", "Internal")
STABILITY_RE: Final[re.Pattern[str]] = re.compile(
    r"#\s*Stability\s*:\s*(Frozen|Stable|Beta|Internal)\b", re.IGNORECASE,
)


@dataclass
class Symbol:
    name: str
    source_file: str
    line: int
    tier: str | None
    kind: str        # "class" | "function" | "assign" | "unresolved"
    signature: str   # AST-unparsed args (for Frozen drift detection)


@dataclass
class DriftFinding:
    name: str
    snapshot: str
    current: str


def _read_all(init_path: Path) -> list[str]:
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return [e.value for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _resolve_imports(init_tree: ast.Module) -> dict[str, str]:
    """Map ``name -> submodule_path`` for ``from nucleus.X import Y`` re-exports."""
    out: dict[str, str] = {}
    for node in ast.walk(init_tree):
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").lstrip(".")
            if not module.startswith("nucleus"):
                module = f"nucleus.{module}" if node.level == 1 and module else module
            for alias in node.names:
                local = alias.asname or alias.name
                if module.startswith("nucleus"):
                    out[local] = module
    return out


def _module_path(dotted: str) -> Path:
    rel = dotted.replace(".", "/")
    candidate = REPO_ROOT / "src" / f"{rel}.py"
    if candidate.exists():
        return candidate
    return REPO_ROOT / "src" / rel / "__init__.py"  # may not exist; caller checks


def _find_def(name: str, tree: ast.Module) -> ast.AST | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node
    return None


def _extract_tier(node: ast.AST) -> str | None:
    doc = (ast.get_docstring(node)
           if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef | ast.Module)
           else None)
    if doc:
        m = STABILITY_RE.search(doc)
        if m:
            return m.group(1).capitalize()
    if isinstance(node, ast.ClassDef):
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__stability__" for t in stmt.targets
            ) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                cap = stmt.value.value.capitalize()
                if cap in VALID_TIERS:
                    return cap
    return None


def _signature(node: ast.AST) -> str:
    if isinstance(node, ast.ClassDef):
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
                return f"__init__({ast.unparse(stmt.args)})"
        return "class()"
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"({ast.unparse(node.args)}){ret}"
    if isinstance(node, ast.AnnAssign) and node.annotation:
        return f": {ast.unparse(node.annotation)}"
    return "<opaque>"


def collect() -> list[Symbol]:
    if not INIT_FILE.exists():
        return []
    init_tree = ast.parse(INIT_FILE.read_text(encoding="utf-8"), filename=str(INIT_FILE))
    names = _read_all(INIT_FILE)
    remote = _resolve_imports(init_tree)
    out: list[Symbol] = []
    for name in names:
        target_file = INIT_FILE
        target_tree: ast.Module = init_tree
        if name in remote:
            target_file = _module_path(remote[name])
            if not target_file.exists():
                out.append(Symbol(name, str(remote[name]), 0, None, "unresolved", "<source missing>"))
                continue
            target_tree = ast.parse(target_file.read_text(encoding="utf-8"), filename=str(target_file))
        node = _find_def(name, target_tree)
        if node is None:
            out.append(Symbol(name, str(target_file.relative_to(REPO_ROOT)), 0,
                              None, "unresolved", "<not found>"))
            continue
        kind = ("class" if isinstance(node, ast.ClassDef)
                else "function" if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                else "assign")
        out.append(Symbol(
            name=name,
            source_file=str(target_file.relative_to(REPO_ROOT)),
            line=getattr(node, "lineno", 0),
            tier=_extract_tier(node),
            kind=kind,
            signature=_signature(node),
        ))
    return out


def _snapshot_path(name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return SNAPSHOT_DIR / f"{safe}.txt"


def record_snapshots(symbols: list[Symbol]) -> list[str]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for s in symbols:
        if s.tier != "Frozen":
            continue
        path = _snapshot_path(s.name)
        path.write_text(s.signature + "\n", encoding="utf-8")
        written.append(str(path.relative_to(REPO_ROOT)))
    return written


def detect_drift(symbols: list[Symbol]) -> list[DriftFinding]:
    drifts: list[DriftFinding] = []
    for s in symbols:
        if s.tier != "Frozen":
            continue
        path = _snapshot_path(s.name)
        if not path.exists():
            continue
        prior = path.read_text(encoding="utf-8").strip()
        if prior != s.signature.strip():
            drifts.append(DriftFinding(s.name, prior, s.signature))
    return drifts


def _render(symbols: list[Symbol], drifts: list[DriftFinding], recorded: list[str] | None) -> str:
    untagged = [s for s in symbols if s.tier is None and s.kind != "unresolved"]
    unresolved = [s for s in symbols if s.kind == "unresolved"]
    lines = ["API stability check (ADR-005)", "=" * 62,
             f" public symbols : {len(symbols)}",
             f" untagged       : {len(untagged)}",
             f" unresolved     : {len(unresolved)}",
             f" Frozen drift   : {len(drifts)}", ""]
    for s in symbols:
        tier = s.tier or "MISSING"
        lines.append(f"  [{tier:<8}] {s.name:<28} {s.kind:<9} {s.source_file}:{s.line}  {s.signature}")
    if drifts:
        lines += ["", "Frozen signature drift (ADR-005 §3 Breaking-change protocol):"]
        for d in drifts:
            lines.append(f"  {d.name}")
            lines.append(f"    snapshot: {d.snapshot}")
            lines.append(f"    current : {d.current}")
        lines.append("  Open ADR-NNN-breaking-<api> + ship DeprecationWarning per ADR-005.")
    if recorded is not None:
        lines += ["", f"Recorded {len(recorded)} Frozen snapshot(s):"] + [f"  - {p}" for p in recorded]
    if untagged and recorded is None:
        lines += ["", "Add `# Stability: <Frozen|Stable|Beta|Internal>` to the docstring",
                  "of each untagged symbol per ADR-005 §1, or set `__stability__` on classes."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="API stability-tier check (ADR-005 §Verification plan).")
    p.add_argument("--snapshot", action="store_true",
                   help="Record signatures of Frozen-tier symbols and exit 0.")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    args = p.parse_args(argv)

    if not INIT_FILE.exists():
        msg = f"check_api_stability: {INIT_FILE} not found — passing vacuously."
        if args.json:
            print(json.dumps({"ok": True, "verdict": "SKELETON", "reason": msg}, indent=2))
        else:
            print(msg)
        return 0

    symbols = collect()
    untagged = [s for s in symbols if s.tier is None and s.kind != "unresolved"]
    recorded: list[str] | None = None
    drifts: list[DriftFinding] = []
    if args.snapshot:
        recorded = record_snapshots(symbols)
    else:
        drifts = detect_drift(symbols)

    if args.json:
        print(json.dumps({
            "ok": not untagged and not drifts,
            "symbols": [asdict(s) for s in symbols],
            "untagged": [asdict(s) for s in untagged],
            "drift": [asdict(d) for d in drifts],
            "recorded": recorded,
        }, indent=2))
    else:
        print(_render(symbols, drifts, recorded))

    if args.snapshot:
        return 0
    if drifts:
        return 2
    if untagged:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
