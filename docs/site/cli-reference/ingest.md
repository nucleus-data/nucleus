---
title: nucleus ingest
description: The 30-minute beachhead one-liner — ingest any source into an Iceberg asset.
---

# `nucleus ingest`

Ingest an external data source into an Iceberg asset.

## Synopsis

```
nucleus ingest SOURCE_URI --table SRC_TABLE --as DEST_KEY [--mode overwrite|append|merge] [--merge-on COL...]
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE_URI` | Required | Connection string or file path |
| `--table SRC_TABLE` | Conditional | Source table name (required for database sources) |
| `--as DEST_KEY` | Required | Destination asset key (`namespace.name`) |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `overwrite` | Write mode: `overwrite`, `append`, or `merge` |
| `--merge-on COL` | — | Merge key column(s) for `--mode merge` (repeatable) |
| `--no-progress` | false | Suppress progress bar |

## Supported sources (v0.1)

| URI scheme | Example |
|-----------|---------|
| `postgres://` | `postgres://user:pass@host:5432/db` |
| `mysql+pymysql://` | `mysql+pymysql://user:pass@host:3306/db` |
| `sqlite:///` | `sqlite:///./data/orders.db` |
| Local CSV | `./data/orders.csv` |
| Local Parquet | `./data/orders.parquet` |
| Local JSON/JSONL | `./data/events.jsonl` |

## Output

```
Ingesting public.orders → raw.orders …
[████████████████████] 10,000 rows in 1.2s

✓ Committed Iceberg snapshot (10,000 rows, 2.1 MB)

Preview (first 10 rows):
┌──────────┬─────────────┬──────────┬───────────┐
│ order_id │ customer_id │ amount   │ status    │
├──────────┼─────────────┼──────────┼───────────┤
│ 1        │ 42          │ 149.99   │ completed │
...
```

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusSourceConnectionError` | NE1001 | Can't reach the source |
| `NucleusSchemaError` | NE2001 | Schema mismatch with existing table |
| `NucleusCommitConflictError` | NE1002 | Concurrent write conflict |

## Examples

```bash
# Postgres, overwrite
nucleus ingest postgres://user:pass@host/db --table public.orders --as raw.orders

# SQLite, append
nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders --mode append

# CSV file, overwrite
nucleus ingest ./data/orders.csv --as raw.orders

# Merge with key
nucleus ingest postgres://user:pass@host/db \
  --table public.orders --as raw.orders \
  --mode merge --merge-on order_id

# Suppress progress bar (CI)
nucleus ingest ./data/orders.csv --as raw.orders --no-progress

# JSON output
nucleus ingest postgres://... --table orders --as raw.orders --format json
```
