# Root Markdown Reorganisation — Phase 2 Plan

| Field | Value |
|---|---|
| **Created** | 2026-05-15 |
| **Status** | DEFERRED — execute after ratification builder + UI v0.3 builder complete |
| **ADR** | [ADR-037](../../decisions/ADR-037-root-md-reorg.md) |
| **Phase 1 completed** | 2026-05-15 (cruft deleted, stale doc archived, `.gitignore` updated) |

---

## Section A: Root-Level Inventory

### A.1 — Markdown files (post–Phase 1)

| File | Size | Last modified | Category | Action |
|---|---|---|---|---|
| `README.md` | 10 KB | 2026-05-15 | Repo standard | **KEEP** at root |
| `CHANGELOG.md` | 30.6 KB | 2026-05-15 | Repo standard | **KEEP** at root |
| `CONTRIBUTING.md` | 10.9 KB | 2026-05-12 | Repo standard | **KEEP** at root |
| `AGENTS.md` | 32.1 KB | 2026-05-15 | AI directive | **KEEP** at root (sacred file) |
| `CODE_OF_CONDUCT.md` | 5.2 KB | 2026-05-15 | Community | **KEEP** at root |
| `SECURITY.md` | 0.9 KB | 2026-05-15 | Community | **KEEP** at root |
| `SUPPORT.md` | 0.7 KB | 2026-05-15 | Community | **KEEP** at root |
| `GOVERNANCE.md` | 1.1 KB | 2026-05-15 | Community | **KEEP** at root |
| `MAINTAINERS.md` | 0.6 KB | 2026-05-15 | Community | **KEEP** at root |
| `SETUP.md` | 26.9 KB | 2026-05-14 | User guide | **MOVE** → `docs/onboarding/setup.md` |
| `docs/specs/nucleus_architecture_v4.1.md` | 81.4 KB | 2026-05-14 | Spec | **MOVE** → `docs/architecture/architecture-v4.1.md` |
| `docs/specs/nucleus_asset_model_spec.md` | 12.1 KB | 2026-05-12 | Spec | **MOVE** → `docs/architecture/asset-model.md` |
| `docs/specs/nucleus_cli_spec.md` | 27.0 KB | 2026-05-15 | Spec | **MOVE** → `docs/architecture/cli-spec.md` |
| `docs/specs/nucleus_ctx_sdk_spec.md` | 17.8 KB | 2026-05-15 | Spec | **MOVE** → `docs/architecture/ctx-sdk-spec.md` |
| `docs/specs/nucleus_project_anatomy.md` | 13.4 KB | 2026-05-15 | Spec | **MOVE** → `docs/architecture/project-anatomy.md` |
| `docs/specs/nucleus_vs_databricks.md` | 22.0 KB | 2026-05-14 | Spec | **MOVE** → `docs/architecture/vs-databricks.md` |
| `docs/specs/nucleus_poc_plan.md` | 25.1 KB | 2026-05-14 | Plan | **MOVE** → `docs/internal/poc/poc-plan.md` |
| `docs/specs/nucleus_implementation_readiness.md` | 11.9 KB | 2026-05-12 | Plan | **MOVE** → `docs/architecture/implementation-readiness.md` |
| `docs/specs/nucleus_red_team_review.md` | 35.6 KB | 2026-05-12 | Review | **MOVE** → `docs/architecture/red-team-review.md` |

**Net**: 9 files stay at root (repo standard + community), 10 files move.

### A.2 — Non-markdown root files (all KEEP at root)

