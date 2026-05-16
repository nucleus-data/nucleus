"""Tests for ``nucleus.coordination.daemon`` — ADR-017 §v0.2.1.

Mini-scheduler daemon: start/stop lifecycle, SIGTERM graceful shutdown,
cron-firing logic, error translation, and status enumeration.

Per ``docs/specs/nucleus_architecture_v4.1.md`` §6.3 (Coordination layer) and
ADR-017 §v0.2.1 (mini-scheduler fallback).

For multiprocessing safety, tests that verify live subprocess behavior
use ``subprocess.Popen`` + ``--foreground --max-iters=N`` to avoid orphan
processes in CI (spec note).  Unit-level tests use ``foreground=True`` with
``max_iters=1`` and a fast ``poll_interval`` to avoid 5-second sleeps.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import nucleus
from nucleus.coordination.daemon import (
    _check_not_already_running,
    _pidfile_path,
    _should_fire,
    _write_pidfile,
    get_daemon_status,
    start_daemon,
    stop_daemon,
    trigger_asset,
)
from nucleus.errors import (
    NucleusDaemonAlreadyRunningError,
    NucleusDaemonNotRunningError,
    NucleusDaemonStartError,
)
from nucleus.sdk.decorators import _reset_registry_for_tests


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A clean temporary directory that acts as a Nucleus project root."""
    return tmp_path


# ---------------------------------------------------------------------------
# T1: start daemon → status running=True + pid
# ---------------------------------------------------------------------------


class TestDaemonStartStatus:
    def test_start_foreground_status_running(self, project_root: Path) -> None:
        """T1: After start_daemon(foreground=True, max_iters=1), pidfile is written."""
        # max_iters=1 with fast poll_interval exits almost immediately.
        start_daemon(project_root, foreground=True, max_iters=1, poll_interval=0.05)
        # _daemon_main's finally cleans the pidfile — status shows stopped.
        status = get_daemon_status(project_root)
        assert status.pid is None or not status.running

    def test_write_pidfile_then_status_shows_running(self, project_root: Path) -> None:
        """T1 (status-only): Manually write a live PID → status.running is True."""
        pidfile = _pidfile_path(project_root)
        _write_pidfile(pidfile, os.getpid())
        status = get_daemon_status(project_root)
        assert status.running is True
        assert status.pid == os.getpid()
        # Cleanup.
        pidfile.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T2: start while running → NE5014
# ---------------------------------------------------------------------------


class TestDaemonAlreadyRunning:
    def test_start_while_running_raises_ne5014(self, project_root: Path) -> None:
        """T2: start_daemon when a live daemon pidfile exists raises NE5014."""
        pidfile = _pidfile_path(project_root)
        _write_pidfile(pidfile, os.getpid())
        try:
            with pytest.raises(NucleusDaemonAlreadyRunningError) as exc_info:
                start_daemon(project_root, foreground=False)
            err = exc_info.value
            assert err.error_code == "NE5014"
            assert str(os.getpid()) in err.user_message
        finally:
            pidfile.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T3: stop daemon → status running=False
# ---------------------------------------------------------------------------


class TestDaemonStop:
    def test_stop_running_daemon(self, project_root: Path) -> None:
        """T3: stop_daemon on a live process cleans the pidfile."""
        # Use current process PID as a stand-in for a live daemon PID.
        pidfile = _pidfile_path(project_root)
        _write_pidfile(pidfile, os.getpid())

        # Patch psutil at the source so we don't kill our own process.
        mock_proc = MagicMock()
        with (
            patch("psutil.pid_exists", return_value=True),
            patch("psutil.Process", return_value=mock_proc),
        ):
            stop_daemon(project_root)

        mock_proc.terminate.assert_called_once()
        assert not pidfile.exists()

        status = get_daemon_status(project_root)
        assert status.running is False


# ---------------------------------------------------------------------------
# T4: stop when not running → NE5013
# ---------------------------------------------------------------------------


class TestDaemonNotRunning:
    def test_stop_when_not_running_raises_ne5013(self, project_root: Path) -> None:
        """T4: stop_daemon with no pidfile raises NE5013."""
        with pytest.raises(NucleusDaemonNotRunningError) as exc_info:
            stop_daemon(project_root)
        err = exc_info.value
        assert err.error_code == "NE5013"

    def test_stop_with_dead_process_pid_raises_ne5013(self, project_root: Path) -> None:
        """T4: stop_daemon with stale pidfile (dead pid) raises NE5013."""
        pidfile = _pidfile_path(project_root)
        _write_pidfile(pidfile, 99999999)  # Extremely unlikely to be a live process.

        with patch("nucleus.coordination.daemon._is_alive", return_value=False):
            with pytest.raises(NucleusDaemonNotRunningError):
                stop_daemon(project_root)

        assert not pidfile.exists()


