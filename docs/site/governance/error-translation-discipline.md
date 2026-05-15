---
title: Error Translation Discipline
description: How Nucleus translates external exceptions to NucleusError — no internal class names in user messages.
---

# Error Translation Discipline

Per [architecture v4.1 §6.4](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md):

> Every code path that catches an external exception must translate it to a `NucleusError` subclass. The original exception is preserved as `error.cause`. User-facing strings must not contain external class names.

## The rule

**Forbidden in any user-facing error message:**
- `dagster.`
- `duckdb.`
- `polars.`
- `pyiceberg.`
- `OpExecutionContext`
- `DagsterInstance`
- `DuckDBPyConnection`
- Any SQLAlchemy or psycopg3 class names

**Required:**
- `NucleusError.user_message` — plain English, no internal types
- `NucleusError.fix_hint` — a concrete action
- `NucleusError.docs_url` — a link to the error docs
- `NucleusError.cause` — the original exception (available for `debug=True` output)

## Why this matters

When a Dagster scheduler error leaks to the user:

```
❌ Bad: DagsterRunFailedError: OpExecutionContext.log_event failed: ...
```

The user sees a framework they didn't choose and couldn't be expected to understand.

With error translation:

```
✓ Good:
  Error: Asset 'raw.orders' failed during coordination.
  Fix:   Check the Python code in assets/raw/orders.py for exceptions.
  Docs:  https://nucleus.dev/errors/ne3xxx/#ne3001
         [NE3001]
```

## Implementation pattern

```python
try:
    result = dagster.materialize(...)
except dagster.DagsterRunFailedError as e:
    raise NucleusInternalError(
        user_message=f"Asset '{asset_key}' failed during coordination.",
        fix_hint="Check the Python code in your asset function for exceptions.",
        asset=asset_key,
    ) from e
```

The original `DagsterRunFailedError` is preserved in `error.__cause__` for debug inspection but never appears in the rendered output.

## CI enforcement

`scripts/dagster_leak_check.py` scans all `src/nucleus/` Python files for forbidden class names in string literals. It runs on every CI build and is a hard release blocker.

```bash
python scripts/dagster_leak_check.py
```

A failing check blocks the PR — no exceptions.
