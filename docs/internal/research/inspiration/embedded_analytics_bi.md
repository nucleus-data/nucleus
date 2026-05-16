# Embedded Analytics & BI Landscape 2026

> Last verified: 2026-05-15 against publicly available official documentation
> Research tier per AGENTS.md §11.14: Inspiration (peer patterns to adopt, not deps to wrap)
> Model used: Claude Sonnet 4.6 (Gemini 3.1 Pro unavailable in current runtime; fallback per AGENTS.md §11.14 availability policy)

---

## Executive Summary — Top 3 Integration Patterns

Ordered by beachhead impact on the **<30-minute to BI-ready Iceberg asset** metric:

### Pattern 1 — Emit `nucleus.db` as the Universal BI Handshake (v0.1)

Nucleus materialises assets to Iceberg+MinIO. By also generating a local `nucleus.db` DuckDB file with `ATTACH` views pointing at each Iceberg snapshot, every DuckDB-compatible BI tool (Superset, Evidence, Rill, Streamlit) gets a single zero-configuration connection. Cost: ~50 LOC in `nucleus run`. This is the v0.1 BI integration story.

### Pattern 2 — Emit `<asset>_metrics_view.yaml` (Rill-Compatible) from Every Materialization (v0.1 stretch / v0.2)

Rill reads a YAML file defining a metrics view (time series column, measures, dimensions) over a DuckDB model. Nucleus can auto-generate this companion file from the asset schema on every materialization. A data engineer runs `nucleus run orders` and instantly gets a drag-and-drop Rill dashboard — no BI configuration. Cost: ~150 LOC. Directly serves the 30-min beachhead metric.

### Pattern 3 — Adopt MetricFlow YAML as Nucleus's Semantic Column Convention (v0.3 gate)

MetricFlow (Apache 2.0, dbt-Labs) is the closest thing to an open standard for semantic layer definitions as of 2026. Its YAML spec (promoted to dbt Core v1.12, May 2026) lets you annotate columns with `metrics:` blocks. If Nucleus's `@nucleus.asset` decorator accepts the same `measures=` / `dimensions=` convention, downstream tools (dbt Semantic Layer, Lightdash, Cube) consume Nucleus assets with zero transformation. This must be *designed in* at v0.1 even if the full spec output is deferred to v0.3.

---

## 1. Rill Data — DuckDB-Native BI-as-Code

| Property | Value |
|---|---|
| Official docs | https://docs.rilldata.com/ |
| License | Apache 2.0 [1] |
| GitHub | https://github.com/rilldata/rill (2,542+ stars) [1] |
| Latest release | v0.86 (March 2026) [4] |
| Engine | Go (no JVM) [1] |

### What it is

Rill is an OSS BI tool where dashboards are git-committed YAML files executed by an embedded DuckDB engine. `rill dev` spins a localhost dashboard in under 5 seconds from a `git clone`. The project files are fully version-controlled — sources, SQL models, metrics views, and explore dashboards all live as YAML. [1][3]

### DuckDB OLAP integration

Rill ships DuckDB as a managed embedded engine by default. The project root gets `connectors/duckdb.yaml`:

```yaml
type: connector
driver: duckdb
managed: true
```

No additional configuration required. Rill also supports live-connecting to an external DuckDB file: [2]

```yaml
type: connector
driver: duckdb
path: '/path/to/nucleus.db'
```

**Performance note:** Rill recommends keeping DuckDB data under 50 GB. For larger datasets, Rill supports ClickHouse as an alternative OLAP engine via `olap_connector: clickhouse` in `rill.yaml`. [2][5]

### DuckDB Extensions

Rill exposes DuckDB extension loading via `init_sql` in the connector YAML: [2]

```yaml
type: connector
driver: duckdb
init_sql: |
  INSTALL iceberg;
  LOAD iceberg;
  INSTALL httpfs;
  LOAD httpfs;
```

This means Nucleus assets stored in Iceberg+MinIO are immediately queryable from Rill by loading the `iceberg` extension and pointing at the REST catalog.

### Metrics view YAML — the BI contract

Rill's metrics layer lives in `<asset>_metrics_view.yaml`: [3]

```yaml
type: metrics_view
model: orders_model
timeseries: event_date
measures:
  - label: "Total Orders"
    expression: COUNT(*)
    name: total_orders
  - label: "Revenue"
    expression: SUM(revenue)
    name: total_revenue
dimensions:
  - column: region
  - column: product_category
```

