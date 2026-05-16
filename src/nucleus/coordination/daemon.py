"""Mini-scheduler daemon — lightweight cron-driven materialization loop.

Per ``docs/specs/nucleus_architecture_v4.1.md`` (Dagster wrapped OR mini-scheduler
fallback by v1.0) and ``AGENTS.md`` §4, we ship the mini-scheduler in
v0.2.1 rather than wrap Dagster's heavy ``SchedulerDaemon`` (which requires
``DagsterInstance`` + workspace config + ``DAGSTER_HOME`` env var — too
heavy for our beachhead).  Dagster's role is preserved for orchestration
semantics via ``coordination/asset_materialization.py``; only the *trigger*
layer is in-house.  This decision is ratified in ADR-017 §v0.2.1 amendment.

Design:
    - Lifecycle: ``subprocess.Popen`` spawns a detached daemon process;
      pidfile at ``<project_root>/.nucleus/.daemon.pid``.
    - Loop: every ``_POLL_INTERVAL`` seconds, walk the schedule registry;
      for each schedule due in the last window, call ``materialize_asset``.
    - One-shot trigger: direct ``materialize_asset`` call (no daemon needed).
    - Graceful shutdown: ``SIGTERM`` / ``SIGINT`` sets ``_shutdown_event``;
      ``finally`` block cleans the pidfile.

Docs (croniter): https://github.com/kiorky/croniter  (croniter==3.0.4)
Docs (psutil):   https://psutil.readthedocs.io/en/latest/ (psutil==7.2.2)

# Stability: Beta
"""

from __future__ import annotations

import importlib
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from nucleus.coordination.error_translation import translate
from nucleus.coordination.schedules import ScheduleEntry, list_schedules, preview_schedule
from nucleus.errors import (
    NucleusDaemonAlreadyRunningError,
    NucleusDaemonNotRunningError,
    NucleusDaemonStartError,
    NucleusError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLL_INTERVAL: Final[float] = 5.0  # seconds between cron polls
_PIDFILE_NAME: Final[str] = ".daemon.pid"
_NUCLEUS_DIR: Final[str] = ".nucleus"

# Module-level shutdown event — set by signal handlers to stop the main loop.
# Cleared at the start of every _daemon_main call so tests can re-use the module.
_shutdown_event: threading.Event = threading.Event()


# ---------------------------------------------------------------------------
# Pidfile helpers
# ---------------------------------------------------------------------------


def _pidfile_path(project_root: Path) -> Path:
    return project_root / _NUCLEUS_DIR / _PIDFILE_NAME


def _read_pidfile(pidfile: Path) -> int:
    """Read the PID from *pidfile*; raise NucleusDaemonNotRunningError on parse error."""
    try:
        return int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise NucleusDaemonNotRunningError(
            user_message="Daemon pidfile is unreadable or corrupt.",
            fix_hint="Run `nucleus schedule on` to start a fresh daemon.",
            cause=exc,
        ) from exc


def _write_pidfile(pidfile: Path, pid: int) -> None:
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(pid), encoding="utf-8")


# ---------------------------------------------------------------------------
# Process-liveness helpers
# ---------------------------------------------------------------------------


def _is_alive(pid: int) -> bool:
    """Cross-platform: True if *pid* is a running process.

    Docs: https://psutil.readthedocs.io/en/latest/#psutil.pid_exists
    (psutil==7.2.2)
    """
    import psutil  # Docs: https://psutil.readthedocs.io/ (psutil==7.2.2)

    try:
        return bool(psutil.pid_exists(pid))
    except Exception:
        return False


def _check_not_already_running(pidfile: Path) -> None:
    """Raise NE5014 if a live daemon exists; silently clear a stale pidfile."""
    if not pidfile.exists():
        return
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pidfile.unlink(missing_ok=True)
        return
    if _is_alive(pid):
        raise NucleusDaemonAlreadyRunningError(
            user_message=f"Nucleus scheduler daemon is already running (pid {pid}).",
            fix_hint=(
                "Run `nucleus schedule off` to stop it first, "
                "or `nucleus schedule status` to inspect."
            ),
        )
    # Stale pidfile — process is dead; clean up and allow fresh start.
    pidfile.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Asset bootstrap (inline — cannot import from cli/ per layering rules)
# ---------------------------------------------------------------------------


