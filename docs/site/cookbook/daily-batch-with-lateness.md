---
title: Daily Batch with Lateness
description: Handle late-arriving rows without reprocessing the entire history.
---

# Daily Batch with Lateness

Late data is a fact of life. This pattern handles rows that arrive after their nominal processing window.

## Strategy: watermark with configurable lookback

Process the current day plus a configurable lookback window to catch late data:

```python
import nucleus
import polars as pl
from datetime import date, timedelta


@nucleus.asset(
    table="mart.daily_revenue",
    schedule="@daily",
)
def daily_revenue(ctx) -> pl.DataFrame:
    lookback_days = 3  # reprocess last 3 days to catch late arrivals
    cutoff = date.today() - timedelta(days=lookback_days)

    orders = ctx.read("staging.orders")
    return (
        orders
        .filter(pl.col("order_date") >= cutoff)
        .group_by("order_date")
        .agg(pl.col("amount").sum().alias("revenue"))
    )
```

Combine with `mode="merge"` to overwrite only the affected date partitions.

## Strategy: partition-based incremental

For partitioned assets, Iceberg's hidden partitioning lets you overwrite specific date partitions:

```python
@nucleus.asset(
    table="mart.daily_revenue_partitioned",
    partitions=nucleus.daily("2025-01-01"),
    schedule="@daily",
)
def daily_revenue_partitioned(ctx) -> pl.DataFrame:
    # Reprocess today + yesterday (catches late arrivals up to 24h)
    yesterday = date.today() - timedelta(days=1)
    orders = ctx.read("staging.orders").filter(
        pl.col("order_date") >= yesterday
    )
    return orders.group_by("order_date").agg(pl.col("amount").sum().alias("revenue"))
```

## Strategy: alerting on late data

Add a check that alerts when too much data is late:

```python
@nucleus.check(asset="mart.daily_revenue")
def check_today_has_data(ctx) -> nucleus.CheckResult:
    df = ctx.read("mart.daily_revenue")
    today = date.today()
    today_rows = df.filter(pl.col("order_date") == today)
    return nucleus.CheckResult(
        passed=len(today_rows) > 0,
        metric=len(today_rows),
        message=f"Today ({today}) has {len(today_rows)} revenue rows",
    )
```

## Strategy: explicit lateness SLA

Declare a freshness SLA on the asset:

```python
@nucleus.asset(
    table="mart.daily_revenue",
    freshness=nucleus.freshness(hours=25),  # must be materialized within 25h
    schedule="@daily",
)
def daily_revenue(ctx) -> pl.DataFrame:
    ...
```

`nucleus.freshness` is surfaced in the Workbench (v0.2+) as a staleness warning when the asset hasn't been materialized within the declared window.
