"""B2 — Materialize-at-scale benchmark.

Verifies the perf doc §2.2 claims for ``@nucleus.asset`` materialization
to filesystem-backed Iceberg:

    1 GB  → Iceberg : <30 s    , peak RSS <3 GB
    10 GB → Iceberg : <5 min   , peak RSS <4 GB (with Polars streaming)

Why a synthetic dataset:
    The beachhead persona deals with 100 GB - 5 TB *aggregate* data, but
    individual asset bodies typically materialise 1-10 GB (per perf doc
    §1). 10 M and 100 M rows of mixed-type data is a realistic upper
    bound on a single asset, and lets us verify the AMA happy path under
    pressure without depending on TPC-H or any external source.

What's measured for each scale:
    * Wall-clock seconds for the full ``materialize()`` call.
    * Peak Python RSS via :class:`scripts.benchmarks._common.RSSWatcher`.
    * On-disk size of the resulting Iceberg snapshot (sum of all files
      under the table directory after the commit).

What's NOT measured:
    * Read-back performance — that's covered by B1 (TPC-H queries).
    * Schema-evolution overhead — covered by chaos test #5 (perf doc §8).
    * Concurrent commits — covered by B4.

Why we keep 10 GB opt-in:
    Generating + committing 10 GB requires ~25 GB free on a single SSD
    (raw Parquet + Arrow buffer + Iceberg copy + temp). On a 16 GB RAM /
    20 GB free disk laptop that's a tight squeeze, so the script
    auto-skips it unless ``--scale=10`` is set explicitly. The 1 GB run
    is still the canonical PASS/FAIL signal.

Docs:
    DuckDB ``range`` + ``COPY ... TO 'parquet'`` —
        https://duckdb.org/docs/data/parquet/overview.html
    Polars LazyFrame.collect (streaming kwarg) —
        https://docs.pola.rs/api/python/stable/reference/lazyframe/api/polars.LazyFrame.collect.html
    PyIceberg table layout —
        https://py.iceberg.apache.org/configuration/
    Perf claims —
        docs/internal/research/performance_reliability_targets.md §2.2 + §3
"""

from __future__ import annotations

import argparse
import gc
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    HIGH,
    LOW,
    MEDIUM,
    PASS,
    SKIP_DEPS,
    BenchResult,
    BenchRow,
    RSSWatcher,
    benchmark_clock,
    classify,
    ensure_repo_root_on_path,
    fmt_bytes,
    fmt_delta,
    fmt_seconds,
    now_iso,
    severity_for,
    write_result,
)

# Scale presets: rows × ~100 bytes/row ≈ raw size. Compressed-Parquet ratio
# is roughly 4-6× smaller (zstd:3 default per perf doc §4 Disk + I/O).
_SCALES: dict[str, dict[str, object]] = {
    "1": {
        "rows": 10_000_000,
        "label": "1 GB synthetic (10M rows)",
        "claim_wall_s": 30.0,
        "claim_peak_rss_bytes": 3 * 1024**3,
        "asset_key": "bench.synthetic_1g",
    },
    "10": {
        "rows": 100_000_000,
        "label": "10 GB synthetic (100M rows)",
        "claim_wall_s": 300.0,  # 5 minutes per perf doc §2.2
        "claim_peak_rss_bytes": 4 * 1024**3,
        "asset_key": "bench.synthetic_10g",
    },
}

# Free-disk safety floor — refuse the 10 GB run when we can't fit raw + temp.
_MIN_FREE_DISK_GB_10G: float = 25.0
# Free-disk safety floor — refuse the 1 GB run when we can't fit raw + temp.
_MIN_FREE_DISK_GB_1G: float = 5.0


