# 14 — Debugging Guide

> **What you're doing**: Triaging a failing run, confusing error, or unexpected behavior in Nucleus.
> **Why it matters**: Nucleus wraps multiple layers (Dagster → DuckDB → pyiceberg → S3). A failure can originate at any layer. Knowing which layer is failing cuts debugging time from hours to minutes.
> **Time**: 5-30 minutes for most issues with this guide

---

## Reading a NucleusError Traceback

When an operation fails, Nucleus prints a structured error:

```
Error [NE1001]: Cannot connect to the database server.
Fix: Check the connection URI is correct and the server is running.
     Example: postgres://user:pass@localhost:5432/mydb
Docs: https://nucleus.dev/errors/source-connection

Run with --verbose to see the full error details.
```

**What each field means**:
- `[NE1001]`: The error code. Look up the band:
  - `NE1xxx`: Physics/Source — connection, auth, S3, Iceberg commit issues
  - `NE2xxx`: Engines — SQL syntax, OOM, DuckDB errors
  - `NE3xxx`: Coordination — asset not materialized, schema mismatch, AMA issues
  - `NE4xxx`: Intelligence — AI Copilot, missing API key
  - `NE5xxx`: Experience/CLI — environment, deferred features, CLI errors
- `user_message`: Plain English description of what went wrong.
- `fix_hint`: Concrete action to take. Try this first.
- `docs_url`: Online documentation for this error (may not exist yet for v0.1 codes).

**First action**: Try the `fix_hint`. 80% of errors are resolved this way.

---

## `--verbose` Flag

Almost every `nucleus` command supports `--verbose`:

```bash
nucleus run my_asset --verbose       # shows full traceback
nucleus ingest postgres://... --verbose  # shows connection debugging
nucleus query "SELECT 1" --verbose   # shows query plan
```

With `--verbose`, the original exception (the `cause`) is printed below the NucleusError. This is the actual error from Dagster, DuckDB, pyiceberg, etc.

---

## Log Files

Nucleus writes structured logs to `.nucleus/logs/`:

```
.nucleus/
  logs/
    nucleus.log            # main application log (structlog JSON)
    lineage/
      events.jsonl         # OpenLineage events from each run
```

Read the log:
```bash
# PowerShell
Get-Content .nucleus\logs\nucleus.log | ConvertFrom-Json | Format-Table

# Or tail-style:
Get-Content .nucleus\logs\nucleus.log -Wait
```

Increase log level:
```bash
NUCLEUS_LOG_LEVEL=DEBUG nucleus run my_asset
```

---

## DuckDB EXPLAIN

For slow or wrong SQL results:

```python
# In a Python session or test:
import duckdb
# Docs: https://duckdb.org/docs/guides/meta/explain

conn = duckdb.connect()
conn.execute("EXPLAIN SELECT * FROM iceberg_scan('s3://my-bucket/my_table')")
```

Or from CLI (after `nucleus up`):
```bash
nucleus query "EXPLAIN SELECT * FROM my_asset"
```

---

## Iceberg Snapshot Inspection

To inspect what's in an Iceberg table at a specific snapshot:

```python
from pyiceberg.catalog import load_catalog
# Docs: https://py.iceberg.apache.org/api/

catalog = load_catalog("default", **{
    "type": "sql",
    "uri": "sqlite:///.nucleus/catalog.db",
})

table = catalog.load_table("default.my_asset")
print(table.metadata)                    # table metadata
print(table.current_snapshot())          # current snapshot
print(list(table.snapshots()))           # all snapshots (history)

# Read the data at the current snapshot:
import pyarrow as pa
df = table.scan().to_arrow()
```

---

## MinIO / SeaweedFS Admin UI

After `nucleus up`:

```
MinIO Console: http://localhost:9001
  Username: minioadmin (default; check docker-compose.yml)
  Password: minioadmin (default; check docker-compose.yml)
```

From the MinIO console:
- Browse buckets: see what Iceberg files were written
- Check file sizes: verify data actually landed
- View metadata.json: inspect Iceberg manifest files

