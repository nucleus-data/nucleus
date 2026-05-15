"""B4 — Concurrent-run safety benchmark.

Verifies the perf doc §5 + §8 row #6 claims:

    Two `nucleus run my_asset` from different terminals → exactly one
    snapshot per logical run, zero data corruption, the loser blocks
    cleanly or surfaces NE3008 (NucleusConcurrentRunError) within
    `lock_timeout`.

NB on error code drift: perf doc §8 row #6 reads "NE5002" for the
concurrent case, but the actual implementation in
``src/nucleus/coordination/locks.py`` raises
:class:`nucleus.errors.NucleusConcurrentRunError` whose ``error_code`` is
"NE3008" (per ``src/nucleus/errors.py`` line 885 + ADR-024 P0-2). The
"NE5002" in the perf doc is reserved for ``NucleusAuthError``. We surface
the discrepancy in the report rather than fixing the perf doc here
(other workers own that file).

How the test runs:

1. Spawn a helper module (``_b4_worker.py``) that defines an asset whose
   body sleeps long enough for the two processes to overlap, then
   commits a tiny DataFrame to a shared warehouse.
2. Launch two of those workers as ``subprocess.Popen`` with the same
   asset key + warehouse + holdtime.
3. Wait for both; classify outcomes:
       (winner_count == 1, blocked_count == 1) → PASS
       (winner_count == 2)                     → FAIL [BLOCKER] data race
       (winner_count == 0)                     → FAIL [BLOCKER] both errored
4. Open the resulting Iceberg table and assert ``row_count == expected``
   for the single-winner case (no silent partial commits).

Docs:
    Python ``subprocess.Popen`` —
        https://docs.python.org/3/library/subprocess.html
    Per perf doc §5 + §8 row #6, AGENTS.md §11.7, ADR-024 P0-2.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    HIGH,
    MEDIUM,
    PASS,
    BenchResult,
    BenchRow,
    benchmark_clock,
    fmt_seconds,
    now_iso,
    write_result,
)

# Worker hold-time (seconds) — needs to be > both processes' import + warm-up
# cost so the two definitely overlap inside the lock-protected region.
DEFAULT_HOLD_S: float = 5.0
# Per-process subprocess timeout (must exceed `hold_s` plus AMA overhead).
PROC_TIMEOUT_S: float = 90.0


def _write_worker_module(tmp_dir: Path, hold_s: float) -> Path:
    """Write a tiny worker script that materialises a registered asset.

    The script imports nucleus, registers ``bench.concurrent_target``,
    pretends to do work (``time.sleep``) inside the asset body so the
    two processes overlap, then commits a small DataFrame to the shared
    warehouse. Output: a JSON line on stdout with ``ok``, ``role``
    (winner / loser / error), and ``snapshot_id`` / ``error_code``.
    """
    src = textwrap.dedent(f"""
        from __future__ import annotations
        import json
        import sys
        import time
        from pathlib import Path

        ROLE = sys.argv[1]
        WAREHOUSE = Path(sys.argv[2])

        # Make the repo's src/ importable when running from a non-installed checkout.
        repo_root = Path(__file__).resolve().parent.parent.parent
        src_dir = repo_root / "src"
        if src_dir.is_dir() and str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/
        import nucleus
        from nucleus.errors import NucleusError

        @nucleus.asset("bench.concurrent_target")
        def body() -> pl.DataFrame:
            time.sleep({hold_s!r})
            return pl.DataFrame({{
                "id": [1, 2, 3, 4, 5],
                "role": [ROLE, ROLE, ROLE, ROLE, ROLE],
            }})

        started = time.perf_counter()
        try:
            result = nucleus.materialize("bench.concurrent_target", warehouse_dir=WAREHOUSE)
            print(json.dumps({{
                "ok": True,
                "role": ROLE,
                "outcome": "winner",
                "snapshot_id": result.snapshot_id,
                "row_count": result.row_count,
                "duration_ms": result.duration_ms,
                "wall_s": time.perf_counter() - started,
            }}))
        except NucleusError as exc:
            print(json.dumps({{
                "ok": True,
                "role": ROLE,
                "outcome": "loser",
                "error_code": getattr(exc, "error_code", "unknown"),
                "user_message": exc.user_message[:240],
                "wall_s": time.perf_counter() - started,
            }}))
        except BaseException as exc:  # noqa: BLE001 — surface anything unexpected
            print(json.dumps({{
                "ok": False,
                "role": ROLE,
                "outcome": "error",
                "type": type(exc).__name__,
                "msg": str(exc)[:240],
                "wall_s": time.perf_counter() - started,
            }}))
    """).strip()
    worker = tmp_dir / "_b4_worker.py"
    worker.write_text(src, encoding="utf-8")
    return worker


def _run_worker(python_exe: str, worker: Path, role: str, warehouse: Path) -> dict[str, object]:
    """Run one worker process and parse the JSON-line outcome."""
    import json

    proc = subprocess.run(
        [python_exe, str(worker), role, str(warehouse)],
        capture_output=True,
        text=True,
        check=False,
        timeout=PROC_TIMEOUT_S,
        encoding="utf-8",
        errors="replace",
    )
    last_line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    try:
        payload = json.loads(last_line) if last_line else {}
    except json.JSONDecodeError:
        payload = {}
    return {
        "rc": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
        "outcome": payload.get("outcome", "unparsed"),
        "error_code": payload.get("error_code"),
        "snapshot_id": payload.get("snapshot_id"),
        "row_count": payload.get("row_count"),
        "wall_s": payload.get("wall_s"),
        "raw_payload": payload,
    }


def _launch_pair(
    python_exe: str,
    worker: Path,
    warehouse: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Start two worker subprocesses overlapping in time, then collect outcomes."""
    import json

    proc_a = subprocess.Popen(
        [python_exe, str(worker), "A", str(warehouse)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # Tiny stagger so process A is guaranteed to grab the lock first.
    time.sleep(0.1)
    proc_b = subprocess.Popen(
        [python_exe, str(worker), "B", str(warehouse)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out_a, err_a = proc_a.communicate(timeout=PROC_TIMEOUT_S)
    out_b, err_b = proc_b.communicate(timeout=PROC_TIMEOUT_S)

    def _parse(out: str, err: str, rc: int, role: str) -> dict[str, object]:
        last_line = (out or "").strip().splitlines()[-1] if out else ""
        try:
            payload = json.loads(last_line) if last_line else {}
        except json.JSONDecodeError:
            payload = {}
        return {
            "role": role,
            "rc": rc,
            "stdout_tail": (out or "")[-1000:],
            "stderr_tail": (err or "")[-1000:],
            "outcome": payload.get("outcome", "unparsed"),
            "error_code": payload.get("error_code"),
            "snapshot_id": payload.get("snapshot_id"),
            "row_count": payload.get("row_count"),
            "wall_s": payload.get("wall_s"),
            "raw_payload": payload,
        }

    return (
        _parse(out_a, err_a, proc_a.returncode, "A"),
        _parse(out_b, err_b, proc_b.returncode, "B"),
    )


def _verify_iceberg_state(warehouse: Path, expected_rows: int) -> tuple[bool, str]:
    """Open the resulting Iceberg table and check row count + snapshot count."""
    try:
        from pyiceberg.catalog import (
            load_catalog,
        )  # Docs: https://py.iceberg.apache.org/api/catalog/

        catalog_db = warehouse / "catalog.db"
        catalog = load_catalog(
            "default",
            type="sql",
            uri=f"sqlite:///{catalog_db.resolve().as_posix()}",
            warehouse=f"file://{warehouse.resolve().as_posix()}",
        )
        table = catalog.load_table(("bench", "concurrent_target"))
        snapshot_count = len(table.snapshots())
        row_count = table.scan().to_arrow().num_rows
    except Exception as exc:  # noqa: BLE001 — surface any pyiceberg failure to caller
        return False, f"verification failed: {type(exc).__name__}: {exc}"

    if row_count != expected_rows:
        return False, (
            f"row count mismatch: expected {expected_rows}, table has {row_count}; "
            f"snapshots={snapshot_count}"
        )
    return True, f"row_count={row_count}, snapshots={snapshot_count}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nucleus B4 — Concurrent-run safety benchmark.")
    parser.add_argument(
        "--hold",
        type=float,
        default=DEFAULT_HOLD_S,
        help="Seconds the worker sleeps inside the asset body (forces overlap). "
        f"Default: {DEFAULT_HOLD_S}",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()

    base_dir = Path(tempfile.mkdtemp(prefix="nucleus_bench_b4_"))
    warehouse = base_dir / "warehouse"
    warehouse.mkdir(parents=True, exist_ok=True)
    print(f"[B4] working dir: {base_dir}")
    print(f"[B4] hold (overlap) seconds: {args.hold}")

    worker = _write_worker_module(base_dir, args.hold)
    python = sys.executable

    rows: list[BenchRow] = []
    notes: list[str] = []
    raw: dict[str, object] = {}

    print(f"[B4] launching two parallel workers ...")
    res_a, res_b = _launch_pair(python, worker, warehouse)
    raw["proc_a"] = res_a
    raw["proc_b"] = res_b

    outcomes = (res_a["outcome"], res_b["outcome"])
    print(f"[B4] outcomes: A={outcomes[0]} B={outcomes[1]}")

    winner_count = sum(1 for o in outcomes if o == "winner")
    loser_count = sum(1 for o in outcomes if o == "loser")
    error_count = sum(1 for o in outcomes if o not in ("winner", "loser"))

    # PASS shape: exactly one winner + one loser; loser surfaces NE3008.
    if winner_count == 1 and loser_count == 1 and error_count == 0:
        loser = res_a if res_a["outcome"] == "loser" else res_b
        loser_code = str(loser.get("error_code") or "")
        # Per perf doc §5: NE3008 is the actual code (perf doc says NE5002 — see
        # the module docstring for the discrepancy note).
        if loser_code != "NE3008":
            rows.append(
                BenchRow(
                    metric="loser error code",
                    claim_ref="perf doc §5 + §8 row #6",
                    claim="NE3008 (NucleusConcurrentRunError)",
                    measured=loser_code or "(unset)",
                    verdict=FAIL,
                    severity=HIGH,
                    note=(
                        "Perf doc §8 row #6 says NE5002 — that's a doc bug; actual code "
                        "is NE3008 per src/nucleus/errors.py:885."
                    ),
                )
            )
        else:
            rows.append(
                BenchRow(
                    metric="loser error code",
                    claim_ref="perf doc §5 (corrected)",
                    claim="NE3008",
                    measured="NE3008",
                    verdict=PASS,
                )
            )
        rows.append(
            BenchRow(
                metric="winner / loser split",
                claim_ref="perf doc §8 row #6",
                claim="exactly 1 winner + 1 blocked-or-failed",
                measured=f"winners={winner_count} losers={loser_count}",
                verdict=PASS,
            )
        )
    elif winner_count == 2:
        rows.append(
            BenchRow(
                metric="winner / loser split",
                claim_ref="perf doc §8 row #6",
                claim="exactly 1 winner",
                measured=f"BOTH committed snapshots: A={res_a['snapshot_id']}, B={res_b['snapshot_id']}",
                verdict=FAIL,
                severity=BLOCKER,
                note="Lock did NOT serialise; possible silent data race per perf doc §6.2 row #1.",
            )
        )
    elif winner_count == 0:
        rows.append(
            BenchRow(
                metric="winner / loser split",
                claim_ref="perf doc §8 row #6",
                claim="exactly 1 winner",
                measured="zero winners (both errored)",
                verdict=FAIL,
                severity=BLOCKER,
                note=f"A.outcome={res_a['outcome']!r} B.outcome={res_b['outcome']!r}",
            )
        )
    else:
        rows.append(
            BenchRow(
                metric="winner / loser split",
                claim_ref="perf doc §8 row #6",
                claim="exactly 1 winner + 1 blocked-or-failed",
                measured=f"winners={winner_count} losers={loser_count} errors={error_count}",
                verdict=FAIL,
                severity=HIGH,
                note="unexpected outcome combination",
            )
        )

    # Verify Iceberg state — exactly 5 rows (the worker DataFrame size).
    ok, detail = _verify_iceberg_state(warehouse, expected_rows=5)
    rows.append(
        BenchRow(
            metric="post-race Iceberg state",
            claim_ref="perf doc §8 row #6",
            claim="row_count = 5 (one snapshot's worth, no double-write)",
            measured=detail,
            verdict=PASS if ok else FAIL,
            severity="" if ok else BLOCKER,
        )
    )

    # Surface a wall-clock note for context — the loser should give up
    # quickly (lock contention is fast), the winner takes hold + commit time.
    rows.append(
        BenchRow(
            metric="winner wall-clock",
            claim_ref="informational",
            claim=f"~{args.hold + 5.0:.1f}s (hold + commit overhead)",
            measured=fmt_seconds(
                float((res_a if res_a["outcome"] == "winner" else res_b).get("wall_s") or 0.0)
            ),
            verdict=PASS,
            note="not a budget claim; recorded for context",
        )
    )
    rows.append(
        BenchRow(
            metric="loser wall-clock",
            claim_ref="informational",
            claim="< winner wall-clock (released early)",
            measured=fmt_seconds(
                float((res_a if res_a["outcome"] == "loser" else res_b).get("wall_s") or 0.0)
            ),
            verdict=PASS,
            note="not a budget claim; recorded for context",
        )
    )

    overall = PASS if all(r.verdict == PASS for r in rows) else FAIL

    if overall != PASS:
        notes.append(f"A stdout tail: {res_a['stdout_tail'][-500:]}")
        notes.append(f"B stderr tail: {res_b['stderr_tail'][-500:]}")

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B4: Concurrent run safety",
        script="scripts/benchmarks/b4_concurrent_run.py",
        command=f"{python} -m scripts.benchmarks.b4_concurrent_run --hold {args.hold}",
        started_at=started_at,
        completed_at=completed_at,
        elapsed_s=elapsed_total,
        overall_verdict=overall,
        rows=rows,
        notes=notes,
        raw=raw,
    )

    out = write_result(result)
    print()
    print(f"[B4] wrote {out}")
    print(f"[B4] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    # Cleanup
    shutil.rmtree(base_dir, ignore_errors=True)
    return 0 if overall == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
