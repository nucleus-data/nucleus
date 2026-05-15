"""Post-commit Iceberg snapshot maintenance — keep snapshot counts manageable.

Per ``nucleus_architecture_v4.1.md`` §6.2 (AMA step 3 post-commit cleanup)
and ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-3.

Without periodic expiry, every ``nucleus run`` appends a new Iceberg snapshot.
After 100+ snapshots, the filesystem catalog's metadata read slows down because
``pyiceberg`` loads all snapshot entries into memory to resolve the current
snapshot chain.  ``expire_old_snapshots`` is called by the AMA after each
successful commit (only when the table has more than ``_TRIGGER_THRESHOLD``
snapshots, to avoid per-run I/O overhead).

## pyiceberg 0.11.1 API — verified 2026-05-15

Official method chain (tested against installed 0.11.1):

    table.maintenance.expire_snapshots().older_than(dt).commit()

``table.maintenance`` → ``MaintenanceTable`` (``pyiceberg.table.maintenance``)
``MaintenanceTable.expire_snapshots()`` → ``ExpireSnapshots`` builder
    (``pyiceberg.table.update.snapshot.ExpireSnapshots``)
``ExpireSnapshots.older_than(dt: datetime)`` → tags all unprotected snapshots
    with ``timestamp_ms < dt`` for expiry; protected snapshots (branch/tag
    HEADs) are automatically skipped.
``ExpireSnapshots.commit()`` → writes the ``RemoveSnapshotsUpdate`` to the
    catalog transaction.

NOTE: ``by_id`` / ``by_ids`` can target individual snapshots if needed.
Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)

## Configurable via nucleus_project.yaml

    maintenance:
      snapshot_retain_days: 30     # default
      snapshot_min_keep: 10        # always retain this many snapshots regardless of age

# Stability: Beta (v0.2)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from nucleus.errors import NucleusMaintenanceError

logger = logging.getLogger(__name__)

# Trigger expiry only when the table has more snapshots than this value.
# Avoids per-run I/O overhead on freshly-created tables.
_TRIGGER_THRESHOLD: int = 100


def expire_old_snapshots(
    table: Any,
    *,
    retain_days: int = 30,
    min_snapshots: int = 10,
) -> int:
    """Expire Iceberg snapshots older than *retain_days* days, keeping at
    least *min_snapshots* recent snapshots.

    This function is called by the AMA after a successful Iceberg commit
    when ``len(table.snapshots()) > _TRIGGER_THRESHOLD``.

    Args:
        table: A live ``pyiceberg.table.Table`` instance.
        retain_days: Snapshots older than this many days are eligible for
            expiry (default 30).  Must be ≥ 1.
        min_snapshots: Minimum number of most-recent snapshots to retain
            regardless of age (default 10).  Must be ≥ 1.

    Returns:
        Number of snapshots expired (0 if nothing to expire or skipped).

    Raises:
        NucleusMaintenanceError: Any pyiceberg exception during the expiry
            commit.  The materialisation itself succeeded; this exception is
            logged but does NOT roll back the committed snapshot.

    Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)
    Per ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-3.
    """
    # Lazy import — maintenance is not on the hot path.
    # Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)
    try:
        from pyiceberg.table.update.snapshot import ExpireSnapshots  # noqa: F401
    except ImportError as exc:
        raise NucleusMaintenanceError(
            user_message="pyiceberg is not installed; snapshot maintenance requires it.",
            fix_hint="Install pyiceberg: pip install pyiceberg==0.11.1",
            asset=getattr(table, "name", lambda: None)(),
        ) from exc

    if retain_days < 1:
        raise ValueError(f"retain_days must be ≥ 1, got {retain_days}")
    if min_snapshots < 1:
        raise ValueError(f"min_snapshots must be ≥ 1, got {min_snapshots}")

    try:
        all_snapshots = list(table.snapshots())
    except Exception as exc:
        raise NucleusMaintenanceError(
            user_message=(
                "Failed to read the snapshot list during maintenance. "
                "The materialisation succeeded; check the Iceberg catalog."
            ),
            fix_hint="Inspect the catalog.db for corruption or disk space issues.",
            cause=exc,
        ) from exc

    if len(all_snapshots) <= min_snapshots:
        logger.debug(
            "snapshot_maintenance: %d snapshots ≤ min_keep=%d; skipping",
            len(all_snapshots),
            min_snapshots,
        )
        return 0

    # Sort by timestamp ascending (oldest first) to respect min_snapshots.
    sorted_snapshots = sorted(all_snapshots, key=lambda s: s.timestamp_ms)
    # Never expire the *min_snapshots* most recent ones.
    keep_cutoff = (
        sorted_snapshots[-min_snapshots].timestamp_ms
        if len(sorted_snapshots) >= min_snapshots
        else 0
    )
    # Also never expire anything newer than retain_days.
    retain_cutoff_ms = int((datetime.now(UTC) - timedelta(days=retain_days)).timestamp() * 1000)
    # Expire threshold = min(keep_cutoff, retain_cutoff_ms) so BOTH guards apply.
    expire_before_ms = min(keep_cutoff, retain_cutoff_ms)

    candidates = [s for s in sorted_snapshots if s.timestamp_ms < expire_before_ms]
    if not candidates:
        logger.debug(
            "snapshot_maintenance: no snapshots eligible for expiry (retain_days=%d, min_keep=%d)",
            retain_days,
            min_snapshots,
        )
        return 0

    expire_before_dt = datetime.fromtimestamp(expire_before_ms / 1000.0, tz=UTC)

    try:
        # Actual pyiceberg 0.11.1 API (verified 2026-05-15):
        # table.maintenance.expire_snapshots().older_than(dt).commit()
        # Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)
        table.maintenance.expire_snapshots().older_than(expire_before_dt).commit()
    except Exception as exc:
        raise NucleusMaintenanceError(
            user_message=(
                "Snapshot expiry failed after a successful materialisation. "
                "No data was lost; old snapshots will accumulate until the "
                "next successful maintenance run."
            ),
            fix_hint=(
                "Check disk space and catalog.db permissions. "
                "Re-run `nucleus run <asset>` to retry maintenance."
            ),
            cause=exc,
        ) from exc

    n_expired = len(candidates)
    logger.debug(
        "snapshot_maintenance: expired %d snapshot(s) older than %s",
        n_expired,
        expire_before_dt.isoformat(),
    )
    return n_expired


__all__ = ["expire_old_snapshots"]
