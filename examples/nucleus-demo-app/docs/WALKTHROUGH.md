# Walkthrough — Nucleus demo app, end to end (~10 minutes)

A guided tour through the eight-asset e-commerce pipeline. Reads bottom to top: the
fastest path is in `README.md`; this doc explains _why_ each step exists.

---

## 0. Prerequisites

* Python **3.11**
* Docker (or Podman) with `docker compose`
* Nucleus installed editable from the repository root:
  ```bash
  cd ../..
  pip install -e ".[dev]"
  cd examples/nucleus-demo-app
  ```

Verify: `nucleus version` should print the package versions in a small
table. If it errors, your installation needs `pip install -e ".[dev]"`
from the repo root first.

---

## 1. Boot the local stack

```bash
nucleus up
```

What happens:

1. The CLI walks up to find `nucleus_project.yaml`.
2. It creates `data/warehouse/` and an empty SQLite catalog at
   `data/warehouse/catalog.db`.
3. It runs `docker compose up -d` against the bundled
   `docker-compose.yaml`, starting MinIO and Postgres in the background.
4. It polls MinIO's `/minio/health/ready` endpoint until the storage is
   ready (≤ 30 s budget).
5. It writes a `nucleus.db` BI handshake file (DuckDB-compatible) so a
   human can immediately point a notebook or BI tool at the catalog.

Expected output (terminal trim):

```
Warehouse: /…/data/warehouse
Catalog:   filesystem (SQLite at /…/data/warehouse/catalog.db)
BI file:   /…/nucleus.db (connect with DuckDB: open('/…/nucleus.db'))

  service          endpoint
  ─────────────────────────────────────────────
  minio (S3 API)   http://127.0.0.1:9100
  minio (console)  http://127.0.0.1:9101
  postgres         (see docker-compose.yaml)

Nucleus up.
```

If MinIO never reports ready, see `TROUBLESHOOTING.md` → "compose stack
fails to boot".

---

## 2. Hydrate Postgres

```bash
python scripts/seed_postgres.py
```

What happens:

1. `psycopg` connects to `postgresql://nucleus:nucleus@127.0.0.1:5433/nucleus_demo`.
2. It creates `public.customers / products / orders` (idempotent).
3. It `TRUNCATE … CASCADE`s each table and `COPY`s the matching CSV
   from `data/seed/`.

Expected output:

```
Loaded  1,000 rows into public.customers from customers.csv
Loaded    500 rows into public.products from products.csv
Loaded 10,000 rows into public.orders from orders.csv
```

You can re-run this script any time — it always wipes-and-reloads.

---

## 3. Materialize the bronze layer

Each bronze asset wraps one `ctx.copy_from(...)` call:

```bash
nucleus run bronze.orders
nucleus run bronze.customers
nucleus run bronze.products
```

Each call:

* Reads the source via `dlt.sources.sql_database` under the hood
  (the dlt-Postgres branch promoted in PoC #3).
* Auto-infers the Iceberg schema from the Postgres column metadata.
* Writes a fresh Iceberg snapshot via `pyiceberg.SqlCatalog`.
* Translates any external library failure to a `NucleusError`
  subclass — never see "psycopg.OperationalError" in a user message.

Expected per-call output (one block):

```
Materialized bronze.orders
  rows:        10,000
  snapshot:    8211735…
  duration:    3.4 s
  checks:      orders_freshness (warn) → newest order is 0 day(s) old (window = 30d)
```

---

## 4. Materialize the silver layer

Each silver asset reads its SQL template from `sql/<asset>.sql` and runs
it via `ctx.sql(...)` against the bronze Iceberg snapshots:

```bash
nucleus run silver.daily_revenue
nucleus run silver.customer_ltv
nucleus run silver.top_products
```

Notes:

* Dependency order matters in v0.1 — Nucleus does not yet auto-run
  upstream assets. If you skip a bronze asset, the silver materialization
  raises `NucleusAssetNotMaterialized (NE3003)` with the exact missing
  key in the message.
* Open any `.sql` file under `sql/` and edit it; the next
  `nucleus run silver.<name>` picks up your changes immediately.

---

## 5. Materialize the gold layer

```bash
nucleus run gold.revenue_dashboard
nucleus run gold.customer_segments
```

`gold.revenue_dashboard` is the headline mart — weekly revenue +
top-20 SKUs in one denormalised view. `gold.customer_segments` buckets
customers into `whale / core / casual / trial / never_purchased` cohorts
by signup quarter and country.

---

## 6. Query the warehouse

```bash
nucleus query "SELECT * FROM {{ ref('gold.revenue_dashboard') }} LIMIT 10"
```

What happens:

1. The CLI opens DuckDB in-process.
2. It registers every Iceberg table in the catalog as a DuckDB view.
3. It rewrites `{{ ref('gold.revenue_dashboard') }}` to the quoted view
   name `"gold"."revenue_dashboard"` (the same Jinja resolver that
   powers `ctx.sql` inside asset bodies).
4. It executes the SQL and prints a Rich table.

Other queries to try:

```bash
nucleus query "SELECT segment, sum(customer_count) AS customers, sum(segment_revenue_usd) AS revenue FROM {{ ref('gold.customer_segments') }} GROUP BY 1 ORDER BY revenue DESC"

nucleus query "SELECT product_name, revenue_usd FROM {{ ref('silver.top_products') }} LIMIT 20"
```

---

## 7. Browse in the Workbench

```bash
nucleus workbench up
```

The Workbench launches FastAPI + a React SPA at `http://localhost:8765`
(per ADR-016). It shows:

* The asset graph (DAG view).
* Every materialization with its row count, snapshot id, and check
  outcomes.
* An ad-hoc SQL query panel that talks to the same DuckDB engine the
  CLI uses.

Press `Ctrl+C` to stop it.

---

## 8. Tear down

```bash
nucleus down                       # stop docker compose
bash scripts/reset_demo.sh         # nuke the warehouse + Postgres + MinIO data
```

`nucleus down` keeps your warehouse and the seed Postgres data — handy
when you just want to free RAM. `reset_demo.sh` is the full wipe; run it
when you change `assets/` schemas in a backwards-incompatible way and
want a clean Iceberg metadata tree.

---

## 9. What you just shipped

* **8 Iceberg assets** with snapshot history, lineage, and checks.
* **Zero non-OSS dependencies.** Everything runs on Apache OSS — DuckDB,
  Polars, Iceberg, dlt, Dagster (hidden), MinIO, Postgres.
* **Portable to any Iceberg catalog.** Move `data/warehouse/` to S3,
  point Lakekeeper or Polaris at it, and you have a managed lakehouse —
  zero code changes, no migration.

That is the whole pitch: ship data products from a laptop, graduate
cleanly when you outgrow it.
