# Nucleus Demo — E-Commerce Pipeline

> A complete, runnable Nucleus project showcasing **bronze → silver → gold**
> Iceberg assets fed by a real Postgres source. ~10,000 orders, 1,000
> customers, 500 products. Everything you need to ship your first data
> product from a laptop in **under five minutes**.

---

## 30-second pitch

Nucleus turns this:

```python
@nucleus.asset("silver.daily_revenue", deps=["bronze.orders"])
def silver_daily_revenue():
    return ctx.sql(
        "SELECT day, sum(amount_usd) FROM {{ ref('bronze.orders') }} GROUP BY 1",
        warehouse_dir=WAREHOUSE_DIR,
    ).collect()
```

…into an **Iceberg-backed asset** with snapshot history, lineage, and
quality checks — running on your laptop, ready to graduate to any Iceberg
catalog (Polaris, Lakekeeper, Unity, R2, Databricks, Snowflake) when you
outgrow it.

This demo wires up a realistic e-commerce graph so you can see all of it
running end-to-end:

| Layer       | Assets | What lives here                                         |
| ----------- | ------ | ------------------------------------------------------- |
| **Bronze**  | 3      | Raw Postgres tables landed verbatim into Iceberg.       |
| **Silver**  | 3      | Cleaned, joined, business-ready aggregates (Jinja SQL). |
| **Gold**    | 2      | Denormalised views a BI tool charts directly.           |
| **Checks**  | 3      | Freshness, uniqueness, and business-rule guards.        |

Total: **~1,200 LOC** of Python + SQL + docs. Everything you need to
demo Nucleus to your team.

> _Screenshot placeholder: `nucleus run gold.revenue_dashboard` rendered output._
> _Screenshot placeholder: Workbench dashboard at `http://localhost:8765`._

---

## 5-minute walkthrough

You will need:

* **Python 3.11**
* **Docker Desktop** (or any compatible runtime that ships `docker compose`)
* **Nucleus** installed: `pip install -e ".[dev]"` from the repo root
  (until the PyPI release is live)

Then, from this directory:

```bash
# 1) Boot MinIO + Postgres and create the local Iceberg warehouse.
nucleus up

# 2) Hydrate Postgres with the seed data (1,000 customers / 500 products / 10,000 orders).
python scripts/seed_postgres.py

# 3) Materialize the bronze layer (ingest from Postgres → Iceberg).
nucleus run bronze.orders
nucleus run bronze.customers
nucleus run bronze.products

# 4) Materialize the silver layer (transformations on top of bronze).
nucleus run silver.daily_revenue
nucleus run silver.customer_ltv
nucleus run silver.top_products

# 5) Materialize the gold layer (BI-ready views).
nucleus run gold.revenue_dashboard
nucleus run gold.customer_segments

# 6) Spot-check a result.
nucleus query "SELECT * FROM {{ ref('gold.revenue_dashboard') }} LIMIT 10"

# 7) Optional: open the Workbench browser UI.
nucleus workbench up                # listens on http://localhost:8765
```

When you are done:

```bash
nucleus down                        # stop the compose stack
bash scripts/reset_demo.sh          # full wipe (warehouse, MinIO, Postgres)
```

> **About `nucleus run`** — v0.1 materializes a single asset per
> invocation. The list above is the canonical dependency order. Multi-asset
> `nucleus run` and `nucleus run --all` ship in v0.2; until then a small
> shell loop (or `Makefile`) is the idiomatic way to chain the eight
> assets above.

---

## What the graph looks like

```
Postgres (public.orders)        Postgres (public.customers)        Postgres (public.products)
        │                                │                                  │
        ▼                                ▼                                  ▼
  bronze.orders ─────┐             bronze.customers                  bronze.products
                     │                   │                                  │
                     ├──────┐            │                                  │
                     │      │            │                                  │
                     ▼      ▼            ▼                                  ▼
       silver.daily_revenue   silver.customer_ltv            silver.top_products
                     │                   │                                  │
                     │                   │                                  │
                     ▼                   ▼                                  │
            gold.revenue_dashboard      gold.customer_segments              │
                     ▲                                                      │
                     └──────────────────────────────────────────────────────┘
```

Full architectural notes live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Layout

```
nucleus-demo-app/
├── nucleus_project.yaml           # project config (catalog, warehouse, lineage)
├── docker-compose.yaml            # MinIO + Postgres for local dev
├── assets/                        # @nucleus.asset definitions (bronze / silver / gold)
├── sql/                           # Jinja SQL transforms used by silver + gold assets
├── checks/                        # @nucleus.check quality guards
├── data/seed/                     # 1k customers, 500 products, 10k orders (CSV)
├── notebooks/exploration.py       # ad-hoc analysis (Marimo-ready in v0.3+)
├── scripts/
│   ├── generate_seed.py           # regenerate the seed CSVs
│   ├── seed_postgres.py           # COPY seed CSVs into the Postgres container
│   └── reset_demo.sh              # wipe local state and start over
└── docs/
    ├── ARCHITECTURE.md            # asset graph + decisions
    ├── WALKTHROUGH.md             # 10-minute guided tour
    └── TROUBLESHOOTING.md         # common errors and fixes
```

---

## Where this fits

This project follows the layout described in
[`docs/specs/nucleus_project_anatomy.md`](../specs/nucleus_project_anatomy.md) and the
v0.1 CLI surface defined in
[`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md). The asset model is
locked in [`docs/specs/nucleus_asset_model_spec.md`](../specs/nucleus_asset_model_spec.md).
None of the bronze / silver / gold patterns are Nucleus-specific — they
follow the same medallion convention used by Databricks, dbt, and most
modern lakehouse pipelines, so a graduating team can lift this graph
into a managed catalog without rewriting it.

For deeper end-to-end runbooks see:

* [`docs/cookbook/production-deployment.md`](../../docs/cookbook/production-deployment.md) — single-node prod
* [`docs/cookbook/aws-deployment.md`](../../docs/cookbook/aws-deployment.md) — graduating to S3 + Glue / Polaris

---

## License

Apache 2.0 (same as the parent repository).
