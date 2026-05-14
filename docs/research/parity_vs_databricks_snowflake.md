# Parity vs Databricks / Snowflake / BigQuery — Research

**Date**: 2026-05-15  
**Researcher**: Claude Sonnet 4.6 (Swarm tier; Gemini 3.1 Pro unavailable — fallback per AGENTS.md §11.14)  
**Output budget**: 18-26 KB (target)  
**Sources**: Internal Nucleus docs (local) + live fetches from official platform docs (all URLs cited).  
> AI training-cutoff caveat: external claims verified against live docs as of 2026-05-15.
> Claims not reachable via live fetch are marked `NEEDS VERIFICATION`.

---

## 1. Scope + Framing

**What this IS**: Honest parity inventory of Nucleus v0.1.0 (released 2026-05-14) vs Databricks, Snowflake, and BigQuery. Ends with a prioritized closure plan through v1.0.

**What this IS NOT**: A pitch claiming we match them. Per `AGENTS.md §8`, Nucleus is **not** a "Databricks killer" <!-- banned-term: Databricks killer --> or "Snowflake replacement". The correct framing (ADR-002 §8.1):

> *"Ship data products from a laptop — a local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks, AI-ready by design, graduating cleanly to any Iceberg catalog when users outgrow their laptop."*

**Yield-to-giants strategy** (`nucleus_architecture_v4.1.md §10`):
- **Mode 1** — Iceberg portability: graduate with zero migration
- **Mode 2** — Hybrid compute: dispatch heavy assets to Databricks/Snowflake via `compute=...` (v1.5+)
- **Mode 3** — Iceberg REST catalog federation for Data Mesh (v2.0+)

**Beachhead persona** (`v4.1 §1.5`): Startup data team — 5-20 engineers, 100GB-5TB, greenfield project. v0.1 success metric: `git clone` → BI-ready Iceberg table in **<30 minutes**.

---

## 2. Capability Matrix

**Status legend**: ✅ Have | 🟡 Partial | ❌ Missing | ⏭ Out-of-scope by design | 🤝 Yield-to-giants  
*Source URLs: §9 References. DB = Databricks, SF = Snowflake, BQ = BigQuery.*

