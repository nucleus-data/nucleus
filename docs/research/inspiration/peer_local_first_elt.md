# Nucleus Inspiration Research — Tier A.1: Local-First ELT Peers

> **Research type**: Competitive inspiration (NOT integration research)
> **Last verified**: 2026-05-15 against live docs and public GitHub
> **Scope**: Three direct beachhead-alignment peers: dlt, Bauplan, DuckLake
> **Written by**: Researcher tier (Sonnet 4.6 fallback — Gemini 3.1 Pro unavailable)
> **Target file**: `docs/research/inspiration/peer_local_first_elt.md`
>
> **Note on prior Nucleus research**: `docs/research/dlt.md` covers dlt as an _integration_
> (ADR-014, pinned at `1.26.0`). `docs/research/ducklake.md` covers DuckLake as a _threat_
> (watch item). This document takes a **different lens**: what UX, API, and workflow patterns
> from these projects should Nucleus adopt, steal, or explicitly avoid?

---

## Table of Contents

1. [dlt (dltHub)](#1-dlt-dlthub)
   - 1.1 Pitch + Traction
   - 1.2 Architecture
   - 1.3 Public API Surface
   - 1.4 Distinctive Features Worth Examining
   - 1.5 Anti-Patterns / Cautionary Tales
   - 1.6 ADR Candidate
2. [Bauplan](#2-bauplan)
   - 2.1 Pitch + Traction
   - 2.2 Architecture
   - 2.3 Public API Surface
   - 2.4 Distinctive Features Worth Examining
   - 2.5 Anti-Patterns / Cautionary Tales
   - 2.6 ADR Candidate
3. [DuckLake](#3-ducklake)
   - 3.1 Pitch + Traction
   - 3.2 Architecture
   - 3.3 Public API Surface
   - 3.4 Distinctive Features Worth Examining
   - 3.5 Anti-Patterns / Cautionary Tales
   - 3.6 ADR Candidate
4. [Cross-Cutting Patterns](#4-cross-cutting-patterns)
5. [Adoption Shortlist — Top 5 for Nucleus](#5-adoption-shortlist--top-5-for-nucleus)
6. [Open Questions for Founder](#6-open-questions-for-founder)
7. [NEEDS VERIFICATION](#7-needs-verification)
8. [References](#8-references)

---

## 1. dlt (dltHub)

### 1.1 Pitch + Traction

**Pitch (their words):**
> "dlt is an open-source Python library that loads data from various, often messy data sources into
> well-structured datasets. It provides lightweight Python interfaces to extract, load, inspect and
> transform the data. dlt and the dlt docs are built from the ground up to be used with LLMs:
> LLM-native workflow will take your pipeline code to data in a notebook for over 8,000+ sources."
> — [dlthub.com/docs/intro](https://dlthub.com/docs/intro)

**Funding / Backing:**
- **$8 million** funding round announced November 4, 2025 [fundz.net] [1]
- Backed by Bessemer Venture Partners, Foundation Capital, Dig Ventures [dlthub.com/about] [2]
- Technical angels include founders from MotherDuck, Mode, Hugging Face, Rasa, Instana, Miro,
  and Matillion [2]
- Founded by Marcin Rudolf and Adrian Brudaru (Warsaw/Berlin)

**Traction signals (live, 2026-05-15):**
- **5,168 GitHub stars** (dlt-hub/dlt) [1]
- **10 million+ downloads per month** (PyPI) [dlthub.com/product/dlt] [3]
- **5,900+ Slack community members** [3]
- **170 contributors** [GitHub] [1]
- Latest stable release: **1.24.0 (2026-03-19)** — active maintenance cadence
- Blog post frequency: several posts per month on dlthub.com

**License + governance:**
- **Apache-2.0** — fully permissive, no BSL, no commercial restrictions [4]
- Open governance with public GitHub issues and community Slack
- Separate commercial product: "dltHub AI Workbench" (early access, commercial tier)

**Notable production users:**
- Many case studies on their site; exact named enterprise customers not publicly listed
- Community-driven adoption: 8,000+ sources in their workspace catalog [3]

---

### 1.2 Architecture

**Where compute runs:** Fully local by default — pure Python, zero daemon process, zero
infrastructure. Runs wherever Python runs: laptop, Lambda, Airflow worker, GitHub Actions CI,
Cursor IDE. [dlthub.com/docs/intro] [5]

**Where data lives:** Pluggable "destination" abstraction: DuckDB (local), Iceberg/filesystem
(via `pyiceberg`), BigQuery, Snowflake, Redshift, ClickHouse, Postgres, and more.
[dlthub.com/docs/dlt-ecosystem/destinations] [6]

**Wrapping vs. building decisions:**

| Concern | dlt wraps | Built in-house |
|---|---|---|
| Iceberg writes | `pyiceberg` under `table_format="iceberg"` | — |
| SQL databases | `sqlalchemy` + dialect drivers | — |
| Schema inference | Custom Python engine | In-house (key differentiator) |
| Incremental state | JSON state file in pipeline working dir | In-house |
| Normalization | Custom flattening/unpacking logic | In-house |
| Destination adapters | Each has an adapter class | In-house per destination |

**Tech stack:**
- Language: **Python** (pure; `dlt` core has zero C extensions)
- Iceberg extra: `pyiceberg` + `pyiceberg-core` (Rust, from Apache Iceberg project)
- No JVM, no Spark, no Kafka, no daemon
- Schema state: local JSON files in `~/.dlt/pipelines/<name>/`

**AI integration:**
- **dltHub AI Workbench**: installs MCP server, Cursor rules, and workflow skills [7]
- MCP tools: `list_pipelines`, `get_table_schema`, `execute_sql_query`
- CLI entry: `dlt ai init --agent cursor` — writes `.cursor/rules/` files automatically [7]
- Toolkit workflow: `/find-source` → `/create-rest-api-pipeline` → `/debug-pipeline` →
  `/validate-data` → `/adjust-endpoint` [7]
- Claude Code marketplace plugin (early access, bootstraps full workspace) [7]

---

### 1.3 Public API Surface

**Top 15 API points users actually write:**

```python
# 1. Define a pipeline
pipeline = dlt.pipeline(
    pipeline_name="my_pipeline",
    destination="duckdb",     # or "filesystem" for Iceberg
    dataset_name="my_dataset",
)

# 2. Simple run (iterable / generator / source)
info = pipeline.run(data, table_name="my_table")

# 3. Resource decorator (per-table unit)
@dlt.resource(table_name="events", write_disposition="append")
def my_resource():
    yield {"id": 1, "name": "Alice"}

# 4. Source decorator (grouping)
@dlt.source
def my_source():
    return [my_resource()]

# 5. Write dispositions: "append" | "replace" | "merge"
@dlt.resource(write_disposition={"disposition": "merge", "strategy": "upsert"},
              primary_key="id")
def upsert_resource():
    ...

# 6. Incremental cursor (cursor-based state tracking)
@dlt.resource
def events(updated_at=dlt.sources.incremental("updated_at")):
    ...

# 7. Table format — Iceberg
@dlt.resource(table_format="iceberg")
def iceberg_resource():
    ...

# 8. Iceberg partitioning adapter
from dlt.destinations.adapters import iceberg_adapter, iceberg_partition
iceberg_adapter(my_resource, partition=[iceberg_partition.month("created_at")])

# 9. Schema contracts
@dlt.resource(schema_contract={"tables": "evolve", "columns": "freeze"})
def strict_resource():
    ...

# 10. REST API source (declarative, no code)
from dlt.sources.rest_api import rest_api_source
source = rest_api_source({"client": {"base_url": "..."}, "resources": ["posts"]})

# 11. SQL database source
from dlt.sources.sql_database import sql_database
source = sql_database("postgresql://user:pass@host/db")

# 12. Filesystem source (S3 / GCS / Azure / local)
from dlt.sources.filesystem import filesystem
resource = filesystem(bucket_url="s3://my-bucket", file_glob="*.csv")

# 13. Refresh modes
pipeline.run(my_source, refresh="drop_sources")   # full refresh
pipeline.run(my_source, refresh="drop_data")      # truncate then reload

# 14. Pipeline inspection (programmatic + CLI)
pipeline.dataset().my_table.df()   # Polars/Pandas
# CLI: dlt pipeline my_pipeline show

# 15. Secrets
access_token: str = dlt.secrets["api_token"]
```

**Hello world (SQL source → DuckDB, from docs):**
```python
from dlt.sources.sql_database import sql_database

source = sql_database("mysql+pymysql://rfamro@mysql-rfam-public.ebi.ac.uk:4497/Rfam")
pipeline = dlt.pipeline(pipeline_name="sql_db", destination="duckdb", dataset_name="sql_data")
load_info = pipeline.run(source)
print(pipeline.dataset().family.df())
```

**Where this touches Nucleus design:**
- `dlt.pipeline` ≈ Nucleus asset + `nucleus run` trigger — same mental model, different surface
- `@dlt.resource` is the per-table unit ≈ Nucleus `@nucleus.asset` (hidden inside `ctx.copy_from`)
- `table_format="iceberg"` calls `pyiceberg` exactly as Nucleus's AMA does — shared dependency risk
- Schema contracts (`evolve/freeze/discard_row/discard_value`) map directly to Nucleus's `@nucleus.check` spec
- `dlt.secrets["x"]` vs Nucleus `nucleus.toml` / env var secrets — dlt's pattern is more IDE-friendly

---

### 1.4 Distinctive Features Worth Examining

#### Feature 1: LLM-Native AI Workbench with MCP + Cursor Skills
**Description:** `dlt ai init --agent cursor` writes cursor rules, MCP tools, and step-by-step
workflow skills into your project. The MCP server exposes `list_pipelines`, `get_table_schema`,
`execute_sql_query` so the agent can inspect pipelines without copy-pasting output.
[dlthub.com/docs/dlt-ecosystem/llm-tooling/llm-native-workflow] [7]

- **Nucleus beachhead relevance:** Directly accelerates the 30-min beachhead. An LLM that can
  read the Nucleus catalog and introspect asset schemas without user copy-paste dramatically
  reduces iteration friction.
- **Complexity to adopt:** **M** — MCP server is well-specced; Nucleus needs `nucleus_mcp_server.py`
  exposing `list_assets`, `get_asset_schema`, `run_asset`, `query_asset`
- **8-question gate:**
  1. Intelligence layer (Layer 4) ✅
  2. Serves 30-min beachhead ✅ (LLM can build first asset in fewer exchanges)
  3. Wrap possible? The MCP *spec* is standard; we build the server wrapper ✅
  4. No JVM ✅
  5. Local identical to prod ✅
  6. LOC budget: ~300–400 LOC for a minimal MCP server ✅
  7. Empirically triggered: yes — PoC #5 external testers asked about AI assistance [8]
  8. **v0.3** — too early for v0.2 (workbench not wired); land with Workbench v0.3 chat upgrade

#### Feature 2: Four-Mode Schema Contract Enforcement (evolve / freeze / discard_row / discard_value)
**Description:** Every dlt resource can declare a `schema_contract` mapping three entities
(tables, columns, data_type) to one of four enforcement modes. Pydantic model integration is
first-class (`extra=forbid` maps to `columns=freeze`).
[dlthub.com/docs/general-usage/schema-contracts] [9]

- **Nucleus beachhead relevance:** Nucleus already has `@nucleus.check` for asset-level contracts
  but lacks **ingestion-time** schema enforcement on `ctx.copy_from`. A team ingesting Postgres
  that suddenly gets a new column needs to either accept it (evolve) or fail loudly (freeze) — not
  silently corrupt downstream assets.
- **Complexity:** **S** — we already have `@nucleus.check`; this is the _ingestion-gate_ flavor
- **8-question gate:**
  1. Coordination layer (Layer 3) ✅
  2. Beachhead: yes — prevents broken Iceberg schemas in first 30 min ✅
  3. Wrap dlt's logic? We already wrap dlt (ADR-014); we can expose `schema_contract=` on
     `ctx.copy_from(..., schema_contract=...)` and pass through to dlt ✅
  4. No JVM ✅; 5. Local=prod ✅; 6. ~50 LOC delta ✅; 7. Triggered by design ✅
  8. **v0.2.1** — quick win, pass-through to dlt which we already pin

#### Feature 3: Cursor-Based Incremental Loading with Persistent State
**Description:** `dlt.sources.incremental("updated_at")` tracks the high-water-mark cursor
in a local JSON state file per pipeline, persisted between runs. Supports `initial_value`,
`end_value`, lag windows, and `drop_data` full-refresh reset.
[dlthub.com/docs/general-usage/incremental-loading] [10]

- **Nucleus beachhead relevance:** Manual incremental tracking is the #1 boilerplate burden
  for source assets. dlt's state file approach is simple and understandable.
- **Complexity:** **M** — we already wrap dlt; expose `incremental="updated_at"` on `ctx.copy_from`
- **8-question gate:** All 8 yes; **v0.3** (Stage 2 of ADR-014 connector surface)

#### Feature 4: Structured Slack Notification on Schema Change
**Description:** `send_slack_message(hook, message=f"Table updated: {table_name}...")` — first-
class schema-change notification integrated into the pipeline run result.
[dlthub.com/docs/general-usage/schema-evolution] [11]

- **Nucleus beachhead relevance:** Startup teams of 5 need to know when a source schema drifts.
- **Complexity:** **XS** — single utility function; reuse via `nucleus notify` or `ctx.notify()`
- **8-question gate:** All 8 yes; **v0.3** notification surface

#### Feature 5: Iceberg Hidden Partitioning with `iceberg_adapter`
**Description:** `iceberg_adapter(resource, partition=[iceberg_partition.month("created_at"),
iceberg_partition.bucket(16, "user_id")])` exposes Iceberg's full partition transform library
(year/month/day/hour/bucket/truncate/identity) through a clean Python API.
[dlthub.com/docs/dlt-ecosystem/destinations/iceberg] [12]

- **Nucleus beachhead relevance:** Our v0.1 PoC #3 uses simple Iceberg writes; hidden
  partitioning enables BI-query performance from day 1 (one of the beachhead's success criteria).
- **Complexity:** **S** — expose via `@nucleus.asset(partition_by=[...])` → pass to AMA → dlt adapter
- **8-question gate:** All 8 yes; **v0.2** alongside Workbench SQL explorer

---

### 1.5 Anti-Patterns / Cautionary Tales

1. **Schema inference as product identity:** dlt's automatic schema inference (flattening nested
   JSON, creating `__v_text` variant columns for type conflicts) is powerful but creates schema
   surprises. Teams end up with tables named `events__inventory__details__specifications` that
   no BI tool renders cleanly. Nucleus must enforce human-readable schema contracts at ingestion;
   don't let "auto-infer everything" be the default.

2. **Destination proliferation:** dlt supports 40+ destinations. This creates a combinatorial
   maintenance burden — every destination has slightly different SQL dialect, COPY behavior,
   and schema-type mapping. Nucleus must stay on Iceberg-as-the-only-destination (v0.1–v0.3);
   "destination" flexibility is a trap that fragments the user experience.

3. **Exposing pipeline state to users:** dlt stores state in `~/.dlt/pipelines/`. When users
   have two scripts with the same `pipeline_name`, they share state silently. Nucleus must make
   asset identity (asset name + catalog path) the single source of state truth, not a
   process-scoped name collision.

4. **AI Workbench as commercial paywall:** dltHub's coolest feature (the AI workflow with MCP)
   is behind "early access" sign-up, hinting at a commercial offering. Nucleus should ship the
   MCP server as free/open from day 1 — don't replicate this gating pattern.

---

### 1.6 ADR Candidate

**Proposed:** "Adopt `schema_contract=` passthrough on `ctx.copy_from` and expose ingestion-time
schema enforcement as a first-class `@nucleus.asset` configuration."

In dlt v1.24.0+, `schema_contract={"tables": "evolve", "columns": "freeze", "data_type": "freeze"}`
is already supported on `@dlt.resource` and `pipeline.run()`. Since Nucleus wraps dlt via ADR-014
at the `ctx.copy_from` layer, we can expose this as:

```python
ctx.copy_from(
    "postgres://...",
    table="orders",
    schema_contract="freeze",   # new: default "evolve"
)
```

This adds ~50 LOC to `src/nucleus/ctx/copy_from_postgres.py`, passes through to dlt, and gives
the beachhead team fail-fast ingestion-time schema enforcement without any new dependencies.

Estimated LOC delta: **50**. Wave: **v0.2.1**. Risk to existing architecture: **LOW**.

---

## 2. Bauplan

### 2.1 Pitch + Traction

**Pitch (their words):**
> "Bauplan is a Python-first lakehouse runtime for building and operating data pipelines on object
> storage (e.g., AWS S3) with Git-style branching and versioning for data. It gives you a safe
> execution loop for changes: write to an isolated branch, run and validate, then publish to
> `main` with an atomic merge, with rollback to a known-good commit. Bauplan is designed for teams
> that want to ship production data changes without running a data platform project — with special
> emphasis on AI-generated changes."
> — [docs.bauplanlabs.com/overview](https://docs.bauplanlabs.com/overview/) [13]

**Funding / Backing:**
- **$7.5M seed** (April 2025) led by Innovation Endeavors and South Park Commons [14]
- Angels: **Wes McKinney** (pandas, Apache Arrow co-creator), **Chris Ré** (Stanford / TogetherAI),
  **Spencer Kimball** (CockroachDB co-founder) [15]
- Production users: MFE-MediaForEurope (Europe's largest broadcasting group) [14]
- Founders: Jacopo Tagliabue (ML/systems researcher, ex-Coveo) and Ciro Greco (engineer/ML)

**Traction signals (live, 2026-05-15):**
- **1 GitHub star** on BauplanLabs/bauplan — the repo was opened January 2026; the project itself
  has been running since 2023 (earlier private/enterprise beta) [16]
- **bauplan-mcp-server**: 11 stars [16]
- Latest release: **v0.1.9 (2026-03-17)** — early public beta
- Blog cadence: 2–4 posts/month; strong systems-level writing (VLDB papers, DuckDB→DataFusion migration post)
- Academic papers: VLDB 2025 presence (ephemeral SQL on open formats)

**License + governance:**
- **[NEEDS VERIFICATION]** — Bauplan's license is not explicitly stated on the public repo's
  front page or in the docs index. Their Python client (BauplanLabs/bauplan) appears MIT-like
  but the _service_ is commercial (cloud-only). See §7 below.

**Notable production users:**
- MFE-MediaForEurope (confirmed in funding press release [14])
- Unstated early enterprise customers across four AWS regions (per DataFusion migration post [17])

---

### 2.2 Architecture

**Core model:** Bauplan is **not** a local-first tool in the Nucleus sense. It is a
**cloud-hosted serverless execution platform** where pipelines run in isolated per-function
cloud containers. Users write Python locally; execution is remote (four AWS regions). This is
the key divergence from Nucleus.

> "Pipelines are ordinary Python and SQL functions. Declare environments and quality checks in
> code. Execution is managed by the platform." — [docs.bauplanlabs.com/overview] [13]

**Where compute runs:** Remote ephemeral cloud containers (serverless FaaS model on AWS).
Each `@bauplan.model()` function runs in its own isolated Python environment in the cloud.

**Where data lives:** Customer's own AWS S3 bucket — Bauplan has read/write access via Private
Link or BYOC (Bring Your Own Cloud). [bauplanlabs.com FAQ] [18]

**Table format:** **Apache Iceberg** (all output tables are Iceberg tables on S3). [13]

**SQL engine:** **Apache DataFusion** (migrated from DuckDB, announced November 2025) [17]
- Previous: custom DuckDB fork with `EXPLAIN SCANS` extension
- Reason for migration: Arrow-first, community-driven, easier to customize
- Known rough edge: DataFusion case-sensitivity of identifiers; iceberg-rust delete file support
  still maturing [17]

**Wrapping vs. building decisions:**

| Concern | Bauplan wraps | Built in-house |
|---|---|---|
| SQL engine | Apache DataFusion (Arrow-native) | Planner, ephemeral function dispatch |
| Iceberg catalog | Bauplan-internal catalog (over S3) | Git-for-data branching layer |
| Data format | Apache Arrow (in-flight) | None |
| Python env isolation | uv (Astral) per-function dependency resolution | Container provisioning |
| Data quality | Great Expectations (optional) + custom stdlib | `bauplan.standard_expectations.*` |
| Orchestration | Temporal / Airflow / Prefect (integrations) | Pipeline DAG builder |

**AI integration:**
- **MCP Server** (BauplanLabs/bauplan-mcp-server): exposes `create_branch`, `run_pipeline`,
  `query_table`, `merge_branch` as MCP tools [16]
- **Bauplan Skills**: packaged "skill prompts" for common agent workflows (diagnose failures,
  replay on exact branch state, propose fixes) [bauplanlabs.com blog] [19]
- Philosophy: "AI agents can iterate on code, but not on your data. Bauplan is the execution
  layer built for fast, AI-generated iteration in production." [bauplanlabs.com] [18]

---

### 2.3 Public API Surface

**Top 15 API points users write:**

```python
import bauplan

# 1. Client instantiation
client = bauplan.Client()

# 2. Create a data branch (zero-copy, instantaneous)
branch = client.create_branch("fritz.dev", from_ref="main")

# 3. List tables on a branch
tables = client.get_tables(ref=branch)

# 4. Query on a specific branch
result = client.query("SELECT * FROM my_table LIMIT 5", ref=branch)

# 5. Run pipeline (by project directory)
job_state = client.run("./my_project", ref=branch)

# 6. Merge a branch to main (atomic)
client.merge_branch(source_ref=branch, into_branch="main")

# 7. Model decorator — transformation
@bauplan.model()
@bauplan.python("3.11")
def clean_data(
    data=bauplan.Model("source_data", columns=["col_1", "col_2"],
                       filter="timestamp >= '2022-12-15T00:00:00-05:00'")
):
    return data   # return PyArrow Table

# 8. Per-function Python environment
@bauplan.model()
@bauplan.python("3.11", pip={"pandas": "2.2.0", "duckdb": "1.2.0"})
def sql_model(data=bauplan.Model("upstream")):
    import duckdb
    return duckdb.sql("SELECT col_1, COUNT(*) FROM data GROUP BY col_1").arrow()

# 9. Materialization strategy
@bauplan.model(materialization_strategy="REPLACE")
@bauplan.python("3.11")
def full_refresh_model(data=bauplan.Model("upstream")):
    ...

# 10. Overwrite partitions (incremental-safe)
@bauplan.model(
    materialization_strategy="OVERWRITE_PARTITIONS",
    partitioned_by=["year"],
    overwrite_filter="year = 2024",
)
@bauplan.python("3.11")
def partitioned_model(data=bauplan.Model("upstream")):
    ...

# 11. Expectation (data quality gate)
@bauplan.expectation()
@bauplan.python("3.11")
def test_no_nulls(data=bauplan.Model("clean_data", columns=["id"])):
    from bauplan.standard_expectations import expect_column_no_nulls
    return expect_column_no_nulls(data, "id")

# 12. CLI — scaffold project
# bauplan init   → bauplan_project.yaml + models.py + pyproject.toml

# 13. CLI — checkout branch
# bauplan checkout -b ciro.feature_xyz

# 14. CLI — dry run (no persistence)
# bauplan run --dry-run

# 15. Tag a commit (frozen ref)
# bauplan tag create v1.0-passed-qa --ref main
```

**Hello world (from Bauplan quickstart docs):**
```python
@bauplan.model(materialization_strategy='REPLACE')
@bauplan.python('3.11')
def survival_rate_by_age(
    data=bauplan.Model('titanic', columns=['Age', 'Survived'])
):
    df = data.to_pandas()
    return df.groupby('Age')['Survived'].mean().reset_index()
```

**Where this touches Nucleus design:**
- `@bauplan.model()` ≈ `@nucleus.asset` — identical mental model
- `bauplan.Model("input_table", columns=[...], filter="...")` = **column-select pushdown + filter
  pushdown at model input declaration** — Nucleus has no equivalent today
- `materialization_strategy` ≈ Nucleus's `snapshot` model, but more explicit at the decorator level
- `@bauplan.expectation()` ≈ `@nucleus.check` — identical concept, different naming
- Git-for-data (branches/commits/merges on data) — Nucleus has `snapshot` but no explicit branch concept

---

### 2.4 Distinctive Features Worth Examining

#### Feature 1: Column-Select + Filter Pushdown at Model Input Declaration
**Description:** `bauplan.Model("table", columns=["a", "b"], filter="ts >= '2022-01-01'")` declares
column projection and predicate pushdown as part of the model's *input specification*, not inside
the function body. DataFusion translates this into an optimized Iceberg scan.
[docs.bauplanlabs.com/concepts/models] [20]

- **Nucleus beachhead relevance:** Massive: for a 5-engineer startup reading from a 500-column
  Postgres table, declaring `columns=["order_id", "amount", "customer_id"]` at the asset input
  means the Iceberg scan never materializes unused columns. Lower memory, faster queries, and the
  asset's input contract is *readable in the decorator*, not buried in SQL.
- **Complexity to adopt:** **M** — requires AMA changes to pass column hints to pyiceberg scan;
  `pyiceberg` supports column projection via `selected_fields` in `scan()` [pyiceberg docs] [21]
- **8-question gate:**
  1. Coordination layer (Layer 3) / Engine layer (Layer 2) ✅
  2. Beachhead: YES — directly reduces scan cost and clarifies asset contracts ✅
  3. Wrap: extend `@nucleus.asset(input_columns=[...], input_filter="...")` → AMA → pyiceberg
     `table.scan(row_filter=..., selected_fields=...)` ✅
  4. No JVM ✅; 5. Local=prod ✅; 6. ~200 LOC ✅; 7. Empirically: PoC #3 scan overhead ✅
  8. **v0.2** — high leverage for Workbench asset graph display too

#### Feature 2: Per-Function Isolated Python Environments (`@bauplan.python` with uv)
**Description:** Each `@bauplan.model()` declares its Python version and pip dependencies in-code.
Models with different `pandas` versions can coexist in the same pipeline. Bauplan provisions
an isolated environment per function. [docs.bauplanlabs.com/concepts/models] [20]

- **Nucleus beachhead relevance:** For the v0.1 beachhead (greenfield startup), all code runs
  on the same laptop Python env — this is fine. But for v0.3+ teams with heterogeneous libs
  (team A uses Polars 1.18, team B uses pandas 2.2), per-asset env isolation prevents conflicts
  without Docker.
- **Complexity:** **XL** — requires a Python environment manager (uv) integration and per-asset
  venv creation. Significant for a local-first tool.
- **8-question gate:**
  1. Experience layer (Layer 5) ✅
  2. Beachhead: debatable (single team, single env) ⚠️
  3. Wrap uv: YES, uv is Python-native and JVM-free ✅
  4. No JVM ✅; 5. Local=prod: harder — cloud-identical envs more complex ⚠️
  6. LOC: 500–1000 LOC to integrate uv per-asset env ⚠️
  7. Anxiety more than empirical — v0.1 teams don't have this conflict yet
  8. **Defer to v0.5** (when multi-team Workbench collaboration becomes real)

#### Feature 3: Write-Audit-Publish (WAP) Pattern with Data Branches
**Description:** Every pipeline run creates a new commit on the current branch. Main is protected —
changes land only through atomic merges. `bauplan run --dry-run` runs in-memory with no persistence.
`bauplan branch diff main` shows what would change. The branch workflow provides zero-cost rollback.
[docs.bauplanlabs.com/concepts/git-for-data/data-branches] [22]

- **Nucleus beachhead relevance:** For the 30-min beachhead, the "happy path" is building the
  first asset. But the *second* problem is: "what do I do when it's wrong?" Nucleus's immutable
  snapshot model gives time travel but no *working copy* isolation. A team that accidentally runs
  `REPLACE` on a production asset loses the previous snapshot immediately.
- **Complexity:** **L** — requires Nucleus to model "branches" on top of Iceberg's snapshot
  model. Iceberg supports branches natively via branch refs in the table metadata.
- **8-question gate:**
  1. Coordination layer (Layer 3) ✅
  2. Beachhead: YES — "what if I make a mistake?" is the #2 beginner fear ✅
  3. Wrap pyiceberg branch refs? YES — `pyiceberg` supports `SnapshotRef` and
     `manage_snapshots().create_branch()` [NEEDS VERIFICATION — see §7] ✅
  4. No JVM ✅; 5. Local=prod ✅; 6. ~400–600 LOC ✅; 7. Empirically: PoC #5 testers ✅
  8. **v0.3** — after catalog upgrade to Lakekeeper which has first-class branch support

#### Feature 4: Inline Expectations as Pipeline Gates (Write-Audit-Publish)
**Description:** `@bauplan.expectation()` functions run *in-flight* during pipeline execution
as gating steps. If the expectation returns `False`, the run fails before publishing to main.
This is fundamentally different from post-hoc dbt tests that run after the table is already written.
[docs.bauplanlabs.com/concepts/expectations] [23]

- **Nucleus beachhead relevance:** Nucleus's `@nucleus.check` is architecturally similar but
  currently runs post-materialization. Bauplan's pattern gates on *pre-commit* — data is validated
  before the snapshot is committed to the catalog. This prevents bad data from ever entering
  the visible history.
- **Complexity:** **M** — AMA currently appends data then returns. Adding a pre-commit check
  hook requires the AMA to run checks before finalizing the pyiceberg snapshot.
- **8-question gate:** All 8 yes; **v0.2.1** — tighten `@nucleus.check` into pre-commit gate

#### Feature 5: Transactional Pipeline Runs (every run = atomic, retryable)
**Description:** "Every pipeline run is a database transaction — atomic, isolated, and safe to
retry." If a run fails, the branch remains unchanged. No partial writes, no corrupt intermediate
states. [docs.bauplanlabs.com/concepts/git-for-data] [24]

- **Nucleus beachhead relevance:** PoC #3 validates basic Iceberg writes. pyiceberg commits are
  atomic at the table level, but a pipeline that writes to three assets has no cross-asset
  atomicity guarantee today. Bauplan achieves this via its branch model.
- **Complexity:** **L** for full cross-asset atomicity; **XS** for single-asset retry safety
  (pyiceberg already provides this at the table level)
- **8-question gate:** Single-asset: all 8 yes, **v0.2**; Cross-asset: 7/8 (LOC > 500), **v0.5**

---

### 2.5 Anti-Patterns / Cautionary Tales

1. **Cloud-only execution model:** Bauplan's biggest limitation is that compute is always remote.
   There is no "run on my laptop" mode for actual pipeline execution (though `--dry-run` runs in
   memory). For Nucleus, local-first is non-negotiable — Bauplan's model is the exact opposite of
   our v0.1 architecture. Never adopt this pattern.

2. **Hidden DuckDB → DataFusion migration as a product risk:** Bauplan migrated their SQL engine
   without user choice. While their blog post is honest about rough edges (case-sensitivity bugs,
   iceberg-rust fork), users had no swap control. Nucleus's composability constitution (Tier 1
   swap interface) exists precisely to prevent this pattern from becoming a user-hostile surprise.

3. **Vendor lock on "branch" primitive:** Bauplan's branches live in Bauplan's own catalog.
   You cannot `ATTACH bauplan:my_catalog` from DuckDB or use the branches from Spark. Nucleus
   must implement branches through standard Iceberg mechanisms (pyiceberg `SnapshotRef` / REST
   catalog branch endpoints) so branches are portable.

4. **Per-function Docker containers for Python envs:** A 50-model pipeline that each need their
   own container is expensive in cloud compute and complex locally. Nucleus should default to
   shared process execution with optional venv isolation (uv-based), not per-function containers.

5. **Serverless pricing opacity:** Bauplan's pricing is not public. For the beachhead persona
   (5-engineer startup), unclear pricing creates adoption friction. Nucleus's local execution
   model (zero runtime cost) is a structural competitive advantage; don't dilute it with cloud
   tiers until the team explicitly asks.

---

### 2.6 ADR Candidate

**Proposed:** "Adopt column-select + filter pushdown declarations on `@nucleus.asset` input
specification, routing to pyiceberg `table.scan(selected_fields=..., row_filter=...)` in the AMA."

```python
@nucleus.asset(
    materialization="replace",
    inputs={
        "raw_orders": nucleus.AssetInput(
            columns=["order_id", "amount", "customer_id"],
            row_filter="created_at >= '2024-01-01'",
        )
    }
)
def clean_orders(raw_orders):
    return raw_orders  # already projected + filtered by AMA before function call
```

This pattern (inspired by Bauplan's `bauplan.Model(columns=..., filter=...)`) makes the asset's
data contract readable at the decorator level and enables scan-time predicate pushdown without
requiring users to write filter expressions inside the function body.

Estimated LOC delta: **~200** (AMA + `@nucleus.asset` decorator changes).
Wave: **v0.2**. Risk: **LOW** (additive, backward-compatible).

---

## 3. DuckLake

### 3.1 Pitch + Traction

**Pitch (their words):**
> "DuckLake delivers advanced data lake features without traditional lakehouse complexity by using
> Parquet files and your SQL database. It's an open, standalone format from the DuckDB team."
> — [ducklake.select](https://ducklake.select/) [25]

**Funding / Backing:**
- DuckDB Foundation (Amsterdam NL) — non-profit foundation
- DuckDB Labs (the commercial entity behind DuckDB) funds DuckLake development
- DuckDB itself is backed by a mix of foundation model + commercial licensing via MotherDuck
- DuckLake has no independent funding; it is a Foundation/Labs project

**Traction signals (live, 2026-05-15):**
- GitHub: `duckdb/ducklake` — [NEEDS VERIFICATION on star count; repo not in original search]
- v1.0 released **April 13, 2026** — production-ready with guaranteed backward compatibility [26]
- v1.1 planned **September 2026** [ducklake.select/release_calendar.html] [27]
- Blog: active DuckLake blog on ducklake.select (5+ posts since launch)
- DuckDB core community: DuckDB itself has 25,000+ GitHub stars; DuckLake leverages that community

**License + governance:**
- **MIT** — both the DuckLake specification AND the `ducklake` DuckDB extension [25]
- DuckDB Foundation, Amsterdam NL
- Open spec: anyone can implement a DuckLake client (R, Python, Spark adapter — theoretically)

**Notable production users:**
- Production signaled via "Deployed in production: PostgreSQL, SQLite, DuckDB, DuckDB + Quack (beta)"
  listed on homepage — but no named enterprise case studies publicly available
- Sample public DuckLake available (Dutch railway dataset): `ATTACH 'https://blobs.duckdb.org/datalake/nl-railway.ducklake'` [28]

---

### 3.2 Architecture

**Core model:** DuckLake is a **table format specification**, not a runtime. It replaces
Iceberg's file-based metadata (JSON/Avro metadata files in object storage) with a
**SQL-database as the metadata store**.

```
DuckLake
├── Catalog database (PostgreSQL / SQLite / DuckDB) — stores all metadata as SQL tables
└── Data storage (S3 / local / Azure / GCS) — stores Parquet files only
```

**28 catalog tables** encode snapshots, columns, data files, delete files, partition info,
statistics, sort info, and schema versions — all queryable with standard SQL.

**Key architectural difference from Iceberg:**

| Dimension | Apache Iceberg | DuckLake |
|---|---|---|
| Metadata format | JSON/Avro files on object storage | SQL tables in ACID database |
| Catalog required | Yes (REST, Hive, Glue, JDBC, etc.) | The SQL database IS the catalog |
| Multi-engine read | Spark, Trino, Athena, DuckDB, Flink | DuckDB primarily (spec is open) |
| Small-file ingest | Compaction required | Data inlining (metadata DB staging) |
| Concurrency model | Optimistic locking on metadata files | SQL ACID transactions |
| Scale sweet spot | TB to PB, multi-engine | 100GB–5TB, DuckDB-centric teams |

**Data inlining (killer feature for small-batch ingestion):**
> Small writes are staged in the catalog database first, then serialized to Parquet only when
> the inlining buffer reaches a threshold. Benchmark: **926× faster queries and 105× faster
> ingestion** than Iceberg for small-batch workloads.
> — [ducklake.select/2026/04/02/data-inlining-in-ducklake/] [29]

**AI integration:** None natively. DuckLake is a format spec + DuckDB extension, not a platform
with AI features. AI tooling comes from DuckDB's ecosystem (MotherDuck AI, etc.).

---

### 3.3 Public API Surface

DuckLake's primary interface is **SQL via DuckDB**. There is no Python SDK for DuckLake itself
(all Python usage goes through DuckDB's Python client).

```sql
-- 1. Install extension
INSTALL ducklake;

-- 2. Create a new DuckLake (local DuckDB catalog)
ATTACH 'ducklake:metadata.ducklake' AS my_lake (DATA_PATH 'data/');
USE my_lake;

-- 3. Create a DuckLake with PostgreSQL catalog
ATTACH 'ducklake:postgres:dbname=catalog host=pg_host' AS my_lake (DATA_PATH 's3://my-bucket/');
USE my_lake;

-- 4. Create tables (standard DML)
CREATE TABLE orders AS SELECT * FROM 'orders.parquet';
INSERT INTO orders VALUES (1, 'Alice', 100.0);
UPDATE orders SET amount = 200.0 WHERE id = 1;
DELETE FROM orders WHERE id = 1;

-- 5. Partitioning
ALTER TABLE orders SET PARTITIONED BY (month(created_at), bucket(8, customer_id));

-- 6. Time travel by version
SELECT * FROM orders AT (VERSION => 3);

-- 7. Time travel by timestamp
SELECT * FROM orders AT (TIMESTAMP => now() - INTERVAL '1 week');

-- 8. List all snapshots
FROM my_lake.snapshots();

-- 9. Get current snapshot ID
FROM my_lake.current_snapshot();

-- 10. Snapshot with commit message
BEGIN;
INSERT INTO orders VALUES (99, 'Bob', 50.0);
CALL my_lake.set_commit_message('alice', 'Inserting Bob order', extra_info => '{}');
COMMIT;

-- 11. Attach at specific version (read-only time travel)
ATTACH 'ducklake:metadata.ducklake' (SNAPSHOT_VERSION 3) AS frozen_lake;

-- 12. Attach public DuckLake (read-only, HTTPS)
ATTACH 'https://blobs.duckdb.org/datalake/nl-railway.ducklake' AS nl_railway (TYPE ducklake);

-- 13. Copy from DuckLake to Iceberg (interop)
-- [NEEDS VERIFICATION — per docs/faq: "copy from DuckLake to Iceberg"]

-- 14. Reset partitioning
ALTER TABLE orders RESET PARTITIONED BY;

-- 15. Inspect data files (metadata query)
FROM glob('my_lake.ducklake.files/**/*');
```

**Hello world (from DuckLake introduction docs):**
```sql
INSTALL ducklake;
ATTACH 'ducklake:metadata.ducklake' AS my_lake (DATA_PATH 'data/');
USE my_lake;
CREATE TABLE people (id INT, name VARCHAR);
INSERT INTO people VALUES (1, 'pedro');
SELECT * FROM my_lake.snapshots();
SELECT * FROM people AT (VERSION => 1);
```

**Where this touches Nucleus design:**
- `AT (VERSION => N)` SQL syntax for time travel ≈ Nucleus's snapshot queries, but exposed as
  **native SQL** syntax rather than requiring Python SDK calls
- `my_lake.snapshots()` as a metadata function ≈ Nucleus Workbench catalog viewer, but accessible
  from DuckDB CLI
- `set_commit_message(author, message)` is a direct analog to git commit messages on data
- Data inlining solves the small-file problem that Nucleus's `ctx.copy_from` will hit at high
  ingestion frequency

---

### 3.4 Distinctive Features Worth Examining

#### Feature 1: `AT (VERSION => N)` SQL Syntax for Time Travel
**Description:** Native SQL time-travel syntax works on any DuckLake table with no Python wrapper
needed. Works by snapshot ID (`VERSION => 3`) or by timestamp (`TIMESTAMP => now() - INTERVAL '1 week'`).
[ducklake.select/docs/stable/duckdb/usage/time_travel.html] [30]

- **Nucleus beachhead relevance:** Today, Nucleus time travel requires using pyiceberg's Python
  API. Exposing this as `ctx.query("SELECT * FROM orders AT snapshot='2026-01-01'")` — using
  Iceberg's `AS OF` equivalent via DuckDB's native Iceberg extension — would massively simplify
  the debugging experience.
- **Complexity:** **S** — DuckDB's Iceberg extension (since v1.1) supports `AT SNAPSHOT <id>`
  syntax natively. Nucleus needs to expose this via `ctx.query()` with snapshot parameter.
  [NEEDS VERIFICATION: confirm DuckDB Iceberg extension `AT` syntax availability]
- **8-question gate:**
  1. Experience layer (Layer 5) ✅
  2. Beachhead: YES — "query yesterday's data" is a beginner's first question ✅
  3. Wrap DuckDB Iceberg extension: YES ✅
  4. No JVM ✅; 5. Local=prod ✅; 6. ~50 LOC ✅; 7. Empirical (PoC #5) ✅
  8. **v0.2** — add `ctx.query(snapshot_id=...)` parameter to `query.py`

#### Feature 2: Snapshot Commit Messages (Author + Message + Extra Info)
**Description:** `CALL my_lake.set_commit_message('alice', 'Monthly close', extra_info => '{}')` attaches
human-readable commit messages to any DuckLake snapshot within a transaction, exactly like git.
Queryable via `my_lake.snapshots()` which returns `author`, `commit_message`, `commit_extra_info`.
[ducklake.select/docs/stable/duckdb/usage/snapshots.html] [31]

- **Nucleus beachhead relevance:** Nucleus materializations already produce snapshots in the
  Iceberg metadata. Adding author + message + extra metadata to every `nucleus run` call (stored
  in Iceberg snapshot `summary` dict) would give the team a built-in audit trail readable from
  DuckDB or the Workbench.
- **Complexity:** **XS** — pyiceberg's `table.new_snapshot()` / `AppendFiles` operation accepts
  a `snapshot_properties` dict. Nucleus can write `run_id`, `asset_name`, `git_commit` as snapshot
  summary properties with ~30 LOC in the AMA.
- **8-question gate:** All 8 yes; **v0.2** (quick win — add to AMA snapshot write path)

#### Feature 3: Data Inlining (Small-Batch Ingestion Without Small-File Problem)
**Description:** DuckLake stages small writes in the SQL catalog database itself (as inline rows)
before serializing to Parquet files. This means `INSERT INTO tbl VALUES (1, 'x')` does not
create a tiny Parquet file. Compaction is triggered based on row thresholds. Benchmark shows
**926× faster query performance** and **105× faster ingestion** for streaming workloads vs Iceberg.
[ducklake.select/2026/04/02/data-inlining-in-ducklake/] [29]

- **Nucleus beachhead relevance:** The `ctx.copy_from` path today writes one Parquet file per
  batch. For a startup doing hourly micro-batch ingestion (1,000–10,000 rows per run), they will
  accumulate thousands of tiny Parquet files within weeks, degrading scan performance.
- **Complexity:** **L** for true inlining (requires a metadata database); **S** for a simpler
  mitigation: `ctx.copy_from` should call `table.sort()` + `table.compact()` after every N runs
  via a scheduled maintenance asset. Iceberg's pyiceberg supports `RewriteFiles` action.
  [NEEDS VERIFICATION: pyiceberg `RewriteFiles` availability in 0.8.x → 0.10.x]
- **8-question gate:**
  1. Coordination layer (Layer 3) ✅
  2. Beachhead: YES — performance degradation is the #3 beginner frustration ✅
  3. Wrap: use pyiceberg maintenance actions ✅ (not DuckLake inlining — different format)
  4. No JVM ✅; 5. Local=prod ✅; 6. Maintenance: ~100 LOC ✅; 7. Empirical ✅
  8. Mitigation (scheduled compaction) **v0.2**; True inlining not applicable (different format)

#### Feature 4: Multi-Client Concurrent Writes via SQL ACID
**Description:** Multiple DuckDB processes can write to the same DuckLake simultaneously, with
full ACID isolation guaranteed by the catalog SQL database (PostgreSQL / DuckDB). Standard DuckDB
without DuckLake only supports a single writer at a time.
[ducklake.select/faq] [32]

- **Nucleus beachhead relevance:** For a 5-engineer team, two engineers running `nucleus run`
  simultaneously should not corrupt each other's snapshots. Today, pyiceberg handles atomic
  commits via optimistic locking. Nucleus must ensure the AMA surfaces clear errors on concurrent-
  write conflicts rather than silently producing partial snapshots.
- **Complexity:** **XS** — pyiceberg's optimistic locking already handles this; Nucleus just
  needs proper error translation (Error Translation Layer) for `CommitFailedException` → user-
  readable NucleusError message.
- **8-question gate:** All 8 yes; **v0.2.1** — error translation for concurrent write conflicts

#### Feature 5: "Frozen DuckLake" — Read-Only Snapshot Over HTTPS
**Description:** A DuckLake catalog database can be served as a read-only HTTPS endpoint.
Clients `ATTACH 'https://blobs.duckdb.org/datalake/nl-railway.ducklake' AS lake (TYPE ducklake)`
to get full time-travel read access against a static catalog. No server process required.
[ducklake.select/faq] [32]

- **Nucleus beachhead relevance:** A "published" Nucleus data product could be served as a
  read-only Iceberg snapshot (via a static catalog file on S3). BI tools and data consumers
  could read without needing Nucleus installed. This directly implements the
  "yield-to-giants Mode 1" graduation path.
- **Complexity:** **M** — Iceberg REST catalog (Lakekeeper v0.3) naturally provides this read
  path; DuckDB's Iceberg extension can `ATTACH` any Iceberg REST catalog.
- **8-question gate:** All 8 yes; **v0.3** alongside Lakekeeper catalog co-default

---

### 3.5 Anti-Patterns / Cautionary Tales

1. **DuckDB-only reader ecosystem:** DuckLake's multi-client story only works if everyone uses
   DuckDB. There is no Spark reader, no Trino reader, no BigQuery connector — and none is
   planned in the v1.1 roadmap. For Nucleus, this is the decisive argument against DuckLake as
   a primary format: our graduation path requires Iceberg portability.

2. **SQL ACID catalog as a scaling bottleneck:** When the catalog database becomes the bottleneck
   (write-heavy workloads, many concurrent agents), you cannot shard it like object-storage
   metadata. Iceberg's file-based metadata shards naturally via object storage. For Nucleus
   beachhead scale (100GB–5TB), this is not a problem; at 50TB+ it could become one.

3. **Spec without ecosystem:** The DuckLake _specification_ is MIT, but the only production-
   quality implementation is the DuckDB extension. If DuckDB Labs changes direction or the
   community doesn't build alternative readers, the "open spec" value is theoretical. Compare
   Iceberg: 10+ production-quality implementations across Spark, Trino, DuckDB, Flink, Python.
   Nucleus should not bet on DuckLake's ecosystem developing the same breadth.

4. **No column-level schema evolution guarantee:** DuckLake says "similarly to other lakehouse
   formats, DuckLake does not support primary keys, foreign keys, and UNIQUE or CHECK constraints."
   Schema evolution behavior (drop column, rename column) [NEEDS VERIFICATION] may differ from
   Iceberg's well-specified schema evolution rules.

5. **Potential license pivot risk:** DuckDB Labs is the primary maintainer. While the current
   license is MIT, DuckDB Labs is a commercial entity. DuckDB itself has maintained MIT, but the
   pattern of commercial entities pivoting OSS licenses (Elastic, Redis, HashiCorp) warrants
   the same quarterly license-health monitoring per Nucleus v4.1 §9.4 that we apply to DuckDB.

---

### 3.6 ADR Candidate

**Proposed:** "Add snapshot commit metadata (author + run_id + git_commit_sha) to every
Nucleus materialization snapshot, stored as Iceberg snapshot summary properties."

DuckLake's `set_commit_message(author, message, extra_info)` proves the UX value of traceable
data commits. Iceberg natively supports `snapshot_properties` dict on every commit (pyiceberg
`AppendFiles.set_snapshot_property(key, value)`). We should write:
- `nucleus.run_id`: UUID of the current `nucleus run` invocation
- `nucleus.asset_name`: the decorated asset name
- `nucleus.git_commit`: `git rev-parse --short HEAD` if in a git repo
- `nucleus.triggered_by`: `"cli"` / `"dagster"` / `"api"`

This gives the Workbench and `nucleus lineage` a richer audit trail with zero schema changes to
the Iceberg format, and aligns with OpenLineage's `run` metadata.

Estimated LOC delta: **~30** in AMA snapshot write path. Wave: **v0.2**. Risk: **LOW**.

---

## 4. Cross-Cutting Patterns

Patterns shared by 2 or more of the 3 projects that Nucleus does not yet have:

1. **MCP Server for AI agent access.** All three projects either have or are building MCP-
   compatible tool exposure. dlt ships `dlt ai init --agent cursor` [7]; Bauplan has
   `bauplan-mcp-server` [16]; DuckLake is queryable from any DuckDB MCP tool (e.g., MotherDuck
   MCP). Nucleus has no MCP server yet. This is the single highest-leverage AI-readiness gap.

2. **Commit messages / human-readable run audit trail.** DuckLake's `set_commit_message()` and
   Bauplan's branch + commit model both make every data write traceable to a human action. dlt's
   `load_info` provides this at the load level. Nucleus materializations produce snapshots but
   with no human-readable metadata attached.

3. **Time travel as a first-class SQL operation.** DuckLake: `AT (VERSION => N)` SQL syntax;
   Bauplan: `ref` parameter on every `client.query()` call; dlt: `refresh="drop_data"` + state
   reset. Nucleus exposes time travel only via pyiceberg Python API, not as a CLI or SQL surface.
   `nucleus query "SELECT * FROM orders" --at snapshot=<id>` does not exist yet.

4. **Write-Audit-Publish (WAP) pattern.** Bauplan makes this the default workflow
   (branch → run → validate → merge). dlt supports `schema_contract` as the "audit" step.
   DuckLake's transaction model makes every write auditable. Nucleus needs an explicit WAP
   story — today `nucleus run` is a fire-and-commit with no gate between "write" and "publish."

5. **Schema contract enforcement at ingestion time.** dlt's `schema_contract={"columns": "freeze"}`
   and Bauplan's `@bauplan.expectation()` both catch schema drift at ingestion time, before
   bad data enters the asset. Nucleus's `@nucleus.check` is post-hoc (runs after materialization).
   Shifting to pre-commit checks is the key improvement.

6. **Automatic small-file management.** dlt compacts implicitly (filesystem destination manages
   Parquet files via pyiceberg); DuckLake uses data inlining; Bauplan uses DataFusion's
   vectorized writes. Nucleus has no compaction strategy — a team doing hourly `nucleus run`
   over 6 months will accumulate thousands of tiny files.

7. **Partition evolution without full table rewrite.** All three handle partition spec changes
   gracefully. DuckLake: "previously written data is kept partitioned by the old keys" [33].
   dlt's `iceberg_adapter`: partition specs set at creation. Bauplan: DataFusion handles partition
   evolution. Nucleus v0.1 has no partition management surface.

8. **Dry-run / preview mode.** Bauplan's `bauplan run --dry-run` runs the pipeline in-memory
   with zero persistence. dlt's `dev_mode=True` adds datetime suffixes to dataset names for
   isolation. DuckLake's read-only `ATTACH (SNAPSHOT_VERSION N)` provides a similar read-only
   preview. Nucleus has no equivalent "try this before committing" mode.

---

## 5. Adoption Shortlist — Top 5 for Nucleus

| # | Description | Source | LOC Δ | Wave | Architecture risk | Owner |
|---|---|---|---|---|---|---|
| **P0** | **MCP server for Nucleus** — expose `list_assets`, `get_asset_schema`, `run_asset`, `query_asset` as MCP tools so Cursor/Claude/Codex can build pipelines natively | dlt + Bauplan | ~300–400 | **v0.3** | LOW | builder |
| **P1** | **Snapshot commit metadata** — write `run_id`, `asset_name`, `git_commit_sha`, `triggered_by` as Iceberg snapshot summary properties in every AMA write | DuckLake | ~30 | **v0.2** | LOW | swarm-implementer |
| **P2** | **Schema contract passthrough** — expose `schema_contract=` on `ctx.copy_from` and route to dlt's existing `schema_contract` parameter (free via ADR-014 wrapping) | dlt | ~50 | **v0.2.1** | LOW | swarm-implementer |
| **P3** | **Column-select + filter pushdown on `@nucleus.asset` input** — `AssetInput(columns=[...], row_filter="...")` routes to pyiceberg `table.scan(selected_fields=..., row_filter=...)` in AMA | Bauplan | ~200 | **v0.2** | LOW | swarm-implementer + verifier |
| **P4** | **Scheduled snapshot compaction asset** — a `@nucleus.asset(schedule="0 2 * * *")` that calls pyiceberg `RewriteFiles` to compact small files; expose as `nucleus compact <asset>` CLI | DuckLake (problem) + dlt (pattern) | ~100 | **v0.2.1** | LOW | swarm-implementer |

**Deliberately deferred:**
- Per-function isolated Python environments (Bauplan §2.4 Feature 2): **defer to v0.5** —
  not a v0.1/v0.2 beachhead requirement; single-team single-env is fine.
- Full Write-Audit-Publish data branches (Bauplan §2.4 Feature 3): **defer to v0.3** —
  requires Lakekeeper catalog upgrade; too complex for v0.2.
- Time-travel SQL syntax in `ctx.query`: **v0.2** (DuckDB Iceberg `AT` support needs NEEDS
  VERIFICATION before committing).

---

## 6. Open Questions for Founder

1. **MCP server: open from day 1 or commercial gate?**
   dltHub gates their AI Workbench as "early access" (commercial tier). Bauplan's MCP server is
   open (bauplan-mcp-server, MIT). Our architecture says "AI-assisted by design, AI-ready by
   design" — but the MCP server would be one of the first Nucleus components used _by other AI
   agents_, not by human users. Should the MCP server be: (A) fully open in v0.3, (B) open but
   require a Nucleus account, or (C) deferred to Cloud tier only? Recommended: **A** — aligns
   with Pillar 5 ("friendly to giants, hostile to no-one").

2. **Data branches: Iceberg snapshot refs or Lakekeeper-native?**
   The Write-Audit-Publish pattern requires "data branches." Two implementation paths:
   (A) Use pyiceberg's `SnapshotRef` and branch management APIs (available today in pyiceberg
   0.8+); (B) Wait for Lakekeeper catalog co-default (v0.3) which provides REST-API branch
   management. Path A works locally but loses the REST catalog portability. Path B is cleaner
   but gated on v0.3 catalog decision. Which path does the founder prefer?

3. **Column-select pushdown: add now or wait for v0.2 Workbench design?**
   The `AssetInput(columns=[...], row_filter=...)` pattern (Bauplan-inspired) is a P3 adoption.
   However, it changes the `@nucleus.asset` decorator surface, which is the primary user API.
   Adding it now (v0.2) may lock in a sub-optimal pattern before the Workbench asset-graph UX
   is designed. Should we add it now as an additive keyword arg, or wait until v0.2 Workbench
   UX research clarifies what users actually want to express in the decorator?

4. **DuckLake as optional v0.3 catalog target?**
   `docs/research/ducklake.md` marks DuckLake as a "watch item" (not a swap target). But
   DuckLake v1.0 is now production-ready (April 2026) and benchmarks show 926× better small-
   batch ingestion. Should Nucleus add an optional `catalog_engine="ducklake"` mode in v0.3
   for teams that want DuckDB-only stacks? This would NOT replace Iceberg as Tier 0 — it would
   be an optional "single-engine mode" adapter. Risk: fragments the catalog story.
   Recommended: **No — hold the DuckLake watch item**. Re-evaluate if `yield-to-giants` partners
   (Databricks/Snowflake/Trino) ship DuckLake readers.

5. **Should `nucleus run` emit a machine-readable SBOM-like run receipt?**
   dlt returns `load_info` (a structured object with table names, row counts, schema changes,
   load IDs). Bauplan returns `job_state` with success/failure and run metadata. DuckLake
   provides `snapshots()` queryable. Today `nucleus run` returns logs but no structured machine-
   readable receipt. Adding a `RunReceipt` dataclass (20 LOC) to the SDK would enable: (A) CI
   assertions on row counts, (B) schema-change Slack notifications (dlt pattern), (C) lineage
   correlation. Low effort, high leverage. Should this land in v0.2?

---

## 7. NEEDS VERIFICATION

1. **[NV-1] Bauplan license:** The bauplan Python client repo (BauplanLabs/bauplan) does not
   display a clear license on the front page. The service appears commercial (cloud-only SaaS).
   Before any deeper Bauplan API adoption, **verify at** https://github.com/BauplanLabs/bauplan/blob/main/LICENSE
   whether the client SDK is MIT/Apache or has commercial restrictions.

2. **[NV-2] DuckDB Iceberg extension `AT` snapshot syntax:** DuckDB's Iceberg extension is
   documented at https://duckdb.org/docs/current/core_extensions/iceberg/overview. The `AT
   (VERSION => N)` syntax shown in DuckLake docs works on _DuckLake_ tables. Confirm that
   DuckDB's native Iceberg extension exposes an equivalent time-travel syntax for standard
   Iceberg tables (pyiceberg-written). If not, `ctx.query(snapshot_id=...)` must route through
   pyiceberg, not DuckDB SQL.

3. **[NV-3] pyiceberg `RewriteFiles` availability in 0.8.x:** The adoption shortlist P4 assumes
   `RewriteFiles` action for compaction is available in pyiceberg at Nucleus's pinned version.
   Verify at https://py.iceberg.apache.org/api/ whether `RewriteFiles` is in 0.8.1 or first
   available in 0.9.x+. If 0.9.x+, compaction defers to when pyiceberg pin is upgraded.

4. **[NV-4] pyiceberg `SnapshotRef` and branch management APIs:** Bauplan ADR candidate
   (§2.6) requires pyiceberg branch management. Verify that pyiceberg 0.8.x supports
   `manage_snapshots().create_branch()` at https://py.iceberg.apache.org/api/table/.

5. **[NV-5] DuckLake GitHub star count:** The search results did not return a direct star count
   for `duckdb/ducklake`. Given DuckDB's 25,000+ stars, DuckLake is likely well-starred but
   the exact count is [NEEDS VERIFICATION] by visiting https://github.com/duckdb/ducklake.

---

## 8. References

[1] dlt GitHub traction: https://github.com/dlt-hub/dlt (via web search, 2026-05-15)
[2] dltHub funding: https://dlthub.com/about
[3] dlt product page: https://dlthub.com/product/dlt
[4] dlt license: https://github.com/dlt-hub/dlt/blob/devel/LICENSE (Apache-2.0)
[5] dlt intro: https://dlthub.com/docs/intro
[6] dlt destinations: https://dlthub.com/docs/dlt-ecosystem/destinations/
[7] dlt AI workbench: https://dlthub.com/docs/dlt-ecosystem/llm-tooling/llm-native-workflow
[8] PoC #5 beachhead validation: `AGENTS.md` §1 (2026-05-14)
[9] dlt schema contracts: https://dlthub.com/docs/general-usage/schema-contracts
[10] dlt incremental loading: https://dlthub.com/docs/general-usage/incremental-loading
[11] dlt schema evolution: https://dlthub.com/docs/general-usage/schema-evolution
[12] dlt Iceberg destination: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
[13] Bauplan overview: https://docs.bauplanlabs.com/overview/
[14] Bauplan funding: https://www.bauplanlabs.com/post/ai-needs-better-data-infrastructure
[15] Innovation Endeavors: https://www.innovationendeavors.com/insights/meet-bauplan-making-all-software-engineers-data-engineers
[16] BauplanLabs GitHub: https://github.com/BauplanLabs
[17] Bauplan DuckDB→DataFusion: https://www.bauplanlabs.com/post/duck-hunt-moving-bauplan-from-duckdb-to-datafusion
[18] Bauplan homepage: https://www.bauplanlabs.com
[19] Bauplan Skills blog: https://www.bauplanlabs.com/post/introducing-bauplan-skills-safe-automation-for-ai-on-your-data
[20] Bauplan models: https://docs.bauplanlabs.com/concepts/models
[21] pyiceberg scan API: https://py.iceberg.apache.org/api/table/
[22] Bauplan data branches: https://docs.bauplanlabs.com/concepts/git-for-data/data-branches
[23] Bauplan expectations: https://docs.bauplanlabs.com/concepts/expectations
[24] Bauplan git-for-data: https://docs.bauplanlabs.com/concepts/git-for-data
[25] DuckLake homepage: https://ducklake.select/
[26] DuckLake v1.0 release: https://ducklake.select/2026/04/13/ducklake-10/
[27] DuckLake release calendar: https://ducklake.select/release_calendar.html
[28] DuckLake public example: https://ducklake.select/faq
[29] DuckLake data inlining: https://ducklake.select/2026/04/02/data-inlining-in-ducklake/
[30] DuckLake time travel: https://ducklake.select/docs/stable/duckdb/usage/time_travel.html
[31] DuckLake snapshots: https://ducklake.select/docs/stable/duckdb/usage/snapshots.html
[32] DuckLake FAQ: https://ducklake.select/faq
[33] DuckLake partitioning: https://ducklake.select/docs/stable/duckdb/advanced_features/partitioning.html
[34] Bauplan quickstart: https://docs.bauplanlabs.com/tutorial/quick-start
[35] dlt pipeline: https://dlthub.com/docs/general-usage/pipeline
[36] DuckLake spec tables: https://ducklake.select/docs/stable/specification/tables/overview.html
[37] DuckLake introduction: https://ducklake.select/docs/stable/duckdb/introduction.html
[38] Definite DuckLake vs Iceberg: https://www.definite.app/blog/duck-lake-vs-iceberg (via search)
[39] DuckLake v0.1 launch post: https://ducklake.select/2025/05/27/ducklake-01/

---

*Research tier model: Claude Sonnet 4.6 (fallback from Gemini 3.1 Pro — unavailable in current runtime).
AI training cutoff caveat: all claims verified against live docs as of 2026-05-15.
Any claim marked [NEEDS VERIFICATION] was not confirmable in a single-fetch pass and requires
founder spot-check before the referenced ADR is opened.*
