# Nucleus Directory Reorg Proposal — Pre-v0.2 Release

> **Status**: DRAFT — created by release-planner builder 2026-05-15  
> **Split strategy**: PR-A (low-risk archive move) + PR-B (higher-risk spec reorganization)  
> **Founder decision required**: Approve PR-B scope for v0.2 vs defer to v0.3 (see §8)

---

## Goals

1. **Clean root**: reduce root-level files from ~20 to 8 (only community + project management files at root)
2. **Discoverable architecture docs**: all specs in `docs/architecture/` alongside existing C4 diagrams and sequence diagrams
3. **Archived history**: deprecated v3/v4 docs in `docs/archive/` — visible but not cluttering the main tree
4. **User vs contributor docs separated**: `docs/site/` = user-facing (Wave-1C); `docs/` (non-site) = contributor/internal
5. **Zero functional breakage**: all CI references, Python docstrings, and Cursor rules remain valid post-reorg

---

## Current State (Root-Level Files)

```
my-data-stack/                          ← repo root
├── AGENTS.md                          ← KEEP at root (universal AI agent instruction file)
├── CHANGELOG.md                       ← KEEP at root (conventional)
├── CONTRIBUTING.md                    ← KEEP at root (GitHub convention)
├── LICENSE                            ← KEEP at root (GitHub convention)
├── Makefile                           ← KEEP at root
├── README.md                          ← KEEP at root
├── SECURITY.md                        ← KEEP at root (GitHub convention)
├── SETUP.md                           ← KEEP at root (contributor onboarding)
├── pyproject.toml                     ← KEEP at root
│
├── nucleus_architecture_v3.md         ← ARCHIVE to docs/archive/
├── nucleus_architecture_v4.md         ← ARCHIVE to docs/archive/
├── docs/specs/nucleus_architecture_v4.1.md       ← MOVE to docs/architecture/overview.md (PR-B)
├── docs/specs/nucleus_cli_spec.md                ← MOVE to docs/architecture/cli-spec.md (PR-B)
├── docs/specs/nucleus_ctx_sdk_spec.md            ← MOVE to docs/architecture/ctx-sdk-spec.md (PR-B)
├── docs/specs/nucleus_asset_model_spec.md        ← MOVE to docs/architecture/asset-model-spec.md (PR-B)
├── docs/specs/nucleus_project_anatomy.md         ← MOVE to docs/architecture/project-anatomy.md (PR-B)
├── docs/specs/nucleus_poc_plan.md                ← MOVE to docs/architecture/poc-plan.md (PR-B)
├── docs/specs/nucleus_implementation_readiness.md ← MOVE to docs/architecture/implementation-readiness.md (PR-B)
├── docs/specs/nucleus_red_team_review.md         ← MOVE to docs/architecture/red-team-review.md (PR-B)
├── docs/specs/nucleus_vs_databricks.md           ← MOVE to docs/architecture/vs-databricks.md (PR-B)
│
├── SESSION_STATE_2026-05-13.md        ← DELETE (see CLEANUP_INVENTORY §1.1)
├── architecture_design_conversation.md ← ARCHIVE to docs/archive/ (see CLEANUP_INVENTORY §1.2)
│
└── docker-compose.yml                 ← KEEP at root (conventional)
    docker-compose.minio.yml           ← KEEP at root
```

---

## Proposed State (Post-Reorg)

