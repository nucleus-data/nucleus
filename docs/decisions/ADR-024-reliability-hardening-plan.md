# ADR-024: Reliability hardening plan (v0.2 P0 items)

Status: PROPOSED
Date: 2026-05-15
Author: builder (v0.2.0 reconciliation pass)
Sources: `docs/research/performance_reliability_targets.md` §6 (ACID gaps), §7 (reliability patterns), §8 (chaos scenarios); `docs/audit/2026-05-15_mass_audit_findings.md` (Wave 1E)

## Context

Nucleus v0.1.0 passes 8/8 beachhead E2E gates on WSL/Linux. However, five reliability gaps were identified by the Wave-1E mass audit and confirmed by the Wave-1H research into ACID semantics and chaos scenarios:

1. **DuckDB OOM**: `GROUP BY` hash tables cannot spill to disk (verified: https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors). Without `SET memory_limit`, a large aggregation silently kills the DuckDB process and surfaces as an opaque `NE5001` internal error.

2. **Concurrent run race**: Two `nucleus run` invocations against the same asset race on Iceberg snapshot commit. One writer's Parquet files survive but the metadata swap overwrites the other — silent data loss. Chaos scenario J6.

3. **Orphaned Parquet files**: If a process is killed (kill -9, disk-full) after writing Parquet but before committing metadata, orphan files accumulate silently. Chaos scenario J2.

4. **Windows `os.rename` atomicity**: NTFS rename is NOT atomic (unlike POSIX `rename(2)`). The filesystem catalog's metadata swap uses `Path.rename()`, which may leave a partial state on Windows. NEEDS VERIFICATION 11.2 (verified empirically on Windows 11 x64 2026-05-15: `Path.rename()` on NTFS is a single MFT operation but NOT atomic across a crash — different from POSIX).

5. **Error-budget / per-operation timeouts**: No defined timeout for Dagster `execute_in_process`. A hung asset hangs the entire `nucleus run` indefinitely without a `NE5001` timeout signal.

The five items above are P0 for v0.2 because PoC #5 external testers will encounter them on real Postgres sources and S3/MinIO objects stores under realistic conditions.

Three additional hardening items (circuit-breaker retry policies, `nucleus health` CLI command, and the full Chaos J3-J8 suite) are P1 for v0.3 when Docker CI infra is available.

## Decision

Implement the five P0 items in v0.2:

### P0-1: DuckDB memory_limit at AMA init

In `src/nucleus/coordination/asset_materialization.py`, set `duckdb.connect().execute("SET memory_limit='10GB'")` (or 70% of `psutil.virtual_memory().total`) at the start of every materialisation. Prevents silent OOM.

Reference: https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html

### P0-2: Advisory filesystem lock for concurrent runs

In `src/nucleus/coordination/asset_materialization.py`, acquire a `FileLock` (stdlib `msvcrt.locking` on Windows, `fcntl.flock` on POSIX — or `filelock==3.16.1` cross-platform wrapper already in `pyproject.toml` optional deps) on `<warehouse>/<asset_key>/.nucleus-run.lock` before calling Dagster `execute_in_process`. A second `nucleus run` on the same asset either:
- (v0.2 simple): waits up to 300 s then raises `NE5002 "Run already in progress for asset X"`.
- (v0.3 full): returns a `run_id` pointing to the in-flight run.

v0.2 ships the simple path; v0.3 graduates to the monitoring-aware path.

### P0-3: `expire_snapshots` hook after successful commit

After every successful Iceberg snapshot commit in the AMA, call `table.expire_snapshots(older_than_ms=7*24*60*60*1000).commit()` to keep at most 7 days of snapshots and clean up orphaned Parquet files from aborted previous runs. Prevents unbounded disk growth.

Reference: https://py.iceberg.apache.org/api/ (pyiceberg==0.8.1; verify `ExpireSnapshots` API name against pinned version before implementation per AGENTS.md §11.12).

### P0-4: Windows rename atomicity verification + documentation

