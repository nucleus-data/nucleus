# PoC #5 — Tester Screening Questions

> **Purpose**: qualify candidates in a 5-minute DM or email exchange before they book a slot. A well-screened cohort produces cleaner signal. A poorly-screened cohort produces noise from mismatched skill levels, wrong environments, or insider bias.
>
> **How to use**: copy the 5 questions below into a reply when a candidate responds to your outreach. Score each answer using the rubric. Auto-disqualifiers end the conversation immediately.

---

## The 5 questions

Send these together in one message. Frame as: *"Quick qualifying questions before I send you the booking link — takes 2 minutes to answer:"*

```
1. How many years have you been building ETL/ELT pipelines or data warehouse loads hands-on?

2. What's your main OS for engineering work? Do you have Python 3.11 and Docker available
   on a laptop you administer yourself (not locked-down corp IT)?

3. Have you ever used or evaluated Apache Iceberg in a real project?

4. Have you heard of Nucleus before — from the team, GitHub, or any technical community
   discussion? (Honest answer only — this is a feature, not a bug.)

5. Do you have a free 90-minute block in the next 2 weeks where you won't be interrupted,
   and are you comfortable with silent observation during a 30-minute timed section?
```

---

## Scoring rubric

### Q1 — Experience depth

| Answer | Score | Action |
|---|---|---|
| ≥ 5 years hands-on DE | ✅ Strong pass | Book immediately |
| 3–4 years hands-on DE | ✅ Pass | Book |
| 2–3 years, includes hands-on ownership (not just support) | ⚠️ Borderline | Ask one follow-up: "Do you own the pipeline end-to-end, or primarily support someone else's?" — pass if owns it |
| < 2 years | ❌ Fail | Decline; offer to notify at v0.2 public launch |
| "Mostly analytics / BI, some light Python" | ❌ Fail | Wrong persona for beachhead validation |

---

### Q2 — Environment

| Answer | Score | Action |
|---|---|---|
| macOS + Python 3.11 + Docker | ✅ Strong pass (macOS is beachhead hardware) | Book |
| Linux + Python 3.11 + Docker | ✅ Pass | Book |
| WSL2 on Windows + Python 3.11 + Docker | ⚠️ Acceptable | Book; note as WSL2 session in tracking |
| Windows native (PowerShell only, no WSL2) | ❌ Fail for v0.1 | Decline; note for Windows-native future milestone |
| "Corp IT laptop, can't install freely" | ❌ **Auto-disqualifier** | Cannot run the test meaningfully |
| Python 3.10 or 3.12 | ⚠️ Flag | Ask to install 3.11 via `pyenv` / `mise`; confirm before booking |

---

### Q3 — Iceberg familiarity

| Answer | Score | Action |
|---|---|---|
| "Never used it" | ✅ Pass — fresh perspective | Book; tag session as "Iceberg-naive" |
| "Evaluated it, never shipped" | ✅ Pass | Book; tag as "Iceberg-aware" |
| "Used it in production (Delta Lake / Hudi experience)" | ✅ Pass | Book; tag as "Iceberg-native" — separate cohort tracking |
| "Currently a Nucleus user or contributor" | ❌ **Auto-disqualifier** | Conflict of interest — decline |

---

### Q4 — Insider exposure

| Answer | Score | Action |
|---|---|---|
| "Never heard of it" | ✅ Strong pass | Book |
| "Saw a link on HN / r/dataengineering, didn't click through" | ✅ Pass | Book; note in tracking |
| "Read the README on GitHub once" | ⚠️ Borderline | Ask: "Did you read any architecture docs or installation steps?" — pass if no |
| "I know someone on the team / was briefed / read architecture docs" | ❌ **Auto-disqualifier** | Insider bias; cannot validate fresh-user experience |
| OSS celebrity / influencer with known Nucleus affiliation | ⚠️ Escalate | Architect-level call before booking |

---

### Q5 — Availability and consent

| Answer | Score | Action |
|---|---|---|
| "Yes to both" | ✅ Pass | Send booking link |
| "Available but prefer async / no live observation" | ⚠️ Borderline | Accept if tester does think-aloud screen recording independently; note as non-standard session |
| "Only have 30–45 min" | ❌ Fail | 90 min is the minimum for valid data including debrief |
| "Yes but I'll need breaks / check Slack during" | ❌ Fail | Uninterrupted block is required for timing validity |

---

## Auto-disqualifiers (end conversation immediately — politely)

Any one of the following ends the screening:

| # | Auto-disqualifier | Response script |
|---|---|---|
| 1 | Currently a Nucleus contributor, reviewer, or insider-briefed contact | "Thanks for your interest! To keep results unbiased, we need participants who've had zero Nucleus exposure. I'll reach out when we run a follow-up study where insider perspective is valuable." |
| 2 | Corp-managed laptop, cannot install dev tools freely | "The test requires a machine you fully administer — corp restrictions would create friction that reflects IT policy, not the product. Happy to follow up when we have a sandbox environment." |
| 3 | Less than 2 years data engineering experience | "We're targeting senior-mid engineers for this round. We'll run a separate study for earlier-career engineers in a future cohort — happy to put you on the list." |
| 4 | Windows-native only (no WSL2, no macOS, no Linux) | "Our v0.1 is tested on macOS and Linux (WSL2 acceptable). Windows-native support is on the roadmap — drop me a note and I'll notify you when that milestone ships." |

---

## Decision matrix summary

| Q1 | Q2 | Q3 | Q4 | Q5 | Verdict |
|---|---|---|---|---|---|
| Pass | Pass | Any | Pass | Pass | ✅ Book immediately |
| Pass | Pass | Any | Pass | Borderline | ⚠️ Book with note |
| Borderline | Pass | Any | Pass | Pass | ⚠️ One follow-up Q then decide |
| Pass | Borderline (WSL2) | Any | Pass | Pass | ✅ Book, tag WSL2 |
| Any | Any | Auto-DQ | Any | Any | ❌ Decline |
| Any | Auto-DQ | Any | Any | Any | ❌ Decline |
| Any | Any | Any | Auto-DQ | Any | ❌ Decline |
| Fail | Any | Any | Any | Any | ❌ Decline |

**Target**: book 7–10 candidates to yield 5 completed sessions (assume ~30% cancellation / no-show rate).

---

## After booking: pre-session checklist (send 24h before)

Once a candidate passes screening and books a slot, send a confirmation that includes:

- [ ] Consent doc link (`CONSENT.md` or hosted version) — ask them to read and reply with attribution level before the session
- [ ] Session scenario doc (`SCENARIO.md`) — this is the ONLY doc they may read before the clock starts
- [ ] Reminder: no AI assistant use during the timed 30-minute section
- [ ] Calendar invite with Zoom/Meet link (if doing live observation)
- [ ] Instruction: "Have a terminal, Python 3.11, and Docker ready before we start — we won't spend setup time on that"