| File | Category | Note |
|---|---|---|
| `pyproject.toml` | Python packaging | Conventional root location |
| `Makefile` | Build tooling | Conventional root location |
| `mkdocs.yml` | Docs site config | Conventional root location |
| `.gitignore` | Git config | Conventional root location |
| `.pre-commit-config.yaml` | Git hooks | Conventional root location |
| `.env.example` | Config template | Conventional root location |
| `.cursorindexingignore` | IDE config | Conventional root location |
| `LICENSE` | Legal | Conventional root location |
| `docker-compose.yml` | Dev environment | See Open Question §E.1 |
| `docker-compose.minio.yml` | Dev environment (MinIO only) | See Open Question §E.1 |
| `docker-compose.demo.yml` | Demo environment | See Open Question §E.1 |

### A.3 — Phase 1 changes already completed (2026-05-15)

| Action | File | Size deleted |
|---|---|---|
| DELETED | `.coverage` | 122,880 bytes |
| DELETED | `coverage.xml` | 204,908 bytes |
| DELETED | `result.txt` | 7 bytes |
| DELETED | `test_results.txt` | 323 bytes |
| DELETED | `verifier-fix-pytest.log` | 1,528 bytes |
| DELETED | `workbench_snapshot.html` | 26,713 bytes |
| ARCHIVED | `architecture_design_conversation.md` → `docs/archive/` | 29,648 bytes |
| UPDATED | `.gitignore` — added `result.txt`, `test_results.txt`, `workbench_snapshot.html` | — |

---

## Section B: Cross-Reference Impact

Cross-references were enumerated using `Grep` (ripgrep) across the full repository (all file types).

### B.1 — Reference counts per file

| File to move | Total occurrences | Unique source files | High-impact referrers |
|---|---|---|---|
| `docs/specs/nucleus_architecture_v4.1.md` | ~500+ | ~200 | `AGENTS.md` (9), `README.md` (10), `.cursor/rules/nucleus.mdc` (7), `docs/recipes/slack_bot_on_data.md` (13), `docs/decisions/ADR-002` (13), all ADRs, all swap docs, all pattern docs |
| `docs/specs/nucleus_cli_spec.md` | ~200+ | ~90 | `src/nucleus/cli/main.py` (19), `tests/release_e2e/` (20), `docs/recipes/postgres_to_iceberg.md` (12), `SETUP.md` (9) |
| `docs/specs/nucleus_ctx_sdk_spec.md` | ~150+ | ~65 | `docs/patterns/time_travel.md` (6), `docs/patterns/secret_management.md` (6), `docs/decisions/ADR-005` (8), `docs/dev-guides/05` (6) |
| `docs/specs/nucleus_poc_plan.md` | ~120+ | ~55 | `poc/p5_beachhead/DESIGN.md` (7), `docs/decisions/ADR-002` (1), `.cursor/rules/nucleus.mdc` (1) |
| `docs/specs/nucleus_red_team_review.md` | ~60+ | ~25 | `docs/specs/nucleus_vs_databricks.md` (7), `docs/specs/nucleus_implementation_readiness.md` (7) |
| `SETUP.md` | ~90+ | ~25 | `CONTRIBUTING.md` (7), `docs/specs/nucleus_architecture_v4.1.md` (1), `docs/decisions/ADR-008` (3) |
| `docs/specs/nucleus_vs_databricks.md` | ~30+ | ~14 | `AGENTS.md` (1), `docs/internal/research/workbench.md` (5) |
| `docs/specs/nucleus_project_anatomy.md` | ~40+ | ~22 | `docs/architecture/v01_skeleton_plan.md` (3), `.cursor/agents/external-data-engineer-tester.md` (2) |
| `docs/specs/nucleus_asset_model_spec.md` | ~30+ | ~25 | `docs/archive/architecture-v4.md` (3), `docs/architecture/v01_skeleton_plan.md` (3) |
| `docs/specs/nucleus_implementation_readiness.md` | ~25+ | ~11 | `AGENTS.md` (3), `docs/specs/nucleus_architecture_v4.1.md` (3) |

