"""Gold layer asset — customer cohort segments by signup quarter and LTV.

Buckets every customer into one of five segments — ``whale``, ``core``,
``casual``, ``trial``, ``never_purchased`` — and rolls up by country and
signup quarter so a dashboard can answer "where are our high-LTV
customers concentrated?".
"""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import WAREHOUSE_DIR, load_sql


@nucleus.asset(
    "gold.customer_segments",
    deps=["silver.customer_ltv"],
)
def gold_customer_segments():
    """Materialize the customer-segment cohort view."""
    sql = load_sql("gold_customer_segments")
    return ctx.sql(sql, warehouse_dir=WAREHOUSE_DIR).collect()
