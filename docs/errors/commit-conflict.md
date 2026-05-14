# NE1002 — NucleusCommitConflictError

**Code**: `NE1002`  ·  **Class**: `NucleusCommitConflictError`  ·  **Layer**: L0 Physics  ·  **Stability**: Stable

## What happened

Two materializations tried to write to the same asset concurrently. The catalog (or the SQL engine's connection-level transaction) rejected the second writer to preserve correctness — the second commit lost the race.

The Asset Materialization Adapter retries this case automatically up to 3 times. If this error reached you, retries were exhausted.

## Likely causes

- Two scheduled materializations target the same asset and overlap.
- Two engineers ran `nucleus run <asset>` simultaneously.
- A long-running materialization is still holding the asset open when a second one starts.

## Fix steps

1. Retry the run once manually.
2. If the conflict persists, identify which two writers target the asset (check schedules and any active runs).
3. Stagger schedules or fold the writers into a single materialization.

## Related

- Source: `src/nucleus/errors.py` (`NucleusCommitConflictError`)
- Default fix hint: "Another writer committed to the same asset. Retry the run; if it persists, check for overlapping schedules."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
