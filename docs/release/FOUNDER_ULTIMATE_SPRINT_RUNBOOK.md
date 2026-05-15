# Nucleus v0.2.0 — Founder Ultimate Sprint Runbook

> **Sole artifact** the founder reads on launch day. Strict top-to-bottom.
> Consolidates every founder-gated action across `FOUNDER_ACTION_QUEUE.md` §0/§0.2/§0.3, `v0.2_FOUNDER_CLOSE_CHECKLIST.md`, the launch kit, and concurrent worker outputs. Inline fallback where a concurrent artifact has not yet landed.
> Canonical org per `AGENTS.md` §1: `github.com/nucleus-data/nucleus` (legacy `mtoanng/nucleus` is the historical remote).

## TL;DR

- **Total founder hands-on time**: ~2 h pre-launch + 4–8 h launch-day monitoring.
- **Founder-only steps**: 34 (every `[ ]` below). 0 AI-completable.
- **Hard prerequisite for tag push**: PyPI OIDC trusted publisher registered (Phase 2). Without it, `release.yml` fails on first tag — register, then re-run the failed workflow (no re-tag needed).
- **Concurrent worker artifacts referenced** (assume they land; fall back inline if missing): `v0.2.0_RELEASE_NOTES.md`, `v0.2.0_RELEASE_READINESS.md`, `launch_kit/LAUNCH_DAY_TIMELINE.md`, `launch_kit/SOCIAL_POSTS.md`, `launch_kit/SHOW_HN_HEADLINES.md`, `launch_kit/HN_REDDIT_FAQ.md`, `launch_kit/60_SECOND_DEMO_SCRIPT.md`, `research/benchmarks_v0.2.0.md` (current empirical truth at `docs/benchmarks/2026-05-15_baseline.md`).

---

## Phase 0 — Final pre-flight check (15 min)

- [ ] **CI green** on `nucleus-data/nucleus@main` HEAD — all 14+ checks PASS. _(2 min)_

  ```powershell
  gh api repos/nucleus-data/nucleus/commits/main/check-runs --jq '.check_runs[] | "\(.conclusion)\t\(.name)"' | Sort-Object
  ```
  Expected: every line begins `success`. Any `failure` / `null` / `cancelled` → STOP, fix root cause.

- [ ] **All 8 launch-kit artifacts present** at `docs/release/launch_kit/`. _(1 min)_

  ```powershell
  @("hn_post","reddit_r_dataengineering","linkedin_post","twitter_thread","blog_post_launch","press_kit","faq_launch","comparison_vs_databricks_snowflake") | ForEach-Object { "$($_).md: $(Test-Path "docs/release/launch_kit/$($_).md")" }
  ```
  Expected: 8 lines, each ending `True`. Bonus concurrent files (`SOCIAL_POSTS.md`, `SHOW_HN_HEADLINES.md`, `HN_REDDIT_FAQ.md`, `60_SECOND_DEMO_SCRIPT.md`, `LAUNCH_DAY_TIMELINE.md`) are nice-to-have.

- [ ] **Benchmark numbers memorized** for HN-comment defense. _(5 min reading)_

  ```powershell
  rg -n "^(BLOCKER|MEDIUM|LOW)" docs/benchmarks/2026-05-15_baseline.md
  ```
  Memorize: boot ~2.1 s warm, 10 GB materialize peak 8.4 GB RAM, B4 concurrent-run race FAILS on Windows / PASSES on Linux+WSL. Lead message for HN: "honest baseline at `docs/benchmarks/`; 11 measured gaps vs aspirational targets; v0.3 closes them; numbers published before launch, not after."

- [ ] **Demo video recorded** following `60_SECOND_DEMO_SCRIPT.md` (fallback: 8-command happy path from `docs/onboarding/quickstart.md`); upload to YouTube **unlisted** first. _(4 min)_

  ```powershell
  Start-Process "https://www.youtube.com/upload"
  ```
  Expected: first frame shows `pip install nucleus`, last frame shows `nucleus query` returning rows.

- [ ] **`try.nucleus.dev` (or fallback docs landing) deployed and reachable** from incognito. _(2 min)_

  ```powershell
  curl.exe -fsSI https://try.nucleus.dev | Select-String -Pattern "HTTP/.*200|HTTP/.*30[12]"
  ```
  Expected: `200` or `301/302`. Fallback if not deployed: docs-only landing at `https://nucleus-data.github.io/nucleus/`.

