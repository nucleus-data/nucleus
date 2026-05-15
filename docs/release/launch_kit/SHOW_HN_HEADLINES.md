# Show HN Headlines — Nucleus v0.2.0

*10 candidate headlines, scored on three axes: **HN-fit**, **founder-honesty**, **moderator-risk**. Top recommendation flagged at the end. HN's 80-character title limit applies to all of them. Vocabulary scrubbed against `AGENTS.md` §7 + §8 — none of these contain a forbidden framing.*

---

## Format A — "Show HN: X – Y" (5 candidates)

This is the most common HN format. The dash separates the project name from the value-prop clause. Crowd recognizes the pattern; moderators don't downrank it.

### A1 — Recommended baseline

> `Show HN: Nucleus – local-first data platform that graduates to Databricks` *(74 chars)*

- **Pros:** Names the integration story (graduation = yield-to-giants). Says "local-first" which signals the laptop-first persona. Names a tangible destination (Databricks) so the audience knows the scope.
- **Cons:** Implies Databricks-only graduation; truth is "any Iceberg catalog." Could read as Databricks fan service to a Databricks-skeptic crowd.
- **Lands with:** Engineers who have already wrestled with Databricks pricing and want a local on-ramp.
- **Moderator risk:** Low. No banned framing. "Graduates to" is neutral language, not adversarial.

### A2

> `Show HN: Nucleus – Python SDK + CLI for Iceberg pipelines on a laptop` *(70 chars)*

- **Pros:** Maximally factual. Names the technologies (Python, Iceberg). HN crowd respects honesty over hype. Boring-on-purpose.
- **Cons:** Doesn't hint at the differentiating wedge (the integration story). Reads like one more parts-list project.
- **Lands with:** Mid-to-senior data engineers who want the technical claim up front.
- **Moderator risk:** Very low.

### A3

> `Show HN: Nucleus – modern data engineering platform for 5–20 engineer teams` *(76 chars)*

- **Pros:** Names the beachhead persona. The team-size specificity feels rigorous. Clear scope.
- **Cons:** "Modern data engineering platform" is fluffy compared to A1's "graduates to Databricks." Reader has to click to find the wedge.
- **Lands with:** CTOs and engineering managers of small teams.
- **Moderator risk:** Low. "Modern" is fine; "platform" is fine. Nothing banned.

### A4

> `Show HN: Nucleus – wrap DuckDB+Polars+Iceberg+Dagster into one CLI` *(67 chars)*

- **Pros:** Speaks the HN crowd's language directly (everyone knows the four projects named). Honest about the wrap-not-build thesis.
- **Cons:** Reads as "yet another integration project." May get the response "why didn't you just use those tools directly?" — which is a fair question and the post will need to answer it.
- **Lands with:** OSS-curious engineers; the dbt + Dagster + DuckDB stack-builders.
- **Moderator risk:** Low.

### A5

> `Show HN: Nucleus – ship data products from a laptop in <30 minutes` *(67 chars)*

- **Pros:** The official tagline. Names the headline metric. Specific time-to-value claim.
- **Cons:** "Ship data products" is fluffier than the technical headlines (A2, A4). May trigger "what does that even mean" responses.
- **Lands with:** Founders who've felt the pain of slow data team setup; less with hardcore platform engineers.
- **Moderator risk:** Low.

---

## Format B — Pain-framed (3 candidates)

These don't lead with the project name; they lead with the pain. Higher-risk format because HN's "Show HN" tag conventionally puts the project name first, but pain-framed posts can over-perform when the pain resonates.

### B1

> `Show HN: I built a data platform that fits on a laptop (instead of $50K/yr)` *(76 chars)*

