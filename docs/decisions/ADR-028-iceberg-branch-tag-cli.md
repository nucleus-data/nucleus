# ADR-028: Iceberg Branch + Tag CLI Verbs

**Status**: ACCEPTED
**Date**: 2026-05-15
**Author**: Synthesis — ratification required from founder
**Priority**: P1
**Target phase**: v0.2
**Source research**: `docs/research/inspiration/iceberg_catalog_deep_dive.md` §3
**Synthesis reference**: `docs/research/inspiration/ADOPTION_SHORTLIST.md` §3 #4

---

## Context

Teams on Nucleus v0.2 need snapshot isolation for pre-commit validation (the write-audit-publish / WAP pattern) and immutable compliance archiving (EOW/EOM snapshots). Both use cases rely on Iceberg's branch and tag primitives, exposed via `table.manage_snapshots()` in PyIceberg 0.11.1.

PyIceberg API confirmed at https://py.iceberg.apache.org/api/#snapshot-management:
- `table.manage_snapshots().create_tag(snapshot_id, tag_name, max_ref_age_ms).commit()`
- `table.manage_snapshots().create_branch(snapshot_id, branch_name, ...).commit()`
- `table.manage_snapshots().remove_tag(tag_name).commit()`
- `table.manage_snapshots().remove_branch(branch_name).commit()`

**Critical limitation** (per R1 §3.3): `table.append(branch="audit-branch")` is NOT yet supported in PyIceberg 0.11.1. Branch-targeted writes require Spark or Flink today. Track: https://github.com/apache/iceberg-python/issues/737. Full WAP workflow deferred to v0.3 when Lakekeeper provides consistent server-side branch isolation.

CLI surface for v0.2:
- `nucleus tag create <asset> <name> [--max-age-days N]`
- `nucleus tag remove <asset> <name>`
- `nucleus tag list <asset>`
- `nucleus branch create <asset> <name> [--max-age-days N]`
- `nucleus branch remove <asset> <name>`
- `nucleus branch list <asset>`

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — CLI verbs v0.2, WAP docs v0.3** | Expose tag/branch create/list/remove at v0.2; document WAP pattern at v0.3 when Lakekeeper is available | ✅ SELECTED — 50 LOC; concrete value even without full WAP |
| B — Full WAP at v0.2 | Include branch-targeted writes | ❌ REJECTED — `table.append(branch=...)` not supported in PyIceberg 0.11.1 |
| C — Defer to v0.3 entirely | No branch/tag until Lakekeeper | ❌ REJECTED — tag commands (compliance archiving) are useful today without Lakekeeper |

---

## Decision

Ratified 2026-05-15: implemented in commit a41a82c (v0.2.0 workstreams bundle).

**Option A implemented.** CLI commands shipped under `nucleus snapshot` subgroup:
- `nucleus snapshot branch create/delete <asset> <name> [options]`
- `nucleus snapshot tag create/delete <asset> <name> [options]`
- `nucleus snapshot list <asset>` (branches + tags in text or JSON)

PyIceberg API verified: `table.manage_snapshots().create_branch/create_tag/remove_branch/remove_tag(...).commit()`. Confirmed in pyiceberg==0.11.1.
New error codes: `NucleusSnapshotNotFoundError` (NE5015), `NucleusBranchAlreadyExistsError` (NE5016).
10 tests in `tests/cli/commands/test_snapshot.py`.

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A**. The CLI must include a prominent help-text note: *"Note: write-audit-publish (branch-targeted writes) requires Lakekeeper catalog — available at v0.3. This command creates/manages snapshot references only."*

---

## Consequences

- **LOC budget impact**: ~50 LOC CLI + ~30 LOC tests
- **No new runtime dependencies** (pyiceberg 0.11.1 already pinned)
- **Maintenance ownership**: Coordination layer (AMA branch support) + CLI (Experience layer)
- **Swap target**: Branch/tag API is part of the Iceberg REST spec — works with any compliant catalog
- **NEEDS VERIFICATION before code**: Confirm `table.append(branch=...)` status at https://github.com/apache/iceberg-python/issues/737

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §6.3 (coordination layer)
- `nucleus_architecture_v4.1.md` §13 (CLI surface)
