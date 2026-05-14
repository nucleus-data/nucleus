# Non-Goals — What Nucleus Will NEVER Build

> **Authority**: `nucleus_architecture_v4.1.md` §20 (superseding source of truth).
> **Purpose**: Definitive list of what Nucleus does NOT build — with rationale. Prevents scope creep, prevents contribution effort going to waste, and guides architectural decisions when "should we build X?" is unclear.

Any contribution that builds something on this list will be declined, regardless of how well it's implemented. If you believe an item should be reconsidered, open a GitHub Discussion, not a PR.

---

## The Core Principle

> **Default decision: WRAP, not BUILD.**
>
> For every proposed component, the first question is: "Which production-grade OSS handles this already?" If an answer exists, we wrap it. We only build when no viable OSS exists OR when wrapping costs more than building (and even then, we write an ADR first).

The items below are cases where wrapping is so clearly superior that building is never acceptable.

---

## 1. Custom SQL Engine

**We will not build**: A SQL execution engine, query planner, or query optimizer.

**We wrap instead**: DuckDB (default). DataFusion (swap target). Interface maintained from v0.1.

**Why**: DuckDB is one of the fastest in-process SQL engines on earth, with an active 50+ engineer team. We cannot compete, and we should not try. Our value is in the developer experience layer above the engine — not the engine itself.

**If DuckDB disappears**: Activate DataFusion swap interface (maintained in CI), build full adapter within 30 days per Composability Constitution §9.3.

---

## 2. Custom DataFrame Engine

**We will not build**: A DataFrame library, columnar memory format, or execution runtime.

**We wrap instead**: Polars (default). DataFusion DF (swap target).

**Why**: Same as SQL engine. Polars has 40K+ GitHub stars and a full-time team. The Arrow-native interface means swapping is safe.

---

## 3. Custom Orchestrator / Scheduler

**We will not build**: A DAG execution engine, task scheduler, sensor framework, or run lifecycle manager.

**We wrap instead**: Dagster (default, hidden behind `ctx`). `nucleus-mini-scheduler` (v1.0 fallback — built on-demand when trigger fires).

**Why**: Orchestration is a deeply complex problem (distributed state, failure recovery, partial failure, retry semantics). Dagster has solved this over years. Our job is to hide Dagster behind a clean interface so users never see it — not to re-implement it.

**Dagster replaceability** (D21): By v1.0, `nucleus-mini-scheduler` can run the same project unchanged, so Dagster is replaceable. But we don't ship mini-scheduler by default — Dagster wraps better.

---

## 4. Custom Iceberg Catalog or Commit Service

**We will not build**: An Iceberg catalog server, REST catalog implementation, distributed transaction coordinator, or Iceberg commit service.

**We use instead**: Filesystem catalog (v0.1), Lakekeeper (v0.3+), Apache Polaris (swap target).

**Why**: Atomic Iceberg commits are a hard distributed systems problem. Catalogs (Lakekeeper, Polaris, AWS Glue, Unity Catalog) exist specifically to handle this. Building our own would be a 3-12 month distraction with no user-visible benefit.

**The Law**: Constraint #5 — "No custom Iceberg commit service / transaction coordinator."

---

## 5. Custom Auth / RBAC System

**We will not build**: User authentication, password management, identity federation, token issuance, RBAC engine, or permission checking system.

**We delegate instead**: OIDC providers (GitHub, Google, Okta, Azure AD, Keycloak, Authentik).

**Why**: Identity is a security-critical problem that requires years of expertise and ongoing maintenance. Delegating to OIDC means users keep their existing SSO, we avoid being a high-value security target, and we never store passwords.

**The Law**: Constraint #6 — "No custom auth system. Always delegate to OIDC."

---

## 6. ML Training Platform / Feature Store / Model Registry

**We will not build**: LLM training infrastructure, model serving, GPU scheduling, feature computation engines, or model version registries.

**We integrate instead**: LiteLLM (AI Copilot, wraps 100+ LLM providers). Lance (vector storage). No training, no serving.

**Why**: This is not Nucleus's category. We help build data products that *feed* ML systems. We use LLMs as tools (AI Copilot). We are not an MLOps platform.

