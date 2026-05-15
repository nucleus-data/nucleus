"""Uniqueness check on ``bronze.customers.customer_id``.

A duplicate customer_id in the bronze snapshot would silently fan out
joins downstream and double-count revenue. Fires as the default
``severity="error"`` so a failure rejects the materialization.
"""

from __future__ import annotations

import polars as pl

import nucleus
import nucleus.ctx as ctx
from nucleus import CheckResult

from assets._common import WAREHOUSE_DIR


@nucleus.check("bronze.customers")
def customer_id_unique():
    """``bronze.customers.customer_id`` must have no duplicates."""
    df = ctx.read("bronze.customers", warehouse_dir=WAREHOUSE_DIR).collect()
    total = df.height
    distinct = df.select(pl.col("customer_id").n_unique()).item()
    duplicates = total - distinct
    return CheckResult(
        passed=duplicates == 0,
        metric=float(duplicates),
        message=(
            f"{duplicates} duplicate customer_id row(s) found "
            f"(total={total}, distinct={distinct})."
        ),
    )
