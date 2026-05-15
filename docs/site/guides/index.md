---
title: Guides
description: Step-by-step guides for common Nucleus workflows.
---

# Guides

Focused how-to guides for specific workflows. Each guide assumes you've completed the [Quickstart](../getting-started/quickstart.md).

## Ingestion guides

| Guide | Source | Status |
|-------|--------|--------|
| [Ingest from Postgres](ingest-from-postgres.md) | PostgreSQL | ✅ v0.1 |
| [Ingest from MySQL](ingest-from-mysql.md) | MySQL / MariaDB | ✅ v0.1 |
| [Ingest from Snowflake](ingest-from-snowflake.md) | Snowflake | ⏳ v0.3 |
| [Ingest from S3](ingest-from-s3.md) | AWS S3 (Parquet/CSV) | ⏳ v0.3 |
| [Ingest from GCS](ingest-from-gcs.md) | Google Cloud Storage | ⏳ v0.3 |
| [Ingest from Filesystem](ingest-from-filesystem.md) | Local CSV/Parquet/JSON | ✅ v0.1 |

## Transformation guides

| Guide | Description |
|-------|-------------|
| [Write SQL Transformations](write-sql-transformations.md) | `@nucleus.sql_asset` + Jinja `{{ ref() }}` |
| [Query Results](query-results.md) | `nucleus query` + `ctx.sql` |

## Operations guides

| Guide | Description |
|-------|-------------|
| [Schedule an Asset](schedule-asset.md) | Declare cron schedules + preview next runs |
| [Use AI Copilot](use-ai-copilot.md) | `nucleus chat` + privacy gate |
| [Graduate to Databricks](graduate-to-databricks.md) | Move your Iceberg tables to the cloud |
