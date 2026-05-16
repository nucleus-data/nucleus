# Nucleus Cleanup Inventory — Pre-v0.2 Release

> **Status**: DRAFT — created by release-planner builder 2026-05-15  
> **Analyst**: Release-planner builder (read-only snapshot analysis)  
> **Note**: Foreground reconciles this against actual Wave-1 state BEFORE executing any action.  
> All file paths are relative to repo root (`c:\Users\GOT4HC\Mordern Data Platform`).  
> **Wave-1 dependency**: some actions must wait until Wave-1 builders (1A–1E) complete. See Execution Order §7.

---

## Summary

| Section | Action type | Est. file count | Risk |
|---|---|---|---|
| 1 – Safe deletions | `rm` | ~8–12 files | Low |
| 2 – Archive (git mv) | `git mv` | 5 files | Low |
| 3 – Consolidate duplicates | code edit | ~4 locations | Medium |
| 4 – Stale docs (rewrite or delete) | doc edit | ~6 docs | Low-Medium |
| 5 – Empty / placeholder files | `rm` | ~3 files | Low |
| 6 – Generated artifacts | `.gitignore` verify | ~8 patterns | Low |
| **Total estimated** | | **~30–35 files** | |

Estimated disk reclaimable: < 5 MB (the major cleanup was already done on 2026-05-14 — `.mypy_cache`, `__pycache__`, `coverage.xml` etc. reduced from 113.8 MiB to 8.7 MiB per `FOUNDER_ACTION_QUEUE.md` §0 "Repo housekeeping").

---

## Section 1: Safe Deletions (Zero References, Zero Risk)

### 1.1 `SESSION_STATE_2026-05-13.md` (root)

