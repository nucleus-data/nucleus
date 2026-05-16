# Nucleus — Solo-Founder Long-Term Handover

> **Audience**: The founder, future-self, 6+ months after the v0.2.0 public launch.
> **Purpose**: The **steady-state** operations manual for solo-maintaining Nucleus long-term. Not the launch-day runbook — that lives in [`docs/release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md). Not the day-0 onboarding — that lives in [`docs/roadmap/HANDOVER.md`](roadmap/HANDOVER.md). **This file is the one you re-read every quarter** when you have forgotten why Nucleus exists, how to triage a Dependabot PR, or whether to take a break.
>
> **Anti-Over-Engineering reminder** (founder directive, 2026-05-13): "Focus on simplicity and real core values. Over-engineering causes black-box experiences and bad future health of the platform." When this file conflicts with new AI suggestions about "clean abstractions" or "future-proofing", **this file wins** until you amend it on purpose.

---

## 1. Mental model — re-read first

When you open this file disoriented, read this section before anything else.

**What Nucleus is.** A local-first Python SDK (`ctx`) + CLI (`nucleus`) for building Iceberg-native pipelines and analytics stacks. It ships data products from a laptop. It graduates cleanly to any Iceberg catalog (Polaris, Lakekeeper, Unity, R2, Databricks, Snowflake) when teams outgrow the laptop. It is **AI-ready by design**, not AI-first. <!-- banned-term: AI-first -->

**What Nucleus is not** (per [`AGENTS.md`](../AGENTS.md) §8 — re-read if you start drifting): not a database, not a SQL engine, not a DataFrame engine, not an orchestrator, not a "Data OS" or "Spark killer" or "AI-native platform". The forbidden framings list has 13 entries — if you ever catch a marketing draft or AI suggestion drifting toward one, push back hard. <!-- banned-term: multiple -->

**The three things you own forever** (per `AGENTS.md` §0):

1. The **asset graph** — the logical model of data products.
2. The **`ctx` SDK** — the developer contract.
3. The **unified developer-first experience** — CLI + Workbench + SDK as one product, with AI assistance as a feature, not the headline.

Everything else is **wrapped** from open source. The hard ceiling is **30K LOC** of proprietary code by v1.0 (`scripts/loc_budget.py` enforces it). At v0.2 ship you sit at roughly 8.3K LOC. You have room. **Use it sparingly.**

**The 11 hard constraints** ([`AGENTS.md`](../AGENTS.md) §3) are non-negotiable. They include: no JVM in the core path, no custom scheduler, no custom compute engine, no custom auth system, no ML platform, exact dependency pins, single-component-per-PR upgrades. If anyone — a contributor, a Dependabot PR, a future-you, an AI suggestion — asks you to violate one of them, the answer is a polite "no, that needs an architecture amendment." Amending the architecture is its own deliberate process (an ADR, not a casual decision).

**The beachhead persona** (`nucleus_architecture_v4.1.md` §1.5) is what every decision serves: **a 5-engineer startup data team, 100GB-5TB total data, greenfield project, building a BI-ready Iceberg table in <30 minutes from `git clone`.** When considering any feature, ask "does this help or hurt that 30-minute path?" Unchanged or worse → defer.

**Mode of operation.** You are solo. AI is your pair. Speed comes from **cutting ceremony, not cutting quality gates**. The quality gates that must stay (per `.cursor/rules/nucleus.mdc` §Velocity Discipline):

- All 11 governance scripts EXIT 0 before merge ([`scripts/check_vocabulary.py`](../scripts/check_vocabulary.py) + 10 others).
- All tests pass at new and old locations after a refactor.
- LOC budget GREEN — under the current phase ceiling.
- Error translation at every external boundary (no Dagster/DuckDB/Polars/pyiceberg classnames in user-facing strings — see `scripts/dagster_leak_check.py`).
- 30-minute beachhead E2E unbroken (`scripts/beachhead_e2e.py` returns 8/8).

If a velocity shortcut breaks any gate, the gate wins. **No exceptions.**

Re-read [`AGENTS.md`](../AGENTS.md) and [`nucleus_architecture_v4.1.md`](../nucleus_architecture_v4.1.md) **once a quarter minimum**. Re-read this file before each quarterly review. When in doubt, re-read.

---

## 2. Daily (15 min)

Open the terminal. Open the browser to two tabs: GitHub Issues, GitHub Notifications.

```powershell
# 1. New issues + new discussions (most signal)
gh issue list --repo nucleus-data/nucleus --state open --search "created:>=$(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')" --limit 20
gh api repos/nucleus-data/nucleus/discussions --jq '.[] | select(.created_at >= (now - 86400 | strftime("%Y-%m-%dT%H:%M:%SZ"))) | "\(.number)  \(.title)"' 2>$null

# 2. CI status on main
gh run list --repo nucleus-data/nucleus --branch main --limit 5 --json conclusion,name,createdAt | ConvertFrom-Json | Format-Table

# 3. Security advisories from pip-audit (Constraint #11 cadence)
pip-audit --strict --skip-editable 2>$null

# 4. Discord / Discussions ping check (manual)
Start-Process "https://github.com/nucleus-data/nucleus/discussions"
```

**What "good" looks like**: zero new critical issues, CI all green, `pip-audit` returns no high/critical CVEs.

**Triage rules**:

- **New `bug` issue** → label, reproduce in a clean clone, do not promise an ETA. If reproducible and breaks the beachhead E2E, escalate to a `v0.2.x` patch tonight. Otherwise queue for the weekly review.
- **New `feature-request` issue** → apply the 8-question gate ([`docs/roadmap/overview.md`](roadmap/overview.md#the-8-question-gate)). If it fails any question, comment with the gate explanation and the label `deferred` or `out-of-scope`. Default is `defer`.
- **New `question`** → answer if it takes <5 min, else schedule for the weekly batch.
- **Dependabot / Renovate PR** → do **not** auto-merge. Triage at the weekly cadence (§3).
- **Security advisory (CVE)** → never defer. Patch within 48h (see Crisis Playbook §7.1).

**If everything is green, close the laptop.** The discipline is "show up daily; do the minimum daily". Heroics are a smell.

---

## 3. Weekly (1 hour, e.g., Friday afternoon)

### 3.1 PR review queue (20 min)

```powershell
gh pr list --repo nucleus-data/nucleus --state open --limit 30 --json number,title,author,statusCheckRollup,labels
```

Categorize each open PR:

- **Community PR with green CI** → review. Read `docs/dev-guides/13-common-pitfalls.md` before commenting. Be **kind, specific, and honest about scope**. If the PR violates the 8-question gate, say so plainly and reference the gate.
- **Community PR with red CI** → comment "CI is red on [job]. Could you debug, or do you want help?" Do not fix it for them on the first round.
- **Dependabot PR** → see decision matrix below.
- **Your own PR draft** → either finish or close. Stale drafts rot.

### 3.2 Dependabot triage decision matrix (15 min)

Per **Constraint #11** ([`AGENTS.md`](../AGENTS.md) §11.13): one component per PR; no bulk upgrades.

| Situation | Decision | Notes |
|---|---|---|
| Patch bump (X.Y.Z → X.Y.Z+1) of a runtime dep, CI green, changelog summary innocuous | **Auto-merge after 24h soak** | Wait 24h to let downstream catch regressions. |
| Minor bump (X.Y.Z → X.Y+1.0) of a runtime dep, CI green | **Manual merge** | Read the changelog; verify no API surface change touches `src/nucleus/`. PR body must include rollback command. |
| Major bump (X.Y.Z → X+1.0.0) of a runtime dep | **HOLD** | Open an ADR per [`docs/dev-guides/08-author-adr.md`](dev-guides/08-author-adr.md). Run full upgrade smoke (`python scripts/upgrade_smoke.py`). Wait 7 days before merge. |
| Dev-dep upgrade (ruff, mypy, pytest) | **Auto-merge after CI green** | Loose-pin tolerated. |
| Two Dependabot PRs on the same component | **Reject the older; keep the newer** | Comment "one component per PR per Constraint #11; merging the newer one." |
| Dep bump on a deprecated component (about to be swapped out) | **Reject** | Comment with the swap target. |
| Bump introduces a new transitive dep with a non-GREEN license | **Reject** | Reference [`scripts/check_licenses.py`](../scripts/check_licenses.py) output. |

If you're not sure, **default to HOLD**. A delayed upgrade is cheaper than a 3-day debug session.

### 3.3 Issue triage batch (15 min)

Process the queue from the daily pass. Apply labels: `triage`, `bug`, `feature-request`, `question`, `deferred`, `good-first-issue`, `v0.3`, `v0.5`, etc. Close `question` issues that have been answered. Convert long discussions into Discussions threads.

### 3.4 CI / governance health (10 min)

```powershell
gh workflow view ci.yml --repo nucleus-data/nucleus
python scripts/loc_budget.py
python scripts/check_pinning.py
python scripts/check_licenses.py
```

Flag any creeping LOC delta (>200 LOC week-over-week from a single PR → investigate).

---

## 4. Monthly (3-4 hours, last business day of the month)

### 4.1 Drift detection pass (1 hour)

Per [`AGENTS.md`](../AGENTS.md) §11.11, run the full drift detection prompt against the last 4 weeks of commits. Paste this into Cursor Chat with `@AGENTS.md`, `@nucleus_architecture_v4.1.md`, `@CHANGELOG.md`:

```
Drift Detection Pass.

Review the last 4 weeks of commits to main. Flag any of:
1. Wrap-not-build violations (per AGENTS §4)
2. Scope creep beyond the current version
3. Composability violations (any non-swappable Tier 1/2 dependency added?)
4. Error translation gaps (any external classname in user-facing strings?)
5. Vocabulary drift (per AGENTS §7)
6. LOC budget overruns (cite scripts/loc_budget.py)
7. Hallucinated API usage (any method that doesn't exist in pinned-version official docs?)
8. Unpinned dependency versions

Be brutally honest. Cite file paths and line numbers. Suggest fixes.
```

**You review the AI's review.** Don't accept all-clear without spot-checking 2-3 flagged items. Log any caught hallucinations in [`docs/internal/research/ai_hallucinations.md`](research/ai_hallucinations.md).

### 4.2 Snapshot LOC + budget history (15 min)

```powershell
python scripts/loc_budget.py | Tee-Object -FilePath docs/budget_history.md -Append
```

Verify trend stays GREEN against the phase ceiling (v0.2: 12,000 / v0.3: 16,000 / v0.5: 20,000 / v1.0: 28,000).

### 4.3 License audit (15 min)

```powershell
python scripts/check_licenses.py
```

Any new YELLOW-tier dep (e.g., GPL, MPL with boundary) needs an ADR per [`docs/decisions/ADR-007-dependency-license-tier-policy.md`](decisions/ADR-007-dependency-license-tier-policy.md).

### 4.4 Dependency audit (30 min)

```powershell
pip-audit --strict
pip list --outdated
```

Update [`docs/compatibility.md`](compatibility.md). Identify any dep >6 months behind upstream. Plan one upgrade for next quarter (do **not** plan more than one per quarter unless forced by CVE).

### 4.5 Community health snapshot (30 min)

Manual screenshot or note to a private journal:

- GitHub stars / forks / issue close-rate / PR merge-rate
- PyPI download trend ([pypistats.org/packages/nucleus](https://pypistats.org/packages/nucleus))
- HN / Reddit / dev.to mentions (Google "site:news.ycombinator.com nucleus iceberg")
- Discord / Discussions message counts

Numbers feed §10 health dashboard. Trends matter; absolute values are noise.

### 4.6 Re-read the founder action queue (15 min)

[`docs/FOUNDER_ACTION_QUEUE.md`](FOUNDER_ACTION_QUEUE.md) is the deferred-work log. Close items you finished. Promote items that have aged into "act now" (e.g., security advisory now has a fix available). Do **not** add new items unless they truly require founder action.

---

## 5. Quarterly (1-2 days, calendar block)

Quarterly is the rhythm of the **upgrade audit** (Constraint #11) and the **roadmap phase-gate review**.

### 5.1 Upgrade audit ([`AGENTS.md`](../AGENTS.md) §11.13)

```powershell
python scripts/upgrade_smoke.py
```

For each wrapped Tier 1/2 dep, decide: stay, minor-bump, major-bump-ADR. Update [`docs/compatibility.md`](compatibility.md) with the chosen target version. Bulk-upgrade is forbidden — pick ONE component to upgrade this quarter and one to plan for next quarter. Open the upgrade PR per [`docs/dev-guides/07-upgrade-wrapped-library.md`](dev-guides/07-upgrade-wrapped-library.md).

### 5.2 Full security review (3 hours)

```powershell
pip-audit --strict --vulnerability-service osv
gh api repos/nucleus-data/nucleus/code-scanning/alerts --jq '.[] | "\(.number)\t\(.rule.severity)\t\(.rule.description)"'
```

Triage every high/critical alert. Document each fix or risk-accept in [`SECURITY.md`](../SECURITY.md). If you have not enabled Code Scanning yet, do so now ([`FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) Phase 1).

