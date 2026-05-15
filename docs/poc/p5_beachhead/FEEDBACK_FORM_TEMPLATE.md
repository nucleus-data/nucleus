# PoC #5 — External Tester Feedback Form (BLANK TEMPLATE)

> **Instructions**: Open this file in a text editor **before the session clock starts**. Fill in Part 1 (tester info) immediately. Keep it open during the session and log friction in real time in Part 2. Fill Parts 3 and 4 immediately after the timed section ends. Part 5 after the debrief.
>
> For an example of a completed form, see `FEEDBACK_FORM_FILLED_2026-05-15.md`.
>
> Privacy: your responses are handled per `CONSENT.md`. Attribution level applies to all content in this form.

---

## Part 1 — Tester info (fill before clock starts)

| Field | Your answer |
|-------|-------------|
| Tester ID (assigned by founder) | |
| Session date | |
| OS + Python version | |
| Years hands-on data engineering | |
| Current role / company size (optional) | |
| Primary stack today (e.g., dbt + Airflow + Snowflake) | |
| Attribution level (A / B / C per `CONSENT.md`) | |
| Recording consent (yes / no) | |
| Have you ever used Apache Iceberg in production? | |
| Clock start time | |
| Clock stop time | |

---

## Part 2 — Real-time friction log (fill during the session)

> Log **every single friction point** — no filtering. A "friction point" is anything that slowed you down, confused you, made you think "I'd quit here in a real job," or required a workaround. Log it in the moment, not retroactively.

| Time elapsed | Step | What happened (be specific) | Severity (Low / Med / High / Critical) | Would you quit here on a real eval? (Y/N) |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |

*(Add rows as needed)*

---

## Part 3 — Timing checkpoints (fill during / immediately after)

| Checkpoint | Target | Your actual time | Status (PASS / FAIL / PARTIAL) | Notes |
|---|---|---|---|---|
| 1. Discovery (README + quickstart read) | < 5 min | | | |
| 2. Install (`pip install -e ".[dev]"`) | < 5 min | | | |
| 3. First project (`nucleus init <name>`) | < 5 min | | | |
| 4. Boot stack (`nucleus up`) | < 2 min | | | |
| 5. Ingest (`nucleus ingest sqlite://...`) | < 8 min | | | |
| 6. Query (`nucleus query "SELECT ..."`) | < 3 min | | | |
| 7. First custom asset (`nucleus run <key>`) | < 5 min | | | |
| 8. Shutdown (`nucleus down`) | < 1 min | | | |
| **Total wall time** | **< 30 min** | | | |

---

## Part 4 — Quantitative scores (fill immediately after timed section)

Rate each item **1–5** (1 = strongly disagree / terrible; 5 = strongly agree / excellent).

> These map to Nucleus's five design pillars plus three UX-specific dimensions and a net promoter question.

| # | Statement | Score (1–5) | Notes (optional) |
|---|---|---|---|
| 1 | The tool performed fast on my laptop with minimal resource usage | | |
| 2 | I can tell it would be easy to swap out components (SQL engine, catalog, connectors) if needed | | |
| 3 | The error messages and CLI output felt like they were designed to help me, not just dump internals | | |
| 4 | The UX felt familiar — I recognized patterns from dbt, Dagster, or similar tools I already use | | |
| 5 | I believe my data would stay portable if I outgrew this tool and moved to Databricks or Snowflake | | |
| 6 | The installation process was smooth and predictable | | |
| 7 | Building my first Iceberg-backed asset felt straightforward | | |
| 8 | When something went wrong, the error messages clearly told me what to do next | | |
| 9 | **NPS**: I would recommend this tool to a colleague at a startup data team (1 = never, 10 = definitely) — *(use 1–10 scale for this item only)* | /10 | |

**Pillar mapping**: Questions 1–5 map to the five design pillars. Questions 6–8 are UX-specific. Question 9 is net promoter.

---

## Part 5 — Qualitative (fill after debrief)

Answer in plain language. No minimum or maximum length. These are the most valuable part.

### Q1: What was the single best thing about the experience?

*(What would make you say "I'd show this to my team on Monday"?)*

> [Your answer here]

---

### Q2: What was the single biggest friction point?

*(If one thing almost made you close the terminal and walk away, what was it? Be specific — which command, which error, which moment.)*

> [Your answer here]

---

### Q3: What's missing for your day-to-day job?

*(What would you need to see before bringing this into a real project? What does your current stack do that this doesn't?)*

> [Your answer here]

---

## Part 6 — Error message log

For each error you encountered (whether expected or unexpected), note the verbatim output and your reaction.

| Error case | Verbatim output (paste or paraphrase) | Your interpretation | Helpful? (Y / N / Partial) |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

---

## Part 7 — Overall verdict

**Would you bring this to your team?**

☐ Yes, right now  
☐ Yes, in 4–8 weeks after these fixes: ________________  
☐ No, these blockers are too fundamental: ________________  
☐ Unsure — want to see more of the product first

**One sentence you'd say to a data engineer colleague about this tool:**

> [Your answer here]

---

## Consent reminder

By submitting this form, you confirm your consent as specified in `CONSENT.md` and the attribution level you selected in Part 1.

To request deletion of your responses, email `<founder-email>` within 14 days of your session date.