- [ ] **All social-post drafts personalized** (no placeholders left). _(1 min)_

  ```powershell
  rg -n "<ORG>|<DOCS_URL>|CALENDLY_LINK_HERE|\[BOOK_30MIN_HERE\]" docs/release/launch_kit/
  ```
  Expected: 0 hits.

---

## Phase 1 — Repo settings (10 min)

- [ ] **Enable Code Scanning** (default setup) at `https://github.com/nucleus-data/nucleus/settings/security_analysis`. _(3 min)_

  ```powershell
  Start-Process "https://github.com/nucleus-data/nucleus/settings/security_analysis"
  ```
  Private repos require GH Pro/Team; public is free.

- [ ] **Verify Dependabot triage** per `FOUNDER_ACTION_QUEUE.md` §0.2 — close PRs failing CI; merge #6 / #7 if green. _(5 min)_

  ```powershell
  gh pr list --repo nucleus-data/nucleus --author "app/dependabot" --state open --json number,title,statusCheckRollup --jq '.[] | "PR #\(.number): \(.title) — \(.statusCheckRollup[0].conclusion // "pending")"'
  ```
  Expected: ≤2 open Dependabot PRs, all green or labeled `needs-adr`.

- [ ] **(Optional, paid)** Apply `main` branch protection from `.scratch/main_ruleset.json` — requires GH Pro/Team. _(1 min or skip)_

  ```powershell
  gh api -X PUT "repos/nucleus-data/nucleus/rules/main" --input .scratch/main_ruleset.json
  ```
  Skip if budget unresolved; tracked as deferred work in `FOUNDER_ACTION_QUEUE.md` §0.3.

- [ ] **Repo description + topics set** for discoverability. _(1 min)_

  ```powershell
  gh repo edit nucleus-data/nucleus --description "Ship data products from a laptop — local-first Python SDK + CLI for Iceberg-native pipelines" --add-topic data-platform --add-topic iceberg --add-topic duckdb --add-topic polars --add-topic ai-assisted
  ```

---

## Phase 2 — PyPI prep (15 min) — HARD PREREQUISITE for Phase 3

- [ ] **Sign in** to `https://pypi.org` (create account if first time; enable 2FA — PyPI requires it for maintainers). _(5 min)_

- [ ] **Register Trusted Publisher** at `https://pypi.org/manage/account/publishing/` with these exact values (must match `.github/workflows/release.yml`): _(5 min)_

  | Field | Value |
  |---|---|
  | PyPI project name | `nucleus` |
  | Owner | `nucleus-data` |
  | Repository | `nucleus` |
  | Workflow filename | `release.yml` |
  | Environment | `pypi` |

  Per `v0.2_FOUNDER_CLOSE_CHECKLIST.md` §4.6 + ADR-022 §"PyPI OIDC publish".

- [ ] **Pre-flight install attempt** in a clean venv — must FAIL (confirms publish target is correct, artifact does not yet exist). _(3 min)_

  ```powershell
  python -m venv .venv-pypi-preflight; .\.venv-pypi-preflight\Scripts\Activate.ps1; pip install nucleus==0.2.0; deactivate; Remove-Item -Recurse -Force .venv-pypi-preflight
  ```
  Expected: `ERROR: Could not find a version that satisfies the requirement nucleus==0.2.0`.

- [ ] **(Optional) Reserve PyPI namespace** if `nucleus` is unexpectedly taken — fallback `nucleus-data`. _(2 min or skip)_

  ```powershell
  curl.exe -fsSI https://pypi.org/project/nucleus/ | Select-String -Pattern "HTTP/"
  ```
  If 200 → name taken; edit `pyproject.toml` `[project].name = "nucleus-data"` and retag.

---

## Phase 3 — Tag + publish (5 min) — IRREVERSIBLE ONCE PYPI PUBLISH SUCCEEDS

- [ ] **Verify HEAD** is the release-bundle commit and `pyproject.toml` is at `0.2.0`. _(1 min)_

  ```powershell
  git log -1 --format='%h %s' main; rg "^version = " pyproject.toml
  ```
  Expected: HEAD is the most recent close-out batch commit; version reads `version = "0.2.0"`.

