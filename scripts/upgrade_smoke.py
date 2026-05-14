"""Upgrade safety smoke test for Nucleus dependency upgrade PRs.

Per AGENTS.md Sec 11.13 (Hard Constraint #11): every dependency upgrade
PR must pass this script before merge.

Validates (in order):
    1. Pin validation -- every runtime dep uses exact pinning (``==X.Y.Z``)
       and never a range / compatible-release operator (Sec 11.13).
    2. ADR-012 cross-check -- ``pyproject.toml`` matches the canonical
       Runtime pin matrix in
       ``docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md``.
    3. ``pytest -x --tb=short`` -- the bedrock gate from Sec 11.13.
    4. Optional gates if their helper scripts exist:
       beachhead E2E (Sec 11.8), benchmark regression (Sec 11.13),
       license-tier check (ADR-007 + Sec 11.13), LOC budget (Sec 11.6).

This script is intentionally stdlib-only (``argparse``, ``dataclasses``,
``json``, ``re``, ``subprocess``, ``sys``, ``time``, ``tomllib``,
``pathlib``); it runs unchanged on Windows, Linux, and macOS.

Usage
-----
    python scripts/upgrade_smoke.py
    python scripts/upgrade_smoke.py --json
    python scripts/upgrade_smoke.py --strict

Exit codes
----------
    0   all gates passed
    1   pytest failed (the bedrock gate)
    2   pin validation failed (loose pin found)
    3   ADR-012 drift detected
    4   license tier violation
    5   any other gate failed (beachhead, benchmark, LOC)

When multiple gates fail, the first failure encountered in gate
execution order determines the exit code; the human and JSON reports
list every failure.

Companion docs
--------------
    AGENTS.md Sec 11.13 (Upgrade Safety Discipline)
    docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md
    docs/compatibility.md
    scripts/check_pinning.py (complement; this script does NOT duplicate it)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
ADR_012 = REPO_ROOT / "docs" / "decisions" / "ADR-012-runtime-dependency-pin-matrix-v01.md"
SCRIPTS_DIR = REPO_ROOT / "scripts"

EXIT_OK = 0
EXIT_PYTEST = 1
EXIT_PIN = 2
EXIT_ADR_DRIFT = 3
EXIT_LICENSE = 4
EXIT_OTHER = 5

_MAX_MSG_LEN = 200

# PEP-508-simplified dep parser: matches ``pkg[extras]<op><version>``.
_DEP_RE = re.compile(
    r"^(?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)"
    r"(?P<extras>\[[^\]]+\])?"
    r"(?P<op>==|~=|>=?|<=?|!=)"
    r"(?P<ver>[^,;\s]+)"
)

# ADR-012 markdown row parser: matches `pkg[extras]==X.Y.Z` (with optional backticks).
_ADR_PIN_RE = re.compile(
    r"`?([a-zA-Z][a-zA-Z0-9_.\-]*)(?:\[[^\]]+\])?==([^`\s|]+)`?"
)


@dataclass
class Gate:
    """One check executed by the upgrade smoke harness.

    ``passed`` is ``True`` (gate ran and succeeded), ``False`` (gate ran
    and failed), or ``None`` (gate was skipped because its prerequisite
    -- e.g., a helper script -- is absent). ``exit_code_on_fail`` is
    used by :func:`main` when this gate is the first failure.
    """

    name: str
    passed: bool | None
    message: str = ""
    duration_ms: int = 0
    exit_code_on_fail: int = EXIT_OTHER


def _parse_dep(raw: str) -> tuple[str, str, str] | None:
    """Parse a dep string. Return ``(pkg, op, version)`` or ``None``."""
    m = _DEP_RE.match(raw.strip())
    return (m["pkg"], m["op"], m["ver"]) if m else None


def parse_pyproject_pins(path: Path) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return ``(runtime, dev, runtime_extras)`` where each dict is ``pkg -> raw spec``.

    ``runtime_extras`` spans ADR-012 optional-runtime groups
    (``observability``, ``lineage-advanced``) — exact-pinned like core
    per ``check_pinning.py`` / ADR-012 amendment 2026-05-14.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    proj = data.get("project", {})
    runtime: dict[str, str] = {}
    dev: dict[str, str] = {}
    runtime_extras: dict[str, str] = {}
    for raw in proj.get("dependencies", []):
        parsed = _parse_dep(raw)
        if parsed:
            pkg, op, ver = parsed
            runtime[pkg] = f"{op}{ver}"
    opt = proj.get("optional-dependencies", {}) or {}
    for raw in opt.get("dev", []):
        parsed = _parse_dep(raw)
        if parsed:
            pkg, op, ver = parsed
            dev[pkg] = f"{op}{ver}"
    for group in ("observability", "lineage-advanced"):
        for raw in opt.get(group, []):
            parsed = _parse_dep(raw)
            if parsed:
                pkg, op, ver = parsed
                runtime_extras[pkg] = f"{op}{ver}"
    return runtime, dev, runtime_extras


def parse_adr_012_pins(path: Path) -> dict[str, str]:
    """Extract exact pins from the ADR-012 Runtime pin matrix table.

    Skips the Python floor (``>=3.11,<3.13``), transitive entries
    (``transitive via ...``), and every section other than
    ``### Runtime pin matrix``.
    """
    if not path.exists():
        return {}
    pins: dict[str, str] = {}
    in_runtime_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### Runtime pin matrix"):
            in_runtime_section = True
            continue
        if in_runtime_section and line.startswith("###"):
            in_runtime_section = False
            continue
        if not in_runtime_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        component = cells[0].strip("`")
        if component.lower() in {"component", ""} or set(component) <= {"-", " "}:
            continue
        m = _ADR_PIN_RE.search(cells[1])
        if m:
            pins[m.group(1)] = m.group(2)
    return pins


def gate_pin_validation() -> Gate:
    """Verify every runtime dep uses ``==X.Y.Z`` (AGENTS.md Sec 11.13)."""
    t0 = time.monotonic()
    try:
        runtime, _dev, _rx = parse_pyproject_pins(PYPROJECT)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Gate(
            "pin_validation", False,
            f"cannot read {PYPROJECT.name}: {exc}",
            int((time.monotonic() - t0) * 1000), EXIT_PIN,
        )
    violations = [f"{p}{s}" for p, s in runtime.items() if not s.startswith("==")]
    elapsed = int((time.monotonic() - t0) * 1000)
    if violations:
        return Gate(
            "pin_validation", False,
            f"{len(violations)} loose pin(s): " + ", ".join(violations[:5]),
            elapsed, EXIT_PIN,
        )
    return Gate(
        "pin_validation", True,
        f"{len(runtime)} runtime deps exact-pinned",
        elapsed,
    )


def gate_adr_012_cross_check() -> Gate:
    """Confirm ``pyproject.toml`` matches the ADR-012 pin matrix.

    Drift is a release blocker per AGENTS.md Sec 11.13: ADR-012 is the
    canonical pin matrix, and ``pyproject.toml`` is the install spec
    that must derive from it.
    """
    t0 = time.monotonic()
    if not ADR_012.exists():
        return Gate(
            "adr_012_cross_check", None,
            f"{ADR_012.name} not present; skipping",
            int((time.monotonic() - t0) * 1000),
        )
    try:
        runtime, _dev, runtime_extras = parse_pyproject_pins(PYPROJECT)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Gate(
            "adr_012_cross_check", False,
            f"cannot read pyproject: {exc}",
            int((time.monotonic() - t0) * 1000), EXIT_ADR_DRIFT,
        )
    adr = parse_adr_012_pins(ADR_012)
    merged = {**runtime, **runtime_extras}
    pyp = {p: s[2:] for p, s in merged.items() if s.startswith("==")}

    missing_in_pyproject = sorted(set(adr) - set(pyp))
    missing_in_adr = sorted(set(pyp) - set(adr))
    mismatch = [(p, pyp[p], adr[p]) for p in set(adr) & set(pyp) if adr[p] != pyp[p]]
    elapsed = int((time.monotonic() - t0) * 1000)

    if not (missing_in_pyproject or missing_in_adr or mismatch):
        return Gate(
            "adr_012_cross_check", True,
            f"pyproject.toml matches ADR-012 ({len(pyp)} pins compared)",
            elapsed,
        )
    parts: list[str] = []
    if missing_in_pyproject:
        parts.append(f"in ADR-012 but not pyproject: {', '.join(missing_in_pyproject)}")
    if missing_in_adr:
        parts.append(f"in pyproject but not ADR-012: {', '.join(missing_in_adr)}")
    if mismatch:
        parts.append("version mismatches: " + "; ".join(
            f"{p} (pyproject={pp}, ADR={ap})" for p, pp, ap in mismatch
        ))
    return Gate(
        "adr_012_cross_check", False,
        " | ".join(parts)[:_MAX_MSG_LEN],
        elapsed, EXIT_ADR_DRIFT,
    )


def _utf8_env() -> dict[str, str]:
    """Force ``PYTHONIOENCODING=utf-8`` so child Pythons write UTF-8.

    Without this, child processes on Windows write cp1252 to their
    stdout pipe and we cannot round-trip non-ASCII (e.g., ``§``).
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(args: list[str]) -> tuple[int, str]:
    """Invoke a subprocess; return ``(exit_code, last-non-empty-line)``.

    UTF-8 is forced for both stdout and stderr capture so Windows
    consoles (default cp1252) do not garble non-ASCII output from
    wrapped scripts. Output is truncated to ``_MAX_MSG_LEN`` chars.
    ``shell=True`` is never used (cross-platform safety).
    """
    try:
        proc = subprocess.run(
            args, cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", env=_utf8_env(),
        )
    except FileNotFoundError as exc:
        return 127, f"command not found: {exc}"
    combined = (proc.stdout or "") + (proc.stderr or "")
    last = next((ln for ln in reversed(combined.splitlines()) if ln.strip()), "")
    return proc.returncode, last[:_MAX_MSG_LEN]


