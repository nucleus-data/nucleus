---
title: Ingest from Snowflake
description: Pull data from Snowflake into Iceberg (pending connector implementation in v0.3).
---

# Ingest from Snowflake

<!-- pending implementation -->

!!! warning "v0.3 — Not yet implemented"
    The Snowflake connector is planned for v0.3 (Mo 14-20). This page is a documentation skeleton.
    Track progress: [GitHub Issues](https://github.com/nucleus-data/nucleus/issues)

## Planned interface

The Snowflake connector will follow the same `nucleus ingest` pattern as Postgres:

```bash
# v0.3+ planned syntax
nucleus ingest snowflake://user:password@account.snowflakecomputing.com/database \
  --table RAW.ORDERS \
  --as raw.orders \
  --mode overwrite
```

## Planned Python SDK

```python
# v0.3+ planned
import nucleus.ctx as ctx

ctx.copy_from(
    "snowflake://user:pass@account.snowflakecomputing.com/db?schema=RAW&warehouse=COMPUTE_WH",
    table="ORDERS",
    target="raw.orders",
)
```

## Workaround until v0.3

Export a Snowflake query to Parquet and ingest the file:

```sql
-- In Snowflake
COPY INTO @my_stage/orders/ FROM (
  SELECT * FROM RAW.ORDERS
) FILE_FORMAT = (TYPE = PARQUET);
```

Then download from the stage and ingest:

```bash
nucleus ingest ./orders/ --as raw.orders --mode overwrite
```

Alternatively, dlt has a mature Snowflake source. See [dlt documentation](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration).

## Design notes

The Snowflake connector will wrap `snowflake-connector-python` via SQLAlchemy's `snowflake-sqlalchemy` dialect. Per AGENTS.md §11.12, the official docs will be read before any implementation starts.

License: `snowflake-connector-python` is Apache-2.0. Verified in [ADR-007](../governance/architecture-decisions.md).