### 5.3 Roadmap phase-gate review (2 hours)

Open [`docs/roadmap/overview.md`](roadmap/overview.md). For the current phase, ask:

- **On track?** Are the listed features shipped / in progress / blocked?
- **Persona still right?** Has any external feedback shifted the beachhead persona?
- **LOC budget?** Are you trending toward the ceiling? If yes, what to defer?
- **8-question gate review** on every feature still on the list — has any become "no" or "unclear"?

Edit the current phase doc. **Do not** edit future phase docs unless research has landed.

### 5.4 Budget history review (30 min)

Read [`docs/budget_history.md`](budget_history.md) tail. Any month where LOC delta exceeded the phase trajectory by >500 LOC = audit which PRs added what. The 30K ceiling is a wall, not a target.

### 5.5 Re-read the deeps (1 hour)

- [`AGENTS.md`](../AGENTS.md) — full file.
- [`nucleus_architecture_v4.1.md`](../nucleus_architecture_v4.1.md) — at least §1 (identity), §3 (layers), §6 (error translation), §9 (composability), §18 (roadmap), §20 (non-goals).
- [`docs/decisions/`](decisions/) — any ADR that landed this quarter.

---

## 6. Annual (1-2 weeks, block in December / January)

### 6.1 Major version planning

Read all ADRs since the last annual review. Note which constraints are bending. Draft the next major version's theme. Major version planning is **strategic**, not tactical — set a 12-month horizon, not a 3-month one.

