# PoC #5 — External Tester Recruitment (Founder Launch Kit)

> Goal: copy-ready outreach so you can post today and collect signups. North star remains AGENTS.md §11.8 — a five-engineer startup-style crew reaches a **BI-ready Iceberg-backed outcome** from `git clone` in **under 30 minutes** (hands-on portion capped there; session budgeting below allows setup + debrief).

---

## One-line pitch

“We pay `<$AMOUNT>` for ~90 minutes of your time to stress-test whether Nucleus’s CLI onboarding survives first contact.”

Replace `<$AMOUNT>` before publishing (example framing for applicants: **$50 Amazon gift card or equivalent** — founder picks one mechanism and applies it consistently).

---

## Beachhead persona (who Nucleus is optimizing for)

From architecture v4.1 §1.5 — **startup data group (~5–20 engineers), ~100 GB–5 TB total footprint, greenfield initiative**. Laptop-first (MacBook is the reference hardware). Production ambition skews **PostgreSQL sources + S3-compatible object storage**; PoC #5 sessions may exercise the **SQLite → filesystem Iceberg** slice that ships in early CLI milestones — still validates time-to-first-outcome and friction.

**Tester fit**: Think “hands-on IC on that squad,” not enterprise platform procurement.

---

## Hard eligibility (all must be true)

1. **External**: Never shipped commits/reviews/docs for Nucleus; no internal rehearsal briefings.
2. **Experience**: **≥ 3 years** hands-on data engineering or hybrid analytics-engineering (ETL/ELT, warehouses, orchestrators you operate yourself).
3. **Comfort**: Fluent enough with **CLI + git + Python 3.11 envs** that friction reflects product gaps, not first-day terminal nerves.
4. **Hardware/time**: MacBook or Linux laptop you administer; **~90 minutes** uninterrupted (≈30 min timed hands-on + buffer + short survey/debrief).
5. **Fresh eyes**: No prereading Nucleus architecture essays — quickstart + session scenario only.

---

## Compensation / incentive

| Founder decision | Guidance |
|------------------|-----------|
| Amount | Lock **`<$AMOUNT>`** globally before day-one outreach (example anchor: **USD 50** retail voucher). |
| Mechanism | Amazon / Visa-style voucher **or** regional equivalent if cards fail locally — pick **one** path per cohort. |
| Partial completion | Pay full incentive even if they bail mid-session — honest dropout still informs UX. |

Document consent + recording choice alongside outreach (`CONSENT.md`).

---

## Scheduling (**PLACEHOLDER**)

Public booking link (replace before blast):

**`https://calendly.com/<founder-handle>/nucleus-beachhead-30min`** — **`PLACEHOLDER`**: founder must swap hostname + path after creating event type (~75–90 min blocks).

Mirror availability privately first so teammates cannot squat slots meant for externals.

---

## Privacy & data collection

- Only automated tooling touched during PoC #5 lives **on the participant machine** unless founder separately observes Zoom/Loom.
- Survey exports + optional recording retention rules → **`docs/poc/p5_beachhead/CONSENT.md`** (have testers acknowledge **before** the clock starts).
- Never scrape Discord/reddit DMs for marketing lists — invite replies route through founder-controlled inbox/sheet.

---

## Channel playbook (quick picks)

| Priority | Surface | Notes |
|----------|---------|-------|
| A | LinkedIn DMs | High-trust warm intros first |
| B | Twitter/X DM | Short blurbs only |
| C | Data-engineering Discords | Observe `#rules` — disclose paid research |

Always disclose compensation up front + approximate duration.

---

## Outreach Template — LinkedIn DM (**≤100 words**)

Hi `<first>` — quick paid research invite (gift card `<$AMOUNT>`, founder confirms retailer).

Building **Nucleus**, local-first Python CLI/SDK around Iceberg-native assets — validating whether **five-engineer-startup-shaped teams** hit **BI-ready Iceberg output under ~30 minutes** after `git clone`.

Seeking **3+ yrs hands-on data eng**, CLI/git/Python-comfy, **90-minute slot**, Mac/Linux laptop. Zero prior Nucleus exposure.

Schedule (**PLACEHOLDER**): https://calendly.com/`<founder-handle>`/nucleus-beachhead-30min

Consent overview: `docs/poc/p5_beachhead/CONSENT.md`

Interested?

---

## Outreach Template — Twitter / X DM (**≤100 words**)

Paid UX cohort (~90 min, `<$AMOUNT>` voucher — founder confirms).

Need **external data engineers (≥3 yrs)** comfortable with CLI/git/Python on Mac/Linux to run **`git clone` → first Iceberg-backed BI-ready outcome in \<30 min** on **Nucleus** (Iceberg-native local-first tooling).

No prior Nucleus familiarity.

Booking (**PLACEHOLDER**): https://calendly.com/`<founder-handle>`/nucleus-beachhead-30min

Consent: `docs/poc/p5_beachhead/CONSENT.md`

Reply “in” + time zone.

---

## Outreach Template — Discord / Slack forum post (**≤100 words**)

`[paid research]` — **Nucleus** CLI onboarding validation.

Looking for **3 external IC-level data engineers (≥3 yrs)** who live in terminals/git/Python on Mac/Linux. Session ~**90 min** (`<$AMOUNT>` gift card — founder picks retailer).

You prove/disprove **\<30 min** from **`git clone` → BI-ready Iceberg-backed output** without insider hints.

Book (**PLACEHOLDER**): https://calendly.com/`<founder-handle>`/nucleus-beachhead-30min

Consent summary lives at repo path **`docs/poc/p5_beachhead/CONSENT.md`** — DM founder `<contact>` after booking.

Mods ping me if flair tweaks needed.

---

## Screening cheatsheet (5 DM replies → qualify fast)

1. Years shipping pipelines / warehouse loads?
2. OS + Python 3.11 availability tomorrow?
3. Ever touched Iceberg knowingly?
4. Conflicted insider ties to Nucleus/repo maintainers?
5. Comfortable silent-founder observation during timed slice?

Green-light ≥4 positives — escalate ambiguous OSS celebrities to architect chat.

---

## Session mechanics reminders

- **Silent observation** during the timed `<30 min` stretch — founder interruption corrupts measurements unless tester taps glass labeled emergency-only.
- **Think-aloud optional** — if awkward, rely on friction log embedded in scenario companion docs post-session.
- **Survey-first quantitative backup**: replicate prompts inside hosted form blueprint [`FEEDBACK_FORM.md`](./FEEDBACK_FORM.md).
- Rotate testers across calendar spread — minimizes hallway chatter leakage cohort-wide.

---

## Success thresholds (tie-break against poc_plan §5)

- Majority finishes timed slice ≤ **30 min** median vs cohort hypothesis targets (< **45 min P90**).
- Few enough systemic friction themes they cluster onto actionable backlog cards inside release horizon.

Miss thresholds ⇒ revisit onboarding backlog — metric stays authoritative.

---

## Founder checklist minutes before blast

- [ ] Amount finalized replacing `<$AMOUNT>`
- [ ] Calendly live + Zapier/email notifier wired (PLACEHOLDER retired)
- [ ] Recording decision propagated → CONSENT + outreach wording coherent
- [ ] Hosted survey instantiated using FEEDBACK_FORM blueprint rows
- [ ] Repo pinned revision testers clone (`SHA`/branch memo internally)

Welcome pings-only inbox monitored `<founder-email>`.
