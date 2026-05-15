---
title: SDK Decorators
description: Auto-generated API reference for nucleus.sdk — decorators and types.
---

# `nucleus.sdk` — Decorators and Types

The `nucleus.sdk` module provides the decorators that define assets, checks, and contracts.

::: nucleus.sdk
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      filters:
        - "!^_"

---

## Decorator summary

| Decorator | Use |
|-----------|-----|
| `@nucleus.asset` | Define a Python asset that returns a DataFrame |
| `@nucleus.sql_asset` | Define a SQL asset that returns a SQL string |
| `@nucleus.source` | Declare an external data source |
| `@nucleus.check` | Define a quality assertion for an asset |
| `@nucleus.contract` | Declare a declarative schema contract |

## Type helpers

| Type | Use |
|------|-----|
| `nucleus.freshness(hours=N)` | Declare an SLA freshness target |
| `nucleus.retries(count=N, delay="exponential")` | Configure retry policy |
| `nucleus.daily(start_date)` | Declare daily partitioning |
| `nucleus.identity(column)` | Declare identity (value-based) partitioning |
| `nucleus.CheckResult` | Return type for `@nucleus.check` functions |
