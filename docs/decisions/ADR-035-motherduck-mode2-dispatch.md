# ADR-035: MotherDuck as Mode 2 Dispatch Reference Architecture

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P2 (watch-list)  
**Target phase**: v1.5+  
**Source research**: `docs/research/inspiration/modern_query_engines.md` §6; `docs/research/inspiration/distributed_compute_2026.md` §10  
**Synthesis reference**: `docs/research/inspiration/ADOPTION_SHORTLIST.md` §2.9, §4

---

## Context

MotherDuck is a serverless cloud analytics service built on DuckDB. Its architectural contribution is **Dual Execution**: a query planner that automatically routes query stages between local DuckDB and cloud DuckDB ("Ducklings") based on where data lives. Per R2 §6.2: `SELECT * FROM local_parquet JOIN md:cloud_table ON id=id` runs the local scan locally and the cloud scan in the cloud, joined optimally.

This is the most concrete production implementation of `nucleus_architecture_v4.1.md §10.2` Mode 2 (hybrid compute). The integration path for Nucleus v0.3+: `compute="md"` on `ctx.run()` ATTACHes MotherDuck via `duckdb.connect("md:token")` — zero new Nucleus LOC.

**Open question before implementation** (R2 NV-6): Are Nucleus's Iceberg files directly attachable to MotherDuck? MotherDuck uses DuckLake as its native lakehouse format. If Iceberg assets are not directly readable via MotherDuck's DuckDB instance, a format bridge is needed. This question must be resolved before any integration work begins.

**Distinction from Modal (ADR-036)**: MotherDuck = continuous DuckDB scale-out (transparent SQL overflow for SELECT-heavy workloads). Modal = Python function dispatch (heavy batch assets that exceed laptop CPU/RAM, not SQL-only workloads).

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Watch-list; plan at v0.3; integrate at v1.5+** | Document MotherDuck as Mode 2 reference; resolve Iceberg/DuckLake NV-6 at v0.3; implement `compute="md"` at v1.5+ gated on user demand | ✅ SELECTED — correct sequence; no user demand yet; NV-6 must resolve first |
| B — Integrate at v0.3 | Add MotherDuck as an optional `compute=` target at v0.3 | ❌ REJECTED — NV-6 (DuckLake/Iceberg compat) unresolved; Lakekeeper not yet deployed; no empirical demand |
| C — Reject entirely | Do not pursue MotherDuck | ❌ REJECTED — it is the best Mode 2 reference for DuckDB-native continuous overflow; documentation alone has value |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A**. No implementation work at v0.3.

At v0.3:
1. Verify R2 NV-6 (MotherDuck DuckLake + Iceberg compatibility at https://motherduck.com/docs/integrations/file-formats/ducklake/)
2. Document MotherDuck as Mode 2 reference architecture in `docs/yield-to-giants/mode2.md`
3. Add to `docs/compatibility.md` as a watch-list item

At v1.5+:
1. Open dedicated ADR if NV-6 confirms Iceberg compatibility
2. Implement `compute="md"` as an optional engine hint in `ctx.run()`
3. Token management in `nucleus_project.yaml` (user provisions `MOTHERDUCK_TOKEN`)

**GATE**: Lakekeeper REST catalog (v0.3) is a prerequisite — Mode 2 dispatch requires a catalog that is accessible from both local and cloud compute.

---

## Consequences

- **LOC budget impact**: 0 LOC for watch phase; ~100 LOC for v1.5+ integration (if triggered)
- **Dependency**: MotherDuck is proprietary SaaS — flag per ADR template (no OSS fallback for the cloud tier)
- **Depends on**: Lakekeeper ADR (v0.3 catalog); R2 NV-6 resolution

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §10.2 (Mode 2 hybrid compute)
- `nucleus_architecture_v4.1.md` §14 (yield-to-giants strategy)