```
my-data-stack/                          ← repo root
├── AGENTS.md                          ← unchanged
├── CHANGELOG.md                       ← unchanged
├── CONTRIBUTING.md                    ← unchanged
├── LICENSE                            ← unchanged
├── Makefile                           ← unchanged
├── README.md                          ← unchanged
├── SECURITY.md                        ← unchanged
├── SETUP.md                           ← unchanged
├── pyproject.toml                     ← unchanged
├── docker-compose.yml                 ← unchanged
├── docker-compose.minio.yml           ← unchanged
│
├── docs/
│   ├── archive/                       ← NEW
│   │   ├── architecture-v3.md         ← was nucleus_architecture_v3.md
│   │   ├── architecture-v4.md         ← was nucleus_architecture_v4.md
│   │   ├── design-conversation.md     ← was architecture_design_conversation.md
│   │   └── poc/                       ← promoted PoC stubs (founder decision)
│   │       ├── p1_error_translation/
│   │       ├── p2_ctx_sql/
│   │       └── p3_ingest/
│   │
│   ├── architecture/                  ← EXISTING (has C4 + sequence diagrams) + NEW specs
│   │   ├── README.md                  ← EXISTING
│   │   ├── C4_context.md              ← EXISTING
│   │   ├── C4_container.md            ← EXISTING
│   │   ├── C4_component.md            ← EXISTING
│   │   ├── sequence_*.md              ← EXISTING (5 sequence diagrams)
│   │   ├── nucleus_overview.excalidraw ← EXISTING
│   │   │
│   │   ├── overview.md                ← NEW: was docs/specs/nucleus_architecture_v4.1.md
│   │   ├── cli-spec.md                ← NEW: was docs/specs/nucleus_cli_spec.md
│   │   ├── ctx-sdk-spec.md            ← NEW: was docs/specs/nucleus_ctx_sdk_spec.md
│   │   ├── asset-model-spec.md        ← NEW: was docs/specs/nucleus_asset_model_spec.md
│   │   ├── project-anatomy.md         ← NEW: was docs/specs/nucleus_project_anatomy.md
│   │   ├── poc-plan.md                ← NEW: was docs/specs/nucleus_poc_plan.md
│   │   ├── implementation-readiness.md ← NEW: was docs/specs/nucleus_implementation_readiness.md
│   │   ├── red-team-review.md         ← NEW: was docs/specs/nucleus_red_team_review.md
│   │   └── vs-databricks.md           ← NEW: was docs/specs/nucleus_vs_databricks.md
│   │
│   ├── audits/                        ← EXISTING
│   ├── decisions/                     ← EXISTING (ADRs 001–018+)
│   ├── errors/                        ← EXISTING
│   ├── onboarding/                    ← EXISTING
│   ├── patterns/                      ← EXISTING
│   ├── poc/                           ← EXISTING (p5_beachhead docs)
│   ├── recipes/                       ← EXISTING
│   ├── release/                       ← NEW (this planning dir + E2E/checklist)
│   ├── research/                      ← EXISTING
│   ├── security/                      ← EXISTING
│   ├── site/                          ← EXISTING (Wave-1C public docs)
│   ├── swap/                          ← EXISTING
│   └── conventions/                   ← EXISTING
│
├── src/nucleus/                        ← UNCHANGED
├── tests/                             ← UNCHANGED (+ new tests/release_e2e/)
├── scripts/                           ← UNCHANGED (+ new scripts/release_e2e/)
└── poc/                               ← p4_boot_time + p5_beachhead remain here
```

---

## PR-A: Archive Deprecated Architecture Docs (LOW RISK)

**Scope**: 2 file moves + 1 `AGENTS.md` path update. No code changes.  
**Estimated effort**: 15 min foreground.  
**Risk**: Low — deprecated files with no production import references.

### Steps

```powershell
# 1. Create archive directory
New-Item -ItemType Directory -Force docs/archive

# 2. Git-move deprecated architecture docs (preserves blame/log)
git mv nucleus_architecture_v3.md docs/archive/architecture-v3.md
git mv nucleus_architecture_v4.md docs/archive/architecture-v4.md

# 3. Update AGENTS.md §2 reading list table
# In the "Required Reading" table, update the two "deprecated" rows:
# Row: "nucleus_architecture_v3.md" → "docs/archive/architecture-v3.md"
# Row: "nucleus_architecture_v4.md" → "docs/archive/architecture-v4.md"
# Add note: "(deprecated — historical reference)"

# 4. Verify
rg "nucleus_architecture_v3\.md|nucleus_architecture_v4\.md" --type md
# Expected: only AGENTS.md (just updated), CHANGELOG.md historical mentions,
# and potentially ADR docs with inline citations
# All citations should still work as "historical reference"

# 5. Commit
git commit -m "archive: move deprecated nucleus_architecture_v3/v4.md to docs/archive/"
```

