# Nucleus Roadmap — Overview

> *Per `nucleus_architecture_v4.1.md` §18 (the authoritative roadmap section). Numbers marked `# NEEDS VERIFICATION` are projections pending external validation (PoC #5 field test).*

---

## Mission (quoted verbatim from `AGENTS.md §0`)

> **Nucleus ships data products from a laptop.** A local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks — built on open Apache foundations, AI-ready by design. Grows with the team. Graduates cleanly to cloud giants (Databricks/Snowflake) — or any Iceberg catalog (Polaris, Lakekeeper, Unity, R2) — when users outgrow it.
>
> We own three things, forever:
> 1. The **asset graph** (logical model of data products)
> 2. The **`ctx` SDK** (the developer contract)
> 3. The **unified developer-first experience** (CLI + Workbench + SDK as one product)

A *data product* in Nucleus terms = an Iceberg-backed asset with transformations, contracts, and lineage, consumable by BI tools, applications, or AI agents via the `ctx` SDK or MCP server (v0.5+).

---

## The Five Pillars

Every decision — a new feature, a dependency upgrade, an ADR — must serve ≥ 1 pillar without harming another.

| # | Pillar | What this means in practice |
|---|---|---|
| 1 | **High performance on minimal resources** | Boot in <10 s. Run 100GB transforms on a laptop. Never need a cluster for the beachhead persona. |
| 2 | **Composable by constitution** | Every Tier 1/2 dependency has a clean swap interface + smoke tests in CI. No lock-in without exit. |
| 3 | **AI-assisted by design** | Asset DSL designed for LLM comprehension. AI features are first-class citizens — not bolt-ons. |
| 4 | **Familiar UX from proven giants** | We borrow vocabulary and patterns from dbt, Dagster, Cursor. No invented jargon. |
| 5 | **Friendly to giants, hostile to no-one** | Iceberg portability means users can graduate to Databricks/Snowflake without migration. |

---

## The 8-Question Gate

**Before proposing any feature, every contributor runs this checklist.** A "no" or "unclear" on any question = feature is rejected or deferred.

```
[ ] 1. Maps to one of the five architectural layers?
       (Physics / Engines / Coordination / Intelligence / Experience)

[ ] 2. Serves the <30-minute beachhead metric?
       (5-engineer team, git clone → BI-ready Iceberg table in <30 min)

[ ] 3. Wrap possible instead of build?
       (check the Do-Not-Build list in AGENTS.md §4)

[ ] 4. Preserves no-JVM constraint?
       (every always-on component is Rust/Go/C++/Python)

[ ] 5. Preserves local-identical-to-prod?
       (nucleus up boots full stack identically in dev and production)

[ ] 6. Stays within the 30K LOC budget?
       (src/nucleus/ only; tracked by scripts/loc_budget.py)

[ ] 7. Triggered by empirical telemetry, not anxiety?
       ("v0.5 might need X" is not a justification)

[ ] 8. Required for v0.1 Hello World (Mo 0-4), or can it defer?
       (honest about version assignment)
```

---

## Version Timeline

| Version | Codename | Shipped / Target | Theme | LOC budget | Persona served |
|---|---|---|---|---|---|
| **v0.1** | Foundation | ✅ 2026-05-14 (internal beta; no PyPI artifact) | Beachhead CLI — `init/up/down/run/ingest/query/chat/version`, Error Translation, `ctx.sql`, `ctx.copy_from`, asset graph | ~4,200 / 8,000 ceiling | Startup data team 5-20 |
| **v0.2** | Public Launch | ✅ **CODE SHIPPED 2026-05-15** — founder-gated tag push pending | Workbench v0.3 + Copilot chat in UI + docs site + scheduled assets daemon + 7 connectors + Wave 2 P0 reliability hardening + Iceberg branch/tag CLI | ~8,300 / 12,000 ceiling | same beachhead |
| **v0.3** | Hardening | 2026 Q4 (Mo 14-20) | Post-launch reliability + chaos tests + dlt 100+ connectors + Marimo notebooks + Lakekeeper catalog | 12,000 / 16,000 ceiling | same beachhead |
| **v0.5** | Multimodal | 2027 Q1 (Mo 20-28) | Daft + Lance + AI Copilot lineage-aware + `ctx.agent` runtime + MCP server + column-level lineage | 16,000 / 20,000 ceiling | + ML engineer |
| **v0.7** | Cloud Tier MVP | 2027 Q2 (Mo 28-36) | OSS Cloud edition (single-tenant managed) + OIDC federation + billing meter | 20,000 / 24,000 ceiling | + platform team |
| **v1.0** | Production-Ready | 2027 Q3 (Mo 28-36, best-case) | SLA + governance maturity + first paying customers + Dagster replaceability proven | 24,000 / 28,000 ceiling | + small enterprise |
| **v1.5** | Enterprise Gateway | 2028 H1 | Auth federation + audit log + multi-env (dev/staging/prod) + vertical packs | 28,000 / 30,000 ceiling | + mid enterprise |
| **v2.0** | Federation + Mesh | 2028 H2+ | Iceberg REST federation + Data Mesh Mode 3 + Data Product Marketplace | 30,000 (ceiling reached) | + data mesh shops |

> **Mo 24 decision gate** (per ADR-002 §8.3): v1.0 GA is contingent on this gate. Auto-fires if any of: 0 paying customers after 3 months beta, <10 active teams after 6 months OSS, founder velocity <3 features/month for 60 days, or a funded competitor ships an equivalent. The gate preserves the option to pivot without burning resources.

---

## Yield-to-Giants Strategy

Nucleus does **not** compete with Databricks/Snowflake. We integrate via three modes (per `nucleus_architecture_v4.1.md` §10):

| Mode | Mechanism | When available |
|---|---|---|
| **Mode 1: Graduation** | Iceberg portability -- user points Databricks/Snowflake/Polaris at the same lakehouse with zero data movement. User's code + SQL assets read the same Parquet files. Step-by-step cookbooks: [`docs/cookbook/graduate-to-databricks.md`](../cookbook/graduate-to-databricks.md), [`graduate-to-snowflake.md`](../cookbook/graduate-to-snowflake.md), [`graduate-to-bigquery.md`](../cookbook/graduate-to-bigquery.md). | v0.1 (Iceberg is the substrate from day 1) |
| **Mode 2: Hybrid Compute** | Dispatch heavy assets to Databricks/Snowflake via `compute="databricks://..."` in `@nucleus.asset`. Nucleus handles the dispatch; user code unchanged. Design spec: [ADR-041](../decisions/ADR-041-mode-2-hybrid-compute-dispatch.md) (PROPOSED 2026-05-15). Implementation milestone: `wave-3-mode2-implementation`, target **v0.3+** (pulled forward from architecture's v1.5+ target per ADR-041 section 6; founder amendment to `v4.1` section 18.6 required at acceptance). | v0.3+ (per ADR-041) |
| **Mode 3: Federation** | Iceberg REST catalog federation for Data Mesh — cross-org asset sharing without data movement. | v2.0+ (Mode 3 federated mesh) |

---

## Non-Goals (summary — full list in `non-goals.md`)

Per `nucleus_architecture_v4.1.md` §20:

| We will NEVER build | Why |
|---|---|
| Custom SQL engine | DuckDB wraps better than we'd build |
| Custom DataFrame engine | Polars wraps better than we'd build |
| Custom orchestrator | Dagster wrapped + mini-scheduler fallback |
| Custom auth/RBAC | We are not an identity company — always delegate to OIDC |
| Custom Iceberg catalog | Filesystem (v0.1) → Lakekeeper/Polaris; catalogs handle atomic commits |
| ML training platform / feature store | Out of scope; we are a data engineering platform |
| Plugin marketplace (v1.x) | No public plugin SDK until v2.0+ reconsideration |
| "Data OS" or "Spark replacement" framings | Category confusion; forbidden per `AGENTS.md §8` | <!-- banned-term: Data OS -->

---

## Beachhead Persona (v0.1 → v1.0)

**Designed exclusively for**: Startup data team — 5-20 engineers, 100GB-5TB total data, greenfield project, MacBooks/Linux.

**v0.1 success metric**: A 5-engineer team builds their first BI-ready Iceberg table from `git clone` in **<30 minutes** via CLI.

Any feature that does not serve this metric is deferred. Other personas (solo consultant, enterprise domain team) are v1.5+.

---

## Proprietary LOC Budget

Hard ceiling: **30,000 LOC** by v1.0. Tracked monthly via `scripts/loc_budget.py`. Committed to `docs/budget_history.md`.

| Phase | LOC ceiling | Rationale |
|---|---|---|
| v0.1 shipped | 8,000 | CLI + ctx SDK + error translation + AMA + connectors |
| v0.2 | 12,000 | + Workbench scaffold + Copilot chat |
| v0.3 | 16,000 | + chaos harness + dlt connectors + Marimo wiring |
| v0.5 | 20,000 | + `ctx.agent` + MCP + Lance + Daft wrapping |
| v0.7 | 24,000 | + Cloud control plane + OIDC federation |
| v1.0 | 28,000 | + governance hardening + mini-scheduler |
| v1.5 | 30,000 (ceiling) | + enterprise features |

**Current state** (2026-05-15 close-out): `src/nucleus/` ≈ **8,300 LOC = 69 % of v0.2 ceiling**, well under the 12,000 LOC v0.2 cap. Re-verify with `python scripts/loc_budget.py`. GREEN.

---

*Source: `nucleus_architecture_v4.1.md` §18. Read the individual phase docs for full feature lists, acceptance criteria, and contributor workflows.*
