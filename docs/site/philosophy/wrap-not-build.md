---
title: Wrap, Not Build
description: Why Nucleus integrates best-of-breed open-source rather than building its own engines.
---

# Wrap, Not Build

Nucleus's default answer to any engineering question is: **wrap an existing, production-grade open-source library. Do not build it yourself.**

## The principle

> For every proposed component, ask: "Which production-grade OSS handles this already?"

If the answer is DuckDB, Polars, Dagster, pyiceberg, dlt, sqlglot, or one of the other dozen libraries in the stack — wrap it. Don't reinvent it.

## Why wrap instead of build?

**1. OSS libraries are battle-tested at scale.** DuckDB runs at thousands of companies. Polars has millions of downloads. Dagster has years of production mileage. No custom engine Nucleus could build in v0.1 would have that depth of testing.

**2. The 30K LOC ceiling.** Per [architecture v4.1 §11.6](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md), the entire Nucleus proprietary code budget is 30,000 lines by v1.0. A custom SQL engine would consume the entire budget. A wrapper consumes &lt;500 lines.

**3. Community leverage.** When DuckDB ships a new feature, Nucleus users get it for free — no work required. When a security vulnerability is patched in pyiceberg, a single version bump fixes it for all users.

**4. Upgrade path.** Wrapped libraries upgrade independently. Building custom means carrying all maintenance forever.

## What Nucleus actually builds

Nucleus builds only the experience and intelligence layers:

| What we build | Why |
|---------------|-----|
| `ctx` SDK | The stable Python API contract — the product |
| `nucleus` CLI | The developer-first entry point |
| Asset Materialization Adapter (~500 LOC) | The five-step pipeline coordinator |
| Error Translation Layer | No Dagster/DuckDB class names in user errors |
| Native `ctx.sql` Jinja resolver (~1000 LOC) | Lighter than dbt-duckdb; fits our scope |
| AI Copilot integration | The differentiating intelligence layer |

Everything else is rented.

## The "Do NOT Build" list

Per [AGENTS.md §4](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md#4-the-do-not-build-list):

- ❌ SQL engine → DuckDB
- ❌ DataFrame engine → Polars
- ❌ Orchestration → Dagster
- ❌ Iceberg table format → Apache Iceberg
- ❌ Connectors → `ctx.copy_from` + dlt (v0.3+)
- ❌ Auth/RBAC → OIDC delegation (v0.3+)
- ❌ Distributed compute → yield to giants

## Anti-over-engineering discipline

The "wrap, not build" principle is a specific instance of a broader discipline:

> Code is a liability, not an asset. Every LOC is future maintenance, future review burden, future drift risk. The 30K LOC ceiling is a wall, not a target.

When you find yourself building something that an OSS library already does, stop. Read the library's docs (per [AGENTS.md §11.12](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md#1112-official-documentation-discipline-hard-constraint-10)), write a thin wrapper, and move on.
