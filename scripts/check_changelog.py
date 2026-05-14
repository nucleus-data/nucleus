"""CHANGELOG gate for CI and local dev.

Rules (ADR-022):
  * Any commit subject/body in the range ``base..head`` may contain
    ``[skip-changelog]`` to exempt the changelog requirement entirely.
  * Otherwise ``CHANGELOG.md`` must change between refs, and ``[Unreleased]``
    must gain at least one new bullet compared to ``base``.

Optional PR title exemptions (Prefixes like ``docs:``, ``ci:``) preserve
changelog.yml ergonomics without requiring label plumbing in this script.

Usage:
    python scripts/check_changelog.py --since HEAD~5
    python scripts/check_changelog.py --since main
    python scripts/check_changelog.py --base "$BASE_SHA" --head "$HEAD_SHA" [--title "..."]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()

EXEMPT_TITLE_PREFIXES = ("chore:", "docs:", "ci:", "build:", "style:", "test:")
SKIP_MARKER = "[skip-changelog]"
BULLET_LINE = re.compile(r"^\s*[-*]\s+\S")


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _rev_parse(spec: str) -> str | None:
    proc = _git(["rev-parse", spec])
    out = proc.stdout.strip() if proc.stdout else ""
    if proc.returncode != 0 or not out:
        return None
    return out.splitlines()[0]


def _commits_have_skip(begin: str, end: str) -> bool:
    proc = _git(["log", f"{begin}..{end}", "--format=%B"])
    out = proc.stdout or ""
    return SKIP_MARKER in out


def _changed_files_between(base_sha: str, head_sha: str) -> list[str]:
    proc = _git(["diff", "--name-only", base_sha, head_sha])
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        sys.exit(proc.returncode or 1)
    return [ln for ln in (proc.stdout or "").splitlines() if ln]


def _changelog_blob(sha: str) -> str:
    proc = _git(["show", f"{sha}:CHANGELOG.md"])
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def _unreleased_lines(text: str) -> list[str]:
    m = re.search(r"## \[Unreleased\](.*?)(?=\n## \[|\Z)", text, flags=re.DOTALL)
    if not m:
        return []
    return [ln.strip() for ln in m.group(1).splitlines() if BULLET_LINE.match(ln)]


def main() -> None:  # noqa: PLR0912 — branching mirrors CI/local mode matrix
    parser = argparse.ArgumentParser(description="Changelog enforcement gate")
    parser.add_argument("--base", help="Base ref (CI mode)")
    parser.add_argument("--head", default="HEAD", help="Head ref (default HEAD)")
    parser.add_argument("--title", default="", help="PR title (optional exemptions)")
    parser.add_argument("--since", help="Shorthand base ref compared to HEAD")
    args = parser.parse_args()

    title_low = args.title.strip().lower()
    for pref in EXEMPT_TITLE_PREFIXES:
        if title_low.startswith(pref):
            print(f"OK: exempt PR title ({pref}); skipping changelog enforcement.")
            sys.exit(0)

    if args.since:
        base_raw, head_raw = args.since, args.head
    elif args.base:
        base_raw, head_raw = args.base, args.head
    else:
        parser.error("Provide --since REF or (--base REF and optional --head REF).")

    base_sha = _rev_parse(base_raw)
    head_sha = _rev_parse(head_raw)
    if base_sha is None:
        print(
            f"OK: base ref ({base_raw!r}) unresolved (fresh clone/root commit). "
            "Skipping changelog-range enforcement."
        )
        sys.exit(0)
    if not head_sha:
        print("ERROR: could not resolve head revision.", file=sys.stderr)
        sys.exit(1)

    if head_sha != base_sha and _commits_have_skip(base_sha, head_sha):
        print(f"OK: {SKIP_MARKER} in commit range — skipping changelog requirement.")
        sys.exit(0)

    changed = _changed_files_between(base_sha, head_sha)
    changelog_touched = any(f.upper() == "CHANGELOG.MD" for f in changed)
    old_lines = _unreleased_lines(_changelog_blob(base_sha))
    new_lines = _unreleased_lines(_changelog_blob(head_sha))
    new_set = set(new_lines)

    if not changelog_touched:
        print(
            "ERROR: CHANGELOG.md not modified in range.\n"
            f'Update "## [Unreleased]" or commit with `{SKIP_MARKER}`.'
        )
        sys.exit(1)

    if not old_lines and any(new_lines):
        print("OK: CHANGELOG.md [Unreleased] has new bullets.")
        sys.exit(0)

    genuinely_new = [ln for ln in new_lines if ln not in set(old_lines)]

    # Allow same-line edits (typos): require at least one line not previously present
    if not genuinely_new and set(new_lines) <= set(old_lines):
        print(
            "ERROR: CHANGELOG.md changed but no new bullets appeared under [Unreleased]. "
            "(Only reorder/format change?)"
        )
        sys.exit(1)

    if genuinely_new:
        print("OK: CHANGELOG.md [Unreleased] has new bullets.")
        sys.exit(0)

    # New lines reorder only but set equal counts as change - still allow if changelog touched
    if new_set != set(old_lines):
        print("OK: CHANGELOG.md [Unreleased] updated.")
        sys.exit(0)

    print("ERROR: CHANGELOG.md did not materially update [Unreleased].")
    sys.exit(1)


if __name__ == "__main__":
    main()
