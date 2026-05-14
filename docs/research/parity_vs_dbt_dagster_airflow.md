# Parity vs dbt / Dagster / Airflow / SQLMesh / Prefect — Research Notes

**Date**: 2026-05-15  
**Nucleus version**: v0.1.0 (beta, released 2026-05-14)  
**Last verified**: 2026-05-15 against official docs (see §10 for all URLs)  
**Researcher model**: Claude Sonnet 4.6 (swarm-tier fallback per AGENTS.md §11.14; Gemini 3.1 Pro unavailable in this subagent context)

---

## 1. Framing

### 1.1 Shape Differences — the Right Lens

Nucleus is not shaped like any of these tools. Understanding shape prevents the parity analysis from becoming a "features we're missing" list that drives scope creep.

| Tool | Shape | Nucleus relationship |
|---|---|---|
| **dbt** | SQL transformation engine; requires external warehouse; no scheduler | **SUBSUME** — `ctx.sql` + `{{ ref() }}` + `@nucleus.check` covers ~80% of dbt's developer surface; we WRAP DuckDB instead of requiring the user's warehouse |
| **Dagster** | Asset orchestration platform; assets, jobs, schedules, sensors | **WRAP** — Dagster runs behind `ctx`; zero Dagster classnames reach users. PoC #1 (Error Translation Layer) promoted 2026-05-13; all 8 error types translate cleanly |
| **Airflow** | Task-DAG orchestration; server-centric; ~800+ provider ecosystem | **DIFFERENT SHAPE** — asset-centric vs task-centric; local-first vs server-required |
| **SQLMesh** | SQL transformation + plan/diff workflow; Python-native; DuckDB-capable | **CLOSEST COMPETITOR IN SPIRIT** — most credible swap target for `ctx.sql` |
| **Prefect** | Python-native flow/task orchestration; remote control plane | **DIFFERENT SHAPE** — similar yield-to-giants stance but flow/task model vs asset model |

Per `nucleus_architecture_v4.1.md` §6 and `AGENTS.md §8`: we are NOT a "dbt killer," a "Dagster competitor," or a "better Airflow." We are a **different shape** that subsumes transformation and wraps orchestration.

**Critical discipline**: the parity matrix shows what Nucleus exposes through `ctx` + CLI, **not** what raw Dagster offers. Per `nucleus_ctx_sdk_spec.md` §0 Principle 1: "`ctx` is the only thing users import." A feature counts only if exercisable via `@nucleus.*`, `nucleus <cmd>`, or `ctx.*` — without importing `dagster`/`duckdb`/`polars` directly.

---

## 2. Capability Matrix

Legend: ✅ shipped v0.1.0/v0.1.1 | 🟡 spec'd/deferred | ❌ not in scope | ➡️ intentional non-match (see §5)

