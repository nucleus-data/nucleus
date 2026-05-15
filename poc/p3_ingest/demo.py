"""PoC #3 — manual end-to-end demo.

Run after ``pip install -e .[dev]`` from the repo root::

    python poc/p3_ingest/demo.py

What it does:
    1. Creates a temp dir for the warehouse + a temp SQLite db.
    2. Builds an ``orders`` table with 5 rows of mixed-type data.
    3. Calls ``ingest_sqlite_to_iceberg`` to copy ``orders`` → ``raw.orders``.
    4. Reads back via ``catalog.load_table(...).scan().to_arrow()`` and prints.
    5. Asserts the row count round-trips (5).
    6. Returns 0 on success, 1 on failure.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from poc.p3_ingest.ingest import _open_catalog, ingest_sqlite_to_iceberg

_ROWS = [
    (1, 100, 19.99, "first"),
    (2, 100, 5.50, "second"),
    (3, 200, 42.00, None),
    (4, 300, 0.01, "fourth"),
    (5, 200, 1234.56, "fifth"),
]


def main() -> int:
    print("=" * 60)
    print("PoC #3 — SQLite → filesystem Iceberg ingest demo")
    print("=" * 60)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        sqlite_path = Path(tmp) / "source.db"
        warehouse = Path(tmp) / "warehouse"

        conn = sqlite3.connect(str(sqlite_path))
        try:
            conn.execute(
                "CREATE TABLE orders ("
                "  id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, note TEXT"
                ")"
            )
            conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", _ROWS)
            conn.commit()
        finally:
            conn.close()
        print(f"\nSeeded SQLite with {len(_ROWS)} orders at {sqlite_path}")

        written = ingest_sqlite_to_iceberg(
            sqlite_path,
            "orders",
            warehouse_dir=warehouse,
            dest_namespace="raw",
            dest_table="orders",
        )
        print(f"Ingest wrote {written} rows to raw.orders.")

        table = _open_catalog(warehouse).load_table(("raw", "orders"))
        arrow_table = table.scan().to_arrow()

        print("\nRead-back from Iceberg:")
        print("-" * 60)
        for row in arrow_table.to_pylist():
            print(row)
        print("-" * 60)

        if arrow_table.num_rows != len(_ROWS) or written != len(_ROWS):
            print(
                f"\nFAIL: expected {len(_ROWS)} rows; wrote {written}, read {arrow_table.num_rows}."
            )
            return 1
        print(f"\n[OK] Round-trip clean ({len(_ROWS)} rows in, {arrow_table.num_rows} rows out).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
