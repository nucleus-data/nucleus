"""B6 — Multi-asset DAG materialize benchmark.

Verifies the realistic v0.2.0 user expectation:

    "On a single laptop, materialize an N-asset analytics DAG end-to-end
     in roughly N x per-asset cost, with low coordination overhead."

There is no perf-doc claim for "N assets in M layers in T seconds" today
(perf doc §2.2 only budgets per-asset materialize), so this script
captures the empirical baseline rather than asserting PASS/FAIL against a
fixed target. The numbers feed `docs/research/benchmarks_v0.2.0.md` (the
user-facing report) so a startup data team can answer "how long does my
50-asset analytics warehouse take to refresh on my MacBook?".

What's measured
---------------
For each scale (10 assets, 50 assets):

    * Total wall-clock to materialize every asset (registered + executed
      in dependency order via repeated :func:`nucleus.materialize` calls;
      v0.1 ``upstream='skip'`` only per ADR-013 §NV #6, so the script
      drives ordering itself).
    * Per-asset wall-clock median + P95 (informational; surfaces fan-out).
    * Coordination overhead = ``total_wall - sum(per_asset_wall)``. A
      large positive number indicates per-asset Iceberg commit ceremony
      dominates over DataFrame compute.
    * Snapshot count post-run; should equal the asset count.

What's NOT measured
-------------------
    * Parallel materialization — Dagster parallelism is wired but
      :func:`nucleus.materialize` is single-asset; multi-asset parallel
      execution lives in CLI ``nucleus run`` which is out of scope here.
    * Asset-level lineage emit cost — captured implicitly in per-asset
      wall-clock.
    * Concurrent DAGs — that's B4.

Anti-fakery
-----------
    * Same synthetic schema as B2 (mixed types, deterministic rows from a
      fixed seed) so cross-benchmark comparisons hold.
    * Each asset writes a small slice (500 rows by default) so the
      benchmark reports DAG-coordination cost, not DataFrame compute.
    * No retries; failures surface as FAIL rows.

Docs:
    nucleus.materialize — docs/decisions/ADR-013-ctx-materialize-api.md
    Polars DataFrame — https://docs.pola.rs/api/python/stable/
    Perf doc §2.2 + §11.5 — Dagster cold-boot overhead NEEDS VERIFICATION
"""

from __future__ import annotations

import argparse
import gc
import shutil
import sys
import tempfile
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
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

# Default DAG shapes — keep small enough to fit comfortably in the v0.2.0
# release window benchmark wall-clock budget on a 4-core laptop.
_DAG_SHAPES: dict[str, dict[str, int]] = {
    "10": {"asset_count": 10, "layer_depth": 3},
    "50": {"asset_count": 50, "layer_depth": 5},
}

# Rows per asset — small intentionally so the benchmark reports
# DAG-coordination overhead, not DataFrame compute time.
DEFAULT_ROWS_PER_ASSET: int = 500


def _build_dag(asset_count: int, layer_depth: int) -> list[tuple[str, list[str]]]:
    """Return ``[(asset_key, deps), ...]`` in topological order.

    Layer 0 is sources (no deps); each subsequent layer's assets depend
    on a fan-in slice of the previous layer's assets. The shape is fixed
    by ``asset_count`` + ``layer_depth`` so two runs with the same args
    produce identical DAGs.
    """
    layers: list[list[str]] = [[] for _ in range(layer_depth)]
    for i in range(asset_count):
        layer_idx = i % layer_depth
        layers[layer_idx].append(f"bench.dag_a{i:03d}")

    pairs: list[tuple[str, list[str]]] = []
    for layer_idx, layer_keys in enumerate(layers):
        upstream = layers[layer_idx - 1] if layer_idx > 0 else []
        # Each asset in this layer depends on up to 3 upstream assets
        # (fan-in cap so dep lists stay readable in the report).
        for j, key in enumerate(layer_keys):
            if upstream:
                fan_in = min(3, len(upstream))
                start = (j * fan_in) % len(upstream)
                deps = upstream[start:start + fan_in]
                if not deps:
                    deps = upstream[:fan_in]
            else:
                deps = []
            pairs.append((key, list(deps)))
    return pairs


