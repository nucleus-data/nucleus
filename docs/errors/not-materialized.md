# NE3003 — NucleusAssetNotMaterialized

**Code**: `NE3003`  ·  **Class**: `NucleusAssetNotMaterialized`  ·  **Layer**: L2 Coordination  ·  **Stability**: Stable

## What happened

An asset is *defined* (decorated with `@nucleus.asset`) but has never been *materialized* — that is, never computed and stored in the catalog. A downstream materialization or `ctx.read(...)` tried to consume it and found no snapshot.

Distinct from `NE3002` (`NucleusAssetNotFound`): `NE3003` means the asset graph knows about this name, but the asset has not been run yet.

Layer note: the catalog-miss is raised at L0 Physics, but the user-facing concern is asset-graph state at L2 Coordination ([ADR-006 §Decision](../decisions/ADR-006-nucleus-error-code-numbering.md) — semantic-over-source classification).

## Likely causes

- The upstream asset has never been run yet.
- The upstream was materialized into a different catalog or warehouse than the current run reads from.
- A prior run failed silently and never produced a snapshot.

## Fix steps

1. Materialize the upstream asset: `nucleus run <upstream-asset>`.
2. If you expected it to already exist, confirm your catalog / warehouse config points at the same location as the run that produced it.
3. Re-run the downstream materialization.

## Related

- Source: `src/nucleus/errors.py` (`NucleusAssetNotMaterialized`)
- Default fix hint: "Run the upstream asset first: `nucleus run <asset>`. If you expect it to exist, check the catalog config."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
