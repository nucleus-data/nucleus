# Architecture — `nucleus-demo-app`

How the asset graph fits together, why each layer exists, and where to
extend it without leaving the v0.1 surface.

---

## 1. The asset graph

```
┌─────────────────────────────┐
│      Postgres (source)       │
│  public.orders              │
│  public.customers           │
│  public.products            │
└──────────────┬──────────────┘
               │ ctx.copy_from (Beta)
               ▼
┌──────────────────────────────────────────┐
│  Bronze (Iceberg, 1:1 copy of source)     │
│  • bronze.orders                         │
│  • bronze.customers                      │
│  • bronze.products                       │
└──────────────┬──────────────┬─────────────┘
               │              │
               │              ├────────────────────────┐
               ▼              ▼                        ▼
┌────────────────────────┐ ┌──────────────────┐ ┌─────────────────────┐
│ silver.daily_revenue    │ │ silver.customer  │ │ silver.top_products │
│  (Jinja SQL on bronze)  │ │ _ltv             │ │  (revenue per SKU)  │
│  daily × channel        │ │  customer × ltv  │ │  ranked desc        │
└──────────────┬─────────┘ └──────────┬───────┘ └─────────┬───────────┘
               │                      │                   │
               │      ┌───────────────┘                   │
               │      │                                   │
               ▼      ▼                                   ▼
┌────────────────────────────────┐         ┌──────────────────────────────┐
│  gold.revenue_dashboard         │         │  gold.customer_segments       │
│  weekly KPIs + top-20 SKUs      │         │  cohort × LTV bucket          │
└────────────────────────────────┘         └──────────────────────────────┘
```

Eight assets, three layers, two checks-by-error and one check-by-warn.

---

## 2. Why three layers?

The medallion split is conventional for a reason — it keeps each asset
small and replayable:

| Layer  | Owns the responsibility for…                                  | Cost of rerun                                     |
| ------ | -------------------------------------------------------------- | ------------------------------------------------- |
| Bronze | Pulling from the operational source. Schema 1:1 with Postgres. | Touches the network → keep cheap, retry-friendly. |
| Silver | Cleaning, typing, joining. Pure SQL on bronze.                 | Local DuckDB on Iceberg — free to rerun.          |
| Gold   | Denormalised views a BI tool consumes directly.                | Free to rerun; small output size.                 |

If a downstream chart looks wrong, you can fix the silver SQL and rerun
just that asset and its descendants — bronze stays put, no Postgres
load, no schema rediscovery.

---

## 3. Why split assets into `assets/` + `sql/`?

Each `@nucleus.asset` body in `assets/` is a thin Python wrapper that
calls `ctx.sql(...)` against a SQL template stored under `sql/`.
Separation keeps the SQL diff-friendly (no Python noise) and lets a
SQL-only contributor open `sql/silver_daily_revenue.sql` without ever
touching the decorator. Same trick dbt uses, same effect.

Bronze assets do not have a SQL counterpart — they pure-call
`ctx.copy_from(...)`. That helper is the canonical v0.1 ingestion entry
point per [`docs/specs/nucleus_ctx_sdk_spec.md`](../../specs/nucleus_ctx_sdk_spec.md) §0
("`ctx` is the only thing users import").

---

## 4. The `ctx` API surface this demo touches

The whole demo only uses three calls from
[`nucleus.ctx`](../../../src/nucleus/ctx/__init__.py):

| Call                               | Where used                                  | Purpose                                          |
| ---------------------------------- | ------------------------------------------- | ------------------------------------------------ |
| `ctx.copy_from(url, ..., target=)` | bronze assets                               | Land a Postgres table as an Iceberg snapshot.    |
| `ctx.sql(query, warehouse_dir=)`   | silver + gold assets, all checks            | Run Jinja SQL against the local Iceberg catalog. |
| `ctx.read(key, warehouse_dir=)`    | checks + `notebooks/exploration.py`         | Read a materialised asset back into Polars.      |

Plus the two decorators from the SDK:

| Decorator                          | Where used    | Purpose                                       |
| ---------------------------------- | ------------- | --------------------------------------------- |
| `@nucleus.asset("schema.name", …)` | every asset   | Register the asset body and its dependencies. |
| `@nucleus.check("schema.name", …)` | every check   | Run a quality assertion after materialization. |

Five symbols. Whole demo. Anything else is YAML or shell.

---

## 5. Vocabulary discipline

Per [`AGENTS.md` §7](../../../AGENTS.md), the project sticks to:

* **asset** — never "table" as a primitive
* **materialization** — the act of producing a snapshot
* **snapshot** — never "version" or "checkpoint"
* **check** — never "test" inside an asset context
* **contract** — declarative shape guarantees (deferred to v0.2+ in this demo)

Forbidden in any user-facing string anywhere in this project: any
external classname (Dagster, DuckDB, Polars, dlt, pyiceberg) — Nucleus
translates them to `NucleusError` subclasses at every boundary.

---

## 6. Extending this demo

| Goal                                      | Where to add it                                                             |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| Add a new bronze source                   | New `assets/bronze_<name>.py` calling `ctx.copy_from(...)`.                |
| Add a new silver/gold transform           | New `sql/<layer>_<name>.sql` + matching `assets/<layer>_<name>.py`.         |
| Add a new quality guard                   | New `checks/<name>.py`; remember to import it from `checks/__init__.py`.    |
| Swap source from Postgres → MySQL/SQLite  | Change the connection URL in `assets/_common.py`; `ctx.copy_from` dispatches by URL scheme. |
| Add column-level lineage                  | v0.5+ — see `docs/specs/nucleus_architecture_v4.1.md` §17.                             |

Avoid:

* Importing Dagster, DuckDB, Polars, pyiceberg directly inside an asset
  body. Use `ctx.*` instead — that is what gives you swap-safety and
  error translation for free.
* Inlining secrets into `assets/`. Either use environment variables
  (the pattern in `assets/_common.py`) or wait for the secrets module
  in v0.3+.

---

## 7. Where this graph graduates

When the dataset outgrows a single laptop:

1. **Mode 1 — Iceberg portability.** Point a managed Iceberg catalog
   (Lakekeeper, Polaris, Unity, R2) at the same Parquet files; nothing
   else changes. The asset Python and SQL are catalog-agnostic.
2. **Mode 2 — Hybrid compute.** Add `compute="databricks"` (v0.3+) to
   the heaviest gold assets so they dispatch to Databricks SQL while
   silver stays local.
3. **Mode 3 — Federation.** Cross-catalog queries via the Iceberg REST
   federation surface (v2.0+).

See `docs/specs/nucleus_architecture_v4.1.md` §10 for the full yield-to-giants
strategy.
