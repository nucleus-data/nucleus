---
title: Contract
description: A declarative data contract that enforces schema and quality rules on every materialization.
---

# Contract

A **contract** is a declarative definition of what an asset's data must look like — its schema, nullability constraints, uniqueness rules, and expected value ranges. Contracts run at step 1 of every materialization; a contract violation aborts the write.

## Defining a contract

```python
import nucleus


@nucleus.contract("sales.orders")
class OrdersContract:
    schema = {
        "order_id":   "int64",
        "customer_id": "int64",
        "order_date":  "date",
        "amount":      "float64",
        "status":      "utf8",
    }
    not_null = ["order_id", "order_date", "amount"]
    unique = ["order_id"]
    accepted_values = {
        "status": ["pending", "completed", "cancelled", "refunded"]
    }
```

## What contracts enforce

| Rule type | Declaration | Error if violated |
|-----------|-------------|-------------------|
| Schema | `schema = {...}` | NucleusSchemaError (NE2001) |
| Non-null | `not_null = [...]` | NucleusSchemaError (NE2001) |
| Uniqueness | `unique = [...]` | NucleusSchemaError (NE2001) |
| Accepted values | `accepted_values = {...}` | NucleusSchemaError (NE2001) |
| Row count threshold | `min_rows = N` | NucleusSchemaError (NE2001) |

## Schema evolution

Contracts enforce the declared schema. When your source schema changes, you must update the contract first (and handle any necessary migration). See [Schema Evolution](../cookbook/schema-evolution.md).

## Contracts vs. checks

| | Contract | Check |
|--|---------|-------|
| When | Before commit (step 1) | After commit |
| Style | Declarative (class) | Imperative (function) |
| On failure | Aborts materialization | Records failure; does not abort |
| Use for | Schema + structural rules | Business logic assertions |

Contracts are the "schema gate." Checks are the "business logic gate." Use both.

## Soda Core (v0.5+)

In v0.5+, contracts can be backed by [Soda Core](https://www.soda.io/soda-core) for richer rule types (distribution checks, freshness, anomaly detection). This requires `pip install nucleus-data[soda]`.

!!! note "v0.1"
    v0.1 contracts use the native `@nucleus.contract` decorator. Soda Core backing is deferred to v0.5+.
