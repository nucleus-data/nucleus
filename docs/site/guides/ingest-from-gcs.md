---
title: Ingest from GCS
description: Read files from Google Cloud Storage into Iceberg (v0.3 planned).
---

# Ingest from GCS

<!-- pending implementation -->

!!! warning "v0.3 — Not yet implemented"
    GCS source ingestion is planned for v0.3. This page is a documentation skeleton.

## Planned interface

```bash
# v0.3+ planned
nucleus ingest gcs://my-bucket/data/orders/ --as raw.orders --mode overwrite
```

## Workaround until v0.3

Use DuckDB's `httpfs` extension with GCS credentials:

```python
import duckdb
# Docs: https://duckdb.org/docs/extensions/httpfs/gcs
# NEEDS VERIFICATION: verify GCS credential params against DuckDB 1.1.3 docs
import polars as pl
import nucleus.ctx as ctx

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
# GCS uses HMAC keys via the S3-compatible endpoint
con.execute("SET s3_endpoint='storage.googleapis.com';")
con.execute("SET s3_access_key_id='GOOG...';")
con.execute("SET s3_secret_access_key='...';")

df = pl.from_arrow(
    con.execute("SELECT * FROM parquet_scan('gcs://my-bucket/orders/*.parquet')").arrow()
)
ctx.write("raw.orders", df, mode="overwrite")
```
