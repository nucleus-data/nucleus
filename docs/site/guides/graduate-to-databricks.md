---
title: Graduate to Databricks
description: The yield-to-giants strategy — moving your Iceberg assets to Databricks without migration.
---

# Graduate to Databricks

When your team outgrows a single laptop or node, your Iceberg data travels with you to Databricks, Snowflake, or any Iceberg-compatible catalog. This is the **yield-to-giants** strategy — the graduation path by design.

## The key insight

Every Nucleus asset is an Apache Iceberg table. Iceberg is an open standard. Any system that can read Iceberg can read your data today — without any export, conversion, or migration.

```python
# In Nucleus (local)
df = ctx.read("mart.daily_revenue")

# In Databricks (after pointing at the same S3 path)
df = spark.read.format("iceberg").load("s3://your-bucket/warehouse/mart.daily_revenue")
```

**Same data. Same snapshots. Same schema history.** Nothing migrates.

## Graduation modes

Per [architecture v4.1 §10](../philosophy/yield-to-giants.md), there are three graduation modes:

### Mode 1 — Iceberg portability

Point Databricks at your existing Iceberg tables on S3. No data movement needed.

**When to use:** You're moving your team to Databricks entirely. Your Nucleus-produced Iceberg tables are already there.

```python
# Databricks: register your Iceberg tables in Unity Catalog
spark.sql("""
  CREATE TABLE my_catalog.sales.daily_revenue
  USING ICEBERG
  LOCATION 's3://your-bucket/warehouse/sales.daily_revenue/'
""")
```

### Mode 2 — Hybrid compute

Keep Nucleus for local development and lightweight transforms. Dispatch heavy assets to Databricks for large-scale compute.

**When to use:** Your team is growing; most assets still run locally, but a few large jobs need distributed compute.

```python
# v0.5+ planned: ctx.materialize with compute target
@nucleus.asset(
    table="analytics.full_history_model",
    compute="databricks",   # v0.5+ planned syntax
)
def full_history_model(ctx) -> pl.DataFrame:
    ...
```

### Mode 3 — Iceberg REST federation

Use Lakekeeper or Polaris as an Iceberg REST catalog that Databricks can query directly. Data lives in your storage; Databricks reads it via REST.

**When to use:** Multi-team data mesh with mixed ownership. Each team uses Nucleus locally; the shared catalog federates across Databricks, Snowflake, and Nucleus.

## Step-by-step: Mode 1

### 1. Push your warehouse to S3

```bash
# Configure your project to use remote S3
# nucleus_project.yaml
storage:
  endpoint: https://s3.amazonaws.com
  bucket: my-prod-data-bucket
  region: us-east-1

# Re-run ingestion + transforms against remote S3
nucleus up --catalog filesystem --storage s3
nucleus run --all
```

### 2. Register tables in Databricks

```python
# In a Databricks notebook
for table_key in ["raw.orders", "staging.orders", "mart.daily_revenue"]:
    namespace, name = table_key.split(".")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS my_catalog.{namespace}.{name}
        USING ICEBERG
        LOCATION 's3://my-prod-data-bucket/warehouse/{table_key}/'
    """)
```

### 3. Verify

```python
# Should return identical results
display(spark.sql("SELECT * FROM my_catalog.mart.daily_revenue LIMIT 10"))
```

## What doesn't move

Nucleus-specific concepts that don't have Databricks equivalents:

| Nucleus concept | Databricks equivalent | Notes |
|----------------|----------------------|-------|
| `@nucleus.asset` | Unity Catalog table | Schema and data transfer; the decorator doesn't |
| `@nucleus.check` | Databricks DQ Expectations | Rewrite check logic in DQ or Soda |
| `nucleus schedule` | Databricks Jobs / Workflows | Rewrite scheduling in Databricks Jobs |
| Error translation | Databricks-native errors | Direct framework errors |

## The contract

When you graduate:
- Your **data** moves seamlessly (Iceberg portability)
- Your **code** (Python assets, SQL transforms) moves with minor changes
- Your **orchestration** (schedules, dependencies) needs rewriting in Databricks format

This is the intended design. Nucleus doesn't lock you in to its orchestration primitives — Iceberg is the lock-free substrate.

## Related

- [Philosophy: Yield to Giants](../philosophy/yield-to-giants.md)
- [Architecture v4.1 §10](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md)