### Cross-references that need updating (PR-A only)

| File | Current reference | Updated reference |
|---|---|---|
| `AGENTS.md` §2 | `nucleus_architecture_v3.md` (deprecated row) | `docs/archive/architecture-v3.md` |
| `AGENTS.md` §2 | `nucleus_architecture_v4.md` (deprecated row) | `docs/archive/architecture-v4.md` |

All other citations (e.g., in ADRs) can remain as `nucleus_architecture_v3.md` with a note that it's now at `docs/archive/`.

---

## PR-B: Reorganize Specs into `docs/architecture/` (HIGHER RISK)

**Scope**: 9 root-level spec files moved + ~50 cross-reference updates.  
**Estimated effort**: 2–3 hours (foreground or dedicated swarm-implementer).  
**Risk**: MEDIUM — ~50 cross-references in Python docstrings, MDX, and cursor rules.

### Founder decision required: **Go for v0.2 OR defer to v0.3?**

**Recommendation**: **DEFER PR-B to v0.3** unless strong reason to do it now. Rationale:
1. v0.2 is already feature-heavy (Workbench, connectors, Wave-1 landing)
2. ~50 cross-ref updates = moderate breakage risk
3. Python docstrings with `# Per docs/specs/nucleus_architecture_v4.1.md §X.Y` are in ~50 places (estimate from FOUNDER_ACTION_QUEUE references)
4. `.cursor/rules/nucleus.mdc` cites the v4.1 path explicitly 3+ times
5. No user-visible benefit (user-facing docs are in `docs/site/`)

If deferred: add a `# TODO: reorg PR-B deferred to v0.3` comment in this doc.

### Steps (if approved for v0.2)

```powershell
# Step 1: Ensure docs/architecture/ exists (it already does with C4 diagrams)
# No mkdir needed

# Step 2: Git-move all 9 spec files
git mv docs/specs/nucleus_architecture_v4.1.md docs/architecture/overview.md
git mv docs/specs/nucleus_cli_spec.md docs/architecture/cli-spec.md
git mv docs/specs/nucleus_ctx_sdk_spec.md docs/architecture/ctx-sdk-spec.md
git mv docs/specs/nucleus_asset_model_spec.md docs/architecture/asset-model-spec.md
git mv docs/specs/nucleus_project_anatomy.md docs/architecture/project-anatomy.md
git mv docs/specs/nucleus_poc_plan.md docs/architecture/poc-plan.md
git mv docs/specs/nucleus_implementation_readiness.md docs/architecture/implementation-readiness.md
git mv docs/specs/nucleus_red_team_review.md docs/architecture/red-team-review.md
git mv docs/specs/nucleus_vs_databricks.md docs/architecture/vs-databricks.md

# Step 3: Cross-reference sweep (the dangerous step)
# A. Python docstrings (estimate ~50 occurrences)
rg "nucleus_architecture_v4\.1\.md" --type py -l
# For each file found: replace "docs/specs/nucleus_architecture_v4.1.md" with "docs/architecture/overview.md"

# B. Markdown docs
rg "nucleus_architecture_v4\.1\.md|nucleus_cli_spec\.md|nucleus_ctx_sdk_spec\.md" --type md -l
# For each file: update relative paths

# C. Cursor rules
rg "nucleus_architecture_v4\.1\.md" ".cursor/rules/"
# Update .cursor/rules/nucleus.mdc (all citations)

# D. AGENTS.md Required Reading table
# Update all 9 paths in AGENTS.md §2 table

# Step 4: Verify no broken references
rg "nucleus_architecture_v4\.1\.md" --type py --type md
# Must return only: archive mentions, CHANGELOG history, and the now-updated files

# Step 5: Run governance
.\.venv\Scripts\python.exe scripts/check_vocabulary.py
.\.venv\Scripts\python.exe scripts/check_pinning.py
.\.venv\Scripts\python.exe scripts/dagster_leak_check.py
.\.venv\Scripts\python.exe -m pytest tests/ -q

# Step 6: Commit
git commit -m "reorg: move spec docs to docs/architecture/ for cleaner root"
```

