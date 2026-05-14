# Nucleus — Architecture v4.1

**Single Source of Truth · Locked Scope · Supersedes v4.0**

> **Ship data products from a laptop.** A local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks, built on open Apache foundations, AI-ready by design. Grows with your team. Graduates cleanly to any Iceberg catalog (Polaris, Lakekeeper, Unity, R2) — or to Databricks/Snowflake — when you outgrow your laptop.
>
> *(Positioning amendment 2026-05-12, per ADR-002 §8: "AI-assisted by design" demoted from marketing headline to engineering pillar; new outcome-first tagline hierarchy adopted; "Iceberg" moves from L1 headline to L2 sub-headline.)*

---

## Document Status

| Field | Value |
|---|---|
| Version | 4.1 |
| Status | **Locked** — PoC validation starts now; v0.1 implementation gated on PoC results |
| Supersedes | `nucleus_architecture_v4.0.md`, `nucleus_architecture_v3.md`, `final_architecture.md`, `architecture_design_conversation.md` |
| Audience | Senior data platform engineers, solution architects, founding team |
| Reading time | ~50 minutes |
| Companions | `nucleus_ctx_sdk_spec.md`, `nucleus_asset_model_spec.md`, `nucleus_project_anatomy.md`, `nucleus_cli_spec.md`, `nucleus_poc_plan.md`, `nucleus_implementation_readiness.md`, `nucleus_red_team_review.md` |

Any future architectural change MUST explicitly amend a section in this document.

---

## Changelog

### v4.1.3 patches (post-positioning-review, May 2026)

Four patches applied after the founder approved ADR-002 (Mid-2026 Strategic Refresh). Two independent reviewer passes converged on ACCEPT with refinements. **No architectural change — positioning, sequencing, and catalog co-default only.**

