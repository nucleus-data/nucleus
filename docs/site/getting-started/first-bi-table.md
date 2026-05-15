---
title: First BI-Ready Table
description: End-to-end walkthrough — Postgres source to an Iceberg table queryable by Metabase, Superset, or any JDBC tool.
---

# First BI-Ready Table

This end-to-end guide takes a Postgres source to a queryable Iceberg asset accessible by any BI tool that speaks JDBC, DuckDB, or Iceberg REST.

## Prerequisites

- Nucleus installed and `nucleus up` running
- A Postgres database (or use the seed script below for a local one)
- (Optional) Metabase, Superset, or another BI tool

## Step 1 — Seed a Postgres database

If you don't have a database handy, use the ecommerce seed from the examples:

```bash
# Start a local Postgres (requires Docker)
docker run -d --name pg-demo \
  -e POSTGRES_USER=nucleus \
  -e POSTGRES_PASSWORD=nucleus \
  -e POSTGRES_DB=ecommerce \
  -p 5432:5432 postgres:15

# Seed the database
psql postgres://nucleus:nucleus@localhost:5432/ecommerce \
  -f examples/01-ecommerce-elt/scripts/seed_postgres.sql
```

## Step 2 — Ingest raw tables

```bash
# Ingest orders table as a raw asset
nucleus ingest postgres://nucleus:nucleus@localhost:5432/ecommerce \
  --table public.orders \
  --as raw.orders \
  --mode overwrite

# Ingest customers table
nucleus ingest postgres://nucleus:nucleus@localhost:5432/ecommerce \
  --table public.customers \
  --as raw.customers \
  --mode overwrite
```

Nucleus auto-infers the schema, creates the Iceberg tables, and commits atomically.

## Step 3 — Write staging transforms

Create `assets/staging/orders.py`:

```python
import nucleus
import polars as pl


@nucleus.asset(
    table="staging.orders",
    deps=["raw.orders"],
    description="Cleaned and typed orders",
)
def stg_orders(ctx) -> pl.DataFrame:
    return (
        ctx.read("raw.orders")
        .rename({"created_at": "order_date"})
        .with_columns([
            pl.col("order_date").cast(pl.Date),
            pl.col("amount").cast(pl.Float64),
            pl.col("status").str.to_lowercase(),
        ])
        .filter(pl.col("order_date").is_not_null())
    )
```

## Step 4 — Write the mart

Create `assets/marts/daily_revenue.py`:

```python
import nucleus
import polars as pl


@nucleus.asset(
    table="mart.daily_revenue",
    schedule="@daily",
    deps=["staging.orders"],
    description="BI-ready daily revenue mart",
    owner="data-team@example.com",
    tags=["bi-ready", "finance"],
)
def daily_revenue(ctx) -> pl.DataFrame:
    orders = ctx.read("staging.orders")
    return (
        orders
        .filter(pl.col("status") == "completed")
        .group_by("order_date")
        .agg([
            pl.col("amount").sum().alias("revenue"),
            pl.col("order_id").n_unique().alias("order_count"),
        ])
        .sort("order_date", descending=True)
    )
```

## Step 5 — Run the full pipeline

```bash
nucleus run --all
```

Output:

```
┌─────────────────────┬────────┬──────────┬────────┐
│ asset               │ status │ duration │ rows   │
├─────────────────────┼────────┼──────────┼────────┤
│ raw.orders          │ ✓ done │    1.2s  │  5,000 │
│ raw.customers       │ ✓ done │    0.8s  │    500 │
│ staging.orders      │ ✓ done │    0.4s  │  4,850 │
│ mart.daily_revenue  │ ✓ done │    0.3s  │    365 │
└─────────────────────┴────────┴──────────┴────────┘
4 assets materialized. All Iceberg snapshots committed.
```

## Step 6 — Query the BI mart

```bash
nucleus query "SELECT * FROM {{ ref('mart.daily_revenue') }} ORDER BY order_date DESC LIMIT 30"
```

## Step 7 — Connect a BI tool

=== "DuckDB (direct)"

    Your Iceberg tables are already readable via DuckDB:

    ```python
    import duckdb
    # Docs: https://duckdb.org/docs/extensions/iceberg

    con = duckdb.connect()
    con.execute("INSTALL iceberg; LOAD iceberg;")
    result = con.execute("""
        SELECT *
        FROM iceberg_scan('data/warehouse/mart.daily_revenue/')
        ORDER BY order_date DESC
        LIMIT 30
    """).fetchdf()
    ```

=== "Superset"

    1. Add a DuckDB database connection pointing to `data/warehouse/`
    2. Browse the `mart.daily_revenue` table in the SQL Lab
    3. Build dashboards as normal

    !!! note "Hosted catalog (v0.3+)"
        When you graduate to Lakekeeper or Polaris REST catalog, connect Superset to the REST endpoint for always-fresh Iceberg metadata.

=== "Metabase"

    Metabase's DuckDB driver reads Iceberg tables directly:

    1. Install the DuckDB driver for Metabase
    2. Configure the database path to your `data/warehouse/`
    3. Query `mart.daily_revenue` via the query builder

=== "Graduation (Databricks)"

    When your team outgrows a single node, your Iceberg tables travel with you:

    ```python
    # In Databricks
    spark.read.format("iceberg").load(
        "s3://your-bucket/mart.daily_revenue"
    )
    ```

    No schema conversion, no migration. The Iceberg snapshot is already there.

## What you built

```
Postgres (raw source)
  └─▶ raw.orders (Iceberg table, atomic commits)
        └─▶ staging.orders (cleaned + typed)
              └─▶ mart.daily_revenue (BI-ready, scheduled daily)
                    └─▶ BI tool (DuckDB / Superset / Metabase)
```

Every layer is an Iceberg table with:
- **Full version history** (Iceberg snapshots)
- **Schema contracts** (optional, declarative)
- **Quality checks** (optional, imperative)
- **Asset-level lineage** (emitted to OpenLineage transport)
- **Portability** (reads from any Iceberg catalog)

[Explore the ecommerce example →](https://github.com/nucleus-data/nucleus/tree/main/examples/01-ecommerce-elt)
