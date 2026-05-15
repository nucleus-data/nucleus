"""Tests for the active-scheduling daemon CLI subcommands — ADR-017 §v0.2.1.

Validates:
    - ``nucleus schedule on``   → exits 0, success message printed
    - ``nucleus schedule status`` → table rendered with correct columns
    - ``nucleus schedule trigger ASSET`` → exits 0, run identifier printed
    - ``nucleus schedule on --foreground`` → works (foreground=True routed correctly)

All daemon functions (start_daemon, stop_daemon, trigger_asset, get_daemon_status)
are mocked so no background processes are started in CI.

Docs:
    - Typer testing: https://typer.tiangolo.com/tutorial/testing/
    - unittest.mock: https://docs.python.org/3/library/unittest.mock.html
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app
from nucleus.sdk.decorators import _reset_registry_for_tests


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


# Shared mock patches — applied per test via context managers.
_PATCH_IMPORT_ASSETS = patch(
    "nucleus.cli.commands.schedule._import_project_assets",
    return_value=None,
)
_PATCH_LOCATE_ROOT = patch(
    "nucleus.cli.commands.schedule._locate_project_root",
    return_value=Path("/tmp/fake-project"),
)


# ---------------------------------------------------------------------------
# T13: ``nucleus schedule on`` → exit 0, success message
# ---------------------------------------------------------------------------


class TestScheduleOn:
    def test_schedule_on_exits_zero(self, runner: CliRunner) -> None:
        """T13: nucleus schedule on exits 0 and prints the daemon PID."""
        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.start_daemon",
                return_value=12345,
            ) as mock_start,
        ):
            result = runner.invoke(app, ["schedule", "on"])

        assert result.exit_code == 0, f"stdout={result.output} stderr={result.stderr}"
        assert "12345" in result.output
        mock_start.assert_called_once()

    def test_schedule_on_calls_start_daemon_with_correct_args(self, runner: CliRunner) -> None:
        """T13b: schedule on passes foreground=False by default."""
        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.start_daemon",
                return_value=9999,
            ) as mock_start,
        ):
            result = runner.invoke(app, ["schedule", "on"])

        assert result.exit_code == 0
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs.get("foreground") is False

    def test_schedule_on_already_running_exits_nonzero(self, runner: CliRunner) -> None:
        """T13c: schedule on when daemon already running surfaces NE5014."""
        from nucleus.errors import NucleusDaemonAlreadyRunningError

        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.start_daemon",
                side_effect=NucleusDaemonAlreadyRunningError(
                    user_message="Daemon already running (pid 9999).",
                    fix_hint="Run nucleus schedule off first.",
                ),
            ),
        ):
            result = runner.invoke(app, ["schedule", "on"])

        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "already running" in combined.lower() or "NE5014" in combined or "Error" in combined


# ---------------------------------------------------------------------------
# T14: ``nucleus schedule status`` → table rendered, right columns
# ---------------------------------------------------------------------------


class TestScheduleStatus:
    def test_schedule_status_renders_daemon_state(self, runner: CliRunner) -> None:
        """T14: nucleus schedule status shows running/stopped + schedule table."""
        from nucleus.coordination.daemon import DaemonStatus
        from nucleus.coordination.schedules import ScheduleEntry

        fake_status = DaemonStatus(
            running=True,
            pid=42,
            schedules=(ScheduleEntry(asset_key="marts.revenue", cron_expression="0 2 * * *"),),
            next_runs={"marts.revenue": "2026-05-16T02:00:00+00:00"},
        )

        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.get_daemon_status",
                return_value=fake_status,
            ),
        ):
            result = runner.invoke(app, ["schedule", "status"])

        assert result.exit_code == 0, f"stdout={result.output}"
        assert "42" in result.output  # PID present.
        assert "marts.revenue" in result.output
        assert "0 2 * * *" in result.output
        assert "2026-05-16" in result.output  # Next run shown.

    def test_schedule_status_stopped_daemon(self, runner: CliRunner) -> None:
        """T14b: schedule status shows 'stopped' when no daemon is running."""
        from nucleus.coordination.daemon import DaemonStatus

        fake_status = DaemonStatus(running=False, pid=None, schedules=(), next_runs={})

        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.get_daemon_status",
                return_value=fake_status,
            ),
        ):
            result = runner.invoke(app, ["schedule", "status"])

        assert result.exit_code == 0
        assert "stopped" in result.output.lower()

    def test_schedule_status_no_dagster_classnames(self, runner: CliRunner) -> None:
        """T14c: No Dagster classnames in schedule status output."""
        from nucleus.coordination.daemon import DaemonStatus

        fake_status = DaemonStatus(running=False, pid=None, schedules=(), next_runs={})

        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.get_daemon_status",
                return_value=fake_status,
            ),
        ):
            result = runner.invoke(app, ["schedule", "status"])

        combined = (result.output or "") + (result.stderr or "")
        assert "dagster" not in combined.lower()
        assert "ScheduleDefinition" not in combined


# ---------------------------------------------------------------------------
# T15: ``nucleus schedule trigger ASSET`` → exit 0, run identifier printed
# ---------------------------------------------------------------------------


class TestScheduleTrigger:
    def test_trigger_exits_zero_and_prints_snapshot(self, runner: CliRunner) -> None:
        """T15: nucleus schedule trigger exits 0 and prints snapshot ID."""
        import nucleus

        @nucleus.asset("marts.triggered")
        def triggered() -> None:
            return None

        from nucleus.sdk.results import MaterializationResult

        mock_result = MaterializationResult(
            asset_key="marts.triggered",
            snapshot_id="snap-abc123",
            partition=None,
            row_count=5,
            duration_ms=42,
            lineage_event_id="",
            materialized_at=datetime.now(UTC),
        )

        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.trigger_asset",
                return_value=mock_result,
            ) as mock_trig,
        ):
            result = runner.invoke(app, ["schedule", "trigger", "marts.triggered"])

        assert result.exit_code == 0, f"stdout={result.output} stderr={result.stderr}"
        assert "snap-abc123" in result.output
        mock_trig.assert_called_once()

    def test_trigger_unknown_asset_exits_nonzero(self, runner: CliRunner) -> None:
        """T15b: trigger on unknown asset surfaces NE3002."""
        from nucleus.errors import NucleusAssetNotFound

        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.trigger_asset",
                side_effect=NucleusAssetNotFound(
                    user_message="Asset 'marts.ghost' is not defined.",
                    fix_hint="Register it first.",
                    asset="marts.ghost",
                ),
            ),
        ):
            result = runner.invoke(app, ["schedule", "trigger", "marts.ghost"])

        assert result.exit_code != 0
        combined = (result.output or "") + (result.stderr or "")
        assert "Error" in combined


# ---------------------------------------------------------------------------
# T16: ``nucleus schedule on --foreground`` works (mocked to exit immediately)
# ---------------------------------------------------------------------------


class TestScheduleOnForeground:
    def test_schedule_on_foreground_exits_zero(self, runner: CliRunner) -> None:
        """T16: nucleus schedule on --foreground passes foreground=True to start_daemon."""
        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.start_daemon",
                return_value=99,
            ) as mock_start,
        ):
            result = runner.invoke(app, ["schedule", "on", "--foreground"])

        assert result.exit_code == 0, f"stdout={result.output} stderr={result.stderr}"
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs.get("foreground") is True

    def test_schedule_on_foreground_no_dagster_in_output(self, runner: CliRunner) -> None:
        """T16b: No Dagster classnames in foreground output."""
        with (
            _PATCH_IMPORT_ASSETS,
            _PATCH_LOCATE_ROOT,
            patch(
                "nucleus.coordination.daemon.start_daemon",
                return_value=99,
            ),
        ):
            result = runner.invoke(app, ["schedule", "on", "--foreground"])

        combined = (result.output or "") + (result.stderr or "")
        assert "dagster" not in combined.lower()
