---
title: Iceberg Time Travel
description: Read past snapshots of any asset for debugging, auditing, and reproducibility.
---

# Iceberg Time Travel

Every asset materialization creates an immutable Iceberg snapshot. Time travel lets you read data as it was at any past point.

## Use cases

- **Debug a data quality issue**: "What did the data look like before the bad deploy?"
- **Audit**: "What was in the orders table on 2026-03-01 at 9 AM?"
- **Reproducibility**: "Reproduce the exact report from last quarter"
- **Recovery**: "Restore to the state before an accidental overwrite"

## Python time travel (v0.1)

Access Iceberg snapshots directly via pyiceberg:

```python
from pyiceberg.catalog import load_catalog
# Docs: https://py.iceberg.apache.org/

# Load the local filesystem catalog
catalog = load_catalog("default", **{
    "type": "sql",
    "uri": "sqlite:///data/catalog.db",
    "warehouse": "data/warehouse",
})

table = catalog.load_table("mart.daily_revenue")

# List all snapshots
for snap in table.history():
    print(snap.snapshot_id, snap.timestamp_ms)

# Read data at a specific snapshot
import duckdb
# Docs: https://duckdb.org/docs/extensions/iceberg

con = duckdb.connect()
con.execute("INSTALL iceberg; LOAD iceberg;")
df = con.execute(f"""
    SELECT * FROM iceberg_scan(
        'data/warehouse/mart.daily_revenue',
        snapshot_id = {snap.snapshot_id}
    )
""").fetchdf()
```

## CLI time travel (v0.3+)

```bash
# List snapshots
nucleus snapshot list mart.daily_revenue

# Read at a specific snapshot
nucleus query "SELECT * FROM {{ ref('mart.daily_revenue') }}" \
  --snapshot 8193820491772946430 \
  --limit 20

# Read at a timestamp
nucleus query "SELECT * FROM {{ ref('mart.daily_revenue') }}" \
  --as-of "2026-05-01 09:00:00 UTC" \
  --limit 20
```

## Restoring a snapshot (v0.3+)

```bash
# Restore mart.daily_revenue to its state at snapshot 7824930102831
nucleus snapshot restore mart.daily_revenue --to-version 7824930102831
```

Restore appends a new snapshot identical to the target — never deletes history.

## DuckDB time travel SQL (v0.3+)

```sql
-- Read at a specific snapshot ID
SELECT *
FROM {{ ref('mart.daily_revenue') }}
FOR SYSTEM_VERSION AS OF 7824930102831

-- Read at a timestamp
SELECT *
FROM {{ ref('mart.daily_revenue') }}
FOR TIMESTAMP AS OF TIMESTAMPTZ '2026-05-01 09:00:00+00'
```

!!! note "v0.1 scope"
    `nucleus snapshot` commands and `FOR SYSTEM_VERSION AS OF` SQL are v0.3+ features. In v0.1, use the direct pyiceberg API shown above.
