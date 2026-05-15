"""Generate deterministic seed CSVs for the Nucleus e-commerce demo.

Run from the project root::

    python scripts/generate_seed.py

Produces three files under ``data/seed/``:

* ``customers.csv``  ~1,000 rows — one row per customer
* ``products.csv``   ~  500 rows — one row per SKU
* ``orders.csv``     ~10,000 rows — one row per order line

Distributions are realistic (signup over the last 18 months, prices log-normal,
order dates concentrated in the last 90 days, status mostly ``completed``) but
fully deterministic via a fixed RNG seed so every clone of the repo produces
byte-identical CSVs. No external packages — stdlib only.

Docs: https://docs.python.org/3/library/random.html
Docs: https://docs.python.org/3/library/csv.html
"""

from __future__ import annotations

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seed"

N_CUSTOMERS = 1_000
N_PRODUCTS = 500
N_ORDERS = 10_000

RNG = random.Random(20260515)

FIRST_NAMES = [
    "Alex", "Bao", "Chen", "Dana", "Elena", "Farah", "Gus", "Huy", "Indira",
    "Jakub", "Kai", "Lina", "Marcos", "Nia", "Oluwa", "Priya", "Qing", "Rosa",
    "Sven", "Tara", "Uma", "Vlad", "Wen", "Ximena", "Yara", "Zane",
]
LAST_NAMES = [
    "Adler", "Bishop", "Cole", "Doan", "Esposito", "Faroukh", "Gomez", "Hsu",
    "Ito", "Jackson", "Kapoor", "Liu", "Marchetti", "Nguyen", "Ortiz", "Park",
    "Quinn", "Reyes", "Saito", "Tran", "Ueda", "Vargas", "Wang", "Xu", "Yamada",
    "Zhao",
]
COUNTRIES = ["US", "CA", "GB", "DE", "FR", "ES", "VN", "JP", "BR", "AU"]
COUNTRY_WEIGHTS = [40, 8, 12, 8, 6, 4, 6, 5, 6, 5]

CHANNELS = ["web", "mobile", "marketplace", "api"]
CHANNEL_WEIGHTS = [60, 30, 7, 3]

ORDER_STATUSES = ["completed", "completed", "completed", "completed", "shipped", "refunded", "cancelled"]

PRODUCT_CATEGORIES = [
    "Apparel", "Books", "Electronics", "Home", "Outdoors", "Beauty", "Toys", "Grocery",
]
PRODUCT_ADJECTIVES = [
    "Classic", "Pro", "Mini", "Eco", "Premium", "Lite", "Smart", "Vintage", "Travel", "Studio",
]
PRODUCT_NOUNS = [
    "Bottle", "Mug", "Backpack", "Lamp", "Notebook", "Speaker", "Sneaker", "Mat",
    "Brush", "Camera", "Knife", "Glove", "Tripod", "Pillow", "Shirt", "Hat",
    "Wallet", "Charger", "Headset", "Vase",
]


def _email(first: str, last: str, idx: int) -> str:
    base = f"{first.lower()}.{last.lower()}{idx:04d}"
    return f"{base}@example.com"


def write_customers() -> list[str]:
    """Write customers.csv; return list of customer_ids in stable order."""
    today = date(2026, 5, 15)
    customer_ids: list[str] = []
    rows: list[dict[str, str]] = []
    for i in range(1, N_CUSTOMERS + 1):
        first = RNG.choice(FIRST_NAMES)
        last = RNG.choice(LAST_NAMES)
        country = RNG.choices(COUNTRIES, weights=COUNTRY_WEIGHTS, k=1)[0]
        days_ago = int(RNG.triangular(0, 540, 180))
        signup = today - timedelta(days=days_ago)
        signup_ts = datetime.combine(signup, datetime.min.time()) + timedelta(
            seconds=RNG.randint(0, 86_399)
        )
        cid = f"c{i:05d}"
        customer_ids.append(cid)
        rows.append(
            {
                "customer_id": cid,
                "email": _email(first, last, i),
                "first_name": first,
                "last_name": last,
                "country": country,
                "signup_ts": signup_ts.isoformat(timespec="seconds"),
                "is_active": "true" if RNG.random() < 0.92 else "false",
            }
        )
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    out = SEED_DIR / "customers.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return customer_ids


def write_products() -> list[tuple[str, int]]:
    """Write products.csv; return list of (product_id, price_cents)."""
    products: list[tuple[str, int]] = []
    rows: list[dict[str, str]] = []
    for i in range(1, N_PRODUCTS + 1):
        category = RNG.choice(PRODUCT_CATEGORIES)
        adjective = RNG.choice(PRODUCT_ADJECTIVES)
        noun = RNG.choice(PRODUCT_NOUNS)
        name = f"{adjective} {noun}"
        price_dollars = max(2.0, RNG.lognormvariate(2.8, 0.65))
        price_cents = int(round(price_dollars * 100))
        sku = f"SKU{i:04d}"
        products.append((sku, price_cents))
        rows.append(
            {
                "product_id": sku,
                "name": name,
                "category": category,
                "price_cents": str(price_cents),
                "in_stock": "true" if RNG.random() < 0.85 else "false",
                "supplier_country": RNG.choices(COUNTRIES, weights=COUNTRY_WEIGHTS, k=1)[0],
            }
        )
    out = SEED_DIR / "products.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return products


def write_orders(customer_ids: list[str], products: list[tuple[str, int]]) -> None:
    """Write orders.csv (~N_ORDERS lines, one product line per order_id)."""
    today = date(2026, 5, 15)
    rows: list[dict[str, str]] = []
    for i in range(1, N_ORDERS + 1):
        cid = RNG.choices(
            customer_ids,
            weights=[max(1, int(40 - abs(idx % 100 - 50))) for idx, _ in enumerate(customer_ids)],
            k=1,
        )[0]
        sku, unit_cents = RNG.choice(products)
        qty = RNG.choices([1, 2, 3, 4, 5], weights=[55, 25, 10, 6, 4], k=1)[0]
        amount_cents = unit_cents * qty
        days_ago = int(RNG.triangular(0, 180, 30))
        order_dt = today - timedelta(days=days_ago)
        order_ts = datetime.combine(order_dt, datetime.min.time()) + timedelta(
            seconds=RNG.randint(0, 86_399)
        )
        status = RNG.choice(ORDER_STATUSES)
        channel = RNG.choices(CHANNELS, weights=CHANNEL_WEIGHTS, k=1)[0]
        rows.append(
            {
                "order_id": f"o{i:06d}",
                "customer_id": cid,
                "product_id": sku,
                "quantity": str(qty),
                "amount_cents": str(amount_cents),
                "currency": "USD",
                "order_ts": order_ts.isoformat(timespec="seconds"),
                "status": status,
                "channel": channel,
            }
        )
    out = SEED_DIR / "orders.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    customer_ids = write_customers()
    products = write_products()
    write_orders(customer_ids, products)
    sizes = {p.name: p.stat().st_size for p in sorted(SEED_DIR.glob("*.csv"))}
    for name, size in sizes.items():
        print(f"Wrote {name}: {size:,} bytes")


if __name__ == "__main__":
    main()
