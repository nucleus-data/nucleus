# Nucleus — Architecture v4.0 (DEPRECATED)

> ## ⚠️ DEPRECATED — Use v4.1 Instead
>
> **This document has been superseded by [`nucleus_architecture_v4.1.md`](./nucleus_architecture_v4.1.md).**
>
> After review by 3 independent senior engineers, **13 amendments** were applied. See the Changelog section in v4.1 for details. Key changes:
>
> - **Dropped "Iceberg Commit Service"** — was over-architecture; catalog handles atomic commits
> - **Composability = clean interfaces + smoke tests** (not maintained second implementations) — avoids "Composability Tax"
> - **v0.1 scope cut ~40%** and split into "Hello World" (Mo 0-4, CLI only) + "Developer Experience" (Mo 4-8, adds Workbench)
> - **AI Copilot staged realistically** (v0.1 has NO Copilot; v0.2 adds simple chat; v0.5 adds lineage-aware features)
> - **Filesystem catalog** in v0.1 (Lakekeeper deferred to v0.3)
> - **Native `ctx.sql` + Jinja** in v0.1 (dbt-duckdb deferred to optional v0.3)
> - **Asset-level lineage** in v0.1 (column-level deferred to v0.5+)
> - **Error Translation Layer** mandatory release blocker
> - **Beachhead persona** explicitly: startup data team 5-20 engineers
> - **No custom auth ever** — always delegate to OIDC
> - **`ctx.copy_from` ingestion helper** in v0.1 (one-liner `nucleus ingest` mandatory)
> - **Dagster replaceability** proven by v1.0 (mini-scheduler runs same project unchanged)
> - **AI APIs flex faster than core data APIs** in versioning policy
>
> This file is retained for historical reference only. Do **not** use as source of truth.

---

# Nucleus — Architecture v4.0 (Historical)

**Single Source of Truth · Locked Scope · Supersedes v3.0**

> A modern, composable data engineering platform — built on open Apache foundations, AI-assisted by design, solving persistent pains. Grows with your team. Graduates cleanly when you outgrow it.

---

## Document Status

| Field | Value |
|---|---|
| Version | 4.0 |
| Status | **Locked** — implementation can begin once PoC validations pass |
| Supersedes | `nucleus_architecture_v3.md`, `final_architecture.md`, `architecture_design_conversation.md` |
| Audience | Senior data platform engineers, solution architects, founding team |
| Reading time | ~45 minutes |
| Companions | `nucleus_ctx_sdk_spec.md`, `nucleus_asset_model_spec.md`, `nucleus_project_anatomy.md`, `nucleus_cli_spec.md`, `nucleus_poc_plan.md`, `nucleus_implementation_readiness.md`, `nucleus_red_team_review.md` |

Any future architectural change MUST explicitly amend a section in this document. No drift.

---

## TL;DR

Nucleus is a **modern data engineering platform** that fixes long-standing pain points of building and operating data products. It is composed of five layers:

1. **Physics** — immortal Apache standards (Arrow, Iceberg, Parquet, Lance, S3)
2. **Engines** — composable, swappable best-in-class OSS (DuckDB, Polars, Daft, dlt, dbt)
3. **Coordination** — wrapped orchestration substrate (Dagster, hidden behind `ctx`)
4. **Intelligence** — AI-assisted authoring, debugging, operations (the differentiating layer)
5. **Experience** — `ctx` SDK + CLI + Workbench + Marimo (the unified UX)

The platform is **local-first** (boot in <10s on a laptop), **composable by constitution** (every dependency has a documented swap path), and **friendly to giants** (Iceberg portability lets users graduate to Databricks/Snowflake without migration).

We do **not** build a database, a SQL engine, a DataFrame engine, an orchestrator, a Spark replacement, or a Databricks competitor. We integrate the best open-source pieces into one coherent product, and we add the AI-assisted experience the modern data stack is missing.

License: **Apache 2.0**. Distribution: OSS core + managed cloud + premium copilot + enterprise tier.

---

## Table of Contents

