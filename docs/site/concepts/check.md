---
title: Check
description: An imperative quality assertion that runs after an asset materializes.
---

# Check

A **check** is an imperative quality assertion that runs after an asset materializes successfully. Checks capture business logic that is too dynamic for a declarative contract: "revenue should never drop by more than 30% day-over-day," "there should be no duplicate order IDs in the last 7 days," etc.

## Defining a check

```python
import nucleus
import polars as pl


@nucleus.check(asset="analytics.daily_revenue")
def check_revenue_not_negative(ctx) -> nucleus.CheckResult:
    df = ctx.read("analytics.daily_revenue")
    bad_rows = df.filter(pl.col("revenue") < 0)
    return nucleus.CheckResult(
        passed=len(bad_rows) == 0,
        metric=len(bad_rows),
        message=f"{len(bad_rows)} rows with negative revenue",
    )
```

## CheckResult

```python
nucleus.CheckResult(
    passed=True,           # required: did the check pass?
    metric=0,              # optional: the measured value (count, ratio, etc.)
    message="All good",    # optional: human-readable summary
)
```

## Multiple checks per asset

An asset can have many checks. All checks run after each materialization; all results are recorded.

```python
@nucleus.check(asset="analytics.daily_revenue")
def check_no_future_dates(ctx) -> nucleus.CheckResult:
    import datetime
    df = ctx.read("analytics.daily_revenue")
    future = df.filter(pl.col("order_date") > datetime.date.today())
    return nucleus.CheckResult(
        passed=len(future) == 0,
        metric=len(future),
        message=f"{len(future)} rows with future dates",
    )

@nucleus.check(asset="analytics.daily_revenue")
def check_daily_revenue_coverage(ctx) -> nucleus.CheckResult:
    df = ctx.read("analytics.daily_revenue")
    # Should have at least 360 days of data after a full year
    return nucleus.CheckResult(
        passed=len(df) >= 360,
        metric=len(df),
        message=f"Got {len(df)} days, expected ≥ 360",
    )
```

## Checks vs. contracts

| | Check | Contract |
|--|-------|---------|
| When | After commit | Before commit |
| Style | Imperative (function) | Declarative (class) |
| On failure | Records failure; doesn't abort | Aborts materialization |
| Use for | Business logic, trends, ratios | Schema, nullability, uniqueness |

!!! tip "Recommendation"
    Use contracts for structural invariants and checks for business logic. A schema violation should abort; a suspicious revenue drop should be flagged but not necessarily block production.

## Viewing check results

```bash
# v0.3+
nucleus checks list analytics.daily_revenue
nucleus checks history analytics.daily_revenue --last 30
```

Until v0.3+, check results are written to the local `.nucleus/` state directory and visible in the Workbench (v0.2+).
