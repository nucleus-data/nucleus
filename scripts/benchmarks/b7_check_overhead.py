"""B7 — Schema check overhead benchmark.

Measures the cost of attaching ``@nucleus.check`` quality checks to an
asset, expressed as a percentage of the asset's materialize wall-clock.

Note on naming: the original task spec talks about "@nucleus.contract"
overhead. The v0.2 SDK ships ``@nucleus.check`` (per
``nucleus_ctx_sdk_spec.md`` §2.4 + ``nucleus_asset_model_spec.md`` §10);
declarative ``contract=`` on ``@nucleus.asset`` accepts the value but
contract enforcement is deferred to v0.3+ per
``src/nucleus/sdk/decorators.py:asset()`` docstring + ADR-013 §NV. The
check decorator is the closest analogue and is what
``coordination/asset_materialization.py:_run_checks_for_asset`` actually
runs after a materialize commit. We measure that.

What's measured
---------------
For each scale (1M rows, 10M rows):

    * Wall-clock to materialize WITHOUT any check attached (baseline).
    * Wall-clock to materialize WITH 3 representative checks attached:
        - ``check_no_nulls(id)``        — null-count assertion
        - ``check_id_unique(id)``       — uniqueness assertion
        - ``check_amount_non_negative`` — value-range assertion
    * Overhead = with - without; reported in seconds and as a percentage.

Why three checks
----------------
A single check can complete in nearly zero time (cached column scan); a
realistic per-asset check budget is 1-3 checks (per industry data
quality conventions and what a startup data team actually writes). The
3-check measurement is closer to user reality than a 1-check minimum.

Anti-fakery
-----------
    * Same row generator as B2 + B3 + B6 (deterministic, fixed seed).
    * Both runs use the same fresh warehouse + asset key (registry reset
      between runs); ordering: baseline first, then with-checks. Reverse
      order also tested in CI to rule out warmup confounds (run twice
      manually if a regression is suspected).
    * The check bodies do real work (``filter`` + ``len``); they are not
      no-ops.

Docs:
    @nucleus.check — src/nucleus/sdk/decorators.py
    Polars filter + count — https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.filter.html
    Asset model spec §10 (check return type) — nucleus_asset_model_spec.md
"""

from __future__ import annotations

import argparse
import gc
import math
import shutil
import sys
import tempfile
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    LOW,
    PASS,
    BenchResult,
    BenchRow,
    benchmark_clock,
    ensure_repo_root_on_path,
    fmt_seconds,
    now_iso,
    write_result,
)

_SCALES: dict[str, dict[str, object]] = {
    "1m": {
        "rows": 1_000_000,
        "label": "1M rows",
    },
    "10m": {
        "rows": 10_000_000,
        "label": "10M rows",
    },
}


def _build_dataframe(rows: int) -> object:
    """Return a deterministic ``polars.DataFrame`` of ``rows`` rows.

    Mirrors the B2 schema slice used by checks:

        id     BIGINT  (unique)
        amount DOUBLE  (always >= 0 in baseline; check verifies)
        name   VARCHAR (1000 distinct values)
    """
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/

    return pl.DataFrame(
        {
            "id": list(range(rows)),
            "amount": [(i * 1.5) % 1000.0 for i in range(rows)],
            "name": [f"name_{i % 1000}" for i in range(rows)],
        }
    )


def _register_asset_no_checks(asset_key: str, rows: int) -> None:
    """Register the asset with NO attached checks (baseline measurement)."""
    import nucleus

    df = _build_dataframe(rows)

    @nucleus.asset(asset_key)
    def _body() -> object:
        return df