**REVISED TOTAL CROSS-REF ESTIMATE: ~1,300+ occurrences across ~350+ unique source files** (across all file types). The earlier Wave 1I estimate of ~83 counted only top-level `.md` files; the actual scope is ~4× larger when all file types and subdirectories are included. The critical observation: most references in `src/nucleus/**/*.py` and `tests/**/*.py` are docstring citations (`# Per architecture v4.1 §6.3`), NOT filesystem paths — those do NOT need updating. Only files containing the literal filename string as a path reference need editing.

### B.2 — Critical high-risk files (require careful update, LOCKED during this wave)

These files have the highest reference counts AND are currently locked by other builders. They MUST wait for Phase 2:

- `AGENTS.md` — §2 Required Reading table references all 9 spec files by exact root-relative path
- `.cursor/rules/nucleus.mdc` — multiple `@`-reference hints to spec files

### B.3 — Files NOT needing path updates (docstring/section citations)

All `src/nucleus/**/*.py` files that say `# Per architecture v4.1 §6.3` — these cite section numbers, not filesystem paths. No update required.

---

## Section C: Execution Plan (Sequenced for Safety)

```
STEP 1: WAIT for both currently-running builders to complete.
        Gate condition: no files locked by ratification builder or UI v0.3 builder.
        Verify: git status shows no outstanding WIP branches from other workers.

STEP 2: Verify clean git state.
        Command: git status
        Expected: working tree clean (or only untracked files acceptable).

STEP 3: Execute moves using git mv (preserves history).
        git mv SETUP.md docs/onboarding/setup.md
        git mv docs/specs/nucleus_architecture_v4.1.md docs/architecture/architecture-v4.1.md
        git mv docs/specs/nucleus_asset_model_spec.md docs/architecture/asset-model.md
        git mv docs/specs/nucleus_cli_spec.md docs/architecture/cli-spec.md
        git mv docs/specs/nucleus_ctx_sdk_spec.md docs/architecture/ctx-sdk-spec.md
        git mv docs/specs/nucleus_project_anatomy.md docs/architecture/project-anatomy.md
        git mv docs/specs/nucleus_vs_databricks.md docs/architecture/vs-databricks.md
        git mv docs/specs/nucleus_poc_plan.md docs/internal/poc/poc-plan.md
        git mv docs/specs/nucleus_implementation_readiness.md docs/architecture/implementation-readiness.md
        git mv docs/specs/nucleus_red_team_review.md docs/architecture/red-team-review.md

        NOTE: Create target directories if missing:
        mkdir -p docs/architecture docs/poc (only if not already present)

STEP 4: Update cross-references in every referencing .md / .mdc / .yml file.
        Scope: all files returned by the Grep searches in Section B.
        Strategy: sed-style search-and-replace per filename.
        MUST update:
        - AGENTS.md §2 Required Reading table (9 path references)
        - .cursor/rules/nucleus.mdc (multiple @-reference hints)
        - README.md
        - All ADR files in docs/decisions/
        - All docs/recipes/, docs/patterns/, docs/internal/swap/, docs/dev-guides/
        - All poc/ README and PROMOTION files
        - mkdocs.yml nav section (if paths are listed)
        DO NOT update:
        - src/nucleus/**/*.py docstring section citations (not filesystem paths)

STEP 5: Verify no stale references remain.
        Run these patterns (should return ZERO matches outside new locations + this plan doc):
        rg "nucleus_architecture_v4\.1\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_asset_model_spec\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_cli_spec\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_ctx_sdk_spec\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_project_anatomy\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_vs_databricks\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_poc_plan\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_implementation_readiness\.md" -- *.md docs/ .cursor/ .github/
        rg "nucleus_red_team_review\.md" -- *.md docs/ .cursor/ .github/
        rg "^SETUP\.md$" -- *.md docs/ .cursor/ .github/

STEP 6: Run full governance suite + tests.
        python scripts/check_vocabulary.py      # must EXIT 0
        python scripts/dagster_leak_check.py    # must EXIT 0
        python scripts/check_layering.py        # must EXIT 0 (if exists)
        python scripts/check_api_stability.py   # must EXIT 0 (if exists)
        pytest tests/ -x -q                     # no regression
        mkdocs build --strict                   # docs site renders (may need nav update in mkdocs.yml)

STEP 7: Update FOUNDER_ACTION_QUEUE.md §0 with cleanup record.

STEP 8: Single atomic commit:
        git add -A
        git commit -m "chore: reorg root .md spec files -> docs/architecture/"

        Rollback command (preserve for PR description):
        git revert <SHA>
        (single atomic commit makes revert clean)
```

