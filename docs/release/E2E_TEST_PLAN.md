# Nucleus v0.2 Final E2E Test Plan

> **Status**: DRAFT — created by release-planner builder 2026-05-15  
> **Version target**: v0.2.0  
> **Owner**: Release planner (foreground reconciles after Wave-1 returns)  
> **References**: `nucleus_architecture_v4.1.md` §1.5 (beachhead metric), `nucleus_cli_spec.md` §3–§8, `nucleus_ctx_sdk_spec.md` §2–§12, `AGENTS.md` §11.8

---

## Scope + Acceptance Criteria

**Persona**: 5-engineer startup, MacBook/Linux laptop, 100 GB–5 TB total data, greenfield project (beachhead §1.5).

**Primary acceptance criteria**:
- ALL Suite A, B (all 8), C, H, I scenarios PASS on both WSL (Ubuntu 22.04) and Windows native venv (Python 3.11)
- ≥ 95% of Suite D, E, F, G, K scenarios PASS
- ≥ 80% of Suite J chaos scenarios PASS (some require Docker infra)
- Zero CRITICAL or HIGH severity findings (error-class leaks, exit-code violations, governance failures)
- Cold boot (v0.1.0 baseline: **5.82s** WSL) remains < **10s** per `nucleus_cli_spec.md` §3.2; `nucleus --version` < **1.5s**; Suite K perf targets met

**CI execution matrix**:

| Environment | Suite priority | Notes |
|---|---|---|
| WSL Ubuntu 22.04 (primary) | All suites | gate for merge |
| Windows native venv (Python 3.11) | Suite A, B, H, I mandatory | regression for merge |
| macOS (Python 3.11) | Deferred to community / PoC #5 external testers | manual only |
| Python 3.12 | Suite I only (governance scripts) | bonus signal |

**Pass/fail criteria for v0.2.0 release**:
- 100% Suite A, B, C, H, I — hard gate
- ≥ 95% Suite D, E, F, G, K — soft gate with documented exceptions
- ≥ 80% Suite J — soft gate; chaos infra gaps documented
- Zero external classnames in any user-visible string (dagster_leak_check.py)
- All 8 governance scripts EXIT 0

---

## Suite A: Boot + Lifecycle (10 scenarios)

### A1. `nucleus version` — cold boot latency

**Setup**: fresh shell, no subprocess caching  
**Steps**: time `nucleus version` wall-clock  
**Expected**: exits 0; prints nucleus + duckdb + polars + pyiceberg + dagster version table  
**Acceptance**: elapsed < 1.5 s wall-clock (measured via `time` / `perf_counter`)  
**Cleanup**: none  
**Governance check**: no Dagster/DuckDB/Polars classnames in output  
**Ref**: `nucleus_cli_spec.md` §3.7; v4.1 §11.2

### A2. `nucleus --help` — response time

**Setup**: fresh shell  
**Steps**: time `nucleus --help` wall-clock  
**Expected**: exits 0; prints command table including init/up/down/run/ingest/query/version/chat/schedule  
**Acceptance**: elapsed < 500 ms; all 8 primary commands listed  
**Cleanup**: none

### A3. `nucleus init my_project` — scaffold creation

**Setup**: empty temp directory  
**Steps**: `nucleus init my_project`; verify file tree  
**Expected**: exits 0; creates `my_project/` with `nucleus_project.yaml`, `assets/__init__.py`, `assets/example.py`, `data/.gitkeep`, `.gitignore`, `README.md`  
**Acceptance**: all 6 TEMPLATE_FILES present (per `beachhead_e2e.py:25`); `nucleus_project.yaml` valid YAML with `project.name`, `catalog`, `storage` keys  
**Cleanup**: `rm -rf my_project`  
**Ref**: `nucleus_cli_spec.md` §3.1; beachhead_e2e.py step 3

### A4. `nucleus init` — idempotency (existing directory)

**Setup**: run `nucleus init my_project` once  
**Steps**: run `nucleus init my_project` again  
**Expected**: exits 1 with `NucleusIOError` (NE1005); user_message mentions "non-empty"; no files overwritten  
**Acceptance**: second run does NOT destructively overwrite original files; exit 1  
**Cleanup**: `rm -rf my_project`  
**Ref**: `nucleus_cli_spec.md` §3.1 "Error exits"

### A5. `nucleus up` — starts MinIO within 30 s

**Setup**: initialized project; Docker daemon running  
**Steps**: `nucleus up` in project dir; capture stdout  
**Expected**: exits 0; stdout contains `✓ MinIO ready`, `✓ Catalog ready`, `✓ Definitions loaded`; `Nucleus up in <N>s.`  
**Acceptance**: N ≤ 10 s (cold); `docker ps` shows minio container; no Dagster classnames in output  
**Cleanup**: `nucleus down`  
**Ref**: `nucleus_cli_spec.md` §3.2; v4.1 §11.2 / §16.1

### A6. `nucleus down` — stops cleanly within 5 s

**Setup**: `nucleus up` complete  
**Steps**: time `nucleus down`  
**Expected**: exits 0; `Nucleus down. Volumes: preserved.`; no Docker container running  
**Acceptance**: elapsed < 5 s; exit 0 even if already down (idempotent per spec §3.3)  
**Cleanup**: none  
**Ref**: `nucleus_cli_spec.md` §3.3

