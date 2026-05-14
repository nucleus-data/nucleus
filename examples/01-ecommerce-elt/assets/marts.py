"""Mart assets: analytics-ready rollups for dashboards."""

from __future__ import annotations

from pathlib import Path

import nucleus
import nucleus.ctx as ctx

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")


@nucleus.asset("marts.daily_revenue", deps=["stg.orders"])
def marts_daily_revenue():
    """Daily revenue for executive dashboard."""
    sql = """
    SELECT
        order_date AS day,
        cast(sum(amount_usd) AS double) AS revenue_usd
    FROM {{ ref('stg.orders') }}
    GROUP BY order_date
    ORDER BY order_date
    """
    return ctx.sql(sql, warehouse_dir=WAREHOUSE).collect()


@nucleus.asset("marts.customer_ltv", deps=["stg.orders", "stg.customers"])
def marts_customer_ltv():
    """Lifetime spend by customer."""
    sql = """
    SELECT
        o.customer_id,
        cast(sum(o.amount_usd) AS double) AS lifetime_revenue_usd
    FROM {{ ref('stg.orders') }} AS o
    INNER JOIN {{ ref('stg.customers') }} AS c
        ON o.customer_id = c.customer_id
    GROUP BY o.customer_id
    ORDER BY lifetime_revenue_usd DESC
    """
    return ctx.sql(sql, warehouse_dir=WAREHOUSE).collect()
