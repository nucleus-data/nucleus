# NE3001 — NucleusInternalError

**Code**: `NE3001`  ·  **Class**: `NucleusInternalError`  ·  **Layer**: L2 Coordination  ·  **Stability**: Stable

## What happened

The Error Translation Layer caught an underlying exception it did not have a specific translator for. Nucleus surfaced the original exception type and message and routed the error here as a catch-all. Seeing `NE3001` means either (a) the translator catalog needs a new handler for this case, or (b) a real internal invariant was violated.

This is the only error that explicitly asks you to file a bug.

## Likely causes

- An edge case in a wrapped engine or library that no translator covers yet.
- A genuine Nucleus invariant violation (assertion, unexpected state).
- A new release of a wrapped engine raised a renamed exception type.

## Fix steps

1. Re-run with `--debug` to get the full traceback and the original cause's class name.
2. File a bug report including the `--debug` output, the asset definition, and the wrapped-engine versions from `pyproject.toml`.
3. As a workaround, you can sometimes isolate the failing asset and run it directly to narrow down the trigger.

## Related

- Source: `src/nucleus/errors.py` (`NucleusInternalError`)
- Default fix hint: "If this is unexpected, please file a bug. Run with --debug to see the full traceback."
- Architecture: [v4.1 §6.4 Error Translation Layer](../specs/nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