### A7. `nucleus up` → `nucleus down` → `nucleus up` — cycle stress

**Setup**: initialized project  
**Steps**: up; down; up; verify final state  
**Expected**: second `up` succeeds without port conflicts or catalog corruption  
**Acceptance**: exit 0 on second up; `✓ Definitions loaded` present; catalog.db unchanged from first up  
**Cleanup**: `nucleus down`

### A8. `nucleus_project.yaml` strict validation — rejects malformed config

**Setup**: project with intentionally malformed `nucleus_project.yaml` (missing `project.name`)  
**Steps**: `nucleus up` or `nucleus run`  
**Expected**: exits 1 with `NucleusConfigError` or equivalent; user_message states which field is missing; fix_hint provided  
**Acceptance**: exit 1; no Dagster classnames; YAML parse error surfaced cleanly  
**Ref**: `nucleus_cli_spec.md` §7

### A9. `nucleus list` — enumerates registered assets

**Setup**: initialized project with `assets/example.py` loaded  
**Steps**: `nucleus list`  
**Expected**: exits 0; lists at minimum `example.greeting` (or the scaffold asset key)  
**Acceptance**: output contains at least one asset key matching `<namespace>.<name>` pattern  
**Ref**: v4.1 §12.1 asset key format (2-level for v0.1)

### A10. `nucleus describe <asset>` — shows schema + snapshot + lineage

**Setup**: project with a materialized asset  
**Steps**: `nucleus describe example.greeting`  
**Expected**: exits 0; output includes asset key, schema (column names/types), last snapshot timestamp, lineage deps  
**Acceptance**: all four sections present; no Dagster/Iceberg classnames in output  
**Ref**: `nucleus_ctx_sdk_spec.md` §3.1 `ctx.asset`

---

## Suite B: Materialization (8 scenarios)

### B1. Empty asset materialize — snapshot created, 0 rows

**Setup**: project with an asset that returns `pl.DataFrame({"id": [], "name": []})`  
**Steps**: `nucleus run empty_test.zero_rows`  
**Expected**: exit 0; `MaterializationResult` with `row_count=0`; Iceberg snapshot created in `.nucleus/`  
**Acceptance**: `.nucleus/catalog.db` contains table entry; snapshot_id non-empty  
**Ref**: `nucleus_ctx_sdk_spec.md` §5.1; `nucleus_architecture_v4.1.md` §6.2

### B2. 1k-row asset materialize — snapshot, schema enforced

**Setup**: asset returning 1,000-row Polars DataFrame with typed columns (int, str, date)  
**Steps**: `nucleus run small_test.orders_1k`  
**Expected**: exit 0; `row_count=1000`; Iceberg schema matches declared table columns  
**Acceptance**: DuckDB `iceberg_scan` confirms 1,000 rows; column types match spec

### B3. 100k-row materialize via Polars LazyFrame — memory < 1 GB peak

**Setup**: asset returning `pl.scan_csv(...)` LazyFrame of 100k rows  
**Steps**: `nucleus run perf_test.large_asset`; measure peak RSS via `psutil`  
**Expected**: exit 0; peak RSS ≤ 1 GB; duration ≤ 30 s  
**Acceptance**: `MaterializationResult.row_count == 100000`  
**Ref**: v4.1 §16.1 (performance targets)

### B4. Dependent asset chain (A → B → C) — topological order

**Setup**: three assets with explicit deps: C reads from B, B reads from A  
**Steps**: `nucleus run --all`  
**Expected**: materializes in order A → B → C; no `NucleusAssetNotMaterialized` errors  
**Acceptance**: exit 0; three `MaterializationResult` records in correct order  
**Ref**: `nucleus_ctx_sdk_spec.md` §4.2 (auto-dependency tracking)

### B5. `nucleus run --dry-run` — resolves DAG, prints plan, NO writes

**Setup**: project with 3-asset chain  
**Steps**: `nucleus run --dry-run --all`  
**Expected**: exit 0; prints execution plan (asset keys in topo order); ZERO Iceberg snapshots created  
**Acceptance**: `.nucleus/` snapshot files unchanged after dry-run; output contains "dry-run" or "plan"  
**Ref**: `nucleus_cli_spec.md` §3.4

### B6. `nucleus run --resume` — from failed checkpoint

**Setup**: asset that fails on first row batch but not second; prior run logged in `.nucleus/runs/`  
**Steps**: `nucleus run --resume <run_id>`  
**Expected**: picks up from last successful checkpoint; completes successfully  
**Acceptance**: exit 0; no duplicate rows in output; `row_count` is additive only  
**Note**: May require Wave-1 run-state persistence feature. Mark SKIPPED if not implemented.

### B7. Concurrent `nucleus run` — against same asset (lock test)

**Setup**: two terminals, same project  
**Steps**: start `nucleus run slow_asset.compute` in background; immediately run same command in foreground  
**Expected**: second invocation fails with `NucleusCommitConflictError` (NE1002) or queues; does NOT corrupt snapshot  
**Acceptance**: exit 1 or 0 (queue); no partial snapshot; atomicity preserved  
**Ref**: `nucleus_architecture_v4.1.md` §6.2 step 3 (atomic commit)

### B8. Schema-contract violation — clean NE2006

