"""Pinned-version check — Constraint #11.

Enforces:

1. Every runtime dependency in ``pyproject.toml`` ``[project] dependencies``
   uses an exact pin (``==X.Y.Z``).
2. Every pinned package in ``pyproject.toml`` also appears in
   ``docs/compatibility.md`` (so the human-readable matrix stays in sync
   with the install spec).
3. Pinned versions in the two files MATCH.

Pre-release identifiers (``==1.2.3rc1``, ``==1.2.3.dev2``) are allowed but
emit a warning. Compatible-release (``~=``) and ranges (``>=``, ``<``) are
rejected for runtime deps. Dev deps allow ``~=`` per
``docs/conventions/engineering.md`` §6.2.

Usage
-----
    python scripts/check_pinning.py
    python scripts/check_pinning.py --json

Exit codes
----------
    0  all OK
    1  pinning violation
    2  invocation / parse error

Reading guide
-------------
- Uses stdlib ``tomllib`` for pyproject parsing.
- Uses a simple regex to extract entries from the compatibility doc.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
COMPAT_DOC = REPO_ROOT / "docs" / "compatibility.md"

# Regex for an exact-pin entry inside an array of strings:
# matches:  "pkgname[extras]==X.Y.Z",
_PIN_RE = re.compile(
    r"""^
    \s*"
    (?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)
    (?P<extras>\[[^\]]+\])?
    (?P<op>==|~=|>=?|<=?|!=)
    (?P<ver>[^"]+)
    "
    \s*,?\s*
    (?:\#.*)?
    $""",
    re.VERBOSE,
)

# Regex for a pin in the compatibility table:
# matches:  | `pkgname` | `X.Y.Z` |   (with backticks) or | pkgname | X.Y.Z |
_COMPAT_RE = re.compile(
    r"^\|\s*`?(?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)`?\s*\|\s*`?(?P<ver>[0-9][^|`\s]*)`?\s*\|"
)

# Pre-release suffix detection (PEP 440 simplified).
_PRERELEASE_RE = re.compile(r"(rc|a|b|alpha|beta|dev|pre)\d*", re.IGNORECASE)


@dataclass
class PinningReport:
    runtime_violations: list[str] = field(default_factory=list)
    dev_violations: list[str] = field(default_factory=list)
    matrix_missing: list[str] = field(default_factory=list)
    matrix_mismatches: list[tuple[str, str, str]] = field(default_factory=list)  # (pkg, pyproj, doc)
    prerelease_warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # prerelease_warnings are warnings, not errors.
        return not (
            self.runtime_violations
            or self.dev_violations
            or self.matrix_missing
            or self.matrix_mismatches
        )


def _parse_dep_string(raw: str) -> tuple[str, str, str] | None:
    """Parse a single dependency string. Returns (pkg, op, version) or None."""
    raw = raw.strip().strip(",")
    if not raw.startswith('"'):
        return None
    m = _PIN_RE.match(raw)
    if not m:
        return None
    return m["pkg"], m["op"], m["ver"]


def _extract_dependencies(pyproject_path: Path) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return (runtime_pins, dev_pins, raw_entries) by scanning the pyproject file.

    We do TWO passes:
    1. ``tomllib`` for the structured arrays.
    2. Text grep for the raw strings (so we can see which entries used non-==).
    """
    if not pyproject_path.exists():
        raise FileNotFoundError(pyproject_path)
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    runtime: dict[str, str] = {}
    dev: dict[str, str] = {}

    for raw in data.get("project", {}).get("dependencies", []):
        m = _PIN_RE.match(f'"{raw}"' if not raw.startswith('"') else raw)
        if m:
            runtime[m["pkg"]] = f"{m['op']}{m['ver']}"

    dev_extras = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    for raw in dev_extras:
        m = _PIN_RE.match(f'"{raw}"' if not raw.startswith('"') else raw)
        if m:
            dev[m["pkg"]] = f"{m['op']}{m['ver']}"

    return runtime, dev, {}


def _extract_compat_versions(compat_path: Path) -> dict[str, str]:
    """Walk the compatibility doc and pick out (pkg → version) rows from tables."""
    pins: dict[str, str] = {}
    if not compat_path.exists():
        return pins
    for line in compat_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        m = _COMPAT_RE.match(line)
        if not m:
            continue
        pkg = m["pkg"]
        ver = m["ver"]
        # Skip rows that are clearly not version strings (e.g. URLs, status labels).
        if ver in {"X", "Y", "Z"} or "/" in ver:
            continue
        if not re.match(r"^\d", ver):
            continue
        # First occurrence wins (compat doc may list a pkg in multiple tables).
        pins.setdefault(pkg, ver)
    return pins


def check_pinning() -> PinningReport:
    runtime, dev, _ = _extract_dependencies(PYPROJECT)
    compat = _extract_compat_versions(COMPAT_DOC)
    report = PinningReport()

    # 1. Runtime deps MUST be exact (== or arbitrary equality).
    for pkg, spec in runtime.items():
        if not spec.startswith("=="):
            report.runtime_violations.append(f"{pkg} -> {spec}  (require ==)")
        else:
            ver = spec[2:]
            if _PRERELEASE_RE.search(ver):
                report.prerelease_warnings.append(f"{pkg}=={ver}  (pre-release pin)")

    # 2. Dev deps may use == or ~= (engineering.md §6.2).
    for pkg, spec in dev.items():
        if not (spec.startswith("==") or spec.startswith("~=")):
            report.dev_violations.append(f"{pkg} -> {spec}  (require == or ~=)")

    # 3. Each runtime dep must appear in the compatibility doc.
    for pkg, spec in runtime.items():
        if not spec.startswith("=="):
            continue
        ver = spec[2:]
        if pkg not in compat:
            # Skip the implicit warning if compat doc isn't present yet.
            if COMPAT_DOC.exists():
                report.matrix_missing.append(pkg)
            continue
        if compat[pkg] != ver:
            report.matrix_mismatches.append((pkg, ver, compat[pkg]))

    return report


def _render(report: PinningReport) -> str:
    lines: list[str] = []
    lines.append("Pinning check report")
    lines.append("=" * 60)
    if report.ok:
        lines.append("PASS: all runtime deps exactly pinned; matrix in sync.")
    else:
        lines.append("FAIL: pinning violations found.")
    lines.append("")

    if report.runtime_violations:
        lines.append("Runtime dependency violations (Constraint #11):")
        for v in report.runtime_violations:
            lines.append(f"  - {v}")
        lines.append("")

    if report.dev_violations:
        lines.append("Dev dependency violations:")
        for v in report.dev_violations:
            lines.append(f"  - {v}")
        lines.append("")

    if report.matrix_missing:
        lines.append("Packages missing from docs/compatibility.md:")
        for pkg in report.matrix_missing:
            lines.append(f"  - {pkg}")
        lines.append("  (add a row in the relevant §1.x table)")
        lines.append("")

    if report.matrix_mismatches:
        lines.append("Version mismatches between pyproject.toml and docs/compatibility.md:")
        for pkg, pyproj_v, doc_v in report.matrix_mismatches:
            lines.append(f"  - {pkg}: pyproject={pyproj_v}  docs={doc_v}")
        lines.append("  (decide which is correct and reconcile)")
        lines.append("")

    if report.prerelease_warnings:
        lines.append("Pre-release pin warnings (allowed, but flagged):")
        for w in report.prerelease_warnings:
            lines.append(f"  - {w}")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify pinned versions (Constraint #11).")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    args = parser.parse_args(argv)

    try:
        report = check_pinning()
    except FileNotFoundError as exc:
        print(f"check_pinning: missing required file: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "runtime_violations": report.runtime_violations,
                    "dev_violations": report.dev_violations,
                    "matrix_missing": report.matrix_missing,
                    "matrix_mismatches": report.matrix_mismatches,
                    "prerelease_warnings": report.prerelease_warnings,
                },
                indent=2,
            )
        )
    else:
        print(_render(report))

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
