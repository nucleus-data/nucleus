# Nucleus v0.2.0 — Packaging Completeness Audit

> *Status table for every artifact a perfect-public-release needs. Three columns: `Artifact / Status / Path or Action`. Status values: **PRESENT** (shipped), **MISSING** (gap → follow-up TODO), **PARTIAL** (exists but incomplete), **FOUNDER-ONLY** (cannot be completed without the founder). Last refreshed 2026-05-15 alongside the v0.2.0 close-out batch.*
>
> **Companion docs**: [`v0.2.0_RELEASE_READINESS.md`](v0.2.0_RELEASE_READINESS.md) (32-item phase-gated checklist), [`v0.2_FOUNDER_CLOSE_CHECKLIST.md`](v0.2_FOUNDER_CLOSE_CHECKLIST.md) (master close-out runbook), [`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) (launch-day top-to-bottom).
>
> **Honesty contract** per [`AGENTS.md`](../../../AGENTS.md) §10.8: anything marked PRESENT is verifiable by a `Test-Path` on Windows or `[ -f ... ]` on POSIX. MISSING / PARTIAL items have explicit follow-up TODOs.

---

## Quick summary

| Section | PRESENT | PARTIAL | MISSING | FOUNDER-ONLY |
|---|---|---|---|---|
| 1. Source code | 12 | 0 | 0 | 0 |
| 2. Test coverage | 6 | 1 | 0 | 0 |
| 3. Documentation surface | 11 | 0 | 0 | 0 |
| 4. Release artifacts | 8 | 0 | 0 | 3 |
| 5. Marketing artifacts | 14 | 0 | 2 | 0 |
| 6. Community infrastructure | 11 | 0 | 0 | 0 |
| 7. Operations / handover | 5 | 0 | 0 | 0 |
| 8. Governance scripts | 11 | 0 | 0 | 0 |
| 9. Self-sustain infrastructure | 6 | 1 | 0 | 1 |
| 10. Founder-gated remaining items | 0 | 0 | 0 | 6 |
| **TOTAL** | **84** | **2** | **2** | **10** |

**Critical launch-day blockers**: ZERO PRESENT items pending. Two MISSING items are 60-sec demo MP4 and rendered architecture diagram — neither blocks PyPI publish; both improve the launch narrative. Ten FOUNDER-ONLY items are pre-mapped in [`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md).

---

## 1. Source code completeness

| Artifact | Status | Path / Action |
|---|---|---|
| `ctx` SDK (`copy_from`, `sql`, `read`, materialize) | PRESENT | [`src/nucleus/ctx/`](../../../src/nucleus/ctx/) |
| `@nucleus.asset`, `@nucleus.sql_asset`, `@nucleus.check`, `@nucleus.contract` decorators | PRESENT | [`src/nucleus/sdk/`](../../../src/nucleus/sdk/) |
| Asset Materialization Adapter (AMA) | PRESENT | [`src/nucleus/coordination/`](../../../src/nucleus/coordination/) |
| Error Translation Layer | PRESENT | [`src/nucleus/coordination/error_translation.py`](../../../src/nucleus/coordination/error_translation.py) |
| Native `ctx.sql` Jinja `{{ ref() }}` resolver | PRESENT | [`src/nucleus/ctx/sql.py`](../../../src/nucleus/ctx/) (~180 LOC, hard 2,500 LOC scope ceiling per v4.1 §5.6.0) |
| AI Copilot (chat) — opt-in `nucleus[ai]` | PRESENT | [`src/nucleus/intelligence/`](../../../src/nucleus/intelligence/) (wraps `litellm==1.83.14`) |
| Schema contracts (`@nucleus.contract`) | PRESENT | [`src/nucleus/sdk/contracts.py`](../../../src/nucleus/sdk/) |
| CLI (8 commands: init / up / down / run / ingest / query / chat / version) | PRESENT | [`src/nucleus/cli/`](../../../src/nucleus/cli/) (Subagent A wiring `list` for v0.2.x) |
| Workbench v0.3 (FastAPI + Vite/React) | PRESENT | [`src/nucleus/workbench/`](../../../src/nucleus/workbench/) |
| Active scheduling daemon + durable run ledger (Wave 2 P0-2) | PRESENT | [`src/nucleus/coordination/scheduling/`](../../../src/nucleus/coordination/) |
| Iceberg branch + tag CLI (ADR-028) | PRESENT | [`src/nucleus/cli/commands/snapshot.py`](../../../src/nucleus/cli/) |
| 7 source connectors via one `ctx.copy_from()` dispatcher | PRESENT | [`src/nucleus/ctx/connectors/`](../../../src/nucleus/ctx/) (Postgres, MySQL, SQLite, Snowflake, S3, GCS, filesystem) |