1. [Positioning](#1-positioning)
2. [Five Pillars](#2-five-pillars)
3. [Architecture Overview](#3-architecture-overview)
4. [Layer 5: Physics](#4-layer-5-physics)
5. [Layer 4: Engines](#5-layer-4-engines)
6. [Layer 3: Coordination](#6-layer-3-coordination)
7. [Layer 2: Intelligence](#7-layer-2-intelligence)
8. [Layer 1: Experience](#8-layer-1-experience)
9. [Composability by Constitution](#9-composability-by-constitution)
10. [Yield-to-Giants Strategy](#10-yield-to-giants-strategy)
11. [Local-First Guarantee](#11-local-first-guarantee)
12. [The Asset Primitive](#12-the-asset-primitive)
13. [The `ctx` SDK Contract](#13-the-ctx-sdk-contract)
14. [Operational Concerns](#14-operational-concerns)
15. [Security & Governance](#15-security--governance)
16. [Performance Targets](#16-performance-targets)
17. [Monetization Model](#17-monetization-model)
18. [Roadmap](#18-roadmap)
19. [Risk Register](#19-risk-register)
20. [Non-Goals](#20-non-goals)
21. [Decision Log](#21-decision-log)
22. [References](#22-references)

---

## 1. Positioning

### 1.1 The Persistent Pains of Data Engineering

These 15 pains have existed for 10-20 years. Big players have **no incentive** to solve them (complexity is their revenue). This is the gap.

| # | Pain | Nucleus addresses via |
|---|---|---|
| 1 | Data quality is reactive, not preventive | Active contracts engine + AI-generated rules |
| 2 | Lineage is metadata, not enforcement | Lineage enforced at write-time, LLM-navigable |
| 3 | Local development is hell | `nucleus up` boots full stack in <10s |
| 4 | Onboarding takes 6+ weeks | AI Copilot with full project context |
| 5 | Cross-team coordination breaks | First-class data contracts + producer/consumer registry |
| 6 | 3am debugging | Replay debugger + AI root cause analysis (v0.7+) |
| 7 | Cost surprises | Per-asset cost meter + cost-aware planner (v0.7+) |
| 8 | Modern data stack is incoherent (15 tools) | One platform, one UX, one auth |
| 9 | AI/ML and BI live in separate worlds | Iceberg + Lance unified, same asset model |
| 10 | Notebook drift from production | Marimo + asset materialization on the same engine |
| 11 | Backfills are terror | Replay debugger predicts cost + impact before run |
| 12 | Privacy/governance bolted on | First-class privacy primitives, lineage-aware deletion |
| 13 | Tests run AFTER bad data lands | Pre-commit contracts, AI-generated from sample data |
| 14 | Cold start for new pipeline = days | `nucleus init` + `ctx.agent.scaffold()` = minutes |
| 15 | Skill barrier extreme | AI Copilot lifts junior to senior productivity |

### 1.2 The AI-Era Trends (Designed for, Not Reacting to)

| # | Trend | Nucleus design response |
|---|---|---|
| 1 | LLMs writing/debugging/operating pipelines | Asset DSL designed for LLM comprehension |
| 2 | Multimodal (text/image/audio) first-class | Iceberg + Lance, Daft engine optional |
| 3 | Vector + relational convergence | Unified query plane over both |
| 4 | Real-time + batch convergence | One asset model for both materializations |
| 5 | Natural language as primary interface | Workbench Copilot from v0.1 |
| 6 | AI-native data contracts | LLM-generated, human-reviewed contracts |
| 7 | Synthetic data + privacy-preserving | Differential privacy primitives v1.5+ |
| 8 | "Vibe coding" data pipelines | `ctx.agent` runtime v0.5+ |

### 1.3 Where We Sit

| Category | Examples | Our relationship |
|---|---|---|
| **Hyperscale lakehouses** | Databricks, Snowflake | We **graduate to them**, not compete |
| **Modern data stack** | Fivetran + dbt + Airflow + Atlan + Soda + Monte Carlo + Snowflake | We **replace 4-6 of these in one platform** for small/mid teams |
| **New OSS engines** | Daft, Lance, DataFusion, DuckDB, Polars | We **wrap them**, never compete |
| **AI coding tools** | Cursor, Copilot | We **port the model** to data engineering |
| **Notebook tools** | Hex, Mode, Marimo | We **integrate Marimo**, don't compete |

We are the **integrator** and **AI-aware UX layer**, not another engine in the stack.

### 1.4 Personas We Serve

| Persona | Profile | Total data scale | What Nucleus gives them |
|---|---|---|---|
| **Solo data engineer / consultant** | 1-5 person team, indie or contractor | <100GB | Full platform on laptop, no infra cost |
| **Startup / mid-market data team** | 5-50 engineers, growing | <10TB | All-in-one platform, no MDS proliferation |
| **Enterprise domain team** (Data Mesh) | Domain-owned data product | 1-10TB per domain | Per-domain Nucleus, federate or use cloud giants for cross-domain |
| **Enterprise central pipeline** (large) | 1000+ engineers, 10-100TB monolith | >10TB cross-partition | Nucleus for orchestration + lightweight, dispatch heavy to Databricks/Snowflake |

We **do not** serve hyperscale (>100TB single-pipeline, FAANG-tier). They stay on Spark.

### 1.5 What We Are NOT

- ❌ A database
- ❌ A SQL engine
- ❌ A DataFrame engine
- ❌ An orchestrator (Dagster is our substrate, hidden)
- ❌ A Spark replacement
- ❌ A Databricks competitor
- ❌ A "Data OS"
- ❌ A universal compute platform
- ❌ An AI/ML training platform
- ❌ A vector database (we use Lance/LanceDB)
- ❌ A BI tool (we surface dashboards but don't build a Tableau)

We own three things and only three things, forever:

1. The **asset graph** (logical model of data products)
2. The **`ctx` SDK** (the developer contract)
3. The **unified AI-assisted experience** (CLI + Workbench + SDK as one product)

Everything else is rented from open source.

---

## 2. Five Pillars

| # | Pillar | Concrete manifestation |
|---|---|---|
| 1 | **High performance on minimal resources** | DuckDB + Polars + Daft. Boot in <10s. 100M rows aggregation in <2s on a laptop. Idle memory <500MB. |
| 2 | **Composable by constitution** | 3-tier dependency classification. Quarterly swap drills in CI. Apache-grade only for Tier 0. No vendor lock-in. |
| 3 | **AI-assisted by design** | Workbench Copilot from v0.1. Asset DSL is LLM-comprehensible. `ctx.agent` runtime v0.5+. |
| 4 | **Familiar UX from proven giants** | dbt SQL feel. Dagster asset graph. Cursor IDE patterns. No reinvented vocabulary. |
| 5 | **Friendly to giants, hostile to no-one** | Iceberg portability. Mode 1/2/3 integration with Databricks/Snowflake. Apache 2.0 license. |

---

## 3. Architecture Overview

### 3.1 The Five Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: EXPERIENCE                                            │
│  How humans and AI interact with Nucleus                        │
│  • ctx SDK (Python) — the only public API                       │
│  • nucleus CLI — power-user interface                           │
│  • Workbench — web IDE with real-time AI Copilot                │
│  • Marimo notebooks — reactive, deterministic                   │
│  • Portal — dashboards, lineage UI, governance                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ ctx SDK (frozen contract)
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 2: INTELLIGENCE                       ⭐ DIFFERENTIATOR  │
│  AI-assisted authoring, debugging, operations                   │
│  • Asset DSL designed for LLM comprehension                     │
│  • Workbench Copilot (v0.1)                                     │
│  • ctx.agent runtime — sandboxed AI execution (v0.5)            │
│  • Semantic knowledge graph — LLM-navigable (v0.7)              │
│  • Cost-aware execution planner (v0.7)                          │
│  • Replay & time-travel debugger (v0.8)                         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 3: COORDINATION                                          │
│  Asset graph, scheduling, lineage, contracts — wrapped Dagster  │
│  • Asset graph + sensors + schedules (Dagster, hidden)          │
│  • Lineage engine (column-level, enforced at write)             │
│  • Contracts engine (schema + quality + SLA)                    │
│  • Iceberg commit service (atomic multi-table writes)           │
│  • Cost meter (per-asset attribution)                           │
│  • Auth + RBAC + audit                                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 4: ENGINES                                               │
│  Composable, swappable compute and integration                  │
│  • SQL: DuckDB (default) ↔ DataFusion (swap target)             │
│  • DataFrame: Polars (default) ↔ DataFusion DF (swap)           │
│  • Multimodal: Daft (optional, AI workloads)                    │
│  • Vector: Lance / LanceDB                                      │
│  • Ingestion: dlt (default) ↔ Sling / Singer                    │
│  • Transformation: dbt-duckdb (default) ↔ SQLMesh               │
│  • Catalog: Lakekeeper (default) ↔ Polaris (swap)               │
│  • Object store: MinIO (local) / cloud S3 (prod)                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 5: PHYSICS                                               │
│  Immortal open standards — the laws of our universe             │
│  • Apache Arrow (in-memory format)                              │
│  • Apache Iceberg (structured table format)                     │
│  • Lance (multimodal/vector table format)                       │
│  • Apache Parquet (column file format)                          │
│  • S3 API (storage protocol)                                    │
│  • OpenLineage (lineage protocol)                               │
│  • OpenTelemetry (observability protocol)                       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer Responsibilities

| Layer | Responsibility | Mutability |
|---|---|---|
| 1. Experience | Surface — humans + AI interact | Evolves with users |
| 2. Intelligence | AI moat — context, planning, copilot | Continuously refined |
| 3. Coordination | Platform brain — graph, contracts, lineage | Stable from v1.0 |
| 4. Engines | Compute kernels — replaceable | Components swap over time |
| 5. Physics | Laws — open standards | Immortal, do not change |

### 3.3 Why This Decomposition

| Decomposition principle | Justification |
|---|---|
| **Bottom is immortal** | Open standards survive vendor pivots and decades of churn |
| **Engines are commodity** | Swap target documented for every Tier 1 engine; vendor death does not kill us |
| **Coordination is glue, not invention** | Wrap Dagster; do not build a custom scheduler |
| **Intelligence is the moat** | No other platform integrates AI this deeply with assets, lineage, contracts |
| **Experience is the product** | Users perceive Nucleus through `ctx` and Workbench; everything else is invisible |

---

## 4. Layer 5: Physics

The **immortal** layer. Open standards backed by multi-vendor consortiums. Zero risk of death.

### 4.1 Components

| Component | Purpose | Why immortal |
|---|---|---|
| **Apache Arrow** | In-memory columnar format | Backed by Snowflake, Databricks, Voltron, Meta, Google. Industry standard. |
| **Apache Iceberg** | Structured table format with ACID, time travel, schema evolution | Apache governance. Netflix, Apple, AWS, Snowflake, Databricks all committers. |
| **Lance** | Multimodal + vector table format with versioning | Open spec, growing community, Linux Foundation aligned. Best-in-class for AI workloads. |
| **Apache Parquet** | Column-oriented file format | De facto standard. 10+ years stable. |
| **S3 API** | Object storage protocol | AWS interface is industry standard. Implemented by MinIO, SeaweedFS, Ceph, Cloudflare R2, GCS, Azure Blob. |
| **OpenLineage** | Lineage event protocol | Linux Foundation, multi-vendor (Airflow, Spark, dbt, etc.). |
| **OpenTelemetry** | Observability protocol (traces, metrics, logs) | CNCF, universally adopted. |

### 4.2 Constraints on This Layer

- We **never** invent a format
- We **never** introduce a proprietary protocol
- We **never** depend on a single-vendor "open standard"
- We track spec evolution and contribute upstream when needed

### 4.3 Why Lance Alongside Iceberg

Iceberg is **excellent for structured data** (tables with columns, rows). Lance is **purpose-built for multimodal** (vectors, embeddings, image/audio/text blobs with versioning).

We use both:

| Workload | Format |
|---|---|
| Customer table, orders, transactions | Iceberg |
| Embeddings, feature vectors | Lance |
| Document corpus (PDFs, articles) | Lance |
| Image/audio datasets | Lance |
| Materialized views for BI | Iceberg |
| ML training datasets | Lance |

This dual-format approach is **the future of data engineering** in the AI era. Big players have not fully embraced this yet — gap for us.

---

## 5. Layer 4: Engines

Best-in-class OSS engines, **composed but never coupled**. Every Tier 1 engine has a documented and CI-tested swap target.

### 5.1 SQL Engine: DuckDB (Default) ↔ DataFusion (Swap Target)

| Aspect | DuckDB | DataFusion (swap target) |
|---|---|---|
| Language | C++ | Rust |
| License | MIT | Apache 2.0 |
| Governance | DuckDB Labs (single vendor) | Apache Software Foundation |
| Iceberg read/write | Native + extension | Via `iceberg-rust` + `datafusion-iceberg` |
| Performance (TPCH 10GB) | ~2.5s | ~3-5s (1.5x slower) |
| Embeddability | Excellent (in-process) | Excellent (Rust crate) |
| **Why default** | Faster, more polished, broader SQL coverage | — |
| **Why swap target** | If DuckDB Labs pivots commercial/dies, DataFusion is Apache-governed immortal | — |

**Default choice rationale:** DuckDB is currently 1.5-3x faster on most analytical workloads and has more mature Iceberg support via extensions. The license (MIT) is permissive and the team is small but well-funded.

**Swap protocol:** Engine selectable via `nucleus.yaml: engine.sql: duckdb | datafusion`. Same `ctx.sql()` API. Full E2E test suite must pass on both quarterly.

### 5.2 DataFrame Engine: Polars (Default) ↔ DataFusion DF (Swap Target)

| Aspect | Polars | DataFusion DataFrame |
|---|---|---|
| Language | Rust | Rust |
| License | MIT | Apache 2.0 |
| Governance | Pola.rs (single vendor) | Apache Software Foundation |
| Streaming engine | Yes (improving) | Yes |
| Out-of-core | Yes (limited) | Yes (better) |
| API ergonomics | Excellent, lazy, expressive | Less ergonomic |
| **Why default** | Best-in-class single-thread perf and DX | — |
| **Why swap target** | Pola.rs is single vendor; DataFusion is Apache | — |

**`ctx.read()` returns a Nucleus DataFrame trait.** Implementation swappable. User code does not import `polars` directly in idiomatic Nucleus assets.

### 5.3 Multimodal / AI Engine: Daft (Optional, v0.5+)

For workloads that need:

- Distributed compute beyond single-node
- Native multimodal columns (images, embeddings, tensors)
- Python UDF performance at scale

**Daft** is the only OSS engine that handles these natively today. It is **optional** — opt-in via `nucleus enable daft`. Default workloads use DuckDB+Polars.

### 5.4 Vector Storage: Lance / LanceDB

For embeddings and AI feature storage. Same Iceberg-style versioning + ACID, but optimized for vectors.

`ctx.read_vector("embeddings.documents")` returns a Lance dataset. Hybrid query with structured tables supported.

### 5.5 Ingestion: dlt (Default) ↔ Sling / Singer (Alt)

| Tool | Use case | Why default |
|---|---|---|
| **dlt** | Pythonic, 100+ connectors, schema-aware | Best DX, fastest iteration |
| **Sling** | High-perf bulk transfer (Postgres → S3, etc.) | When dlt is too slow |
| **Singer / Meltano** | Industry-standard protocol fallback | If dlt dies |

`@nucleus.source()` decorator wraps the chosen tool. User code does not import `dlt` directly.

### 5.6 Transformation: dbt-duckdb (Default) ↔ SQLMesh (Alt)

`@nucleus.sql_asset` compiles to engine-agnostic SQL. Internally uses dbt-duckdb today (mature, widely adopted). SQLMesh is the long-term swap target for stronger semantics (column-level lineage, virtual env builds).

User's SQL files are portable across both.

### 5.7 Catalog: Lakekeeper (Default) ↔ Apache Polaris (Swap)

| Aspect | Lakekeeper | Apache Polaris |
|---|---|---|
| Language | Rust | Java |
| Governance | Single vendor (early stage) | Apache Software Foundation (donated by Snowflake) |
| Iceberg REST API | Yes | Yes |
| Resource footprint | Low (~50MB RAM) | Higher (JVM, ~500MB) |
| **Why default** | Lightweight, Rust-native, aligned with our philosophy | — |
| **Why swap target** | If Lakekeeper stalls, Polaris is Apache | — |

### 5.8 Object Store: MinIO (Local) / Cloud S3 (Prod)

| Environment | Object store |
|---|---|
| Local dev | MinIO (single binary, ~50MB) |
| AWS production | S3 |
| GCP production | GCS (S3-compatible mode) |
| Azure production | Azure Blob (S3-compatible mode via R2 or proxy) |
| Self-hosted production | MinIO or SeaweedFS |

Code is identical across environments. Only `connections/storage.yml` changes.

### 5.9 Engine Selection Matrix by Workload

| Workload | Default engine path | Notes |
|---|---|---|
| SQL analytical query (<100GB) | DuckDB | Fastest |
| SQL analytical (100GB-2TB) | DuckDB | With Iceberg partition pruning |
| DataFrame transformation | Polars | Lazy + streaming |
| Multimodal (images, embeddings) | Daft (optional) | Opt-in |
| Vector search | LanceDB | Sub-second over millions of vectors |
| Ingestion (REST API, DB) | dlt | Schema auto-discovery |
| Ingestion (high-volume bulk) | Sling | Engine selectable via `@nucleus.source(engine="sling")` |
| Streaming (v1.5+) | Benthos / Redpanda | Future module |
| Cross-partition full scan >10TB | **Dispatch to Databricks via Mode 2** | Not for us |

---

## 6. Layer 3: Coordination

Wrap Dagster. Do not build a scheduler.

### 6.1 What We Take from Dagster

| Capability | Dagster provides | We expose via |
|---|---|---|
| Asset graph topology | Yes | `@nucleus.asset` decorator |
| Software-defined assets | Yes | Asset model |
| Sensors | Yes | `@nucleus.sensor` |
| Schedules | Yes | `@nucleus.schedule` |
| Backfills | Yes | `nucleus backfill` CLI |
| Retries, runs, state | Yes | Internal to Coordination layer |
| Web UI | Yes | **Hidden by default; exposed via `nucleus enable compat-dagster`** |

### 6.2 What We Add on Top

| Capability | Why added |
|---|---|
| **Iceberg commit service** | Atomic multi-table writes; conflict resolution; snapshot management |
| **Active contracts engine** | Block bad writes at materialization time (Dagster's checks are post-hoc) |
| **Lineage engine** | Column-level lineage enforced at write time; OpenLineage emission |
| **Cost meter** | Per-asset cost attribution (queries, storage, AI tokens) |
| **Asset registry** | Stable IDs, versioning, deprecation tracking |
| **Unified RBAC** | Single auth model across CLI, Workbench, Portal, SDK |

### 6.3 Progressive Disclosure of Dagster

Three tiers:

| Tier | Default for | Dagster visibility |
|---|---|---|
| **Tier 1 (95% users)** | Standard data engineers | `ctx` SDK only. Dagster fully hidden. |
| **Tier 2 (escape hatch)** | Advanced patterns | `ctx.dagster_context` exposed. Documented as "stepping outside abstraction." |
| **Tier 3 (full power)** | Migration from existing Dagster projects | `nucleus enable compat-dagster` exposes Dagster UI + classes directly. |

### 6.4 Fallback If Dagster Goes Hostile

If Dagster Labs pivots license, gets acquired and turns evil, or stops shipping:

1. We have `nucleus-mini-scheduler` design ready (~3-5K LOC):
   - Asset graph stored in PostgreSQL
   - Cron + retry queue
   - Basic sensors via polling
2. Migration: 30 days
3. Lost capabilities: advanced backfill UI, some sensor types, dynamic partitioning
4. Public `ctx` API: **unchanged**

This fallback is **designed in**, not hoped for. Documented in `/docs/swap/dagster.md`.

---

## 7. Layer 2: Intelligence

**This is the differentiator.** No other platform integrates AI this deeply with data engineering primitives.

### 7.1 Design Principle

Every part of Nucleus is engineered for LLM comprehension and operation:

- Asset DSL has rich type annotations, docstring conventions, predictable patterns
- Errors are structured, machine-parseable, suggest fixes
- Lineage and contracts are queryable as graphs
- `ctx` SDK introspectable: any LLM can ask "what assets exist? what's the schema of X? who depends on X?"

### 7.2 v0.1 Capability: Workbench Copilot

The only AI feature in v0.1. Ships in 6 months.

| Feature | Description |
|---|---|
| Schema-aware SQL completion | Suggests columns, joins, aggregations based on actual table schemas |
| Asset-aware code completion | Suggests `ctx.read("...")` with real asset names |
| Lineage-aware refactoring | "Rename column X" updates all downstream assets that reference it |
| Inline AI chat | Ask questions about the project, get answers grounded in actual code + schema |
| AI-generated tests | Given an asset, generate suggested `@nucleus.check` rules |
| Documentation generation | Given an asset, generate `docs/` markdown |

**Implementation:** Workbench is built on Monaco editor + LSP. Copilot uses Claude/GPT via API (configurable provider) with structured context injection (project graph, schemas, lineage).

### 7.3 v0.5+ Capability: `ctx.agent` Runtime

Sandboxed AI execution.

```python
from nucleus import agent

agent.scaffold_pipeline(
    description="Ingest Stripe charges nightly, build daily revenue rollup, expose to BI",
    target_dir="assets/finance/",
)
```

Behavior:

1. LLM proposes asset code (`@nucleus.source`, `@nucleus.asset`, `@nucleus.sql_asset`)
2. Code written to **sandbox branch**, not committed
3. Tests auto-generated and run
4. User reviews diff in Workbench
5. User approves → merged to project

**Critical guardrails:**

- Agent **cannot** modify Tier 0 standards or core configs
- Agent **cannot** commit without human approval
- Agent **cannot** access production secrets
- All agent actions logged in audit trail

### 7.4 v0.7+ Capability: Semantic Knowledge Graph

A queryable graph that LLMs and humans can both use:

- Nodes: assets, columns, contracts, sensors, schedules, owners, business terms
- Edges: depends_on, produces, contracts_with, owned_by, semantically_means

Queries (natural language → graph traversal):

- "Which dashboards depend on `raw.stripe.charges`?"
- "Find all assets that contain PII"
- "Show me revenue-related assets and their freshness"

### 7.5 v0.7+ Capability: Cost-Aware Planner

Before running a materialization, the planner estimates:

| Metric | How estimated |
|---|---|
| Query cost (CPU-seconds) | Iceberg stats + historical run telemetry |
| I/O cost (bytes scanned, S3 GETs) | Partition pruning + column projection analysis |
| Cloud egress cost | Per-environment pricing config |
| AI token cost | If asset uses `ctx.llm` calls |

Output: dollars per run + cumulative monthly forecast. User sees this **before** scheduling.

### 7.6 v0.8+ Capability: Replay & Time-Travel Debugger

For every run, Nucleus snapshots:

- Asset code (git hash)
- Input table snapshots (Iceberg snapshot IDs)
- Configuration
- Output Iceberg snapshot

Replay: re-run any historical materialization with current code (test refactor on real history) or historical code (reproduce a past bug).

Time-travel: query any asset "as of" any past timestamp.

### 7.7 Why This Layer Is the Moat

| Reason | Explanation |
|---|---|
| **Built-in, not bolt-on** | dbt Copilot, Hex Magic, etc. are bolt-on. Nucleus has AI access to full lineage, contracts, schemas, history. |
| **Composable, not coupled** | Works with Claude, GPT, local Llama, anything via OpenAI-compatible API |
| **Replicable trust** | Sandbox + audit + human-approval gate. No "AI YOLO into production." |
| **Compounds with usage** | Every asset's code, schema, contract, run history feeds context |

---

## 8. Layer 1: Experience

How users (humans + AI) actually interact with Nucleus.

### 8.1 Surfaces

| Surface | Audience | Capability |
|---|---|---|
| **`ctx` SDK (Python)** | Developers writing assets | The only public API. All asset code uses this. |
| **`nucleus` CLI** | Power users, CI/CD, automation | Init, up, down, run, build, test, deploy, etc. |
| **Workbench (web)** | Day-to-day developers | Monaco IDE + AI Copilot + lineage UI + run history |
| **Portal (web)** | All users | Catalog, lineage browser, dashboards, governance |
| **Marimo notebooks** | Data scientists, exploration | Reactive notebooks on the same engines |

### 8.2 Design Principles

| Principle | Manifestation |
|---|---|
| **One mental model** | Everything is an asset. No "tasks", "jobs", "notebooks-vs-pipelines" split. |
| **Familiar vocabulary** | "asset", "source", "check", "sensor", "schedule" — all standard data engineering terms |
| **Progressive disclosure** | Beginners see Workbench. Power users use CLI + SDK. Advanced users access escape hatches. |
| **AI-aware by default** | Copilot is in every text input. Asset DSL is LLM-friendly. |
| **Local-first** | Everything works offline (except cloud-specific features) |

### 8.3 Reference UX Patterns Borrowed

| Pattern from | What we borrow |
|---|---|
| **dbt** | SQL-first project layout, `ref()` resolution, model materialization |
| **Dagster** | Asset graph mental model, sensors, schedules |
| **Cursor** | AI-aware editor with project-wide context |
| **Vercel** | Deploy via single command, zero-config defaults |
| **Supabase** | Local dev = identical to prod, one tool for everything |
| **Linear** | Fast, keyboard-first, beautifully designed |
| **Marimo** | Reactive deterministic notebooks |

---

## 9. Composability by Constitution

**Design Law #1.** Supersedes all other laws.

### 9.1 The Constitution

> The user depends on the `ctx` SDK and the Iceberg lake.
> The user does NOT depend on any specific engine, orchestrator, ingestion tool, or notebook runtime.
>
> Any Tier 1 or Tier 2 component MUST have:
>   1. Documented swap target (Apache-governed preferred)
>   2. CI swap-test passing within 7 days of swap declaration
>   3. Migration path documented in `/docs/swap/{component}.md`
>
> If a component cannot be swapped, it MUST be Tier 0 (immortal standard).

### 9.2 The 3-Tier Classification

#### Tier 0: Bedrock (immortal, never swap)

| Component | Why immortal |
|---|---|
| Apache Arrow | Multi-vendor consortium, industry default |
| Apache Iceberg | Apache governance, multi-vendor committers |
| Apache Parquet | De facto standard |
| Lance | Open spec, growing adoption |
| S3 API | Universal protocol |
| OpenLineage | CNCF/LF backed |
| OpenTelemetry | CNCF universal |

#### Tier 1: First-class engines (must have swap)

| Component | Default | Swap Target | Swap Status |
|---|---|---|---|
| SQL engine | DuckDB | DataFusion | Documented + quarterly CI test |
| DataFrame engine | Polars | DataFusion DF | Documented + quarterly CI test |
| Catalog | Lakekeeper | Apache Polaris | Documented + quarterly CI test |
| Object store | MinIO | SeaweedFS / Direct cloud S3 | Documented |

#### Tier 2: Wrapped capabilities (fully replaceable)

| Component | Default | Swap Target |
|---|---|---|
| Orchestration | Dagster | `nucleus-mini-scheduler` (in-house fallback) |
| Ingestion | dlt | Sling / Singer / custom |
| Transformation | dbt-duckdb | SQLMesh / native `ctx.sql` runner |
| Notebooks | Marimo | Jupyter or none |
| Streaming (future) | Benthos / Redpanda | Kafka native / Flink |

### 9.3 Swap Drill Protocol

```
Quarterly (automated CI):
  1. Spin up Nucleus with swap config (e.g., engine.sql=datafusion)
  2. Run full E2E test suite against canonical pipelines
  3. Compare performance vs default (alert if >2x regression)
  4. Compare feature coverage (alert if any test fails)
  5. Generate swap drill report
  6. Block release if blocker found
```

### 9.4 License & Health Monitoring

Per Tier 1/2 component, tracked monthly:

- Commit frequency (90-day rolling)
- Release cadence
- Funding events (acquisition rumors, license changes)
- Community health (stars, Discord activity)
- Maintainer count

Auto-alert if any metric drops 50%+.

License monitoring: every dependency MUST be permissive (Apache 2.0, MIT, BSD). Any pivot to BSL/SSPL/proprietary triggers automatic swap activation.

### 9.5 Forking Strategy

If a Tier 1/2 component goes hostile:

1. Activate swap target immediately
2. Communicate to users (transparent disclosure)
3. If swap target also unhealthy, fork the component under Nucleus org
4. Maintain fork until alternative emerges or community resumes

### 9.6 Why This Matters

History of platforms killed by vendor death:
- Parse → Facebook shut down (2017)
- RethinkDB → bankrupt (2016)
- Heroku → Salesforce gutted free tier (2022)
- HashiCorp → BSL pivot (2023)
- Redis → BSL pivot (2024)

Nucleus survives all of these scenarios **by design**, not by hope.

---

## 10. Yield-to-Giants Strategy

We do not compete with Databricks/Snowflake. We integrate.

### 10.1 Mode 1: Graduation (zero-effort)

User outgrows Nucleus (domain hits 50TB+, needs distributed compute):

1. Data already in Iceberg on S3
2. Point Databricks/Snowflake/Trino at same S3 + Iceberg catalog
3. Zero migration. Same tables. Different compute.
4. User can keep using Nucleus for ingestion + light transforms; use giants for heavy analytics

**Implementation cost:** zero. Iceberg standard handles it.

### 10.2 Mode 2: Hybrid Compute (v1.5+)

Some assets need big compute. Dispatch them.

```python
@nucleus.sql_asset(compute="databricks")
def fct_yearly_revenue_rollup(ctx):
    """Yearly aggregation over 10TB raw_events. Too big for DuckDB."""
    return ctx.sql("""
        SELECT year, region, SUM(amount)
        FROM raw_events
        WHERE year >= 2020
        GROUP BY 1, 2
    """)
```

Nucleus:
- Orchestrates the asset (schedule, retry, lineage, contract)
- Dispatches the SQL to Databricks cluster via JDBC/REST
- Tracks cost and run history
- Asset output is committed back to Iceberg (no data movement)

Other compute providers supported: Snowflake, BigQuery, Trino, ClickHouse (via DBAPI plugin).

### 10.3 Mode 3: Federation (v2.0+)

For full Data Mesh:

- Each domain runs its own Nucleus
- Iceberg REST catalog federation
- Cross-domain queries via Trino, Databricks, or Snowflake
- Permissions handled via Lakekeeper + central RBAC

### 10.4 Why This Strategy Wins

| Strategic benefit | Explanation |
|---|---|
| **Acquisition-friendly** | Giants see us as a feeder, not a threat |
| **No data lock-in for users** | Iceberg portability removes objection |
| **Smaller engineering scope** | We don't build distributed compute |
| **Customer trust** | "If we outgrow you, we can leave" → users stay longer |
| **Coopetition optionality** | Partnerships, OEM deals, integration revenue |

---

## 11. Local-First Guarantee

### 11.1 The `nucleus up` Promise

```bash
$ git clone my-data-project
$ cd my-data-project
$ nucleus up
✓ MinIO ready (port 9000)
✓ Lakekeeper ready (port 8181)
✓ PostgreSQL (metadata) ready
✓ Dagster substrate ready
✓ Workbench ready (http://localhost:3000)
Total: 8.2s
```

### 11.2 Performance Targets

| Metric | Target |
|---|---|
| Cold boot time (laptop, M1/M2, 16GB) | <10s |
| Warm boot (after first up) | <3s |
| Idle RAM | <500MB |
| Active small pipeline RAM | <2GB |
| Time to first materialized asset (new user) | <5 min |

### 11.3 Identical-to-Production

The exact same code, same versions, same engines run locally and in production. Only `connections/*.yml` and `environments/*.yml` differ.

| Concern | Local | Production |
|---|---|---|
| Object store | MinIO | S3 |
| Catalog | Lakekeeper (local sqlite) | Lakekeeper (postgres) |
| Metadata | SQLite | PostgreSQL |
| Orchestration | Dagster in-process | Dagster on k8s |
| Secrets | `.env.local` | Vault / cloud secrets manager |
| Code | identical | identical |

### 11.4 Disconnected Operation

Nucleus can run fully offline (except features that explicitly require internet):

- All assets materialize locally against MinIO
- AI Copilot can use local LLMs (Ollama, llama.cpp) via OpenAI-compatible API
- Telemetry buffers and flushes on reconnect

---

## 12. The Asset Primitive

The central concept. Everything in Nucleus is an asset.

### 12.1 Definition

An **asset** is a named, versioned, contractually-enforced unit of data that:

- Has a stable identity (`catalog.schema.name`)
- Has a code-defined production logic (Python or SQL)
- Has a known schema and contract
- Has explicit dependencies on other assets
- Has lineage tracked at column level
- Has a freshness SLA
- Has owners and a deprecation policy

### 12.2 Asset Types

| Type | Decorator | Materialized as |
|---|---|---|
| Python asset | `@nucleus.asset` | Iceberg table or Lance dataset |
| SQL asset | `@nucleus.sql_asset` | Iceberg table |
| Source | `@nucleus.source` | External system pull → Iceberg table |
| Check | `@nucleus.check` | Validation run (not materialized) |
| Multi-asset | `@nucleus.multi_asset` | Multiple Iceberg tables atomically |
| Sensor | `@nucleus.sensor` | Trigger logic (not materialized) |
| Schedule | `@nucleus.schedule` | Time-based trigger (not materialized) |

### 12.3 Materialization Modes

| Mode | Description | Use case |
|---|---|---|
| `table` | Full rebuild on each run | Small dimensions, reference data |
| `view` | Logical view, not materialized | Lightweight transforms |
| `incremental` | Only new rows merged | Event tables, fact tables |
| `snapshot` | New version on each run | Slowly changing dimensions, audit |

### 12.4 Lineage

Lineage is **enforced at write time**, not derived from logs:

- SQL assets: parsed via SQLGlot to extract column dependencies
- Python assets: tracked via `ctx.read()` calls + return type analysis
- Emitted to OpenLineage backend (queryable)

Column-level lineage is queryable through the semantic graph and Workbench Portal.

### 12.5 Contracts

A contract is a machine-enforced agreement about an asset:

```python
@nucleus.contract("sales.orders")
class OrdersContract:
    schema = {
        "order_id": "string NOT NULL UNIQUE",
        "customer_id": "string NOT NULL",
        "amount": "decimal(10,2) NOT NULL CHECK > 0",
        "created_at": "timestamp NOT NULL",
    }
    freshness = "max 1 hour stale"
    sla = "99.9% successful daily runs over 30-day window"
    pii_columns = ["customer_id"]
    owner = "@team-revenue"
```

Contracts are **enforced at materialization**: bad data is rejected before commit. Not a post-hoc check.

(Full spec: `nucleus_asset_model_spec.md`)

---

## 13. The `ctx` SDK Contract

### 13.1 Principles

1. **The only public API.** Users never import `dagster`, `polars`, `duckdb`, `dlt`, `dbt` directly.
2. **Frozen at v1.0.** Breaking changes require major version bump and migration tool.
3. **Engine-agnostic.** Internal engine swaps do not change `ctx` surface.
4. **Introspectable.** Every object has structured metadata accessible to humans and LLMs.

### 13.2 Surface Summary

```python
import nucleus

@nucleus.asset(materialize="incremental", partition="day")
def fct_orders(ctx):
    raw = ctx.read("raw.stripe.charges", as_="polars")  # pl.LazyFrame
    cleaned = raw.filter(pl.col("status") == "succeeded")
    ctx.write(cleaned, contract="sales.orders")
    ctx.log.info("Processed orders", count=cleaned.shape[0])
    ctx.metrics.gauge("orders.row_count", cleaned.shape[0])
```

Key APIs:

| API | Purpose |
|---|---|
| `ctx.read(name, as_=...)` | Read upstream asset as Polars / Arrow / DuckDB / Pandas |
| `ctx.write(df, contract=...)` | Atomic write to Iceberg with contract enforcement |
| `ctx.sql(query)` | Execute SQL on current asset context with `{{ ref() }}` resolution |
| `ctx.log` | Structured logger |
| `ctx.metrics` | OpenTelemetry metrics |
| `ctx.secrets` | Access secrets without exposing them in code |
| `ctx.config` | Access typed configuration |
| `ctx.snapshot(name)` | Take an Iceberg snapshot |
| `ctx.dagster_context` | Tier 2 escape hatch |

(Full spec: `nucleus_ctx_sdk_spec.md`)

### 13.3 Versioning Policy

| Change type | Version bump | Compatibility |
|---|---|---|
| New optional argument | Patch | Full backward |
| New method | Minor | Full backward |
| Remove method | Major | Migration tool provided, 12-month deprecation window |
| Change method signature | Major | Migration tool, deprecation |

---

## 14. Operational Concerns

### 14.1 Retries & Backoff

- Per-asset configurable: `max_retries`, `backoff_strategy`
- Default: 3 retries, exponential backoff (1s, 5s, 25s)
- Idempotency: writes are transactional via Iceberg snapshots — partial failures roll back
- Dead-letter on permanent failure: notified via configured channel (Slack, PagerDuty, email)

### 14.2 Backfills

```bash
nucleus backfill fct_orders --from 2024-01-01 --to 2024-12-31
```

- Replays historical partitions
- Cost-aware planner shows estimate first
- Can be parallelized (configurable concurrency)
- Progress tracked in run history
- Cancellable mid-run; resumes from last committed partition

### 14.3 Schema Evolution

Iceberg supports schema evolution natively. Nucleus enforces:

| Change | Allowed | Action |
|---|---|---|
| Add column | Yes (auto) | Backfilled NULL |
| Drop column | Requires contract update + deprecation flag | 30-day deprecation period |
| Rename column | Requires migration script | Lineage updated automatically |
| Change type (compatible widening) | Yes | Auto-applied |
| Change type (lossy) | Requires migration script | Manual review |

### 14.4 Concurrency

| Scope | Concurrency model |
|---|---|
| Within a single asset run | Engine-specific (DuckDB multi-thread, Polars parallel) |
| Across assets in same run | Dagster scheduler — DAG-aware parallelism |
| Across runs (same asset) | Iceberg commit retries handle conflicts |
| Multi-user Workbench | PostgreSQL-backed session state; optimistic locking |
| Multi-tenant production | Process-per-tenant or k8s namespace-per-tenant |

### 14.5 Disaster Recovery

| Scenario | Recovery |
|---|---|
| Single asset corrupted | Roll back to previous Iceberg snapshot (time-travel) |
| Catalog corrupted | Restore from PostgreSQL backup; Iceberg metadata is self-describing |
| Object store data loss | Restore from cross-region replication; Iceberg manifests can rebuild |
| Full disaster | Lake is portable. Spin up new Nucleus, point at S3+catalog, continue. |

---

## 15. Security & Governance

### 15.1 Authentication

| Tier | Method |
|---|---|
| Local dev | None (single user) |
| Cloud (hosted) | OAuth (Google, GitHub, Microsoft) |
| Self-hosted | OIDC integration (Auth0, Authentik, Keycloak) |
| Enterprise | SAML / SCIM provisioning |

### 15.2 Authorization (RBAC)

Hierarchical:

```
Org
├── Domain (data mesh boundary)
│   ├── Project (Nucleus instance)
│   │   ├── Asset (catalog.schema.name)
│   │   │   ├── Read
│   │   │   ├── Materialize
│   │   │   ├── Delete
│   │   │   └── Manage contract
```

Backed by OPA or Casbin internally. Surfaced via `nucleus permissions` CLI.

### 15.3 Secrets

- Local: `.env` files (gitignored)
- Cloud: Encrypted at rest, accessed via `ctx.secrets.get("name")`
- Enterprise: HashiCorp Vault / Infisical / cloud KMS integration

Secrets never appear in logs, run metadata, or AI Copilot context.

### 15.4 PII & Compliance

| Feature | Capability |
|---|---|
| PII column tagging | Declarative in contract; flows through lineage |
| Masking | Automatic in non-production environments based on contract tags |
| Right-to-be-forgotten (GDPR) | `nucleus delete-subject --id ...` traverses lineage, deletes from all downstream assets |
| Audit trail | Every asset materialization, secret access, permission change logged immutably |
| Differential privacy primitives | v1.5+ for aggregate exports |

### 15.5 Compliance Posture

We design for:
- **SOC 2 Type II** (Cloud offering)
- **GDPR Article 17** (right to erasure via lineage)
- **HIPAA** (with enterprise tier add-ons; PHI handling templates)
- **CCPA** (subject access via lineage)

We do **not** claim compliance certifications until audited. Honest about state.

---

## 16. Performance Targets

Committed targets. Failing these is a release blocker.

### 16.1 Boot & Startup

| Metric | Target |
|---|---|
| `nucleus up` cold | <10s (M1/M2 laptop, 16GB) |
| `nucleus up` warm | <3s |
| `nucleus run <asset>` startup overhead | <500ms |

### 16.2 Query Performance

| Workload | Target |
|---|---|
| 100M-row aggregation (laptop) | <2s |
| 1B-row aggregation (32-core server) | <30s |
| TPCH-10GB on DuckDB | <3s (matches DuckDB native) |
| Iceberg partition pruning | <100ms metadata overhead |

### 16.3 Resource Footprint

| Metric | Target |
|---|---|
| Idle RAM | <500MB |
| Active small pipeline | <2GB |
| Workbench server (single user) | <1GB |
| Per-asset overhead | <10MB metadata |

### 16.4 Scale Limits

| Limit | Target |
|---|---|
| Assets per project | 10,000+ |
| Concurrent runs | 100+ (single-node) |
| Iceberg snapshots retained | 1000+ |
| Workbench concurrent users | 50+ (single-server) |

### 16.5 Reliability

| Metric | Target |
|---|---|
| Asset materialization success rate | >99.9% (assuming valid code) |
| Iceberg commit success rate | >99.99% |
| Workbench uptime (Cloud SLA) | 99.9% |

---

## 17. Monetization Model

### 17.1 Tiers

| Tier | Price | Includes |
|---|---|---|
| **OSS Core** | Free (Apache 2.0) | Full platform, all engines, CLI, SDK, Workbench (self-hosted) |
| **Nucleus Cloud** | $20/seat/mo + usage | Managed catalog, S3, secrets, deploy, basic Copilot |
| **Nucleus Copilot Pro** | +$50/seat/mo | Premium AI features: agent runtime, advanced models, custom prompts |
| **Nucleus Enterprise** | $50K-500K/year | SSO/SAML, audit, multi-tenant, RBAC, vertical packs, SLA, support |
| **Marketplace** (v2.0+) | 15-25% rev share | Data product templates, vertical accelerators |

### 17.2 Realistic Trajectory (Humble)

| Phase | Timeline | Users | ARR | Milestone |
|---|---|---|---|---|
| v0.1 → v0.5 | Month 0-9 | 10-100 trial | $0 | Validate PMF |
| v1.0 launch | Month 9-12 | 500-2,000 | $50-300K | First paying customers |
| v1.5 | Year 2 | 5,000-15,000 | $500K-$2M | Sustainable indie business |
| v2.0 | Year 3 | 15,000-50,000 | $2-10M | Acquisition-eligible |
| v3.0 | Year 5 | 50,000+ | $10-30M | Strategic acquisition target ($100-500M exit) |

### 17.3 What We Don't Do

- No license pivot (Apache 2.0 stays)
- No "feature lock" that breaks composability
- No proprietary data formats
- No "enterprise edition" with different SDK

The OSS core is **complete enough** to use forever without paying us.

---

## 18. Roadmap

### 18.1 v0.1 — "Foundation" (Month 0-6)

**Must ship:**
- OSS core: ctx SDK, CLI, Workbench (basic), Marimo integration
- Layer 5: Iceberg + Parquet + Arrow + MinIO + Lakekeeper
- Layer 4: DuckDB + Polars + dlt + dbt-duckdb
- Layer 3: Dagster wrapped (asset graph, basic lineage, basic contracts)
- Layer 2: Workbench Copilot (schema-aware completion, inline chat)
- Layer 1: CLI (init, up, run, build, test, list, describe)

**Out:** ctx.agent, semantic graph, cost planner, replay debugger, multimodal, federation, marketplace

### 18.2 v0.5 — "Intelligence Awakens" (Month 6-9)

- `ctx.agent` runtime (sandboxed AI code generation)
- Improved Copilot (project-wide context, test generation, doc generation)
- Daft integration (optional, multimodal opt-in)
- Lance integration (vector storage)

### 18.3 v1.0 GA — "Production Ready" (Month 9-12)

- Hardened SDK (frozen at v1.0)
- Cloud offering (managed catalog, S3, secrets)
- Enterprise SSO/RBAC
- SLA-grade reliability
- First paying customers

### 18.4 v1.5 — "Operations Mastery" (Year 2)

- Cost-aware planner
- Replay & time-travel debugger
- Semantic knowledge graph
- Streaming support (Benthos / Redpanda)
- Hybrid compute Mode 2 (Databricks/Snowflake dispatch)
- Vertical packs (finance, healthcare, retail)

### 18.5 v2.0 — "Federation & Marketplace" (Year 3)

- Mode 3 federation (Data Mesh full)
- Data Product Marketplace (vertical templates + community sharing)
- Advanced privacy primitives (differential privacy, synthetic data)
- Multi-region deployment

### 18.6 v3.0+ — "Acquisition or Independence"

By v3.0 (Year 5):
- $10-30M ARR
- 50K+ users
- Established as the standard for Data Mesh / mid-market
- Acquisition discussions with Databricks/Snowflake/Microsoft realistic
- Or continue independent path

---

## 19. Risk Register

Top 10 risks. Each has mitigation tied to architecture.

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Dagster Labs pivots license / acquired hostile | Medium | High | `nucleus-mini-scheduler` fallback designed; 30-day swap |
| 2 | DuckDB Labs commercial pivot | Low-Medium | Medium | DataFusion swap quarterly tested |
| 3 | LLM cost / capability changes break Copilot economics | Medium | Medium | Provider-agnostic (Claude/GPT/Llama); local model support |
| 4 | Big players build "AI for data" themselves | Medium | High | Stay 12+ months ahead via integration depth; acquisition becomes attractive |
| 5 | Data Mesh adoption slower than projected | Medium | Medium | Architecture also serves single-domain mid-market |
| 6 | Iceberg adoption stalls | Very low | Critical | Multi-vendor commitment makes this unlikely |
| 7 | Hiring senior platform engineers slow | High | High | Open-source first to attract via mission, not money |
| 8 | Scope creep adds 6-12 months to v0.1 | High | High | Hard cuts enforced via this document + AGENTS.md + Cursor rules |
| 9 | Composability is too abstract; perf suffers | Medium | Medium | Each layer benchmarked; abstraction must justify itself |
| 10 | Cloud margin compressed by AI token costs | Medium | Medium | Token usage metered per-seat; Copilot Pro tier captures premium |

---

## 20. Non-Goals

What we **explicitly do not build**, ever:

### 20.1 We Do Not Build

- ❌ Our own SQL engine
- ❌ Our own DataFrame engine
- ❌ Our own catalog (we use Lakekeeper/Polaris)
- ❌ Our own object store (we use MinIO/S3)
- ❌ Our own table format (we use Iceberg/Lance)
- ❌ Our own scheduler (we wrap Dagster; fallback if needed)
- ❌ Our own connectors at scale (we use dlt/Sling)
- ❌ Our own SQL transformation framework (we use dbt-duckdb/SQLMesh)
- ❌ Our own notebook runtime (we integrate Marimo)
- ❌ Our own BI tool (we surface dashboards via Portal)
- ❌ A Spark replacement
- ❌ A Databricks competitor
- ❌ A vector database (we use Lance)
- ❌ An ML training platform

### 20.2 We Do Not Compete With

- Databricks, Snowflake (we feed them via Mode 1/2)
- Cloud providers (we run on top of S3/GCS/Azure)
- BI tools (we surface their dashboards)
- AI providers (we use them; our moat is integration depth, not LLM models)

### 20.3 We Do Not Target

- Hyperscale (>100TB single-pipeline)
- FAANG-tier in-house data platforms
- Workloads requiring custom CUDA / proprietary hardware
- Real-time sub-millisecond OLTP

---

## 21. Decision Log

Key architectural decisions and rationale. New decisions appended; existing ones not rewritten.

### D1. Wrap Dagster, do not build orchestrator

**Decision:** Use Dagster as hidden substrate.
**Date:** v3 (preserved in v4)
**Rationale:** Building a custom scheduler is a 3-5 year rabbit hole. Dagster's asset model is exactly what we need. Hide it; expose `ctx`.
**Risk:** Dagster Labs business risk. Mitigated by `nucleus-mini-scheduler` fallback.

### D2. DuckDB + Polars over DataFusion-only

**Decision:** Default to DuckDB (SQL) + Polars (DataFrame). DataFusion is swap target.
**Date:** v4
**Rationale:** DuckDB is 1.5-3x faster on most analytical workloads; Polars has best DX. Apache-grade swap path mitigates single-vendor risk.
**Reconsideration trigger:** DuckDB Labs pivot or perf regression >2x.

### D3. Apache 2.0 license

**Decision:** Apache 2.0 forever. No BSL/SSPL pivot.
**Date:** v4
**Rationale:** Friendly to giants enables acquisition path. Maximum trust from enterprise. Composability requires permissive license. AWS forking us is acceptable risk vs alienating ecosystem.

### D4. Iceberg + Lance dual-format

**Decision:** Iceberg for structured, Lance for multimodal/vector.
**Date:** v4 (new)
**Rationale:** Iceberg is best for structured; Lance is purpose-built for AI workloads. Both Apache-grade or LF-aligned. Dual format is the future of AI-era data.

### D5. Yield to giants via Mode 1/2/3

**Decision:** Do not build distributed compute. Provide Iceberg portability + dispatch hooks.
**Date:** v4 (new, replaces v3 "scale module")
**Rationale:** Distributed compute is a moat we cannot win. Iceberg portability removes user objection. Giants become friends.

### D6. Intelligence Layer as differentiator

**Decision:** AI-assisted features are first-class architectural layer (not bolt-on).
**Date:** v4 (new)
**Rationale:** No other platform integrates AI this deeply. Built-in beats bolt-on. Cursor's success proves market.

### D7. v0.1 ships with only Workbench Copilot (no agent runtime)

**Decision:** Defer `ctx.agent` to v0.5.
**Date:** v4
**Rationale:** Agent runtime is hard. Ship Copilot first to validate AI thesis. Agent without polish destroys trust.

### D8. Composability by Constitution as Law #1

**Decision:** Every Tier 1/2 dependency must have swap target tested quarterly.
**Date:** v4 (new, formalized from concerns)
**Rationale:** Vendor death has killed too many platforms. Architecture must survive worst-case.

### D9. Local-first identical-to-prod

**Decision:** `nucleus up` boots full stack in <10s; same code runs in production.
**Date:** v3 (preserved)
**Rationale:** Iteration speed is competitive advantage. Spark-on-laptop is dead end.

### D10. ctx SDK is the only public API

**Decision:** Users never import Dagster, Polars, DuckDB, dlt, dbt directly.
**Date:** v3 (preserved)
**Rationale:** Engine swaps must be invisible. Public API frozen at v1.0.

---

## 22. References

### Internal Documents (companion specs)

| Document | Purpose |
|---|---|
| `nucleus_ctx_sdk_spec.md` | Full `ctx` SDK API specification |
| `nucleus_asset_model_spec.md` | Asset primitive deep-dive |
| `nucleus_project_anatomy.md` | On-disk layout convention |
| `nucleus_cli_spec.md` | Complete CLI specification |
| `nucleus_poc_plan.md` | PoC validation plan (pre-v0.1) |
| `nucleus_implementation_readiness.md` | Go/no-go gate for v0.1 |
| `nucleus_red_team_review.md` | Adversarial review with mitigations |
| `nucleus_vs_databricks.md` | Feature parity analysis |
| `AGENTS.md` | AI agent operating instructions |
| `.cursor/rules/nucleus.mdc` | Cursor IDE rule for project discipline |

### External References

- Apache Arrow: https://arrow.apache.org
- Apache Iceberg: https://iceberg.apache.org
- Apache Parquet: https://parquet.apache.org
- Apache DataFusion: https://datafusion.apache.org
- Apache Polaris: https://polaris.apache.org
- Lance Format: https://lancedb.github.io/lance/
- DuckDB: https://duckdb.org
- Polars: https://pola.rs
- Daft: https://www.getdaft.io
- Dagster: https://dagster.io
- dlt: https://dlthub.com
- dbt: https://docs.getdbt.com
- Marimo: https://marimo.io
- Lakekeeper: https://lakekeeper.io
- OpenLineage: https://openlineage.io
- OpenTelemetry: https://opentelemetry.io

### Conceptual Influences

- Data Mesh (Zhamak Dehghani)
- Software-Defined Assets (Dagster)
- Lakehouse architecture (Databricks academic papers)
- Composable Data Systems (Voltron Data, Wes McKinney essays)
- Modular Open-Source Software (Unix philosophy, Cathedral & Bazaar)

---

## Appendix A: How to Read This Document

### For a senior data platform engineer

1. Read TL;DR (5 min)
2. Skim §1 Positioning, §3 Architecture Overview (10 min)
3. Deep-dive sections relevant to their domain (20 min):
   - Storage/format → §4 Physics
   - Compute → §5 Engines
   - Orchestration → §6 Coordination
   - AI features → §7 Intelligence
   - DX → §8 Experience
4. Scrutinize §14 Operational, §16 Performance, §19 Risk Register (10 min)

Total: ~45 minutes for full critical review.

### Questions a senior engineer will likely ask

| Question | Answer location |
|---|---|
| Why not Spark? | §1.3, §10, §20 |
| How does Iceberg integration work atomically? | §6.2, §14 |
| What happens if DuckDB dies? | §5.1, §9 |
| How does Dagster get hidden? | §6.3 |
| What's the failure mode for X? | §14 |
| How do you handle PII? | §15.4 |
| What's the perf vs Databricks? | §16, §10 |
| Can I migrate off Nucleus? | §10.1 |

### For a founding team member

Read in order: §1, §2, §3, §17, §18, §19, §20. Then implementation specs.

### For an investor / partner

Read TL;DR, §1, §17, §18. Then ask questions.

---

## Appendix B: Open Questions (To Resolve Before v0.1 Code)

Despite this document, these remain open:

1. **Cloud architecture** — single-tenant per customer vs multi-tenant shared. Affects pricing math significantly.
2. **AI provider strategy** — own Claude/GPT keys vs BYOK vs both. Affects Copilot economics.
3. **Workbench technology** — Tauri (cross-platform desktop) vs pure web. Affects development cost.
4. **Marimo deep integration vs lightweight** — fork Marimo vs use as-is. Affects long-term flexibility.
5. **Initial vertical focus** — should v1.0 marketing focus on a vertical (finance, healthcare) or stay horizontal.

These do not block this architecture but must be answered before v0.1 begins.

---

## Sign-off

This document is the **single source of truth** for Nucleus architecture as of v4.0.

Implementation may begin once:
1. PoCs in `nucleus_poc_plan.md` pass
2. Open questions in Appendix B are answered
3. Team and resources are confirmed per `nucleus_implementation_readiness.md`

Any deviation from this document requires explicit amendment with rationale.

---

**End of v4.0**