- [ ] **Tag-corruption recovery** if local `v0.1.0` / `v0.2.0` exist at wrong SHA (per `v0.2_FOUNDER_CLOSE_CHECKLIST.md` §1.6). _(2 min or skip)_

  ```powershell
  git tag --list -n9 v0.1.0 v0.2.0; git ls-remote --tags origin v0.1.0 v0.2.0
  # If wrong SHA detected, BEFORE the tag step run:
  git tag -d v0.1.0 v0.2.0 2>$null; git push --delete origin v0.1.0 2>$null
  ```

- [ ] **Create + push annotated tag** `v0.2.0` (full multi-line message in `v0.2_FOUNDER_CLOSE_CHECKLIST.md` §4.5; one-liner below is the minimum). _(1 min)_

  ```powershell
  git tag v0.2.0 -a -m "v0.2.0 — public release of Nucleus data platform"
  git push origin v0.2.0
  ```
  NEVER `--force`. NEVER `--no-verify`. If pre-push hook fails, fix and create a NEW commit before re-tagging.

- [ ] **Watch publish workflow** until it completes (~6–8 min). _(7 min wait)_

  ```powershell
  gh run watch --repo nucleus-data/nucleus --exit-status
  ```
  On failure with `OIDC: publisher not configured` → return to Phase 2 step #2, then **re-run the failed workflow** from the GitHub Actions UI (do NOT re-push the tag).

- [ ] **Verify wheels on PyPI**. _(1 min)_

  ```powershell
  curl.exe -fsSI https://pypi.org/project/nucleus/0.2.0/ | Select-String -Pattern "HTTP/.*200"
  ```

- [ ] **Test install in a clean venv** — the public smoke test. _(2 min)_

  ```powershell
  python -m venv .venv-pypi-smoke; .\.venv-pypi-smoke\Scripts\Activate.ps1; pip install "nucleus[core]==0.2.0"; nucleus version; deactivate; Remove-Item -Recurse -Force .venv-pypi-smoke
  ```
  Expected: `nucleus version` reports `0.2.0`.

---

## Phase 4 — GitHub Release verification (5 min)

- [ ] **Verify the workflow-created GitHub Release exists**. `.github/workflows/release.yml` auto-creates the release after PyPI publish; do **not** run `gh release create` on the normal path. _(2 min)_

  ```powershell
  gh release view v0.2.0 --repo nucleus-data/nucleus
  ```

- [ ] **Replace the auto-generated body with curated notes**, if the auto-generated CHANGELOG extract needs polish. Manual `gh release create` is allowed only as fallback if `gh release view` returns 404 after the workflow completed successfully. _(3 min)_

  ```powershell
  gh release edit v0.2.0 --repo nucleus-data/nucleus --notes-file docs/release/v0.2.0_RELEASE_NOTES.md
  Start-Process "https://github.com/nucleus-data/nucleus/releases/tag/v0.2.0"
  ```

---

## Phase 5 — Public announce (30 min, time-sequenced)

Follow `launch_kit/LAUNCH_DAY_TIMELINE.md` if present; otherwise the order below is canonical.

