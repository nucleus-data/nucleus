# PoC #5 — External Tester Recruitment (Founder Launch Kit)

> **Goal**: copy-ready outreach so you can post today and collect signups. North star: a five-engineer startup-shaped crew reaches a **BI-ready Iceberg-backed outcome** from `git clone` in **under 30 minutes** (hands-on portion capped there; session budget below allows setup + debrief).

---

## Subject lines (4 variations — rotate to avoid filter patterns)

1. **[Paid UX study, ~90 min]** Help us stress-test a new data CLI before public launch
2. **Paid research ($`<$AMOUNT>`)** — data engineer wanted: prove our "30-min to Iceberg table" claim
3. Quick paid session (~90 min): `git clone` → BI-ready Iceberg table — can you do it in 30 min?
4. [Paid research] Calling data engineers — Iceberg-native CLI onboarding study, ~90 min

*Replace `<$AMOUNT>` before posting. Subject #1 performs best on cold outreach; #3 best for communities where builders self-select.*

---

## The pitch — 3-paragraph invite email / DM body

Hi `<FIRST>`,

I'm the founder of **Nucleus** — a local-first Python CLI/SDK for building Iceberg-native data pipelines, built for startup data teams who are tired of over-engineered stacks. We're running a paid study before our public launch to find out if a data engineer with no prior Nucleus exposure can reach a BI-ready Iceberg table from `git clone` in under 30 minutes.

The session is ~90 minutes total: a ~30-minute timed hands-on slice (you work alone, I observe silently), a short friction survey, and a 15-minute debrief. You get **`<$AMOUNT>`** as a gift card (retailer confirmed before session), and your feedback directly shapes what we fix before launch. You keep full rights to everything you say or write — I only use it internally to improve the product.

If you have **3+ years of hands-on data engineering** (ETL/ELT, orchestrators, warehouses you actually operate yourself), a Mac or Linux laptop you administer, and ~90 uninterrupted minutes in the next two weeks — I'd love to have you. Zero Nucleus prior knowledge required; that's the point. Reply here or book directly: **`[BOOK_30MIN_HERE]`**

`<FOUNDER NAME>`

---

## What you'll do in 30 minutes

- Open a fresh terminal on your own laptop
- Clone a public repo and install Nucleus (one `pip install` command)
- Create a new project with one CLI command
- Ingest a small dataset into an Iceberg-backed asset
- Query it with plain SQL and confirm the expected result

That's it. You prove — or disprove — our 30-minute promise. Every stumble, typo, confusing error message, and "I'd quit here" moment is more valuable than a smooth run.

---

## What you get

| | |
|---|---|
| **Compensation** | `<$AMOUNT>` gift card (Amazon / Visa-style / regional equivalent — founder confirms retailer before session) |
| **Partial completion** | Full incentive paid even if you bail early — honest dropout is still actionable UX data |
| **Early-user credit** | Named in the acknowledgments section of our public docs (opt-in, Level B/C consent) |
| **Direct founder access** | 15-minute debrief where you get direct answers from the founder — no sales pitch |
| **Influence the roadmap** | Your friction log goes straight into the v0.1 backlog, tracked publicly |
| **No obligation** | One session, no follow-up asks without your explicit permission |

---

## Beachhead persona (who Nucleus is optimizing for)

From `docs/specs/nucleus_architecture_v4.1.md` §1.5 — **startup data group (~5–20 engineers), ~100 GB–5 TB total footprint, greenfield initiative**. Laptop-first (MacBook is the reference hardware). Production ambition skews **PostgreSQL sources + S3-compatible object storage**; PoC #5 sessions exercise the **SQLite → filesystem Iceberg** slice — still validates time-to-first-outcome and real friction.

**Tester fit**: "Hands-on IC on that squad," not enterprise platform procurement.

---

## Hard eligibility (all must be true)

1. **External**: Never shipped commits, reviews, or docs for Nucleus; no internal rehearsal briefings.
2. **Experience**: **≥ 3 years** hands-on data engineering or hybrid analytics-engineering (ETL/ELT, warehouses, orchestrators you operate yourself).
3. **Comfort**: Fluent enough with **CLI + git + Python 3.11 envs** that friction reflects product gaps, not first-day terminal nerves.
4. **Hardware/time**: MacBook or Linux laptop you administer; **~90 minutes** uninterrupted (≈30 min timed hands-on + buffer + short survey/debrief).
5. **Fresh eyes**: No prereading Nucleus architecture essays — quickstart + session scenario only.

