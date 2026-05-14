# NE1006 — NucleusPermissionError

**Code**: `NE1006`  ·  **Class**: `NucleusPermissionError`  ·  **Layer**: L0 Physics  ·  **Stability**: Stable

## What happened

A filesystem or object-store operation was denied for permission reasons. The user / role running Nucleus could see the resource but could not perform the requested read or write.

## Likely causes

- The catalog / warehouse directory is not writable by the current OS user.
- An object-store bucket policy or IAM role denies write to the warehouse prefix.
- Cloud credentials are configured but scoped to a different bucket or prefix.
- A read-only mount (NFS, SMB, container volume).

## Fix steps

1. Confirm the catalog and warehouse paths are writable by the user running Nucleus.
2. For cloud object stores, check the IAM policy / bucket policy grants write on the warehouse prefix.
3. Re-run the materialization once permission is granted.

## Related

- Source: `src/nucleus/errors.py` (`NucleusPermissionError`)
- Default fix hint: "Check that the catalog / warehouse path is writable by the current user."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
