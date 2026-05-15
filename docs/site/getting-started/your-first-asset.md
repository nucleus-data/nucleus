---
title: Your First Asset
description: A step-by-step guide to defining and materializing your first @nucleus.asset.
---

# Your First Asset

This guide walks through writing a `@nucleus.asset` from first principles — what the decorator does, how `ctx` works, and how to add contracts and checks.

## What is an asset?

An **asset** in Nucleus is a named, versioned Iceberg table produced by a Python function. Every time you call `nucleus run`, the function executes, writes a new Iceberg snapshot, and emits lineage metadata. See [Concepts: Asset](../concepts/asset.md) for the full model.

## The minimal asset

```python
# assets/orders.py
import nucleus
import polars as pl


@nucleus.asset(table="sales.orders")
def orders(ctx) -> pl.DataFrame:
    """Raw orders ingested from the source database.

    This asset returns a Polars DataFrame; the runtime
    converts it to an Iceberg snapshot automatically.
    """
    return ctx.read("raw.orders")
```

Three things define this asset:

1. **`table`** — the three-level Iceberg key: `<namespace>.<name>` (two-level is v0.1 default)
2. **The function name** — must match the last part of `table` by convention
3. **`ctx`** — the context object the runtime passes in; never import it directly

## Return types

The `ctx` runtime accepts several return types:

| Return type | When to use |
|-------------|-------------|
| `polars.DataFrame` | Python transforms (most common) |
| `polars.LazyFrame` | Memory-efficient when source is large |
| `pyarrow.Table` | When reading Arrow from external sources |
| `duckdb.DuckDBPyRelation` | SQL-heavy transforms via `ctx.sql` |
| `None` | When you use `ctx.write(df)` explicitly |

## Adding a schedule

```python
@nucleus.asset(
    table="analytics.daily_revenue",
    schedule="@daily",          # or "0 2 * * *" (cron)
)
def daily_revenue(ctx) -> pl.DataFrame:
    ...
```

Nucleus validates the cron expression at import time and raises `NucleusScheduleParseError` (NE5005) immediately if it's invalid. Active execution of schedules requires `nucleus schedule on` (v0.2).

## Declaring dependencies

Dependencies are usually auto-derived from `ctx.read()` calls. You can also be explicit:

```python
@nucleus.asset(
    table="analytics.revenue_by_product",
    deps=["sales.orders", "dim.products"],
)
def revenue_by_product(ctx) -> pl.DataFrame:
    orders = ctx.read("sales.orders")
    products = ctx.read("dim.products")
    return orders.join(products, on="product_id")
```

## Adding a contract

Contracts enforce schema and quality rules that must hold every materialization:

```python
import nucleus

@nucleus.contract("analytics.daily_revenue")
class DailyRevenueContract:
    schema = {
        "order_date": "date",
        "revenue": "float64",
        "order_count": "int64",
    }
    not_null = ["order_date", "revenue"]
    unique = ["order_date"]
```

## Adding a check

Checks are imperative quality assertions that run after materialization:

```python
import nucleus
import polars as pl


@nucleus.check(asset="analytics.daily_revenue")
def check_revenue_positive(ctx) -> nucleus.CheckResult:
    df = ctx.read("analytics.daily_revenue")
    bad = df.filter(pl.col("revenue") <= 0)
    return nucleus.CheckResult(
        passed=len(bad) == 0,
        metric=len(bad),
        message=f"{len(bad)} rows with non-positive revenue",
    )
```

## Materializing the asset

```bash
nucleus run analytics.daily_revenue
```

Or from Python:

```python
import nucleus

result = nucleus.materialize("analytics.daily_revenue")
print(result.rows_written, result.duration_ms)
```

## What happens under the hood

When you call `nucleus run`:

1. **Validate** — `ctx` checks the schema contract (if any)
2. **Partition** — `ctx` applies any partition spec
3. **Compute** — your function body executes
4. **Atomic commit** — pyiceberg writes an Iceberg snapshot atomically
5. **Lineage** — an OpenLineage event is emitted to the local transport

All five steps happen behind the `ctx` abstraction. Error messages never leak Dagster or Iceberg class names. See [Error Translation](../governance/error-translation-discipline.md).

## Next steps

- [SQL Transformations](../guides/write-sql-transformations.md) — `@nucleus.sql_asset` with Jinja `{{ ref() }}`
- [Concepts: Asset](../concepts/asset.md) — the full asset model
- [Concepts: Materialization](../concepts/materialization.md) — what happens on every run
- [First BI-Ready Table](first-bi-table.md) — connecting to a BI tool