**Setup**: asset with `@nucleus.contract` requiring `amount > 0`; asset body returns rows with negative amounts  
**Steps**: `nucleus run contract_test.orders_with_negatives`  
**Expected**: exit 5 (schema/contract per `nucleus_cli_spec.md` §8); `NucleusCheckExecutionError` (NE3007 per AGENTS.md cleanup); user_message describes which check failed; no partial write  
**Acceptance**: no Iceberg snapshot committed; exit code = 5  
**Ref**: `nucleus_ctx_sdk_spec.md` §2.4 `@nucleus.check`; `nucleus_cli_spec.md` §8

---

## Suite C: Query (6 scenarios)

### C1. `nucleus query "SELECT 1"` — basic connectivity

**Setup**: `nucleus up` running  
**Steps**: `nucleus query "SELECT 1 AS one"`  
**Expected**: exit 0; output contains `1` row with value `1`  
**Acceptance**: exit 0; no Dagster/DuckDB classnames in output  
**Ref**: `nucleus_cli_spec.md` §3.6; `nucleus_ctx_sdk_spec.md` §6.1

### C2. `nucleus query` — against materialized asset

**Setup**: `raw.users` asset materialized (3 rows via ingest)  
**Steps**: `nucleus query "SELECT count(*) AS cnt FROM raw.users"`  
**Expected**: exit 0; output contains `3`  
**Acceptance**: count matches materialized row count

### C3. `nucleus query --format csv` — exports to stdout

**Setup**: materialized asset with known rows  
**Steps**: `nucleus query --format csv "SELECT id, name FROM raw.users"`  
**Expected**: exit 0; stdout is valid CSV (header row + data rows); color/Rich suppressed  
**Acceptance**: CSV parseable; column names match schema  
**Ref**: `nucleus_cli_spec.md` §5.2

### C4. `nucleus query --format parquet path.parquet` — exports to file

**Setup**: materialized asset  
**Steps**: `nucleus query --format parquet /tmp/result.parquet "SELECT * FROM raw.users"`  
**Expected**: exit 0; `/tmp/result.parquet` created and readable by pyarrow  
**Acceptance**: `pyarrow.parquet.read_table("/tmp/result.parquet").num_rows > 0`

### C5. SQL injection attempt — Jinja autoescape

**Setup**: `nucleus up` running  
**Steps**: `nucleus query "SELECT * FROM {{ ref('raw.users'); DROP TABLE raw.users; --') }}"`  
**Expected**: exit 1 with `NucleusSQLSyntaxError` (NE2002); `raw.users` table unaffected  
**Acceptance**: Jinja renderer rejects the malformed ref call; exit 1; no data loss  
**Ref**: `nucleus_cli_spec.md` §3.6; `nucleus_ctx_sdk_spec.md` §6.1

### C6. Large result set — 1M rows streamed without OOM

**Setup**: asset with 1M rows materialized  
**Steps**: `nucleus query --no-page "SELECT count(*) FROM large_test.million_rows"`  
**Expected**: exit 0; count = 1,000,000; peak RSS ≤ 2 GB  
**Acceptance**: query completes without `NucleusResourceError` (NE2003)  
**Note**: Mark SKIPPED if 1M-row fixture not available; run as `@pytest.mark.slow`

---

## Suite D: Ingest (10 scenarios)

### D1. Postgres → Iceberg — happy path

**Setup**: Postgres test container (Docker); 1k-row `public.users` table  
**Steps**: `nucleus ingest postgres://test:test@localhost:5432/testdb --table public.users --as raw.users --mode overwrite`  
**Expected**: exit 0; Iceberg snapshot with 1,000 rows; 10-row preview printed  
**Acceptance**: `nucleus query "SELECT count(*) FROM raw.users"` = 1000  
**Ref**: `nucleus_cli_spec.md` §3.5; `docs/recipes/postgres_to_iceberg.md`

### D2. Postgres — bad credentials → clean NE2003 + fix_hint

**Setup**: no Postgres running; bad DSN  
**Steps**: `nucleus ingest postgres://bad:creds@localhost:5432/db --table users --as raw.users`  
**Expected**: exit 1; `NucleusSourceConnectionError` (NE1001); user_message mentions connection failed; fix_hint suggests checking host/credentials; NO stack trace in default mode  
**Acceptance**: exit 1; fix_hint present; no "sqlalchemy" or "psycopg" in output  
**Ref**: ADR-006 H1+H17; `nucleus_cli_spec.md` §5.4

### D3. Postgres — unreachable host → clean NE1001

**Setup**: host address that doesn't resolve  
**Steps**: `nucleus ingest postgres://user:pass@10.255.255.255:5432/db --table t --as raw.t`  
**Expected**: exit 4 (network error per `nucleus_cli_spec.md` §8); `NucleusSourceConnectionError` NE1001; fix_hint with timeout suggestion  
**Acceptance**: exit 4; no raw Python traceback; user_message actionable

### D4. MySQL → Iceberg — happy path

**Setup**: MySQL test container; `orders` table with 500 rows  
**Steps**: `nucleus ingest mysql://test:test@localhost:3306/testdb --table orders --as raw.orders`  
**Expected**: exit 0; 500 rows in Iceberg snapshot  
**Acceptance**: count matches  
**Ref**: Worker B (`copy_from_mysql.py`) promoted in v0.1.1

