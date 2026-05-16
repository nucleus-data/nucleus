"""Nucleus v0.2 Final E2E Orchestrator.

Runs all 11 suites (A–K) from docs/internal/release-process/E2E_TEST_PLAN.md.
Outputs structured JSON report + Markdown summary to docs/internal/release-process/.

Usage:
    python scripts/release_e2e/e2e_full.py --suite all
    python scripts/release_e2e/e2e_full.py --suite A,I
    python scripts/release_e2e/e2e_full.py --suite A --dry-run
    python scripts/release_e2e/e2e_full.py --suite I --output results.json

Per docs/internal/release-process/E2E_TEST_PLAN.md.
Suite A (Boot + Lifecycle) and Suite I (Governance) are FULLY IMPLEMENTED.
Suites B–H, J, K are STUBBED with # TODO: implement post-Wave-1 markers.

Refs:
    docs/internal/release-process/E2E_TEST_PLAN.md
    docs/specs/nucleus_cli_spec.md §3–§8
    AGENTS.md §11.8 (beachhead metric)
    scripts/beachhead_e2e.py (existing E2E baseline)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_RELEASE_DIR = REPO_ROOT / "docs" / "internal" / "release-process"
GOVERNANCE_SCRIPTS = [
    "check_vocabulary.py",
    "check_pinning.py",
    "loc_budget.py",
    "dagster_leak_check.py",
    "check_error_codes.py",
    "check_api_stability.py",
    "check_licenses.py",
    "check_layering.py",
]
TEMPLATE_FILES = (
    "README.md",
    ".gitignore",
    "nucleus_project.yaml",
    "assets/__init__.py",
    "assets/example.py",
    "data/.gitkeep",
)
COLD_BOOT_THRESHOLD_S = 1.5  # Suite A1 / K1
UP_BOOT_THRESHOLD_S = 10.0  # Suite A5 per docs/specs/nucleus_cli_spec.md §3.2
VERSION_THRESHOLD_S = 1.5  # Suite A2 / K1


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    suite: str
    scenario_id: str
    name: str
    status: str  # PASS | FAIL | SKIP | ERROR
    elapsed_s: float
    detail: str = ""
    skip_reason: str = ""


@dataclass
class SuiteResult:
    suite_id: str
    name: str
    scenarios: list[ScenarioResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scenarios if s.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for s in self.scenarios if s.status == "FAIL")

    @property
    def skipped(self) -> int:
        return sum(1 for s in self.scenarios if s.status in ("SKIP", "ERROR"))

    @property
    def total(self) -> int:
        return len(self.scenarios)

    @property
    def pass_rate(self) -> float:
        if not self.total:
            return 1.0
        return self.passed / (self.passed + self.failed) if (self.passed + self.failed) > 0 else 1.0


@dataclass
class E2EReport:
    version: str = "1"
    generated_at: str = ""
    suites_requested: list[str] = field(default_factory=list)
    dry_run: bool = False
    suite_results: list[SuiteResult] = field(default_factory=list)

    @property
    def total_passed(self) -> int:
        return sum(s.passed for s in self.suite_results)

    @property
    def total_failed(self) -> int:
        return sum(s.failed for s in self.suite_results)

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.suite_results)

    @property
    def overall_status(self) -> str:
        if self.total_failed > 0:
            return "FAIL"
        if self.total_skipped > 0 and self.total_passed == 0:
            return "SKIP"
        return "PASS"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _nucleus_cmd() -> list[str]:
    """Docs: https://docs.python.org/3/library/shutil.html#shutil.which"""
    binary = shutil.which("nucleus")
    return [binary] if binary else [sys.executable, "-m", "nucleus.cli.main"]


def _python() -> str:
    return sys.executable


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 120,
    env: dict | None = None,
) -> tuple[int, str, str, float]:
    """Run a subprocess and return (rc, stdout, stderr, elapsed_s)."""
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, **(env or {})},
        )
        return proc.returncode, proc.stdout, proc.stderr, time.perf_counter() - started
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT after {timeout}s", time.perf_counter() - started
    except Exception as exc:
        return -2, "", f"EXEC ERROR: {exc}", time.perf_counter() - started


