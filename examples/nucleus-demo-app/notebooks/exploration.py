"""Ad-hoc exploration of the demo warehouse.

Reads the two gold assets via ``ctx.read`` and prints a one-page summary
to stdout. Runnable today as a plain Python script; the same file is
intended to drop into a Marimo notebook (v0.3+) without modification.

Usage::

    python notebooks/exploration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl  # noqa: E402

import nucleus.ctx as ctx  # noqa: E402

WAREHOUSE = str(PROJECT_ROOT / "data" / "warehouse")


def main() -> None:
    print("=== Gold asset: gold.revenue_dashboard ===")
    revenue = ctx.read("gold.revenue_dashboard", warehouse_dir=WAREHOUSE).collect()
    print(revenue.head(5))
    print(f"... ({revenue.height:,} rows total)\n")

    print("=== Gold asset: gold.customer_segments ===")
    segments = ctx.read("gold.customer_segments", warehouse_dir=WAREHOUSE).collect()
    summary = (
        segments.group_by("segment")
        .agg(
            pl.col("customer_count").sum().alias("customers"),
            pl.col("segment_revenue_usd").sum().alias("total_revenue_usd"),
        )
        .sort("total_revenue_usd", descending=True)
    )
    print(summary)


if __name__ == "__main__":
    main()
