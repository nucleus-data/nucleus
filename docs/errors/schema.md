# NE2001 — NucleusSchemaError

**Code**: `NE2001`  ·  **Class**: `NucleusSchemaError`  ·  **Layer**: L1 Engines  ·  **Stability**: Stable

## What happened

The data flowing through an asset did not match the schema the engine expected. The mismatch was caught at bind / plan / execute time, before the materialization could land.

This is the most common error during asset development — the asset's return value drifts from its declared schema, or a SQL transformation references a column the upstream asset no longer produces.

## Likely causes

- The asset's return value has an extra, missing, or renamed column.
- A column's type does not match the declared schema (e.g. string in an int column).
- A `NOT NULL` column received a null value.
- A SQL transform references a column that no longer exists on the upstream asset.

## Fix steps

1. Compare the asset's actual return value (or upstream schema) against the declared contract.
2. Fix the mismatch in the asset body, or update the declared schema if the change is intentional.
3. Re-run the materialization.

## Related

- Source: `src/nucleus/errors.py` (`NucleusSchemaError`)
- Default fix hint: "Verify column types and nullability in your asset's return value." (variants per source: column-name spelling, dtypes match declared schema.)
- Architecture: [v4.1 §6.4 Error Translation Layer](../specs/nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