### D5. S3 Parquet → Iceberg — happy path (moto mock)

**Setup**: moto mock S3 bucket with test Parquet file  
**Steps**: `nucleus ingest s3://test-bucket/data/orders.parquet --as raw.orders_parquet`  
**Expected**: exit 0; rows from Parquet file in Iceberg snapshot  
**Note**: Requires `moto[s3]` in test environment; mock S3 endpoint via `MINIO_ENDPOINT` override

### D6. GCS Parquet → Iceberg — happy path (mocked)

**Setup**: GCS mock (e.g., `google-cloud-storage` test harness) or MinIO with GCS-compatible API  
**Steps**: `nucleus ingest gs://test-bucket/data.parquet --as raw.gcs_test`  
**Expected**: exit 0; snapshot created  
**Note**: Requires GCS mock; may remain SKIPPED if infra not available in CI

### D7. Filesystem CSV → Iceberg — happy path

**Setup**: local CSV file with 100 rows  
**Steps**: `nucleus ingest ./test_data/users.csv --as raw.csv_users`  
**Expected**: exit 0; 100 rows in snapshot; schema inferred from CSV header  
**Ref**: `nucleus_cli_spec.md` §3.5 "Sources (v0.1)"

### D8. Filesystem glob → Iceberg — mixed schema → NE2004

**Setup**: two CSV files with different column sets in same directory  
**Steps**: `nucleus ingest "./test_data/*.csv" --as raw.mixed`  
**Expected**: exit 5 (`NucleusSchemaError` NE2001 or `NucleusSchemaEvolutionError` NE2004); user_message describes conflicting schemas  
**Acceptance**: exit 5; no partial Iceberg write  
**Ref**: `nucleus_architecture_v4.1.md` §6.2 step 1 (validate)

### D9. Snowflake → Iceberg — mocked

**Setup**: mocked Snowflake connector (stub DSN returning test data)  
**Steps**: `nucleus ingest snowflake://user:pass@account/db/schema --table orders --as raw.sf_orders`  
**Expected**: exit 0 (mock) or exit 1 with `NucleusSourceConnectionError` if connector not yet implemented  
**Note**: SKIPPED if Snowflake connector is v0.3+ deferred

### D10. `nucleus ingest --preview N` — shows N rows without commit

**Setup**: Postgres with 1k rows  
**Steps**: `nucleus ingest postgres://... --table users --as raw.users --preview 5`  
**Expected**: exit 0; prints 5-row preview table; NO Iceberg snapshot created; NO write to catalog  
**Acceptance**: preview rows printed; `.nucleus/` unchanged from before; idempotent on second run  
**Note**: `--preview` flag must be implemented; SKIPPED if not yet wired

---

## Suite E: Scheduling (5 scenarios)

### E1. `nucleus schedule list` — enumerates registered schedules

**Setup**: project with at least one asset decorated `schedule="@daily"`  
**Steps**: `nucleus schedule list`  
**Expected**: exit 0; table showing asset key, cron expression, next run time (UTC)  
**Acceptance**: at minimum one row; cron format valid per croniter  
**Ref**: `nucleus_cli_spec.md` §3.9; ADR-017

### E2. `nucleus schedule preview <asset>` — shows next 5 runs

**Setup**: asset with `schedule="0 2 * * *"` (daily at 02:00 UTC)  
**Steps**: `nucleus schedule preview my_asset.daily_orders --count 5`  
**Expected**: exit 0; 5 future datetimes listed, all at 02:00 UTC, consecutive days  
**Acceptance**: datetimes are monotonically increasing; no Dagster daemon required for preview  
**Ref**: `nucleus_cli_spec.md` §3.9 (croniter-based, no daemon)

### E3. Sub-second cron expression — rejected at decoration time

**Setup**: asset with `schedule="* * * * * *"` (6-field sub-minute, invalid for 5-field croniter)  
**Steps**: `python -c "import nucleus; @nucleus.asset(table='t', schedule='* * * * * *') def t(ctx): pass"`  
**Expected**: `NucleusScheduleParseError` (NE5005) raised on import; clear message  
**Acceptance**: fails at decoration (import time), not at runtime  
**Ref**: `nucleus_ctx_sdk_spec.md` §2.1 `schedule=` kwarg; ADR-017

### E4. DST transition — Spring-forward handled correctly

**Setup**: schedule with `schedule="0 2 * * *"` in `America/New_York` timezone  
**Steps**: `nucleus schedule preview dst_test.spring_forward --count 6` spanning 2026-03-08 (clocks spring forward)  
**Expected**: no duplicate or missing 02:00 run; gap at missing hour handled per croniter DST logic  
**Acceptance**: 6 consecutive datetimes; no crash; correct UTC offsets  
**Ref**: `docs/architecture/sequence_swap_drill.md` DST section; croniter docs

### E5. Timezone-aware schedules — respect tz offset

**Setup**: asset with `schedule="0 9 * * 1"` (Monday 09:00) and timezone `Asia/Ho_Chi_Minh` (UTC+7)  
**Steps**: `nucleus schedule preview tz_test.morning_report --count 3`  
**Expected**: next runs at Monday 02:00 UTC (= 09:00 ICT)  
**Acceptance**: UTC times in output are 7 hours behind the declared local time

---

## Suite F: Workbench UI (8 scenarios)