---

## Section D: 8-Question Gate

| Question | Answer |
|---|---|
| Q1: Maps to an architectural layer? | YES — Experience layer (developer DX, repo hygiene) |
| Q2: Serves the <30-min beachhead metric? | INDIRECT — cleaner root lowers cognitive friction for new engineers cloning the repo |
| Q3: Wrap possible instead of build? | N/A — pure filesystem reorganisation |
| Q4: Preserves no-JVM constraint? | YES — no code changes |
| Q5: Preserves local-identical-to-prod? | YES — no runtime changes |
| Q6: Stays within 30K LOC budget? | YES — 0 LOC delta |
| Q7: Triggered by empirical telemetry? | YES — founder explicit request + external tester report that root is confusing |
| Q8: Required for v0.1 or deferrable? | DEFERRABLE — ship after ratification + UI builders return |

**Verdict: PASS** (low-risk hygiene, founder-requested, zero LOC impact).

---

## Section E: Open Questions for Founder

### E.1 — Docker Compose consolidation

Three `docker-compose*.yml` files currently live at root:

- `docker-compose.yml` (core dev stack, 839 bytes)
- `docker-compose.minio.yml` (MinIO-only override, 965 bytes)
- `docker-compose.demo.yml` (demo/public stack, 1,060 bytes)

Options:
- **A**: Keep all three at root (conventional location, Docker documentation expects `docker-compose.yml` at root)
- **B**: Keep `docker-compose.yml` + `docker-compose.minio.yml` at root; move `docker-compose.demo.yml` → `docker/`
- **C**: Move all three to `docker/` with a root-level symlink for `docker-compose.yml`

**Recommended: A** — Docker convention strongly favours root location. The noise is minimal (3 files vs. a directory jump for users). Revisit if count grows beyond 5.

### E.2 — File naming convention on move

Files are currently `snake_case` (e.g., `docs/specs/nucleus_architecture_v4.1.md`). New paths use `kebab-case` (e.g., `architecture-v4.1.md`).

Options:
- **A**: Rename to kebab-case on move (cleaner, matches MkDocs convention)
- **B**: Preserve snake_case (fewer cross-ref changes, lower risk)

**Recommended: A** — kebab-case is the web/docs convention; cleaner URLs in the docs site.

### E.3 — MkDocs `nav:` section

After moves, `mkdocs.yml` `nav:` may need updating to point at new paths. This is safe to do in the same Phase 2 commit. Assign to Phase 2 executor explicitly.

### E.4 — `docs/architecture/` directory already exists?

The directory `docs/architecture/` already exists and contains C4 diagrams and sequence diagrams. The 9 spec files would be added alongside them. Verify no naming collisions before Step 3.

---

## Appendix: Locked Files Reference (Phase 1 constraint)

Files that were NOT touched in Phase 1 due to parallel builder locks:

- `pyproject.toml`, `CHANGELOG.md`, `Makefile` (ratification builder)
- `docs/decisions/ADR-018` through `ADR-036` (ratification builder)
- `.github/workflows/*.yml` (ratification builder)
- `src/nucleus/**`, `tests/**` (both builders)
- `AGENTS.md`, `.cursor/rules/nucleus.mdc` (sacred — Phase 2 only)
- `mkdocs.yml` (UI v0.3 builder)