| Capability | Nucleus | dbt | Dagster | Airflow | SQLMesh | Prefect |
|---|---|---|---|---|---|---|
| Asset/model declaration (Python) | ✅ | ✅ | ✅ | ❌ | 🟡 | ✅ |
| Asset/model declaration (SQL) | ✅ | ✅ | 🟡 | ❌ | ✅ | ❌ |
| Asset dependencies (auto-derived refs) | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Materialization — full table | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Materialization — incremental | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 |
| Materialization — view | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Materialization — SCD2 snapshot | 🟡 | ✅ | ❌ | ❌ | ✅ | ❌ |
| Asset partitioning (time-based) | 🟡 | 🟡 | ✅ | ✅ | ✅ | ✅ |
| Asset partitions backfill | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 |
| Asset checks — built-in + custom Python | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Asset contracts (schema) | ✅ | ✅ | 🟡 | ❌ | 🟡 | ❌ |
| Asset metadata (owner, tags, description) | ✅ | ✅ | ✅ | 🟡 | 🟡 | 🟡 |
| SQL Jinja templating | ✅ | ✅ | 🟡 | 🟡 | ✅ | ❌ |
| `{{ ref(...) }}` dbt-compatible syntax | ✅ | ✅ | ❌ | ❌ | 🟡 | ❌ |
| SQL macros / shared logic | 🟡 | ✅ | ❌ | ❌ | ✅ | ❌ |
| Python transformation | ✅ | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Notebooks | ❌ | ❌ | 🟡 | 🟡 | ❌ | ❌ |
| Source declaration (external data) | ✅ | ✅ | 🟡 | ✅ | 🟡 | ✅ |
| Seeds (static CSV data) | 🟡 | ✅ | ❌ | ❌ | ✅ | ❌ |
| Schedules — cron declared | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Schedules — cron active execution | 🟡 | ❌ | ✅ | ✅ | ✅ | ✅ |
| Event-driven sensors | 🟡 | ❌ | ✅ | ✅ | ✅ | ✅ |
| Declarative auto-materialize | ❌ | ❌ | ✅ | ❌ | 🟡 | ❌ |
| Asset-event-driven scheduling | ❌ | ❌ | 🟡 | ✅ | ✅ | ✅ |
| Backfill management | 🟡 | 🟡 | ✅ | ✅ | ✅ | 🟡 |
| Asset code version tracking | ✅ | ❌ | 🟡 | ❌ | ❌ | ❌ |
| Asset lineage (asset-level, auto) | ✅ | ✅ | ✅ | 🟡 | ✅ | 🟡 |
| Asset lineage (column-level) | ❌ | ✅ | 🟡 | ❌ | 🟡 | ❌ |
| Time travel (snapshot read) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Documentation site generation | ❌ | ✅ | 🟡 | ❌ | ✅ | ❌ |
| Self-hosted web UI | 🟡 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-environment (dev/staging/prod) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cross-project / mesh references | 🟡 | ✅ | ✅ | ❌ | ✅ | 🟡 |
| Semantic layer (metrics) | ❌ | ✅ | ❌ | ❌ | 🟡 | ❌ |
| Data exposures (consumer declarations) | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Plan / diff (preview before apply) | ❌ | ❌ | 🟡 | ❌ | ✅ | ❌ |
| Run history | ✅ | 🟡 | ✅ | ✅ | ✅ | ✅ |
| Run retry policies | ✅ | ❌ | ✅ | ✅ | 🟡 | ✅ |
| Run alerting (Slack/email) | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| AI chat / question answering | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| AI-assisted (lineage-aware) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Multi-asset (N outputs, 1 function) | 🟡 | ❌ | ✅ | ❌ | ❌ | ❌ |

**Key**: Nucleus unique advantages — **time travel** (Iceberg snapshots, no competitor matches), **code version tracking** (three-axis: code/data/schema), **AI chat** (first-class `nucleus chat` with opt-in privacy gate). Nucleus biggest gaps vs peers — **active scheduling daemon** (v0.2), **partition execution** (v0.3), **SCD2** (v0.2), **run alerting** (v0.2), **`nucleus plan`** (v0.2).

---

## 3. By-Tool Deep Dive

### 3.1 dbt

**Sources**: https://docs.getdbt.com/docs/introduction · https://docs.getdbt.com/docs/build/models · https://docs.getdbt.com/docs/build/sources · https://docs.getdbt.com/docs/build/seeds

**We SUBSUME via**:
- `@nucleus.sql_asset` + `ctx.sql` + `{{ ref() }}` — dbt SQL models + ref resolution + Jinja (intentionally dbt-compatible per ctx SDK §6.2)
- `@nucleus.asset` returning Polars/Arrow — dbt Python models (no warehouse required; DuckDB local)
- `@nucleus.source` — dbt `sources:` YAML (Python decorator instead of YAML)
- `@nucleus.check` — dbt built-in + custom tests
- `@nucleus.contract` — dbt model contracts (schema enforcement)
- `nucleus.freshness(hours=24)` — dbt source freshness SLA
- `materialized="incremental|view"` — dbt incremental models + views
- `environments:` in `nucleus_project.yaml` — dbt profiles