### F1. `nucleus workbench up` — serves on localhost:8080

**Setup**: initialized project; workbench dependencies installed (`pip install nucleus[workbench]`)  
**Steps**: `nucleus workbench up` (or `nucleus up` if workbench auto-starts)  
**Expected**: exit 0 (background process); GET `http://localhost:8080/` returns 200  
**Acceptance**: HTTP 200 within 10 s of command  
**Ref**: ADR-016 (Workbench Fork B scaffold); `src/nucleus/workbench/app.py`

### F2. GET /api/dashboard/summary — valid JSON

**Setup**: Workbench running with at least one materialized asset  
**Steps**: `curl http://localhost:8080/api/dashboard/summary`  
**Expected**: HTTP 200; JSON with `{"assets": [...], "total_runs": N, ...}` structure  
**Acceptance**: valid JSON; `Content-Type: application/json`; no Dagster classnames in response  
**Ref**: `src/nucleus/workbench/app.py` routes; `tests/workbench/test_api_assets.py`

### F3. GET /api/runs — paginated list

**Setup**: Workbench running; at least 3 completed runs in run history  
**Steps**: `curl http://localhost:8080/api/runs?page=1&per_page=2`  
**Expected**: HTTP 200; JSON with `runs` array (≤ 2 items) and `total`, `page` pagination metadata  
**Acceptance**: NDJSON or JSON array; pagination metadata present

### F4. GET /api/runs/{id}/log — streams (SSE)

**Setup**: Workbench running; a known run_id  
**Steps**: `curl -N http://localhost:8080/api/runs/{id}/log` (SSE stream)  
**Expected**: HTTP 200; `Content-Type: text/event-stream`; log lines streamed  
**Acceptance**: at least 1 SSE event before stream ends; no raw Dagster log lines

### F5. POST /api/runs/trigger — creates a run

**Setup**: Workbench running; `example.greeting` asset registered  
**Steps**: `curl -X POST http://localhost:8080/api/runs/trigger -d '{"asset_key": "example.greeting"}'`  
**Expected**: HTTP 202; JSON with `{"run_id": "..."}`; run appears in `/api/runs` within 5 s  
**Acceptance**: HTTP 202; run_id is a valid UUID; materialization completes

### F6. GET /api/search?q=revenue — returns relevant assets

**Setup**: project with assets named `*revenue*`  
**Steps**: `curl http://localhost:8080/api/search?q=revenue`  
**Expected**: HTTP 200; JSON array with matching assets  
**Acceptance**: assets with "revenue" in key or description ranked first; exact match returned

### F7. Editorial Hero dashboard — loads < 2 s cold

**Setup**: Workbench running; browser or curl  
**Steps**: time GET `http://localhost:8080/`  
**Expected**: HTTP 200; static HTML + editorial hero section served in < 2 s cold, < 500 ms warm  
**Acceptance**: elapsed < 2 s cold  
**Ref**: ADR-016 §"Static fallback" (editorial hero serves even without npm)

### F8. Static fallback — renders editorial hero offline

**Setup**: Workbench running; no frontend npm build artifacts  
**Steps**: GET `http://localhost:8080/` without running `npm run build`  
**Expected**: HTTP 200; editorial hero section visible in HTML response; NO "Cannot GET /" error  
**Acceptance**: editorial hero content present in raw HTML (server-side rendered fallback per ADR-016)

---

## Suite G: AI Copilot (4 scenarios)

### G1. `nucleus chat` — mocked LLM returns helpful response

**Setup**: `ANTHROPIC_API_KEY=sk-test-mock-key` (offline mode test); LiteLLM mock patch  
**Steps**: `nucleus chat "What assets exist in this project?"`  
**Expected**: exit 0 OR exit 1 with `NucleusCopilotAuthError` (NE4001) — both acceptable if real key needed  
**Acceptance**: no raw `litellm.` or `anthropic.` classnames in output; fix_hint present on auth failure  
**Ref**: `nucleus_cli_spec.md` §3.8; ADR-015

### G2. Token budget guardrail — prevents runaway

**Setup**: `NUCLEUS_COPILOT_MAX_TOKENS=100` (or equivalent small budget)  
**Steps**: send an extremely long prompt via `nucleus chat`  
**Expected**: exit 1 with `NucleusBudgetExceededError` (NE4005); clear message about budget  
**Acceptance**: exit 1; NE4005 in output; no actual LLM call made beyond budget  
**Ref**: `nucleus_cli_spec.md` §3.8; `src/nucleus/intelligence/copilot.py`

### G3. Schema-aware prompt — includes project assets

**Setup**: project with 3 known assets; mocked LLM capture prompt  
**Steps**: `nucleus chat "How do I query daily revenue?"` (with LLM mock that echos prompt)  
**Expected**: prompt sent to LLM includes asset list from `ctx.gather_context()` or equivalent  
**Acceptance**: asset keys visible in captured prompt; no absolute filesystem paths exposed  
**Ref**: `src/nucleus/intelligence/context.py`; `nucleus_cli_spec.md` §3.8

### G4. Fix-hint banner — missing API key

**Setup**: unset `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_HOST`  
**Steps**: `nucleus chat "test"`  
**Expected**: exit 1; `NucleusCopilotAuthError` (NE4001); fix_hint says "Set ANTHROPIC_API_KEY=..." or similar  
**Acceptance**: fix_hint non-empty; no raw `litellm.AuthenticationError` in output  
**Ref**: `src/nucleus/intelligence/translate.py` `_BANNED_NAMES` regex