---

## Dagster Internals Access (Debug Mode)

In normal operation, Dagster is hidden. For deep debugging:

```bash
# Enable Dagster debug logging:
NUCLEUS_DEBUG_DAGSTER=1 nucleus run my_asset --verbose
```

This sets Dagster's internal log level to DEBUG and prints Dagster-level events (not normally visible). Use this only when the NucleusError message is insufficient.

**Warning**: Debug output will contain Dagster classnames — this is expected in debug mode. Do NOT ship code with `NUCLEUS_DEBUG_DAGSTER=1` hardcoded.

---

## Common Error Scenarios and Fixes

### NE1001 — Cannot connect to database

```
Error [NE1001]: Cannot connect to the database server.
```

**Diagnose**:
```bash
# Is the database reachable?
nc -zv <host> <port>   # (Linux/Mac)
Test-NetConnection -ComputerName <host> -Port <port>  # (Windows PowerShell)

# Does the URI parse correctly?
nucleus ingest postgres://user:pass@host:5432/db --dry-run --verbose
```

**Common fixes**:
- Check URI format: `postgres://user:pass@host:5432/dbname`
- Start `nucleus up` if using local stack
- Check VPN or firewall if connecting to remote database

---

### NE2001 — SQL syntax error

```
Error [NE2001]: SQL syntax error in query.
Fix: Check the SQL syntax in your ctx.sql() call.
```

**Diagnose**:
```bash
nucleus query "YOUR SQL HERE" --verbose  # see the actual DuckDB error
```

**Common fixes**:
- Check `{{ ref('asset_name') }}` references: does the asset exist? Is it materialized?
- Check DuckDB-specific syntax (e.g., `COLUMNS(*)` is DuckDB 1.x only)

---

### NE3001 — Asset not materialized

```
Error [NE3001]: Asset 'upstream_asset' has not been materialized yet.
Fix: Run 'nucleus run upstream_asset' first.
```

**Diagnose**:
```bash
nucleus run upstream_asset  # materialize the dependency first
```

---

### NE1002 — Commit conflict

```
Error [NE1002]: A concurrent write conflict was detected.
Fix: Another process may be writing to the same asset. Wait and retry.
```

**Diagnose**:
```bash
# Check for stale lock files (if using filesystem advisory lock):
ls .nucleus/locks/
```

**Fix**: Kill any stale `nucleus run` processes. Delete the lock file if the process is definitely dead. Retry.

---

### NE5001 — Environment error

```
Error [NE5001]: Nucleus environment is not properly configured.
```

**Diagnose**:
```bash
nucleus --version  # verify installed
cat nucleus_project.yaml  # verify project config exists
nucleus up  # start the local stack
```

---

## Profiling Cold Boot

If `nucleus up` or `nucleus run` is slow:

```bash
# Time cold boot:
time nucleus --version   # quick smoke

# Import time audit:
python -X importtime -c "import nucleus" 2>&1 | head -20

# Profile a specific command:
python -m cProfile -s cumulative -m nucleus.cli.main run my_asset > profile.txt
```

See `docs/dev-guides/15-performance-profiling.md` for full profiling guide.

---

## Testing Environment Issues

**"Works in my environment, fails in CI"**:
1. Check Python version: `python --version` (must be 3.11 or 3.12).
2. Check if Docker is running: `docker ps`.
3. Check if `.venv` is activated: `which python` must point to `.venv/`.
4. Clean install: `rm -rf .venv && python -m venv .venv && pip install -e ".[dev]"`.

---

## References

- NE-code reference: `src/nucleus/errors.py` (each error code documented there)
- `docs/errors/` — user-facing error docs (one file per error slug)
- DuckDB docs: https://duckdb.org/docs/ (pinned version: 1.1.3)
- pyiceberg docs: https://py.iceberg.apache.org/ (pinned version: 0.11.1)
- MinIO docs: https://min.io/docs/minio/linux/reference/minio-mc.html