def _generate_parquet_via_duckdb(parquet_path: Path, rows: int) -> tuple[float, int]:
    """Generate a synthetic Parquet file using DuckDB's ``range()`` generator.

    Returns ``(elapsed_seconds, file_size_bytes)``. Uses ``zstd`` compression
    (DuckDB default) which matches what the AMA writes, so the ratio is
    representative.

    Schema (10 columns, mixed types — perf doc §2.2 wording):

        id            BIGINT
        value         DOUBLE
        name          VARCHAR
        ts            TIMESTAMP
        bucket        INTEGER
        grp           VARCHAR
        amount        DOUBLE
        count_col     INTEGER
        flag          BOOLEAN
        descr         VARCHAR
    """
    import duckdb  # Docs: https://duckdb.org/docs/api/python/overview

    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    sql = textwrap.dedent(f"""
        COPY (
            SELECT
                id::BIGINT                                                   AS id,
                (id * 1.234567)::DOUBLE                                      AS value,
                ('name_' || (id % 1000)::VARCHAR)                            AS name,
                TIMESTAMP '2026-01-01' + INTERVAL (id % 86400) SECOND        AS ts,
                (id % 100)::INTEGER                                          AS bucket,
                ('group_' || (id % 50)::VARCHAR)                             AS grp,
                ((id * 7 % 100000) / 100.0)::DOUBLE                          AS amount,
                (id % 100)::INTEGER                                          AS count_col,
                (id % 2 = 0)::BOOLEAN                                        AS flag,
                ('descr_' || (id % 10000)::VARCHAR)                          AS descr
            FROM range(0, {rows}) t(id)
        )
        TO '{parquet_path.as_posix()}'
        (FORMAT PARQUET, COMPRESSION 'zstd', ROW_GROUP_SIZE 122880)
    """).strip()

    started = benchmark_clock()
    con = duckdb.connect()
    try:
        con.execute(sql)
    finally:
        con.close()
    elapsed = benchmark_clock() - started
    return elapsed, parquet_path.stat().st_size


def _warehouse_dir_size(warehouse_dir: Path) -> int:
    """Total byte size of all files under *warehouse_dir* (recursive)."""
    if not warehouse_dir.exists():
        return 0
    return sum(p.stat().st_size for p in warehouse_dir.rglob("*") if p.is_file())


def _materialize_one(
    parquet_path: Path,
    asset_key: str,
    warehouse_dir: Path,
    *,
    use_streaming: bool,
) -> dict[str, object]:
    """Run a single materialize, returning a stats dict.

    The asset is registered inline so each scale gets a fresh registry
    entry. Reading the Parquet uses Polars' lazy API; the optional
    ``streaming=True`` kwarg is the documented out-of-core path
    (see https://docs.pola.rs/user-guide/concepts/streaming/).

    NEEDS VERIFICATION: As of polars 1.18.0 the streaming engine is marked
    "unstable" in the docstring. The kwarg is ``streaming=True`` (boolean),
    NOT ``engine="streaming"`` — confirmed empirically against the pinned
    version's ``LazyFrame.collect`` signature.
    """
    ensure_repo_root_on_path()
    import nucleus  # noqa: F401 — registers @nucleus.asset
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/

    @nucleus.asset(asset_key)
    def _body() -> "pl.DataFrame":
        lf = pl.scan_parquet(parquet_path.as_posix())
        if use_streaming:
            # Polars 1.18.0: collect(streaming=True) — not engine="streaming".
            return lf.collect(streaming=True)
        return lf.collect()

    watcher = RSSWatcher(interval_s=0.05).start()
    started = benchmark_clock()
    try:
        result = nucleus.materialize(asset_key, warehouse_dir=warehouse_dir)
    finally:
        peak_bytes = watcher.stop()
    wall_s = benchmark_clock() - started

    # Free Polars/Arrow buffers before the next iteration so RSSWatcher numbers
    # are not contaminated by the previous scale.
    del _body
    gc.collect()

    snapshot_bytes = _warehouse_dir_size(warehouse_dir)
    return {
        "wall_s": wall_s,
        "peak_rss_bytes": peak_bytes,
        "snapshot_bytes": snapshot_bytes,
        "row_count": result.row_count,
        "snapshot_id": result.snapshot_id,
        "duration_ms_internal": result.duration_ms,
    }


def _claim_row_for_wall(scale: dict[str, object], measured_wall: float) -> BenchRow:
    claim = float(scale["claim_wall_s"])  # type: ignore[arg-type]
    verdict = classify(measured_wall, claim, lower_is_better=True)
    severity = "" if verdict == PASS else severity_for(measured_wall, claim)
    return BenchRow(
        metric=f"{scale['label']} — wall-clock",
        claim_ref="perf doc §2.2",
        claim=f"<{fmt_seconds(claim)}",
        measured=fmt_seconds(measured_wall),
        verdict=verdict,
        delta=fmt_delta(measured_wall, claim),
        severity=severity,
    )


def _claim_row_for_rss(scale: dict[str, object], measured_rss: float) -> BenchRow:
    claim = float(scale["claim_peak_rss_bytes"])  # type: ignore[arg-type]
    verdict = classify(measured_rss, claim, lower_is_better=True)
    severity = "" if verdict == PASS else severity_for(measured_rss, claim)
    return BenchRow(
        metric=f"{scale['label']} — peak RSS",
        claim_ref="perf doc §3",
        claim=f"<{fmt_bytes(claim)}",
        measured=fmt_bytes(measured_rss),
        verdict=verdict,
        delta=fmt_delta(measured_rss, claim),
        severity=severity,
    )


