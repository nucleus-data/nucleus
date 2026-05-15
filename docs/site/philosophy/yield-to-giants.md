---
title: Yield to Giants
description: The Nucleus strategy for handling scale — integrate with Databricks and Snowflake rather than competing with them.
---

# Yield to Giants

Nucleus does not compete with Databricks. It integrates with Databricks (and Snowflake, and any other Iceberg-compatible platform) and yields to them when teams need distributed compute.

## The core idea

> When a Nucleus user's team grows beyond what a laptop can handle, we celebrate the graduation and make it frictionless — rather than forcing them to stay on Nucleus at all costs.

This is the opposite of vendor lock-in. It is lock-out prevention.

## Three graduation modes

### Mode 1 — Iceberg portability

The simplest path. Point Databricks at the same Iceberg tables you already have on S3. No data migration, no format conversion.

```python
# In Databricks — reads the exact same Iceberg tables Nucleus wrote
spark.read.format("iceberg").load("s3://your-bucket/warehouse/mart.daily_revenue")
```

**What moves:** The data (via S3), the schema (via Iceberg), the snapshot history.
**What doesn't:** The `@nucleus.asset` code, the schedule declarations, the `ctx` SDK calls.

### Mode 2 — Hybrid compute

Run lightweight assets locally (ingest, light transforms) and dispatch compute-heavy assets to Databricks:

```python
# v0.5+ planned
@nucleus.asset(
    table="analytics.full_history_model",
    compute="databricks",   # dispatch to Databricks for large join
)
def full_history_model(ctx) -> pl.DataFrame:
    ...
```

### Mode 3 — Iceberg REST federation

Use Lakekeeper or Polaris as a shared Iceberg catalog that both Nucleus and Databricks read from:

```
Nucleus → writes → Iceberg tables on S3
                         ↑
Databricks ← reads ← Lakekeeper REST catalog
```

Multi-team data mesh: each team uses their preferred tool; the catalog federates.

## Why not compete?

1. **Resource reality.** A solo founder cannot out-engineer Databricks's 2,000+ engineers.
2. **Iceberg moat.** The open standard is the moat — it makes graduation easy AND keeps Databricks from locking users in. We benefit from Iceberg's ubiquity.
3. **Different ICP.** Databricks's primary customer is an enterprise with hundreds of engineers. Nucleus's primary customer is a 5-person startup. These aren't competing.
4. **The graduation signal is a success.** When a Nucleus user migrates to Databricks, that's a win: they used Nucleus to build their first data products; those products are now running at scale; Nucleus helped them get there.

## Forbidden framing

Never describe Nucleus as:

- "A Databricks killer" ← forbidden per AGENTS.md §8 <!-- banned-term: Databricks killer -->
- "A Databricks replacement" ← forbidden
- "Better than Databricks" ← forbidden (different, not better-of-the-same)

Correct: **"We integrate and yield to giants rather than fight them."**
