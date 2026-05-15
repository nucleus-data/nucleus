---
title: Materialization
description: What happens when Nucleus runs an asset — the five-step pipeline that produces an Iceberg snapshot.
---

# Materialization

A **materialization** is one execution of an asset function that produces one Iceberg snapshot. It is triggered by `nucleus run` or (in v0.2+) by the active scheduler.

## The five-step pipeline

Every materialization runs these five steps via the **Asset Materialization Adapter (AMA)**:

```
1. Validate    → schema contract check (if declared)
2. Partition   → apply partition spec (if any)
3. Compute     → your function body executes
4. Commit      → pyiceberg writes an atomic Iceberg snapshot
5. Lineage     → OpenLineage event emitted to transport
```

All five steps are handled by the `ctx` runtime. Your function only needs to worry about step 3 — returning the data.

## Modes

| Mode | What it does | When to use |
|------|-------------|-------------|
| `overwrite` | Replaces all existing data | Full refresh |
| `append` | Adds new rows without removing old ones | Incremental / CDC |
| `merge` | Upsert via merge key(s) | SCD Type 1 |

Set mode in `ctx.write()` or via `nucleus ingest --mode`.

## Materialization result

A `MaterializationResult` is returned from every successful run:

```python
result = nucleus.materialize("sales.daily_revenue")

print(result.asset_key)       # "sales.daily_revenue"
print(result.rows_written)    # 365
print(result.snapshot_id)     # Iceberg snapshot ID (integer)
print(result.duration_ms)     # 312
print(result.bytes_written)   # 124_800
```

## Partial failures

If a materialization fails mid-way, the Iceberg snapshot is **not committed** — the previous snapshot remains intact. Iceberg's atomic commit guarantee means you never see partial data.

If the failure is after step 3 but before step 4 (a commit failure), the error is raised as `NucleusCommitConflictError` (NE1002) or `NucleusCommitUnknownError` (NE1003). In both cases, the data on disk is unchanged.

## Incremental materialization

Incremental materializations only process data that changed since the last run. Set `mode="append"` and optionally provide a watermark:

```python
@nucleus.asset(
    table="raw.events",
    schedule="@hourly",
)
def raw_events(ctx) -> pl.DataFrame:
    last_run = ctx.last_materialization_time("raw.events")
    return fetch_events(since=last_run)
```

!!! note "v0.1 limitation"
    `ctx.last_materialization_time()` is not in v0.1. Use `ctx.read()` + Iceberg snapshot metadata for now, or handle watermarking in your function body.

## Retries

```python
@nucleus.asset(
    table="raw.orders",
    retries=nucleus.retries(count=3, delay="exponential"),
)
def raw_orders(ctx) -> pl.DataFrame:
    ...
```

Retries apply to transient failures (network timeouts, source connection drops). They do not retry schema validation failures or contract violations.

## Related

- [Asset](asset.md) — the underlying data primitive
- [Snapshot](snapshot.md) — what the commit produces
- [Contract](contract.md) — the validation in step 1
- [Check](check.md) — quality assertions after commit
