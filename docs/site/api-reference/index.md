---
title: API Reference
description: Auto-generated Python API reference for nucleus.ctx, nucleus.sdk, and nucleus.errors.
---

# API Reference

Auto-generated from source docstrings via [mkdocstrings](https://mkdocstrings.github.io/).

| Module | Description |
|--------|-------------|
| [`nucleus.ctx`](ctx.md) | The context object — `copy_from`, `sql`, `read`, `write`, `param` |
| [`nucleus.sdk`](sdk.md) | Decorators — `@nucleus.asset`, `@nucleus.sql_asset`, `@nucleus.source`, `@nucleus.check`, `@nucleus.contract` |
| [`nucleus.errors`](errors.md) | Error types — all `NucleusError` subclasses with NE-codes |

## Design principle

Per [architecture v4.1 §13](../philosophy/wrap-not-build.md):

> `ctx` is the only thing users import. No `dagster`, no `iceberg`, no `duckdb`, no `dlt`, no `s3://`.

The `ctx` object is the stable API surface. Everything else (Dagster, pyiceberg, DuckDB) is an implementation detail hidden behind it.

## Stability tiers (ADR-005)

| Tier | Meaning |
|------|---------|
| **Frozen** | No changes after v1.0; breaking change requires v2.0 |
| **Stable** | No breaking changes without ADR |
| **Beta** | May change with `CHANGELOG.md` entry |
| **Internal** | Not part of public API; may change any time |

Each class and method is tagged with its stability tier in the docstring.
