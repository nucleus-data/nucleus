# Observability & Lineage Landscape 2026

> **Last verified**: 2026-05-15 against live docs, public GitHub, and PyPI  
> **Tier per AGENTS.md §1**: OpenLineage = Tier 0 (immortal); Marquez = Tier 2 (swap target); all others = inspiration/watch items  
> **Research scope**: 8 topics for Nucleus v0.1 → v0.5 lineage story  
> **Written by**: Researcher tier (Claude Sonnet 4.6 fallback — Gemini 3.1 Pro unavailable in current Cursor runtime)  
> **Target**: `docs/research/inspiration/observability_lineage_2026.md`  
> **Prior art**: `docs/research/openlineage.md` (AMA wire format), `docs/research/sqlglot.md` (lineage API), `docs/research/observability_backends.md` (VictoriaMetrics + Marquez deployment), `docs/research/soda.md` (license boundary)

---

## Executive Summary — Top 3 Adoption Candidates

### 1. Marquez ilum-cloud fork v0.54.0 — Adopt at v0.3+

The upstream Marquez project stalled (v0.50.0, October 2024). The **ilum-cloud fork shipped a complete Rust backend rewrite in March 2026** (v0.54.0: Axum + SQLx + tokio, 100% API-compatible upstream). The Rust path eliminates Java 17 from the API server; only PostgreSQL 16 remains. The `lineageStatistics` facet added in v0.54.0 — upstream/downstream dependency counts computed at write time — aligns with Nucleus's "how many assets depend on this?" Workbench query. This is the correct v0.3+ lineage viewer target. Pin `ilum/marquez:0.54.0`, not `marquezproject/marquez:latest`.

### 2. OpenLineage Explicit Lineage Facets (`LineageRunFacet`) — Adopt at v0.5

In April 2026 OpenLineage merged three new facets (`LineageRunFacet`, `LineageJobFacet`, `LineageDatasetFacet`) to eliminate false-positive lineage edges from the implicit inputs/outputs cartesian product model. Nucleus's v0.1 `@nucleus.asset` materializations are already clean (N inputs → 1 output, no false edges). The explicit facets matter at v0.5+ when Nucleus orchestrates multi-engine chains. The recommended adoption is `compatibility=both` mode: emit both new explicit facets AND the legacy inputs/outputs for backward-compatible consumers.

### 3. sqlglot `lineage()` + `ColumnLineageDatasetFacet` — Adopt at v0.5

The v0.5 column-level lineage implementation is unblocked: `sqlglot.lineage(column=None, sql=rendered_sql, schema=schema_dict, dialect="duckdb")` returns a `dict[str, Node]`. Each `Node.walk()` populates `ColumnLineageDatasetFacet.fields`. This is the most production-proven path for SQL-asset column lineage. Requires upgrading `sqlglot==26.0.0` → `>=30.0.0` (4 major versions; ADR required). Gate-test `UNION BY NAME` before shipping.

---

## Table of Contents

