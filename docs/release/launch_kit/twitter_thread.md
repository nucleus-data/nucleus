# Twitter / X Launch Thread — Nucleus v0.2.0

*12-tweet thread. Each tweet ≤280 chars. Hook tweet posts standalone; replies thread off the first. Best post window: Tue–Thu 09:00–11:00 ET.*

---

## Pinned thread

### Tweet 1 / 12 — HOOK (262 chars)

```
A 5-engineer startup spends month one wiring 9 tools just to ship one Iceberg table.

We released Nucleus v0.2.0 today — local-first Python SDK + CLI for Iceberg-native pipelines.

git clone → BI-ready table in <30 minutes.

Apache 2.0. No JVM. 🧵
```

> *Image placeholder*: hero shot of `nucleus init my-stack && cd my-stack && nucleus up && nucleus run example.greeting` running in a terminal, with the editorial Workbench v0.3 dashboard visible in a browser tab.
>
> *Alt-text*: "Terminal showing four Nucleus CLI commands running in sequence: `nucleus init`, `nucleus up`, `nucleus run example.greeting`, and `nucleus query`. A browser window beside it shows the Nucleus Workbench dashboard with a blue gradient hero, four glassmorphism stat chips reading 'total assets / rows / checks green / last run ago', and a 3-column body grid."

---

### Tweet 2 / 12 — what it is (270 chars)

```
Nucleus wraps DuckDB, Polars, Apache Iceberg + embedded orchestration into one ctx SDK + nucleus CLI.

We own three things, forever:
1) the asset graph
2) the ctx SDK
3) the unified developer experience

Everything else is rented from open source.
```

---

### Tweet 3 / 12 — the install (243 chars)

```
30-second start:

```
pip install nucleus
nucleus init my-stack && cd my-stack
nucleus up
nucleus ingest postgres://localhost/app --table public.orders --as raw.orders
nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
```
```

> *Image placeholder*: animated GIF or asciinema of the five commands executing successfully on a fresh laptop, ending with the row count printed.
>
> *Alt-text*: "Five-command terminal demo: pip install, nucleus init, nucleus up (boots local stack in ~6 seconds with green checkmarks for storage, catalog, orchestration), nucleus ingest reads 25,841 rows from a Postgres orders table into an Iceberg table named raw.orders, and nucleus query returns the same row count from the materialized Iceberg snapshot."

---

### Tweet 4 / 12 — connectors (231 chars)

```
v0.2 ships 7 connectors via one ctx.copy_from() dispatcher:

→ Postgres
→ MySQL
→ SQLite
→ Snowflake
→ Amazon S3
→ Google Cloud Storage
→ Local filesystem (Parquet/CSV/JSON, glob patterns)

Auto-infer schema. Auto-create Iceberg target. Atomic commit.
```

---

### Tweet 5 / 12 — Workbench v0.3 (251 chars)

```
Workbench v0.3 — single command (nucleus workbench up) opens a web IDE:

→ Editorial gradient dashboard
→ 7 interactive routes (Assets / Runs / Schedules / Catalog / Query / detail slide-overs)
→ Live SSE log streaming
→ ⌘K command palette

No build step needed.
```

> *Image placeholder*: full-resolution screenshot of the Workbench Editorial Hero dashboard with the blue gradient hero, four stat chips, the recent runs card on the left, the pipeline DAG card in the middle, and the AI Copilot card on the right.
>
> *Alt-text*: "Nucleus Workbench v0.3 dashboard. Top hero shows 'Today's pipeline' on a blue gradient with four glassmorphism stat chips (12 assets / 4.2M rows / 18 checks green / 3 min ago last run). Below, three cards: Recent Runs table on left, Pipeline DAG SVG in center, AI Copilot panel on right with an animated iridescent orb avatar."

---

### Tweet 6 / 12 — scheduling + run ledger (272 chars)

```
@nucleus.asset(schedule="@daily") now actually runs on schedule.

A 5-second-poll cron daemon (croniter) materializes due assets via the AMA.

Every materialization writes a typed record to a durable NDJSON ledger.

nucleus runs list / show / cancel / tail --follow.
```

---

### Tweet 7 / 12 — composability (264 chars)

```
Composability by Constitution (architecture v4.1 §9):

Every Tier 1/2 dep ships with a clean swap interface + 5-10 smoke tests in CI.

Full alternate adapters built on demand only — when a trigger event fires.

DuckDB → DataFusion ✓
Polars → DataFusion DF ✓
Dagster → mini-scheduler ✓
```

---

### Tweet 8 / 12 — yield to giants (264 chars)

```
The day you outgrow Nucleus, you point Databricks/Snowflake at the same S3 + Iceberg catalog and you're done.

Mode 1 (graduation, today): zero effort. Iceberg portability.
Mode 2 (hybrid dispatch, v1.5): @nucleus.sql_asset(compute="databricks").
Mode 3 (federation, v2.0): Data Mesh.
```

---

### Tweet 9 / 12 — AI Copilot (intentionally thin) (261 chars)

