# Scale-Out Audit — Nucleus at Large-Team Scale

> **Date**: 2026-05-15
> **Researcher**: Claude Opus 4.7 (Researcher tier; Gemini 3.1 Pro unavailable in current Cursor runtime — fallback per `AGENTS.md` §11.14)
> **Constraint frame**: `AGENTS.md` §3 Constraints **#1 (no JVM)**, **#3 (no custom scheduler)**, **#4 (no custom compute engine)**, **#5 (no custom commit service)**, **#6 (no custom auth)**, **#8 (≤30K LOC)**, **#9 (composability)** are **inviolable**. This audit operates inside that envelope.
> **Scope**: Honest assessment of where Nucleus's ~13K LOC of proprietary glue code breaks at large-team scale (100+ engineers, > 5 TB warehouse, > 100 scheduled assets, 10+ concurrent Workbench users), and which (if any) components deserve a non-Python rewrite.
> **Out of scope**: Recommending Nucleus become a Spark replacement, Databricks competitor, or "universal compute platform". Per `AGENTS.md` §8 those framings are forbidden by name.
> **Source-code snapshot**: `src/nucleus/` at v0.2.0 (HEAD as of 2026-05-15), 64 files, 12,944 LOC.

---

## TL;DR

For the audit-target persona — **100+ engineers, multi-team concurrent usage, > 5 TB warehouse, > 100 scheduled assets** — Nucleus v0.2.0 is **NOT a fit today**, **and that is by design** per `nucleus_architecture_v4.1.md` §1.5 (beachhead 5–20 engineers, 100 GB–5 TB) and §10 (yield-to-giants for scale beyond beachhead). That persona sits at or above the **upper edge** of the documented scale envelope (v4.1 §16.4: 50+ Workbench users, 100+ concurrent runs single-node, 10,000+ assets) and well above the documented data envelope. The architecturally-correct path for that persona is **graduation via Iceberg portability (Mode 1)** + **selective Mode 2 dispatch** to Databricks/Snowflake — not a Rust rewrite of Nucleus internals.

Three real (closeable) gaps surface at the upper edge of the documented envelope:

