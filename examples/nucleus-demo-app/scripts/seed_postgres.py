"""Load the demo CSVs into the local Postgres container.

The compose file mounts the CSVs into Postgres but does NOT auto-import
them — that would tie the schema to ``COPY`` semantics inside an init
script. Running this helper after ``nucleus up`` (or ``docker compose
up -d postgres``) gives a deterministic, idempotent load you can re-run
whenever you regenerate the seed CSVs.

Usage::

    cd examples/nucleus-demo-app
    python scripts/seed_postgres.py
    # ... seeds 1,000 customers / 500 products / 10,000 orders ...

Docs:
    https://www.psycopg.org/psycopg3/docs/basic/copy.html
    https://www.postgresql.org/docs/current/sql-createtable.html

This script uses ``psycopg`` (psycopg 3) which is already a Nucleus
runtime dependency, so no extra ``pip install`` is required.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seed"

DSN = os.environ.get(
    "NUCLEUS_DEMO_POSTGRES_URL",
    "postgresql://nucleus:nucleus@127.0.0.1:5433/nucleus_demo",
)

DDL = """
CREATE TABLE IF NOT EXISTS public.customers (
    customer_id  TEXT PRIMARY KEY,
    email        TEXT NOT NULL,
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    country      TEXT NOT NULL,
    signup_ts    TIMESTAMP NOT NULL,
    is_active    BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS public.products (
    product_id        TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL,
    price_cents       INTEGER NOT NULL,
    in_stock          BOOLEAN NOT NULL,
    supplier_country  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.orders (
    order_id      TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES public.customers(customer_id),
    product_id    TEXT NOT NULL REFERENCES public.products(product_id),
    quantity      INTEGER NOT NULL,
    amount_cents  INTEGER NOT NULL,
    currency      TEXT NOT NULL,
    order_ts      TIMESTAMP NOT NULL,
    status        TEXT NOT NULL,
    channel       TEXT NOT NULL
);
"""

LOAD_ORDER: list[tuple[str, str, list[str]]] = [
    (
        "customers",
        "customers.csv",
        ["customer_id", "email", "first_name", "last_name", "country", "signup_ts", "is_active"],
    ),
    (
        "products",
        "products.csv",
        ["product_id", "name", "category", "price_cents", "in_stock", "supplier_country"],
    ),
    (
        "orders",
        "orders.csv",
        [
            "order_id",
            "customer_id",
            "product_id",
            "quantity",
            "amount_cents",
            "currency",
            "order_ts",
            "status",
            "channel",
        ],
    ),
]


def _check_seeds_present() -> None:
    missing = [name for _, name, _ in LOAD_ORDER if not (SEED_DIR / name).is_file()]
    if missing:
        sys.stderr.write(
            "Missing seed CSV(s): "
            + ", ".join(missing)
            + "\nRun `python scripts/generate_seed.py` first.\n"
        )
        sys.exit(2)


def main() -> None:
    _check_seeds_present()

    try:
        import psycopg
    except ImportError:
        sys.stderr.write(
            "psycopg is not installed. Run `pip install psycopg[binary]` "
            "(it is also a Nucleus runtime dependency).\n"
        )
        sys.exit(2)

    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)

        for table, filename, columns in LOAD_ORDER:
            csv_path = SEED_DIR / filename
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE public.{table} CASCADE")
                col_list = ", ".join(columns)
                copy_sql = f"COPY public.{table} ({col_list}) FROM STDIN WITH CSV HEADER"
                with (
                    csv_path.open("r", encoding="utf-8", newline="") as fh,
                    cur.copy(copy_sql) as copy,
                ):
                    reader = csv.reader(fh)
                    next(reader, None)
                    for row in reader:
                        copy.write_row(row)
                cur.execute(f"SELECT count(*) FROM public.{table}")
                row = cur.fetchone()
                count = row[0] if row else 0
            print(f"Loaded {count:>6} rows into public.{table} from {filename}")


if __name__ == "__main__":
    main()