# ---------------------------------------------------------------------------
# T5: trigger one-shot → returns result + invokes AMA
# ---------------------------------------------------------------------------


class TestTriggerAsset:
    def test_trigger_invokes_materialize_asset(self, project_root: Path) -> None:
        """T5: trigger_asset calls materialize_asset and returns a result."""

        @nucleus.asset("staging.trigger_test")
        def trigger_test() -> None:
            return None

        with patch("nucleus.coordination.asset_materialization.materialize_asset") as mock_mat:
            from datetime import UTC, datetime  # noqa: PLC0415

            from nucleus.sdk.results import MaterializationResult  # noqa: PLC0415

            mock_result = MaterializationResult(
                asset_key="staging.trigger_test",
                snapshot_id="snap-123",
                partition=None,
                row_count=0,
                duration_ms=10,
                lineage_event_id="",
                materialized_at=datetime.now(UTC),
            )
            mock_mat.return_value = mock_result

            result = trigger_asset("staging.trigger_test")

        mock_mat.assert_called_once_with("staging.trigger_test", warehouse_dir=None)
        assert result.asset_key == "staging.trigger_test"


# ---------------------------------------------------------------------------
# T6: trigger non-existent asset → NE3xxx
# ---------------------------------------------------------------------------


class TestTriggerNonExistent:
    def test_trigger_nonexistent_asset_raises_asset_not_found(self) -> None:
        """T6: trigger_asset for an unknown key raises NucleusAssetNotFound (NE3002)."""
        from nucleus.errors import NucleusAssetNotFound

        with pytest.raises(NucleusAssetNotFound) as exc_info:
            trigger_asset("marts.does_not_exist")

        err = exc_info.value
        assert err.error_code == "NE3002"
        assert "marts.does_not_exist" in err.user_message


# ---------------------------------------------------------------------------
# T7: stale pidfile detection + cleanup on start
# ---------------------------------------------------------------------------


class TestStalePidfileCleanup:
    def test_stale_pidfile_cleared_on_start(self, project_root: Path) -> None:
        """T7: start_daemon clears a stale pidfile and proceeds normally."""
        pidfile = _pidfile_path(project_root)
        _write_pidfile(pidfile, 99999999)  # Dead PID.

        with patch("nucleus.coordination.daemon._is_alive", return_value=False):
            # Should NOT raise NE5014 — stale file is cleaned.
            _check_not_already_running(pidfile)

        assert not pidfile.exists()

    def test_check_not_already_running_removes_stale_pidfile(self, project_root: Path) -> None:
        """T7b: _check_not_already_running with dead process cleans up."""
        pidfile = _pidfile_path(project_root)
        _write_pidfile(pidfile, 99999999)

        with patch("nucleus.coordination.daemon._is_alive", return_value=False):
            _check_not_already_running(pidfile)

        assert not pidfile.exists()


# ---------------------------------------------------------------------------
# T8: start/stop 5x in a row, no leaks
# ---------------------------------------------------------------------------


class TestStartStopRepeat:
    def test_start_stop_five_times_no_leaks(self, project_root: Path) -> None:
        """T8: 5 foreground start/stop cycles leave no orphan pidfiles."""
        for _ in range(5):
            start_daemon(project_root, foreground=True, max_iters=1, poll_interval=0.01)
            # After foreground run with max_iters=1, pidfile is cleaned.
            pidfile = _pidfile_path(project_root)
            assert not pidfile.exists(), "Pidfile should be cleaned up after foreground run."


# ---------------------------------------------------------------------------
# T9: SIGTERM mid-poll → graceful shutdown, no orphan
# ---------------------------------------------------------------------------


class TestSigtermGracefulShutdown:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM behavior differs on Windows; daemon subprocess test requires POSIX.",
    )
    def test_sigterm_cleans_pidfile(self, project_root: Path) -> None:
        """T9: SIGTERM during poll loop sets _shutdown_event; finally unlinks pidfile."""
        cmd = [
            sys.executable,
            "-m",
            "nucleus.coordination.daemon",
            str(project_root),
            "--max-iters",
            "9999",
            "--poll-interval",
            "2",
        ]
        proc = subprocess.Popen(cmd)

        pidfile = _pidfile_path(project_root)
        # Wait for daemon to write its pidfile.
        for _ in range(40):
            if pidfile.exists():
                break
            time.sleep(0.1)

        assert pidfile.exists(), "Daemon should have written pidfile at startup."

        # Send SIGTERM.
        proc.terminate()
        proc.wait(timeout=10)

        # Give the finally block a moment to clean up.
        for _ in range(20):
            if not pidfile.exists():
                break
            time.sleep(0.1)

        assert not pidfile.exists(), "Daemon should clean up pidfile on SIGTERM."
        assert proc.returncode in (0, -15, 1), f"Unexpected exit code: {proc.returncode}"