def _run_scale(
    scale: dict[str, object],
    *,
    base_dir: Path,
    use_streaming: bool,
) -> tuple[list[BenchRow], dict[str, object], list[str]]:
    """Run one scale (1 GB or 10 GB); return (rows, raw_stats, notes)."""
    notes: list[str] = []
    rows_out: list[BenchRow] = []
    n_rows = int(scale["rows"])  # type: ignore[arg-type]
    label = str(scale["label"])

    parquet_path = base_dir / f"synth_{n_rows}.parquet"
    warehouse_dir = base_dir / f"warehouse_{n_rows}"

    print(f"[B2] generating Parquet: {label} ({n_rows:,} rows) -> {parquet_path}")
    gen_elapsed, parquet_bytes = _generate_parquet_via_duckdb(parquet_path, n_rows)
    print(f"[B2]   generated {fmt_bytes(parquet_bytes)} in {fmt_seconds(gen_elapsed)}")
    notes.append(
        f"Parquet generation ({label}): {fmt_seconds(gen_elapsed)} "
        f"-> {fmt_bytes(parquet_bytes)} on disk (compressed)."
    )

    print(f"[B2] materialize {scale['asset_key']} (streaming={use_streaming}) ...")
    stats = _materialize_one(
        parquet_path,
        str(scale["asset_key"]),
        warehouse_dir,
        use_streaming=use_streaming,
    )
    print(
        f"[B2]   wall={fmt_seconds(stats['wall_s'])} "  # type: ignore[arg-type]
        f"peak_rss={fmt_bytes(stats['peak_rss_bytes'])} "  # type: ignore[arg-type]
        f"snapshot={fmt_bytes(stats['snapshot_bytes'])} "  # type: ignore[arg-type]
        f"rows={stats['row_count']}"
    )

    rows_out.append(_claim_row_for_wall(scale, float(stats["wall_s"])))  # type: ignore[arg-type]
    rows_out.append(_claim_row_for_rss(scale, float(stats["peak_rss_bytes"])))  # type: ignore[arg-type]

    # Auxiliary informational rows — no PASS/FAIL claim attached.
    rows_out.append(
        BenchRow(
            metric=f"{label} — Iceberg snapshot size",
            claim_ref="perf doc §4 (zstd 4-8x)",
            claim="ratio reported below",
            measured=fmt_bytes(float(stats["snapshot_bytes"])),  # type: ignore[arg-type]
            verdict=PASS,
            delta=(
                f"raw Parquet={fmt_bytes(parquet_bytes)}; "
                f"snapshot/parquet={float(stats['snapshot_bytes']) / max(parquet_bytes, 1):.2f}x"
            ),
        )
    )
    rows_out.append(
        BenchRow(
            metric=f"{label} — row count",
            claim_ref="generator spec",
            claim=f"{n_rows:,}",
            measured=f"{int(stats['row_count']):,}",
            verdict=PASS if int(stats["row_count"]) == n_rows else FAIL,
            delta="0"
            if int(stats["row_count"]) == n_rows
            else (f"+{int(stats['row_count']) - n_rows}"),
            severity="" if int(stats["row_count"]) == n_rows else BLOCKER,
            note="row-count mismatch indicates a write bug, not a perf issue",
        )
    )

    raw = {
        "asset_key": scale["asset_key"],
        "rows_target": n_rows,
        "rows_committed": stats["row_count"],
        "snapshot_id": stats["snapshot_id"],
        "wall_s": stats["wall_s"],
        "peak_rss_bytes": stats["peak_rss_bytes"],
        "snapshot_bytes": stats["snapshot_bytes"],
        "parquet_bytes": parquet_bytes,
        "parquet_gen_s": gen_elapsed,
        "ama_internal_duration_ms": stats["duration_ms_internal"],
        "use_streaming": use_streaming,
    }
    return rows_out, raw, notes


