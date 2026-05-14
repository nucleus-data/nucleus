# IoT sensor rollup (bronze / silver / gold)

Narrative: you attach thousands of cheap sensors at the edge. Raw readings land in a **SQLite** export (daily batch file from the field gateway). Inside Nucleus you shape **bronze → silver → gold** Iceberg assets:

- **Bronze** — append-friendly landing with little interpretation.
- **Silver** — daily aggregates per device (`obs_date` is the logical day key).
- **Gold** — compact weekly KPIs per device for dashboards.

The pattern mirrors how teams stage analytical maturity without reaching for a hosted warehouse on day one.

## What you need

- Python **3.11**
- Nucleus installed from the repo (`pip install -e ".[dev]"` at the repository root)
- **Docker** only if you want MinIO; the sample also works with the **filesystem warehouse** alone

## Quick run (SQLite only)

```bash
cd examples/02-iot-sensor-rollup
python scripts/seed_sensors_sqlite.py
nucleus up
nucleus run bronze.sensor_readings
nucleus run silver.daily_sensor_metrics
nucleus run gold.weekly_metrics
nucleus query "SELECT * FROM {{ ref('gold.weekly_metrics') }} LIMIT 20"
nucleus down
```

Expected highlights:

- `seed_sensors_sqlite.py` prints `Wrote .../data/sensors.db (18 rows)` (18 is the deterministic demo batch).
- `nucleus run` lines show per-asset success and row counts once Iceberg commits complete.
- `nucleus query` prints the `gold.weekly_metrics` projection (exact Rich table formatting depends on your terminal).

## Quality checks

`checks/__init__.py` registers:

- **Freshness** on `silver.daily_sensor_metrics` — asserts the latest `day` is within the last **90** days of “today” on your laptop (refresh demo data if you revisit this folder after a long pause).
- **Non-empty gold** — `gold.weekly_metrics` must return at least one device aggregate.

## Notes

- **`nucleus up` is optional** here — filesystem Iceberg + `nucleus run` work without MinIO. Skip `nucleus up` / `nucleus down` when Docker is unavailable.
- If you change SQL and Iceberg reports a **schema mismatch**, delete **`data/warehouse/`** and **`.nucleus/`** in this folder, then re-run bronze → silver → gold.

## Optional MinIO

`docker compose up -d` starts the bundled MinIO profile (same pattern as `nucleus init`). Iceberg metadata still uses the filesystem catalog from `nucleus_project.yaml`; object storage remains optional for this sample.

## Where this maps in the roadmap

For lifecycle milestones (Workbench, hosted catalogs, richer orchestration), follow release notes and the public roadmap in the repository.
