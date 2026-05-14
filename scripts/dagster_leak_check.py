"""Dagster leak check — v4.1 §6.4.

Verifies that Dagster types do NOT leak past the ``coordination/`` layer.

Rule
----
``from dagster ...`` (or ``import dagster``) is allowed ONLY in:
    - ``src/nucleus/coordination/**.py``
    - ``tests/coordination/**.py``
    - ``poc/**.py`` (PoCs are exploratory — but lint warns)

If a Dagster import appears anywhere else, the abstraction has leaked.
This script fails CI and pre-commit when violations are found.

It also greps rendered CLI output (when ``--scan-output`` is given) for
any string starting with ``dagster.`` (a stack-trace prefix). This catches
the case where exceptions are translated but their str() repr still
contains the Dagster module path.

Usage
-----
    python scripts/dagster_leak_check.py
    python scripts/dagster_leak_check.py --json
    python scripts/dagster_leak_check.py --scan-output path/to/cli_output.txt

Exit codes
----------
    0  no leaks
    1  leak detected (CI fail)
    2  invocation error (bad args, etc.)

Reading guide
-------------
This script uses ``ast`` for accurate import detection (regex would have
too many false positives in strings/comments). For text scanning, regex
is fine.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "nucleus"

# Directories where Dagster imports are allowed.
ALLOWED_IMPORT_DIRS = (
    "src/nucleus/coordination",
    "tests/coordination",
    # poc/ is allowed but warned (we'll print a notice for these)
    "poc",
)

# Directories where LiteLLM / provider imports are allowed (intelligence layer only).
ALLOWED_LITELLM_IMPORT_DIRS = (
    "src/nucleus/intelligence",
    "tests/intelligence",
    "tests/upgrade_smoke",
    "poc",
)

# Allowed regex prefixes when scanning rendered output text.
# (Empty for now; users should never see "dagster." in any CLI output.)
ALLOWED_OUTPUT_SUBSTRINGS: tuple[str, ...] = ()

# Provider / LLM library names banned from user_message= and fix_hint= strings.
# Extended per ADR-015 §6 / AGENTS.md §11.7 (v0.2 Copilot work, 2026-05-13).
# Rule: internal provider library names must not appear in user-facing strings;
# user should see "provider" or "Copilot" not the underlying SDK name.
# NOTE: "ollama" omitted here — it IS user-facing as the `--provider ollama` CLI flag.
# Compound class names (e.g. litellm.AuthenticationError) are caught by
# the `*_API_KEY` pattern below or by the literal string checks above.
BANNED_PROVIDER_NAMES: tuple[str, ...] = (
    "litellm",
    "LiteLLM",
    "anthropic",
    "openai",
)

# API key patterns to scan for in user-facing strings (e.g. ANTHROPIC_API_KEY).
_API_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*_API_KEY\b")


@dataclass
class Leak:
    file: str
    line: int
    code: str
    reason: str


def _is_path_in(parent: str, child: Path) -> bool:
    """True if ``child`` (relative to repo) starts with ``parent``."""
    try:
        rel = child.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    return rel.startswith(parent + "/") or rel == parent


def _find_litellm_imports(file: Path) -> list[tuple[int, str]]:
    """Parse ``file`` and return [(line_no, source_line)] for each LiteLLM/provider import."""
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"), filename=str(file))
    except (SyntaxError, UnicodeDecodeError):
        return []
    hits: list[tuple[int, str]] = []
    source_lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("litellm", "anthropic", "openai", "ollama") or \
                   any(alias.name.startswith(p + ".") for p in ("litellm", "anthropic", "openai")):
                    line_no = node.lineno
                    src = source_lines[line_no - 1] if line_no - 1 < len(source_lines) else ""
                    hits.append((line_no, src.strip()))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in ("litellm", "anthropic", "openai", "ollama") or \
               any(mod.startswith(p + ".") for p in ("litellm", "anthropic", "openai")):
                line_no = node.lineno
                src = source_lines[line_no - 1] if line_no - 1 < len(source_lines) else ""
                hits.append((line_no, src.strip()))
    return hits


def scan_litellm_imports(roots: list[Path]) -> list[Leak]:
    """Walk roots, return leaks where litellm/provider imports outside allowed dirs."""
    leaks: list[Leak] = []
    for root in roots:
        if not root.exists():
            continue
        for file in sorted(root.rglob("*.py")):
            hits = _find_litellm_imports(file)
            if not hits:
                continue
            rel_str = file.relative_to(REPO_ROOT).as_posix()
            allowed = any(rel_str.startswith(d + "/") or rel_str == d for d in ALLOWED_LITELLM_IMPORT_DIRS)
            if allowed:
                continue
            for line_no, src in hits:
                leaks.append(
                    Leak(
                        file=rel_str,
                        line=line_no,
                        code=src,
                        reason="LiteLLM/provider import outside intelligence/ — ADR-015 §6 violated",
                    )
                )
    return leaks


def scan_provider_strings_in_nucleus_errors(roots: list[Path]) -> list[Leak]:
    """Scan NucleusError user_message= literals for banned provider class names + API_KEY patterns."""
    leaks: list[Leak] = []
    banned_pat = re.compile(
        r"\b(" + "|".join(re.escape(n) for n in BANNED_PROVIDER_NAMES) + r")\b"
    )
    for root in roots:
        if not root.exists():
            continue
        for file in sorted(root.rglob("*.py")):
            try:
                source = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel_str = file.relative_to(REPO_ROOT).as_posix()
            for idx, line in enumerate(source.splitlines(), 1):
                # Check lines with user_message= or fix_hint= assignments for banned strings.
                if "user_message=" in line or "fix_hint=" in line:
                    if banned_pat.search(line):
                        leaks.append(
                            Leak(
                                file=rel_str,
                                line=idx,
                                code=line.strip(),
                                reason="Provider class name in user_message/fix_hint — ADR-015 §6 violated",
                            )
                        )
                    if _API_KEY_PATTERN.search(line):
                        leaks.append(
                            Leak(
                                file=rel_str,
                                line=idx,
                                code=line.strip(),
                                reason="*_API_KEY pattern in user_message/fix_hint — ADR-015 §6 violated",
                            )
                        )
    return leaks


def _find_dagster_imports(file: Path) -> list[tuple[int, str]]:
    """Parse ``file`` and return [(line_no, source_line)] for each Dagster import."""
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"), filename=str(file))
    except (SyntaxError, UnicodeDecodeError):
        # Skip un-parseable files; they will fail another check anyway.
        return []
    hits: list[tuple[int, str]] = []
    source_lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dagster" or alias.name.startswith("dagster."):
                    line_no = node.lineno
                    src = source_lines[line_no - 1] if line_no - 1 < len(source_lines) else ""
                    hits.append((line_no, src.strip()))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "dagster" or mod.startswith("dagster."):
                line_no = node.lineno
                src = source_lines[line_no - 1] if line_no - 1 < len(source_lines) else ""
                hits.append((line_no, src.strip()))
    return hits


def scan_imports(roots: list[Path]) -> list[Leak]:
    """Walk roots, return list of leaks (Dagster imports outside allowed dirs)."""
    leaks: list[Leak] = []
    for root in roots:
        if not root.exists():
            continue
        for file in sorted(root.rglob("*.py")):
            hits = _find_dagster_imports(file)
            if not hits:
                continue
            rel_str = file.relative_to(REPO_ROOT).as_posix()
            allowed = any(rel_str.startswith(d + "/") or rel_str == d for d in ALLOWED_IMPORT_DIRS)
            if allowed:
                continue
            for line_no, src in hits:
                leaks.append(
                    Leak(
                        file=rel_str,
                        line=line_no,
                        code=src,
                        reason="Dagster import outside coordination/ — v4.1 §6.4 violated",
                    )
                )
    return leaks


def scan_output(file: Path) -> list[Leak]:
    """Grep file for unmasked Dagster identifiers (e.g. ``dagster.X``)."""
    if not file.exists():
        return []
    leaks: list[Leak] = []
    # Match e.g. "dagster.foo", "dagster._core", "dagster.DagsterError"
    pat = re.compile(r"\bdagster\.[a-zA-Z_]")
    for idx, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if pat.search(line):
            if any(s in line for s in ALLOWED_OUTPUT_SUBSTRINGS):
                continue
            leaks.append(
                Leak(
                    file=str(file),
                    line=idx,
                    code=line.strip(),
                    reason="Dagster identifier in user-facing output — v4.1 §6.4 violated",
                )
            )
    return leaks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify no Dagster types leak past ctx (v4.1 §6.4).")
    parser.add_argument(
        "--scan-output",
        type=Path,
        default=None,
        help="Path to a CLI-output capture; greps for unmasked Dagster names.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON output.",
    )
    args = parser.parse_args(argv)

    import_roots = [REPO_ROOT / "src", REPO_ROOT / "tests", REPO_ROOT / "poc"]
    import_leaks = scan_imports(import_roots)
    litellm_leaks = scan_litellm_imports(import_roots)
    provider_string_leaks = scan_provider_strings_in_nucleus_errors(
        [REPO_ROOT / "src" / "nucleus"]
    )
    output_leaks = scan_output(args.scan_output) if args.scan_output else []
    leaks = import_leaks + litellm_leaks + provider_string_leaks + output_leaks

    if args.json:
        print(
            json.dumps(
                {
                    "leaks": [leak.__dict__ for leak in leaks],
                    "leak_count": len(leaks),
                },
                indent=2,
            )
        )
    elif not leaks:
        if not SRC_ROOT.exists():
            print("Dagster leak check: no src/nucleus yet — passes vacuously.")
        else:
            print(f"Dagster leak check: PASS ({len(import_roots)} roots scanned).")
    else:
        print(f"Dagster leak check: FAIL — {len(leaks)} violation(s) found:\n")
        for leak in leaks:
            print(f"  {leak.file}:{leak.line}")
            print(f"      {leak.code}")
            print(f"      reason: {leak.reason}\n")
        print("Move Dagster usage inside src/nucleus/coordination/ or remove it.")
        print("See nucleus_architecture_v4.1.md §6.4 and docs/architecture/sequence_error_translation.md.")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