- [ ] **T+0 (06:00 PT or local equivalent, Tue or Wed for HN peak)** — Submit Show HN with the top headline from `SHOW_HN_HEADLINES.md` (fallback: title #1 from `hn_post.md`). _(3 min)_

  ```
  Title: Show HN: Nucleus — local-first Iceberg pipelines from a laptop, in <30 minutes
  URL:   https://github.com/nucleus-data/nucleus
  ```
  Pin the first-comment draft from `hn_post.md` line 33+ within 60 s of submission.

- [ ] **T+5 min** — Fire Twitter/X thread from `launch_kit/twitter_thread.md` (or `SOCIAL_POSTS.md`). _(3 min)_

  ```powershell
  Start-Process "docs/release/launch_kit/twitter_thread.md"
  ```

- [ ] **T+10 min** — Email PoC #5 round-2 testers using `docs/poc/p5_beachhead/OUTREACH_EMAIL_TEMPLATE.md`. Include the HN submission URL + PyPI install one-liner. _(5 min)_

- [ ] **T+30 min** — Cross-post: `r/dataengineering` (body: `reddit_r_dataengineering.md`), LinkedIn (`linkedin_post.md`), dev.to/Hashnode/Medium (`blog_post_launch.md`). _(10 min total)_

- [ ] **T+30 min onwards** — Monitor HN ranking; respond to top-N substantive comments using `HN_REDDIT_FAQ.md` (or fallback `hn_post.md` §"Anticipated HN questions") as scaffolding — **never paste verbatim, always tailor**. _(5 min initial; bleeds into Phase 6)_

  ```powershell
  Start-Process "https://news.ycombinator.com/from?site=github.com/nucleus-data"
  ```

---

## Phase 6 — Watch + respond (4–8 h ongoing)

- [ ] **Refresh HN every 15 min** for the first 4 h; reply within 30 min to the top 10 substantive comments. Scaffold from `HN_REDDIT_FAQ.md`; tailor each response. Do NOT vote-ring — HN auto-detects and shadow-bans. _(4 h windowed attention)_

  ```powershell
  Start-Process "https://news.ycombinator.com/newest"
  ```

- [ ] **GitHub Discussions / Issues** monitoring; triage new issues `triage` / `bug` / `discussion` within 1 h. _(30 min over the window)_

  ```powershell
  gh issue list --repo nucleus-data/nucleus --state open --limit 20; gh api repos/nucleus-data/nucleus/discussions --jq '.[] | "\(.number): \(.title)"' 2>$null
  ```

- [ ] **Demo URL load-watch** — if `try.nucleus.dev` is being hammered, fall back gracefully. _(5 min if triggered)_

  ```powershell
  curl.exe -fsSI https://try.nucleus.dev
  ```
  If 5xx / timeout → flip a comment on HN: "demo currently rate-limited, repo + docs are the canonical entry points".

- [ ] **Hot-patch protocol** if a critical bug surfaces: (1) reproduce in a clean clone, (2) foreground-fix on `main` — NOT `v0.3` (do not conflate roadmap with hotfix), (3) tag `v0.2.1` and push (PyPI re-publishes via the same OIDC workflow, do NOT yank `v0.2.0`), (4) comment "Fixed in v0.2.1, `pip install -U nucleus`." _(30–90 min if triggered)_

---

## Phase 7 — Post-launch (T+24 h)

- [ ] **Post-mortem note** at `docs/release/v0.2.0_POST_LAUNCH_NOTES.md` — what happened vs plan, HN peak rank, PyPI install count, top 3 surprises, decisions for v0.2.1 / v0.3. _(30 min writing)_

  ```powershell
  curl.exe -fsS "https://pypistats.org/api/packages/nucleus/recent" | python -m json.tool
  ```

- [ ] **PoC #5 round-2 feedback** → triage into v0.3 backlog at `docs/poc/p5_beachhead/AGGREGATE_FINDINGS.md`. _(30 min review)_

- [ ] **Update** `docs/FOUNDER_ACTION_QUEUE.md` — prepend a new `## §0.4` section summarizing launch outcome + new founder-gated items surfaced. _(15 min)_

---

## Quick reference

- **Release bundle commit verification**: `git log -1 --format='%h %s' main`
- **Governance suite (11/11 must PASS pre-tag)**: `ForEach ($s in @("check_vocabulary","check_pinning","loc_budget","dagster_leak_check","check_error_codes","check_api_stability","check_licenses","check_layering","check_lazy_imports","check_install_size","check_perf_budget")) { python "scripts/$s.py"; if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: $s"; break } }`
- **Rollback tag** (only valid if PyPI publish HAS NOT succeeded): `git push --delete origin v0.2.0; git tag -d v0.2.0`
- **Yank PyPI version** (last resort, non-destructive): web UI at `https://pypi.org/project/nucleus/0.2.0/` → "Yank release"; existing installs unaffected.
- **Forbidden framings reminder** (`AGENTS.md` §8): never describe Nucleus with the banned terms from `AGENTS.md` §8. Correct framing: "Ship data products from a laptop".

*Refresh trigger: at T+48 h after tag push, replace this file with `v0.2_POST_LAUNCH_RETRO.md`. Until then, work top-to-bottom.*
