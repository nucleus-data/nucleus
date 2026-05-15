"""Durable run ledger — NDJSON append-only persistence.

Per ``nucleus_architecture_v4.1.md`` §6.2 (AMA coordination layer owns run
history) + ADR-025 §P0-2 (run monitoring + persistence).

NDJSON file location::

    <project_root>/.nucleus/runs/runs.ndjson

Each line is a :class:`RunRecord` snapshot.  The file is append-only:
``record_start`` writes a ``"running"`` line; ``record_finish`` writes a
second line with the terminal status.  On load, the **last** record for
each ``run_id`` wins (finish record overwrites the start record in cache).

Thread-safety: a single :class:`threading.Lock` guards all file I/O and
in-memory cache mutations.

Docs (stdlib):
    - json:      https://docs.python.org/3/library/json.html
    - threading: https://docs.python.org/3/library/threading.html
    - pathlib:   https://docs.python.org/3/library/pathlib.html
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_CACHE_MAX = 1000


@dataclass
class RunRecord:
    """One run snapshot.  Serialises to / from the NDJSON line shape.

    ``started_at`` and ``finished_at`` are ISO 8601 strings in UTC
    (``datetime.now(tz=timezone.utc).isoformat()`` format).
    """

    run_id: str
    asset_key: str
    started_at: str  # ISO 8601 UTC ("+00:00" suffix)
    status: str  # "running" | "success" | "failed" | "cancelled"
    trigger: str  # "manual" | "schedule" | "sensor"
    finished_at: str | None = None
    snapshot_id: str | None = None
    row_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    fix_hint: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict (suitable for one NDJSON line)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        """Construct from a parsed NDJSON dict; unknown keys are silently dropped."""
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


class RunLedger:
    """Append-only NDJSON run ledger with in-memory LRU-style cache.

    Instantiate once per project root::

        ledger = RunLedger(project_root)
        ledger.record_start(run_id, "raw.orders", trigger="manual")
        ledger.record_finish(run_id, "success", row_count=1234, duration_ms=4200)
        for r in ledger.list(limit=20):
            print(r.run_id, r.status)

    Architecture: ``nucleus_architecture_v4.1.md`` §6.2 + ADR-025 §P0-2.
    """

    def __init__(self, project_root: Path) -> None:
        self._run_file: Path = project_root / ".nucleus" / "runs" / "runs.ndjson"
        self._lock = threading.Lock()
        self._by_id: dict[str, RunRecord] = {}
        self._ordered: list[RunRecord] = []  # newest-first, ≤ _CACHE_MAX entries
        self._loaded = False

    # ------------------------------------------------------------------
    # Private helpers — must be called with self._lock held
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self._run_file.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: RunRecord) -> None:
        """Write one NDJSON line and flush immediately."""
        self._ensure_dir()
        line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
        with self._run_file.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()

    def _load(self) -> None:
        """Lazily read NDJSON into cache.  Last record per run_id wins."""
        if self._loaded:
            return
        self._by_id.clear()
        if self._run_file.exists():
            try:
                raw_lines = self._run_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                raw_lines = []
            for raw in raw_lines:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = RunRecord.from_dict(json.loads(raw))
                    self._by_id[record.run_id] = record
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue  # tolerate single-line corruption
        self._rebuild_ordered()
        self._loaded = True

    def _rebuild_ordered(self) -> None:
        """Rebuild newest-first ordered slice from the id map."""
        self._ordered = sorted(
            self._by_id.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )[:_CACHE_MAX]

    def _upsert(self, record: RunRecord) -> None:
        """Upsert record into cache; rebuild ordered list."""
        self._by_id[record.run_id] = record
        self._rebuild_ordered()

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def record_start(
        self,
        run_id: str,
        asset_key: str,
        trigger: str = "manual",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a run-started record (status = ``"running"``)."""
        now = datetime.now(tz=UTC).isoformat()
        record = RunRecord(
            run_id=run_id,
            asset_key=asset_key,
            started_at=now,
            status="running",
            trigger=trigger,
            metadata=metadata or {},
        )
        with self._lock:
            self._load()
            self._append(record)
            self._upsert(record)

    def record_finish(
        self,
        run_id: str,
        status: str,
        **fields: Any,
    ) -> None:
        """Persist a run-finished record; overwrites start record in cache.

        ``status`` must be one of ``"success"``, ``"failed"``, ``"cancelled"``.
        Additional keyword arguments map to :class:`RunRecord` fields
        (``row_count``, ``duration_ms``, ``snapshot_id``, ``error_code``,
        ``error_message``, ``fix_hint``, ``metadata``).
        """
        now = datetime.now(tz=UTC).isoformat()
        with self._lock:
            self._load()
            existing = self._by_id.get(run_id)
            updated = RunRecord(
                run_id=run_id,
                asset_key=existing.asset_key if existing else fields.get("asset_key", "unknown"),
                started_at=existing.started_at if existing else fields.get("started_at", now),
                status=status,
                trigger=existing.trigger if existing else fields.get("trigger", "manual"),
                finished_at=fields.get("finished_at", now),
                snapshot_id=fields.get("snapshot_id"),
                row_count=fields.get("row_count"),
                error_code=fields.get("error_code"),
                error_message=fields.get("error_message"),
                fix_hint=fields.get("fix_hint"),
                duration_ms=fields.get("duration_ms"),
                metadata=fields.get("metadata", existing.metadata if existing else {}),
            )
            self._append(updated)
            self._upsert(updated)

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def list(
        self,
        *,
        limit: int = 50,
        asset_key: str | None = None,
        status: str | None = None,
        since: str | None = None,
    ) -> list[RunRecord]:
        """Return runs newest-first, optionally filtered, capped at ``limit``.

        ``since`` is an ISO 8601 UTC string lower bound; runs whose
        ``started_at`` is lexicographically less than ``since`` are excluded.
        """
        with self._lock:
            self._load()
            records: list[RunRecord] = list(self._ordered)
        # Filtering happens outside the lock (records is a snapshot copy).
        if asset_key is not None:
            records = [r for r in records if r.asset_key == asset_key]
        if status is not None:
            records = [r for r in records if r.status == status]
        if since is not None:
            records = [r for r in records if r.started_at >= since]
        return records[:limit]

    def get(self, run_id: str) -> RunRecord | None:
        """Return a single run by exact ID, or ``None`` if absent."""
        with self._lock:
            self._load()
            return self._by_id.get(run_id)

    def tail(self, n: int = 20) -> list[RunRecord]:
        """Return the ``n`` most-recent runs (newest first)."""
        with self._lock:
            self._load()
            return list(self._ordered[:n])

    def cancel(self, run_id: str) -> bool:
        """Mark a running run as cancelled in the ledger.

        Returns ``True`` if the run was in ``"running"`` state and was
        marked cancelled; ``False`` if the run is absent or already in a
        terminal state.

        This is a ledger-only marker — it does not terminate any live
        process.  Send SIGTERM to the ``nucleus run`` process to stop
        execution.
        """
        now = datetime.now(tz=UTC).isoformat()
        with self._lock:
            self._load()
            existing = self._by_id.get(run_id)
            if existing is None or existing.status != "running":
                return False
            updated = RunRecord(
                run_id=run_id,
                asset_key=existing.asset_key,
                started_at=existing.started_at,
                status="cancelled",
                trigger=existing.trigger,
                finished_at=now,
                snapshot_id=existing.snapshot_id,
                row_count=existing.row_count,
                error_code=existing.error_code,
                error_message=existing.error_message,
                fix_hint=existing.fix_hint,
                duration_ms=existing.duration_ms,
                metadata=existing.metadata,
            )
            self._append(updated)
            self._upsert(updated)
        return True
