---
title: Ingest from S3
description: Read Parquet or CSV files from AWS S3 or S3-compatible storage into Iceberg (v0.3).
---

# Ingest from S3

<!-- pending implementation -->

!!! warning "v0.3 — Not yet implemented"
    S3 source ingestion is planned for v0.3 (Mo 14-20). This page is a documentation skeleton.
    Track progress: [GitHub Issues](https://github.com/nucleus-data/nucleus/issues)

## Planned interface

```bash
# v0.3+ planned
nucleus ingest s3://my-bucket/data/orders/*.parquet --as raw.orders --mode overwrite
nucleus ingest s3://my-bucket/data/events/dt=2026-05-*/ --as raw.events --mode append
```

## Workaround until v0.3

Use DuckDB directly to read S3 Parquet and pipe through `ctx.copy_from`:

```python
# Works today in v0.1
import duckdb
# Docs: https://duckdb.org/docs/extensions/httpfs/s3api
import nucleus.ctx as ctx
import polars as pl

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET s3_region='us-east-1';")
con.execute("SET s3_access_key_id='...';")
con.execute("SET s3_secret_access_key='...';")

df = pl.from_arrow(
    con.execute("SELECT * FROM parquet_scan('s3://my-bucket/orders/*.parquet')").arrow()
)
ctx.write("raw.orders", df, mode="overwrite")
```

!!! note "NEEDS VERIFICATION"
    The DuckDB httpfs S3 read path above uses APIs verified against
    https://duckdb.org/docs/extensions/httpfs/s3api as of DuckDB 1.1.3.
    Verify `s3_access_key_id` parameter name against that version's docs before use.