def gate_pytest() -> Gate:
    """Run ``pytest -x --tb=short`` -- bedrock gate (AGENTS.md Sec 11.13)."""
    t0 = time.monotonic()
    exit_code, last = _run([sys.executable, "-m", "pytest", "-x", "--tb=short"])
    return Gate(
        "pytest", exit_code == 0,
        last or f"exit={exit_code}",
        int((time.monotonic() - t0) * 1000), EXIT_PYTEST,
    )


def gate_optional(name: str, filename: str, fail_code: int = EXIT_OTHER) -> Gate:
    """Run an optional helper script; skip cleanly if its file is absent."""
    t0 = time.monotonic()
    path = SCRIPTS_DIR / filename
    if not path.exists():
        return Gate(
            name, None,
            f"scripts/{filename} not present; skipping",
            int((time.monotonic() - t0) * 1000),
        )
    exit_code, last = _run([sys.executable, str(path)])
    return Gate(
        name, exit_code == 0,
        last or f"exit={exit_code}",
        int((time.monotonic() - t0) * 1000), fail_code,
    )


def gate_loc_budget() -> Gate:
    """Parse ``loc_budget.py --json``; fail when verdict is ``RED``.

    loc_budget always exits 0 (informational), so we inspect its JSON
    payload directly. AGENTS.md Sec 11.6 hard-ceils proprietary LOC at
    30K by v1.0; the upgrade smoke fails fast when an upgrade pushes
    the count past phase ceiling.
    """
    t0 = time.monotonic()
    path = SCRIPTS_DIR / "loc_budget.py"
    if not path.exists():
        return Gate(
            "loc_budget", None,
            "scripts/loc_budget.py not present; skipping",
            int((time.monotonic() - t0) * 1000),
        )
    try:
        proc = subprocess.run(
            [sys.executable, str(path), "--json"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", env=_utf8_env(),
        )
    except FileNotFoundError as exc:
        return Gate(
            "loc_budget", False, f"cannot invoke: {exc}",
            int((time.monotonic() - t0) * 1000), EXIT_OTHER,
        )
    elapsed = int((time.monotonic() - t0) * 1000)
    if proc.returncode != 0:
        return Gate(
            "loc_budget", False,
            f"loc_budget exit={proc.returncode}",
            elapsed, EXIT_OTHER,
        )
    try:
        payload = json.loads(proc.stdout)
        src = payload.get("src_nucleus", {})
        verdict = src.get("verdict", "UNKNOWN")
        total = src.get("total", 0)
        ceiling = payload.get("ceiling", 0)
        msg = f"src/nucleus={total} LOC / {ceiling} ceiling ({verdict})"
        passed = verdict != "RED"
    except (json.JSONDecodeError, AttributeError):
        msg = "loc_budget.py emitted non-JSON output"
        passed = False
    return Gate("loc_budget", passed, msg, elapsed, EXIT_OTHER)


def render_text(gates: list[Gate]) -> str:
    """Human-readable report mirroring scripts/loc_budget.py style."""
    bar = "=" * 72
    lines = [bar, " Nucleus -- Upgrade Smoke Test (AGENTS.md Sec 11.13)", bar, ""]
    width = max((len(g.name) for g in gates), default=10)
    for g in gates:
        status = "SKIP" if g.passed is None else ("PASS" if g.passed else "FAIL")
        lines.append(
            f"  [{status}] {g.name:<{width}}   ({g.duration_ms:>7,} ms)  {g.message}"
        )
    lines.append("")
    fails = [g for g in gates if g.passed is False]
    skipped = [g for g in gates if g.passed is None]
    if not fails:
        lines.append(
            f" Verdict: PASS  ({len(skipped)} gate(s) skipped, "
            f"{len(gates) - len(skipped)} ran)"
        )
    else:
        first = fails[0]
        lines.append(
            f" Verdict: FAIL  ({len(fails)} gate(s) failed; "
            f"first = {first.name}, exit = {first.exit_code_on_fail})"
        )
    lines.append(bar)
    return "\n".join(lines)


def render_json(gates: list[Gate]) -> str:
    """Machine-readable JSON output for CI consumers."""
    return json.dumps(
        {
            "gates": [asdict(g) for g in gates],
            "passed": all(g.passed for g in gates if g.passed is not None),
            "ran_count": sum(1 for g in gates if g.passed is not None),
            "failed_count": sum(1 for g in gates if g.passed is False),
            "skipped_count": sum(1 for g in gates if g.passed is None),
        },
        indent=2, sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the dependency-upgrade smoke gate "
            "(AGENTS.md Sec 11.13 / Hard Constraint #11)."
        ),
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of the human report.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat skipped gates as failures (use this in upgrade-PR CI).",
    )
    args = parser.parse_args(argv)

    gates: list[Gate] = [
        gate_pin_validation(),
        gate_adr_012_cross_check(),
        gate_pytest(),
        gate_optional("beachhead_e2e", "beachhead_e2e.py"),
        gate_optional("benchmark_regression", "benchmark_regression.py"),
        gate_optional("license_check", "check_licenses.py", EXIT_LICENSE),
        gate_loc_budget(),
    ]

    if args.strict:
        for g in gates:
            if g.passed is None:
                g.passed = False
                g.message = "(skipped -> strict failure) " + g.message

    sys.stdout.write((render_json(gates) if args.json else render_text(gates)) + "\n")

    for g in gates:
        if g.passed is False:
            return g.exit_code_on_fail
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
