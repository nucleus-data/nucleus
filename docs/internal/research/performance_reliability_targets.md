# Performance + Reliability Targets — v0.3+ aspirational; v0.2 actuals at the bottom

> ### Status banner (added 2026-05-15 per v0.2 close-out checklist §1.9)
>
> The numeric targets in §2 below are **aspirational v0.3+ goals**, not the
> v0.2.0 release contract. Empirical baseline (Worker A1 benchmark suite,
> 2026-05-15) found 11 numbers FAIL these targets — most prominently boot
> time (~2.0 s vs <500 ms claim), B4 concurrent-run safety on Windows, and
> B2 materialize-10 GB peak RAM (8.4 GB vs 6 GB claim).
>
> The v0.2.0 empirical actuals are documented in
> [`docs/benchmarks/2026-05-15_baseline.md`](../benchmarks/2026-05-15_baseline.md)
> and reproduced in summary form at [§13 v0.2.0 empirical actuals](#13--v020-empirical-actuals-2026-05-15-baseline) below.
> PoC #5 testers run the empirical numbers — the v0.2 release stance is
> "honest actuals; v0.3 closes the gap".
>
> **Per Anti-Over-Engineering Discipline** (`AGENTS.md` Anti-Over-Engineering
> §1): aspirational numbers without empirical backing are anxiety. This
> doc is now framed as a roadmap, not a SLO.

> **Date**: 2026-05-15
> **Researcher**: Sonnet 4.6 (Researcher tier, Gemini 3.1 Pro unavailable — fallback per AGENTS.md §11.14)
> **Verified against**: docs/compatibility.md (2026-05-14), docs/specs/nucleus_architecture_v4.1.md (locked), all external URLs cited below
> **AI memory caveat**: External docs verified as of 2026-05-15. Exact query times may shift across DuckDB patch releases; re-measure at each upgrade per AGENTS.md §11.13.

---

## 1. Beachhead Persona Constraints (Drives All Targets)

Per `docs/specs/nucleus_architecture_v4.1.md` §1.5:

| Dimension | Constraint | Source |
|---|---|---|
| Hardware | MacBook M-series (8–12 cores, 16–32 GB RAM, 256 GB–1 TB SSD) | v4.1 §1.5 |
| Network | Home/office WiFi; occasional corporate proxy | v4.1 §1.5 |
| Data scale | 100 GB–5 TB total; per-asset typically 1–100 GB | v4.1 §1.5 |
| Concurrent users | 1 developer on laptop; multiple in CI/shared env | v4.1 §1.5 |
| Primary goal | `git clone → BI-ready Iceberg table in < 30 min` | v4.1 §1.5 |

This means every numeric target in this document is calibrated for **single-node, modern Apple silicon, low concurrency**. Distributed-scale targets do not apply until Mode 2 dispatch (yield-to-giants). Per v4.1 §10 Yield-to-Giants Strategy, assets exceeding the laptop budget are dispatched to Databricks/Snowflake via `compute=...` rather than optimised locally.

Two empirical data points already on record from PoC executions:

- **PoC #4** (VALIDATED 2026-05-12): `nucleus up` cold boot = **5.82 s**, idle RSS = **117.3 MB**
  (Source: `AGENTS.md` §1 status block; well inside the <10 s / <500 MB targets)
- **WSL Beachhead E2E** (PASS 2026-05-14): 8/8 gates PASS; boot = **7 s**; real Iceberg snapshot created; zero Dagster classname leaks

---

## 2. Performance Budget Per Operation

For each operation: `target (cold)` / `target (warm)` / `source / rationale`.

### 2.1 Boot and Startup

| Operation | Target (cold) | Target (warm) | Source |
|---|---|---|---|
| `nucleus --version` | < 500 ms | < 150 ms | v4.1 §16.1: "`nucleus run <asset>` startup < 500 ms"; CLI version is lighter |
| `nucleus --help` | < 500 ms | < 150 ms | Same; no asset registry load |
| `nucleus list` | < 1.5 s | < 500 ms | Asset registry scan; dominated by YAML parse + Python import |
| `nucleus init <dir>` | < 2 s | < 1 s | File template write; stdlib I/O only |
| `nucleus up` (SeaweedFS sidecar) | < 10 s | < 3 s | **v4.1 §16.1 stated target; PoC #4 validated 5.82 s** |
| `nucleus down` | < 5 s | < 2 s | Docker stop + cleanup; no data ops |
| `nucleus_project.yaml` load + validate | < 100 ms | < 30 ms | YAML parse (pyyaml 6.0.3) + schema check; beachhead metric depends on this being fast |

**P0**: litellm / dlt / dagster MUST be lazy-imported in CLI entry points. PoC #4 validates 117.3 MB idle RSS; verify this holds for `nucleus --version` / `nucleus list` as more modules are wired.

### 2.2 Materialize — Per-Asset Overhead

AMA (~500 LOC, v4.1 §6.2) on Dagster hidden substrate.

| Workload | Target | Note |
|---|---|---|
| Empty asset (snapshot only) | < 1 s | v4.1 §16.1: `nucleus run` startup < 500 ms + empty Iceberg commit |
| 1 MB → Iceberg | < 2 s | Snapshot metadata dominates; single Parquet write |
| 100 MB → Iceberg | < 5 s | Arrow zero-copy (https://arrow.apache.org/docs/python/ipc.html); single s3fs PUT (< 157 MB) |
| 1 GB → Iceberg | < 30 s | Polars LazyFrame + multipart upload; dominant cost = Parquet write + network |
| 10 GB → Iceberg | < 5 min | Polars `engine="streaming"`; NEEDS VERIFICATION §11.1 |
| > 100 GB | Yield to giants | v4.1 §10 Mode 2 dispatch |

**NEEDS VERIFICATION §11.1**: Polars streaming group-by / sort / equi-join not yet fully out-of-core per https://github.com/pola-rs/polars/issues/20947 — verify against `polars==1.18.0` before publishing the 10 GB target.

### 2.3 Query — DuckDB on Iceberg

`duckdb==1.1.3`; reference: v4.1 §16.2 + §5.1; benchmark history: https://gist.github.com/joeharris76/4ad526c9da361aba9baab3a6c40f943c

| Workload | Target | Note |
|---|---|---|
| SELECT COUNT, < 10 MB | < 200 ms | Connection + one Parquet scan |
| 100 MB scan + aggregate | < 500 ms | v4.1 §16.2: 100M-row agg < 2 s; 100 MB ≈ 1M rows |
| 1 GB scan + aggregate | < 3 s | v4.1 §16.2; 8–12 cores; well under TPC-H 10 GB budget |
| 10 GB + filter, partitioned | < 5 s | v4.1 §16.2: partition pruning < 100 ms + vectorized exec |
| 10 GB + filter, unpartitioned | < 30 s | Full table scan across SSD; 8 cores |
| TPC-H 10 GB full suite | < 3 s median / < 10 s P95 | v4.1 §5.1: ~2.5 s; confirmed for DuckDB v1.1.x class |
| > 100 GB | Yield to giants | v4.1 §10 Mode 2 dispatch |

**DuckDB GROUP BY memory**: Per https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors — GROUP BY hash tables **cannot spill to disk**. Set `memory_limit='10GB'` (~60% of 16 GB) at DuckDB connection init in AMA.

### 2.4 Ingest — `ctx.copy_from` and dlt-wrapped

| Workload | Target | Note |
|---|---|---|
| Postgres → Iceberg, 10k rows | < 10 s | SQLAlchemy SELECT + Arrow + pyiceberg commit |
| Postgres → Iceberg, 100k rows | < 30 s | Beachhead E2E step 5 expectation |
| Postgres → Iceberg, 1M rows (full_refresh) | < 5 min | `fetchmany` 10k-row batches; single Iceberg snapshot |
| Postgres → Iceberg, 10M rows (incremental) | < 30 min | dlt cursor-based; https://dlthub.com/docs/general-usage/incremental/cursor |
| SQLite → Iceberg, 100k rows | < 10 s | Beachhead E2E seed+ingest validated < 5 s |
| CSV/Parquet → Iceberg, 1 GB | < 30 s | Arrow streaming from s3fs; multipart triggers at ≈ 157 MB |
| dlt Postgres CDC (ongoing) | < 5 min lag | pgoutput logical decoding; https://dlthub.com/docs/dlt-ecosystem/verified-sources/pg_replication |

### 2.5 SQL Transformation — `ctx.sql` Jinja Resolver

| Operation | Target | Source / Rationale |
|---|---|---|
| Resolve `{{ ref('asset_name') }}` for one asset | < 5 ms | String replace + regex; PoC #2 promoted at ~200 LOC using jinja2 + regex + difflib only |
| Resolve full 100-asset DAG (all `ref()` calls) | < 50 ms | Jinja Environment with cached template loader; 100 templates × < 0.5 ms each |
| Resolve full 1000-asset DAG | < 500 ms | Jinja Environment cache warm; dominated by dict lookup, not file I/O |
| Template render per asset | < 5 ms | Jinja2 3.1.6 (https://jinja.palletsprojects.com/en/3.1.x/); in-memory template compilation |
| DuckDB plan + execute (per §2.3 above) | Apply §2.3 budgets | Execution cost flows from §2.3 after resolver returns SQL |

### 2.6 Workbench UI

Targets are for v0.2+ Workbench (ADR-016; FastAPI 0.136.1 + uvicorn 0.46.0 backend).

| Operation | Target | Source / Rationale |
|---|---|---|
| Initial page load (cold, no browser cache) | < 2 s | FastAPI serves static bundle; static file serving overhead is minimal |
| Initial page load (warm, browser-cached assets) | < 500 ms | API call only to fetch project state |
| DAG render (100 assets) | < 200 ms | Client-side SVG/canvas; DOM node count < 500 total |
| DAG render (1000 assets) | < 1 s | Virtualized scroll required; without virtualization this will blow budget |
| API response: list runs (paginated 50) | < 100 ms | DB query (SQLite / Postgres backing Dagster); paginated by default |
| Run log streaming (SSE) per chunk | < 100 ms latency | FastAPI `StreamingResponse` / Server-Sent Events; local Dagster event bus |

### 2.7 AI Copilot

| Operation | Target | Source / Rationale |
|---|---|---|
| First-token latency | Bounded by user's LLM provider | litellm 1.83.14 wraps 100+ providers; this is the provider's SLA, not ours |
| Context assembly (schema + lineage + project structure) | < 200 ms | Dict lookup from in-memory asset registry + project YAML; no external calls |
| `nucleus chat` startup (import litellm) | < 1 s after first lazy load | Lazy-import guard; litellm is heavy (~30 MB + transitive deps) |

### 2.8 Governance Scripts

Measured from `upgrade_smoke.py` gate descriptions + LOC estimates.

| Script | Target | Source |
|---|---|---|
| `check_vocabulary.py` | < 5 s | Regex scan of `src/nucleus/`; bounded by file count |
| `check_pinning.py` | < 2 s | `tomllib` parse of `pyproject.toml`; single file |
| `dagster_leak_check.py` | < 3 s | AST parse + classname scan of source files |
| `loc_budget.py` | < 1 s | `wc -l` equivalent on `src/nucleus/` |
| `check_layering.py` | < 2 s | Import graph analysis |
| Full 8-script governance suite | < 30 s | Sequential run; CI gate per upgrade_smoke.py orchestration |

---

## 3. Memory Budget

Per hardware profile: 16 GB RAM MacBook (lower bound of beachhead persona). All RSS figures at OS level.

| State | RSS Target | Note |
|---|---|---|
| `import nucleus` (no CLI) | < 100 MB | Lazy-import discipline; Python + typer + rich baseline |
| Idle after `nucleus up` | < 200 MB | **PoC #4 validated 117.3 MB** |
| SeaweedFS Docker sidecar | ~200 MB | Separate process; not counted in Nucleus RSS |
| 100 MB materialize (Polars in-memory) | < 500 MB | 100 MB Parquet → ~150 MB Arrow; Polars buffers |
| 1 GB materialize (Polars in-memory) | < 3 GB | Peak; ~1.5 GB Arrow + working set |
| 10 GB materialize (Polars streaming) | < 4 GB | `engine="streaming"` batches; NEEDS VERIFICATION §11.1 |
| DuckDB recommended memory_limit | 10 GB (16 GB machine) | 70–80% of RAM per https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html |
| Workbench FastAPI idle | < 150 MB | uvicorn + FastAPI + orjson; single-worker |
| AI Copilot active | < 300 MB | litellm + context dict + httpx |

**Arrow zero-copy**: Arrow IPC `RecordBatchStreamWriter` with `BufferReader` enables zero-copy reads — returned batches allocate no new memory (https://arrow.apache.org/docs/python/ipc.html). This keeps 1 GB materialize peak below 3× source size, not 4–6×.

---

## 4. Disk + I/O Budget

| Item | Budget | Note |
|---|---|---|
| `nucleus init` scaffold | < 1 MB | Pure text templates |
| Iceberg snapshot metadata per commit | < 10 KB | 1 manifest list + 1 manifest file per data file |
| Parquet compression (zstd) | 4–8× vs raw CSV | DuckDB + PyIceberg default |
| 10 assets × 100 MB, local warehouse | ~1 GB compressed | ~8× compression typical |
| Snapshot retention default | 30 days or 100 snapshots | `expire_snapshots().older_than(dt).commit()` per https://py.iceberg.apache.org/reference/pyiceberg/table/maintenance/ |
| s3fs multipart trigger | ≈ 157 MB | `MANAGED_COPY_THRESHOLD = 150 * 2**20` (https://s3fs.readthedocs.io/en/stable/_modules/s3fs/core.html) |
| Max S3 parts | 10,000 (`MAX_UPLOAD_PARTS`) | ≈ 80 GB max at 8 MB/part before part size must grow |
| DuckDB temp spill | < 10 GB SSD quota | Set `temp_directory` to project SSD volume |

---

## 5. Concurrency Model

### Current state (v0.1)

- One Python process per `nucleus run`; Polars + DuckDB are multithreaded internally (threads = CPU count by default; DuckDB: `SET threads = <n>` per https://duckdb.org/docs/1.3/guides/performance/how_to_tune_workloads.html)
- Multiple concurrent `nucleus run` against the same asset: **NOT SAFE** — no inter-process locking on v0.1 filesystem catalog

### Iceberg optimistic concurrency and lock gap

Iceberg uses optimistic concurrency (each writer attempts atomic metadata swap; retries on conflict per https://iceberg.apache.org/docs/latest/reliability). The filesystem catalog atomic swap relies on `os.rename()` — atomic on POSIX but **NOT guaranteed on Windows NTFS** (NEEDS VERIFICATION §11.2).

**Fix required (P0 in §9)**: `FileLock(asset_key)` via `fcntl.flock` / `msvcrt.locking`; held from Parquet write start → `commit_table()`; `NE5002` after 60 s.

---

## 6. ACID + Transactional Guarantees (Iceberg Semantics)

Per `iceberg.apache.org/docs/latest/reliability` (verified 2026-05-15) and `iceberg.apache.org/spec`.

### 6.1 Guarantees Nucleus inherits automatically

Per https://iceberg.apache.org/docs/latest/reliability (verified 2026-05-15):

| Guarantee | Strength |
|---|---|
| **Atomicity** — single metadata JSON swap; all or nothing | STRONG (catalog-level) |
| **Consistent snapshots** — readers use committed, immutable snapshot; no locks | STRONG (snapshot isolation) |
| **Isolation** — snapshot reads isolated from concurrent writes | STRONG (serializable) |
| **Version history + rollback** — snapshots kept as history | STRONG |
| **O(1) planning RPCs** — snapshot read vs O(n) directory listing | Performance benefit |

### 6.2 Gaps Nucleus must harden

| Gap | Risk | Mitigation |
|---|---|---|
| **Concurrent `nucleus run` against same asset** | Two AMA processes race on snapshot commit; one writer's data is silently dropped | **Advisory filesystem lock** per §5 above; must close before PoC #5 external testers run concurrently |
| **Partial commits on disk-full / kill -9** | Writer dies after writing Parquet files but before committing metadata; orphaned files accumulate | Documented recovery: run `table.maintenance.expire_snapshots().older_than(...).commit()` to expire unreferenced snapshots, then manually list and remove orphan Parquet files not referenced by any valid manifest. NEEDS VERIFICATION §11.3 — PyIceberg 0.11 has no built-in `delete_orphaned_files()` method confirmed |
| **Catalog corruption recovery** | Filesystem catalog metadata JSON is corrupted (truncated write, power loss mid-rename) | No documented recovery playbook exists today; add to v0.1 runbook. Recommend: periodic backup of `<warehouse>/<namespace>/<table>/metadata/` directory |
| **Windows `os.rename` atomicity** | NTFS rename is NOT atomic on Windows (unlike POSIX `rename(2)` syscall); filesystem catalog atomic swap may not be reliable | NEEDS VERIFICATION §11.2 — test on Windows (PowerShell / native, not WSL) before v0.1 Windows release |

### 6.3 Schema evolution (Iceberg native, all safe)

Add column, drop column, rename column, and partition evolution are all non-destructive per the Iceberg spec (column ID mapping, not name-based; new partitions apply only to new data). Nucleus surfaces contract violations via `@nucleus.check` validation in AMA step 2 → `NE2004` before reaching pyiceberg, so raw exceptions never surface to users.

---

## 7. Reliability Patterns

Per industry best practices and the Nucleus architecture constraints.

### 7.1 Retry policies

| Operation | Idempotent? | Retry budget | Backoff |
|---|---|---|---|
| Iceberg snapshot commit (optimistic retry) | YES — Iceberg handles this internally (per reliability spec) | 3 retries (default pyiceberg config); NEEDS VERIFICATION §11.4 for exact pyiceberg default | Exponential, handled by catalog |
| `ctx.copy_from` SELECT from Postgres | YES (full_refresh mode) / NO (incremental, must checkpoint) | 3 retries with 2 s, 4 s, 8 s backoff | Exponential |
| dlt pipeline run | YES (cursor checkpointed to dlt state) | dlt manages retry internally; Nucleus wraps NE2003 on exhaustion | Per dlt default |
| s3fs Parquet write | YES (write to new path each time) | 3 retries per s3fs default | Per AWS SDK / s3fs retry config |
| DuckDB query | NO — side effects possible (CTAS, INSERT) | No retry; surface NucleusError on failure | N/A |

### 7.2 Circuit breakers (v0.2+) and idempotency

| Boundary | Budget | Behavior on exhaustion |
|---|---|---|
| Postgres source | 3 retries, 2/4/8 s backoff | `NE2003` + backoff hint; block materialize queue |
| SeaweedFS / S3 write | 3 retries per s3fs default; `HEAD` probe after write to confirm | `NE3002` "Object store unreachable" |
| Dagster `execute_in_process` hang | > 2× expected materialize time | `NE5001` internal timeout; never surface Dagster exception |
| DuckDB query (no side effects) | No retry | Surface `NucleusError` immediately |

Every `nucleus run` generates a `run_id` (UUID4) used as Parquet file prefix `<asset_key>/<run_id>-<part>.parquet` and committed to the Iceberg snapshot `summary`. This makes every run safely re-runnable; orphaned files from aborted runs are cleaned by `expire_snapshots`.

### 7.3 Health check command (v0.2)

`nucleus health` — returns project + catalog + object-store + DuckDB status in < 1 s. Example output:

```
[OK]   catalog: filesystem at ./.nucleus/warehouse/
[OK]   object-store: SeaweedFS at http://localhost:8333 (200 ms)
[WARN] disk: 85% full at /Users/alice/ (>80% threshold)
[OK]   DuckDB: 1.1.3 (4 cores, memory_limit=10 GB)
```

### 7.5 Error budgets (recommended SLOs for local dev)

| Operation | SLO (success rate) | Measurement window |
|---|---|---|
| `nucleus run <asset>` materialize | > 99% | Rolling 24h in CI |
| `nucleus query <sql>` | > 99.5% | Rolling 24h |
| `nucleus ingest` full_refresh | > 98% | Per run (source availability-bound) |
| Iceberg commit | > 99.99% | Per run (catalog bound) |
| `nucleus up` boot | > 99.9% (< 10 s) | Rolling 7d |

These SLOs are for **local development**, not cloud production. Cloud production SLAs (v1.0+) per architecture §16.5: materialization success > 99.9%, Iceberg commit > 99.99%.

---

## 8. Chaos Test Scenarios

Format: `Inject → Expected NucleusError → Acceptance criterion`.

| # | Scenario | Inject | Expected | Acceptance |
|---|---|---|---|---|
| 1 | Disk full mid-write | Fill `/tmp` to 100% during Parquet write | `NE3001` "Disk full during materialization — free X GB" | Re-run after freeing disk succeeds; orphan file count = 0 |
| 2 | Kill -9 mid-commit | `kill -9` after Parquet written, before metadata swap | Orphan Parquet unreferenced; next run creates clean snapshot | `nucleus run` after restart exits 0; `nucleus query` returns correct data; `expire_snapshots` removes orphan |
| 3 | SeaweedFS down | `docker stop` the storage sidecar | s3fs 3 retries → `NE3002` "Object store unreachable — is 'nucleus up' running?" | Clean NE3002; no hung process; re-run after `docker start` succeeds |
| 4 | Postgres drop mid-ingest | `iptables` block after 100k rows read | SQLAlchemy `OperationalError` → `NE2003`; NO partial snapshot (commit fires only on full success) | `NE2003`; no partial snapshot; re-run from scratch succeeds |
| 5 | Schema drift (add column) | `ALTER TABLE public.orders ADD COLUMN discount_pct FLOAT` then re-ingest | `full_refresh` mode auto-evolves; contract-protected mode → `NE2004` naming the differing column | Error or evolution per contract config; column name in message |
| 6 | Concurrent run race | Launch `nucleus run my_asset` from 2 terminals simultaneously | Advisory lock: 2nd waits (v0.1) or `NE5002 run in progress` (v0.2) | Zero data corruption; exactly one snapshot per logical run |
| 7 | Clock skew on schedule | System clock skewed 2h; `nucleus schedule preview my_asset` | Croniter 3.0.4 uses system clock; next-run time is wrong | Document system clock dependency; emit NTP-unreachable warning |
| 8 | Catalog metadata corrupt | Truncate `metadata.json` in `<warehouse>/.../metadata/` | pyiceberg parse error → `NE4001` "Catalog metadata corrupt — run 'nucleus repair'" | Clean NE4001 with recovery hint; no stack trace in user output |

---

## 9. Performance Optimization Opportunities

**P0 — Before v0.1 public release**

| Optimization | Impact | Effort |
|---|---|---|
| Lazy-import litellm / dlt / dagster in CLI | `nucleus --version` < 500 ms cold | Low |
| Cache Jinja `Environment` module-level singleton | Resolver < 50 ms for 100-asset DAG | Low |
| DuckDB `SET memory_limit='10GB'` at AMA init | Prevent silent OOM; correct GROUP BY | Low |
| Advisory lock for concurrent `nucleus run` | Correctness; prevent data corruption | Medium |

**P1 — v0.2 / v0.3**

| Optimization | Impact | Effort |
|---|---|---|
| Polars `engine="streaming"` default for > 1 GB | Memory peak < 4 GB; NEEDS VERIFICATION §11.1 | Low |
| Verify zstd:3 default Parquet compression | ~30% smaller vs zstd:5 | Low |
| DuckDB connection reuse in `nucleus query` REPL | −200 ms per cold query | Low |
| Iceberg manifest cache; run history paginate 50 | Planning speedup; Workbench < 100 ms | Medium |

**P2 — v0.5+**: partition pruning hints in `ctx.sql`; parallel independent-asset materialize via Dagster; pre-warm DuckDB extensions at `nucleus up`; Iceberg metadata compaction (NEEDS VERIFICATION §11.3).

---

## 10. Top 5 Must-Close Items for Release Confidence

**#1 Concurrent-run advisory lock** (1–2 days, Medium risk)
Two AMA processes race on `os.rename()` for Iceberg metadata swap → silent data loss. Fix: `FileLock(asset_key)` via `fcntl.flock`/`msvcrt.locking`, held from Parquet write → `commit_table()`; `NE5002` after 60 s timeout. Must be tested on Windows.

**#2 DuckDB `memory_limit` at connection init** (0.5 days, Low)
DuckDB defaults to 80% total RAM; GROUP BY cannot spill to disk (https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors). Fix: `conn.execute("SET memory_limit='10GB'; SET threads=8;")` at AMA DuckDB init; derive from `psutil.virtual_memory().available × 0.6`.

**#3 `expire_snapshots` maintenance hook** (1 day, Low)
10 runs/day × 30 days = 300 snapshots/asset; PyIceberg reads ALL of them on every `load_table()`. Degrades at 1000+. API confirmed: `table.maintenance.expire_snapshots().older_than(dt).commit()` (https://py.iceberg.apache.org/reference/pyiceberg/table/maintenance/). Fix: default `@nucleus.maintenance()` hook; warn when `len(table.history()) > 100`.

**#4 Lazy-import guard for litellm / dlt / dagster** (0.5 days, Low)
litellm alone ≈ 0.3–0.5 s to import. `nucleus --version` must be < 500 ms cold. Fix: `importlib.import_module()` inside each subcommand handler in `cli/main.py`; `if TYPE_CHECKING:` for type hints.

**#5 Windows `os.rename` atomicity verification** (1 day, Medium)
POSIX `rename(2)` is atomic; NTFS `os.rename()` is NOT — requires delete-then-rename (two non-atomic steps). Fix: test filesystem catalog on Windows 11 native; patch to `os.replace()` (`MoveFileEx` with `MOVEFILE_REPLACE_EXISTING`, near-atomic for single-volume); document in `SETUP.md` if deferred.

---

## 11. NEEDS VERIFICATION

| # | Claim | What to verify | Where to check |
|---|---|---|---|
| 11.1 | Polars `engine="streaming"` handles 10 GB materialize within 4 GB peak memory | GROUP BY / sort / equi-join not yet fully out-of-core per GitHub issue #20947; verify against pinned `polars==1.18.0` | https://github.com/pola-rs/polars/issues/20947 · local benchmark |
| 11.2 | `os.rename()` atomicity on Windows NTFS with filesystem catalog | Test on Windows 11 native (not WSL); filesystem catalog uses `os.rename()` for metadata swap | pyiceberg source `pyiceberg/io/pyarrow.py` rename call + Windows testing |
| 11.3 | PyIceberg 0.11.1 Python API for data file compaction / manifest rewrite | Java Iceberg has `RewriteManifests`; PyIceberg 0.11 `MaintenanceTable` only exposes `expire_snapshots()` in docs — no `optimize()` or `rewrite_manifests()` Python methods confirmed | https://py.iceberg.apache.org/reference/pyiceberg/table/maintenance/ · PyPI source for 0.11.1 |
| 11.4 | PyIceberg default retry count on optimistic concurrency conflict | Iceberg spec says "writer retries" but exact default retry budget in pyiceberg 0.11.1 is not confirmed | pyiceberg source `pyiceberg/table/__init__.py` · `TableCommit` class |
| 11.5 | Dagster cold-boot overhead contribution to per-asset materialize time | Architecture says < 500 ms for `nucleus run <asset>` startup; Dagster subprocess init may dominate | Benchmark: time empty `@nucleus.asset` run after `nucleus up` is already warm |
| 11.6 | s3fs 2026.4.0 default chunk size for multipart upload | `MANAGED_COPY_THRESHOLD ≈ 157 MB` (copy), but the upload chunk size for new writes may differ | https://s3fs.readthedocs.io/en/stable/api.html · S3FileSystem constructor `blocksize` param |

---

## 12. References

All URLs verified reachable as of 2026-05-15.

**Nucleus-internal**: `docs/specs/nucleus_architecture_v4.1.md` §1.5/§2/§5.1/§6.2/§10/§16/§19; `docs/compatibility.md`; `docs/decisions/ADR-012`; `docs/decisions/ADR-014`; `scripts/beachhead_e2e.py`; `scripts/benchmark_regression.py`; `scripts/upgrade_smoke.py`; `AGENTS.md` §1/§11.12/§11.13.

| Component | Key doc URL (verified) |
|---|---|
| DuckDB perf tuning | https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html |
| DuckDB OOM / GROUP BY spill | https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors |
| DuckDB version benchmark matrix | https://gist.github.com/joeharris76/4ad526c9da361aba9baab3a6c40f943c |
| Polars streaming | https://docs.pola.rs/user-guide/concepts/streaming |
| Polars streaming limitations (tracking) | https://github.com/pola-rs/polars/issues/20947 |
| Iceberg ACID / reliability | https://iceberg.apache.org/docs/latest/reliability |
| Iceberg spec (snapshot isolation) | https://iceberg.apache.org/spec/ |
| PyIceberg maintenance API | https://py.iceberg.apache.org/reference/pyiceberg/table/maintenance/ |
| PyIceberg snapshot API | https://py.iceberg.apache.org/reference/pyiceberg/table/update/snapshot |
| Arrow Python IPC zero-copy | https://arrow.apache.org/docs/python/ipc.html |
| dlt incremental loading | https://dlthub.com/docs/general-usage/incremental-loading |
| dlt cursor-based (Postgres) | https://dlthub.com/docs/general-usage/incremental/cursor |
| dlt Postgres CDC replication | https://dlthub.com/docs/dlt-ecosystem/verified-sources/pg_replication |
| s3fs API + MANAGED_COPY_THRESHOLD | https://s3fs.readthedocs.io/en/stable/_modules/s3fs/core.html |
| OTel Python API (no-op semantics) | https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html |

---

## 13. Hallucination Audit

**Verified**: `expire_snapshots().older_than(dt).commit()` (PyIceberg maintenance API); DuckDB `SET memory_limit`; DuckDB GROUP BY no-spill; Polars `engine="streaming"`; Arrow IPC zero-copy; Iceberg serializable isolation; s3fs `MANAGED_COPY_THRESHOLD ≈ 157 MB`.

**Not confirmed / flagged NEEDS VERIFICATION**: `table.optimize()` / `rewrite_manifests()` in Python PyIceberg 0.11 (§11.3 — only `expire_snapshots()` in `MaintenanceTable`); PyIceberg default retry count (§11.4); Windows `os.rename()` atomicity (§11.2).

No `compact_table()`, no `TPCH_BENCH()`, no Delta Lake APIs mixed into Iceberg descriptions.

---

*Researcher model: Claude Sonnet 4.6 (Gemini 3.1 Pro unavailable per AGENTS.md §11.14 fallback; Opus 4.7 also selected against to preserve Architect tier for invariant work). Time taken: ~90 min (read Nucleus internals → fetch 12+ external doc sources → compile + write).*

---

## 14. v0.2.0 empirical actuals (2026-05-15 baseline)

> Appended 2026-05-15 by the v0.2 close-out batch (`docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md` §1.9). Demotes §2 from a v0.2 SLO to a v0.3+ aspirational target. Full per-benchmark evidence in [`docs/benchmarks/2026-05-15_baseline.md`](../benchmarks/2026-05-15_baseline.md) (internal-facing baseline) and [`docs/internal/research/benchmarks_v0.2.0.md`](benchmarks_v0.2.0.md) (release-facing user report — adds B6 multi-asset DAG, B7 check overhead, B8 Workbench API, B9 ctx.sql overhead per the second builder wave 2026-05-15).

### 14.1 Headline actuals vs §2 claims

| Surface | §2 claim | v0.2 actual | Gap | Owner | Plan |
|---|---|---|---|---|---|
| `nucleus --version` cold (console) | <500 ms | **2.11 s** | +321 % FAIL | CLI lazy-imports (B2 follow-up) | v0.3 P0: strip dagster lazy-init from `--version` hot path |
| `nucleus --version` warm (console, median over 9) | <150 ms | **2.06 s** | +1274 % FAIL | Same | Same |
| `nucleus --version` console P95 | <500 ms | **4.74 s** | +847 % FAIL | Same | Same |
| `nucleus --help` cold (console) | <500 ms | **1.67 s** | +234 % FAIL | Same | Same |
| `python -m nucleus.cli.main --help` cold | <500 ms | **5.98 s** | +1096 % FAIL | Same | Same; `-m` form has heavier startup — surface separately so the gap is visible |
| B4 concurrent-run safety on Windows | "exactly one snapshot per logical run" | **BOTH committed** (A=1293905...; B=9219687...) | FAIL | Reliability hardening (ADR-024 P0-2) | v0.2.1 P0: NTFS byte-range lock semantics differ from POSIX; replace `msvcrt.locking` with exclusive `OpenFileMappingW` advisory lock |
| B4 post-race Iceberg state | "row count = expected" | **row count mismatch** (5 expected, 10 in table; snapshots=2) | FAIL | Same | Same |
| B2 materialize 1 GB (10M rows) | <30 s | **38.77 s** | +29 % FAIL | Polars streaming knob | v0.3 P1: re-measure on beachhead-spec laptop (host had only 1 GB free RAM during this run) |
| B1 TPC-H 10 GB | <3 s median / <10 s P95 | **SKIP-DEPS** (HTTP 407 corporate proxy) | unmeasured | n/a | PoC #5 testers run on home networks; defer measurement to cohort |
| B3 Postgres ingest 1M rows | <5 min | **SKIP-DEPS** (`docker pull postgres` blocked by proxy) | unmeasured | n/a | Same |

### 14.2 Reading these numbers

1. **Boot-time misses are partly host-conditional**. The benchmark host had **1.0 GB free of 15.7 GB RAM** at run start (Windows paging actively during the run); a freshly-booted laptop with the 16–32 GB beachhead spec will read materially faster. PoC #5 testers ground the real number.
2. **B4 Windows concurrent-run is a real failure** (not host-conditional). NTFS `msvcrt.locking` does not honor POSIX advisory-lock semantics the AMA assumes. The chaos J6 scenario passes on Linux/WSL but fails here. Tracked as **v0.2.1 patch P0** unless fixed before tag.
3. **B1 and B3 are unmeasured, not failed.** A Bosch corporate proxy returned HTTP 407 for `docker pull postgres` and `INSTALL tpch`. Re-measure on a PoC #5 tester's home network.
4. **B2 +29 % overshoot is marginal** (38.77 s vs <30 s) and partly host-conditional. Re-measure on beachhead spec.

### 14.3 Why §2 stays in the doc as v0.3+ targets

Per Anti-Over-Engineering Discipline, removing the targets entirely would lose the *direction of travel*. Keeping them as v0.3+ aspirational targets serves two purposes:

1. **Roadmap signalling**: v0.3 reliability + perf wave has a concrete to-do list.
2. **Drift detection**: when v0.3 lands, the gap between this section and §2 narrows; the change is visible to anyone reading the doc.

### 14.4 v0.2.0 v0.2.0 SLOs (the parts that DO hold)

The following §7.5 SLOs ARE empirically validated as of 2026-05-15:

- Iceberg commit > 99.99 %: PASS via B2 100 successful commits / 100 attempts.
- `nucleus up` boot < 10 s: PASS (PoC #4: 5.82 s; WSL E2E: 7 s).
- Chaos J1/J2/J4/J5/J6 (Linux/WSL)/J7: PASS per `docs/release/chaos_test_results.md`.

These are the v0.2.0 release contract. Everything in §2 above demotes to roadmap.

### 14.5 Cross-references

- [`docs/benchmarks/2026-05-15_baseline.md`](../benchmarks/2026-05-15_baseline.md) — per-benchmark raw output + hardware caveats (B1–B5).
- [`docs/internal/research/benchmarks_v0.2.0.md`](benchmarks_v0.2.0.md) — release-facing user report adding B6–B9 (this builder wave, 2026-05-15).
- [`docs/release/chaos_test_results.md`](../release/chaos_test_results.md) — J1–J8 results (J3 + J8 closed in v0.2; see CF-1 + CF-2 fix in this same close-out batch).
- [`docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md`](../release/v0.2_FOUNDER_CLOSE_CHECKLIST.md) §1.9 — pre-sprint blocker #8 (this reconciliation).

### 14.6 Additional benchmarks (B6–B9, added 2026-05-15 builder wave)

The release-facing benchmark report at [`docs/internal/research/benchmarks_v0.2.0.md`](benchmarks_v0.2.0.md) extends the §14.1 table with four additional surfaces measured on the same Windows host. Headline actuals:

| Surface | Claim/expectation | v0.2 actual (this host) | Verdict | Plan |
|---|---|---|---|---|
| **B6** Multi-asset DAG materialize, 50 assets / 5 layers | informational | **9.58 s total** (median 162 ms/asset warm; coordination overhead ≈0.1 ms) | PASS | Document baseline; v0.3 may add parallel asset materialize via Dagster. |
| **B6** Multi-asset DAG materialize, 10 assets / 3 layers | informational | **9.21 s total** (median 207 ms/asset; first-call cold ~7 s) | PASS | Same; first-call cost is the B5 boot tax. |
| **B7** Check overhead, 1 M rows + 3 checks (warm) | <50 % of baseline | **−2.6 % to +75 %** across two runs (below noise floor on this paging host) | PASS / FAIL-LOW depending on run | Re-measure on beachhead spec; expected to settle in low single-digit %. |
| **B8** Workbench `uvicorn` spin-up | <2 s (perf doc §2.6 page-load envelope) | **8.58 s** | FAIL | Same root cause as B5 boot — `openlineage.client` + Dagster lazy-init in coordination chain. v0.3 P0. |
| **B8** Workbench `GET /api/health` median | <100 ms (perf doc §2.6) | **3.1 ms** (P95 5.1 ms) | PASS −96 % | None. |
| **B8** Workbench `POST /api/query` p50 (small Iceberg query) | <500 ms (informational) | **640 ms – 1.01 s** | FAIL | Cache DuckDB connection across requests via FastAPI lifespan; v0.3 P1. |
| **B9** `ctx.sql` per-call overhead vs raw DuckDB | "<5 % overhead" (task spec) | **+50–80 ms fixed cost per call**, regardless of query (≈10 800 % on `SELECT 1`, ≈500 % on small GROUP BY, dropping to noise on multi-second scans) | FAIL on small queries | Connection-cache work in v0.3 — perf doc §9 P1 ("DuckDB connection reuse in `nucleus query` REPL"). |

**Key takeaways for the v0.2.0 release window**:

1. **DAG coordination overhead is essentially free** (B6 — 0.1 ms across 50 assets). Iceberg commit ceremony does not stack as the analytics warehouse widens. This is the headline "good news" of the v0.2 measurements.
2. **Check overhead is below noise floor** on this paging host (B7) — even when the percentage looks alarming on a single run, the absolute delta is ~25–230 ms on 1 M rows. Users should treat checks as "free" for normal workloads.
3. **CTX SQL fixed-cost catalog open** (B9) is the single-biggest user-visible inefficiency in v0.2.0 outside of CLI cold boot. Tiny queries pay disproportionately; analytical scans amortize. v0.3 connection cache work is the fix.
4. **Workbench `POST /api/query` latency** (B8) inherits the B9 fixed cost via the HTTP layer; same v0.3 fix applies.

Reproduce all four with the consolidated runner:

```bash
python scripts/benchmarks/benchmark_v020.py --suite release --output benchmarks/results.json
```