LOC at v0.2.0 ship: **~8,300 / 12,000 phase ceiling** (per `python scripts/loc_budget.py`). GREEN.

---

## 2. Test coverage

| Artifact | Status | Path / Action |
|---|---|---|
| Unit tests | PRESENT | [`tests/`](../../../tests/) — 850+ passing |
| Integration tests | PRESENT | [`tests/`](../../../tests/) — marked `@pytest.mark.integration` |
| Beachhead E2E (8 gates) | PRESENT | [`scripts/beachhead_e2e.py`](../../../scripts/beachhead_e2e.py) — 8/8 PASS on WSL 2026-05-14 |
| Chaos tests | PRESENT | [`tests/chaos/`](../../../tests/chaos/) + [`docs/release/chaos_test_results.md`](chaos_test_results.md) |
| Upgrade smoke tests | PRESENT | [`tests/upgrade_smoke/`](../../../tests/upgrade_smoke/) + [`scripts/upgrade_smoke.py`](../../../scripts/upgrade_smoke.py) |
| Benchmark suite + baseline | PRESENT | [`scripts/benchmarks/`](../../../scripts/benchmarks/) + [`docs/internal/benchmarks/2026-05-15_baseline.md`](../benchmarks/2026-05-15_baseline.md) — 5 benchmarks (B1–B5), 11 measured failures documented honestly |
| macOS native E2E coverage | PARTIAL | CI runs on `macos-latest` but zero external macOS testers in v0.1/v0.2. **Follow-up**: PoC #5 closes the gap. |

---

## 3. Documentation surface

| Artifact | Status | Path / Action |
|---|---|---|
| Landing page (`README.md`) | PRESENT | [`README.md`](../../../README.md) — patch proposed at [`launch_kit/README_HERO_PATCH.md`](launch_kit/README_HERO_PATCH.md); founder applies pre-launch |
| `START_HERE.md` entry point | PRESENT | [`docs/START_HERE.md`](../../START_HERE.md) — 8-way branch navigation |
| Quickstart (30-min beachhead path) | PRESENT | [`docs/onboarding/quickstart.md`](../../onboarding/quickstart.md) |
| Concepts (asset, materialization, snapshot, contract, check, catalog, lineage, schedule) | PRESENT | [`docs/site/concepts/`](../../site/concepts/) — 9 files via mkdocs |
| Cookbook (5 recipes + 4 production cookbooks: ai-copilot-setup, production-deployment, cloud-credentials, bi-connectivity) | PRESENT | [`docs/cookbook/`](../../cookbook/) + [`docs/site/cookbook/`](../../site/cookbook/) — 9 files at repo + 11 at site |
| CLI reference (per-command pages) | PRESENT | [`docs/site/cli-reference/`](../../site/cli-reference/) — 12 files (10 commands + index + `list` from Subagent A) |
| API reference (mkdocstrings auto-gen) | PRESENT | [`docs/site/api-reference/`](../../site/api-reference/) — `ctx` SDK, decorators, errors |
| Errors directory (NE-code reference) | PRESENT | [`docs/errors/`](../../errors/) — 16 NE-code remediation pages |
| Architecture v4.1 source of truth | PRESENT | [`docs/specs/nucleus_architecture_v4.1.md`](../../specs/nucleus_architecture_v4.1.md) at repo root |
| Public docs site (MkDocs Material) | PRESENT | [`mkdocs.yml`](../../../mkdocs.yml) → docs/site/; `mkdocs build --strict` exits 0 (verified 2026-05-15) |
| Roadmap (13 phase docs) | PRESENT | [`docs/roadmap/`](../../roadmap/) — overview + 7 phase docs + HANDOVER + non-goals + risks + FOLLOW_UPS + README |

---

## 4. Release artifacts

