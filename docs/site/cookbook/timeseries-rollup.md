---
title: Timeseries Rollup
description: Aggregate high-frequency events into hourly, daily, and weekly buckets.
---

# Timeseries Rollup

The IoT sensor rollup pattern — aggregate high-frequency events into summary buckets.

## Example: sensor readings → hourly averages

See also: [`examples/02-iot-sensor-rollup/`](https://github.com/nucleus-data/nucleus/tree/main/examples/02-iot-sensor-rollup)

```python
import nucleus
import polars as pl


@nucleus.asset(
    table="bronze.sensor_readings",
    schedule="@hourly",
)
def sensor_readings(ctx) -> pl.DataFrame:
    """Ingest raw sensor readings."""
    return ctx.copy_from(
        "sqlite:///./data/sensors.db",
        table="readings",
        target="bronze.sensor_readings",
        mode="append",
    )


@nucleus.sql_asset(
    table="silver.sensor_hourly",
    schedule="@hourly",
    deps=["bronze.sensor_readings"],
)
def sensor_hourly(ctx) -> str:
    return """
        SELECT
            sensor_id,
            DATE_TRUNC('hour', recorded_at) AS hour_bucket,
            AVG(temperature)    AS avg_temp,
            MIN(temperature)    AS min_temp,
            MAX(temperature)    AS max_temp,
            COUNT(*)            AS reading_count
        FROM {{ ref('bronze.sensor_readings') }}
        GROUP BY 1, 2
    """


@nucleus.sql_asset(
    table="gold.sensor_daily",
    schedule="@daily",
    deps=["silver.sensor_hourly"],
)
def sensor_daily(ctx) -> str:
    return """
        SELECT
            sensor_id,
            DATE_TRUNC('day', hour_bucket) AS day_bucket,
            AVG(avg_temp)           AS daily_avg_temp,
            MIN(min_temp)           AS daily_min_temp,
            MAX(max_temp)           AS daily_max_temp,
            SUM(reading_count)      AS total_readings
        FROM {{ ref('silver.sensor_hourly') }}
        GROUP BY 1, 2
        ORDER BY 1, 2 DESC
    """
```

## Run the pipeline

```bash
nucleus run bronze.sensor_readings silver.sensor_hourly gold.sensor_daily
```

## Handling time zones

```sql
-- Convert UTC timestamps to local time before bucketing
SELECT
    sensor_id,
    DATE_TRUNC('hour',
        timezone('America/New_York', recorded_at AT TIME ZONE 'UTC')
    ) AS hour_bucket_eastern,
    AVG(temperature) AS avg_temp
FROM {{ ref('bronze.sensor_readings') }}
GROUP BY 1, 2
```

## Reprocessing historical data

If you need to reprocess a time range (e.g., after a source fix):

```bash
# Overwrite the affected snapshot
nucleus run silver.sensor_hourly --param reprocess_date=2026-05-01
```

Use `ctx.param("reprocess_date")` in your asset to filter the input.
