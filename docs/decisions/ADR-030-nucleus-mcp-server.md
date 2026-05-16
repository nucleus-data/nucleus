# ADR-030: `nucleus-mcp-server` — MCP Tools for Assets, Lineage, Runs

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P1  
**Target phase**: v0.5  
**Source research**: `docs/internal/research/inspiration/ai_data_tooling_2026.md` §5; `docs/internal/research/inspiration/observability_lineage_2026.md` §8; `docs/internal/research/inspiration/embedded_analytics_bi.md` §5  
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #13, §2.3

---

## Context

MCP (Model Context Protocol, Anthropic Nov 2024, donated to Linux Foundation Dec 2025) is the ambient AI protocol in 2026: 97M monthly SDK downloads, 10,000+ public servers, supported by Claude Desktop, ChatGPT, Gemini, Cursor, VS Code, JetBrains, GitHub Copilot (per R3 §5.1). Snowflake and Databricks both shipped managed MCP servers in 2025 (per R3 §5.2).

Nucleus's differentiation vs existing Iceberg MCP servers (`cloudera/iceberg-mcp-server`, `dragonejt/iceberg-mcp-server`): those servers expose raw Iceberg files. Nucleus's server surfaces `asset` graph, `contract` compliance status, `lineage`, `freshness`, and materialisation `runs` through the `ctx` SDK — the semantic layer that raw Iceberg tools lack.

Proposed scope (~500 LOC, `src/nucleus/mcp/server.py`, v0.5):

**Four tools:**
- `list_assets(filter: str?)` → asset keys, schema columns, freshness, contract status
- `query_asset(asset_key: str, sql: str, max_rows: int = 100)` → rows (read-only DuckDB, 1,000 max enforced)
- `get_lineage(asset_key: str, depth: int = 2)` → upstream + downstream asset key pairs
- `get_runs(asset_key: str, n: int = 5)` → last N materialisation results + NE-codes for failures

**Four resources (read-only URIs):**
- `nucleus://assets`, `nucleus://assets/{key}`, `nucleus://lineage/{key}`, `nucleus://errors/recent`

**Security guardrails** (non-negotiable per R3 §7.3):
1. `query_asset` runs inside `duckdb.connect(read_only=True)`
2. Pre-call parse blocks DDL, DML, COPY, EXPORT
3. Hard tool-call budget: default 10 per session → `NucleusBudgetExceededError`
4. All calls logged to `.nucleus/mcp.log` (no data values)
5. stdio transport only — zero network exposure

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Standalone nucleus-mcp-server, stdio, v0.5** | ~500 LOC, `nucleus serve --mcp` CLI command, four tools + four resources, hard guardrails | ✅ SELECTED — scoped, additive, zero new user-facing complexity |
| B — Integrate into Workbench v0.3 | Add MCP endpoint to FastAPI server | ❌ REJECTED — mixes HTTP REST and stdio concerns; complicates Workbench surface |
| C — Skip MCP entirely | Use REST API for AI agent integration | ❌ REJECTED — MCP is the ambient protocol; all major AI hosts adopt it; building against REST requires custom client per tool |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A** at v0.5.

**MUST VERIFY before writing ADR body:**
- MCP Python SDK package name and current version on PyPI (R3 NV #3: check https://github.com/modelcontextprotocol/python-sdk)
- OpenLineage RFC #4484 (MCP-to-lineage) resolution status before implementing any MCP lineage tracking (R4 §1.3)

---

## Consequences

- **LOC budget impact**: ~500 LOC (`src/nucleus/mcp/server.py` + CLI command)
- **1 new runtime dependency**: `mcp` (Python SDK) — version to be confirmed
- **Depends on**: ADR-029 (MetricFlow semantic YAML) for `list_assets` asset descriptions; Marquez v0.3 (ADR-033) for `get_lineage` Marquez backend
- **Maintenance ownership**: Intelligence layer
- **Swap target**: MCP spec is protocol-level; the Python SDK could be swapped without changing tool definitions

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §7.3 (AI Copilot — MCP integration)
- `nucleus_architecture_v4.1.md` §18.4 (v0.5 roadmap)
