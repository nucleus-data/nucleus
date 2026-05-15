"""Gold layer asset — weekly revenue + top-20 product leaderboard.

Combines the silver daily_revenue and silver top_products assets into a
single denormalised view a BI tool can chart directly. Outputs ~one row
per (week × top-20 product), so the table stays small even after a year
of orders.
"""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import WAREHOUSE_DIR, load_sql


@nucleus.asset(
    "gold.revenue_dashboard",
    deps=["silver.daily_revenue", "silver.top_products"],
)
def gold_revenue_dashboard():
    """Materialize the executive revenue dashboard."""
    sql = load_sql("gold_revenue_dashboard")
    return ctx.sql(sql, warehouse_dir=WAREHOUSE_DIR).collect()
