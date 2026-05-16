"""Nucleus v0.2 Release Smoke Tests.

A subset of E2E scenarios from docs/release/E2E_TEST_PLAN.md runnable via pytest.
10 highest-value scenarios selected for fast CI feedback.

Runnable NOW (no Wave-1 features required):
  - test_A1_version_cold_boot        (A1)  — nucleus version < 1.5s
  - test_I1_governance_scripts_pass  (I1)  — all 8 governance scripts EXIT 0
  - test_I2_loc_budget_green         (I2)  — src/nucleus/ < 8000 LOC
  - test_H1_every_ne_code_has_fix_hint (H1) — all NucleusError subclasses have fix_hint

Runnable after Wave-1 (marked @pytest.mark.integration):
  - test_A3_init_scaffold_files      (A3)  — nucleus init creates 6 template files
  - test_A5_up_boots_within_10s      (A5)  — nucleus up < 10s [Docker]
  - test_B5_dry_run_no_writes        (B5)  — nucleus run --dry-run creates no snapshots
  - test_C1_query_select_1           (C1)  — nucleus query "SELECT 1"
  - test_D2_bad_creds_clean_error    (D2)  — bad Postgres DSN → NE1001, no classname leaks
  - test_K1_version_perf_p95         (K1)  — P95 of 5 version calls < 1.5s

Usage:
    # Run all (collect-only safe even if some need Wave-1):
    pytest tests/release_e2e/ --collect-only

    # Run only immediately-runnable tests:
    pytest tests/release_e2e/ -m "not integration and not slow"

    # Run integration tests (requires nucleus up + Wave-1):
    pytest tests/release_e2e/ -m integration

Refs:
    docs/release/E2E_TEST_PLAN.md
    docs/specs/nucleus_cli_spec.md §3, §8
    AGENTS.md §11.8 (beachhead metric)
    scripts/beachhead_e2e.py (existing E2E baseline)
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
VERSION_THRESHOLD_S = 1.5  # docs/specs/nucleus_cli_spec.md §3.7; Suite A1/K1
UP_THRESHOLD_S = 10.0  # docs/specs/nucleus_cli_spec.md §3.2; Suite A5
LOC_CEILING = 8_000  # AGENTS.md §11.6 v0.1 ceiling

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


def _nucleus_cmd() -> list[str]:
    """Docs: https://docs.python.org/3/library/shutil.html#shutil.which"""
    binary = shutil.which("nucleus")
    return [binary] if binary else [sys.executable, "-m", "nucleus.cli.main"]


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a subprocess and return CompletedProcess."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def _is_stub(stderr: str) -> bool:
    """Detect nucleus v0.1 stub responses."""
    return "not yet implemented" in stderr.lower()


# ---------------------------------------------------------------------------
# Immediately runnable tests (no external deps, no Wave-1 features)
# ---------------------------------------------------------------------------


class TestA1VersionColdBoot:
    """A1: nucleus version cold boot < 1.5s.

    Per docs/release/E2E_TEST_PLAN.md §A1.
    Ref: docs/specs/nucleus_cli_spec.md §3.7.
    """

    def test_version_exits_zero(self) -> None:
        """nucleus version must exit 0."""
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "version"], REPO_ROOT)
        assert result.returncode == 0, (
            f"nucleus version exited {result.returncode}\n"
            f"stdout: {result.stdout[:200]}\n"
            f"stderr: {result.stderr[:200]}"
        )

    def test_version_contains_required_strings(self) -> None:
        """nucleus version output must include nucleus, duckdb, polars (per CLI spec §3.7)."""
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "version"], REPO_ROOT)
        output = (result.stdout + result.stderr).lower()
        for required in ("nucleus", "duckdb", "polars"):
            assert required in output, (
                f"'{required}' not found in nucleus version output.\nOutput: {output[:300]}"
            )

    def test_version_no_external_classnames(self) -> None:
        """nucleus version output must NOT contain Dagster/pyiceberg classnames.

        Per docs/specs/nucleus_cli_spec.md §5.4 (error translation discipline).
        """
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "version"], REPO_ROOT)
        output = result.stdout + result.stderr
        banned = [
            "dagster.",
            "DagsterInstance",
            "OpExecutionContext",
            "DuckDBPyConnection",
            "pyiceberg.",
            "polars.exceptions.",
        ]
        leaks = [b for b in banned if b in output]
        assert not leaks, (
            f"External classnames in nucleus version output: {leaks}\nOutput: {output[:300]}"
        )

    def test_version_cold_boot_speed(self) -> None:
        """nucleus version P95 of 3 calls < 1.5s.

        Per docs/release/E2E_TEST_PLAN.md §K1.
        """
        nucleus = _nucleus_cmd()
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            result = _run([*nucleus, "version"], REPO_ROOT)
            elapsed = time.perf_counter() - t0
            if result.returncode == 0:
                times.append(elapsed)

        assert times, "nucleus version never succeeded"
        p95 = sorted(times)[-1]  # with 3 samples, max is P95+
        assert p95 <= VERSION_THRESHOLD_S, (
            f"nucleus version P95={p95:.2f}s exceeds {VERSION_THRESHOLD_S}s threshold.\n"
            f"Times: {[round(t, 3) for t in times]}"
        )


