# Big Cloud Platforms — Recent Feature Drops (2024-2026)

> **Tier B.1: Big-cloud recent-feature inspiration**  
> Last verified: 2026-05-15 against live official docs  
> Researcher: Claude Sonnet 4.6 (Research tier; Gemini 3.1 Pro unavailable — fallback per AGENTS.md §11.14)  
> Complements: `docs/internal/research/parity_vs_databricks_snowflake.md` (capability matrix) and `docs/internal/research/parity_vs_bosch_ely_adb_batch.md` (Databricks pipeline analysis)  
> This doc is DIFFERENT — it focuses on specific 2024-2026 flagship features and what Nucleus should adopt, match, or yield on.

> AI training-cutoff caveat: all claims verified against live docs as of 2026-05-15. Claims that could not be confirmed from primary sources are marked `[NEEDS VERIFICATION]`.

---

## 1. Framing

**What this IS**: A structured review of the 12 most relevant 2024-2026 feature drops across Databricks, Snowflake, and BigQuery — evaluated through the Nucleus 8-question gate and Five Pillars framework, to identify what to adopt, match, yield, or ignore.

**What this IS NOT**: A competitive benchmark or marketing pitch. Nucleus serves startups (5-20 engineers, 100GB-5TB, greenfield) and yields to giants for everything else. Per ADR-002 §8.1:

> *"Ship data products from a laptop — a local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks, AI-ready by design, graduating cleanly to any Iceberg catalog when users outgrow their laptop."*

**Verdict key used below**:  
- **YIELD** — graduate Nucleus users here; build bridge features in `ctx`/CLI for seamless handoff  
- **MATCH** — we can replicate the user value at our scale within 30K LOC budget  
- **ADOPT** — directly copy the pattern / UX / API design into Nucleus (not the implementation)  
- **IGNORE** — out of scope by design (per v4.1 §20 Non-Goals)

---

## 2. Databricks — 4 Flagship 2024-2026 Features

### Feature D1: Unity Catalog Open APIs + Credential Vending

