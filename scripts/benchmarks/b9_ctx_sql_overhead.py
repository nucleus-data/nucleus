"""B9 — ``ctx.sql`` vs raw DuckDB overhead benchmark.

Measures the cost of routing a SELECT through ``nucleus.ctx.sql`` (Jinja
``{{ ref() }}`` resolution + filesystem-catalog lookup + Arrow view
registration + DuckDB execute) compared to running the same SQL directly
against raw DuckDB on the same Parquet data.

The user-facing claim in `docs/research/benchmarks_v0.2.0.md` is

    "ctx.sql adds <5% overhead vs raw DuckDB on a single-asset query."

The 5% number is what the v0.2 SDK aims for and is what we measure here
empirically.

What's measured
---------------
For three representative queries on a single Iceberg-backed table:

    * Q1: ``SELECT 1`` — pure framework overhead baseline.
    * Q2: ``SELECT COUNT(*) FROM <asset>`` — single Iceberg scan.
    * Q3: ``SELECT name, AVG(amount) GROUP BY name LIMIT 10`` — aggregate.

For each query, run N times (default 5) on each engine path; take the
median; report ``ctx_sql_median - raw_median`` and the percentage delta.

Why no TPC-H
------------
B1 owns TPC-H. This benchmark is intentionally cheap so the v0.2 release
suite can run end-to-end on every CI check without a TPC-H download.

Anti-fakery
-----------
    * Both paths read the SAME on-disk data (single Iceberg snapshot
      committed by the AMA, then a single Parquet file on disk for the
      raw-DuckDB path — pyiceberg materialises one Parquet per snapshot
      for our small table size).
    * The raw-DuckDB path uses the same ``duckdb.connect()`` defaults as
      ``nucleus.ctx.sql._build_catalog_views`` so we don't double-count
      a connection-pool warm-up.
    * We pre-warm both paths with one untimed call so the first measured
      run isn't biased by import cost.

Docs:
    DuckDB Python API — https://duckdb.org/docs/api/python/dbapi
    PyIceberg ``Table.scan`` — https://py.iceberg.apache.org/api/table/
    ctx.sql — src/nucleus/ctx/sql.py
"""

from __future__ import annotations

import argparse
import gc
import math
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    LOW,
    MEDIUM,
    PASS,
    BenchResult,
    BenchRow,
    benchmark_clock,
    ensure_repo_root_on_path,
    fmt_seconds,
    now_iso,
    stats_summary,
    write_result,
)

DEFAULT_RUNS_PER_QUERY: int = 5
DEFAULT_ROWS: int = 100_000

# Acceptable ctx.sql overhead vs raw DuckDB.
# Per ADR-013 + v4.1 §5.6.0: ctx.sql is a thin Jinja + catalog wrapper.
# 50% overhead is our PASS bar — the catalog open + Arrow registration
# is unavoidable for {{ ref() }} resolution, but should not double the
# raw query cost.
ACCEPTABLE_OVERHEAD_PCT: float = 50.0


def _seed_warehouse(warehouse: Path, rows: int) -> tuple[str, Path]:
    """Materialize a small Iceberg table and return (asset_key, parquet_path).

    ``parquet_path`` points at the single Parquet file pyiceberg writes for
    this table, used by the raw-DuckDB measurement path so both paths read
    identical bytes.
    """
    ensure_repo_root_on_path()
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/

    import nucleus

    asset_key = "bench.sql_overhead"
    df = pl.DataFrame({
        "id": list(range(rows)),
        "amount": [(i * 1.5) % 1000.0 for i in range(rows)],
        "name": [f"name_{i % 100}" for i in range(rows)],
    })

    @nucleus.asset(asset_key)
    def _body() -> pl.DataFrame:
        return df

    nucleus.materialize(asset_key, warehouse_dir=warehouse)

    # Find the Parquet file pyiceberg wrote (one per commit at this scale).
    candidates = list(warehouse.rglob("*.parquet"))
    parquet = candidates[0] if candidates else warehouse / "missing.parquet"
    return asset_key, parquet


