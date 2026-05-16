# NE1004 — NucleusSchemaEvolutionError

**Code**: `NE1004`  ·  **Class**: `NucleusSchemaEvolutionError`  ·  **Layer**: L0 Physics  ·  **Stability**: Stable

## What happened

A schema change on an existing asset was rejected by Iceberg's evolution rules. Iceberg only allows safe, backward-compatible schema changes on existing snapshots; the change you attempted would lose information or invalidate readers of older snapshots.

## Likely causes

- Narrowing a column type (e.g. `BIGINT` → `INT`).
- Changing a nullable column to non-nullable.
- Removing or renaming a partition key.
- Dropping a required column that older snapshots still carry.

## Fix steps

1. Widen rather than narrow: keep the column at its current type, or upcast it.
2. Keep already-nullable columns nullable; add new columns as nullable.
3. If you genuinely need a breaking change, materialize a new asset rather than evolving the existing one.

## Related

- Source: `src/nucleus/errors.py` (`NucleusSchemaEvolutionError`)
- Default fix hint: "Iceberg allows adding/widening fields; narrowing or nullable→required is not allowed. Review the contract."
- Architecture: [v4.1 §6.4 Error Translation Layer](../specs/nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
