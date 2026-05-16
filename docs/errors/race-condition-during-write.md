# NE5018 — RaceConditionDuringWrite

> **Class**: `nucleus.errors.NucleusRaceConditionDuringWrite`
> **Layer (ADR-006 §1)**: L4 Experience
> **Stability**: Beta
> **Introduced**: v0.2.0
> **Related ADRs**: [ADR-006 §Decision](../decisions/ADR-006-nucleus-error-code-numbering.md), [ADR-024 P0-2](../decisions/ADR-024-reliability-hardening-plan.md)
> **Closes chaos finding**: [CF-1 / J3](../internal/release-process/chaos_test_results.md)

## What this error means

A materialization write attempted to create the warehouse / catalog
directory and discovered a **non-directory entry already exists at the
same path**. Per the [Python pathlib docs](https://docs.python.org/3/library/pathlib.html#pathlib.Path.mkdir),
`Path.mkdir(parents=True, exist_ok=True)` only silently succeeds when
the existing entry is itself a directory — if it is a file (or symlink
to a non-directory), `FileExistsError` is raised. Nucleus translates
that to `NE5018` so the user sees a typed, NE-coded message instead of
a raw Python traceback.

## Typical triggers

1. **Operator action**: someone ran `rm -rf <warehouse>` and then
   `touch <warehouse>` (or a backup tool restored a file at the
   directory path).
2. **Hostile-storage mock**: the chaos suite J3 scenario corrupts the
   warehouse path on purpose to verify the translate() boundary holds.
3. **True race**: an unrelated process raced ahead of the AMA between
   its existence check and its `mkdir` syscall and wrote a file at the
   target path. The AMA's advisory filesystem lock
   (`nucleus.coordination.locks` per ADR-024 P0-2) serializes
   *Nucleus* writers, but does not block external processes.

## How to fix

1. **Inspect the path** in the user-facing message: it is the warehouse
   root the AMA tried to create. If it exists as a file, remove or
   rename it.
2. **Restore the directory** (or let Nucleus re-create it): `rm <path>`
   then re-run the materialization.
3. **If another Nucleus process is racing**: just retry — the advisory
   lock will serialize the second writer.
4. **If a backup tool is responsible**: exclude the Nucleus warehouse
   path from the tool's restore policy.

## Source mapping

| Source                    | Path                                                                | Handler                          |
|---------------------------|---------------------------------------------------------------------|----------------------------------|
| `builtins.FileExistsError`| `coordination/asset_materialization.py:_commit_to_iceberg` (mkdir) | `_file_exists_handler` (NE5018) |

The handler lives in
[`src/nucleus/coordination/error_translation.py`](../../src/nucleus/coordination/error_translation.py)
under `_file_exists_handler`. The mkdir boundary lives in
[`src/nucleus/coordination/asset_materialization.py`](../../src/nucleus/coordination/asset_materialization.py)
just before the DuckDB connection setup.

## Related codes

- [NE3008 — ConcurrentRun](concurrent-run.md): a *second Nucleus run*
  hit the advisory lock first (the wait branch); not the same as
  NE5018.
- [NE1005 — IOError](io.md): generic read/write failure on the local
  FS / object store.
- [NE1006 — PermissionError](permission.md): the path is a directory
  but writes are denied.

## Background

This code was allocated by the v0.2 close-out checklist
(`docs/internal/release-process/v0.2_FOUNDER_CLOSE_CHECKLIST.md` §1.7 — pre-sprint
blocker #6) to close the chaos J3 / CF-1 translate() gap. Prior to
v0.2.0 the same condition leaked a raw `FileExistsError` traceback
through the CLI, violating `docs/specs/nucleus_architecture_v4.1.md` §6.4 +
`AGENTS.md` §11.7. The `dagster_leak_check.py` governance script did
not catch the leak because it targets Dagster classnames only; the
v0.2.1 governance hardening item is to extend it to flag any stdlib
`*Error` classname in user-facing strings.
