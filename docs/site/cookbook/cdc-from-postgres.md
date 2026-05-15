---
title: CDC from Postgres
description: Change data capture from Postgres into Iceberg using merge mode.
---

# CDC from Postgres

Capture only new or changed rows from a Postgres table and merge them into an Iceberg asset.

## Pattern: merge on primary key

```bash
# One-time or scheduled via nucleus run
nucleus ingest postgres://user:pass@host/db \
  --table public.orders \
  --as raw.orders \
  --mode merge \
  --merge-on order_id
```

This reads **all rows** from the source, merges on `order_id`, and upserts changes. For large tables, this is expensive. See the incremental pattern below.

## Pattern: incremental via updated_at

```python
import nucleus
import polars as pl
from datetime import datetime, timezone


@nucleus.asset(
    table="raw.orders",
    schedule="@hourly",
)
def raw_orders(ctx) -> pl.DataFrame:
    # Get the last successful materialization time
    # v0.1: read from Iceberg snapshot metadata
    last_snapshot = ctx.catalog.last_snapshot("raw.orders")
    watermark = last_snapshot.committed_at if last_snapshot else datetime(2020, 1, 1, tzinfo=timezone.utc)

    # Fetch only rows changed since the watermark
    import sqlalchemy as sa
    engine = sa.create_engine("postgres://user:pass@host/db")
    with engine.connect() as conn:
        result = conn.execute(sa.text(
            "SELECT * FROM public.orders WHERE updated_at > :watermark"
        ), {"watermark": watermark})
        df = pl.from_arrow(result.mappings().fetchall())

    return df
```

!!! note "ctx.last_materialization_time"
    `ctx.last_materialization_time()` is planned for v0.2. In v0.1, read the Iceberg snapshot metadata directly via `ctx.catalog.last_snapshot()`.

## Pattern: full CDC with Debezium (v0.3+)

For true row-level CDC (INSERT/UPDATE/DELETE events), use Debezium + dlt (v0.3+):

```python
# v0.3+ — dlt Debezium source (planned)
@nucleus.source(
    name="raw.orders_cdc",
    connector="debezium",
    connection="orders-postgres",
)
def raw_orders_cdc(ctx):
    return ctx.connector.debezium(topic="postgres.public.orders")
```

## Deduplication after merge

After a merge, deduplicate to ensure exactly one row per key:

```python
@nucleus.sql_asset(table="staging.orders_deduped")
def orders_deduped(ctx) -> str:
    return """
        SELECT * EXCLUDE (rn)
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY updated_at DESC
                ) AS rn
            FROM {{ ref('raw.orders') }}
        )
        WHERE rn = 1
    """
```