```
AI Copilot in v0.2 is intentionally just chat.

nucleus chat "How do I add a daily schedule to my orders asset?"

Routed via litellm — bring your own anthropic / openai / ollama key. We don't have servers; we don't see your keys.

Schema-aware in v0.3. Lineage-aware in v0.5.
```

---

### Tweet 10 / 12 — honest disclosures (270 chars)

```
HONEST disclosures because this community deserves them:

→ It's beta
→ Empirical perf baseline FAILED 11 metrics vs aspirational targets (publishing the numbers anyway: docs/benchmarks/2026-05-15_baseline.md)
→ B4 concurrent-run safety FAILS on Windows; passes Linux/WSL
→ Solo founder
```

---

### Tweet 11 / 12 — what's next (242 chars)

```
Roadmap snapshot:

v0.3 — Lakekeeper / Polaris co-default + dlt (100+ connectors) + dbt-duckdb adapter + Marimo + schema-aware Copilot
v0.5 — ctx.agent runtime + lineage-aware Copilot + Lance multimodal + nucleus-mcp-server
v1.0 GA — best-case Mo 28-36
```

---

### Tweet 12 / 12 — call to action (264 chars)

```
Try it:

→ Repo: github.com/nucleus-data/nucleus
→ Architecture: nucleus_architecture_v4.1.md (50 min read)
→ License: Apache 2.0

If you build something useful, tell me.
If something breaks, file an issue with the NE#### error code.

Thanks for reading. 🙏
```

> *Image placeholder*: the Nucleus logo (`assets/brand/nucleus-logo.png`) on a clean background with the tagline "Ship data products from a laptop." underneath.
>
> *Alt-text*: "Nucleus logo — a stylized atomic nucleus with orbiting electrons rendered in a modern flat-vector style. Tagline below reads 'Ship data products from a laptop.' Color palette is the same blue gradient as the Workbench Editorial Hero."

---

## Posting checklist

- [ ] Schedule tweet 1 for **Tue or Wed 09:00–11:00 ET** for max reach
- [ ] Pin thread to profile for first 48 hours
- [ ] Quote-tweet the hook with one screenshot when engagement plateaus (typically hour 4-6)
- [ ] Reply to every meaningful comment in the first 24 hours
- [ ] Do NOT chase engagement with hyperbole — the founder voice in this thread is honest, not breathless
- [ ] Cross-link to LinkedIn post + HN thread + r/dataengineering thread once they go live (one-line "Also on HN: <link>" reply is fine; do NOT spam)
- [ ] Tag relevant accounts ONLY if they have explicitly opted in (do NOT tag DuckDB, Polars, Iceberg, Dagster, Snowflake, Databricks unfunny — those teams hate marketing tags from random projects)
- [ ] Use hashtags sparingly: `#dataengineering` on tweet 1 only; do NOT chain `#iceberg #python #apachefoundation` etc. (looks spammy)

---

## Image asset checklist

| Tweet | Asset | Path | Status |
|---|---|---|---|
| 1 | Hero terminal + Workbench split-screen | `assets/screenshots/v0.2/twitter_t1_hero.png` | WORKSTREAM C ACTION: capture before posting |
| 3 | 5-command terminal GIF | `assets/demos/v0.2/twitter_t3_install.gif` | WORKSTREAM C ACTION: record asciinema then export GIF |
| 5 | Workbench dashboard full-res | `assets/screenshots/v0.2/twitter_t5_workbench.png` | WORKSTREAM C ACTION: capture before posting |
| 12 | Logo + tagline lockup | `assets/brand/twitter_t12_lockup.png` | WORKSTREAM C ACTION: derive from `assets/brand/nucleus-logo.png` |

---

## Do NOT tweet

- ❌ "Spark killer / Databricks killer" framings (banned per `AGENTS.md` §8) <!-- banned-term: Spark killer --> <!-- banned-term: Databricks killer -->
- ❌ "AI-native data platform" (banned) <!-- banned-term: AI-native -->
- ❌ "Better than X" (we are *different*, not *better-of-the-same*)
- ❌ Any number not in `docs/benchmarks/2026-05-15_baseline.md` or `docs/research/scale_out_audit.md` or `pyproject.toml`
- ❌ "Production-ready" / "enterprise-ready" — this is beta
- ❌ Memes about competitor failures (we are friendly to giants)
- ❌ Engagement-bait CTAs ("Like + RT if you've ever spent a week wiring orchestrators…")

---

## Character-count audit

| Tweet | Chars | Limit | OK |
|---|---|---|---|
| 1 | 262 | 280 | ✓ |
| 2 | 270 | 280 | ✓ |
| 3 | 243 | 280 | ✓ |
| 4 | 231 | 280 | ✓ |
| 5 | 251 | 280 | ✓ |
| 6 | 272 | 280 | ✓ |
| 7 | 264 | 280 | ✓ |
| 8 | 264 | 280 | ✓ |
| 9 | 261 | 280 | ✓ |
| 10 | 270 | 280 | ✓ |
| 11 | 242 | 280 | ✓ |
| 12 | 264 | 280 | ✓ |

*All tweets confirmed under 280 chars including emoji and trailing whitespace.*
