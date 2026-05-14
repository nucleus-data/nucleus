# NE3002 — NucleusAssetNotFound

**Code**: `NE3002`  ·  **Class**: `NucleusAssetNotFound`  ·  **Layer**: L2 Coordination  ·  **Stability**: Stable

## What happened

An asset name was referenced (in SQL, in `ctx.read`, or as a dependency) but the asset is not registered in your project. Nucleus searches the asset graph for the name and finds nothing — so it cannot plan the materialization.

Distinct from `NE3003` (`NucleusAssetNotMaterialized`): `NE3002` means the asset was never even *defined*; `NE3003` means it is defined but has never been computed.

Layer note: the underlying catalog miss is raised at L1 Engines, but the user-facing concern is asset-graph registration at L2 Coordination ([ADR-006 §Decision](../decisions/ADR-006-nucleus-error-code-numbering.md) — semantic-over-source classification).

## Likely causes

- Typo in the asset name in a SQL `FROM` clause or `ctx.read(...)`.
- The asset module is not imported anywhere reachable from the project's asset discovery root.
- The asset is decorated but in a namespace the project is not loading.

## Fix steps

1. Run `nucleus list` to print every registered asset name and confirm the exact spelling.
2. If the name is missing, check the asset definition has `@nucleus.asset` and its module is imported.
3. Re-run the materialization.

## Related

- Source: `src/nucleus/errors.py` (`NucleusAssetNotFound`)
- Default fix hint: "Verify the asset name is registered. List available assets with `nucleus list`."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