### 6.2 Community health deep-dive

Aggregate the monthly health snapshots. Compute:

- Active contributors (people with a merged PR in the last 12 months)
- Issue first-response median time
- Top 5 most-requested features → does the 8-question gate accept any?
- Top 5 most-frequent bug categories → do they suggest an architectural gap?

### 6.3 License + governance review

Re-read [`LICENSE`](../LICENSE), [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`GOVERNANCE.md`](../GOVERNANCE.md), [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md). Confirm they still match how the project actually runs. Update if the project's governance has drifted (e.g., you added a co-maintainer).

### 6.4 Sponsor relations

If you have GitHub Sponsors enabled (see §9): personally thank each active sponsor. Send a 1-page private year-in-review. Update [`.github/FUNDING.yml`](../.github/FUNDING.yml) if you've added Open Collective or other channels.

### 6.5 Vision statement re-validation

Open [`docs/decisions/ADR-002-positioning-decision-2026-05.md`](decisions/ADR-002-positioning-decision-2026-05.md). Re-read §8 (positioning hierarchy). Has the tagline still earned its place after a year of real users? If not, the **only** path is a new ADR — never silently change the tagline.

### 6.6 Take a real break

A week off, no laptop, no GitHub notifications. The project survived without you for the week — that is a feature, not a bug. If it didn't survive, the architecture has a single-point-of-failure problem worth fixing (see Crisis Playbook §7.5).