def _bootstrap_assets(project_root: Path) -> None:
    """Populate the in-process ``@nucleus.asset`` registry for *project_root*.

    Inline equivalent of ``cli.main._import_assets_package``.  Cannot
    import from ``cli/`` due to the strict L2-cannot-import-L4 rule enforced
    by ``scripts/check_layering.py``.

    Import failures are non-fatal — the daemon runs with an empty registry
    (zero schedules fire) rather than crashing.
    """
    assets_dir = project_root / "assets"
    if not assets_dir.is_dir():
        return
    project_str = str(project_root.resolve())
    if project_str not in sys.path:
        sys.path.insert(0, project_str)
    try:
        importlib.invalidate_caches()
        importlib.import_module("assets")
        for child in sorted(assets_dir.iterdir()):
            if child.suffix == ".py" and child.name != "__init__.py":
                importlib.import_module(f"assets.{child.stem}")
    except Exception:  # non-fatal
        pass


# ---------------------------------------------------------------------------
# Cron-firing logic
# ---------------------------------------------------------------------------


def _should_fire(
    cron_expr: str,
    now: datetime,
    last_fired: datetime | None,
    *,
    poll_interval: float = _POLL_INTERVAL,
) -> bool:
    """True if *cron_expr* has a due fire-time in the last *poll_interval* + 1s window.

    Uses ``croniter.get_prev`` to find the most recent past fire time.
    Returns False if that time is outside the window OR was already handled.

    Docs: https://github.com/kiorky/croniter#cron-expression (croniter==3.0.4)
    """
    try:
        from croniter import croniter
    except ImportError:
        return False

    itr = croniter(cron_expr, now)
    prev_fire: datetime = itr.get_prev(datetime)

    # Require prev_fire to be within the rolling window.
    window_start = now - timedelta(seconds=poll_interval + 1)
    if prev_fire < window_start:
        return False
    # Skip if we already fired this particular tick.
    if last_fired is not None and last_fired >= prev_fire:
        return False
    return True


# ---------------------------------------------------------------------------
# Daemon main loop
# ---------------------------------------------------------------------------


def _handle_shutdown(signum: int, frame: object) -> None:  # noqa: ARG001
    _shutdown_event.set()


def _daemon_main(
    project_root: Path,
    *,
    max_iters: int | None = None,
    poll_interval: float = _POLL_INTERVAL,
) -> None:
    """Cron-poll loop — runs until SIGTERM/SIGINT fires or max_iters is reached.

    Writes/cleans the pidfile in the foreground-start path.  The subprocess
    path writes the pidfile from the parent; the daemon's ``finally`` block
    always unlinks it on exit regardless of how it was started.

    Per ``docs/specs/nucleus_architecture_v4.1.md`` §4 (mini-scheduler fallback) and
    ADR-017 §v0.2.1.
    """
    _shutdown_event.clear()  # Reset so tests can call _daemon_main multiple times.

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle_shutdown)
        except (OSError, ValueError):
            pass  # Platform may not support all signals (e.g. Windows SIGTERM).

    pidfile = _pidfile_path(project_root)
    last_fired: dict[str, datetime] = {}
    iters: int = 0

    try:
        while not _shutdown_event.is_set():
            now = datetime.now(UTC)

            try:
                entries = list_schedules()
            except Exception as exc:
                _ = translate(exc)  # translate but don't crash; next poll resumes
                entries = ()

            for entry in entries:
                if _should_fire(
                    entry.cron_expression,
                    now,
                    last_fired.get(entry.asset_key),
                    poll_interval=poll_interval,
                ):
                    try:
                        from nucleus.coordination.asset_materialization import (
                            materialize_asset,
                        )

                        materialize_asset(entry.asset_key)
                        last_fired[entry.asset_key] = now
                    except NucleusError:
                        pass  # Typed errors don't crash the daemon; next poll retries.
                    except Exception as exc:
                        _ = translate(exc)

            iters += 1
            if max_iters is not None and iters >= max_iters:
                break

            _shutdown_event.wait(timeout=poll_interval)
    finally:
        pidfile.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class DaemonStatus:
    """Runtime status of the Nucleus mini-scheduler daemon.

    # Stability: Beta
    """

    running: bool
    pid: int | None
    schedules: tuple[ScheduleEntry, ...] = field(default_factory=tuple)
    next_runs: dict[str, str] = field(default_factory=dict)


