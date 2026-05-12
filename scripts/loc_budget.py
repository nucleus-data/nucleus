"""LOC budget enforcement — Constraint #8.

Counts non-blank, non-comment lines in ``src/nucleus/`` and reports against
the per-tier ceilings defined in ``pyproject.toml`` under ``[tool.nucleus]``.

Usage
-----
    python scripts/loc_budget.py --report    # always exits 0; prints table
    python scripts/loc_budget.py --warn      # exits 0 but prints warning if over budget
    python scripts/loc_budget.py             # exits 1 if over current tier ceiling
    python scripts/loc_budget.py --json      # machine-readable output for CI

What counts
-----------
- Lines in ``.py`` files under ``src/nucleus/``.
- Excludes blank lines and pure-comment lines.
- Excludes files matching patterns in ``pyproject.toml`` ``[tool.nucleus] loc_exclude``.

What does NOT count
-------------------
- ``tests/``, ``poc/``, ``scripts/``, ``docs/``.
- Stub files (``*.pyi``).
- ``__init__.py`` files that contain only re-exports.

Why this exists
---------------
Constraint #8 says: v0.1 ceiling 8000 LOC, v0.5 ceiling 18000 LOC, v1.0 ceiling 30000 LOC.
Larger codebases are harder for a solo founder to maintain and harder for
AI agents to navigate. If you blow past the ceiling, the platform is leaking
complexity — fix the design, not the budget.

Reading guide for a junior DE
-----------------------------
This script is intentionally simple — readable in 5 minutes. We chose pure
``tomllib`` + ``pathlib`` (both stdlib) so it has no dependencies. If you
want to extend it, add features behind ``--flag`` rather than restructuring.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "nucleus"
PYPROJECT = REPO_ROOT / "pyproject.toml"


@dataclass
class TierBudget:
    """Per-tier LOC ceilings parsed from pyproject.toml."""

    v01: int = 8_000
    v05: int = 18_000
    v10: int = 30_000

    @classmethod
    def from_pyproject(cls, path: Path) -> "TierBudget":
        if not path.exists():
            return cls()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        nucl = data.get("tool", {}).get("nucleus", {})
        return cls(
            v01=int(nucl.get("loc_budget_v01_ceiling", cls.v01)),
            v05=int(nucl.get("loc_budget_v05_ceiling", cls.v05)),
            v10=int(nucl.get("loc_budget_v10_ceiling", cls.v10)),
        )

    def current_ceiling(self) -> tuple[str, int]:
        """Return the *currently active* tier ceiling.

        We pick conservatively: the lowest tier we have not yet promoted to.
        Override the tier via the env var ``NUCLEUS_TIER`` (=01|05|10).
        """
        import os

        tier = os.environ.get("NUCLEUS_TIER", "01")
        if tier == "01":
            return "v0.1", self.v01
        if tier == "05":
            return "v0.5", self.v05
        return "v1.0", self.v10


def _excluded_patterns(path: Path) -> list[str]:
    """Read ``[tool.nucleus] loc_exclude`` from pyproject. Default sane list."""
    if not path.exists():
        return ["tests/", "poc/", "docs/", "scripts/", "*.pyi", "**/__init__.py"]
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return list(
        data.get("tool", {})
        .get("nucleus", {})
        .get("loc_exclude", ["tests/", "poc/", "docs/", "scripts/", "*.pyi", "**/__init__.py"])
    )


def _is_excluded(file: Path, patterns: list[str], src_root: Path) -> bool:
    rel = file.relative_to(REPO_ROOT)
    rel_str = rel.as_posix()
    for pat in patterns:
        # crude but effective: substring or fnmatch-style match.
        if pat.endswith("/") and rel_str.startswith(pat):
            return True
        if pat.startswith("*."):
            if rel.suffix == pat[1:]:
                return True
        if pat.startswith("**/") and rel.match(pat):
            return True
        if pat in rel_str:
            return True
    return False


def _count_lines(file: Path) -> int:
    """Count code-bearing lines.

    A line counts if it's NOT entirely blank AND NOT a pure comment line.
    Docstring lines DO count (they're documentation and contribute to size).
    """
    count = 0
    for raw in file.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def _collect_loc(src_root: Path, patterns: list[str]) -> dict[str, int]:
    """Walk src_root collecting per-module LOC counts."""
    out: dict[str, int] = {}
    if not src_root.exists():
        return out
    for file in sorted(src_root.rglob("*.py")):
        if _is_excluded(file, patterns, src_root):
            continue
        rel = file.relative_to(REPO_ROOT).as_posix()
        out[rel] = _count_lines(file)
    return out


def _module_summary(file_counts: dict[str, int], src_root: Path) -> dict[str, int]:
    """Aggregate file counts under top-level modules of src_root.

    E.g.   src/nucleus/ctx/foo.py     → ctx
           src/nucleus/engines/bar.py → engines
    """
    summary: dict[str, int] = {}
    prefix = src_root.relative_to(REPO_ROOT).as_posix() + "/"
    for path, count in file_counts.items():
        if not path.startswith(prefix):
            continue
        tail = path[len(prefix) :]
        first = tail.split("/", 1)[0]
        module = first if "/" in tail else "_top"
        summary[module] = summary.get(module, 0) + count
    return summary


def _render_report(file_counts: dict[str, int], src_root: Path, budget: TierBudget) -> str:
    total = sum(file_counts.values())
    tier_name, ceiling = budget.current_ceiling()
    summary = _module_summary(file_counts, src_root)
    pct = (total / ceiling * 100) if ceiling else 0
    lines = []
    lines.append("=" * 60)
    lines.append(" Nucleus — LOC Budget Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f" Current tier        : {tier_name}")
    lines.append(f" Active ceiling      : {ceiling:>6,} LOC")
    lines.append(f" Cumulative LOC      : {total:>6,} LOC")
    lines.append(f" Usage               : {pct:>5.1f}%")
    lines.append("")
    if summary:
        lines.append(" By module:")
        for mod, count in sorted(summary.items(), key=lambda kv: -kv[1]):
            bar = "█" * max(1, int(count / max(1, max(summary.values())) * 40))
            lines.append(f"   {mod:<16} {count:>5,}  {bar}")
    else:
        lines.append("  (No source code yet — pre-Heartbeat state.)")
    lines.append("")
    lines.append(f" Future budgets      : v0.1={budget.v01:,}, v0.5={budget.v05:,}, v1.0={budget.v10:,}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nucleus LOC budget enforcement.")
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print report; always exit 0.",
    )
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Print report; exit 0 (warn but don't fail) if over budget.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of human report.",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=SRC_ROOT,
        help="Source root to scan (default: src/nucleus).",
    )
    args = parser.parse_args(argv)

    budget = TierBudget.from_pyproject(PYPROJECT)
    patterns = _excluded_patterns(PYPROJECT)
    file_counts = _collect_loc(args.src, patterns)
    total = sum(file_counts.values())
    tier_name, ceiling = budget.current_ceiling()
    over = total > ceiling

    if args.json:
        print(
            json.dumps(
                {
                    "total": total,
                    "ceiling": ceiling,
                    "tier": tier_name,
                    "over_budget": over,
                    "per_file": file_counts,
                    "per_module": _module_summary(file_counts, args.src),
                },
                indent=2,
            )
        )
    else:
        print(_render_report(file_counts, args.src, budget))

    if args.report:
        return 0
    if over:
        if args.warn:
            print(f"\nWARNING: over budget ({total:,} > {ceiling:,}), but exiting 0 per --warn.", file=sys.stderr)
            return 0
        print(f"\nERROR: LOC over budget ({total:,} > {ceiling:,} for {tier_name}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
