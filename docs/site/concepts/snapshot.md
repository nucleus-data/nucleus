---
title: Snapshot
description: An immutable, versioned point-in-time state of an asset's Iceberg data.
---

# Snapshot

A **snapshot** is an immutable, versioned point-in-time state of an asset's data. Every materialization produces exactly one snapshot. Snapshots accumulate over time — Nucleus and Iceberg never delete them (unless you explicitly compact or expire them).

## What a snapshot is

An Iceberg snapshot is a pointer to a set of Parquet files. The snapshot records:

- Snapshot ID (unique integer)
- Timestamp of commit
- Parent snapshot ID (for time travel)
- Summary of the operation (rows added/deleted, bytes written)
- Manifest lists (the actual Parquet file locations)

Because snapshots are immutable Parquet + manifest files, they are:
- **Portable** — any Iceberg-compatible catalog can read them
- **Safe** — concurrent readers always see a consistent state
- **Durable** — stored in the object store, not in a proprietary format

## Listing snapshots

```bash
# v0.3+ command
nucleus snapshot list sales.daily_revenue
```

```
┌────────────────────┬──────────────┬───────────────────────┬──────────┐
│ snapshot_id        │ operation    │ committed_at          │ rows     │
├────────────────────┼──────────────┼───────────────────────┼──────────┤
│ 8193820491772...   │ overwrite    │ 2026-05-14 10:00:01   │   365    │
│ 7824930102831...   │ overwrite    │ 2026-05-13 10:00:03   │   364    │
└────────────────────┴──────────────┴───────────────────────┴──────────┘
```

## Time travel

Read data as it was at any past snapshot:

```python
# Read the snapshot from yesterday
snapshot = ctx.snapshot("sales.daily_revenue").at_version(7824930102831)
df = snapshot.read()
```

Or in SQL:

```sql
-- v0.3+
SELECT * FROM {{ ref('sales.daily_revenue') }}
FOR SYSTEM_VERSION AS OF 7824930102831
```

## Restoring a snapshot

`nucleus snapshot restore` (v0.3+) appends a new snapshot that is identical to a past one. It **never deletes** — the restore is itself a new snapshot:

```bash
nucleus snapshot restore sales.daily_revenue --to-version 7824930102831
```

## Snapshot retention

Iceberg snapshots accumulate. For long-lived assets, configure snapshot expiration:

```yaml
# nucleus_project.yaml
snapshots:
  expire_after_days: 30    # keep last 30 days of snapshots
  min_snapshots: 5         # always keep at least 5 snapshots
```

!!! note "v0.1"
    Snapshot expiration config is v0.3+. In v0.1, snapshots accumulate indefinitely. Disk usage is bounded by the Parquet file sizes; metadata overhead is minimal.

## Iceberg snapshot vs. Nucleus snapshot

In Nucleus vocabulary, **snapshot** always means an Iceberg snapshot — a full, consistent, readable point-in-time state of one asset. Never say "version" or "checkpoint".

## Related

- [Time Travel cookbook](../cookbook/iceberg-time-travel.md)
- [Iceberg documentation on snapshots](https://iceberg.apache.org/spec/#snapshots)
