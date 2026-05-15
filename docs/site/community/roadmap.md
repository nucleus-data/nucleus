---
title: Roadmap
description: What's coming in Nucleus v0.2, v0.3, v0.5, and v1.0.
---

# Roadmap

Per [architecture v4.1 §18](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md#18-roadmap).

!!! info "Honest note"
    This roadmap is for a solo-founder project. Timelines are best-case estimates contingent on a Mo 24 decision gate (3 months after beta: if &lt;10 active teams, roadmap is reassessed). See [ADR-002](../governance/architecture-decisions.md).

## v0.1 — Foundation (Mo 0-8) ✅ SHIPPED

**Beachhead:** 5-engineer team builds first BI-ready Iceberg table in &lt;30 minutes.

| Feature | Status |
|---------|--------|
| `nucleus init/up/down/run/ingest/query/version` | ✅ |
| `@nucleus.asset`, `@nucleus.sql_asset`, `@nucleus.check`, `@nucleus.contract` | ✅ |
| `ctx.copy_from` (Postgres, MySQL, SQLite, CSV, Parquet, JSON) | ✅ |
| `ctx.sql` + Jinja `{{ ref() }}` | ✅ |
| Filesystem Iceberg catalog + local warehouse | ✅ |
| Asset-level lineage (OpenLineage, file transport) | ✅ |
| `nucleus schedule list/preview` | ✅ |
| Beachhead E2E: 8/8 gates PASS, 7s boot, real Iceberg snapshot | ✅ |

## v0.2 — Developer Experience (Mo 8-14)

| Feature | Notes |
|---------|-------|
| `nucleus chat` — AI Copilot, single-turn | Anthropic, OpenAI, Ollama |
| `nucleus workbench` — Web IDE | Asset graph, SQL editor, run history |
| `nucleus schedule on/off/trigger` — Active scheduling | Dagster daemon wired |
| Incremental materializations | Watermark + append mode |
| `nucleus doctor` — Diagnostic checklist | |

## v0.3 — Connectors & Catalogs (Mo 14-20)

| Feature | Notes |
|---------|-------|
| Lakekeeper REST catalog integration | Migrate from filesystem |
| Apache Polaris as alternate catalog | `nucleus enable polaris` |
| dlt connectors (Snowflake, BigQuery, more) | `nucleus enable dlt` |
| S3 / GCS source connectors | `nucleus ingest s3://...` |
| Column-level lineage | sqlglot SQL walker |
| `nucleus snapshot list/restore` — Time travel | |
| Marimo notebooks | `nucleus enable marimo` |

## v0.5 — Intelligence (Mo 20-28)

| Feature | Notes |
|---------|-------|
| Lineage-aware AI Copilot | Knows your full asset graph |
| MCP server (`nucleus-mcp-server`) | Expose assets to AI agents via MCP |
| Lance / LanceDB for multimodal assets | Vector + Iceberg side-by-side |
| OpenTelemetry SDK + exporters | `nucleus enable observability` |
| Soda Core data quality | `nucleus enable soda` |

## v1.0 — General Availability (Mo 28-36)

| Feature | Notes |
|---------|-------|
| CLI commands Frozen | Stability per ADR-005 |
| `nucleus-mini-scheduler` fallback | Pure-Python scheduler |
| Full swap implementations on demand | If Dagster/DuckDB trigger fires |
| Enterprise IAM (OIDC RBAC at catalog level) | Per ADR-010 |

## What's explicitly not on the roadmap

- Custom SQL engine
- Distributed compute (yield to Databricks/Spark)
- ML platform / feature store / model serving
- Multi-tenant cloud control plane (Cloud tier only)
- Plugin marketplace

Per [Do Not Build list](../philosophy/wrap-not-build.md).
