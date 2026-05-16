# Nucleus v0.2 Release Execution Checklist

> **Status**: DRAFT — created by release-planner builder 2026-05-15  
> **Purpose**: Foreground operator runbook for executing v0.2 release after all Wave-1 builders return.  
> **Owner**: Foreground architect (Opus 4.7 tier)  
> **Refs**: `docs/release/E2E_TEST_PLAN.md`, `docs/release/CLEANUP_INVENTORY.md`, `docs/release/REORG_PROPOSAL.md`

---

## Prerequisites — Before Starting

All of the following must be TRUE before proceeding:

- [ ] All 5 Wave-1 builders have returned (1A workbench, 1B connectors, 1C docs, 1D community, 1E mass audit)
- [ ] All researcher subagents have returned with findings
- [ ] Each Wave-1 builder reported PASS or PASS-WITH-CAVEATS (no FAIL/BLOCKED)
- [ ] No `pyproject.toml` merge conflicts (foreground verified with `git diff`)
- [ ] No `CHANGELOG.md` section conflicts
- [ ] Foreground has read each builder's output report

**If any Wave-1 builder reported BLOCKED**: Surface to founder before proceeding. Do not merge a blocked wave.

---

## Step 1: Reconciliation (~30 min, foreground)

Merge the parallel wave output into a consistent repo state.

### 1.1 pyproject.toml Merge

```powershell
# View all Wave-1 additions
git diff HEAD pyproject.toml

# Manual merge rules:
# - Dependencies section: alphabetical order; no duplicates; all == exact pins
# - Optional-dependencies: preserve all groups; alphabetical within groups
# - Verify no conflicting pins (two waves pinning same lib to different versions)
.\.venv\Scripts\python.exe scripts/check_pinning.py
# Must EXIT 0
```

- [ ] `pyproject.toml` merged; all deps alphabetical and exactly pinned
- [ ] `python scripts/check_pinning.py` EXIT 0

### 1.2 CHANGELOG.md Merge

```powershell
# Each wave appends to [Unreleased] section
# Merge rule: combine all added lines under [Unreleased]; deduplicate; group by type
# (Added / Changed / Fixed / Deprecated / Removed / Security)
git diff HEAD CHANGELOG.md
```

- [ ] `CHANGELOG.md` [Unreleased] section contains all Wave-1 additions
- [ ] No duplicate entries; properly grouped

### 1.3 Full Test Suite

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q --ignore=tests/release_e2e
# Target: 500+ passed / 0 failed / ≤ 30 skipped
```

- [ ] pytest EXIT 0 (zero failures)
- [ ] Any new failures from Wave-1 triaged: document if acceptable or fix immediately

### 1.4 Governance Baseline

```powershell
.\.venv\Scripts\python.exe scripts/check_vocabulary.py
.\.venv\Scripts\python.exe scripts/check_pinning.py
.\.venv\Scripts\python.exe scripts/loc_budget.py
.\.venv\Scripts\python.exe scripts/dagster_leak_check.py
.\.venv\Scripts\python.exe scripts/check_error_codes.py
.\.venv\Scripts\python.exe scripts/check_api_stability.py
.\.venv\Scripts\python.exe scripts/check_licenses.py
.\.venv\Scripts\python.exe scripts/check_layering.py
```

- [ ] All 8 governance scripts EXIT 0

**Hard gate**: Do NOT proceed past Step 1 if any governance script fails or pytest has failures.

---

## Step 2: Verifier Pass (~20 min, background)

Launch a verifier on the reconciled Wave-1 output before cleanup.

```
Spawn: verifier subagent (read-only)
Prompt: "Verify the reconciled post-Wave-1 state:
  1. All 8 governance scripts EXIT 0?
  2. Any Dagster classname leaks in user-facing strings?
  3. LOC budget GREEN (< 8,000 src/nucleus/)?
  4. pyproject.toml exactly pinned + no missing deps?
  5. Any fabricated APIs or hallucinated method calls?
  Return: PASS / PASS-WITH-CAVEATS / FAIL with evidence."
