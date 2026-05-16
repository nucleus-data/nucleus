# Why "Wrap, Not Build" Is the Moat

*One page. Numbers cited come from `docs/specs/nucleus_architecture_v4.1.md` section 3, section 9, section 10 and `docs/budget_history.md`. Last updated 2026-05-15.*

---

## The hook

**What if your data platform was 8,484 lines of code instead of half a million?**

Most "modern data" platforms ship as monoliths that re-implement engines, catalogs, and orchestrators in-house. The result is vendor lock-in dressed up as differentiation. Nucleus took the opposite bet. Our proprietary surface is small on purpose. The hot path is rented from production-grade open source. The slim glue layer is where every dollar of engineering compounds.

## The three-sentence answer

We **wrap** the engines that work - DuckDB, Polars, pyiceberg, Dagster, OpenLineage. We **own** the three things our users actually depend on: the asset graph, the `ctx` SDK, and the unified developer experience. Everything we write graduates with the user - Iceberg snapshots port one-for-one to Databricks, Snowflake, Polaris, Lakekeeper, or any future catalog that speaks the spec.

## The leverage math

| Component | Source LOC | Role in Nucleus |
|---|---|---|
| DuckDB (C++) | ~700,000 | SQL engine - wrapped (v4.1 section 5.1) |
| Polars (Rust) | ~250,000 | DataFrame engine - wrapped (v4.1 section 5.2) |
| Dagster (Python) | ~150,000 | Orchestration - wrapped (v4.1 section 6) |
| dlt (v0.3+) | ~80,000 | Connectors - wrapped (v4.1 section 5.5) |
| pyiceberg | ~50,000 | Iceberg client - wrapped (v4.1 section 6.2) |
| **OSS rented (total)** | **~1,230,000** | All Tier 1/2 wrapped components |
| **Nucleus proprietary** | **8,484** | Asset graph + `ctx` + CLI + Workbench |

Counted via `loc_budget.py` against `src/nucleus/` on v0.2.0; well under the 30,000 LOC v1.0 hard ceiling per `AGENTS.md` section 3 #8. Every line we do not write is a line we do not have to debug, secure, or upgrade.

## What we own forever

Per `docs/specs/nucleus_architecture_v4.1.md` section 1.6:

1. **The asset graph** - the logical model of data products, expressed as `@nucleus.asset` Python and resolved as Iceberg snapshots.
2. **The `ctx` SDK** - the stable contract that hides every wrapped component behind one import (spec: `docs/specs/nucleus_ctx_sdk_spec.md`).
3. **The unified developer experience** - `ctx` + `nucleus` CLI + Workbench, treated as one product, with AI assistance as a feature, not the headline.

## Why this is a moat, not a weakness

- **Error Translation Layer (v4.1 section 6.4).** Every external exception becomes a `NucleusError` with a stable `NE####` code, a `docs_url`, and zero wrapped-library class names in user-facing strings. CI enforces this. One error namespace across five engines, parseable by humans and by LLMs.
- **AI Copilot leverage (v4.1 section 7).** Structured errors, asset names, and contract signatures are the substrate that makes AI-assisted debugging useful. The Copilot sits on top of a typed surface, not a black box.
- **Iceberg portability (v4.1 section 10.1).** We write plain Iceberg snapshots to user-owned object storage. The day a team outgrows a laptop, they point Databricks, Snowflake, or any Iceberg catalog at the same bucket. Zero migration. No proprietary byte format, ever.
- **Composability by Constitution (v4.1 section 9).** Every Tier 1/2 dependency ships with a swap interface and 5-10 CI smoke tests. Full alternates get built on demand - when license pivot, vendor death, or >2x perf regression fires the trigger.

## The honest part - what we do NOT own

We yield to giants for the things giants do well, per `docs/specs/nucleus_architecture_v4.1.md` section 20:

- Distributed compute - Databricks / Snowflake / Trino; we dispatch via Mode 2 (v1.5+).
- Vector storage - Lance / LanceDB (v0.5+ optional).
- ML training and model serving - we use models, we do not host them.
- Identity - we delegate to OIDC.
- Iceberg commit coordination - the catalog handles atomic commits (Hard Constraint #5).

## One-line close

**Composable by constitution. Friendly to giants. AI-ready by design.**
