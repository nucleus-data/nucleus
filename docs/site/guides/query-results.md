---
title: Query Results
description: Use nucleus query and ctx.sql to run DuckDB SQL against your Iceberg assets.
---

# Query Results

Once assets are materialized, you can query them with SQL via the CLI or the Python SDK.

## CLI queries

```bash
# Inline SQL
nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }} LIMIT 10"

# From a file
nucleus query --file ./queries/revenue.sql

# By asset key (SELECT * automatically)
nucleus query --asset analytics.daily_revenue --limit 50

# JSON output (pipe-friendly)
nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }}" --format json | jq .revenue

# CSV output
nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }}" --format csv > report.csv
```

## Python SDK

```python
import nucleus.ctx as ctx

# Returns a DuckDB relation — call .fetchdf() or .pl() for DataFrames
result = ctx.sql("SELECT * FROM {{ ref('analytics.daily_revenue') }} LIMIT 10")
df = result.pl()  # Polars DataFrame

# Or read an entire asset
df = ctx.read("analytics.daily_revenue")
```

## Jinja resolution

All `{{ ref('...') }}` references resolve at query time to the DuckDB Iceberg scan path. This means:

```sql
-- This works
SELECT a.*, b.customer_name
FROM {{ ref('sales.orders') }} a
JOIN {{ ref('dim.customers') }} b ON a.customer_id = b.id
WHERE a.order_date >= CURRENT_DATE - INTERVAL 30 DAY
```

## DuckDB SQL functions

DuckDB supports a rich SQL dialect. Some commonly useful functions:

```sql
-- Date truncation
DATE_TRUNC('month', order_date)

-- Window functions
SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date)

-- Unnesting arrays
SELECT UNNEST(tags) AS tag FROM {{ ref('analytics.tagged_events') }}

-- QUALIFY (filter on window functions)
SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) AS rn
FROM {{ ref('raw.events') }}
QUALIFY rn = 1
```

Full DuckDB SQL reference: https://duckdb.org/docs/sql/query_syntax/

## Pagination

For large result sets, the CLI auto-paginates through `less -R` on TTY. Override:

```bash
nucleus query "SELECT * FROM {{ ref('analytics.large_table') }}" --no-page
```

## Errors

| Error | Code | Fix |
|-------|------|-----|
| `NucleusSQLSyntaxError` | NE2002 | Fix the SQL; check column names |
| `NucleusAssetNotFound` | NE3002 | Asset key not registered; run `nucleus run <key>` first |
| `NucleusAssetNotMaterialized` | NE3003 | Asset is defined but never ran; run `nucleus run <key>` |
| `NucleusResourceError` | NE2003 | Memory limit exceeded; add `LIMIT`, filter, or use `SUMMARIZE` |