---

## 7. Crisis playbooks

Eight scenarios. Each is a decision tree, not a prescription. Decision time **before** the crisis hits is cheap; decision time **during** the crisis is expensive.

### 7.1 Security advisory in upstream (e.g., DuckDB CVE)

**Trigger**: `pip-audit` flags a high/critical CVE in a pinned wrapped dep.

**Tree**:

1. **Is a fixed version available?**
   - **Yes** → pin to it in `pyproject.toml`. Run `python scripts/upgrade_smoke.py`. If smoke passes → tag `v0.X.Y` patch within 48h. Comment on the relevant PoC #5 / community issue.
   - **No** → next branch.
2. **Can we work around in our code?** (e.g., disable the affected feature, sanitize input before passing to the dep)
   - **Yes** → ship the workaround as a patch. Document in [`SECURITY.md`](../SECURITY.md). Track a follow-up issue to remove the workaround when upstream fixes.
   - **No** → next branch.
3. **Is the CVE exploitable in our usage?** (read the CVE carefully — many DuckDB CVEs apply only to networked usage; we ship local-first.)
   - **No** → document non-applicability in [`SECURITY.md`](../SECURITY.md). No patch needed. Add a test that asserts the non-applicable code path stays unused.
   - **Yes, but low** → defer to next patch release with a CHANGELOG entry.
   - **Yes, critical** → trigger the swap interface for that dep ([`docs/swap/<dep>.md`](swap/) — built on-demand per [`AGENTS.md`](../AGENTS.md) §11). This is the "vendor death" scenario.

**Time budget**: 4h triage; 48h ship.

### 7.2 Major version breaking in a wrapped library (e.g., pyiceberg 0.x → 1.0)

**Trigger**: A Dependabot PR proposes a major bump, or upstream announces 1.0 EOL of 0.x.

**Tree**:

1. Read the migration guide and breaking changes section in full. Annotate every breaking change against `src/nucleus/` usage.
2. Open an ADR per [`docs/dev-guides/08-author-adr.md`](dev-guides/08-author-adr.md). Title: `ADR-NNN: pyiceberg X.Y → X+1.0 migration`. Status: PROPOSED.
3. In a feature branch, apply the upgrade. Run the full test suite + `scripts/beachhead_e2e.py` + benchmarks.
4. If benchmarks regress >10% on any tracked metric → STOP. Document the regression. Either fix in `src/nucleus/` adapter code, or hold the upgrade until upstream improves.
5. Once green: ratify the ADR. Merge. Tag a minor release (e.g., `v0.4.0` if you were on `v0.3.x`).

**Time budget**: 2-5 days, spread across a week. Do not rush a major upgrade.

### 7.3 Community PR with hostile or risky changes

**Trigger**: A PR arrives that (a) introduces a new heavy dep, (b) violates the 8-question gate, (c) inverts the wrap-vs-build default, or (d) uses forbidden framings in docs/code.

**Tree**:

1. Do not merge. Do not close immediately either.
2. Comment with the **specific constraint violated** ([`AGENTS.md`](../AGENTS.md) §X, [`.cursor/rules/nucleus.mdc`](../.cursor/rules/nucleus.mdc), the 8-question gate). Link the relevant section.
3. Offer one of: (a) close as out-of-scope with a Discussion thread for the deferred idea, (b) keep open with `needs-adr` label if the idea has merit but needs design work, (c) accept a narrower version that fits.
4. Be **respectful and specific**. The PR author spent real time. Do not be terse; do not be dismissive. The phrase "I appreciate the work; this conflicts with X for reason Y; here is what would land" is the template.
5. If the PR author becomes hostile in response → label `do-not-merge`, comment "I'm going to close this; let's reopen if we have a different design", close. **Never** engage in flame wars. The project's tone is set by the maintainer's response, not by the PR author's prompt.

