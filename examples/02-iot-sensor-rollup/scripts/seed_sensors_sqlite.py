"""Populate ``data/sensors.db`` with synthetic high-frequency readings.

Run from the example root:
  python scripts/seed_sensors_sqlite.py

Docs: https://docs.python.org/3/library/sqlite3.html
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "sensors.db"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    rows: list[tuple[str, str, float, str]] = []
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS readings (
                device_id TEXT NOT NULL,
                event_ts TEXT NOT NULL,
                metric_value REAL NOT NULL,
                obs_date TEXT NOT NULL
            )
            """
        )
        base_days = [
            "2026-05-12",
            "2026-05-13",
            "2026-05-14",
        ]
        for day in base_days:
            for hour in range(0, 18, 6):
                rows.append(
                    (
                        "dev_alpha",
                        f"{day}T{hour:02d}:15:00",
                        20.0 + hour * 0.1,
                        day,
                    )
                )
                rows.append(
                    (
                        "dev_beta",
                        f"{day}T{hour:02d}:20:00",
                        55.5 - hour * 0.05,
                        day,
                    ),
                )
        conn.executemany(
            """
            INSERT INTO readings (device_id, event_ts, metric_value, obs_date)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Wrote {DB_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
