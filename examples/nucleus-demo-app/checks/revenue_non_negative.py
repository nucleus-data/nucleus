"""Business-rule check on ``silver.daily_revenue``.

Net revenue should never be negative — if the silver SQL accidentally
includes refund amounts as positive entries (or sums signs incorrectly)
this check catches the regression at materialization time.
"""

from __future__ import annotations

import polars as pl

import nucleus
import nucleus.ctx as ctx
from nucleus import CheckResult

from assets._common import WAREHOUSE_DIR


@nucleus.check("silver.daily_revenue")
def revenue_non_negative():
    """No row in silver.daily_revenue may have negative gross revenue."""
    df = ctx.read("silver.daily_revenue", warehouse_dir=WAREHOUSE_DIR).collect()
    bad = df.filter(pl.col("gross_revenue_usd") < 0).height
    return CheckResult(
        passed=bad == 0,
        metric=float(bad),
        message=f"{bad} day(s) recorded negative revenue.",
    )