| # | Patch | Section | Source |
|---|---|---|---|
| P1 | **Thesis epigraph rewritten** to outcome-first tagline hierarchy (L1: "Ship data products from a laptop"; L2: "Python SDK + CLI for Iceberg-native pipelines"). "AI-assisted by design" demoted from marketing headline to engineering pillar (still §2 pillar #3). | Document epigraph | ADR-002 §8.1 |
| P2 | **Apache Polaris elevated to co-default with Lakekeeper at v0.3+**, justified by ASF Top-Level Project graduation Feb 18, 2026. Lakekeeper retained for Rust-fit deployments. | §5.7 | ADR-002 §4.2 |
| P3 | **Mo 24 explicit decision gate** with 4-condition trigger checklist (auto-fires if any of: 0 paying after 3 mo beta, <10 active teams after 6 mo OSS, founder velocity <3 features/month for 60 days, or funded competitor ships equivalent). Mo 28-36 v1.0 GA is best-case-only, contingent on Mo 24 decision. | §17.2 | ADR-002 §8.3 |
| P4 | **`nucleus-mcp-server` (~500 LOC) added to v0.5 roadmap** as agent-substrate hedge. Exposes assets / contracts / lineage to MCP-compatible agents via `ctx`. Does not pivot Nucleus into the agent-substrate category — purely additive thin adapter. | §18.4 | ADR-002 §4.2 |

Plus: **"data product" defined explicitly** in `README.md` and `AGENTS.md §0` as *Iceberg-backed asset with transformations + contracts + lineage, consumable by BI / applications / AI agents via `ctx` or MCP*. Wraps `§12.1` *asset* definition for external-facing copy.

Tagline locking deferred to PoC #5 external-tester field test per ADR-002 §8.4.

**Evening-pass follow-up (2026-05-12).** Worker B's drift sweep (`docs/audits/positioning_drift_2026-05-12.md`) surfaced 2 items the initial v4.1.3 apply log missed: (a) `docs/architecture/C4_context.md:29` Mermaid label still carried the pre-v4.1.3 thesis — fixed; the initial ADR-002 §8.6 apply log didn't include C4 diagrams. (b) `§1.2` trend table row 6 contained `"AI-native data contracts"` (banned vocab per `scripts/check_vocabulary.py`) — renamed to `"AI-assisted contract authoring"`; this was a pre-existing drift, not caused by v4.1.3, but fixed opportunistically since v4.1 was being touched. ADR-002 §8.6.1 carries the extended apply log. <!-- banned-term: AI-native -->

**Alignment sweep #1 follow-up (2026-05-13).** Worker R's research (`docs/research/lance.md` §9 item 7 + §10 risk #4) flagged that §4 Tier 0 row 4 claimed Lance is *"Linux Foundation aligned"* — no public LF announcement enumerates Lance as of 2026-05-13. Phrasing downgraded to *"ASF-inspired governance, open spec"* (the verifiable claim per Lance's three-tier PMC/Maintainers/Contributors model + the `lance-format/lance` repo separation from LanceDB Inc.'s commercial brand). Tier 0 case stands on Lance's other 6 qualifications (`docs/research/lance.md` §9 items 1-6); only the marketing phrasing changed.

**Alignment sweep #2 — storage substrate update (2026-05-13).** Per [`docs/decisions/ADR-008-storage-substrate-v01.md`](docs/decisions/ADR-008-storage-substrate-v01.md) (PROPOSED), §5.8 Object Store amended to document a dual-track docker-compose: SeaweedFS (Apache-2.0, actively maintained) becomes the documented default; the archived MinIO `RELEASE.2025-10-15T17-29-55Z` (AGPLv3) is preserved as opt-in alternate via `docker-compose.minio.yml`. Trigger: `github.com/minio/minio` archived 2026-04-25 + ADR-007 AGPLv3 Tier 2 YELLOW + AGENTS.md §9 Stop Condition. Nucleus's S3-API-agnostic hot path (s3fs + pyiceberg + DuckDB httpfs) is unchanged — propagation is documentation + compose YAML only. Cross-refs updated in `README.md` (quickstart), `SETUP.md` (§M3 Docker), `docs/research/minio.md` (status header → ALTERNATE), `docker-compose.yml` + `docker-compose.minio.yml` (NEW stubs at repo root pending ADR-008 acceptance — `NEEDS VERIFICATION` markers on SeaweedFS exact tag pin + S3 API parity edge cases, both retired by PoC #4).

**Alignment sweep #2 — catalog wording refinement (2026-05-13).** Per [`docs/decisions/ADR-004-catalog-migration-v01-to-v03.md`](docs/decisions/ADR-004-catalog-migration-v01-to-v03.md) (PROPOSED), §5.7 catalog wording refined from v4.1.3 P2's "Polaris co-default" (deferred at ADR-002 §4.2) to ADR-004's resolved split: **Lakekeeper documented default** (Rust, ~100-300 MB idle, ~1-2 s cold-start, OIDC-validation-only — never issues tokens) + **Polaris alternate** via `nucleus enable polaris` (JVM, ~500 MB-1.5 GB idle, ASF TLP governance signal, native federation to Snowflake / Databricks / Glue). Both run identically through `pyiceberg.RestCatalog`; v0.1 `pyiceberg.SqlCatalog` (filesystem) remains supported indefinitely (no one is stranded). Mo 24 founder gate (ADR-002 §8.3) preserves the option to flip the documented default with no code change. No architectural change — wording sharpened on top of v4.1.3 P2 to converge on the operationally-superior default for the beachhead while honouring procurement-sensitive ASF governance for Mo 20+ customer-pilot scenarios.

### v4.1.2 patches (post-drift-detection audit)

Two patches applied after the Drift Detection Audit (May 2026). Both align
architecture text with shipped reality — no semantic change to behavior.

| # | Patch | Section | Source |
|---|---|---|---|
| P1 | **§3.1 layer numbering harmonized to bottom-up (L0=Physics, L4=Experience)** to match implementation (`src/nucleus/` package structure, `scripts/check_layering.py`, `engineering.md` §3.1, `docs/architecture/C4_container.md`, README). No semantic change. | §3.1, §3.2, §4–§8 titles | Drift Detection Audit |
| P2 | **§17.2 timeline expanded for solo-founder pacing** — v0.1 Mo 2-8, v0.2 Mo 8-14, v0.3 Mo 14-20, v0.5 Mo 20-28, v1.0 GA Mo 28-36. Supersedes v4.1's original 14-18 mo v1.0 estimate. Formalizes the README's timeline as source of truth. | §17.2, §18.1–§18.5 | Drift Detection Audit |

### v4.1.1 patches (post-final-review polish)

Four patches applied after the v4.1 review round (3 senior engineers all returned GO verdicts). These are NOT architectural changes — they are discipline tightening.

| # | Patch | Section | Source |
|---|---|---|---|
| P1 | Native `ctx.sql` scope ceiling (≤2500 LOC, no macro ecosystem, no semantic layer, no adapter framework) | §5.6.0 | Reviewer #2 — "accidentally rebuilding dbt" warning |
| P2 | Moat clarification: Felt Moat (friction elimination) vs Technical Edge (AI integration depth) | §2.1 | Reviewer #2 — precise identification of what users actually buy |
| P3 | PoC #5 external testers mandatory (not founding team) | `nucleus_poc_plan.md` §5 | Reviewer #1 — workaround bias methodological point |
| P4 | Appendix B reordered by urgency: only Q1 (cloud arch) blocks NOW; Q3 (Workbench tech) blocks v0.2 design; rest can wait | Appendix B | Reviewer #1 — accurate triage |

Plus: **Q1 answer recorded** — Multi-tenant for v1.0 Cloud (single-tenant tier as v1.5+ enterprise upsell).

**Architecture is now frozen.** No further changes before PoC #1 starts.

### v4.0 → v4.1 amendments

| # | Amendment | Section Affected | Rationale |
|---|---|---|---|
| 1 | **Drop "Iceberg Commit Service"** → replace with thin Asset Materialization Adapter | §6.2 | Catalog (Lakekeeper/Polaris) already handles atomic commits. Building our own = distributed transaction coordinator we don't need. |
| 2 | **Stage AI Copilot realistically** (v0.1 = chat only; schema/lineage features deferred to v0.3-v0.5) | §7.2 | "Lineage-aware refactoring" is 2-3 months alone. Over-promised in v4.0. |
| 3 | **Composability = clean interfaces + smoke tests** (not maintained second implementations) | §9.3 | Avoid "Composability Tax". 30-day crisis-response viable with interface + smoke test combo. |
| 4 | **Defer Lakekeeper to v0.3** (v0.1 uses filesystem catalog via pyiceberg) | §5.7 | One fewer operational domain in v0.1 boot. Filesystem catalog is enough for single-node. |
| 5 | **Asset-level lineage in v0.1** (column-level deferred to v0.5+) | §12.4 | 90% of users only need "what depends on X table?". Column lineage is rabbit hole. |
| 6 | **Native `ctx.sql()` with Jinja** replaces dbt-duckdb as v0.1 default | §5.6 | dbt-duckdb is community-maintained, fragile. ~1000 LOC native resolver beats integration burden. |
| 7 | **Add Error Translation Discipline** (no Dagster object leaks to user) | §6.4 (new) | Leaky abstraction kills the "wrap" thesis. Mandatory release blocker. |
| 8 | **Soften "frozen v1.0 SDK"** policy (AI-related APIs may evolve faster than core data APIs) | §13.3 | AI paradigms evolve quickly; can't freeze for 5+ years. |
| 9 | **No custom auth ever** — always delegate to OIDC | §15.1 | Nucleus is not an identity company. Don't own identity. |
| 10 | **Pick beachhead persona explicitly** (startup data team 5-20 engineers) | §1.5 (new) | Cannot serve 4 personas simultaneously with 2-5 engineers. |
| 11 | **Cut v0.1 scope ~40%** + split into v0.1 "Hello World" + v0.2 "Developer Experience" | §18.1, §18.2 | Honest 4-month + 4-month milestones; checkpoint at month 4. |
| 12 | **Stronger Dagster replaceability mandate** (replaceable by v1.0 without user code changes) | §6.5 (new) | Prevents Dagster mental-model capture. |
| 13 | **Connector UX "wow" requirement** — even without dlt, `nucleus ingest postgres://...` must feel modern | §1.5 + §5.6.1 (new) | Local-first story is weak without one-liner ingestion. ~200 LOC `ctx.copy_from()` helper. |

---

## TL;DR

Nucleus is a **modern data engineering platform** that fixes long-standing pain points of building and operating data products. Five layers:

1. **Physics** — immortal Apache standards (Arrow, Iceberg, Parquet, Lance, S3)
2. **Engines** — composable, swappable OSS (DuckDB, Polars; Daft optional)
3. **Coordination** — wrapped Dagster substrate, hidden behind `ctx`
4. **Intelligence** — AI-assisted authoring + debugging (the differentiating layer)
5. **Experience** — `ctx` SDK + CLI + Workbench + Marimo (the unified UX)

**Local-first** (boot in <10s on laptop), **composable by constitution** (every dependency has a clean swap interface), **friendly to giants** (Iceberg portability lets users graduate to Databricks/Snowflake without migration).

We do **not** build a database, SQL engine, DataFrame engine, orchestrator, Spark replacement, or Databricks competitor. We integrate best-of-breed open source into one coherent product, and add the AI-assisted experience the modern data stack is missing.

**License**: Apache 2.0. **Distribution**: OSS core + managed cloud + premium copilot + enterprise tier.

**Beachhead persona (v0.1-v1.0)**: Startup data team (5-20 engineers, 100GB-5TB total data, greenfield project).

**v0.1 success metric**: A 5-engineer startup team, on MacBooks, with Postgres source + S3, builds their first BI-ready Iceberg table from `git clone` in **<30 minutes**.

---

## Table of Contents

1. [Positioning](#1-positioning)
2. [Five Pillars](#2-five-pillars)
3. [Architecture Overview](#3-architecture-overview)
4. [Layer 0: Physics](#4-layer-0-physics)
5. [Layer 1: Engines](#5-layer-1-engines)
6. [Layer 2: Coordination](#6-layer-2-coordination)
7. [Layer 3: Intelligence](#7-layer-3-intelligence)
8. [Layer 4: Experience](#8-layer-4-experience)
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

These 15 pains have existed for 10-20 years. Big players have **no incentive** to solve them (complexity is their revenue).

| # | Pain | Nucleus addresses via | When |
|---|---|---|---|
| 1 | Data quality reactive | Active contracts engine (schema in v0.1; quality rules v0.5+) | v0.1-v0.5 |
| 2 | Lineage is metadata not enforcement | Asset-level enforced at write; column-level v0.5+ | v0.1, expanded v0.5 |
| 3 | Local development hell | `nucleus up` boots in <10s | v0.1 |
| 4 | Onboarding 6+ weeks | AI Copilot with project context | v0.2+ |
| 5 | Cross-team coordination breaks | Asset contracts + producer/consumer registry | v0.5+ |
| 6 | 3am debugging | Replay debugger + AI RCA | v0.7+ |
| 7 | Cost surprises | Per-asset cost meter | v0.5+ |
| 8 | MDS incoherent (15 tools) | One platform, one UX, one auth | v0.1+ |
| 9 | AI/ML and BI separate | Iceberg + Lance unified | v0.5+ |
| 10 | Notebook drift from prod | Marimo + asset model on same engine | v0.3+ |
| 11 | Backfills are terror | Replay debugger predicts cost + impact | v0.7+ |
| 12 | Privacy/governance bolted on | First-class primitives | v1.5+ |
| 13 | Tests run AFTER bad data | Pre-commit contracts | v0.1, AI-generated v0.5 |
| 14 | Cold start = days | `nucleus init` + scaffolding | v0.1 |
| 15 | Skill barrier extreme | AI Copilot lifts junior productivity | v0.2+ |

### 1.2 The AI-Era Trends (Designed for, Not Reacting to)

| # | Trend | Nucleus design response |
|---|---|---|
| 1 | LLMs writing/debugging/operating pipelines | Asset DSL designed for LLM comprehension |
| 2 | Multimodal first-class | Iceberg + Lance, Daft optional |
| 3 | Vector + relational convergence | Unified query plane |
| 4 | Real-time + batch convergence | One asset model for both |
| 5 | Natural language as primary interface | Workbench Copilot from v0.2 |
| 6 | AI-assisted contract authoring | LLM-drafted, human-reviewed (v0.5+) |
| 7 | Synthetic data + privacy | Differential privacy primitives v1.5+ |
| 8 | "Vibe coding" data pipelines | `ctx.agent` runtime v0.5+ |

### 1.3 Where We Sit

| Category | Examples | Our relationship |
|---|---|---|
| Hyperscale lakehouses | Databricks, Snowflake | **Graduate to**, not compete |
| Modern data stack | Fivetran + dbt + Airflow + Atlan + Soda + Snowflake | **Replace 4-6 in one platform** for small/mid teams |
| New OSS engines | Daft, Lance, DataFusion, DuckDB, Polars | **Wrap**, never compete |
| AI coding tools | Cursor, Copilot | **Port the model** to data engineering |
| Notebook tools | Hex, Mode, Marimo | **Integrate Marimo**, don't compete |

We are the **integrator** and **AI-aware UX layer**, not another engine.

### 1.4 Personas We Serve (Long-Term)

| Persona | Profile | Total data | When primarily served |
|---|---|---|---|
| Solo data engineer / consultant | 1-5 person | <100GB | v0.1 (incidental) |
| **Startup / mid-market data team** | **5-50 engineers** | **<10TB** | **v0.1-v1.0 (BEACHHEAD)** |
| Enterprise domain team (Data Mesh) | Domain-owned product | 1-10TB per domain | v1.5+ |
| Enterprise central pipeline | 1000+ engineers, 10-100TB monolith | >10TB cross-partition | v2.0+, via Mode 2 dispatch |

We **do not** serve hyperscale (>100TB single-pipeline, FAANG-tier).

### 1.5 The Beachhead (v0.1 through v1.0)

**v0.1 through v1.0 serves exclusively: Startup data team — 5-20 engineers, 100GB-5TB total data, greenfield project, no existing data platform.**

Other personas (solo consultant, enterprise domain, enterprise central) are addressable but **not designed for**. Their feedback is welcome but does not drive priorities until v1.5+.

**v0.1 success metric:**

> A 5-engineer startup team, on MacBooks, with Postgres source + S3 destination, builds their first BI-ready Iceberg table from `git clone` to live data in **<30 minutes**.

**This metric drives every v0.1 decision.** Any feature that doesn't serve this metric is deferred.

**Implication for connector UX:** Even without full dlt integration, the platform MUST support a one-liner ingestion experience:

```bash
nucleus ingest postgres://user:pass@host/db --table public.orders
```

That command must:
- Auto-infer schema from source
- Auto-create Iceberg destination table
- Pull rows + commit atomically
- Show preview after completion

If `nucleus ingest` requires Python code, README reading, or external tools, the 30-minute promise breaks. **This is non-negotiable.**

### 1.6 What We Are NOT

- ❌ A database
- ❌ A SQL engine
- ❌ A DataFrame engine
- ❌ An orchestrator (Dagster is our substrate, hidden)
- ❌ A Spark replacement
- ❌ A Databricks competitor
- ❌ A "Data OS" <!-- banned-term: Data OS -->
- ❌ A universal compute platform
- ❌ An AI/ML training platform
- ❌ A vector database (we use Lance/LanceDB)
- ❌ A BI tool (we surface dashboards but don't build a Tableau)
- ❌ An identity / auth company
- ❌ A distributed transaction coordinator

We own three things, forever:

1. The **asset graph** (logical model of data products)
2. The **`ctx` SDK** (the developer contract)
3. The **unified AI-assisted experience** (CLI + Workbench + SDK as one product)

Everything else is rented from open source.

---

## 2. Five Pillars

| # | Pillar | Concrete manifestation |
|---|---|---|
| 1 | **High performance on minimal resources** | DuckDB + Polars. Boot in <10s. 100M-row aggregation <2s on laptop. Idle <500MB. |
| 2 | **Composable by constitution** | 3-tier dependency classification. Clean interfaces + basic smoke tests. Full swap built on-demand. Apache-grade only for Tier 0. |
| 3 | **AI-assisted by design** | Workbench Copilot from v0.2. Asset DSL LLM-comprehensible. `ctx.agent` runtime v0.5+. |
| 4 | **Familiar UX from proven giants** | dbt SQL feel. Dagster asset graph (hidden). Cursor IDE patterns. No reinvented vocabulary. |
| 5 | **Friendly to giants, hostile to no-one** | Iceberg portability. Mode 1/2/3 integration with Databricks/Snowflake. Apache 2.0 license. |

### 2.1 Moat Clarification

There are two distinct concepts that should not be confused:

| Concept | What it is | Where it lives |
|---|---|---|
| **The Felt Moat** | What users perceive as the platform's value: **friction elimination** — `git clone → first table in <30 min`, local-first identical-to-prod, one coherent UX vs 15 disjoint tools | Layer 1 (Experience) + cross-layer integration |
| **The Technical Edge** | What compounds over years and is hard to replicate: **AI-assisted authoring/debugging/operations** integrated with full asset graph, lineage, contracts, schemas | Layer 2 (Intelligence) |

**The Felt Moat is what closes deals.** Users say "Nucleus feels coherent" not "Nucleus has AI". They might appreciate AI features, but they BUY because friction is gone.

**The Technical Edge is what builds defensibility over 3-5 years.** As LLMs improve, our integration depth (asset graph context, lineage navigation, contract awareness) becomes the differentiator. Bolt-on AI tools can't match this without rebuilding the whole platform.

**Implication for v0.1-v0.5:** Spend most effort on Felt Moat. Layer 2 (Intelligence) gets thin scope (just AI chat in v0.2) until Felt Moat is proven. Don't lead with AI marketing.

---

## 3. Architecture Overview

### 3.1 The Five Layers

> **Numbering**: bottom-up, **L0 = Physics, L4 = Experience**. This matches the
> shipped implementation (`src/nucleus/` package structure, `scripts/check_layering.py`,
> `engineering.md` §3.1, `docs/architecture/C4_container.md`, README).

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 4: EXPERIENCE                                            │
│  • ctx SDK (Python) — the only public API                       │
│  • nucleus CLI                                                  │
│  • Workbench — web IDE with AI Copilot (v0.2+)                  │
│  • Marimo notebooks (v0.3+)                                     │
│  • Portal (v0.5+)                                               │
└──────────────────────────────┬──────────────────────────────────┘
                               │ ctx SDK (stable contract)
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 3: INTELLIGENCE                       ⭐ DIFFERENTIATOR  │
│  • Inline AI chat (v0.2)                                        │
│  • Schema-aware completion (v0.3)                               │
│  • ctx.agent runtime (v0.5)                                     │
│  • Lineage-aware refactoring (v0.5)                             │
│  • Semantic knowledge graph (v0.7)                              │
│  • Cost-aware execution planner (v0.7)                          │
│  • Replay & time-travel debugger (v0.8)                         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 2: COORDINATION                                          │
│  • Asset graph (Dagster substrate, hidden)                      │
│  • Asset Materialization Adapter (thin, ~500 LOC)               │
│  • Error Translation Layer (mandatory)                          │
│  • Contracts engine (schema v0.1; quality v0.5+)                │
│  • Lineage (asset-level v0.1; column-level v0.5+)               │
│  • Auth (OIDC delegation; local-only in v0.1)                   │
│  • Cost meter (v0.5+)                                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 1: ENGINES                                               │
│  • SQL: DuckDB (default) → DataFusion (swap interface)          │
│  • DataFrame: Polars (default) → DataFusion DF (swap interface) │
│  • Multimodal: Daft (v0.5+, optional)                           │
│  • Vector: Lance / LanceDB (v0.5+)                              │
│  • Ingestion: ctx.copy_from helper (v0.1); dlt (v0.3+)          │
│  • Transformation: native ctx.sql + Jinja (v0.1); dbt opt v0.3+ │
│  • Catalog: filesystem (v0.1); Lakekeeper (v0.3+); Polaris swap │
│  • Object store: MinIO (local) / cloud S3 (prod)                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│  LAYER 0: PHYSICS                                               │
│  • Apache Arrow                                                 │
│  • Apache Iceberg                                               │
│  • Lance (v0.5+)                                                │
│  • Apache Parquet                                               │
│  • S3 API                                                       │
│  • OpenLineage                                                  │
│  • OpenTelemetry                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer Responsibilities

| Layer | Responsibility | Mutability |
|---|---|---|
| L4. Experience | Human + AI interaction surface | Evolves with users |
| L3. Intelligence | AI moat — context, planning, copilot | Continuously refined |
| L2. Coordination | Platform brain — graph, contracts, lineage | Stable from v1.0 |
| L1. Engines | Compute kernels — replaceable | Swap on-demand |
| L0. Physics | Laws — open standards | Immortal |

---

## 4. Layer 0: Physics

The **immortal** layer. Open standards backed by multi-vendor consortiums. Zero death risk.

### 4.1 Components

| Component | Purpose | Why immortal |
|---|---|---|
| Apache Arrow | In-memory columnar format | Snowflake, Databricks, Meta, Google back it |
| Apache Iceberg | Structured table format (ACID, time travel) | Apache; Netflix, Apple, AWS, Snowflake, Databricks committers |
| Lance | Multimodal + vector tables (v0.5+) | ASF-inspired governance, open spec |
| Apache Parquet | Column file format | De facto standard 10+ years |
| S3 API | Object storage protocol | Universal: MinIO, SeaweedFS, R2, GCS, Azure |
| OpenLineage | Lineage protocol | Linux Foundation, multi-vendor |
| OpenTelemetry | Observability protocol | CNCF universal |

### 4.2 Constraints

- We **never** invent a format
- We **never** depend on a single-vendor "open standard"
- We track spec evolution and contribute upstream when needed

---

## 5. Layer 1: Engines

Best-in-class OSS engines. **Composed but never coupled.**

### 5.1 SQL Engine: DuckDB (Default) → DataFusion (Swap Interface)

| Aspect | DuckDB | DataFusion |
|---|---|---|
| Language | C++ | Rust |
| License | MIT | Apache 2.0 |
| Governance | DuckDB Labs | Apache Software Foundation |
| Performance (TPCH 10GB) | ~2.5s | ~3-5s |
| **Why default** | Faster, more polished | — |
| **Why swap target** | If DuckDB Labs pivots, DataFusion is Apache | — |

**Swap status (per Amendment 3):** Clean interface maintained + basic smoke tests (5-10 tests) running quarterly. **Full DataFusion adapter built on-demand** when license/health trigger fires.

### 5.2 DataFrame Engine: Polars (Default) → DataFusion DF (Swap Interface)

| Aspect | Polars | DataFusion DF |
|---|---|---|
| Language | Rust | Rust |
| License | MIT | Apache 2.0 |
| Governance | Pola.rs | Apache |
| **Why default** | Best single-thread perf + DX | — |

**Swap status:** Same as SQL engine — interface + smoke tests; full adapter on-demand.

### 5.3 Multimodal / AI Engine: Daft (Optional, v0.5+)

For:
- Distributed compute beyond single-node
- Native multimodal columns (images, embeddings, tensors)
- Python UDF performance at scale

**Optional from v0.5.** Default workloads stay on DuckDB+Polars.

### 5.4 Vector Storage: Lance / LanceDB (v0.5+)

For embeddings and AI feature storage. Hybrid queries with structured tables.

### 5.5 Ingestion

#### 5.5.1 v0.1: Native `ctx.copy_from` helper (NEW per Amendment 13)

Minimum viable ingestion, ~200 LOC using SQLAlchemy + pyiceberg:

```python
import nucleus
from nucleus import ctx

@nucleus.source()
def raw_orders(ctx):
    return ctx.copy_from(
        source="postgresql://user:pass@host/db",
        table="public.orders",
        mode="full_refresh",  # incremental in v0.3+
        target_partition="day",  # optional
    )
```

CLI equivalent (one-liner):

```bash
nucleus ingest postgres://user:pass@host/db --table public.orders --as raw.orders
```

Auto-infers schema, creates Iceberg destination, atomic commit, preview output.

**Supported sources in v0.1:** PostgreSQL, MySQL, SQLite, CSV, Parquet, JSON. (Five — keep small.)

#### 5.5.2 v0.3+: dlt integration

When users need 100+ connectors (Stripe, Salesforce, Hubspot, etc.), dlt is wrapped behind `@nucleus.source(engine="dlt")`. `ctx.copy_from` remains the simple default.

### 5.6 Transformation: Native `ctx.sql` + Jinja (Default) — Amendment 6

**v0.1 ships native SQL transformation, NOT dbt-duckdb.**

#### 5.6.0 Scope Ceiling (Discipline Boundary)

**The native `ctx.sql` resolver MUST stay within these hard limits:**

| Boundary | Limit | Rationale |
|---|---|---|
| Total LOC for resolver + Jinja + ref/source | **≤ 2500 LOC** | Trigger reconsideration if exceeded |
| Macro support | Built-in primitives only (date_trunc, dateadd, current_timestamp) + user-defined macros via `macros/` folder | NO macro package ecosystem |
| Adapter ecosystem | None | NOT building "nucleus-sql adapter for X" |
| Semantic layer | None | NOT building MetricFlow-equivalent |
| Tests framework | Via `@nucleus.check` only | NOT building dbt-tests-equivalent |
| Documentation generation | Deferred to v0.3 | NOT in v0.1 |
| Snapshots (SCD Type 2) | Deferred to v0.5 | NOT in v0.1 |

**If we drift past these limits, we are "accidentally rebuilding dbt" — STOP and integrate dbt-duckdb instead.**

This discipline boundary protects against the most common failure mode of OSS data platforms: scope creep into adjacent ecosystems they're not equipped to maintain.

```python
@nucleus.sql_asset
def fct_orders(ctx):
    return ctx.sql("""
        SELECT 
            order_id,
            customer_id,
            amount
        FROM {{ ref('raw.orders') }}
        WHERE status = 'completed'
    """)
```

| Capability | v0.1 native | dbt-duckdb |
|---|---|---|
| `{{ ref() }}` resolution | ✅ | ✅ |
| Jinja templating | ✅ | ✅ |
| Macros | ✅ basic | ✅ rich |
| Tests | ✅ via `@nucleus.check` | ✅ |
| Documentation generation | v0.3+ | ✅ |
| Materialization strategies (table/view/incremental) | ✅ | ✅ |
| Snapshots (SCD Type 2) | v0.5+ | ✅ |
| Custom hooks | v0.5+ | ✅ |

**Why native:** ~1000 LOC of code we own outright beats community-maintained adapter with release lag. dbt-duckdb becomes **optional integration** in v0.3 for teams migrating from dbt.

### 5.7 Catalog (Amendment 4 — revised by v4.1.3 P2; refined by ADR-004)

| Stage | Catalog |
|---|---|
| **v0.1** | **Filesystem catalog via pyiceberg (`pyiceberg.SqlCatalog`)** — zero external service. Supported indefinitely per ADR-004 (no one is stranded). |
| **v0.3+ (per [ADR-004](docs/decisions/ADR-004-catalog-migration-v01-to-v03.md))** | **Lakekeeper documented default** (Rust, ~100-300 MB idle, ~1-2 s cold-start, OIDC-validation-only) + **Polaris alternate** via `nucleus enable polaris` (JVM, ~500 MB-1.5 GB idle, ASF TLP). Both run identically through `pyiceberg.RestCatalog`; swap is a `nucleus_config.toml` `[catalog]` flip — no `coordination/` code changes per §9.3. v0.1 `SqlCatalog` remains supported. |
| v0.5+ | Unity Catalog OSS, Cloudflare R2 Data Catalog (swap interfaces with smoke tests only — on-demand full adapter per §9.3) |

This removes one operational domain from `nucleus up` in v0.1. Boot time and onboarding both benefit. ADR-004 (2026-05-13) resolved the v4.1.3 P2 "co-default" deferral on operational + governance grounds (Worker F + Worker H research, 2026-05-13): idle memory + cold-start dominate the beachhead, ASF governance + built-in Snowflake/Databricks/Glue federation surface at customer-pilot time (Mo 20+) not first-touch onboarding. Mo 24 founder gate (ADR-002 §8.3) can flip the documented default with no code change. Both catalogs are wrapped behind the same pyiceberg `Catalog` interface; `nucleus catalog migrate --from filesystem --to {lakekeeper|polaris}` (per `nucleus_cli_spec.md` §4.2) is metadata-only — Iceberg data files in S3 / SeaweedFS / MinIO stay put.

### 5.8 Object Store

| Environment | Object store |
|---|---|
| Local dev | **SeaweedFS (default, per [ADR-008](docs/decisions/ADR-008-storage-substrate-v01.md))** or MinIO (archived-upstream alternate) |
| AWS production | S3 |
| GCP production | GCS (S3-compatible) |
| Azure production | Azure Blob (S3-compatible via R2 / proxy) |
| Self-hosted | SeaweedFS (default) or MinIO (opt-in alternate) |

Code is identical across environments. Only `connections/storage.yml` changes.

**Storage substrate (v0.1, per [ADR-008](docs/decisions/ADR-008-storage-substrate-v01.md)):** dual-track docker-compose. SeaweedFS (Apache-2.0, actively maintained — release 2026-05-04 per Worker BB) is the documented default in `docker-compose.yml`; the archived MinIO `RELEASE.2025-10-15T17-29-55Z` (AGPLv3, `github.com/minio/minio` archived 2026-04-25) is preserved as alternate in `docker-compose.minio.yml` for teams with existing MinIO tooling. Nucleus's S3-API-agnostic code (`s3fs` + `pyiceberg` + DuckDB `httpfs`) works identically against either backend — no application-layer change. S3 API itself is Tier 0 immortal per §4.1 (*"Universal: MinIO, SeaweedFS, R2, GCS, Azure"*); the dual-track is purely documentation + compose YAML. PoC #4 + PoC #3 verify SeaweedFS parity (signature v4, path-style addressing, multipart thresholds) pre-ADR-008 acceptance.

### 5.9 Engine Selection Matrix by Workload

| Workload | Default engine path | Notes |
|---|---|---|
| SQL analytical query (<100GB) | DuckDB | Fastest |
| SQL analytical (100GB-2TB) | DuckDB | With Iceberg partition pruning |
| DataFrame transformation | Polars | Lazy + streaming |
| Multimodal (v0.5+) | Daft (optional) | Opt-in |
| Vector search (v0.5+) | LanceDB | Sub-second |
| Ingestion (DB → Iceberg) | `ctx.copy_from` (v0.1) / dlt (v0.3+) | — |
| Ingestion (high-volume bulk) | Sling (v0.5+) | `engine="sling"` |
| Streaming (v1.5+) | Benthos / Redpanda | Future module |
| Cross-partition full scan >10TB | **Dispatch to Databricks via Mode 2** | Not for us |

---

## 6. Layer 2: Coordination

Wrap Dagster. Do not build a scheduler.

### 6.1 What We Take from Dagster

| Capability | Dagster provides | We expose via |
|---|---|---|
| Asset graph topology | Yes | `@nucleus.asset` |
| Software-defined assets | Yes | Asset model |
| Sensors | Yes | `@nucleus.sensor` |
| Schedules | Yes | `@nucleus.schedule` |
| Backfills | Yes | `nucleus backfill` |
| Retries, runs, state | Yes | Internal |
| Web UI | Yes | **Hidden by default; exposed via `nucleus enable compat-dagster`** |

### 6.2 Asset Materialization Adapter (Amendment 1)

**v4.1 explicitly drops "Iceberg Commit Service" as a Nucleus-built component.**

Catalog (Lakekeeper/Polaris/filesystem-catalog) ALREADY handles:
- Atomic single-table commits
- Snapshot management
- Schema evolution
- Concurrent commit conflict resolution (optimistic concurrency)

Nucleus does NOT compete with this. Instead, a **thin Asset Materialization Adapter** (~500 LOC) does 5 things:

```
1. Pre-write: validate output against asset contract
2. Pre-write: enforce partition constraints
3. Delegate atomic write to Catalog (Lakekeeper/Polaris/filesystem)
4. Post-write: emit OpenLineage event
5. Post-write: update asset registry (run history, freshness, cost)
```

**Multi-table atomic transactions:** Deferred. Two paths:
- **v1.0+ approach:** Leverage Iceberg REST Catalog v2 multi-table commits when spec stabilizes
- **v2.0+ approach:** Optional Nessie integration for users needing branching

**Concurrency bottleneck risk: ZERO** because Nucleus doesn't sit on the critical write path. Catalog handles concurrency; Dagster handles inter-asset scheduling.

### 6.3 What We Add on Top of Dagster

| Capability | Why added |
|---|---|
| Asset Materialization Adapter | Pre-/post-write hooks + contract enforcement + lineage emission |
| Schema contracts engine | Active prevention (Dagster checks are post-hoc) |
| Asset-level lineage engine | Enforced at write time; column-level v0.5+ |
| Asset registry | Stable IDs, versioning, deprecation tracking |
| Error Translation Layer | Mandatory — see §6.4 |
| Unified RBAC | OIDC-delegated single auth model |
| Cost meter (v0.5+) | Per-asset attribution |

### 6.4 Error Translation Discipline (Amendment 7, NEW)

**Mandatory release blocker. No exceptions.**

All errors propagating from wrapped components (Dagster, DuckDB, Polars, dlt, pyiceberg) MUST be intercepted at the `ctx` SDK boundary and re-emitted as `NucleusError` subclasses with:

```python
class NucleusError(Exception):
    user_message: str            # Plain-language, in user vocabulary (asset names not op names)
    fix_hint: str                # Concrete next step (may be empty string)
    docs_url: str                # Reference URL on nucleus.dev/errors/<slug>
    asset: str | None            # The asset involved, if any
    cause: BaseException | None  # Original error preserved (also exposed via __cause__)
```

> **Note (v4.1.2 — superseded 2026-05-13 by ADR-006):** Stable **NE-prefixed** error codes ship in v0.1, **not** deferred to v0.5. Numbering scheme per [ADR-006](docs/decisions/ADR-006-nucleus-error-code-numbering.md): `NE1xxx` (Layer 0 Physics) · `NE2xxx` (Layer 1 Engines) · `NE3xxx` (Layer 2 Coordination) · `NE5xxx` (Layer 4 Experience). Layer 3 (Intelligence) reserved for v0.5+. Codes are paired with class names + URL slugs (e.g. `NucleusCommitConflictError = NE1002`, docs slug `/errors/commit-conflict`). 24 codes assigned in `src/nucleus/errors.py` as of 2026-05-13.

**Example translation:**

| Internal (Dagster) | Translated (Nucleus) |
|---|---|
| `dagster._core.errors.DagsterAssetMaterializationPlanningError: OpExecutionContext.materialize() failed for op fct_orders` | `NucleusInvalidAssetDefinition: Asset 'sales.fct_orders' failed to materialize. Suggested action: run 'nucleus describe sales.fct_orders' to inspect upstream dependencies. Docs: nucleus.dev/errors/invalid-asset` |
| `pyiceberg.exceptions.CommitFailedException: Concurrent modification` | `NucleusCommitConflictError: Could not commit changes to 'sales.fct_orders' due to a concurrent write. Suggested action: retry the run. If this persists, check for overlapping schedules. Docs: nucleus.dev/errors/commit-conflict` |
| `duckdb.duckdb.OutOfMemoryException: ...` | `NucleusResourceError: Out of memory while processing 'sales.fct_orders' (~5GB of data). Suggested action: add partition filter, increase machine memory, or use 'compute=databricks'. Docs: nucleus.dev/errors/resource` |

**Validation set (all 8 must translate cleanly):**

1. Asset materialization failure (Python exception)
2. SQL execution error (DuckDB error)
3. Out-of-memory crash
4. Iceberg commit conflict
5. Dependency asset not yet materialized
6. Schema mismatch (contract violation)
7. Timeout / cancellation
8. Concurrent write conflict

**Original cause** accessible via `--verbose` flag for advanced debugging.

**Leaky Dagster errors in user-facing surface = release blocker.**

### 6.5 Dagster Replaceability Mandate (Amendment 12, NEW)

> **Dagster MUST be replaceable internally by v1.0 without ANY user code changes.**

This is the proof that the abstraction is real, not a leak.

Concrete tests for replaceability:

| Test | Pass criteria |
|---|---|
| User code grep for `dagster` import | Zero results in user project |
| User code grep for Dagster types (`OpExecutionContext`, `AssetMaterialization`, etc.) | Zero results in user project |
| `nucleus-mini-scheduler` (fallback POC by v1.0) | Runs same project unchanged |
| Error translation coverage | 100% (no Dagster classnames in user-facing output) |

If any test fails before v1.0 GA, **release blocked.**

### 6.6 Progressive Disclosure of Dagster

| Tier | Default for | Dagster visibility |
|---|---|---|
| Tier 1 (95% users) | Standard data engineers | `ctx` SDK only. Dagster fully hidden. |
| Tier 2 (escape hatch) | Advanced patterns | `ctx.dagster_context` exposed. **Telemetry tracks usage.** If >5% of users use a specific escape hatch feature for >3 months, build native ctx equivalent. |
| Tier 3 (full power) | Migration from Dagster projects | `nucleus enable compat-dagster` exposes Dagster UI + classes directly. |

### 6.7 Fallback If Dagster Goes Hostile

`nucleus-mini-scheduler` design ready (~3-5K LOC):
- Asset graph in SQLite (PostgreSQL prod)
- Cron + retry queue
- Basic sensors via polling

Migration: 30 days. Lost capabilities: advanced backfill UI, some sensor types, dynamic partitioning. Public `ctx` API: **unchanged**.

Documented in `/docs/swap/dagster.md`.

---

## 7. Layer 3: Intelligence

**The differentiator.** Designed for LLM comprehension from the start.

### 7.1 Design Principle

Every part of Nucleus is engineered for LLM comprehension and operation:

- Asset DSL has rich type annotations, docstring conventions, predictable patterns
- Errors are structured (see §6.4), machine-parseable, suggest fixes
- Lineage queryable as graph
- `ctx` SDK introspectable

### 7.2 AI Copilot Staging (Amendment 2 — REALISTIC)

| Stage | Capability | Effort estimate |
|---|---|---|
| **v0.1** (Mo 0-4) | None — no Copilot in Hello World release | 0 |
| **v0.2** (Mo 4-8) | **Inline AI chat in Workbench** — Claude API + project file context (no schema introspection) | 4 weeks |
| **v0.3** (Mo 8-11) | Schema-aware completion + asset-aware suggestions | 6 weeks |
| **v0.5** (Mo 11-14) | Lineage-aware refactoring + AI test generation | 10 weeks |
| **v0.7** (Mo 14-18) | Doc generation, semantic graph queries | 8 weeks |

This is honest. v4.0's "lineage-aware refactoring in v0.1" was a 2-3 month feature bundled into a 6-month milestone with 5 other 2-month features. Impossible.

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
- Agent cannot modify Tier 0 standards or core configs
- Agent cannot commit without human approval
- Agent cannot access production secrets
- All agent actions logged in audit trail

### 7.4 v0.7+ Capability: Semantic Knowledge Graph

Nodes: assets, columns, contracts, sensors, schedules, owners, business terms.
Edges: depends_on, produces, contracts_with, owned_by, semantically_means.

Natural language queries:
- "Which dashboards depend on `raw.stripe.charges`?"
- "Find all assets containing PII"
- "Show me revenue-related assets and their freshness"

### 7.5 v0.7+ Capability: Cost-Aware Planner

Pre-run estimates: CPU-seconds, S3 GETs, egress, AI tokens. Output: dollars per run + cumulative forecast.

### 7.6 v0.8+ Capability: Replay & Time-Travel Debugger

Every run snapshotted (code git hash, input snapshots, config, output). Replay any historical materialization with current code or historical code. Query any asset "as of" any past timestamp.

### 7.7 Why This Layer Is the Moat

| Reason | Explanation |
|---|---|
| **Built-in, not bolt-on** | dbt Copilot, Hex Magic are bolt-on. We have AI access to full lineage, contracts, schemas, history. |
| **Composable, not coupled** | Works with Claude, GPT, local Llama via OpenAI-compatible API |
| **Replicable trust** | Sandbox + audit + human-approval. No "AI YOLO into production". |
| **Compounds with usage** | Every asset's code, schema, contract, run history feeds context |

---

## 8. Layer 4: Experience

### 8.1 Surfaces by Release

| Surface | v0.1 | v0.2 | v0.3 | v0.5 |
|---|---|---|---|---|
| `ctx` SDK | ✅ Core (read/write/sql/log) | ✅ + metrics/secrets | ✅ + params/agent | ✅ Full |
| `nucleus` CLI | ✅ init/up/run | ✅ + test/list/describe | ✅ + ingest/deploy | ✅ Full |
| Workbench | ❌ | ✅ Monaco + asset list + chat | ✅ + schema-aware Copilot | ✅ Full IDE |
| Marimo | ❌ | ❌ | ✅ Integration | ✅ |
| Portal | ❌ | ❌ | ❌ | ✅ Catalog + lineage |

### 8.2 Design Principles

| Principle | Manifestation |
|---|---|
| One mental model | Everything is an asset. No "tasks", "jobs", "notebooks-vs-pipelines" split. |
| Familiar vocabulary | Standard data engineering terms only |
| Progressive disclosure | Beginners → Workbench. Power users → CLI+SDK. Advanced → escape hatches. |
| AI-aware by default (v0.2+) | Copilot in every text input. LLM-friendly Asset DSL. |
| Local-first | Works offline (except cloud-specific features) |

### 8.3 Reference UX Patterns Borrowed

| Pattern from | What we borrow |
|---|---|
| dbt | SQL-first project layout, `ref()` resolution, model materialization |
| Dagster | Asset graph mental model, sensors, schedules |
| Cursor | AI-aware editor with project-wide context |
| Vercel | Deploy via single command, zero-config defaults |
| Supabase | Local dev = identical to prod, one tool for everything |
| Linear | Fast, keyboard-first, beautifully designed |
| Marimo | Reactive deterministic notebooks |

---

## 9. Composability by Constitution

**Design Law #1.** Supersedes all other laws.

### 9.1 The Constitution

> The user depends on the `ctx` SDK and the Iceberg lake.
> The user does NOT depend on any specific engine, orchestrator, ingestion tool, or notebook runtime.
>
> Any Tier 1 or Tier 2 component MUST have:
>   1. **A clean swap interface** (types compile, API surface matches) — ALWAYS maintained
>   2. **Basic smoke tests** (5-10 tests, not full E2E) — ALWAYS run in CI
>   3. **Full swap implementation** — built **on-demand** when trigger event fires (vendor death, license pivot, perf regression, community demand)
>   4. **Migration path documented** in `/docs/swap/{component}.md`
>
> If a component cannot be swapped, it MUST be Tier 0 (immortal standard).

### 9.2 The 3-Tier Classification

#### Tier 0: Bedrock (immortal, never swap)

| Component | Why immortal |
|---|---|
| Apache Arrow | Multi-vendor consortium |
| Apache Iceberg | Apache governance, multi-vendor committers |
| Apache Parquet | De facto standard |
| Lance | Open spec, growing adoption |
| S3 API | Universal protocol |
| OpenLineage | CNCF/LF backed |
| OpenTelemetry | CNCF universal |

#### Tier 1: First-class engines (clean interface, on-demand swap)

| Component | Default | Swap Target | Interface maintained | Full adapter |
|---|---|---|---|---|
| SQL engine | DuckDB | Apache DataFusion | ✅ from v0.1 | On-demand |
| DataFrame engine | Polars | DataFusion DF | ✅ from v0.1 | On-demand |
| Catalog | Filesystem (v0.1) → Lakekeeper (v0.3+) | Apache Polaris | ✅ from v0.3 | On-demand |
| Object store | MinIO | SeaweedFS / Direct cloud | ✅ from v0.1 | On-demand |

#### Tier 2: Wrapped capabilities (fully replaceable)

| Component | Default | Swap Target |
|---|---|---|
| Orchestration | Dagster | `nucleus-mini-scheduler` |
| Ingestion | `ctx.copy_from` (v0.1) / dlt (v0.3+) | Sling / Singer / custom |
| Transformation | Native `ctx.sql` (v0.1) | dbt-duckdb / SQLMesh |
| Notebooks | Marimo (v0.3+) | Jupyter or none |
| Streaming (v1.5+) | Benthos / Redpanda | Kafka native / Flink |

### 9.3 Swap Drill Protocol (Amendment 3 — REVISED)

```
Quarterly (automated CI):
  Phase 1 — Interface health (ALWAYS):
    - Verify swap target interface still compiles
    - Run 5-10 smoke tests covering basic ops
    - Generate compatibility delta report

Phase 2 — Full adapter build (TRIGGER-DRIVEN ONLY):
    Trigger events:
      - Default vendor: license pivot, acquisition, dormancy >6 months
      - Default vendor: performance regression >2x
      - Community demand: >10 enterprise customers request alt
    On trigger:
      - Build full adapter within 30 days
      - Run full E2E test suite
      - Release as opt-in via `nucleus.yaml: engine.sql: datafusion`
```

**This middle ground gives 80% of safety at 10% of cost** vs maintaining full implementations of every alternative pre-emptively.

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
1. Activate swap target immediately (interface already exists; build full adapter in 30 days)
2. Communicate to users (transparent disclosure)
3. If swap target also unhealthy, fork the component under Nucleus org
4. Maintain fork until alternative emerges

### 9.6 Why This Matters

History of platforms killed by vendor death: Parse, RethinkDB, Heroku, HashiCorp, Redis, Elastic. Nucleus survives these scenarios **by design**.

---

## 10. Yield-to-Giants Strategy

We do not compete with Databricks/Snowflake. We integrate.

### 10.1 Mode 1: Graduation (zero-effort)

User outgrows Nucleus → point Databricks/Snowflake/Trino at same S3 + Iceberg catalog → zero migration → use giants for heavy analytics, Nucleus for ingestion + light transforms.

**Implementation cost:** zero. Iceberg standard handles it.

### 10.2 Mode 2: Hybrid Compute (v1.5+)

```python
@nucleus.sql_asset(compute="databricks")
def fct_yearly_revenue_rollup(ctx):
    return ctx.sql("""
        SELECT year, region, SUM(amount)
        FROM raw_events WHERE year >= 2020 GROUP BY 1, 2
    """)
```

Nucleus orchestrates; Databricks executes; result committed back to Iceberg.

Other providers: Snowflake, BigQuery, Trino, ClickHouse via DBAPI plugin.

### 10.3 Mode 3: Federation (v2.0+)

Each domain runs its own Nucleus. Iceberg REST catalog federation. Cross-domain queries via Trino, Databricks, or Snowflake.

### 10.4 Why This Strategy Wins

| Benefit | Explanation |
|---|---|
| Acquisition-friendly | Giants see us as feeder, not threat |
| No data lock-in | Iceberg portability removes objection |
| Smaller scope | We don't build distributed compute |
| Customer trust | "If we outgrow you, we can leave" → users stay longer |

---

## 11. Local-First Guarantee

### 11.1 The `nucleus up` Promise

```bash
$ git clone my-data-project
$ cd my-data-project
$ nucleus up
✓ MinIO ready (port 9000)
✓ Filesystem catalog ready (.nucleus/catalog)
✓ Metadata DB ready (.nucleus/state.sqlite)
✓ Dagster substrate ready
Total: 6.4s

$ nucleus ingest postgres://localhost:5432/app --table public.orders --as raw.orders
✓ Schema inferred: 12 columns
✓ Iceberg table 'raw.orders' created
✓ 25,841 rows committed in 1.2s
```

### 11.2 Performance Targets

| Metric | Target |
|---|---|
| Cold boot (laptop, M1/M2, 16GB) | <10s |
| Warm boot | <3s |
| Idle RAM | <500MB |
| Active small pipeline RAM | <2GB |
| Time to first materialized asset (new user) | <5 min |
| Time to first BI-ready table from git clone (5-engineer team) | <30 min |

### 11.3 Identical-to-Production

Same code, versions, engines locally and in production. Only `connections/*.yml` and `environments/*.yml` differ.

| Concern | Local | Production |
|---|---|---|
| Object store | MinIO | S3 |
| Catalog | Filesystem (v0.1) / Lakekeeper (v0.3+) | Lakekeeper |
| Metadata | SQLite | PostgreSQL |
| Orchestration | Dagster in-process | Dagster on k8s |
| Secrets | `.env.local` | Vault / cloud secrets |
| Code | identical | identical |

### 11.4 Disconnected Operation

- All assets materialize locally against MinIO
- AI Copilot (v0.2+) can use local LLMs (Ollama, llama.cpp) via OpenAI-compatible API
- Telemetry buffers and flushes on reconnect

---

## 12. The Asset Primitive

### 12.1 Definition

An asset is a named, versioned, contractually-enforced unit of data that:

- Has stable identity (`catalog.schema.name`)
- Has code-defined production logic (Python or SQL)
- Has known schema and contract
- Has explicit dependencies on other assets
- Has lineage tracked
- Has freshness SLA (v0.5+)
- Has owners and deprecation policy (v0.5+)

### 12.2 Asset Types

| Type | Decorator | Materialized as | Available |
|---|---|---|---|
| Python asset | `@nucleus.asset` | Iceberg table or Lance dataset | v0.1 |
| SQL asset | `@nucleus.sql_asset` | Iceberg table | v0.1 |
| Source | `@nucleus.source` | External → Iceberg via `ctx.copy_from` | v0.1 |
| Check | `@nucleus.check` | Validation run | v0.1 |
| Multi-asset | `@nucleus.multi_asset` | Multiple Iceberg tables atomically | v0.5 |
| Sensor | `@nucleus.sensor` | Trigger logic | v0.3 |
| Schedule | `@nucleus.schedule` | Time-based trigger | v0.1 |

### 12.3 Materialization Modes

| Mode | Description | Available |
|---|---|---|
| `table` | Full rebuild on each run | v0.1 |
| `view` | Logical view, not materialized | v0.1 |
| `incremental` | Only new rows merged | v0.3 |
| `snapshot` | New version on each run | v0.5 |

### 12.4 Lineage (Amendment 5 — REVISED)

| Granularity | Available |
|---|---|
| **Asset-level** (X depends on Y) | **v0.1** — enforced at write time, emitted to OpenLineage |
| Column-level for SQL assets | v0.5 — via SQLGlot parsing |
| Column-level for Python assets | v1.0 — via DataFrame introspection |

Asset-level lineage answers 90% of real questions ("what depends on this table?"). Column-level is a rabbit hole that's deferred until we have evidence users need it.

### 12.5 Contracts

```python
@nucleus.contract("sales.orders")
class OrdersContract:
    schema = {
        "order_id": "string NOT NULL UNIQUE",
        "customer_id": "string NOT NULL",
        "amount": "decimal(10,2) NOT NULL CHECK > 0",
        "created_at": "timestamp NOT NULL",
    }
    # Available v0.5+:
    freshness = "max 1 hour stale"
    sla = "99.9% successful daily runs over 30-day window"
    pii_columns = ["customer_id"]
    owner = "@team-revenue"
```

**v0.1:** schema validation only. **v0.5+:** freshness, SLA, PII tagging.

Contracts are **enforced at materialization** — bad data rejected before commit.

(Full spec: `nucleus_asset_model_spec.md`)

---

## 13. The `ctx` SDK Contract

### 13.1 Principles

1. **The only public API.** Users never import `dagster`, `polars`, `duckdb`, `dlt`, `dbt` directly.
2. **Stable from v1.0** — but with AI-evolution caveat (see §13.3).
3. **Engine-agnostic.** Internal engine swaps do not change `ctx` surface.
4. **Introspectable.** Every object has structured metadata accessible to humans and LLMs.

### 13.2 Surface Summary

```python
import nucleus

@nucleus.asset(materialize="incremental", partition="day")
def fct_orders(ctx):
    raw = ctx.read("raw.stripe.charges", as_="polars")
    cleaned = raw.filter(pl.col("status") == "succeeded")
    ctx.write(cleaned, contract="sales.orders")
    ctx.log.info("Processed orders", count=cleaned.shape[0])
```

| API | v0.1 | v0.2 | v0.3 | v0.5 |
|---|---|---|---|---|
| `ctx.read(name, as_=...)` | ✅ | ✅ | ✅ | ✅ |
| `ctx.write(df, contract=...)` | ✅ | ✅ | ✅ | ✅ |
| `ctx.sql(query)` | ✅ | ✅ | ✅ | ✅ |
| `ctx.copy_from(source, table=...)` | ✅ | ✅ | ✅ | ✅ |
| `ctx.materialize(asset, *, partition, upstream, timeout_seconds)` | ✅ | ✅ | ✅ | ✅ |
| `ctx.log` | ✅ | ✅ | ✅ | ✅ |
| `ctx.params` | ✅ | ✅ | ✅ | ✅ |
| `ctx.metrics` | ❌ | ✅ | ✅ | ✅ |
| `ctx.secrets` | ❌ | ✅ | ✅ | ✅ |
| `ctx.snapshot(name)` | ❌ | ❌ | ✅ | ✅ |
| `ctx.agent` | ❌ | ❌ | ❌ | ✅ |
| `ctx.llm` | ❌ | ❌ | ❌ | ✅ |
| `ctx.dagster_context` (escape hatch) | ✅ | ✅ | ✅ | ✅ |

(Full spec: `nucleus_ctx_sdk_spec.md`)

### 13.3 Versioning Policy (Amendment 8 — REVISED)

**Core data APIs** (`ctx.read`, `ctx.write`, `ctx.sql`, `ctx.copy_from`, `ctx.log`, `ctx.metrics`, `ctx.secrets`, `ctx.snapshot`):

| Change type | Version bump | Compatibility |
|---|---|---|
| New optional argument | Patch | Full backward |
| New method | Minor | Full backward |
| Remove method | **Major** | Migration tool, 12-month deprecation |
| Change method signature | **Major** | Migration tool, deprecation |

**AI-related APIs** (`ctx.agent`, `ctx.llm`, `ctx.copilot.*`):

| Change type | Version bump | Compatibility |
|---|---|---|
| New optional argument | Patch | Full backward |
| New method | Minor | Full backward |
| **Breaking change allowed in minor** | Minor | 6-month deprecation window |
| Remove method | **Major** | Migration tool, 12-month deprecation |

**Rationale:** AI paradigms evolve too quickly to freeze for 5+ years. Core data APIs stay strict; AI APIs flex.

---

## 14. Operational Concerns

### 14.1 Retries & Backoff

- Per-asset configurable: `max_retries`, `backoff_strategy`
- Default: 3 retries, exponential backoff (1s, 5s, 25s)
- Idempotency: writes transactional via Iceberg snapshots — partial failures roll back
- Dead-letter on permanent failure: notified via configured channel

### 14.2 Backfills

```bash
nucleus backfill fct_orders --from 2024-01-01 --to 2024-12-31
```

- Replays historical partitions
- Cost-aware planner shows estimate first (v0.7+)
- Parallelizable (configurable concurrency)
- Progress tracked in run history
- Cancellable mid-run; resumes from last committed partition

### 14.3 Schema Evolution

Iceberg supports schema evolution natively. Nucleus enforces:

| Change | Allowed | Action |
|---|---|---|
| Add column | Yes (auto) | Backfilled NULL |
| Drop column | Requires contract update | 30-day deprecation |
| Rename column | Requires migration script | Lineage updated automatically |
| Change type (compatible widening) | Yes | Auto-applied |
| Change type (lossy) | Requires migration | Manual review |

### 14.4 Concurrency

| Scope | Model |
|---|---|
| Within single asset run | Engine-specific (DuckDB multi-thread, Polars parallel) |
| Across assets in same run | Dagster scheduler — DAG-aware parallelism |
| Across runs (same asset) | Iceberg optimistic concurrency control via catalog |
| Multi-user Workbench | PostgreSQL-backed session state; optimistic locking |
| Multi-tenant production | Process-per-tenant or k8s namespace-per-tenant |

### 14.5 Disaster Recovery

| Scenario | Recovery |
|---|---|
| Single asset corrupted | Roll back to previous Iceberg snapshot |
| Catalog corrupted | Restore from PostgreSQL backup; Iceberg metadata self-describing |
| Object store data loss | Restore from cross-region replication; Iceberg manifests can rebuild |
| Full disaster | Lake is portable. Spin up new Nucleus, point at S3+catalog. |

---

## 15. Security & Governance

### 15.1 Authentication (Amendment 9 — REVISED)

**Nucleus never owns identity. Always delegate to OIDC.**

| Tier | Method |
|---|---|
| Local dev (v0.1) | None (single user) |
| Team mode (v0.3+) | OIDC integration (Authentik / Keycloak self-hosted, or hosted Auth0) |
| Enterprise (v1.0+) | Customer's OIDC provider (Okta, Azure AD, Google Workspace) |

No custom auth system. No password storage. No session management beyond OIDC tokens.

### 15.2 Authorization (RBAC) — v0.3+

Hierarchical:

```
Org
├── Domain
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
- Cloud: Encrypted at rest, accessed via `ctx.secrets.get("name")` (v0.2+)
- Enterprise: Vault / Infisical / cloud KMS integration (v1.0+)

Secrets never appear in logs, run metadata, or AI Copilot context.

### 15.4 PII & Compliance (v1.0+)

| Feature | Capability |
|---|---|
| PII column tagging | Declarative in contract; flows through lineage |
| Masking | Automatic in non-production based on contract tags |
| Right-to-be-forgotten (GDPR) | `nucleus delete-subject --id ...` traverses lineage |
| Audit trail | Every materialization, secret access, permission change logged immutably |
| Differential privacy primitives | v1.5+ for aggregate exports |

### 15.5 Compliance Posture

Design for: SOC 2 Type II (Cloud), GDPR Article 17, HIPAA (enterprise tier), CCPA.

We do **not** claim certifications until audited.

---

## 16. Performance Targets

### 16.1 Boot & Startup

| Metric | Target |
|---|---|
| `nucleus up` cold | <10s |
| `nucleus up` warm | <3s |
| `nucleus run <asset>` startup | <500ms |

### 16.2 Query Performance

| Workload | Target |
|---|---|
| 100M-row aggregation (laptop) | <2s |
| 1B-row aggregation (32-core server) | <30s |
| TPCH-10GB on DuckDB | <3s |
| Iceberg partition pruning overhead | <100ms |

### 16.3 Resource Footprint

| Metric | Target |
|---|---|
| Idle RAM | <500MB |
| Active small pipeline | <2GB |
| Workbench server (single user) | <1GB |

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
| OSS Core | Free (Apache 2.0) | Full platform, self-hosted Workbench |
| Nucleus Cloud | $20/seat/mo + usage | Managed catalog, S3, secrets, deploy, basic Copilot |
| Nucleus Copilot Pro | +$50/seat/mo | Premium AI: agent runtime, advanced models, custom prompts |
| Nucleus Enterprise | $50K-500K/year | SSO/SAML, audit, multi-tenant, RBAC, vertical packs, SLA |
| Marketplace (v2.0+) | 15-25% rev share | Data product templates, vertical accelerators |

### 17.2 Realistic Trajectory

> **Note (v4.1.2 patch):** Timeline expanded for solo-founder pacing. Tier 0
> "Heartbeat" (Mo 0-2) precedes v0.1. Supersedes v4.1's original 14-18 mo
> v1.0 estimate. See §18 for tier-by-tier scope.

> **Note (v4.1.3 patch):** Mo 28-36 v1.0 GA below is **best-case-only**,
> explicitly contingent on the Mo 24 decision gate (see "Mo 24 decision
> gate" subsection below). No solo project shipped a serious data
> engineering platform alone past v1.0 in 2022-2026; the gate forces an
> honest founder choice **while there is still runway**, not at exhaustion.

| Phase | Timeline | Users | ARR | Milestone |
|---|---|---|---|---|
| Tier 0 Heartbeat | Month 0-2 | founder only | $0 | First runnable slice (`ctx.read` + `ctx.write` locally) |
| v0.1 Hello World | Month 2-8 | 0-10 testers | $0 | CLI E2E validates `git clone → first table <30 min` |
| v0.2 DX | Month 8-14 | 10-100 testers | $0 | Workbench validates `5-engineer team productive` |
| v0.3 Connectors | Month 14-20 | 100-300 trial | $0-25K | Lakekeeper / Polaris co-default + dlt; beta opens |
| v0.5 Intelligence | Month 20-28 | 300-1,000 trial | $25-100K | Lineage-aware Copilot + `ctx.agent` + `nucleus-mcp-server` |
| **Mo 24 GATE** | — | — | — | **Founder commits to (a) raise, (b) hand off, or (c) indie — see below** |
| v1.0 GA *(best-case)* | Month 28-36 | 500-2,000 | $100K-500K | First paying customers; SDK stable per semver |
| v1.5 | Year 3-5 | 5,000-15,000 | $500K-2M | Sustainable indie business |
| v2.0 | Year 5-6 | 15,000-50,000 | $2-10M | Acquisition-eligible |
| v3.0 | Year 7+ | 50,000+ | $10-30M | Strategic acquisition target |

**Mo 24 decision gate (per ADR-002 §8.3).** By Month 24 (mid-v0.5), the founder MUST commit to exactly one of:

- **(a) Raise seed / pre-seed** → build a team to ship v1.0 GA
- **(b) Hand off** → downstream consumer / acqui-hire (Bosch internal data-platform team is the documented off-ramp)
- **(c) Accept indie outcome** → cap scope, charge from v1.0 OSS-friendly tier, retire fundraise ambitions

The gate **fires automatically from weakness** if any of these hold:

1. v0.5 released + **0 paying customers** after 3 months beta
2. v0.5 released + **<10 active teams** after 6 months OSS
3. **Founder velocity sustained <3 features/month for 60 consecutive days** (measured against PoCs and v0.x deliverables)
4. **Funded competitor ships an equivalent local-first Iceberg stack** with comparable DX (current watch list: Tower.dev, Bauplan, Tobiko, dbt-Fusion-with-DuckDB-GA)

The gate **also fires from strength** if **>50 active teams + ≥2 design partners paying** — still pick (a)/(b)/(c), but raise/hand-off from leverage, not desperation. Rationale: strong traction without team conversion creates the most dangerous founder trap (sales-cycle defeat by funded competitor at Mo 30-36); the gate forces conversion *before* the trap closes.

**No "default extension" is permitted.** Reaching Mo 24 without an explicit choice = automatic option (c).

### 17.3 What We Don't Do

- No license pivot (Apache 2.0 stays)
- No "feature lock" that breaks composability
- No proprietary data formats
- No different SDK in "enterprise edition"

The OSS core is complete enough to use forever without paying us.

---

## 18. Roadmap

### 18.0 Tier ↔ Version Map

The README and contributor docs use a user-facing "Tier" framing parallel to
the architectural version labels. The mapping is:

| Tier | Version | Months | Scope label |
|---|---|---|---|
| Tier 0 Heartbeat | pre-v0.1 | Mo 0-2 | Just `ctx.read` + `ctx.write` working locally |
| Tier 1 Foundation | v0.1 | Mo 2-8 | Beachhead-ready CLI: `git clone → BI-ready Iceberg table <30 min` |
| Tier 2 Workbench | v0.2 | Mo 8-14 | Web IDE + simple Copilot |
| Tier 3 Connectors | v0.3 | Mo 14-20 | Lakekeeper, dlt, dbt-duckdb adapter, Marimo |
| Tier 4 Intelligence | v0.5 | Mo 20-28 | Lineage-aware Copilot + `ctx.agent` runtime |
| (no tier) | v1.0 GA | Mo 28-36 | Public stable release |

> **There is no v0.4 in the Tier framing — that is intentional.** Tier 4 jumps
> directly to v0.5 because v0.4 is reserved for incremental Tier 3 polish
> releases (notebook UX, connector hardening) without a numbered Tier event.

### 18.1 v0.1 — "Hello World" (Month 2-8)

**Must ship (CLI-only, no Workbench yet):**

- `ctx` SDK Core: `read`, `write`, `sql`, `copy_from`, `log`, `params`
- `nucleus` CLI: `init`, `up`, `down`, `run`, `ingest`
- Engines: DuckDB + Polars only
- Storage: Iceberg via pyiceberg + filesystem catalog + MinIO
- Orchestration: Dagster wrapped + **Error Translation Layer (mandatory)**
- Transformation: native `ctx.sql` with Jinja `{{ ref() }}` resolution
- Ingestion: `ctx.copy_from` helper (PostgreSQL, MySQL, SQLite, CSV, Parquet, JSON)
- Lineage: asset-level via OpenLineage emission
- Contracts: schema validation only
- Auth: local single-user only

**Success metric:** 5-engineer startup team builds Postgres → Iceberg first table in <30 min via CLI from `git clone`.

**Explicitly OUT of v0.1:**
- Workbench (v0.2)
- AI Copilot (v0.2)
- dlt integration (v0.3)
- Marimo (v0.3)
- Lakekeeper (v0.3)
- Schema-aware completion (v0.3)
- ctx.agent / lineage-aware refactoring (v0.5)
- Lance / multimodal / Daft (v0.5)
- Cost meter / replay debugger (v0.7+)
- Federation / Marketplace (v2.0+)

### 18.2 v0.2 — "Developer Experience" (Month 8-14)

- Workbench (web IDE): Monaco editor + asset list + run history + simple AI chat
- `ctx.metrics`, `ctx.secrets`
- CLI additions: `test`, `list`, `describe`
- Error Translation Layer expanded coverage
- Beta program opens

**Success metric:** 5-engineer team works collaboratively in Workbench; junior engineer ships first asset within 1 hour.

### 18.3 v0.3 — "Connectors & SQL Heritage" (Month 14-20)

- dlt integration (100+ connectors)
- Marimo notebook integration
- Lakekeeper REST catalog (when multi-engine demand emerges)
- Schema-aware Copilot completion
- dbt-duckdb optional adapter (migration path)
- `ctx.snapshot()`, incremental materialization
- Sensors

### 18.4 v0.5 — "Intelligence Awakens" (Month 20-28)

- `ctx.agent` runtime (sandboxed AI code generation)
- Lineage-aware refactoring + AI test generation
- **`nucleus-mcp-server` (~500 LOC)** — expose assets / contracts / lineage to MCP-compatible agents via `ctx` (per ADR-002 §4.2 hedge against agent-substrate scenario; not a category pivot, purely additive thin adapter)
- Lance + multimodal optional
- Daft optional engine
- Cost meter v1
- Column-level lineage for SQL
- Snapshots, multi-asset

### 18.5 v1.0 GA — "Production Ready" (Month 28-36)

- Hardened SDK (core data APIs stable per §13.3)
- Cloud offering managed (catalog, S3, secrets)
- Enterprise OIDC/SAML
- SLA-grade reliability
- First paying customers
- Dagster replaceability proven (mini-scheduler runs same project unchanged)
- Polaris swap interface + smoke tests
- Column-level lineage for Python

### 18.6 v1.5 — "Operations Mastery" (Year 2)

- Cost-aware planner
- Replay & time-travel debugger
- Semantic knowledge graph
- Streaming support (Benthos / Redpanda)
- Hybrid compute Mode 2 (Databricks/Snowflake dispatch)
- Vertical packs (finance, healthcare, retail)
- Differential privacy primitives

### 18.7 v2.0 — "Federation & Marketplace" (Year 3)

- Mode 3 federation (Data Mesh full)
- Data Product Marketplace
- Multi-region deployment
- Advanced governance plane

### 18.8 v3.0+ — "Acquisition or Independence"

By Year 5: $10-30M ARR, 50K+ users, acquisition discussions or continued independence.

---

## 19. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Dagster Labs pivots license / hostile | Medium | High | `nucleus-mini-scheduler` fallback designed; 30-day swap |
| 2 | DuckDB Labs commercial pivot | Low-Medium | Medium | DataFusion interface + smoke tests; full adapter on-demand |
| 3 | LLM cost / capability changes | Medium | Medium | Provider-agnostic; local model support |
| 4 | Big players build "AI for data" | Medium | High | Stay 12+ months ahead via integration depth |
| 5 | Beachhead market smaller than expected | Medium | High | v1.5+ expand to enterprise domain teams |
| 6 | Iceberg adoption stalls | Very low | Critical | Multi-vendor commitment |
| 7 | Hiring senior engineers slow | High | High | OSS-first mission attracts |
| 8 | **Error Translation Layer cannot cover all cases** | Medium | Critical | **PoC Week 1-2 validates feasibility before commit** |
| 9 | v0.1 scope still creeps | Medium | High | Hard cuts enforced; Hello World metric is single judge |
| 10 | Cloud margin compressed by AI token costs | Medium | Medium | Token usage metered per-seat; Copilot Pro captures premium |
| 11 | Composability interfaces drift over time | Medium | Medium | Quarterly interface health check in CI |
| 12 | Dagster mental model leaks into user code via Tier 2 escape hatch | Medium | High | Telemetry tracks usage; if >5% users use specific feature for 3 months, build native equivalent |

---

## 20. Non-Goals

### 20.1 We Do Not Build

- ❌ Our own SQL engine
- ❌ Our own DataFrame engine
- ❌ Our own catalog (we use filesystem/Lakekeeper/Polaris)
- ❌ Our own object store
- ❌ Our own table format
- ❌ Our own scheduler (wrap Dagster; mini-scheduler fallback)
- ❌ Our own connectors at scale (use `ctx.copy_from` minimal; dlt later)
- ❌ Our own SQL transformation framework beyond Jinja+ref (no full dbt-equivalent)
- ❌ Our own notebook runtime (integrate Marimo)
- ❌ Our own BI tool
- ❌ A Spark replacement
- ❌ A Databricks competitor
- ❌ A vector database (use Lance)
- ❌ An ML training platform
- ❌ **An Iceberg commit service / distributed transaction coordinator**
- ❌ **An auth/identity system**
- ❌ A column-level lineage engine in v0.1
- ❌ A full AI Copilot (lineage-aware, schema-aware) in v0.1

### 20.2 We Do Not Compete With

- Databricks, Snowflake (we feed them via Mode 1/2)
- Cloud providers (we run on top)
- BI tools (we surface their dashboards)
- AI providers (we use them)

### 20.3 We Do Not Target (in v0.1-v1.0)

- Solo consultants (incidentally served, not designed for)
- Enterprise domain teams (v1.5+)
- Enterprise central pipelines (v2.0+)
- Hyperscale (>100TB single-pipeline) — never

---

## 21. Decision Log

### D1. Wrap Dagster, do not build orchestrator

**v3** — Use Dagster as hidden substrate. Build mini-scheduler as fallback.

### D2. DuckDB + Polars over DataFusion-only

**v4** — Default DuckDB (SQL) + Polars (DataFrame). DataFusion is swap interface.

### D3. Apache 2.0 license

**v4** — Forever. No BSL/SSPL pivot. Friendly to giants enables acquisition path.

### D4. Iceberg + Lance dual-format

**v4** — Iceberg structured; Lance multimodal (v0.5+).

### D5. Yield to giants via Mode 1/2/3

**v4** — Do not build distributed compute. Iceberg portability + dispatch hooks.

### D6. Intelligence Layer as differentiator

**v4** — AI features first-class architectural layer.

### D7. v0.1 ships with only inline AI chat (no agent runtime, no lineage-aware refactoring)

**v4.1** — Defer richer AI features to v0.3-v0.5. Honest about implementation cost.

### D8. Composability by Constitution as Law #1

**v4** — Every Tier 1/2 dependency must have swap target.

### D9. Local-first identical-to-prod

**v3** — `nucleus up` boots full stack in <10s; same code in production.

### D10. ctx SDK is the only public API

**v3** — Users never import Dagster, Polars, DuckDB, dlt directly.

### D11. NO Iceberg Commit Service (v4.1 amendment)

**v4.1** — Catalog handles atomic commits. Nucleus is thin Asset Materialization Adapter, not transaction coordinator.

### D12. Composability = clean interface + smoke tests, NOT maintained second implementations (v4.1 amendment)

**v4.1** — Avoid "Composability Tax". Full adapter built on-demand when trigger fires.

### D13. Native `ctx.sql` + Jinja in v0.1; dbt-duckdb deferred to optional v0.3 (v4.1 amendment)

**v4.1** — Own ~1000 LOC beats fragile community-maintained adapter.

### D14. Filesystem catalog in v0.1; Lakekeeper deferred to v0.3 (v4.1 amendment)

**v4.1** — Cut one operational domain from boot. Filesystem catalog sufficient for single-node.

### D15. Asset-level lineage in v0.1; column-level in v0.5+ (v4.1 amendment)

**v4.1** — 90% of value at 20% of cost. Column lineage is a rabbit hole.

### D16. Error Translation Layer is mandatory release blocker (v4.1 amendment)

**v4.1** — Leaky Dagster errors kill the abstraction. PoC Week 1-2 validates feasibility.

### D17. No custom auth; always delegate to OIDC (v4.1 amendment)

**v4.1** — Nucleus is not an identity company.

### D18. Beachhead persona is startup data team 5-20 engineers (v4.1 amendment)

**v4.1** — v0.1-v1.0 designed exclusively for this. Other personas v1.5+.

### D19. v0.1 split into "Hello World" (Mo 0-4) + "Developer Experience" (Mo 4-8) (v4.1 amendment)

**v4.1** — Checkpoint at month 4 with CLI-only validation. Workbench in v0.2.

### D20. Connector UX one-liner mandatory (v4.1 amendment)

**v4.1** — `nucleus ingest postgres://...` must auto-infer + auto-create + commit. Otherwise 30-min promise breaks.

### D21. Dagster replaceability proven by v1.0 (v4.1 amendment)

**v4.1** — `nucleus-mini-scheduler` runs same project unchanged. Zero user code grep for `dagster`.

---

## 22. References

### Internal Documents (companion specs)

| Document | Purpose |
|---|---|
| `nucleus_ctx_sdk_spec.md` | Full ctx SDK API |
| `nucleus_asset_model_spec.md` | Asset primitive deep-dive |
| `nucleus_project_anatomy.md` | On-disk layout |
| `nucleus_cli_spec.md` | CLI specification |
| `nucleus_poc_plan.md` | PoC validation plan (Dagster Error Translation = PoC #1) |
| `nucleus_implementation_readiness.md` | Go/no-go gate for v0.1 |
| `nucleus_red_team_review.md` | Adversarial review |
| `nucleus_vs_databricks.md` | Feature parity analysis |
| `AGENTS.md` | AI agent operating instructions |
| `.cursor/rules/nucleus.mdc` | Cursor IDE rule |

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

---

## Appendix A: How to Read This Document

### For a senior data platform engineer

1. Read TL;DR + Changelog (5 min)
2. Skim §1 Positioning, §3 Architecture Overview (10 min)
3. Deep-dive relevant sections (20 min):
   - Storage/format → §4 Physics
   - Compute → §5 Engines
   - Orchestration + Error Translation → §6 Coordination
   - AI features → §7 Intelligence
   - DX → §8 Experience
4. Scrutinize §14 Operational, §16 Performance, §19 Risk Register (10 min)
5. Read §21 Decision Log (5 min)

Total: ~50 minutes for full critical review.

### Questions a senior engineer will likely ask

| Question | Answer location |
|---|---|
| Why not Spark? | §1.3, §10, §20 |
| Why no Iceberg commit service? | §6.2 (and D11) |
| What happens if DuckDB dies? | §5.1, §9.3 |
| How does Dagster get hidden? | §6.3, §6.5 (and D21) |
| What if errors leak from Dagster? | §6.4 (mandatory translation) |
| Why filesystem catalog in v0.1? | §5.7 (and D14) |
| Why native ctx.sql not dbt? | §5.6 (and D13) |
| What's the perf vs Databricks? | §16, §10 |
| Can I migrate off Nucleus? | §10.1 (Mode 1 graduation) |
| Why no column lineage in v0.1? | §12.4 (and D15) |
| How long until v0.1 ships? | §18.1 (4 months Hello World) |

---

## Appendix B: Open Questions (Triaged by Urgency)

### Blocking v0.1 PoCs (must resolve NOW)

1. **Cloud architecture** — single-tenant per customer vs multi-tenant shared
   - **RECOMMENDED: Multi-tenant for v1.0 Cloud launch.** Single-tenant tier becomes Enterprise upsell in v1.5+ for regulated industries.
   - **Rationale**: $20/seat startup beachhead pricing requires shared infra economics. Multi-→single retrofit is easy; single-→multi retrofit is a nightmare.
   - **Architecture impact**: tenant_id propagated in `ctx`; Iceberg buckets scoped `s3://nucleus-tenant-{id}/`; PostgreSQL schema per tenant; dedicated DuckDB process per query.

### Blocking v0.2 design (resolve before Month 3)

3. **Workbench technology** — Tauri (cross-platform desktop) vs pure web (Vite + browser)
   - Affects whether Workbench is desktop-app or web-app
   - Retrofit between them is significant rework
   - Decision needed before v0.2 UX design starts (Month 3-4)

### Can wait until needed

2. **AI provider strategy** — own keys vs BYOK vs both
   - Not relevant until v0.2 Copilot ships (Month 4-8)
   - Decision can wait until Cloud tier design (Month 9+)

4. **Marimo integration depth** — fork vs use as-is
   - Not relevant until v0.3 (Month 8-11)

5. **Initial vertical focus** — finance/healthcare vs horizontal
   - Marketing decision for v1.0 launch, not architectural
   - Can wait until Month 12+

**Bottom line: Only Question 1 actually blocks PoC #1 start. Question 3 blocks within 3 months. The rest can wait.**

---

## Appendix C: PoC Priorities (Week 1+)

Per Decision D16 and consensus from senior review:

### PoC #1 (Week 1-2): Dagster Error Translation Layer — CRITICAL

**Hypothesis:** Every Dagster error type can be intercepted at ctx boundary and re-emitted as NucleusError cleanly.

**Validation set (all 8 must translate cleanly):**
1. Asset materialization failure (Python exception)
2. SQL execution error (DuckDB error)
3. Out-of-memory crash
4. Iceberg commit conflict
5. Dependency asset not yet materialized
6. Schema mismatch (contract violation)
7. Timeout / cancellation
8. Concurrent write conflict

**Failure trigger:** If any error type cannot be translated, escalate; consider mini-scheduler.

### PoC #2 (Week 3-4): Native ctx.sql Jinja Resolver

**Hypothesis:** ~1000 LOC Jinja+sqlglot can replace 80% of dbt-duckdb functionality.

**Validation set:**
- `{{ ref() }}` resolution
- `{{ source() }}` resolution
- Basic macros (date_trunc, dateadd)
- Multi-CTE support
- Incremental config

**Failure trigger:** If LOC blows past 2500 or DAG resolution slow, fall back to dbt-duckdb as v0.1 default.

### PoC #3 (Week 5): nucleus ingest one-liner

**Hypothesis:** ~200 LOC SQLAlchemy + pyiceberg gives auto-infer + auto-create + commit for Postgres/MySQL/SQLite + file formats.

### PoC #4 (Week 6): nucleus up <10s

**Hypothesis:** MinIO + filesystem catalog + Dagster in-process boots in <10s on M1 laptop.

### PoC #5 (Week 7-8): End-to-end 30-minute beachhead validation

**Hypothesis:** Real 5-engineer team can go from `git clone` to BI-ready Iceberg table in <30 minutes.

---

## Sign-off

This document is the **single source of truth** for Nucleus architecture as of v4.1.

Implementation may begin once:
1. PoC #1 (Dagster Error Translation) passes
2. PoC #2-5 pass within their time budgets
3. Open questions in Appendix B are answered
4. Team and resources confirmed per `nucleus_implementation_readiness.md`

Any deviation from this document requires explicit amendment with rationale.

---

**End of v4.1**
