"""Count proprietary LOC for the Nucleus project.

Per AGENTS.md Sec 11.6 + Hard Constraint #8: total proprietary LOC <= 30,000
by v1.0. Phase ceilings (verbatim from Sec 11.6):

    PoCs complete : ~1,000  (informational; PoC code is pre-production)
    v0.1 ship     : ~8,000
    v0.5 ship     : ~18,000
    v1.0 ship     : ~30,000  (hard ceiling)

Counting rules (be honest):
    COUNT     : actual code lines (statements, expressions, signatures).
    SKIP      : blank lines, comment-only lines, docstring-only lines
                (module/class/function docstrings, identified via ``ast``).
    INCLUDED  : ``__init__.py`` files. They are proprietary surface even when
                they only re-export -- debatable, but counting them prevents
                gaming the budget by stuffing logic into ``__init__.py``.

Scope: ``src/nucleus/`` counts toward the ceiling; ``poc/`` and ``tests/``
are reported as informational and do NOT count.

Stdlib-only (Python 3.11+); runs on Windows, Linux, macOS unchanged.

Docs:
    https://docs.python.org/3/library/tokenize.html
    https://docs.python.org/3/library/ast.html
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import sys
import tokenize
from contextlib import suppress
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "nucleus"
POC_ROOT = REPO_ROOT / "poc"
TESTS_ROOT = REPO_ROOT / "tests"

PHASE_CEILINGS: dict[str, int] = {
    "pocs": 1_000,
    "v0.1": 8_000,
    "v0.5": 18_000,
    "v1.0": 30_000,
}

_DOCSTRING_PARENTS: tuple[type, ...] = (
    ast.Module,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)
_SKIP_TOKEN_TYPES: frozenset[int] = frozenset(
    {
        tokenize.COMMENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
)


def _docstring_lines(tree: ast.Module) -> set[int]:
    """Return line numbers occupied by module/class/function docstrings."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRING_PARENTS):
            continue
        body = getattr(node, "body", None)
        if not body or not isinstance(body[0], ast.Expr):
            continue
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            start = body[0].lineno
            end = body[0].end_lineno or start
            out.update(range(start, end + 1))
    return out


def count_loc(path: Path) -> int:
    """Count code-bearing lines in a single Python file."""
    src = path.read_text(encoding="utf-8", errors="replace")
    docstrings: set[int] = set()
    with suppress(SyntaxError):
        docstrings = _docstring_lines(ast.parse(src))

    code_lines: set[int] = set()
    try:
        readline = io.BytesIO(src.encode("utf-8")).readline
        for tok in tokenize.tokenize(readline):
            if tok.type in _SKIP_TOKEN_TYPES:
                continue
            line_no = tok.start[0]
            if line_no in docstrings:
                continue
            code_lines.add(line_no)
    except (tokenize.TokenizeError, IndentationError):
        for i, raw in enumerate(src.splitlines(), 1):
            stripped = raw.strip()
            if stripped and not stripped.startswith("#") and i not in docstrings:
                code_lines.add(i)
    return len(code_lines)


def collect_loc(root: Path) -> dict[str, int]:
    """Walk ``root`` and return {relative_path: loc} for every .py file."""
    out: dict[str, int] = {}
    if not root.exists():
        return out
    for file in sorted(root.rglob("*.py")):
        out[file.relative_to(REPO_ROOT).as_posix()] = count_loc(file)
    return out


def per_subdir(file_counts: dict[str, int], root: Path) -> dict[str, int]:
    """Aggregate per-file counts under top-level subdirectories of ``root``."""
    summary: dict[str, int] = {}
    prefix = root.relative_to(REPO_ROOT).as_posix() + "/"
    for path, count in file_counts.items():
        if not path.startswith(prefix):
            continue
        tail = path[len(prefix) :]
        bucket = tail.split("/", 1)[0] if "/" in tail else "(top-level)"
        summary[bucket] = summary.get(bucket, 0) + count
    return summary


