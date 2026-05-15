---
title: Error Recovery
description: How to diagnose and recover from materialization failures.
---

# Error Recovery

## Understanding NE-codes

Every Nucleus error carries a structured NE-code. Read the message — it tells you what failed and how to fix it:

```
Error: Could not reach source 'postgres://prod-db/ecommerce'. Connection refused.
Fix:   Check the host/port and that the database is running. Verify credentials with a psql test.
Docs:  https://nucleus.dev/errors/ne1xxx/#ne1001
       [NE1001]
```

## Common recovery scenarios

### Source unreachable (NE1001)

```bash
# Test the connection first
psql postgres://user:pass@host:5432/db -c "SELECT 1"

# If the host is correct, check Docker networking
docker ps   # is the database container running?
docker network ls

# Retry after fixing the root cause
nucleus run raw.orders
```

### Commit conflict (NE1002)

Two materializations of the same asset ran concurrently:

```bash
# Check if another process is running
nucleus version   # harmless; verifies CLI is alive

# Wait for the other process to finish, then retry
nucleus run analytics.daily_revenue

# If the conflict persists, check for stale lock files
ls .nucleus/runs/
```

### Schema mismatch (NE2001)

The source schema changed:

```bash
# Inspect the current source schema
nucleus query --asset raw.orders | head -1   # shows column names

# Update your contract to match the new schema
# Edit your @nucleus.contract class, then:
nucleus run staging.orders
```

### Asset not materialized (NE3003)

A downstream asset needs an upstream that hasn't run yet:

```bash
# Run upstream assets first
nucleus run raw.orders staging.orders

# Or run the full graph
nucleus run --all
```

## Retries

Add retries for transient failures:

```python
@nucleus.asset(
    table="raw.api_data",
    retries=nucleus.retries(count=3, delay="exponential"),
)
def raw_api_data(ctx) -> pl.DataFrame:
    ...
```

## Dry run

Preview which assets would run without actually running them:

```bash
nucleus run --all --dry-run
```

```
[dry-run] Would materialize:
  raw.orders          (needs run — no snapshot)
  staging.orders      (needs run — deps changed)
  mart.daily_revenue  (up-to-date — skip)
```

## Debugging with Python

```python
import nucleus

# Get the last materialization result
result = nucleus.get_last_result("analytics.daily_revenue")
print(result.status, result.error_code, result.user_message)

# Read the most recent snapshot to inspect data quality
df = nucleus.ctx.read("analytics.daily_revenue")
print(df.describe())
```

## Related

- [Error index](../errors/index.md)
- [NE1xxx Physics errors](../errors/ne1xxx.md)
- [NE3xxx Coordination errors](../errors/ne3xxx.md)
