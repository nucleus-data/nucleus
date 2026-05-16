# ADR-031: Iceberg v3 Format Migration Helper

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P1  
**Target phase**: v0.3  
**Source research**: `docs/internal/research/inspiration/iceberg_catalog_deep_dive.md` §2; `docs/internal/research/inspiration/storage_formats_2026.md` §2  
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #8, §2.4

---

## Context

Apache Iceberg v3 was ratified in June 2025. Three v3 features are materially relevant to Nucleus assets:

1. **Deletion Vectors (DVs)**: Roaring Bitmap blobs replacing v2 positional delete files. Databricks reports 10× faster UPDATE/DELETE/MERGE with DVs enabled (per R8 §2 AWS blog). DuckDB reads + writes DVs (Feb–Mar 2026, PRs #327/#728 in duckdb-iceberg). Trino GA'd March 2025. PyIceberg 0.11.1 reads DVs.

2. **`variant` type**: Semi-structured JSON columns without `STRING+JSON` hacks. DuckDB Iceberg extension: Variant column read+write merged March 2026 (PR #474). Useful for `ctx.copy_from` pipelines ingesting `json`/`jsonb` Postgres columns.

3. **Row Lineage** (`_row_id`, `_last_update`): Always-on in v3. Complements Nucleus's asset-level OpenLineage for GDPR audit use cases.

**CRITICAL GATE**: PyIceberg DV write support is gated on PR #2822 merge confirmation (R8 NV-2). Do NOT enable format-version=3 writes until this is confirmed at https://github.com/apache/iceberg-python/blob/main/CHANGES.md.

**One-way door**: Tables migrated to format-version=3 cannot be downgraded to v2. This is a breaking change for any reader without v3 support.

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Two-phase: docs first, opt-in writes after gate** | Phase 1 (v0.3): document v3 readability; add `nucleus migrate-format --table <asset> --version 3` as explicit opt-in CLI command. Phase 2: unlock DV writes once pyiceberg NV-2 confirmed. | ✅ SELECTED — safe; user opt-in per table; correct one-way-door framing |
| B — Silent auto-migration to v3 | Upgrade all tables automatically on `nucleus up` | ❌ REJECTED — one-way door; would break v2-only readers; violates beachhead compatibility guarantee |
| C — Defer v3 to v0.5 entirely | No v3 support until v0.5 | ❌ REJECTED — v3 READ is already free (PyIceberg 0.11.1); delay only the write helper |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A** two-phase implementation.

Phase 1 (v0.3, ~80 LOC):
- Document v3 read capability in Wave 2 migration guide
- `nucleus migrate-format --table <asset> --version 3 --dry-run` shows what would change
- Gate: confirm pyiceberg DV write support (NV-2) before enabling non-dry-run mode
- Clear warning in CLI: "This is a one-way migration. Readers without v3 support will silently miss deleted rows."

Phase 2 (post NV-2 confirmation): Enable actual DV writes; update format-version in table metadata.

---

## Consequences

- **LOC budget impact**: ~80 LOC Phase 1 (CLI + dry-run check); ~120 LOC Phase 2 (actual migration)
- **No new runtime dependencies** (pyiceberg and duckdb already pinned)
- **Breaking if misused**: Format version upgrade is irreversible per Iceberg spec
- **Depends on**: Lakekeeper ADR (v0.3 catalog) for server-side DV support; NV-2 confirmation
- **NEEDS VERIFICATION**: R8 NV-2 (PyIceberg PR #2822 merge status); R8 NV-1 (DuckDB `_row_id` column exposure)

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §4 (Tier 0 — Iceberg as immortal table format)
- `nucleus_architecture_v4.1.md` §5.5 (catalog handles atomic commits)