---

## Suite H: Error UX (6 scenarios)

### H1. Every NE-code has a fix_hint

**Setup**: enumerate all `NucleusError` subclasses from `src/nucleus/errors.py`  
**Steps**: for each subclass, instantiate with minimal args; check `fix_hint` attribute  
**Expected**: every subclass has a non-empty `fix_hint` string  
**Acceptance**: `fix_hint != ""` for all 32 NE-codes (per `docs/budget_history.md` latest count)  
**Automation**: `scripts/check_error_codes.py` already validates NE-codes; extend to check fix_hint

### H2. Zero external classnames in user-visible strings

**Setup**: run full CLI command suite; capture all stdout + stderr  
**Steps**: `python scripts/dagster_leak_check.py`  
**Expected**: EXIT 0; 0 leaks in 3 scanned roots  
**Acceptance**: `dagster.`, `duckdb.`, `polars.`, `pyiceberg.`, `OpExecutionContext`, `DagsterInstance`, `DuckDBPyConnection` absent from all user-facing strings  
**Ref**: `AGENTS.md` §11.7; `nucleus_cli_spec.md` §5.4

### H3. Stack traces hidden by default; `--verbose` reveals

**Setup**: trigger a `NucleusError` on any command (e.g., ingest bad DSN)  
**Steps**: run without flags; run with `--verbose`  
**Expected**: without `--verbose`, no Python traceback in stderr; with `--verbose`, `NucleusError.cause` class + stack printed  
**Acceptance**: `Traceback` string absent in default mode; present in verbose mode  
**Ref**: `nucleus_cli_spec.md` §6 (`--verbose` flag)

### H4. Exit codes consistent (0/1/2/3/4/5/130)

**Setup**: trigger each exit code scenario  
**Steps**: collect exit codes from each CLI command variant  
**Expected**: all 7 exit codes (0, 1, 2, 3, 4, 5, 130) behave per `nucleus_cli_spec.md` §8 table  
**Acceptance**: 0=success; 1=NucleusError; 2=usage error; 3=Docker unavailable; 4=network; 5=schema; 130=Ctrl-C  
**Ref**: `nucleus_cli_spec.md` §8; `tests/cli/test_main.py` exit code matrix

### H5. `nucleus describe <typo>` — "Did you mean…?" suggestion

**Setup**: project with `example.greeting` registered  
**Steps**: `nucleus describe example.greetnig` (typo)  
**Expected**: exit 1; `NucleusAssetNotFound` (NE3002); user_message includes "Did you mean 'example.greeting'?"  
**Acceptance**: difflib/fuzzy suggestion present in user_message  
**Ref**: `coordination/sql_resolver.py` "did you mean" logic; `nucleus_ctx_sdk_spec.md` §4.1 unknown asset

### H6. `--quiet` mode — suppresses non-error output

**Setup**: initialized project with valid asset  
**Steps**: `nucleus version --quiet`; `nucleus run example.greeting --quiet`  
**Expected**: stdout empty on success; stderr shows errors only  
**Acceptance**: no progress bars, no checkmarks, no status messages in stdout; exit code is the sole signal  
**Ref**: `nucleus_cli_spec.md` §5.3; `nucleus_cli_spec.md` §6 (`--quiet` flag)

---

## Suite I: Governance (8 scenarios)

### I1. All 8 governance scripts PASS on clean repo

**Setup**: clean working directory (no uncommitted changes)  
**Steps**: run each script independently  
**Expected**: each script exits 0  

| Script | Acceptance |
|---|---|
| `scripts/check_vocabulary.py` | EXIT 0; 6 banned terms watched; 0 violations |
| `scripts/check_pinning.py` | EXIT 0; all runtime deps exactly pinned (== syntax) |
| `scripts/loc_budget.py` | EXIT 0; `src/nucleus/` < 8,000 LOC (v0.1 ceiling per §11.6) |
| `scripts/dagster_leak_check.py` | EXIT 0; 0 leaks in 3 scanned roots |
| `scripts/check_error_codes.py` | EXIT 0; all NE-codes valid + ADR-006 mapping intact |
| `scripts/check_api_stability.py` | EXIT 0; 7 public symbols tagged; 0 untagged |
| `scripts/check_licenses.py` | EXIT 0; 0 RED-tier licenses |
| `scripts/check_layering.py` | EXIT 0; no cross-layer imports |

### I2. LOC budget respected (< 8,000 `src/nucleus/`)

**Setup**: `src/nucleus/` at current state  
**Steps**: `python scripts/loc_budget.py`  
**Expected**: `src/nucleus/` total ≤ 8,000 LOC (v0.1 ceiling); each subdir under per-module budget  
**Acceptance**: current baseline 4,124 LOC (51.5% of ceiling; GREEN); after Wave-1 estimated < 7,000  
**Ref**: `AGENTS.md` §11.6; `docs/budget_history.md`

### I3. Upgrade smoke 7/7 gates PASS

**Setup**: clean install of pinned deps  
**Steps**: `python scripts/upgrade_smoke.py`  
**Expected**: all 7 upgrade smoke gates EXIT 0  
**Acceptance**: EXIT 0 overall  
**Ref**: `scripts/upgrade_smoke.py`; `AGENTS.md` §11.13

