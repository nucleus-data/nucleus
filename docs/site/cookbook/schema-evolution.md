---
title: Schema Evolution
description: Add columns, rename fields, and handle breaking schema changes safely in Iceberg.
---

# Schema Evolution

Iceberg supports safe schema evolution — adding columns and renaming fields without rewriting data. Nucleus surfaces this via the contract system.

## Adding a new column

Iceberg adds columns non-destructively. Existing snapshots remain readable; old rows have `NULL` for the new column.

**Step 1:** Add the column to your asset's return type:

```python
@nucleus.asset(table="staging.orders")
def staging_orders(ctx) -> pl.DataFrame:
    return (
        ctx.read("raw.orders")
        .with_columns([
            # New column: derive region from country
            pl.when(pl.col("country").is_in(["US", "CA", "MX"]))
              .then(pl.lit("AMER"))
              .otherwise(pl.lit("INTL"))
              .alias("region")
        ])
    )
```

**Step 2:** Update the contract:

```python
@nucleus.contract("staging.orders")
class StagingOrdersContract:
    schema = {
        "order_id": "int64",
        "amount": "float64",
        "region": "utf8",   # ← new column
    }
```

**Step 3:** Run the asset:

```bash
nucleus run staging.orders
```

Iceberg automatically handles the schema update.

## Renaming a column

```python
@nucleus.asset(table="staging.orders")
def staging_orders(ctx) -> pl.DataFrame:
    return ctx.read("raw.orders").rename({"order_amount": "amount"})
```

Update the contract to use the new name. Downstream assets that reference the old name via `{{ ref() }}` will need updating.

## Handling breaking changes

Some schema changes break Iceberg's evolution rules (e.g., changing a column's type from `int64` to `utf8`). These require explicit migration:

```python
@nucleus.asset(
    table="staging.orders_v2",  # new asset key
    deps=["raw.orders"],
)
def staging_orders_v2(ctx) -> pl.DataFrame:
    return (
        ctx.read("raw.orders")
        .with_columns(
            pl.col("legacy_amount_cents").cast(pl.Float64).truediv(100).alias("amount")
        )
    )
```

Use the new asset key downstream, then deprecate the old one.

## Schema evolution errors

| Scenario | Error | Fix |
|----------|-------|-----|
| New required column with no default | NE2001 / NE1004 | Make column nullable or provide a default |
| Type narrowing (float → int) | NE1004 | Cast explicitly in your function |
| Removing a column | NE1004 | Create a new asset version |

See [NE1004: Schema evolution error](../errors/ne1xxx.md).

## Iceberg evolution rules

Iceberg supports:
- ✅ Add column (nullable)
- ✅ Add column with default (Iceberg spec v3)
- ✅ Rename column
- ✅ Widen type (int32 → int64, float → double)
- ❌ Narrow type (int64 → int32)
- ❌ Change column to non-nullable
- ❌ Remove column from existing schema (soft-delete only)

Docs: https://iceberg.apache.org/docs/latest/evolution/
