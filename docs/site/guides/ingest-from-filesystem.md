---
title: Ingest from Filesystem
description: Ingest local CSV, Parquet, JSON, and SQLite files into Iceberg.
---

# Ingest from Filesystem

Local files (CSV, Parquet, JSON, SQLite) are fully supported in v0.1 — no external service required.

## CSV

```bash
nucleus ingest ./data/orders.csv --as raw.orders --mode overwrite
```

With options:

```bash
nucleus ingest ./data/orders.csv \
  --as raw.orders \
  --mode append

# Multiple files (glob)
nucleus ingest "./data/orders_*.csv" --as raw.orders --mode append
```

Python SDK:

```python
import nucleus.ctx as ctx

ctx.copy_from("./data/orders.csv", target="raw.orders", mode="overwrite")
```

## Parquet

```bash
nucleus ingest ./data/orders.parquet --as raw.orders --mode overwrite
# Or a directory of Parquet files
nucleus ingest ./data/orders/ --as raw.orders --mode overwrite
```

## JSON (newline-delimited)

```bash
nucleus ingest ./data/events.jsonl --as raw.events --mode append
```

## SQLite

```bash
nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
```

Python SDK:

```python
ctx.copy_from(
    "sqlite:///./data/orders.db",
    table="orders",
    target="raw.orders",
    warehouse_dir="./data/warehouse",
)
```

## Schema inference

Nucleus auto-infers schema from the source file. If you need to override types:

```python
import polars as pl
import nucleus.ctx as ctx

# Read with explicit schema override
df = pl.read_csv("./data/orders.csv", schema={
    "order_id": pl.Int64,
    "amount": pl.Float64,
    "order_date": pl.Date,
})
ctx.write("raw.orders", df, mode="overwrite")
```

## Common errors

| Error | Code | Fix |
|-------|------|-----|
| `NucleusIOError` | NE1005 | File not found, permission denied, or disk full |
| `NucleusSchemaError` | NE2001 | CSV has inconsistent columns or wrong types |
| `NucleusSourceConnectionError` | NE1001 | SQLite file path is wrong (Windows: use absolute paths) |

!!! tip "Windows paths"
    On Windows, prefer absolute paths for SQLite: `sqlite:///C:/data/orders.db`
