# Recipe: Postgres → Iceberg in 25 minutes

> **Time**: ~25 min (5-min buffer against the 30-min beachhead metric) · **Difficulty**: Junior DE · **Prereqs**: Python 3.11 / 3.12, Docker Desktop, ~2 GB disk
> **Status**: pre-v0.1 — depends on PoCs #1 + #3 + #4 passing first; CLI lines marked `<!-- pre-v0.1 -->`
> **Refs**: [v4.1 §1.5](../specs/nucleus_architecture_v4.1.md) · [`docs/specs/nucleus_poc_plan.md`](../specs/nucleus_poc_plan.md) §5 · [`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) · [`csv_to_iceberg.md`](./csv_to_iceberg.md) (no-Docker variant)

The canonical beachhead recipe — the one PoC #5 external testers run end-to-end ([`docs/specs/nucleus_poc_plan.md`](../specs/nucleus_poc_plan.md) §5). 5-engineer team, `git clone` to BI-ready Iceberg asset on a laptop in <30 minutes.

---

## What you'll build

A Northwind-style orders pipeline: local Postgres source → Iceberg `raw.orders` asset (auto-inferred schema) → Python asset `analytics.orders_daily` rolled up by day → BI tool reading the Iceberg path via the DuckDB Iceberg extension.

## Why this matters

The non-negotiable v0.1 metric ([v4.1 §1.5](../specs/nucleus_architecture_v4.1.md)): *5-engineer startup team, MacBooks, Postgres + S3, first BI-ready Iceberg table from `git clone` in **<30 minutes**.* The data product you ship is an *asset* per [v4.1 §12.1](../specs/nucleus_architecture_v4.1.md) — Iceberg-backed, inferred schema, asset-level lineage, contract slot.

---

## Step 1: Confirm prerequisites (~2 min)

```bash
python --version          # 3.11.x or 3.12.x
docker compose version    # v2 syntax
```

Install missing pieces via [`SETUP.md`](../../SETUP.md) §1-§3.

## Step 2: Stand up a Postgres source (~5 min)

`docker-compose.yml` next to your future project root:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: <PLACEHOLDER>
      POSTGRES_DB: northwind
    ports: ["5432:5432"]
```

Boot and seed 100 rows of Northwind-style orders:

```bash
docker compose up -d postgres
sleep 5
docker compose exec -T postgres psql -U postgres -d northwind <<'SQL'
CREATE TABLE public.orders (
  order_id    INTEGER PRIMARY KEY,
  customer_id TEXT NOT NULL,
  amount      NUMERIC(10, 2) NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT now()
);
INSERT INTO public.orders (order_id, customer_id, amount)
SELECT i, 'cust_' || (i % 20), 10.0 + (random() * 990)
FROM generate_series(1, 100) i;
SQL
```

## Step 3: Initialize a Nucleus project (~2 min)

```bash
nucleus init northwind-demo --template=basic   # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.1 -->
cd northwind-demo
nucleus up                                      # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.2 -->
```

Expected ([v4.1 §11.1](../specs/nucleus_architecture_v4.1.md)):

```
✓ MinIO ready                  :9000
✓ Filesystem catalog ready     .nucleus/catalog
✓ Metadata DB ready            .nucleus/state.sqlite
✓ Dagster substrate ready
Total: 6.4s
```

## Step 4: Ingest the source table (~3 min)

```bash
nucleus ingest postgres://postgres:<PLACEHOLDER>@localhost:5432/northwind \
    --table public.orders --as raw.orders       # <!-- pre-v0.1; v4.1 §5.5.1 -->
```

Auto-infers the Iceberg schema, atomically commits via the filesystem catalog, prints a 10-row preview. Destination: `.nucleus/warehouse/raw/orders/`. No Python, no schema declaration, no orchestration code.

## Step 5: Verify (~1 min)

```bash
nucleus sql "SELECT count(*) FROM raw.orders"   # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §4.5 -->
# Expected: 100
```

`nucleus sql` runs DuckDB against your Iceberg assets via `Table.scan().to_duckdb('orders')` zero-copy ([`docs/internal/research/pyiceberg.md`](../internal/research/pyiceberg.md) §5).

## Step 6: Add a transformation asset (~8 min)

`assets/analytics/orders_daily.py`:

```python
import nucleus
import polars as pl
# Docs: https://docs.pola.rs/api/python/stable/

@nucleus.asset
def orders_daily(ctx) -> pl.DataFrame:
    """Daily order rollup. Materializes to analytics.orders_daily."""
    raw = ctx.read("raw.orders", as_="polars")
    return (
        raw.with_columns(pl.col("created_at").dt.truncate("1d").alias("day"))
        .group_by("day")
        .agg(
            pl.col("order_id").count().alias("order_count"),
            pl.col("amount").sum().alias("revenue"),
        )
        .sort("day")
    )
```

```bash
nucleus run analytics.orders_daily              # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §4.1 -->
```

Second Iceberg asset, downstream of `raw.orders`, asset-level lineage emitted to OpenLineage ([v4.1 §12.4](../specs/nucleus_architecture_v4.1.md)).

## Step 7: Hook a BI tool to your data (~4 min)

Any BI tool with a DuckDB driver — Metabase OSS, Tableau Desktop 2024+, Power BI via ODBC, Hex, Mode, Evidence — can attach:

```sql
-- in `duckdb` CLI:
INSTALL iceberg;
LOAD iceberg;
SELECT * FROM iceberg_scan('.nucleus/warehouse/analytics/orders_daily');
-- Point your BI tool at this DuckDB connection.
```

Post-v0.1, `nucleus enable bi-metabase` ([`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) §8.1) will boot Metabase pre-wired.

Done. Total: **<25 min** if nothing went sideways.

---

## Verification

| Signal | Pass criterion |
|---|---|
| Source seeded | `psql ... SELECT count(*)` returns 100 |
| Iceberg ingest | `.nucleus/warehouse/raw/orders/` has non-empty `metadata/` + `data/` |
| Asset materialized | `nucleus describe analytics.orders_daily` shows recent `✓` |
| Lineage | `nucleus lineage analytics.orders_daily` shows `raw.orders` upstream |
| BI reads | `duckdb` + `iceberg_scan(...)` returns expected columns |

## Troubleshooting

- **`connection refused` on ingest** — Postgres not yet ready; `docker compose logs postgres` should show `database system is ready to accept connections`.
- **Schema picks `STRING` for `amount`** — source was `VARCHAR`, not `NUMERIC`. Re-create the source table; v0.1 has no manual type override (NEEDS VERIFICATION).
- **`nucleus sql` says "asset not defined"** — namespace mismatch; check spelling against `nucleus list` ([`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) §5.1).

## What's next

- **No Docker?** [`csv_to_iceberg.md`](./csv_to_iceberg.md) — same pattern, ~15 min, no source DB.
- **Agent access (v0.5+)?** [`slack_bot_on_data.md`](./slack_bot_on_data.md). **Not runnable today.**
- **Patterns**: [`partitioning.md`](../patterns/partitioning.md) · [`snapshot_retention.md`](../patterns/snapshot_retention.md).

---

## NEEDS VERIFICATION

Per [AGENTS.md §11.12](../../AGENTS.md), uncertain claims logged so PoC #5 can confirm or reject:

1. **`nucleus ingest postgres://...`** is spec-only as of 2026-05; PoC #3 validates SQLite only ([`poc/p3_ingest/STATUS.md`](../../poc/p3_ingest/STATUS.md)). Postgres lands once the scaffold graduates to `src/nucleus/ctx/copy_from.py` (~200 LOC per [v4.1 §5.5.1](../specs/nucleus_architecture_v4.1.md)).
2. **`nucleus init --template=basic`** scaffold content unspecified beyond the template name in [`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) §3.1.
3. **`@nucleus.asset` + `ctx.read(..., as_="polars")`** are v0.1 per the ctx SDK table ([v4.1 §13.2](../specs/nucleus_architecture_v4.1.md)) but no implementation lives in `src/nucleus/` yet (AGENTS.md §11.1 phase gate).
4. **`nucleus sql` auto-resolves Iceberg asset names to DuckDB tables** — pyiceberg supports the underlying `.to_duckdb(name)` ([`docs/internal/research/pyiceberg.md`](../internal/research/pyiceberg.md) §5); the `ctx`-side glue is unimplemented.
5. **DuckDB Iceberg extension** read coverage of newly-written tables — read-only in 1.1.3 per [`docs/internal/research/duckdb.md`](../internal/research/duckdb.md); confirm against [`docs/internal/compatibility.md`](../internal/compatibility.md).

Hit any of these? Log to [`docs/internal/research/ai_hallucinations.md`](../internal/research/ai_hallucinations.md). Re-validate after PoC #5 (per [`docs/specs/nucleus_poc_plan.md`](../specs/nucleus_poc_plan.md) §13).
