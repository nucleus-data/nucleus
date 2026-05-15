---
title: Asset
description: The fundamental data primitive in Nucleus — a named, versioned Iceberg table with declared transformations, contracts, and lineage.
---

# Asset

An **asset** is the fundamental data primitive in Nucleus. Every piece of data you work with — raw ingested tables, staged transformations, analytical marts — is an asset.

Formally, an asset is:

> An Iceberg-backed table produced by a Python or SQL function, with declared transformations, optional contracts, and automatic lineage — consumable by BI tools, applications, or AI agents.

## The asset model

```
Asset = name + function + metadata
         │         │           └── schedule, owner, tags, freshness SLA
         │         └── returns pl.DataFrame | pl.LazyFrame | pyarrow.Table
         └── "sales.daily_revenue" — namespace.name (3-level at v0.3+)
```

## Defining an asset

```python
import nucleus
import polars as pl


@nucleus.asset(
    table="sales.daily_revenue",         # required: asset key
    schedule="@daily",                    # optional: when to materialize
    deps=["raw.orders"],                  # optional: explicit deps (auto-derived from ctx.read)
    owner="data@example.com",             # optional: ownership annotation
    description="Daily revenue by date",  # optional: visible in Workbench + lineage
    tags=["bi-ready", "finance"],         # optional: for search + filtering
    freshness=nucleus.freshness(hours=24),# optional: SLA target
    retries=nucleus.retries(count=3, delay="exponential"),  # optional
)
def daily_revenue(ctx) -> pl.DataFrame:
    orders = ctx.read("raw.orders")
    return orders.group_by("date").agg(pl.col("amount").sum())
```

## Asset key naming

Asset keys follow `<namespace>.<name>` (two-level in v0.1):

- `raw.orders` — ingested from a source, no transformations
- `staging.orders` — lightly cleaned
- `mart.daily_revenue` — BI-ready aggregate
- `analytics.cohort_retention` — derived insight

Three-level keys (`catalog.namespace.name`) are reserved for v0.3+ multi-catalog setups.

## Source assets

External data sources that aren't produced by Nucleus are declared as **source assets**:

```python
@nucleus.source(
    name="raw.orders",
    connector="postgres",
    connection="prod-db",
    schedule="@hourly",
    incremental_key="updated_at",
)
def raw_orders(ctx):
    return ctx.connector.postgres(table="public.orders")
```

Sources are leaves in the asset graph — they produce data but don't depend on other assets.

## Asset lifecycle

```
define (decorator) → materialize (nucleus run) → snapshot (Iceberg commit) → serve (ctx.read / query)
```

Every materialization produces one Iceberg snapshot. Snapshots are immutable; you can travel back to any point in time. See [Snapshot](snapshot.md).

## Relationship to Iceberg

Each asset corresponds to exactly one Iceberg table. The table name in the catalog is derived from the asset key. This 1:1 mapping is intentional: when you graduate to Databricks or Snowflake, you point at the same Iceberg table path and your data is immediately accessible.

## Asset graph

Assets form a directed acyclic graph (DAG) through `deps` declarations and `ctx.read()` calls:

```
raw.orders ──────────────┐
                         ▼
raw.customers ──▶ staging.orders ──▶ mart.daily_revenue
```

`nucleus run --all` executes the full graph in dependency order.

## Vocabulary note

Nucleus uses **asset** consistently. Never say "table" (as a primitive), "job", or "task" when referring to an asset. See [AGENTS.md §7](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md#7-vocabulary-use-these-terms).