```

- [ ] Verifier returned PASS or PASS-WITH-CAVEATS
- [ ] All caveats reviewed; blocking ones fixed before proceeding

---

## Step 3: Cleanup (~30 min, foreground or swarm-implementer)

Execute cleanup per `docs/release/CLEANUP_INVENTORY.md`. Order matters.

### 3.1 .gitignore audit (5 min)

```powershell
# Verify all generated artifact patterns are gitignored
Select-String -Path ".gitignore" -Pattern "htmlcov|_site|dist|build|egg-info|\.venv"
```

- [ ] `htmlcov/` gitignored
- [ ] `_site/`, `site/` gitignored
- [ ] `dist/`, `build/`, `*.egg-info` gitignored
- [ ] `.venv/` gitignored

If any missing: add patterns to `.gitignore`; commit: `"housekeeping: ensure generated artifacts gitignored"`

### 3.2 Safe deletions (10 min)

Per CLEANUP_INVENTORY §1:

```powershell
# 3.2.1 — stale session state (founder approval assumed from FAQ.md recommendation)
Remove-Item .\SESSION_STATE_2026-05-13.md

# 3.2.2 — superseded threat model v0
git rm docs/internal/security/threat_model_v0.md

# 3.2.3 — architecture_design_conversation.md (archive if has content; delete if stub)
# Check first: rg "unique-insights" architecture_design_conversation.md
# If purely boilerplate:
# git rm architecture_design_conversation.md
# If has real design context:
# git mv architecture_design_conversation.md docs/archive/design-conversation.md

# 3.2.4 — frontend/ (only after Wave-1A workbench confirmed shipped)
# git rm -r frontend/
```

- [ ] `SESSION_STATE_2026-05-13.md` removed
- [ ] `docs/internal/security/threat_model_v0.md` removed
- [ ] `architecture_design_conversation.md` archived or removed
- [ ] `frontend/` removed (after Wave-1A confirmed)

Commit: `"cleanup: remove stale/superseded files pre-v0.2"`

### 3.3 Stale doc fixes (10 min)

Per CLEANUP_INVENTORY §4:

```powershell
# 3.3.1 — Add SUPERSEDED header to docs/specs/nucleus_project_anatomy.md
# Edit: add the SUPERSEDED header block at top of file

# 3.3.2 — Fix docs/internal/swap/lakekeeper.md (mark test paths as TBD)
# Edit: find "tests/swap/" references; add "(TBD when v0.3+ promotes)" note

# 3.3.3 — Fix docs/internal/swap/dlt.md similarly
```

- [ ] `docs/specs/nucleus_project_anatomy.md` has SUPERSEDED header
- [ ] `docs/internal/swap/lakekeeper.md` TBD notes added
- [ ] `docs/internal/swap/dlt.md` TBD notes added

Commit: `"docs: mark stale docs and add TBD notes for unrealized test paths"`

### 3.4 Archive deprecated architecture docs (PR-A from REORG_PROPOSAL)

```powershell
New-Item -ItemType Directory -Force docs/archive
git mv nucleus_architecture_v3.md docs/archive/architecture-v3.md
git mv nucleus_architecture_v4.md docs/archive/architecture-v4.md

# Update AGENTS.md §2 reading list table: change paths for deprecated rows
# Find: "nucleus_architecture_v3.md"
# Replace: "docs/archive/architecture-v3.md"