**Launch date + maturity**: Credential Vending → **GA** (2026). External write access to managed tables → **Beta** (2026). Iceberg REST Catalog API → **Public Preview** (2026).  
Docs: [Expanded Interoperability](https://www.databricks.com/blog/expanded-interoperability-unity-catalog-open-apis) | [Credential Vending](https://docs.databricks.com/aws/en/external-access/credential-vending) | [External Access Admin](https://docs.databricks.com/aws/en/external-access/admin)

**Description (from Databricks docs)**: Unity Catalog now exposes Open APIs that allow external engines — Apache Spark, Flink, DuckDB, Trino — to create, read, and write to both Delta and Iceberg managed tables with centralized governance. Credential vending issues short-lived, scoped, M2M-OAuth-backed credentials on demand, so external engines connect without static service-account keys.

**What problem it solves**: Data teams stuck in silos because every new compute tool required copying datasets and rebuilding access policies. Unity Catalog's Open APIs enable "one copy of data, any compute engine, governed from one place."

**How Nucleus currently handles this**: Nucleus does not interact with Unity Catalog today. Users who outgrow Nucleus and move to Databricks must migrate their Iceberg catalog (Mode 1 — Iceberg portability). There is no `ctx` bridge to read/write Unity Catalog assets from the Nucleus side.

**8-question gate**:
1. Maps to Architecture Layer? → Yes (Coordination layer, Catalog — v4.1 §5.3 + §10)
2. Serves <30 min beachhead? → Indirectly — it's a graduation enabler, not day-1 value
3. Wrap possible? → Yes: `databricks-sdk` Python library wraps Unity REST API
4. No-JVM? → ✅ Python SDK, no JVM
5. Local-identical-to-prod? → ✅ (Nucleus stays local; UC is the remote graduation target)
6. 30K LOC budget? → Small: `ctx.read_unity_table()` / `ctx.write_unity_table()` is ~100 LOC
7. Empirical telemetry? → v0.5+ — founders will hit this when first enterprise user graduates
8. v0.1 scope? → No — Mode 1 graduation is v0.5+

**Equivalent Nucleus path**: Mode 1 (Iceberg portability) is the structural answer. Missing: concrete CLI/SDK bridge to read/write Unity Catalog from Nucleus side.

**Verdict: YIELD** — This is our graduation destination, not something we replicate. The outstanding work is building the bridge: `ctx.read_unity_table(catalog, schema, table)` + `nucleus graduate --target unity-catalog` CLI command. Target v0.5+ per roadmap. Two concrete bridge features below in §6.

---

### Feature D2: Lakeflow Spark Declarative Pipelines (Rebranded DLT)

**Launch date + maturity**: DLT rebranded as Lakeflow Declarative Pipelines at Data + AI Summit 2025. Unity Catalog integration **GA** (2025). Serverless CPU autoscaling + 2026 streaming enhancements → **GA** (March 2026).  
Docs: [2025 DLT Update](https://databricks.com/blog/2025-dlt-update-intelligent-fully-governed-data-pipelines) | [2026 Release Notes](https://docs.databricks.com/aws/en/release-notes/dlt/2026)

**Description**: Lakeflow Declarative Pipelines is a declarative framework defining datasets rather than jobs. Users write `@dlt.table` Python decorators or SQL `CREATE STREAMING TABLE AS SELECT` statements; Dagster-equivalent orchestration, retry, and observability is handled automatically. Auto CDC APIs replace legacy `APPLY CHANGES` for SCD Type 1/2 from CDC feeds. Serverless pipelines now scale CPU vertically without cluster configuration.

**What problem it solves**: ETL fragility from hand-stitched task DAGs. Declarative definitions allow the platform to auto-derive orchestration, handle retries, enforce data quality expectations inline, and track lineage automatically.

**How Nucleus currently handles this**: Nucleus v0.1 does precisely this — `@nucleus.asset` is the conceptual equivalent of `@dlt.table`. The asset graph is declarative; DAG order is auto-derived from `ctx.read()` calls. This is our strongest conceptual alignment with a Databricks flagship feature. We are ALREADY the "DLT for the laptop."

**8-question gate**:
1. Architecture layer? → Yes (Experience + Coordination layers, v4.1 §3)
2. Beachhead? → ✅ This IS the beachhead feature — asset-centric declarative pipelines
3. Wrap possible? → Already built (Dagster wrapped + `@nucleus.asset`)
4. No-JVM? → ✅ Already Python-first
5. Local-identical? → ✅ Core principle
6. 30K LOC? → Already within budget
7. Empirical telemetry? → Validated by PoC #3 and PoC #5
8. v0.1? → ✅ Already shipped

**Equivalent Nucleus path**: `@nucleus.asset` + `ctx.sql()` + `ctx.read()` dependency graph. **We match DLT's core value proposition.**

Three DLT features worth tracking for future versions:
- **CDC AUTO flow** (DLT 2025.30 multi-flow + `once` backfill) → equivalent is our `--mode merge` CDC path, currently experimental; promote in v0.3+
- **Pipeline hooks** (job-triggered pipeline events in 2026) → equivalent is `schedule=` + `nucleus run` hooks; already partially there
- **Type widening** (INT→LONG without re-write) → track in pyiceberg schema evolution, v0.3+

**Verdict: MATCH (already done)** — We have DLT's core at our scale. Track 3 incremental features above for v0.3+ backlog.

---

### Feature D3: Mosaic AI Agent Framework + Vector Search

**Launch date + maturity**: Vector Search → **GA** (2025). Agent Bricks → **Beta** (2025). MLflow 3.0 (AI observability) → **2025**. Storage-Optimized Vector Search → **Public Preview** (2025).  
Docs: [Vector Search GA](https://databricks.com/blog/announcing-mosaic-ai-vector-search-general-availability-databricks) | [Mosaic AI Summit 2025](https://databricks.com/blog/mosaic-ai-announcements-data-ai-summit-2025) | [Agent Framework](https://www.databricks.com/blog/announcing-mosaic-ai-agent-framework-and-agent-evaluation)

**Description**: Mosaic AI Agent Framework provides production-quality RAG: automated data indexing via Vector Search (up to 1B embeddings per serverless endpoint, 5x faster than competitors), automated evaluation harnesses, MLflow 3.0 lifecycle management, and Agent Bricks for domain-specific agent auto-optimization from a task description. MLflow 3.0 now supports cross-platform agent observability (AWS, GCP, on-premise).

**What problem it solves**: Building and deploying RAG applications in production — finding the right chunks, evaluating retrieval quality, managing agent versions, and monitoring accuracy over time.

**How Nucleus currently handles this**: Out of scope by v4.1 §20. Nucleus is AI-ready (we provide clean Iceberg assets that LLMs can consume via MCP), not AI-native. We do not host models or build RAG pipelines.

**8-question gate**:
1. Architecture layer? → No — ML model hosting is §20 Non-Goal
2. Beachhead? → No — 5-engineer startup does not need a vector search cluster on day 1
3. Wrap possible? → Technically yes (Lance/LanceDB for v0.5+), but the Agent Framework is far beyond Lance
4. No-JVM? → ✅ Python SDK
5. Local-identical? → Breaks it — Vector Search requires a cloud endpoint
6. 30K LOC? → Would blow the budget
7. Empirical telemetry? → No evidence startup beachhead needs this
8. v0.1? → ❌ No. Not even v0.5.

**Equivalent Nucleus path**: None today. v0.5+ Lance/LanceDB for local vector storage. Heavy RAG = YIELD to Mosaic AI.

**Verdict: YIELD + partial ADOPT**.  
YIELD: full Mosaic AI Agent Framework is out of scope.  
ADOPT the **MCP server pattern**: Databricks exposes Mosaic AI assets via MCP. We should do the same — `nucleus serve --mcp` exposes all Iceberg assets as MCP tools in v0.5+. This is a "Pillar 3: AI-assisted by design" win at zero JVM cost.

---

### Feature D4: AI SQL Functions — `ai_query()` + Genie NL→SQL

**Launch date + maturity**: `ai_query()` → **Public Preview** (May 2026). Task-specific AI functions → **GA** (2025-2026). Genie NL→SQL next-gen → **2026** (connected reasoning, iOS/Android).  
Docs: [ai_query](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query) | [AI Functions Guide](https://docs.databricks.com/aws/en/large-language-models/ai-query) | [Genie 2026](https://www.databricks.com/blog/next-generation-databricks-genie)

**Description**: `ai_query(model, prompt)` is a SQL function callable from any Databricks SQL query, enabling inline LLM inference (summarization, classification, extraction) on structured data without leaving the warehouse. Task-specific variants include batch document parsing (ai_parse), entity extraction, sentiment analysis, and translation — all callable as SQL functions on table columns. Genie 2026 adds enterprise knowledge source integration (Google Drive, SharePoint) for multi-source NL→SQL.

**What problem it solves**: Enriching structured data with AI without moving it out of the warehouse or writing custom Python pipelines. Developers can call `SELECT ai_query('gpt-4o', prompt_col) FROM my_table` to enrich any dataset.

**How Nucleus currently handles this**: `nucleus chat` (v0.2, single-turn) is the primitive. No SQL-callable AI function. AI enrichment today requires external Python in an `@nucleus.asset`.

**8-question gate**:
1. Architecture layer? → Yes — Intelligence layer (v4.1 §3.4, AI Copilot surface)
2. Beachhead? → Adjacent — enriching a data product with AI is a real startup use case
3. Wrap possible? → ✅ DuckDB supports user-defined functions (UDFs) callable from SQL; we can wrap any LLM API
4. No-JVM? → ✅ Python UDFs in DuckDB
5. Local-identical? → ✅ DuckDB Python UDFs run locally
6. 30K LOC? → ~200 LOC for a thin `ctx.ai_query()` + DuckDB UDF registration
7. Empirical telemetry? → v0.3+ — wait for first user asking "can I call Claude from my SQL?"
8. v0.1? → ❌ Defer to v0.3+

**Equivalent Nucleus path**: No equivalent today. `ctx.ai_query(model, prompt)` as a DuckDB UDF via `ctx.sql("SELECT ctx_ai_query(?, col) FROM tbl")` is achievable in v0.3+.

**Verdict: ADOPT (pattern, v0.3+)** — The SQL-callable AI function pattern is brilliant and fits our five pillars perfectly. Snowflake's `AI_COMPLETE` and BigQuery's `AI.CLASSIFY` confirm this is the universal pattern. We should expose `ctx.ai_query()` + `{{ ai_query(model, prompt) }}` Jinja macro in v0.3+ Copilot. Implementation: DuckDB Python UDF + httpx call to any OpenAI-compatible API endpoint. No cloud lock-in.

---

## 3. Snowflake — 4 Flagship 2024-2026 Features

### Feature S1: Iceberg Tables — From GA to v3 (2024-2026 Arc)

**Launch date + maturity**:  
- Iceberg Tables (Snowflake-managed) → **GA** June 2024  
- Dynamic Iceberg Tables → **GA** November 2024  
- Partitioned writes (v2 spec, all transforms) → **GA** October 2025  
- External engine read via Horizon Iceberg REST Catalog → **GA** 2026  
- Iceberg v3 (deletion vectors, default values, row lineage, geography/geometry types) → **GA** May 7, 2026  
Docs: [Iceberg Tables](https://docs.snowflake.com/en/user-guide/tables-iceberg) | [Iceberg v3 GA](https://docs.snowflake.com/en/release-notes/2026/other/2026-05-07-iceberg-v3-ga) | [Partitioned Writes GA](https://docs.snowflake.com/en/release-notes/2025/other/2025-10-17-iceberg-partitioned-writes-ga)

**Description**: Snowflake now supports Apache Iceberg as a first-class native table format. Snowflake-managed Iceberg tables are readable by external engines (DuckDB, Spark, Flink) via Horizon Iceberg REST Catalog. v3 adds deletion vectors for faster updates/deletes, row lineage for CDC, and new data types (geography, geometry, nanosecond timestamps). Writes from external engines to v3 tables via Horizon are not yet supported (reads only).

**What problem it solves**: Snowflake users can now graduate data to an open format (Iceberg) without vendor lock-in. External engines can read Snowflake's Iceberg tables via the REST catalog API without proprietary Snowflake connectors.

**How Nucleus currently handles this**: Nucleus writes Iceberg v2 tables via pyiceberg. We are already Iceberg-native. The Snowflake Horizon REST Catalog is a potential graduation target (Mode 1) — a Nucleus user could `nucleus graduate --target snowflake-open-catalog` and have Snowflake read their Iceberg tables via Horizon.

**8-question gate**:
1. Architecture layer? → Yes (Catalog/Storage, v4.1 §5.3, §10)
2. Beachhead? → Graduation path — enables the 30-min startup to later run Snowflake SQL on their Nucleus data
3. Wrap possible? → pyiceberg already handles our Iceberg writes; Horizon is just a catalog endpoint
4. No-JVM? → ✅
5. Local-identical? → ✅ (Nucleus stays local; Snowflake reads via REST)
6. 30K LOC? → Near-zero — just a catalog config pointing to Snowflake Horizon
7. Empirical? → v0.5+ — real need when enterprise buyer requires Snowflake compatibility
8. v0.1? → ❌ Defer

**v3 Upgrade tracking for Nucleus**: pyiceberg's v3 support should be tracked before we upgrade our Iceberg pin. Deletion vectors (v3) could improve our `--mode merge` CDC update/delete performance significantly. Row lineage (v3) could enrich our OpenLineage integration at v0.5+.

**Equivalent Nucleus path**: Mode 1 graduation. Missing bridge: `nucleus graduate --target snowflake-horizon` that updates the catalog config to point to Snowflake Open Catalog (Polaris-based Horizon REST endpoint).

**Verdict: YIELD (graduation target) + TRACK pyiceberg v3**. Snowflake's Iceberg v3 feature arc validates our Iceberg substrate choice as Tier 0. Bridge feature: `nucleus graduate --target snowflake-horizon` at v0.5+. Also: track pyiceberg v3 upgrade to unlock deletion vectors + row lineage.

---

### Feature S2: Cortex AI Functions — SQL-Callable LLMs (GA Nov 2025)

**Launch date + maturity**: `AI_COMPLETE` → **GA** November 21, 2025. `AI_CLASSIFY`, `AI_EMBED`, `AI_SIMILARITY`, `AI_TRANSCRIBE` → **GA** November 4, 2025. `AI_FILTER`, `AI_AGG`, `AI_SUMMARIZE_AGG` → **GA** 2025. Cortex Agents → **GA** November 4, 2025. Cortex Analyst multi-semantic-model → **GA** March 2025. Direct SQL generation in Cortex Agents → April 2026.  
Docs: [Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql) | [AI_COMPLETE GA](https://docs.snowflake.com/en/release-notes/2025/other/2025-11-21-ai-complete-ga) | [Cortex Analyst](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst)

**Description**: Snowflake Cortex AI provides 10+ SQL-callable AI functions directly in SELECT/WHERE/HAVING/JOIN clauses. `AI_COMPLETE(model, prompt)` generates LLM responses inline. `AI_CLASSIFY` routes text to user-defined categories. `AI_EMBED` generates embedding vectors without a separate indexing step. Cortex Analyst uses a YAML semantic model to translate natural language to verified SQL — no vector search, no hallucinated schema. Multiple semantic models can be joined in a single query (March 2025 GA).

**What problem it solves**: Enriching structured data with AI without moving it to Python, building RAG pipelines, or leaving the SQL interface. The Cortex Analyst semantic YAML model is a brilliant solution to NL→SQL hallucinations — the semantic layer grounds the LLM in the actual schema vocabulary.

**How Nucleus currently handles this**: `nucleus chat` (v0.2) is single-turn and schema-unaware. No SQL-callable AI functions. No semantic model layer. This is a significant inspiration gap.

**8-question gate** (for the `AI_COMPLETE`-pattern specifically):
1. Architecture layer? → Yes (Intelligence layer, AI Copilot surface, v4.1 §3.4)
2. Beachhead? → ✅ Adjacent — enriching a customer table with LLM is a real day-1 startup task
3. Wrap possible? → ✅ DuckDB Python UDF wrapping httpx to any OpenAI-compatible API
4. No-JVM? → ✅
5. Local-identical? → ✅ DuckDB runs locally; model endpoint is remote
6. 30K LOC? → ~200 LOC for `ctx.ai_complete()` + DuckDB UDF
7. Empirical? → Wait for 3 users to ask "can I call an LLM from SQL?" before shipping
8. v0.1? → ❌ v0.3+

**8-question gate** (for the semantic YAML model / Cortex Analyst pattern):
1. Architecture layer? → Yes (Intelligence layer)
2. Beachhead? → ✅ Direct — makes `nucleus chat` actually useful for business users
3. Wrap possible? → ✅ YAML semantic file + local LLM call (no cloud dependency)
4. No-JVM? → ✅
5. Local-identical? → ✅ Semantic model is a local YAML file
6. 30K LOC? → Semantic model parser: ~300 LOC; schema-aware prompt builder: ~200 LOC
7. Empirical? → v0.3+ when chat command gets real usage
8. v0.1? → ❌ v0.3+

**Equivalent Nucleus path**: No equivalent today for `AI_COMPLETE`-pattern. `nucleus chat` is closest to Cortex Analyst but lacks a semantic grounding model.

**Verdict: ADOPT (two patterns, v0.3+)**:  
1. **SQL-callable AI function** (`ctx.ai_complete(model, prompt)` as DuckDB UDF) — mirrors `AI_COMPLETE` pattern  
2. **Semantic YAML model for `nucleus chat`** — mirrors Cortex Analyst's `semantic_model.yaml` approach. Each Nucleus project can define `nucleus_semantic.yaml` with table/column descriptions, verified metrics, and natural-language aliases. The `nucleus chat` command uses this to ground LLM prompts instead of raw schema strings.

---

### Feature S3: Dynamic Tables — Declarative Incremental Refresh (GA April 2024)

**Launch date + maturity**: **GA** April 29, 2024 (AWS + Azure + GCP). Incremental refresh with time-based filters → **GA** May 2025. Dynamic Iceberg Tables → **GA** November 2024.  
Docs: [Dynamic Tables GA](https://docs.snowflake.com/en/release-notes/2024/other/2024-04-29-dynamic-tables) | [Manual Refresh](https://docs.snowflake.com/en/user-guide/dynamic-tables-manual-refresh) | [Dynamic Iceberg Tables](https://docs.snowflake.com/en/release-notes/2024/other/2024-11-12-dynamic-iceberg-tables)

**Description**: Dynamic Tables are Snowflake's declarative approach to data transformation — users write a `CREATE DYNAMIC TABLE AS SELECT ...` with a `TARGET_LAG` (freshness SLA), and Snowflake automatically handles refresh scheduling, incremental processing, DAG orchestration of chained tables, and observability. Dynamic Iceberg Tables extend this to write results as Iceberg format. No external orchestrator needed; no Airflow/Dagster to manage.

**What problem it solves**: ETL orchestration complexity — rather than managing task DAGs, users declare what data they want and let the platform figure out how to keep it fresh. The `TARGET_LAG` concept makes freshness a first-class parameter (e.g., "refresh within 5 minutes of source change").

**How Nucleus currently handles this**: `@nucleus.asset` is our conceptual equivalent — declarative, DAG auto-derived, incremental refresh triggered by `nucleus run`. We do not yet have a continuous `TARGET_LAG`-style freshness SLA. Active scheduling daemon (ADR-025) is in Wave 2.

**8-question gate** (for TARGET_LAG freshness SLA):
1. Architecture layer? → Yes (Coordination layer, Scheduling, v4.1 §7)
2. Beachhead? → ✅ Startups care deeply about "how stale is my data?"
3. Wrap possible? → The concept wraps naturally onto `schedule=` parameter in `@nucleus.asset`
4. No-JVM? → ✅
5. Local-identical? → ✅ A `freshness_sla="5m"` parameter on `@nucleus.asset` is local
6. 30K LOC? → ~50 LOC to add `freshness_sla=` parameter; scheduling daemon is ~500 LOC (already planned in ADR-025)
7. Empirical? → Yes — Wave 2 scheduling daemon gated on ADR-025
8. v0.1? → ❌ v0.2 (scheduling daemon)

**Equivalent Nucleus path**: `@nucleus.asset(schedule="*/5 * * * *")` is the nearest equivalent but lacks a `freshness_sla=` parameter that makes the intent human-readable.

**Verdict: MATCH (adopt TARGET_LAG vocabulary)**. We already have the structural equivalent. The missing piece is `freshness_sla="5m"` as a human-readable alias for cron. Add `freshness_sla=` as a synonym for `schedule=` in `@nucleus.asset` — 50 LOC change, high UX value, strong Pillar 4 alignment (familiar vocabulary from proven giants).

---

### Feature S4: Snowpark Container Services + Notebooks (GA 2025-2026)

**Launch date + maturity**: Snowpark Container Services → **GA** August 2025. Streamlit in Snowflake container runtime → **GA** March 9, 2026. Notebooks in Workspaces → **GA** February 5, 2026.  
Docs: [Container Services GA](https://snowflake.com/en/blog/secure-app-deployment-snowpark-container-services-ga) | [Streamlit Container GA](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-09-sis-container-runtime-ga) | [Notebooks GA](https://docs.snowflake.com/en/release-notes/2026/other/2026-02-05-notebooks-in-workspaces.html)

**Description**: Snowpark Container Services allows users to run arbitrary Docker containers (ReactJS frontends, open-source LLMs, distributed computing) within Snowflake's security perimeter. GPU access is available without self-procurement. Streamlit in Snowflake now supports a container runtime (GPU-enabled, broader Python packages, no sleep timers). Notebooks in Workspaces run on container compute with Git integration, background kernel persistence, and pre-installed ML packages.

**What problem it solves**: The "last mile" of data products — serving model results, building internal tools, and running Python workloads — without moving data outside Snowflake's governance boundary.

**How Nucleus currently handles this**: Out of scope. Nucleus v0.1 is CLI-only. Workbench (v0.2+) is our equivalent of Streamlit in Snowflake — a local-first app, not a container service. Marimo notebooks (v0.3+) are our equivalent of Notebooks in Workspaces.

**8-question gate**:
1. Architecture layer? → Partially (Experience layer — Workbench)
2. Beachhead? → Workbench and Marimo serve this, not Snowpark Container Services
3. Wrap possible? → Our Workbench IS our answer; no need to replicate container hosting
4. No-JVM? → ✅ (Nucleus side); container services are opaque
5. Local-identical? → ❌ Container Services requires cloud; Nucleus is local-first
6. 30K LOC? → Would need container orchestration — major budget hit
7. Empirical? → Not needed; Workbench covers this use case
8. v0.1? → ❌

**Equivalent Nucleus path**: Workbench (v0.2+) + Marimo (v0.3+). When a Nucleus user needs container-based serving, they YIELD to Snowflake Container Services or similar.

**Verdict: YIELD**. Snowpark Container Services is the graduation target for "I need to run a custom GPU workload alongside my data." Bridge feature: Nucleus should make it easy to export an asset as a Snowflake-readable Iceberg table, so a Container Services workload can read it. No Nucleus code needed — Mode 1 graduation handles this.

---

## 4. BigQuery — 4 Flagship 2024-2026 Features

### Feature B1: Managed Iceberg Tables + Lakehouse Iceberg REST Catalog

**Launch date + maturity**: BigQuery Tables for Apache Iceberg → **announced** October 2024, **GA** April 2026 (as "Managed Iceberg tables in Lakehouse"). Lakehouse Iceberg REST Catalog → **GA** November 2025. Read/write interoperability (Iceberg REST catalog for external engines) → **Preview** April 2026, **GA** "coming next month" (May 2026 per announcement).  
Docs: [Managed Iceberg Tables](https://cloud.google.com/bigquery/docs/iceberg-tables) | [BigLake REST Catalog GA](https://cloud.google.com/blog/products/data-analytics/biglake-metastore-now-supports-iceberg-rest-catalog) | [BQ Agentic Era](https://cloud.google.com/blog/products/data-analytics/unveiling-new-bigquery-capabilities-for-the-agentic-era)

**Description**: BigQuery now offers fully managed Iceberg tables with automatic storage optimization, adaptive file sizing, automatic clustering, garbage collection, and multi-statement transactions (preview). The Lakehouse Iceberg REST Catalog (`BLMS REST Catalog`) exposes an Apache Iceberg REST endpoint for read/write access from Spark, Trino, Flink, and other OSS engines. Cross-cloud Lakehouse (preview) extends this to AWS and Azure. Catalog federation (preview) enables zero-copy sharing across AWS Glue, Databricks, Snowflake, SAP, and Salesforce.

**What problem it solves**: BigQuery-managed data was previously locked behind proprietary BigQuery Storage API. Managed Iceberg tables make BigQuery data readable/writable by any Iceberg-compatible engine without BigQuery-specific connectors.

**How Nucleus currently handles this**: BigQuery is a potential graduation target (Mode 1). Nucleus users can write Iceberg tables locally, then graduate to BigQuery Lakehouse as a catalog. No current bridge in Nucleus `ctx` or CLI.

**8-question gate**:
1. Architecture layer? → Yes (Catalog/Storage graduation, v4.1 §10)
2. Beachhead? → Graduation path — real need at v0.5+ when first GCP-based startup hits growth
3. Wrap possible? → pyiceberg already speaks Iceberg REST; BLMS REST Catalog is just a catalog URL
4. No-JVM? → ✅
5. Local-identical? → ✅
6. 30K LOC? → Near-zero — just a catalog config pointing to BLMS REST endpoint
7. Empirical? → v0.5+ when first GCP user asks to graduate
8. v0.1? → ❌

**Equivalent Nucleus path**: Mode 1 graduation. Missing bridge: `nucleus graduate --target bigquery-lakehouse` that configures the BLMS REST Catalog endpoint in `nucleus_project.yaml`.

**Verdict: YIELD (graduation target)**. All three platforms now speak Iceberg REST Catalog. This validates our Tier-0 substrate choice and means a single graduation CLI command can route to Databricks Unity, Snowflake Horizon, or BigQuery BLMS at v0.5+. We need ONE bridge abstraction: `nucleus graduate --target <unity|snowflake-horizon|bigquery-lakehouse>`.

---

### Feature B2: BigQuery AI — SQL-Callable Functions + MCP Server (2024-2026)

**Launch date + maturity**: Gemini in BigQuery (SQL generation, data insights) → **GA** August 2024. `AI.CLASSIFY`, `AI.IF` in "optimized mode" → **Preview** 2026. `ObjectRef` (process unstructured data in SQL) → **GA** April 2026. Python UDF → **GA** April 2026. BigQuery remote MCP server → **GA** April 2026. Conversational Analytics → **GA** April 2026.  
Docs: [BQ Agentic Era](https://cloud.google.com/blog/products/data-analytics/unveiling-new-bigquery-capabilities-for-the-agentic-era) | [BigQuery MCP](https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp) | [Conversational Analytics](https://docs.cloud.google.com/bigquery/docs/conversational-analytics)

**Description**: BigQuery now ships as an "autonomous data-to-AI platform." Two features stand out: (1) SQL-callable AI functions (`AI.CLASSIFY`, `AI.IF`, `AI.PARSE_DOCUMENT`, `ObjectRef`) that process unstructured data inline with structured SQL — eliminating the need to copy data to a separate AI pipeline; (2) A fully managed **BigQuery remote MCP server** (GA April 2026) that exposes BigQuery tables, metadata, and query execution as MCP tools for AI agents (Claude, Cursor, LangGraph, ADK). The MCP server runs on Google's infrastructure — no management overhead, HTTP endpoint.

**What problem it solves**: (1) AI enrichment without data movement. (2) AI agents that need to read/query data can connect to BigQuery via standardized MCP protocol instead of custom database connectors.

**How Nucleus currently handles this**: No MCP server today. `nucleus chat` (v0.2) handles AI enrichment via Python assets but not SQL-callable functions. The MCP server gap is our biggest AI-readiness miss.

**8-question gate** (MCP server specifically):
1. Architecture layer? → Yes (Intelligence layer, v4.1 §3.4, AI Copilot / agent runtime)
2. Beachhead? → ✅ A startup wants AI agents to read their Iceberg data — MCP is the standard interface
3. Wrap possible? → ✅ `mcp` Python library + `pyiceberg` catalog reads = ~400 LOC
4. No-JVM? → ✅
5. Local-identical? → ✅ MCP server runs locally alongside `nucleus up`
6. 30K LOC? → ~400 LOC for a basic MCP server exposing catalog + query + schema
7. Empirical? → Moderate: BigQuery, Snowflake, and Databricks all GA'd MCP in 2026 — market signal
8. v0.1? → ❌ v0.3+ (after `nucleus chat` matures)

**Equivalent Nucleus path**: None today. `nucleus serve --mcp` would expose: list_assets, read_asset_schema, query_asset (DuckDB SQL over Iceberg), get_lineage. Cursor, Claude Code, and any MCP client could then browse and query Nucleus assets without custom connectors.

**Verdict: ADOPT (MCP server, v0.3+)**. All 3 big platforms shipped MCP servers in 2025-2026. This is a Pillar 3 (AI-assisted) win with low LOC cost. The pattern: `nucleus serve --mcp --port 3000` starts a local MCP server, registered in Cursor's MCP settings. AI agents can then call `list_nucleus_assets()`, `query_nucleus_asset(asset_name, sql)`, and `get_nucleus_lineage(asset_name)` directly from any MCP-compatible IDE or agent runtime.

---

### Feature B3: BigQuery Studio — Data Science Agent + Colab Data Apps (2026)

**Launch date + maturity**: Data Science Agent → **GA** April 2026. Colab Data Apps → **Preview** April 2026. BigQuery Studio Notebook Gallery → **GA** April 2026. Git integration (GitHub, GitLab, Bitbucket, Azure DevOps) → **Preview** April 2026.  
Docs: [BQ Agentic Era](https://cloud.google.com/blog/products/data-analytics/unveiling-new-bigquery-capabilities-for-the-agentic-era) | [Data Science Agent](https://docs.cloud.google.com/bigquery/docs/colab-data-science-agent) | [Colab Data Apps](https://docs.cloud.google.com/bigquery/docs/colab-data-apps)

**Description**: BigQuery Studio's Data Science Agent (GA April 2026) lets users state goals in plain English — "load, clean, and visualize this dataset" — and automatically executes a plan using BigQuery ML, DataFrames, or Spark. Colab Data Apps transform notebook analyses into shareable, fully managed interactive Python apps accessible by business teams. Studio now has Git integration across all major SCM providers (GitHub, GitLab, Bitbucket, Azure DevOps).

**What problem it solves**: The last 10% of data product delivery — sharing insights with business stakeholders. A data scientist writes code in Studio; Colab Data Apps turns that into a governed business app without engineering effort.

**How Nucleus currently handles this**: Workbench (v0.2+) is our equivalent of Colab Data Apps — a local-first web UI for data products. Marimo (v0.3+) is our equivalent of interactive notebooks. Git integration is native (Nucleus projects are git repos by design — per `nucleus_project_anatomy.md`).

**8-question gate** (Data Science Agent specifically):
1. Architecture layer? → Intelligence layer (v4.1 §3.4)
2. Beachhead? → Partial — "natural language to pipeline" is interesting but requires mature LLM tooling
3. Wrap possible? → LLM + DuckDB SQL generation is feasible; complex agentic loop is risky
4. No-JVM? → ✅
5. Local-identical? → ✅ If model is called locally or via API
6. 30K LOC? → An agentic pipeline generator would consume 1,000+ LOC — too expensive for v0.1
7. Empirical? → No telemetry to justify yet; wait for v0.3+ Copilot feedback
8. v0.1? → ❌

**Equivalent Nucleus path**: Git integration is native. Workbench is our equivalent of Colab Data Apps. A Data Science Agent equivalent could emerge from `nucleus chat` evolution in v0.5+.

**Verdict: MATCH on git (already done) + YIELD on Data Science Agent + ADOPT UX idea**. The "plain English → pipeline plan" UX idea is compelling but out of budget for v0.3. Log in FOUNDER_ACTION_QUEUE.md for v0.5+ Copilot. One concrete adoption: the `nucleus chat` command in v0.3+ should support multi-turn conversation (not just single-turn), grounded in the project's semantic YAML model (see S2 Cortex Analyst pattern above).

---

### Feature B4: BigQuery Graph + Conversational Analytics (2026)

**Launch date + maturity**: BigQuery Graph (entities + relationships + business logic) → **Preview** April 2026. Conversational Analytics in BigQuery → **GA** April 2026. Graph support in Conversational Analytics → **Preview** April 2026.  
Docs: [BigQuery Graph](https://docs.cloud.google.com/bigquery/docs/graph-overview) | [Conversational Analytics](https://docs.cloud.google.com/bigquery/docs/conversational-analytics)

**Description**: BigQuery Graph allows data practitioners to define entities, relationships, and business logic (measures like "Churn Rate") directly within BigQuery, creating a governed "business map." Conversational Analytics agents navigate this business map rather than raw tables, delivering more accurate NL→SQL answers. Measures defined in BigQuery Graph can be reused in Looker. The graph becomes the semantic layer that grounds AI agents in governed business reality.

**What problem it solves**: LLM hallucinations in NL→SQL are caused by the LLM not understanding what a table column *means* in business terms. A graph-based semantic layer that defines entities, relationships, and KPIs gives agents a deterministic map to navigate.

**How Nucleus currently handles this**: No equivalent. The closest is `@nucleus.contract` (schema definitions) but with no semantic graph capability.

**8-question gate**:
1. Architecture layer? → Intelligence layer (v4.1 §3.4) — partially
2. Beachhead? → Only for v0.5+ Copilot evolution
3. Wrap possible? → The semantic YAML model idea (from Snowflake Cortex Analyst, S2 above) is a simpler version of this — no graph complexity needed at startup scale
4. No-JVM? → ✅
5. Local-identical? → ✅ if implemented as a local YAML file
6. 30K LOC? → Full graph engine = too much; YAML semantic model = 300 LOC
7. Empirical? → Not yet
8. v0.1? → ❌

**Equivalent Nucleus path**: `nucleus_semantic.yaml` (a YAML file per the Cortex Analyst adoption from S2) is our answer to BigQuery Graph at startup scale — without graph complexity.

**Verdict: IGNORE the graph approach + ADOPT the semantic layer pattern (via S2)**. BigQuery Graph is enterprise-scale complexity. The Snowflake Cortex Analyst YAML semantic model solves the same problem (grounding NL→SQL) at our scale. We already marked that ADOPT above. No additional work from this feature.

---

## 5. Common Themes 2024-2026

All three platforms are converging on the same architectural patterns. This is strong signal for Nucleus strategy:

1. **Iceberg as the universal table format**: All 3 now offer Iceberg-native storage with GA support (Snowflake Iceberg GA June 2024, BigQuery Managed Iceberg GA April 2026, Databricks Iceberg via Unity GA 2026). Iceberg is no longer a "nice-to-have" — it is the open standard. Nucleus's Tier-0 bet on Iceberg is now validated by all three giants.

2. **Iceberg REST Catalog as the federation standard**: Databricks (Unity REST), Snowflake (Horizon), and BigQuery (BLMS REST Catalog) all expose an Iceberg REST Catalog endpoint. External engines (DuckDB, Spark, Flink) can plug in via this standard. Nucleus can graduate to ANY of them with a single catalog configuration change.

3. **SQL-callable AI functions as first-class DX**: `ai_query()` (Databricks), `AI_COMPLETE()` (Snowflake), `AI.CLASSIFY` / `AI.IF` (BigQuery). All 3 platforms now allow calling LLMs from SQL without leaving the warehouse. This is the convergent pattern for AI-enriched data pipelines.

4. **Semantic grounding for NL→SQL**: Cortex Analyst (Snowflake YAML semantic model), BigQuery Graph (entity/relationship graph), Genie (enterprise knowledge sources). All 3 solve LLM hallucination in NL→SQL via a structured semantic layer. The YAML semantic model is the startup-scale equivalent.

5. **MCP (Model Context Protocol) as the AI-agent data interface**: BigQuery (remote MCP server GA April 2026), Databricks (Mosaic AI agent framework MCP tools), Snowflake (Cortex Agents + API). All 3 platforms expose their data as MCP tools for AI agents. MCP is becoming the standard "AI-agent to data" protocol, superseding custom database connectors.

6. **Declarative pipelines as the default**: Lakeflow Declarative Pipelines (Databricks DLT), Dynamic Tables (Snowflake), Dataform `ref()` (BigQuery) — all three converge on asset-centric declarative transformations, not task-centric DAGs. This directly validates the `@nucleus.asset` approach.

7. **Serverless compute everywhere**: Databricks serverless SQL Warehouses + serverless DLT autoscaling, Snowflake serverless virtual warehouses + container services, BigQuery serverless slots with per-second billing. Zero-idle-cost compute is now standard. Nucleus's DuckDB (always serverless) is already here for startup scale.

8. **Credential vending as the cross-engine security pattern**: Databricks Unity (GA), Snowflake Open Catalog (GA), BigQuery BLMS (GA). Short-lived, scoped, M2M-OAuth-backed credentials are the standard for external engine access. Nucleus's OIDC delegation strategy (v0.8+ per ADR-016) aligns with this.

9. **Git integration as a table-stakes developer experience**: BigQuery Studio notebooks now support GitHub/GitLab/Bitbucket/Azure DevOps. Databricks Repos has had this for years. Snowflake Notebooks in Workspaces added Git (2026). Nucleus's git-native project model (`nucleus_project_anatomy.md`) is ahead — we are git-first by design.

10. **Cross-cloud lakehouse as the enterprise endgame**: BigQuery Cross-Cloud Lakehouse (AWS + Azure, preview April 2026), Databricks Delta Sharing cross-cloud, Snowflake cross-cloud replication. The large enterprises need data accessible across clouds. Nucleus's yield-to-giants Mode 3 (Iceberg REST federation, v2.0+) is the startup-friendly precursor to this.

---

## 6. Yield-to-Giants Tightening

For each YIELD verdict above, these are the concrete bridge features needed in `ctx`/CLI to make graduation seamless. Target milestone per feature:

| # | Bridge Feature | Needed for Graduation to | Milestone | Nucleus LOC Est. |
|---|---|---|---|---|
| 1 | `nucleus graduate --target unity-catalog` | Databricks Unity Catalog | v0.5 | ~100 |
| 2 | `ctx.read_unity_table(catalog, schema, table)` | Databricks Unity (read from Nucleus) | v0.5 | ~100 |
| 3 | `nucleus graduate --target snowflake-horizon` | Snowflake Open Catalog (Horizon) | v0.5 | ~80 |
| 4 | `nucleus graduate --target bigquery-lakehouse` | BigQuery BLMS REST Catalog | v0.5 | ~80 |
| 5 | Generic `nucleus graduate --target <iceberg-rest-url>` | Any Iceberg REST Catalog | v0.5 | ~150 |
| 6 | Iceberg v3 upgrade path in pyiceberg (ADR required) | Snowflake v3 tables, BQ v3 | v0.3+ | 0 (pyiceberg only) |
| 7 | `ctx.dispatch(engine="databricks", sql=...)` | Databricks SQL Warehouse (DBSQL connector) | v1.5 | ~300 |
| 8 | `ctx.dispatch(engine="snowflake", sql=...)` | Snowflake Virtual Warehouse | v1.5 | ~300 |
| 9 | `ctx.dispatch(engine="bigquery", sql=...)` | BigQuery serverless SQL | v1.5 | ~300 |
| 10 | `nucleus serve --mcp` docs pointing to cloud MCP endpoints | BigQuery MCP, Unity MCP | v0.5 | 0 (docs only) |
| 11 | M2M OAuth credential export (`nucleus credentials export --target ...`) | Unity credential vending, Horizon | v0.8 | ~200 |

**Total bridge LOC for v0.5 (items 1-6, 10)**: ~510 LOC. Well within budget.

---

## 7. Match-Don't-Yield Candidates

Features we can replicate at 5-50 engineer scale without leaving the 30K LOC budget:

| # | Big-cloud feature | Our match | LOC estimate | Milestone |
|---|---|---|---|---|
| 1 | **Snowflake Dynamic Tables `TARGET_LAG`** | Add `freshness_sla="5m"` as human-readable alias for `schedule=` on `@nucleus.asset` | ~50 LOC | v0.2 (scheduling daemon) |
| 2 | **Snowflake Cortex Analyst semantic YAML** | `nucleus_semantic.yaml` per project — table/column descriptions, verified metrics, NL aliases — used by `nucleus chat` as grounding context | ~300 LOC | v0.3+ |
| 3 | **Databricks DLT AUTO CDC `once` backfill** | `--mode backfill-once` flag on `nucleus ingest` — ingests a snapshot once, ignores future arrivals | ~80 LOC | v0.3 |
| 4 | **Snowflake Iceberg v3 deletion vectors** | Tracked via pyiceberg upgrade (ADR required) — improves `--mode merge` update/delete performance with zero Nucleus-specific LOC | 0 LOC | v0.3+ (pyiceberg upgrade) |
| 5 | **BigQuery Git integration** | Already done — Nucleus projects are git repos by design; `nucleus_project_anatomy.md` mandates git | 0 LOC | v0.1 ✅ |
| 6 | **Databricks DLT type widening** | `nucleus migrate-schema --widen int-to-long` CLI command calling pyiceberg schema evolution API | ~150 LOC | v0.3+ |
| 7 | **BigQuery `max_staleness` materialized view** | `max_staleness=` parameter on `@nucleus.asset` — equivalent to `TARGET_LAG` freshness contract | ~30 LOC (extends item 1) | v0.2 |

---

## 8. Adopt-from Verdict

Direct adoptions — patterns pioneered at big-cloud scale that we should bring DOWN to our scale:

### Adoption 1: SQL-callable AI functions (`ctx.ai_query()` / `ctx.ai_complete()`)

**Source**: Databricks `ai_query()` (Public Preview 2026), Snowflake `AI_COMPLETE()` (GA Nov 2025), BigQuery `AI.CLASSIFY` (GA 2026).  
**Pattern to copy**: A single SQL function `ai_query(model_name, prompt)` callable from SELECT/WHERE/HAVING. All three platforms converged on this independently — it is the right primitive.  
**Nucleus implementation**: DuckDB Python UDF (`duckdb.create_function("ai_query", ...)`) wrapping httpx to any OpenAI-compatible endpoint. Registered automatically when `nucleus up` runs with an API key configured. No cloud lock-in — works with Ollama locally, OpenAI remotely.  
**LOC**: ~200. **Milestone**: v0.3+.

### Adoption 2: Semantic YAML model for `nucleus chat`

**Source**: Snowflake Cortex Analyst (GA March 2025), BigQuery Graph (Preview 2026).  
**Pattern to copy**: A structured YAML file that defines tables, column descriptions, verified metrics, and natural-language aliases. The LLM uses this file to ground NL→SQL generation — preventing hallucinations of non-existent columns.  
**Nucleus implementation**: `nucleus_semantic.yaml` per project, parsed by `nucleus chat`. Example schema: `{tables: [{name: orders, description: "...", columns: [{name: status, description: "...", verified_values: [open, shipped, cancelled]}]}]}`. The `nucleus chat` command injects this as system context.  
**LOC**: ~300 (YAML parser + prompt builder). **Milestone**: v0.3+.

### Adoption 3: MCP server for AI-agent access (`nucleus serve --mcp`)

**Source**: BigQuery remote MCP server (GA April 2026), Databricks Mosaic AI MCP tools (2025), Snowflake Cortex Agents API (GA Nov 2025).  
**Pattern to copy**: A standardized MCP endpoint that exposes `list_assets()`, `read_schema(asset)`, `query(sql)`, and `get_lineage(asset)` as MCP tools. AI agents (Cursor, Claude Code, Codex) can then browse and query Nucleus assets without custom connectors.  
**Nucleus implementation**: `mcp` Python library + pyiceberg catalog reads + DuckDB SQL execution. Runs as a sidecar alongside `nucleus up`. Exposed at `http://localhost:3000/mcp`.  
**LOC**: ~400. **Milestone**: v0.3+.

### Adoption 4: `freshness_sla=` human-readable lag parameter

**Source**: Snowflake Dynamic Tables `TARGET_LAG` (GA April 2024).  
**Pattern to copy**: Instead of cron expressions (`schedule="*/5 * * * *"`), allow `freshness_sla="5 minutes"` as a human-readable SLA declaration. The platform translates this to a schedule internally.  
**Nucleus implementation**: `@nucleus.asset(freshness_sla="5m")` parses the string and sets the schedule accordingly. Resolves to `schedule="*/5 * * * *"` internally.  
**LOC**: ~50. **Milestone**: v0.2 (alongside scheduling daemon, ADR-025).

---

## 9. Adoption Shortlist — Top 7 from Tier B.1

| # | Feature | Source | Verdict | Target milestone | LOC est. | Pillar served |
|---|---|---|---|---|---|---|
| 1 | **`nucleus serve --mcp` — AI agent data interface** | BigQuery remote MCP GA + all 3 platforms | ADOPT | v0.3+ | ~400 | Pillar 3 (AI-assisted) |
| 2 | **`nucleus_semantic.yaml` — grounded NL→SQL** | Snowflake Cortex Analyst semantic model | ADOPT | v0.3+ | ~300 | Pillar 3 + Pillar 4 |
| 3 | **`ctx.ai_query(model, prompt)` DuckDB UDF** | Databricks `ai_query` + Snowflake `AI_COMPLETE` | ADOPT | v0.3+ | ~200 | Pillar 3 |
| 4 | **`freshness_sla="5m"` on `@nucleus.asset`** | Snowflake Dynamic Tables `TARGET_LAG` | MATCH/ADOPT vocabulary | v0.2 | ~50 | Pillar 4 (familiar UX) |
| 5 | **`nucleus graduate --target <iceberg-rest-url>`** | All 3 platforms converge on Iceberg REST | YIELD bridge | v0.5 | ~150 | Pillar 2 (composable) |
| 6 | **`--mode backfill-once` on `nucleus ingest`** | Databricks DLT AUTO CDC `once` parameter | MATCH | v0.3 | ~80 | Pillar 1 (performance) |
| 7 | **pyiceberg Iceberg v3 upgrade (deletion vectors)** | Snowflake Iceberg v3 GA + all 3 converge | TRACK/UPGRADE | v0.3+ | 0 (pyiceberg pin only) | Pillar 1 (performance on merge) |

---

## 10. Open Questions for Founder

These platform-strategy forks require founder judgment and cannot be resolved by Anti-Over-Engineering defaults:

1. **MCP server timing**: BigQuery GA'd their remote MCP server in April 2026. All three platforms now expose MCP. Should `nucleus serve --mcp` move to v0.2 (6 months earlier than the default v0.3+ plan) to capture the MCP-native-AI-agent wave? Risk: 400 LOC distraction from v0.2 Workbench. Reward: Nucleus assets become consumable by Cursor agents on day 1.

2. **Semantic YAML vs. contract convergence**: The `nucleus_semantic.yaml` adoption (from Cortex Analyst) overlaps with `@nucleus.contract` (schema contracts). Should these merge into one file? Or stay separate — contracts as machine-enforceable assertions, semantic model as human/AI-readable descriptions? Merging reduces file proliferation; separating preserves single-responsibility.

3. **`ctx.ai_query()` model endpoint strategy**: DuckDB UDF + httpx works locally, but which model endpoints do we support at v0.3+? Options: (a) OpenAI-compatible only (simple, broad, includes Ollama), (b) model-agnostic (user supplies any httpx-compatible endpoint), (c) require explicit API key in `nucleus_project.yaml` (no defaults). Choice has pricing, privacy, and DX implications.

4. **Iceberg v3 upgrade gate**: Snowflake GA'd Iceberg v3 on May 7, 2026. BigQuery has v3 in preview. Deletion vectors in v3 would significantly improve our `--mode merge` CDC performance. Should we fast-track the pyiceberg v3 upgrade (requires ADR per Constraint #11) ahead of v0.3+ schedule? Risk: pyiceberg 0.9+ may not yet have stable v3 support. Benefit: better merge performance for early users.

5. **Graduation CLI UX**: All three platforms now support Iceberg REST Catalog as a graduation target. Should `nucleus graduate` be a first-class v0.5 CLI command with `--target unity|snowflake-horizon|bigquery-lakehouse|<custom-url>`? Or should we implement it as a simple `nucleus_project.yaml` migration guide (docs-only)? The CLI command signals graduation as a first-class feature; docs-only signals it's a power-user edge case.

---

## 11. NEEDS VERIFICATION

Items that could not be fully confirmed from primary sources at time of writing:

1. **`[NEEDS VERIFICATION]` pyiceberg v3 support timeline** — pyiceberg's roadmap for Iceberg v3 (deletion vectors, row lineage) was not confirmed from official pyiceberg docs. Check: [https://py.iceberg.apache.org/](https://py.iceberg.apache.org/) and [pyiceberg GitHub releases](https://github.com/apache/iceberg-python/releases) before planning pyiceberg upgrade ADR. This is the highest-priority verification item.

2. **`[NEEDS VERIFICATION]` BigQuery BLMS REST Catalog GA status (May 2026)** — The April 2026 announcement said "will be GA next month" (May 2026). As of 2026-05-15 (this doc's date), GA may have shipped. Check: [https://cloud.google.com/bigquery/docs/blms-rest-catalog](https://cloud.google.com/bigquery/docs/blms-rest-catalog) for current GA status.

3. **`[NEEDS VERIFICATION]` Databricks `ai_query()` GA timeline** — Currently "Public Preview" as of May 2026. Databricks has not announced a GA date. Check: [https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query) for status updates before we build our `ctx.ai_query()` against the Databricks pattern.

4. **`[NEEDS VERIFICATION]` Snowflake external engine WRITES to Iceberg v3 via Horizon** — The May 7, 2026 GA announcement states: "Writes from external engines to Snowflake-managed Iceberg v3 tables through Horizon Catalog aren't supported yet." This limits graduation from Nucleus → Snowflake to read-only scenarios. Check: [https://docs.snowflake.com/en/user-guide/tables-iceberg](https://docs.snowflake.com/en/user-guide/tables-iceberg) for when write support ships.

5. **`[NEEDS VERIFICATION]` DuckDB `create_function` API for async httpx calls** — The `ctx.ai_query()` implementation above assumes DuckDB supports async Python UDFs callable from SQL. This needs verification against current DuckDB Python API docs before implementation. Check: [https://duckdb.org/docs/api/python/function](https://duckdb.org/docs/api/python/function).

---

## 12. References

All docs URLs cited in this report:

**Databricks**
- Unity Catalog Expanded Interoperability: https://www.databricks.com/blog/expanded-interoperability-unity-catalog-open-apis
- Unity Catalog Credential Vending: https://docs.databricks.com/aws/en/external-access/credential-vending
- Unity Catalog External Access Admin: https://docs.databricks.com/aws/en/external-access/admin
- Lakeflow Declarative Pipelines 2026 Release Notes: https://docs.databricks.com/aws/en/release-notes/dlt/2026
- DLT 2025 Update Blog: https://databricks.com/blog/2025-dlt-update-intelligent-fully-governed-data-pipelines
- Lakeflow AUTO CDC APIs: https://docs.databricks.com/aws/en/ldp/cdc
- Mosaic AI Vector Search GA: https://databricks.com/blog/announcing-mosaic-ai-vector-search-general-availability-databricks
- Mosaic AI Summit 2025: https://databricks.com/blog/mosaic-ai-announcements-data-ai-summit-2025
- Mosaic AI Agent Framework: https://www.databricks.com/blog/announcing-mosaic-ai-agent-framework-and-agent-evaluation
- `ai_query` Function: https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query
- AI Functions Guide: https://docs.databricks.com/aws/en/large-language-models/ai-query
- Genie NL→SQL Next Gen: https://www.databricks.com/blog/next-generation-databricks-genie
- Databricks SQL Connector for Python: https://docs.databricks.com/en/dev-tools/python-sql-connector.html
- Full Iceberg Support Announcement: https://databricks.com/blog/announcing-full-apache-iceberg-support-databricks

**Snowflake**
- Iceberg Tables (main): https://docs.snowflake.com/en/user-guide/tables-iceberg
- Iceberg v3 GA (May 7, 2026): https://docs.snowflake.com/en/release-notes/2026/other/2026-05-07-iceberg-v3-ga
- Partitioned Writes GA (Oct 2025): https://docs.snowflake.com/en/release-notes/2025/other/2025-10-17-iceberg-partitioned-writes-ga
- Dynamic Iceberg Tables GA (Nov 2024): https://docs.snowflake.com/en/release-notes/2024/other/2024-11-12-dynamic-iceberg-tables
- Dynamic Tables GA (Apr 2024): https://docs.snowflake.com/en/release-notes/2024/other/2024-04-29-dynamic-tables
- Dynamic Tables Incremental Refresh (May 2025): https://docs.snowflake.com/en/release-notes/2025/other/2025-05-01-dynamic-tables-current-timestamp.html
- Cortex AI Functions: https://docs.snowflake.com/en/user-guide/snowflake-cortex/aisql
- AI_COMPLETE GA (Nov 2025): https://docs.snowflake.com/en/release-notes/2025/other/2025-11-21-ai-complete-ga
- Cortex AI Functions GA (Nov 2025): https://docs.snowflake.com/en/release-notes/2025/other/2025-11-04-cortex-aisql-operators-ga
- Cortex Agents GA (Nov 2025): https://docs.snowflake.com/en/release-notes/2025/other/2025-11-04-cortex-agents
- Cortex Analyst: https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst
- Cortex Analyst Improved SQL (Apr 2026): https://docs.snowflake.com/en/release-notes/2026/other/2026-04-13-cortex-agents-agentic-analyst
- Snowpark Container Services GA: https://snowflake.com/en/blog/secure-app-deployment-snowpark-container-services-ga
- Streamlit Container Runtime GA (Mar 2026): https://docs.snowflake.com/en/release-notes/2026/other/2026-03-09-sis-container-runtime-ga
- Notebooks in Workspaces GA (Feb 2026): https://docs.snowflake.com/en/release-notes/2026/other/2026-02-05-notebooks-in-workspaces.html
- Native Apps Framework: https://docs.snowflake.com/en/developer-guide/native-apps/native-apps-about.md
- Native Apps Configuration GA (Apr 2026): https://docs.snowflake.com/en/release-notes/2026/other/2026-04-28-nativeapps-configuration-ga

**BigQuery / Google Cloud**
- BQ Agentic Era (Apr 2026): https://cloud.google.com/blog/products/data-analytics/unveiling-new-bigquery-capabilities-for-the-agentic-era
- Managed Iceberg Tables: https://cloud.google.com/bigquery/docs/iceberg-tables
- BigLake Metastore REST Catalog GA: https://cloud.google.com/blog/products/data-analytics/biglake-metastore-now-supports-iceberg-rest-catalog
- Lakehouse Iceberg REST Catalog: https://cloud.google.com/bigquery/docs/blms-rest-catalog
- BQ Announcing Iceberg Tables (Oct 2024): https://cloud.google.com/blog/products/data-analytics/announcing-bigquery-tables-for-apache-iceberg
- Iceberg External Tables: https://cloud.google.com/bigquery/docs/iceberg-external-tables
- BigQuery MCP Server: https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp
- BigQuery Remote MCP Blog: https://cloud.google.com/blog/products/data-analytics/using-the-fully-managed-remote-bigquery-mcp-server-to-build-data-ai-agents/
- Conversational Analytics: https://docs.cloud.google.com/bigquery/docs/conversational-analytics
- Data Science Agent: https://docs.cloud.google.com/bigquery/docs/colab-data-science-agent
- Colab Data Apps: https://docs.cloud.google.com/bigquery/docs/colab-data-apps
- BigQuery Graph: https://docs.cloud.google.com/bigquery/docs/graph-overview
- Gemini in BQ GA (Aug 2024): https://cloud.google.com/blog/products/data-analytics/gemini-in-bigquery-features-are-now-ga
- BigQuery Materialized Views: https://cloud.google.com/bigquery/docs/materialized-views-intro
- BigQuery Studio Notebook Gallery GA (Apr 2026): https://cloud.google.com/blog/products/data-analytics/templates-in-bigquery-studio-notebook-gallery
- BigQuery Release Notes: https://cloud.google.com/bigquery/docs/release-notes

---

*End of Tier B.1 research doc. Complements `parity_vs_databricks_snowflake.md` (capability matrix) and `parity_vs_bosch_ely_adb_batch.md` (pipeline analysis). This doc focuses exclusively on 2024-2026 flagship features and their Nucleus adoption/match/yield evaluation.*
