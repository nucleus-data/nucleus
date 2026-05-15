"""Silver layer asset — revenue per SKU, ranked descending.

Powers the gold revenue dashboard (top-N products) and is also useful as
an ad-hoc list for category leads.
"""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import WAREHOUSE_DIR, load_sql


@nucleus.asset("silver.top_products", deps=["bronze.orders", "bronze.products"])
def silver_top_products():
    """Join bronze orders against bronze products and aggregate by SKU."""
    sql = load_sql("silver_top_products")
    return ctx.sql(sql, warehouse_dir=WAREHOUSE_DIR).collect()
