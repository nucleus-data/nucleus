# FOUNDER_ULTIMATE_SPRINT_RUNBOOK Gap Audit

*Cross-check of `docs/release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md` against the actual repo state and recent founder-action surface (2026-05-16). Companion to `docs/FOUNDER_ACTION_QUEUE.md` and `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md`. ASCII-only. Last updated 2026-05-15.*

> **One-line verdict**: the runbook is structurally correct and Phase-sequenced; six items are now demonstrably DONE on the repo, seven items are MISSING (mostly cross-references to launch-kit artifacts that landed after the runbook was written), and four items are STALE (point at filenames or framings that have since shifted). Proposed remedy: an **inline patch** rather than a full v2 file - the bones are right, the citations need refresh.

---

## Section A - Items in the runbook that are NOW DONE (verified against repo)

| # | Runbook reference | Empirical check (`gh` / `git`) | Status |
|---|---|---|---|
| 1 | Phase 2 step 1: PyPI account + 2FA | `gh api repos/nucleus-data/nucleus/environments` shows `pypi` env created `2026-05-15T19:00:33Z` | DONE (founder created the env; trusted publisher binding still TBD per Section B-2) |
| 2 | Phase 1 step 4: Repo description + topics | `gh repo view nucleus-data/nucleus` shows description set and `data-platform / iceberg / duckdb / polars / ai-assisted` topics | DONE (auto-applied by parallel worker) |
| 3 | Phase 0: Concurrent worker artifact `v0.2.0_RELEASE_NOTES.md` | File exists in working tree as untracked | LANDED (in working tree, not yet committed - founder commit batch pending) |
| 4 | Phase 0: Concurrent worker artifact `v0.2.0_RELEASE_READINESS.md` | File exists in working tree as untracked | LANDED (in working tree, not yet committed) |
| 5 | Phase 1 step 1: Enable Code Scanning | Recent commit `cdfc09e ci(codeql): skip analyze job on private repos` confirms the CodeQL/Advanced-Security gating decision was made | RESOLVED INDIRECTLY (CodeQL skip on private; full Code Scanning blocked on visibility flip - see Section D-1) |
| 6 | Phase 6: `gh issue list` for triage | `hasIssuesEnabled=true`, `hasDiscussionsEnabled=true` | DONE (Issues and Discussions both ON) |

---

## Section B - Items MISSING from the runbook (should be added)

These are founder-gated steps that exist on the surface but are NOT yet anywhere in the runbook's seven phases.

### B-1. Repo visibility decision (PRIVATE -> PUBLIC) - PRE-Phase 1 blocker

- **Empirical fact**: `gh repo view nucleus-data/nucleus --json visibility,isPrivate` returns `"PRIVATE", true`. `has_pages=false`. `allow_auto_merge=false`.
- **Implication**: on the GitHub free tier, branch protection on `main` (Phase 1 step 3) AND GitHub Pages docs site (Phase 0 step 5) BOTH require either (a) repo to flip to PUBLIC or (b) GitHub Pro. The runbook treats branch protection as `(Optional, paid)` but does not surface this as a launch-day prerequisite for the docs site.
- **Fix needed**: insert a NEW Phase 0 step 0 - "Decide repo visibility (PRIVATE -> PUBLIC) before launch day" with the trade-off (Public = free Pages + free branch protection + open-source signalling; Private + Pro = continuing internal review window at $4/mo, no Pages without paid add-on).

### B-2. PyPI Trusted Publisher binding verification (Phase 2 has the registration step but not the verification)

- **Empirical fact**: `gh api repos/nucleus-data/nucleus/environments/pypi` returns `"protection_rules": []` and `"deployment_branch_policy": null`. The env exists; the binding to `https://pypi.org/manage/account/publishing/` has not been verified by a workflow run.
- **Fix needed**: add a Phase 2 step 2.5 - "Smoke-check the OIDC binding with a dry-run workflow trigger" - either by manually invoking the release workflow on a throwaway branch with `dry_run: true` or by reading the workflow file and confirming the OIDC claims match (audience, repository, ref).

### B-3. Demo recording artifact trio (production handbook + checklist + asciinema cast)

- **Empirical fact**: today's docs commit adds three new artifacts:
  - `docs/release/launch_kit/DEMO_VIDEO_PRODUCTION.md` (production handbook)
  - `docs/release/launch_kit/DEMO_RECORDING_CHECKLIST.md` (founder pre-record checklist)
  - `docs/release/launch_kit/demo.cast` (asciinema source for the terminal-only path)
- **Fix needed**: Phase 0 step 4 ("Demo video recorded") currently references only `60_SECOND_DEMO_SCRIPT.md`. Update it to chain into the new trio so the founder reads the checklist first, executes per the production handbook, and falls back to the asciinema cast if the live recording is blocked.

