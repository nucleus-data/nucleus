"""Vocabulary guard — ``docs/conventions/engineering.md`` §15.

Bans terms we've explicitly decided not to use, anywhere in source or docs:

    - "metastore"        → use "catalog"
    - "data lake"        → use "warehouse" or "lakehouse"
    - "Spark killer"     → use "graduation path"
    - "Databricks killer"→ use "graduation path"
    - "Data OS"          → never; we're a platform, not an OS
    - "AI-native"        → use "AI-assisted"
    - "AI-first"         → use "AI-assisted"

Matches are CASE-INSENSITIVE but word-boundary aware (so "metadata" is fine
while "metastore" or "Metastore" is flagged).

Exemptions
----------
- This script (``scripts/check_vocabulary.py``) itself contains the banned
  words as data, so it self-exempts.
- Any file ending in ``.banned.md`` is exempt — use for documenting why
  a term is banned (rare).
- Glossary section markers like ``<!-- banned-term: metastore -->`` create
  an inline exemption for that line.

Usage
-----
    python scripts/check_vocabulary.py
    python scripts/check_vocabulary.py --paths AGENTS.md README.md
    python scripts/check_vocabulary.py --json

Exit codes
----------
    0  no banned terms found
    1  banned term found

Reading guide
-------------
We use ``re.IGNORECASE`` with explicit word boundaries. We exclude
script self-reference and certain doc patterns explicitly.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

DEFAULT_BANNED_TERMS: list[str] = [
    "metastore",
    "data lake",  # we say "warehouse" or "lakehouse"
    "spark killer",
    "databricks killer",
    "data os",
    "AI-native",
    "AI-first",
]

# File patterns we always skip (ignore-listed below).
SKIP_PATTERNS = [
    ".git/",
    ".venv/",
    # Sibling venvs created by worker scripts (e.g. .venv-adr039, .venv-smoke,
    # .venv-pypi). Per founder action #13/#15 (close-out batch, 2026-05-15
    # FOUNDER_ACTION_QUEUE.md §0.3) — these test-venv trees inherit licence /
    # README / docs that contain banned terms verbatim and would pollute the
    # gate with 5+ false positives per worker pass. Matched as a substring
    # against the file's POSIX path so `.venv-foo/...`, `.venv-bar/...`,
    # etc. all skip.
    ".venv-",
    "venv/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    "node_modules/",
    # node_modules/ already listed above; mirrored under workbench frontend
    # for the case where the worker installs nested node_modules outside the
    # repo root convention (e.g. src/.../frontend/node_modules/).
    # Transient agent-worker inter-process scratch space — git-ignored
    # already (`.gitignore` "/.scratch/"), but the vocab scanner walks the
    # disk regardless of git tracking, so worker commit-message drafts +
    # benchmark text snippets that legitimately quote banned terms
    # ("Governance: vocabulary clean (pre-existing docs/HANDOVER.md AI-first ...")
    # would otherwise pollute the gate. Added 2026-05-16 during the v0.2.0
    # ultimate-sprint close-out builder pass; matches the .venv- precedent.
    ".scratch/",
    "scripts/check_vocabulary.py",  # self-exempt; we list the terms here
    "site/",  # mkdocs build output
    "build/",
    "dist/",
    # Whole-file exemptions for retirement narratives + audit trails (per
    # ADR-002 §8.6.1 evening-pass follow-up). These documents legitimately
    # cite banned vocabulary as the subject of discussion.
    "docs/archive/",  # archived deprecated docs (moved 2026-05-15 REORG PR-A)
    "architecture_design_conversation.md",  # superseded historical conversation (v4.1 line 17)
    "docs/audits/",  # audit trails MUST contain banned terms as evidence
    "docs/audit/",  # audit trails MUST contain banned terms as evidence (alt spelling)
    "docs/decisions/",  # ADRs MAY discuss what was decided NOT to do
    "docs/research/",  # research files cite competitor positioning narratives and ecosystem analysis
    "docs/dev-guides/",  # scaffolding guides reference banned comparator terms verbatim
    "docs/roadmap/",  # roadmap docs discuss positioning context and what we decided NOT to do
    "pyproject.toml",  # holds the ban-list itself; TOML can't carry HTML exemption markers
]

# Inline exemption marker.
INLINE_EXEMPT = re.compile(r"<!--\s*banned-term:\s*[^>]+?\s*-->", re.IGNORECASE)


@dataclass
class Hit:
    file: str
    line: int
    term: str
    excerpt: str


def _load_terms_from_pyproject() -> list[str]:
    if not PYPROJECT.exists():
        return list(DEFAULT_BANNED_TERMS)
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    terms = (
        data.get("tool", {}).get("nucleus", {}).get("forbidden_terms_in_docs", DEFAULT_BANNED_TERMS)
    )
    return [str(t) for t in terms] or list(DEFAULT_BANNED_TERMS)


def _build_pattern(term: str) -> re.Pattern[str]:
    """Build a case-insensitive, word-boundary-aware regex for a banned term."""
    # If the term contains punctuation/spaces, escape & don't add \b around
    # punctuation (which would never match). Use a simpler boundary approach:
    # require the term to be surrounded by non-word characters (or string edges).
    escaped = re.escape(term)
    # (?<![A-Za-z0-9_])  before; (?![A-Za-z0-9_])  after
    return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)


def _should_skip(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return True  # outside repo root (e.g. Windows broken symlinks)
    for pat in SKIP_PATTERNS:
        if rel.startswith(pat) or pat in rel:
            return True
    return path.name.endswith(".banned.md")


def scan_files(roots: list[Path], terms: list[str]) -> list[Hit]:
    patterns = [(t, _build_pattern(t)) for t in terms]
    hits: list[Hit] = []
    for root in roots:
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = []
            for ext in (".py", ".md", ".mdc", ".rst", ".txt", ".yml", ".yaml", ".toml", ".cfg"):
                try:
                    files.extend(root.rglob(f"*{ext}"))
                except (FileNotFoundError, PermissionError, OSError):
                    continue
        else:
            continue
        for file in sorted(files):
            if _should_skip(file):
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for idx, line in enumerate(content.splitlines(), 1):
                if INLINE_EXEMPT.search(line):
                    continue
                for term, pat in patterns:
                    if pat.search(line):
                        hits.append(
                            Hit(
                                file=file.relative_to(REPO_ROOT).as_posix(),
                                line=idx,
                                term=term,
                                excerpt=line.strip()[:120],
                            )
                        )
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forbidden vocabulary check (engineering.md §15).")
    parser.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="Specific paths to scan (default: repo root).",
    )
    parser.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args(argv)

    terms = _load_terms_from_pyproject()
    roots = [Path(p).resolve() for p in args.paths] if args.paths else [REPO_ROOT]
    hits = scan_files(roots, terms)

    if args.json:
        print(
            json.dumps(
                {"hits": [h.__dict__ for h in hits], "hit_count": len(hits), "banned_terms": terms},
                indent=2,
            )
        )
    elif not hits:
        print(f"Vocabulary check: PASS ({len(terms)} terms watched).")
    else:
        print(f"Vocabulary check: FAIL — {len(hits)} occurrence(s) of banned term(s):\n")
        for h in hits:
            print(f'  {h.file}:{h.line}  ["{h.term}"]')
            print(f"      {h.excerpt}")
        print("\nSee docs/conventions/engineering.md §15 for alternative vocabulary.")
        print("If a legitimate use is required, add an inline exemption:")
        print("  <!-- banned-term: <term> -->  on the same line.")

    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
