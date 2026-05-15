---
title: NE1xxx — Physics Layer Errors
description: Errors from the Physics layer — Iceberg, Parquet, Arrow, S3, network IO.
---

# NE1xxx — Physics Layer Errors

These errors originate in the storage, table format, and network IO layer (architecture v4.1 §4).

---

## NE1001 — NucleusSourceConnectionError {#ne1001}

**Class:** `NucleusSourceConnectionError`

Cannot reach an external data source.

**Triggers:**
- Postgres/MySQL/SQLite is not running or not reachable
- Wrong host, port, or credentials
- Firewall or proxy blocking the connection

**Fix:**
```bash
# Test connectivity first
psql postgres://user:pass@host:5432/db -c "SELECT 1"
# Or for MySQL:
mysql -u user -p -h host -P 3306 db

# Then retry
nucleus ingest postgres://... --table orders --as raw.orders
```

---

## NE1002 — NucleusCommitConflictError {#ne1002}

**Class:** `NucleusCommitConflictError`

Two materializations of the same asset tried to commit simultaneously.

**Triggers:**
- Two `nucleus run` processes running concurrently against the same asset
- `TransactionException` from DuckDB during Iceberg write
- `CommitFailedException` from pyiceberg

**Fix:**
Wait for any running process to complete, then retry:

```bash
nucleus run analytics.daily_revenue
```

If the conflict persists, check for stale lock files in `data/warehouse/<asset>/metadata/`.

---

## NE1003 — NucleusCommitUnknownError {#ne1003}

**Class:** `NucleusCommitUnknownError`

A commit was sent but its outcome is unknown (network interrupted mid-commit).

**Fix:** Inspect the Iceberg snapshot list to determine whether the commit landed:

```python
from pyiceberg.catalog import load_catalog
catalog = load_catalog("default", **{"type": "sql", "uri": "sqlite:///data/catalog.db", "warehouse": "data/warehouse"})
table = catalog.load_table("raw.orders")
for snap in table.history():
    print(snap.snapshot_id, snap.timestamp_ms)
```

If the latest snapshot is more recent than the error, the commit succeeded.

---

## NE1004 — NucleusSchemaEvolutionError {#ne1004}

**Class:** `NucleusSchemaEvolutionError`

A schema change violates Iceberg's evolution rules.

**Triggers:**
- Attempting to narrow a column type (int64 → int32)
- Making a nullable column required
- Removing a column that still exists in a snapshot

**Fix:** See [Schema Evolution cookbook](../cookbook/schema-evolution.md).

---

## NE1005 — NucleusIOError {#ne1005}

**Class:** `NucleusIOError`

A filesystem or object-store read/write failed.

**Triggers:**
- File not found at the expected path
- Disk full
- Permission denied on `data/warehouse/`
- SeaweedFS/MinIO container not running

**Fix:**
```bash
# Check disk space
df -h data/

# Check container is running
docker ps | grep seaweedfs

# Verify warehouse directory is writable
ls -la data/warehouse/
```

---

## NE1006 — NucleusPermissionError {#ne1006}

**Class:** `NucleusPermissionError`

OS or storage permission denied.

**Triggers:**
- Database user lacks SELECT on source table
- Object store credentials lack write permission
- OS file permission denied on `data/warehouse/`

**Fix:**
```sql
-- Postgres: grant SELECT
GRANT SELECT ON public.orders TO nucleus_user;

-- Or create a dedicated read-only user
CREATE USER nucleus_reader WITH PASSWORD 'password';
GRANT CONNECT ON DATABASE mydb TO nucleus_reader;
GRANT USAGE ON SCHEMA public TO nucleus_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nucleus_reader;
```
