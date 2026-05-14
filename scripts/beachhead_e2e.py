"""Beachhead E2E walker — AGENTS.md §11.8 (30-min beachhead metric).

Walks the v0.1 chain (version → init → seed sqlite → ingest → query →
run) in a temp dir; classifies each step PASS / SKIPPED (v0.1 stub:
``NucleusInternalError`` "not yet implemented") / FAIL (exit 1 now).
Pure stdlib. Run from repo root: ``python scripts/beachhead_e2e.py``.
Refs: AGENTS.md §11.8; v4.1 §1.5; nucleus_cli_spec.md §3.1-§3.7.
"""

from __future__ import annotations

import argparse
import atexit
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

TARGET_S = 1800.0
STUB_MARKER = "not yet implemented"
TEMPLATE_FILES = (
    "README.md", ".gitignore", "nucleus_project.yaml",
    "assets/__init__.py", "assets/example.py", "data/.gitkeep",
)


@dataclass
class StepResult:
    name: str
    status: str  # PASS | SKIPPED | FAIL
    elapsed: float  # -1 marks short-circuited
    detail: str = ""


def _nucleus_cmd() -> list[str]:
    binary = shutil.which("nucleus")
    return [binary] if binary else [sys.executable, "-m", "nucleus.cli.main"]


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str, float]:
    """Docs: https://docs.python.org/3/library/subprocess.html"""
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          check=False, timeout=120, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr, time.perf_counter() - started


def _seed_sqlite(db_path: Path) -> None:
    """3-row users source DB. Docs: https://docs.python.org/3/library/sqlite3.html"""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.executemany("INSERT INTO users (id, name) VALUES (?, ?)",
                         [(1, "alice"), (2, "bob"), (3, "carol")])
        conn.commit()
    finally:
        conn.close()


def _classify(rc: int, out: str, err: str, expect: tuple[str, ...]) -> tuple[str, str]:
    """Map subprocess outcome to (status, detail). Stub detection wins."""
    if rc != 0 and STUB_MARKER in err:
        return "SKIPPED", "v0.1 stub - not yet implemented"
    if rc != 0:
        return "FAIL", f"rc={rc}; stderr={err.strip()[:200]}"
    missing = [tok for tok in expect if tok not in out]
    if missing:
        return "FAIL", f"missing expected tokens: {missing}"
    return "PASS", ""


def _record(num: int, label: str, status: str, dur: float, detail: str,
            results: list[StepResult]) -> None:
    elapsed = f"{dur:.2f}s" if dur >= 0 else "-"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [step {num}] {label:<28} {status:<10} {elapsed:>8}{suffix}")
    results.append(StepResult(f"{num}. {label}", status, dur, detail))


def _report(results: list[StepResult], wall: float) -> str:
    """Final ASCII summary block (no external deps)."""
    lines = ["", "=" * 60, "Nucleus v0.1 Beachhead E2E - Result Summary", "=" * 60,
             f"{'Step':<30} {'Status':<13} {'Elapsed':>10}", "-" * 60]
    for r in results:
        mark = " *" if r.status == "SKIPPED" else ""
        el = f"{r.elapsed:.2f}s" if r.elapsed >= 0 else "-"
        lines.append(f"{r.name:<30} {r.status + mark:<13} {el:>10}")
    lines += ["-" * 60,
              f"TOTAL elapsed: {wall:.2f}s    Target: 30 minutes ({TARGET_S:.0f}s)",
              f"Headroom: {TARGET_S - wall:.2f}s", "=" * 60]
    fails = sum(1 for r in results if r.status == "FAIL")
    skips = sum(1 for r in results if r.status == "SKIPPED")
    if fails:
        lines.append(f"Status: FAIL ({fails} step(s) failed)")
    elif skips:
        lines += [f"Status: PASS-WITH-SKIPS ({skips} command(s) not yet wired)", "",
                  "* SKIPPED: v0.1-pending stub; re-run after data-plane wave lands."]
    else:
        lines.append("Status: PASS")
    return "\n".join(lines)


def _bail(results: list[StepResult], wall_start: float) -> int:
    print(_report(results, time.perf_counter() - wall_start))
    return 1


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Walk the v0.1 beachhead chain (AGENTS.md §11.8).").parse_args(argv)
    nucleus = _nucleus_cmd()
    tmp = Path(tempfile.mkdtemp(prefix="nucleus_beachhead_"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    print(f"Working directory: {tmp}")
    print(f"Nucleus invocation: {' '.join(nucleus)}\n")

    results: list[StepResult] = []
    wall_start = time.perf_counter()
    project = "test-demo"
    project_dir = tmp / project

    _record(1, "setup", "PASS", time.perf_counter() - wall_start, "tmp dir registered", results)

    rc, out, err, dur = _run([*nucleus, "version"], tmp)
    status, detail = _classify(rc, out, err, ("nucleus", "duckdb", "polars", "pyiceberg", "dagster"))
    _record(2, "nucleus version", status, dur, detail, results)
    if status == "FAIL":
        return _bail(results, wall_start)

    rc, out, err, dur = _run([*nucleus, "init", project], tmp)
    status, detail = _classify(rc, out, err, ())
    if status == "PASS":
        missing = [f for f in TEMPLATE_FILES if not (project_dir / f).exists()]
        if missing:
            status, detail = "FAIL", f"missing scaffolded files: {missing}"
    _record(3, "nucleus init", status, dur, detail, results)
    if status == "FAIL":
        return _bail(results, wall_start)

    seed_start = time.perf_counter()
    _seed_sqlite(project_dir / "users.db")
    _record(4, "SQLite source seed", "PASS", time.perf_counter() - seed_start, "3 rows", results)

    rc, out, err, dur = _run([*nucleus, "ingest", "sqlite:///users.db",
                              "--table", "users", "--as", "raw.users"], project_dir)
    status5, detail = _classify(rc, out, err, ())
    _record(5, "nucleus ingest", status5, dur, detail, results)
    if status5 == "FAIL":
        return _bail(results, wall_start)

    if status5 == "SKIPPED":
        _record(6, "nucleus query", "SKIPPED", -1, "upstream ingest skipped", results)
        _record(7, "nucleus run", "SKIPPED", -1, "upstream ingest skipped", results)
    else:
        rc, out, err, dur = _run([*nucleus, "query", "SELECT count(*) as cnt FROM raw.users"],
                                 project_dir)
        status, detail = _classify(rc, out, err, ("3",))
        _record(6, "nucleus query", status, dur, detail, results)
        if status == "FAIL":
            return _bail(results, wall_start)

        rc, out, err, dur = _run([*nucleus, "run", "example.greeting"], project_dir)
        status, detail = _classify(rc, out, err, ("Materialization", "status"))
        _record(7, "nucleus run", status, dur, detail, results)
        if status == "FAIL":
            return _bail(results, wall_start)

    print(_report(results, time.perf_counter() - wall_start))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
