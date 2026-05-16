"""Cold-boot benchmark harness for the Nucleus CLI.

Measures wall-clock time of light CLI invocations (``nucleus --version``,
``nucleus --help``, ``nucleus list``) by spawning a fresh Python interpreter
for each run via :func:`subprocess.run`. Each invocation is therefore a
true cold-start measurement (no in-process module cache), which is the
metric end users actually feel when they type ``nucleus --version``.

Acceptance threshold (``docs/internal/research/performance_reliability_targets.md``
§2.1): ``nucleus --version`` median < 500 ms cold on a beachhead-class
laptop. Heavy libraries (``litellm``, ``dlt``, ``dagster``, ``pyiceberg``,
``polars``, ``duckdb``, ``s3fs``, ``psycopg2``, ``fastapi``, ``uvicorn``)
MUST NOT be eagerly imported by ``nucleus.cli.main`` — see
:mod:`scripts.check_lazy_imports` for the static enforcement counterpart.

Per ``AGENTS.md`` Constraint #11: this harness pins the threshold against
the PoC #4 baseline (5.82 s for ``nucleus up``) and the perf-doc §10 #4
target (< 500 ms for ``nucleus --version``); regressions surface as a
non-zero exit code so CI catches them before they ship.

Usage
-----
    python scripts/benchmark_cli_cold_boot.py
    python scripts/benchmark_cli_cold_boot.py --runs 20
    python scripts/benchmark_cli_cold_boot.py --threshold-ms 500

Exit codes
----------
    0  All commands within budget
    1  ``nucleus --version`` exceeded the cold-boot threshold
    2  Invocation error (CLI not installed, command crashed, etc.)

Docs:
    https://docs.python.org/3.11/library/subprocess.html#subprocess.run
    https://docs.python.org/3.11/library/statistics.html
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Per ``docs/internal/research/performance_reliability_targets.md`` §2.1 cold target.
DEFAULT_THRESHOLD_MS: int = 500
DEFAULT_RUNS: int = 10
DEFAULT_TIMEOUT_S: float = 30.0


def _resolve_nucleus_argv() -> tuple[str, ...]:
    """Locate the ``nucleus`` console script.

    Prefers ``shutil.which`` (PATH lookup, identical to what end users get).
    Falls back to ``<venv>/Scripts/nucleus`` (Windows) or ``<venv>/bin/nucleus``
    (POSIX) when run from a non-activated developer venv. Final fallback is
    ``python -m nucleus.cli.main`` so the harness still works in containers /
    CI where the console script is not installed.
    """
    on_path = shutil.which("nucleus")
    if on_path:
        return (on_path,)
    here = Path(sys.executable).resolve()
    # ``<venv>/Scripts/python.exe`` -> ``<venv>/Scripts/nucleus.exe``
    sibling = here.parent / ("nucleus.exe" if sys.platform == "win32" else "nucleus")
    if sibling.is_file():
        return (str(sibling),)
    return (sys.executable, "-m", "nucleus.cli.main")


_NUCLEUS_ARGV: tuple[str, ...] = _resolve_nucleus_argv()

# Commands measured. ``--version`` is the gating one; ``--help`` and ``list``
# are reported for visibility (informational only — not gating).
_COMMANDS: tuple[tuple[str, ...], ...] = (
    (*_NUCLEUS_ARGV, "--version"),
    (*_NUCLEUS_ARGV, "--help"),
    (*_NUCLEUS_ARGV, "list"),
)

# Per-command threshold. Only ``--version`` gates exit code; the others
# inform tuning. ``list`` is allowed to be slower because it loads the
# project's ``assets/`` package at runtime.
_GATING_COMMAND: tuple[str, ...] = (*_NUCLEUS_ARGV, "--version")


@dataclass
class CommandTiming:
    """Per-command benchmark result.

    ``runs_ms`` holds the per-invocation wall-clock in milliseconds; the
    derived statistics (min, median, p95, max) are computed lazily so the
    JSON output stays a single source of truth for downstream tooling
    (e.g. ``scripts/release.py`` future perf gate).
    """

    argv: tuple[str, ...]
    runs_ms: list[float] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def min_ms(self) -> float:
        return min(self.runs_ms) if self.runs_ms else float("nan")

    @property
    def median_ms(self) -> float:
        return statistics.median(self.runs_ms) if self.runs_ms else float("nan")

    @property
    def p95_ms(self) -> float:
        if not self.runs_ms:
            return float("nan")
        # Only one statistically meaningful percentile here; quantiles requires
        # n >= 2. For n == 1 fall back to the only sample we have.
        if len(self.runs_ms) < 2:
            return self.runs_ms[0]
        return statistics.quantiles(self.runs_ms, n=20)[18]  # 95th percentile

    @property
    def max_ms(self) -> float:
        return max(self.runs_ms) if self.runs_ms else float("nan")


def _run_once(argv: tuple[str, ...], timeout_s: float) -> tuple[float, str | None]:
    """Spawn ``argv`` via subprocess; return (wall-clock-ms, error-or-None).

    Each call is a fresh Python interpreter so module cache is cold.
    """
    started = time.perf_counter()
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout_s,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        return 0.0, f"{argv[0]} not on PATH: {exc}"
    except subprocess.TimeoutExpired:
        return timeout_s * 1000.0, f"timed out after {timeout_s}s"
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if result.returncode != 0:
        # ``nucleus list`` exits 1 in a directory without nucleus_project.yaml
        # — don't treat that as a hard error; surface as an info-level note.
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        if argv[-1] == "list" and "nucleus_project.yaml" in stderr:
            return elapsed_ms, None
        return elapsed_ms, f"exit {result.returncode}: {stderr[:200]}"
    return elapsed_ms, None


def _bench_command(argv: tuple[str, ...], runs: int, timeout_s: float) -> CommandTiming:
    """Run ``argv`` ``runs`` times and collect timings + failures."""
    timing = CommandTiming(argv=argv)
    for _ in range(runs):
        elapsed_ms, err = _run_once(argv, timeout_s)
        if err is None:
            timing.runs_ms.append(elapsed_ms)
        else:
            timing.failures.append(err)
    return timing


def _format_row(label: str, timing: CommandTiming) -> str:
    """Render one timing row for the human-readable report."""
    if not timing.runs_ms:
        return f"  {label:<22}  no successful runs (failures: {len(timing.failures)})"
    return (
        f"  {label:<22}  "
        f"min={timing.min_ms:>7.1f}ms  "
        f"median={timing.median_ms:>7.1f}ms  "
        f"p95={timing.p95_ms:>7.1f}ms  "
        f"max={timing.max_ms:>7.1f}ms  "
        f"(n={len(timing.runs_ms)})"
    )


def _argv_label(argv: tuple[str, ...]) -> str:
    """Human-readable label for an argv tuple, e.g. ``nucleus --version``.

    Strips the resolved binary path / ``python -m`` prefix so labels are
    stable across PATH / venv / module-execution invocations and the
    JSON/text output stays diff-friendly across machines.
    """
    prefix_len = len(_NUCLEUS_ARGV)
    suffix = argv[prefix_len:]
    return " ".join(("nucleus", *suffix))


def main() -> int:
    """Entry point — parse args, run benchmarks, exit with verdict code."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Number of subprocess invocations per command (default: {DEFAULT_RUNS}).",
    )
    parser.add_argument(
        "--threshold-ms",
        type=int,
        default=DEFAULT_THRESHOLD_MS,
        help=(
            "Median-time gate for `nucleus --version` in ms "
            f"(default: {DEFAULT_THRESHOLD_MS}, per perf doc §2.1)."
        ),
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"Per-invocation timeout in seconds (default: {DEFAULT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the human-readable report.",
    )
    args = parser.parse_args()

    timings: dict[str, CommandTiming] = {}
    for argv in _COMMANDS:
        label = _argv_label(argv)
        timings[label] = _bench_command(argv, runs=args.runs, timeout_s=args.timeout_s)

    gating_label = _argv_label(_GATING_COMMAND)
    gating_timing = timings[gating_label]
    median_ms = gating_timing.median_ms
    pass_gate = median_ms <= args.threshold_ms and bool(gating_timing.runs_ms)
    verdict = "PASS" if pass_gate else "FAIL"

    if args.json:
        payload = {
            "_schema_version": 1,
            "threshold_ms": args.threshold_ms,
            "verdict": verdict,
            "commands": {
                label: {
                    "argv": list(t.argv),
                    "runs_ms": t.runs_ms,
                    "min_ms": t.min_ms if t.runs_ms else None,
                    "median_ms": t.median_ms if t.runs_ms else None,
                    "p95_ms": t.p95_ms if t.runs_ms else None,
                    "max_ms": t.max_ms if t.runs_ms else None,
                    "failures": t.failures,
                }
                for label, t in timings.items()
            },
        }
        print(json.dumps(payload, indent=2))
    else:
        print("=" * 78)
        print(" Nucleus CLI cold-boot benchmark")
        print(" Source: docs/internal/research/performance_reliability_targets.md §2.1 / §10 #4")
        print(f" Runs per command: {args.runs}    Threshold: {args.threshold_ms}ms cold")
        print("=" * 78)
        for label in (_argv_label(a) for a in _COMMANDS):
            print(_format_row(label, timings[label]))
        for label in (_argv_label(a) for a in _COMMANDS):
            failures = timings[label].failures
            if failures:
                print(f"\n  Failures for `{label}`:")
                for failure in failures[:5]:
                    print(f"    - {failure}")
        print()
        print(
            f"  Gate: `{gating_label}` median = "
            f"{median_ms:.1f}ms (threshold {args.threshold_ms}ms)  -->  {verdict}"
        )
        print()
        if not pass_gate and gating_timing.runs_ms:
            print(
                "  HINT: run `python scripts/check_lazy_imports.py` to verify no\n"
                "        heavy modules leaked into the cli.main module top-level."
            )

    if not gating_timing.runs_ms:
        return 2
    return 0 if pass_gate else 1


if __name__ == "__main__":
    sys.exit(main())