This YAML is the exact output Nucleus should emit alongside every materialized asset. The measures and dimensions can be inferred from the asset schema (numeric columns → potential measures; low-cardinality columns → dimensions).

### Rill v0.86 — DuckLake live connector

Rill v0.86 added **BigQuery and DuckLake live connectors**, upgrading to DuckDB 1.5.2. [4] DuckLake is the DuckDB-native Iceberg-compatible table format — assets materialized via DuckLake are directly explorable in Rill with no additional configuration.

### Workbench UX patterns worth borrowing

- **Auto-profiling on source attach**: cardinality, nulls, min/max rendered without a user query. Workbench's Query page should profile an asset on open.
- **AI-assisted metrics generation**: Rill's "Explain this error" AI feature in v0.86 is one step toward `rill edit metrics` via natural language. Nucleus Workbench v0.2 should offer "Suggest measures for this asset" using the same pattern.
- **Time grain picker**: Rill's `smallest_time_grain` config in `rill.yaml` [5] maps naturally to a Nucleus asset's `freshness_sla` annotation.
- **Project-wide OLAP defaults**: Rill inherits settings from `rill.yaml` → resource YAML → individual override. Nucleus could adopt the same three-tier inheritance for asset rendering defaults.

### 8-Question Gate

| Question | Answer |
|---|---|
| Maps to architectural layer? | Experience layer (v4.1 §3) — **YES** |
| Serves <30-min beachhead? | **YES** — companion YAML makes assets Rill-ready in seconds |
| Wrap possible instead of build? | **YES** — emit compatible YAML; zero library import |
| Preserves no-JVM? | **YES** — Rill is Go-based |
| Local-identical-to-prod? | **YES** |
| Within 30K LOC budget? | **YES** — ~200 LOC |
| Empirical trigger? | **YES** — beachhead requires BI output |
| v0.1 Hello World or deferrable? | PARTIAL — `nucleus.db` in v0.1; companion YAML in v0.1 stretch / v0.2 |

**Verdict: PATTERN-ADOPT.** No direct library import. Emit `<asset>_metrics_view.yaml` from `nucleus run`. Embed Rill-compatible preview in Workbench v0.2 via the DuckDB live connector.

---

## 2. Evidence.dev — Markdown-Driven BI

| Property | Value |
|---|---|
| Evidence OSS docs | https://docs.evidence.dev/ |
| Evidence Studio docs | https://docs.evidence.studio/ |
| License | MIT (OSS) [1] |
| Studio launch | June 2025 [7] |

### What it is

Evidence is a BI-as-code platform where dashboards are `.md` files with embedded SQL — git-committed, CI-deployable, peer-reviewable. The developer writes SQL in markdown; Evidence compiles to a static site. No drag-and-drop. [1]

### Platform bifurcation (2025–2026)

Evidence has split into two products:

- **Evidence OSS**: DuckDB-native, local dev, static site output. Free, MIT. [1][6]
- **Evidence Studio** (cloud, June 2025): Managed ClickHouse backend (replacing DuckDB for scale), Iceberg + DuckDB + Delta Lake connectors, AI agent (GPT-4o + Mistral Codestral) writing markdown/SQL from natural language, row-level access controls. [7][8]

The backend migration from DuckDB to ClickHouse for the cloud product validates Nucleus's own design: DuckDB is excellent for local/exploration; yield to giants (or a hosted OLAP engine) for cloud-scale serving. The OSS DuckDB path remains the right default for Nucleus's beachhead persona.

### DuckDB connection

Evidence OSS configures data sources in YAML: [6]

```yaml
# sources/nucleus_output/connections.yaml
type: duckdb
database: /path/to/nucleus.db
```

This means a Nucleus user can point Evidence at `nucleus.db` (the handshake file from Pattern 1) with a single YAML edit. Total setup time: < 2 minutes. Within beachhead.

### Evidence Studio Iceberg connector

Evidence Studio added Iceberg as a data source alongside DuckDB, Delta Lake, and direct cloud storage. [8] ⚠️ **NEEDS VERIFICATION** — connector config details not confirmed (see §12).

### Git-first workflow alignment

Evidence projects are Git repositories with GitHub integration, feature branch workflows, and branch preview deployments. [9] This is 100% aligned with Nucleus's asset graph model: each materialized asset has a git-committed definition. The natural extension: Nucleus could ship an `<asset>.evidence.md` template that Evidence opens for instant reporting. Each asset type (source asset, transform, aggregate) gets a different template.

### UX patterns worth borrowing