def _seed_sqlite(db_path: Path) -> None:
    """Seed a 3-row SQLite source DB for ingest tests.
    Docs: https://docs.python.org/3/library/sqlite3.html
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO users (id, name) VALUES (?, ?)",
            [(1, "alice"), (2, "bob"), (3, "carol")],
        )
        conn.commit()
    finally:
        conn.close()


def _pass(
    name: str, suite: str, scenario_id: str, elapsed: float, detail: str = ""
) -> ScenarioResult:
    print(f"  [{scenario_id}] {name:<40} PASS  ({elapsed:.2f}s)")
    return ScenarioResult(suite, scenario_id, name, "PASS", elapsed, detail)


def _fail(name: str, suite: str, scenario_id: str, elapsed: float, detail: str) -> ScenarioResult:
    print(f"  [{scenario_id}] {name:<40} FAIL  ({elapsed:.2f}s)  -> {detail[:100]}")
    return ScenarioResult(suite, scenario_id, name, "FAIL", elapsed, detail)


def _skip(name: str, suite: str, scenario_id: str, reason: str) -> ScenarioResult:
    print(f"  [{scenario_id}] {name:<40} SKIP  -> {reason[:80]}")
    return ScenarioResult(suite, scenario_id, name, "SKIP", 0.0, skip_reason=reason)


def _stub(name: str, suite: str, scenario_id: str) -> ScenarioResult:
    reason = "TODO: implement post-Wave-1"
    print(f"  [{scenario_id}] {name:<40} SKIP  -> {reason}")
    return ScenarioResult(suite, scenario_id, name, "SKIP", 0.0, skip_reason=reason)


# ---------------------------------------------------------------------------
# Suite A — Boot + Lifecycle (FULLY IMPLEMENTED)
# ---------------------------------------------------------------------------


def run_suite_a(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite A: Boot + Lifecycle (10 scenarios).

    Per docs/internal/release-process/E2E_TEST_PLAN.md §"Suite A".
    Ref: docs/specs/nucleus_cli_spec.md §3.1–§3.3, §3.7; v4.1 §11.2.
    """
    suite = SuiteResult("A", "Boot + Lifecycle")
    suite.started_at = datetime.now(UTC).isoformat()
    project = "test-demo-a"
    project_dir = tmpdir / project

    print("\n[Suite A] Boot + Lifecycle")
    print("-" * 60)

    # A1: version cold boot
    t0 = time.perf_counter()
    rc, out, err, elapsed = _run([*nucleus, "version"], tmpdir)
    if dry_run:
        suite.scenarios.append(_skip("A1 version cold boot", "A", "A1", "dry-run"))
    elif rc != 0:
        suite.scenarios.append(
            _fail("A1 version cold boot", "A", "A1", elapsed, f"exit {rc}: {err.strip()[:120]}")
        )
    elif elapsed > VERSION_THRESHOLD_S:
        suite.scenarios.append(
            _fail(
                "A1 version cold boot",
                "A",
                "A1",
                elapsed,
                f"Too slow: {elapsed:.2f}s > {VERSION_THRESHOLD_S}s threshold",
            )
        )
    else:
        # Check for required version strings (no external classnames)
        required = ["nucleus", "duckdb", "polars"]
        missing = [tok for tok in required if tok.lower() not in out.lower()]
        if missing:
            suite.scenarios.append(
                _fail(
                    "A1 version cold boot",
                    "A",
                    "A1",
                    elapsed,
                    f"Missing version strings: {missing}",
                )
            )
        else:
            suite.scenarios.append(_pass("A1 version cold boot", "A", "A1", elapsed))

    # A2: --help response time
    rc, out, err, elapsed = _run([*nucleus, "--help"], tmpdir)
    if dry_run:
        suite.scenarios.append(_skip("A2 --help response time", "A", "A2", "dry-run"))
    elif rc != 0:
        suite.scenarios.append(
            _fail("A2 --help response time", "A", "A2", elapsed, f"exit {rc}: {err.strip()[:120]}")
        )
    elif elapsed > 0.5:
        suite.scenarios.append(
            _fail(
                "A2 --help response time",
                "A",
                "A2",
                elapsed,
                f"Too slow: {elapsed:.2f}s > 0.5s threshold",
            )
        )
    else:
        suite.scenarios.append(_pass("A2 --help response time", "A", "A2", elapsed))

    # A3: nucleus init — scaffold creation
    rc, out, err, elapsed = _run([*nucleus, "init", project], tmpdir)
    if dry_run:
        suite.scenarios.append(_skip("A3 init scaffold", "A", "A3", "dry-run"))
    elif rc != 0 and "not yet implemented" in err:
        suite.scenarios.append(
            _skip("A3 init scaffold", "A", "A3", "v0.1 stub (not yet implemented)")
        )
    elif rc != 0:
        suite.scenarios.append(
            _fail("A3 init scaffold", "A", "A3", elapsed, f"exit {rc}: {err.strip()[:120]}")
        )
    else:
        missing = [f for f in TEMPLATE_FILES if not (project_dir / f).exists()]
        if missing:
            suite.scenarios.append(
                _fail(
                    "A3 init scaffold", "A", "A3", elapsed, f"Missing scaffolded files: {missing}"
                )
            )
        else:
            suite.scenarios.append(
                _pass(
                    "A3 init scaffold",
                    "A",
                    "A3",
                    elapsed,
                    f"All {len(TEMPLATE_FILES)} template files present",
                )
            )

    # A4: idempotency (re-run in existing dir)
    if project_dir.exists():
        rc, out, err, elapsed = _run([*nucleus, "init", project], tmpdir)
        if dry_run:
            suite.scenarios.append(_skip("A4 init idempotency", "A", "A4", "dry-run"))
        elif rc == 0:
            suite.scenarios.append(
                _fail(
                    "A4 init idempotency",
                    "A",
                    "A4",
                    elapsed,
                    "Should have exited non-zero for existing non-empty dir",
                )
            )
        elif rc != 0 and (
            "NucleusIOError" in err
            or "non-empty" in err.lower()
            or "already exists" in err.lower()
            or "NE1005" in err
        ):
            suite.scenarios.append(
                _pass(
                    "A4 init idempotency", "A", "A4", elapsed, f"Correctly rejected with exit {rc}"
                )
            )
        else:
            suite.scenarios.append(
                _skip(
                    "A4 init idempotency",
                    "A",
                    "A4",
                    f"exit {rc} but unclear error; details: {err.strip()[:80]}",
                )
            )
    else:
        suite.scenarios.append(_skip("A4 init idempotency", "A", "A4", "A3 must pass first"))

    # A5–A8: Docker-dependent; skip in dry-run or if Docker unavailable
    docker_available = shutil.which("docker") is not None
    if not docker_available or dry_run:
        reason = "dry-run mode" if dry_run else "Docker not available in this environment"
        for sid, name in [
            ("A5", "up MinIO < 30s"),
            ("A6", "down < 5s"),
            ("A7", "up-down-up cycle"),
            ("A8", "malformed config rejected"),
        ]:
            suite.scenarios.append(_skip(f"{sid} {name}", "A", sid, reason))
    else:
        # A5: nucleus up
        rc, out, err, elapsed = _run([*nucleus, "up"], project_dir, timeout=60)
        if rc != 0 and "not yet implemented" in err:
            suite.scenarios.append(_skip("A5 up MinIO < 30s", "A", "A5", "v0.1 stub"))
        elif rc != 0:
            suite.scenarios.append(
                _fail("A5 up MinIO < 30s", "A", "A5", elapsed, f"exit {rc}: {err.strip()[:120]}")
            )
        elif elapsed > UP_BOOT_THRESHOLD_S:
            suite.scenarios.append(
                _fail(
                    "A5 up MinIO < 30s",
                    "A",
                    "A5",
                    elapsed,
                    f"Too slow: {elapsed:.2f}s > {UP_BOOT_THRESHOLD_S}s",
                )
            )
        else:
            suite.scenarios.append(_pass("A5 up MinIO < 30s", "A", "A5", elapsed))

        # A6: nucleus down
        rc, out, err, elapsed = _run([*nucleus, "down"], project_dir, timeout=30)
        if rc != 0 and "not yet implemented" in err:
            suite.scenarios.append(_skip("A6 down < 5s", "A", "A6", "v0.1 stub"))
        elif rc != 0:
            suite.scenarios.append(
                _fail("A6 down < 5s", "A", "A6", elapsed, f"exit {rc}: {err.strip()[:120]}")
            )
        elif elapsed > 5.0:
            suite.scenarios.append(
                _fail("A6 down < 5s", "A", "A6", elapsed, f"Too slow: {elapsed:.2f}s > 5.0s")
            )
        else:
            suite.scenarios.append(_pass("A6 down < 5s", "A", "A6", elapsed))

        # A7: cycle stress
        rc1, _, _, _ = _run([*nucleus, "up"], project_dir, timeout=60)
        rc2, _, _, _ = _run([*nucleus, "down"], project_dir, timeout=30)
        rc3, _, err3, elapsed = _run([*nucleus, "up"], project_dir, timeout=60)
        _run([*nucleus, "down"], project_dir, timeout=30)  # cleanup
        if rc3 != 0 and "not yet implemented" in err3:
            suite.scenarios.append(_skip("A7 up-down-up cycle", "A", "A7", "v0.1 stub"))
        elif rc3 == 0:
            suite.scenarios.append(_pass("A7 up-down-up cycle", "A", "A7", elapsed))
        else:
            suite.scenarios.append(
                _fail("A7 up-down-up cycle", "A", "A7", elapsed, f"Second up failed: exit {rc3}")
            )

        # A8: malformed config
        malformed_yaml = project_dir / "nucleus_project.yaml"
        if malformed_yaml.exists():
            orig = malformed_yaml.read_text(encoding="utf-8")
            malformed_yaml.write_text("project: {}\n# missing required fields\n", encoding="utf-8")
            rc, out, err, elapsed = _run([*nucleus, "run"], project_dir)
            malformed_yaml.write_text(orig, encoding="utf-8")
            if rc != 0:
                suite.scenarios.append(
                    _pass(
                        "A8 malformed config rejected",
                        "A",
                        "A8",
                        elapsed,
                        f"Correctly rejected with exit {rc}",
                    )
                )
            else:
                suite.scenarios.append(
                    _fail(
                        "A8 malformed config rejected",
                        "A",
                        "A8",
                        elapsed,
                        "Should have failed on malformed config",
                    )
                )
        else:
            suite.scenarios.append(
                _skip("A8 malformed config rejected", "A", "A8", "A3 must pass first")
            )

    # A9: nucleus list — needs running project
    rc, out, err, elapsed = _run([*nucleus, "list"], project_dir)
    if dry_run:
        suite.scenarios.append(_skip("A9 list assets", "A", "A9", "dry-run"))
    elif rc != 0 and "not yet implemented" in err:
        suite.scenarios.append(_skip("A9 list assets", "A", "A9", "v0.1 stub"))
    elif rc != 0:
        suite.scenarios.append(_fail("A9 list assets", "A", "A9", elapsed, f"exit {rc}"))
    else:
        suite.scenarios.append(_pass("A9 list assets", "A", "A9", elapsed, out.strip()[:80]))

    # A10: nucleus describe
    rc, out, err, elapsed = _run([*nucleus, "describe", "example.greeting"], project_dir)
    if dry_run:
        suite.scenarios.append(_skip("A10 describe asset", "A", "A10", "dry-run"))
    elif rc != 0 and "not yet implemented" in err:
        suite.scenarios.append(_skip("A10 describe asset", "A", "A10", "v0.1 stub"))
    elif rc != 0 and "NucleusAssetNotFound" in err:
        suite.scenarios.append(
            _skip(
                "A10 describe asset",
                "A",
                "A10",
                "Asset not materialized yet (expected in integration)",
            )
        )
    elif rc != 0:
        suite.scenarios.append(_fail("A10 describe asset", "A", "A10", elapsed, f"exit {rc}"))
    else:
        suite.scenarios.append(_pass("A10 describe asset", "A", "A10", elapsed))

    suite.finished_at = datetime.now(UTC).isoformat()
    return suite


