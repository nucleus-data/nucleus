# NE1003 — NucleusCommitUnknownError

**Code**: `NE1003`  ·  **Class**: `NucleusCommitUnknownError`  ·  **Layer**: L0 Physics  ·  **Stability**: Stable

## What happened

A materialization started a commit but lost contact with the catalog before confirmation arrived. The new snapshot may have landed, partially landed, or not landed at all. Nucleus cannot tell from here.

This is the one case where a blind retry is unsafe — retrying a commit that did land would double-write.

## Likely causes

- Network glitch during the catalog metadata pointer swap.
- Catalog backend (filesystem / REST / SQL) timed out mid-write.
- Process / machine killed while the commit was in flight.

## Fix steps

1. Do NOT retry blindly.
2. Run `nucleus catalog inspect <asset>` to read the asset's snapshot history.
3. If the snapshot you expected is present, mark the run successful and move on. If it is absent, re-run the materialization.

## Related

- Source: `src/nucleus/errors.py` (`NucleusCommitUnknownError`)
- Default fix hint: "Do NOT blindly retry. Inspect the asset's snapshot history (`nucleus catalog inspect`) first."
- Architecture: [v4.1 §6.4 Error Translation Layer](../specs/nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