### Cross-reference map (PR-B)

Complete map of files requiring path updates. Survey run 2026-05-15 (approximate — foreground must re-verify after Wave-1):

| Old path | New path | Files that reference it |
|---|---|---|
| `docs/specs/nucleus_architecture_v4.1.md` | `docs/architecture/overview.md` | `AGENTS.md`, `.cursor/rules/nucleus.mdc`, ~50 Python docstrings in `src/nucleus/`, all ADRs, `CHANGELOG.md`, `docs/FOUNDER_ACTION_QUEUE.md`, `README.md` |
| `docs/specs/nucleus_cli_spec.md` | `docs/architecture/cli-spec.md` | `AGENTS.md §2`, `src/nucleus/cli/main.py` docstrings, `tests/cli/`, ADR-005, ADR-017 |
| `docs/specs/nucleus_ctx_sdk_spec.md` | `docs/architecture/ctx-sdk-spec.md` | `AGENTS.md §2`, `src/nucleus/sdk/`, `src/nucleus/ctx/`, ADR-005, ADR-013 |
| `docs/specs/nucleus_asset_model_spec.md` | `docs/architecture/asset-model-spec.md` | `AGENTS.md §2`, ADR-013, v4.1 references |
| `docs/specs/nucleus_project_anatomy.md` | `docs/architecture/project-anatomy.md` | `AGENTS.md §2`, `docs/specs/nucleus_cli_spec.md §3.1` |
| `docs/specs/nucleus_poc_plan.md` | `docs/architecture/poc-plan.md` | `AGENTS.md §2`, `FOUNDER_ACTION_QUEUE.md`, ADR docs |
| `docs/specs/nucleus_implementation_readiness.md` | `docs/architecture/implementation-readiness.md` | `AGENTS.md §2`, `FOUNDER_ACTION_QUEUE.md` |
| `docs/specs/nucleus_red_team_review.md` | `docs/architecture/red-team-review.md` | `AGENTS.md §2` |
| `docs/specs/nucleus_vs_databricks.md` | `docs/architecture/vs-databricks.md` | `AGENTS.md §2`, `README.md` |

**Estimated count**: ~50 Python docstrings + ~30 Markdown links + 3 cursor rule citations = ~83 references total.  
**Automation**: use `rg` + `sd` (or PowerShell `Get-Content | ForEach-Object { $_ -replace ... }`) for bulk replace.

---

## Source Tree (No Changes Proposed)

The `src/nucleus/` tree is well-organized and should NOT be touched in reorg. Current structure:

```
src/nucleus/
  __init__.py         ← package root + version
  errors.py           ← NucleusError hierarchy (32 codes)
  ctx/                ← public ctx SDK (copy_from, sql, read)
  sdk/                ← decorators, materialize, contracts, results, types
  coordination/       ← AMA, error_translation, sql_resolver, lineage, schedules
  intelligence/       ← copilot, context, translate
  cli/                ← main.py + commands/
  workbench/          ← FastAPI app (Wave-1A)
  templates/          ← v01/ scaffold template
  _internal/          ← internal helpers
  engines/            ← DuckDB swap interface (stub)
  physics/            ← Arrow physics layer (stub)
```

This layout directly mirrors the 5-layer architecture (Physics/Engines/Coordination/Intelligence/Experience) per `docs/specs/nucleus_architecture_v4.1.md` §3. Do not restructure.

---

## Tests Tree (Minor Addition Only)

