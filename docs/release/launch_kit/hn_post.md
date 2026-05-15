# Hacker News Submission — Nucleus v0.2.0

*Target: <https://news.ycombinator.com/submit> · Submit window: Tue/Wed 09:00–10:00 ET for max visibility · Founder voice, technical, honest.*

---

## Title (78 chars, ≤80 char HN limit)

```
Show HN: Nucleus – local-first Iceberg pipelines from a laptop, in <30 minutes
```

### Title alternates (use if A/B testing or first lands flat)

- `Show HN: Nucleus – Python SDK + CLI for Iceberg-native pipelines on a laptop` (76)
- `Show HN: Ship data products from a laptop with Iceberg + DuckDB + Polars` (72)
- `Show HN: Nucleus – modern data engineering platform for 5–20 engineer teams` (75)

---

## URL field

```
https://github.com/nucleus-data/nucleus
```

*Use the canonical org URL for launch. The legacy personal remote is historical only.*

---

## First-comment draft (post immediately after submission so it pins context)

> Founder here. Three things I want to be upfront about because HN deserves it.
>
> **1. What Nucleus actually is.** A local-first Python SDK + CLI that wraps DuckDB, Polars, Apache Iceberg (via pyiceberg), and embedded orchestration (Dagster, hidden behind the `ctx` SDK) into a single `pip install nucleus`. The headline use case is a 5–20 engineer team going from `git clone` to a BI-ready Iceberg table in under 30 minutes on a laptop. No JVM in the default path. Apache 2.0. The eight CLI commands (`init / up / down / run / ingest / query / chat / version`) are intentionally boring — `nucleus ingest postgres://... --table public.orders --as raw.orders` is the one-liner that makes the 30-min metric possible.
>
> **2. What it's NOT.** Not a Spark replacement. Not a Databricks competitor. Not "AI-native" — it's AI-ready, the Copilot is one optional chat command via litellm. Not a database, not a SQL engine, not a vector DB. Not a "Data OS" or any of those framings. The proprietary code is ~13K LOC of glue (with a 30K LOC ceiling we will hit before v1.0); 95% of execution time at any meaningful workload runs in C++ (DuckDB, pyarrow), Rust (Polars), or wire-bound network I/O. The whole thesis is wrap-not-build. <!-- banned-term: AI-native --> <!-- banned-term: Data OS -->
>
> **3. Honest disclosures.**
> - It's beta. v0.2.0 is the first publicly available release; v0.1.0 was an internal beta two days ago.
> - Performance numbers in `docs/benchmarks/2026-05-15_baseline.md` show 11 measured failures vs aspirational targets. Boot time is ~2 s on a contention-loaded host (target was <500 ms — the host had only 1 GB free RAM during the run, so re-measurement on a freshly-booted laptop is tracked for v0.2.1). The B4 concurrent-run safety test FAILs on Windows because NTFS lock semantics differ from POSIX (`fcntl.flock` works; `msvcrt.locking` byte-range doesn't serialize the same way) — Linux/WSL passes. I'm publishing the numbers honestly rather than re-running until they pass.
> - This is a solo project. There is no team behind it (yet). The Mo 24 decision gate per ADR-002 §8.3 forces me to commit to (a) raise, (b) hand off, or (c) accept indie outcome — no default extension permitted.
>
> The architecture doc (`nucleus_architecture_v4.1.md`, ~50 min read) is the source of truth. The "yield to giants" strategy is explicit: the day a team outgrows Nucleus, they point Databricks/Snowflake at the same S3 + Iceberg catalog and they're done. Mode 1 graduation is zero effort because it's just Iceberg portability — there is no Nucleus byte format to migrate off.
>
> The honest pitch: if you're a small team building greenfield analytics on 100 GB–5 TB of data and the existing menu (Fivetran + dbt + Airflow + warehouse + catalog + BI = 6 tools) feels like overkill before any value flows, give this a try. If you have 100+ engineers and a 100 TB warehouse, it is genuinely not for you yet (and may never be — see the scale-out audit at `docs/research/scale_out_audit.md` for why a Rust rewrite of Nucleus internals would be the wrong optimization).
>
> Quickstart:
>
>     python3.11 -m venv .venv && source .venv/bin/activate
>     pip install nucleus
>     nucleus init demo && cd demo
>     nucleus up
>     nucleus run example.greeting
>     nucleus query "SELECT * FROM {{ ref('example.greeting') }}"
>
> Happy to answer the obvious questions: why not dbt, why not Dagster directly, why not Spark, why not Databricks, why Iceberg over Delta. The honest one-line on each: dbt has the macro ecosystem and we don't (we own ~180 LOC of Jinja+ref resolver with a hard 2,500 LOC scope ceiling so we don't accidentally rebuild dbt — see v4.1 §5.6.0); Dagster directly is what we wrap, but the boot time + error-translation + asset-graph-hidden ergonomics meant a thin layer earned its keep; Spark is the JVM constraint we reject by design; Databricks is what we yield to, not what we replace; Iceberg is what every catalog is converging on (Polaris, Lakekeeper, Unity, R2) and Delta isn't.
>
> Code: <https://github.com/nucleus-data/nucleus>. Apache 2.0. Issues + PRs welcome (limited contributor scope while Tier 1 stabilizes — open an issue first for anything large). If PyPI publish is not green yet, defer posting; the local-dev fallback is `git clone https://github.com/nucleus-data/nucleus.git && cd nucleus && pip install -e ".[dev]"`.

