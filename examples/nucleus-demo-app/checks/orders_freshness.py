"""Freshness check on ``bronze.orders``.

Asserts that the most recent order timestamp in the bronze snapshot is
within the last 30 days. Fires as ``severity="warn"`` so the
materialization succeeds but the operator gets a flag — useful when a
demo dataset goes stale because nobody re-ran the seed for a while.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl

import nucleus
import nucleus.ctx as ctx
from nucleus import CheckResult

from assets._common import WAREHOUSE_DIR

FRESHNESS_WINDOW_DAYS = 30


@nucleus.check("bronze.orders", severity="warn")
def orders_freshness():
    """Newest order in bronze.orders must be within the freshness window."""
    df = ctx.read("bronze.orders", warehouse_dir=WAREHOUSE_DIR).collect()
    if df.height == 0:
        return CheckResult(
            passed=False,
            metric=0.0,
            message="bronze.orders is empty — re-run `nucleus run bronze.orders`.",
        )
    latest = df.select(pl.col("order_ts").max()).item()
    if isinstance(latest, str):
        latest = datetime.fromisoformat(latest)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - latest).days
    return CheckResult(
        passed=age_days <= FRESHNESS_WINDOW_DAYS,
        metric=float(age_days),
        message=(
            f"newest order is {age_days} day(s) old "
            f"(window = {FRESHNESS_WINDOW_DAYS}d). "
            "Refresh demo data via `python scripts/generate_seed.py` if stale."
        ),
    )