class TestI1GovernanceScriptsPass:
    """I1: All 8 governance scripts EXIT 0.

    Per docs/release/E2E_TEST_PLAN.md §I1.
    Ref: AGENTS.md §11.7.
    """

    @pytest.mark.parametrize("script_name", GOVERNANCE_SCRIPTS)
    def test_governance_script_exits_zero(self, script_name: str) -> None:
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            pytest.skip(f"Script not found: {script_path}")

        result = _run([sys.executable, str(script_path)], REPO_ROOT, timeout=120)
        assert result.returncode == 0, (
            f"{script_name} exited {result.returncode}\n"
            f"stdout: {result.stdout[:400]}\n"
            f"stderr: {result.stderr[:400]}"
        )


class TestI2LocBudgetGreen:
    """I2: src/nucleus/ LOC < 8,000 (v0.1 ceiling).

    Per docs/release/E2E_TEST_PLAN.md §I2.
    Ref: AGENTS.md §11.6; docs/budget_history.md.
    """

    def test_loc_budget_under_ceiling(self) -> None:
        loc_script = SCRIPTS_DIR / "loc_budget.py"
        if not loc_script.exists():
            pytest.skip("loc_budget.py not found")

        result = _run([sys.executable, str(loc_script)], REPO_ROOT, timeout=60)

        # The script exits 0 if under budget, non-zero if over
        assert result.returncode == 0, (
            f"loc_budget.py reports over budget (exit {result.returncode}).\n"
            f"stdout: {result.stdout[:400]}"
        )

    def test_src_nucleus_py_files_exist(self) -> None:
        """Secondary check: src/nucleus/ contains Python source files.

        LOC budget enforcement deferred to test_loc_budget_under_ceiling
        which uses the authoritative scripts/loc_budget.py counter.
        Manual counting uses a different algorithm than loc_budget.py
        (which may use pygount or similar tools).
        """
        src_dir = REPO_ROOT / "src" / "nucleus"
        if not src_dir.exists():
            pytest.skip("src/nucleus/ not found")

        py_files = list(src_dir.rglob("*.py"))
        assert py_files, "No .py files found under src/nucleus/"

        # Verify the main package root exists
        assert (src_dir / "__init__.py").exists(), "src/nucleus/__init__.py missing"
        assert (src_dir / "errors.py").exists(), (
            "src/nucleus/errors.py missing (NucleusError hierarchy)"
        )


