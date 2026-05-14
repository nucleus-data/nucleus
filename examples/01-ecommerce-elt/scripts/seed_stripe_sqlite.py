"""Create a minimal SQLite file simulating Stripe webhook events (demo only).

Run from the example root:
  python scripts/seed_stripe_sqlite.py

Docs: https://docs.python.org/3/library/sqlite3.html
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "stripe_events.db"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stripe_events (
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                event_ts TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO stripe_events (event_id, order_id, amount_cents, event_ts)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("evt_1", "o100", 4999, "2026-05-01T10:00:00"),
                ("evt_2", "o102", 8900, "2026-05-02T14:20:00"),
                ("evt_3", "o103", 4500, "2026-05-04T09:15:00"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
