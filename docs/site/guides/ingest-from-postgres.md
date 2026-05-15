---
title: Ingest from Postgres
description: Pull data from a PostgreSQL database into Iceberg using nucleus ingest or ctx.copy_from.
---

# Ingest from Postgres

Nucleus can ingest from any PostgreSQL-compatible database (PostgreSQL, Amazon RDS, Aurora, Supabase, Neon) in one CLI command or one Python call.

## Prerequisites

- Nucleus installed with core deps (includes `psycopg[binary]==3.2.3` and `sqlalchemy==2.0.36`)
- A Postgres connection string: `postgres://user:password@host:port/database`
- `nucleus up` running

## CLI (one-liner)

```bash
nucleus ingest postgres://user:password@localhost:5432/mydb \
  --table public.orders \
  --as raw.orders \
  --mode overwrite
```

Output:

```
Ingesting public.orders → raw.orders …
[████████████████████] 10,000 rows in 1.2s
✓ Committed Iceberg snapshot (10,000 rows, 2.1 MB)

Preview (first 10 rows):
┌──────────┬─────────────┬────────┬───────────┐
│ order_id │ customer_id │ amount │ status    │
...
```

## Python SDK

```python
import nucleus.ctx as ctx

rows = ctx.copy_from(
    "postgres://user:password@localhost:5432/mydb",
    table="public.orders",
    target="raw.orders",
    mode="overwrite",
)
print(f"Ingested {rows} rows")
```

## Incremental ingest (append mode)

```bash
nucleus ingest postgres://user:password@host/db \
  --table public.events \
  --as raw.events \
  --mode append
```

!!! tip "Watermark-based incremental"
    For truly incremental ingestion (only new rows since last run), use the `--merge-on` flag with a monotonic key:

    ```bash
    nucleus ingest postgres://... \
      --table public.events \
      --as raw.events \
      --mode merge \
      --merge-on event_id
    ```

## Multiple tables at once

Use a shell loop or Python:

```bash
for table in orders customers products; do
  nucleus ingest postgres://user:pass@host/db \
    --table public.$table \
    --as raw.$table \
    --mode overwrite
done
```

## SSL / TLS connections

Append SSL parameters to the connection string:

```bash
# SSL required
nucleus ingest "postgres://user:pass@host/db?sslmode=require" \
  --table public.orders --as raw.orders
```

## Common errors

| Error | Code | Cause | Fix |
|-------|------|-------|-----|
| `NucleusSourceConnectionError` | NE1001 | Can't reach the database | Check host, port, firewall; verify credentials |
| `NucleusSchemaError` | NE2001 | Source schema changed since last ingest | Review schema, update contract |
| `NucleusPermissionError` | NE1006 | DB user lacks SELECT | Grant `SELECT ON public.orders TO nucleus_user` |

See [NE1xxx errors](../errors/ne1xxx.md) for full error reference.

## Source types supported in v0.1

| Source URI | Driver |
|-----------|--------|
| `postgres://` / `postgresql://` | `psycopg[binary]` via SQLAlchemy |
| `mysql://` | `pymysql` via SQLAlchemy |
| `sqlite:///` | stdlib `sqlite3` via SQLAlchemy |
| Local CSV / Parquet / JSON | `polars` / `duckdb` direct |

## Related

- [ctx.copy_from API reference](../api-reference/ctx.md)
- [NE1001: Source connection error](../errors/ne1xxx.md)
- [Postgres to Iceberg recipe](https://github.com/nucleus-data/nucleus/blob/main/docs/recipes/postgres_to_iceberg.md)
