"""Staging assets: typed, cleaned relations over raw Iceberg assets."""

from __future__ import annotations

from pathlib import Path

import nucleus
import nucleus.ctx as ctx

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")


@nucleus.asset("stg.orders", deps=["raw.orders"])
def stg_orders():
    """Drop QA rows and expose USD amount as float."""
    sql = """
    SELECT
        order_id,
        customer_id,
        CAST(amount_cents AS DOUBLE) / 100.0 AS amount_usd,
        order_date
    FROM {{ ref('raw.orders') }}
    WHERE order_id NOT LIKE 'TEST-%'
    """
    return ctx.sql(sql, warehouse_dir=WAREHOUSE).collect()


@nucleus.asset("stg.customers", deps=["raw.customers"])
def stg_customers():
    """One row per customer (dedupe on natural key)."""
    sql = """
    SELECT
        customer_id,
        max(email) AS email,
        max(signup_ts) AS signup_ts
    FROM {{ ref('raw.customers') }}
    GROUP BY customer_id
    """
    return ctx.sql(sql, warehouse_dir=WAREHOUSE).collect()