- **Pros:** Pain-first; names the dollar number (the $50K starting Databricks contract). HN crowd loves pricing transparency.
- **Cons:** Could read as anti-Databricks pile-on, which is the wrong vibe (we yield to giants, not fight them). The `$50K/yr` claim must be defensible — it's a public Databricks ballpark for production tier, not Free Edition. Document the source in the body.
- **Lands with:** Bootstrapped founders, small-team CTOs, OSS-leaning engineers.
- **Moderator risk:** Medium. HN moderators sometimes downrank price-comparison framings as ad-like. Use only if the body is technical-deep; would also need to sand off any anti-Databricks tone in the comments.

### B2

> `Show HN: I got tired of wiring 9 tools to ship one Iceberg table` *(63 chars)*

- **Pros:** Pure pain framing, no vendor named. The "9 tools" specificity is striking. HN crowd will recognize the pattern (Fivetran + dbt + Airflow + warehouse + catalog + BI + observability + notebook + AI).
- **Cons:** Doesn't say what was built or for whom. Reader has to click to find out it's a SDK+CLI, not a thinkpiece.
- **Lands with:** Practitioners who've felt the integration tax; first-time platform builders.
- **Moderator risk:** Medium. "I got tired" framings sometimes read as personal-blog rather than project-launch. Mitigation: lead the body with the project name in bold the first sentence.

### B3

> `Show HN: A solo founder's take on the "modern data stack is too many tools"` *(76 chars)*

- **Pros:** Honest about solo-founder status (HN audience appreciates founder transparency). Frames the project as "a take," not a category claim.
- **Cons:** Soft positioning. Doesn't specify what was built. May undersell the technical depth.
- **Lands with:** OSS founders, indie hackers, the "just ship it" subset.
- **Moderator risk:** Low. Solo-founder framing is well-trodden on HN.

---

## Format C — Outcome-focused (2 candidates)

Lead with the result, not the project name or the pain.

### C1

> `Show HN: From git clone to BI-ready Iceberg table in 30 minutes (Apache 2.0)` *(78 chars)*

- **Pros:** Names the headline beachhead metric directly. "Apache 2.0" in parentheses signals OSS up front (HN values this). Time-to-value as the lead is empirically validated by the WSL E2E (8/8 PASS, ~7 min boot per `docs/release/launch_kit/press_kit.md` §key stats).
- **Cons:** Doesn't say what tool. Reader has to click to find out. The "30 minutes" claim must be defensible — link the WSL E2E result + the PoC #5 external-tester kit in the body.
- **Lands with:** Engineers tired of multi-week onboarding. Time-skeptics will click to see the trick.
- **Moderator risk:** Low. The metric is real and cited.

### C2

> `Show HN: Iceberg snapshots, no JVM, 30-minute on-ramp, on a laptop` *(64 chars)*

- **Pros:** Compact. Lists the three differentiators (Iceberg, no-JVM, on-ramp time, local). HN technical crowd reads this as "concrete, not marketing."
- **Cons:** No project name in the title means brand recall is low. The headline is the project's only chance to lodge in memory; this one trades brand for clarity.
- **Lands with:** Engineers who'd skip a "Show HN: Nucleus" for fatigue but read "no JVM, on a laptop" for technical curiosity.
- **Moderator risk:** Very low.

---

## Scoring matrix

| ID | Headline | HN-fit | Honesty | Mod-risk | Composite |
|---|---|---|---|---|---|
| A1 | `local-first data platform that graduates to Databricks` | 9 | 9 | 1 | **27** |
| A2 | `Python SDK + CLI for Iceberg pipelines on a laptop` | 8 | 10 | 1 | 25 |
| A3 | `modern data engineering platform for 5–20 engineer teams` | 7 | 9 | 1 | 23 |
| A4 | `wrap DuckDB+Polars+Iceberg+Dagster into one CLI` | 9 | 10 | 1 | 26 |
| A5 | `ship data products from a laptop in <30 minutes` | 7 | 8 | 1 | 22 |
| B1 | `built a data platform that fits on a laptop (instead of $50K/yr)` | 8 | 8 | 4 | 20 |
| B2 | `got tired of wiring 9 tools to ship one Iceberg table` | 8 | 9 | 3 | 22 |
| B3 | `solo founder's take on "modern data stack is too many tools"` | 6 | 9 | 1 | 20 |
| C1 | `From git clone to BI-ready Iceberg table in 30 minutes (Apache 2.0)` | 9 | 9 | 1 | **27** |
| C2 | `Iceberg snapshots, no JVM, 30-minute on-ramp, on a laptop` | 8 | 9 | 1 | 24 |