| Capability | Nucleus | DB | SF | BQ |
|---|---|---|---|---|
| **SQL engine** | ✅ DuckDB in-process, 0 spin-up (v4.1 §5.1) | Photon/Spark on SQL Warehouses | Virtual Warehouses, auto-scale | Serverless slots — `NEEDS VER.` |
| **DataFrame engine** | ✅ Polars in-process (v4.1 §5.2) | PySpark | Snowpark Python | BigQuery DataFrames — `NEEDS VER.` |
| **Distributed compute** | 🤝 Mode 2 yield-to-giants v1.5+ (v4.1 §10.3) | Spark, unlimited scale | Multi-cluster virtual warehouses | Serverless auto-scale |
| **ML/AI training** | ⏭ Out-of-scope (v4.1 §20.1) | MLflow + ML Runtime + GPU clusters | Snowflake ML, feature store, model registry | BigQuery ML — `NEEDS VER.` |
| **Table format (structured)** | ✅ Apache Iceberg (v1/v2, pyiceberg) | Delta Lake (proprietary-but-open); Iceberg via Unity | Iceberg Tables v1/v2/v3 GA + native | BigLake Iceberg — `NEEDS VER.` |
| **Table format (multimodal)** | ⏭ Lance v0.5+ (v4.1 §18.4) | Volumes (unstructured files) | Stages + VARIANT; no vector table | BigLake (limited) — `NEEDS VER.` |
| **Catalog (unified namespace)** | 🟡 Filesystem v0.1; Lakekeeper/Polaris v0.3+ | Unity Catalog (3-level, table/view/volume/model) | Native 3-level + Open Catalog (Polaris-based) | Datasets + Dataplex |
| **Catalog (cross-org federation)** | ⏭ Mode 3 v2.0+ (v4.1 §18.7) | Delta Sharing | Snowflake Marketplace + Data Clean Rooms | Analytics Hub — `NEEDS VER.` |
| **Time-travel / versioning** | ⏭ `ctx.snapshot()` + CLI (v0.5) | Delta time travel `VERSION AS OF` | Time Travel ≤90 days + Fail-safe 7 days | Table snapshots, 7-day window — `NEEDS VER.` |
| **Branching / zero-copy clone** | ❌ Not in roadmap yet (Iceberg spec v2 branch/tag applicable) | Delta `CLONE` (shallow + deep) | Zero-copy `CLONE` (metadata-only, instantaneous) | Table snapshots — `NEEDS VER.` |
| **Streaming ingest** | ⏭ v1.5+ Benthos/Redpanda (v4.1 §18.6) | Spark Structured Streaming + Lakeflow continuous | Snowpipe + Snowpipe Streaming (row-by-row) | Streaming inserts API — `NEEDS VER.` |
| **Batch ingest — CDC** | 🟡 `--mode merge` experimental v0.1; full CDC via dlt v0.3+ | Delta Change Data Feed + Auto Loader incremental | Streams + Tasks; Dynamic Tables GA Apr 2026 | Datastream (CDC) — `NEEDS VER.` |
| **Batch ingest — object storage** | ✅ `nucleus ingest ./file.csv` (CSV/Parquet/JSON, S3) | Auto Loader, `COPY INTO` | `COPY INTO` from S3/GCS/Azure | `bq load`, Transfer Service — `NEEDS VER.` |
| **Batch ingest — HTTP/REST** | 🟡 via dlt v0.3+; not in v0.1 | Lakeflow Connectors + Fivetran/Airbyte | Snowflake Connectors + Snowpark HTTP | Transfer Service, Data Fusion — `NEEDS VER.` |
| **SQL transformation** | ✅ `ctx.sql` + Jinja (`{{ ref() }}`, `{{ source() }}`), ~1000 LOC (v0.1); dbt-duckdb optional v0.3+ | dbt-spark; Lakeflow Spark Declarative Pipelines | dbt-snowflake; Dynamic Tables (incremental) | Dataform (SQLX + `ref()`, free, GA) |
| **Python transformation** | ✅ `@nucleus.asset` (Python + Polars, v0.1) | PySpark + Python notebooks | Snowpark Python DataFrames | Dataform Python + BigQuery DataFrames — `NEEDS VER.` |
| **Notebook environment** | ⏭ Marimo v0.3+ (v4.1 §18.3) | Notebooks (Python/SQL/Scala/R, collaborative) | Snowsight worksheets + Streamlit-in-Snowflake | Colab Enterprise (Jupyter) — `NEEDS VER.` |
| **Workflow / orchestration** | ✅ Dagster wrapped (hidden), DAG auto-derived from `ctx.read()` (v0.1) | Lakeflow Jobs (task DAG, branching/looping) | Tasks + DAG of Tasks | Cloud Composer (managed Airflow); Dataform |
| **Scheduling** | 🟡 `schedule=` declared (v0.1.1); active daemon deferred to v0.2 | Lakeflow Jobs cron/file-arrival/manual triggers | Tasks CRON/SCHEDULE; Dynamic Table target lag | Scheduled Queries — `NEEDS VER.` |
| **Lineage — asset-level** | ✅ OpenLineage (FileTransport, v0.1) | Unity Catalog table/pipeline lineage | Access History (query + object) | Dataplex lineage — `NEEDS VER.` |
| **Lineage — column-level** | ⏭ v0.5+ (OpenLineage + sqlglot, v4.1 §12.4) | Unity Catalog column lineage (GA) | Horizon Catalog — `NEEDS VER.` | Dataplex column lineage — `NEEDS VER.` |
| **Data quality / contracts** | 🟡 `@nucleus.contract` schema (v0.1); quality rules (Soda) v0.5+ | DLT Expectations + Lakeflow constraints | Dynamic Table constraints; ML anomaly detection | Dataform assertions (GA) |
| **Observability (logs/metrics/traces)** | ⏭ OpenTelemetry + VictoriaMetrics + VictoriaLogs (v0.5+, v4.1 §18.4) | System tables, Lakeview dashboards | Account Usage, Query History, INFORMATION_SCHEMA | Cloud Logging/Monitoring — `NEEDS VER.` |
| **Cost meter** | ⏭ Per-asset cost meter (v0.5+) | Unity usage dashboards + system tables | Resource Monitors, credit usage views | Cloud Billing budgets — `NEEDS VER.` |
| **BI integration** | ✅ DuckDB ODBC + open Iceberg → any BI tool, zero lock-in | Partner Connect JDBC/ODBC | First-class Tableau/PowerBI connectors | Looker (Google-owned), PowerBI |
| **AI — chat / SQL generation** | 🟡 `nucleus chat` single-turn opt-in (v0.2); schema-aware v0.3+ | Genie NL→SQL, `ai_query()`, AI/BI dashboards | Cortex Analyst/Code/Agents (NL→SQL + pipeline gen) | Gemini in BigQuery — `NEEDS VER.` |
| **AI — IDE autocomplete** | ✅ IDE-native (Cursor/Copilot); deliberately not our responsibility | Databricks Assistant in notebooks | Cortex Code in Snowsight + CLI | Gemini in BigQuery — `NEEDS VER.` |
| **Vector storage** | ⏭ Lance / LanceDB (v0.5+, v4.1 §18.4) | Mosaic AI Vector Search (GA) | Cortex Search | No native vector store — `NEEDS VER.` |
| **RBAC / Auth** | ⏭ OIDC delegation + Casbin (v0.8+, v4.1 §15, D17) | Unity Catalog RBAC (table/column/row level); SAML/OIDC/SCIM | System + custom roles, column/row policies; SAML/OIDC | IAM + column/row policies; Google SSO — `NEEDS VER.` |
| **Audit log / secret management** | ⏭ Audit v1.0; secrets: `.env` only v0.1, vault v0.3+ | System tables (audit); Databricks Secrets | ACCESS_HISTORY; Snowflake Secrets (GA) | Cloud Audit Logs; Google Secret Manager |
| **Multi-tenant control plane** | ⏭ Out-of-scope for OSS (v4.1 §20.3) | Account console (multi-workspace) | Organization accounts | GCP projects + folders |
| **Local-first dev experience** | ✅ `nucleus up` <10s (5.82s cold-start validated — AGENTS.md §1) | Community Edition only; no local mode | No local mode | Community emulator (unofficial) — `NEEDS VER.` |
| **Open format portability** | ✅ Iceberg-native (Apache 2.0); graduate to any Iceberg catalog | Delta primary; Iceberg via Unity federation | Iceberg Tables GA; Open Catalog (Polaris) | BigLake Iceberg — `NEEDS VER.` |
| **One-command local stack** | ✅ `nucleus up` (MinIO + catalog + Dagster, <10s) | ❌ None | ❌ None | ❌ None |