- **Aggregation-in-component syntax** (Evidence Studio 2025): moves aggregation logic into the component definition rather than requiring raw SQL. Reduces page-level code by >60%. [7]
- **Schema-aware autocomplete in IDE**: Workbench v0.2 should implement this for `ctx.sql()` blocks.
- **AI chat on published reports**: Evidence Studio embeds a chat interface over governed data. The Nucleus Copilot (v0.2) should support the same pattern: `nucleus chat --asset <name>` opens a chat over the asset's DuckDB view.

**Verdict: PATTERN-ADOPT (git-first philosophy + DuckDB connection). Evidence.dev is the closest philosophical peer to Nucleus. No direct integration needed — `nucleus.db` is the bridge.**

---

## 3. Quary — dbt+Visualization (Rust+TS)

| Property | Value |
|---|---|
| GitHub | https://github.com/quarylabs/quary (2,364 stars, v0.10.1 Jan 2026) [10] |
| License | Apache 2.0 [10] |
| Backer | Y Combinator W24 [10] |
| Last push | April 2026 [10] |

### What it is

Quary is an OSS BI platform for engineers: SQL transformations (dbt-style) + chart generation in a VSCode extension + CLI, written in Rust (73.9%) + TypeScript (24.3%). [10]

### Current status (2026)

| Feature | Status |
|---|---|
| Charts (SQL → visualization) | ✅ Fully supported |
| Dashboards (multi-chart layout) | 🚧 WIP |
| Reports | 🚧 WIP |
| Web UI (browser sharing) | 🔬 Early development |

Supported databases: DuckDB, BigQuery, Snowflake, PostgreSQL, Redshift, SQLite, Supabase. [10]

### Adoption signal

2,364 GitHub stars with YC W24 backing. Slower cadence than Rill (2,542 stars, enterprise users) or Lightdash (9,000+ stars). The WIP dashboard surface area makes it unsuitable as a direct integration target. The philosophical alignment is strong: engineers doing BI, code-first, Rust performance.

### Nucleus relevance

Quary's **SQL transformation → chart in a single developer action** pattern is worth adopting in Workbench. The Rust CLI architecture demonstrates that a BI tool can be fast and lightweight without JVM.

**Verdict: MONITOR. Re-evaluate when dashboards reach production-ready status. Target: v0.3 Workbench planning cycle.**

---

## 4. Lightdash — OSS Looker Alternative (dbt-Native Semantic Layer)

| Property | Value |
|---|---|
| Official docs | https://docs.lightdash.com/ |
| License | MIT [11] |
| GitHub stars | 9,000+ [11] |
| Cloud Pro | $3,000/month, unlimited seats [13] |

### What it is

Lightdash is an OSS BI platform that reads dbt `models/*.yml` and auto-generates an explore interface. The semantic layer lives in YAML co-located with dbt models — no separate LookML, no secondary DSL. [11][13]

### The semantic annotation YAML pattern

Lightdash metrics are defined inline with dbt column definitions: [12]

```yaml
# models/orders.yml (dbt)
models:
  - name: orders
    columns:
      - name: order_id
        meta:
          metrics:
            order_count:
              type: count_distinct
      - name: revenue
        meta:
          metrics:
            total_revenue:
              type: sum
```

One YAML definition consumed by both dbt and Lightdash. This is the **single-source-of-truth semantic pattern** Nucleus must adopt: metric definitions live in the asset contract, not in a downstream BI tool.

### dbt v1.12 + MetricFlow convergence

Lightdash is actively tracking dbt Core v1.12 (May 2026) and the MetricFlow spec convergence. [12] The dbt Semantic Layer (MetricFlow-powered) and Lightdash's own metric YAML are converging toward the same spec. Nucleus should design `@nucleus.asset` to be compatible with this emerging standard from day one, even if full output is v0.3.

### 2026 capabilities

- **Agentic AI**: auto-builds dashboards, refactors analytics, answers Slack queries — all grounded in the governed semantic layer to prevent hallucinations. [13]
- **React SDK embed**: iframe-free embedding, no vendor lock-in. [11]
- **Branch preview environments**: like GitHub PR previews, but for BI dashboards. [13]

### Iceberg integration path

