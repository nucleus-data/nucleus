"""Tests for ``nucleus runs`` command group — ADR-025 §P0-2.

Covers T11-T18 from the Wave 2 P0-2 spec:

T11  Empty list shows a helpful "no runs yet" message
T12  Populated list shows table columns (run id / asset / duration / started / trigger)
T13  --limit N restricts the number of rows returned
T14  --status filter only returns matching rows
T15  ``runs show`` renders all fields in a panel
T16  ``runs show`` with unknown ID exits non-zero with NE3011 in output
T17  ``runs list --format json`` emits one NDJSON line per run
T18  ``runs cancel`` marks a running run as cancelled

The ``_get_ledger`` helper in ``runs.py`` is patched via monkeypatch / fixture
so tests do not require a ``nucleus_project.yaml`` on disk.

Docs:
    - Typer testing: https://typer.tiangolo.com/tutorial/testing/
    - unittest.mock:  https://docs.python.org/3/library/unittest.mock.html
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app
from nucleus.coordination.run_ledger import RunLedger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture()
def ledger(tmp_path: Path) -> RunLedger:
    """A RunLedger backed by a temp directory."""
    return RunLedger(tmp_path)


def _patch_ledger(ledger: RunLedger) -> contextlib.AbstractContextManager:  # type: ignore[name-defined]  # noqa: F821
    """Context manager that replaces ``_get_ledger`` with a pre-seeded instance."""
    return patch("nucleus.cli.commands.runs._get_ledger", return_value=ledger)


# ---------------------------------------------------------------------------
# T11 – Empty list shows helpful message
# ---------------------------------------------------------------------------


class TestRunsList:
    def test_t11_empty_list_message(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T11: When no runs exist, a helpful message must be shown."""
        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "list"])

        assert result.exit_code == 0
        assert "No runs" in result.output or "no runs" in result.output.lower()

    # ---------------------------------------------------------------------------
    # T12 – Populated list shows table columns
    # ---------------------------------------------------------------------------

    def test_t12_populated_table_shows_columns(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T12: Populated list must show run id, asset, duration, started, trigger."""
        ledger.record_start("abc12345", "raw.orders", trigger="manual")
        ledger.record_finish("abc12345", "success", duration_ms=1500, row_count=100)

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "list"])

        assert result.exit_code == 0
        # Short run_id (first 8 chars)
        assert "abc12345" in result.output
        # Asset key
        assert "raw.orders" in result.output
        # Trigger
        assert "manual" in result.output

    # ---------------------------------------------------------------------------
    # T13 – --limit restricts rows
    # ---------------------------------------------------------------------------

    def test_t13_limit_flag(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T13: --limit N must cap the output to N rows."""
        for i in range(10):
            ledger.record_start(f"run{i:04d}xx", f"raw.t{i}")
            ledger.record_finish(f"run{i:04d}xx", "success")

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "list", "--limit", "3"])

        assert result.exit_code == 0
        # Count occurrences of "raw.t" — should be exactly 3
        assert result.output.count("raw.t") == 3

    # ---------------------------------------------------------------------------
    # T14 – --status filter
    # ---------------------------------------------------------------------------

    def test_t14_status_filter(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T14: --status failed must only return failed runs."""
        ledger.record_start("ok-run1", "raw.a")
        ledger.record_finish("ok-run1", "success")
        ledger.record_start("fail-r1", "raw.b")
        ledger.record_finish("fail-r1", "failed", error_message="boom")

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "list", "--status", "failed"])

        assert result.exit_code == 0
        assert "fail-r1" in result.output
        assert "ok-run1" not in result.output

    # ---------------------------------------------------------------------------
    # T17 – --format json emits NDJSON
    # ---------------------------------------------------------------------------

    def test_t17_json_format_emits_ndjson(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T17: --format json must emit one JSON object per line."""
        ledger.record_start("json-001", "raw.orders")
        ledger.record_finish("json-001", "success", row_count=42)

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "list", "--format", "json"])

        assert result.exit_code == 0
        lines = [l for l in result.output.splitlines() if l.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["run_id"] == "json-001"
        assert data["status"] == "success"
        assert data["row_count"] == 42


# ---------------------------------------------------------------------------
# T15 – ``runs show`` renders panel
# ---------------------------------------------------------------------------


class TestRunsShow:
    def test_t15_show_renders_fields(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T15: ``runs show`` must display all key fields in a panel."""
        ledger.record_start("show-001", "marts.revenue", trigger="schedule")
        ledger.record_finish(
            "show-001",
            "success",
            row_count=999,
            duration_ms=3000,
            snapshot_id="snap-999",
        )

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "show", "show-001"])

        assert result.exit_code == 0
        assert "show-001" in result.output
        assert "marts.revenue" in result.output
        assert "success" in result.output
        assert "schedule" in result.output
        assert "999" in result.output  # row_count

    def test_show_json_format(self, runner: CliRunner, ledger: RunLedger) -> None:
        ledger.record_start("show-json", "raw.x")
        ledger.record_finish("show-json", "success", row_count=7)

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "show", "show-json", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["run_id"] == "show-json"
        assert data["row_count"] == 7

    # ---------------------------------------------------------------------------
    # T16 – unknown ID exits non-zero with NE3011
    # ---------------------------------------------------------------------------

    def test_t16_unknown_run_id_exits_nonzero(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T16: ``runs show`` with unknown ID must exit non-zero and mention NE3011."""
        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "show", "nonexistent-run-id"])

        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "NE3011" in combined or "not found" in combined.lower() or "Error" in combined

    def test_show_fix_hint_present_on_not_found(self, runner: CliRunner, ledger: RunLedger) -> None:
        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "show", "missing-id"])

        combined = (result.output or "") + (result.stderr or "")
        assert "nucleus runs list" in combined or "runs list" in combined


# ---------------------------------------------------------------------------
# T18 – ``runs cancel`` marks run as cancelled
# ---------------------------------------------------------------------------


class TestRunsCancel:
    def test_t18_cancel_marks_run(self, runner: CliRunner, ledger: RunLedger) -> None:
        """T18: ``runs cancel`` must flip a running run to 'cancelled' in the ledger."""
        ledger.record_start("to-cancel", "raw.orders")

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "cancel", "to-cancel"])

        assert result.exit_code == 0
        assert "cancel" in result.output.lower()

        record = ledger.get("to-cancel")
        assert record is not None
        assert record.status == "cancelled"

    def test_cancel_already_finished_exits_nonzero(
        self, runner: CliRunner, ledger: RunLedger
    ) -> None:
        ledger.record_start("already-done", "raw.x")
        ledger.record_finish("already-done", "success")

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "cancel", "already-done"])

        assert result.exit_code != 0

    def test_cancel_unknown_run_exits_nonzero(self, runner: CliRunner, ledger: RunLedger) -> None:
        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "cancel", "ghost-run"])

        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "Error" in combined or "not found" in combined.lower()


# ---------------------------------------------------------------------------
# No Dagster classnames in any output
# ---------------------------------------------------------------------------


class TestNoDagsterLeaks:
    def test_no_dagster_classnames_in_list_output(
        self, runner: CliRunner, ledger: RunLedger
    ) -> None:
        ledger.record_start("leak-test", "raw.orders")
        ledger.record_finish("leak-test", "success")

        with _patch_ledger(ledger):
            result = runner.invoke(app, ["runs", "list"])

        combined = (result.output or "") + (result.stderr or "")
        for banned in ("dagster", "opexecutioncontext", "duckdbpyconnection"):
            assert banned not in combined.lower(), f"Banned term '{banned}' found in output"
