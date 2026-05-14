# E-commerce ELT example

Narrative: you run an early-stage e-commerce company. Orders and customers live in **Postgres**; a lightweight finance teammate keeps a **SQLite** file that mirrors payment-webhook events. You want **Iceberg-backed assets** in a warehouse you fully control, then daily revenue and customer-LTV rollups you can hand to a BI tool.

This sample follows the **v0.1 CLI + SDK** only: `ctx.copy_from`, `ctx.sql`, `@nucleus.asset`, `@nucleus.check`, `nucleus run`, and `nucleus query`. No Workbench, no `ctx.write`, no scheduling UI.

Audience: **startup data teams** (on the order of five engineers, roughly **100GB–5TB** greenfield) — the beachhead persona described in `nucleus_architecture_v4.1.md` **section 1.5**.

## What you need

- **Python 3.11** (same pin as Nucleus v0.1)
- **Docker Desktop** (or compatible runtime) for MinIO + Postgres
- A **git checkout of Nucleus** with an editable install (`pip install -e ".[dev]"` from the repo root — `pip install nucleus` ships once the PyPI release is out)

## Layout

| Path | Purpose |
|------|---------|
| `nucleus_project.yaml` | Project config (catalog + warehouse paths) |
| `docker-compose.yaml` | MinIO + Postgres (port **5433** to avoid clashing with a local 5432) |
| `scripts/seed_postgres.sql` | Loaded automatically on first Postgres container start |
| `scripts/seed_stripe_sqlite.py` | Builds `data/stripe_events.db` |
| `assets/` | `@nucleus.asset` definitions (`raw` → `stg` → `marts`) |
| `checks/` | `@nucleus.check` contracts bound to those assets |

## Run it end-to-end

From the **repository root** (so `nucleus` is on your PATH):

```bash
cd examples/01-ecommerce-elt
docker compose up -d
python scripts/seed_stripe_sqlite.py
nucleus up
```

Expected: `nucleus up` finishes in a few seconds with storage + catalog checks (exact wording varies by terminal).

Materialize in dependency order (`upstream='skip'` in v0.1 — Nucleus does **not** auto-run upstream assets yet):

```bash
nucleus run raw.orders raw.customers raw.stripe_events
nucleus run stg.orders stg.customers
nucleus run marts.daily_revenue marts.customer_ltv
```

Spot-check the mart:

```bash
nucleus query "SELECT * FROM {{ ref('marts.daily_revenue') }} ORDER BY day"
```

Tear down containers when finished:

```bash
nucleus down
docker compose down
```

## Honest limitations (v0.1)

- **No auto orchestration** — you run layers explicitly (or script them) until upstream materialization lands in a later release.
- **`ctx` in asset bodies is a placeholder** — examples call `ctx.copy_from` / `ctx.sql` as module functions with explicit `warehouse_dir`.
- **Stripe is simulated** — the SQLite file stands in for a webhook log so the sample stays reproducible without API keys.

## Licensing

Example code is **Apache-2.0** (same as the parent repository) unless you add your own proprietary data or credentials.