---

## Compensation / incentive

| Founder decision | Guidance |
|------------------|-----------|
| **Amount** | Lock **`<$AMOUNT>`** globally before day-one outreach (example anchor: **USD 50** retail voucher). |
| **Mechanism** | Amazon / Visa-style voucher **or** regional equivalent if cards fail locally — pick **one** path per cohort. |
| **Partial completion** | Pay full incentive even if they bail mid-session — honest dropout still informs UX. |

Document consent + recording choice alongside outreach (see `CONSENT.md`).

---

## Scheduling

Public booking link (replace before blast):

**`[BOOK_30MIN_HERE]`** ← founder swaps with live Calendly/Cal.com URL (~75–90 min blocks, buffer between slots).

*Example format: `https://calendly.com/<founder-handle>/nucleus-beachhead-90min`*

Mirror availability privately first so teammates cannot squat slots meant for externals.

---

## Channel playbook (priority order)

| Priority | Channel | Notes |
|----------|---------|-------|
| **A** | **Hacker News** "Who's Hiring / Who Wants to Be Hired" thread | Highest signal-to-noise; DE lurkers self-select; post on first weekday of the month |
| **B** | **r/dataengineering** (500K+ members) | Use `[Research Participation]` flair; read subreddit rules first; disclose compensation up front |
| **C** | **LinkedIn DMs** (warm intros first) | High-trust; reach 3rd-degree contacts through mutual DE connections |
| **D** | **Data-engineering Discords / Slacks** | dbt Slack `#jobs-and-opportunities`, Data Engineering Discord; always disclose paid research + observe `#rules` |
| **E** | **Twitter / X DMs** | Short blurbs only; good for quick "in" confirmations |
| **F** | **Indie Hackers** community | Post in "Looking for feedback" or "User research" boards; builders are receptive |
| **G** | **dev.to** | Write a 200-word "Calling data engineers" post linking to calendar |
| **H** | **lobste.rs** | Smaller, high-signal; tag `[data-engineering]` or `[tools]` |

*Always disclose compensation up front + approximate duration. Never scrape DMs for marketing lists.*

---

## Outreach template — LinkedIn DM (≤100 words)

Hi `<FIRST>` — quick paid research invite (gift card `<$AMOUNT>`, founder confirms retailer).

Building **Nucleus**, a local-first Python CLI/SDK for Iceberg-native data pipelines — validating whether **startup-shaped teams** hit **BI-ready Iceberg output under ~30 minutes** after `git clone`.

Seeking **3+ yrs hands-on data eng**, CLI/git/Python-comfy, **90-minute slot**, Mac/Linux laptop. Zero prior Nucleus exposure.

Book here: `[BOOK_30MIN_HERE]`

Consent overview: `docs/internal/poc/p5_beachhead/CONSENT.md`

Interested?

---

## Outreach template — Twitter / X DM (≤100 words)

Paid UX cohort (~90 min, `<$AMOUNT>` voucher — founder confirms).

Need **external data engineers (≥3 yrs)** comfortable with CLI/git/Python on Mac/Linux to run **`git clone` → first Iceberg-backed BI-ready outcome in \<30 min** on **Nucleus** (Iceberg-native local-first tooling).

Zero prior Nucleus familiarity required.

Book here: `[BOOK_30MIN_HERE]`

Reply "in" + time zone.

---

## Outreach template — Discord / Slack forum post (≤100 words)

`[paid research]` — **Nucleus** CLI onboarding validation.

Looking for **3 external IC-level data engineers (≥3 yrs)** who live in terminals/git/Python on Mac/Linux. Session ~**90 min** (`<$AMOUNT>` gift card — founder picks retailer).

You prove/disprove **\<30 min** from **`git clone` → BI-ready Iceberg-backed output** without insider hints.

Book here: `[BOOK_30MIN_HERE]`

Mods: ping me if flair tweaks needed.

---

## Outreach template — Hacker News (≤150 words)

**Title**: Paying data engineers ($`<AMOUNT>`) to try our CLI cold — 30-min timed challenge

**Body**:
We're building Nucleus — a local-first Python CLI/SDK for Iceberg-native data pipelines aimed at startup data teams. Before public launch, we want to know if an external data engineer can reach a BI-ready Iceberg table from `git clone` in under 30 minutes, with no hand-holding.

Session is ~90 min total (30 min timed + survey + debrief). Compensation: `<$AMOUNT>` gift card.

