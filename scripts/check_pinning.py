"""Pinned-version check -- Hard Constraint #11 (AGENTS.md Sec 11.13).

Enforces (in order of severity):

1. Every runtime dep in ``pyproject.toml`` ``[project] dependencies`` uses an
   exact pin (``==X.Y.Z``). This is the canonical install spec the
   ADR-012 Runtime pin matrix is derived from.
2. Every entry under a *runtime extras* group in
   ``[project.optional-dependencies]`` (``observability``,
   ``lineage-advanced``; see ``RUNTIME_EXTRAS_GROUPS`` below) is also pinned
   with ``==``, exactly as for ``[project] dependencies``. These are real
   runtime libraries that simply ship behind an opt-in install (e.g.
   ``pip install nucleus[observability]``); they are not contributor
   tooling. Source: ADR-012 amendment 2026-05-14 +
   ``docs/research/otel_day1_decision.md`` Option α-split.
3. Every entry across every other ``[project.optional-dependencies]`` table
   (``dev``, ``docs``, future contributor-tooling extras) is also pinned. By
   default, those deps may use compatible-release (``~=``) since minor-flex
   on linters and test runners is benign; ``--strict`` disables that.
4. Each pinned runtime package (core or runtime-extras) appears in
   ``docs/compatibility.md`` and the pinned version matches (keeps the
   human-readable matrix in sync with the install spec; ADR-012 calls
   ``compatibility.md`` the derived view).

Loose-pin exemption
-------------------
Loose pins (``>=``, ``<=``, ``>``, ``<``, ``!=``, or ``~=`` outside
dev/extras) are allowed ONLY when the same source line in
``pyproject.toml`` carries an inline ``# loose-allowed: <reason>``
comment. Example::

    "pytest>=8.0",  # loose-allowed: dev tool, plugin compat surface

Each exemption is recorded in the human + JSON report. ``--strict``
upgrades EVERY exemption (inline + the default dev ``~=`` allowance) to
a violation; this is the intended CI default once v0.1 ships.

Pre-release identifiers (``==1.2.3rc1``, ``==1.2.3.dev2``) are allowed
but emit a warning -- pre-release pins are a release-blocker hazard.

Companion script
----------------
``scripts/upgrade_smoke.py`` runs the broader upgrade-gate workflow
(pin validation + ADR-012 cross-check + pytest + license tier + LOC
budget); this script is the narrow, fast pin-validation step that
gate relies on. Exit codes here are stable so upgrade_smoke can rely on
them.

Usage
-----
    python scripts/check_pinning.py
    python scripts/check_pinning.py --json
    python scripts/check_pinning.py --strict
    python scripts/check_pinning.py --help

Exit codes
----------
    0  all OK (clean, or every loose pin carries a ``# loose-allowed:``
       exemption and ``--strict`` is not set)
    1  pinning violation (loose pin without exemption, missing matrix
       row, or version mismatch between pyproject.toml and
       docs/compatibility.md)
    2  invocation / parse error (pyproject.toml unreadable / malformed)

Docs:
    AGENTS.md Sec 11.13 (Hard Constraint #11)
    docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md
    docs/compatibility.md
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

# Runtime-extras groups: opt-in install buckets (e.g. `pip install
# nucleus[observability]`) that ship real runtime libraries -- not
# contributor tooling. Same exact-pin discipline as `[project]
# dependencies`. Source: ADR-012 amendment 2026-05-14 +
# `docs/research/otel_day1_decision.md` Option alpha-split.
#
# Add a group name here only when the extras row carries runtime semantics.
# Linters / test runners / docs generators stay outside this set so their
# `~=` flexibility (default mode) is preserved.
RUNTIME_EXTRAS_GROUPS: frozenset[str] = frozenset({
    "observability",
    "lineage-advanced",
    "snowflake",   # dlt[snowflake]==1.26.0 — ADR-019 connector expansion 2026-05-15
    "gcs",         # gcsfs==2026.5.0 — ADR-020 connector expansion 2026-05-15
})

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

# Regex for a pin in the compatibility table. Handles:
#   | `pkgname`                   | `X.Y.Z` |              (§1 runtime layout)
#   | pkgname                     | X.Y.Z   |
#   | `pkgname[extra1,extra2]`    | `X.Y.Z` |              (extras stripped from pkg group)
_COMPAT_RE = re.compile(
    r"^\|\s*`?(?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)(?:\[[^\]]+\])?`?\s*\|"
    r"\s*`?(?P<ver>[0-9][^|`\s]*)`?\s*\|"
)

# Second compat-row layout used by §2 (`[project.optional-dependencies]`):
#   | `pkgname` | extras-group-name | `X.Y.Z` | License ... |
# Version sits in the third pipe-delimited cell; the second cell is the
# group name (alphabetic, non-numeric -- so the §1 regex above misses it).
# Added 2026-05-14 alongside the runtime-extras tier (ADR-012 amendment).
_COMPAT_RE_EXTRAS = re.compile(
    r"^\|\s*`?(?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)(?:\[[^\]]+\])?`?\s*\|"
    r"\s*[a-zA-Z][a-zA-Z0-9_\-]*\s*\|"
    r"\s*`?(?P<ver>[0-9][^|`\s]*)`?\s*\|"
)

# Pre-release suffix detection (PEP 440 simplified).
_PRERELEASE_RE = re.compile(r"(rc|a|b|alpha|beta|dev|pre)\d*", re.IGNORECASE)

# Inline exemption: a loose pin is allowed when the same source line in
# pyproject.toml carries `# loose-allowed: <reason>`. We scan raw lines
# because tomllib drops comments; correlation is by package name.
_LOOSE_ALLOWED_RE = re.compile(
    r"""^
    \s*"\s*
    (?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)
    (?:\[[^\]]+\])?
    (?:==|~=|>=?|<=?|!=)[^"]+"
    \s*,?\s*
    \#\s*loose-allowed:
    """,
    re.VERBOSE,
)


@dataclass
class PinningReport:
    runtime_violations: list[str] = field(default_factory=list)
    runtime_extras_violations: list[str] = field(default_factory=list)
    dev_violations: list[str] = field(default_factory=list)
    matrix_missing: list[str] = field(default_factory=list)
    matrix_mismatches: list[tuple[str, str, str]] = field(default_factory=list)  # (pkg, pyproj, doc)
    prerelease_warnings: list[str] = field(default_factory=list)
    exemptions_used: list[str] = field(default_factory=list)  # loose-allowed pins
    # Counts for the summary line; populated by check_pinning().
    mandatory_pin_count: int = 0
    runtime_extras_pin_count: int = 0
    dev_pin_count: int = 0

    @property
    def ok(self) -> bool:
        # prerelease_warnings + exemptions_used are informational, not errors.
        return not (
            self.runtime_violations
            or self.runtime_extras_violations
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


def _extract_dependencies(
    pyproject_path: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Return ``(runtime, runtime_extras, dev, raw_entries)`` from the pyproject.

    Three pin buckets:

    * ``runtime``        -- ``[project] dependencies`` (always ``==`` required).
    * ``runtime_extras`` -- entries inside any ``[project.optional-dependencies]``
      group whose name is in ``RUNTIME_EXTRAS_GROUPS`` (always ``==`` required;
      runtime libraries that just happen to ship behind an opt-in install).
    * ``dev``            -- entries inside every other extras group
      (``dev``, ``docs``, future contributor tooling); ``==`` always OK and
      ``~=`` accepted unless ``--strict``.

    A single package collisioning across two buckets keeps both rows so the
    output is honest, but the matrix-rule cross-check uses the strictest one.
    """
    if not pyproject_path.exists():
        raise FileNotFoundError(pyproject_path)
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    runtime: dict[str, str] = {}
    runtime_extras: dict[str, str] = {}
    dev: dict[str, str] = {}

    for raw in data.get("project", {}).get("dependencies", []):
        m = _PIN_RE.match(f'"{raw}"' if not raw.startswith('"') else raw)
        if m:
            runtime[m["pkg"]] = f"{m['op']}{m['ver']}"

    # Walk every [project.optional-dependencies] subtable. Split into runtime
    # extras (RUNTIME_EXTRAS_GROUPS) vs dev/docs (everything else).
    # Meta-extras like `all = ["nucleus[dev,docs]"]` do not match _PIN_RE
    # (no version operator) and are silently skipped.
    extras = data.get("project", {}).get("optional-dependencies", {})
    for group_name, raw_deps in extras.items():
        bucket = runtime_extras if group_name in RUNTIME_EXTRAS_GROUPS else dev
        for raw in raw_deps:
            m = _PIN_RE.match(f'"{raw}"' if not raw.startswith('"') else raw)
            if m:
                bucket[m["pkg"]] = f"{m['op']}{m['ver']}"

    return runtime, runtime_extras, dev, {}


def _extract_compat_versions(compat_path: Path) -> dict[str, str]:
    """Walk the compatibility doc and pick out (pkg → version) rows from tables.

    Tries the §1 runtime layout first (``| pkg | ver | …``) and the §2
    extras layout second (``| pkg | extras-group | ver | …``). First
    occurrence wins so a pkg listed in both tables resolves to the §1 row.
    """
    pins: dict[str, str] = {}
    if not compat_path.exists():
        return pins
    for line in compat_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        m = _COMPAT_RE.match(line) or _COMPAT_RE_EXTRAS.match(line)
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


def _extract_exemptions(pyproject_path: Path) -> set[str]:
    """Return packages with `# loose-allowed: <reason>` on their decl line."""
    if not pyproject_path.exists():
        return set()
    out: set[str] = set()
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        m = _LOOSE_ALLOWED_RE.match(line)
        if m:
            out.add(m["pkg"])
    return out


def _record_runtime_rules(
    runtime: dict[str, str],
    exemptions: set[str],
    strict: bool,
    report: PinningReport,
    *,
    label: str = "runtime",
    bucket: list[str] | None = None,
) -> None:
    """Exact-pin (``==``) discipline for the given runtime bucket.

    ``label`` is the human-readable bucket name surfaced in violation rows
    and exemption rows (``runtime``, ``runtime extras``, ...). ``bucket``
    selects which violation list on the report receives the failures; when
    ``None`` the report's ``runtime_violations`` is used to preserve the
    pre-extras call signature.
    """
    sink = report.runtime_violations if bucket is None else bucket
    for pkg, spec in runtime.items():
        if not spec.startswith("=="):
            if pkg in exemptions and not strict:
                report.exemptions_used.append(f"{pkg}{spec}  ({label}; loose-allowed)")
                continue
            sink.append(f"{pkg} -> {spec}  ({label}; require ==)")
        else:
            ver = spec[2:]
            if _PRERELEASE_RE.search(ver):
                report.prerelease_warnings.append(f"{pkg}=={ver}  ({label}; pre-release pin)")


def _record_dev_rules(
    dev: dict[str, str],
    exemptions: set[str],
    strict: bool,
    report: PinningReport,
) -> None:
    """Dev / extras: == always OK; ~= OK in default mode unless --strict."""
    for pkg, spec in dev.items():
        ok_default = spec.startswith("==") or (spec.startswith("~=") and not strict)
        if ok_default:
            continue
        if pkg in exemptions and not strict:
            report.exemptions_used.append(f"{pkg}{spec}  (extras; loose-allowed)")
            continue
        requirement = "require ==" if strict else "require == or ~="
        report.dev_violations.append(f"{pkg} -> {spec}  ({requirement})")


def _record_matrix_rules(
    runtime: dict[str, str],
    compat: dict[str, str],
    report: PinningReport,
) -> None:
    """Each pinned runtime dep must match docs/compatibility.md (ADR-012).

    Accepts the union of core runtime + runtime-extras pins -- both tiers
    are tracked in the compatibility matrix per ADR-012 amendment 2026-05-14.
    """
    for pkg, spec in runtime.items():
        if not spec.startswith("=="):
            continue
        ver = spec[2:]
        if pkg not in compat:
            if COMPAT_DOC.exists():
                report.matrix_missing.append(pkg)
            continue
        if compat[pkg] != ver:
            report.matrix_mismatches.append((pkg, ver, compat[pkg]))


def check_pinning(strict: bool = False) -> PinningReport:
    """Run the pin-validation gate. ``strict`` disables every exemption."""
    runtime, runtime_extras, dev, _ = _extract_dependencies(PYPROJECT)
    compat = _extract_compat_versions(COMPAT_DOC)
    exemptions = _extract_exemptions(PYPROJECT)
    report = PinningReport(
        mandatory_pin_count=len(runtime),
        runtime_extras_pin_count=len(runtime_extras),
        dev_pin_count=len(dev),
    )
    _record_runtime_rules(runtime, exemptions, strict, report)
    _record_runtime_rules(
        runtime_extras,
        exemptions,
        strict,
        report,
        label="runtime extras",
        bucket=report.runtime_extras_violations,
    )
    _record_dev_rules(dev, exemptions, strict, report)
    # Matrix-rule covers both core + runtime-extras (both tracked in
    # docs/compatibility.md per ADR-012 amendment 2026-05-14).
    matrix_runtime = {**runtime, **runtime_extras}
    _record_matrix_rules(matrix_runtime, compat, report)
    return report


def _append_bullet_block(lines: list[str], title: str, bullets: list[str]) -> None:
    if not bullets:
        return
    lines.append(title)
    lines.extend(f"  - {b}" for b in bullets)
    lines.append("")


def _render(report: PinningReport) -> str:
    summary_counts = (
        f"  Tracked: {report.mandatory_pin_count} mandatory pins, "
        f"{report.runtime_extras_pin_count} optional-runtime pins "
        f"({', '.join(sorted(RUNTIME_EXTRAS_GROUPS))}), "
        f"{report.dev_pin_count} dev/docs pins."
    )
    lines: list[str] = [
        "Pinning check report",
        "=" * 60,
        (
            "PASS: all runtime + runtime-extras deps exactly pinned; matrix in sync."
            if report.ok
            else "FAIL: pinning violations found."
        ),
        summary_counts,
        "",
    ]

    _append_bullet_block(
        lines,
        "Runtime dependency violations (Constraint #11):",
        report.runtime_violations,
    )
    _append_bullet_block(
        lines,
        "Runtime-extras dependency violations (ADR-012 amendment 2026-05-14):",
        report.runtime_extras_violations,
    )
    _append_bullet_block(lines, "Dev dependency violations:", report.dev_violations)

    if report.matrix_missing:
        lines.append("Packages missing from docs/compatibility.md:")
        lines.extend(f"  - {pkg}" for pkg in report.matrix_missing)
        lines.extend([
            "  (add a row in the relevant Sec 1.x table of docs/compatibility.md)",
            "",
        ])

    if report.matrix_mismatches:
        lines.append("Version mismatches between pyproject.toml and docs/compatibility.md:")
        lines.extend(
            f"  - {pkg}: pyproject={pyproj_v}  docs={doc_v}"
            for pkg, pyproj_v, doc_v in report.matrix_mismatches
        )
        lines.extend(["  (decide which is correct and reconcile)", ""])

    _append_bullet_block(
        lines,
        "Pre-release pin warnings (allowed, but flagged):",
        report.prerelease_warnings,
    )

    if report.exemptions_used:
        lines.append("Loose-pin exemptions accepted (`# loose-allowed:`):")
        lines.extend(f"  - {e}" for e in report.exemptions_used)
        lines.extend([
            "  (re-run with --strict to upgrade exemptions to violations)",
            "",
        ])

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify exact pinning of runtime + extras dependencies "
            "(AGENTS.md Sec 11.13 / Hard Constraint #11)."
        ),
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of the human report.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help=(
            "Disable every exemption: require == on EVERY dep "
            "(runtime + extras), reject the dev `~=` allowance, "
            "and treat every `# loose-allowed:` exemption as a violation. "
            "Use this in CI once v0.1 ships."
        ),
    )
    args = parser.parse_args(argv)

    try:
        report = check_pinning(strict=args.strict)
    except FileNotFoundError as exc:
        print(f"check_pinning: missing required file: {exc}", file=sys.stderr)
        return 2
    except tomllib.TOMLDecodeError as exc:
        print(f"check_pinning: malformed pyproject.toml: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "strict": args.strict,
                    "mandatory_pin_count": report.mandatory_pin_count,
                    "runtime_extras_pin_count": report.runtime_extras_pin_count,
                    "runtime_extras_groups": sorted(RUNTIME_EXTRAS_GROUPS),
                    "dev_pin_count": report.dev_pin_count,
                    "runtime_violations": report.runtime_violations,
                    "runtime_extras_violations": report.runtime_extras_violations,
                    "dev_violations": report.dev_violations,
                    "matrix_missing": report.matrix_missing,
                    "matrix_mismatches": report.matrix_mismatches,
                    "prerelease_warnings": report.prerelease_warnings,
                    "exemptions_used": report.exemptions_used,
                },
                indent=2,
            )
        )
    else:
        print(_render(report))

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
