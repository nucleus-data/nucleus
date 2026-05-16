"""B5 — Boot-time benchmark.

Verifies the perf doc §2.1 claims for CLI startup latency:

    nucleus --version   cold < 500 ms / warm < 150 ms
    nucleus --help      cold < 500 ms / warm < 150 ms
    nucleus up          cold < 10 s    / warm < 3 s   (PoC #4 already validated 5.82 s)

Two invocation paths are measured because users hit both in practice:

* ``nucleus.exe`` console script (PEP 503 entry point installed by
  ``pip install -e .``) — the path users type at the shell.
* ``python -m nucleus.cli.main`` — the path used by tests, scripts, and
  CI (avoids PATH issues; loads heavier because of the ``-m`` machinery).

Each measurement runs in a **fresh interpreter** so we capture true import
cost. We don't purge the OS page cache (would require sudo on Linux /
restart on Windows), but the first iteration after a long pause
approximates a "cold" Python import; subsequent iterations measure "warm"
with bytecode caches loaded.

Per task spec the script is **runnable everywhere** — no Docker, no
external services, no large temp files, no internet. This is the
guaranteed-PASS-or-FAIL benchmark in the suite.

# Stability: this script is internal to the benchmark suite (not part of
# the public Nucleus API). It may be reorganised between minor releases.

Docs:
    Python ``subprocess`` — https://docs.python.org/3/library/subprocess.html
    Python ``time.perf_counter`` — https://docs.python.org/3/library/time.html#time.perf_counter
    PoC #4 reference — AGENTS.md §1 status block (5.82 s validated 2026-05-12)
    Perf doc claims — docs/internal/research/performance_reliability_targets.md §2.1
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.benchmarks._common import (
    FAIL,
    PASS,
    BenchResult,
    BenchRow,
    benchmark_clock,
    classify,
    fmt_delta,
    fmt_seconds,
    now_iso,
    severity_for,
    stats_summary,
    write_result,
)

DEFAULT_ITERATIONS: int = 10
SUBPROC_TIMEOUT_S: float = 30.0

# Claims from docs/internal/research/performance_reliability_targets.md §2.1.
CLAIM_VERSION_COLD_S: float = 0.5
CLAIM_VERSION_WARM_S: float = 0.150
CLAIM_HELP_COLD_S: float = 0.5
CLAIM_HELP_WARM_S: float = 0.150


def _find_console_script(python_exe: str) -> str | None:
    """Locate ``nucleus.exe`` / ``nucleus`` next to *python_exe*.

    ``shutil.which`` may miss venv-local console scripts when PATH wasn't
    activated. Look in the same Scripts/bin directory as the interpreter.
    """
    bin_dir = Path(python_exe).parent
    for candidate in ("nucleus.exe", "nucleus"):
        path = bin_dir / candidate
        if path.is_file():
            return str(path)
    return None


def _spawn_command(args: list[str]) -> tuple[float, int, str]:
    """Run *args* as a fresh subprocess; return (wall_clock_s, returncode, stderr)."""
    started = benchmark_clock()
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=SUBPROC_TIMEOUT_S,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = benchmark_clock() - started
    return elapsed, proc.returncode, proc.stderr or ""


def _measure_command(args: list[str], iterations: int) -> tuple[list[float], list[str]]:
    """Run *args* *iterations* times, returning (elapsed_seconds, error_messages)."""
    elapsed: list[float] = []
    errors: list[str] = []
    for i in range(iterations):
        wall, rc, stderr = _spawn_command(args)
        elapsed.append(wall)
        if rc != 0:
            tag = f"iter#{i + 1} rc={rc}: {stderr.strip()[:160]}"
            errors.append(tag)
    return elapsed, errors


def _row_for(
    label: str,
    measured_s: float,
    claim_s: float,
    *,
    note: str = "",
) -> BenchRow:
    verdict = classify(measured_s, claim_s, lower_is_better=True)
    severity = "" if verdict == PASS else severity_for(measured_s, claim_s, lower_is_better=True)
    return BenchRow(
        metric=label,
        claim_ref="perf doc §2.1",
        claim=f"<{fmt_seconds(claim_s)}",
        measured=fmt_seconds(measured_s),
        verdict=verdict,
        delta=fmt_delta(measured_s, claim_s),
        severity=severity,
        note=note,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on PASS, 1 on FAIL, 2 on configuration error."""
    parser = argparse.ArgumentParser(description="Nucleus B5 — Boot-time benchmark.")
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Iterations per command (default {DEFAULT_ITERATIONS}).",
    )
    parser.add_argument(
        "--include-up",
        action="store_true",
        help="Also run `nucleus up` cold-boot once (slow; PoC #4 validates 5.82 s).",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()

    python = sys.executable
    nucleus_exe = shutil.which("nucleus") or _find_console_script(python)

    rows: list[BenchRow] = []
    notes: list[str] = []
    raw: dict[str, object] = {}

    # Path 1 — the console script (what users type)
    if nucleus_exe and Path(nucleus_exe).is_file():
        cmd_v_exe = [nucleus_exe, "--version"]
        cmd_h_exe = [nucleus_exe, "--help"]
        print(f"[B5] console script = {nucleus_exe}")
        print(f"[B5] iterations = {args.iterations}")
        print(f"[B5] running `nucleus --version` x{args.iterations} ...")
        v_exe_elapsed, v_exe_errs = _measure_command(cmd_v_exe, args.iterations)
        v_exe_stats = stats_summary(v_exe_elapsed)
        print(f"[B5] running `nucleus --help` x{args.iterations} ...")
        h_exe_elapsed, h_exe_errs = _measure_command(cmd_h_exe, args.iterations)
        h_exe_stats = stats_summary(h_exe_elapsed)

        rows.append(
            _row_for(
                "nucleus --version (console, cold)",
                v_exe_elapsed[0],
                CLAIM_VERSION_COLD_S,
                note="console script via PEP 503 entry point",
            )
        )
        rows.append(
            _row_for(
                f"nucleus --version (console, warm median over {args.iterations - 1})",
                v_exe_stats["median"],
                CLAIM_VERSION_WARM_S,
            )
        )
        rows.append(
            _row_for(
                "nucleus --version (console, P95)",
                v_exe_stats["p95"],
                CLAIM_VERSION_COLD_S,
                note="cold-claim reused for tail latency",
            )
        )
        rows.append(_row_for("nucleus --help (console, cold)", h_exe_elapsed[0], CLAIM_HELP_COLD_S))
        rows.append(
            _row_for(
                f"nucleus --help (console, warm median over {args.iterations - 1})",
                h_exe_stats["median"],
                CLAIM_HELP_WARM_S,
            )
        )
        if v_exe_errs:
            notes.append(
                f"nucleus --version (console) had {len(v_exe_errs)} non-zero exits; "
                f"first: {v_exe_errs[0]}"
            )
        if h_exe_errs:
            notes.append(
                f"nucleus --help (console) had {len(h_exe_errs)} non-zero exits; "
                f"first: {h_exe_errs[0]}"
            )
        raw["console_version_s"] = v_exe_elapsed
        raw["console_version_stats"] = v_exe_stats
        raw["console_help_s"] = h_exe_elapsed
        raw["console_help_stats"] = h_exe_stats
    else:
        notes.append("Console script `nucleus` not found on PATH — only python -m form measured.")

    # Path 2 — `python -m nucleus.cli.main` (used by tests, slower because of -m machinery)
    cmd_version = [python, "-m", "nucleus.cli.main", "--version"]
    cmd_help = [python, "-m", "nucleus.cli.main", "--help"]
    print(f"[B5] python = {python}")
    print(f"[B5] running `python -m nucleus.cli.main --version` x{args.iterations} ...")
    version_elapsed, version_errs = _measure_command(cmd_version, args.iterations)
    version_stats = stats_summary(version_elapsed)
    print(f"[B5] running `python -m nucleus.cli.main --help` x{args.iterations} ...")
    help_elapsed, help_errs = _measure_command(cmd_help, args.iterations)
    help_stats = stats_summary(help_elapsed)

    rows.append(
        _row_for(
            "python -m nucleus.cli.main --version (cold)",
            version_elapsed[0] if version_elapsed else float("nan"),
            CLAIM_VERSION_COLD_S,
            note="`-m` form has higher startup cost; surfaced separately so the gap is visible.",
        )
    )
    rows.append(
        _row_for(
            f"python -m nucleus.cli.main --version (warm median over {args.iterations - 1})",
            version_stats["median"],
            CLAIM_VERSION_WARM_S,
        )
    )
    rows.append(
        _row_for(
            "python -m nucleus.cli.main --help (cold)",
            help_elapsed[0] if help_elapsed else float("nan"),
            CLAIM_HELP_COLD_S,
        )
    )
    rows.append(
        _row_for(
            f"python -m nucleus.cli.main --help (warm median over {args.iterations - 1})",
            help_stats["median"],
            CLAIM_HELP_WARM_S,
        )
    )

    if version_errs:
        notes.append(
            f"python -m --version had {len(version_errs)} non-zero exits; first: {version_errs[0]}"
        )
    if help_errs:
        notes.append(f"python -m --help had {len(help_errs)} non-zero exits; first: {help_errs[0]}")
    raw["module_version_s"] = version_elapsed
    raw["module_version_stats"] = version_stats
    raw["module_help_s"] = help_elapsed
    raw["module_help_stats"] = help_stats

    if args.include_up:
        # `nucleus up` requires Docker + the project compose file; only run when explicitly asked.
        # Per PoC #4 (AGENTS.md §1) this was 5.82 s on the validation host.
        compose = Path(__file__).resolve().parent.parent.parent / "docker-compose.demo.yml"
        if not compose.is_file():
            notes.append("`nucleus up` skipped: docker-compose.demo.yml not found at repo root.")
        else:
            print(f"[B5] running `nucleus up` once (using {compose.name}) ...")
            up_args = [python, "-m", "nucleus.cli.main", "up"]
            up_wall, up_rc, up_err = _spawn_command(up_args)
            verdict = PASS if up_rc == 0 and up_wall <= 10.0 else FAIL
            rows.append(
                BenchRow(
                    metric="nucleus up (cold boot)",
                    claim_ref="perf doc §2.1; PoC #4",
                    claim="<10s",
                    measured=fmt_seconds(up_wall),
                    verdict=verdict,
                    delta=fmt_delta(up_wall, 10.0),
                    severity="" if verdict == PASS else severity_for(up_wall, 10.0),
                    note=(
                        "docker stack started"
                        if up_rc == 0
                        else f"rc={up_rc} stderr={up_err.strip()[:120]}"
                    ),
                )
            )
            # Cleanup — best-effort `nucleus down`. Not measured.
            subprocess.run(  # noqa: S603 — controlled args, not user input
                [python, "-m", "nucleus.cli.main", "down"],
                capture_output=True,
                check=False,
                timeout=60,
            )

    overall = PASS if all(r.verdict == PASS for r in rows) else FAIL

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B5: Boot time",
        script="scripts/internal/benchmarks/b5_boot_time.py",
        command=f"{python} -m scripts.benchmarks.b5_boot_time --iterations {args.iterations}",
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
    print(f"[B5] wrote {out}")
    print(f"[B5] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(
            f"  - {r.metric}: claim={r.claim} measured={r.measured} delta={r.delta} -> {r.verdict}{sev}"
        )
    return 0 if overall == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
