# ADR-032: sqlglot 26→30 Upgrade for Column Lineage

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P1  
**Target phase**: Gate before v0.5 column lineage work  
**Source research**: `docs/internal/research/inspiration/observability_lineage_2026.md` §3; `docs/internal/research/inspiration/ai_data_tooling_2026.md` §3.2  
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #11, §2.5

---

## Context

Nucleus currently pins `sqlglot==26.0.0`. The current stable release is `sqlglot==30.7.0` (verified 2026-05-04). This is a 4-major-version gap.

The v0.5 column-level lineage implementation requires `sqlglot.lineage()`:
```python
from sqlglot.lineage import lineage
nodes = lineage(column=None, sql=rendered_sql, schema=schema_dict, dialect="duckdb")
```
This API is stable per R4 §3.1, but the 4-major-version gap requires an upgrade ADR per AGENTS.md §11.13.

**Known breaking issue**: `UNION BY NAME` / `UNION ALL BY NAME` fail with `list index out of range` in older versions. A fix was merged in a recent 30.x version. Gate-test this pattern before enabling column lineage (R4 NV #5: confirm fix version at https://github.com/tobymao/sqlglot/issues/7332).

Additionally, the PoC #2 SQL resolver promotion notes confirm that `sqlglot` was moved to `[project.optional-dependencies] lineage-advanced` in the v0.1 speculative-pin cleanup (per FOUNDER_ACTION_QUEUE.md B2.8 α-split). This upgrade ADR should also confirm the correct `pyproject.toml` location (mandatory runtime dep for v0.5, not optional).

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Single-component upgrade ADR per AGENTS.md §11.13** | Read sqlglot changelog 26.x → 30.x; run upgrade smoke tests; move to mandatory deps at v0.5 | ✅ SELECTED — required by AGENTS.md §11.13 for major version upgrades |
| B — Bulk upgrade with other deps | Upgrade sqlglot alongside other dependencies | ❌ REJECTED — AGENTS.md §11.13 explicitly prohibits bulk upgrades |
| C — Stay on 26.0.0 | Do not upgrade | ❌ REJECTED — 26.0.0 blocks column lineage; API may have diverged from 30.x |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A**. Implementation steps:
1. Read sqlglot CHANGELOG from 26.0.0 → 30.7.0 (every minor release)
2. Identify behavioral changes in `lineage()` API and `parse_one()` behavior
3. Upgrade pin: `sqlglot==26.0.0` → `sqlglot==30.7.0` (exact pin per AGENTS.md §11.13)
4. Gate-test `UNION BY NAME` regression (R4 NV #5)
5. Move `sqlglot` from `[project.optional-dependencies] lineage-advanced` → `[project.dependencies]` when v0.5 column lineage goes active
6. Document rollback: `pip install sqlglot==26.0.0`
7. PR description must include: changelog summary, behavioral changes, rollback command

**Must complete BEFORE any v0.5 column lineage implementation starts.**

---

## Consequences

- **LOC budget impact**: 0 LOC on `src/nucleus/` (pin change only + tests)
- **Runtime impact**: `sqlglot` moves to mandatory deps at v0.5 activation
- **Rollback command**: `pip install sqlglot==26.0.0`
- **NEEDS VERIFICATION**: sqlglot changelog 26→30 (https://github.com/tobymao/sqlglot/tags); NV #5 (UNION BY NAME fix version)

## Architecture Sections Touched

- `AGENTS.md §11.13` (upgrade safety discipline — major version requires ADR)
- `docs/specs/nucleus_architecture_v4.1.md` §6.4 (lineage layer at v0.5+)
