"""Generate deterministic e-commerce demo data for the Nucleus public demo.

Used at Docker image build time (``deploy/Dockerfile.demo``) to bake a fixed,
read-only e-commerce dataset into the image so visitors to
``demo.nucleus-data.dev`` always see the same numbers regardless of pod restart.

Why stdlib-only:
    Per ``deploy/Dockerfile.demo``, this script runs during the multi-stage
    build BEFORE Nucleus is installed.  Keeping it standard-library-only means
    the build step works on any Python 3.11+ base image without extra ``pip``
    rounds.  CSV is intentionally chosen over Parquet for the same reason —
    the image's ``RUN nucleus ingest`` step converts CSV → Iceberg later.

Determinism:
    ``random.seed(42)`` + ``datetime`` arithmetic from a fixed anchor means
    two builds produce byte-identical CSVs.  This lets us cache the image
    layer for ``COPY data/raw/`` if upstream Nucleus does not change.

No-PII guarantee:
    Every name, email, and address is generated from a hard-coded synthetic
    pool below.  No external dataset is read.  No real user data is ever
    embedded.  See ``deploy/RESET_POLICY.md`` for the user-facing policy.

Usage:
    python deploy/seed_demo_data.py --output-dir ./demo-data/raw

    # Or with custom row counts (defaults: 500 products, 1000 customers,
    # 10000 orders):
    python deploy/seed_demo_data.py \\
        --output-dir ./demo-data/raw \\
        --products 500 --customers 1000 --orders 10000

Files written:
    ``products.csv``   — 500 rows, columns: product_id, name, category, price_usd
    ``customers.csv``  — 1000 rows, columns: customer_id, name, country, signup_date
    ``orders.csv``     — 10000 rows, columns: order_id, customer_id, product_id,
                         quantity, order_date, status

Asset keys produced by ``nucleus ingest`` (Docker build step):
    raw.products, raw.customers, raw.orders

Promoted from PoC #5 fixture generator (2026-05-14) to deploy/ on 2026-05-15
for the public demo bundle.
"""
# Docs: https://docs.python.org/3/library/csv.html
# Docs: https://docs.python.org/3/library/random.html
# Docs: https://docs.python.org/3/library/argparse.html
# Docs: https://docs.python.org/3/library/datetime.html

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

_SEED = 42

_PRODUCT_CATEGORIES = (
    "electronics",
    "books",
    "home",
    "outdoor",
    "toys",
    "kitchen",
    "garden",
    "office",
)

_PRODUCT_PREFIXES = (
    "Pro",
    "Eco",
    "Lite",
    "Classic",
    "Smart",
    "Mini",
    "Max",
    "Ultra",
    "Basic",
    "Premium",
)

_PRODUCT_NOUNS = (
    "Widget",
    "Gadget",
    "Tool",
    "Device",
    "Kit",
    "Bundle",
    "Pack",
    "Set",
    "Item",
    "Unit",
)

_COUNTRIES = (
    "US",
    "GB",
    "DE",
    "FR",
    "CA",
    "AU",
    "JP",
    "NL",
    "SE",
    "BR",
    "IN",
    "SG",
)

_GIVEN_NAMES = (
    "Avery",
    "Blake",
    "Casey",
    "Drew",
    "Emerson",
    "Finley",
    "Gray",
    "Hayden",
    "Indigo",
    "Jordan",
    "Kai",
    "Lane",
    "Morgan",
    "Noa",
    "Oakley",
    "Parker",
    "Quinn",
    "River",
    "Sage",
    "Taylor",
)

_FAMILY_NAMES = (
    "Anders",
    "Brooks",
    "Chen",
    "Dixon",
    "Ellis",
    "Forbes",
    "Greene",
    "Hayes",
    "Ito",
    "Jain",
    "Kovacs",
    "Lopez",
    "Murphy",
    "Novak",
    "Owens",
    "Park",
    "Quinn",
    "Reyes",
    "Singh",
    "Tanaka",
)

