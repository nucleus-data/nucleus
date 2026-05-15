"""Cross-platform advisory filesystem lock for concurrent-run protection.

Per ``nucleus_architecture_v4.1.md`` §6.2 (AMA) + §6.4 (Error Translation)
and ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-2.

Prevents two ``nucleus run`` invocations from racing on the same asset's
Iceberg snapshot commit (chaos scenario J6 — silent data loss).

Lock location: ``<project_root>/.nucleus/locks/<asset_key>.lock``

The lockfile contains JSON: ``{"pid": <int>, "started_at": "<iso>"}`` so a
crashed process's stale lock can be detected by checking if the PID is still
alive and automatically reclaimed.

Platform strategy:
    POSIX  — ``fcntl.flock(fd, LOCK_EX | LOCK_NB)``
    Windows — ``msvcrt.locking(fd, LK_NBLCK, 1)``

Using stdlib only (no ``filelock`` dep) to stay within the 30K LOC budget
and avoid adding a required dep for a <200 LOC feature per ADR-024 §Consequences
footnote. The ``filelock`` cross-platform wrapper would also work; we choose
stdlib to keep the dep count minimal.

Docs:
    https://docs.python.org/3/library/fcntl.html  (POSIX)
    https://docs.python.org/3/library/msvcrt.html (Windows)

# Stability: Beta (v0.2)
"""

from __future__ import annotations

import json
import os
import platform
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nucleus.errors import NucleusConcurrentRunError

_IS_WINDOWS: bool = platform.system() == "Windows"

# Sentinel: how long to wait for lock before giving up (default 30 s).
_DEFAULT_TIMEOUT_S: float = 30.0
# Poll interval when the lock is contested.
_POLL_INTERVAL_S: float = 0.2


def _locks_dir(project_root: Path) -> Path:
    """Return the locks directory, creating it if necessary."""
    d = project_root / ".nucleus" / "locks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _lock_path(project_root: Path, asset_key: str) -> Path:
    """Return the lockfile path for *asset_key*.

    Asset keys contain dots (``schema.table``); replace with ``__`` so the
    filename remains shell-safe.
    """
    safe_key = asset_key.replace(".", "__").replace("/", "__").replace("\\", "__")
    return _locks_dir(project_root) / f"{safe_key}.lock"


def _read_lock_info(lock_file: Path) -> dict[str, Any] | None:
    """Return the JSON payload written by the lock owner, or None on any error."""
    try:
        text = lock_file.read_text(encoding="utf-8")
        payload: dict[str, Any] = json.loads(text)
        return payload
    except (OSError, json.JSONDecodeError):
        return None


def _pid_alive(pid: int) -> bool:
    """Return True if *pid* corresponds to a running process.

    Platform strategy:
    - Windows: uses ``psutil.pid_exists(pid)`` (avoids ``os.kill`` which maps
      signal 0 → CTRL_C_EVENT on Windows and can interrupt the current process).
    - POSIX: uses ``os.kill(pid, 0)`` — raises ``ProcessLookupError`` when the
      process is gone, ``PermissionError`` when it exists but we can't send
      signals (still alive).

    Docs (POSIX): https://docs.python.org/3/library/os.html#os.kill
    Docs (Windows): https://psutil.readthedocs.io/en/latest/#psutil.pid_exists
    """
    if _IS_WINDOWS:
        try:
            import psutil  # Docs: https://psutil.readthedocs.io/en/latest/

            return bool(psutil.pid_exists(pid))
        except ImportError:
            # psutil unavailable — fall back to OpenProcess via ctypes.
            # Docs: https://docs.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False

    # POSIX path
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we lack permission — still alive.
        return True
    except OSError:
        return False


def _try_acquire_posix(fd: int) -> bool:
    """Non-blocking exclusive lock attempt on POSIX using ``fcntl.flock``."""
    import fcntl  # type: ignore[import]  # not available on Windows

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _release_posix(fd: int) -> None:
    """Release POSIX flock."""
    import fcntl  # type: ignore[import]

    fcntl.flock(fd, fcntl.LOCK_UN)


