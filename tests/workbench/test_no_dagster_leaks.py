"""Workbench-scoped guard: no orchestrator UI vocabulary in source trees.

Mirrors the intent of ``scripts/dagster_leak_check.py`` for
``src/nucleus/workbench/`` and ``frontend/src/`` (token scan).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Whole-word / phrase patterns (case-insensitive where noted).
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdagster\b", re.IGNORECASE),
    re.compile(r"\bop\b", re.IGNORECASE),
    re.compile(r"Code\s+Location", re.IGNORECASE),
    re.compile(r"\bDefinitions\b", re.IGNORECASE),
)

_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".html", ".json"}


def _iter_scannable_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in _SUFFIXES
        and "__pycache__" not in p.parts
    )


def _find_violations(text: str, rel_posix: str) -> list[str]:
    return [
        f"{rel_posix}: matched {pat.pattern!r}"
        for pat in _PATTERNS
        if pat.search(text)
    ]


def test_workbench_tree_has_no_banned_tokens() -> None:
    root = REPO / "src" / "nucleus" / "workbench"
    violations: list[str] = []
    for path in _iter_scannable_files(root):
        raw = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO).as_posix()
        violations.extend(_find_violations(raw, rel))
    assert not violations, "Banned tokens in workbench tree:\n" + "\n".join(violations)


def test_frontend_src_has_no_banned_tokens() -> None:
    root = REPO / "frontend" / "src"
    violations: list[str] = []
    for path in _iter_scannable_files(root):
        raw = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO).as_posix()
        violations.extend(_find_violations(raw, rel))
    assert not violations, "Banned tokens in frontend/src:\n" + "\n".join(violations)