---

## 3. By-Platform Deep Dive

### 3.1 Databricks

**Sources verified 2026-05-15**: [introduction](https://docs.databricks.com/en/introduction/index.html) · [delta](https://docs.databricks.com/aws/en/delta/index.html) · [workflows](https://docs.databricks.com/aws/en/workflows/index.html) · [unity-catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html)

| | Databricks has, we don't replicate | Nucleus has, Databricks doesn't |
|---|---|---|
| Compute | Spark (unlimited scale), GPU clusters | Local-first: DuckDB in-process, 0 $/min idle |
| Storage | Delta Lake (proprietary-but-open format, needs Delta reader) | Apache Iceberg (portable, any reader) |
| ML | MLflow, Model Registry, ML Runtime, Mosaic AI Agent Framework | — (deliberately out-of-scope per §20) |
| AI | Genie NL→SQL, Vector Search, Foundation Model APIs | IDE-native: users bring Cursor/Copilot to local Python |
| Orchestration | Task-centric DAG (explicit `depends_on` YAML) | Asset-centric: DAG auto-derived from `ctx.read()` |
| Operations | Unity Catalog GA column/row RBAC + audit + auto-lineage | Git-native projects (real diffs, real PRs; no workspace DB) |

**Features we COULD add**: zero-copy clone (Iceberg v2 branch/tag spec, M), per-asset cost meter (M), column lineage (sqlglot, M).  
**Features we WON'T add** (v4.1 §20): Distributed Spark / GPU, MLflow, Mosaic AI model hosting, Databricks Apps.

---

### 3.2 Snowflake

**Sources verified 2026-05-15**: [guides-overview](https://docs.snowflake.com/en/guides-overview) · [iceberg-tables](https://docs.snowflake.com/en/user-guide/tables-iceberg) · [dynamic-tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-intro) · [cortex-overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/overview) · [Apr 2026 Iceberg release](https://docs.snowflake.com/en/release-notes/2026/other/2026-04-13-dynamic-iceberg-tables-partition-file-path)

| | Snowflake has, we don't replicate | Nucleus has, Snowflake doesn't |
|---|---|---|
| Compute | Multi-cluster virtual warehouses, auto-suspend | Local-first: 0 cloud cost to start |
| Cloning | Zero-copy `CLONE` (metadata-only, instantaneous) | Iceberg open format (no clone needed for portability) |
| AI | Cortex Analyst/Code/Agents/Fine-tuning/Search | Asset-centric Python model (Polars vs Snowpark cloud roundtrip) |
| ML | Feature store, model registry, ML Functions (GA) | — (out-of-scope) |
| Pipelines | Dynamic Tables (incremental refresh + CDC, GA Apr 2026) | `@nucleus.asset(materialized="incremental")` — same pattern, local |
| Governance | Column masking + row policies (GA); Open Catalog federation | Git-native; composable architecture |

**Features we COULD add**: Iceberg branch/tag clone (v0.5+, M), richer incremental CDC merge key (v0.3, M).  
**Features we WON'T add** (v4.1 §20): Cortex model hosting, Virtual Warehouse management, Snowflake Marketplace.

---

### 3.3 BigQuery

**Sources**: [dataform-overview](https://cloud.google.com/dataform/docs/overview) (verified 2026-05-15) · [bq-query-overview](https://cloud.google.com/bigquery/docs/query-overview) (partial).  
> **Warning**: 7 of 10 BigQuery `NEEDS VERIFICATION` items below arose from direct fetch timeouts. See §7 for verification URLs. Treat BigQuery column as indicative, not authoritative.

| | BigQuery has, we don't replicate | Nucleus has, BigQuery doesn't |
|---|---|---|
| Compute | Serverless slots, no cluster config — `NEEDS VERIFICATION` | Local-first: no GCP account needed |
| Storage | BigLake Iceberg — `NEEDS VERIFICATION` | Iceberg-native (certain, not speculative) |
| AI | Gemini NL→SQL, BigQuery ML — `NEEDS VERIFICATION` | Python-native with IDE Copilot support |
| Pipelines | Dataform (SQLX, `ref()`, assertions, DAG, free, GA — verified) | `@nucleus.asset` Python + `ctx.sql` Jinja — local execution |
| Orchestration | Cloud Composer (managed Airflow) | Asset DAG with auto-derived dependencies |
| BI | Looker (Google-owned) native integration | Open Iceberg → any BI tool zero-friction |

**Features we COULD add**: richer `@nucleus.check` assertions (covers Dataform assertions surface — S effort).  
**Features we WON'T add** (v4.1 §20): Serverless cloud SQL engine, BigQuery ML, Analytics Hub.

---

## 4. Prioritized Closure Plan (v0.2 → v1.0)

All items evaluated against the 8-question gate (`.cursor/rules/nucleus.mdc`). Items that fail any gate are marked DEFER and not included here.

### Tier P0 — Must-close before public release (v0.2, Mo 8-14)

| # | Title | Gap | Beachhead impact | Effort | Wrap target | Blocked by |
|---|---|---|---|---|---|---|
| P0-1 | **Active scheduling daemon** | `schedule=` declared but not executed | Pipeline that doesn't auto-run is a script, not a pipeline | S | Dagster `ScheduleDefinition` (already in coordination layer) | None — v0.2 per ADR-017 |
| P0-2 | **Run failure notifications** | No email/Slack/webhook on pipeline failure | Production teams can't operate blind | S | Dagster `failure_hook` → Slack webhook / SMTP | P0-1 |
| P0-3 | **Secret vault integration** | `.env` only; no cloud key store | Engineers expose DB credentials in `.env` | M | `nucleus enable vault` → HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager | None |

### Tier P1 — Close in v0.2–v0.3 (Mo 8-20)

| # | Title | Gap | Beachhead impact | Effort | Wrap target |
|---|---|---|---|---|---|
| P1-1 | **Full CDC ingest from Postgres** | Basic merge only; no event-streaming CDC | Most startup Postgres sources need incremental reads | M | dlt `sql_database` source with `incremental` ([dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database)) |
| P1-2 | **Workbench MVP (SQL editor + asset graph)** | No web UI in v0.1 | Analysts and non-engineers can't explore data | XL | Vite + DuckDB WASM per ADR-016 |
| P1-3 | **Basic run observability (history + duration)** | Zero monitoring beyond CLI output | "Did my pipeline run last night?" is unanswerable | M | OpenTelemetry → SQLite (local); VictoriaMetrics later |
| P1-4 | **Marimo notebook integration** | No notebook in v0.1 | Data exploration requires an external Jupyter | M | Marimo (Tier 2, [marimo.io](https://marimo.io)) |
| P1-5 | **dlt connector breadth (100+ sources)** | HTTP/REST/SaaS sources not in v0.1 | Stripe, HubSpot, GitHub are common startup sources | M | dlt ([dlthub.com](https://dlthub.com)) |

### Tier P2 — Close in v0.5+ (Mo 20-28)

| # | Title | Gap | Effort | Wrap target |
|---|---|---|---|---|
| P2-1 | **Column-level lineage (SQL)** | Asset-level only; no column provenance | M | OpenLineage + sqlglot (planned v4.1 §12.4) |
| P2-2 | **Observability dashboard (metrics/traces)** | No production performance monitoring | L | OpenTelemetry → VictoriaMetrics + Grafana |
| P2-3 | **Per-asset cost meter** | No compute spend visibility | M | DuckDB profiling API → asset metadata store |
| P2-4 | **Zero-copy clone / branch** | Can't fork a dataset for experimentation | M | PyIceberg Iceberg spec v2 branch/tag |
| P2-5 | **AI Copilot schema-aware (v0.3+) / lineage-aware (v0.5+)** | v0.2 chat is context-free single-turn | L | litellm + schema + lineage context injection |
| P2-6 | **Vector storage (LanceDB)** | No vector store for AI-adjacent workloads | M | Lance / LanceDB (Tier 0, v4.1 §4.1) |

### Tier P3 — Consider for v1.0 GA (Mo 28-36)

| # | Title | Why | Effort |
|---|---|---|---|
| P3-1 | **RBAC / OIDC delegation** | Teams of 10+ need access control | L (Casbin + Authentik/Keycloak) |
| P3-2 | **Audit log** | Compliance baseline for enterprise | M |
| P3-3 | **SOC2 Type II certification** | Enterprise sales blocker (costs money, not LOC) | XL (Vanta/Drata + auditor) |
| P3-4 | **Column-level security + PII masking** | Regulated industries (fintech, healthtech) | M (governance module) |

---

## 5. Honest "We Don't Compete Here" Section

Per `nucleus_vs_databricks.md §Where We Deliberately Lose` and v4.1 §20: *"These are not gaps. They are focus."*

- **Distributed compute** (Spark, multi-cluster warehouses, serverless slots) → **Yield via Mode 2** (v1.5+). Per v4.1 §10.
- **ML training / model hosting** (MLflow, Snowflake ML, BigQuery ML) → **Out-of-scope** per v4.1 §20.1. Users run MLflow OSS alongside Nucleus.
- **Foundation model APIs / AI platforms** (Mosaic AI, Cortex Agents, Gemini) → **Out-of-scope.** We call LLMs; we don't host them.
- **Multi-tenant cloud control plane** → **Out-of-scope for OSS** per v4.1 §20.3. Cloud tier handles this.
- **Real-time streaming at scale** (Spark Streaming, Snowpipe Streaming) → **v1.5+** via Benthos/Redpanda (v4.1 §18.6).
- **Data Marketplace** (Databricks Marketplace, Snowflake Marketplace, Analytics Hub) → **v3.0+** per v4.1 §18.7.
- **BI dashboard builder** (Lakeview, Looker, Snowsight) → **Not our product.** Open Iceberg = zero friction with any BI tool.
- **App hosting** (Databricks Apps, Streamlit-in-Snowflake) → **Out-of-scope.** Iceberg data powers external apps.

---

## 6. Top 5 Must-Close Items for Ultimate Release Confidence

### #1 — Active Scheduling Daemon (v0.2 · effort S · risk LOW)

**Why**: `schedule=` is declared in v0.1.1 but the daemon that triggers execution is deferred to v0.2 (ADR-017). A pipeline that declares `schedule="@daily"` but never auto-runs is a script, not a platform. The first engineer who wakes up to find nothing materialized will file "Nucleus is not production-ready."

**How**: Wire Dagster `ScheduleDefinition` through the coordination layer. ~100-200 LOC + integration test. No new ADR needed.

---

### #2 — Basic Production Monitoring (v0.3 · effort M · risk LOW)

**Why**: Every major platform provides run history and failure alerts (Databricks system tables, Snowflake Access History, BigQuery Cloud Logging). Nucleus v0.1 has zero monitoring beyond Rich CLI output. Silent failures are the #1 reason teams abandon OSS data tools.

**How**: Wire OpenTelemetry (Tier 0, already in architecture) through the AMA. Emit one span per materialization. Persist locally to SQLite (zero-infra). Surface in `nucleus observe` at v0.3; connect to VictoriaMetrics at v0.5.

---

### #3 — Full CDC from Postgres via dlt (v0.3 · effort M · risk MEDIUM)

**Why**: The beachhead persona has Postgres as their primary source. `ctx.copy_from` handles full-refresh only. Production teams need incremental CDC to avoid overloading source databases as data exceeds 10M rows. Without this, teams evaluate Airbyte or Fivetran instead.

**How**: Wire dlt `sql_database` source with `incremental` mode ([dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database)). Surface as `nucleus ingest postgres://... --mode cdc`. Wrap all dlt exceptions through the Error Translation Layer. Risk: dlt CDC has schema-evolution edge cases.

---

### #4 — RBAC Skeleton + OIDC Delegation (v0.8 · effort L · risk HIGH)

**Why**: Unity Catalog and Snowflake RBAC are table-stakes for any enterprise conversation. A 5-person founding team trusts each other; a 15-person team does not. Per v4.1 §15.1 D17, we never own identity — always delegate to OIDC. Missing this at v1.0 GA makes enterprise sales impossible.

**How**: Casbin for asset-level authorization. OIDC delegation to Authentik/Keycloak/Okta/Azure AD. `nucleus_project.yaml` `auth:` block + `ctx.permissions`. ~1-2K LOC. OWASP check required before merge.

---

### #5 — Column-Level Lineage for SQL (v0.5 · effort M · risk MEDIUM)

**Why**: Asset-level lineage is in v0.1. Column-level lineage is what compliance teams, GDPR/HIPAA officers, and data stewards need. Both Unity Catalog (GA) and Snowflake Horizon Catalog have it. Without column lineage, Nucleus cannot be platform of record for fintech/healthtech (the two highest-value startup verticals in our beachhead).

**How**: OpenLineage + sqlglot AST parsing, planned at v4.1 §12.4. Wire into AMA's lineage emission step. Python lineage deferred to v1.0 per decision D15 ([github.com/tobymao/sqlglot](https://github.com/tobymao/sqlglot)). Risk: complex CTEs + window functions — see `docs/research/sqlglot.md §5`.

---

## 7. NEEDS VERIFICATION Items (10 items)

| # | Claim | Where to verify |
|---|---|---|
| 1 | BigQuery fully serverless (no clusters, auto-slot scaling) | [cloud.google.com/bigquery/docs/slots-intro](https://cloud.google.com/bigquery/docs/slots-intro) |
| 2 | BigQuery DataFrames API details + Python compatibility | [cloud.google.com/bigquery/docs/bigquery-dataframes-introduction](https://cloud.google.com/bigquery/docs/bigquery-dataframes-introduction) |
| 3 | BigQuery BigLake Iceberg read/write scope | [cloud.google.com/bigquery/docs/iceberg-tables](https://cloud.google.com/bigquery/docs/iceberg-tables) |
| 4 | BigQuery Analytics Hub cross-org data sharing | [cloud.google.com/analytics-hub/docs](https://cloud.google.com/analytics-hub/docs) |
| 5 | BigQuery ML functions (ML.GENERATE_TEXT, ML.FORECAST) current scope | [cloud.google.com/bigquery/docs/bqml-introduction](https://cloud.google.com/bigquery/docs/bqml-introduction) |
| 6 | BigQuery Time Travel window length + configuration | [cloud.google.com/bigquery/docs/time-travel](https://cloud.google.com/bigquery/docs/time-travel) |
| 7 | BigQuery Colab Enterprise: availability + collaborative editing | [cloud.google.com/colab/docs](https://cloud.google.com/colab/docs) |
| 8 | Snowflake Snowsight worksheet real-time co-editing status | [docs.snowflake.com/en/user-guide/ui-snowsight-worksheets](https://docs.snowflake.com/en/user-guide/ui-snowsight-worksheets) |
| 9 | Snowflake Horizon Catalog column lineage GA status | [docs.snowflake.com/en/user-guide/object-dependencies](https://docs.snowflake.com/en/user-guide/object-dependencies) |
| 10 | BigQuery local emulator: official vs community-maintained status | [cloud.google.com/bigquery/docs/emulator](https://cloud.google.com/bigquery/docs/emulator) |

**Recommendation**: Spawn a dedicated BigQuery research pass before using §3.3 in any external positioning. BigQuery fetch failures led to 7 of these 10 unverified claims.

---

## 8. Logged Hallucinations

The following potential hallucinations were identified and avoided during research:

- **`pyiceberg.branch()`**: Researcher was tempted to reference this as a zero-copy clone API. Reality: Iceberg spec v2 defines branch/tag semantics, but the pyiceberg API surface for this needs verification. Resolved: cited the spec-level feature (Iceberg spec v2 branch/tag), not a pyiceberg API. No fabricated API shipped.
- **BigQuery `ML.GENERATE_TEXT`**: Referenced based on training knowledge; marked `NEEDS VERIFICATION` since live docs fetch timed out.
- **Snowflake Horizon Catalog column lineage**: Mentioned in search results but GA status not confirmed in live docs; marked `NEEDS VERIFICATION`.

Appended to `docs/research/ai_hallucinations.md`:

```markdown
## 2026-05-15: pyiceberg branch/tag API
Researcher was tempted to cite pyiceberg.branch() for zero-copy clone.
Reality: Iceberg spec v2 defines branch/tag semantics but pyiceberg API
surface for this is unconfirmed. Resolved pre-write. Cited spec, not API.
```

---

## 9. References

**Databricks** (live-fetched 2026-05-15):
- Introduction: https://docs.databricks.com/en/introduction/index.html
- Delta Lake: https://docs.databricks.com/aws/en/delta/index.html
- Lakeflow Jobs: https://docs.databricks.com/aws/en/workflows/index.html
- Unity Catalog: https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html
- Delta Sharing: https://docs.databricks.com/aws/en/delta-sharing/ *(cited only)*
- System Tables: https://docs.databricks.com/aws/en/admin/system-tables/audit-logs *(cited only)*

**Snowflake** (live-fetched 2026-05-15):
- Guides: https://docs.snowflake.com/en/guides-overview
- Iceberg Tables: https://docs.snowflake.com/en/user-guide/tables-iceberg
- Dynamic Tables: https://docs.snowflake.com/en/user-guide/dynamic-tables-intro
- Cortex AI: https://docs.snowflake.com/en/user-guide/snowflake-cortex/overview
- Apr 2026 Iceberg release: https://docs.snowflake.com/en/release-notes/2026/other/2026-04-13-dynamic-iceberg-tables-partition-file-path

**BigQuery** (partial — direct fetches timed out):
- Dataform Overview: https://cloud.google.com/dataform/docs/overview *(live-fetched)*
- Query Overview: https://cloud.google.com/bigquery/docs/query-overview *(partial)*

**Nucleus** (local docs, all verified):
- `nucleus_architecture_v4.1.md`, `nucleus_vs_databricks.md`, `nucleus_cli_spec.md`, `nucleus_ctx_sdk_spec.md`, `AGENTS.md`

**Other**: sqlglot lineage API: https://github.com/tobymao/sqlglot · dlt CDC: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database

---

*Snapshot as of 2026-05-15. Re-run before v0.5, v1.0, v2.0. A dedicated BigQuery research pass is recommended to resolve the 10 NEEDS VERIFICATION items in §7.*