def status_for(actual: int, ceiling: int) -> str:
    """GREEN < 80% of ceiling; YELLOW 80-100%; RED > 100%."""
    if ceiling <= 0:
        return "GREEN"
    pct = actual / ceiling * 100
    if pct > 100:
        return "RED"
    return "YELLOW" if pct >= 80 else "GREEN"


def render_text(
    src_counts: dict[str, int],
    poc_counts: dict[str, int],
    test_counts: dict[str, int],
    phase: str,
) -> str:
    src_total = sum(src_counts.values())
    poc_total = sum(poc_counts.values())
    test_total = sum(test_counts.values())
    ceiling = PHASE_CEILINGS[phase]
    pct = (src_total / ceiling * 100) if ceiling else 0
    src_breakdown = per_subdir(src_counts, SRC_ROOT)
    bar = "=" * 64
    lines = [
        bar,
        " Nucleus -- LOC Budget Report (per AGENTS.md Sec 11.6)",
        bar,
        "",
        " Phase ceilings (verbatim from Sec 11.6):",
        "   PoCs complete  : ~1,000  LOC (informational)",
        "   v0.1 ship      : ~8,000  LOC",
        "   v0.5 ship      : ~18,000 LOC",
        "   v1.0 ship      : ~30,000 LOC (hard ceiling)",
        "",
        f" Reference phase     : {phase}",
        f" Reference ceiling   : {ceiling:>6,} LOC",
        f" src/nucleus/ total  : {src_total:>6,} LOC  ({pct:5.1f}% of {phase} ceiling)",
        f" Verdict             : {status_for(src_total, ceiling)}",
        "",
        " src/nucleus/ per-subdirectory breakdown:",
    ]
    if src_breakdown:
        width = max(len(name) for name in src_breakdown)
        for name, count in sorted(src_breakdown.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"   {name:<{width}}   {count:>6,} LOC")
    else:
        lines.append("   (no .py files found under src/nucleus/)")
    lines += [
        "",
        f" poc/   total (informational, NOT in ceiling) : {poc_total:>6,} LOC",
        f" tests/ total (informational, NOT in ceiling) : {test_total:>6,} LOC",
        "",
        " Status legend: GREEN < 80%, YELLOW 80-100%, RED > 100% of ceiling.",
        bar,
    ]
    return "\n".join(lines)


def render_json(
    src_counts: dict[str, int],
    poc_counts: dict[str, int],
    test_counts: dict[str, int],
    phase: str,
) -> str:
    src_total = sum(src_counts.values())
    ceiling = PHASE_CEILINGS[phase]
    return json.dumps(
        {
            "phase": phase,
            "ceiling": ceiling,
            "phase_ceilings": PHASE_CEILINGS,
            "src_nucleus": {
                "total": src_total,
                "percent_of_ceiling": round(src_total / ceiling * 100, 2) if ceiling else 0,
                "verdict": status_for(src_total, ceiling),
                "per_subdir": per_subdir(src_counts, SRC_ROOT),
                "per_file": src_counts,
            },
            "poc": {"total": sum(poc_counts.values()), "per_file": poc_counts},
            "tests": {"total": sum(test_counts.values()), "per_file": test_counts},
        },
        indent=2,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Count proprietary LOC under src/nucleus/ vs the AGENTS.md Sec 11.6 ceilings.",
    )
    parser.add_argument(
        "--phase",
        choices=sorted(p for p in PHASE_CEILINGS if p != "pocs"),
        default="v0.1",
        help="Phase ceiling to compare against (default: v0.1).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human report.",
    )
    args = parser.parse_args(argv)

    src_counts = collect_loc(SRC_ROOT)
    poc_counts = collect_loc(POC_ROOT)
    test_counts = collect_loc(TESTS_ROOT)
    renderer = render_json if args.json else render_text
    sys.stdout.write(renderer(src_counts, poc_counts, test_counts, args.phase) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
