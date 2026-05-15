# PoC #5 — Recruitment Plan

> **Goal**: 5 completed external tester sessions within 3 weeks of launch.
> **Metric for success**: NPS ≥ 7/10 from 5 testers; ≥3 of 5 say "would recommend to a colleague"; 0 critical-severity friction blockers unsurfaced pre-launch.

---

## Prerequisites (founder must complete before outreach opens)

| # | Prerequisite | Status | Blocker? |
|---|---|---|---|
| 1 | `github.com/nucleus-data/nucleus` remote live and `git clone` works | ❌ Currently 404 | **YES — hard blocker** |
| 2 | Compensation amount confirmed (`<$AMOUNT>` replaced everywhere) | ❌ Founder decision | YES |
| 3 | Booking link live (`[BOOK_30MIN_HERE]` replaced with real URL) | ❌ Founder action | YES |
| 4 | Postgres bad-creds error translation fixed (CRITICAL finding in simulation) | ❌ Engineering | Strongly recommended |
| 5 | CONSENT.md attribution levels confirmed and sent to each tester before session | ❌ Founder action | YES |
| 6 | `FEEDBACK_FORM_TEMPLATE.md` shareable link ready | ❌ Founder action | YES |

**Do not open outreach until prerequisites 1, 2, 3, and 5 are complete. Prerequisites 4 and 6 are strongly recommended.**

---

## Channel priority

Channels are ordered by expected yield-to-effort ratio, based on community size and data engineering representation.

### Channel A — Hacker News "Who's Hiring / Who Wants to Be Hired"

- **Post type**: Monthly thread reply (first weekday of each month)
- **Target**: 2–3 qualified signups per post
- **Format**: Use `OUTREACH_EMAIL_TEMPLATE.md` HN template (≤150 words)
- **Why first**: High signal-to-noise, builders self-select, zero cold-outreach friction, HN users are comfortable with pre-launch tools
- **Disclosure**: Not required by HN norms but include compensation amount — it increases trust
- **Timing**: If launching mid-month, use HN's "Ask HN" format instead: "Ask HN: data engineers — 90-min paid UX study for a new Iceberg CLI"

### Channel B — r/dataengineering (Reddit)

- **Post type**: Standalone post with `[Research Participation]` or `[Hiring/Opportunity]` flair (check current subreddit rules)
- **Target**: 3–5 qualified signups per post
- **Format**: Use `OUTREACH_EMAIL_TEMPLATE.md` r/dataengineering template
- **Why second**: 500K+ members, strong IC-level data engineer concentration, tolerant of pre-launch tool discussions when honest
- **Rules check**: Read subreddit rules before posting — some communities require disclosure that it's paid research and disallow direct promotional links; use calendar link sparingly
- **Posting time**: Tuesday–Thursday, 9–11 AM UTC for maximum visibility

### Channel C — LinkedIn DMs (warm intros first, cold second)

- **Post type**: Direct message (warm contacts → 2nd-degree through mutual DE connections)
- **Target**: 1–2 qualified signups per 10 personalized DMs
- **Format**: Use `OUTREACH_EMAIL_TEMPLATE.md` LinkedIn DM template
- **Why third**: Highest trust (existing relationship), low reply friction, but high effort per contact
- **Warm first**: Start with 5–10 engineers you've worked with who are now at startup-sized companies
- **Cold second**: After warm exhaust, use LinkedIn search (title: "data engineer", company size: 11–200) with personalized opening line

### Channel D — Twitter / X DMs

- **Post type**: Public tweet + DM to engaged DE accounts
- **Target**: 1–2 qualified signups per campaign
- **Format**: Use `OUTREACH_EMAIL_TEMPLATE.md` Twitter/X template
- **Why fourth**: Fast but low signal — most data engineers are on LinkedIn or Discord, not Twitter/X
- **Best approach**: Quote-tweet a popular DE thread with "Building something related — looking for 5 testers..."

### Channel E — Data-engineering Discords and Slacks (supplemental)

- **Communities**: dbt Slack `#jobs-and-opportunities`, Data Engineering Discord, locally active DE Slacks
- **Rules**: Always read server rules before posting; disclose paid research explicitly; never DM without a public post first
- **Target**: 0–2 signups per community
- **Why supplemental**: Discord/Slack communities have strict anti-spam rules and paid-research posts need mod approval in many servers; don't rely on this as a primary channel

### Channel F — Indie Hackers (secondary)

- **Post type**: "Looking for beta testers" post in product feedback board
- **Why**: IH community skews builders/founders who self-host; overlap with 5-20 engineer startup persona
- **Target**: 0–1 signup

---

## Recruitment target

| Metric | Target |
|---|---|
| Outreach contacts reached | 30–50 (across all channels) |
| Qualified signups | 7–10 (assume 30% response rate to outreach) |
| Screening calls / DM exchanges | 7–10 |
| Passed screening | 7–8 (assume ~90% pass rate post-outreach filter) |
| Scheduled sessions | 7–8 |
| Completed sessions | **5** (assume 20–30% cancellation / no-show) |

