# NE1005 — NucleusIOError

**Code**: `NE1005`  ·  **Class**: `NucleusIOError`  ·  **Layer**: L0 Physics  ·  **Stability**: Stable

## What happened

A read or write against the local filesystem or object storage failed. The path Nucleus tried to touch was not reachable, did not exist, or returned an IO error from the OS / object store.

## Likely causes

- The path does not exist (typo, wrong working directory, file moved).
- A glob pattern matched zero files where at least one was expected.
- The mounted volume / network share is offline.
- Object-store credentials are present but the bucket / prefix is wrong.

## Fix steps

1. Verify the path or glob in your source config / asset definition resolves on disk (`ls <path>` or equivalent).
2. If the path lives in object storage, list the bucket directly to confirm the object is there.
3. Re-run the materialization once the path resolves.

## Related

- Source: `src/nucleus/errors.py` (`NucleusIOError`)
- Default fix hint: "Check the path exists and is reachable. For source files, verify any glob patterns and credentials."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
