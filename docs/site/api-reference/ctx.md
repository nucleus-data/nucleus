---
title: ctx SDK
description: Auto-generated API reference for nucleus.ctx — the core context module.
---

# `nucleus.ctx` — Context SDK

The `ctx` module is the primary API surface for Nucleus. Every asset function receives a `ctx` object; these are the functions available on it.

::: nucleus.ctx
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      filters:
        - "!^_"

---

## Key functions

### `ctx.read()`

Read a materialized asset into a Polars LazyFrame:

```python
df = ctx.read("sales.orders")           # returns pl.LazyFrame
df_eager = ctx.read("sales.orders").collect()  # eager Polars DataFrame
```

### `ctx.copy_from()`

Ingest an external source:

```python
rows = ctx.copy_from(
    "postgres://user:pass@host/db",
    table="public.orders",
    target="raw.orders",
    mode="overwrite",
)
```

### `ctx.sql()`

Run DuckDB SQL with Jinja `{{ ref() }}` resolution:

```python
result = ctx.sql("SELECT * FROM {{ ref('raw.orders') }} LIMIT 10")
df = result.pl()   # convert to Polars DataFrame
```

### `ctx.write()`

Explicitly write a DataFrame to an asset (bypassing the return value):

```python
ctx.write("analytics.summary", df, mode="overwrite")
```

### `ctx.param()`

Read a runtime parameter passed via `nucleus run --param KEY=VAL`:

```python
start_date = ctx.param("start_date", default="2024-01-01")
```
