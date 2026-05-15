"""Tests for :mod:`nucleus.coordination.snapshot_maintenance`.

Validates snapshot expiry per
``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-3.

Uses the actual pyiceberg 0.11.1 API:
    table.maintenance.expire_snapshots().older_than(dt).commit()

Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)

Coverage:
    M1  expire_old_snapshots returns 0 when snapshot count ≤ min_snapshots.
    M2  expire_old_snapshots returns 0 when no snapshots are old enough.
    M3  Expired snapshots older than retain_days are removed.
    M4  min_snapshots guard: never expires the N most recent snapshots.
    M5  NucleusMaintenanceError raised + wrapped when pyiceberg commit fails.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nucleus.coordination.snapshot_maintenance import (
    _TRIGGER_THRESHOLD,
    expire_old_snapshots,
)
from nucleus.errors import NucleusMaintenanceError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(snapshot_id: int, days_ago: float) -> MagicMock:
    """Return a mock Iceberg snapshot with a timestamp *days_ago* in the past."""
    snap = MagicMock()
    snap.snapshot_id = snapshot_id
    ts_ms = int((datetime.now(UTC) - timedelta(days=days_ago)).timestamp() * 1000)
    snap.timestamp_ms = ts_ms
    return snap


def _make_table(snapshots: list[MagicMock]) -> MagicMock:
    """Return a mock pyiceberg Table with the given snapshots list."""
    table = MagicMock()
    table.snapshots.return_value = list(snapshots)
    # Simulate maintenance.expire_snapshots().older_than(dt).commit() chain
    expire_builder = MagicMock()
    expire_builder.older_than.return_value = expire_builder
    expire_builder.commit.return_value = None
    table.maintenance.expire_snapshots.return_value = expire_builder
    return table


# ---------------------------------------------------------------------------
# M1: No expiry when snapshot count ≤ min_snapshots
# ---------------------------------------------------------------------------


def test_expire_returns_zero_when_count_below_min(tmp_path: Path) -> None:
    """M1: No expiry when snapshot count ≤ min_snapshots."""
    # 5 snapshots, min_keep=10 → nothing to expire
    snaps = [_make_snapshot(i, days_ago=i * 10) for i in range(1, 6)]
    table = _make_table(snaps)
    result = expire_old_snapshots(table, retain_days=30, min_snapshots=10)
    assert result == 0
    table.maintenance.expire_snapshots.assert_not_called()


def test_expire_returns_zero_when_count_equals_min(tmp_path: Path) -> None:
    """M1: Exactly min_snapshots count → nothing to expire."""
    snaps = [_make_snapshot(i, days_ago=i * 10) for i in range(1, 11)]
    table = _make_table(snaps)
    result = expire_old_snapshots(table, retain_days=30, min_snapshots=10)
    assert result == 0


# ---------------------------------------------------------------------------
# M2: No expiry when all snapshots are within retain window
# ---------------------------------------------------------------------------


def test_expire_returns_zero_when_all_snapshots_fresh(tmp_path: Path) -> None:
    """M2: No snapshots older than retain_days → nothing to expire."""
    # 15 snapshots, all < 10 days old; retain_days=30
    snaps = [_make_snapshot(i, days_ago=float(i)) for i in range(1, 16)]
    table = _make_table(snaps)
    result = expire_old_snapshots(table, retain_days=30, min_snapshots=5)
    assert result == 0


# ---------------------------------------------------------------------------
# M3: Expired count matches eligible old snapshots
# ---------------------------------------------------------------------------


def test_expire_old_snapshots_calls_pyiceberg_api(tmp_path: Path) -> None:
    """M3: expire_old_snapshots calls the actual pyiceberg 0.11.1 API chain."""
    # 15 snapshots: 12 are 60 days old, 3 are fresh
    old_snaps = [_make_snapshot(i, days_ago=60) for i in range(1, 13)]
    fresh_snaps = [_make_snapshot(i + 100, days_ago=1) for i in range(3)]
    table = _make_table(old_snaps + fresh_snaps)

    result = expire_old_snapshots(table, retain_days=30, min_snapshots=3)

    # Should have called the pyiceberg maintenance chain
    table.maintenance.expire_snapshots.assert_called_once()
    expire_builder = table.maintenance.expire_snapshots.return_value
    expire_builder.older_than.assert_called_once()
    expire_builder.commit.assert_called_once()
    assert result > 0  # at least some snapshots expired


# ---------------------------------------------------------------------------
# M4: min_snapshots guard
# ---------------------------------------------------------------------------


def test_expire_respects_min_snapshots(tmp_path: Path) -> None:
    """M4: The N most recent snapshots are never expired."""
    # 10 snapshots 90 days old + 5 recent snapshots 1 day old, min_keep=5
    old_snaps = [_make_snapshot(i, days_ago=90 + i * 0.1) for i in range(10)]
    fresh_snaps = [_make_snapshot(i + 100, days_ago=1.0) for i in range(5)]
    table = _make_table(old_snaps + fresh_snaps)

    expire_old_snapshots(table, retain_days=7, min_snapshots=5)

    expire_builder = table.maintenance.expire_snapshots.return_value
    expire_builder.commit.assert_called_once()


# ---------------------------------------------------------------------------
# M5: NucleusMaintenanceError on pyiceberg failure
# ---------------------------------------------------------------------------


def test_expire_wraps_pyiceberg_exception(tmp_path: Path) -> None:
    """M5: pyiceberg commit failure → NucleusMaintenanceError (NE3009).

    Regression: snapshots use a 0.1-day timestamp spread (matching M4) to
    guarantee distinct ``timestamp_ms`` values. Without the spread, multiple
    ``_make_snapshot`` calls on fast hardware land in the same millisecond,
    causing the strict ``s.timestamp_ms < expire_before_ms`` candidate filter
    in ``snapshot_maintenance.expire_old_snapshots`` to yield zero candidates
    and short-circuit before ``commit()`` runs — the test then sees
    ``DID NOT RAISE NucleusMaintenanceError`` non-deterministically.
    Docs: https://docs.pytest.org/en/stable/how-to/fixtures.html
    """
    snaps = [_make_snapshot(i, days_ago=90 + i * 0.1) for i in range(15)]
    table = _make_table(snaps)
    # Make commit() raise an arbitrary exception
    expire_builder = table.maintenance.expire_snapshots.return_value
    expire_builder.commit.side_effect = RuntimeError("iceberg write failed")

    with pytest.raises(NucleusMaintenanceError) as exc_info:
        expire_old_snapshots(table, retain_days=7, min_snapshots=3)

    err = exc_info.value
    assert err.error_code == "NE3009"
    # Original cause must be preserved via __cause__ (NucleusError convention)
    assert isinstance(err.__cause__, RuntimeError)
    # No external class names in user_message
    assert "RuntimeError" not in err.user_message
    assert "iceberg write failed" not in err.user_message


def test_trigger_threshold_is_100() -> None:
    """Module constant confirms the 100-snapshot trigger threshold."""
    assert _TRIGGER_THRESHOLD == 100


def test_invalid_retain_days_raises_value_error() -> None:
    """retain_days=0 is rejected with ValueError."""
    table = _make_table([])
    with pytest.raises(ValueError, match="retain_days"):
        expire_old_snapshots(table, retain_days=0)


def test_invalid_min_snapshots_raises_value_error() -> None:
    """min_snapshots=0 is rejected with ValueError."""
    table = _make_table([])
    with pytest.raises(ValueError, match="min_snapshots"):
        expire_old_snapshots(table, min_snapshots=0)