**Time budget**: 30 min response; do not engage further the same day.

### 7.4 License pivot of an upstream OSS (e.g., Iceberg goes ELv2)

**Trigger**: Upstream announces a license change to a non-Apache-compatible license (BSL, ELv2, AGPL, etc.).

**Tree**:

1. Read the license change carefully. ELv2 / BSL with usage caps may or may not affect Apache-2.0 redistribution. Consult a lawyer if it's ambiguous — this is the **one** "stop and ask for paid advice" scenario.
2. If the change blocks redistribution: trigger the swap interface (`docs/swap/<dep>.md` — built on-demand per [`AGENTS.md`](../AGENTS.md) §11). Pin to the last Apache-compatible version meanwhile. Patch `pyproject.toml` immediately.
3. Open an ADR: `ADR-NNN: License pivot of <dep>; swap to <alternative>`. Status: ACCEPTED (this is a forced decision, not an optional one).
4. Communicate publicly within 7 days: GitHub Discussion announcement + CHANGELOG entry + Twitter/Mastodon post.
5. Ship the swap within the next minor version. Do not let this drag — it's an existential risk to the project's open-source posture.

**Time budget**: 7 days emergency window. Time-box this; do not let it become months.

### 7.5 Founder burnout / planned break

**Trigger**: You feel a real, sustained sense of dread when opening GitHub Notifications. Or a planned 4+ week absence.

**Tree**:

1. **First, name it.** "I'm burned out / I'm taking a break." Self-deception extends the problem.
2. **Communicate publicly.** Pin a GitHub Discussion: "Nucleus is on a planned hiatus from [date] to [date]. Issues will be triaged but not actively worked. Security CVEs will be patched. Other work resumes [date]." Do **not** silently disappear — that kills community trust.
3. **Set notification filters.** Mute Discussions, mute non-security issues. Keep only CVE alerts active.
4. **Pre-write a "back from break" plan** before you leave. Don't trust future-you to be motivated on Day 1 back. The pre-written plan is the lifeline.
5. **Recovery doesn't have to be fast.** A 2-week hiatus is not "abandonment." A 6-month silence with no announcement is. The difference is communication.
6. **If burnout is structural** (not episodic): look at §8 hiring signals. Solo OSS is not a permanent state for healthy projects.

**Time budget**: as long as you need. Don't rush this.

### 7.6 Critical bug in production for a paying customer (when Cloud tier exists)

**Trigger**: Cloud-tier customer reports data loss, materialization failure, or a stuck snapshot.

**Tree**:

1. Acknowledge within 1h. "I'm investigating; will update by [time]." Do **not** promise a fix time before reproducing.
2. Reproduce in a clean clone with the customer's project layout. If you can't reproduce → ask for the full `runs.ndjson` ledger + `nucleus.toml` + the exact CLI command + stderr.
3. **Roll back, do not roll forward.** If the customer was on `v0.X.Y`, roll their managed deploy to `v0.X.Y-1` while you investigate. Their data takes priority over your debugging convenience.
4. Fix on `main`, tag a `v0.X.Y+1` patch. Cloud-tier customer gets first migration support; OSS users get the same patch published the same day.
5. Write a post-mortem in `docs/postmortems/YYYY-MM-DD-<short-title>.md`. Be honest. Public post-mortems build trust; concealed ones erode it.

**Time budget**: 24h fix; 7 days post-mortem.

### 7.7 Surge of GitHub Issues post-HN

**Trigger**: HN front page traffic produces 50+ new issues in 48h.

**Tree**:

1. **Triage all 50 in one block** (3-4 hours). Apply labels. Mark duplicates. Close `question` issues with a one-liner pointing to docs.
2. **Pin a "current state of triage" issue** at the top of the repo. Be honest: "I'm one person; I'm working through this queue; here are the top 3 things I'm actively investigating; everything else is queued."
3. **Use canned responses for repetitive questions.** Save as GitHub saved replies:
   - "Thanks for trying Nucleus. This is documented at [link]. Closing as answered; feel free to reopen if it doesn't resolve."
   - "Thanks for the report. This needs reproduction steps to act on. Could you share `nucleus_project.yaml` + the exact command?"
   - "Thanks for the feature request. This conflicts with [constraint]; see [link]. Closing as out-of-scope for v0.X."
4. **Do not promise fixes** in the surge window. Promises made under traffic load break the road map.
5. **Aggregate the top 5 themes** into a Discussion thread "v0.X.Y roadmap shaped by HN feedback" once the surge subsides.

**Time budget**: 4h initial; 2h/day for 7 days; then back to weekly cadence.

### 7.8 Trademark / brand confusion (someone else uses "Nucleus")

**Trigger**: A competing project, a company product, or a typosquat appears using "Nucleus" for a data tool.

**Tree**:

