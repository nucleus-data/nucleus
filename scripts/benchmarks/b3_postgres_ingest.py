"""B3 — Postgres ingest scale benchmark.

Verifies the perf doc §2.4 claims for the ``ctx.copy_from(postgres://...)``
helper (which wraps dlt + pyiceberg per ADR-014):

    1M  rows, full_refresh : <5 min  wall-clock
    10M rows, full_refresh : <30 min wall-clock

The script:

1. Spawns a one-shot ``postgres:16-alpine`` container via ``docker run``.
   Trust-auth + ephemeral data volume; container is stopped + removed on
   exit (atexit + try/finally).
2. Connects via ``psycopg`` (pinned 3.2.3) and seeds a synthetic table
   with the requested row count using ``COPY FROM STDIN`` (much faster
   than per-row ``INSERT``).
3. Calls ``ctx.copy_from('postgresql://...', table=..., target=...)``
   with ``write_disposition='replace'`` (== full_refresh) and a fresh
   filesystem warehouse.
4. Captures wall-clock + peak Python RSS via :class:`RSSWatcher`.
5. Records SKIP-DEPS when Docker is unavailable, when image pull fails,
   or when the container does not become ready within the timeout.

Verification rules:
    * Row count returned by ``ctx.copy_from`` must match the seeded count.
    * No ``NucleusError`` raised (ingest path completed successfully).

Docs:
    psycopg 3.2.3 — https://www.psycopg.org/psycopg3/docs/api/copy.html
    Postgres COPY — https://www.postgresql.org/docs/16/sql-copy.html
    dlt sql_database — https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
    Perf claims — docs/internal/research/performance_reliability_targets.md §2.4
"""

from __future__ import annotations

import argparse
import atexit
import gc
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    HIGH,
    LOW,
    MEDIUM,
    PASS,
    SKIP_DEPS,
    BenchResult,
    BenchRow,
    RSSWatcher,
    benchmark_clock,
    classify,
    docker_available,
    fmt_bytes,
    fmt_delta,
    fmt_seconds,
    now_iso,
    severity_for,
    write_result,
)

DEFAULT_IMAGE: str = "postgres:16-alpine"
CONTAINER_NAME_PREFIX: str = "nucleus_bench_b3_"
PG_USER: str = "bench"
PG_PASSWORD: str = "bench"  # noqa: S105 — local Docker container, never accepts external traffic
PG_DB: str = "bench"
PG_READY_TIMEOUT_S: float = 60.0
DOCKER_PULL_TIMEOUT_S: float = 180.0

# Scale presets — rows × ~80 bytes/row in Postgres ≈ on-disk size.
_SCALES: dict[str, dict[str, object]] = {
    "1m": {
        "rows": 1_000_000,
        "label": "Postgres 1M rows full_refresh",
        "claim_wall_s": 300.0,  # 5 minutes per perf doc §2.4
        "claim_peak_rss_bytes": 4 * 1024**3,  # generous; perf doc §3 doesn't tag this row
    },
    "10m": {
        "rows": 10_000_000,
        "label": "Postgres 10M rows full_refresh",
        "claim_wall_s": 1800.0,  # 30 minutes per perf doc §2.4
        "claim_peak_rss_bytes": 6 * 1024**3,
    },
}