### B-4. HEADLINE_AB_VARIANTS.md as Phase 5 fallback source

- **Empirical fact**: new `docs/release/launch_kit/HEADLINE_AB_VARIANTS.md` adds 5 alternative Show HN framings plus alt-channel rewrites for Twitter / LinkedIn / Reddit / dev.to.
- **Fix needed**: Phase 5 T+0 step currently says "fallback: title #1 from `hn_post.md`"; the new fallback chain is `SHOW_HN_HEADLINES.md` (top pick A1) -> `HEADLINE_AB_VARIANTS.md` V1/V3 (if A1 underperforms in first 30 min) -> `hn_post.md` title block (legacy fallback).

### B-5. Why-wrap-not-build pitch as HN-comment ammunition

- **Empirical fact**: new `docs/marketing/why_wrap_not_build.md` (645 words, 1 page) is the canonical comeback for the "this is just glue code" objection that the WOW_MOMENTS.md predicts will appear in the first 30 minutes of HN comments.
- **Fix needed**: add to Phase 5 T+30 min monitoring step under "Top-N comment scaffolding": "If a commenter says 'just glue code' or 'just a wrapper', link to `docs/marketing/why_wrap_not_build.md` instead of typing the argument from scratch."

### B-6. New launch-kit / release docs that landed as untracked

- **Empirical fact** (`git status` after recent worker waves): `docs/release/FIRST_7_DAYS_PLAYBOOK.md`, `docs/release/GO_NO_GO_CHECKLIST.md`, `docs/release/LAUNCH_RISK_REGISTER.md`, `docs/release/beachhead_e2e_evidence.md`, `docs/release/public_demo_deploy_plan.md`, plus 3 cookbook graduation recipes and ADR-041 (mode-2 hybrid compute dispatch).
- **Fix needed**: Phase 0 step 1 ("All 8 launch-kit artifacts present") should be expanded to a full sweep against the launch_kit dir; Phase 7 ("Post-launch") should link to `FIRST_7_DAYS_PLAYBOOK.md` as the next-7-days playbook; Phase 6 ("Watch + respond") should reference `LAUNCH_RISK_REGISTER.md` for hot-patch trigger conditions.

### B-7. PoC #5 compensation + Calendly link pre-flight

- **Empirical fact**: `docs/poc/p5_beachhead/RECRUITMENT_PLAN.md` still has `<TBD>` placeholders for compensation and Calendly link per the v0.2_FOUNDER_CLOSE_CHECKLIST.md cross-reference. Phase 0 step 6 currently sweeps for `<ORG>|<DOCS_URL>|CALENDLY_LINK_HERE|\[BOOK_30MIN_HERE\]` but does NOT include the actual placeholder tokens in the recruitment plan.
- **Fix needed**: extend the rg pattern to include `<TBD>` and `compensation:` and `calendly\\.com/<you>` so the Phase 0 sweep catches the recruitment-plan placeholders too.

---

## Section C - Items in the runbook that are STALE

### C-1. "All 8 launch-kit artifacts present" check undercounts by ~7 files

- **Stale text** (Phase 0 step 2):

  ```powershell
  @("hn_post","reddit_r_dataengineering","linkedin_post","twitter_thread","blog_post_launch","press_kit","faq_launch","comparison_vs_databricks_snowflake")
  ```

- **Reality** (`ls docs/release/launch_kit/`): launch kit dir has 19 files including the 8 listed plus `SHOW_HN_HEADLINES`, `SOCIAL_POSTS`, `HN_REDDIT_FAQ`, `LAUNCH_DAY_TIMELINE`, `60_SECOND_DEMO_SCRIPT`, `README_HERO_PATCH`, `WOW_MOMENTS`, and the three new ones from this commit (`HEADLINE_AB_VARIANTS`, `DEMO_VIDEO_PRODUCTION`, `DEMO_RECORDING_CHECKLIST`) plus `demo.cast`.
- **Fix proposed**: replace the hardcoded list with a directory glob.

### C-2. Phase 5 T+0 inline Show HN title disagrees with the file's top recommendation

- **Stale text** (Phase 5 T+0):

  ```
  Title: Show HN: Nucleus - local-first Iceberg pipelines from a laptop, in <30 minutes
  ```

- **Reality**: `SHOW_HN_HEADLINES.md` section "Top recommendation" picks A1: `Show HN: Nucleus - local-first data platform that graduates to Databricks` (composite score 27/30, cited as the differentiating wedge).
- **Fix proposed**: cite the SHOW_HN_HEADLINES.md A1 recommendation by reference rather than inlining a stale string.

### C-3. Phase 6 demo URL load-watch points at `try.nucleus.dev` without DNS verification