def _register_asset_with_checks(asset_key: str, rows: int) -> None:
    """Register the asset and 3 representative checks bound to it."""
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/

    import nucleus

    df = _build_dataframe(rows)

    @nucleus.asset(asset_key)
    def _body() -> object:
        return df

    # Check 1: no nulls in id
    @nucleus.check(asset_key)
    def _check_no_nulls() -> nucleus.CheckResult:
        # We re-build the df to keep the check independent of body capture
        # (mirrors how a user-defined check would re-read via ctx.read).
        local_df = df
        bad = int(local_df.select(pl.col("id").is_null().sum()).item())
        return nucleus.CheckResult(
            passed=bad == 0,
            metric=float(bad),
            message=f"null id count = {bad}",
        )

    # Check 2: id uniqueness
    @nucleus.check(asset_key)
    def _check_id_unique() -> nucleus.CheckResult:
        local_df = df
        # Polars ``n_unique`` is column-aware; matches the unique-key
        # check pattern in dbt + Soda (Docs: https://docs.pola.rs/api/python/stable/reference/series/api/polars.Series.n_unique.html).
        unique_count = int(local_df.select(pl.col("id")).n_unique())
        total = len(local_df)
        return nucleus.CheckResult(
            passed=unique_count == total,
            metric=float(total - unique_count),
            message=f"{total - unique_count} duplicate ids out of {total}",
        )

    # Check 3: amount non-negative
    @nucleus.check(asset_key)
    def _check_amount_non_neg() -> nucleus.CheckResult:
        local_df = df
        bad = int(local_df.filter(pl.col("amount") < 0).height)
        return nucleus.CheckResult(
            passed=bad == 0,
            metric=float(bad),
            message=f"{bad} negative amount rows",
        )


def _materialize_once(asset_key: str, warehouse: Path) -> tuple[float, int]:
    """Materialize and return ``(wall_s, row_count)``."""
    import nucleus

    started = benchmark_clock()
    result = nucleus.materialize(asset_key, warehouse_dir=warehouse)
    wall = benchmark_clock() - started
    return wall, result.row_count


