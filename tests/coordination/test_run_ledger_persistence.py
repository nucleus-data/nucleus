"""Tests for the durable run ledger (NDJSON persistence) — ADR-025 §P0-2.

Covers T1-T10 from the Wave 2 P0-2 spec:

T1   record_start creates NDJSON file at the expected path
T2   record_finish updates status on disk (persists the finish record)
T3   list() returns records newest-first
T4   list(asset_key=...) filters correctly
T5   list(status=...) filters correctly
T6   tail(n) returns the n most-recent runs
T7   Corrupt NDJSON line is skipped; other records are intact
T8   File is created at <root>/.nucleus/runs/runs.ndjson
T9   Concurrent thread appends do not corrupt the file
T10  1000-entry write + list() stays within a reasonable time budget

Docs:
    - threading: https://docs.python.org/3/library/threading.html
    - pathlib:   https://docs.python.org/3/library/pathlib.html
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from nucleus.coordination.run_ledger import RunLedger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ledger(tmp_path: Path) -> RunLedger:
    return RunLedger(tmp_path)


def _run_file(tmp_path: Path) -> Path:
    return tmp_path / ".nucleus" / "runs" / "runs.ndjson"


# ---------------------------------------------------------------------------
# T1 – record_start creates the NDJSON file
# ---------------------------------------------------------------------------


class TestRecordStart:
    def test_t1_creates_ndjson_file(self, tmp_path: Path) -> None:
        """T1: record_start must create the NDJSON file at the canonical path."""
        ledger = _ledger(tmp_path)
        ledger.record_start("run-001", "raw.orders")
        assert _run_file(tmp_path).is_file()

    def test_file_contains_valid_json_line(self, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        ledger.record_start("run-001", "raw.events", trigger="schedule")
        lines = [l for l in _run_file(tmp_path).read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["run_id"] == "run-001"
        assert data["asset_key"] == "raw.events"
        assert data["status"] == "running"
        assert data["trigger"] == "schedule"

    def test_status_is_running(self, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        ledger.record_start("run-002", "raw.users")
        record = ledger.get("run-002")
        assert record is not None
        assert record.status == "running"


# ---------------------------------------------------------------------------
# T2 – record_finish persists the finish record
# ---------------------------------------------------------------------------


class TestRecordFinish:
    def test_t2_finish_updates_status_on_disk(self, tmp_path: Path) -> None:
        """T2: record_finish must append a terminal-status line to the NDJSON file."""
        ledger = _ledger(tmp_path)
        ledger.record_start("run-010", "raw.orders")
        ledger.record_finish(
            "run-010",
            "success",
            row_count=500,
            duration_ms=1200,
            snapshot_id="snap-abc",
        )
        # Two lines on disk: start + finish.
        lines = [l for l in _run_file(tmp_path).read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        finish_data = json.loads(lines[1])
        assert finish_data["status"] == "success"
        assert finish_data["row_count"] == 500
        assert finish_data["duration_ms"] == 1200
        assert finish_data["snapshot_id"] == "snap-abc"

    def test_get_after_finish_returns_terminal_record(self, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        ledger.record_start("run-011", "staging.events")
        ledger.record_finish("run-011", "failed", error_code="NE2002", error_message="SQL err")
        record = ledger.get("run-011")
        assert record is not None
        assert record.status == "failed"
        assert record.error_code == "NE2002"

    def test_finish_without_prior_start(self, tmp_path: Path) -> None:
        """record_finish without record_start should still persist."""
        ledger = _ledger(tmp_path)
        ledger.record_finish(
            "run-orphan",
            "success",
            asset_key="marts.revenue",
            row_count=100,
        )
        record = ledger.get("run-orphan")
        assert record is not None
        assert record.status == "success"
        assert record.asset_key == "marts.revenue"


# ---------------------------------------------------------------------------
# T3 – list() returns newest-first
# ---------------------------------------------------------------------------


class TestList:
    def test_t3_newest_first_order(self, tmp_path: Path) -> None:
        """T3: list() must return records newest-first by started_at."""
        ledger = _ledger(tmp_path)
        for i in range(5):
            run_id = f"run-{i:03d}"
            ledger.record_start(run_id, f"raw.table{i}")
            ledger.record_finish(run_id, "success")
            time.sleep(0.01)  # ensure distinct timestamps

        records = ledger.list(limit=10)
        assert len(records) == 5
        # Most recent (highest index) should be first.
        for j in range(len(records) - 1):
            assert records[j].started_at >= records[j + 1].started_at

    # ---------------------------------------------------------------------------
    # T4 – list(asset_key=...) filters correctly
    # ---------------------------------------------------------------------------

    def test_t4_asset_key_filter(self, tmp_path: Path) -> None:
        """T4: list(asset_key=...) must only return runs for that asset."""
        ledger = _ledger(tmp_path)
        ledger.record_start("run-a1", "raw.orders")
        ledger.record_start("run-b1", "raw.users")
        ledger.record_start("run-a2", "raw.orders")

        results = ledger.list(asset_key="raw.orders")
        assert all(r.asset_key == "raw.orders" for r in results)
        assert len(results) == 2

    # ---------------------------------------------------------------------------
    # T5 – list(status=...) filters correctly
    # ---------------------------------------------------------------------------

    def test_t5_status_filter(self, tmp_path: Path) -> None:
        """T5: list(status=...) must only return runs with that status."""
        ledger = _ledger(tmp_path)
        ledger.record_start("run-s1", "raw.orders")
        ledger.record_finish("run-s1", "success")
        ledger.record_start("run-s2", "raw.orders")
        ledger.record_finish("run-s2", "failed")
        ledger.record_start("run-s3", "raw.orders")  # still running

        success_runs = ledger.list(status="success")
        assert all(r.status == "success" for r in success_runs)
        assert len(success_runs) == 1
        assert success_runs[0].run_id == "run-s1"

    def test_limit_is_respected(self, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        for i in range(10):
            ledger.record_start(f"run-lim-{i}", "raw.x")
        results = ledger.list(limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# T6 – tail(n) returns n most-recent
# ---------------------------------------------------------------------------


class TestTail:
    def test_t6_tail_returns_n_most_recent(self, tmp_path: Path) -> None:
        """T6: tail(n) must return exactly n runs (newest-first)."""
        ledger = _ledger(tmp_path)
        for i in range(8):
            ledger.record_start(f"run-tail-{i}", "raw.x")
            time.sleep(0.01)

        result = ledger.tail(3)
        assert len(result) == 3
        # The three most-recent should be the last three written.
        assert result[0].run_id == "run-tail-7"
        assert result[1].run_id == "run-tail-6"
        assert result[2].run_id == "run-tail-5"

    def test_tail_with_n_larger_than_total(self, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        ledger.record_start("run-only", "raw.x")
        result = ledger.tail(100)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# T7 – Corrupt NDJSON line is skipped
# ---------------------------------------------------------------------------


class TestCorruptionTolerance:
    def test_t7_corrupt_line_skipped(self, tmp_path: Path) -> None:
        """T7: A single malformed line in the NDJSON file must not crash list()."""
        ndjson = _run_file(tmp_path)
        ndjson.parent.mkdir(parents=True, exist_ok=True)
        # Write a valid line, a corrupt line, and another valid line.
        ndjson.write_text(
            '{"run_id":"good-1","asset_key":"raw.x","started_at":"2026-01-01T00:00:00+00:00",'
            '"status":"success","trigger":"manual"}\n'
            "{{CORRUPT LINE NOT JSON}}\n"
            '{"run_id":"good-2","asset_key":"raw.y","started_at":"2026-01-02T00:00:00+00:00",'
            '"status":"success","trigger":"manual"}\n',
            encoding="utf-8",
        )
        ledger = RunLedger(tmp_path)
        records = ledger.list(limit=100)
        run_ids = {r.run_id for r in records}
        assert "good-1" in run_ids
        assert "good-2" in run_ids


# ---------------------------------------------------------------------------
# T8 – File is at expected canonical path
# ---------------------------------------------------------------------------


class TestFileLocation:
    def test_t8_canonical_path(self, tmp_path: Path) -> None:
        """T8: run file must be at <project_root>/.nucleus/runs/runs.ndjson."""
        ledger = RunLedger(tmp_path)
        ledger.record_start("run-path", "raw.x")
        expected = tmp_path / ".nucleus" / "runs" / "runs.ndjson"
        assert expected.is_file()


# ---------------------------------------------------------------------------
# T9 – Concurrent thread appends
# ---------------------------------------------------------------------------


class TestConcurrentAppends:
    def test_t9_concurrent_appends_no_corruption(self, tmp_path: Path) -> None:
        """T9: Multiple threads appending concurrently must not corrupt the file."""
        ledger = _ledger(tmp_path)
        errors: list[Exception] = []

        def _write(i: int) -> None:
            try:
                run_id = f"concurrent-{i:04d}"
                ledger.record_start(run_id, f"raw.table{i % 5}")
                ledger.record_finish(run_id, "success", row_count=i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        records = ledger.list(limit=100)
        # All 20 runs must be present and have terminal status.
        assert len(records) == 20
        assert all(r.status == "success" for r in records)


# ---------------------------------------------------------------------------
# T10 – 1000-entry performance
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_t10_1000_entry_perf(self, tmp_path: Path) -> None:
        """T10: Write 1000 records; list() must complete in < 2 s."""
        ledger = _ledger(tmp_path)
        for i in range(1000):
            run_id = f"perf-{i:04d}"
            ledger.record_start(run_id, f"raw.t{i % 10}")
            ledger.record_finish(run_id, "success", row_count=i)

        # Fresh ledger to force a cold cache read from disk.
        ledger2 = RunLedger(tmp_path)
        start = time.monotonic()
        records = ledger2.list(limit=1000)
        elapsed = time.monotonic() - start

        assert len(records) == 1000
        assert elapsed < 2.0, f"list(limit=1000) took {elapsed:.2f}s — too slow"