def _free_tcp_port() -> int:
    """Return a currently-unused TCP port for the Postgres container."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _docker_pull(image: str) -> tuple[bool, str]:
    """Pull *image* if not already cached. Returns (ok, message)."""
    print(f"[B3] docker pull {image} ...")
    started = benchmark_clock()
    try:
        proc = subprocess.run(
            ["docker", "pull", image],
            capture_output=True,
            text=True,
            check=False,
            timeout=DOCKER_PULL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return False, f"docker pull timed out after {DOCKER_PULL_TIMEOUT_S}s"
    elapsed = benchmark_clock() - started
    if proc.returncode != 0:
        return False, f"docker pull rc={proc.returncode}: {proc.stderr.strip()[:200]}"
    return True, f"image ready in {elapsed:.1f}s"


def _start_pg_container(image: str, port: int) -> tuple[str, str]:
    """Start a postgres container; return (container_name, error_msg).

    On success error_msg is empty. The container is registered for cleanup
    via :py:func:`atexit.register`.
    """
    name = CONTAINER_NAME_PREFIX + uuid.uuid4().hex[:8]
    cmd = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "-p",
        f"{port}:5432",
        "-e",
        f"POSTGRES_USER={PG_USER}",
        "-e",
        f"POSTGRES_PASSWORD={PG_PASSWORD}",
        "-e",
        f"POSTGRES_DB={PG_DB}",
        image,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    if proc.returncode != 0:
        return name, f"docker run rc={proc.returncode}: {proc.stderr.strip()[:200]}"
    atexit.register(_kill_container, name)
    return name, ""


def _kill_container(name: str) -> None:
    """Best-effort container teardown; never raises."""
    try:
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def _wait_for_pg_ready(port: int, timeout_s: float) -> bool:
    """Poll ``pg_isready``-equivalent: open TCP + try a SELECT 1."""
    import psycopg  # Docs: https://www.psycopg.org/psycopg3/docs/api/

    deadline = time.monotonic() + timeout_s
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(
                f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{port}/{PG_DB}",
                connect_timeout=2,
            ) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as exc:  # noqa: BLE001 — keep polling until deadline
            last_exc = exc
            time.sleep(0.3)
    print(
        f"[B3] pg never ready: {type(last_exc).__name__ if last_exc else 'unknown'}: "
        f"{str(last_exc)[:120] if last_exc else ''}"
    )
    return False


def _seed_postgres(conn_str: str, rows: int) -> tuple[float, str]:
    """Create a synthetic table and bulk-load *rows* rows via ``COPY FROM STDIN``.

    Returns ``(elapsed_seconds, table_name)``. Uses a 10-column schema mirroring
    B2's synthetic Parquet so cross-benchmark comparisons stay apples-to-apples.

    Docs: https://www.psycopg.org/psycopg3/docs/api/copy.html
    """
    import psycopg

    table_name = "bench_synth"
    started = benchmark_clock()
    with psycopg.connect(conn_str, autocommit=True) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute(f"""
            CREATE UNLOGGED TABLE {table_name} (
                id        BIGINT      NOT NULL PRIMARY KEY,
                value     DOUBLE PRECISION,
                name      TEXT,
                ts        TIMESTAMP,
                bucket    INTEGER,
                grp       TEXT,
                amount    DOUBLE PRECISION,
                count_col INTEGER,
                flag      BOOLEAN,
                descr     TEXT
            )
        """)

        with conn.cursor() as cur:
            with cur.copy(f"COPY {table_name} FROM STDIN WITH (FORMAT TEXT)") as copy:
                # 10k rows per CSV chunk to limit Python overhead.
                names = [f"name_{i % 1000}" for i in range(min(rows, 10_000))]
                groups = [f"group_{i % 50}" for i in range(min(rows, 10_000))]
                descrs = [f"descr_{i % 10000}" for i in range(min(rows, 10_000))]
                base_ts = "2026-01-01 00:00:00"
                for i in range(rows):
                    name = names[i % len(names)]
                    grp = groups[i % len(groups)]
                    descr = descrs[i % len(descrs)]
                    flag = "t" if i % 2 == 0 else "f"
                    line = (
                        f"{i}\t{i * 1.234567:.6f}\t{name}\t{base_ts}\t"
                        f"{i % 100}\t{grp}\t{(i * 7 % 100000) / 100.0:.3f}\t"
                        f"{i % 100}\t{flag}\t{descr}\n"
                    )
                    copy.write(line)
    elapsed = benchmark_clock() - started
    return elapsed, table_name


def _do_ingest_one(
    scale_key: str,
    *,
    image: str,
    base_dir: Path,
) -> tuple[list[BenchRow], dict[str, object], list[str]]:
    """Run a single scale's ingest. Returns (rows, raw, notes)."""
    notes: list[str] = []
    rows_out: list[BenchRow] = []
    scale = _SCALES[scale_key]
    n_rows = int(scale["rows"])  # type: ignore[arg-type]
    label = str(scale["label"])

    port = _free_tcp_port()
    print(f"[B3] starting {image} on port {port} ...")
    container, err = _start_pg_container(image, port)
    if err:
        notes.append(err)
        rows_out.append(
            BenchRow(
                metric=label,
                claim_ref="perf doc §2.4",
                claim=f"<{fmt_seconds(float(scale['claim_wall_s']))}",  # type: ignore[arg-type]
                measured="(skipped)",
                verdict=SKIP_DEPS,
                severity=MEDIUM,
                note=err,
            )
        )
        return rows_out, {}, notes

    if not _wait_for_pg_ready(port, PG_READY_TIMEOUT_S):
        notes.append(f"Postgres ({image}) never became ready within {PG_READY_TIMEOUT_S}s.")
        rows_out.append(
            BenchRow(
                metric=label,
                claim_ref="perf doc §2.4",
                claim=f"<{fmt_seconds(float(scale['claim_wall_s']))}",  # type: ignore[arg-type]
                measured="(skipped)",
                verdict=SKIP_DEPS,
                severity=MEDIUM,
                note="pg never ready",
            )
        )
        _kill_container(container)
        return rows_out, {}, notes

    conn_str = f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{port}/{PG_DB}"
    print(f"[B3] seeding {n_rows:,} rows ...")
    seed_elapsed, table_name = _seed_postgres(conn_str, n_rows)
    print(f"[B3]   seeded in {fmt_seconds(seed_elapsed)}")
    notes.append(f"Postgres seed ({label}): {fmt_seconds(seed_elapsed)} for {n_rows:,} rows.")

    warehouse = base_dir / f"warehouse_{scale_key}"
    warehouse.mkdir(parents=True, exist_ok=True)

    # Lazy import to keep the script importable even when nucleus isn't installed.
    import nucleus.ctx as ctx  # noqa: PLC0415

    print(f"[B3] ingest via ctx.copy_from -> {warehouse}")
    watcher = RSSWatcher(interval_s=0.05).start()
    started = benchmark_clock()
    err_str: str | None = None
    row_count: int | None = None
    try:
        row_count = ctx.copy_from(
            conn_str,
            table=f"public.{table_name}",
            target=f"raw.{table_name}",
            warehouse_dir=warehouse,
            write_disposition="replace",
        )
    except Exception as exc:  # noqa: BLE001 — surface as FAIL row
        err_str = f"{type(exc).__name__}: {exc!s}"
        print(f"[B3] ingest raised: {err_str[:200]}")
    finally:
        peak_bytes = watcher.stop()
        wall_s = benchmark_clock() - started

    gc.collect()
    _kill_container(container)

    if err_str is not None:
        rows_out.append(
            BenchRow(
                metric=f"{label} — wall-clock",
                claim_ref="perf doc §2.4",
                claim=f"<{fmt_seconds(float(scale['claim_wall_s']))}",  # type: ignore[arg-type]
                measured="(error)",
                verdict=FAIL,
                severity=BLOCKER,
                note=err_str[:200],
            )
        )
        return rows_out, {"error": err_str, "wall_s": wall_s}, notes

    claim_wall = float(scale["claim_wall_s"])  # type: ignore[arg-type]
    claim_rss = float(scale["claim_peak_rss_bytes"])  # type: ignore[arg-type]
    wall_verdict = classify(wall_s, claim_wall)
    rss_verdict = classify(float(peak_bytes), claim_rss)

    rows_out.append(
        BenchRow(
            metric=f"{label} — wall-clock",
            claim_ref="perf doc §2.4",
            claim=f"<{fmt_seconds(claim_wall)}",
            measured=fmt_seconds(wall_s),
            verdict=wall_verdict,
            delta=fmt_delta(wall_s, claim_wall),
            severity="" if wall_verdict == PASS else severity_for(wall_s, claim_wall),
        )
    )
    rows_out.append(
        BenchRow(
            metric=f"{label} — peak RSS",
            claim_ref="perf doc §3 (informational)",
            claim=f"<{fmt_bytes(claim_rss)}",
            measured=fmt_bytes(float(peak_bytes)),
            verdict=rss_verdict,
            delta=fmt_delta(float(peak_bytes), claim_rss),
            severity="" if rss_verdict == PASS else severity_for(float(peak_bytes), claim_rss),
        )
    )
    rows_out.append(
        BenchRow(
            metric=f"{label} — row count",
            claim_ref="seed contract",
            claim=f"{n_rows:,}",
            measured=f"{row_count:,}" if row_count is not None else "(none)",
            verdict=PASS if row_count == n_rows else FAIL,
            delta="0" if row_count == n_rows else (f"+{(row_count or 0) - n_rows}"),
            severity="" if row_count == n_rows else BLOCKER,
            note="row-count mismatch is correctness, not perf",
        )
    )

    raw = {
        "scale_key": scale_key,
        "rows_seeded": n_rows,
        "rows_returned": row_count,
        "seed_s": seed_elapsed,
        "ingest_wall_s": wall_s,
        "ingest_peak_rss_bytes": peak_bytes,
        "container": container,
        "image": image,
        "port": port,
    }
    return rows_out, raw, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nucleus B3 — Postgres ingest scale benchmark.")
    parser.add_argument(
        "--scale",
        choices=["1m", "10m", "all"],
        default="1m",
        help="Which scale(s) to run. 1m = 1,000,000 rows; 10m = 10,000,000 rows; "
        "all = both. Default: 1m.",
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help=f"Postgres Docker image (default: {DEFAULT_IMAGE}).",
    )
    args = parser.parse_args(argv)

    started_at = now_iso()
    started = benchmark_clock()

    rows: list[BenchRow] = []
    notes: list[str] = []
    raw: dict[str, object] = {}
    overall = PASS

    if not docker_available():
        notes.append("docker CLI not found or not responsive — B3 cannot run.")
        rows.append(
            BenchRow(
                metric="Postgres ingest (1m + 10m)",
                claim_ref="perf doc §2.4",
                claim="docker required",
                measured="(skipped)",
                verdict=SKIP_DEPS,
                severity=LOW,
                note="docker --version returned non-zero; install Docker Desktop or skip B3.",
            )
        )
        overall = SKIP_DEPS
    else:
        ok_pull, msg = _docker_pull(args.image)
        notes.append(f"docker pull: {msg}")
        if not ok_pull:
            rows.append(
                BenchRow(
                    metric="docker pull postgres",
                    claim_ref="prerequisite",
                    claim="image cached",
                    measured="failed",
                    verdict=SKIP_DEPS,
                    severity=MEDIUM,
                    note=msg,
                )
            )
            overall = SKIP_DEPS
        else:
            base_dir = Path(tempfile.mkdtemp(prefix="nucleus_bench_b3_"))
            print(f"[B3] working dir: {base_dir}")
            scales_to_run = ["1m", "10m"] if args.scale == "all" else [args.scale]
            for sk in scales_to_run:
                scale_rows, scale_raw, scale_notes = _do_ingest_one(
                    sk, image=args.image, base_dir=base_dir
                )
                rows.extend(scale_rows)
                notes.extend(scale_notes)
                if scale_raw:
                    raw[f"scale_{sk}"] = scale_raw
            shutil.rmtree(base_dir, ignore_errors=True)

            if any(r.verdict == FAIL for r in rows):
                overall = FAIL
            elif any(r.verdict == SKIP_DEPS for r in rows) and overall != FAIL:
                overall = SKIP_DEPS
            elif overall != FAIL:
                overall = PASS

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="B3: Postgres ingest scale",
        script="scripts/internal/benchmarks/b3_postgres_ingest.py",
        command=f"{sys.executable} -m scripts.benchmarks.b3_postgres_ingest --scale {args.scale}",
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
    print(f"[B3] wrote {out}")
    print(f"[B3] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    return 0 if overall in (PASS, SKIP_DEPS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
