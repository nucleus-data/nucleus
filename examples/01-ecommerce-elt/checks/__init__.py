"""Schema checks (``@nucleus.check``) for the e-commerce example.

v0.1 runs each check with zero arguments; bodies read the warehouse via ``ctx``.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

import nucleus
import nucleus.ctx as ctx
from nucleus import CheckResult

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")


@nucleus.check("raw.orders")
def raw_orders_has_rows():
    df = ctx.read("raw.orders", warehouse_dir=WAREHOUSE).collect()
    n = len(df)
    return CheckResult(
        passed=n > 0,
        metric=float(n),
        message=f"raw.orders row count = {n}",
    )


@nucleus.check("stg.orders")
def stg_orders_primary_key_present():
    df = ctx.read("stg.orders", warehouse_dir=WAREHOUSE).collect()
    nulls = df.filter(pl.col("order_id").is_null()).height
    return CheckResult(
        passed=nulls == 0,
        metric=float(nulls),
        message=f"null order_id rows = {nulls}",
    )


@nucleus.check("marts.daily_revenue")
def daily_revenue_non_negative():
    df = ctx.read("marts.daily_revenue", warehouse_dir=WAREHOUSE).collect()
    bad = df.filter(pl.col("revenue_usd") < 0).height
    return CheckResult(
        passed=bad == 0,
        metric=float(bad),
        message=f"negative revenue rows = {bad}",
    )