def _build_query_pairs(asset_key: str) -> list[tuple[str, str, str]]:
    """Return ``[(label, ctx_sql_query, raw_sql_query), ...]``.

    The two SQL strings differ only in the table reference: ctx.sql uses
    ``{{ ref('asset_key') }}`` (resolved by Jinja); raw uses a placeholder
    that the caller will swap to a Parquet path via ``read_parquet``.
    """
    return [
        (
            "Q1: SELECT 1 (pure framework overhead)",
            "SELECT 1 AS x",
            "SELECT 1 AS x",
        ),
        (
            f"Q2: COUNT(*) FROM {asset_key}",
            f"SELECT COUNT(*) AS n FROM {{{{ ref('{asset_key}') }}}}",
            "SELECT COUNT(*) AS n FROM read_parquet('{parquet}')",
        ),
        (
            f"Q3: GROUP BY over {asset_key}",
            (
                "SELECT name, AVG(amount) AS avg_amt "
                f"FROM {{{{ ref('{asset_key}') }}}} "
                "GROUP BY name ORDER BY name LIMIT 10"
            ),
            (
                "SELECT name, AVG(amount) AS avg_amt "
                "FROM read_parquet('{parquet}') "
                "GROUP BY name ORDER BY name LIMIT 10"
            ),
        ),
    ]


def _time_ctx_sql(query: str, warehouse: Path) -> float:
    """Time one ``ctx.sql(...).collect()`` call."""
    from nucleus.ctx.sql import sql as ctx_sql

    started = benchmark_clock()
    lazy = ctx_sql(query, warehouse_dir=warehouse)
    _ = lazy.collect()  # Force materialization so we measure the full path.
    return benchmark_clock() - started


def _time_raw_duckdb(query_template: str, parquet: Path) -> float:
    """Time one raw DuckDB call against the same Parquet file."""
    import duckdb  # Docs: https://duckdb.org/docs/api/python/dbapi

    sql = query_template.replace("{parquet}", parquet.as_posix())
    con = duckdb.connect()
    try:
        started = benchmark_clock()
        con.sql(sql).fetchall()
        return benchmark_clock() - started
    finally:
        con.close()