def start_daemon(
    project_root: Path,
    *,
    foreground: bool = False,
    max_iters: int | None = None,
    poll_interval: float = _POLL_INTERVAL,
) -> int:
    """Start the Nucleus scheduler daemon.

    Args:
        project_root: Root directory of the Nucleus project (contains
            ``nucleus_project.yaml``).  The pidfile and the daemon's
            working context are anchored here.
        foreground: When ``True``, run the daemon loop in the current
            process (blocking).  Used by ``nucleus schedule on --foreground``
            and by tests.  Default ``False`` spawns a detached subprocess.
        max_iters: Debug/test parameter — exit after this many poll
            iterations.  Only meaningful when ``foreground=True`` or when
            the daemon is spawned via ``__main__``.
        poll_interval: Seconds between cron polls (default 5.0).

    Returns:
        The daemon's PID.

    Raises:
        NucleusDaemonAlreadyRunningError (NE5014): A live daemon is already
            running at *project_root*.
        NucleusDaemonStartError (NE5012): Subprocess could not be spawned.

    Per ADR-017 §v0.2.1 (mini-scheduler fallback).
    """
    pidfile = _pidfile_path(project_root)
    try:
        _check_not_already_running(pidfile)
    except NucleusDaemonAlreadyRunningError:
        raise
    except Exception as exc:
        raise NucleusDaemonStartError(
            user_message=f"Failed to start the Nucleus scheduler daemon: {exc}",
            fix_hint="Check that the project root is a valid Nucleus project.",
            cause=exc,
        ) from exc

    if foreground:
        _write_pidfile(pidfile, os.getpid())
        _daemon_main(project_root, max_iters=max_iters, poll_interval=poll_interval)
        return os.getpid()

    # Spawn a detached subprocess running this module as __main__.
    # The subprocess writes its own pidfile on start so start_daemon
    # can return immediately without a race on the pidfile.
    cmd = [
        sys.executable,
        "-m",
        "nucleus.coordination.daemon",
        str(project_root.resolve()),
    ]
    if max_iters is not None:
        cmd += ["--max-iters", str(max_iters)]
    if poll_interval != _POLL_INTERVAL:
        cmd += ["--poll-interval", str(poll_interval)]

    spawn_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        spawn_kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        spawn_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **spawn_kwargs)
    except Exception as exc:
        raise NucleusDaemonStartError(
            user_message=f"Failed to spawn the scheduler daemon subprocess: {exc}",
            fix_hint=("Ensure `nucleus` is installed correctly and the project root exists."),
            cause=exc,
        ) from exc

    assert proc.pid is not None  # Popen.pid is set immediately after start.
    # Wait briefly then check pidfile written by child.
    for _ in range(20):
        if pidfile.exists():
            break
        time.sleep(0.05)

    return proc.pid


def stop_daemon(project_root: Path, *, timeout: int = 10) -> None:
    """Stop the Nucleus scheduler daemon.

    Sends SIGTERM (POSIX) / ``TerminateProcess`` (Windows) via psutil and
    waits *timeout* seconds.  Escalates to SIGKILL on timeout.  Always
    removes the pidfile on exit.

    Raises:
        NucleusDaemonNotRunningError (NE5013): No live daemon found.
    """
    pidfile = _pidfile_path(project_root)
    if not pidfile.exists():
        raise NucleusDaemonNotRunningError(
            user_message="No Nucleus scheduler daemon is running (no pidfile found).",
            fix_hint="Run `nucleus schedule on` to start the daemon first.",
        )

    pid = _read_pidfile(pidfile)
    if not _is_alive(pid):
        pidfile.unlink(missing_ok=True)
        raise NucleusDaemonNotRunningError(
            user_message=f"Nucleus scheduler daemon (pid {pid}) is not running.",
            fix_hint="Run `nucleus schedule on` to start a new daemon.",
        )

    import psutil  # Docs: https://psutil.readthedocs.io/ (psutil==7.2.2)

    try:
        proc = psutil.Process(pid)
        proc.terminate()  # SIGTERM on POSIX; TerminateProcess on Windows.
        proc.wait(timeout=timeout)
    except psutil.NoSuchProcess:
        pass  # Already gone.
    except psutil.TimeoutExpired:
        try:
            proc.kill()  # SIGKILL on POSIX; TerminateProcess /F on Windows.
        except psutil.NoSuchProcess:
            pass
    except Exception:
        pass
    finally:
        pidfile.unlink(missing_ok=True)


def trigger_asset(
    asset_key: str,
    *,
    warehouse_dir: Path | None = None,
) -> Any:
    """Trigger an immediate one-shot materialization, bypassing the cron schedule.

    Does NOT require the daemon to be running.  Delegates directly to
    :func:`nucleus.coordination.asset_materialization.materialize_asset`.

    Returns:
        :class:`nucleus.sdk.results.MaterializationResult`

    Raises:
        NucleusAssetNotFound (NE3002): *asset_key* is not in the registry.
        NucleusError: Any error produced by the AMA.
    """
    from nucleus.coordination.asset_materialization import (
        materialize_asset,
    )

    try:
        return materialize_asset(asset_key, warehouse_dir=warehouse_dir)
    except NucleusError:
        raise
    except Exception as exc:
        raise translate(exc) from exc