1. **Check trademark registry** (USPTO for US, EUIPO for EU). Did we register? If not → next branch.
2. **If we registered** → consult an IP lawyer. Cease-and-desist is a formal process; do not DIY.
3. **If we did not register** → assess severity:
   - **Typosquat / phishing** (e.g., "nucleus-iceberg.org" running scams) → report to GitHub / domain registrar / hosting provider; do **not** waste energy beyond that.
   - **Legitimate other project** using the name in a different vertical → ignore. Nucleus is a common word; we don't own it.
   - **Direct competitor** in the data space → consider rebranding **only if** their project has materially more traction. Otherwise compete on substance, not brand.
4. **Always document the response** in `docs/postmortems/` so the next confusion-event has prior art.

**Time budget**: 2h investigation; weeks-to-months for any IP action.

---

## 8. AI workflow playbook

You will run this project alongside AI for the foreseeable future. The discipline is the same as for human contributors: **trust, but verify; and only delegate what is appropriate to delegate**.

### 8.1 Which AI surface for which task

Per [`AGENTS.md`](../AGENTS.md) §11.3 (the AI Boundary Map). Memorize this table; do not work outside it.

| Task | AI quality | Discipline |
|---|---|---|
| Decorator scaffolds, type defs, dataclasses | Excellent | Cursor Composer or Chat. Light review. |
| Basic test cases from spec | Excellent | Cursor Composer. Verify edge cases. |
| Documentation generation | Excellent | Cursor Composer + manual editing pass. |
| Refactoring (rename, extract, inline) | Excellent | Cursor Composer. Check the LOC delta. |
| Wrapping a stable OSS library | Good | Cursor Chat. **Verify the API actually exists** (see §8.4). |
| SQL parsing logic | Good | Cursor Chat. Verify edge cases. |
| Error Translation Layer | **Risky** | Human writes; AI suggests only. |
| `ctx.sql` Jinja resolver | **Risky** | Human writes core; AI assists. |
| Concurrency / atomicity decisions | **Risky** | Human authority only. |
| Schema evolution edge cases | **Risky** | Human authority + tests. |
| Performance-critical paths | **Risky** | Human authority + benchmarks. |
| Dagster internals interaction | **Bad** | Human writes; AI cannot reason about Dagster internals. |
| ADR drafting (architectural decision) | **Bad** | Human writes; AI proofreads. |
| Roadmap / vision decisions | **Bad** | Human only. |

**Rule of thumb**: when in doubt about which row applies, treat it as **Risky** and write it yourself with AI as a proofreader.

### 8.2 Cursor surface guide

- **Cursor Tab Completion** — safe for type annotations, imports, common patterns, test boilerplate. **Not safe** for error-handling blocks, wrapped-OSS calls, concurrency primitives, SQL string construction.
- **Cursor Chat (Ctrl+L)** — use for architectural questions where you need citations. Required context: `@AGENTS.md`, `@nucleus_architecture_v4.1.md`, the relevant spec file. If the AI gives an answer that doesn't cite architecture sections, the answer is unreliable. Push back.
- **Cursor Composer** — multi-file edits. **Discouraged in v0.1; cautious in v0.2+.** Use only for pure renames, vocabulary swaps, or scaffolding a single new decorator across `__init__.py` + new file. Never for cross-layer feature work.
- **Subagents** (per [`AGENTS.md`](../AGENTS.md) §11.14) — for v0.2+ multi-step work, route by role: Architect (Opus 4.7), Builder (GPT-5.5), Swarm (Sonnet 4.6), Research (Gemini 3.1 Pro). Don't use the strongest model for everything; it wastes compute and over-engineers.

### 8.3 Per-task budget guidelines

- **Single-file edit**: 1 AI message, then ship. No infinite-loop iteration.
- **Multi-file feature**: 1 plan message, 1 implementation pass, 1 test-and-verify pass. If you're on iteration 4, **stop and re-plan**.
- **Debugging**: 30 min AI-assisted. If still stuck, switch to manual reproduction with `pdb` / `print()`. AI cannot debug what it cannot run.
- **Documentation**: 1 generation pass, 1 manual editing pass. AI-generated docs without a human pass read like AI-generated docs.

### 8.4 AI hallucination discipline

Per [`AGENTS.md`](../AGENTS.md) §11.12: **never trust an API the AI suggests without verifying it exists in the pinned version's official docs**.

Pattern:

```python
# Every external library import gets a docs URL comment
from pyiceberg.catalog import load_catalog
# Docs: https://py.iceberg.apache.org/api/catalog/  # pinned 0.8.1
```

If the AI suggests a method you don't recognize:

1. Cursor Chat: "Cite the official docs URL for `<library>.<method>` and confirm it exists in version `<pinned>`."
2. If the AI hedges or refuses to cite → the method probably doesn't exist. Assume hallucination.
3. Log every caught hallucination in [`docs/internal/research/ai_hallucinations.md`](research/ai_hallucinations.md). This catalog becomes priceless over time.

### 8.5 LLM cost management