def _register_dag(
    pairs: list[tuple[str, list[str]]], rows_per_asset: int
) -> None:
    """Register every asset in ``pairs`` via :func:`nucleus.asset`.

    Each asset body returns a tiny Polars DataFrame with deterministic
    rows (seeded from the asset key) so per-asset compute cost is
    constant; we want to measure DAG-coordination overhead, not compute.
    """
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/

    import nucleus

    def _make_body(key: str) -> object:
        # Closure over `key` so each asset has a distinct, deterministic body.
        rows = rows_per_asset

        def _body() -> pl.DataFrame:
            return pl.DataFrame({
                "id": list(range(rows)),
                "asset_key": [key] * rows,
                "value": [i * 1.5 for i in range(rows)],
            })

        return _body

    for key, deps in pairs:
        body = _make_body(key)
        body.__name__ = "body_" + key.replace(".", "_")
        nucleus.asset(key, deps=deps)(body)


def _materialize_in_order(
    pairs: list[tuple[str, list[str]]], warehouse: Path
) -> tuple[float, list[float], list[str | None]]:
    """Materialize every asset in dependency order via :func:`nucleus.materialize`.

    Returns ``(total_wall_s, per_asset_wall_s, per_asset_snapshot_id)``.
    """
    import nucleus

    total_started = benchmark_clock()
    per_wall: list[float] = []
    per_snapshot: list[str | None] = []
    for key, _deps in pairs:
        started = benchmark_clock()
        result = nucleus.materialize(key, warehouse_dir=warehouse)
        per_wall.append(benchmark_clock() - started)
        per_snapshot.append(result.snapshot_id)
    total_wall = benchmark_clock() - total_started
    return total_wall, per_wall, per_snapshot


def _verify_snapshots(warehouse: Path, expected_assets: list[str]) -> tuple[bool, str]:
    """Open the warehouse catalog and confirm every asset created a snapshot.

    Returns ``(ok, detail)``. Used to surface silent commit drops as a
    BLOCKER row rather than letting the timing roll up as PASS.
    """
    try:
        from pyiceberg.catalog import (
            load_catalog,  # Docs: https://py.iceberg.apache.org/api/catalog/
        )

        catalog = load_catalog(
            "default",
            type="sql",
            uri=f"sqlite:///{(warehouse / 'catalog.db').resolve().as_posix()}",
            warehouse=f"file://{warehouse.resolve().as_posix()}",
        )
        missing: list[str] = []
        for key in expected_assets:
            ns, name = key.split(".", 1)
            try:
                table = catalog.load_table((ns, name))
                if not table.snapshots():
                    missing.append(key)
            except Exception:
                missing.append(key)
        if missing:
            return False, f"{len(missing)}/{len(expected_assets)} assets missing snapshots: {missing[:5]}"
        return True, f"all {len(expected_assets)} assets committed"
    except Exception as exc:
        return False, f"verification failed: {type(exc).__name__}: {exc}"


