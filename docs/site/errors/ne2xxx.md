---
title: NE2xxx — Engine Layer Errors
description: Errors from the Engines layer — DuckDB, Polars; compute, parse, plan.
---

# NE2xxx — Engine Layer Errors

Errors from the compute and SQL engine layer (architecture v4.1 §5).

---

## NE2001 — NucleusSchemaError {#ne2001}

**Class:** `NucleusSchemaError`

Data didn't match the declared schema contract.

**Triggers:**
- A `@nucleus.contract` rule was violated (missing required column, wrong type, null in non-null column, value not in accepted_values)
- Source data changed schema without updating the contract

**Fix:**
1. Run `nucleus query --asset <key>` to inspect the actual data
2. Compare with your `@nucleus.contract` class
3. Either fix the source data or update the contract
4. Re-run `nucleus run <asset>`

---

## NE2002 — NucleusSQLSyntaxError {#ne2002}

**Class:** `NucleusSQLSyntaxError`

A SQL string failed to parse in DuckDB.

**Triggers:**
- Typo in a SQL keyword
- Invalid `{{ ref() }}` syntax
- DuckDB-specific SQL feature used incorrectly

**Fix:**
```bash
# Test the SQL in isolation
nucleus query "YOUR BROKEN SQL HERE"

# DuckDB SQL reference: https://duckdb.org/docs/sql/query_syntax/
```

---

## NE2003 — NucleusResourceError {#ne2003}

**Class:** `NucleusResourceError`

An engine resource limit was exceeded — typically memory.

**Triggers:**
- DuckDB ran out of memory processing a large query
- Polars LazyFrame materialization exceeded RAM
- Spill to disk failed (disk full)

**Fix:**
```bash
# Add LIMIT to your query
nucleus query "SELECT * FROM {{ ref('large_table') }} LIMIT 1000"

# Use DuckDB's SUMMARIZE for quick stats without reading all data
nucleus query "SUMMARIZE {{ ref('large_table') }}"

# Or configure DuckDB memory limit in nucleus_project.yaml:
# engines:
#   duckdb:
#     memory_limit: "4GB"
#     threads: 4
```
