# PoC #5 — Recruitment Plan

## Hard rule (`AGENTS.md` §11.9)

**Testers MUST be external to the founding team.** Founding team intuition
lies to them; strangers' confusion is the truth. A "valid" session is one
where the moderator never intervened on Nucleus mechanics — see
[`SCENARIO.md`](SCENARIO.md) anti-bias rules.

## Target: 5 testers (over-recruit by 2; allow up to 7 if cheap)

Per `docs/specs/nucleus_poc_plan.md` §5 criterion 1, a minimum of **3 valid sessions**
is required for the PoC to be considered run. We aim for 5 to absorb
no-shows + invalidated sessions (moderator broke discipline).

### Profile

- **Role**: data engineer (NOT software engineer, NOT analyst, NOT ML
  engineer).
- **Experience**: 2-5 years (mid-level — matches `docs/specs/nucleus_poc_plan.md`
  §5 "mid-level data engineers... preferred").
- **Team context**: works at a startup or scale-up with ≤ 30 engineers
  total (interpretive from `docs/specs/nucleus_architecture_v4.1.md` §1.5
  "5-20 engineers").
- **Background**: has shipped at least one production pipeline (Airflow /
  dbt / Dagster / Spark / Snowflake / Databricks acceptable).
- **Nucleus exposure**: zero — never seen the repo, never read the
  architecture, never met the founder.

### Anti-profile (exclude)

- Anyone the founder personally knows beyond LinkedIn surface.
- Anyone who has worked at the same company as the founder.
- Anyone the founder has interviewed or who has interviewed the founder.
- Senior data engineers (> 5 years) — too much context bias.
- Junior data engineers (< 2 years) — get stuck on basics unrelated to
  Nucleus.
- ML engineers / data scientists — wrong persona.
- Current employees of a watch-listed competitor (Databricks, Snowflake,
  dbt Labs, Bauplan, Tower.dev, Tobiko — per
  `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.3
  watch list).

## Recruitment channels (in priority order)

1. **r/dataengineering Discord** — post a clearly-labeled paid
   user-research call (read sub rules first).
2. **Locally Optimistic Slack** — same.
3. **dbt Slack** — only the `#user-research` channel; cite the rules in
   the post.
4. **DEW (Data Engineering Weekly) newsletter** — paid slot if needed.
5. **LinkedIn cold outreach** — last resort; high noise, low signal.

## Compensation

- **$200-500 per 2-hour session** (per `docs/specs/nucleus_poc_plan.md` §5).
  Default: **$300** baseline; bump to $400-500 if a tester runs over
  with valuable findings.
- Pay via Wise / Wire / Stripe payouts — choose based on tester location.
- Reimburse for fresh AWS account ($1-5 in S3 fees if they use real S3
  rather than the offered MinIO container).
- **Pay in full** even if the tester aborts early — partial data is
  still valuable; refusing to pay biases the recruitment pool against
  honest failures.

## Recording + consent

- Screen recording (Loom / Zoom local recording).
- Think-aloud protocol — tester narrates what they're trying to do.
- Audio recording with consent form (template stub — fill in when v0.1
  ships).
- Data retention: 90 days, then transcript-only.
- Optional opt-in for anonymized inclusion in a retrospective blog post
  (separate checkbox; default off).

## Scheduling

- Block **90 minutes** on each tester's calendar (50% buffer over the
  60-minute nominal session — see [`SCENARIO.md`](SCENARIO.md) Acceptance).
- Run **all 5 sessions in a 5-day window** — minimizes the
  "I learned from the previous test and improved overnight" bias.
- Founder is **NOT** in the call. Use Calendly + Zoom; no founder
  attendance.
- Recordings are reviewed asynchronously *after all 5 sessions complete*
  — avoids re-tuning the scenario mid-cohort.
- **OS spread**: ≥ 3 macOS, ≥ 1 Linux or Windows-WSL2; surfaces OS-portability
  stuck-points before v0.1 ship.

## Anti-bias rules

- DO NOT pre-coach testers on Nucleus concepts.
- DO NOT answer questions during the session — testers note questions in
  a shared doc; founder answers all at the end (post-session interview).
- DO NOT show error messages in advance — testers must hit them organically.
- DO NOT defend the design when challenged in the post-session interview
  — *confusion IS the data* (`AGENTS.md` §11.9).
- DO NOT count a session if the moderator intervened on Nucleus mechanics
  (per `docs/specs/nucleus_poc_plan.md` §5 criterion 2).