| Field | Value |
|---|---|
| **Path** | `SESSION_STATE_2026-05-13.md` |
| **Why delete** | Stale session snapshot from 2026-05-13 04:56 UTC+7; captured workers-in-flight at that moment. All referenced PoCs (#1–4) are now PROMOTED/VALIDATED; founder decision queue now lives in `docs/FOUNDER_ACTION_QUEUE.md`. Content is 100% superseded. |
| **Safety check** | `rg "SESSION_STATE" --type md` → zero cross-references expected; this doc is standalone |
| **FOUNDER_ACTION_QUEUE citation** | §0 "Repo housekeeping" explicitly recommends DELETE |
| **Action** | `Remove-Item .\SESSION_STATE_2026-05-13.md` |

### 1.2 `architecture_design_conversation.md` (root)

| Field | Value |
|---|---|
| **Path** | `architecture_design_conversation.md` |
| **Why delete** | Appears to be a planning conversation transcript used during architecture design. Superseded by the formal architecture docs (`docs/specs/nucleus_architecture_v4.1.md` + ADRs). Per `AGENTS.md` §2, v4.1 is the single source of truth. |
| **Safety check** | `rg "architecture_design_conversation"` → verify zero inbound links before deleting |
| **Action** | Delete if no inbound links, otherwise archive to `docs/archive/` |

### 1.3 `docs/security/threat_model_v0.md`

| Field | Value |
|---|---|
| **Path** | `docs/security/threat_model_v0.md` |
| **Why delete** | Explicitly superseded by `docs/security/threat_model_v1.md`. Version number in filename confirms this. |
| **Safety check** | `rg "threat_model_v0"` → should be zero or only historical references |
| **Action** | `git rm docs/security/threat_model_v0.md` (preserves history) |

### 1.4 `frontend/` directory (stale pre-workbench scaffold)

| Field | Value |
|---|---|
| **Path** | `frontend/` (contains at minimum `frontend/README.md`) |
| **Why delete** | Appears to be the pre-Workbench v0.2 scratch frontend directory. Wave-1A ships the real Workbench under `src/nucleus/workbench/frontend/`. The `frontend/README.md` is tracked in git status as an existing file. |
| **Safety check** | `rg --include="*.py" "frontend/" --type py` → confirm no Python imports reference this dir. Check if `Makefile` has `frontend/` targets. |
| **Wave-1 dependency** | Confirm Wave-1A shipped `src/nucleus/workbench/frontend/` first |
| **Action** | `git rm -r frontend/` if safe; OR preserve as archive if still referenced |

### 1.5 `docs/audits/README.md` + `docs/audits/positioning_drift_2026-05-12.md` + `docs/audits/positioning_drift_2026-05-13.md`

| Field | Value |
|---|---|
| **Path** | `docs/audits/` (3 files) |
| **Why review** | Positioning drift audit docs from 2026-05-12/13. ADR-002 locked positioning at those dates. These may be archivable. |
| **Safety check** | `rg "positioning_drift"` → confirm not actively referenced in any current doc |
| **Action** | Move to `docs/archive/audits/` if zero active references; safe to keep if uncertain |

---

## Section 2: Archive (Move, Preserve Git History)

Use `git mv` to preserve blame/log history. These files are intentionally kept per `AGENTS.md §2` (historical reference) but should not clutter the root.

### 2.1 `nucleus_architecture_v3.md` → `docs/archive/architecture-v3.md`

| Field | Value |
|---|---|
| **Current path** | `nucleus_architecture_v3.md` (root) |
| **Target path** | `docs/archive/architecture-v3.md` |
| **Why archive** | Explicitly deprecated. `docs/specs/nucleus_architecture_v4.1.md` supersedes. `AGENTS.md §2` says "Use only as historical reference." |
| **References to update** | `AGENTS.md §2` table row (update path); `docs/decisions/` ADRs that cite "v3" may have inline mentions |
| **Command** | `git mv nucleus_architecture_v3.md docs/archive/architecture-v3.md` |
| **Risk** | Low — but update `AGENTS.md §2` reading list path simultaneously |

### 2.2 `nucleus_architecture_v4.md` → `docs/archive/architecture-v4.md`

| Field | Value |
|---|---|
| **Current path** | `nucleus_architecture_v4.md` (root) |
| **Target path** | `docs/archive/architecture-v4.md` |
| **Why archive** | Explicitly deprecated. v4.1 supersedes. Same rationale as 2.1. |
| **References to update** | Same as 2.1; `AGENTS.md §2` row |
| **Command** | `git mv nucleus_architecture_v4.md docs/archive/architecture-v4.md` |
| **Risk** | Low — update `AGENTS.md §2` simultaneously |

### 2.3 PoC stubs already promoted — archive, don't delete

| Field | Value |
|---|---|
| **Paths** | `poc/p1_error_translation/`, `poc/p2_ctx_sql/`, `poc/p3_ingest/` (all PROMOTED) |
| **Why archive vs delete** | Per PoC lifecycle: PROMOTED PoCs are audit trail for promotion decisions; their `PROMOTION_PR_DRAFT.md` + `REVIEW_NOTES.md` are referenced in ADRs. Git history preserves them, but clearing from active workspace reduces noise. |
| **Safety check** | `rg "poc/p1_" --type py` → only `poc/p1_error_translation/test_translator.py` has `@pytest.mark.skip` mirror; no production code under `src/nucleus/` references these paths |
| **Proposed action** | `git mv poc/p1_error_translation docs/archive/poc/p1_error_translation` (repeat for p2, p3) |
| **Wave-1 dependency** | Wait until Wave-1E (audit) confirms all test references updated |
| **Note** | `poc/p4_boot_time/` (VALIDATED) and `poc/p5_beachhead/` (KIT_READY) should be KEPT at their current locations for active use |

---

## Section 3: Consolidate Duplicates

### 3.1 CLI ingest dispatch bypass

| Field | Value |
|---|---|
| **Duplicates** | `src/nucleus/cli/main.py` lines 1091 + 1113 (direct `ingest_sqlite_to_iceberg` / `ingest_postgres_to_iceberg` imports) vs `nucleus.ctx.copy_from()` unified dispatcher |
| **Root cause** | MEDIUM finding from verifier 2 (2026-05-14); CLI bypasses the public `ctx.copy_from()` entry point |
| **Risk** | MEDIUM — functional duplicate, not a correctness issue today, but diverges from SDK spec |
| **Keep** | `nucleus.ctx.copy_from()` (public SDK entry point) |
| **Action** | Builder wave needed; foreground verifier gate required; defer to v0.2.1 patch per FOUNDER_ACTION_QUEUE §"Verifier findings" item 1 |

### 3.2 Duplicate `quickstart.md` paths

| Field | Value |
|---|---|
| **Duplicates** | `docs/onboarding/quickstart.md` + `docs\onboarding\quickstart.md` (Windows path variants in git status); also `docs/site/getting-started/quickstart.md` (Wave-1C public docs) |
| **Root cause** | Windows git path normalization artifacts; `docs/onboarding/quickstart.md` is the contributor-facing doc; `docs/site/getting-started/quickstart.md` is the public user-facing doc |
| **Action** | Verify they are NOT the same file (Windows paths); if distinct content, keep both and add cross-reference note. If identical, delete contributor version and redirect |

### 3.3 Duplicate `compatibility.md` paths

| Field | Value |
|---|---|
| **Duplicates** | `docs/compatibility.md` + `docs\compatibility.md` (Windows/Unix path variants in git status) |
| **Root cause** | Same Windows path artifact; likely the same file |
| **Action** | `git status --porcelain` to verify; if same file, no action needed (git normalizes) |

### 3.4 Multiple `slugify` / `safe_str` utility helpers

| Field | Value |
|---|---|
| **Suspected duplicates** | Any string-sanitization helpers spread across `cli/main.py` and `sdk/` or `coordination/` |
| **Safety check** | `rg "def slugify\|def safe_str\|def sanitize"` to locate all instances |
| **Action** | If 2+ implementations found: consolidate into `src/nucleus/_internal/utils.py` (or closest canonical module); import from one location |

---

## Section 4: Stale Docs (Rewrite or Delete)

### 4.1 `docs/specs/nucleus_project_anatomy.md` — v3-era drift

| Field | Value |
|---|---|
| **Path** | `docs/specs/nucleus_project_anatomy.md` (root) |
| **Status** | v3-era; references `nucleus.yaml` (not `nucleus_project.yaml`); references `.nucleus/warehouse/` layout not emitted by current `nucleus init` |
| **Impact** | MINOR per FOUNDER_ACTION_QUEUE §0 "Silent-landing audit" item 4 |
| **Short-term action** | Add `SUPERSEDED` header: `> **STATUS — SUPERSEDED**: This doc is v3-era. See \`docs/specs/nucleus_architecture_v4.1.md §3.1\` and \`docs/specs/nucleus_cli_spec.md §3.1\` for current layout.` |
| **Long-term action** | Full rewrite for v0.3 site docs; `docs/site/getting-started/` (Wave-1C) may already cover this |
| **Reorg note** | If reorg PR-B runs, this moves to `docs/archive/project-anatomy-v3.md` |

### 4.2 `docs/onboarding/quickstart.md` — may be superseded by `docs/site/`

| Field | Value |
|---|---|
| **Path** | `docs/onboarding/quickstart.md` |
| **Status** | Updated 2026-05-14 with Phase D ctx functions; content is reasonably current but may overlap with `docs/site/getting-started/quickstart.md` (Wave-1C) |
| **Action** | After Wave-1C lands: compare both docs; if `docs/site/` version covers same ground, convert `docs/onboarding/quickstart.md` to redirect note: `See docs/site/getting-started/quickstart.md` |

### 4.3 `docs/swap/lakekeeper.md` + `docs/swap/dlt.md` — reference non-existent test paths

| Field | Value |
|---|---|
| **Paths** | `docs/swap/lakekeeper.md`, `docs/swap/dlt.md` |
| **Issue** | Both reference `tests/swap/` paths for v0.3+ smoke tests that don't exist yet (MINOR verifier finding 6) |
| **Action** | Edit both docs to mark referenced test paths as `"TBD when promoted to v0.3+"` rather than current-pointing claims. 5-min foreground edit. |

### 4.4 `docs/swap/workbench.md` — missing formal Composability sections

| Field | Value |
|---|---|
| **Path** | `docs/swap/workbench.md` |
| **Issue** | Missing the 4-section swap template (interface / smoke tests / migration / owner); documents 4 internal sub-component swaps instead. MINOR verifier finding 7. |
| **Action** | Defer to v0.2 structural review (non-blocking for v0.2.0 release); add TODO note to doc header |

### 4.5 `docs/NEEDS_VERIFICATION_INDEX.md`

| Field | Value |
|---|---|
| **Path** | `docs/NEEDS_VERIFICATION_INDEX.md` |
| **Status** | Likely has stale entries pre-Phase D |
| **Action** | Review and close/archive resolved verification items; keep as living doc |

### 4.6 `docs/architecture/v01_skeleton_plan.md` — post-ship archivable

| Field | Value |
|---|---|
| **Path** | `docs/architecture/v01_skeleton_plan.md` |
| **Status** | v0.1 implementation skeleton plan; now that v0.1 shipped, this is historical planning |
| **Action** | Keep until v0.2 planning doc is created; then archive to `docs/archive/` |

---

## Section 5: Empty / Placeholder Files

### 5.1 `.gitkeep` files that should remain

These are intentional placeholders for empty directories that should stay in git:

| File | Directory | Keep? |
|---|---|---|
| `data/.gitkeep` (in project templates) | `src/nucleus/templates/v01/data/gitkeep` | YES — template scaffold must emit this |
| Any `tests/*/` `.gitkeep` | Various test subdirs | YES — preserve test directory structure |

### 5.2 Empty `__init__.py` re-exports

| Field | Value |
|---|---|
| **Search** | `rg "^$\|^#" --type py src/nucleus/` to find near-empty `__init__.py` files |
| **Action** | If an `__init__.py` has zero exports and zero content, add a minimal module docstring OR delete if the directory is genuinely internal; confirm no import chain depends on it |

---

## Section 6: Generated Artifacts Polluting Tree

The 2026-05-14 repo housekeeping wave already cleaned the major generated artifacts (`.mypy_cache`, `__pycache__`, `coverage.xml`). Verify these patterns are in `.gitignore`:

| Pattern | Currently .gitignored? | Action if missing |
|---|---|---|
| `.pytest_cache/` | YES per housekeeping wave | None |
| `__pycache__/` | YES | None |
| `*.pyc` | YES | None |
| `coverage.xml` | YES (post-housekeeping) | None |
| `htmlcov/` | Verify | Add if missing |
| `_site/`, `site/` | Verify | Add if missing (mkdocs output) |
| `*.bak`, `*.orig`, `*.tmp` | YES (added 2026-05-14) | None |
| `node_modules/`, `.npm/` | YES (added 2026-05-14) | None |
| `.venv/` | Verify | Add if missing |
| `dist/`, `build/`, `*.egg-info` | Verify | Add if missing (wheel build artifacts) |

**Action**: `rg "htmlcov\|_site\|dist\|build\|egg-info" .gitignore` to verify. If any missing, add to `.gitignore` in a single foreground edit.

**Note**: `.venv/` is appearing in git status (`?? .venv\...`) which means it is either NOT in `.gitignore` or the venv was created before .gitignore was in place. Verify and add if missing.

---

## Section 7: Execution Order (Post Wave-1)

```
PRE-CONDITION: All 5 Wave-1 builders have returned + verifier PASS

Step 1 — Governance baseline (foreground, ~5 min)
  Run all 8 governance scripts; confirm EXIT 0 before any deletions.
  Any failures → fix first.

Step 2 — Section 6: .gitignore audit (foreground, ~5 min)
  rg "htmlcov|_site|dist|build|egg-info|\.venv" .gitignore
  Add missing patterns. One commit: "housekeeping: ensure generated artifacts gitignored"

Step 3 — Section 5: Empty placeholders (foreground, ~5 min)
  Verify .gitkeep files are intentional. Audit near-empty __init__.py.

Step 4 — Section 1.1–1.4: Safe deletions (foreground or swarm, ~15 min)
  git rm docs/security/threat_model_v0.md
  Remove-Item SESSION_STATE_2026-05-13.md  (if founder approves)
  Review architecture_design_conversation.md (delete vs archive)
  Review frontend/ (delete vs archive — wave-1A dependency)
  One commit: "cleanup: remove stale/superseded files"

Step 5 — Section 4: Doc fixes (foreground, ~20 min)
  Update 5 docs (anatomy header, swap/lakekeeper, swap/dlt TODOs)
  One commit: "docs: mark stale docs and fix broken test path references"

Step 6 — Section 2: Archive deprecated architecture docs (PR-A in reorg plan)
  git mv nucleus_architecture_v3.md docs/archive/architecture-v3.md
  git mv nucleus_architecture_v4.md docs/archive/architecture-v4.md
  Update AGENTS.md §2 reading list table
  PR: "archive: move deprecated v3/v4 architecture docs to docs/archive/"

Step 7 — Section 2.3: Archive promoted PoC stubs (founder decision)
  Decide: git mv poc/p1–p3 to docs/archive/poc/ OR keep in place
  If move: update any test conftest.py that references poc/ paths
  PR: "archive: move promoted poc/ stubs to docs/archive/poc/"

Step 8 — Section 3: Consolidate dispatchers (v0.2.1 patch)
  CLI ingest dispatch consolidation requires a dedicated builder + verifier
  Not safe for foreground foreground edit; defer to v0.2.1
```

---

## Founder Decisions Required

| # | Decision | Options | Recommendation |
|---|---|---|---|
| F1 | `SESSION_STATE_2026-05-13.md` | A: Delete (stale snapshot) / B: Archive | **A: Delete** per FOUNDER_ACTION_QUEUE explicit recommendation |
| F2 | `architecture_design_conversation.md` | A: Delete (superseded) / B: Archive `docs/archive/` | **B: Archive** (retains design rationale context) |
| F3 | PoC p1/p2/p3 stubs post-promotion | A: Archive to `docs/archive/poc/` / B: Keep in `poc/` | **A: Archive** — reduces active tree noise; git history preserved |
| F4 | `frontend/` directory | A: Delete (pre-workbench scratch) / B: Keep until Wave-1A fully confirmed | **B: Keep** until Wave-1A verified; then delete |
| F5 | `docs/specs/nucleus_project_anatomy.md` short-term action | A: Add SUPERSEDED header now (5 min) / B: Leave for reorg PR-B | **A: Add header now** — user-visible confusion risk if left as-is |

---

*Analysis based on repo snapshot 2026-05-15. Foreground must re-verify paths after Wave-1 builders land, as some files may have been modified or deleted by concurrent waves.*
