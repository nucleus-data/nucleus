"""B8 — Workbench HTTP API latency benchmark.

Measures end-to-end latency of the Workbench's ``POST /api/query`` endpoint
(see ``src/nucleus/workbench/api/query.py``) against a small Iceberg
warehouse — the surface a Workbench user actually hits when running a query
in the Editorial Hero v0.2 Query Editor (per ADR-016 §3 Fork B).

What's measured
---------------
    * uvicorn process spin-up time (informational; per perf doc §2.1
      Workbench claim is <2 s initial page load).
    * POST /api/health round-trip (sanity ping; <100 ms target).
    * POST /api/query for three representative queries:
        Q1: ``SELECT 1`` — pure framework + DuckDB connect overhead.
        Q2: ``SELECT COUNT(*) FROM bench.api_demo`` — single Iceberg scan.
        Q3: ``SELECT name, SUM(amount) FROM bench.api_demo GROUP BY name``
            — aggregate over the same table.

Each query runs N times. Reports min / median / P95 / P99 / max.

Skip behaviour
--------------
    * If the ``[workbench]`` extras (FastAPI / uvicorn / orjson) are not
      installed, the benchmark records SKIP-DEPS LOW and exits 0. The
      v0.2 install matrix (ADR-039) makes Workbench optional, so a core-
      only install must not fail the suite.
    * If the uvicorn process does not become ready within the timeout
      (free port races, antivirus on Windows), records SKIP-DEPS MEDIUM.

Why not ``TestClient``
----------------------
    * The task spec asks for **HTTP** latency on ``/api/query``. FastAPI
      ``TestClient`` is in-process and would mis-measure framework
      overhead by skipping the WSGI/ASGI loop. Spawning real uvicorn
      keeps the measurement honest.

Docs:
    httpx — https://www.python-httpx.org/  (already in core deps)
    uvicorn — https://www.uvicorn.org/
    FastAPI ``TestClient`` (intentionally NOT used) — https://fastapi.tiangolo.com/tutorial/testing/
    Workbench API — src/nucleus/workbench/api/query.py
    Perf doc §2.6 — Workbench UI budgets
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    LOW,
    MEDIUM,
    PASS,
    SKIP_DEPS,
    BenchResult,
    BenchRow,
    benchmark_clock,
    classify,
    ensure_repo_root_on_path,
    fmt_seconds,
    now_iso,
    severity_for,
    stats_summary,
    write_result,
)

DEFAULT_RUNS_PER_QUERY: int = 10
# 60s rather than 30s — the workbench app's import chain pulls in
# ``nucleus.coordination.error_translation`` which transitively loads
# ``openlineage.client`` (~3 s); on a paging laptop the full uvicorn
# bootstrap + first ASGI factory call can exceed 30 s.
SERVER_READY_TIMEOUT_S: float = 60.0

# Perf doc §2.6 row "API response: list runs (paginated 50)".
# Closest published claim for an API endpoint; reused as a reference target
# for the in-process /api/health probe below.
CLAIM_HEALTH_LATENCY_S: float = 0.100

# No published budget for /api/query yet — these are the user-expectation
# defaults documented in `docs/internal/research/benchmarks_v0.2.0.md` after this run.
INFORMATIONAL_QUERY_BUDGET_S: float = 0.500


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _seed_warehouse(warehouse: Path, rows: int = 10_000) -> str:
    """Materialize a small Iceberg table at ``warehouse`` for the API to query.

    Returns the asset key (``"bench.api_demo"``) for use in /api/query bodies.
    """
    ensure_repo_root_on_path()
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/

    import nucleus

    asset_key = "bench.api_demo"
    df = pl.DataFrame(
        {
            "id": list(range(rows)),
            "amount": [(i * 1.5) % 1000.0 for i in range(rows)],
            "name": [f"name_{i % 100}" for i in range(rows)],
        }
    )

    @nucleus.asset(asset_key)
    def _body() -> pl.DataFrame:
        return df

    nucleus.materialize(asset_key, warehouse_dir=warehouse)
    return asset_key


def _httpx_client_for_localhost(timeout_s: float = 5.0) -> Any:  # type: ignore[name-defined]
    """Return a httpx.Client that bypasses any system / corporate proxy.

    Some hosts (e.g. corporate Bosch laptops) route 127.0.0.1 through an
    enterprise proxy that returns "Web Site does not exist" for localhost.
    httpx's ``trust_env=False`` skips ``HTTP_PROXY`` / ``HTTPS_PROXY`` /
    ``ALL_PROXY`` env-var lookups; ``mounts={}`` plus an explicit no-proxy
    transport is the documented way to force a direct TCP connect.

    Docs: https://www.python-httpx.org/advanced/proxies/  (trust_env section)
    """
    import httpx  # Docs: https://www.python-httpx.org/  (core dep)

    return httpx.Client(timeout=timeout_s, trust_env=False)


def _wait_for_server(host: str, port: int, timeout_s: float) -> bool:
    """Poll ``GET /api/health`` until 200 or timeout."""
    import httpx  # Docs: https://www.python-httpx.org/  (core dep)

    deadline = time.monotonic() + timeout_s
    with _httpx_client_for_localhost(timeout_s=2.0) as client:
        while time.monotonic() < deadline:
            try:
                r = client.get(f"http://{host}:{port}/api/health")
                if r.status_code == 200:
                    return True
            except (httpx.HTTPError, OSError):
                pass
            time.sleep(0.2)
    return False


def _spawn_uvicorn(host: str, port: int, log_path: Path) -> subprocess.Popen[bytes]:
    """Start ``uvicorn nucleus.workbench.app:create_app`` in a subprocess.

    stdout + stderr are redirected to *log_path* so a failure is recoverable.
    """
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "nucleus.workbench.app:create_app",
        "--factory",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    # The file handle outlives this function on purpose: subprocess.Popen
    # owns it for the lifetime of the child process. Closing the handle
    # here would terminate child stdout writes, so the SIM115 / file-leak
    # warning is silenced — the child process drains it. Use Path.open
    # per PTH123.
    log_fh = log_path.open("wb")
    return subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )


def _post_query(
    host: str, port: int, sql: str, warehouse: Path, *, limit: int = 200
) -> tuple[float, int, dict | str]:
    """POST one query; return ``(elapsed_s, status_code, body)``."""
    import httpx

    started = benchmark_clock()
    try:
        with _httpx_client_for_localhost(timeout_s=15.0) as client:
            r = client.post(
                f"http://{host}:{port}/api/query",
                json={"sql": sql, "warehouse_dir": str(warehouse), "limit": limit},
            )
        elapsed = benchmark_clock() - started
        try:
            body: dict | str = r.json()
        except (ValueError, TypeError):
            body = r.text[:200]
        return elapsed, r.status_code, body
    except httpx.HTTPError as exc:
        elapsed = benchmark_clock() - started
        return elapsed, 0, f"{type(exc).__name__}: {exc!s}"[:200]


def _check_workbench_extras_installed() -> tuple[bool, str]:
    """Return (installed, missing_module_name)."""
    for mod in ("fastapi", "uvicorn"):
        try:
            __import__(mod)
        except ImportError:
            return False, mod
    return True, ""


def _build_query_set(asset_key: str) -> list[tuple[str, str]]:
    """Return ``[(label, sql), ...]`` for the three benchmark queries."""
    return [
        ("Q1: SELECT 1 (pure framework overhead)", "SELECT 1 AS x"),
        (
            f"Q2: COUNT(*) FROM {asset_key} (single scan)",
            f"SELECT COUNT(*) AS n FROM {{{{ ref('{asset_key}') }}}}",
        ),
        (
            f"Q3: GROUP BY over {asset_key} (aggregate)",
            (
                "SELECT name, SUM(amount) AS total "
                f"FROM {{{{ ref('{asset_key}') }}}} "
                "GROUP BY name ORDER BY name LIMIT 10"
            ),
        ),
    ]


def _row_for_query(label: str, samples: list[float]) -> BenchRow:
    s = stats_summary(samples)
    median = float(s["median"])
    verdict = classify(median, INFORMATIONAL_QUERY_BUDGET_S)
    severity = "" if verdict == PASS else severity_for(median, INFORMATIONAL_QUERY_BUDGET_S)
    return BenchRow(
        metric=f"{label} (median)",
        claim_ref="user expectation (informational)",
        claim=f"<{fmt_seconds(INFORMATIONAL_QUERY_BUDGET_S)}",
        measured=fmt_seconds(median),
        verdict=verdict,
        delta=(
            f"min={fmt_seconds(float(s['min']))} "
            f"P95={fmt_seconds(float(s['p95']))} "
            f"P99={fmt_seconds(float(s['p99']))}"
        ),
        severity=severity,
        note=f"n={len(samples)}",
    )


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0912, PLR0915 — flat orchestration; per-skip-condition branches mirror the report sections one-to-one
    parser = argparse.ArgumentParser(description="Nucleus B8 — Workbench HTTP API latency.")
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS_PER_QUERY,
        help=f"Iterations per query (default {DEFAULT_RUNS_PER_QUERY}).",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=10_000,
        help="Rows in the seed Iceberg table (default 10,000; small to keep B8 fast).",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()

    rows: list[BenchRow] = []
    notes: list[str] = []
    raw: dict[str, object] = {}

    installed, missing = _check_workbench_extras_installed()
    if not installed:
        rows.append(
            BenchRow(
                metric="Workbench extras installed",
                claim_ref="prerequisite",
                claim="fastapi + uvicorn importable",
                measured=f"missing: {missing}",
                verdict=SKIP_DEPS,
                severity=LOW,
                note=(
                    "Workbench is an optional extra per ADR-039 install-size split. "
                    "Run `pip install -e .[workbench]` to enable."
                ),
            )
        )
        completed_at = now_iso()
        elapsed_total = benchmark_clock() - started
        result = BenchResult(
            name="B8: Workbench HTTP API latency",
            script="scripts/benchmarks/b8_workbench_api.py",
            command=(
                f"{sys.executable} -m scripts.benchmarks.b8_workbench_api "
                f"--runs {args.runs} --rows {args.rows}"
            ),
            started_at=started_at,
            completed_at=completed_at,
            elapsed_s=elapsed_total,
            overall_verdict=SKIP_DEPS,
            rows=rows,
            notes=notes,
            raw={"workbench_extras_installed": False},
        )
        out = write_result(result)
        print(f"[B8] wrote {out}")
        print("[B8] overall = SKIP-DEPS (workbench extras not installed)")
        return 0

    base_dir = Path(tempfile.mkdtemp(prefix="nucleus_bench_b8_"))
    warehouse = base_dir / "warehouse"
    warehouse.mkdir(parents=True, exist_ok=True)
    log_path = base_dir / "uvicorn.log"
    print(f"[B8] working dir: {base_dir}")

    # Seed the warehouse.
    print(f"[B8] seeding warehouse with {args.rows:,} rows ...")
    seed_started = benchmark_clock()
    try:
        asset_key = _seed_warehouse(warehouse, rows=args.rows)
    except Exception as exc:
        rows.append(
            BenchRow(
                metric="warehouse seed",
                claim_ref="prerequisite",
                claim="materialize bench.api_demo",
                measured=f"{type(exc).__name__}: {exc!s}"[:200],
                verdict=FAIL,
                severity=BLOCKER,
            )
        )
        shutil.rmtree(base_dir, ignore_errors=True)
        completed_at = now_iso()
        elapsed_total = benchmark_clock() - started
        result = BenchResult(
            name="B8: Workbench HTTP API latency",
            script="scripts/benchmarks/b8_workbench_api.py",
            command=f"{sys.executable} -m scripts.benchmarks.b8_workbench_api --runs {args.runs}",
            started_at=started_at,
            completed_at=completed_at,
            elapsed_s=elapsed_total,
            overall_verdict=FAIL,
            rows=rows,
            notes=notes,
            raw=raw,
        )
        write_result(result)
        return 1
    seed_elapsed = benchmark_clock() - seed_started
    notes.append(f"warehouse seeded in {fmt_seconds(seed_elapsed)} ({args.rows:,} rows).")

    # Spawn uvicorn.
    host = "127.0.0.1"
    port = _free_tcp_port()
    print(f"[B8] starting uvicorn at http://{host}:{port} (log: {log_path}) ...")
    spawn_started = benchmark_clock()
    proc = _spawn_uvicorn(host, port, log_path)
    server_ready = _wait_for_server(host, port, SERVER_READY_TIMEOUT_S)
    spawn_elapsed = benchmark_clock() - spawn_started

    if not server_ready:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_tail = ""
        try:
            log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-1000:]
        except OSError:
            pass
        rows.append(
            BenchRow(
                metric="uvicorn ready",
                claim_ref="prerequisite",
                claim=f"server reachable within {SERVER_READY_TIMEOUT_S:.0f}s",
                measured="never ready",
                verdict=SKIP_DEPS,
                severity=MEDIUM,
                note=f"log tail: {log_tail[-300:].strip()}",
            )
        )
        shutil.rmtree(base_dir, ignore_errors=True)
        completed_at = now_iso()
        elapsed_total = benchmark_clock() - started
        result = BenchResult(
            name="B8: Workbench HTTP API latency",
            script="scripts/benchmarks/b8_workbench_api.py",
            command=f"{sys.executable} -m scripts.benchmarks.b8_workbench_api --runs {args.runs}",
            started_at=started_at,
            completed_at=completed_at,
            elapsed_s=elapsed_total,
            overall_verdict=SKIP_DEPS,
            rows=rows,
            notes=notes,
            raw={"server_ready": False, "log_tail": log_tail[-1000:]},
        )
        write_result(result)
        return 0

    # Server is up — record spin-up time as informational.
    rows.append(
        BenchRow(
            metric="uvicorn spin-up wall",
            claim_ref="perf doc §2.6 (initial page load <2s)",
            claim="<2s",
            measured=fmt_seconds(spawn_elapsed),
            verdict=classify(spawn_elapsed, 2.0, lower_is_better=True),
            delta="",
            severity="" if spawn_elapsed <= 2.0 else severity_for(spawn_elapsed, 2.0),
            note="includes ASGI wiring + CORS middleware + static mount",
        )
    )

    try:
        # /api/health probe (warm). Use the proxy-bypass client so corporate
        # proxies that intercept localhost traffic don't poison the timing.
        print(f"[B8] /api/health probe (n={args.runs}) ...")
        health_samples: list[float] = []
        with _httpx_client_for_localhost(timeout_s=5.0) as health_client:
            for _ in range(args.runs):
                t0 = benchmark_clock()
                try:
                    r = health_client.get(f"http://{host}:{port}/api/health")
                    health_samples.append(benchmark_clock() - t0)
                    if r.status_code != 200:
                        notes.append(f"/api/health returned {r.status_code}")
                except Exception as exc:
                    notes.append(f"/api/health raised {type(exc).__name__}: {exc!s}")
        if health_samples:
            s = stats_summary(health_samples)
            verdict_h = classify(float(s["median"]), CLAIM_HEALTH_LATENCY_S)
            rows.append(
                BenchRow(
                    metric="/api/health (median)",
                    claim_ref="perf doc §2.6",
                    claim=f"<{fmt_seconds(CLAIM_HEALTH_LATENCY_S)}",
                    measured=fmt_seconds(float(s["median"])),
                    verdict=verdict_h,
                    delta=(
                        f"min={fmt_seconds(float(s['min']))} "
                        f"P95={fmt_seconds(float(s['p95']))} "
                        f"P99={fmt_seconds(float(s['p99']))}"
                    ),
                    severity=""
                    if verdict_h == PASS
                    else severity_for(float(s["median"]), CLAIM_HEALTH_LATENCY_S),
                    note=f"n={len(health_samples)}",
                )
            )

        # /api/query probes.
        for label, sql in _build_query_set(asset_key):
            print(f"[B8] {label} (n={args.runs}) ...")
            samples: list[float] = []
            for i in range(args.runs):
                wall, status, _body = _post_query(host, port, sql, warehouse)
                if status != 200:
                    # Surface the failure verbatim; do NOT retry per task spec.
                    notes.append(f"{label} run #{i + 1}: status={status} body={str(_body)[:160]}")
                else:
                    samples.append(wall)
            if samples:
                rows.append(_row_for_query(label, samples))
                raw[f"{label} samples"] = samples
            else:
                rows.append(
                    BenchRow(
                        metric=f"{label} (median)",
                        claim_ref="user expectation",
                        claim=f"<{fmt_seconds(INFORMATIONAL_QUERY_BUDGET_S)}",
                        measured="(no successful runs)",
                        verdict=FAIL,
                        severity=BLOCKER,
                        note="all calls returned non-200; see notes",
                    )
                )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    overall = PASS
    if any(r.verdict == FAIL for r in rows):
        overall = FAIL
    elif any(r.verdict == SKIP_DEPS for r in rows):
        overall = SKIP_DEPS

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B8: Workbench HTTP API latency",
        script="scripts/benchmarks/b8_workbench_api.py",
        command=(
            f"{sys.executable} -m scripts.benchmarks.b8_workbench_api "
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
    print(f"[B8] wrote {out}")
    print(f"[B8] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    shutil.rmtree(base_dir, ignore_errors=True)
    return 0 if overall in (PASS, SKIP_DEPS) else 1


# Suppress unused import warning.
_ = textwrap


if __name__ == "__main__":
    raise SystemExit(main())