# Verify no broken imports
rg "nucleus_architecture_v3\.md|nucleus_architecture_v4\.md" --type md
# Expect: only AGENTS.md (updated), CHANGELOG historical mentions, ADR docs
```

- [ ] `docs/archive/` created
- [ ] v3 + v4 moved to `docs/archive/`
- [ ] `AGENTS.md §2` reading list updated with new paths
- [ ] `rg` sweep shows no broken references

Commit (PR-A): `"archive: move deprecated architecture v3/v4 docs to docs/archive/"`

---

## Step 4: Release E2E Validation (~45 min)

Run the full E2E orchestrator to verify the release candidate.

### 4.1 Suite A + I (mandatory, no external deps)

```powershell
.\.venv\Scripts\python.exe scripts/release_e2e/e2e_full.py --suite A,I
```

- [ ] Suite A: all scenarios PASS or SKIP (0 FAIL)
- [ ] Suite I: all 8 governance scripts PASS (0 FAIL)

**Hard gate**: Suite A and I must be 100% PASS before tagging.

### 4.2 Suite H (error UX, mostly no external deps)

```powershell
.\.venv\Scripts\python.exe scripts/release_e2e/e2e_full.py --suite H
```

- [ ] H1 (fix_hint present): PASS
- [ ] H2 (no classname leaks = dagster_leak_check): PASS (already covered in I)

### 4.3 Full E2E run (with integration features)

```powershell
.\.venv\Scripts\python.exe scripts/release_e2e/e2e_full.py --suite all
```

Expected thresholds per `E2E_TEST_PLAN.md`:
- [ ] Suite A: 100%
- [ ] Suite B: 100% (B6 may SKIP)
- [ ] Suite C: 100%
- [ ] Suite D: ≥ 90% (D5/D6/D9 may SKIP pending infra)
- [ ] Suite E: 100%
- [ ] Suite F: ≥ 75%
- [ ] Suite G: 100% of G2/G4 (auth-independent)
- [ ] Suite H: 100%
- [ ] Suite I: 100%
- [ ] Suite J: ≥ 80% (J3–J8 need Docker; J8 needs network tools)
- [ ] Suite K: 100% of K1–K4

### 4.4 Beachhead E2E (existing baseline)

```powershell
.\.venv\Scripts\python.exe scripts/beachhead_e2e.py
```

- [ ] `beachhead_e2e.py` PASS or PASS-WITH-SKIPS (0 FAIL)
- [ ] Total elapsed < 1800s (30-min beachhead target)

### 4.5 Pytest release smoke tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/release_e2e/ -v
```

- [ ] All immediately-runnable tests PASS (A1, I1, I2, H1)
- [ ] Integration tests SKIP gracefully (not FAIL) if deps unavailable

### 4.6 WSL repeat (Linux validation)

```bash
# Run in WSL terminal
python scripts/release_e2e/e2e_full.py --suite A,I
python -m pytest tests/release_e2e/ -m "not integration and not slow"
```

- [ ] Suite A + I PASS in WSL
- [ ] No Windows-specific path issues in smoke tests

---

## Step 5: Reorg PR-A (Low-Risk Archive) — Optional Timing

**Decision**: Run PR-A (archive deprecated docs) before or after tagging?

**Recommendation**: BEFORE tagging — clean tree is easier to navigate for post-release work.

Steps are in Step 3.4 above (already covered in cleanup).

**PR-B decision**: Per `REORG_PROPOSAL.md` §8 recommendation, **defer to v0.3**. Log decision:

- [ ] PR-B (spec files → docs/architecture/) deferred to v0.3 — noted in `REORG_PROPOSAL.md`

---

## Step 6: CHANGELOG Finalization

```markdown
# In CHANGELOG.md, replace [Unreleased] with version + date:
#
# Before:
# ## [Unreleased]
#
# After:
# ## [0.2.0] — 2026-05-15
```

- [ ] `[Unreleased]` section renamed to `[0.2.0] — YYYY-MM-DD`
- [ ] New empty `[Unreleased]` section added above `[0.2.0]`
- [ ] All Wave-1 additions are under `[0.2.0]` section
- [ ] Content reviewed for accuracy (no fabricated pytest counts)

---

## Step 7: Version Bump

```python
# In pyproject.toml:
# Before: version = "0.1.0"
# After:  version = "0.2.0"

# In src/nucleus/__init__.py (if __version__ is hardcoded):
# __version__ = "0.2.0"
```

- [ ] `pyproject.toml` version → `0.2.0`
- [ ] `src/nucleus/__init__.py` `__version__` → `"0.2.0"` (if applicable)
- [ ] `nucleus version` output shows `0.2.0`

---

## Step 8: AGENTS.md Phase Gate Update

Per `AGENTS.md §1` current phase tracking:

```markdown
# In AGENTS.md §1 "Current Phase":
# Update status line: "v0.2.0 released YYYY-MM-DD"
# Update checklist items marked [ ] that are now complete
# Specifically:
# [✓] Stage 1 wave (Postgres dlt source + Workbench v0.2 scaffold) shipped
# [~] Open questions in v4.1 Appendix B answered → [x] if resolved
# [~] v0.1 implementation → [✓] v0.2.0 released YYYY-MM-DD
```

- [ ] `AGENTS.md §1` phase gate updated
- [ ] Status line shows v0.2.0 released

---

## Step 9: Final Governance Check

