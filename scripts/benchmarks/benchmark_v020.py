"""Nucleus v0.2.0 release benchmark suite — single-command entry point.

Per the user-facing benchmark task spec (see
`docs/internal/research/benchmarks_v0.2.0.md`):

    "Reproduce: 1 command:
       python scripts/internal/benchmarks/benchmark_v020.py --suite all --output benchmarks/results.json"

This script is a thin orchestrator that:

    1. Runs the v0.2.0 release benchmarks in dependency order:
        B5  — Boot time
        B2  — Single-table materialize at scale
        B6  — Multi-asset DAG materialize
        B7  — Schema check overhead
        B9  — ctx.sql vs raw DuckDB overhead
        B8  — Workbench HTTP API latency
        B1  — TPC-H 10 GB on DuckDB        (optional; needs network egress)
        B3  — Postgres ingest scale         (optional; needs Docker)
        B4  — Concurrent run safety         (optional; reliability rather than perf)
    2. Collects each per-script JSON blob from
       ``docs/internal/benchmarks/_results/<name>.json``.
    3. Writes a single consolidated JSON to ``--output`` so a third party
       can run one command and email back a comparable artifact.

The legacy orchestrator at ``scripts/internal/benchmarks/run_all.py`` writes the
internal-facing markdown baseline at ``docs/internal/benchmarks/<date>_baseline.md``
and is still the right tool for daily CI; ``benchmark_v020.py`` is the
release-facing single-output entry users see in
``docs/internal/research/benchmarks_v0.2.0.md``.

Per Anti-Over-Engineering Discipline (`AGENTS.md`):
    Keep this file thin. It does not measure anything itself; it only
    routes execution through the per-benchmark scripts and the existing
    ``run_all.py`` infrastructure. Adding measurement logic here would
    duplicate `_common.py` and grow the proprietary LOC budget.

Docs:
    Python ``subprocess`` — https://docs.python.org/3/library/subprocess.html
    AGENTS.md §11.13 (upgrade smoke baseline) — re-runnable benchmarks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.benchmarks._common import (
    FAIL,
    PASS,
    REPO_ROOT,
    RESULTS_DIR,
    SKIP_DEPS,
    benchmark_clock,
    fmt_seconds,
    hardware_specs,
    now_iso,
    software_versions,
)

# ---------------------------------------------------------------------------
# Suite definitions
# ---------------------------------------------------------------------------
# Each tuple records: short-name, module path, default CLI args, result-file basename.
# Order matters — boot-time first so `nucleus --version` cold cache is the
# first cost a user reads.
_SUITE_RELEASE: tuple[tuple[str, str, list[str], str], ...] = (
    ("b5", "scripts.benchmarks.b5_boot_time", ["--iterations", "10"], "b5_boot_time"),
    ("b2", "scripts.benchmarks.b2_materialize", ["--scale", "1"], "b2_materialize"),
    ("b6", "scripts.benchmarks.b6_dag_materialize", ["--shape", "10"], "b6_dag_materialize"),
    ("b7", "scripts.benchmarks.b7_check_overhead", ["--scale", "1m"], "b7_check_overhead"),
    ("b9", "scripts.benchmarks.b9_ctx_sql_overhead", ["--runs", "5"], "b9_ctx_sql_overhead"),
    ("b8", "scripts.benchmarks.b8_workbench_api", ["--runs", "10"], "b8_workbench_api"),
)

# Optional benchmarks that need external services (Docker / DuckDB extension
# catalogue / multi-process serialization). Run on --suite all only.
_SUITE_OPTIONAL: tuple[tuple[str, str, list[str], str], ...] = (
    ("b4", "scripts.benchmarks.b4_concurrent_run", ["--hold", "5"], "b4_concurrent_run"),
    (
        "b1",
        "scripts.benchmarks.b1_tpch_duckdb",
        ["--scale-factor", "10", "--runs", "3"],
        "b1_tpch_duckdb",
    ),
    ("b3", "scripts.benchmarks.b3_postgres_ingest", ["--scale", "1m"], "b3_postgres_ingest"),
)

_TIMEOUTS_S: dict[str, float] = {
    "b5": 600,
    "b2": 1200,
    "b6": 1200,
    "b7": 1800,
    "b9": 600,
    "b8": 600,
    "b4": 600,
    "b1": 1800,
    "b3": 2400,
}

DEFAULT_OUTPUT = REPO_ROOT / "benchmarks" / "results.json"


def _selected_benchmarks(suite: str) -> list[tuple[str, str, list[str], str]]:
    """Return the benchmark list for the requested suite name."""
    if suite == "release":
        return list(_SUITE_RELEASE)
    if suite == "all":
        return list(_SUITE_RELEASE) + list(_SUITE_OPTIONAL)
    if suite == "fast":
        # Fast subset: just B5 + B6 + B7 + B9 — all run in well under 5 min on
        # a beachhead laptop with no external services.
        return [b for b in _SUITE_RELEASE if b[0] in {"b5", "b6", "b7", "b9"}]
    raise ValueError(f"unknown suite={suite!r}; valid: release, all, fast")


def _run_one(short: str, module: str, args: list[str]) -> tuple[int, float, str]:
    """Run ``python -m <module>`` with *args*; return (rc, elapsed, stderr_tail)."""
    timeout = _TIMEOUTS_S.get(short, 1200)
    cmd = [sys.executable, "-m", module, *args]
    print(f"[v020] => {short}: `{' '.join(cmd)}` (timeout {timeout:.0f}s)")
    started = benchmark_clock()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = benchmark_clock() - started
        return proc.returncode, elapsed, (proc.stderr or "")[-1500:]
    except subprocess.TimeoutExpired:
        elapsed = benchmark_clock() - started
        return 124, elapsed, f"TIMEOUT after {timeout:.0f}s"


def _load_result(filename: str) -> dict[str, Any] | None:
    """Read the per-benchmark JSON blob; return None when missing/corrupt."""
    path = RESULTS_DIR / f"{filename}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _aggregate_verdict(per_bench: list[dict[str, Any]]) -> str:
    """Aggregate per-benchmark overall_verdict into one suite verdict."""
    overall = [str(b["result"].get("overall_verdict", "")) for b in per_bench if "result" in b]
    if FAIL in overall:
        return FAIL
    if all(v == PASS for v in overall) and overall:
        return PASS
    if all(v in (PASS, SKIP_DEPS) for v in overall) and overall:
        return SKIP_DEPS
    return "MIXED"


def _summary_lines(per_bench: list[dict[str, Any]]) -> list[str]:
    """Build the printed/text summary block."""
    lines: list[str] = []
    for sec in per_bench:
        if "result" not in sec:
            lines.append(f"  - {sec.get('short', '?').upper()}: NO RESULT JSON")
            continue
        r = sec["result"]
        lines.append(
            f"  - {sec['short'].upper()}: {r.get('overall_verdict')} "
            f"({fmt_seconds(float(r.get('elapsed_s', 0)))}, "
            f"{len(r.get('rows', []))} rows)"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nucleus v0.2.0 release benchmark suite single-command runner."
    )
    parser.add_argument(
        "--suite",
        choices=["release", "all", "fast"],
        default="release",
        help=(
            "release (default): B5 B2 B6 B7 B9 B8. "
            "all: release + B4 B1 B3. fast: B5 B6 B7 B9 only (<5 min, no external deps)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to write the consolidated JSON (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Skip running benchmarks; just consolidate cached _results/*.json.",
    )
    args = parser.parse_args(argv)

    benches = _selected_benchmarks(args.suite)
    print(f"[v020] suite={args.suite}: {[b[0] for b in benches]}")

    started_at = now_iso()
    suite_started = benchmark_clock()
    per_bench: list[dict[str, Any]] = []

    for short, module, default_args, result_name in benches:
        if not args.no_execute:
            rc, elapsed, stderr_tail = _run_one(short, module, default_args)
            print(f"[v020] <= {short}: rc={rc} elapsed={fmt_seconds(elapsed)}")
            if rc not in (0, 1):
                print(f"[v020]   stderr tail: {stderr_tail[-600:]}")
        loaded = _load_result(result_name)
        per_bench.append(
            {
                "short": short,
                "module": module,
                "result": (loaded or {}).get("result"),
                "hardware": (loaded or {}).get("hardware"),
                "software": (loaded or {}).get("software"),
            }
        )

    suite_elapsed = benchmark_clock() - suite_started
    completed_at = now_iso()

    consolidated: dict[str, Any] = {
        "schema_version": 1,
        "suite": args.suite,
        "tool": "scripts/internal/benchmarks/benchmark_v020.py",
        "started_at": started_at,
        "completed_at": completed_at,
        "suite_elapsed_s": suite_elapsed,
        "overall_verdict": _aggregate_verdict(per_bench),
        "hardware": (
            per_bench[0]["hardware"] if per_bench and per_bench[0]["hardware"] else hardware_specs()
        ),
        "software": (
            per_bench[0]["software"]
            if per_bench and per_bench[0]["software"]
            else software_versions()
        ),
        "benchmarks": per_bench,
        "report_url": "docs/internal/research/benchmarks_v0.2.0.md",
        "rerun_command": f"python scripts/internal/benchmarks/benchmark_v020.py --suite {args.suite}",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(consolidated, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    tmp.replace(args.output)

    print()
    print(f"[v020] wrote consolidated JSON to {args.output}")
    print(
        f"[v020] suite verdict: {consolidated['overall_verdict']} "
        f"(elapsed {fmt_seconds(suite_elapsed)})"
    )
    print("[v020] benchmark summary:")
    for line in _summary_lines(per_bench):
        print(line)
    print(f"[v020] re-run with: {consolidated['rerun_command']}")

    today = datetime.now(UTC).date().isoformat()
    print(f"[v020] today is {today}; user-facing report at {consolidated['report_url']}")
    return 0 if consolidated["overall_verdict"] in (PASS, SKIP_DEPS, "MIXED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