---

## 7. Custom Connectors at Scale (dlt handles this)

**We will not build**: 100+ custom connector implementations for external data sources.

**We wrap instead**: `ctx.copy_from` (v0.1, ~200 LOC, handles SQLite/Postgres/MySQL). dlt verified sources (v0.3+, 100+ sources). Sling / Singer as swap targets.

**Why**: Connectors are an unbounded long tail. dlt has a verified-source ecosystem with tests. We build the dispatch and error translation layer on top of dlt, not the connectors themselves.

---

## 8. Custom Notebook Runtime

**We will not build**: A notebook execution engine, cell scheduler, or reactive computation graph.

**We wrap instead**: Marimo (v0.3+). Jupyter (swap target, via Marimo compatibility).

**Why**: Marimo already solves the "reactive, reproducible notebook" problem elegantly. Integration is ~150 LOC CLI command + `ctx.read` bridge.

---

## 9. Custom Vector Database

**We will not build**: A vector indexing system, HNSW implementation, or ANN search engine.

**We use instead**: Lance format (vector storage). LanceDB (optional — higher-level vector API on top of Lance).

**Why**: Lance is Tier 0 immortal (ASF-inspired governance, open spec). LanceDB wraps Lance with production vector search. We don't need to build either.

---

## 10. BI Tool or Notebook Front-End

**We will not build**: A business intelligence tool, dashboard builder, chart library, or data visualization system.

**We integrate with instead**: Any BI tool that reads Iceberg (Tableau, Superset, Looker, Metabase, etc.) via Mode 1 graduation.

**Why**: BI is a solved problem. Our job is to produce Iceberg tables that BI tools can read — not to replace the BI tools.

---

## 11. Plugin Marketplace (v1.x)

**We will not build**: A public plugin SDK, plugin registry, or connector marketplace before v2.0.

**Why**: Internal interfaces must be battle-tested before being published as a public extension surface. Premature plugin SDKs create backward-compat debt that traps the architecture. No public plugin SDK until v2.0 review.

---

## 12. Multi-Tenant SaaS at Hyperscale

**We will not build**: A multi-tenant shared-infrastructure SaaS at Databricks/Snowflake scale.

**We are instead**: Single-tenant managed service (v0.7), with OSS self-hosted as the primary path. Enterprise multi-tenant is v2.0+ territory, and even there we yield to giants for actual hyperscale.

**Why**: This isn't the beachhead, and we don't have the operational team to run hyperscale SaaS. If a user needs that, they graduate to Databricks/Snowflake via Mode 1.

---

## 13. Forbidden Framings (Not Just Features — Framings Too)

These are not just non-goals — they are banned descriptions of the product:

| Banned framing | Why banned |
|---|---|
| "Data OS" | Implies owning every layer; we rent from OSS |
| "Spark killer" | We yield to giants; Spark users graduate to giants |
| "Databricks killer / replacement" | We integrate with Databricks via Mode 1/2 |
| "Universal compute platform" | We wrap DuckDB; we don't build compute |
| "AI-native platform" | We are AI-*assisted*; AI features are a layer, not the category |
| "AI-native data CLI" | Retired per ADR-002 (Angle C) |
| "Agent data substrate" | Retired per ADR-002 (Angle D) |
| "Iceberg company" | We use Iceberg; we are not an Iceberg vendor |
| "Plugin marketplace" (v1.x) | No public plugin SDK before v2.0 review |
| "Better Databricks" | We are *different*, not better-of-the-same |

---

## How to Propose a Reconsideration

If you believe a non-goal should be reconsidered:

1. Open a GitHub Discussion (not a PR).
2. Apply the 8-question gate from [`overview.md`](overview.md).
3. Cite which of the Five Pillars this serves without harming others.
4. Propose an ADR draft.
5. Wait for founder response before writing any code.

The default answer is "no." The bar for moving something off the non-goals list is very high.

---

*Source: `nucleus_architecture_v4.1.md` §20, `AGENTS.md §4`, `AGENTS.md §8`. ADR-001 (no Iceberg commit service), ADR-010 (no custom auth).*
