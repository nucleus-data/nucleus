"""Empirical NTFS atomicity harness for ``os.replace``.

Per ``docs/research/performance_reliability_targets.md`` §10 #5 +
``docs/research/windows_atomicity.md`` (companion findings doc).

What this validates
-------------------
The Iceberg SQL catalog used by Nucleus (``type="sql"`` against SQLite)
relies on SQLite atomic transactions for the metadata-pointer swap, so the
filesystem ``rename`` atomicity question is moot for our specific
catalog choice. **However**, every other path that swaps a file
(lockfile rotation, cached metadata, etc.) still depends on
``os.replace`` doing the right thing on NTFS. This harness empirically
verifies it.

Test design
-----------
1. Two worker processes are spawned in parallel.
2. Each worker writes a unique source file (``src_1`` containing
   ``b"AAAA…"`` and ``src_2`` containing ``b"BBBB…"``).
3. Both call ``os.replace(src_N, target)`` against the SAME target path,
   timed to overlap as tightly as possible (synchronised on a
   :class:`multiprocessing.Barrier`).
4. After both return, the parent reads ``target`` and classifies the
   outcome:
     * ``A`` — target's content matches src_1 (writer 1 won)
     * ``B`` — target's content matches src_2 (writer 2 won)
     * ``MISSING`` — target file does not exist (NEVER expected)
     * ``TORN`` — target's content is neither src_1 nor src_2 (NEVER expected)
5. Repeat for *iterations* iterations (default 100).

Acceptance: ``MISSING`` count + ``TORN`` count == 0.

If any "unexpected state" is observed, ``os.replace`` is not safe on this
filesystem and Nucleus must add an explicit advisory lock for non-Iceberg
catalog code paths (we already have the asset-level lock per
``coordination/locks.py`` for the AMA write path).

Caveats vs documented behaviour
-------------------------------
This harness verifies steady-state contention atomicity (both writers
return success or one raises ``PermissionError`` while the winner's
content lands intact). It does NOT simulate the full kill-9 / power-cut
case the perf doc §10 #5 also worries about — see
``docs/research/windows_atomicity.md`` §"Kill -9 caveat" for that.

Docs
----
* https://docs.python.org/3.11/library/os.html#os.replace
* https://docs.python.org/3.11/library/multiprocessing.html
* https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa

Usage
-----
    python scripts/test_windows_atomicity.py
    python scripts/test_windows_atomicity.py --iterations 500 --payload-bytes 65536
    python scripts/test_windows_atomicity.py --json
    python scripts/test_windows_atomicity.py --help

Exit codes
----------
    0  zero unexpected outcomes (TORN + MISSING == 0)
    1  one or more unexpected outcomes
    2  invocation / IO error
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Tag bytes for src_1 and src_2. Distinct, repeated for the configured
# payload size so the parent can recognise either writer's content
# verbatim or detect a torn write (mixed bytes).
_TAG_A: int = ord("A")
_TAG_B: int = ord("B")


# Outcome classes returned by the parent classifier.
_OUTCOME_A: str = "A"  # writer 1 won
_OUTCOME_B: str = "B"  # writer 2 won
_OUTCOME_MISSING: str = "MISSING"  # target file disappeared (unexpected)
_OUTCOME_TORN: str = "TORN"  # mixed / partial bytes (unexpected)


@dataclass
class IterationResult:
    """Outcome of a single race."""

    iteration: int
    outcome: str
    writer1_error: str | None = None
    writer2_error: str | None = None


@dataclass
class HarnessReport:
    """Aggregated results across all iterations."""

    platform: str = field(default_factory=lambda: platform.platform())
    is_windows: bool = field(default_factory=lambda: platform.system() == "Windows")
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    iterations: int = 0
    payload_bytes: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    unexpected: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.counts.get(_OUTCOME_TORN, 0) == 0 and self.counts.get(_OUTCOME_MISSING, 0) == 0


# ---------------------------------------------------------------------------
# Worker (runs in a child process)
# ---------------------------------------------------------------------------


def _worker(
    worker_id: int,
    src_path_str: str,
    target_path_str: str,
    barrier: mp.synchronize.Barrier,
    err_queue: mp.queues.Queue,
) -> None:
    """Replace *target* with *src* once the barrier opens.

    Communicates the outcome back via *err_queue*: pushes ``None`` on
    success, or the exception's repr on any failure (PermissionError,
    FileNotFoundError, etc.). The harness treats ``PermissionError`` /
    ``FileNotFoundError`` as expected races (one winner, one loser);
    other errors propagate as "unexpected".
    """
    src_path = Path(src_path_str)
    target_path = Path(target_path_str)
    try:
        # Wait for the parent to release both workers simultaneously so
        # the race window is as tight as the OS scheduler allows.
        barrier.wait(timeout=30.0)
        os.replace(str(src_path), str(target_path))
        err_queue.put((worker_id, None))
    except Exception as exc:  # noqa: BLE001 — we want to capture every variant
        err_queue.put((worker_id, repr(exc)))


# ---------------------------------------------------------------------------
# Iteration driver
# ---------------------------------------------------------------------------


def _run_iteration(
    iteration: int,
    work_dir: Path,
    payload_bytes: int,
) -> IterationResult:
    """Run one race iteration; return its classified outcome."""
    src1 = work_dir / f"src_{iteration}_1.bin"
    src2 = work_dir / f"src_{iteration}_2.bin"
    target = work_dir / f"target_{iteration}.bin"

    src1.write_bytes(bytes([_TAG_A]) * payload_bytes)
    src2.write_bytes(bytes([_TAG_B]) * payload_bytes)
    # Pre-create the target so os.replace overwrites instead of "moves
    # into a non-existent slot" (the latter is the trivial case).
    target.write_bytes(b"\x00" * payload_bytes)

    barrier = mp.Barrier(parties=3)  # 2 workers + the parent releaser
    err_queue: mp.queues.Queue = mp.Queue()

    p1 = mp.Process(
        target=_worker,
        args=(1, str(src1), str(target), barrier, err_queue),
        name=f"worker-1-iter{iteration}",
    )
    p2 = mp.Process(
        target=_worker,
        args=(2, str(src2), str(target), barrier, err_queue),
        name=f"worker-2-iter{iteration}",
    )
    p1.start()
    p2.start()

    # Release both workers from the barrier as close together as we can.
    barrier.wait(timeout=30.0)

    p1.join(timeout=30.0)
    p2.join(timeout=30.0)

    # Drain the queue; collect (worker_id, error_repr) tuples.
    errors: dict[int, str | None] = {1: None, 2: None}
    while not err_queue.empty():
        wid, err = err_queue.get_nowait()
        errors[wid] = err

    # Classify by reading the target.
    if not target.exists():
        return IterationResult(
            iteration=iteration,
            outcome=_OUTCOME_MISSING,
            writer1_error=errors.get(1),
            writer2_error=errors.get(2),
        )

    content = target.read_bytes()
    if all(b == _TAG_A for b in content):
        outcome = _OUTCOME_A
    elif all(b == _TAG_B for b in content):
        outcome = _OUTCOME_B
    else:
        outcome = _OUTCOME_TORN

    return IterationResult(
        iteration=iteration,
        outcome=outcome,
        writer1_error=errors.get(1),
        writer2_error=errors.get(2),
    )


# ---------------------------------------------------------------------------
# Public harness entry
# ---------------------------------------------------------------------------


def run_harness(iterations: int, payload_bytes: int) -> HarnessReport:
    """Drive *iterations* parallel-replace iterations, return the report."""
    if iterations < 1:
        raise ValueError(f"iterations must be >= 1; got {iterations}")
    if payload_bytes < 1:
        raise ValueError(f"payload_bytes must be >= 1; got {payload_bytes}")

    report = HarnessReport(
        iterations=iterations,
        payload_bytes=payload_bytes,
        counts={
            _OUTCOME_A: 0,
            _OUTCOME_B: 0,
            _OUTCOME_TORN: 0,
            _OUTCOME_MISSING: 0,
        },
    )

    work_dir = Path(tempfile.mkdtemp(prefix="nucleus_atomicity_"))
    t0 = time.perf_counter()
    try:
        for i in range(1, iterations + 1):
            result = _run_iteration(i, work_dir, payload_bytes)
            report.counts[result.outcome] = report.counts.get(result.outcome, 0) + 1
            if result.outcome in (_OUTCOME_TORN, _OUTCOME_MISSING):
                report.unexpected.append(asdict(result))
    finally:
        report.duration_seconds = time.perf_counter() - t0
        # Best-effort cleanup; on Windows the kernel sometimes holds the
        # last-known target locked momentarily — ignore if unlinkable.
        shutil.rmtree(work_dir, ignore_errors=True)

    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _render(report: HarnessReport) -> str:
    """Return the human-readable report."""
    counts = report.counts
    summary_lines = [
        "Windows NTFS atomicity harness for os.replace",
        "=" * 60,
        f"Platform        : {report.platform}",
        f"Python version  : {report.python_version}",
        f"Is Windows      : {report.is_windows}",
        f"Iterations      : {report.iterations}",
        f"Payload (bytes) : {report.payload_bytes}",
        f"Duration (s)    : {report.duration_seconds:.2f}",
        "",
        "Outcome counts:",
        f"  A (writer 1)  : {counts.get(_OUTCOME_A, 0)}",
        f"  B (writer 2)  : {counts.get(_OUTCOME_B, 0)}",
        f"  TORN          : {counts.get(_OUTCOME_TORN, 0)}",
        f"  MISSING       : {counts.get(_OUTCOME_MISSING, 0)}",
        "",
    ]

    if report.ok:
        summary_lines.append(
            "PASS: zero unexpected states. os.replace appears atomic on this filesystem."
        )
    else:
        summary_lines.append(
            "FAIL: unexpected states observed. os.replace is NOT safe on this "
            "filesystem; Nucleus must add an advisory lock for the affected "
            "code path. See docs/research/windows_atomicity.md."
        )
        summary_lines.append("")
        summary_lines.append("Failing iterations (first 5):")
        for entry in report.unexpected[:5]:
            summary_lines.append(
                f"  iter={entry['iteration']:3d} outcome={entry['outcome']} "
                f"w1_err={entry['writer1_error']!r} w2_err={entry['writer2_error']!r}"
            )

    return "\n".join(summary_lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Empirically test os.replace atomicity under contention. "
            "Per perf doc §10 #5 + docs/research/windows_atomicity.md."
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="How many race iterations to run (default: 100).",
    )
    parser.add_argument(
        "--payload-bytes",
        type=int,
        default=4096,
        help="Bytes per source file (default: 4096; one filesystem block).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human report.",
    )
    args = parser.parse_args(argv)

    try:
        report = run_harness(args.iterations, args.payload_bytes)
    except ValueError as exc:
        print(f"test_windows_atomicity: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(_render(report))

    return 0 if report.ok else 1


if __name__ == "__main__":
    # Guard with __main__ so multiprocessing.spawn can re-import safely
    # on Windows without re-running run_harness().
    raise SystemExit(main())