Requirements: ≥3 years hands-on data engineering, CLI + Python comfortable, Mac/Linux laptop, no prior Nucleus exposure.

Book: `[BOOK_30MIN_HERE]`

---

## Outreach template — r/dataengineering post (≤150 words)

**Title**: [Research Participation] Paying data engineers ($`<AMOUNT>`) to stress-test a new Iceberg CLI — 90 min, no strings

**Body**:
Founder here. Building Nucleus — a local-first Python CLI for Iceberg-native pipelines. We're running a paid UX study before public launch.

The challenge: `git clone` → BI-ready Iceberg table in under 30 minutes. No insider hints. You work alone, I observe silently.

**What you need**: ≥3 years hands-on DE, CLI/Python comfortable, Mac or Linux laptop, 90-minute slot in the next 2 weeks.

**What you get**: `<$AMOUNT>` gift card + 15-min founder debrief + your feedback directly in the backlog.

Disclosure: this is paid user research. I will not use your contact details for anything beyond scheduling.

DM me or book: `[BOOK_30MIN_HERE]`

---

## Screening criteria (5 qualifying questions)

Use these to qualify candidates who reply before booking. A 5-minute DM exchange saves a 90-minute wasted slot.

1. **Experience depth**: "How many years have you been building ETL/ELT pipelines or warehouse loads hands-on?" → Pass: ≥3 years. Fail: <2 years. Borderline (2-3 years): escalate to live call.
2. **Environment check**: "Do you have Python 3.11 and Docker available on a Mac or Linux laptop you control?" → Pass: yes to both. Fail: Windows-only (WSL2 acceptable for v0.1 validation).
3. **Iceberg familiarity**: "Have you worked with Apache Iceberg in production or evaluated it seriously?" → Pass: any answer (Iceberg-native testers are welcome; track separately). Flag: tester already runs Nucleus in production (disqualifier — conflict of interest).
4. **Insider check**: "Are you aware of Nucleus from the founding team, GitHub, or any insider briefing?" → Pass: no. Fail: yes — escalate to architect chat to verify no prior exposure.
5. **Availability + consent**: "Are you available for a ~90-minute session in the next 2 weeks, and comfortable with silent observation during the 30-minute timed section?" → Pass: yes to both. Borderline: async/text-only OK if think-aloud declined — log as non-standard session.

**Green-light criteria**: ≥4 passes — book immediately. 3 passes — founder judgment call. <3 passes — politely decline, offer to notify at v0.2 public launch.

---

## Privacy & data collection

- All automated tooling runs **on the participant machine** during the session; nothing is extracted from their system.
- Survey exports + optional recording retention rules → see `CONSENT.md` (have testers acknowledge before the clock starts).
- Never scrape Discord/Reddit DMs for marketing lists — replies route through founder-controlled inbox.

---

## Session mechanics reminders

- **Silent observation** during the timed ≤30 min stretch — founder interruption corrupts measurements unless tester signals an emergency.
- **Think-aloud optional** — if awkward, rely on friction log embedded in `SCENARIO.md` post-session.
- **Quantitative backup**: all pillars scored in `FEEDBACK_FORM_TEMPLATE.md` — have testers open it before the clock starts.
- Rotate testers across calendar spread — minimizes hallway-chatter leakage cohort-wide.

---

## Success thresholds (ties back to `docs/specs/nucleus_poc_plan.md` §5)

- Majority finishes timed slice ≤ **30 min** median (P90 target: < **45 min**).
- NPS ≥ **7/10** average from all testers.
- ≥ **3 of 5** testers say "would recommend to a colleague in a similar role."
- **0** critical-severity friction points unsurfaced before v0.1 public launch.

Miss thresholds ⇒ revisit onboarding backlog — metric stays authoritative.

---

## Founder checklist (minutes before blast)

- [ ] `<$AMOUNT>` finalized — replace all instances globally before posting
- [ ] `[BOOK_30MIN_HERE]` live — Calendly/Cal.com event created, 75–90 min blocks, email notifier wired
- [ ] GitHub remote `github.com/nucleus-data/nucleus` resolves (currently 404 — **blocker for real external testers**)
- [ ] Recording decision made → CONSENT levels propagated to all outreach wording
- [ ] `FEEDBACK_FORM_TEMPLATE.md` hosted or shared link ready (testers need it before clock starts)
- [ ] Repo SHA / branch pinned internally — note which revision testers clone
- [ ] Inbox monitored: `<founder-email>`