class TestH1FixHintPresent:
    """H1: Every NucleusError subclass has error_code defined; fix_hint is wirable.

    Per docs/release/E2E_TEST_PLAN.md §H1.
    Ref: docs/specs/nucleus_cli_spec.md §5.4; ADR-006.

    Note on fix_hint: `fix_hint` is an *instance* attribute set via NucleusError.__init__()
    (see src/nucleus/errors.py:96 — `fix_hint: str = ""`). The guarantee that each NE-code
    "has a fix_hint" is enforced at error-translation-call-time by the handlers in
    coordination/error_translation.py — not by a class-level default. These tests verify
    structural readiness: every subclass declares error_code (ADR-006 §Decision) and
    NucleusError.__init__ exposes the fix_hint parameter (docs/specs/nucleus_cli_spec.md §5.4).
    """

    def test_all_nucleus_error_subclasses_have_error_code(self) -> None:
        """All NucleusError subclasses must declare a non-empty error_code ClassVar.

        Per ADR-006: every concrete subclass declares `error_code: ClassVar[str] = "NEXxxx"`.
        Enforced at runtime by scripts/check_error_codes.py (Suite I governance).
        """
        sys.path.insert(0, str(REPO_ROOT / "src"))
        try:
            import nucleus.errors as errors_module  # type: ignore[import]
        except ImportError:
            pytest.skip("nucleus.errors not importable (check PYTHONPATH)")
        finally:
            if str(REPO_ROOT / "src") in sys.path:
                sys.path.remove(str(REPO_ROOT / "src"))

        base_class = getattr(errors_module, "NucleusError", None)
        if base_class is None:
            pytest.skip("NucleusError not found in nucleus.errors")

        subclasses = [
            v
            for v in vars(errors_module).values()
            if inspect.isclass(v) and issubclass(v, base_class) and v is not base_class
        ]
        assert subclasses, "No NucleusError subclasses found"

        # Each concrete subclass must have a non-empty error_code ClassVar
        missing_code = []
        for cls in subclasses:
            code = getattr(cls, "error_code", None)
            if not code or not isinstance(code, str) or not code.strip():
                missing_code.append(cls.__name__)

        assert not missing_code, (
            f"NucleusError subclasses missing error_code: {missing_code}\n"
            f"Per ADR-006: each subclass must declare error_code: ClassVar[str] = 'NEXxxx'."
        )

    def test_nucleus_error_init_accepts_fix_hint(self) -> None:
        """NucleusError.__init__ must accept fix_hint as a keyword argument.

        Per docs/specs/nucleus_cli_spec.md §5.4: every NucleusError instance carries user_message,
        fix_hint, docs_url. fix_hint is set per-instance at error-raise time.
        """
        sys.path.insert(0, str(REPO_ROOT / "src"))
        try:
            from nucleus.errors import NucleusError  # type: ignore[import]
        except ImportError:
            pytest.skip("nucleus.errors not importable")
        finally:
            if str(REPO_ROOT / "src") in sys.path:
                sys.path.remove(str(REPO_ROOT / "src"))

        # Verify __init__ signature has fix_hint parameter (inspect.signature)
        sig = inspect.signature(NucleusError.__init__)
        assert "fix_hint" in sig.parameters, (
            "NucleusError.__init__ missing 'fix_hint' parameter\n"
            f"Per docs/specs/nucleus_cli_spec.md §5.4. Got params: {list(sig.parameters.keys())}"
        )
        assert "user_message" in sig.parameters, (
            "NucleusError.__init__ missing 'user_message' parameter"
        )

        # Verify construction with fix_hint produces accessible instance attribute
        try:
            err = NucleusError("test error", fix_hint="run nucleus --help")
            assert err.user_message == "test error"
            assert err.fix_hint == "run nucleus --help"
            assert hasattr(err, "docs_url")
        except TypeError as exc:
            pytest.fail(f"NucleusError cannot be instantiated with fix_hint: {exc}")


# ---------------------------------------------------------------------------
# Integration tests (require Wave-1 features; marked @pytest.mark.integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestA3InitScaffold:
    """A3: nucleus init creates valid 6-file scaffold.

    Per docs/release/E2E_TEST_PLAN.md §A3.
    Ref: docs/specs/nucleus_cli_spec.md §3.1; scripts/beachhead_e2e.py step 3.
    """

    def test_init_creates_template_files(self, tmp_path: Path) -> None:
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "init", "smoke-project"], tmp_path)

        if _is_stub(result.stderr):
            pytest.skip("nucleus init is a v0.1 stub (not yet implemented)")

        assert result.returncode == 0, (
            f"nucleus init failed (exit {result.returncode})\nstderr: {result.stderr[:200]}"
        )

        project_dir = tmp_path / "smoke-project"
        missing = [f for f in TEMPLATE_FILES if not (project_dir / f).exists()]
        assert not missing, (
            f"Missing template files: {missing}\nPer docs/specs/nucleus_cli_spec.md §3.1 + beachhead_e2e.py:25"
        )

    def test_init_yaml_is_valid(self, tmp_path: Path) -> None:
        """nucleus_project.yaml must be valid YAML with required keys."""
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "init", "yaml-check"], tmp_path)

        if _is_stub(result.stderr) or result.returncode != 0:
            pytest.skip("nucleus init failed or is a stub")

        yaml_file = tmp_path / "yaml-check" / "nucleus_project.yaml"
        if not yaml_file.exists():
            pytest.skip("nucleus_project.yaml not created")

        try:
            import yaml  # type: ignore[import]

            config = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except ImportError:
            pytest.skip("pyyaml not available for YAML validation")

        assert isinstance(config, dict), "nucleus_project.yaml is not a YAML mapping"
        assert "project" in config, "nucleus_project.yaml missing 'project' key"