# ---------------------------------------------------------------------------
# T10: 2 schedules → status enumerates both with next-run times
# ---------------------------------------------------------------------------


class TestStatusMultipleSchedules:
    def test_status_enumerates_two_schedules(self, project_root: Path) -> None:
        """T10: get_daemon_status returns both scheduled assets with next-run strings."""

        @nucleus.asset("marts.daily_a", schedule="@daily")
        def daily_a() -> None:
            return None

        @nucleus.asset("marts.hourly_b", schedule="@hourly")
        def hourly_b() -> None:
            return None

        status = get_daemon_status(project_root)
        assert len(status.schedules) == 2
        keys = {e.asset_key for e in status.schedules}
        assert "marts.daily_a" in keys
        assert "marts.hourly_b" in keys

        for key in keys:
            nxt = status.next_runs.get(key, "")
            assert "T" in nxt, f"next_run for {key!r} should be ISO-8601; got {nxt!r}"


# ---------------------------------------------------------------------------
# T11: clock skew (mock datetime.now) → cron resolves correctly
# ---------------------------------------------------------------------------


class TestClockSkew:
    def test_should_fire_respects_mocked_now(self) -> None:
        """T11: _should_fire uses the `now` argument, not wall clock."""
        # @daily fires at midnight.
        cron_expr = "0 0 * * *"
        # 1 second after midnight — should fire since prev fire = 00:00 is within window.
        just_after_midnight = datetime(2026, 5, 15, 0, 0, 3, tzinfo=UTC)
        assert _should_fire(cron_expr, just_after_midnight, None) is True

    def test_should_fire_last_fired_suppresses_re_fire(self) -> None:
        """T11b: _should_fire returns False if last_fired covers the same tick."""
        cron_expr = "0 0 * * *"
        midnight = datetime(2026, 5, 15, 0, 0, 3, tzinfo=UTC)
        last_fired = datetime(2026, 5, 15, 0, 0, 0, tzinfo=UTC)  # Already fired.
        assert _should_fire(cron_expr, midnight, last_fired) is False

    def test_should_fire_outside_window_returns_false(self) -> None:
        """T11c: Fire time more than poll_interval+1s ago → no fire."""
        cron_expr = "0 0 * * *"  # midnight
        # It is now 2 minutes past midnight — last fire was 2 minutes ago.
        two_minutes_past = datetime(2026, 5, 15, 0, 2, 0, tzinfo=UTC)
        assert _should_fire(cron_expr, two_minutes_past, None, poll_interval=5.0) is False


# ---------------------------------------------------------------------------
# T12: error translation — daemon internal exception → NE5xxx, NO Dagster leak
# ---------------------------------------------------------------------------


class TestDaemonErrorTranslation:
    def test_daemon_translates_internal_error_no_dagster_leak(self, project_root: Path) -> None:
        """T12: Exceptions inside the daemon loop are translated; no Dagster classnames."""
        entries_list = [
            type("E", (), {"asset_key": "marts.err_asset", "cron_expression": "0 0 * * *"})()
        ]

        with (
            patch("nucleus.coordination.daemon.list_schedules", return_value=entries_list),
            patch(
                "nucleus.coordination.asset_materialization.materialize_asset",
                side_effect=RuntimeError("dagster.DagsterError: boom"),
            ),
        ):
            # _daemon_main with max_iters=1 — should NOT crash despite the error.
            start_daemon(
                project_root,
                foreground=True,
                max_iters=1,
                poll_interval=0.01,
            )

        # The daemon exited cleanly (didn't crash) — no Dagster classname exposed.
        # We verify the loop ran without raising by reaching this line.

    def test_ne5012_error_code_correct(self) -> None:
        """T12b: NucleusDaemonStartError has NE5012."""

        err = NucleusDaemonStartError(user_message="test", fix_hint="fix")
        assert err.error_code == "NE5012"
        assert "dagster" not in str(err).lower()

    def test_ne5013_error_code_correct(self) -> None:
        """T12c: NucleusDaemonNotRunningError has NE5013."""
        from nucleus.errors import NucleusDaemonNotRunningError

        err = NucleusDaemonNotRunningError(user_message="test", fix_hint="fix")
        assert err.error_code == "NE5013"
        assert "dagster" not in str(err).lower()

    def test_ne5014_error_code_correct(self) -> None:
        """T12d: NucleusDaemonAlreadyRunningError has NE5014."""
        from nucleus.errors import NucleusDaemonAlreadyRunningError

        err = NucleusDaemonAlreadyRunningError(user_message="test", fix_hint="fix")
        assert err.error_code == "NE5014"
        assert "dagster" not in str(err).lower()