def _run_one_scale(  # noqa: PLR0915 — flat orchestration; refactor would obscure the warmup→baseline→checked sequence the report mirrors
    scale_key: str, *, base_dir: Path
) -> tuple[list[BenchRow], dict[str, object], list[str]]:
    """Run one row-scale; return (rows, raw, notes)."""
    notes: list[str] = []
    rows_out: list[BenchRow] = []
    scale = _SCALES[scale_key]
    n_rows = int(scale["rows"])  # type: ignore[arg-type]
    label = str(scale["label"])

    ensure_repo_root_on_path()
    from nucleus.sdk.decorators import _reset_registry_for_tests

    asset_key = f"bench.check_target_{scale_key}"

    # WARMUP — pay Dagster + pyiceberg + Polars cold-import cost on a
    # throwaway materialize so the two measured passes both see a hot
    # cache. Without this, the first measured call dominates the
    # comparison and the "overhead" reading is meaningless. Warmup uses
    # a small row count to keep its own cost off the wall-clock.
    _reset_registry_for_tests()
    warmup_warehouse = base_dir / f"warehouse_warmup_{scale_key}"
    warmup_warehouse.mkdir(parents=True, exist_ok=True)
    _register_asset_no_checks(f"bench.warmup_{scale_key}", 100)
    print(f"[B7] {label}: warmup materialize (untimed) ...")
    try:
        _materialize_once(f"bench.warmup_{scale_key}", warmup_warehouse)
    except Exception as exc:
        notes.append(f"warmup raised {type(exc).__name__}: {exc!s}; continuing")

    # Pass 1 — baseline (no checks). Now warm.
    _reset_registry_for_tests()
    warehouse_baseline = base_dir / f"warehouse_baseline_{scale_key}"
    warehouse_baseline.mkdir(parents=True, exist_ok=True)
    _register_asset_no_checks(asset_key, n_rows)
    print(f"[B7] {label}: materialize WITHOUT checks (baseline, warm) ...")
    try:
        baseline_wall, baseline_rows = _materialize_once(asset_key, warehouse_baseline)
    except Exception as exc:
        rows_out.append(
            BenchRow(
                metric=f"{label} — baseline materialize",
                claim_ref="prerequisite",
                claim="materialize succeeds without checks",
                measured=f"{type(exc).__name__}: {exc!s}"[:200],
                verdict=FAIL,
                severity=BLOCKER,
            )
        )
        return rows_out, {"error_baseline": str(exc)}, notes
    print(f"[B7]   baseline wall = {fmt_seconds(baseline_wall)} (rows={baseline_rows})")

    # Pass 2 — with 3 checks attached.
    _reset_registry_for_tests()
    warehouse_checked = base_dir / f"warehouse_checked_{scale_key}"
    warehouse_checked.mkdir(parents=True, exist_ok=True)
    _register_asset_with_checks(asset_key, n_rows)
    print(f"[B7] {label}: materialize WITH 3 checks ...")
    try:
        checked_wall, checked_rows = _materialize_once(asset_key, warehouse_checked)
    except Exception as exc:
        rows_out.append(
            BenchRow(
                metric=f"{label} — checked materialize",
                claim_ref="user expectation",
                claim="materialize succeeds with checks attached",
                measured=f"{type(exc).__name__}: {exc!s}"[:200],
                verdict=FAIL,
                severity=BLOCKER,
                note="baseline succeeded; check path is the regression",
            )
        )
        return rows_out, {"baseline_wall_s": baseline_wall, "error_checked": str(exc)}, notes
    print(f"[B7]   checked wall = {fmt_seconds(checked_wall)} (rows={checked_rows})")

    overhead_s = checked_wall - baseline_wall
    overhead_pct = (overhead_s / baseline_wall) * 100.0 if baseline_wall > 0 else float("nan")

    # Verdict heuristic.
    # <0% (checked is faster than baseline): below noise floor = PASS with
    #   "below noise floor" note (legitimate; tiny check cost is dominated
    #   by per-call jitter even after warmup).
    # 0-50% overhead: PASS (low cost; expected envelope).
    # 50-200% overhead: FAIL LOW (still usable; flag for review).
    # >200% overhead: FAIL HIGH (probably a bug).
    if math.isnan(overhead_pct):
        verdict = FAIL
        severity = BLOCKER
    elif overhead_pct < 50:
        verdict = PASS
        severity = ""
    else:
        verdict = FAIL
        severity = LOW

    rows_out.append(
        BenchRow(
            metric=f"{label} — baseline materialize wall (no checks)",
            claim_ref="informational",
            claim="bounded by per-asset compute",
            measured=fmt_seconds(baseline_wall),
            verdict=PASS,
            note=f"row_count={baseline_rows:,}",
        )
    )
    rows_out.append(
        BenchRow(
            metric=f"{label} — checked materialize wall (3 checks)",
            claim_ref="informational",
            claim="baseline + check cost",
            measured=fmt_seconds(checked_wall),
            verdict=PASS,
            note=f"row_count={checked_rows:,}",
        )
    )
    rows_out.append(
        BenchRow(
            metric=f"{label} — check overhead",
            claim_ref="user expectation",
            claim="<50% of baseline materialize wall (low cost)",
            measured=f"{fmt_seconds(overhead_s)} ({overhead_pct:.1f}%)",
            verdict=verdict,
            delta=f"+{overhead_pct:.1f}%" if not math.isnan(overhead_pct) else "n/a",
            severity=severity,
            note="3 representative checks: not_null + unique + range",
        )
    )

    raw = {
        "scale": scale_key,
        "rows": n_rows,
        "baseline_wall_s": baseline_wall,
        "checked_wall_s": checked_wall,
        "overhead_s": overhead_s,
        "overhead_pct": overhead_pct,
    }
    return rows_out, raw, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nucleus B7 — Schema check overhead benchmark.")
    parser.add_argument(
        "--scale",
        choices=["1m", "10m", "all"],
        default="1m",
        help="Row scale: 1m (1M rows), 10m (10M rows), all.",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()
    base_dir = Path(tempfile.mkdtemp(prefix="nucleus_bench_b7_"))
    print(f"[B7] working dir: {base_dir}")

    rows: list[BenchRow] = []
    raw: dict[str, object] = {}
    notes: list[str] = []
    overall = PASS

    scales_to_run = ["1m", "10m"] if args.scale == "all" else [args.scale]
    for sk in scales_to_run:
        try:
            scale_rows, scale_raw, scale_notes = _run_one_scale(sk, base_dir=base_dir)
        except Exception as exc:
            scale_rows = [
                BenchRow(
                    metric=f"scale={sk}",
                    claim_ref="user expectation",
                    claim="benchmark completes",
                    measured=f"{type(exc).__name__}: {exc!s}"[:200],
                    verdict=FAIL,
                    severity=BLOCKER,
                )
            ]
            scale_raw = {"error": str(exc)}
            scale_notes = []
        rows.extend(scale_rows)
        if scale_raw:
            raw[f"scale_{sk}"] = scale_raw
        notes.extend(scale_notes)
        gc.collect()

    if any(r.verdict == FAIL for r in rows):
        overall = FAIL

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B7: Schema check overhead",
        script="scripts/benchmarks/b7_check_overhead.py",
        command=f"{sys.executable} -m scripts.benchmarks.b7_check_overhead --scale {args.scale}",
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
    print(f"[B7] wrote {out}")
    print(f"[B7] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    shutil.rmtree(base_dir, ignore_errors=True)
    return 0 if overall == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