- Token budget per task: aim for <50K tokens per single-file task; <200K per multi-file feature.
- Subagent loops with no budget cap are the #1 cost-overrun pattern. **Always** pass an iteration ceiling (default 5-7 attempts) to a Builder agent.
- Re-prompt with less context, not more. If you keep dumping more files in, the AI is not improving — your prompt is.
- Architecture-tier work (Opus 4.7) is expensive **per token**. Don't burn it on boilerplate. Route via the role-based stack ([`AGENTS.md`](../AGENTS.md) §11.14).

### 8.6 When NOT to use AI

- **ADR votes.** A decision-record's authority comes from the human who took responsibility. AI can proofread; AI cannot ratify.
- **Vocabulary / framing decisions.** Forbidden framings ([`AGENTS.md`](../AGENTS.md) §8) are guarded by the human, because AI optimizes for plausibility and "AI-native" sounds plausible — and is forbidden. <!-- banned-term: AI-native -->
- **Security advisories.** Read the CVE yourself. AI summaries miss subtle "applies only when X" clauses.
- **License decisions.** See Crisis Playbook §7.4.
- **Hiring decisions** (if/when you have collaborators). AI cannot read body language or motivation.
- **Customer relationships.** Personalized response always; templated never (for paying customers especially).

---

## 9. Solo-founder OSS economics

You will not be paid to maintain Nucleus full-time at the start. Plan accordingly.

### 9.1 GitHub Sponsors setup

[`.github/FUNDING.yml`](../.github/FUNDING.yml) should list your Sponsors handle. Onboard at <https://github.com/sponsors>. Suggested tiers:

- **$5 / month** — "Coffee" — name in README acknowledgments.
- **$25 / month** — "Cookie" — name + logo (if individual sponsor wants).
- **$100 / month** — "Pizza" — quarterly 30-min office hour Zoom.
- **$500 / month** — "Underwriter" — early access to v0.X release candidates; named in ANNUAL release notes.

Do **not** offer "feature votes" or "priority bug fixes" at any tier. That breaks the open-source promise.

### 9.2 Open Collective alternative

Open Collective lets you accept funds without GitHub. Useful for companies that have procurement processes incompatible with GitHub Sponsors. Setup: <https://opencollective.com/create>. Add the link to [`.github/FUNDING.yml`](../.github/FUNDING.yml).

### 9.3 Sponsorship outreach template

For companies you suspect use Nucleus seriously, after 3+ months of usage:

```
Subject: Quick note from Nucleus maintainer

Hi [name],

I'm the maintainer of Nucleus (https://github.com/nucleus-data/nucleus), the
local-first Iceberg pipeline SDK + CLI. I noticed [your team / your project]
has been using Nucleus for [observable signal — issues filed, dependency
detected, blog post mentioning].

I wanted to ask: would your engineering team consider sponsoring Nucleus
development via GitHub Sponsors or Open Collective? Sponsorship at
$500/month covers roughly one day/month of maintenance work — enough to
keep Nucleus reliable for production usage like yours.

Concrete value to your team:
- Faster turnaround on bugs that affect your workflow
- Direct line via private email for non-public questions
- Influence on the v0.X / v0.Y roadmap (not "priority feature votes" — but
  an explicit signal of what serious users need most)

If interested: https://github.com/sponsors/[handle] or
https://opencollective.com/[project]. Happy to set up a 20-min call to
talk through specifics.

Either way — thanks for using Nucleus.

[name]
```

Send no more than 3-5 of these per quarter. Mass outreach is spam.

### 9.4 Cloud tier monetization timing

Per [`nucleus_architecture_v4.1.md`](../nucleus_architecture_v4.1.md) §13: Cloud tier (managed single-tenant) is v0.7+ scope. Do **not** launch Cloud before:

- At least 100 active OSS users (verified via PyPI download stats + GitHub stars)
- At least 3 prospective customers asking for managed (unsolicited)
- A clear single-tenant deployment story (not multi-tenant; multi-tenant is v1.5+)

Premature monetization is the #2 killer of solo OSS (after burnout).

### 9.5 When to consider hiring

Signals you've outgrown solo:

- **Velocity signal**: average <3 substantive PRs / month for 60 days, with backlog growing.
- **Backlog signal**: open issues > 100 with no triage in 7 days.
- **Sponsorship signal**: $5,000+ / month in stable recurring sponsorship.
- **Founder signal**: you feel dread, not curiosity, on Monday morning. (§7.5.)

First hire options, in order of impact:

1. **Part-time technical writer** (5-10 hrs / week) — keeps docs current as the codebase evolves. Highest leverage per dollar.
2. **Part-time community manager** — issue triage, Discord, social. Frees founder for code.
3. **Part-time backend engineer** — Tier 1 / 2 wrapping work, governance script maintenance. Last priority because requires the most onboarding.

Do not hire someone "to help with everything." Hire to a **specific role with a specific scope**.

---

## 10. Decision-making process

### 10.1 When to write an ADR

Per [`AGENTS.md`](../AGENTS.md) §11.5 — every "build" decision (vs wrapping), every major version upgrade, every new dependency, every framing/positioning change. Template: [`docs/decisions/_template.md`](decisions/_template.md). Guide: [`docs/dev-guides/08-author-adr.md`](dev-guides/08-author-adr.md).

