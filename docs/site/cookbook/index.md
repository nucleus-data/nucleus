---
title: Cookbook
description: Practical recipes for common data engineering patterns in Nucleus.
---

# Cookbook

Real patterns, ready to adapt. Each recipe is a complete, runnable example.

| Recipe | Pattern |
|--------|---------|
| [CDC from Postgres](cdc-from-postgres.md) | Change data capture with merge keys |
| [Slowly Changing Dimensions](slowly-changing-dimensions.md) | SCD Type 1 and Type 2 |
| [Timeseries Rollup](timeseries-rollup.md) | Aggregating time-series events into buckets |
| [Deduplication](deduplication.md) | Removing duplicate rows with window functions |
| [Daily Batch with Lateness](daily-batch-with-lateness.md) | Handling late-arriving data |
| [Error Recovery](error-recovery.md) | Retrying failed materializations and debugging errors |
| [Multi-Tenant Projects](multi-tenant-projects.md) | Isolating data by tenant in a single project |
| [Schema Evolution](schema-evolution.md) | Adding columns, renaming, handling incompatible changes |
| [Iceberg Time Travel](iceberg-time-travel.md) | Reading past snapshots for debugging and auditing |
| [AI Copilot Prompts](ai-copilot-prompts.md) | Effective prompts for the nucleus chat Copilot |