| Artifact | Status | Path / Action |
|---|---|---|
| `pyproject.toml` version `0.2.0` | PRESENT | [`pyproject.toml`](../../../pyproject.toml) |
| `CHANGELOG.md` `[0.2.0]` section | PRESENT | [`CHANGELOG.md`](../../../CHANGELOG.md) — dated 2026-05-15 |
| Release notes (curated body for workflow-created GitHub Release) | PRESENT | [`docs/release/v0.2.0_RELEASE_NOTES.md`](v0.2.0_RELEASE_NOTES.md) |
| Release readiness checklist | PRESENT | [`docs/release/v0.2.0_RELEASE_READINESS.md`](v0.2.0_RELEASE_READINESS.md) — 32 items |
| OIDC publish workflow | PRESENT | [`.github/workflows/release.yml`](../../../.github/workflows/release.yml) |
| Packaging recipes (brew, scoop, chocolatey) | PRESENT | [`packaging/`](../../../packaging/) — Homebrew formula, Scoop manifest, Chocolatey nuspec (drafts; founder publishes post-tag) |
| Demo project | PRESENT | [`examples/nucleus-demo-app/`](../../../examples/nucleus-demo-app/) — full bronze/silver/gold ELT |
| Public demo deploy plan | PRESENT | [`docs/release/public_demo_deploy_plan.md`](public_demo_deploy_plan.md) |
| **PyPI Trusted Publisher pre-registered** | FOUNDER-ONLY | Owner `nucleus-data`, repo `nucleus`, workflow `release.yml`, env `pypi` — see [`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) Phase 2 |
| **`v0.2.0` git tag push** | FOUNDER-ONLY | Per [`AGENTS.md`](../../../AGENTS.md) §3 — NEVER unilateral. Runbook Phase 3 |
| **GitHub Release page** | FOUNDER-ONLY | Auto-created from CHANGELOG by `release.yml`, but founder reviews/edits per Runbook Phase 4 |

---

## 5. Marketing artifacts

| Artifact | Status | Path / Action |
|---|---|---|
| README hero patch proposal | PRESENT | [`docs/release/launch_kit/README_HERO_PATCH.md`](launch_kit/README_HERO_PATCH.md) |
| 60-second demo SCRIPT | PRESENT | [`docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md`](launch_kit/60_SECOND_DEMO_SCRIPT.md) |
| **60-second demo MP4 recording** | MISSING | **Follow-up**: founder records per script Phase 0 ([`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md)). Target: `assets/demos/v0.2/launch_60s.mp4` + `.srt`. ~10 min effort. |
| **Architecture diagram (rendered SVG/PNG)** | MISSING | **Follow-up**: render the 5-layer model + wrapped engines as `assets/architecture/v4.1_five_layers.svg`. Text-form lives in `docs/specs/nucleus_architecture_v4.1.md` §3. ~30 min effort with mermaid. |
| WOW Moments inventory | PRESENT | [`docs/release/launch_kit/WOW_MOMENTS.md`](launch_kit/WOW_MOMENTS.md) — 7 priority-ordered WOWs + asset gap matrix |
| Show HN headlines (A/B variants) | PRESENT | [`docs/release/launch_kit/SHOW_HN_HEADLINES.md`](launch_kit/SHOW_HN_HEADLINES.md) |
| HN post body | PRESENT | [`docs/release/launch_kit/hn_post.md`](launch_kit/hn_post.md) |
| HN / Reddit FAQ scaffolding | PRESENT | [`docs/release/launch_kit/HN_REDDIT_FAQ.md`](launch_kit/HN_REDDIT_FAQ.md) |
| Reddit r/dataengineering post | PRESENT | [`docs/release/launch_kit/reddit_r_dataengineering.md`](launch_kit/reddit_r_dataengineering.md) |
| LinkedIn post | PRESENT | [`docs/release/launch_kit/linkedin_post.md`](launch_kit/linkedin_post.md) |
| Twitter / X thread (12 tweets) | PRESENT | [`docs/release/launch_kit/twitter_thread.md`](launch_kit/twitter_thread.md) |
| Social posts (compact) | PRESENT | [`docs/release/launch_kit/SOCIAL_POSTS.md`](launch_kit/SOCIAL_POSTS.md) |
| Blog post (dev.to / Hashnode / Medium) | PRESENT | [`docs/release/launch_kit/blog_post_launch.md`](launch_kit/blog_post_launch.md) |
| Press kit | PRESENT | [`docs/release/launch_kit/press_kit.md`](launch_kit/press_kit.md) |
| Launch FAQ (long form) | PRESENT | [`docs/release/launch_kit/faq_launch.md`](launch_kit/faq_launch.md) |
| Comparison vs Databricks/Snowflake | PRESENT | [`docs/release/launch_kit/comparison_vs_databricks_snowflake.md`](launch_kit/comparison_vs_databricks_snowflake.md) |
| Launch-day timeline (T+0 → T+24h) | PRESENT | [`docs/release/launch_kit/LAUNCH_DAY_TIMELINE.md`](launch_kit/LAUNCH_DAY_TIMELINE.md) |

