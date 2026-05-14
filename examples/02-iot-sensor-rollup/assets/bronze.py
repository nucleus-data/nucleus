"""Bronze layer: land raw readings in Iceberg from SQLite."""

from __future__ import annotations

from pathlib import Path

import nucleus
import nucleus.ctx as ctx

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")
SENSORS_SQLITE = f"sqlite:///{(ROOT / 'data' / 'sensors.db').resolve().as_posix()}"


@nucleus.asset("bronze.sensor_readings")
def bronze_sensor_readings():
    """Ingest SQLite ``readings`` — one row per device observation."""
    return ctx.copy_from(
        SENSORS_SQLITE,
        table="readings",
        target="bronze.sensor_readings",
        warehouse_dir=WAREHOUSE,
        write_disposition="replace",
    )