You write the ADR **before** writing the code, not after. ADRs are decisions; code is execution. Reversing the order means you write justifications, not decisions.

### 10.2 When to defer

Per [`AGENTS.md`](../AGENTS.md) §10 disciplines — "Default to deferring. Over-eagerness is a bug." Apply the 8-question gate. Any "no" or "unclear" → defer. Log the deferred item to [`docs/FOUNDER_ACTION_QUEUE.md`](FOUNDER_ACTION_QUEUE.md) with a 1-line note for future-you.

### 10.3 When to escalate to "stop and ask"

Per [`AGENTS.md`](../AGENTS.md) §9 stop conditions:

- More than 2 PoCs require fallback plans.
- LOC exceeds 30K before v1.0.
- Internal interfaces become a maintenance burden.
- A major upstream OSS breaks compatibility or hostile-licenses.
- Composability swap drill fails for any Tier 1 component.
- A pillar is violated to serve another pillar.
- AI Copilot economics break (token cost > 30% of Cloud margin).

You are solo; "escalate" means "stop, write down the problem in a Discussion, do not act for 48h." Sleep on it. The discipline is **not** to act on Stop Conditions in the same session you discover them.

---

## 11. Health metrics dashboard (manual; no automation needed)

Track monthly in a private spreadsheet or notebook. Trends matter; absolute values are noise.

| Metric | Source | Healthy trend |
|---|---|---|
| Proprietary LOC | `python scripts/loc_budget.py` | Phase-ceiling GREEN; not >500 LOC/month delta |
| Dep staleness | `pip list --outdated` | <5 deps >6 months behind |
| GitHub stars | `gh api repos/nucleus-data/nucleus` | Up & to the right; spikes from HN posts expected |
| Issue close rate | `gh api repos/.../issues?state=closed` | >70% within 30 days |
| PR merge rate | `gh api repos/.../pulls?state=closed` | Community PRs >50% merged |
| PyPI weekly downloads | pypistats.org/packages/nucleus | Up & to the right; floor 100/week |
| HN / Reddit mentions | Manual Google search | At least 1/quarter |
| Discord / Discussions msgs | Manual | Active = >10 msgs/week |
| CI green-rate on main | `gh run list --workflow=ci.yml` | >95% pass on `main` |
| Test suite size | `pytest --collect-only | tail -1` | Grows with codebase; no shrinkage |
| Benchmark stability | `docs/benchmarks/` | No regression >10% on any tracked metric |

If three metrics trend red simultaneously, that's a **stop condition** — book a quarterly-grade review immediately.

---

## 12. Final word — re-read when discouraged

Solo OSS is hard. The compounding interest of small, daily, **deliberate** discipline is the only thing that works. Heroics produce burnout; routine produces longevity. Every quarter you stay alive is a win.

When you feel the urge to **build more**, re-read [`AGENTS.md`](../AGENTS.md) §4 (the Do-Not-Build list) and the founder directive at the top of this file: *focus on simplicity and real core values; over-engineering causes black-box experiences and bad future health of the platform*. The discipline is to **build less, ship less, defer more, and let the open source ecosystem do its share.**

When you feel the urge to **promise more**, re-read [`AGENTS.md`](../AGENTS.md) §10.8: be brutally honest. Over-promising is the #1 killer of OSS projects. Under-promise; over-deliver in calm increments. The honest "v0.X.Y patches a CVE within 48h" record buys more trust over five years than any single ambitious "v1.0 in 3 months" promise.

When you feel the urge to **chase the AI hype**, re-read [`AGENTS.md`](../AGENTS.md) §8 (forbidden framings). Nucleus is **AI-ready**, not AI-first. The day it becomes "AI-native" is the day it stops being Nucleus. <!-- banned-term: AI-native -->

When you feel like quitting, re-read §7.5 above. Take a planned break — not a silent exit. Come back in 4-8 weeks. The project survived; it will survive again.

When you feel like succeeding, re-read [`docs/decisions/ADR-002-positioning-decision-2026-05.md`](decisions/ADR-002-positioning-decision-2026-05.md) §8.4: the final tagline locks only after PoC #5 external-tester field-test data. Don't celebrate the brand; celebrate the user who graduated to Databricks with their Iceberg snapshots intact. **That** is what Nucleus shipped.

---

*Last reviewed: 2026-05-15 (v0.2.0 ship). Re-review next quarter (2026-08).*

*Cross-references: [`AGENTS.md`](../AGENTS.md) (universal AI handover), [`nucleus_architecture_v4.1.md`](../nucleus_architecture_v4.1.md) (architecture source of truth), [`docs/START_HERE.md`](START_HERE.md) (entry point for new arrivals), [`docs/roadmap/HANDOVER.md`](roadmap/HANDOVER.md) (Day-0 onboarding for next developer), [`docs/release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) (launch-day runbook).*