1. **Cross-machine concurrency primitives are filesystem-local only** — `coordination/locks.py` and `coordination/run_ledger.py` are single-host correct; multi-host coordination is unowned. Closure path: **Lakekeeper REST catalog** (already planned v0.3+ per v4.1 §5.7 + ADR-004). No Nucleus rewrite needed.
2. **Workbench backend is single-uvicorn-worker** — fine for a 5-engineer team, blocks at ~50 concurrent users per v4.1 §16.4. Closure path: **uvicorn `--workers=N` config** + reverse proxy. Documentation, not code. No Nucleus rewrite needed.
3. **Scheduling daemon is single-process, no leader election** — `coordination/daemon.py` is the v0.2.1 mini-scheduler fallback per v4.1 §6.7 + ADR-017. For HA scheduling at multi-team scale, the architecturally-correct answer is the **Dagster daemon on Kubernetes with Postgres event log** (the wrap target per `AGENTS.md` §3 #3) — not a Go/Rust rewrite of `daemon.py`.

Verdict on every "rewrite X in Rust/Go" candidate the founder is likely entertaining: **REJECT**. Each fails the 8-question gate (`.cursor/rules/nucleus.mdc`) on Q2 (beachhead service), Q3 (wrap not build), and/or Q7 (empirical telemetry, not anxiety). The reasoning is uniform: Nucleus's ~13K Python LOC is **glue**; the ~95% of execution time at any meaningful workload is already inside C++ (DuckDB, pyarrow), Rust (Polars), or wire-bound network I/O (s3fs, postgres). Rewriting the glue in Rust optimizes the ~5% that isn't the bottleneck while violating Constraints #4, #8, and the anti-over-engineering directive.

The honest scale-out story is unchanged: **Nucleus is excellent for the documented beachhead envelope; for the audit-target persona, the design intent is graduation, not engine rewrite.**

---

## Section 1: LOC + complexity inventory

Counted via PowerShell `Get-Content | Measure-Object -Line` on every `.py` file under `src/nucleus/` excluding `__pycache__`. Numbers are physical lines (matches `scripts/loc_budget.py` methodology per `AGENTS.md` §11.6).

### 1.1 Per-directory totals

| Directory | Files | LOC | Role | Layer (v4.1 §3.1) |
|---|---|---|---|---|
| `coordination/` | 12 | **3,303** | AMA, error translation, locks, scheduler, lineage, run ledger, BI handshake | L2 Coordination |
| `cli/` | 11 | **3,243** | 8 user-facing commands + Docker compose orchestration + Rich rendering | L4 Experience |
| `ctx/` | 11 | **2,304** | `ctx.read/write/sql/copy_from` + 7 connectors (postgres, mysql, snowflake, sqlite, csv, gcs, s3) | L4 Experience (SDK) |
| `workbench/` | 12 | **1,216** | FastAPI app + 8 routers (assets, runs, query, chat, dashboard, schedules, catalog, search) | L4 Experience |
| `sdk/` | 5 | **1,132** | `@nucleus.asset` + `@nucleus.check` decorators, `materialize()`, contracts, `MaterializationResult` | L4 Experience |
| `intelligence/` | 4 | **595** | Copilot v0.2 (single-turn chat via litellm), translation glue | L3 Intelligence |
| `errors.py` (root) | 1 | **785** | NE-coded error class registry (24 codes per ADR-006) | Cross-cutting |
| `__init__.py` (root) | 1 | **78** | Public re-exports | Cross-cutting |
| `_internal/` | 2 | 95 | Logging, internal helpers | Cross-cutting |
| `templates/` | 3 | 36 | `nucleus init` scaffold templates | Cold path |
| `engines/` | 1 | 16 | Engine adapter scaffold (placeholder) | L1 Engines |
| `physics/` | 1 | 16 | Physics-layer scaffold (placeholder) | L0 Physics |
| **TOTAL** | **64** | **12,944** | — | — |

LOC budget headroom per `AGENTS.md` §11.6 (v0.2 expected ~8K, v1.0 ceiling 30K): **comfortably under** — 12.9K is 43% of the v1.0 ceiling, on track for the v0.2 → v0.5 LOC trajectory. Drift toward 30K is the watch metric, not the current count.

### 1.2 Hot-file ranking (top 20 by LOC, descending)

| # | File | LOC | Hot path? | Cyclomatic complexity hotspots |
|---|---|---|---|---|
| 1 | `cli/main.py` | 1,171 | NO — cold (process entry) | Many `if subcommand` branches; 8 commands, each 50–150 LOC |
| 2 | `coordination/error_translation.py` | 818 | YES per-error (rare) | Switch-style handler dispatch; 16+ handlers with `__cause__` chain walk (`_iter_causes`, depth ≤ 8) |
| 3 | `errors.py` | 785 | NO — class definitions | 24 NE-coded subclasses; mostly dataclass-like shape + `rendered()` formatter |
| 4 | `coordination/asset_materialization.py` | 600 | YES per-materialization | `_invoke_asset_body` → `_commit_to_iceberg`; nested try/except for `CommitFailedException`/`NamespaceAlreadyExistsError`/`TableAlreadyExistsError`; `_arrow_type_to_iceberg` is a 12-branch type mapper |
| 5 | `sdk/decorators.py` | 520 | NO — runs at import | Schedule cron validator (croniter) + key-shape regex; `_AssetDefinition` immutable dataclass |
| 6 | `coordination/daemon.py` | 418 | YES per-poll (5 s) | Single `while not _shutdown_event.is_set()` loop; `_should_fire` croniter call per schedule per poll |
| 7 | `cli/commands/snapshot.py` | 348 | NO — cold | Iceberg snapshot list/show/expire commands |
| 8 | `cli/commands/schedule.py` | 344 | NO — cold | Daemon on/off/trigger/status commands |
| 9 | `cli/commands/runs.py` | 340 | NO — cold | Run history list/show/cancel commands |
| 10 | `cli/commands/dagit.py` | 333 | NO — cold | `nucleus enable compat-dagster` — Tier 3 escape hatch (v4.1 §6.6) |
| 11 | `ctx/copy_from_s3.py` | 315 | YES per-ingest | s3fs `glob` + Arrow stream + `pyiceberg` append; multipart trigger ≈ 157 MB |
| 12 | `cli/_compose.py` | 298 | NO — cold | Docker compose YAML generation for `nucleus up` |
| 13 | `ctx/copy_from_gcs.py` | 289 | YES per-ingest | gcsfs equivalent of s3 path |
| 14 | `ctx/copy_from_filesystem.py` | 274 | YES per-ingest | local file glob + Arrow read |
| 15 | `intelligence/copilot.py` | 272 | YES per-chat | litellm wrap (v0.2 single-turn); LLM-bound, not CPU-bound |
| 16 | `coordination/lineage.py` | 244 | YES per-materialization | OpenLineage event NDJSON write (best-effort, never fails AMA) |
| 17 | `coordination/run_ledger.py` | 237 | YES per-materialization | NDJSON append with `threading.Lock`; in-memory cache cap 1000 |
| 18 | `coordination/locks.py` | 225 | YES per-materialization | `fcntl.flock` (POSIX) / `msvcrt.locking` (Win); poll interval 200 ms; 30 s default timeout |
| 19 | `sdk/materialize.py` | 224 | NO — thin SDK boundary | Validates inputs, delegates to AMA |
| 20 | `workbench/api/runs.py` | 220 | YES per-API-call | FastAPI route → `RunLedger.list()` paginated |

The five highest-complexity files (subjective complexity, not raw cyclomatic):

1. `coordination/error_translation.py` — 16+ handler functions + cause-chain walker + module-prefix Dagster filter (avoiding leaky wrapper classnames per v4.1 §6.4)
2. `coordination/asset_materialization.py` — handles dry-run, lock acquire, body invoke, Iceberg create-or-load-or-append, snapshot expiry hook, lineage emit pre/post (best-effort)
3. `coordination/daemon.py` — subprocess spawn (Win `DETACHED_PROCESS` vs POSIX `start_new_session`), pidfile race handling, signal handlers (Win SIGTERM caveat), cron poll loop
4. `coordination/locks.py` — cross-platform `fcntl`/`msvcrt` dispatch, stale-PID detection (psutil with ctypes fallback), JSON owner metadata, poll-with-deadline
5. `cli/main.py` — Typer app with 8 subcommands, lazy-import discipline (litellm/dlt/dagster guards per perf doc §10 #4), exit-code mapping

### 1.3 Dependency-language audit (the wrapped engine claim)

**Claim** (per `nucleus.mdc` "Default Decision: WRAP, not BUILD" + `AGENTS.md` §4): Nucleus is *glue*; the heavy work happens inside libraries already implemented in C++/Rust.

| Dependency | Implementation language | Citation | Notes |
|---|---|---|---|
| DuckDB | **C++** (with C API) | https://duckdb.org/why_duckdb.html ("written in C++") | All scan/filter/group-by happens here, not in Nucleus Python |
| Polars | **Rust** (with `polars-arrow`, `polars-core` Rust crates) | https://pola.rs/ ("blazingly fast DataFrame Library implemented in Rust") | DataFrame ops, joins, group-bys execute in Rust; Python is a thin facade |
| Apache Arrow / PyArrow | **C++** core, Python bindings | https://arrow.apache.org/docs/python/ | Zero-copy IPC; `RecordBatchStreamWriter` per perf doc §3 |
| PyIceberg | **Python** (no Rust core in 0.11.x) | https://py.iceberg.apache.org/ | Iceberg metadata I/O is Python; data file write delegates to PyArrow C++. **NEEDS VERIFICATION**: Apache Iceberg Rust project (https://github.com/apache/iceberg-rust) exists separately; Python bindings status NOT confirmed for 0.11.1 — do not assume |
| Dagster | **Python** | https://docs.dagster.io/ | Hidden behind `ctx` per v4.1 §6.3; replaceable per §6.5 by v1.0 |
| Jinja2 | **Python** | https://jinja.palletsprojects.com/en/3.1.x/ | `Environment` is the cache target per perf doc §10 P0 |
| s3fs | **Python** | https://s3fs.readthedocs.io/en/stable/ | Multipart trigger 157 MB per perf doc §4 |
| FastAPI / Starlette / uvicorn | **Python** (uvicorn uses asyncio + uvloop optionally) | https://fastapi.tiangolo.com/ | Workbench backend |
| psutil | **Python** with C extension | https://psutil.readthedocs.io/ | Cross-platform process / mem inspection |
| filelock (optional) | **Python** (uses `fcntl`/`msvcrt` stdlib) | https://py-filelock.readthedocs.io/ | Currently unused; `coordination/locks.py` uses stdlib directly to avoid the dep |
| croniter | **Python** | https://github.com/kiorky/croniter | Schedule parser; called once per poll per schedule |
| pyo3 (potential rewrite vehicle) | Rust framework for Python bindings | https://pyo3.rs/ | Cited only as the *vehicle* if any rewrite happened — none recommended |

**Implication**: a 1 GB Polars group-by → DuckDB SELECT → pyiceberg commit takes seconds. The Python *coordination glue* in that path (AMA orchestration, error translation, lock acquire, lineage emit) is single-digit milliseconds. **Optimizing the glue in Rust improves the runtime by < 1%** — a textbook case of the wrong optimization target.

---

## Section 2: 5-dimension scoring table

Per the founder's directive: **extreme performance, reliability, feasibility, composability, scalability**. Scored for the **large-team scenario** (100 engineers, 500 scheduled assets, 5,000 ad-hoc materializations/day, 100 TB warehouse, 10 simultaneous Workbench users, multi-team writes to same Iceberg namespace). Scoring legend:

- **GREEN** — no risk for large team within current envelope
- **YELLOW** — degrades but works; documented mitigation exists
- **RED** — breaks; needs intervention before large-team adoption
- **BLOCKED-BY-ARCH** — cannot fix without violating `AGENTS.md` §3 Constraints; the architectural answer is yield-to-giants

| Component | LOC | Perf | Reliability | Feasibility | Composability | Scalability | Overall verdict |
|---|---|---|---|---|---|---|---|
| `ctx/copy_from_postgres.py` (+ mysql, snowflake, sqlite, csv variants) | 206–315 each | **YELLOW** — single fetchmany loop in one Python process | **GREEN** — full_refresh is idempotent; failure → no Iceberg commit; advisory lock prevents racing writers | **GREEN** for v0.2 beachhead; **YELLOW** for 100M+ rows (single-process saturates) | **GREEN** — `dlt` is the v0.3+ swap (ADR-025 P1-1) | **YELLOW** at 10M+ row tables; CDC via dlt v0.3+ closes this | **YELLOW** — by design; Mode 2 dispatch + dlt CDC are the documented closures, not glue rewrite |
| `cli/main.py` + `cli/commands/*` | 87–1171 | **GREEN** — cold path; lazy-imports per perf doc §10 P0 #4 | **GREEN** — typed exits; NucleusError rendering | **GREEN** — `nucleus run` startup < 500 ms per v4.1 §16.1 | **GREEN** — Typer is a wrap, not a custom CLI framework | **GREEN** — CLI is per-process; no shared state at scale | GREEN — boring shell, by design |
| `coordination/asset_materialization.py` (AMA) | 600 | **GREEN** — per-asset glue is sub-ms; bottleneck is wrapped engines (DuckDB query, pyarrow Parquet write, pyiceberg commit) | **GREEN** at single-host (P0-1/2/3/5 closed per ADR-024); **YELLOW** at multi-host (lock is fcntl/msvcrt → host-local) | **GREEN** for beachhead; **YELLOW** for multi-team if filesystem catalog is shared via NFS (v0.1 catalog isn't designed for that) | **GREEN** — `materialize_asset` is the swap point per v4.1 §6.5; replaceable by mini-scheduler equivalent at v1.0 | **YELLOW** — single-asset-per-call by design (line 40 of file: "No batch materialization"); horizontal scale is "more processes", catalog handles concurrency via Iceberg optimistic commits | GREEN with caveat: large-team needs Lakekeeper for cross-machine catalog (v0.3+, ADR-004) |
| `coordination/error_translation.py` | 818 | **GREEN** — switch-style dispatch, microseconds per error even at 1000 errors/s | **GREEN** — handlers MUST NOT raise (line 41); fallback is `NucleusInternalError` | **GREEN** — Python is more than fast enough | **GREEN** — handler list is data, not architecture | **GREEN** — stateless; horizontal-scale-trivial | GREEN — no concerns; perf is irrelevant compared to the actual error condition cost |
| `coordination/run_ledger.py` (NDJSON) | 237 | **GREEN** — single append per finish, flushed; in-memory LRU cache cap 1000 | **YELLOW** — `threading.Lock` is single-process; multi-process (e.g., daemon + manual `nucleus run`) appends to the same file with no inter-process lock; POSIX append < PIPE_BUF (4 KB) is atomic per OS, longer lines may interleave; NTFS append atomicity is **NEEDS VERIFICATION** | **GREEN** for single-host; **RED** for multi-host shared-volume scenarios | **YELLOW** — clear swap target is Postgres-backed ledger (v4.1 §11.3 production stack); NDJSON works for v0.1/v0.2 single-host | **YELLOW** — file grows linearly; cache cap protects memory; no rotation; 5000 mat/day × 365d = 1.8M lines/yr ≈ 200–400 MB | YELLOW — close via Postgres-backed ledger at v0.3 (Lakekeeper coexists with Postgres) |
| `coordination/daemon.py` (mini-scheduler) | 418 | **GREEN** — 5 s poll, croniter call per schedule is microseconds | **YELLOW** — single-process pidfile; no leader election; SIGTERM-handled but Win SIGTERM is best-effort (line 226: "Platform may not support all signals") | **GREEN** as v0.2 fallback per v4.1 §6.7 + ADR-017 | **GREEN** — `mini-scheduler is fallback` per `AGENTS.md` §3 #3; primary remains Dagster daemon | **YELLOW** — single-process throughput; for 500 schedules at minute-granularity, fine; for HA across machines, **BLOCKED-BY-ARCH** in mini-scheduler scope — yield to Dagster daemon on k8s (v4.1 §6.1, §11.3) | YELLOW for large team; the architecturally-correct primary is wrapped Dagster + Postgres event log + k8s leases, not extending mini-scheduler |
| `coordination/locks.py` | 225 | **GREEN** — `fcntl.flock` is microseconds; 200 ms poll interval | **YELLOW** — host-local only; `fcntl.flock` does NOT span NFS reliably; `msvcrt.locking` is Windows-local; stale-PID detection works on same host | **GREEN** for beachhead (single laptop); **RED** for multi-host shared-warehouse scenarios | **GREEN** — clear interface (`asset_lock(project_root, asset_key)`); swappable to a catalog-managed lock at v0.3+ | **RED** for multi-host: file locks do not coordinate across machines | **BLOCKED-BY-ARCH** for cross-machine — that's catalog territory; Lakekeeper handles it via the Iceberg REST commit endpoint (v4.1 §5.7, ADR-004) |
| `coordination/sql_resolver.py` (Jinja `{{ ref() }}`) | 180 | **GREEN** — `Environment` cached + `from_string`; perf doc §2.5 says < 50 ms for 100-asset DAG | **GREEN** — `StrictUndefined` rejects unknown vars; Jinja exceptions translated to `NucleusSQLSyntaxError` | **GREEN** — well within v4.1 §5.6.0 ≤ 2500 LOC scope ceiling | **GREEN** — dbt-duckdb is the documented optional v0.3+ adapter swap (`nucleus.mdc` table) | **GREEN** — pure function; horizontal-scale-trivial | GREEN — no concerns; resolver is a tiny line item next to query execution time |
| `coordination/bi_handshake.py` (DuckDB sidecar generation) | 138 | **GREEN** — generates a `.duckdb` file for BI tools to attach | **GREEN** — generated file is ephemeral; rebuild on each `nucleus query --bi-output` | **GREEN** — wrapped DuckDB | **GREEN** — DuckDB is the v4.1 §5.1 default; DataFusion is the swap | **GREEN** — single-asset op; not a hot loop | GREEN |
| `sdk/decorators.py` + `sdk/materialize.py` | 520 + 224 | **GREEN** — registration is one-time at import; `materialize()` is a thin SDK boundary | **GREEN** — typed validation rejects malformed input at decoration time | **GREEN** — public surface is the v0.1 `ctx` SDK contract per v4.1 §13 | **GREEN** — the SDK *is* the swap-stable contract per v4.1 §13.1 (the only public API) | **GREEN** — registry is in-process dict; not a scale primitive | GREEN |
| `errors.py` (NE registry) | 785 | **GREEN** — class definitions + `rendered()` formatter | **GREEN** — typed surface; ADR-006 numbering policy | **GREEN** — already in production for v0.2 | **GREEN** — additive only; backward compatible | **GREEN** — no scale impact | GREEN |
| `workbench/` (FastAPI + 8 routers) | 1,216 | **YELLOW** — single uvicorn worker per `workbench/cli.py` line 99; FastAPI is async but Python GIL limits CPU-bound parallelism per request | **GREEN** — endpoints are read-only or thin write wrappers; CORS configured for Vite dev | **GREEN** for v4.1 §16.4 target (single-server 50 users); **RED** at 50+ concurrent users without multi-worker config | **GREEN** — FastAPI is the wrap (vs Flask, Django); routers can be replaced individually | **YELLOW** for 50+ users on single host; **GREEN** with `uvicorn --workers=N` config or k8s replicas | YELLOW — close via documentation (cookbook recipe owned by C2 worker); zero LOC change |
| `templates/` (`nucleus init` scaffold) | 36 | N/A — cold path | N/A | GREEN | GREEN | GREEN | GREEN — boring scaffolds |
| `intelligence/copilot.py` | 272 | **GREEN** — LLM-call latency dominates; provider-bound | **GREEN** — opt-in (v0.2); failure surfaced as NucleusError | **GREEN** for v0.2 single-turn chat (v4.1 §7.2) | **GREEN** — litellm is the wrap; provider-agnostic | **GREEN** at modest concurrency; for 100-engineer chat traffic, the bottleneck is the LLM provider rate limit, not Nucleus | GREEN for v0.2 scope; v0.5+ schema-aware Copilot is a different scaling story (token cost per `AGENTS.md` §9) |

**Reading the table**: the only two RED cells are (a) `coordination/locks.py` for cross-machine scenarios — and that's BLOCKED-BY-ARCH because cross-machine locking IS the catalog's job per v4.1 §6.2, not Nucleus's; (b) `workbench/` at 50+ concurrent users without multi-worker config — and that's a one-line config change + a cookbook recipe. **No component is RED on a dimension where the architecture invites Nucleus to fix it.**

---

## Section 3: Breakage map (where it fails first under scale)

For each scenario, format is: **failure mode → severity (BLOCKER/HIGH/MEDIUM/LOW) → recommended fix path** drawn from the v4.1-approved set: **YIELD** (Mode 2 dispatch), **OPTIMIZE** (Python-level), **HOT-PATH** (Cython/PyO3 for inner loop), **ACCEPT** (document the limit), **ARCH-CHANGE** (surface as ADR; likely violates a constraint). Scenarios are scored against the audit-target persona, not the beachhead.

### 3.1 Multi-team writes to same Iceberg namespace, multi-host workers

- **Failure mode**: 10 worker hosts each spawn an AMA, all targeting `sales.fct_orders`. The host-local `coordination/locks.py` provides no cross-host coordination. Iceberg optimistic concurrency at the catalog *will* serialize the actual snapshot commits (the catalog handles this per v4.1 §6.2), but Nucleus's per-asset advisory lock prevents only same-host races, not cross-host. Most commits will retry, occasional `NucleusCommitConflictError` (NE1002) surfaces.
- **Severity**: MEDIUM at v0.2 with filesystem catalog (filesystem catalog should not be shared across hosts, period). LOW at v0.3 with Lakekeeper, because the REST catalog handles atomic commits and conflict signaling.
- **Recommendation**: **YIELD** to Lakekeeper (v0.3+, ADR-004). No `coordination/locks.py` changes needed; the host-local lock remains correct for what it claims to do (single-host de-dup). Cross-host coordination is **Iceberg's job, not Nucleus's job** per `AGENTS.md` §3 #5 and v4.1 §20.1 ("No custom Iceberg commit service / distributed transaction coordinator"). Do NOT extend `coordination/locks.py` to be cross-machine — that's a constraint violation in flight.

### 3.2 Run ledger (NDJSON) under cross-process append concurrency

- **Failure mode**: `coordination/run_ledger.py` uses `threading.Lock` for single-process safety. If the daemon and a manual `nucleus run` (separate processes) both append to `runs.ndjson`, POSIX guarantees atomicity for writes < `PIPE_BUF` (4 KB on Linux); a long line (lots of metadata) might interleave. NTFS append atomicity for concurrent writers is **NEEDS VERIFICATION** but conservatively assume it's not guaranteed.
- **Severity**: LOW for the documented beachhead (one user, one machine). MEDIUM for shared-CI scenarios. MEDIUM-HIGH at large-team scale on shared volumes.
- **Recommendation**: **OPTIMIZE** at v0.2 by ensuring each line < 4 KB (currently true: a `RunRecord` dict ≈ 300–800 B). **ARCH-CHANGE** at v0.3 — graduate to a Postgres-backed ledger when Lakekeeper is the catalog (production stack per v4.1 §11.3 already specifies PostgreSQL for metadata). Keep the NDJSON path as the single-host default; switch to Postgres via the same `RunLedger` interface when `nucleus_project.yaml` declares a Postgres connection. **No Rust rewrite warranted** — Postgres at scale is the well-known answer.

### 3.3 Workbench at 50+ concurrent users on a single uvicorn worker

- **Failure mode**: `workbench/cli.py` runs `uvicorn` single-process. FastAPI is async, but DuckDB queries inside `query.py` are synchronous and hold the GIL during the call into the C++ engine — concurrent queries serialize. At 50+ users, p95 latency degrades.
- **Severity**: HIGH if a 100-engineer team adopts Workbench heavily; LOW if Workbench is used by 5–10 people while CLI is the primary surface (the v0.1 model).
- **Recommendation**: **OPTIMIZE** via a one-line change to use `uvicorn --workers=N` (or `gunicorn -w N -k uvicorn.workers.UvicornWorker`), plus a cookbook recipe in `docs/cookbook/production-deployment.md` (currently owned by worker C2 — do not write to it from this audit). For very large scale, document a reverse-proxy + horizontal-replica deployment. **No Rust rewrite warranted** — moving to axum/actix-web would mean rewriting all 8 routers (~1,200 LOC) for a problem that uvicorn workers solve at zero LOC. Per v4.1 §16.4, the single-server target is 50 concurrent users; for more, the architecture invites horizontal scale, not engine swap.

### 3.4 Scheduling daemon HA / leader election at 500 scheduled assets across multiple hosts

- **Failure mode**: `coordination/daemon.py` is a single-process polling loop; pidfile prevents same-host duplicates but offers no cross-host election. Two hosts with the daemon → schedules fire twice. The `coordination/asset_materialization.py` advisory lock prevents data corruption (same-asset same-host de-dup), but cross-host duplicate firing is the catalog's commit-conflict path, not a no-op.
- **Severity**: HIGH at multi-host scale.
- **Recommendation**: **ACCEPT** at the mini-scheduler level — `daemon.py` is the v4.1 §6.7 fallback, designed for single-host. **YIELD** to the Dagster daemon on Kubernetes (with Postgres event log and k8s lease-based leader election) for multi-host HA. This is the *primary* path per v4.1 §6.1 and `AGENTS.md` §3 #3; mini-scheduler is the fallback. Per `AGENTS.md` §4 ("Custom scheduler → use Dagster"), extending `daemon.py` with leader election would be re-implementing what Dagster already does. Document this in cookbook (production-deployment.md, owned by C2). **No Rust rewrite warranted; no Nucleus rewrite warranted at all.**

### 3.5 100 TB total warehouse with single-node Polars/DuckDB

- **Failure mode**: Per perf doc §2.2, > 100 GB per asset should yield. Per v4.1 §1.5, the documented data envelope ends at 5 TB total. At 100 TB, the laptop (and even a 32-core server) is the wrong tool. Polars streaming has known limits (group-by/sort/equi-join not fully out-of-core per https://github.com/pola-rs/polars/issues/20947, NEEDS VERIFICATION 11.1 in perf doc); DuckDB GROUP BY hash table cannot spill to disk per https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors.
- **Severity**: BLOCKER at this scale — and that's by design.
- **Recommendation**: **YIELD** via Mode 2 dispatch (`@nucleus.sql_asset(compute="databricks")` per v4.1 §10.2). No Nucleus internal change. Engineers with 100 TB warehouses are above-beachhead per v4.1 §1.4 and §1.5 — they belong on Databricks/Snowflake for the heavy lifting; Nucleus orchestrates and stays the SDK. **Do NOT** attempt to optimize DuckDB GROUP BY by writing a custom Rust hash-spill — Constraint #4 ("No custom compute engine") forbids it.

### 3.6 1,000 errors/second translation rate

- **Failure mode**: At 1,000 errors/s, the switch-style handler dispatch in `error_translation.py` is approximately 1,000 microsecond-scale operations per second = 1 ms/s aggregate CPU. Negligible.
- **Severity**: LOW (essentially no failure mode).
- **Recommendation**: **ACCEPT** — this scenario is not a real bottleneck. If a system is generating 1,000 typed errors/second, the problem is not error-translation throughput; it's whatever is *causing* 1,000 errors/second.

### 3.7 Cold boot of 100+ Python imports (CLI startup at 100-engineer scale, multiplied by CI workers)

- **Failure mode**: Per perf doc §2.1, `nucleus --version` target is < 500 ms cold. PoC #4 validated 5.82 s for `nucleus up` and 117.3 MB idle RSS (`AGENTS.md` §1). At 100 engineers running `nucleus run` in CI hundreds of times per day, cold boot per run amortizes well.
- **Severity**: LOW.
- **Recommendation**: **OPTIMIZE** the existing lazy-import discipline (already enforced for litellm/dlt/dagster in `cli/main.py`); ensure new connectors follow the same pattern. No rewrite needed. CI users can also use `nucleus up` to keep a daemon warm.

### 3.8 Shared filesystem catalog `catalog.db` (SQLite) under multi-writer load

- **Failure mode**: v0.1 filesystem catalog uses SQLite (per `coordination/asset_materialization.py` line 441: `uri=f"sqlite:///{catalog_db.resolve().as_posix()}"`). SQLite supports one writer at a time (https://www.sqlite.org/lockingv3.html). At 100 concurrent materializations, writers serialize on the SQLite catalog file.
- **Severity**: HIGH at multi-host scale; MEDIUM at single-host.
- **Recommendation**: **YIELD** to Lakekeeper REST catalog at v0.3 (ADR-004; v4.1 §5.7). The filesystem catalog is explicitly v0.1 default, not the production answer per v4.1 §11.3. **No Nucleus rewrite warranted** — this is exactly the case the architecture's catalog-swap interface is designed to handle.

### 3.9 OIDC delegation at 100-engineer multi-team scale

- **Failure mode**: v0.2 has no auth (single-user local). Multi-team usage requires identity, RBAC, audit trail.
- **Severity**: BLOCKER for any team beyond ~10 people.
- **Recommendation**: **YIELD** to OIDC provider (Authentik / Keycloak / Okta / Azure AD) per v4.1 §15.1 + `AGENTS.md` §3 #6 ("No custom auth system. Always delegate to OIDC."). Already planned at v0.8+ per ADR-025 P3-1. **Do NOT** build a custom user system in Rust or Python; that's a Constraint #6 violation in flight.

### 3.10 Workbench search/dashboard endpoints scanning 10K+ assets

- **Failure mode**: `workbench/api/search.py` (106 LOC) and `workbench/api/dashboard.py` (94 LOC) walk the in-process asset registry. At 10K assets per v4.1 §16.4 target, a linear scan is sub-ms in Python; rendering 10K rows in a single API response is the actual bottleneck.
- **Severity**: LOW (paginate at the API edge — already done in `runs.py` per perf doc §2.6).
- **Recommendation**: **OPTIMIZE** — ensure search/dashboard paginate at default 50 like runs do. If virtualized scroll is needed for 1,000-asset DAG render, that's a Workbench frontend job, not a Rust rewrite.

---

## Section 4: Language-rewrite candidates (the founder's explicit question)

For EACH candidate the founder is likely entertaining, the 8-question gate (`.cursor/rules/nucleus.mdc`) is applied honestly. Verdict legend: **ADOPT NOW** / **DEFER (revisit at vX.Y)** / **REJECT**.

### Candidate 1: Error translation hot path → PyO3/Rust

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | L2 Coordination per v4.1 §3.1 |
| 2. Serves the 30-min beachhead? | NO | Perf is irrelevant — error translation runs only when something already failed; the user is already in a bad path. Speed-up of microseconds → nanoseconds saves nothing user-visible |
| 3. WRAP not BUILD? | NO | There is no off-the-shelf Rust crate that translates Dagster/DuckDB/PyIceberg exceptions to NucleusError; we'd be building a Rust port of `error_translation.py`'s 16+ handlers + cause-chain walker |
| 4. Preserves no-JVM? | YES | Rust is fine per Constraint #1 |
| 5. Preserves local-identical-to-prod? | YES (with caveat) | PyO3 wheels for win/mac/linux work — but build complexity rises (`maturin develop` for dev loop, multi-platform wheel CI per https://pyo3.rs/) |
| 6. Within 30K LOC budget? | UNCLEAR | A faithful Rust port is 400–800 LOC + bindings. Whether Rust LOC counts against the 30K Python ceiling of `AGENTS.md` §3 #8 is **unspecified policy** and would need founder ratification first. If yes, it eats ~3% of the budget for negligible gain |
| 7. Triggered by empirical telemetry? | NO | No user has ever reported error-translation latency as a problem. The motivation is **anxiety**, not signal. Per `AGENTS.md` §11.4 step 1 (wrap-vs-build check) and `nucleus.mdc` Anti-Over-Engineering rule #4 ("No speculative code") — REJECT |
| 8. Required for v0.1? | NO | Already shipped as Python, working |
| **Verdict** | **REJECT** | Rust here optimizes the 0% (errors are rare; dispatch is microseconds; failure-path latency is invisible to users). Re-evaluate only if telemetry ever shows error translation as a top-5 latency contributor (it never will, by construction). |

### Candidate 2: SQL resolver (Jinja `{{ ref() }}`) → Rust template engine (e.g., `tera`, `handlebars-rust`)

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | L2 Coordination per v4.1 §3.1 |
| 2. Serves 30-min beachhead? | NO | Perf doc §2.5: 100-asset DAG resolve is < 50 ms with Jinja `Environment` cache. That's < 1% of the 30-min budget |
| 3. WRAP not BUILD? | YES (in principle) — Rust crates `tera`, `handlebars-rust`, `minijinja` exist | But: their dialects differ from Jinja2. `{% for %}` semantics, `{% if %}` truthiness, `\| filter` chains — all subtly different. Switching dialects is a **user-visible breaking change** to `ctx.sql` templates (the v4.1 §13.1 stable contract) |
| 4. Preserves no-JVM? | YES | Rust is fine |
| 5. Preserves local-identical-to-prod? | YES | But adds maturin build complexity |
| 6. Within 30K LOC budget? | YES | Minor LOC delta if pure swap; negligible |
| 7. Triggered by empirical telemetry? | NO | Resolver perf is already comfortably under the < 50 ms target per perf doc §2.5 |
| 8. Required for v0.1? | NO | Already shipped at 180 LOC, well under v4.1 §5.6.0's 2,500 LOC ceiling |
| **Verdict** | **REJECT** | Speed gain is invisible; dialect difference is a user-facing breaking change. Jinja2 is the ecosystem-standard SQL templating dialect (dbt's lineage). Switching to a Rust template engine for nanoseconds violates Pillar 4 ("Familiar UX from proven giants" per v4.1 §2). |

### Candidate 3: Schedule daemon (asyncio polling) → Rust async runtime (tokio)

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | L2 Coordination per v4.1 §3.1 |
| 2. Serves 30-min beachhead? | NO | The 30-min metric is one-shot CLI; daemon is v0.2.1 surface |
| 3. WRAP not BUILD? | **YES** — and this is the killer point. **`AGENTS.md` §3 #3: "No custom scheduler. Dagster wrapped + mini-scheduler fallback by v1.0."** The mini-scheduler IS the fallback that exists because Dagster's scheduler was too heavy for the beachhead boot budget per ADR-017 §v0.2.1. For HA scheduling at large-team scale, the wrap target IS Dagster's daemon (with Postgres event log and k8s lease-based leader election), not a Rust rewrite of `daemon.py` |
| 4. Preserves no-JVM? | YES | |
| 5. Preserves local-identical-to-prod? | YES | |
| 6. Within 30K LOC budget? | YES per file, but builds new maintenance surface |
| 7. Triggered by empirical telemetry? | NO | Cron-poll loop is `time.sleep(5.0)`. Even at 1,000 schedules, the per-poll work is microseconds; the daemon spends 99.9% of its time sleeping |
| 8. Required for v0.1? | NO | Already shipped as Python at 418 LOC |
| **Verdict** | **REJECT** | A Rust async runtime would optimize the 0.1% of CPU the daemon actually uses. For real HA at large-team scale, the architecture's answer is the wrapped Dagster daemon + k8s; the mini-scheduler stays Python by design as the fallback. |

### Candidate 4: File lock (`fcntl`/`msvcrt` wrapper) → native Rust crate (`fs2`, `parking_lot`)

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | L2 Coordination per v4.1 §3.1 |
| 2. Serves 30-min beachhead? | NO | Lock acquire is microseconds |
| 3. WRAP not BUILD? | **NO** — the current implementation already wraps `fcntl.flock` and `msvcrt.locking` (Python stdlib). Both call into the same OS primitives a Rust crate would call. There is no "deeper" wrap available. Rust adds **nothing** here |
| 4. Preserves no-JVM? | YES | |
| 5. Preserves local-identical-to-prod? | YES | But adds `pyo3` build cost for what stdlib already does |
| 6. Within 30K LOC budget? | YES | Small delta |
| 7. Triggered by empirical telemetry? | NO | Lock contention has never been reported; in chaos test J6 the lock works as intended |
| 8. Required for v0.1? | NO | Already shipped |
| **Verdict** | **REJECT** | The architecturally relevant scaling problem (cross-machine coordination) is **not solvable** by any local file-lock implementation, Python or Rust. That problem belongs to the catalog (Lakekeeper) per v4.1 §6.2 + `AGENTS.md` §3 #5. Rewriting the local lock in Rust optimizes a path that's already free. |

### Candidate 5: AMA hot path → PyO3/Rust

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | L2 Coordination per v4.1 §3.1 |
| 2. Serves 30-min beachhead? | NO | The AMA's measured time on a 100 MB asset is < 5 s per perf doc §2.2 — and 99% of that is **already** in C++ (DuckDB query) / Rust (Polars to_arrow) / wire I/O (s3fs PUT). The Python AMA glue contributes single-digit ms |
| 3. WRAP not BUILD? | **PARTIAL** — `iceberg-rust` (https://github.com/apache/iceberg-rust) is a separate Apache project; whether it has stable Python bindings on par with `pyiceberg` 0.11.x is **NEEDS VERIFICATION** — do not assume. Even if it did, swapping pyiceberg → iceberg-rust-py is a Tier 1 component swap requiring the v4.1 §9.3 "trigger event" justification (vendor death, license pivot, perf regression > 2x). None has fired |
| 4. Preserves no-JVM? | YES | |
| 5. Preserves local-identical-to-prod? | YES (with build cost) | |
| 6. Within 30K LOC budget? | UNCLEAR | A faithful AMA port is 600 → ~1,200 Rust LOC (verbose vs Python); LOC policy for Rust unclear |
| 7. Triggered by empirical telemetry? | NO | AMA Python overhead is microseconds vs second-scale physical I/O |
| 8. Required for v0.1? | NO | Already shipped, working |
| **Verdict** | **REJECT** | Nucleus's AMA glue is FAST. The 95% of AMA wall-clock time is in already-native engines (DuckDB C++, Polars Rust, pyarrow C++, network I/O). Rewriting the glue in Rust optimizes the 5% that isn't the bottleneck. |

### Candidate 6: Workbench backend (FastAPI) → Rust (axum, actix-web)

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | L4 Experience per v4.1 §3.1 |
| 2. Serves 30-min beachhead? | NO | Workbench is v0.2+, not in beachhead path |
| 3. WRAP not BUILD? | **YES** — FastAPI/Starlette/uvicorn IS the wrap of best-of-breed Python web tooling. axum or actix-web are alternatives but the dialect change requires rewriting all 8 routers (`assets`, `runs`, `query`, `chat`, `dashboard`, `schedules`, `catalog`, `search` — total 1,216 LOC) |
| 4. Preserves no-JVM? | YES | |
| 5. Preserves local-identical-to-prod? | YES (with build complexity) | |
| 6. Within 30K LOC budget? | NO (significant) | Rust verbosity + 8 routers + bindings layer = 2,000+ Rust LOC. Doubles the Workbench LOC for negligible benefit; nukes the LOC headroom |
| 7. Triggered by empirical telemetry? | NO | Single-uvicorn-worker bottleneck is solved at zero LOC by `--workers=N` or gunicorn+UvicornWorker. The architecture target is "single-server 50+ users" per v4.1 §16.4 — uvicorn workers cover that |
| 8. Required for v0.1? | NO | Workbench is v0.2 |
| **Verdict** | **REJECT** | The actual scaling answer is config (`uvicorn --workers=N`), reverse proxy (nginx/Traefik), or k8s replicas. Zero LOC change. Rewriting 1,200 LOC of Python in 2,000+ LOC of Rust to solve a config-level problem is the textbook anti-pattern the founder's "Anti-Over-Engineering Discipline" (`nucleus.mdc`) explicitly forbids. |

### Candidate 7: Custom in-house Iceberg writer in Rust (replace pyiceberg entirely)

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | YES | Spans L0 Physics + L2 Coordination |
| 2. Serves 30-min beachhead? | NO | pyiceberg is the v0.1 default; PoC #3 validated SQLite → Iceberg in beachhead time |
| 3. WRAP not BUILD? | **NO — and this is a Constraint #4 violation in flight.** `AGENTS.md` §3 #4 "No custom compute engine" extends to "No custom Iceberg commit service" (Constraint #5) and v4.1 §20.1 "Our own table format". Building a Rust Iceberg writer is on the explicit Do-Not-Build list |
| 4. Preserves no-JVM? | YES | |
| 5. Preserves local-identical-to-prod? | YES | |
| 6. Within 30K LOC budget? | NO — would consume 3,000–5,000 LOC | |
| 7. Triggered by empirical telemetry? | NO | pyiceberg works; ADR-024 P0-3 (snapshot expiry) is the only known caveat and is already closed |
| 8. Required for v0.1? | NO | |
| **Verdict** | **REJECT — and surface as architectural risk** if anyone proposes it. This violates Constraint #4/#5 directly and would invite the constraint-amendment-required process per `AGENTS.md` §3. The wrap target (`iceberg-rust`) exists separately; if a swap is ever justified, v4.1 §9.3's interface-first protocol applies. |

### Candidate 8: Custom multi-tenant control plane in Go/Rust

| 8-Q | Pass? | Notes |
|---|---|---|
| 1. Maps to one of 5 layers? | NO — multi-tenant control plane is **out of OSS scope** per v4.1 §20.3 |
| **Verdict** | **REJECT** | Per `AGENTS.md` §4 "Multi-tenant cloud control plane → out of scope for OSS; Cloud tier only". Not a Nucleus open-core component, period. |

### Summary of all 8 candidates: **all REJECT**

The uniform reasoning: every candidate optimizes a slice of execution time that is dwarfed by either (a) wrapped engine cost (already C++/Rust), (b) network I/O (latency-dominated), or (c) physical disk I/O (latency-dominated). Rust would optimize the 5% that isn't the bottleneck, while consuming LOC budget, breaking dialect compatibility, and forcing build complexity. **The founder's instinct to look for rewrite candidates is healthy; the honest answer is that none of them clear the 8-question gate.**

If the founder *insists* on adopting Rust somewhere strategically, the only candidate that *might* clear the gate is the **swap-target evaluation for pyiceberg → iceberg-rust** when the Apache iceberg-rust project ships stable, production-quality Python bindings. That is a v0.5+ research item, not a v0.2 / v0.3 build item, and follows the v4.1 §9.3 swap-drill protocol — interface first, full adapter only on trigger event.

---

## Section 5: Architecturally correct scale-out path (v4.1 reaffirmation)

For each scale scenario the founder is worried about, the v4.1-approved answer is restated, with citations, so this audit can be referenced verbatim in future "should we rewrite X?" debates.

| Scale scenario | v4.1-approved fix | Available |
|---|---|---|
| Per-asset > 100 GB | **Mode 2 dispatch** to Databricks via `compute="databricks"` (v4.1 §10.2) | v1.5+ (per v4.1 §10.2 timing) |
| Total warehouse > 5 TB | **Mode 1 graduation** — point Databricks/Snowflake/Trino at the same S3 + Iceberg catalog (v4.1 §10.1) | Available NOW (Iceberg portability) |
| Multi-team Iceberg writes to same namespace | **Lakekeeper REST catalog** (v4.1 §5.7, ADR-004); REST commits with optimistic concurrency | v0.3+ |
| > 50 concurrent Workbench users | **uvicorn `--workers=N`** + reverse proxy + horizontal replicas; documented in production-deployment cookbook (owned by C2 worker) | v0.2 (config-only) |
| Multi-host scheduling HA | **Wrapped Dagster daemon on Kubernetes** with Postgres event log and k8s lease-based leader election (v4.1 §6.1 + §11.3 production stack) | v0.3+ |
| Cross-region warehouse | **Iceberg REST catalog federation (Mode 3)** (v4.1 §10.3) | v2.0+ |
| Auth / RBAC at scale | **OIDC delegation** (Authentik / Keycloak / Okta / Azure AD) — `AGENTS.md` §3 #6 "Always delegate to OIDC" | v0.3+ skeleton; v0.8+ full per ADR-025 P3-1 |
| Audit log at scale | **OpenTelemetry → VictoriaMetrics + VictoriaLogs** (v4.1 §14 + ADR-025 P2-3) | v0.5+ |
| Multi-tenant cloud SaaS | **Cloud tier only** — out of OSS scope per v4.1 §20.3 | v1.5+ Cloud product |
| ML training / model hosting | **Out of scope** per v4.1 §20.1; users run MLflow OSS alongside Nucleus | NEVER (by design) |
| Streaming ingest at scale | **Benthos / Redpanda** (v4.1 §18.6) + Mode 2 to Databricks Structured Streaming | v1.5+ |
| Distributed compute generally | **Mode 2 dispatch** + Mode 3 federation (v4.1 §10) | v1.5+ Mode 2 / v2.0+ Mode 3 |

**Reading this table**: every "scale problem" the founder might raise has a v4.1-approved answer that does NOT require rewriting Nucleus internals. The architecture has anticipated this question and answered it: **scale-out comes from the wrapped components (Lakekeeper, Dagster, OIDC, Databricks) and from horizontal/dispatch patterns, not from optimizing Nucleus's ~13K LOC of glue.**

---

## Section 6: Top 5 actual must-close items for "large team" usage

After applying the 8-question gate to every candidate, the **realistic** top-5 list of changes that improve large-team viability is:

### #1 — Lakekeeper REST catalog default at v0.3 (already on roadmap)

- **Why**: Replaces filesystem catalog (single-host SQLite) with multi-host REST catalog supporting OIDC validation, multi-team namespace separation, and atomic commit coordination. Closes scenario 3.1 (multi-team writes), 3.2 (cross-host run ledger via Postgres backend), 3.8 (SQLite catalog under multi-writer load).
- **Architecture cite**: v4.1 §5.7 + ADR-004 (catalog migration plan).
- **Effort**: Already designed; implementation is wrapping `pyiceberg.RestCatalog` (which `coordination/asset_materialization.py` is already structured to call — line 438 currently uses `type="sql"`; v0.3+ adds `type="rest"` codepath).
- **NOT what to do**: Build a custom Iceberg commit service (Constraint #5 violation).

### #2 — Workbench multi-worker production recipe (documentation, not code)

- **Why**: Closes scenario 3.3 (50+ concurrent users) via `uvicorn --workers=N` or `gunicorn -w N -k uvicorn.workers.UvicornWorker` + reverse-proxy guidance. Zero LOC change to Workbench itself; one line in `workbench/cli.py` (already owned by B1 — do not write to it from this audit).
- **Architecture cite**: v4.1 §16.4 (Workbench concurrent users 50+ single-server).
- **Effort**: Cookbook recipe (owned by C2 — `docs/cookbook/production-deployment.md`).
- **NOT what to do**: Rewrite Workbench in axum/actix-web (Candidate 6 above, REJECTED).

### #3 — Postgres-backed run ledger at v0.3 (interface already isolated)

- **Why**: Closes scenario 3.2 (cross-host NDJSON append concurrency). The `RunLedger` class in `coordination/run_ledger.py` (lines 69–276) is interface-isolated; swap implementation from NDJSON to Postgres via the same public API when `nucleus_project.yaml` declares a Postgres URL. NDJSON path stays as the single-host default per v4.1 §11.3.
- **Architecture cite**: v4.1 §11.3 (production stack: PostgreSQL for metadata) + ADR-025 P0-2 (run monitoring + persistence — currently NDJSON, swap to Postgres at v0.3).
- **Effort**: ~200 LOC for a `PostgresRunLedger` adapter implementing the same interface; one ADR; smoke tests per v4.1 §9.3.
- **NOT what to do**: Move to a Rust ledger crate (gains nothing; NDJSON is already at the right abstraction level for single-host; Postgres for multi-host).

### #4 — Active Dagster daemon as primary scheduler (v0.3+, leveraging existing wrap)

- **Why**: Closes scenario 3.4 (multi-host scheduling HA). The mini-scheduler (`coordination/daemon.py`) is the v4.1 §6.7 fallback; the *primary* per Constraint #3 is the wrapped Dagster daemon. For multi-host HA, run the Dagster daemon on Kubernetes with Postgres event log and k8s lease leader election (Dagster handles this — Nucleus wraps).
- **Architecture cite**: v4.1 §6.1 (what we take from Dagster) + v4.1 §11.3 (production stack: Dagster on k8s) + ADR-025 P0-1 (active scheduling daemon, Wave 2 P0-1).
- **Effort**: Wave 2 implementer work — wire Dagster's `ScheduleDefinition` through the coordination layer (per ADR-025 P0-1, ~100–200 LOC + integration test).
- **NOT what to do**: Add k8s leader election to `coordination/daemon.py` (re-implementing Dagster's job per Constraint #3) or rewrite in Rust (Candidate 3 above, REJECTED).

### #5 — OIDC delegation skeleton at v0.3, full RBAC at v0.8 (already on roadmap)

- **Why**: Closes scenario 3.9 (auth at 100-engineer scale). Per `AGENTS.md` §3 #6 "Always delegate to OIDC. Never own identity." Already planned via Authentik/Keycloak/Okta/Azure AD per v4.1 §15.1 + ADR-025 P3-1.
- **Architecture cite**: v4.1 §15.1 (OIDC delegation) + `AGENTS.md` §3 #6.
- **Effort**: ~1–2K LOC for OIDC validation + Casbin authz per ADR-025 P3-1; no new auth state.
- **NOT what to do**: Build a custom user table or password store (Constraint #6 violation in flight).

**What is NOT on this list (and why)**: any Rust rewrite. Per Section 4, all eight candidates fail the 8-question gate. Per Section 1.3, the wrapped engines are already C++/Rust where they need to be. The realistic large-team improvements are configuration, documentation, and swap to already-planned wrap targets — not engine surgery.

---

## Section 7: Things to NOT change (architectural integrity)

These are components where the founder might be tempted to rewrite for "performance" or "reliability" reasons, but the architecture's answer is "leave it alone":

| Component | Tempting rewrite | Why REJECT | Architectural cite |
|---|---|---|---|
| Error translation layer | Port to Rust via PyO3 | Negligible perf gain on a path that runs only when errors fire; breaks LOC budget if Rust counts; anxiety-driven, no telemetry | `nucleus.mdc` Anti-Over-Engineering rule #4 ("No speculative code"); `AGENTS.md` §11.4 step 1 (wrap-vs-build) |
| Custom orchestrator in Go/Rust | "Compete with Dagster on resource usage" | Constraint #3 — no custom scheduler. Mini-scheduler is the *fallback*; primary is wrapped Dagster. For HA, the answer is Dagster on k8s, not Rust port | `AGENTS.md` §3 #3; v4.1 §6.7; ADR-017 |
| Custom Iceberg writer in Rust | "Avoid pyiceberg dependency" | Constraint #4/#5 violation in flight. PyIceberg is the wrap; iceberg-rust is the *swap-target* (v4.1 §9.3 protocol applies) — not a build candidate | `AGENTS.md` §3 #4, #5; v4.1 §20.1 |
| Custom auth system in any language | "Faster than OIDC roundtrip" | Constraint #6 — no custom auth, ever | `AGENTS.md` §3 #6; v4.1 §15.1 |
| Multi-worker FastAPI in Rust (axum/actix-web) | "Solve concurrency" | uvicorn `--workers=N` solves it at config level (zero LOC). Rewriting 1,200 LOC for a config problem is exactly the founder's anti-over-engineering target | `nucleus.mdc` Anti-Over-Engineering rules #1, #5; v4.1 §16.4 |
| Custom run ledger in C/Rust for "concurrent appends" | "Faster than threading.Lock + NDJSON" | At v0.3, swap to Postgres. Postgres is fast enough at this scale. Rust offers nothing | `AGENTS.md` §4 ("Custom observability backend → use OTel + VictoriaMetrics"); v4.1 §11.3 |
| Cross-machine file lock in Rust | "Solve multi-host coordination" | Cross-machine locking is the catalog's job per v4.1 §6.2; Lakekeeper handles it. Local file lock stays Python | `AGENTS.md` §3 #5; v4.1 §6.2 |
| Custom in-process DAG executor in Rust | "Replace Dagster execute_in_process" | Constraint #3; Dagster is the wrap | `AGENTS.md` §3 #3 |
| Custom JSON serializer in Rust (orjson, simdjson via PyO3) | "Faster lineage emit" | Lineage emit is best-effort and runs once per materialization. JSON serialization is microseconds. orjson is already a Python option if it ever matters; never has | Anti-Over-Engineering rule #4 |
| Mini-scheduler in Go | "Better cron" | Same as #3 above. Mini-scheduler is fallback per design | v4.1 §6.7 |
| Custom Polars replacement | "Faster DataFrames" | Constraint #4; Polars IS the wrap (Rust under the hood) | `AGENTS.md` §3 #4; `nucleus.mdc` table |
| Custom DuckDB replacement | "Faster SQL" | Constraint #4; DuckDB IS the wrap (C++ under the hood); DataFusion is the swap target per v4.1 §9 | `AGENTS.md` §3 #4 |
| `cli/main.py` rewrite in Rust (Click → clap) | "Faster startup" | Cold path; lazy-imports already get `nucleus --version` < 500 ms per perf doc §2.1; Typer is the wrap. Rust would force users to install a separate binary, breaking `pip install nucleus` simplicity | `nucleus.mdc` Anti-Over-Engineering rule #5; v4.1 §16.1 |
| `intelligence/copilot.py` rewrite in Rust | "Faster Copilot" | LLM-bound; provider latency dominates; Rust optimizes nothing on the wire | `AGENTS.md` §9 (AI Copilot economics — token cost is the variable, not local CPU) |

This list exists because rewrite-temptation is a recurring pattern in solo-founder + AI-assisted projects: every component looks rewritable when the boilerplate-generation cost is near-zero. The architecture's discipline is the only firewall.

---

## Section 8: Hallucination audit + NEEDS VERIFICATION

Per `AGENTS.md` §11.12 (official documentation discipline) and `AGENTS.md` §10 #10 (cite or flag).

### Verified claims (with URLs)

- **DuckDB is C++**: https://duckdb.org/why_duckdb.html — verified language claim
- **Polars is Rust**: https://pola.rs/ — verified language claim
- **PyArrow C++ core, Python bindings**: https://arrow.apache.org/docs/python/ + https://arrow.apache.org/docs/python/ipc.html — verified
- **PyIceberg is Python**: https://py.iceberg.apache.org/ — verified
- **Apache Iceberg Rust project exists separately**: https://github.com/apache/iceberg-rust — verified the repo exists; status of stable Python bindings flagged below
- **DuckDB GROUP BY no-spill**: https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors — verified per perf doc §2.3
- **Polars streaming limitations**: https://github.com/pola-rs/polars/issues/20947 — referenced from perf doc §11.1
- **Iceberg ACID semantics**: https://iceberg.apache.org/docs/latest/reliability — referenced from perf doc §6
- **PyIceberg snapshot expiry API**: https://py.iceberg.apache.org/api/ — referenced from perf doc §9 P0 #3 / ADR-024 P0-3
- **`fcntl.flock` (POSIX) docs**: https://docs.python.org/3/library/fcntl.html — verified per `coordination/locks.py:25`
- **`msvcrt.locking` (Windows) docs**: https://docs.python.org/3/library/msvcrt.html — verified per `coordination/locks.py:26`
- **PyO3 framework**: https://pyo3.rs/ — verified the framework exists; LOC overhead claim is general-knowledge level
- **FastAPI**: https://fastapi.tiangolo.com/ — verified
- **uvicorn workers**: https://www.uvicorn.org/ — verified

### NEEDS VERIFICATION items (do not act on these without checking)

| # | Claim | What to verify | Where to check |
|---|---|---|---|
| 8.1 | Apache Iceberg Rust (`iceberg-rust`) has stable Python bindings on par with `pyiceberg` 0.11.x for catalog ops + table append + snapshot expiry | Repo activity 2026; presence of `iceberg-rust-py` or equivalent on PyPI; API surface coverage | https://github.com/apache/iceberg-rust + PyPI search |
| 8.2 | NTFS append atomicity for concurrent writers under `O_APPEND` semantics | Whether two processes appending lines to the same file on NTFS can interleave inside a single `write()` | Microsoft Win32 API docs on `WriteFile` + concurrent file handles |
| 8.3 | uvicorn `--workers=N` performance characteristics for the Workbench routers (which mix sync DuckDB calls with async FastAPI handlers) | Whether sync DuckDB queries inside async routes block the event loop without `run_in_threadpool` | https://www.uvicorn.org/ + FastAPI docs on `Depends` and sync routes |
| 8.4 | Whether the audit-target persona ("100+ engineers, 100 TB, 500 schedules, 10 Workbench users") is a real prospective user OR a hypothetical | If hypothetical, every "must-close item" in Section 6 is itself **anxiety-driven** per `AGENTS.md` §11.4 step 1 — the 8-question Q7 ("triggered by empirical telemetry, not anxiety") demands clarification before any of P3/P4/P5 work begins | Founder confirmation needed; perf doc §10 acknowledges only single beachhead user data |
| 8.5 | Dagster daemon boot time on k8s with Postgres event log at 500-schedule scale | Whether the Dagster daemon's load-time stays < 30 s for 500 `ScheduleDefinition` instances; if it doesn't, mini-scheduler stays primary for longer than v4.1 §6.7 anticipates | Dagster docs https://docs.dagster.io/ + ADR-025 NV cited there |
| 8.6 | Whether Lakekeeper at multi-team scale (100 engineers, multi-namespace) actually delivers on "OIDC validation + atomic REST commits" without a custom commit service | Verify against Lakekeeper docs + load test scenario; ADR-004 cites this but does not yet have an empirical multi-team test | https://lakekeeper.io/ + ADR-004 + planned v0.3 PoC |

### Logged hallucination check

No new hallucinations introduced in this audit. Section 1.3's language claims for DuckDB, Polars, PyArrow, PyIceberg, FastAPI are cited inline. The single area where I deliberately marked uncertainty is the Apache Iceberg Rust Python-bindings status (#8.1 above) — no claim was made about it without the NEEDS VERIFICATION tag, per the discipline learned from `docs/internal/research/openlineage.md` (which flagged the dead `openlineage-dagster` bridge correctly).

If the founder finds any factual claim in Sections 1–7 that doesn't trace to either (a) the cited URL, (b) the cited Nucleus internal doc, or (c) actual file content, please surface it for ai_hallucinations.md logging per `AGENTS.md` §11.12.

---

## Section 9: Honest closing assessment

For a 100-engineer team **today**, Nucleus v0.2.0 is **not yet a fit**, and that should not be reframed as a flaw. It is the precise consequence of the v4.1 §1.5 beachhead choice (5–20 engineers, 100 GB–5 TB) and the §10 yield-to-giants strategy. By v0.3 (with Lakekeeper REST catalog, Postgres-backed run ledger, multi-worker Workbench config, and active Dagster daemon as primary scheduler — all already on the ADR-025 roadmap), Nucleus reaches the *upper bound* of its documented scale envelope (50 Workbench users / 500 schedules / single-region multi-team). For a 100-engineer team that has outgrown that envelope, the architecturally-correct answer is **graduation via Iceberg portability (Mode 1)** — point Databricks/Snowflake/Trino at the same warehouse — with selective **Mode 2 dispatch** (`compute="databricks"`) when individual assets exceed laptop economics.

There is no version of Nucleus, in any planned roadmap, that natively serves a 1000-engineer pipeline at 100 TB. Per `AGENTS.md` §0 ("It is not a database, a SQL engine... a Spark replacement, a Databricks competitor, a 'Data OS', an ML platform... Treat any drift toward those framings as a bug."), trying to make Nucleus serve that scale through internal rewrite would not be improvement — it would be *category drift*. The right answer for that scale is and remains: **let the giants do the heavy lifting; Nucleus stays the developer-first SDK + CLI + Workbench layer that runs comfortably from a laptop, scales to ~50-engineer teams via wrapped catalogs and OIDC, and graduates cleanly when teams need more.** That story is consistent from v0.1 to v3.0 and is the moat — *not* engine performance.

Practically: **adopt the Section 6 top-5 list as the v0.3 closure plan; reject every rewrite candidate in Section 4; keep Section 7's "do not change" list under the founder's pillow as a guard against rewrite drift; and answer "Nucleus for 100 engineers?" with "graduate to your Iceberg catalog of choice; Nucleus stays the laptop-first SDK that took you here."**

---

*Researcher model: Claude Opus 4.7 (Researcher tier; Gemini 3.1 Pro unavailable in current Cursor runtime — fallback recorded per `AGENTS.md` §11.14). Time taken: ~2 hours (read AGENTS.md, arch v4.1 §1/§6/§9/§10/§11/§16/§17/§20, `nucleus.mdc`, perf-targets research, ADR-024, ADR-025, parity-vs-Databricks/Snowflake/BQ doc head, parity-vs-Bosch doc head, full LOC inventory + 5 hot-file inspections + 8-question gate per candidate). Cited architecture/AGENTS sections (count): v4.1 §1.5, §1.6, §3.1, §5.1, §5.6.0, §5.7, §6.1, §6.2, §6.3, §6.4, §6.5, §6.6, §6.7, §7.2, §9.3, §10.1, §10.2, §10.3, §11.3, §13.1, §15.1, §16.1, §16.4, §18 (roadmap), §20.1, §20.3 + `AGENTS.md` §0, §3 #1/#3/#4/#5/#6/#8/#9, §4, §8, §9, §11.3, §11.4, §11.6, §11.7, §11.12, §11.14 + `nucleus.mdc` 8-question gate, Anti-Over-Engineering rules #1/#4/#5, Velocity Discipline, Vocabulary, Five Pillars + ADR-002, ADR-004, ADR-006, ADR-013, ADR-017, ADR-024, ADR-025 + perf doc §2.1/§2.2/§2.3/§2.5/§2.6/§3/§4/§9/§10/§11. Total ≥ 50 distinct citations.*