- **Stale text** (Phase 6): `curl.exe -fsSI https://try.nucleus.dev`
- **Reality**: `public_demo_deploy_plan.md` is one of the untracked files; the `try.nucleus.dev` domain is aspirational per the deploy plan. No DNS resolution check exists in any worker output.
- **Fix proposed**: gate the demo URL load-watch behind a Phase 0 verification step ("If `try.nucleus.dev` does not resolve, drop this step and rely on docs site + repo as the canonical entry points").

### C-4. Phase 4 GitHub Release block was already mid-edited (auto-vs-manual flow)

- **Stale text** (HEAD version) calls `gh release create` for both branches of the `if`.
- **Reality** (unstaged diff in working tree): the founder-applied edit clarifies that `release.yml` auto-creates the release after PyPI publish; manual `gh release create` is fallback only. The edit is unstaged at audit time.
- **Fix proposed**: confirm the auto-release flow is the canonical Phase 4 path before commit, and add a fallback explicit-create command for the 404-after-workflow-success edge case.

---

## Section D - Net new founder actions surfaced by this audit

Surface for `FOUNDER_ACTION_QUEUE.md` section 0.4 (post-launch consolidation). Each item is founder-only (zero AI-completable):

1. **Decide repo visibility (PRIVATE -> PUBLIC)** before Phase 1 - pre-launch blocker for Pages and branch protection on the free tier.
2. **Smoke-test the PyPI OIDC binding** before pushing the v0.2.0 tag - the env is created but the first workflow run will be the validation; use a dry-run trigger if possible to avoid burning the tag on a misconfigured binding.
3. **Record the 60-second demo** per the new trio (`DEMO_RECORDING_CHECKLIST.md` -> `DEMO_VIDEO_PRODUCTION.md` -> `demo.cast` fallback) - the production handbook expands the previous shot list and the checklist surfaces the pre-flight hygiene that has been costing the founder retakes.
4. **Update Phase 0 launch-kit artifact sweep** to a directory glob so the check does not silently miss the 7 files that landed after the runbook was first authored.
5. **Replace inlined Show HN title with a reference** to `SHOW_HN_HEADLINES.md` section "Top recommendation" so the canonical pick stays in one file.
6. **Verify `try.nucleus.dev` DNS** before launch day; if not live, remove the Phase 6 load-watch step or replace with the docs-site URL.
7. **Add a Phase 5 T+30 min line** that links the new `docs/marketing/why_wrap_not_build.md` as the canonical reply to the "just glue code" objection - this is the founder-facing version of the "WHY THIS VARIANT" rationale shipped in HEADLINE_AB_VARIANTS.md V2 (technical-flex).

---

## Section E - Final amended runbook: inline patch (recommended) over v2 file

The runbook bones are right. A full v2 file would create a maintenance fork. The cleaner remedy is the inline patch below, ready to apply with a single `git apply`-style edit (the founder applies; this file is the spec).

> **Note**: the patch below is presented as a list of section-anchored edits rather than a `unified-diff` block, because the runbook file is already mid-edited in the working tree (Phase 4 auto-release flow). A unified diff would conflict; the section-anchored edits below let the founder review and apply each one independently.

### Patch 1 - Insert NEW Phase 0 step 0 (BEFORE the existing step 1)

Anchor: immediately under the heading `## Phase 0 - Final pre-flight check (15 min)`

```markdown
- [ ] **Decide repo visibility for launch day** - PRIVATE today; PUBLIC required for free GitHub Pages + free branch protection on `main`, OR keep PRIVATE + buy GitHub Pro ($4/mo). _(5 min decision; flip command if PUBLIC chosen)_

  ```powershell
  gh repo view nucleus-data/nucleus --json visibility,isPrivate,hasIssuesEnabled
  # If flipping to PUBLIC:
  gh repo edit nucleus-data/nucleus --visibility public --accept-visibility-change-consequences
  ```
  Expected after flip: `visibility=PUBLIC`. Pages and branch-protection-without-Pro both unblocked.
```

### Patch 2 - Replace Phase 0 step 1 hardcoded list with a glob

Anchor: the `@("hn_post"...)` PowerShell block under "All 8 launch-kit artifacts present at `docs/release/launch_kit/`."

Replace with:

```powershell
Get-ChildItem docs/release/launch_kit/*.md docs/release/launch_kit/*.cast | Sort-Object Name | ForEach-Object { "$($_.Name): $(if ($_.Length -gt 0) {'OK'} else {'EMPTY'})" }
```

Expected: at least 18 lines, every line ending `OK`.

### Patch 3 - Extend Phase 0 step 6 placeholder sweep

Anchor: the `rg -n "<ORG>|<DOCS_URL>|CALENDLY_LINK_HERE|\[BOOK_30MIN_HERE\]"` block.

Replace with:

