"""Silver layer asset — daily revenue from completed orders.

Reads its SQL body from ``sql/silver_daily_revenue.sql`` (the dbt-style
split between Python registration and SQL transform). The Jinja
``{{ ref('bronze.orders') }}`` macro is resolved by ``ctx.sql`` against
the local Iceberg catalog.
"""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import WAREHOUSE_DIR, load_sql


@nucleus.asset("silver.daily_revenue", deps=["bronze.orders"])
def silver_daily_revenue():
    """Aggregate revenue per day per channel from the bronze orders snapshot."""
    sql = load_sql("silver_daily_revenue")
    return ctx.sql(sql, warehouse_dir=WAREHOUSE_DIR).collect()