---

## Anticipated HN questions + prepared responses

> *Drop these as inline replies as the discussion develops. Do NOT batch-paste them up front; let the thread breathe.*

**Q: How is this different from dbt-core + Dagster + DuckDB + pyiceberg?**

> Honestly? It's the same parts, with a single SDK and CLI on top so a 5-engineer team isn't doing the integration work themselves. The wins: one auth model, one boot command (`nucleus up`), one error namespace (every error is an `NE####` code with a `docs_url`), one asset graph that's the same primitive whether you write it in Python or SQL, one Workbench. The losses: dbt's macro ecosystem isn't ours (we cap our SQL resolver at 2,500 LOC by hard policy — `nucleus_architecture_v4.1.md` §5.6.0 — so we don't accidentally rebuild dbt), and Dagster's web UI is hidden by default (you opt into it with `nucleus enable compat-dagster`).

**Q: Why no JVM constraint?**

> Per Hard Constraint #1 in `AGENTS.md`. JVM in the always-on path means cold boot times measured in tens of seconds and idle RAM measured in gigabytes. Neither is acceptable for a tool whose North Star metric is "5-engineer team productive in 30 minutes on a laptop." That's why we wrap pyiceberg (Python+Rust) instead of iceberg-java, and Lakekeeper (Rust) instead of REST catalogs that ship a JVM.

**Q: Why Iceberg, not Delta?**

> Iceberg is what catalogs are converging on (Polaris ASF, Lakekeeper Rust, R2, Unity-Iceberg-compat, Snowflake Iceberg-compat). Delta is great for Databricks shops; less universal across the catalog ecosystem. The yield-to-giants story works at zero effort because the bytes Nucleus writes to S3 are valid Iceberg snapshots that anything Iceberg-aware can read.

**Q: How does the AI Copilot work?**

> One CLI command (`nucleus chat "..."`), routed through litellm to your provider of choice (anthropic / openai / ollama). API keys come from your shell env, never logged, never sent to anyone but the LLM provider. The opt-in consent is stored at `.nucleus/copilot_opt_in`. Cost ceiling defaults to $0.10/call. Nucleus has no servers, no telemetry. v0.2 is intentionally just chat — schema-aware completion is v0.3, lineage-aware refactoring is v0.5. We're not selling AI as the headline.

**Q: What's the LOC budget?**

> 30K LOC ceiling for proprietary code by v1.0, hard-enforced by `scripts/loc_budget.py` in CI. We're at ~13K LOC today (v0.2). The whole thesis is wrap-not-build; if a feature can't fit under that ceiling, it's not in v1.0.

**Q: Why not just use Databricks Free Edition / Snowflake Trial?**

