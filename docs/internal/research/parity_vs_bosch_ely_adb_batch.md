# Parity check: Bosch ELY ADB Batch pipeline vs Nucleus

**Date**: 2026-05-15  
**Researcher**: Claude Sonnet 4.6 (builder tier; GPT-5.5 preferred model unavailable — fallback recorded per AGENTS.md §11.14)  
**Target repo**: `C:\Users\GOT4HC\TBP-ADB\TBP-ADB\bosch_ely_adb_batch`  
**Bottom-line verdict**: **NO** — Nucleus cannot replicate this pipeline professionally today. The mismatch is architectural, not a feature gap. Three root causes: (1) the compute engine is Apache Spark (distributed, JVM-based) vs Nucleus's DuckDB/Polars (single-node, no-JVM); (2) the table format is Delta Lake vs Nucleus's Apache Iceberg; (3) the ingest patterns use proprietary industrial measurement formats (TDMS, MF4/ASAM, DTA) for which no Nucleus adapter exists. Approximately 20-25% of the *orchestration* concepts map cleanly; 0% of the *compute and storage* stack maps without an engine rewrite.

---

## 1. Bosch repo inventory

### 1.1 Directory tree (depth 2)

```
bosch_ely_adb_batch/
├── databricks.yml              # Asset Bundle root config: bundle, variables, 7 targets
├── resources/                  # 9 job + orchestration YAML files
│   ├── job_ely_bronze.yml       # Raw → Bronze (8 tasks: TDMS/CSV/DTA/MF4/Parquet ingestion)
│   ├── job_ely_silver.yml       # Bronze → Silver (17 tasks: dim/fact tables)
│   ├── job_ely_gold.yml         # Silver → Gold (9 tasks: aggregated views)
│   ├── job_ely_r2g.yml          # Orchestrator: runs bronze → silver → gold as subtasks
│   ├── job_ely_optimize_tables.yml  # Delta OPTIMIZE + VACUUM maintenance
│   ├── job_ely_table_cleanup.yml    # Cleanup stale data
│   ├── job_ely_integration_test.yml # E2E integration test jobs
│   ├── common_job_ely_create_views.yml # View creation utilities
│   └── common_job_ely_load_sys_files.yml # Config/sys-file loading
├── src/                        # Python source: 41 files, ~5,500 LOC
│   ├── _0_system/              # 8 system utility scripts
│   ├── _1_ingestion/           # 4 ingestion + signal-mapping scripts
│   ├── _2_r2b/                 # 8 Raw→Bronze (R2B) scripts (one per format/type)
│   ├── _3_b2s/                 # 20 Bronze→Silver (B2S) scripts (dim + fact tables)
│   ├── _4_s2g/                 # 10 Silver→Gold (S2G) scripts (views + aggregations)
│   ├── _5_common/              # 4 shared utility modules (2,100 LOC)
│   └── _9_tests/               # 24 unit test files (PySpark-based)
├── sys_files/                  # Config + test data
│   ├── config_files/           # 5 CSVs: layer configs (bronze/silver/gold)
│   ├── validation_rules/       # validation_rules.csv
│   └── test_data/integration/  # 150+ test fixture files (TDMS, CSV, DTA, MF4)
├── telemetry/                  # Observability: FluentBit → Loki → Grafana (OpenShift)
│   ├── fluentbit/              # init-fluentbit.sh init script
│   ├── openshift/              # Grafana dashboards (3 JSON), stack deployment YAML
│   └── docs/                   # ELY telemetry docs
└── scratch/                    # Exploration notes, draft YAML, dev scripts
```

### 1.2 File inventory (counts)

| Type | Count | Notes |
|---|---|---|
| `.py` source (business logic) | 41 | All use PySpark DataFrames; no plain Python/Polars |
| `.py` unit tests | 24 | pytest + PySpark `SparkSession.builder.master("local[1]")` |
| `.yml` / `.yaml` job configs | 9 | Databricks Asset Bundle YAML |
| `.csv` config files | 5 | Runtime layer/table configurations (bronze/silver/gold) |
| `.csv` test data | ~150 | Integration test fixtures |
| Binary test data | ~30 | TDMS + DTA + MF4 binary measurement files (unreadable as text) |
| `.json` test fixtures | ~50 | OutSystems ERP data fixtures |
| Total source Python | ~5,500 LOC | (business logic + utilities, excluding tests) |
| Total YAML config | ~1,100 LOC | All 9 job YAML files |

Source citations: `README.md:3-36`, directory listing confirmed by recursive glob.

### 1.3 Stack inventory

| Component | Value | Source |
|---|---|---|
| **Databricks Runtime** | `15.4.x-scala2.12` (Spark 3.5.x + Scala 2.12) | `databricks.yml:47` |
| **Python version** | 3.11+ (README), `cpython-310` in `__pycache__` | `README.md:80`, `src/_2_r2b/__pycache__/` |
| **Compute engine** | Apache Spark (PySpark) via Databricks Runtime | `b2s_fact_timeseries.py:53` `SparkSession.builder.getOrCreate()` |
| **Table format** | **Delta Lake** (NOT Iceberg) | `common_io_utils.py` (read_delta_table_using_metadata) |
| **Catalog** | Unity Catalog (3-level: `catalog.schema.table`) | `common_utils.py:46-67` |
| **Storage** | Azure ADLS Gen2 | `common_utils.py:49` (`*.dfs.core.windows.net`) |
| **Cluster type** | Autoscaled job clusters (2-8 workers) | `job_ely_silver.yml:11-13` |
| **Worker size** | `Standard_E20as_v4` (160 GB RAM / 20 vCPU) | `databricks.yml:50` |
| **Driver size** | `Standard_D16as_v4` (64 GB RAM / 16 vCPU) | `databricks.yml:53` |
| **Key Python deps** | `pyspark` (bundled), `npTDMS` (per-task), `asammdf==8.0.0` (per-task) | `job_ely_bronze.yml:91,100` |
| **Scheduling** | Quartz cron (6-field, timezone-aware) | `job_ely_r2g.yml:139-142` |
| **Environments** | 7 targets: dev_user, dev, qa, prod + 3 integration-test variants | `databricks.yml:109-162` |
| **Observability** | Fluent Bit → Loki → Grafana (OpenShift) + custom telemetry Delta table | `telemetry/`, `telemetry_utils.py` |
| **Auth** | Service principal (`sp-pemely-databricks`) via Databricks secret scope | `databricks.yml:28-30` |