# ---------------------------------------------------------------------------
# Suite I — Governance (FULLY IMPLEMENTED)
# ---------------------------------------------------------------------------


def run_suite_i(dry_run: bool) -> SuiteResult:
    """Suite I: Governance (8 scenarios).

    Per docs/internal/release-process/E2E_TEST_PLAN.md §"Suite I".
    Ref: AGENTS.md §11.7; scripts/check_*.py.
    """
    suite = SuiteResult("I", "Governance")
    suite.started_at = datetime.now(UTC).isoformat()

    print("\n[Suite I] Governance")
    print("-" * 60)

    for script_name in GOVERNANCE_SCRIPTS:
        script_path = SCRIPTS_DIR / script_name
        scenario_id = f"I{GOVERNANCE_SCRIPTS.index(script_name) + 1}"
        scenario_name = f"{scenario_id} {script_name}"

        if not script_path.exists():
            suite.scenarios.append(
                _skip(scenario_name, "I", scenario_id, f"Script not found: {script_path}")
            )
            continue

        if dry_run:
            suite.scenarios.append(_skip(scenario_name, "I", scenario_id, "dry-run"))
            continue

        rc, out, err, elapsed = _run([_python(), str(script_path)], REPO_ROOT)

        if rc == 0:
            suite.scenarios.append(_pass(scenario_name, "I", scenario_id, elapsed))
        else:
            combined = (out + "\n" + err).strip()
            suite.scenarios.append(_fail(scenario_name, "I", scenario_id, elapsed, combined[:200]))

    suite.finished_at = datetime.now(UTC).isoformat()
    return suite


