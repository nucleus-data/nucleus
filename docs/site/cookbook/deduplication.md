---
title: Deduplication
description: Remove duplicate rows from Iceberg assets using window functions and row-number filters.
---

# Deduplication

## Pattern 1 — Polars deduplication (Python asset)

```python
@nucleus.asset(table="staging.orders_deduped", deps=["raw.orders"])
def orders_deduped(ctx) -> pl.DataFrame:
    return (
        ctx.read("raw.orders")
        .sort("updated_at", descending=True)
        .unique(subset=["order_id"], keep="first")
    )
```

`pl.DataFrame.unique(subset=, keep="first")` retains the first row per key after sorting, which gives you the latest record after sorting by `updated_at` descending.

Docs: https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.unique.html

## Pattern 2 — SQL ROW_NUMBER (sql_asset)

```python
@nucleus.sql_asset(table="staging.orders_deduped")
def orders_deduped(ctx) -> str:
    return """
        SELECT * EXCLUDE (rn)
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY updated_at DESC NULLS LAST
                ) AS rn
            FROM {{ ref('raw.orders') }}
        )
        WHERE rn = 1
    """
```

## Pattern 3 — QUALIFY clause (DuckDB-specific)

DuckDB supports `QUALIFY` to filter directly on window function results:

```sql
SELECT *
FROM {{ ref('raw.orders') }}
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY order_id
    ORDER BY updated_at DESC NULLS LAST
) = 1
```

## Deduplication check

Add a check to verify deduplication succeeded:

```python
@nucleus.check(asset="staging.orders_deduped")
def check_no_duplicate_order_ids(ctx) -> nucleus.CheckResult:
    df = ctx.read("staging.orders_deduped")
    total = len(df)
    unique = df.n_unique(subset=["order_id"])
    return nucleus.CheckResult(
        passed=(total == unique),
        metric=total - unique,
        message=f"{total - unique} duplicate order_ids remain",
    )
```
