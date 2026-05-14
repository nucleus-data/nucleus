"""Silver layer: daily rollups partitioned by calendar day (logical key in data)."""

from __future__ import annotations

from pathlib import Path

import nucleus
import nucleus.ctx as ctx

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")


@nucleus.asset("silver.daily_sensor_metrics", deps=["bronze.sensor_readings"])
def silver_daily_sensor_metrics():
    """Sum readings per device per ``obs_date`` (YYYY-MM-DD partition column)."""
    sql = """
    SELECT
        obs_date AS day,
        device_id,
        sum(metric_value) AS daily_total,
        count(*) AS reading_count
    FROM {{ ref('bronze.sensor_readings') }}
    GROUP BY obs_date, device_id
    ORDER BY day, device_id
    """
    return ctx.sql(sql, warehouse_dir=WAREHOUSE).collect()