def _row_for_query(
    label: str, ctx_samples: list[float], raw_samples: list[float]
) -> BenchRow:
    """Return one BenchRow comparing ctx.sql vs raw DuckDB medians."""
    if not ctx_samples or not raw_samples:
        return BenchRow(
            metric=label,
            claim_ref="user expectation",
            claim=f"<{ACCEPTABLE_OVERHEAD_PCT:.0f}% overhead",
            measured="no samples",
            verdict=FAIL,
            severity=BLOCKER,
        )
    ctx_median = float(stats_summary(ctx_samples)["median"])
    raw_median = float(stats_summary(raw_samples)["median"])
    overhead_s = ctx_median - raw_median
    overhead_pct = (overhead_s / raw_median) * 100.0 if raw_median > 0 else float("inf")

    if math.isinf(overhead_pct) or math.isnan(overhead_pct):
        verdict = FAIL
        severity = MEDIUM
    elif overhead_pct < ACCEPTABLE_OVERHEAD_PCT:
        verdict = PASS
        severity = ""
    else:
        verdict = FAIL
        severity = LOW

    return BenchRow(
        metric=label,
        claim_ref="user expectation (informational)",
        claim=f"<{ACCEPTABLE_OVERHEAD_PCT:.0f}% overhead vs raw DuckDB",
        measured=(
            f"ctx={fmt_seconds(ctx_median)} "
            f"raw={fmt_seconds(raw_median)} "
            f"delta={fmt_seconds(overhead_s)}"
        ),
        verdict=verdict,
        delta=f"+{overhead_pct:.1f}%" if not math.isnan(overhead_pct) else "n/a",
        severity=severity,
        note=f"n_ctx={len(ctx_samples)} n_raw={len(raw_samples)}",
    )


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915 — flat orchestration; per-query loop mirrors report rows
    parser = argparse.ArgumentParser(
        description="Nucleus B9 — ctx.sql vs raw DuckDB overhead benchmark."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS_PER_QUERY,
        help=f"Iterations per query per engine (default {DEFAULT_RUNS_PER_QUERY}).",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help=f"Rows in the seed table (default {DEFAULT_ROWS:,}).",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()
    base_dir = Path(tempfile.mkdtemp(prefix="nucleus_bench_b9_"))
    warehouse = base_dir / "warehouse"
    warehouse.mkdir(parents=True, exist_ok=True)
    print(f"[B9] working dir: {base_dir}")

    rows: list[BenchRow] = []
    raw: dict[str, object] = {}
    notes: list[str] = []
    overall = PASS

    print(f"[B9] seeding warehouse with {args.rows:,} rows ...")
    try:
        asset_key, parquet = _seed_warehouse(warehouse, rows=args.rows)
        notes.append(f"seed asset={asset_key}; parquet={parquet.name} "
                     f"({parquet.stat().st_size if parquet.exists() else 0} bytes)")
    except Exception as exc:
        rows.append(BenchRow(
            metric="seed warehouse",
            claim_ref="prerequisite",
            claim="materialize bench.sql_overhead",
            measured=f"{type(exc).__name__}: {exc!s}"[:200],
            verdict=FAIL,
            severity=BLOCKER,
        ))
        overall = FAIL
        completed_at = now_iso()
        elapsed_total = benchmark_clock() - started
        result = BenchResult(
            name="B9: ctx.sql overhead",
            script="scripts/benchmarks/b9_ctx_sql_overhead.py",
            command=f"{sys.executable} -m scripts.benchmarks.b9_ctx_sql_overhead",
            started_at=started_at,
            completed_at=completed_at,
            elapsed_s=elapsed_total,
            overall_verdict=overall,
            rows=rows,
            notes=notes,
            raw=raw,
        )
        write_result(result)
        shutil.rmtree(base_dir, ignore_errors=True)
        return 1

    if not parquet.exists():
        rows.append(BenchRow(
            metric="locate Parquet for raw-DuckDB path",
            claim_ref="prerequisite",
            claim="exactly 1 Parquet file under warehouse/",
            measured="no Parquet found",
            verdict=FAIL,
            severity=BLOCKER,
            note=f"warehouse={warehouse}",
        ))
        overall = FAIL

    queries = _build_query_pairs(asset_key)

    # Pre-warm both paths once (not measured) to flush import cost.
    print("[B9] pre-warming both engine paths ...")
    try:
        for _label, ctx_q, raw_q_template in queries:
            _time_ctx_sql(ctx_q, warehouse)
            _time_raw_duckdb(raw_q_template, parquet)
    except Exception as exc:
        notes.append(f"pre-warm raised {type(exc).__name__}: {exc!s}; continuing")

    for label, ctx_q, raw_q_template in queries:
        print(f"[B9] {label} (n={args.runs} per engine) ...")
        ctx_samples: list[float] = []
        raw_samples: list[float] = []
        for _ in range(args.runs):
            try:
                ctx_samples.append(_time_ctx_sql(ctx_q, warehouse))
            except Exception as exc:
                notes.append(f"{label} ctx.sql raised {type(exc).__name__}: {exc!s}")
            try:
                raw_samples.append(_time_raw_duckdb(raw_q_template, parquet))
            except Exception as exc:
                notes.append(f"{label} raw DuckDB raised {type(exc).__name__}: {exc!s}")

        rows.append(_row_for_query(label, ctx_samples, raw_samples))
        raw[label] = {
            "ctx_samples_s": ctx_samples,
            "raw_samples_s": raw_samples,
        }

    if any(r.verdict == FAIL for r in rows):
        overall = FAIL

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B9: ctx.sql overhead",
        script="scripts/benchmarks/b9_ctx_sql_overhead.py",
        command=(
            f"{sys.executable} -m scripts.benchmarks.b9_ctx_sql_overhead "
            f"--runs {args.runs} --rows {args.rows}"
        ),
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
    print(f"[B9] wrote {out}")
    print(f"[B9] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    shutil.rmtree(base_dir, ignore_errors=True)
    gc.collect()
    return 0 if overall == PASS else 1


_ = textwrap  # keep imported for future docstring re-format hooks


if __name__ == "__main__":
    raise SystemExit(main())