### I4. License check — 0 RED, only GREEN + bounded YELLOW

**Setup**: current pyproject.toml deps  
**Steps**: `python scripts/check_licenses.py`  
**Expected**: 0 RED-tier licenses; YELLOW licenses all have documented boundary note in `docs/decisions/ADR-007`  
**Acceptance**: EXIT 0; known YELLOW: `orjson==3.11.9` (MPL-2.0), `psycopg==3.2.3` (LGPL-3.0) — both boundary-documented  
**Ref**: ADR-007

### I5. Pinning check — every active dep has exact pin

**Setup**: `pyproject.toml` at current state  
**Steps**: `python scripts/check_pinning.py`  
**Expected**: EXIT 0; every `[project.dependencies]` entry uses `==` pin syntax  
**Acceptance**: no `>=`, `~=`, or unpinned deps in runtime group  
**Ref**: `AGENTS.md` §11.13; `docs/compatibility.md`

### I6. Vocabulary check — zero banned terms in user strings

**Setup**: `src/nucleus/` at current state  
**Steps**: `python scripts/check_vocabulary.py`  
**Expected**: EXIT 0; 0 occurrences of banned terms (table, job, task, pipeline output, catalog/metastore, etc.) in user-facing strings <!-- banned-term: metastore -->  
**Acceptance**: 6 terms watched; 0 violations  
**Ref**: `AGENTS.md` §7; `nucleus_cli_spec.md` §12

### I7. Layering check — no cross-layer imports

**Setup**: `src/nucleus/` at current state  
**Steps**: `python scripts/check_layering.py`  
**Expected**: EXIT 0; no lower-layer module importing from higher-layer  
**Acceptance**: workbench layer included in LAYERS list (fixed in Phase D)  
**Ref**: `AGENTS.md` §11.7

### I8. Error-code uniqueness + ADR-006 mapping intact

**Setup**: `src/nucleus/errors.py` at current state  
**Steps**: `python scripts/check_error_codes.py`  
**Expected**: EXIT 0; 32 NE-codes (NE1001–NE3007 + NE4001–NE4005 + NE5001–NE5008); no duplicates; each in ADR-006 layer band  
**Acceptance**: every `NucleusError` subclass has `error_code: ClassVar[str]` populated  
**Ref**: ADR-006; `src/nucleus/errors.py`

---

## Suite J: Chaos + Reliability (8 scenarios)

> **Infra note**: J3 requires Docker (MinIO container); J4 requires Postgres container; J5 requires seeded data. CI flag `--run-chaos` gates execution.

### J1. Disk-full mid-write → clean error + no orphan files

**Setup**: mount tmpfs with 50 MB limit; asset writing > 50 MB  
**Steps**: trigger materialization; disk fills mid-write  
**Expected**: exit 1 with `NucleusIOError` (NE1005) or `NucleusCommitUnknownError` (NE1004); NO orphan Parquet files in `.nucleus/warehouse/`  
**Acceptance**: no partial snapshot; cleanup complete  
**Ref**: `src/nucleus/ctx/copy_from.py` error handling; atomic commit guarantee

### J2. Kill -9 mid-commit → Iceberg snapshot atomic

**Setup**: slow asset (sleep in body); `nucleus run` in subprocess  
**Steps**: start run; send SIGKILL after 1 s; verify snapshot state  
**Expected**: snapshot either fully committed OR fully absent (no partial state)  
**Acceptance**: `pyiceberg` catalog shows either the old snapshot OR the new one; never a partial write  
**Ref**: Iceberg atomic commit guarantee; `nucleus_architecture_v4.1.md` §6.2 step 3

### J3. MinIO down during materialize → retries + NE-coded final error

**Setup**: MinIO running; asset that writes to S3/MinIO  
**Steps**: start `nucleus run`; stop MinIO container mid-run  
**Expected**: retry logic (if implemented) + final exit 4 with `NucleusIOError` or `NucleusSourceConnectionError`; user_message says storage unavailable; NO silent success  
**Note**: Requires Docker in CI

### J4. Postgres connection drop mid-ingest → dlt retry + clean error

**Setup**: Postgres running; ingest of 10k-row table  
**Steps**: start `nucleus ingest postgres://...`; kill Postgres connection mid-ingest  
**Expected**: dlt retry logic triggers; if exhausted, exit 1 with `NucleusSourceConnectionError` (NE1001); no partial Iceberg snapshot committed  
**Note**: Requires Postgres container + connection manipulation

### J5. Schema drift on source → NE2004 contract violation

**Setup**: asset with strict schema contract; source updated to add incompatible column type  
**Steps**: `nucleus run schema_test.strict_asset` after source schema change  
**Expected**: exit 5; `NucleusSchemaEvolutionError` (NE2004); user_message describes the incompatible field; no partial write  
**Ref**: `docs/patterns/schema_evolution.md`; `nucleus_ctx_sdk_spec.md` §2.5

### J6. Concurrent run race — lock or fail-fast

