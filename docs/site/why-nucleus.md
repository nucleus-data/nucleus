---
title: Why Nucleus
description: How Nucleus compares to dbt, Dagster, Airflow, and Databricks for small data engineering teams.
---

# Why Nucleus

The data engineering toolchain has fragmented into a constellation of excellent point tools that don't quite fit together: a SQL transformer over here, an orchestrator over there, an Iceberg write adapter bolted on, a BI connector hanging off the side. **Nucleus is the single, coherent surface that wraps the best of those tools** — without hiding what's underneath.

## The problem it solves

A typical early-stage data team spends its first month wiring tools together rather than shipping data products:

1. **dbt** for SQL transforms — but dbt needs a runner, and its Iceberg adapter is community-maintained
2. **Dagster or Airflow** for orchestration — but now you have a second mental model on top of dbt
3. **pyiceberg** for table writes — but atomic commits + schema evolution requires careful wiring
4. **MinIO or S3** for storage — but the endpoint config differs between dev and prod
5. **Some BI connector** pointing at the Iceberg tables — but it needs a REST catalog that you haven't set up yet

Nucleus replaces that wiring with one coherent product. You define assets in Python or SQL, run `nucleus up`, and get a working local stack. The orchestration, Iceberg writes, schema contracts, and lineage tracking are handled automatically.

## Honest comparison

### vs. dbt-core

| Dimension | dbt-core | Nucleus |
|-----------|----------|---------|
| SQL transforms | Excellent macro ecosystem | `ctx.sql` + Jinja; smaller ecosystem but no external runner needed |
| Asset graph | Models + seeds + snapshots | `@nucleus.asset` graph with explicit deps |
| Orchestration | Needs dbt Cloud or separate runner | Embedded (Dagster, hidden) |
| Iceberg support | Adapter-dependent | Native, first-class |
| Python assets | Limited (dbt-py) | Full Python (`@nucleus.asset` returns DataFrames) |
| Local dev | Fast for SQL; clunky for Iceberg | `nucleus up` → local Iceberg in &lt;10s |

**When to pick dbt:** Your team is SQL-first, you have an existing dbt project, and you need the full macro + package ecosystem. Nucleus can supplement by handling Iceberg writes and the asset graph.

**When to pick Nucleus:** You're greenfield, want Python and SQL unified under one model, and need Iceberg from day one without cloud infrastructure.

### vs. Dagster

| Dimension | Dagster | Nucleus |
|-----------|---------|---------|
| Asset graph | Excellent — industry-leading | Built on top of Dagster's internals (hidden) |
| Orchestration | Full featured | Embedded v0.1; active scheduling in v0.2 |
| Iceberg | DIY wiring | Native |
| Error messages | Dagster-framework language | Translated to Nucleus language (no Dagster class names) |
| Developer surface | `@asset`, `@op`, Resources, Config... | One decorator: `@nucleus.asset` |
| Boot time | Several seconds (large framework) | &lt;10s including storage + catalog |

**When to pick Dagster standalone:** You need multi-team lineage, complex IO managers, Dagster Cloud, or the full framework surface. Nucleus wraps Dagster for the common 80% case; the remaining 20% needs the full tool.

**When to pick Nucleus:** You want Dagster's asset model without learning Dagster's framework concepts.

### vs. Airflow

| Dimension | Airflow | Nucleus |
|-----------|---------|---------|
| Maturity | Very high — 10+ years | Beta — v0.1 |
| Learning curve | High (DAGs, operators, hooks, connections) | Low — Python decorators + one CLI |
| Iceberg support | Plugin-dependent | Native |
| Local dev | Heavy (docker-compose mandatory) | `nucleus up` = one command |
| Table format | None native | Iceberg tables everywhere |

**When to pick Airflow:** Your company already runs Airflow at scale, you need its ecosystem of 1000+ operators, or you're processing petabyte-scale workloads on distributed clusters.

**When to pick Nucleus:** You want to start shipping before you need enterprise orchestration.

### vs. Databricks

This comparison deserves honesty: **Databricks is an enterprise-grade, distributed compute platform. Nucleus is a local-first developer tool.** We don't compete on the same dimension.

| Dimension | Databricks | Nucleus |
|-----------|------------|---------|
| Scale | Petabytes, distributed, GPU clusters | &lt;10TB on a laptop or small node |
| Cost | Dollar-per-minute cluster costs | Free (open source core) |
| Iceberg | Delta Lake primarily; Iceberg via Unity | Iceberg-native everywhere |
| Setup time | Hours to configure a workspace | &lt;10 minutes to first asset |
| Vendor dependency | High | Zero — Apache-2.0 core, Iceberg portability |
| Graduation path | Nucleus → Databricks via Iceberg portability | ✅ No migration needed |

**The graduation story:** When your team outgrows Nucleus, your Iceberg data travels with you to Databricks, Snowflake, or any Iceberg REST catalog. No ETL migration, no vendor conversion. That's the point of Iceberg portability.

See the full mapping: [`docs/specs/nucleus_vs_databricks.md`](https://github.com/nucleus-data/nucleus/blob/main/nucleus_vs_databricks.md) in the repo.

## What Nucleus is not

Per the [Five Pillars](philosophy/five-pillars.md), Nucleus deliberately avoids several framings:

- **Not a "Data OS"** — we don't own infrastructure or compute <!-- banned-term: Data OS -->
- **Not an AI-native platform** — AI is a feature, not the product headline; it's opt-in and privacy-gated <!-- banned-term: AI-native -->
- **Not a Spark replacement** — we yield to distributed compute (Databricks, Snowflake) for petabyte-scale work
- **Not an ML platform** — no model training, feature stores, or model serving
- **Not a competitor to Databricks** — we integrate and yield to giants rather than fight them

## The design principle

> **Wrap, don't build.** Every component Nucleus touches (DuckDB, Polars, Dagster, pyiceberg) is a best-of-breed open-source library that already solves the problem. Nucleus adds the integration layer, the error translation, the CLI ergonomics, and the AI assistance. Nothing more.

[Five Pillars →](philosophy/five-pillars.md) · [Wrap, not build →](philosophy/wrap-not-build.md) · [Yield to giants →](philosophy/yield-to-giants.md)