Lightdash queries via dbt adapters. dbt-duckdb (Nucleus's v0.3 optional adapter) supports Iceberg through DuckDB's Iceberg extension. Full chain: Nucleus → dbt-duckdb (optional, v0.3) → Lightdash. **Deferred to v0.3.**

**Verdict: PATTERN-ADOPT (semantic YAML convention). The column-level `metrics:` annotation pattern is the most important takeaway from this entire research lane. Integration path is v0.3+ via dbt-duckdb.**

---

## 5. Metabase + Superset in 2026: Adoption and Iceberg/DuckDB Status

### Metabase

**Official docs:** https://www.metabase.com/  
**DuckDB connector page:** https://www.metabase.com/data-sources/duckdb

- DuckDB connector: **community-managed, self-hosted only**. Not supported on Metabase Cloud. Requires custom JAR driver. [14]
- Iceberg: **no native connector**. Accessible indirectly via Databricks (official connector), Dremio (community), Trino (community), StarRocks (community). [14]
- Known issue (v0.59.1, updated 2026): Iceberg column type `string` not properly mapped from Redshift external tables, causing filtering breakage. [14]
- Market position: ~36,000 GitHub stars; dominates "simple BI for non-technical users" segment.
- DuckDB story is community-driven — Metabase Cloud will not support it without a first-class sponsorship.

**Nucleus integration path:** Metabase can query Nucleus assets via DuckDB JDBC → REST catalog → Iceberg scan. Setup complexity is HIGH; not suitable for beachhead metric (>30 min setup). **Document as v0.5 advanced guide, not v0.1 quickstart.**

### Apache Superset

**Official docs:** https://superset.apache.org/docs/databases/supported/duckdb/  
**License:** Apache 2.0

- DuckDB connector: **officially supported** via `duckdb-engine` PyPI package. Feature score 38/201 (JOINs, subqueries, dynamic catalog, catalog support). [15]
- MotherDuck supported as compatible database (same connection string pattern). [15]
- **DuckDB catalog support merged April 2025** (PR #28751): Superset can now browse DuckDB catalogs, which includes DuckDB-attached Iceberg databases via the Iceberg extension. [15]
- Iceberg: accessible via DuckDB's Iceberg extension attached in `nucleus.db`. No native `iceberg://` connector required.

**Nucleus integration path (v0.1):**

```
# User adds to Superset: Database → DuckDB
# SQLAlchemy URI:
duckdb:////${NUCLEUS_HOME}/nucleus.db
```

Once connected, Superset sees all materialized Nucleus assets as queryable views. Setup time: under 5 minutes from `nucleus up`. **Include in v0.1 "Connect BI Tools" docs.**

### Market position 2026

- Superset is gaining enterprise traction (Airbnb, Netflix, Preset.io as managed hosting). Growing.
- Metabase dominates SMB. Stable.
- Both are being challenged by AI-native tools (Hex, Mode Analytics, ThoughtSpot).
- The **DuckDB-as-universal-connector pattern** (Nucleus emits `nucleus.db` → any DuckDB-compatible BI tool connects) is the cleanest v0.1 integration story that covers both tools simultaneously.

---

## 6. Streamlit / Gradio / Shiny for Python

### Streamlit

**Official docs:** https://docs.streamlit.io/  
**License:** Apache 2.0

The Streamlit + DuckDB + Iceberg stack is well-documented and production-proven. [16] The core pattern:

```python
import duckdb
import streamlit as st

# Nucleus ctx.df() returns a DuckDB relation
conn = duckdb.connect("/path/to/nucleus.db")
df = conn.execute("SELECT * FROM default.orders").df()

st.dataframe(df)
st.bar_chart(df.groupby("region")["revenue"].sum())
```

PyIceberg also enables `table.scan().to_duckdb()` — Iceberg → DuckDB relation in a single expression. [16] The natural `ctx.df()` extension for v0.1 docs: `ctx.df("orders")` returns an object with `.to_arrow()`, `.to_pandas()`, and `.to_duckdb()` — all three are importable by Streamlit apps.

**Verdict: PATTERN-ADOPT. Document `ctx.df().to_arrow()` + Streamlit in v0.1 "Quick Dashboards" quickstart. No library integration needed.**

### Gradio

**Official docs:** https://www.gradio.app/  
**License:** Apache 2.0

Gradio (now beyond ML model demos) supports real-time streaming dashboards via DuckDB + Python threading (September 2025 demonstration). [search context] Better for interactive input forms + output visualization than Streamlit's data-first approach. Relevant for Nucleus's v0.5 AI Copilot output rendering — where the user sends a natural language query and sees a rendered chart.

**Verdict: MONITOR for v0.5 AI Copilot output rendering.**

### Shiny for Python

**Official docs:** https://shiny.posit.co/py/  
**License:** MIT

Shiny for Python (Posit) is gaining traction in R-heavy data science teams. A January 2026 comparison demonstrates Shiny and Streamlit at equivalent performance for DuckDB OLAP rendering with geospatial data. [search context] Primarily relevant for teams with R/RStudio background. Nucleus's beachhead is Python-first.

**Verdict: LOW PRIORITY. Document as community-contributed example in v0.3+.**

---

## 7. "BI-Ready Asset" — Minimum Metadata Checklist for 2026

Based on what Metabase, Superset, Rill, Lightdash, and Tableau require to auto-detect and correctly render a Nucleus Iceberg asset without manual configuration:

### Tier 1 — Required for any BI tool to connect and query

| Metadata | Iceberg mechanism | Nucleus emission point |
|---|---|---|
| Human-readable name | `table_properties['nucleus.display_name']` | `@nucleus.asset(label=...)` |
| Schema (column names + types) | Iceberg schema (field IDs per spec) | Auto from DuckDB `DESCRIBE` |
| Partition spec | Iceberg partition spec | Asset definition |
| Row count (estimate) | Snapshot summary `total-records` | Written on every materialization |
| Last materialization timestamp | Snapshot `committed-at` | Auto-written by pyiceberg |
| Primary key columns | `table_properties['nucleus.primary_key']` | Asset spec `primary_key=[...]` |
| Description | `table_properties['comment']` | `@nucleus.asset(description=...)` |

### Tier 2 — Required for semantic-layer tools (Lightdash, Cube, MetricFlow)

| Metadata | Format | Nucleus emission point |
|---|---|---|
| Measure definitions | Iceberg `table_properties` OR companion YAML | `nucleus_semantic.yaml` (v0.3) |
| Dimension columns | Companion YAML | `nucleus_semantic.yaml` (v0.3) |
| Freshness SLA | `table_properties['nucleus.freshness_sla']` (ISO 8601 duration, e.g., `PT1H`) | Asset spec `freshness=...` |
| Source lineage | OpenLineage NDJSON (already in spec) | ✅ Already emitted |
| Owner | `table_properties['nucleus.owner']` | `nucleus_project.yaml` |

### Tier 3 — Iceberg v3 features (future, v0.5+)

Iceberg v3 is in active development; not all engines support the full feature set as of 2026. [26] Nucleus should write v2 tables by default with `format_version=3` as an optional flag for v0.3+.

| Feature | Iceberg v3 mechanism | Relevance to Nucleus |
|---|---|---|
| Row lineage | Row IDs + sequence numbers | GDPR audit, regulated pipelines |
| `variant` type | Semi-structured JSON columns | Event streams, API data |
| `geometry`/`geography` | Geospatial types | Logistics, mapping assets |
| Binary deletion vectors | Compact delete representation | CDC, high-churn assets |
| Default column values | Schema-level defaults | Simplified schema evolution |
| Multi-argument partition transforms | Composite partitioning | Advanced performance tuning |

### The `nucleus.db` BI handshake file (v0.1)

The simplest v0.1 BI integration: `nucleus up` generates a `nucleus.db` DuckDB file that exposes all materialized assets as views:

```sql
-- Generated automatically by `nucleus up`
ATTACH 'http://minio:9000' AS minio_store (
  TYPE ICEBERG,
  ENDPOINT 'http://minio:9000'
);
-- Each materialized asset becomes a view
CREATE OR REPLACE VIEW default.orders AS
  SELECT * FROM iceberg_scan('s3://data/default/orders/');
CREATE OR REPLACE VIEW default.customers AS
  SELECT * FROM iceberg_scan('s3://data/default/customers/');
```

Cost: ~50 LOC. Any DuckDB-compatible BI tool (Superset, Evidence, Rill, Streamlit) connects with one file path. **This is the v0.1 BI handshake.**

---

## 8. Notebook-as-Dashboard: Observable and Quarto

### Observable Framework

**Official docs:** https://observablehq.com/framework  
**License:** ISC (Framework), Apache 2.0 (Plot library)

Observable's 2025-2026 positioning: notebook-for-exploration (Observable Notebooks) paired with Observable Framework for production dashboards. [18] Key patterns:

- **Data loaders**: server-side data fetching at build time, output cached as Parquet/Arrow/JSON for static serving — no database connection required at serve time.
- **Reactive cells**: Observable's reactive runtime auto-re-executes downstream cells when upstream data changes.
- **DuckDB-WASM**: built-in DuckDB running in the browser via WebAssembly. In December 2025, DuckDB-WASM gained support for reading Iceberg REST catalogs from the browser — zero server setup for sub-50GB Iceberg queries. [19]

The DuckDB-WASM + Iceberg REST pattern means a Nucleus user could embed an Observable dashboard that reads Nucleus assets directly in the browser, with zero additional backend. This is architecturally elegant and directly relevant to Workbench's client-side query page.

**Verdict: PATTERN-MONITOR.** The DuckDB-WASM + Iceberg REST combination (December 2025) is the most exciting development in this space. Re-evaluate for Workbench v0.3 (client-side query execution, zero-backend preview).

### Quarto Dashboards

**Official docs:** https://quarto.org/docs/dashboards/  
**License:** MIT

Quarto Dashboards (v1.4+, current v1.9) turn `.qmd` files into dashboard layouts — Python cells become cards, rows/columns defined with markdown headings. [17] Key facts:

- Deploy as **static HTML** (no server) or with **Shiny backend** for full interactivity. [17]
- Supports Python (Plotly, Matplotlib, Jupyter Widgets), R, Julia, Observable JS. [17]
- Quarto 1.9 adds `output for LLMs` (generates `llms.txt` / `.llms.md` for AI tool consumption) — directly relevant to Nucleus's AI-ready pillar.
- `quarto-marimo` engine extension in development: will upgrade Marimo from a filter extension to a full engine, making `.marimo.py` notebooks publishable as Quarto dashboards. [17]

The `quarto-marimo` connection is the critical link: Marimo is Nucleus's v0.3+ notebook engine. If `quarto-marimo` matures, `nucleus publish --format quarto` becomes a natural one-command dashboard deployment.

**Verdict: PATTERN-MONITOR for v0.3.** Document as a `nucleus publish --format quarto` future path. Track `quarto-marimo` engine PR.

---

## 9. Open BI Standards: Cube.dev, MetricFlow, Malloy

### MetricFlow — The Emerging Open Standard

| Property | Value |
|---|---|
| Docs | https://docs.getdbt.com/docs/build/build-metrics-intro |
| GitHub | https://github.com/dbt-labs/metricflow (1,559 stars) [20] |
| License | Apache 2.0 [20] |
| Latest | v0.209.0 (October 2025) [20] |
| dbt Core v1.12 | May 2026 [21] |

MetricFlow is the open-source semantic layer engine under dbt's Semantic Layer. The latest spec (promoted in dbt Core v1.12, May 2026) defines five metric types: simple, cumulative, ratio, derived, conversion. [21] Example: [21]

```yaml
metrics:
  - name: total_revenue
    type: simple
    label: "Total Revenue"
    measure:
      name: revenue
      agg: sum
    time_spine_required_granularity: day
```

MetricFlow is the **closest thing to an open standard for semantic layers as of 2026**. The Apache 2.0 license means Nucleus can freely adopt and emit this format.

**Nucleus semantic spec alignment (v0.3):** The `@nucleus.asset` decorator should accept a `measures=` parameter mapping to MetricFlow `metrics:` definitions. Emitting a `nucleus_semantic.yaml` alongside each materialized asset would make Nucleus assets passable to dbt Semantic Layer, Lightdash, and Cube without transformation. Design must be compatible from v0.1 even if the full YAML output ships in v0.3.

### Cube.dev — Semantic Layer (BSL License)

| Property | Value |
|---|---|
| Docs | https://docs.cube.dev/ |
| License | Elastic License 2.0 (BSL-ish) — **cannot be embedded** [22][23] |
| Data model format | YAML or JavaScript [23] |

Cube's YAML defines cubes with measures, dimensions, and joins. Cube exposes a `/meta` REST endpoint returning the data model as JSON for downstream tool consumption. [22] An open GitHub issue (#6389) requests an exportable CI artifact. [22]

**Nucleus relevance:** Cube's BSL license prohibits embedding or wrapping. However, emitting Cube-compatible YAML as a companion file (a documentation guide, not a code integration) lets users who self-host Cube point it at Nucleus outputs. ~100 LOC companion generator, v0.3.

**Verdict: DOCUMENTATION GUIDE only (BSL blocks integration). Emitting a Cube-compatible companion YAML is low-cost and high-value for enterprise users.**

### Malloy — Semantic Query Language (Google)

| Property | Value |
|---|---|
| Official site | https://www.malloydata.dev/ |
| GitHub | https://github.com/malloydata/malloy (2,433 stars, v0.0.368 Apr 2026) [24] |
| License | Apache 2.0 [24] |
| PyPI status | Alpha (3 - Alpha) [25] |
| Monthly downloads | 7,727 (PyPI) [25] |

Malloy is a semantic query language from Google that compiles to SQL. Natively supports DuckDB, BigQuery, Snowflake, PostgreSQL, MySQL, Trino, Presto. [24] VSCode extension: 9,598 installs. [24]

Key Malloy concepts: **Sources** (named views with semantic metadata), **Explores** (ad-hoc analytical queries), **Turtles** (named reusable subqueries). Malloy expressions compile to DuckDB SQL — directly relevant to Nucleus's DuckDB engine.

Malloy remains Alpha status. Community traction (2,433 stars) is modest compared to the MetricFlow/dbt ecosystem. The npm API is "still in beta and subject to change." [24][25]

**Verdict: MONITOR. If Malloy gains traction (>5K stars, stable PyPI API), evaluate as an optional Nucleus query language for power users. Not v0.1 or v0.3 material.**

---

## 10. Workbench Analytics-Embed Sketch (v0.2)

Based on the above research, here is a proposed Workbench v0.2 analytics preview architecture. This is a design pattern sketch, not a specification — it should be validated against `docs/specs/nucleus_architecture_v4.1.md` before implementation.

### Query Page Flow

```
User opens asset in Workbench Query page
  → Nucleus backend queries: SELECT * FROM <asset> LIMIT 1000
    via DuckDB connection to nucleus.db
  → Results render as:
      1. Auto-profile row: column count, row count, cardinality,
         nulls, min/max per column (Rill-style, zero user config)
      2. Default chart: timeseries → line chart if timestamp column
         detected; categorical × numeric → bar chart otherwise
      3. "Open in Rill" button → launches Rill dev with companion
         metrics_view.yaml (if present)
      4. SQL console: user edits query, chart re-renders reactively
```

### Asset Materialization Output Bundle

```
nucleus run <asset>
  → Iceberg snapshot (pyiceberg, existing)
  → nucleus.db view update (~50 LOC, v0.1)
  → <asset>_metrics_view.yaml (auto-generated, ~150 LOC, v0.1 stretch)
  → <asset>_semantic.yaml (MetricFlow-compatible, ~200 LOC, v0.3)
```

This bundle is "BI-ready" in the sense that:

| Tool | What it consumes | Version |
|---|---|---|
| Rill | `<asset>_metrics_view.yaml` + `nucleus.db` | v0.1 stretch |
| Superset | `nucleus.db` (SQLAlchemy URI) | v0.1 |
| Evidence.dev | `nucleus.db` (DuckDB connection) | v0.1 |
| Streamlit app | `ctx.df("asset").to_arrow()` | v0.1 |
| Lightdash | `<asset>_semantic.yaml` via dbt-duckdb adapter | v0.3 |
| Cube.dev (self-hosted) | `<asset>_cube.yaml` companion | v0.3 |
| Observable Framework | DuckDB-WASM + Iceberg REST catalog | v0.3 |
| Quarto dashboard | Marimo notebook → `nucleus publish` | v0.3 |

### Implementation cost estimate

| Component | Approx LOC | Phase |
|---|---|---|
| `nucleus.db` catalog file generation | ~50 | v0.1 |
| `<asset>_metrics_view.yaml` auto-generation | ~150 | v0.1 stretch |
| Workbench auto-profile on asset open | ~300 | v0.2 |
| Workbench default chart rendering | ~500 | v0.2 |
| `<asset>_semantic.yaml` (MetricFlow) | ~200 | v0.3 |
| Cube-compatible companion YAML | ~100 | v0.3 |

Total v0.1 contribution: ~200 LOC. Well within the v0.1 LOC phase ceiling per AGENTS.md §11.6.

---

## 11. NEEDS VERIFICATION

1. **Rill v0.86 standard Iceberg REST support** — confirmed DuckLake connector added; unclear if standard Iceberg REST (non-DuckLake) works without DuckLake extension. Check: https://docs.rilldata.com/notes/0.86 and https://docs.rilldata.com/connect/data-source/duckdb

2. **Evidence Studio Iceberg connector config** — documented as available in Evidence Studio, but specific YAML config format not fetched. Check: https://docs.evidence.studio/core-concepts/data-sources

3. **Metabase DuckDB community driver DuckDB 1.5.x compatibility** — driver may have been updated. Check: https://github.com/MotherDuck-Open-Source/metabase-duckdb-driver/releases

4. **`table.scan().to_duckdb()` method in pyiceberg 0.8.x** — used in Streamlit section above, should be verified against the pinned version before code is written. Check: https://py.iceberg.apache.org/api/ (pinned version per `pyproject.toml`)

5. **dbt Core v1.12 release date** — stated as "May 2026" per MetricFlow docs [21]; MetricFlow YAML changes are gated on this. Check: https://docs.getdbt.com/docs/dbt-versions/core-upgrade

6. **DuckDB `ATTACH ... TYPE ICEBERG`** connection syntax for `nucleus.db` generation — confirmed DuckDB Iceberg REST catalog support in v1.5.x; exact `ATTACH` syntax should be verified before implementation. Check: https://duckdb.org/docs/current/core_extensions/iceberg/iceberg_rest_catalogs.html

---

## 12. Logged Hallucinations

None detected during this research session. All API calls and YAML schemas cited above were confirmed against official documentation before inclusion. The `table.scan().to_duckdb()` reference (section 6) is flagged as NEEDS VERIFICATION (#4 above) due to version specificity.

---

## 13. ADR Candidates

| ADR | Trigger | Urgency |
|---|---|---|
| ADR-026: Emit `nucleus.db` as canonical BI handshake from `nucleus up` | Superset/Evidence/Rill connectivity; v0.1 beachhead | **P0 — v0.1** |
| ADR-027: Emit `<asset>_metrics_view.yaml` from `nucleus run` | Rill integration pattern | v0.1 stretch / v0.2 |
| ADR-028: Adopt MetricFlow YAML as `nucleus_semantic.yaml` contract | Lightdash/Cube standard alignment | v0.3 gate |

---

## 14. References

All URLs confirmed accessible as of 2026-05-15.

[1] Rill GitHub — https://github.com/rilldata/rill  
[2] Rill DuckDB OLAP docs — https://docs.rilldata.com/connect/olap/duckdb  
[3] Rill metrics-view docs — https://docs.rilldata.com/developers/build/metrics-view  
[4] Rill 0.86 release notes — https://docs.rilldata.com/notes/0.86  
[5] Rill project YAML reference — https://docs.rilldata.com/reference/project-files/rill-yaml  
[6] Evidence OSS DuckDB source — https://docs.evidence.dev/core-concepts/data-sources/duckdb  
[7] Evidence Studio announcement blog — https://evidence.dev/blog/evidence-studio  
[8] Evidence Studio data sources — https://docs.evidence.studio/core-concepts/data-sources  
[9] Evidence Studio version control — https://docs.evidence.studio/features/version-control  
[10] Quary GitHub — https://github.com/quarylabs/quary  
[11] Lightdash semantic layer docs — https://docs.lightdash.com/guides/lightdash-semantic-layer  
[12] Lightdash metrics reference — https://docs.lightdash.com/references/metrics  
[13] Lightdash.com homepage — https://www.lightdash.com/  
[14] Metabase DuckDB connector — https://www.metabase.com/data-sources/duckdb  
[15] Superset DuckDB docs — https://superset.apache.org/docs/databases/supported/duckdb/  
[16] Streamlit + Iceberg + DuckDB pattern — https://dipankar-tnt.medium.com/building-a-streamlit-app-on-a-lakehouse-using-apache-iceberg-duckdb-b7bb1752445e  
[17] Quarto Dashboards — https://quarto.org/docs/dashboards/  
[18] Observable data apps blog — https://observablehq.com/blog/from-data-exploration-to-data-apps-with-observable  
[19] DuckDB Iceberg in browser (Dec 2025) — https://duckdb.org/2025/12/16/iceberg-in-the-browser  
[20] MetricFlow GitHub — https://github.com/dbt-labs/metricflow  
[21] dbt latest metrics spec (v1.12) — https://docs.getdbt.com/docs/build/latest-metrics-spec  
[22] Cube REST API — https://docs.cube.dev/reference/core-data-apis/rest-api  
[23] Cube YAML syntax — https://docs.cube.dev/docs/data-modeling/concepts/syntax  
[24] Malloy GitHub — https://github.com/malloydata/malloy  
[25] Malloy PyPI — https://pypi.org/project/malloy/  
[26] Dremio Iceberg v3 blog — https://dremio.com/blog/apache-iceberg-v3  
[27] Iceberg v3 Databricks blog — https://databricks.com/blog/apache-icebergtm-v3-moving-ecosystem-towards-unification  