**Setup**: two processes; same project; same asset (slow enough for race)  
**Steps**: launch two concurrent `nucleus run` invocations in parallel  
**Expected**: exactly one succeeds (exit 0); other exits 1 with `NucleusCommitConflictError` (NE1002) OR one is queued and both eventually succeed  
**Acceptance**: no data corruption; no `row_count` inflation  
**Ref**: `nucleus_architecture_v4.1.md` §6.2 step 3

### J7. Catalog corruption → recoverable

**Setup**: manually corrupt `catalog.db` (truncate or write invalid SQL)  
**Steps**: `nucleus up`; `nucleus run`  
**Expected**: exit 1 with clean error message; no Python traceback; fix_hint suggests `nucleus doctor` or catalog repair  
**Acceptance**: nucleus does NOT crash with raw SQLite error; wraps and surfaces cleanly

### J8. Network partition during S3 multipart upload → clean rollback

**Setup**: large asset (> 5 MB); MinIO with network partition injection  
**Steps**: trigger materialization; inject network partition during S3 multipart upload  
**Expected**: pyiceberg abort_multipart_upload called; no orphan S3 parts; Iceberg snapshot absent  
**Note**: Requires network partition tooling (e.g., `tc` on Linux); complex infra

---

## Suite K: Performance (5 scenarios)

### K1. Cold boot — `nucleus version` < 1.5 s

**Setup**: fresh shell; no import caching  
**Steps**: time 5 consecutive `nucleus version` calls; record all; use P95  
**Expected**: P95 < 1.5 s  
**Acceptance**: measured baseline on 2026-05-14 was 5.82 s for `nucleus up` cold; `nucleus version` (import-only) should be faster  
**Ref**: `nucleus_cli_spec.md` §3.7

### K2. `nucleus list` — < 2 s for 100 assets

**Setup**: project with 100 registered asset definitions  
**Steps**: time `nucleus list` 3 times; use median  
**Expected**: median < 2 s  
**Note**: 100-asset project fixture required; may need synthetic generator

### K3. 1 GB DataFrame → Iceberg < 30 s

**Setup**: asset returning 1 GB Polars LazyFrame (CSV → parquet)  
**Steps**: `nucleus run perf_test.gigabyte_asset`; measure duration from `MaterializationResult.duration_ms`  
**Expected**: `duration_ms` < 30,000  
**Acceptance**: no OOM; snapshot created; row count correct  
**Ref**: v4.1 §16.1; Suite B3

### K4. 1 GB scan + aggregate < 3 s

**Setup**: `raw.big_table` with 1 GB of data (1M rows × several float columns)  
**Steps**: `nucleus query "SELECT AVG(amount), COUNT(*) FROM raw.big_table"`  
**Expected**: result in < 3 s; correct aggregate  
**Acceptance**: elapsed < 3 s; DuckDB's vectorized scan doing the work  
**Ref**: v4.1 §16.1 (DuckDB perf target)

### K5. Workbench static fallback — Lighthouse Performance ≥ 90

**Setup**: Workbench running; Lighthouse CLI installed  
**Steps**: `lighthouse http://localhost:8080 --output json --only-categories=performance`  
**Expected**: `categories.performance.score >= 0.9`  
**Note**: Requires Lighthouse CLI; skip in standard CI; manual or dedicated perf CI  
**Ref**: ADR-016 (editorial hero performance target)

---

## Execution Matrix

| Suite | WSL (primary) | Windows native | macOS | Python 3.12 |
|---|---|---|---|---|
| A (Boot) | ALL | ALL | Manual | A1 only |
| B (Materialize) | ALL | ALL | Manual | — |
| C (Query) | ALL | ALL | Manual | — |
| D (Ingest) | D1-D4, D7, D10 | D3, D7, D10 | Manual | — |
| E (Schedule) | ALL | E1-E3 | Manual | — |
| F (Workbench) | ALL | ALL | Manual | — |
| G (Copilot) | ALL | G4 | Manual | — |
| H (Error UX) | ALL | H1-H4 | Manual | — |
| I (Governance) | ALL | I1-I5 | — | I1, I2 |
| J (Chaos) | J1-J2 (no Docker), J3-J8 (Docker) | — | — | — |
| K (Performance) | ALL | K1 | Manual | — |

---

## Pass/Fail Criteria for v0.2.0 Release Gate

| Suite | Threshold | Notes |
|---|---|---|
| A | 100% | Hard gate — boot regression = release blocker |
| B | 100% (B6 may SKIP) | B6 SKIP acceptable if run-state not in Wave-1 scope |
| C | 100% | Hard gate |
| D | ≥ 90% | D5/D6/D9 may SKIP pending infra |
| E | 100% | Hard gate |
| F | ≥ 75% | F5-F8 may SKIP if Wave-1A workbench not fully landed |
| G | 100% of G2, G4 (auth-independent) | G1, G3 SKIP if no API key in CI |
| H | 100% | Hard gate — error UX is core product promise |
| I | 100% | Hard gate — governance is release gate per AGENTS.md |
| J | ≥ 80% (≥ 6/8) | J3-J8 need Docker infra; J8 needs network tools |
| K | 100% of K1-K4; K5 manual | K1 hardest gate (regression from 5.82s baseline) |

---

*This plan is produced by the release-planner builder (2026-05-15) and will be reconciled against Wave-1 output by the foreground. Scenario counts may shift slightly as Wave-1A (workbench) and Wave-1B (connectors) land features. Suite A and I are always runnable regardless of Wave-1 state.*