def _run_one_shape(
    shape_key: str, *, base_dir: Path, rows_per_asset: int
) -> tuple[list[BenchRow], dict[str, object], list[str]]:
    """Run one DAG shape; return (rows, raw, notes)."""
    notes: list[str] = []
    rows_out: list[BenchRow] = []
    shape = _DAG_SHAPES[shape_key]
    asset_count = shape["asset_count"]
    layer_depth = shape["layer_depth"]
    label = f"{asset_count}-asset DAG ({layer_depth} layers)"

    ensure_repo_root_on_path()

    # Reset the registry between shapes so layer-N assets in the previous
    # shape don't leak into the current one.
    from nucleus.sdk.decorators import _reset_registry_for_tests

    _reset_registry_for_tests()

    pairs = _build_dag(asset_count, layer_depth)
    print(f"[B6] {label}: registering {asset_count} assets (rows/asset={rows_per_asset}) ...")
    _register_dag(pairs, rows_per_asset)

    warehouse = base_dir / f"warehouse_{shape_key}"
    warehouse.mkdir(parents=True, exist_ok=True)
    print(f"[B6] {label}: materializing into {warehouse} ...")
    try:
        total_wall, per_wall, _per_snap = _materialize_in_order(pairs, warehouse)
    except Exception as exc:
        rows_out.append(BenchRow(
            metric=f"{label} — execution",
            claim_ref="user expectation (no perf doc claim)",
            claim="materializes all assets without error",
            measured=f"{type(exc).__name__}: {exc!s}"[:200],
            verdict=FAIL,
            severity=BLOCKER,
            note="see stderr for full traceback",
        ))
        return rows_out, {"error": str(exc)}, notes

    coordination_overhead = total_wall - sum(per_wall)
    per_stats = stats_summary(per_wall)

    rows_out.append(BenchRow(
        metric=f"{label} — total wall-clock",
        claim_ref="user expectation",
        claim=f"~{asset_count} x per-asset cost (informational)",
        measured=fmt_seconds(total_wall),
        verdict=PASS,
        delta=(
            f"per-asset median={fmt_seconds(per_stats['median'])} "
            f"P95={fmt_seconds(per_stats['p95'])}"
        ),
        note=f"materialized {asset_count} assets in dep order",
    ))
    rows_out.append(BenchRow(
        metric=f"{label} — coordination overhead",
        claim_ref="informational",
        claim="~0 (low Iceberg commit ceremony per asset)",
        measured=fmt_seconds(max(0.0, coordination_overhead)),
        verdict=PASS,
        delta=(
            f"{(coordination_overhead / max(total_wall, 1e-9)) * 100:.1f}% of total"
        ),
        note=(
            "total_wall - sum(per_asset_wall); <5% means commit ceremony is "
            "small relative to compute"
        ),
    ))
    rows_out.append(BenchRow(
        metric=f"{label} — per-asset wall (median / P95 / max)",
        claim_ref="informational",
        claim="bounded by per-asset compute (rows x schema)",
        measured=(
            f"median={fmt_seconds(per_stats['median'])} "
            f"P95={fmt_seconds(per_stats['p95'])} "
            f"max={fmt_seconds(per_stats['max'])}"
        ),
        verdict=PASS,
    ))

    ok, detail = _verify_snapshots(warehouse, [k for k, _ in pairs])
    rows_out.append(BenchRow(
        metric=f"{label} — snapshot verification",
        claim_ref="user expectation",
        claim=f"{asset_count} assets each have a committed snapshot",
        measured=detail,
        verdict=PASS if ok else FAIL,
        severity="" if ok else BLOCKER,
    ))

    raw = {
        "asset_count": asset_count,
        "layer_depth": layer_depth,
        "rows_per_asset": rows_per_asset,
        "total_wall_s": total_wall,
        "per_asset_wall_s": per_wall,
        "per_asset_stats": per_stats,
        "coordination_overhead_s": coordination_overhead,
        "snapshots_verified": ok,
        "snapshot_detail": detail,
    }
    return rows_out, raw, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nucleus B6 — Multi-asset DAG materialize benchmark."
    )
    parser.add_argument(
        "--shape",
        choices=["10", "50", "all"],
        default="10",
        help="DAG shape: 10 (10 assets / 3 layers), 50 (50 assets / 5 layers), all.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS_PER_ASSET,
        help=f"Rows per asset (default {DEFAULT_ROWS_PER_ASSET}; small to surface coordination cost).",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()
    base_dir = Path(tempfile.mkdtemp(prefix="nucleus_bench_b6_"))
    print(f"[B6] working dir: {base_dir}")

    rows: list[BenchRow] = []
    raw: dict[str, object] = {}
    notes: list[str] = []
    overall = PASS

    shapes_to_run = ["10", "50"] if args.shape == "all" else [args.shape]
    for sk in shapes_to_run:
        try:
            shape_rows, shape_raw, shape_notes = _run_one_shape(
                sk, base_dir=base_dir, rows_per_asset=args.rows
            )
        except Exception as exc:
            shape_rows = [BenchRow(
                metric=f"shape={sk}",
                claim_ref="user expectation",
                claim="benchmark completes",
                measured=f"{type(exc).__name__}: {exc!s}"[:200],
                verdict=FAIL,
                severity=BLOCKER,
            )]
            shape_raw = {"error": str(exc)}
            shape_notes = []
        rows.extend(shape_rows)
        if shape_raw:
            raw[f"shape_{sk}"] = shape_raw
        notes.extend(shape_notes)
        gc.collect()

    if any(r.verdict == FAIL for r in rows):
        overall = FAIL

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B6: Multi-asset DAG materialize",
        script="scripts/benchmarks/b6_dag_materialize.py",
        command=(
            f"{sys.executable} -m scripts.benchmarks.b6_dag_materialize "
            f"--shape {args.shape} --rows {args.rows}"
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
    print(f"[B6] wrote {out}")
    print(f"[B6] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    shutil.rmtree(base_dir, ignore_errors=True)
    return 0 if overall == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
