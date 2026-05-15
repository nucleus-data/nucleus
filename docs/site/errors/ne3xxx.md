---
title: NE3xxx — Coordination Layer Errors
description: Errors from the Coordination layer — asset graph, orchestration, contracts, lineage.
---

# NE3xxx — Coordination Layer Errors

Errors from the coordination layer — asset graph management, orchestration substrate, contracts, and lineage (architecture v4.1 §6).

---

## NE3001 — NucleusInternalError {#ne3001}

**Class:** `NucleusInternalError`

An unhandled exception in your asset body or the coordination layer.

This is the catch-all error class. It means something unexpected happened that Nucleus didn't specifically handle.

**What to do:**
1. Read the `fix_hint` — it usually points to the likely cause
2. Check your Python asset function body for unhandled exceptions
3. Run with `--format json` to get the structured error including `cause`
4. If it looks like a Nucleus bug: [file an issue](https://github.com/nucleus-data/nucleus/issues) with the NE3001 message and your asset code

```bash
# Get structured error output
nucleus run my.asset --format json 2>&1 | jq .
```

---

## NE3002 — NucleusAssetNotFound {#ne3002}

**Class:** `NucleusAssetNotFound`

An asset key referenced in `{{ ref('...') }}` or `ctx.read('...')` is not registered.

**Fix:**
```bash
# List all registered assets
nucleus schedule list   # shows assets with schedules
nucleus query "SHOW TABLES"  # shows materialized tables

# Check your asset is discovered correctly
# Assets must be Python files with @nucleus.asset in the assets/ directory
ls assets/
```

---

## NE3003 — NucleusAssetNotMaterialized {#ne3003}

**Class:** `NucleusAssetNotMaterialized`

An asset is defined but has never been materialized (no Iceberg snapshot exists yet).

**Fix:**
```bash
# Run the missing asset first
nucleus run raw.orders
# Then run the downstream asset
nucleus run analytics.daily_revenue

# Or run the full graph
nucleus run --all
```

---

## NE3004 — NucleusInvalidAssetDefinition {#ne3004}

**Class:** `NucleusInvalidAssetDefinition`

An asset or project definition is invalid — wrong decorator arguments, missing required fields, or invalid cron expression.

**Fix:**
Check the error message for the specific field. Common causes:
- `table=` not in `namespace.name` format
- Invalid project name (no spaces, start with letter)

---

## NE3005 — NucleusTimeoutError {#ne3005}

**Class:** `NucleusTimeoutError`

An operation timed out — typically an AI Copilot call or a slow source query.

**Fix:** Retry. If the source query is slow, add filters or indexes to the source table.