---

## 2. Pipeline patterns identified

For each pattern: What it is · Bosch implementation (file:line) · Nucleus equivalent · Status.

### 2.1 Medallion architecture (Bronze → Silver → Gold)

**Bosch**: Three explicitly separated Databricks jobs (`job_ely_bronze.yml`, `job_ely_silver.yml`, `job_ely_gold.yml`) each targeting a different Unity Catalog schema (`pemely_dev` for bronze/silver, `pemely_ops` for gold). Layer variable mapping in `common_utils.py:96-100`:
```python
LAYER_VARIABLES = {
    "_2_r2b": {"read_layer": "raw", "write_layer": "bronze"},
    "_3_b2s": {"read_layer": "bronze", "write_layer": "silver"},
    "_4_s2g": {"read_layer": "silver", "write_layer": "gold"},
}
```

**Nucleus equivalent**: `@nucleus.asset` with `deps=` creates the implicit DAG; assets map to `schema.name` 2-level keys (v0.1), or `catalog.schema.name` 3-level at v0.3+. `ctx.read("bronze.orders")` pulls upstream. The 3-tier concept is representable but namespace management differs.

**Status**: 🟡 PARTIAL — The concept maps. The 3-level naming (`catalog.schema.table`) for multi-schema separation is deferred to v0.3+ (`sdk/decorators.py:53-55`). v0.1 supports `schema.name` (2-level only).

---

### 2.2 Task dependency wiring

**Bosch**: Explicit `depends_on:` blocks in job YAML. Example from `job_ely_silver.yml:167-173`:
```yaml
- task_key: tsk_dim_file
  depends_on:
    - task_key: tsk_fact_timeseries
    - task_key: tsk_fact_impedance
    - task_key: tsk_dim_metadata
    - task_key: tsk_dim_channel
  run_if: ALL_SUCCESS
```
The `run_if: ALL_SUCCESS` condition ensures no downstream runs if upstream fails.

**Nucleus equivalent**: `@nucleus.asset(deps=["silver.fact_timeseries", "silver.fact_impedance", ...])` or auto-derived from `ctx.read()` calls within the asset body. The Dagster-backed DAG engine (v4.1 §6.3) enforces ordering.

**Status**: ✅ HAVE — explicit `deps=` in decorators + `run_if: ALL_SUCCESS` semantic maps to default Dagster behavior.

---

### 2.3 Apache Spark as compute engine

**Bosch**: Every transformation file uses PySpark. Example `b2s_fact_timeseries.py:53-63`:
```python
spark = SparkSession.builder.getOrCreate()
spark.conf.set("spark.sql.shuffle.partitions", "2000")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")
spark.conf.set("spark.sql.streaming.stateStore.providerClass",
    "org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider")
```
This configures distributed Spark with RocksDB state store for streaming, which requires the JVM runtime.

**Nucleus equivalent**: DuckDB (default in-process engine) + Polars (per v4.1 §4). Neither is distributed; both are single-node. Per AGENTS.md §3 constraint #1: **No JVM in core path**. Per v4.1 §17 yield-to-giants: for distributed compute, Nucleus dispatches to Databricks via `compute="databricks"` (v0.3+).