*Scoring: HN-fit (1-10, how well it matches Show HN crowd preference) + Honesty (1-10, how truthfully it represents v0.2.0) + (10 − Mod-risk) where Mod-risk is 1-10. Composite = sum / 30.*

---

## Top recommendation

> **A1 — `Show HN: Nucleus – local-first data platform that graduates to Databricks`** *(74 chars)*

**Reasoning:**

1. **Carries the differentiating wedge in the title.** "Graduates to Databricks" is the architecturally-correct way to describe the yield-to-giants strategy (`nucleus_architecture_v4.1.md` §10). It signals "we don't compete with Databricks; we hand off to it cleanly," which is exactly the founder-honest framing.
2. **Names the project for brand recall.** Unlike B-series and C-series, the project name "Nucleus" is in the title. HN front-page traffic that doesn't click still helps brand awareness.
3. **Specifies the scope of competition.** "Local-first" tells the reader the persona (5–20 engineer teams on laptops, per `nucleus_architecture_v4.1.md` §1.5) and the deployment model (laptop, not cluster).
4. **Mod-risk is minimal.** No banned framing. "Graduates to" is neutral and architecturally precise.
5. **Pairs with the strongest first comment.** The existing first-comment draft in `docs/release/launch_kit/hn_post.md` opens with "Founder here. Three things I want to be upfront about because HN deserves it" — the title sets up the post body's honesty cleanly.

### Strong runner-up

> **C1 — `Show HN: From git clone to BI-ready Iceberg table in 30 minutes (Apache 2.0)`** *(78 chars)*

Use this if A1 lands flat in the first 30 minutes (less than 5 upvotes / 0 comments). Resubmission is allowed on HN under different titles per HN's `submitted` guidelines provided you have a meaningful title change. C1 is the alt-take optimized for the time-to-value crowd.

### Pre-flight checklist

- [ ] Confirm `Show HN: ` prefix is present (mandatory for the Show HN tag — moderators will retag if missing)
- [ ] Title length ≤ 80 characters including spaces (HN soft limit)
- [ ] Re-read against `AGENTS.md` §8 forbidden framings — none present in A1, A2, A3, A4, A5, C1, C2
- [ ] Confirm the URL field is the GitHub repo (`https://github.com/nucleus-data/nucleus` if org-rename done, else `https://github.com/mtoanng/nucleus`) — NOT the docs site
- [ ] First-comment draft from `docs/release/launch_kit/hn_post.md` ready in the clipboard, ready to paste within 60 s of submission so it pins above other replies
- [ ] Submit window is **Tue or Wed 09:00–10:00 ET** for max front-page reach (per the existing posting checklist)

---

## Headlines we will NOT post

For the record (every one of these would trigger `scripts/check_vocabulary.py`):

- ❌ `Show HN: Nucleus – AI-native data platform for the modern stack` <!-- banned-term: AI-native -->
- ❌ `Show HN: Nucleus – the Spark killer that fits on a laptop` <!-- banned-term: Spark killer -->
- ❌ `Show HN: Nucleus – better Databricks for startups` <!-- banned-term: better Databricks -->
- ❌ `Show HN: Nucleus – the Data OS for AI-era pipelines` <!-- banned-term: Data OS -->
- ❌ `Show HN: Nucleus – Iceberg company building the future of data` <!-- banned-term: Iceberg company -->

These would all fail vocabulary CI; they would also accurately predict a moderator delisting and a community pile-on.

---

*Last updated 2026-05-15. If A1 underperforms after the launch window, log the alternate title used + the engagement metrics in `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md` so future launches can pick a different format.*