---

## 6. Community infrastructure

| Artifact | Status | Path / Action |
|---|---|---|
| `CONTRIBUTING.md` | PRESENT | [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) at repo root + [`docs/site/community/contributing.md`](../../site/community/contributing.md) |
| `CODE_OF_CONDUCT.md` | PRESENT | [`CODE_OF_CONDUCT.md`](../../../CODE_OF_CONDUCT.md) |
| `SECURITY.md` | PRESENT | [`SECURITY.md`](../../../SECURITY.md) + [`docs/site/community/security.md`](../../site/community/security.md) |
| `SUPPORT.md` | PRESENT | [`SUPPORT.md`](../../../SUPPORT.md) + [`docs/site/community/support.md`](../../site/community/support.md) |
| `GOVERNANCE.md` | PRESENT | [`GOVERNANCE.md`](../../../GOVERNANCE.md) |
| `MAINTAINERS.md` | PRESENT | [`MAINTAINERS.md`](../../../MAINTAINERS.md) |
| `.github/FUNDING.yml` | PRESENT | [`.github/FUNDING.yml`](../../../.github/FUNDING.yml) — founder fills handle pre-launch |
| `.github/ISSUE_TEMPLATE/` (bug / feature / ADR / wrap-request) | PRESENT | [`.github/ISSUE_TEMPLATE/`](../../../.github/ISSUE_TEMPLATE/) — 4 templates + `config.yml` |
| `.github/PULL_REQUEST_TEMPLATE.md` | PRESENT | [`.github/PULL_REQUEST_TEMPLATE.md`](../../../.github/PULL_REQUEST_TEMPLATE.md) |
| `.github/CODEOWNERS` | PRESENT | [`.github/CODEOWNERS`](../../../.github/CODEOWNERS) |
| `.github/dependabot.yml` | PRESENT | [`.github/dependabot.yml`](../../../.github/dependabot.yml) |

---

## 7. Operations / handover