```
tests/
  ctx/                ← EXISTING
  sdk/                ← EXISTING
  coordination/       ← EXISTING
  intelligence/       ← EXISTING
  cli/                ← EXISTING
  workbench/          ← EXISTING (Wave-1A)
  contracts/          ← EXISTING
  errors/             ← if added by Wave-1E
  swap/               ← EXISTING (swap smoke tests)
  templates/          ← EXISTING
  upgrade_smoke/      ← EXISTING
  release_e2e/        ← NEW (release-planner builder, this dir)
  fixtures/           ← EXISTING (conftest.py)
  test_errors.py      ← EXISTING (root-level)
  conftest.py         ← EXISTING
```

---

## Scripts Tree (Minor Addition Only)

```
scripts/
  beachhead_e2e.py           ← EXISTING
  benchmark_regression.py    ← EXISTING
  check_api_stability.py     ← EXISTING
  check_bundle_size.py       ← EXISTING
  check_changelog.py         ← EXISTING
  check_error_codes.py       ← EXISTING
  check_layering.py          ← EXISTING
  check_licenses.py          ← EXISTING
  check_pinning.py           ← EXISTING
  check_vocabulary.py        ← EXISTING
  dagster_leak_check.py      ← EXISTING
  loc_budget.py              ← EXISTING
  release.py                 ← EXISTING
  upgrade_smoke.py           ← EXISTING
  release_e2e/               ← NEW (release-planner builder, this dir)
    e2e_full.py
    run_chaos.py
```

---

## Risks + Rollback

### PR-A Risks (Low)

| Risk | Mitigation |
|---|---|
| IDE cached paths to old location | Clear IDE file index post-merge; paths in archive still valid |
| Cursor rule `@nucleus_architecture_v3.md` references | Add redirect comment in archive file |
| CI docs build referencing old paths | mkdocs.yml nav entries need update if wave-1C added them |

**Rollback PR-A**: `git mv docs/archive/architecture-v3.md nucleus_architecture_v3.md && git mv docs/archive/architecture-v4.md nucleus_architecture_v4.md`

### PR-B Risks (Medium)

| Risk | Mitigation |
|---|---|
| ~83 broken cross-references | Full `rg` sweep + automated replace before merge |
| `.cursor/rules/nucleus.mdc` @-references broken | Update 3 explicit path citations in the rules file |
| Python `# Per docs/specs/nucleus_architecture_v4.1.md §X.Y` comments broken | These are citation comments, not import paths — they won't break CI but will be stale; do a `rg` sweep to update all |
| mkdocs.yml nav paths | Update `nav:` entries in `mkdocs.yml` if they reference root-level spec files |
| Cursor context-attach `@docs/specs/nucleus_architecture_v4.1.md` in existing chat history | Non-issue — historical chats are not affected |

**Rollback PR-B**: `git revert HEAD` (entire commit can be reverted cleanly if all moves are in one commit).

---

## Recommendation Summary

| Action | For v0.2 | Notes |
|---|---|---|
| PR-A: Archive deprecated v3/v4 | **YES — do now** | Low risk, high cleanup value, 15 min |
| Cleanup section 1–6 | **YES — do now** | Low risk, see CLEANUP_INVENTORY |
| PR-B: Specs → docs/architecture/ | **DEFER to v0.3** | ~83 ref updates, risky during v0.2 feature landing |

If the founder approves PR-B for v0.2, execute it **in a dedicated PR with no other changes** (AGENTS.md §11.10 Composer discipline).

---

## Section 8: Founder Decision (PR-B Timing)

```
PAUSE — PR-B timing decision

Options:
 A) Execute PR-B for v0.2 (concurrent with release wave)
 B) Execute PR-B after v0.2 tag is cut (as a v0.2.1 housekeeping PR)
 C) Defer PR-B entirely to v0.3 milestone

Recommended: C (defer to v0.3) — spec doc locations are only visible to
contributors/AI agents, not end users; root clutter is minor; the ~83
ref-update effort is best spent on features during v0.2 crunch.
```

---

*Proposal created by release-planner builder 2026-05-15. Foreground reconciles against Wave-1 output before execution.*
