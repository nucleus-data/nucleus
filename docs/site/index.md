---
title: Nucleus — Ship data products from a laptop
description: A local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks, AI-ready by design.
hide:
  - navigation
  - toc
---

<div class="nucleus-hero">
  <h1>Ship data products from a laptop.</h1>
  <p class="hero-tagline">
    A modern, composable data engineering platform.<br>
    Iceberg-native. AI-assisted. Yields to giants when you outgrow it.
  </p>
  <div class="hero-actions">
    <a href="getting-started/quickstart/" class="md-button">Get started in 30 min →</a>
    <a href="why-nucleus/" class="md-button md-button--secondary">Why Nucleus?</a>
  </div>
</div>

## 30-second demo

=== "Python SDK"

    ```python
    import nucleus
    import polars as pl

    @nucleus.asset(
        table="sales.daily_revenue",
        schedule="@daily",
        description="Daily revenue aggregated from cleaned orders",
    )
    def daily_revenue(ctx) -> pl.DataFrame:
        df = ctx.read("sales.orders")
        return (
            df
            .filter(pl.col("status") == "completed")
            .group_by("order_date")
            .agg(pl.col("amount").sum().alias("revenue"))
        )
    ```

=== "SQL Transform"

    ```python
    import nucleus

    @nucleus.sql_asset(
        table="analytics.daily_revenue",
        schedule="@daily",
        materialized="table",
    )
    def daily_revenue(ctx) -> str:
        return """
            SELECT
                order_date,
                SUM(amount) AS revenue,
                COUNT(*) AS order_count
            FROM {{ ref('sales.orders') }}
            WHERE status = 'completed'
            GROUP BY 1
        """
    ```

=== "CLI"

    ```bash
    # Scaffold a new project
    nucleus init my-analytics && cd my-analytics

    # Start the local stack (<10 seconds)
    nucleus up

    # Ingest Postgres into Iceberg
    nucleus ingest postgres://localhost/prod \
      --table public.orders \
      --as raw.orders

    # Run your asset graph
    nucleus run --all

    # Query the result
    nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }} LIMIT 10"
    ```

---

## Why teams choose Nucleus

<div class="feature-grid">

<div class="feature-card">
  <span class="feature-icon">🏠</span>
  <h3>Local-first, no clusters needed</h3>
  <p>Boot in &lt;10 seconds on a laptop. DuckDB + Polars replace cluster compute for &lt;10TB datasets. Zero cloud spend while building.</p>
</div>

<div class="feature-card">
  <span class="feature-icon">🧊</span>
  <h3>Iceberg-native from day one</h3>
  <p>Every asset is an Iceberg table. When your team outgrows a laptop, your data goes with you to Databricks, Snowflake, or any Iceberg catalog — no migration, no vendor lock.</p>
</div>

<div class="feature-card">
  <span class="feature-icon">🔧</span>
  <h3>Open Apache foundations</h3>
  <p>Apache Iceberg, Arrow, and Parquet at the core. MIT-licensed DuckDB and Polars for compute. Apache-2.0 everywhere. Your data is yours.</p>
</div>

<div class="feature-card">
  <span class="feature-icon">🤖</span>
  <h3>AI-assisted, not AI-dependent</h3>
  <p>Copilot helps you write assets, debug errors, and explore your data graph. Opt-in, privacy-gated, works with Anthropic, OpenAI, or local Ollama.</p>
</div>

<div class="feature-card">
  <span class="feature-icon">🔄</span>
  <h3>Composable by constitution</h3>
  <p>Every wrapped engine (DuckDB, Polars, Dagster) has a clean swap interface. We don't lock you into our choices.</p>
</div>

<div class="feature-card">
  <span class="feature-icon">⚡</span>
  <h3>Familiar developer experience</h3>
  <p>If you know dbt, Dagster, or SQLAlchemy, you know 80% of Nucleus. Git-native projects. Standard Python. No DSL to learn.</p>
</div>

</div>

---

## From git clone to BI-ready table in under 30 minutes

```
git clone https://github.com/nucleus-data/nucleus && cd nucleus
pip install -e ".[dev]"                                   # or: pip install nucleus-data

nucleus init beachhead-demo && cd beachhead-demo
nucleus up                                                 # MinIO + catalog + definitions ready
nucleus ingest postgres://user:pass@host/db \
  --table public.orders --as raw.orders
nucleus run --all                                          # materializes every asset
nucleus query "SELECT * FROM {{ ref('sales.daily_revenue') }} LIMIT 20"
```

**The 30-minute target is the whole point.** See the [full quickstart →](getting-started/quickstart.md)

---

## Beachhead persona

Nucleus v0.1 is designed exclusively for:

> **~5 engineers. ~100GB–5TB. Greenfield project. MacBooks or Linux.**

If that's your team, read the [installation guide](getting-started/installation.md). If you're a solo analyst, an enterprise with IAM requirements, or a team running petabyte-scale distributed compute — Nucleus will serve you in later versions. Check the [roadmap](community/roadmap.md).

---

## Architecture in one picture

Nucleus is five layers over open-source foundations:

| Layer | What it is | How we handle it |
|-------|------------|-----------------|
| **Physics** | Arrow, Iceberg, Parquet, S3 | Immortal substrate — never replaced |
| **Engines** | DuckDB, Polars | Wrapped + swappable; DataFusion as swap target |
| **Coordination** | Dagster (hidden behind `ctx`) | Error-translated; replaceable by v1.0 |
| **Intelligence** | AI Copilot, error translator | Optional; privacy-first |
| **Experience** | `ctx` SDK, CLI, Workbench | The product we own forever |

[Dive into the architecture →](philosophy/five-pillars.md) · [Why we wrap instead of build →](philosophy/wrap-not-build.md)

---

!!! tip "v0.1 beta"
    Nucleus is beta software. The API is stable within v0.1; breaking changes follow [ADR-005](governance/architecture-decisions.md). Pin versions; read [`docs/internal/compatibility.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/compatibility.md) before upgrading.