_ORDER_STATUSES = ("placed", "paid", "shipped", "delivered", "cancelled", "returned")
_ORDER_STATUS_WEIGHTS = (0.05, 0.10, 0.10, 0.65, 0.07, 0.03)


def _gen_products(n: int, rng: random.Random) -> list[dict[str, object]]:
    """Return n synthetic products with stable PKs and deterministic prices."""
    products: list[dict[str, object]] = []
    for i in range(1, n + 1):
        prefix = rng.choice(_PRODUCT_PREFIXES)
        noun = rng.choice(_PRODUCT_NOUNS)
        category = rng.choice(_PRODUCT_CATEGORIES)
        price = round(rng.uniform(4.99, 499.99), 2)
        products.append(
            {
                "product_id": i,
                "name": f"{prefix} {noun} {i:04d}",
                "category": category,
                "price_usd": price,
            }
        )
    return products


def _gen_customers(
    n: int, rng: random.Random, anchor: datetime
) -> list[dict[str, object]]:
    """Return n synthetic customers with signup dates within the last 2 years."""
    customers: list[dict[str, object]] = []
    for i in range(1, n + 1):
        given = rng.choice(_GIVEN_NAMES)
        family = rng.choice(_FAMILY_NAMES)
        country = rng.choice(_COUNTRIES)
        days_back = rng.randint(0, 730)
        signup = (anchor - timedelta(days=days_back)).date().isoformat()
        customers.append(
            {
                "customer_id": i,
                "name": f"{given} {family}",
                "country": country,
                "signup_date": signup,
            }
        )
    return customers


def _gen_orders(
    n: int,
    rng: random.Random,
    n_customers: int,
    n_products: int,
    anchor: datetime,
) -> list[dict[str, object]]:
    """Return n synthetic orders referencing valid customer + product FKs."""
    orders: list[dict[str, object]] = []
    for i in range(1, n + 1):
        customer_id = rng.randint(1, n_customers)
        product_id = rng.randint(1, n_products)
        quantity = rng.choices([1, 2, 3, 4, 5], weights=[60, 20, 10, 6, 4])[0]
        days_back = rng.randint(0, 365)
        order_dt = (anchor - timedelta(days=days_back)).date().isoformat()
        status = rng.choices(_ORDER_STATUSES, weights=_ORDER_STATUS_WEIGHTS)[0]
        orders.append(
            {
                "order_id": i,
                "customer_id": customer_id,
                "product_id": product_id,
                "quantity": quantity,
                "order_date": order_dt,
                "status": status,
            }
        )
    return orders


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write rows to a CSV file with stable column ordering."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    # Docs: https://docs.python.org/3/library/csv.html#csv.DictWriter
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """CLI entrypoint — parse args, generate, write three CSVs."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic e-commerce demo data (products, "
            "customers, orders) for the Nucleus public demo image."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./demo-data/raw"),
        help="Directory to write CSVs into (created if missing).",
    )
    parser.add_argument("--products", type=int, default=500)
    parser.add_argument("--customers", type=int, default=1000)
    parser.add_argument("--orders", type=int, default=10000)
    parser.add_argument(
        "--anchor",
        type=str,
        default="2026-05-15",
        help=(
            "ISO date anchor for synthetic timestamps; defaults to demo "
            "release date for reproducibility."
        ),
    )
    args = parser.parse_args()

    rng = random.Random(_SEED)
    anchor = datetime.fromisoformat(args.anchor)

    products = _gen_products(args.products, rng)
    customers = _gen_customers(args.customers, rng, anchor)
    orders = _gen_orders(args.orders, rng, args.customers, args.products, anchor)

    out_dir = args.output_dir
    _write_csv(out_dir / "products.csv", products)
    _write_csv(out_dir / "customers.csv", customers)
    _write_csv(out_dir / "orders.csv", orders)

    print(
        f"Wrote {len(products):,} products, {len(customers):,} customers, "
        f"{len(orders):,} orders to {out_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