```powershell
# Run all governance scripts one final time on the tagged state
.\.venv\Scripts\python.exe scripts/check_vocabulary.py
.\.venv\Scripts\python.exe scripts/check_pinning.py
.\.venv\Scripts\python.exe scripts/loc_budget.py
.\.venv\Scripts\python.exe scripts/dagster_leak_check.py
.\.venv\Scripts\python.exe scripts/check_error_codes.py
.\.venv\Scripts\python.exe scripts/check_api_stability.py
.\.venv\Scripts\python.exe scripts/check_licenses.py
.\.venv\Scripts\python.exe scripts/check_layering.py
```

- [ ] All 8 scripts EXIT 0 on the final version-bumped state

---

## Step 10: Release Tag — FOUNDER GATE

**STOP HERE. Founder approval required before tagging.**

Present to founder:
1. E2E report summary (from Step 4)
2. LOC count (from governance)
3. Any open SKIP scenarios (document why)
4. Confirmed: all hard gates passed

```
Present:
  "Release candidate v0.2.0 ready.
   E2E: A=100% / B=X% / C=100% / H=100% / I=100%
   LOC: <N> / 8,000 (GREEN)
   Governance: 8/8 PASS
   Open skips: <list>
   
   Ready to tag? Founder: git tag v0.2.0 && git push origin v0.2.0"
```

- [ ] Founder reviewed and approved
- [ ] Founder creates tag: `git tag v0.2.0 && git push origin v0.2.0`

---

## Step 11: Post-Tag Actions (~15 min)

```powershell
# CI auto-runs on tag push per .github/workflows/release.yml
# Monitor CI run for publish success

# GitHub Release is automated by .github/workflows/release.yml:
# gh release view v0.2.0 --repo nucleus-data/nucleus
# Fallback only if the workflow completed but no release exists:
# gh release create v0.2.0 --repo nucleus-data/nucleus --title "Nucleus v0.2.0" --notes-file docs/release/v0.2.0_RELEASE_NOTES.md

# Announce on:
# - https://nucleus-data.github.io/nucleus/ (update "Latest" badge once Pages is enabled)
# - GitHub Discussions (announcement post)
# - PoC #5 external testers (notify of new release to test against)
```

- [ ] CI release workflow completed (green)
- [ ] PyPI package published (`pip install nucleus-data==0.2.0` works)
- [ ] GitHub Release created with CHANGELOG excerpt
- [ ] PoC #5 external testers notified

---

## Rollback Procedure

If any hard gate fails post-tag:

```powershell
# 1. Delete local tag
git tag -d v0.2.0

# 2. Delete remote tag
git push --delete origin v0.2.0

# 3. PyPI yank (if published)
# twine upload --yank nucleus-0.2.0 (non-destructive; users with pin are unaffected)
# OR: contact PyPI support for emergency removal

# 4. Fix the blocking issue; re-run from Step 4

# 5. Create new tag (do NOT reuse v0.2.0 if PyPI was published)
# Use v0.2.1 for the fixed release
```

---

## Appendix: Quick Command Reference

```powershell
# Full governance check
ForEach ($s in @("check_vocabulary","check_pinning","loc_budget","dagster_leak_check",
                  "check_error_codes","check_api_stability","check_licenses","check_layering")) {
  Write-Host "--- $s ---"
  .\.venv\Scripts\python.exe "scripts/$s.py"
}

# Quick E2E (no Docker)
.\.venv\Scripts\python.exe scripts/release_e2e/e2e_full.py --suite A,I,H,K

# Full E2E with JSON output
.\.venv\Scripts\python.exe scripts/release_e2e/e2e_full.py --suite all --output docs/release/final_e2e.json

# Chaos test (J1 + J2 only, no Docker needed)
.\.venv\Scripts\python.exe scripts/release_e2e/run_chaos.py --scenario J1
.\.venv\Scripts\python.exe scripts/release_e2e/run_chaos.py --scenario J2

# Release smoke tests (immediately runnable subset)
.\.venv\Scripts\python.exe -m pytest tests/release_e2e/ -m "not integration and not slow" -v

# Full test suite (excluding release_e2e)
.\.venv\Scripts\python.exe -m pytest tests/ -q --ignore=tests/release_e2e

# Beachhead E2E baseline
.\.venv\Scripts\python.exe scripts/beachhead_e2e.py
```

---

*Checklist created by release-planner builder 2026-05-15. Foreground completes this sequentially after all Wave-1 builders return. No step may be skipped; hard gates are release blockers per `AGENTS.md §9`.*
