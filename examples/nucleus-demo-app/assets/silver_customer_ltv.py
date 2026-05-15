"""Silver layer asset — lifetime value per customer.

Joins bronze customer dimension to the bronze order fact table. Each row
is one customer; ``lifetime_revenue_usd`` is ``0.0`` (or null) for
customers who have not placed any non-refunded orders yet.
"""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import WAREHOUSE_DIR, load_sql


@nucleus.asset("silver.customer_ltv", deps=["bronze.orders", "bronze.customers"])
def silver_customer_ltv():
    """Compute lifetime revenue per customer from completed/shipped orders."""
    sql = load_sql("silver_customer_ltv")
    return ctx.sql(sql, warehouse_dir=WAREHOUSE_DIR).collect()