**Minimum viable cohort**: 5 completed sessions with at least 3 on macOS and at least 1 on Linux/WSL2.

---

## Timeline (3-week plan from outreach launch)

### Week 1 — Outreach

| Day | Action |
|---|---|
| Day 1 (Monday) | Post on r/dataengineering + HN (if monthly thread is live). Send 5 warm LinkedIn DMs to personal network. |
| Day 2 | Reply to any early inbound signups. Send 5 more LinkedIn DMs (2nd degree). Post Twitter/X thread. |
| Day 3 | Screen all respondents using `SCREENING_QUESTIONS.md`. Send booking link to qualified candidates. |
| Day 4–5 | Follow up with non-responders (one follow-up only). Post in 1–2 Discord communities if needed. |
| Day 6–7 | Review pipeline. If < 5 qualified signups, trigger Channel F (Indie Hackers) + 10 cold LinkedIn DMs. |

**Week 1 gate**: ≥5 confirmed bookings. If not reached, extend outreach by 3–5 days before starting sessions.

### Week 2 — Sessions

| Day | Action |
|---|---|
| Day 8–9 | First 2 tester sessions. Debrief within 24h. Note any systemic friction patterns. |
| Day 10 | Mid-cohort review: if 2/2 testers hit the same critical blocker, pause remaining sessions and fix before proceeding. |
| Day 11–12 | Sessions 3 and 4. Note whether prior fixes resolved Week 1 friction. |
| Day 13–14 | Session 5. Complete cohort. |

**Session pacing**: Do not run more than 2 sessions per day — friction patterns need time to surface before the next session starts. Space sessions ≥24h apart when possible.

### Week 3 — Aggregate and iterate

| Day | Action |
|---|---|
| Day 15–16 | Aggregate all 5 feedback forms. Count friction entries per checkpoint. Compute NPS average. Identify top-3 friction themes. |
| Day 17 | Write `docs/poc/p5_beachhead/results/AGGREGATE_SUMMARY.md` (see template structure below). |
| Day 18–19 | Convert top-3 friction themes to backlog issues with severity + owner + resolution estimate. |
| Day 20 | Founder decision: did we pass the PoC #5 gate? (see success criteria below) |
| Day 21 | If PASS → unlock v0.1 ship gate per `nucleus_poc_plan.md` §13. If FAIL → schedule fix sprint and re-test. |

---

## Success criteria (binding)

Per `nucleus_poc_plan.md` §5 and `AGENTS.md` §11.8:

| Metric | Pass threshold | Measured by |
|---|---|---|
| Median completion time | ≤ 30 min | Checkpoint 8 wall time across sessions |
| P90 completion time | < 45 min | |
| NPS (0–10 scale) | ≥ 7 average | `FEEDBACK_FORM_TEMPLATE.md` Q9 |
| "Would recommend" | ≥ 3 of 5 testers | `FEEDBACK_FORM_TEMPLATE.md` Part 7 |
| Critical blockers unsurfaced | 0 | All friction log items reviewed pre-launch |
| Iceberg snapshot verified | 100% of sessions | SHA-256 fingerprint from checkpoint 6 |

**If any metric fails**: do not ship v0.1 as a public release. Document the failure, fix root causes, and re-run with 3 additional testers (new cohort, no prior Nucleus exposure).

---

## Aggregate summary template

After all sessions complete, create `docs/poc/p5_beachhead/results/AGGREGATE_SUMMARY.md` with this structure:

```markdown
# PoC #5 Aggregate Summary

Sessions: N / 5 completed
Date range: YYYY-MM-DD to YYYY-MM-DD

## Timing
- Median: X min
- P90: Y min
- Fastest: Z min
- Slowest: W min
- Pass threshold: ≤30 min median — [PASS / FAIL]

## NPS
- Average: X.X / 10
- Scores: [list]
- Pass threshold: ≥7.0 — [PASS / FAIL]

## Would-recommend
- Count: N of 5
- Pass threshold: ≥3 — [PASS / FAIL]

## Top 3 friction themes
1. [Theme]: N testers hit this, avg severity X, checkpoint Y
2. [Theme]: ...
3. [Theme]: ...

## Critical blockers found
[None / list with issue links]

## Overall verdict: [PASS / FAIL]

## Next action
[Ship v0.1 / Fix and re-test / Escalate to architect]
```

---

## Anti-patterns to avoid

- **Do not use the founding team as testers.** Workarounds are invisible to people who wrote the code.
- **Do not coach testers.** If they get stuck, let them stay stuck and log it. That's the data.
- **Do not run more than 5 testers before reviewing.** Two sessions revealing the same critical blocker should pause the cohort.
- **Do not show the FEEDBACK_FORM.md simulation to testers.** It biases their answers. They get `FEEDBACK_FORM_TEMPLATE.md` only.
- **Do not accept sessions shorter than 90 min.** 30 min of timed work + 60 min of survey/debrief is the minimum for actionable data.
