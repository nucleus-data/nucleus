"""Quality checks — data freshness on the silver layer."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import polars as pl

import nucleus
import nucleus.ctx as ctx
from nucleus import CheckResult

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")


@nucleus.check("silver.daily_sensor_metrics")
def silver_has_recent_days():
    """Fail when the latest ``day`` is older than 90 calendar days vs today."""
    df = ctx.read("silver.daily_sensor_metrics", warehouse_dir=WAREHOUSE).collect()
    if len(df) == 0:
        return CheckResult(passed=False, metric=0.0, message="silver layer is empty")
    max_day = df.select(pl.col("day").max()).item()
    try:
        latest = date.fromisoformat(str(max_day))
    except ValueError:
        return CheckResult(
            passed=False,
            metric=0.0,
            message=f"could not parse latest day from {max_day!r}",
        )
    stale_limit = date.today() - timedelta(days=90)
    ok = latest >= stale_limit
    return CheckResult(
        passed=ok,
        metric=float((date.today() - latest).days),
        message=f"latest silver day = {latest} (limit {stale_limit})",
    )


@nucleus.check("gold.weekly_metrics")
def gold_has_devices():
    df = ctx.read("gold.weekly_metrics", warehouse_dir=WAREHOUSE).collect()
    n = len(df)
    return CheckResult(
        passed=n > 0,
        metric=float(n),
        message=f"gold device groups = {n}",
    )