def _check_disk_space(scale: str, base_dir: Path, notes: list[str]) -> bool:
    """Return False (and append a SKIP note) when disk is too tight for *scale*."""
    base_dir.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(str(base_dir)).free / 1024**3
    floor = _MIN_FREE_DISK_GB_10G if scale == "10" else _MIN_FREE_DISK_GB_1G
    if free_gb < floor:
        notes.append(
            f"Skipping scale={scale}: only {free_gb:.1f} GB free at {base_dir}, "
            f"requires {floor:.0f} GB."
        )
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nucleus B2 — Materialize-at-scale benchmark.")
    parser.add_argument(
        "--scale",
        choices=["1", "10", "all"],
        default="1",
        help="Which scale(s) to run. 1 = 10M rows ~1 GB; 10 = 100M rows ~10 GB; "
        "all = both. Default: 1.",
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Disable Polars streaming=True even for the 10 GB scale. Default: streaming on for 10 GB.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temp Parquet + warehouse for inspection (default: delete on exit).",
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="Override the temp directory (default: system tempdir / nucleus_bench_b2).",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()

    base_dir = (
        args.temp_dir
        if args.temp_dir is not None
        else Path(tempfile.mkdtemp(prefix="nucleus_bench_b2_"))
    )
    base_dir.mkdir(parents=True, exist_ok=True)
    print(f"[B2] working dir: {base_dir}")

    rows: list[BenchRow] = []
    notes: list[str] = []
    raw: dict[str, object] = {}
    overall_verdict = PASS

    scales_to_run = ["1", "10"] if args.scale == "all" else [args.scale]
    for scale_key in scales_to_run:
        if not _check_disk_space(scale_key, base_dir, notes):
            scale = _SCALES[scale_key]
            rows.append(
                BenchRow(
                    metric=f"{scale['label']} — wall-clock",
                    claim_ref="perf doc §2.2",
                    claim=f"<{fmt_seconds(float(scale['claim_wall_s']))}",  # type: ignore[arg-type]
                    measured="(skipped)",
                    verdict=SKIP_DEPS,
                    delta="insufficient free disk",
                    severity=MEDIUM,
                    note=notes[-1],
                )
            )
            overall_verdict = SKIP_DEPS if overall_verdict == PASS else overall_verdict
            continue

        scale = _SCALES[scale_key]
        # Streaming default: on for 10 GB (perf doc §2.2 calls it out), off for 1 GB
        # so we can compare against the in-memory budget claim. --no-streaming forces off.
        use_streaming = (scale_key == "10") and not args.no_streaming
        try:
            scale_rows, scale_raw, scale_notes = _run_scale(
                scale, base_dir=base_dir, use_streaming=use_streaming
            )
            rows.extend(scale_rows)
            notes.extend(scale_notes)
            raw[f"scale_{scale_key}"] = scale_raw
        except Exception as exc:  # noqa: BLE001 — surface any failure as a benchmark FAIL row
            verdict_msg = f"{type(exc).__name__}: {exc}"
            print(f"[B2] EXCEPTION on scale={scale_key}: {verdict_msg}")
            rows.append(
                BenchRow(
                    metric=f"{scale['label']} — execution",
                    claim_ref="perf doc §2.2",
                    claim="materializes without error",
                    measured=verdict_msg[:200],
                    verdict=FAIL,
                    severity=BLOCKER,
                    note="see stderr for full traceback",
                )
            )
            overall_verdict = FAIL

    # Aggregate verdict — any FAIL wins, otherwise SKIP-DEPS, otherwise PASS.
    if any(r.verdict == FAIL for r in rows):
        overall_verdict = FAIL
    elif any(r.verdict == SKIP_DEPS for r in rows):
        overall_verdict = SKIP_DEPS if overall_verdict != FAIL else FAIL
    elif all(r.verdict == PASS for r in rows):
        overall_verdict = PASS

    # Cleanup unless --keep-temp.
    if not args.keep_temp and args.temp_dir is None:
        try:
            shutil.rmtree(base_dir, ignore_errors=True)
        except OSError as exc:
            notes.append(f"cleanup of {base_dir} failed: {exc}")

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B2: Materialize at scale",
        script="scripts/internal/benchmarks/b2_materialize.py",
        command=(
            f"{sys.executable} -m scripts.benchmarks.b2_materialize "
            f"--scale {args.scale}{' --no-streaming' if args.no_streaming else ''}"
        ),
        started_at=started_at,
        completed_at=completed_at,
        elapsed_s=elapsed_total,
        overall_verdict=overall_verdict,
        rows=rows,
        notes=notes,
        raw=raw,
    )

    out = write_result(result)
    print()
    print(f"[B2] wrote {out}")
    print(f"[B2] overall = {overall_verdict} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")
    return 0 if overall_verdict in (PASS, SKIP_DEPS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