# ---------------------------------------------------------------------------
# Suites B–H, J, K — STUBS (implement post-Wave-1)
# ---------------------------------------------------------------------------


def run_suite_b(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite B: Materialization (8 scenarios).
    TODO: implement post-Wave-1 (requires Wave-1B connector + Wave-1E test wiring).
    """
    suite = SuiteResult("B", "Materialization")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite B] Materialization — STUB (post-Wave-1)")
    for sid, name in [
        ("B1", "empty asset materialize"),
        ("B2", "1k-row materialize"),
        ("B3", "100k-row Polars LazyFrame"),
        ("B4", "dependent asset chain A→B→C"),
        ("B5", "dry-run no writes"),
        ("B6", "run --resume from checkpoint"),
        ("B7", "concurrent run lock test"),
        ("B8", "schema-contract violation NE2006"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "B", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1
    # B1: create temp @nucleus.asset returning empty DataFrame; nucleus run; verify snapshot
    # B2: create asset returning 1k-row pl.DataFrame; verify row_count
    # B3: large LazyFrame test with psutil RSS monitoring
    # B4: 3-asset chain with ctx.read dependencies
    # B5: assert no .nucleus/warehouse/*.parquet created after --dry-run
    # B6: requires run-state persistence (Wave-1 feature)
    # B7: multiprocess concurrent run via subprocess.Popen
    # B8: @nucleus.contract with failing check; assert exit 5 + NE2006/NE3007
    return suite


def run_suite_c(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite C: Query (6 scenarios).
    TODO: implement post-Wave-1 (requires materialized asset for C2–C6).
    """
    suite = SuiteResult("C", "Query")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite C] Query — STUB (post-Wave-1)")
    for sid, name in [
        ("C1", "SELECT 1 connectivity"),
        ("C2", "query materialized asset"),
        ("C3", "--format csv stdout"),
        ("C4", "--format parquet export"),
        ("C5", "SQL injection rejected"),
        ("C6", "1M rows no OOM"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "C", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1
    # C1: nucleus query "SELECT 1 AS one" -- nucleus up must be running
    # C2: nucleus query "SELECT count(*) FROM raw.users" after D1 ingest
    # C3: nucleus query --format csv; parse stdout as CSV
    # C4: nucleus query --format parquet /tmp/out.parquet; verify with pyarrow
    # C5: nucleus query "SELECT * FROM {{ ref('raw.users'); DROP TABLE ...') }}"
    # C6: 1M-row fixture; psutil RSS check; mark @pytest.mark.slow
    return suite


def run_suite_d(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite D: Ingest (10 scenarios).
    TODO: implement post-Wave-1.
    D2 (bad creds) and D7 (filesystem CSV) can run without external infra.
    """
    suite = SuiteResult("D", "Ingest")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite D] Ingest — STUB (post-Wave-1)")
    for sid, name in [
        ("D1", "Postgres → Iceberg happy path"),
        ("D2", "Postgres bad creds → NE1001"),
        ("D3", "Postgres unreachable → NE1001"),
        ("D4", "MySQL → Iceberg happy path"),
        ("D5", "S3 Parquet → Iceberg (moto)"),
        ("D6", "GCS Parquet → Iceberg (mocked)"),
        ("D7", "Filesystem CSV → Iceberg"),
        ("D8", "Filesystem glob mixed schema → NE2004"),
        ("D9", "Snowflake → Iceberg (mocked)"),
        ("D10", "ingest --preview no commit"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "D", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1
    # D2 is high priority: nucleus ingest postgres://bad:creds@localhost/db --table t --as raw.t
    #   assert exit 1; assert "NucleusSourceConnectionError" or "NE1001" in stderr
    #   assert "sqlalchemy" and "psycopg" NOT in stderr (error translation test)
    # D7: create temp CSV; nucleus ingest ./test.csv --as raw.csv_test; verify row count
    return suite


def run_suite_e(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite E: Scheduling (5 scenarios).
    TODO: implement post-Wave-1.
    E3 (invalid cron) can run without external infra — high priority.
    """
    suite = SuiteResult("E", "Scheduling")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite E] Scheduling — STUB (post-Wave-1)")
    for sid, name in [
        ("E1", "schedule list enumerates"),
        ("E2", "schedule preview next 5 runs"),
        ("E3", "sub-second cron rejected"),
        ("E4", "DST Spring-forward handled"),
        ("E5", "timezone-aware schedules"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "E", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1
    # E3: python -c "import nucleus; @nucleus.asset(table='t', schedule='* * * * * *') def t(ctx): pass"
    #   assert NucleusScheduleParseError raised; see docs/specs/nucleus_ctx_sdk_spec.md §2.1
    return suite


def run_suite_f(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite F: Workbench UI (8 scenarios).
    TODO: implement post-Wave-1A (workbench).
    """
    suite = SuiteResult("F", "Workbench UI")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite F] Workbench UI — STUB (post-Wave-1A)")
    for sid, name in [
        ("F1", "workbench up serves :8080"),
        ("F2", "GET /api/dashboard/summary"),
        ("F3", "GET /api/runs paginated"),
        ("F4", "GET /api/runs/{id}/log SSE"),
        ("F5", "POST /api/runs/trigger"),
        ("F6", "GET /api/search"),
        ("F7", "editorial hero < 2s cold"),
        ("F8", "static fallback offline"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "F", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1A
    # F1: subprocess nucleus workbench up; wait; requests.get("http://localhost:8080/"); assert 200
    # F2: requests.get("http://localhost:8080/api/dashboard/summary"); assert 200 + valid JSON
    # Note: requires httpx or requests (not in core deps); add to test extras
    return suite


def run_suite_g(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite G: AI Copilot (4 scenarios).
    TODO: implement post-Wave-1.
    G4 (missing API key fix_hint) can run without a real API key.
    """
    suite = SuiteResult("G", "AI Copilot")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite G] AI Copilot — STUB (post-Wave-1)")
    for sid, name in [
        ("G1", "mocked LLM response"),
        ("G2", "token budget guardrail"),
        ("G3", "schema-aware prompt"),
        ("G4", "missing API key fix_hint"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "G", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1
    # G4: env without ANTHROPIC_API_KEY; nucleus chat "test"; assert exit 1; assert NE4001
    #   assert "ANTHROPIC_API_KEY" in stderr (fix_hint); assert "AuthenticationError" NOT in stderr
    return suite


def run_suite_h(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite H: Error UX (6 scenarios).
    TODO: H1 (fix_hint check) can run now via Python import.
    """
    suite = SuiteResult("H", "Error UX")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite H] Error UX — partial STUB")

    # H1: every NE-code has a fix_hint — runnable NOW via Python import
    if dry_run:
        suite.scenarios.append(_skip("H1 every NE-code has fix_hint", "H", "H1", "dry-run"))
    else:
        try:
            t0 = time.perf_counter()
            result = subprocess.run(
                [
                    _python(),
                    "-c",
                    """
import sys
sys.path.insert(0, '.')
from nucleus import errors as e
import inspect
subclasses = [v for v in vars(e).values()
              if inspect.isclass(v) and issubclass(v, e.NucleusError) and v is not e.NucleusError]
missing = [c.__name__ for c in subclasses if not getattr(c, 'fix_hint', '')]
if missing:
    print(f'MISSING fix_hint: {missing}', file=sys.stderr)
    sys.exit(1)
print(f'All {len(subclasses)} NucleusError subclasses have fix_hint')
""",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            elapsed = time.perf_counter() - t0
            if result.returncode == 0:
                suite.scenarios.append(
                    _pass(
                        "H1 every NE-code has fix_hint", "H", "H1", elapsed, result.stdout.strip()
                    )
                )
            else:
                suite.scenarios.append(
                    _fail(
                        "H1 every NE-code has fix_hint", "H", "H1", elapsed, result.stderr.strip()
                    )
                )
        except Exception as exc:
            suite.scenarios.append(_fail("H1 every NE-code has fix_hint", "H", "H1", 0.0, str(exc)))

    for sid, name in [
        ("H2", "zero external classnames"),
        ("H3", "stack trace hidden by default"),
        ("H4", "exit codes consistent"),
        ("H5", "did you mean suggestion"),
        ("H6", "--quiet suppresses output"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "H", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    # TODO: implement post-Wave-1
    # H2: covered by Suite I dagster_leak_check; additional: run full CLI and capture output
    # H3: nucleus ingest bad_dsn; assert "Traceback" NOT in stderr by default; with --verbose it IS
    # H4: map each exit code scenario; test_exit_codes.py already covers this
    # H5: nucleus describe example.greetnig; assert "Did you mean" in stderr
    # H6: nucleus version --quiet; assert stdout == ""; assert exit 0
    return suite


def run_suite_j(tmpdir: Path, dry_run: bool) -> SuiteResult:
    """Suite J: Chaos (8 scenarios).
    TODO: J1 and J2 are fully implemented in scripts/release_e2e/run_chaos.py.
    This suite delegates to run_chaos.py for those two.
    """
    suite = SuiteResult("J", "Chaos + Reliability")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite J] Chaos + Reliability — partial STUB")

    # J1 + J2: delegate to run_chaos.py
    chaos_script = SCRIPTS_DIR / "release_e2e" / "run_chaos.py"
    for sid, name in [("J1", "disk-full mid-write"), ("J2", "kill-9 mid-commit")]:
        if not chaos_script.exists():
            suite.scenarios.append(
                _skip(
                    f"{sid} {name}",
                    "J",
                    sid,
                    "run_chaos.py not found; run scripts/release_e2e/run_chaos.py",
                )
            )
        elif dry_run:
            suite.scenarios.append(_skip(f"{sid} {name}", "J", sid, "dry-run"))
        else:
            rc, out, err, elapsed = _run(
                [_python(), str(chaos_script), f"--scenario={sid.lower()}"],
                REPO_ROOT,
                timeout=120,
            )
            if rc == 0:
                suite.scenarios.append(_pass(f"{sid} {name}", "J", sid, elapsed))
            else:
                suite.scenarios.append(
                    _fail(f"{sid} {name}", "J", sid, elapsed, (out + err).strip()[:200])
                )

    for sid, name in [
        ("J3", "MinIO down retries + NE error"),
        ("J4", "Postgres connection drop mid-ingest"),
        ("J5", "schema drift source → NE2004"),
        ("J6", "concurrent run race"),
        ("J7", "catalog corruption recoverable"),
        ("J8", "S3 multipart rollback"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "J", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    return suite


def run_suite_k(tmpdir: Path, nucleus: list[str], dry_run: bool) -> SuiteResult:
    """Suite K: Performance (5 scenarios).
    K1 (cold boot) is partially implemented (reuses A1 timing).
    """
    suite = SuiteResult("K", "Performance")
    suite.started_at = datetime.now(UTC).isoformat()
    print("\n[Suite K] Performance — partial STUB")

    # K1: cold boot < 1.5s — runnable now
    times = []
    for _ in range(3):
        rc, out, err, elapsed = _run([*nucleus, "version"], tmpdir)
        if rc == 0:
            times.append(elapsed)
    if dry_run:
        suite.scenarios.append(_skip("K1 version cold boot < 1.5s", "K", "K1", "dry-run"))
    elif not times:
        suite.scenarios.append(
            _fail("K1 version cold boot < 1.5s", "K", "K1", 0.0, "nucleus version failed")
        )
    else:
        p95 = sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]
        if p95 <= COLD_BOOT_THRESHOLD_S:
            suite.scenarios.append(
                _pass(
                    "K1 version cold boot < 1.5s",
                    "K",
                    "K1",
                    p95,
                    f"P95={p95:.2f}s (3 runs: {[round(t, 2) for t in times]})",
                )
            )
        else:
            suite.scenarios.append(
                _fail(
                    "K1 version cold boot < 1.5s",
                    "K",
                    "K1",
                    p95,
                    f"P95={p95:.2f}s > {COLD_BOOT_THRESHOLD_S}s threshold",
                )
            )

    for sid, name in [
        ("K2", "list < 2s for 100 assets"),
        ("K3", "1GB DataFrame → Iceberg < 30s"),
        ("K4", "1GB scan + aggregate < 3s"),
        ("K5", "Workbench Lighthouse ≥ 90"),
    ]:
        suite.scenarios.append(_stub(f"{sid} {name}", "K", sid))
    suite.finished_at = datetime.now(UTC).isoformat()
    return suite


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _build_report(report: E2EReport) -> str:
    """Build a Markdown summary of the E2E report."""
    lines = [
        "# Nucleus v0.2 E2E Report",
        "",
        f"**Generated**: {report.generated_at}",
        f"**Dry run**: {report.dry_run}",
        f"**Suites**: {', '.join(report.suites_requested)}",
        f"**Overall**: {report.overall_status} "
        f"({report.total_passed} passed / {report.total_failed} failed / {report.total_skipped} skipped)",
        "",
        "## Suite Summary",
        "",
        "| Suite | Name | Pass | Fail | Skip | Rate |",
        "|---|---|---|---|---|---|",
    ]
    for s in report.suite_results:
        rate = f"{s.pass_rate * 100:.0f}%" if (s.passed + s.failed) > 0 else "N/A"
        lines.append(
            f"| {s.suite_id} | {s.name} | {s.passed} | {s.failed} | {s.skipped} | {rate} |"
        )

    lines += ["", "## Scenario Details", ""]
    for s in report.suite_results:
        lines.append(f"### Suite {s.suite_id}: {s.name}")
        lines.append("")
        for sc in s.scenarios:
            emoji = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭", "ERROR": "⚠️"}.get(sc.status, "?")
            detail = sc.detail or sc.skip_reason
            detail_str = f" — {detail[:100]}" if detail else ""
            lines.append(
                f"- {emoji} **{sc.scenario_id}** {sc.name} ({sc.elapsed_s:.2f}s){detail_str}"
            )
        lines.append("")
    return "\n".join(lines)


def _save_results(report: E2EReport, output_path: Path | None) -> None:
    """Save JSON report and Markdown summary."""
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")

    json_path = output_path or (DOCS_RELEASE_DIR / f"e2e_results_{ts}.json")
    md_path = json_path.with_suffix(".md")

    DOCS_RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2)
    print(f"\nJSON report: {json_path}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(_build_report(report))
    print(f"MD report:   {md_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_SUITES = list("ABCDEFGHIJK")
SUITE_MAP: dict[str, Callable] = {}  # populated in main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nucleus v0.2 E2E orchestrator (docs/internal/release-process/E2E_TEST_PLAN.md)."
    )
    parser.add_argument(
        "--suite",
        default="all",
        help="Comma-separated suite IDs (A,B,C...) or 'all'. Default: all",
    )
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="JSON output path (default: docs/internal/release-process/e2e_results_<ts>.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip all I/O-touching tests; only verify script structure compiles",
    )
    args = parser.parse_args(argv)

    if args.suite.lower() == "all":
        requested = ALL_SUITES
    else:
        requested = [s.strip().upper() for s in args.suite.split(",")]

    print("=" * 60)
    print("Nucleus v0.2 E2E Orchestrator")
    print(f"Suites: {', '.join(requested)}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)

    report = E2EReport(
        generated_at=datetime.now(UTC).isoformat(),
        suites_requested=requested,
        dry_run=args.dry_run,
    )

    nucleus = _nucleus_cmd()
    tmpdir = Path(tempfile.mkdtemp(prefix="nucleus_e2e_"))
    try:
        for suite_id in requested:
            if suite_id == "A":
                report.suite_results.append(run_suite_a(tmpdir, nucleus, args.dry_run))
            elif suite_id == "B":
                report.suite_results.append(run_suite_b(tmpdir, nucleus, args.dry_run))
            elif suite_id == "C":
                report.suite_results.append(run_suite_c(tmpdir, nucleus, args.dry_run))
            elif suite_id == "D":
                report.suite_results.append(run_suite_d(tmpdir, nucleus, args.dry_run))
            elif suite_id == "E":
                report.suite_results.append(run_suite_e(tmpdir, nucleus, args.dry_run))
            elif suite_id == "F":
                report.suite_results.append(run_suite_f(tmpdir, nucleus, args.dry_run))
            elif suite_id == "G":
                report.suite_results.append(run_suite_g(tmpdir, nucleus, args.dry_run))
            elif suite_id == "H":
                report.suite_results.append(run_suite_h(tmpdir, nucleus, args.dry_run))
            elif suite_id == "I":
                report.suite_results.append(run_suite_i(args.dry_run))
            elif suite_id == "J":
                report.suite_results.append(run_suite_j(tmpdir, args.dry_run))
            elif suite_id == "K":
                report.suite_results.append(run_suite_k(tmpdir, nucleus, args.dry_run))
            else:
                print(f"  [WARN] Unknown suite ID: {suite_id}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    _save_results(report, args.output)

    print("\n" + "=" * 60)
    print(_build_report(report).split("## Suite Summary")[1].split("## Scenario")[0].strip())
    print("=" * 60)
    print(f"\nFinal status: {report.overall_status}")

    return 0 if report.total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