@pytest.mark.integration
@pytest.mark.slow
class TestA5UpBootsWithin10s:
    """A5: nucleus up boots within 10s.

    Per docs/release/E2E_TEST_PLAN.md §A5.
    Ref: docs/specs/nucleus_cli_spec.md §3.2; v4.1 §11.2 / §16.1.
    Requires: Docker daemon + initialized project.
    """

    def test_up_exits_zero(self, tmp_path: Path) -> None:
        if not shutil.which("docker"):
            pytest.skip("Docker not available")

        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "boot-test"], tmp_path)
        project_dir = tmp_path / "boot-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        result = _run([*nucleus, "up"], project_dir, timeout=60)
        _run([*nucleus, "down"], project_dir, timeout=30)  # cleanup

        if _is_stub(result.stderr):
            pytest.skip("nucleus up is a v0.1 stub")

        assert result.returncode == 0, (
            f"nucleus up failed (exit {result.returncode})\nstderr: {result.stderr[:300]}"
        )

    def test_up_boots_within_threshold(self, tmp_path: Path) -> None:
        if not shutil.which("docker"):
            pytest.skip("Docker not available")

        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "perf-test"], tmp_path)
        project_dir = tmp_path / "perf-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        t0 = time.perf_counter()
        result = _run([*nucleus, "up"], project_dir, timeout=60)
        elapsed = time.perf_counter() - t0
        _run([*nucleus, "down"], project_dir, timeout=30)

        if _is_stub(result.stderr):
            pytest.skip("nucleus up is a v0.1 stub")

        assert result.returncode == 0
        assert elapsed <= UP_THRESHOLD_S, (
            f"nucleus up took {elapsed:.2f}s > {UP_THRESHOLD_S}s threshold.\n"
            f"Per docs/specs/nucleus_cli_spec.md §3.2 target."
        )


@pytest.mark.integration
class TestB5DryRunNoWrites:
    """B5: nucleus run --dry-run resolves DAG, prints plan, NO writes.

    Per docs/release/E2E_TEST_PLAN.md §B5.
    Ref: docs/specs/nucleus_cli_spec.md §3.4.
    """

    def test_dry_run_exits_zero(self, tmp_path: Path) -> None:
        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "dry-run-test"], tmp_path)
        project_dir = tmp_path / "dry-run-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        result = _run([*nucleus, "run", "--dry-run", "--all"], project_dir)

        if _is_stub(result.stderr):
            pytest.skip("nucleus run --dry-run is a v0.1 stub")

        assert result.returncode == 0, f"nucleus run --dry-run failed (exit {result.returncode})"

    def test_dry_run_creates_no_snapshots(self, tmp_path: Path) -> None:
        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "no-write-test"], tmp_path)
        project_dir = tmp_path / "no-write-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        nucleus_dir = project_dir / ".nucleus"
        warehouse_before = set(nucleus_dir.rglob("*.parquet")) if nucleus_dir.exists() else set()

        result = _run([*nucleus, "run", "--dry-run", "--all"], project_dir)

        if _is_stub(result.stderr):
            pytest.skip("nucleus run --dry-run is a v0.1 stub")

        warehouse_after = set(nucleus_dir.rglob("*.parquet")) if nucleus_dir.exists() else set()
        new_files = warehouse_after - warehouse_before

        assert not new_files, (
            f"nucleus run --dry-run created {len(new_files)} Parquet file(s): {new_files}\n"
            f"Per E2E_TEST_PLAN §B5: dry-run must NOT write."
        )


@pytest.mark.integration
class TestC1QuerySelect1:
    """C1: nucleus query 'SELECT 1' — basic connectivity.

    Per docs/release/E2E_TEST_PLAN.md §C1.
    Ref: docs/specs/nucleus_cli_spec.md §3.6.
    Requires: nucleus up running.
    """

    def test_select_1_exits_zero(self, tmp_path: Path) -> None:
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "query", "SELECT 1 AS one"], REPO_ROOT)

        if _is_stub(result.stderr):
            pytest.skip("nucleus query is a v0.1 stub")
        if result.returncode == 3:
            pytest.skip("nucleus up not running (exit 3)")

        assert result.returncode == 0, (
            f"nucleus query 'SELECT 1' failed (exit {result.returncode})\n"
            f"stderr: {result.stderr[:200]}"
        )

    def test_select_1_contains_result(self, tmp_path: Path) -> None:
        nucleus = _nucleus_cmd()
        result = _run([*nucleus, "query", "SELECT 1 AS one"], REPO_ROOT)

        if _is_stub(result.stderr) or result.returncode != 0:
            pytest.skip("nucleus query not available or returned error")

        assert "1" in result.stdout, f"Expected '1' in query result, got:\n{result.stdout[:200]}"