def _try_acquire_windows(fd: int) -> bool:
    """Non-blocking exclusive lock attempt on Windows using ``msvcrt.locking``.

    Docs: https://docs.python.org/3/library/msvcrt.html#msvcrt.locking
    Lock 1 byte at offset 0. LK_NBLCK raises ``OSError`` immediately if
    the lock cannot be obtained.
    """
    import msvcrt  # type: ignore[import]  # Windows-only

    try:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
        return True
    except OSError:
        return False


def _release_windows(fd: int) -> None:
    """Release Windows msvcrt lock."""
    import msvcrt  # type: ignore[import]

    try:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    except OSError:
        pass  # already unlocked — harmless


def _try_acquire(fd: int) -> bool:
    """Dispatch to the platform-appropriate non-blocking lock attempt."""
    if _IS_WINDOWS:
        return _try_acquire_windows(fd)
    return _try_acquire_posix(fd)


def _release(fd: int) -> None:
    """Dispatch to the platform-appropriate lock release."""
    if _IS_WINDOWS:
        _release_windows(fd)
    else:
        _release_posix(fd)


@contextmanager
def asset_lock(
    project_root: Path,
    asset_key: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> Generator[None, None, None]:
    """Acquire an exclusive advisory lock for *asset_key*; release on exit.

    Raises :class:`~nucleus.errors.NucleusConcurrentRunError` (NE3008) if the
    lock cannot be obtained within *timeout* seconds.

    The lockfile stores ``{"pid": <int>, "started_at": "<iso>"}`` so a
    CLI status command or operator can inspect which run holds the lock.
    Stale locks (dead PID) are reclaimed automatically.

    Usage::

        with asset_lock(project_root, "schema.table"):
            _commit_to_iceberg(...)

    Args:
        project_root: Root directory of the Nucleus project (same as
            ``nucleus_project.yaml`` location).
        asset_key: Canonical Nucleus asset key (``"schema.table"``).
        timeout: Seconds to wait before raising ``NE3008``. Default 30 s.

    Raises:
        NucleusConcurrentRunError: Lock not obtained within *timeout*.
        OSError: Unexpected filesystem error opening the lockfile.

    Per ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-2.
    """
    lock_file = _lock_path(project_root, asset_key)
    deadline = time.monotonic() + timeout

    # Open (or create) the lockfile. "a+b" creates if absent, appends if
    # present, and leaves existing content readable for stale-lock detection.
    fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        while True:
            acquired = _try_acquire(fd)
            if acquired:
                break

            # Lock contested — check for stale lock before waiting.
            info = _read_lock_info(lock_file)
            if info is not None:
                stale_pid = info.get("pid")
                if stale_pid is not None and not _pid_alive(int(stale_pid)):
                    # Dead PID — truncate and retry immediately.
                    os.ftruncate(fd, 0)
                    os.lseek(fd, 0, os.SEEK_SET)
                    continue

            if time.monotonic() >= deadline:
                owner_pid = info.get("pid", "unknown") if info else "unknown"
                owner_ts = info.get("started_at", "unknown") if info else "unknown"
                raise NucleusConcurrentRunError(
                    user_message=(
                        f"Asset {asset_key!r} is already being materialised "
                        f"(PID {owner_pid}, started {owner_ts}). "
                        f"Wait for it to finish or remove the stale lock at "
                        f"{lock_file}."
                    ),
                    fix_hint=(
                        "If the other run is stuck, kill PID "
                        f"{owner_pid} and delete {lock_file}, "
                        "then retry."
                    ),
                    docs_url="https://nucleus.dev/errors/concurrent-run",
                    asset=asset_key,
                )
            time.sleep(_POLL_INTERVAL_S)

        # Write owner metadata so operators can inspect who holds the lock.
        payload = json.dumps(
            {
                "pid": os.getpid(),
                "started_at": datetime.now(UTC).isoformat(),
                "asset_key": asset_key,
            }
        )
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, payload.encode())

        try:
            yield
        finally:
            _release(fd)
            # Truncate the payload so a future reader can't see stale data.
            try:
                os.ftruncate(fd, 0)
            except OSError:
                pass

    finally:
        try:
            os.close(fd)
        except OSError:
            pass


__all__ = ["asset_lock"]
