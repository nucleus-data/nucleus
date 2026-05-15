---
title: Write SQL Transformations
description: Author SQL transforms with @nucleus.sql_asset and the Jinja {{ ref() }} pattern.
---

# Write SQL Transformations

Nucleus provides a native SQL asset decorator — `@nucleus.sql_asset` — that uses Jinja templating to resolve asset references. If you know dbt, this is familiar.

## The `@nucleus.sql_asset` decorator

```python
import nucleus


@nucleus.sql_asset(
    table="analytics.daily_revenue",
    schedule="@daily",
    materialized="table",   # "table" | "view" | "incremental"
)
def daily_revenue(ctx) -> str:
    return """
        SELECT
            order_date,
            SUM(amount)  AS revenue,
            COUNT(*)     AS order_count
        FROM {{ ref('staging.orders') }}
        WHERE status = 'completed'
        GROUP BY 1
        ORDER BY 1 DESC
    """
```

## `{{ ref() }}` — the Jinja asset reference

`{{ ref('staging.orders') }}` resolves to the underlying DuckDB Iceberg scan path at query time. It is the equivalent of dbt's `ref()`.

```sql
-- This Jinja template:
SELECT * FROM {{ ref('staging.orders') }}

-- Resolves to something like:
SELECT * FROM iceberg_scan('s3://localhost:9000/warehouse/staging.orders/')
```

## Materialization modes

| Mode | What it does |
|------|-------------|
| `"table"` | Full overwrite on every run (default) |
| `"view"` | Creates a DuckDB view; no data written |
| `"incremental"` | Appends new rows since last run (v0.2+) |

## Multi-statement SQL

Use a list of strings for CTEs or multi-step transforms:

```python
@nucleus.sql_asset(table="analytics.cohort_sizes")
def cohort_sizes(ctx) -> str:
    return """
        WITH cohort_base AS (
            SELECT
                customer_id,
                DATE_TRUNC('month', first_order_date) AS cohort_month
            FROM {{ ref('dim.customers') }}
        ),
        cohort_counts AS (
            SELECT
                cohort_month,
                COUNT(DISTINCT customer_id) AS cohort_size
            FROM cohort_base
            GROUP BY 1
        )
        SELECT * FROM cohort_counts
        ORDER BY cohort_month
    """
```

## Parameterized queries

```python
@nucleus.sql_asset(
    table="analytics.revenue_by_region",
    params={"min_revenue": 1000},
)
def revenue_by_region(ctx) -> str:
    return """
        SELECT region, SUM(amount) AS revenue
        FROM {{ ref('staging.orders') }}
        GROUP BY 1
        HAVING SUM(amount) >= {{ params.min_revenue }}
    """
```

## Mixing Python and SQL

You can call `ctx.sql()` inside a Python asset:

```python
import nucleus
import polars as pl


@nucleus.asset(table="analytics.summary")
def summary(ctx) -> pl.DataFrame:
    # SQL for the heavy aggregation
    result = ctx.sql("""
        SELECT
            region,
            SUM(amount) AS revenue
        FROM {{ ref('staging.orders') }}
        GROUP BY 1
    """)
    # Python for post-processing
    return result.collect().filter(pl.col("revenue") > 0)
```

## DuckDB SQL features available

Since `ctx.sql` runs in DuckDB, all DuckDB-specific SQL is available:

```sql
-- Window functions
SELECT
    order_date,
    revenue,
    SUM(revenue) OVER (ORDER BY order_date) AS cumulative_revenue
FROM {{ ref('analytics.daily_revenue') }}

-- Date functions
SELECT DATE_TRUNC('week', order_date) AS week_start, ...

-- Array aggregation
SELECT customer_id, LIST(product_id) AS products, ...

-- ASOF JOIN (DuckDB-specific)
SELECT ... FROM left ASOF JOIN right ON ...
```

Docs: https://duckdb.org/docs/sql/query_syntax/

## SQL scope ceiling

Per [architecture v4.1 §5.6](../philosophy/wrap-not-build.md), the native `ctx.sql` Jinja resolver is intentionally kept ≤2500 LOC with no macro ecosystem, no semantic layer. This keeps the platform simple and auditable. Complex macro needs → use dbt-duckdb (v0.3+ optional adapter).

## Common errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusSQLSyntaxError` | NE2002 | Invalid SQL; DuckDB parse error |
| `NucleusAssetNotFound` | NE3002 | `{{ ref('..') }}` references unknown asset key |
| `NucleusResourceError` | NE2003 | Query exceeded DuckDB memory limit |