```powershell
rg -n "<ORG>|<DOCS_URL>|CALENDLY_LINK_HERE|\[BOOK_30MIN_HERE\]|<TBD>|compensation: \\\$<|calendly\.com/<you>" docs/release/launch_kit/ docs/poc/p5_beachhead/
```

Expected: 0 hits.

### Patch 4 - Add Phase 2 step 2.5: OIDC binding smoke-test

Anchor: after Phase 2 step 2 (Register Trusted Publisher).

```markdown
- [ ] **Smoke-check the OIDC binding** before tagging - the env is created, but the first workflow run is the only validation. If you have a `dry_run` input on `release.yml`, trigger it manually now. Otherwise read `.github/workflows/release.yml` and confirm `permissions.id-token: write` and `environment: pypi` are both present. _(5 min)_

  ```powershell
  gh workflow view release.yml --repo nucleus-data/nucleus
  rg "id-token|environment:" .github/workflows/release.yml
  ```
  Expected: both lines present. If neither, the OIDC publish will fail with a non-obvious error - fix before Phase 3.
```

### Patch 5 - Update Phase 0 step 4: demo recording chain

Anchor: the existing "Demo video recorded" line under Phase 0.

Replace with:

```markdown
- [ ] **Demo video recorded** following the chain `DEMO_RECORDING_CHECKLIST.md` (pre-flight) -> `DEMO_VIDEO_PRODUCTION.md` (shot list + voiceover) -> `60_SECOND_DEMO_SCRIPT.md` (editorial source). Fallback if live recording is blocked: ship the asciinema cast at `docs/release/launch_kit/demo.cast` and update README to embed `<asciinema-player>` instead of `<video>`. Upload MP4 to YouTube **unlisted** first. _(60-90 min including retakes)_
```

### Patch 6 - Replace Phase 5 T+0 inline title

Anchor: the line `Title: Show HN: Nucleus - local-first Iceberg pipelines from a laptop, in <30 minutes`.

Replace with:

```
Title: <load from docs/release/launch_kit/SHOW_HN_HEADLINES.md section "Top recommendation" - currently A1: "Show HN: Nucleus - local-first data platform that graduates to Databricks">
URL:   https://github.com/nucleus-data/nucleus
```

### Patch 7 - Add Phase 5 T+30 min comeback line

Anchor: under the existing T+30 min HN monitoring item.

```markdown
- [ ] **"Just glue code" comeback** ready in the clipboard: paste a one-line summary of `docs/marketing/why_wrap_not_build.md` (the 8,484 LOC vs ~1.2M LOC ratio is the lead) and link the doc directly. Do NOT type the leverage-math argument from scratch in a comment - the canonical wording is in the file.
```

### Patch 8 - Add Phase 6 hot-patch reference to LAUNCH_RISK_REGISTER

Anchor: the existing "Hot-patch protocol" item.

Append:

```markdown
  Before reaching for hotpatch: cross-check `docs/release/LAUNCH_RISK_REGISTER.md` for the pre-identified failure modes; if the surfacing issue matches a registered risk, apply the documented mitigation before improvising.
```

### Patch 9 - Add Phase 7 next-7-days handoff

Anchor: end of Phase 7.

Append:

```markdown
- [ ] **Next 7 days**: switch to `docs/release/FIRST_7_DAYS_PLAYBOOK.md` for the post-launch operating cadence (HN-comment refresh schedule, dependabot triage on a public repo, PoC #5 onboarding pace, v0.2.1 hot-patch protocol). _(linked, not duplicated, in this file.)_
```

---

## Verification commands the auditor ran

```powershell
# repo state
gh repo view nucleus-data/nucleus --json visibility,isPrivate,allowAutoMerge,hasIssuesEnabled,hasDiscussionsEnabled
gh api repos/nucleus-data/nucleus/environments
git ls-remote --tags origin
git log --oneline -5
git status --short | Sort-Object
gh api repos/nucleus-data/nucleus --jq '.allow_auto_merge, .has_pages, .default_branch'
ls docs/release/launch_kit/
```

Empirical findings reproducible at audit time (2026-05-15 23:45 UTC). If any value changes (visibility flip, tag push, pages enabled) re-run this audit before applying the patches.

---

## What this file is NOT

- NOT a v2 replacement for the runbook (the bones are right; inline patches above are the smaller remedy).
- NOT a list of ADRs (those live under `docs/decisions/`).
- NOT a substitute for the founder reading the runbook end-to-end on launch day.
- NOT a security audit (that is `docs/security/dependabot_alert_dispositions.md` and the GHAS gate).

---

*Refresh trigger: when the v0.2.0 tag is pushed and PyPI publish succeeds, replace this file's "Empirical findings" section with the post-launch state. Until then, work the inline patches top to bottom.*
