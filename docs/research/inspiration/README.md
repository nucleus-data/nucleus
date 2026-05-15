# docs/research/inspiration/

Competitive inspiration research — projects with strong alignment to Nucleus's beachhead
positioning that we study to adopt patterns, not to integrate directly.

**This folder is different from `docs/research/`** (component integration research).
Integration research covers deps Nucleus actually wraps (dlt, pyiceberg, DuckDB, etc.).
Inspiration research covers *peers* — what they got right, what we should adopt, and what to avoid.

---

## Index

| File | Tier | Projects | Key ADR candidates | Status |
|---|---|---|---|---|
| `ADOPTION_SHORTLIST.md` | **CAPSTONE — 8-Lane Synthesis** | All R1–R8 projects | ADR-026 through ADR-036 (11 new ADR stubs) | ✅ Published 2026-05-15 |
| `peer_local_first_elt.md` | **A.1 — Local-First ELT Peers** | dlt, Bauplan, DuckLake | MCP server (P0), snapshot metadata (P1), schema contract passthrough (P2), column-select pushdown (P3), compaction asset (P4) | ✅ Published 2026-05-15 |
| `tier0_oss_evolution.md` | **T0 — Tier 0/1 Engine Evolution** | DuckDB, Polars, PyIceberg, PyArrow, Lakekeeper | DuckDB 1.2.x upgrade (ADR req), Polars `sink_iceberg`, PyIceberg maintenance ops | ✅ Published 2026-05-15 |
| `storage_formats_2026.md` | **R8 — Storage Formats + Cross-Engine RPC** | Iceberg v3, Parquet v3, Vortex, Lance v2, Delta Lake 4, Paimon, Arrow Flight SQL, Arrow IPC, Compression | Iceberg v3 migration helper (v0.3 ADR req), Arrow Flight SQL Workbench endpoint (v0.3 ADR req), Vortex tracking (v1.0) | ✅ Published 2026-05-15 |
| `embedded_analytics_bi.md` | **B.3 — Embedded Analytics & BI** | Rill, Evidence.dev, Quary, Lightdash, Metabase, Superset, Streamlit, Observable, Quarto, Cube.dev, MetricFlow, Malloy | nucleus.db handshake (ADR-026), metrics_view.yaml emission (ADR-027), MetricFlow semantic contract (ADR-028) | ✅ Published 2026-05-15 |
| `modern_query_engines.md` | **C.1 — Modern Query Engine Alternatives** | DataFusion, Velox, chDB, GlareDB, MotherDuck, Substrait, Vortex, Polars SQL | ADR-026 (DataFusion CI smoke), ADR-027 (MotherDuck Mode 2), ADR-028 (Vortex v0.5+), ADR-029 (Substrait MCP consumer) | ✅ Published 2026-05-15 |
| `ai_data_tooling_2026.md` | **B.1 — AI-Assisted Data Tooling** | Spider 2.0, Vanna AI, SQLCoder/Defog, Cube.dev semantic layer, dbt MetricFlow, Malloy, LangGraph, CrewAI, AutoGen, MCP, dbt Copilot, Hex Magic | ADR-NNN (nucleus-mcp-server v0.5), asset-description sidecar v0.3, ctx.agent tool harness v0.7 | ✅ Published 2026-05-15 |
| `team_mesh_compute.md` | **R9 — Team Mesh Compute** | Ray, Dask, Tailscale, MotherDuck dual-exec, Modal, NATS JetStream, BOINC, Automerge/Yjs | `compute="mesh"` reserved keyword (0 LOC); re-evaluate at v1.0 if ≥3 teams request it | ✅ Published 2026-05-15 |

---

## Folder conventions

- One file per research tier (e.g., `peer_local_first_elt.md`, `peer_observability.md`)
- Each file: 20–30 KB, docs-grounded, per `AGENTS.md §11.12`
- ADR candidates from inspiration research land in `docs/decisions/ADR-NNN-*.md` after founder review
- All citations use numbered `[N]` footnotes pointing to official docs URLs

---

## Planned future tiers

| Tier | Description | Status |
|---|---|---|
| A.2 | Local-first SQL transformation peers (Evidence, SQLFrame, Rill) | NOT STARTED |
| A.3 | Python-native orchestration peers (Prefect, Hamilton, Lakeflow) | NOT STARTED |
| B.1 | AI data copilot peers (Hex, mode, Metabase AI) | ✅ Covered by `ai_data_tooling_2026.md` |
| B.2 | Data contract peers (Soda, Elementary, Monte Carlo) | NOT STARTED |

*Tiers opened on empirical demand — never speculatively.*