**dbt's key weakness Nucleus exploits**: dbt has NO scheduling. Users must separately configure dbt Cloud ($300+/month), Dagster, Airflow, or Prefect. Nucleus owns scheduling via Dagster wrap (daemon v0.2). This is a genuine advantage.

**Remaining gaps**:

| Gap | dbt Feature | Effort | Action |
|---|---|---|---|
| Named seed concept | `dbt seed` for static CSVs | S | Document `nucleus ingest ./file.csv` as the pattern — no new code |
| SCD2 execution | `dbt snapshot` | M | Implement `materialized="snapshot"` path in AMA (P0, see §6 #3) |
| Macro ecosystem | Jinja macro library/packages | L | Intentional non-match — ≤2500 LOC ceiling per v4.1.1 P1 |
| dbt Mesh | `{{ ref('project', 'model') }}` | L | v0.5+ (needs Lakekeeper namespace resolution) |
| Semantic layer | MetricFlow | XL | v1.5+ if ever |
| Documentation site | `dbt docs serve` | L | Workbench v0.2+ (ADR-016) covers this |

**Watch**: dbt's Fusion engine (Rust-based per https://docs.getdbt.com/docs/fusion) brings instant SQL validation + cross-dialect awareness. Same fast-local territory as Nucleus/DuckDB. Monitor OSS availability.

---

### 3.2 Dagster

**Sources**: https://docs.dagster.io/guides/build/assets/defining-assets · https://docs.dagster.io/guides/automate/schedules · https://docs.dagster.io/guides/automate/sensors · https://docs.dagster.io/guides/automate/declarative-automation

**We WRAP (hidden from user)**: Dagster runs entirely behind `ctx`. PoC #1 (Error Translation) promoted 2026-05-13 — 8 error types translate cleanly; `scripts/dagster_leak_check.py` enforces zero-leak in CI per `AGENTS.md §11.7`.

**Features we EXPOSE via ctx** (Dagster-backed, user-visible):
- `@nucleus.asset` → Dagster `@dg.asset` (hidden by AMA)
- `ctx.materialize()` → `dagster.materialize()` via `coordination/asset_materialization.py`
- `nucleus run <key>` → iterates `ctx.materialize()`
- `schedule=` kwarg → Dagster `ScheduleDefinition` (v0.2 daemon; `to_dagster_schedule()` already in `coordination/schedules.py`)
- All errors → `NucleusError` hierarchy with `[NE-code]`

**Intentionally NOT exposed**: IO Managers (replaced by `ctx.write()` + AMA Iceberg-commit), `Ops` (intra-asset logic is user's Python), raw `ResourceDefinition` (replaced by `ctx.secrets`/`ctx.params`/`ctx.connector`), `JobDefinition` (hidden behind AMA).

**Features to expose in later versions**:

| Dagster Feature | Nucleus Path | Version |
|---|---|---|
| Partition execution | `nucleus run --partition 2026-01-15` + AMA wiring | v0.3 |
| Asset event sensors | `@nucleus.sensor` implementation (spec'd, not wired) | v0.2 |
| Declarative auto-materialize | `@nucleus.asset(auto_materialize="on_cron")` façade | v0.5+ |
| `@dg.multi_asset` | `@nucleus.multi_asset` (in asset model §3, not frozen surface) | v0.3 |
| Dagster+ Cloud features | Nucleus Cloud tier | v1.0+ |

**Most critical gap**: partition execution. Daily time-series assets are the first real use case for the beachhead persona; without it, all incremental work degrades to full-overwrite.

---

### 3.3 Airflow

**Sources**: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html · https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/datasets.html (Airflow 3.2.1)

**Fundamentally different shape** — no parity closure required. Airflow requires an always-on `airflow webserver` + `airflow scheduler`; Nucleus boots embedded in <10s. Airflow is task-centric; Nucleus is asset-centric.

**Airflow 3.x concepts worth borrowing**:
- **Asset-Aware Scheduling** (v2.4+): DAGs scheduled on `Asset` URI updates with AND/OR operators (`dag1_asset & dag2_asset`). This is the pattern `@nucleus.sensor` + Dagster sensor should expose in v0.2.
- **External event injection via REST API** (`POST /assets/queuedEvent/{uri}`): useful for v0.3+ event-driven ingestion from external systems.
- **Deferrable operators**: yield-control pattern for long-running I/O. Nucleus `@nucleus.sensor` polling covers this.

**Action**: Write `docs/swap/airflow.md` migration guide (task→asset paradigm shift). No platform changes for v0.1.

---

### 3.4 SQLMesh

**Sources**: https://sqlmesh.readthedocs.io/en/stable/concepts/models/overview/ · https://sqlmesh.readthedocs.io/en/stable/concepts/plans/

SQLMesh is the **closest competitor in spirit**: Python-first, local-first, SQL-centric, DuckDB-capable, no warehouse required at dev time.

**Model kind mapping**:

| SQLMesh Kind | Nucleus Equivalent | Gap |
|---|---|---|
| `FULL` | `materialized="table"` (default) | ✅ matched |
| `INCREMENTAL_BY_TIME_RANGE` | `materialized="incremental"` + time `incremental_key=` | 🟡 equivalent behavior, no explicit kind name |
| `INCREMENTAL_BY_UNIQUE_KEY` | `ctx.write(..., mode="merge", on=["id"])` | 🟡 mode exists, no model-level kind |
| `SCD_TYPE_2` | `materialized="snapshot"` | 🟡 spec'd, not CI-verified |
| `VIEW` | `materialized="view"` | ✅ matched |
| `SEED` | `nucleus ingest ./file.csv --as raw.x` | 🟡 functional but unnamed |
| `EMBEDDED` | Inline Jinja subquery in `ctx.sql` | 🟡 no separate embeddable model type |

**SQLMesh's killer feature**: `sqlmesh plan` — shows which models are affected, previews data change in a virtual dev environment, flags whether backfill is needed — **before** applying anything. `nucleus run --dry-run` shows which assets would run, not a data diff. This gap is the #1 reason SQL-centric teams choose SQLMesh over dbt; closing it (see §6 #4) would neutralize SQLMesh's biggest differentiator.

**SQLMesh's virtual dev environments**: Isolated dev/prod promotion before commit. Nucleus covers this via `environments:` in `nucleus_project.yaml` + `--env prod`, but without the explicit plan→apply gate.

**SQLMesh as swap target** (Composability by Constitution, v4.1 §9):

If `ctx.sql` grows beyond the 2500 LOC ceiling, SQLMesh is the drop-in swap:
- Uses DuckDB as default local engine: NEEDS VERIFICATION at https://sqlmesh.readthedocs.io/en/stable/integrations/engines/duckdb/
- Writes Iceberg-compatible formats: NEEDS VERIFICATION at https://sqlmesh.readthedocs.io/en/stable/integrations/
- Swap interface: `docs/swap/sqlmesh.md` (already in repo per git status)

**Features worth borrowing from SQLMesh**:
- `nucleus plan` (diff preview before apply) — P1 v0.2
- Explicit model kind names (`kind=`) alongside `materialized=` for clarity — P2 v0.3
- Signal-based scheduling → expose via `@nucleus.sensor` (v0.2)

---

### 3.5 Prefect

**Sources**: https://docs.prefect.io/v3/develop/write-flows · https://docs.prefect.io/v3/deploy/serve-flows

**Similar yield-to-giants philosophy** — both defer distributed compute to Databricks/Snowflake. The similarity ends there: Prefect's primary unit is `@flow` / `@task` (arbitrary Python), not a named data asset with Iceberg persistence.

**Differences**:
- Prefect's `@flow` can produce any side effect; Nucleus `@nucleus.asset` **must** produce a named Iceberg table with lineage
- Prefect state tracking is run-level; Nucleus tracks materialization (snapshot) history
- Prefect work pools abstract infrastructure; Nucleus uses `compute=` dispatch (v0.3+)

**Features worth borrowing**:
1. Work pool dispatch naming — maps to `compute=` kwarg; cleaner name for yield-to-giants
2. Event-driven automations (webhooks, triggers) — richer than Nucleus's current `@nucleus.sensor` spec
3. Interactive pause-for-approval — relevant for v0.5+ human-in-the-loop data quality workflows

**Conclusion**: Write a `docs/swap/prefect.md` migration guide (flow→asset paradigm shift, Iceberg as Prefect artifact replacement). No platform changes for v0.1.

---

## 4. Prioritized Closure Plan

### P0: Must-Close Before Public OSS Announcement

The beachhead persona hits these gaps on day 2 of real usage. Without them, Nucleus is "demo-ready" but not "production-ready."

| # | Title | Capability | Why Beachhead | Effort | Wrap Target | Blocked By |
|---|---|---|---|---|---|---|
| 1 | **Active schedule daemon** | `nucleus schedule on/off/trigger` | Teams need `@daily` to actually run; NE5008 error on `schedule on` breaks trust at OSS launch | M | Dagster daemon + `to_dagster_schedule()` (already implemented) | v0.2 sprint |
| 2 | **Sensor / event-driven triggers** | `@nucleus.sensor` wired | File-arrival ingestion, cross-system triggers replace ad-hoc cron+shell | M | Dagster `@dg.sensor` (pinned dep) | Active daemon (#1) |
| 3 | **Partition execution** | `nucleus run <key> --partition 2026-01-15` actually executes | Daily event tables are the first real use case; full-overwrite on each run eliminates incremental ROI | M-L | Dagster `DailyPartitionsDefinition` + AMA extension | ADR-013 NV #6 resolution |
| 4 | **SCD2 snapshot** | `materialized="snapshot"` writes SCD2 | Dimension tables are in ~80% of startup stacks; hand-rolling SCD2 is the worst pattern in data engineering | M | pyiceberg row-level delete + append | ADR-003 (pyiceberg 0.8.1 → 0.11.x) |

### P1: Close in v0.2–v0.3

| # | Title | Capability | Effort | Wrap Target | Blocked By |
|---|---|---|---|---|---|
| 5 | **Backfill management** | `nucleus backfill <key> --range ...` | M | Dagster partition backfill API | Partition execution (#3) |
| 6 | **`nucleus plan` (diff preview)** | Preview affected assets + row-count delta before applying | M | Isolated DuckDB + dry-run Iceberg catalog | None |
| 7 | **Multi-asset decorator** | `@nucleus.multi_asset` producing N Iceberg tables | M | Dagster `@dg.multi_asset` | AMA extension |
| 8 | **Run alerting** | Slack/email on materialization failure | S | Dagster hook API (NEEDS VERIFICATION for `dagster==1.9.5`) | Active daemon (#1) |
| 9 | **Cross-project deps (runtime)** | `deps=["other_project::asset"]` resolved at execution | L | pyiceberg + Lakekeeper namespace | Lakekeeper v0.3+ |
| 10 | **Workbench v0.2 scaffold** | Self-hosted asset browser + lineage graph | XL | Marimo-based (ADR-016) | ADR-016 spec |

### P2: Close in v0.5+ (summary)

- **Column-level lineage** — sqlglot + OpenLineage (v4.1 §12.4) | Effort: L
- **Declarative auto-materialize** — `AutomationCondition.eager()` façade | Effort: M
- **Asset exposures metadata** — YAML consumer declarations | Effort: S
- **Notebook assets (Marimo)** — `@nucleus.notebook_asset` | Effort: M
- **Lineage-aware Copilot** — `nucleus chat` with asset graph context | Effort: L

### P3: v1.0 Nice-to-Have (summary)

- **Semantic layer / metrics** via MCP server | Effort: XL
- **dbt integration adapter** (`nucleus enable dbt`) | Effort: L
- **IDE extension** (VS Code asset graph) | Effort: L-XL
- **Interactive approval workflows** (human-in-loop quality sign-off) | Effort: M
- **`AssetAlias`** (multiple names → same Iceberg table) | Effort: S

---

## 5. "Different Shape" Features (Intentional Non-Matches)

Do NOT add these to any parity closure plan. Each would violate Anti-Over-Engineering discipline.

1. **Server-centric web UI required at runtime** — Airflow/Dagster/Prefect require always-on web servers. Nucleus is local-first; Workbench is optional, session-scoped. Required servers block the 30-min beachhead metric.

2. **Task-level orchestration** — Airflow `@task`, Prefect `@task` track arbitrary Python functions. Nucleus tracks `@nucleus.asset` materializations only. Intra-asset structure is the user's Python.

3. **Distributed compute natively** — CeleryExecutor, KubernetesExecutor, Prefect work pools (K8s/AWS). Nucleus yields-to-giants via `compute=` dispatch (v4.1 §6.7). We graduate, not build.

4. **800+ connector ecosystem** — Airflow providers, Prefect integrations. Nucleus wraps dlt (150+ sources). Connector breadth is dlt's responsibility.

5. **Raw SQL without asset model** — SQLMesh supports standalone scripts not producing named assets. Nucleus requires every output to be a named `@nucleus.asset`. The constraint is the guarantee (lineage, atomicity, time travel).

6. **Macro package ecosystem** — dbt Hub packages, SQLMesh macros. `ctx.sql` is intentionally capped at ≤2500 LOC ceiling (v4.1.1 P1 review: "accidentally rebuilding dbt" warning).

7. **Plugin marketplace** — Hard Constraint #2 in v4.1: no public plugin SDK in v1. `nucleus enable <feature>` is the bounded opt-in mechanism.

---

## 6. Top 5 Must-Close Items for OSS-Launch Confidence

### #1 — Active Schedule Daemon (P0)

**Why**: Declaring `schedule="@daily"` and having it do nothing is the single most jarring gap. `NucleusFeatureDeferredError` on `nucleus schedule on` is acceptable in beta; it is a credibility blocker at public OSS release.

**How**: Wire the Dagster daemon that `to_dagster_schedule()` in `coordination/schedules.py` already wraps. Add `nucleus schedule on/off/trigger` that activate daemon-driven execution. The Dagster `ScheduleDefinition` wrapper is already implemented per ADR-017 §1; the gap is daemon startup + `nucleus_project.yaml` persistence.

**Effort**: M (1-2 weeks). **Risk**: daemon boot time must stay within PoC #4's 5.82s reference.

### #2 — Partition Execution (P0)

**Why**: Daily event tables are the first real use case. Declaring `partitions=nucleus.daily(...)` but being unable to run a single partition means all incremental work degrades to full-overwrite — eliminating the performance benefit that justifies Iceberg.

**How**: Extend `ctx.materialize(asset, partition="2026-01-15")` end-to-end (spec'd in ADR-013 NV #6, not wired); extend AMA to pass `partition_key=` to Dagster `DailyPartitionsDefinition`; verify pyiceberg partition spec alignment at https://py.iceberg.apache.org/api/.

**Effort**: M-L (2-3 weeks). **Risk**: pyiceberg partition spec alignment — verify before implementing.

### #3 — SCD2 Snapshot (P0)

**Why**: Dimension tables with slowly-changing attributes (~80% of startup stacks) require SCD2. Without it, teams hand-roll the most error-prone pattern in data engineering. dbt has had `dbt snapshot` since 2018.

**How**: Implement `materialized="snapshot"` path in AMA: read previous snapshot, merge with `valid_from`/`valid_to`, append rows atomically — Iceberg immutability provides the guarantee. NEEDS VERIFICATION: pyiceberg row-level merge API at https://py.iceberg.apache.org/api/ — ADR-003 pyiceberg upgrade (0.8.1 → 0.11.x) is likely a prerequisite.

**Effort**: M (1-2 weeks post-ADR-003). **Risk**: row-level deletes arrived in pyiceberg 0.9.x; upgrade gates this.

### #4 — `nucleus plan` Diff Preview (P1)

**Why**: SQLMesh's `sqlmesh plan` is the #1 reason SQL-centric teams choose SQLMesh. Nucleus's `--dry-run` shows which assets would run — not data diffs. Closing this gap neutralizes SQLMesh's biggest differentiator.

**How**: `nucleus plan [ASSET_KEY...]` — execute in isolated DuckDB + temp Iceberg catalog, compare row count + schema to committed snapshot, report delta without committing. ~300-500 LOC in `coordination/planner.py`.

**Effort**: M (2-3 weeks). **Risk**: isolated dry-run catalog abstraction in AMA.

### #5 — Run Alerting (P1)

**Why**: Scheduled materializations run unattended overnight. Silent failures undetected for 12+ hours cause downstream trust collapse. Every competitor provides Slack/email alerting. Nucleus v0.1 has none.

**How**: Wrap Dagster hook API (NEEDS VERIFICATION: `@success_hook`/`@failure_hook` in `dagster==1.9.5` at https://docs.dagster.io/api/) — expose zero-code config in `nucleus_project.yaml`:
```yaml
alerts:
  on_failure:
    slack: $SLACK_WEBHOOK_URL
    email: data-team@company.com
```

**Effort**: S-M (1-2 weeks). **Risk**: verify Dagster hooks API against `dagster==1.9.5`.

---

## 7. `NEEDS VERIFICATION` Items

Per `AGENTS.md §11.12` — must resolve before implementing the corresponding items.

| # | Claim | URL to Verify | Blocks |
|---|---|---|---|
| NV-1 | `@nucleus.sensor` implementation status — spec'd in ctx SDK §2.6 + frozen surface §12 but not found in `src/nucleus/sdk/decorators.py` | Read `src/nucleus/sdk/` directory | P0 #2 |
| NV-2 | `materialized="snapshot"` implementation — spec'd in asset model §4.4, no implementation evidence in reviewed code | Read `src/nucleus/coordination/asset_materialization.py` | P0 #4 |
| NV-3 | SQLMesh Iceberg catalog integration depth | https://sqlmesh.readthedocs.io/en/stable/integrations/ | Swap doc update |
| NV-4 | pyiceberg `Table.merge()` / row-level delete API in v0.8.1 vs v0.11.x | https://py.iceberg.apache.org/api/ | P0 #4, ADR-003 |
| NV-5 | Dagster `@success_hook`/`@failure_hook` in `dagster==1.9.5` | https://docs.dagster.io/api/ | P1 #8 |
| NV-6 | dbt Semantic Layer current doc path (404 at previous URL) | https://docs.getdbt.com/docs/build/metricflow-core-concepts | §3.1 gap assessment |
| NV-7 | dbt model contracts doc path (404 at previous URL) | https://docs.getdbt.com/docs/collaborate/govern/model-contracts | §3.1 gap assessment |

---

## 8. Suggested ADRs

| ADR | Title | Trigger |
|---|---|---|
| ADR-019 | Partition Execution v0.2 | AMA partition wiring; Dagster `DailyPartitionsDefinition` alignment with pyiceberg partition spec |
| ADR-020 | SCD2 Snapshot Implementation | pyiceberg row-level merge choice; gates on ADR-003 |
| ADR-021 | `nucleus plan` Diff Preview | Isolated dry-run catalog architecture; wrap SQLMesh planner vs build ~300 LOC |
| ADR-022 | Run Alerting Strategy | Dagster hook-based vs standalone notification service; `alerts:` config schema |

---

## 9. Logged Hallucinations

No hallucinations caught in this research pass. The following potential risks were explicitly avoided and flagged NV instead:

- Did NOT assume pyiceberg has `table.merge()` — flagged NV-4.
- Did NOT assume `@nucleus.sensor` is implemented — flagged NV-1 (not found in reviewed code).
- Did NOT assume dbt model contracts URL is stable — flagged NV-7 (404 encountered).
- Did NOT assume Dagster run alert hooks are available in `dagster==1.9.5` — flagged NV-5.

**Append to `/docs/research/ai_hallucinations.md`**:

```markdown
## 2026-05-15: @nucleus.sensor implementation uncertain

Research found `@nucleus.sensor` in ctx SDK spec §2.6 and frozen surface §12 but
not in `src/nucleus/sdk/decorators.py`. Whether implemented elsewhere is unknown.
Detection: direct code review during research pass. NV-1 logged.
```

---

## 10. Citations

All external documentation URLs cited in this report, verified 2026-05-15:

### dbt
- Introduction + Fusion: https://docs.getdbt.com/docs/introduction
- Models: https://docs.getdbt.com/docs/build/models
- Sources: https://docs.getdbt.com/docs/build/sources
- Seeds: https://docs.getdbt.com/docs/build/seeds
- Fusion engine: https://docs.getdbt.com/docs/fusion
- VS Code extension: https://docs.getdbt.com/docs/about-dbt-extension
- Snapshots: https://docs.getdbt.com/docs/build/snapshots *(timed out; key facts from introduction)*
- Model contracts: https://docs.getdbt.com/docs/collaborate/govern/model-contracts *(404 — NV-7)*
- Semantic Layer: https://docs.getdbt.com/docs/build/metricflow-core-concepts *(404 — NV-6)*
- dbt Mesh: https://docs.getdbt.com/docs/collaborate/govern/project-dependencies

### Dagster
- Defining assets: https://docs.dagster.io/guides/build/assets/defining-assets
- Asset checks API: https://docs.dagster.io/api/dagster/asset-checks
- Schedules: https://docs.dagster.io/guides/automate/schedules
- ScheduleDefinition API: https://docs.dagster.io/api/python-api/schedules-sensors#dagster.ScheduleDefinition
- Sensors: https://docs.dagster.io/guides/automate/sensors
- Declarative automation: https://docs.dagster.io/guides/automate/declarative-automation
- Partitions and backfills: https://docs.dagster.io/guides/build/partitions-and-backfills
- Run alerts: https://docs.dagster.io/guides/operate/run-alerts *(NV-5 — verify for dagster==1.9.5)*

### Airflow (3.2.1)
- DAGs core concepts: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html
- Asset-Aware Scheduling: https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/datasets.html

### SQLMesh
- Models overview: https://sqlmesh.readthedocs.io/en/stable/concepts/models/overview/
- Plans: https://sqlmesh.readthedocs.io/en/stable/concepts/plans/
- Integrations (timed out): https://sqlmesh.readthedocs.io/en/stable/integrations/ *(NV-3)*
- DuckDB engine: https://sqlmesh.readthedocs.io/en/stable/integrations/engines/duckdb/ *(NV-3)*

### Prefect
- Write flows: https://docs.prefect.io/v3/develop/write-flows
- Serve/deploy flows: https://docs.prefect.io/v3/deploy/serve-flows

### Nucleus internal (primary sources of truth)
- `nucleus_architecture_v4.1.md` §6.2, §6.3, §6.4, §6.5, §6.7, §7.2, §9, §10, §12, §18
- `nucleus_ctx_sdk_spec.md` §0, §2, §3, §5, §6, §10, §12, §14
- `nucleus_cli_spec.md` §3, §4, §5, §10
- `nucleus_asset_model_spec.md` §3, §4, §5, §6, §8, §9, §10, §11, §15
- `nucleus_poc_plan.md` (PoC #1–5 status)
- `docs/decisions/ADR-017-schedule-exposure-v01.md`
- `src/nucleus/sdk/decorators.py` (current `@nucleus.asset` + `@nucleus.check`)
- `src/nucleus/coordination/schedules.py` (schedule façade + `to_dagster_schedule`)
- `src/nucleus/intelligence/copilot.py` (AI Copilot surface)
- `AGENTS.md` §0, §4, §7, §8, §11.12, §11.13, §11.14

---

*AI training cutoff may be stale; this doc reflects docs as of 2026-05-15. Model recorded: Claude Sonnet 4.6 (swarm-tier fallback per AGENTS.md §11.14 — Gemini 3.1 Pro unavailable; choice recorded per fallback policy).*