| Artifact | Status | Path / Action |
|---|---|---|
| Solo-founder long-term `HANDOVER.md` | PRESENT | [`docs/HANDOVER.md`](../../HANDOVER.md) — daily/weekly/monthly/quarterly/annual + 8 crisis playbooks + AI workflow + OSS economics |
| `START_HERE.md` super-context entry | PRESENT | [`docs/START_HERE.md`](../../START_HERE.md) |
| Day-0 onboarding HANDOVER | PRESENT | [`docs/roadmap/HANDOVER.md`](../../roadmap/HANDOVER.md) |
| Launch-day Founder runbook | PRESENT | [`docs/release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) |
| Drift Detection Prompt | PRESENT | [`AGENTS.md`](../../../AGENTS.md) §11.11 + [`docs/HANDOVER.md`](../../HANDOVER.md) §4.1 |

---

## 8. Governance scripts (11/11 in CI)

| Script | Status | Purpose |
|---|---|---|
| [`scripts/check_vocabulary.py`](../../../scripts/check_vocabulary.py) | PRESENT | Vocabulary discipline per [`AGENTS.md`](../../../AGENTS.md) §7 |
| [`scripts/check_pinning.py`](../../../scripts/check_pinning.py) | PRESENT | All runtime deps exactly pinned per Constraint #11 |
| [`scripts/loc_budget.py`](../../../scripts/loc_budget.py) | PRESENT | `src/nucleus/` under phase ceiling |
| [`scripts/dagster_leak_check.py`](../../../scripts/dagster_leak_check.py) | PRESENT | No external classnames in user-facing strings |
| [`scripts/check_error_codes.py`](../../../scripts/check_error_codes.py) | PRESENT | NE-code uniqueness + ADR-006 mapping |
| [`scripts/check_api_stability.py`](../../../scripts/check_api_stability.py) | PRESENT | Tier-frozen surface unchanged |
| [`scripts/check_layering.py`](../../../scripts/check_layering.py) | PRESENT | No cross-layer imports |
| [`scripts/check_licenses.py`](../../../scripts/check_licenses.py) | PRESENT | Only GREEN + YELLOW-with-boundary deps |
| [`scripts/check_install_size.py`](../../../scripts/check_install_size.py) | PRESENT | Core install footprint guard |
| [`scripts/check_lazy_imports.py`](../../../scripts/check_lazy_imports.py) | PRESENT | CLI cold-boot import discipline |
| [`scripts/check_changelog.py`](../../../scripts/check_changelog.py) | PRESENT | Release-notes hygiene |

Plus runtime-quality scripts (not pre-merge blockers but invoked in CI on dep-bump triggers): [`scripts/upgrade_smoke.py`](../../../scripts/upgrade_smoke.py), [`scripts/benchmark_regression.py`](../../../scripts/benchmark_regression.py), [`scripts/beachhead_e2e.py`](../../../scripts/beachhead_e2e.py), [`scripts/check_perf_budget.py`](../../../scripts/check_perf_budget.py).

---

## 9. Infrastructure for self-sustain

| Artifact | Status | Path / Action |
|---|---|---|
| Dependabot config (single-component-per-PR) | PRESENT | [`.github/dependabot.yml`](../../../.github/dependabot.yml) |
| CI workflow (lint / governance / test matrix / upgrade-smoke / beachhead-E2E) | PRESENT | [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) |
| Security workflow (pip-audit + CodeQL) | PRESENT | [`.github/workflows/security.yml`](../../../.github/workflows/security.yml) + [`.github/workflows/codeql.yml`](../../../.github/workflows/codeql.yml) |
| Release workflow (OIDC publish) | PRESENT | [`.github/workflows/release.yml`](../../../.github/workflows/release.yml) |
| Docs workflow (mkdocs build + GitHub Pages deploy) | PRESENT | [`.github/workflows/docs.yml`](../../../.github/workflows/docs.yml) |
| Stale-issue workflow | PRESENT | [`.github/workflows/stale.yml`](../../../.github/workflows/stale.yml) |
| Compatibility matrix | PARTIAL | [`docs/compatibility.md`](../../compatibility.md) exists; founder updates each quarterly upgrade audit per [`AGENTS.md`](../../../AGENTS.md) §11.13 |
| **Branch protection on `main`** | FOUNDER-ONLY | Ruleset at `.scratch/main_ruleset.json` applied after founder upgrades to GitHub Pro/Team per Runbook Phase 1 |

---

## 10. Founder-gated remaining items (cross-ref to runbook)

These items **cannot** be completed without the founder. They are mapped 1:1 to [`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) phases.

| Item | Phase in runbook | Estimate |
|---|---|---|
| Enable Code Scanning (default setup) | Phase 1 | 3 min |
| Apply main branch protection | Phase 1 (optional, paid) | 1 min or skip |
| Repo description + topics set | Phase 1 | 1 min |
| Register PyPI Trusted Publisher | Phase 2 | 5 min |
| Tag + push `v0.2.0` (irreversible) | Phase 3 | 1 min + 7 min wait for publish |
| Publish GitHub Release | Phase 4 | 5 min |
| Record 60-second demo video | Phase 0 | 4 min + retakes |
| Show HN submission | Phase 5 (T+0) | 3 min |
| Twitter / LinkedIn / Reddit cross-post | Phase 5 (T+5–T+30) | 13 min |
| PoC #5 round-2 tester outreach | Phase 5 (T+10) | 5 min |

Total founder time: ~2 h pre-launch + 4–8 h launch-day monitoring.

---

## Recommended order of follow-up

1. **MISSING #1** — Record the 60-second demo MP4 (HIGH priority, blocks README hero patch + Twitter thread tweet 1). Founder, ~10 min. Phase 0 of [`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md).
2. **PARTIAL #1** — macOS native testing — closed by PoC #5 external testers. Track at [`docs/internal/poc/p5_beachhead/AGGREGATE_FINDINGS.md`](../poc/p5_beachhead/) (placeholder).
3. **MISSING #2** — Render the 5-layer architecture SVG (MEDIUM priority, improves README + docs landing). ~30 min with mermaid. Defer to v0.2.1 if it pushes launch.
4. **FOUNDER-ONLY** — Work the runbook top-to-bottom. Each item has explicit verification + rollback per runbook phase.

---

*This audit is the **complete** picture as of 2026-05-15 close-out. Future audits live alongside each new release: copy this file, version-suffix it (`PACKAGING_COMPLETENESS_AUDIT_v0.3.md`), update the table, and amend the introduction with the new release reference. Don't mutate this file post-launch — it's the v0.2.0 snapshot.*