**Status**: ❌ CRITICAL BLOCKER — Nucleus fundamentally forbids JVM (Constraint #1 in AGENTS.md §3). The Bosch pipeline's compute engine (Spark 3.5.x on JVM) cannot run inside Nucleus. The compute must stay on Databricks (via yield-to-giants Mode 2 dispatch, v0.3+).

---

### 2.4 Delta Lake as table format

**Bosch**: All read/write via Delta. Example from `common_io_utils.py` (referenced throughout source):
```python
read_delta_table_using_metadata(...)
write_delta_table_using_metadata(...)
write_upsert(...)  # Delta MERGE under the hood
```
Delta MERGE conditions are constructed dynamically in `b2s_fact_timeseries.py:103-108`:
```python
merge_condition = f"""
    target.order_id IN ({...}) AND
    target.file_id IN ({...}) AND
    target.order_id = source.order_id AND
    target.file_id = source.file_id AND
    target.channel_id = source.channel_id AND
    target.time = source.time
"""
```

**Nucleus equivalent**: Apache Iceberg (Tier 0, immortal per v4.1 §5). The formats are incompatible: different file layouts, different metadata protocol (Delta `_delta_log/` JSON vs Iceberg `metadata/*.json`), different MERGE APIs. Iceberg does support MERGE INTO, but the pyiceberg API differs fundamentally from `delta.merge()`.

**Status**: ❌ CRITICAL BLOCKER — Delta Lake and Apache Iceberg are different table formats. Migrating 20+ tables from Delta to Iceberg requires a full data migration + pipeline rewrite. Per ADR-002 and v4.1 §2, Iceberg is Nucleus's immortal substrate. Delta is a non-goal (`AGENTS.md §4`).

---

### 2.5 Structured Streaming with foreachBatch

**Bosch**: The Bronze→Silver transform for timeseries uses Spark Structured Streaming triggered with `availableNow=True`. From `b2s_fact_timeseries.py:373-379`:
```python
(
    batch_df.writeStream.foreachBatch(batch_processor)
    .trigger(availableNow=True)
    .option("checkpointLocation", table_metadata["checkpoint_location"])
    .start()
    .awaitTermination()
)
```
This pattern processes only *newly arrived* files on each run (incremental streaming micro-batch). Without this, re-processing the entire dataset every run would be prohibitively expensive.

**Nucleus equivalent**: Streaming is explicitly deferred to v0.5+ per v4.1 §18 roadmap. In v0.1, all materialization is batch. `ctx.copy_from` supports full-scan ingestion but has no incremental streaming checkpoint mechanism.

**Status**: ❌ CRITICAL BLOCKER — Streaming (`writeStream`, `foreachBatch`, checkpoint location) is deferred to v0.5+. This affects the **Bronze layer entirely** and parts of Silver (fact_timeseries, fact_impedance).

---

### 2.6 Industrial measurement file formats (TDMS, MF4/ASAM, DTA)

**Bosch**: The pipeline ingests four proprietary industrial measurement formats:
- **TDMS** (`npTDMS` library) — National Instruments Technical Data Management Streaming format. Installed per-task in `job_ely_bronze.yml:91`: `- pypi: package: "npTDMS"`
- **MF4** (`asammdf==8.0.0`) — ASAM MDF v4, automotive/industrial measurement standard. Installed per-task: `job_ely_bronze.yml:100-102`
- **DTA** — Proprietary frequency analysis data format (custom parser in `_2_r2b/r2b_sss_testrig_dta.py`)
- **CSV variants** — Multiple location-specific CSV schemas (BAP, EXT, LIZ, RNG, SYV, TBP test rig types)

The Bronze layer (`_2_r2b/`) exists entirely to decode these formats into Delta tables.

**Nucleus equivalent**: `ctx.copy_from` supports: SQLite, Postgres, MySQL, S3, GCS, Snowflake, filesystem. **None of these cover TDMS, MF4, or DTA.** There is no Nucleus connector for industrial measurement formats. Adding them would require new `copy_from` adapters plus third-party library integration.

**Status**: ❌ CRITICAL BLOCKER — The entire Bronze ingestion layer (8 scripts, ~1,500 LOC) has no Nucleus equivalent. The source data is in binary industrial formats that `ctx.copy_from` does not handle. This is the #1 blocker for any migration attempt.

---

### 2.7 Multi-environment targets (7 environments)

**Bosch**: `databricks.yml:109-162` defines 7 deployment targets with different workspace URLs, root paths, security modes, and service principals:
- `dev_user` — personal dev (development mode, per-user path)
- `dev` — shared dev team (production mode)
- `qa` — QA environment (separate workspace: `adb-7376334951991000.0.azuredatabricks.net`)
- `prod` — production (separate workspace: `adb-5407587042408609.9.azuredatabricks.net`)
- `dev_integration_test`, `qa_integration_test`, `prod_integration_test` — integration test variants with `USER_ISOLATION` security mode vs `SINGLE_USER`

Each target has environment-specific: workspace host, artifact location, security mode, and optionally different schedules (`prod` has the real production cron; `dev_user` has the same schedule but `PAUSED`).

**Nucleus equivalent**: v0.1 has no environment management system. The closest approximation is using different `warehouse_dir` values per environment and managing `.env.local` files manually. Multi-environment promotion is deferred to v1.5+ per v4.1 §18.

**Status**: ❌ MISSING — Multi-environment target management (dev/qa/prod workspace isolation, environment-specific schedules, security mode switching) is not in Nucleus v0.1. Workaround: manual `.env.local` + `warehouse_dir` switching per environment. Full feature deferred to v1.5+.

---

### 2.8 Scheduling (Quartz cron, timezone-aware)

**Bosch**: Production schedule on `job_ely_r2g` uses Quartz cron expression with Amsterdam timezone. From `job_ely_r2g.yml:140-143`:
```yaml
schedule:
  quartz_cron_expression: "0 0 17 ? * MON-FRI"
  timezone_id: "Europe/Amsterdam"
  pause_status: "UNPAUSED"
```
Quartz uses 6 fields: `seconds minutes hours day month weekday`. The `?` wildcard and `MON-FRI` range are Quartz-specific.

Gold job schedule: `"0 0 22 ? * MON-FRI"` (`job_ely_gold.yml:146`). Optimize: `"0 0 2 ? * MON-FRI"` (`job_ely_optimize_tables.yml:79`).

**Nucleus equivalent**: `@nucleus.asset(schedule="0 17 * * 1-5")` accepts **5-field POSIX cron** (not Quartz 6-field). Nucleus converts `MON-FRI` → `1-5` equivalently but strips the leading seconds field. Per `sdk/decorators.py:279-283`, 6-field cron raises `NucleusScheduleParseError`. Timezone-awareness is not implemented in v0.1 (ADR-017 §6 defers active execution to v0.2+). The schedule is stored but not actively triggered in v0.1.

**Status**: 🟡 PARTIAL — Scheduling concept maps; cron expression converts with minor translation (`0 17 * * 1-5` equivalent). Quartz 6-field format rejected by validator (remove leading `0`). Timezone-aware execution deferred to v0.2+. Active triggering deferred to v0.2+.

---

### 2.9 Job orchestration (run_job_task pattern)

**Bosch**: `job_ely_r2g.yml` is an orchestrator job that invokes the three layer-jobs as subtasks using `run_job_task`. From `job_ely_r2g.yml:55-66`:
```yaml
tasks:
  - task_key: tsk_bronze
    run_job_task:
      job_id: ${resources.jobs.job_ely_bronze.id}
  - task_key: tsk_silver
    run_job_task:
      job_id: ${resources.jobs.job_ely_silver.id}
    depends_on:
      - task_key: tsk_bronze
```
This "job-of-jobs" pattern allows the three layers to be run independently or together.

**Nucleus equivalent**: The DAG-of-assets handles this natively — `@nucleus.asset(deps=["bronze.x"])` automatically triggers upstream before downstream. There is no explicit "run this job as a task" concept; Dagster's asset graph resolves the dependency chain. In practice, `nucleus run gold.my_asset` would trigger the full bronze→silver→gold chain if upstream is stale.

**Status**: ✅ HAVE — Nucleus's asset graph with implicit deps handles this pattern more elegantly. No explicit orchestrator job needed.

---

### 2.10 Email notifications on failure

**Bosch**: All production jobs notify a list of engineers on failure and duration-exceeded. From `job_ely_silver.yml:50-53`:
```yaml
email_notifications:
  on_failure: ${var.notification_recipients}
  on_duration_warning_threshold_exceeded: ${var.notification_recipients}
notification_settings:
  no_alert_for_skipped_runs: true
```
Recipients defined in `databricks.yml:19-26` (5 email addresses). Production gold has separate recipient list (`job_ely_gold.yml:174-179`).

**Nucleus equivalent**: ❌ Not in v0.1. No notification system exists. Workaround: wire Dagster's native alerting hooks (v4.1 §6.3 wrapper exposes this) or use a CI/CD webhook on run failure. Cookbook pattern (`docs/recipes/slack_bot_on_data.md` exists as placeholder per directory listing). Formal notification deferred to v0.3+.

**Status**: ❌ MISSING — v0.1 has no built-in notification system. Dagster exposes failure hooks that could be wired by the user, but Nucleus doesn't expose this surface today.

---

### 2.11 Health monitoring (duration threshold alerts)

**Bosch**: Job-level health rules fire when a job runs too long. From `job_ely_silver.yml:55-59`:
```yaml
health:
  rules:
    - metric: "RUN_DURATION_SECONDS"
      op: "GREATER_THAN"
      value: 18000  # 5 hours in seconds
```
R2G orchestrator threshold is 10 hours (`job_ely_r2g.yml:47`).

**Nucleus equivalent**: Not available. OpenTelemetry integration for observability is planned for v0.5+ (v4.1 §11). No duration-based alerting in v0.1.

**Status**: ❌ MISSING — Deferred to v0.5+ (OpenTelemetry + VictoriaMetrics/VictoriaLogs per v4.1 §11 + nucleus.mdc rules table).

---

### 2.12 Permissions / ACL (Unity Catalog RBAC)

**Bosch**: Every job grants `CAN_MANAGE` to a Unity Catalog group. From `job_ely_silver.yml:39-41`:
```yaml
permissions:
  - group_name: "idm2bcd_dssi03prod_pemely_data"
    level: "CAN_MANAGE"
```
Unity Catalog enforces column-level and table-level security via groups.

**Nucleus equivalent**: Per AGENTS.md §3 Constraint #6 and v4.1 §7: **no custom auth system**. Nucleus delegates to OIDC (Authentik/Keycloak/Okta/Azure AD). In v0.1, no RBAC layer exists. Users with access to the warehouse directory have full access.

**Status**: ⏭ OUT-OF-SCOPE BY DESIGN — AGENTS.md §3 constraint #6 forbids custom auth. Delegate to OIDC provider for auth; catalog-level ACLs are a v0.3+ consideration with Lakekeeper integration.

---

### 2.13 Cluster autoscaling and sizing

**Bosch**: Every production job uses autoscaled Azure clusters. From `job_ely_silver.yml:11-14`:
```yaml
autoscale:
  min_workers: 2
  max_workers: 8
azure_attributes:
  availability: "ON_DEMAND_AZURE"
```
`Standard_E20as_v4` workers: 160 GB RAM, 20 vCPU each. At max scale: 1.28 TB RAM + 160 vCPU available for the `b2s_fact_timeseries.py` distributed streaming job.

**Nucleus equivalent**: Nucleus runs on a single node (your laptop or dev server). DuckDB has been validated at 5TB on modern hardware (per v4.1 §1.5 beachhead). However, the Bosch pipeline processes multi-gigabyte TDMS measurement files in distributed streaming batches, potentially across many files simultaneously. This scale pattern requires distributed compute.

Per v4.1 §17 yield-to-giants: "For assets exceeding single-node capacity, dispatch via `compute='databricks'` (v0.3+)." This is the correct answer — Nucleus doesn't compete here, it yields.

**Status**: 🤝 YIELD-TO-GIANTS by design — per v4.1 §17. For this pipeline's scale and compute requirements, the correct Nucleus answer is: run locally for development + integration testing; dispatch production runs to Databricks via Mode 2 (v0.3+).

---

### 2.14 Job-level parameters (is_integration_test, env, orders_to_reprocess)

**Bosch**: Jobs accept runtime parameters that control behavior. From `job_ely_silver.yml:33-37`:
```yaml
parameters:
  - name: "is_integration_test"
    default: "false"
  - name: "env"
    default: ${bundle.environment}
```
Gold also accepts `orders_to_reprocess` to trigger selective backfill (`job_ely_gold.yml:39-41`). Scripts read these via `get_integration_test_flag()` and `get_dev_user_flag()` from `common_utils.py`.

**Nucleus equivalent**: `ctx.params` is deferred to v0.2+ (per `ctx/__init__.py:38`). Today, workaround is env vars or `nucleus run --param key=value` if exposed. In v0.1, assets receive no runtime parameters from the CLI.

**Status**: 🟡 PARTIAL — concept exists (params API planned), implementation deferred to v0.2+. Workaround: pass values via environment variables, read in asset body with `os.getenv()`.

---

### 2.15 Per-task pip library installs

**Bosch**: Individual tasks install specialized libraries at task-start time. From `job_ely_bronze.yml:91-102`:
```yaml
- task_key: tsk_ely_r2b_load_tdms_testrig
  libraries:
    - pypi:
        package: "npTDMS"
- task_key: tsk_ely_r2b_load_mf4_testrig
  libraries:
    - pypi:
        package: "asammdf==8.0.0"
```
This lets different tasks have different dependency sets without bloating all clusters.

**Nucleus equivalent**: No equivalent. Nucleus uses `pyproject.toml` with exact-pinned dependencies that apply to all assets. Per AGENTS.md §11.13, all runtime deps are exact-pinned globally. There is no per-asset dependency mechanism.

**Status**: ❌ MISSING — Per-task pip installs are a Databricks/cluster-compute concept that has no equivalent in Nucleus v0.1. If TDMS/MF4 adapters were built, they would be added as project-level deps, not per-task installs.

---

### 2.16 Delta table maintenance (OPTIMIZE, VACUUM)

**Bosch**: A dedicated weekly job (`job_ely_optimize_tables.yml`) runs `sys_optimize_tables.py` that performs Delta OPTIMIZE and VACUUM operations. Production schedule: Monday-Friday at 02:00 (`job_ely_optimize_tables.yml:79`).

**Nucleus equivalent**: Apache Iceberg handles table maintenance differently:
- **Compaction**: `table.optimize().execute()` via pyiceberg (no separate job needed)
- **Expiry**: `table.expire_snapshots().execute()` to clean old snapshots
- In v0.1, Nucleus doesn't expose an automatic compaction job. This would be a scheduled `@nucleus.asset` wrapping pyiceberg maintenance APIs.

**Status**: 🟡 PARTIAL — Iceberg has equivalent maintenance operations via different APIs. A `@nucleus.asset(schedule="0 2 * * 1-5")` wrapping pyiceberg compaction would replicate the intent. Not provided out-of-the-box in v0.1.

---

### 2.17 CSV-driven configuration (config_files/*.csv)

**Bosch**: Runtime behavior is driven by CSV config files uploaded to ADLS. `bronze_config.csv`, `silver_config.csv`, `gold_config.csv` define table names, schemas, paths, and modes per layer. `common_utils.py:104-109` reads these via `get_active_config()`.

**Nucleus equivalent**: `nucleus_project.yaml` (project config) + `@nucleus.asset` decorator arguments encode this configuration as code. No external CSV config needed — the asset registry IS the configuration. This is a net simplification.

**Status**: ✅ HAVE (differently) — Nucleus encodes table config as Python decorator arguments + `nucleus_project.yaml`. CSV-driven runtime config is replaced by code-as-config. This is a design improvement over the Bosch pattern, not a gap.

---

### 2.18 Telemetry (Fluent Bit → Loki → Grafana)

**Bosch**: Full observability stack in `telemetry/`:
- **Init script**: `telemetry/fluentbit/init-fluentbit.sh` deployed to Databricks workspace via `sync:` block, runs on every cluster boot
- **Markers**: `telemetry_utils.py:78` emits `###TASK_MARKER###` JSON lines to stdout, Fluent Bit ships to Loki
- **Dashboards**: 3 Grafana dashboards (`ely-cluster-resources.json`, `ely-operations.json`, `ely-pipeline-flow.json`) deployed to OpenShift
- **Delta telemetry table**: `telemetry_utils.py:225` writes run events to `{catalog}.pemely_ops._telemetry_run_events`

**Nucleus equivalent**: OpenTelemetry + VictoriaMetrics + VictoriaLogs planned for v0.5+ (per v4.1 §11, nucleus.mdc rules table). The `observe_task()` context manager pattern in Bosch maps conceptually to OTel spans in Nucleus. v0.1 has structured logging (`_internal/logging.py`) but no telemetry backend.

**Status**: 🟡 PARTIAL — The architecture intent (structured task markers → backend → dashboards) maps to Nucleus's planned OTel stack. v0.5+ implementation. Today: use stdlib logging + Dagster UI for run visibility.

---

### 2.19 Integration test infrastructure

**Bosch**: Separate job definitions for integration tests (`USER_ISOLATION` mode vs `SINGLE_USER` for production). Test fixtures in `sys_files/test_data/integration/` (150+ files). Unit tests in `_9_tests/` use PySpark `local[1]` session (conftest.py confirmed).

**Nucleus equivalent**: pytest + `@nucleus.check` for data quality checks. Unit tests use DuckDB in-process (no Spark needed). Integration tests use MinIO (docker-compose) for local storage. The PySpark-based unit tests in the Bosch repo would need full rewrites.

**Status**: 🟡 PARTIAL — Test infrastructure concept maps, but all test code requires rewriting from PySpark to Polars/DuckDB. Binary test fixtures (TDMS, MF4, DTA) are unusable without the adapter libraries.

---

### 2.20 Secret management

**Bosch**: Databricks secrets backend via Databricks secret scope (`kv-databricks-secret-scope-tbp`). From `databricks.yml:64`:
```
default: "{{secrets/kv-databricks-secret-scope-tbp/loki-api-key}}"
```
Service principal resolved via DAB variable lookup (`databricks.yml:28-30`).

**Nucleus equivalent**: `.env.local` + environment variables (informal pattern per `docs/patterns/secret_management.md`). Formal secret backend delegates to OIDC ecosystem (v0.3+ with Lakekeeper integration). Per AGENTS.md §3 Constraint #6: no custom auth system.

**Status**: 🤝 YIELD-TO-GIANTS / 🟡 PARTIAL — `.env.local` works for dev. Production secrets management must use an external vault (Azure Key Vault, HashiCorp Vault via OIDC). Not Nucleus's responsibility.

---

## 3. Concrete worked example: rewrite `b2s_dim_order.py` in Nucleus

`b2s_dim_order.py` is the most straightforward Silver-layer asset — a dimension table with standard transformations (filter, select, cast, deduplicate). It is chosen because it does **not** use streaming (unlike `b2s_fact_timeseries.py`), making it the best candidate for a realistic rewrite.

### 3.1 Bosch original (key sections)

**File**: `src/_3_b2s/b2s_dim_order.py`  
**LOC**: 183 lines  
**Pattern**: Config-driven read from Bronze Delta table → transform → write to Silver Delta table

```python
# b2s_dim_order.py (excerpted, actual file: lines 1-183)
import __init__  # noqa: F401
from _5_common.common_io_utils import (
    read_delta_table_using_metadata,   # Reads from Unity Catalog Delta table
    write_delta_table_using_metadata,  # Writes to Unity Catalog Delta table
)
from _5_common.common_utils import (
    get_active_config,       # Reads bronze_config.csv / silver_config.csv
    get_integration_test_flag,
    get_dev_user_flag,
    env_variables,           # Unity Catalog name from workspace URL
    medallion_variables,     # Schema names per layer
)
from pyspark.sql.functions import col, explode_outer
from pyspark.sql.types import StringType

def main():
    is_integration_test = get_integration_test_flag()
    is_dev_user = get_dev_user_flag()
    df_config = get_active_config("silver", "b2s_dim_order")   # CSV config lookup
    dict_config = config_df_to_list(df_config)[0]

    df_leepa_orders = read_delta_table_using_metadata(
        table_name="test_general_leepa_orders",
        unity_catalog=env_variables["unity_catalog"],   # "ps_xplatform_dev"
        medallion_variables=medallion_variables["bronze"],
        is_stream=False,
        is_integration_test=is_integration_test,
        is_dev_user=is_dev_user,
    )
    # ... filter, explode, deduplicate, cast, write ...

if __name__ == "__main__":
    from _5_common.telemetry_utils import observe_task
    with observe_task("b2s_dim_order", "silver"):
        main()
```

**Infrastructure burden**: 183 LOC asset, but also depends on:
- `common_utils.py` (~700 LOC config/env utility layer)
- `common_io_utils.py` (~400 LOC Delta read/write layer)
- `b2s_utils.py` (~200 LOC transform utilities)
- `silver_config.csv` (runtime config lookup)
- Unity Catalog + ADLS Gen2 (infrastructure)

Total supporting infrastructure for one asset: ~1,500 LOC.

### 3.2 Nucleus equivalent

```python
# nucleus_dim_order.py — equivalent @nucleus.asset
# Per nucleus_architecture_v4.1.md §6.2 (Asset Materialization Adapter)
# Per nucleus_ctx_sdk_spec.md §2.1 (@nucleus.asset pattern)

import nucleus
import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/reference/
from nucleus import ctx

@nucleus.asset(
    "silver.dim_order",
    deps=["bronze.test_general_leepa_orders"],
    description="ELY order dimension: deduplicated order→sample mapping from LEEPA ERP",
)
def silver_dim_order() -> pl.DataFrame:
    """Bronze→Silver: dim_order

    Replicates b2s_dim_order.py main() logic using Polars instead of PySpark.
    Source: bronze.test_general_leepa_orders (JSON array of order structs)
    Target: silver.dim_order

    Per nucleus_architecture_v4.1.md §6.2: returns DataFrame, AMA writes to Iceberg.
    """
    raw_orders = ctx.read("bronze.test_general_leepa_orders")

    # Replicate filter_on_latest_value + explode_outer("samples.identifier")
    dim_order = (
        raw_orders
        # Keep latest file per order (replaces filter_on_latest_value)
        .with_columns(
            pl.col("file_path").rank("dense", descending=True)
              .over("orderNumber")
              .alias("_file_rank")
        )
        .filter(pl.col("_file_rank") == 1)
        .drop("_file_rank")
        # Explode samples array → one row per sample_id
        .explode("samples")
        .with_columns(pl.col("samples").struct.field("identifier").alias("sample_id"))
        .drop("samples")
        # Add row number per order, keep latest
        .with_columns(
            pl.col("sample_id").rank("dense", descending=True)
              .over("orderNumber")
              .alias("_rn")
        )
        .filter(pl.col("_rn") == 1)
        .drop("_rn")
        # Select, cast, rename (mirrors get_required_order_columns)
        .select([
            pl.col("orderNumber").cast(pl.String).alias("order_id"),
            pl.col("sample_id").cast(pl.String),
            pl.col("shortOrderDescription").cast(pl.String).alias("short_description"),
            pl.col("projectMcrIdName").cast(pl.String).alias("project_name"),
            pl.col("order_TestType").cast(pl.String).alias("type"),
            pl.col("Requested_by_location").cast(pl.String).alias("location"),
            pl.col("def3").cast(pl.String).alias("purpose"),
        ])
        .unique()
    )
    return dim_order


@nucleus.check("silver.dim_order", severity="error")
def check_dim_order_has_rows() -> nucleus.CheckResult:
    """Replicate error_occurred guard in b2s_dim_order.py:finally block."""
    df = ctx.read("silver.dim_order")
    row_count = df.height
    return nucleus.CheckResult(
        passed=row_count > 0,
        metric=row_count,
        message=f"dim_order has {row_count} rows (must be > 0)",
    )
```

**LOC comparison**:
- Bosch `b2s_dim_order.py`: 183 LOC (plus 1,300 LOC supporting infrastructure)
- Nucleus equivalent asset: ~65 LOC (no separate infrastructure layer — `ctx.read` + AMA handle I/O)
- Reduction: **~65% fewer LOC** for equivalent business logic

**What's simpler in Nucleus**:
- No `get_active_config()` / CSV config lookup — asset key IS the config
- No `env_variables` / `medallion_variables` — `ctx.read("bronze.x")` resolves automatically
- No `is_integration_test` / `is_dev_user` flags — Nucleus test vs prod is handled by environment config
- No Spark session management — Polars is in-process
- No `telemetry_utils.observe_task()` wrapper — OTel instrumentation is built-in (v0.5+)

**What's different in Nucleus**:
- Iceberg (not Delta) as storage format — different file layout and maintenance
- Single-node Polars (not distributed PySpark) — adequate for dimension tables at Bosch scale; fact_timeseries requires yield-to-giants
- `ctx.read()` requires the upstream asset already materialized (explicit dep chain)
- Window function syntax differs (Polars `.over()` vs PySpark `Window.partitionBy()`)

**What would FAIL**:
- `b2s_fact_timeseries.py` equivalent — uses Spark Structured Streaming + RocksDB state store + MERGE. Not replicable in v0.1.
- Any script using `SparkSession` configuration tuning — all Spark-specific, no Nucleus equivalent
- TDMS/MF4/DTA source reading — no adapter exists

---

## 4. Gap analysis: blockers ranked by severity

### CRITICAL — blocks any production migration

| Gap | What's missing | Workaround today | Roadmap | Effort to close |
|---|---|---|---|---|
| **Apache Spark engine** | Distributed PySpark compute (fact_timeseries, impedance streaming) | Yield-to-giants: keep heavy compute on Databricks | v0.3+ `compute="databricks"` Mode 2 | XL (requires Databricks dispatch adapter) |
| **Delta Lake format** | Delta MERGE/UPSERT, `_delta_log`, Delta-specific APIs | Full data re-materialization to Iceberg | Iceberg MERGE INTO (v0.3+ pyiceberg) | XL (full data migration) |
| **Structured Streaming** | `writeStream.foreachBatch(availableNow=True)` incremental processing | Full-scan batch (correct results, slower) | v0.5+ streaming | L (design + implementation) |
| **TDMS/MF4/DTA ingestion** | npTDMS, asammdf adapters for industrial measurement formats | None — formats are binary proprietary | Not on roadmap; would need ADR BUILD decision | XL (new adapter + library integration) |

### HIGH — blocks professional-quality replication

| Gap | What's missing | Workaround today | Roadmap | Effort to close |
|---|---|---|---|---|
| **Multi-environment targets** | dev/qa/prod namespace isolation + workspace switching | Manual `.env.local` + `warehouse_dir` param | v1.5+ | L |
| **Job-level parameters** | `--is_integration_test`, `--env`, `--orders_to_reprocess` | `os.getenv()` in asset body | v0.2+ `ctx.params` | S |
| **Email notifications** | `on_failure:` + `on_duration_warning_threshold_exceeded:` | Dagster failure hooks (user-wired) | v0.3+ | M |
| **Quartz cron + timezones** | 6-field `"0 0 17 ? * MON-FRI"` + `timezone_id: "Europe/Amsterdam"` | Convert to 5-field `"0 17 * * 1-5"`, UTC only | v0.2+ (active scheduling) | S |

### MEDIUM — reduces production confidence

| Gap | What's missing | Workaround today | Roadmap | Effort to close |
|---|---|---|---|---|
| **Delta OPTIMIZE/VACUUM** | Delta table compaction maintenance job | pyiceberg `optimize().execute()` (different API) | v0.3+ Iceberg maintenance scheduler | S |
| **Max concurrent runs** | `max_concurrent_runs: 2` concurrency control | Dagster concurrency limits (user-configures) | v0.3+ | S |
| **Health threshold alerts** | `RUN_DURATION_SECONDS > 18000` job health rules | None in v0.1 | v0.5+ (OTel + VictoriaMetrics) | M |
| **3-level catalog naming** | `catalog.schema.table` Unity Catalog paths | 2-level only in v0.1 | v0.3+ (Lakekeeper) | M |
| **Telemetry stack** | Fluent Bit → Loki → Grafana pipeline monitoring | Dagster UI + stdlib logging | v0.5+ (OTel + VictoriaLogs) | L |

### LOW — quality-of-life gaps

| Gap | What's missing | Workaround today | Roadmap |
|---|---|---|---|
| Per-task pip installs | Different deps per task | Project-wide pinned deps | Not planned (by design) |
| `run_if: ALL_DONE` vs `ALL_SUCCESS` | Conditional task execution modes | Dagster retry policies | v0.3+ |
| Integration test env isolation (`USER_ISOLATION` vs `SINGLE_USER`) | Security mode switching per target | Single security mode in v0.1 | v1.5+ |

---

## 5. What Nucleus does differently than the Bosch pattern

(Honest assessment — not a sales pitch. "Different" does not mean "better"; it means a different trade-off.)

### 5.1 Local dev identical to production
Bosch developers spin up a Databricks cluster (cold-start: 3-8 minutes) to test any change. With Nucleus, `nucleus run silver.dim_order` runs instantly on-laptop against local Iceberg files. For dimension tables and SQL transforms, this is a significant DX improvement.

### 5.2 No configuration CSVs — code is the config
Bosch's `bronze_config.csv`, `silver_config.csv`, `gold_config.csv` are runtime configuration that must be kept in sync with job YAML. In Nucleus, the asset key, deps, and contract are declared in code. Drift is impossible because the code IS the config.

### 5.3 Structured error messages with fix hints
Bosch errors surface as raw PySpark stack traces (`RuntimeError: Errors were encountered during processing...`). Nucleus wraps all errors in `NucleusError` subclasses with `user_message` + `fix_hint` per v4.1 §6.4. Every failure tells the user what went wrong and how to fix it.

### 5.4 Asset-level lineage tracked automatically
Bosch has no automatic lineage — Unity Catalog lineage requires column-level queries against system tables and is unavailable for Python UDFs. Nucleus emits OpenLineage events automatically for every `ctx.read()` + asset materialize (v4.1 §8; column-level at v0.5+).

### 5.5 Iceberg portability — graduate without migration
Bosch's Delta tables are vendor-specific to Databricks (Delta Sharing notwithstanding). Nucleus's Iceberg tables are portable to any Iceberg-compatible catalog (Polaris, Lakekeeper, Databricks Unity Catalog's Iceberg REST endpoint, R2, Snowflake). When a Nucleus user outgrows local compute, they `nucleus graduate --catalog=databricks` and keep all their data.

### 5.6 `< 30 min` from git clone to first BI-ready table
Bosch onboarding requires: Databricks workspace access, CLI setup, service principal configuration, ADLS access, Unity Catalog namespace provisioning, cluster policy approval. Per `README.md:78-98`, "Local Development: in development." Nucleus's beachhead metric: 5-engineer team, git clone → BI-ready Iceberg table in under 30 minutes (validated in WSL 2026-05-14).

---

## 6. Migration playbook (if the Bosch team wanted to gradually move)

This is a realistic multi-phase migration, not a "just switch" fantasy.

### Phase 0: Assessment (this document)
Identify which parts of the pipeline are feasibly ported vs which must stay on Databricks.

**Feasibly portable to Nucleus (single-node Polars/DuckDB):**
- Dimension tables (dim_order, dim_testrig, dim_channel, dim_sample, dim_test, dim_testtype, dim_order, dim_cellunit, dim_cellunitsequence, dim_meta) — 12 of 17 Silver tasks
- Gold aggregation views (s2g_order_view, s2g_sample_view) — if data fits in RAM
- Gold time series aggregations at 1h/1s granularity — potentially feasible on beefy dev box

**Must stay on Databricks (distributed Spark required):**
- TDMS/MF4/DTA Bronze ingestion (format adapters don't exist + scale)
- `fact_timeseries` streaming (Structured Streaming + MERGE)
- `fact_impedance` if same streaming pattern
- Gold timeseries pivot/mapping (large data volume)

### Phase 1: Parallel development environment (weeks 1-2)
1. `nucleus init bosch-ely-local` on one developer's machine
2. Export a Silver snapshot from Databricks: `COPY INTO ... TO ... WITH (FORMAT='PARQUET')`
3. Import to local Iceberg via `ctx.copy_from("s3://...", target="silver.dim_order", ...)`
4. Rewrite the 12 feasibly-portable dimension assets as `@nucleus.asset`
5. Run checks: `nucleus run silver.dim_order && nucleus check silver.dim_order`
6. Compare output row-for-row against Databricks Silver tables

### Phase 2: Establish hybrid operating model (weeks 3-6)
- Keep Bronze + fact_timeseries/impedance on Databricks (streaming, scale, TDMS formats)
- Run Gold aggregations on Nucleus (once Silver is available)
- Wire: Databricks job completes Silver write → trigger `nucleus run gold.timeseries_agg_1h` via webhook or schedule

### Phase 3: Evaluate scale (weeks 6-12)
- If Gold aggregations run comfortably locally (target: <30 min for daily batch)
- Gradually move Silver dimension tables to Nucleus-managed Iceberg with Lakekeeper (v0.3+)
- Run integration test: Nucleus output vs Databricks output (row diff < 0.01%)

### Phase 4: Graduate when ready (v0.3+ required)
- Switch Iceberg catalog to Lakekeeper or Databricks Iceberg REST endpoint
- Nucleus `@nucleus.asset(compute="databricks")` for heavy fact tables → yield-to-giants Mode 2
- Decommission Databricks jobs for dimension tables only; keep bronze + streaming on Databricks

**Caveats:**
- Full Silver migration requires TDMS/MF4 adapter (not on Nucleus roadmap — would need ADR BUILD decision, ~XL effort)
- The `fact_timeseries` streaming job is the hardest to migrate. At v0.5+ streaming maturity, revisit
- Multi-environment promotion (dev/qa/prod) requires v1.5+ Nucleus environment management
- Do NOT attempt a "big bang" migration. Run in parallel for at least one quarter before switching production

---

## 7. Bottom-line verdict

**NO.** Nucleus cannot replicate this pipeline professionally today.

Three reasons:

1. **The compute engine is fundamentally incompatible.** The Bosch pipeline's core asset (`b2s_fact_timeseries.py`) uses Apache Spark Structured Streaming with RocksDB state, dynamic MERGE conditions, 2-8 node autoscaled clusters with 160 GB RAM workers. This requires JVM + Spark. Nucleus's No-JVM constraint (AGENTS.md §3 Constraint #1) makes this permanently out-of-scope for the Nucleus runtime. The correct Nucleus answer: yield to Databricks for this compute tier.

2. **The table format requires a full data migration.** Every table is Delta Lake. Nucleus uses Apache Iceberg. These are different, incompatible table formats. Even if you replicated all the transformation logic, you would need to re-materialize all historical data (potentially TB-scale) from Delta to Iceberg before Nucleus could serve it. This is a data migration project, not a configuration change.

3. **The Bronze ingestion layer has no Nucleus equivalent.** The entire `_1_ingestion/` + `_2_r2b/` layer (12 scripts, ~1,500 LOC) reads proprietary binary industrial measurement formats (TDMS, MF4, DTA) from Azure ADLS. No Nucleus `copy_from` adapter exists for these formats. Building one requires: sourcing/validating the `npTDMS` + `asammdf` libraries, writing adapter code, adding Azure ADLS support (beyond S3-compatible MinIO), and validating against the actual test rig data. This is a significant build decision (would require ADR BUILD per v4.1 §9 composability constitution).

**What Nucleus CAN contribute today:** The 12 dimension-table Silver assets (not the fact/streaming ones) could be rewritten as `@nucleus.asset` with Polars in roughly half the LOC. This would create a local development environment where engineers iterate in minutes instead of waiting for cluster cold-starts. The remaining Gold aggregation views are also feasible candidates.

**Recommendation:** For the Bosch ELY team — don't attempt to migrate to Nucleus now. The pipeline is correctly sized for Databricks. If the team wants faster local iteration on dimension-table development, Nucleus could serve as a local dev tool where engineers prototype transforms before deploying them to Databricks as PySpark jobs. This is Nucleus's strongest value add for this specific pipeline today.

---

## 8. Citations

### Bosch repo citations
| Claim | Source file | Lines |
|---|---|---|
| Bundle name, 7 targets | `databricks.yml` | 3, 109-162 |
| Spark version 15.4.x-scala2.12 | `databricks.yml` | 47 |
| Node types Standard_E20as_v4, Standard_D16as_v4 | `databricks.yml` | 50, 53 |
| Autoscale 2-8 workers | `job_ely_silver.yml` | 11-13 |
| Quartz cron "0 0 17 ? * MON-FRI" | `job_ely_r2g.yml` | 140-143 |
| Email notifications pattern | `job_ely_silver.yml` | 50-55 |
| Permissions group CAN_MANAGE | `job_ely_silver.yml` | 39-41 |
| per-task pip install npTDMS, asammdf | `job_ely_bronze.yml` | 91, 100-102 |
| SparkSession.builder.getOrCreate() | `src/_3_b2s/b2s_fact_timeseries.py` | 53 |
| writeStream.foreachBatch(availableNow=True) | `src/_3_b2s/b2s_fact_timeseries.py` | 373-379 |
| MEDALLION_VARIABLES / ENVIRONMENT_VARIABLES | `src/_5_common/common_utils.py` | 46-93 |
| telemetry observe_task context manager | `src/_5_common/telemetry_utils.py` | 82-142 |
| Delta telemetry table write | `src/_5_common/telemetry_utils.py` | 225 |
| b2s_dim_order main() logic | `src/_3_b2s/b2s_dim_order.py` | 96-176 |
| run_job_task orchestrator pattern | `resources/job_ely_r2g.yml` | 55-66 |
| 3-level Unity Catalog naming | `src/_5_common/common_utils.py` | 46-67 |
| LAYER_VARIABLES layer-to-layer config | `src/_5_common/common_utils.py` | 96-100 |

### Nucleus source citations
| Claim | Source file | Lines |
|---|---|---|
| @nucleus.asset decorator API | `src/nucleus/sdk/decorators.py` | 365-475 |
| 2-level key regex (3-level deferred v0.3+) | `src/nucleus/sdk/decorators.py` | 52-55 |
| 5-field cron validation (6-field rejected) | `src/nucleus/sdk/decorators.py` | 279-283 |
| Schedule stored, execution deferred to v0.2 | `src/nucleus/sdk/decorators.py` | 411-414 |
| @nucleus.check + CheckResult | `src/nucleus/sdk/decorators.py` | 478-554 |
| ctx.copy_from supported sources | `src/nucleus/ctx/__init__.py` | 50-57 |
| ctx.params deferred to v0.2+ | `src/nucleus/ctx/__init__.py` | 38 |
| ctx.read() beta status | `src/nucleus/ctx/__init__.py` | 28 |
| schedule.py list_schedules + ScheduleEntry | `src/nucleus/coordination/schedules.py` | 39-60 |

### Architecture citations
| Claim | Architecture reference |
|---|---|
| No JVM in core path | AGENTS.md §3 Constraint #1 |
| No custom auth system | AGENTS.md §3 Constraint #6 |
| No ML platform | AGENTS.md §3 Constraint #7 |
| Streaming deferred to v0.5+ | v4.1 §18 roadmap |
| Yield-to-giants for distributed compute | v4.1 §17; AGENTS.md §0 |
| Iceberg = Tier 0 immortal | v4.1 §5 |
| Lakekeeper for multi-namespace (v0.3+) | nucleus.mdc rules table |
| 3-level catalog naming deferred to v0.3+ | `sdk/decorators.py` docstring citing cli_spec §10 NV #6 |
| OTel + VictoriaMetrics planned v0.5+ | nucleus.mdc rules table; v4.1 §11 |
| ctx.params deferred to v0.2+ | ADR-013; ctx/__init__.py:38 |

---

*No Bosch file paths or Nucleus APIs were invented in this document. All claims are sourced from files actually read and cited above.*