1. [OpenLineage 2025/2026 Spec Changes](#1-openlineage-20252026-spec-changes)
2. [DataHub vs Marquez vs Atlan vs OpenMetadata Matrix](#2-datahub-vs-marquez-vs-atlan-vs-openmetadata-matrix)
3. [Column-Level Lineage State of Art](#3-column-level-lineage-state-of-art)
4. [Data Observability OSS Landscape](#4-data-observability-oss-landscape)
5. [OpenLineage Propagation Across Engines](#5-openlineage-propagation-across-engines)
6. [Audit Logs vs Lineage Events](#6-audit-logs-vs-lineage-events)
7. [Visualizing Lineage](#7-visualizing-lineage)
8. [Lineage-Aware AI Copilot](#8-lineage-aware-ai-copilot)
9. [Column-Level Lineage Effort Estimate for Nucleus](#9-column-level-lineage-effort-estimate-for-nucleus)
10. [Workbench Lineage View UI Spec Sketch](#10-workbench-lineage-view-ui-spec-sketch)
11. [NEEDS VERIFICATION](#11-needs-verification)
12. [References](#12-references)

---

## 1. OpenLineage 2025/2026 Spec Changes

### 1.1 Versioning Context

OpenLineage uses two parallel version schemes that AI agents routinely conflate:

- **Spec version** (OpenAPI): currently `2-0-2`. The "2-0-2" refers to the OpenAPI document revision — NOT a semver breaking change. There is no separately branded "OpenLineage 2.0" release. `[NEEDS VERIFICATION #1]`
- **Library version**: `openlineage-python==1.47.1` (PyPI, 2026-05-12). Monthly minor cadence; 1.40.0 → 1.47.1 over 6 months.

The core 4-noun model (Run, Job, Dataset, Facet) is stable. New behavior lands as new facet schemas, not spec rewrites. See `docs/research/openlineage.md` §1–§4 for full API surface.

### 1.2 Explicit Lineage Facets — April 2026 (the real news)

**Source**: GitHub issue [#4359](https://github.com/OpenLineage/OpenLineage/issues/4359), commit [f6abf14](https://github.com/OpenLineage/OpenLineage/commit/f6abf1405b00da8ef20950e65a054dd0a91a590b), adoption guideline commit [195d1de](https://github.com/OpenLineage/OpenLineage/commit/195d1de48858cf60d116050a8a9039f5c213a0b2).

**Problem**: The current OL model uses *implicit lineage* — if a Run has `inputs=[A, B]` and `outputs=[C, D]`, consumers infer all 4 combinations (A→C, A→D, B→C, B→D). For bulk ETL-like jobs processing N independent tables, **up to 90% of inferred edges are false positives**.

**Solution**: Three new facets explicitly declare data flow:

| Facet | Attached to | Meaning |
|---|---|---|
| `LineageRunFacet` | `run.facets.lineage` | Runtime-observed flow — what *actually* transformed what |
| `LineageJobFacet` | `job.facets.lineage` | Design-time declared flow — what the job *intends* to do |
| `LineageDatasetFacet` | `dataset.facets.lineage` | Structural derivation — views, synonyms, reports |

**Adoption strategy**: `compatibility = both` — emit BOTH new explicit facets AND legacy inputs/outputs simultaneously. New consumers (Marquez v0.54+, DataHub v1.5+) read accurate explicit facets; old consumers read the cartesian product fallback.

**Nucleus impact for v0.1**: Low. `@nucleus.asset` materializations are already clean (1 job, N input assets, 1 output Iceberg snapshot, zero false-positive edges). The explicit facets matter for v0.5+ when Nucleus orchestrates cross-engine multi-output asset chains.

**Action for v0.5**: Emit `LineageRunFacet` alongside the existing inputs/outputs in the AMA. `[NEEDS VERIFICATION #4]` for exact Python class path in `openlineage-python>=1.47.1`.

### 1.3 MCP-to-Lineage RFC (April 2026)

OpenLineage RFC [#4484](https://github.com/openlineage/openlineage/issues/4484): *"Lineage for runtime actor-initiated data interactions — MCP calls, API requests, and agentic read/write operations."*

Context: the current OL model handles job-mediated lineage (pipeline reads A, writes B). It does not handle an LLM agent calling an MCP tool to read column X, then calling another MCP tool to write column Y. The RFC proposes extending the spec for those interactions.

**Nucleus relevance**: v0.5+ AI Copilot uses `ctx.read()` and `ctx.sql()` via MCP. If Nucleus emits OL events for Copilot data access, those interactions become auditable alongside pipeline lineage. A `nucleus_agent_identity` custom run facet carrying OIDC `sub` would implement this. Watch RFC #4484 before implementing any MCP lineage tracking; it is still open as of 2026-05-15.

**AWS reference implementation**: `aws-samples/sample-agentic-data-lineage` (October 2025) ships a Marquez MCP server (`marquez-mcp/`) demonstrating agent lineage collection with Glue + dbt + Redshift.

### 1.4 `duck_lineage` DuckDB Community Extension (v0.2.0, March 2026)

Source: https://duckdb.org/community_extensions/extensions/duck_lineage.html

A DuckDB community extension that hooks into DuckDB's query execution to capture lineage for every query:
- Emits START, COMPLETE, FAIL OL events
- Column-level lineage tracking per query
- DuckLake catalog support
- Async event delivery (non-blocking)
- Configure via `SET` statements (OL URL, namespace, API key)

Standard DuckDB (`duckdb==1.1.3` Nucleus pin) does **not** emit OL events natively. The extension is opt-in. For Nucleus v0.1, the AMA-side emission is correct and sufficient. `duck_lineage` can be an opt-in feature at v0.3+ for users who want per-query DuckDB lineage granularity beyond per-asset.

`[NEEDS VERIFICATION #7]` whether `duck_lineage` actually produces `ColumnLineageDatasetFacet` or just table-level facets.

---

## 2. DataHub vs Marquez vs Atlan vs OpenMetadata Matrix

| Dimension | DataHub | Marquez (ilum fork) | Atlan | OpenMetadata |
|---|---|---|---|---|
| **GitHub stars** | ~11,900 | ~2,100 upstream | N/A (SaaS) | ~10,000 |
| **License** | Apache-2.0 | Apache-2.0 | **Proprietary SaaS** | Apache-2.0 |
| **Open source?** | Yes | Yes | **No** | Yes |
| **Latest release** | v1.5.0 (2026-03-24) | upstream 0.50.0 (stale 18 mo); **ilum 0.54.0 (2026-03-08)** | SaaS | active commits April 2026 |
| **JVM required?** | Yes — Java 17 | upstream: Java 17; **ilum v0.54 Rust API** | SaaS | Yes — Java 21 |
| **Other infra deps** | Kafka + Elasticsearch + MySQL | PostgreSQL 16 only | SaaS | Elasticsearch + MySQL/PG |
| **Docker containers** | 6+ services | 2 (API + PG) | SaaS | 4+ services |
| **OL consumer** | Yes (native) | Yes (reference impl) | Yes (OL connector) | Yes (OL connector) |
| **Column-level lineage** | Yes | Via OL facets | Yes | Yes (depth: 5 layers) |
| **REST API** | GraphQL + REST | REST `/api/v1/lineage` | REST | REST + GraphQL |
| **Scope** | Full catalog + governance | Lineage-only | Full catalog + AI | Full catalog + quality |
| **Min RAM estimate** | ~8 GB (Kafka + ES + JVM) | ~1 GB (Postgres + Rust) | N/A | ~4 GB (ES + JVM) |
| **Nucleus fit (v0.3)** | Too heavy | **Best fit** | Not OSS | Too heavy |
| **Nucleus fit (v0.5+)** | Power users with infra | Default self-hosted viewer | Enterprise watch | Teams with ES |
| **Pricing** | Free OSS / Acryl Cloud paid | Free OSS | ~$50k/yr median enterprise | Free OSS / managed paid |
| **Activity signal** | Very active (2026 releases) | ilum active; upstream stale | SaaS (active) | Active |

**Key finding — Atlan is NOT open source.** Any document grouping Atlan alongside DataHub and Marquez as "OSS data catalog options" is wrong. Atlan is a proprietary SaaS. The median enterprise contract runs $49,764/year (Vendr data, 2026). AWS Marketplace entry starts at $100,000/12 months. Not viable for Nucleus's local-first audience. Sources: [Atlan pricing](https://www.modern-datatools.com/tools/atlan/pricing), [Vendr marketplace](https://www.vendr.com/marketplace/atlan).

**Key finding — ilum-cloud Marquez v0.54.0 ships Rust backend.** The API server is rewritten in Rust (Axum + SQLx + tokio). Java backend is preserved as an opt-in fallback via `./docker/up.sh --java`. The Rust path is the default. ~38,000 LOC new Rust across 5 workspace crates. 100% API-compatible with upstream Marquez. This resolves the JVM-sidecar issue from `docs/research/observability_backends.md` §2.3.

**Recommended v0.3 ADR wording**: "Default lineage viewer for `nucleus enable marquez` is `ilum/marquez:0.54.0`. The Java fallback option (`--java`) is available but not supported in Nucleus documentation. The Rust path is the tested path." Document in `/docs/swap/marquez.md`.

**DataHub vs OpenMetadata comparison**: Both are full data catalogs (discovery + governance + quality + lineage). Both require Elasticsearch + JVM. Both are significantly heavier than Marquez for Nucleus's target persona (5-20 engineer startup). Neither is recommended as a Nucleus default at any version through v1.0 — recommend to users who already have DataHub/OpenMetadata deployed. OL `HttpTransport` connects Nucleus to either without any Nucleus code change.

---

## 3. Column-Level Lineage State of Art

### 3.1 sqlglot `lineage()` — The v0.5 Path for Nucleus

Detailed API coverage in `docs/research/sqlglot.md` §3–§4.1. Summary for this context:

```python
# Docs: https://sqlglot.com/sqlglot/lineage.html
from sqlglot.lineage import lineage

nodes: dict[str, Node] = lineage(
    column=None,        # None = return all output columns
    sql=rendered_sql,   # Jinja-resolved SQL from ctx.sql()
    schema={            # dict[qualified_table, dict[col, dtype]]
        "nucleus.raw.orders": {"amount": "bigint", "qty": "int"}
    },
    dialect="duckdb",   # always specify; default is permissive superset
)
```

Each `Node` maps to one output column. `Node.walk()` yields the DAG of input columns. Transformation types are `DIRECT` (column is selected or renamed) or `INDIRECT` (column appears in filter/group/sort but is not a direct input to the output column).

**Current pin risk**: `sqlglot==26.0.0` is 4 major versions behind the current `30.7.0` (2026-05-04). The `lineage()` API surface is stable, but a major-version upgrade ADR is required before v0.5 work starts.

**Known gap**: `UNION BY NAME` / `UNION ALL BY NAME` fail with `list index out of range` — a fix was merged in 2026. `[NEEDS VERIFICATION #5]` which specific version contains the fix.

### 3.2 `ColumnLineageDatasetFacet` — Canonical OL Representation

Verified schema v1-2-0 (from `docs/research/openlineage.md` §5.2):

```json
{ "columnLineage": {
    "fields": { "<output_col>": { "inputFields": [
      { "namespace": "...", "name": "...", "field": "<input_col>",
        "transformations": [
          { "type": "DIRECT|INDIRECT", "subtype": "...", "masking": false }
        ] }
    ] } }
} }
```

Emit the `transformations` array — NOT the deprecated `transformationDescription` / `transformationType` per-field strings from the v1-1-0 schema.

### 3.3 dbt Column-Level Lineage — Enterprise Gate

dbt's CLL is **Enterprise-only** as of 2025. Source: https://docs.getdbt.com/docs/explore/column-level-lineage.md. Powered internally by sqlglot. Key limitations per official docs:
- Reflects only `SELECT` statements — joins and filters not captured
- JSON unpacking, lateral joins may produce incomplete lineage
- Cross-project CLL requires `access: public` + Production deployment environment

**Pattern to steal from dbt**: the **"column evolution lens"** — a visual indicator distinguishing columns *transformed* vs *passed through* (renamed). Surfaceable from sqlglot's `transformation.type = DIRECT/INDIRECT` plus the expression type. Low-effort addition for Workbench v0.5.

`[NEEDS VERIFICATION #6]` whether dbt's internal CLL engine is confirmed as sqlglot.

### 3.4 SQLMesh Column-Level Lineage — OSS, No Enterprise Gate

SQLMesh provides column-level lineage in its OSS tier. Built on sqlglot internally. Tracks lineage across model boundaries, not just within a single SQL file. Relevant because SQLMesh is an optional adapter for Nucleus v0.3+ (per architecture `docs/decisions/ADR-014`). If Nucleus adds SQLMesh support, column lineage comes nearly free.

### 3.5 What "Good Column-Level Lineage" Looks Like in Production

Four canonical use cases (from DataHub, OpenMetadata, SQLMesh): (a) **Impact analysis** — filter `ColumnLineageDatasetFacet` for all OutputDatasets where `orders.amount` appears as `inputField`; (b) **Sensitivity propagation** — PII column → all `DIRECT`-derived columns inherit the tag; (c) **Freshness + lineage join** — join key is OL `Dataset.name` (`namespace + name`), linking catalog to event log; (d) **Transformation audit** — pair column lineage with OTEL spans carrying OIDC `user_id` Baggage.

---

## 4. Data Observability OSS Landscape

### 4.1 Elementary — Best OSS Option (dbt-native)

**Status**: Active. v0.23.1, April 2026. Apache-2.0. ~4,000 GitHub stars. Source: https://github.com/elementary-data/elementary

**What it does**:
- Anomaly detection: row count / freshness / null rates / column distributions / schema changes
- Materializes results into `elementary_test_results` and `elementary_model_runs` dbt models
- CLI generates HTML reports; integrates with Slack/PagerDuty
- Free OSS tier: full anomaly detection. Elementary Cloud adds AI alerting (proprietary)

**Nucleus fit**: Elementary is **dbt-centric**. Nucleus v0.1 does NOT use dbt (native `ctx.sql` + Jinja resolver). For v0.3+ teams that adopt the optional dbt-duckdb adapter, Elementary is the recommended observability companion — recommend it to users, do not build against it. 8-question gate fails Q2 (doesn't serve 30-min beachhead), Q8 (v0.3+ at earliest). **Defer.**

### 4.2 re_data — Effectively Stagnant

Last release `0.11.0`: December 2023. Last commit: April 2024. Not archived, but development has stopped. ~1,600 stars. Use Elementary instead. Source: https://github.com/re-data/re-data

### 4.3 Soda Core — Off-Table

Critical finding from `docs/research/soda.md` §1.2: v3.x = Apache-2.0 (last release: `3.5.6`, September 2025); v4.x = Elastic License 2.0 (NOT OSI-approved, anti-cloud-hosting clause). v3.x DuckDB connector requires `duckdb<1.1.0` — incompatible with Nucleus's `duckdb==1.1.3` pin. v4 is out of scope due to ELv2. **Soda is off-table for Nucleus through v0.3.**

Native `@nucleus.check` (Python decorator) + `@nucleus.contract` (schema) covers the core use case at zero additional dependency cost.

### 4.4 Bauplan "Git-for-Data" — The Right Pattern, Already Covered

Bauplan's git-for-data branching model means every transformation is a *commit with a parent* — enabling time-travel and diff-style observability. This is NOT anomaly detection; it is **snapshot provenance**. For Nucleus: Iceberg's snapshot model already delivers this natively. `@nucleus.snapshot` + the OL `version` dataset facet IS the Nucleus-equivalent at zero additional cost.

**Pattern to steal**: "What changed between snapshot X and snapshot Y?" → `pyiceberg` snapshot diff API + a Workbench two-pane diff view (v0.5+). More user-visible than building an Elementary-style anomaly detector in v0.1.

---

## 5. OpenLineage Propagation Across Engines

### 5.1 Engine Emission Gap Analysis

| Engine | OL emission | Column-level? | Free OSS? | Nucleus v0.1 strategy |
|---|---|---|---|---|
| DuckDB (standard) | No native | No | Yes | AMA emits on behalf |
| DuckDB (`duck_lineage` ext) | Yes (v0.2.0, March 2026) | `[NV #7]` | Yes | Opt-in v0.3+ |
| Polars (OSS free tier) | **No** | No | Yes | AMA emits on behalf |
| Polars (On-Prem licensed) | Yes (`with_lineage()`) | Partial | **No** | Not applicable |
| Spark | Yes (native `openlineage-spark`) | Yes | Yes (JVM artifact) | Parent run facet at dispatch |
| Trino | Yes (`openlineage-trino`) | Yes | Yes | Parent run facet at dispatch |
| Flink | Yes | Partial | Yes | v0.5+ streaming; out of scope v0.1 |

**Critical finding — Polars OSS does NOT emit OL**: The official Polars docs at https://docs.pola.rs/polars-on-premises/integrations/openlineage/ confirm OL support is **Polars On-Prem only** (commercial product). Free `polars` package emits nothing. Nucleus AMA must wrap all Polars operations and emit OL events at the Nucleus layer. Any AI agent suggesting "just enable Polars OL integration" for the free tier is hallucinating.

### 5.2 Cross-Engine Lineage at Dispatch Boundary (v0.5+)

When Nucleus routes an asset to an external engine via `compute="spark"` dispatch, link the Spark child run back to the Nucleus parent via `ParentRunFacet` (standard OL spec, class `openlineage.client.facet_v2.parent_run.ParentRunFacet`). Inject the Nucleus `runId` into the Spark OL configuration via `OPENLINEAGE_CONFIG`. Marquez renders the full cross-engine chain automatically when parent/child `runId` are linked.

---

## 6. Audit Logs vs Lineage Events

### 6.1 The Two-Layer Model (Databricks / Snowflake Pattern)

Both Databricks Unity Catalog and Snowflake separate these concerns explicitly:

| Layer | Answers | Event type | Databricks equivalent | Snowflake equivalent |
|---|---|---|---|---|
| **Audit log** | *Who touched what, when, from where* | Identity + access events | `system.access.audit` (1-year rolling) | `ACCESS_HISTORY` (Enterprise+, 365 days) |
| **Lineage** | *How data flows and transforms* | Transformation dependency events | `system.access.{table_lineage, column_lineage}` | `DATA_LINEAGE` (Snowsight UI) |

Sources: https://docs.databricks.com/aws/en/admin/system-tables/lineage, https://docs.snowflake.com/en/user-guide/access-history.md

Snowflake even provides a bridge: `Snowflake-Labs/OpenLineage-AccessHistory-Setup` extracts table lineage from `ACCESS_HISTORY` in OL format.

### 6.2 Should Nucleus Differentiate?

**Recommendation**: Yes conceptually, but implement both via the same underlying OL event. The differentiation is a *consumer view concern*, not a *producer mechanism change*.

An OL `RunEvent` already encodes both layers:
- **Lineage layer**: `inputs[]`, `outputs[]`, `ColumnLineageDatasetFacet` — what transformed what
- **Audit layer**: `run.facets.nominalTime` (when), `job.facets.sourceCodeLocation` (who authored it), `run.facets.parent` (which orchestration triggered it)

The missing piece: Nucleus has no runtime identity in v0.1 (single-user laptop; Constraint #6 — no custom auth). In v0.3+ Cloud/Team mode with OIDC, inject a `nucleus_identity` custom run facet (per OL naming convention: `{prefix}_{name}` key in `run.facets`) carrying OIDC `sub`, `email`, and `clientIp`. Schema URL must be an immutable pointer (e.g., `https://nucleus.dev/spec/NucleusIdentityRunFacet/v1-0-0.json`).

**v0.1 action**: No change needed.  
**v0.3+ action**: Implement `NucleusIdentityRunFacet`. Gate on OIDC token presence. Add to AMA `emit_start()` call.

---

## 7. Visualizing Lineage

### 7.1 Tool-by-Tool Comparison

| Tool | Visualization library | Node/edge model | Interactive? |
|---|---|---|---|
| Marquez Web UI | **visx** (Airbnb's React kit) | DAG: datasets as rectangles, jobs as circles | Click-to-expand depth |
| ilum-cloud Marquez fork | visx + enhanced (TableLineageDatasetNode, TableLineageJobNode) | Same + richer node metadata | Yes; improved styling |
| DataHub | Custom React + Cytoscape.js | Full catalog graph | Yes; filter by entity type |
| OpenMetadata | React + custom SVG | Catalog DAG | Yes; column-level expand |
| dbt Explorer | React + D3 | Model-centric DAG | Yes; cross-project |

Sources: Marquez UI commit [c756cb2](https://github.com/ilum-cloud/marquez/commit/c756cb2da5a84b8bfc7bb5810d1b9ea348cf4f20) — uses visx components. Marquez does NOT use ReactFlow.

**ReactFlow** ([reactflow.dev](https://reactflow.dev)) is the best choice for a *custom* lineage UI in Workbench. It provides: composable React DAG canvas, built-in pan/zoom/minimap, custom node/edge components, elkjs auto-layout plugin for complex graphs. Used by Retool, Prefect, and several commercial workflow builders. License: MIT for OSS use.

Alternative: **visx** (Airbnb) — lower-level, more flexible, but more implementation work. Marquez uses it; we could embed the Marquez web client as an iframe in v0.3+.

### 7.2 Workbench Lineage View UI Spec Sketch

See Section 10 for the full wireframe.

---

## 8. Lineage-Aware AI Copilot

### 8.1 dbt MCP Server — Reference Pattern

Sources: https://docs.getdbt.com/docs/dbt-cloud-apis/mcp, https://www.getdbt.com/blog/bringing-structured-context-to-ai-with-dbt

dbt's MCP server (launched 2025) exposes: model graph + column-level lineage, business metrics and dimension logic, test results and freshness, ownership + documentation — all to LLM tools via the Model Context Protocol.

**Key insight from dbt Labs**: structured lineage context prevents LLM hallucinations by grounding AI in actual data dependencies. Without lineage, the LLM guesses table relationships. With lineage, it navigates the asset graph authoritatively. The "structured context layer" they describe is exactly what Nucleus's OL event log + Iceberg catalog provides.

### 8.2 Nucleus Copilot MCP Tools (v0.5+)

Per arch §13 + §18.4, the MCP server should expose five lineage-aware tools:

| Tool | Source | LLM use case |
|---|---|---|
| `get_asset_lineage(name, depth=2)` | Marquez REST (v0.3+) or NDJSON scan | "What feeds this asset?" |
| `get_column_lineage(name, column)` | Most recent COMPLETE RunEvent | "Where does this column come from?" |
| `get_asset_schema(name)` | pyiceberg catalog | "What columns does this asset have?" |
| `get_recent_runs(name, n=5)` | NDJSON scan grouped by job.name | "Has this failed recently?" |
| `get_check_results(name)` | `@nucleus.check` outcomes | "Is this data valid?" |

**Example Copilot flow** — "Why did `mart.revenue` change yesterday?": `get_recent_runs` → 3pm FAIL, 2pm COMPLETE; `get_asset_lineage` → `raw.orders` is an input; `get_recent_runs("raw.orders")` → schema change at 1:45pm in `errorMessage` facet. Copilot synthesizes the chain without any custom logic.

**Context size**: embed only depth=2 neighborhood of the queried asset. Serialize as `{asset, upstream: [...], downstream: [...], columns: {...}}`. Target **<2 KB per asset** for LLM injection.

**RFC #4484 watch**: If the Copilot itself calls `ctx.read()` via MCP, those reads should emit OL `DatasetEvent` (access, not transformation). Depends on RFC #4484 resolution; do not implement MCP lineage tracking before the RFC merges.

---

## 9. Column-Level Lineage Effort Estimate for Nucleus

### 9.1 Scope — v0.5 SQL-Asset Only (~300 LOC proprietary)

| File | LOC | Ceiling |
|---|---|---|
| `src/nucleus/intelligence/sql_lineage_adapter.py` | ~250 | 300 |
| `tests/intelligence/test_sql_lineage.py` | ~200 | 250 |
| AMA hook delta (attach `columnLineage` facet to COMPLETE event) | ~30 | 40 |

**Dependency change required**: `sqlglot==26.0.0` → `sqlglot>=30.0.0` (4 major versions). Upgrade ADR required per Constraint #11. Read sqlglot CHANGELOG for breaking changes between 26.x and 30.x before writing the ADR.

### 9.2 OL Facet Integration Sketch

Pattern for `intelligence/sql_lineage_adapter.py`:

```python
# Docs: https://sqlglot.com/sqlglot/lineage.html + https://openlineage.io/docs/spec/facets/
from sqlglot.lineage import lineage
from openlineage.client.facet_v2 import column_lineage_dataset

nodes = lineage(column=None, sql=rendered_sql, schema=schema, dialect="duckdb")
fields = {}
for col_name, root_node in nodes.items():
    input_fields = [
        column_lineage_dataset.InputField(
            namespace=_ns(node), name=_fqn(node), field=node.name,
            transformations=[column_lineage_dataset.Transformation(
                type="DIRECT", subtype=node.expression.key.upper(), masking=False,
            )],
        )
        for node in root_node.walk() if node.source and not node.downstream
    ]
    if input_fields:
        fields[col_name] = column_lineage_dataset.Fields(inputFields=input_fields)
# Wrap any Exception → NucleusLineageError; log at WARN; return None for graceful fallback
```

`[NEEDS VERIFICATION #3]` — confirm `column_lineage_dataset.Transformation` dataclass shape in `openlineage-python==1.47.1` at `openlineage/client/facet_v2/column_lineage_dataset.py`.

### 9.3 Canonical Test Cases (5 Required for v0.5 Gate)

| # | SQL pattern | Expected result |
|---|---|---|
| 1 | `SELECT amount AS revenue FROM orders` | `revenue` ← `orders.amount`, DIRECT/IDENTITY |
| 2 | `SELECT price * qty AS total FROM orders` | `total` ← `orders.price` + `orders.qty`, DIRECT |
| 3 | `SELECT CASE WHEN status='active' THEN 1 ELSE 0 END AS is_active FROM orders` | `is_active` ← `orders.status`, DIRECT |
| 4 | `SELECT o.id, c.name FROM orders o JOIN customers c ON o.cid=c.id` | `id` ← `orders.id`; `name` ← `customers.name`, DIRECT each |
| 5 | `SELECT id, SUM(amount) OVER (PARTITION BY user_id) AS running FROM orders` | `running` ← `orders.amount` (DIRECT); `user_id` is INDIRECT |
| 6 (gate-test) | `SELECT * FROM a UNION BY NAME SELECT * FROM b` | Must not crash — graceful fallback to asset-level |

---

## 10. Workbench Lineage View UI Spec Sketch

**Tech stack**: React 19 + ReactFlow 12 (MIT). State: Zustand. API client: `fetch`. Page route: `/lineage` in Workbench (v0.2+). Deep link: `/lineage?asset=mart.orders_daily`.

**v0.2 data source**: Parse `.nucleus/lineage/*.ndjson` at page load. Group events by `job.name`. Build adjacency: for each COMPLETE RunEvent, `inputs[*].name → job.name → outputs[*].name`. Merge by unique `(namespace, name)`.

**v0.3 data source**: Replace NDJSON scan with Marquez `GET /api/v1/lineage?nodeId=dataset:{namespace}:{name}&depth=3`. Fallback to NDJSON if Marquez not configured.

**v0.5 upgrade**: Toggle "Column-level" mode adds `ColumnLineageDatasetFacet` edges as thin annotated lines.

```
┌────────────────────────────────────────────────────────────────────┐
│  LINEAGE  [○ Asset graph]  [○ Column-level ▸v0.5]   [Depth: 3 ▾]  │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐    ┌───────────────┐    ┌─────────────────────────┐ │
│  │ Postgres │───▶│ raw.orders    │───▶│ mart.orders_daily       │ │
│  │ source   │    │  [Iceberg]    │    │  [Iceberg]              │ │
│  └──────────┘    └───────────────┘    └─────────────────────────┘ │
│                       │                           │               │
│                 last run: 2m ago           last run: 5m ago       │
│                 12.4M rows · ✓              8.2k rows · ✓         │
│                                                                    │
│  ── Click any node to expand detail panel ──────────────────────  │
│                                                                    │
│  [v0.5 column-level mode adds thin annotated edge lines]          │
│  mart.orders_daily.revenue  ←──────── raw.orders.amount           │
│                              (DIRECT / multiply)                  │
└────────────────────────────────────────────────────────────────────┘

Right panel (node selected):
┌────────────────────────────────────────────┐
│  raw.orders                                │
│  Iceberg · nucleus.raw.orders              │
│  12.4M rows · 4 cols · 2.1 MB             │
│  Last snapshot: 2026-05-15 10:44 UTC       │
│  ─────────────────────────────────────    │
│  Upstream: [postgres.public.orders]        │
│  Downstream: [mart.orders_daily]           │
│  ─────────────────────────────────────    │
│  Recent runs:                              │
│    ✓ 10:44 UTC — 2.1s — 12,432 rows       │
│    ✓ 09:44 UTC — 2.0s — 12,195 rows       │
│    ✗ 08:44 UTC — FAIL — schema drift       │
│  ─────────────────────────────────────    │
│  [View raw NDJSON]  [Run now]  [Inspect]   │
└────────────────────────────────────────────┘
```

**Accessibility**: WCAG 2.1 AA. Node labels readable at 14px. Keyboard navigation for node selection. `aria-label` on each node. High-contrast mode via Tailwind dark mode classes.

---

## 11. NEEDS VERIFICATION

| # | Claim | URL to verify |
|---|---|---|
| 1 | "OpenLineage 2.0" as a named release — confirm whether spec version `2-0-2` is the formal "2.0" milestone or just an OpenAPI document revision number | https://openlineage.io/apidocs/openapi/ + https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md |
| 2 | ilum-cloud Marquez v0.54.0 Rust backend — confirm the default Docker image has zero JVM (not just "optional Java fallback") | https://github.com/ilum-cloud/marquez/blob/0.54.0/docker/Dockerfile-api — check base image |
| 3 | `column_lineage_dataset.Transformation` Python dataclass shape in `openlineage-python==1.47.1` — verify it has `type`, `subtype`, `masking` fields as described | https://github.com/OpenLineage/OpenLineage/tree/main/client/python/src/openlineage/client/facet_v2/ |
| 4 | `LineageRunFacet` Python class path in `openlineage-python>=1.47.1` — confirm it was included in the April 2026 facet merge and the exact import path | Check `openlineage/client/facet_v2/lineage_run.py` (hypothetical path) in latest release |
| 5 | sqlglot `UNION BY NAME` lineage fix — confirm which version (>= 30.x?) contains the fix from issue #7332 | https://github.com/tobymao/sqlglot/issues/7332 + https://github.com/tobymao/sqlglot/tags |
| 6 | dbt CLL powered internally by sqlglot — find official confirmation or look for sqlglot as a dependency in `dbt-core` `pyproject.toml` | https://github.com/dbt-labs/dbt-core/blob/main/core/pyproject.toml |
| 7 | `duck_lineage` extension column-level lineage — confirm it produces `ColumnLineageDatasetFacet` (not just table-level `SchemaDatasetFacet`) | https://duckdb.org/community_extensions/extensions/duck_lineage.html — check "Column-level lineage" docs section |
| 8 | upstream `MarquezProject/marquez` last release — confirm latest tagged release is `0.50.0` (October 2024) and there are no newer official releases (only un-released tags `0.51.0`/`0.51.1`) | https://github.com/MarquezProject/marquez/releases/latest |

---

## 12. References

**OpenLineage**
1. Spec + facets: https://openlineage.io/docs/spec/object-model + https://openlineage.io/docs/spec/facets/
2. Python client: https://openlineage.io/docs/client/python
3. Explicit Lineage Facets proposal + commit: https://github.com/OpenLineage/OpenLineage/issues/4359 + https://github.com/OpenLineage/OpenLineage/commit/f6abf1405b00da8ef20950e65a054dd0a91a590b
4. MCP-to-lineage RFC: https://github.com/openlineage/openlineage/issues/4484
5. ColumnLineageDatasetFacet schema: https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/spec/facets/ColumnLineageDatasetFacet.json
6. Polars On-Prem OL: https://docs.pola.rs/polars-on-premises/integrations/openlineage/
7. `duck_lineage` extension: https://duckdb.org/community_extensions/extensions/duck_lineage.html

**Lineage backends**
8. Marquez v0.50.0 (upstream stale): https://github.com/MarquezProject/marquez/releases/tag/0.50.0
9. ilum-cloud Marquez v0.54.0 (Rust): https://github.com/ilum-cloud/marquez/releases/tag/0.54.0
10. Marquez lineage API: https://marquezproject.ai/docs/api/get-lineage
11. DataHub releases + GitHub: https://docs.datahub.com/docs/releases + https://github.com/datahub-project/datahub
12. OpenMetadata GitHub: https://github.com/open-metadata/OpenMetadata
13. Atlan pricing: https://www.modern-datatools.com/tools/atlan/pricing

**Column-level lineage**
14. sqlglot lineage API: https://sqlglot.com/sqlglot/lineage.html
15. sqlglot UNION BY NAME issue: https://github.com/tobymao/sqlglot/issues/7332
16. dbt column-level lineage: https://docs.getdbt.com/docs/explore/column-level-lineage.md

**Observability OSS**
17. Elementary docs + GitHub: https://docs.elementary-data.com/data-tests/introduction + https://github.com/elementary-data/elementary
18. re_data (stagnant): https://github.com/re-data/re-data
19. Soda Core license research: `docs/research/soda.md` §1.2

**Audit logs + platform references**
20. Databricks lineage system tables: https://docs.databricks.com/aws/en/admin/system-tables/lineage
21. Snowflake access history: https://docs.snowflake.com/en/user-guide/access-history.md
22. Snowflake OpenLineage bridge: https://github.com/Snowflake-Labs/OpenLineage-AccessHistory-Setup

**AI Copilot + lineage**
23. dbt MCP server: https://docs.getdbt.com/docs/dbt-cloud-apis/mcp
24. dbt structured context blog: https://www.getdbt.com/blog/bringing-structured-context-to-ai-with-dbt
25. AWS agentic lineage sample: https://github.com/aws-samples/sample-agentic-data-lineage

**Prior Nucleus research (do not repeat)**
26. `docs/research/openlineage.md`, `docs/research/sqlglot.md`, `docs/research/observability_backends.md`, `docs/research/soda.md`

---

*AI training cutoff may be stale; this document reflects official docs as verified on 2026-05-15. Re-verify §2 matrix figures (stars, release dates) and NEEDS VERIFICATION items before opening the v0.3 Marquez ADR or the v0.5 column-lineage ADR.*