> Both are excellent and we yield to them at scale. The friction we eliminate is the cluster boot time, the cloud account setup, the credential plumbing, the cost surprise, and the proprietary-format anxiety. If your team is going to live on Databricks anyway, Nucleus might be the local-dev environment that makes your code identical-to-prod (Iceberg → S3 = Iceberg → Databricks). If you outgrow Nucleus in 18 months, your bytes are already in the right format. There is no migration.

**Q: How do you make money?**

> The OSS core is complete and free forever (Apache 2.0). Future tiers (per v4.1 §17): managed Cloud (catalog + storage + secrets, $20/seat/mo target), premium Copilot Pro (+$50/seat for richer agent runtime, v0.5+), Enterprise (SSO/SAML/audit, $50K-500K/yr). None of this is shipping today. v0.2 is OSS only. The Mo 24 gate forces an explicit founder choice: raise, hand off, or accept indie. No default extension.

**Q: Why a 30-minute beachhead metric specifically?**

> Because anything longer than that doesn't get tried. A 5-engineer team has one engineer per role; if "evaluate Nucleus" takes a week of someone's time, it doesn't happen. 30 minutes is roughly "I tried it before lunch and we have a real ingestion working before standup tomorrow." That metric drives every cut decision in v0.1 and v0.2 — anything that doesn't serve it is deferred.

**Q: Composability — what happens if Dagster goes hostile / dies?**

> `nucleus-mini-scheduler` is the documented fallback (~3-5K LOC; design ready, not yet built). The full mini-scheduler ships by v1.0 per `nucleus_architecture_v4.1.md` §6.5 + ADR-024. The `ctx` SDK API surface stays unchanged through any Dagster swap — `dagster_leak_check.py` enforces zero `dagster.*` classnames in user-facing strings, and per the replaceability mandate, zero user code grep for `dagster` import will succeed. If Dagster goes hostile tomorrow, we have 30 days to ship the full mini-scheduler before users notice.

**Q: Solo founder. What's your plan?**

> Honest answer: Mo 24 gate per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.3. By month 24 (mid-v0.5) I commit to (a) raise seed, (b) hand off (Bosch internal data-platform team is the documented off-ramp), or (c) cap as indie. The gate fires automatically from weakness (0 paying after 3 months beta, <10 active teams after 6 months OSS, founder velocity <3 features/month for 60 days, funded competitor ships equivalent) AND from strength (>50 active teams + paying design partners). No default extension permitted. Reaching Mo 24 without a choice = automatic option (c).

---

## Posting checklist

- [ ] Submit between **09:00–10:00 ET Tue or Wed** (peak HN visibility window)
- [ ] Title is "Show HN: ..." (mandatory for the Show HN tag)
- [ ] URL is the GitHub repo, NOT the docs site (HN crowd lands on the README, then clicks through)
- [ ] Post the first-comment draft within 60 seconds of submission so it pins above other replies
- [ ] Do NOT vote-ring. Do NOT ask friends to upvote. HN auto-detects and shadow-bans.
- [ ] Be online and responsive for the first 4 hours — answer every comment in good faith
- [ ] If a comment is hostile but technically substantive, engage; if it's hostile and content-free, don't take the bait
- [ ] Have the README install command tested on a fresh venv 30 min before submitting
- [ ] Have a fallback "currently overloaded" pinned message ready in case the repo gets DDOS'd by clones

---

## Do NOT post

- ❌ "Show HN: Nucleus — better Databricks for startups" (banned framing per `AGENTS.md` §8) <!-- banned-term: better Databricks -->
- ❌ "Show HN: AI-native data platform" (banned framing) <!-- banned-term: AI-native -->
- ❌ "Show HN: Nucleus — Spark killer" (banned framing) <!-- banned-term: Spark killer -->
- ❌ Any comparison that bashes Databricks / Snowflake / dbt / Dagster — be respectful, they are excellent products that we wrap or yield to
- ❌ Any LOC / benchmark number that is not in `docs/benchmarks/2026-05-15_baseline.md` or `docs/research/scale_out_audit.md`
- ❌ Any claim about "production-ready" — Nucleus v0.2 is **beta**

---

*Final sanity check before posting: re-read the 8-question gate (`AGENTS.md` §5) and the forbidden framings (§8). If anything in the title, URL, or first-comment draft would fail those, fix it before submitting.*
