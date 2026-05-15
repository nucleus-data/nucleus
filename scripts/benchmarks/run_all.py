"""Orchestrator for the Nucleus empirical benchmark suite.

Runs each ``b*_*.py`` benchmark sequentially (parallel is unsafe — they
all hammer DuckDB / Polars / disk), collects the per-script JSON
output, and writes a single human-readable markdown report at
``docs/benchmarks/<date>_baseline.md``.

Usage::

    python scripts/benchmarks/run_all.py                # all five
    python scripts/benchmarks/run_all.py --only b5,b2   # subset
    python scripts/benchmarks/run_all.py --report-only  # re-render markdown only

The orchestrator is intentionally **dumb** — it does no measurement
itself. Each ``b*_*.py`` script writes its own
``docs/benchmarks/_results/<name>.json`` blob; the report is a
deterministic rendering of those blobs plus a hardware/software
preamble. This keeps the source of truth in one place per benchmark.

Per the task spec: zero fabrication. If a benchmark errors during
execution we record the failure verbatim; we do not retry, do not
smooth, and do not omit. Honest numbers — even when they fail — are
the entire point of the suite.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.benchmarks._common import (
    FAIL,
    PASS,
    SKIP_DEPS,
    REPO_ROOT,
    RESULTS_DIR,
    benchmark_clock,
    fmt_seconds,
    hardware_specs,
    now_iso,
    software_versions,
)

# Order matters: cheaper benchmarks first so a slow one doesn't delay quick signals.
BENCHMARKS: tuple[tuple[str, str], ...] = (
    ("b5", "scripts.benchmarks.b5_boot_time"),
    ("b2", "scripts.benchmarks.b2_materialize"),
    ("b4", "scripts.benchmarks.b4_concurrent_run"),
    ("b1", "scripts.benchmarks.b1_tpch_duckdb"),
    ("b3", "scripts.benchmarks.b3_postgres_ingest"),
)

# Per-benchmark timeout (seconds). B2 + B3 + B1 can take a while at full scale.
BENCH_TIMEOUTS_S: dict[str, float] = {
    "b5": 600,
    "b2": 1200,
    "b4": 600,
    "b1": 1800,
    "b3": 2400,
}

# Per-benchmark default arg list (the orchestrator runs at sane defaults; users
# wanting bigger scales should run the script directly).
BENCH_DEFAULT_ARGS: dict[str, list[str]] = {
    "b5": ["--iterations", "10"],
    "b2": ["--scale", "1"],
    "b4": ["--hold", "5"],
    "b1": ["--scale-factor", "10", "--runs", "3"],
    "b3": ["--scale", "1m"],
}

REPORT_DIR: Path = REPO_ROOT / "docs" / "benchmarks"


def _result_path_for(short_name: str) -> Path:
    """Map ``"b5"`` → ``docs/benchmarks/_results/b5_boot_time.json``."""
    pairs = {short: module.split(".")[-1] for short, module in BENCHMARKS}
    return RESULTS_DIR / f"{pairs[short_name]}.json"


def _run_benchmark(short_name: str, module: str, extra_args: list[str]) -> tuple[int, float, str]:
    """Run ``python -m <module>`` and return (rc, elapsed_s, stderr_tail)."""
    timeout = BENCH_TIMEOUTS_S.get(short_name, 1200)
    args = [sys.executable, "-m", module, *BENCH_DEFAULT_ARGS.get(short_name, []), *extra_args]
    print(f"[run_all] => {short_name}: `{' '.join(args)}` (timeout {timeout:.0f}s)")
    started = benchmark_clock()
    try:
        proc = subprocess.run(
            args,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = benchmark_clock() - started
        stderr_tail = (proc.stderr or "")[-1500:]
        return proc.returncode, elapsed, stderr_tail
    except subprocess.TimeoutExpired:
        elapsed = benchmark_clock() - started
        return 124, elapsed, f"TIMEOUT after {timeout:.0f}s"


def _load_result(short_name: str) -> dict[str, Any] | None:
    """Read the JSON blob written by a benchmark; return None if missing/parse-error."""
    path = _result_path_for(short_name)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _render_table(rows: list[dict[str, Any]]) -> str:
    """Render the per-benchmark BenchRow list as a markdown table."""
    if not rows:
        return "_(no rows recorded)_"
    out = [
        "| Metric | Claim (perf doc §) | Measured | Delta | Verdict | Severity | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        metric = str(r.get("metric", "")).replace("|", "\\|")
        claim_ref = str(r.get("claim_ref", "")).replace("|", "\\|")
        claim = str(r.get("claim", "")).replace("|", "\\|")
        measured = str(r.get("measured", "")).replace("|", "\\|")
        delta = str(r.get("delta", "")).replace("|", "\\|")
        verdict = str(r.get("verdict", ""))
        severity = str(r.get("severity", ""))
        note = str(r.get("note", "")).replace("|", "\\|")
        # Truncate noisy fields for readability; the JSON has the full text.
        if len(measured) > 80:
            measured = measured[:77] + "..."
        if len(note) > 100:
            note = note[:97] + "..."
        out.append(
            f"| {metric} | {claim_ref} — {claim} | {measured} | {delta} | "
            f"{verdict} | {severity} | {note} |"
        )
    return "\n".join(out)


def _render_hardware(hw: dict[str, Any]) -> str:
    """Render the hardware section."""
    return (
        f"- **Platform**: `{hw.get('platform')}`\n"
        f"- **Architecture**: `{hw.get('machine')}`\n"
        f"- **Python**: `{hw.get('python')}`\n"
        f"- **CPU cores**: {hw.get('physical_cores')} physical / "
        f"{hw.get('logical_cores')} logical\n"
        f"- **RAM**: {hw.get('ram_total_gb')} GB total "
        f"(at run start: {hw.get('ram_available_gb')} GB available)\n"
    )


def _render_software(sw: dict[str, str]) -> str:
    """Render the wrapped-library version table."""
    out = ["| Library | Pinned version |", "|---|---|"]
    for name in sorted(sw):
        out.append(f"| `{name}` | `{sw[name]}` |")
    return "\n".join(out)


def _render_hardware_caveats(hw: dict[str, Any]) -> str:
    """Surface hardware-vs-target gaps so the founder can weight the numbers."""
    physical = hw.get("physical_cores")
    ram_total = hw.get("ram_total_gb")
    ram_avail = hw.get("ram_available_gb")
    plat = str(hw.get("platform", ""))

    issues: list[str] = []
    # Beachhead persona (perf doc §1, v4.1 §1.5): 8-12 cores, 16-32 GB RAM, MacBook M-series.
    if physical is not None and isinstance(physical, int) and physical < 8:
        issues.append(
            f"This host has **{physical} physical cores** — below the perf doc §1 "
            "beachhead persona target of 8–12 cores. CPU-bound benchmarks (B1, B2) "
            "should be re-measured on a beachhead-spec laptop before publishing."
        )
    if ram_total is not None and isinstance(ram_total, (int, float)) and ram_total < 16:
        issues.append(
            f"Total RAM is **{ram_total} GB** — at or below the lower bound of the "
            "16–32 GB beachhead persona. Polars / DuckDB working sets may spill or "
            "trigger OOM behaviour absent on the target hardware."
        )
    if ram_avail is not None and isinstance(ram_avail, (int, float)) and ram_avail < 4:
        issues.append(
            f"Only **{ram_avail} GB available** at run start (out of "
            f"{ram_total or '?'} GB). The OS was likely paging during the run, "
            "which inflates B5 (boot) and B2 (materialize) wall-clock numbers. "
            "Re-measure on a freshly-booted host before treating B5 as definitive."
        )
    if "windows" in plat.lower():
        issues.append(
            "Host OS is **Windows** — perf doc §1 + ADR-024 P0-2 explicitly flag "
            "filesystem-lock behaviour as differing from POSIX (`msvcrt.locking` "
            "byte-range semantics, NTFS `os.rename` non-atomicity). B4's failure "
            "mode is consistent with that gap; verify on Linux before promoting."
        )

    if not issues:
        return ""
    return (
        "\n### Hardware vs beachhead persona — caveats\n\n"
        + "\n".join(f"- {it}" for it in issues)
        + "\n"
    )


def _render_version_caveats(sw: dict[str, str]) -> str:
    """Surface drift between installed dist-info and source __version__ for nucleus."""
    nucleus_v = sw.get("nucleus", "")
    try:
        import nucleus  # noqa: PLC0415

        source_v = getattr(nucleus, "__version__", nucleus_v)
    except ImportError:
        return ""
    if source_v and source_v != nucleus_v:
        return (
            "\n### Version metadata drift\n\n"
            f'- `importlib.metadata.version("nucleus")` reports **{nucleus_v}**, '
            f"but `nucleus.__version__` reads **{source_v}** from the source. "
            f"This indicates the editable install dist-info is stale — re-run "
            f"`pip install -e .` to refresh. CLI users see `{source_v}` because "
            f"`--version` reads `nucleus.__version__` directly.\n"
        )
    return ""


def _verdict_badge(verdict: str) -> str:
    """Render the section-level verdict badge in the report."""
    return {
        PASS: "**PASS**",
        FAIL: "**FAIL**",
        SKIP_DEPS: "_SKIP-DEPS_",
        "NEEDS-INVESTIGATION": "_NEEDS-INVESTIGATION_",
    }.get(verdict, verdict)


def _summarise_sevs(sections: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Bucket severities across all rows so the founder sees BLOCKERs first."""
    buckets: dict[str, list[str]] = {"BLOCKER": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for sec in sections:
        result = sec.get("result", {})
        for r in result.get("rows", []) or []:
            sev = str(r.get("severity", ""))
            verdict = str(r.get("verdict", ""))
            if sev and verdict in (FAIL, SKIP_DEPS):
                buckets.setdefault(sev, []).append(
                    f"{result.get('name')} — {r.get('metric')} ({verdict}: {r.get('measured')})"
                )
    return buckets


def _render_report(short_names: list[str], total_wall_s: float) -> str:
    """Render the complete markdown report."""
    today = datetime.now(UTC).date().isoformat()
    sections: list[dict[str, Any]] = []
    for sn in short_names:
        loaded = _load_result(sn)
        if loaded is not None:
            sections.append({"short_name": sn, **loaded})
    if not sections:
        return (
            f"# Nucleus Empirical Benchmark Baseline — {today}\n\n_(no benchmark results found)_\n"
        )

    # Pull hardware + software from the first section (consistent across run).
    hw = sections[0].get("hardware", hardware_specs())
    sw = sections[0].get("software", software_versions())

    # Aggregate verdict.
    overall_verdicts = [str(s["result"].get("overall_verdict")) for s in sections]
    if FAIL in overall_verdicts:
        overall = FAIL
    elif SKIP_DEPS in overall_verdicts and PASS not in overall_verdicts:
        overall = SKIP_DEPS
    elif all(v == PASS for v in overall_verdicts):
        overall = PASS
    else:
        overall = "MIXED"

    sev_buckets = _summarise_sevs(sections)

    parts: list[str] = []
    parts.append(f"# Nucleus Empirical Benchmark Baseline — {today}\n")
    parts.append(
        textwrap.dedent(f"""
        > Honest measurements of the v0.2.0 GA performance + reliability claims
        > documented in `docs/research/performance_reliability_targets.md`.
        >
        > **Why this exists**: those claims were never empirically verified before
        > the v0.2.0 tag. This report is the first run of the benchmark suite that
        > now lives at `scripts/benchmarks/`. Re-run with
        > `python scripts/benchmarks/run_all.py`. Per AGENTS.md §11.13 a regression
        > >10 % vs this baseline is a CI-blocking event; per the task spec a real
        > FAIL must surface honestly — never fake numbers.
    """).strip()
        + "\n"
    )

    parts.append(f"\n## Run summary\n")
    parts.append(f"- **Generated**: {now_iso()}")
    parts.append(f"- **Total suite wall-clock**: {fmt_seconds(total_wall_s)}")
    parts.append(f"- **Overall verdict**: {_verdict_badge(overall)}")
    parts.append(f"- **Benchmarks run**: {', '.join(s['short_name'].upper() for s in sections)}\n")

    if any(sev_buckets.values()):
        parts.append("### Findings to escalate (severity-ordered)\n")
        for label in ("BLOCKER", "HIGH", "MEDIUM", "LOW"):
            items = sev_buckets.get(label, [])
            if not items:
                continue
            parts.append(f"**{label}** ({len(items)})")
            for it in items:
                parts.append(f"- {it}")
            parts.append("")
    else:
        parts.append("_No severity-tagged failures recorded._\n")

    parts.append("## Hardware\n")
    parts.append(_render_hardware(hw))
    parts.append(_render_hardware_caveats(hw))
    parts.append("\n## Software (wrapped libraries)\n")
    parts.append(_render_software(sw))
    parts.append(_render_version_caveats(sw))

    parts.append("\n## How to re-run\n")
    parts.append(
        textwrap.dedent("""
        ```bash
        # Full suite (recommended; re-renders this document):
        python scripts/benchmarks/run_all.py

        # Single benchmark (any subset is valid):
        python -m scripts.benchmarks.b5_boot_time --iterations 10
        python -m scripts.benchmarks.b2_materialize --scale 1
        python -m scripts.benchmarks.b4_concurrent_run --hold 5
        python -m scripts.benchmarks.b1_tpch_duckdb --scale-factor 10 --runs 3
        python -m scripts.benchmarks.b3_postgres_ingest --scale 1m
        ```
    """).strip()
        + "\n"
    )

    for sec in sections:
        result = sec["result"]
        verdict_badge = _verdict_badge(str(result.get("overall_verdict")))
        parts.append(f"\n## {result.get('name')}  ·  {verdict_badge}\n")
        parts.append(f"- **Script**: `{result.get('script')}`")
        parts.append(f"- **Command**: `{result.get('command')}`")
        parts.append(f"- **Wall-clock**: {fmt_seconds(float(result.get('elapsed_s', 0)))}")
        parts.append(
            f"- **Started / completed**: "
            f"{result.get('started_at')} → {result.get('completed_at')}\n"
        )
        parts.append(_render_table(result.get("rows", [])))

        notes = result.get("notes") or []
        if notes:
            parts.append("\n**Notes**\n")
            for n in notes:
                parts.append(f"- {n}")
        parts.append("\n")

    parts.append("---\n")
    parts.append(f"_Generated by `scripts/benchmarks/run_all.py` on {now_iso()}._\n")
    return "\n".join(parts)


def _short_name_pairs() -> dict[str, str]:
    return {short: module for short, module in BENCHMARKS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nucleus benchmark suite orchestrator.")
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated subset of benchmarks to run (default: all). Example: --only b5,b2,b4",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip execution; just rebuild the markdown from cached _results/*.json.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Override the markdown output path "
        "(default: docs/benchmarks/<YYYY-MM-DD>_baseline.md).",
    )
    args = parser.parse_args(argv)

    requested: list[str] = (
        [s.strip().lower() for s in args.only.split(",") if s.strip()]
        if args.only
        else [s for s, _ in BENCHMARKS]
    )
    pairs = _short_name_pairs()
    unknown = [s for s in requested if s not in pairs]
    if unknown:
        print(f"[run_all] unknown benchmark(s): {unknown}; valid: {sorted(pairs)}", file=sys.stderr)
        return 2

    started = benchmark_clock()
    if not args.report_only:
        for sn in requested:
            module = pairs[sn]
            rc, elapsed, stderr_tail = _run_benchmark(sn, module, [])
            print(f"[run_all] <= {sn}: rc={rc} elapsed={fmt_seconds(elapsed)}")
            if rc not in (0, 1):
                # rc=1 is a graceful FAIL by a benchmark; anything else is a crash.
                print(f"[run_all]   stderr tail (last 600 chars): {stderr_tail[-600:]}")
    suite_elapsed = benchmark_clock() - started

    report_path = (
        args.report_path
        if args.report_path is not None
        else REPORT_DIR / f"{datetime.now(UTC).date().isoformat()}_baseline.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    md = _render_report(requested, suite_elapsed)
    report_path.write_text(md, encoding="utf-8")
    print(f"[run_all] wrote {report_path}")
    print(f"[run_all] suite total: {fmt_seconds(suite_elapsed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
