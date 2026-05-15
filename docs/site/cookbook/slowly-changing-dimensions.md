---
title: Slowly Changing Dimensions
description: Implement SCD Type 1 (overwrite) and Type 2 (history) in Nucleus.
---

# Slowly Changing Dimensions

## SCD Type 1 — overwrite

The simplest approach: overwrite the current value. No history retained.

```python
@nucleus.asset(
    table="dim.customers",
    schedule="@daily",
    deps=["raw.customers"],
)
def dim_customers(ctx) -> pl.DataFrame:
    return (
        ctx.read("raw.customers")
        .select(["customer_id", "name", "email", "country", "updated_at"])
        .unique(subset=["customer_id"], keep="last")
    )
```

## SCD Type 2 — track history with valid_from / valid_to

Keep a full history of changes:

```python
import nucleus
import polars as pl
from datetime import date


@nucleus.sql_asset(
    table="dim.customers_history",
    materialized="table",
)
def customers_history(ctx) -> str:
    return """
        WITH current AS (
            SELECT
                customer_id,
                name,
                email,
                country,
                updated_at AS valid_from,
                LEAD(updated_at) OVER (
                    PARTITION BY customer_id
                    ORDER BY updated_at
                ) AS valid_to,
                CASE
                    WHEN LEAD(updated_at) OVER (
                        PARTITION BY customer_id ORDER BY updated_at
                    ) IS NULL THEN TRUE
                    ELSE FALSE
                END AS is_current
            FROM {{ ref('raw.customers_changelog') }}
        )
        SELECT * FROM current
    """
```

## SCD Type 2 — incremental append

For large dimension tables, only append new history rows:

```python
@nucleus.asset(
    table="dim.customers_history",
    schedule="@daily",
)
def customers_history_incremental(ctx) -> pl.DataFrame:
    current = ctx.read("dim.customers_history")
    new_records = ctx.read("raw.customers")

    # Find customers whose attributes changed
    changed = (
        new_records
        .join(
            current.filter(pl.col("is_current")).select(["customer_id", "email", "country"]),
            on="customer_id",
            how="anti",  # rows in new_records NOT in current
        )
        .with_columns([
            pl.lit(date.today()).alias("valid_from"),
            pl.lit(None).cast(pl.Date).alias("valid_to"),
            pl.lit(True).alias("is_current"),
        ])
    )
    return changed
```

Use `mode="append"` when calling this asset:

```python
# nucleus_project.yaml
assets:
  dim.customers_history_incremental:
    write_mode: append
```
