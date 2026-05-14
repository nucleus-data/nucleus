"""Gold layer: cross-day aggregates for dashboards."""

from __future__ import annotations

from pathlib import Path

import nucleus
import nucleus.ctx as ctx

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")


@nucleus.asset("gold.weekly_metrics", deps=["silver.daily_sensor_metrics"])
def gold_weekly_metrics():
    """Roll silver daily totals into a compact aggregate per device (demo window = all loaded days)."""
    sql = """
    SELECT
        device_id,
        cast(sum(daily_total) AS double) AS weekly_energy,
        cast(sum(reading_count) AS bigint) AS weekly_reading_count
    FROM {{ ref('silver.daily_sensor_metrics') }}
    GROUP BY device_id
    ORDER BY device_id
    """
    return ctx.sql(sql, warehouse_dir=WAREHOUSE).collect()