def run_asset(
    asset_key: str,
    *,
    partition: str | None = None,
    dry_run: bool = False,
    warehouse_dir: Path | None = None,
    memory_limit: str | None = None,
    lock_timeout: float = 30.0,
    snapshot_retain_days: int = 30,
    snapshot_min_keep: int = 10,
) -> Any:
    """Mini-scheduler asset entry point — empirical composability proof.

    # Stability: Beta

    This function is the explicit, named alternative entry point for the
    Dagster → mini-scheduler swap target documented in
    ``docs/specs/nucleus_architecture_v4.1.md`` §6.7 (mini-scheduler) + §9.3
    (composability constitution: interface + smoke tests).  It is the path
    the integration test ``tests/integration/test_dagster_to_mini_scheduler_swap.py``
    exercises to verify the swap boundary works end-to-end without
    importing Dagster.

    When ``NUCLEUS_USE_MINI_SCHEDULER=1`` is exported, the default
    :func:`nucleus.coordination.asset_materialization.materialize_asset`
    entry point routes through this function — proving the swap is real.
    Otherwise this function works exactly like :func:`trigger_asset`,
    delegating to the AMA helpers; the data write path has been
    Dagster-free since the 2026-05-14 beachhead E2E fix (Option A,
    ``coordination/asset_materialization.py`` docstring), so both routes
    converge on the same helpers — the empirical proof is the equivalent
    :class:`MaterializationResult` returned from both entry points.

    Args:
        asset_key, partition, dry_run, warehouse_dir, memory_limit,
        lock_timeout, snapshot_retain_days, snapshot_min_keep: see
        :func:`nucleus.coordination.asset_materialization.materialize_asset`
        for full descriptions.  ``upstream`` is fixed to ``"skip"``
        (v0.1 scope) and ``timeout_seconds`` is omitted (accepted but
        not enforced at the AMA layer).

    Returns:
        :class:`nucleus.sdk.results.MaterializationResult`

    Raises:
        NucleusAssetNotFound (NE3002), NucleusError: see AMA contract.
    """
    from nucleus.coordination.asset_materialization import (
        materialize_asset,
    )

    try:
        return materialize_asset(
            asset_key,
            partition=partition,
            dry_run=dry_run,
            warehouse_dir=warehouse_dir,
            memory_limit=memory_limit,
            lock_timeout=lock_timeout,
            snapshot_retain_days=snapshot_retain_days,
            snapshot_min_keep=snapshot_min_keep,
            _via_mini_scheduler=True,
        )
    except NucleusError:
        raise
    except Exception as exc:
        raise translate(exc) from exc


def get_daemon_status(project_root: Path) -> DaemonStatus:
    """Return the current daemon status and active schedule overview.

    # Stability: Beta
    """
    pidfile = _pidfile_path(project_root)
    running = False
    pid: int | None = None

    if pidfile.exists():
        try:
            candidate = int(pidfile.read_text(encoding="utf-8").strip())
            if _is_alive(candidate):
                running = True
                pid = candidate
        except (OSError, ValueError):
            pass

    entries = list_schedules()
    next_runs: dict[str, str] = {}
    for entry in entries:
        try:
            times = preview_schedule(entry.asset_key, n=1)
            next_runs[entry.asset_key] = times[0] if times else ""
        except NucleusError:
            next_runs[entry.asset_key] = ""

    return DaemonStatus(
        running=running,
        pid=pid,
        schedules=entries,
        next_runs=next_runs,
    )


__all__ = [
    "DaemonStatus",
    "get_daemon_status",
    "run_asset",
    "start_daemon",
    "stop_daemon",
    "trigger_asset",
]


# ---------------------------------------------------------------------------
# __main__ — daemon subprocess entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nucleus mini-scheduler daemon")
    parser.add_argument("project_root", help="Project root directory")
    parser.add_argument("--max-iters", type=int, default=None, dest="max_iters")
    parser.add_argument("--poll-interval", type=float, default=_POLL_INTERVAL, dest="poll_interval")
    cli_args = parser.parse_args()

    _proj = Path(cli_args.project_root)

    # Write our own PID so start_daemon(foreground=False) can read it
    # immediately after the subprocess starts.
    _pf = _pidfile_path(_proj)
    _pf.parent.mkdir(parents=True, exist_ok=True)
    _pf.write_text(str(os.getpid()), encoding="utf-8")

    _bootstrap_assets(_proj)
    _daemon_main(
        _proj,
        max_iters=cli_args.max_iters,
        poll_interval=cli_args.poll_interval,
    )