Add a test `tests/coordination/test_windows_rename_atomicity.py` that:
- Verifies `pathlib.Path.rename()` on the current platform is either atomic (POSIX) or documented as non-atomic (Windows NTFS).
- Emits a `logging.WARNING` on Windows indicating the atomicity caveat.

Add the Windows caveat to `docs/compatibility.md` and `SETUP.md` "Platform notes" section. Do NOT attempt to "fix" NTFS atomicity in v0.2 (would require a custom write-ahead log, violating the anti-over-engineering directive). Document the safe workaround: store filesystem catalog on WSL2 ext4 volume instead of NTFS root.

### P0-5: Error-budget timeout for Dagster execution

In `src/nucleus/coordination/asset_materialization.py`, wrap `execute_in_process(...)` with a 10-minute (600 s) wall-clock timeout using `concurrent.futures.ThreadPoolExecutor`. On timeout, raise `NucleusInternalError(error_code="NE5001", user_message="Asset materialization timed out after 600 s", fix_hint="Check logs for a hung database query; set a shorter DuckDB timeout via NUCLEUS_QUERY_TIMEOUT_S env var.")`.

## OSS Options Considered

| Concern | Decision | Alternative rejected |
|---|---|---|
| Advisory lock | `filelock==3.16.1` (already optional in pyproject) | Custom `fcntl` + `msvcrt` — Windows portability, no gain |
| DuckDB memory_limit detection | `psutil==6.1.1` (already in dev deps) OR hardcode 10 GB default | `resource.getrlimit` — Unix-only |
| Snapshot expiry | `pyiceberg` native `table.expire_snapshots()` | Custom manifest walk — "Build not wrap" violation |
| Timeout | `concurrent.futures.ThreadPoolExecutor` (stdlib) | `signal.alarm` — Unix-only; asyncio — adds dep |

## Consequences

**Positive:**

- Closes five gaps that would cause data corruption or silent hangs in PoC #5 field test.
- `NE5002` and the lock path are ~200 LOC each; comfortably inside per-feature 500 LOC ceiling.
- `expire_snapshots` hook keeps warehouse disk usage predictable.
- Windows caveat documented before any Windows-first tester hits it.

**Negative / Open:**

- `filelock` promoted from optional to required dep (adds ~30 KB to install). Needs `pyproject.toml` edit + `docs/compatibility.md` row.
- `expire_snapshots` API name NEEDS VERIFICATION against `pyiceberg==0.8.1` before implementation (Research doc NEEDS VERIFICATION 11.3).
- Chaos J3-J8 full automation deferred to v0.3 (needs Docker CI infra; Chaos J1 + J2 are runnable immediately per `scripts/run_chaos.py`).

## Chaos Test Coverage

| Scenario | v0.2 coverage | v0.3 plan |
|---|---|---|
| J1 — Disk full mid-write | Manual (`scripts/run_chaos.py --scenario J1`) | Automated Docker |
| J2 — kill -9 mid-commit | Manual (`scripts/run_chaos.py --scenario J2`) | Automated Docker |
| J3 — SeaweedFS down | Deferred (needs Docker compose in CI) | Automated |
| J4 — Postgres drop mid-ingest | Deferred | Automated |
| J5 — Schema drift (add column) | Covered by `test_schema_evolution.py` unit tests | Automated integration |
| J6 — Concurrent run race | **Closed by P0-2** (advisory lock) | Load test |
| J7 — Clock skew | Documentation only | Monitoring alert |
| J8 — Catalog metadata corrupt | Covered by `NE4001` error translation | Automated |

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §6.2 (AMA step 3 — commit + lineage)
- `nucleus_architecture_v4.1.md` §6.4 (Error Translation Layer — NE5001/5002)
- `nucleus_architecture_v4.1.md` §9.3 (Composability — pyiceberg swap interface)
- `AGENTS.md` §11.7 (Error translation discipline)

## Rollback

Each P0 item is independently revertable. P0-1/3/4: remove the 1-5 line AMA additions. P0-2: remove the lock acquisition + `filelock` dep. P0-5: unwrap the `ThreadPoolExecutor` timeout.
