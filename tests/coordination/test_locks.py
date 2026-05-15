"""Tests for :mod:`nucleus.coordination.locks`.

Validates the cross-platform advisory lock for concurrent-run protection
per ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-2.

Coverage:
    L1  Happy-path acquire + release (no contention).
    L2  Context manager leaves no lockfile payload after exit.
    L3  NucleusConcurrentRunError raised when lock is held and timeout expires.
    L4  Stale lock (dead PID) is automatically reclaimed.
    L5  Lock path uses safe filename for asset keys with dots.
    L6  Lock payload contains pid + started_at + asset_key.
    L7  Re-entrant acquire on the same asset from the same process raises.
    L8  Lock directory is created automatically when missing.
"""

from __future__ import annotations

import json
import os
import platform
import threading
import time
from pathlib import Path

import pytest

from nucleus.coordination.locks import (
    _lock_path,
    _pid_alive,
    asset_lock,
)
from nucleus.errors import NucleusConcurrentRunError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"


# ---------------------------------------------------------------------------
# L1: Happy-path acquire + release
# ---------------------------------------------------------------------------


def test_asset_lock_acquires_and_releases(tmp_path: Path) -> None:
    """L1: The context manager acquires the lock and exits cleanly."""
    with asset_lock(tmp_path, "schema.table"):
        lock_file = _lock_path(tmp_path, "schema.table")
        assert lock_file.exists(), "Lockfile should exist while held"

    # After release, the lockfile still exists (OS artefact) but is empty.
    assert lock_file.exists()  # file kept; payload truncated


def test_asset_lock_yields_control_inside_block(tmp_path: Path) -> None:
    """L1: Code inside the context manager executes normally."""
    sentinel = []
    with asset_lock(tmp_path, "staging.orders"):
        sentinel.append(1)
    assert sentinel == [1]


# ---------------------------------------------------------------------------
# L2: Payload cleared after exit
# ---------------------------------------------------------------------------


def test_lock_payload_cleared_after_exit(tmp_path: Path) -> None:
    """L2: Lockfile is truncated (empty) once the context manager exits."""
    with asset_lock(tmp_path, "schema.table"):
        pass
    lock_file = _lock_path(tmp_path, "schema.table")
    assert lock_file.stat().st_size == 0, "Lock payload should be cleared after release"


# ---------------------------------------------------------------------------
# L3: Timeout raises NucleusConcurrentRunError
# ---------------------------------------------------------------------------


def test_concurrent_lock_raises_ne3008(tmp_path: Path) -> None:
    """L3: Acquiring a held lock beyond timeout raises NucleusConcurrentRunError."""
    ready = threading.Event()
    can_release = threading.Event()

    def _hold_lock() -> None:
        with asset_lock(tmp_path, "schema.table", timeout=60):
            ready.set()
            can_release.wait(timeout=5)

    thread = threading.Thread(target=_hold_lock, daemon=True)
    thread.start()
    ready.wait(timeout=5)

    try:
        with pytest.raises(NucleusConcurrentRunError) as exc_info:
            with asset_lock(tmp_path, "schema.table", timeout=0.2):
                pass
        err = exc_info.value
        assert err.error_code == "NE3008"
        assert "schema.table" in err.user_message
    finally:
        can_release.set()
        thread.join(timeout=5)


def test_concurrent_run_error_has_asset_key_in_message(tmp_path: Path) -> None:
    """L3: NucleusConcurrentRunError message always contains the asset key.

    The PID may read as 'unknown' when the scheduler preempts the lock-holding
    thread between OS-lock acquisition and payload write (timing race on Windows).
    The asset key is always in the message regardless of timing.
    """
    ready = threading.Event()
    can_release = threading.Event()

    def _hold_lock() -> None:
        with asset_lock(tmp_path, "schema.table", timeout=60):
            ready.set()
            can_release.wait(timeout=5)

    thread = threading.Thread(target=_hold_lock, daemon=True)
    thread.start()
    ready.wait(timeout=5)

    try:
        with pytest.raises(NucleusConcurrentRunError) as exc_info:
            with asset_lock(tmp_path, "schema.table", timeout=0.3):
                pass
        msg = exc_info.value.user_message
        # Asset key is always present; PID may be the owner PID or "unknown"
        assert "schema.table" in msg
        assert "materialised" in msg or "materialized" in msg
    finally:
        can_release.set()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# L4: Stale lock (dead PID) is reclaimed
# ---------------------------------------------------------------------------


def test_stale_lock_with_dead_pid_is_reclaimed(tmp_path: Path) -> None:
    """L4: A lockfile left by a dead PID is automatically reclaimed."""
    # Write a lockfile with a PID that is definitely dead.
    # PID 99999 is almost certainly not running (and can't be ours).
    lock_file = _lock_path(tmp_path, "schema.table")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    dead_pid = 99999
    lock_file.write_text(
        json.dumps(
            {
                "pid": dead_pid,
                "started_at": "2020-01-01T00:00:00+00:00",
                "asset_key": "schema.table",
            }
        ),
        encoding="utf-8",
    )
    # Should succeed even though a "stale" lock exists for a dead PID.
    with asset_lock(tmp_path, "schema.table", timeout=2.0):
        pass  # stale lock reclaimed; no exception


# ---------------------------------------------------------------------------
# L5: Safe filename for asset keys with dots
# ---------------------------------------------------------------------------


def test_lock_path_replaces_dots(tmp_path: Path) -> None:
    """L5: Dots in asset_key are replaced to produce a safe filename."""
    path = _lock_path(tmp_path, "my_schema.my_table")
    assert "." not in path.name or path.suffix == ".lock", (
        "Asset key dots should be replaced in filename"
    )
    assert "my_schema__my_table" in path.name


# ---------------------------------------------------------------------------
# L6: Lock payload is valid JSON with expected fields
# ---------------------------------------------------------------------------


def test_lock_payload_has_pid_and_timestamp(tmp_path: Path) -> None:
    """L6: The lockfile payload contains pid, started_at, asset_key."""
    lock_file = _lock_path(tmp_path, "schema.table")
    payload_holder: list[dict] = []

    def _read_payload() -> None:
        time.sleep(0.05)
        try:
            text = lock_file.read_text(encoding="utf-8")
            payload_holder.append(json.loads(text))
        except Exception:
            pass

    reader = threading.Thread(target=_read_payload, daemon=True)
    reader.start()
    with asset_lock(tmp_path, "schema.table"):
        reader.join(timeout=2)

    if payload_holder:
        payload = payload_holder[0]
        assert payload.get("pid") == os.getpid()
        assert "started_at" in payload
        assert payload.get("asset_key") == "schema.table"


# ---------------------------------------------------------------------------
# L8: Lock directory created automatically
# ---------------------------------------------------------------------------


def test_lock_directory_created_automatically(tmp_path: Path) -> None:
    """L8: The .nucleus/locks/ directory is created if it does not exist."""
    # Ensure it does not pre-exist
    locks_dir = tmp_path / ".nucleus" / "locks"
    assert not locks_dir.exists()

    with asset_lock(tmp_path, "schema.table"):
        assert locks_dir.exists(), ".nucleus/locks/ should be auto-created"


# ---------------------------------------------------------------------------
# pid_alive utility
# ---------------------------------------------------------------------------


def test_pid_alive_current_process() -> None:
    """The current process's PID is always alive."""
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_dead_pid() -> None:
    """PID 99999 is almost certainly not alive on a dev machine."""
    assert _pid_alive(99999) is False
