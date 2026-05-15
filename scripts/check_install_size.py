"""Install-size guard --- ADR-039 PoC #5 install-size split.

Enforces a hard ceiling on the number of entries in
``pyproject.toml`` ``[project.dependencies]`` so the default
``pip install nucleus`` invocation stays inside the
beachhead 30-minute target (PoC #5 feedback: 6 minutes / 100+
transitive deps was an evaluation killer).

Rules
-----
1. Total entries in ``[project.dependencies]`` MUST be ``<= MAX_CORE_DEPS``
   (default 30 -- override via ``--max=N`` for emergency relief but
   record the override in an ADR).
2. Each entry MUST be an exact pin (``==``). This is also enforced
   by ``scripts/check_pinning.py``; we double-check here so a stale
   pyproject can't bypass the install-size budget by loosening pins.
3. Every entry under a ``RUNTIME_EXTRAS_GROUPS`` extras group (defined
   in ``scripts/check_pinning.py``) MUST also use ``==``; same reason.
4. The ``all`` meta-group MUST self-reference (i.e. contain a
   ``nucleus[...]`` entry) so ``pip install nucleus[all]`` resolves
   the named runtime extras as a single transaction.

Exit codes
----------
0  -- core <= MAX_CORE_DEPS, every entry exactly pinned, ``all``
      meta-group well-formed.
1  -- budget exceeded OR pinning violation OR ``all`` meta-group
      malformed.
2  -- invocation / parse error (pyproject.toml unreadable / malformed).

Usage
-----
    python scripts/check_install_size.py
    python scripts/check_install_size.py --json
    python scripts/check_install_size.py --max=25  # tighter local budget

Docs
----
* ADR-039 (this PR) -- ``docs/decisions/ADR-039-install-size-split.md``
* AGENTS.md Sec 11.13 (exact-pin discipline)
* PEP 621 ``[project.optional-dependencies]`` -- https://peps.python.org/pep-0621/
* PEP 508 extras self-reference (``nucleus[a,b]``) -- https://peps.python.org/pep-0508/
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

# Default ceiling per ADR-039. Lower than the PoC #5 empirical floor on
# transitive-resolved package count (which is ~25 today) so an addition
# of a new core dep triggers an explicit ADR amendment instead of silent
# drift.
DEFAULT_MAX_CORE_DEPS: int = 30

# Self-reference regex: ``nucleus[postgres,ai,...]``.
_SELF_REF_RE = re.compile(r"^nucleus\s*\[\s*[a-zA-Z][a-zA-Z0-9_,\-\s]*\]\s*$")

# Pin regex (mirrors check_pinning.py but only cares about the operator).
_PIN_RE = re.compile(
    r"""^
    (?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)
    (?P<extras>\[[^\]]+\])?
    (?P<op>==|~=|>=?|<=?|!=)
    (?P<ver>.+)
    $""",
    re.VERBOSE,
)


@dataclass
class InstallSizeReport:
    core_count: int = 0
    core_limit: int = DEFAULT_MAX_CORE_DEPS
    core_entries: list[str] = field(default_factory=list)
    extras_entries: dict[str, list[str]] = field(default_factory=dict)
    core_loose_pins: list[str] = field(default_factory=list)
    extras_loose_pins: list[str] = field(default_factory=list)
    all_meta_ok: bool = True
    all_meta_value: list[str] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def ok(self) -> bool:
        if self.parse_error is not None:
            return False
        return (
            self.core_count <= self.core_limit
            and not self.core_loose_pins
            and not self.extras_loose_pins
            and self.all_meta_ok
        )

    @property
    def budget_breach(self) -> bool:
        return self.core_count > self.core_limit


def _classify(entry: str) -> tuple[str, str] | None:
    """Return ``(pkg, op)`` for a dep entry, or None if not parseable."""
    raw = entry.strip()
    if not raw:
        return None
    m = _PIN_RE.match(raw)
    if not m:
        return None
    return m["pkg"], m["op"]


def check_install_size(max_core: int = DEFAULT_MAX_CORE_DEPS) -> InstallSizeReport:
    report = InstallSizeReport(core_limit=max_core)
    try:
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.parse_error = f"missing pyproject.toml at {PYPROJECT}"
        return report
    except tomllib.TOMLDecodeError as exc:
        report.parse_error = f"malformed pyproject.toml: {exc}"
        return report

    project = data.get("project", {})
    core_deps: list[str] = list(project.get("dependencies", []))
    report.core_count = len(core_deps)
    report.core_entries = core_deps

    for entry in core_deps:
        classified = _classify(entry)
        if classified is None:
            continue
        pkg, op = classified
        if op != "==":
            report.core_loose_pins.append(f"{pkg}{op}... ({entry!r})")

    extras = project.get("optional-dependencies", {})
    for group_name, entries in extras.items():
        report.extras_entries[group_name] = list(entries)

    # Extras pin discipline applies to RUNTIME extras only. We mirror the
    # set from check_pinning.py instead of importing it -- this script
    # stays standalone so CI can invoke it without a configured PYTHONPATH.
    runtime_extras_groups = frozenset(
        {
            "observability",
            "lineage-advanced",
            "snowflake",
            "gcs",
            "postgres",
            "mysql",
            "s3",
            "ai",
            "workbench",
        }
    )
    for group_name in runtime_extras_groups:
        for entry in report.extras_entries.get(group_name, []):
            classified = _classify(entry)
            if classified is None:
                continue
            pkg, op = classified
            if op != "==":
                report.extras_loose_pins.append(
                    f"[{group_name}] {pkg}{op}... ({entry!r}; runtime extras must pin)"
                )

    # `all` meta-group must self-reference so `pip install nucleus[all]`
    # resolves every runtime extras in one transaction.
    all_entries = report.extras_entries.get("all", [])
    report.all_meta_value = list(all_entries)
    if not all_entries:
        report.all_meta_ok = False
    elif not any(_SELF_REF_RE.match(e.strip()) for e in all_entries):
        report.all_meta_ok = False

    return report


def _render(report: InstallSizeReport, max_core: int) -> str:
    if report.parse_error:
        return f"check_install_size: {report.parse_error}\n"
    lines: list[str] = [
        "Install-size check (ADR-039)",
        "=" * 60,
        (
            f"PASS: [project.dependencies] = {report.core_count} entries (limit {max_core})."
            if report.ok
            else f"FAIL: budget or pinning violation."
        ),
        f"  core entries  : {report.core_count} / {max_core}",
        f"  extras groups : {', '.join(sorted(report.extras_entries.keys())) or '(none)'}",
        "",
    ]
    if report.budget_breach:
        lines.append(
            f"BUDGET BREACH: [project.dependencies] has {report.core_count} entries "
            f"but the ADR-039 ceiling is {max_core}. Move runtime libs into an "
            f"existing or new [project.optional-dependencies] group, or amend "
            f"ADR-039 with empirical install-time evidence justifying the bump."
        )
        lines.append("Current core entries:")
        lines.extend(f"  - {e}" for e in report.core_entries)
        lines.append("")
    if report.core_loose_pins:
        lines.append("Loose pins in core (must be ==):")
        lines.extend(f"  - {p}" for p in report.core_loose_pins)
        lines.append("")
    if report.extras_loose_pins:
        lines.append("Loose pins in runtime extras (must be ==):")
        lines.extend(f"  - {p}" for p in report.extras_loose_pins)
        lines.append("")
    if not report.all_meta_ok:
        lines.append(
            "`all` meta-group malformed: expected a single `nucleus[...]` "
            "self-reference entry per PEP 508 extras, got: "
            f"{report.all_meta_value!r}"
        )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ADR-039 install-size guard: assert [project.dependencies] "
            "<= N entries and every runtime pin uses ==."
        )
    )
    parser.add_argument(
        "--max",
        dest="max_core",
        type=int,
        default=DEFAULT_MAX_CORE_DEPS,
        help=(
            "Maximum entries allowed in [project.dependencies] "
            f"(default {DEFAULT_MAX_CORE_DEPS}; record overrides in an ADR)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args(argv)

    report = check_install_size(max_core=args.max_core)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "parse_error": report.parse_error,
                    "core_count": report.core_count,
                    "core_limit": report.core_limit,
                    "budget_breach": report.budget_breach,
                    "core_loose_pins": report.core_loose_pins,
                    "extras_loose_pins": report.extras_loose_pins,
                    "all_meta_ok": report.all_meta_ok,
                    "extras_groups": sorted(report.extras_entries.keys()),
                },
                indent=2,
            )
        )
    else:
        print(_render(report, args.max_core))

    if report.parse_error:
        return 2
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
