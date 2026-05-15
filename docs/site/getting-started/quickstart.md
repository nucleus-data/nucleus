---
title: Quickstart — 30 minutes to your first BI-ready Iceberg table
description: The full beachhead path from git clone to a queryable Iceberg asset.
---

# Quickstart

**Audience:** A 5-engineer startup team, ~100GB–5TB greenfield data, MacBooks or Linux.
**Goal:** First BI-ready Iceberg table from a clean machine in under 30 minutes.
**Prereqs:** [Installation](installation.md) complete; Docker Desktop running.

!!! tip "Existing quickstart"
    A shorter version lives at [`docs/onboarding/quickstart.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/onboarding/quickstart.md) in the repo. This page is the complete guided walkthrough.

---

## Step 1 — Clone and install (5 min)

```bash
git clone https://github.com/nucleus-data/nucleus.git
cd nucleus
python3.11 -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Verify:

```bash
nucleus version
```

You should see a table of version numbers. If `nucleus: command not found`, your venv is not activated.

---

## Step 2 — Scaffold a new project (2 min)

```bash
nucleus init beachhead-demo
cd beachhead-demo
```

`nucleus init` creates:

```
beachhead-demo/
├── nucleus_project.yaml     # Project config
├── assets/
│   └── example.py           # Starter @nucleus.asset
├── checks/
│   └── __init__.py
├── data/
│   └── .gitkeep
├── .gitignore
└── README.md
```

The starter asset (`assets/example.py`) produces a small greeting table — enough to prove the whole pipeline end-to-end before you wire real data.

---

## Step 3 — Boot the local stack (2 min)

```bash
nucleus up
```

Expected output:

```
✓ Object store ready (SeaweedFS on :9000)
✓ Catalog ready (filesystem, 0 tables)
✓ Definitions loaded (1 asset)
Nucleus up in 6.1s.
```

`nucleus up` starts:

- **SeaweedFS** (S3-compatible object store) via docker-compose
- **Filesystem Iceberg catalog** via `pyiceberg.SqlCatalog`
- **Dagster Definitions** in-process (hidden behind `ctx`)

!!! note "Boot time target"
    Per [architecture v4.1 §16.1](../philosophy/five-pillars.md), cold boot must be &lt;10s. If it takes longer, check Docker Desktop is running and port 9000 is free.

---

## Step 4 — Materialize the starter asset (1 min)

```bash
nucleus run example.greeting
```

Expected:

```
┌─────────────────┬────────┬──────────┬──────┐
│ asset           │ status │ duration │ rows │
├─────────────────┼────────┼──────────┼──────┤
│ example.greeting│ ✓ done │    0.8s  │    3 │
└─────────────────┴────────┴──────────┴──────┘
1 asset materialized. Iceberg snapshot committed.
```

Your first Iceberg snapshot is written. It lives under `data/warehouse/`.

---

## Step 5 — Query the result (1 min)

```bash
nucleus query "SELECT * FROM {{ ref('example.greeting') }} LIMIT 5"
```

Expected:

```
┌──────────┬───────────────────────────────┐
│ name     │ value                         │
├──────────┼───────────────────────────────┤
│ hello    │ world                         │
│ nucleus  │ ship data products from a...  │
│ iceberg  │ your data travels with you    │
└──────────┴───────────────────────────────┘
```

The `{{ ref('example.greeting') }}` Jinja syntax resolves the asset key to its underlying Iceberg table path — exactly like `ref()` in dbt.

---

## Step 6 — Ingest real data (10 min)

### Option A: SQLite (no external service needed)

```bash
# Use the seed script from the examples
python examples/01-ecommerce-elt/scripts/seed_stripe_sqlite.py
nucleus ingest sqlite:///./data/stripe.db --table charges --as raw.charges
```

### Option B: Postgres

```bash
nucleus ingest postgres://user:password@localhost:5432/mydb \
  --table public.orders \
  --as raw.orders \
  --mode overwrite
```

### Option C: CSV file

```bash
nucleus ingest ./data/orders.csv --as raw.orders --mode append
```

After ingest, query the new asset:

```bash
nucleus query "SELECT count(*) AS n FROM {{ ref('raw.orders') }}"
```

---

## Step 7 — Write your first transform (5 min)

Open `assets/` and create `assets/daily_revenue.py`:

```python
import nucleus
import polars as pl


@nucleus.asset(
    table="analytics.daily_revenue",
    schedule="@daily",
    deps=["raw.orders"],
    description="Daily revenue aggregated from raw orders",
)
def daily_revenue(ctx) -> pl.DataFrame:
    orders = ctx.read("raw.orders")
    return (
        orders
        .filter(pl.col("status") == "completed")
        .group_by("order_date")
        .agg(pl.col("amount").sum().alias("revenue"))
        .sort("order_date", descending=True)
    )
```

Run it:

```bash
nucleus run analytics.daily_revenue
nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }} LIMIT 10"
```

---

## Step 8 — Shut down (1 min)

```bash
nucleus down
```

Your Iceberg data is preserved in `data/warehouse/`. Pass `--volumes` only if you want to wipe everything.

---

## What just happened

In under 30 minutes you:

1. Booted a complete local data stack (object store + Iceberg catalog + orchestration engine)
2. Ingested raw data from an external source
3. Transformed it into an analytics-ready Iceberg table with a declared schedule
4. Queried the result via DuckDB

Every Iceberg table is already readable by Databricks, Snowflake, or any Iceberg REST catalog — no migration needed when you grow.

---

## Next steps

- [Your First Asset](your-first-asset.md) — deeper dive into asset authoring
- [Write SQL Transformations](../guides/write-sql-transformations.md) — `@nucleus.sql_asset` + Jinja
- [Schedule an Asset](../guides/schedule-asset.md) — `schedule=` parameter + `nucleus schedule`
- [`examples/01-ecommerce-elt/`](https://github.com/nucleus-data/nucleus/tree/main/examples/01-ecommerce-elt) — a real multi-layer ELT project to adapt