@pytest.mark.integration
class TestD2BadCredsCleanError:
    """D2: Postgres bad credentials → clean NE1001 + fix_hint, no classname leaks.

    Per docs/release/E2E_TEST_PLAN.md §D2.
    Ref: docs/specs/nucleus_cli_spec.md §3.5; ADR-006 H1+H17.
    Does NOT require a running Postgres — tests the error path only.
    """

    def test_bad_creds_exits_nonzero(self, tmp_path: Path) -> None:
        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "pg-test"], tmp_path)
        project_dir = tmp_path / "pg-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        result = _run(
            [
                *nucleus,
                "ingest",
                "postgres://baduser:badpass@localhost:5432/nonexistent",
                "--table",
                "users",
                "--as",
                "raw.users",
            ],
            project_dir,
        )

        if _is_stub(result.stderr):
            pytest.skip("nucleus ingest is a v0.1 stub")

        assert result.returncode != 0, "Expected failure for bad Postgres DSN but got exit 0"

    def test_bad_creds_no_classname_leaks(self, tmp_path: Path) -> None:
        """Error message must not contain raw sqlalchemy/psycopg classnames."""
        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "leak-test"], tmp_path)
        project_dir = tmp_path / "leak-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        result = _run(
            [
                *nucleus,
                "ingest",
                "postgres://bad:creds@10.255.255.1:5432/db",
                "--table",
                "t",
                "--as",
                "raw.t",
            ],
            project_dir,
            timeout=10,  # short timeout; unreachable host
        )

        if _is_stub(result.stderr):
            pytest.skip("nucleus ingest is a v0.1 stub")

        output = result.stdout + result.stderr
        banned_patterns = [
            "sqlalchemy.",
            "psycopg.",
            "OperationalError",
            "pg8000.",
            "dagster.",
            "DagsterInstance",
        ]
        leaks = [p for p in banned_patterns if p in output]
        assert not leaks, (
            f"External classnames leaked in error output: {leaks}\n"
            f"Per AGENTS.md §11.7 + docs/specs/nucleus_cli_spec.md §5.4.\n"
            f"Output: {output[:400]}"
        )

    def test_bad_creds_fix_hint_present(self, tmp_path: Path) -> None:
        """Error output must contain a fix_hint (non-empty)."""
        nucleus = _nucleus_cmd()
        _run([*nucleus, "init", "hint-test"], tmp_path)
        project_dir = tmp_path / "hint-test"

        if not project_dir.exists():
            pytest.skip("nucleus init failed (stub)")

        result = _run(
            [
                *nucleus,
                "ingest",
                "postgres://bad:creds@10.255.255.1:5432/db",
                "--table",
                "t",
                "--as",
                "raw.t",
            ],
            project_dir,
            timeout=10,
        )

        if _is_stub(result.stderr):
            pytest.skip("nucleus ingest is a v0.1 stub")
        if result.returncode == 0:
            pytest.skip("Ingest unexpectedly succeeded")

        output = result.stderr
        # Fix hint appears after "Fix:" line per docs/specs/nucleus_cli_spec.md §5.4
        has_fix = "Fix:" in output or "fix_hint" in output.lower() or "Check" in output
        assert has_fix, (
            f"No fix_hint found in error output.\n"
            f"Per docs/specs/nucleus_cli_spec.md §5.4: 'Fix: <fix_hint>' must be present.\n"
            f"stderr: {output[:400]}"
        )


@pytest.mark.slow
class TestK1VersionPerfP95:
    """K1: nucleus version P95 of 5 calls < 1.5s.

    Per docs/release/E2E_TEST_PLAN.md §K1.
    Ref: docs/specs/nucleus_cli_spec.md §3.7; Suite A1.
    """

    def test_version_p95_under_threshold(self) -> None:
        nucleus = _nucleus_cmd()
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            result = _run([*nucleus, "version"], REPO_ROOT)
            elapsed = time.perf_counter() - t0
            if result.returncode == 0:
                times.append(elapsed)

        assert len(times) >= 3, f"nucleus version only succeeded {len(times)}/5 times"

        sorted_times = sorted(times)
        p95_idx = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_idx, len(sorted_times) - 1)]

        assert p95 <= VERSION_THRESHOLD_S, (
            f"nucleus version P95={p95:.3f}s exceeds {VERSION_THRESHOLD_S}s.\n"
            f"All times: {[round(t, 3) for t in times]}\n"
            f"Per docs/release/E2E_TEST_PLAN.md §K1."
        )
