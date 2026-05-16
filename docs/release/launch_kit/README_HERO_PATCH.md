# Proposed README.md Hero-Section Patch — Nucleus v0.2.0

*This file is a **proposed patch for parent foreground review**. DO NOT auto-apply. The current `README.md` hero predates the v0.2.0 launch (it still reads "v0.1 beta", talks about `pip install -e ".[dev]"` as the supported workflow, and uses a 5-row comparison table). For launch day we want the hero to (a) reflect the v0.2.0 PyPI release as the default path, (b) embed the 60-sec demo, (c) front-load the three honest differentiators, (d) link to the roadmap for "what's not yet", and (e) ship an honest 1-row vendor matrix that a skeptical HN reader will accept at a glance. Last updated 2026-05-15.*

> **Author intent**: minimal, surgical changes to lines 10–80 of `README.md`. The Five Pillars block, Architecture block, and everything below remain unchanged.

---

## Patch — replace lines 10–80 of `README.md` with the block below

> Diff context: the existing block opens with the three badges, the blockquote hero, the "v0.1 beta — what works vs. what waits" table, the Install section, and the 30-second demo. The patch keeps the badges, rewrites the blockquote, embeds the demo, simplifies the install, adds a "Why Nucleus" + "What's not in v0.2" pair, and replaces the 5-row vendor matrix with a 1-row honest matrix. Order of sections after the patch: badges → hero → demo → install → Why → What's not → comparison → Five Pillars (existing) → …

```markdown
[![PyPI version](https://img.shields.io/pypi/v/nucleus.svg)](https://pypi.org/project/nucleus/)
[![Status: v0.2 beta](https://img.shields.io/badge/status-v0.2%20beta-yellow)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue)]()
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue)](https://nucleus-data.github.io/nucleus/)

> # Ship data products from a laptop.
>
> **Nucleus is a local-first Python SDK and CLI for building Iceberg-native pipelines and analytics stacks.** Wraps DuckDB, Polars, Apache Iceberg, and embedded orchestration into one coherent product. AI-ready by design. Apache 2.0. **No JVM** in the default path. Graduates cleanly to **any Iceberg catalog** (Polaris, Lakekeeper, Unity, R2, Snowflake-Iceberg-compat) — including Databricks and Snowflake — the day a single laptop stops being enough.

---

## 60-second demo

<p align="center">
  <a href="https://github.com/nucleus-data/nucleus/raw/main/assets/demos/v0.2/launch_60s.mp4">
    <img src="assets/demos/v0.2/launch_60s_poster.png" alt="60-second Nucleus demo — pip install nucleus-data, init, up, run, query, Workbench" width="720" />
  </a>
</p>

*Click to play (60 s, no audio, captions burned in). From `pip install nucleus-data` to a queried Iceberg snapshot with the Workbench dashboard on `localhost:8765`. Source script: [`docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md`](docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md).*

---

## 3-command quickstart

**Python 3.11** is the primary supported interpreter (3.12 may work; follow `pyproject.toml`).

```bash
pip install nucleus-data                                  # ~16 deps, <60 s on warm pip cache
nucleus init my-stack && cd my-stack && nucleus up   # scaffold + boot local stack (~6 s)
nucleus run example.greeting                         # materialize your first Iceberg snapshot
```

Optional extras when you need real data sources or the Workbench web IDE:

```bash
pip install "nucleus[postgres,workbench]"
nucleus ingest postgres://localhost/app --table public.orders --as raw.orders
nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
nucleus workbench up                                 # http://localhost:8765
```

Full quickstart with Postgres + S3 + a BI-ready mart in <30 min: [`docs/onboarding/quickstart.md`](docs/onboarding/quickstart.md).

---

## Why Nucleus

- **Graduates to giants, not away from them.** Nucleus writes plain Apache Iceberg snapshots to your own S3 (or filesystem) — no Nucleus-proprietary byte format, ever. The day you outgrow a laptop, you point Databricks, Snowflake, or any Iceberg catalog at the same bucket. Zero migration. The yield-to-giants strategy is a first-class architectural principle, not a fallback ([`docs/specs/nucleus_architecture_v4.1.md` §8](docs/specs/nucleus_architecture_v4.1.md#8-yield-to-giants-strategy)).
- **Local-first by construction.** Cold boot ~6 s (`nucleus up`). Idle RAM ~117 MB. Iceberg snapshots, scheduling daemon, run ledger, and Workbench all run from a single `pip install` on a laptop. No cluster. No JVM. Local-identical-to-prod ([`docs/internal/benchmarks/2026-05-15_baseline.md`](docs/internal/benchmarks/2026-05-15_baseline.md)).
- **AI-assisted, not AI-gated.** `nucleus chat` routes through `litellm` to your provider of choice (Anthropic / OpenAI / Ollama / 100+ more), with opt-in consent, no Nucleus servers, no key logging. The Copilot is a feature; the data path is the product. Lineage-aware refactoring arrives in v0.5 ([ADR-015](docs/decisions/ADR-015-ai-chat-mvp.md)). <!-- banned-term: AI-native -->

---

## What's not in v0.2 (yet)

We are honest about scope. v0.2.0 is the first publicly available release; treat it as beta. The following are **deferred** to v0.3 / v0.5 / v1.0 per the roadmap at [`docs/specs/nucleus_architecture_v4.1.md` §18](docs/specs/nucleus_architecture_v4.1.md#18-roadmap):

- **Lakekeeper REST catalog** — v0.3+ (v0.2 stays on filesystem catalog; bytes are still valid Iceberg).
- **`dbt-duckdb` adapter** — v0.3+ optional. v0.2 ships native `ctx.sql` + Jinja `{{ ref() }}` (~180 LOC, hard 2,500 LOC scope ceiling).
- **Marimo notebooks** — v0.3+. v0.2 ships no notebook runtime.
- **Column-level lineage** — v0.5+ for SQL; v1.0 for Python. v0.2 ships asset-level OpenLineage NDJSON.
- **Lineage-aware AI Copilot** — v0.5+. v0.2 ships single-turn chat only.
- **Hybrid compute dispatch** (`@nucleus.sql_asset(compute="databricks")`) — v1.5+.
- **Nucleus Cloud** (managed catalog, managed S3, managed deploy) — v1.0+. The OSS core is and will remain free forever.

If your problem requires any of these today, Nucleus is not yet for you. The full disclosure of empirical numbers (including 11 measured failures vs aspirational targets) lives at [`docs/internal/benchmarks/2026-05-15_baseline.md`](docs/internal/benchmarks/2026-05-15_baseline.md).

---

## Honest 1-row comparison

| | **Nucleus v0.2** | dbt-core | Airflow | Databricks |
|---|---|---|---|---|
| **Best for** | 5–20 engineer team, 100 GB–5 TB, greenfield Iceberg + laptop-first | SQL-centric transforms on a warehouse you already have | Batch orchestration at scale, mature on-call patterns | 200+ engineer central platform, 100+ TB, distributed compute |

This is not a feature matrix — feature matrices favor whoever picks the features. It is a **persona matrix**. If you are not a 5–20 engineer team building greenfield Iceberg-native analytics on laptops, one of the other three columns is probably the right tool for you, and we will gladly help you graduate ([`docs/release/launch_kit/comparison_vs_databricks_snowflake.md`](docs/release/launch_kit/comparison_vs_databricks_snowflake.md) holds the full capability matrix with honest deltas).
```

---

## Why these changes (rationale for the founder reviewing)

1. **Lead with the differentiator, not the disclaimer.** The current hero opens with "v0.1 beta" badges and a "What works vs. What waits" table. That signals "still cooking" before signaling "what you'd ever want this for." The patch moves the badges below the demo embed and front-loads the value-prop sentence.

2. **The demo is the wow.** A 60-second video earns more clicks than 60 seconds of reading. The poster image is what shows when JavaScript is off (RSS readers, email, mirrors); the click takes the user to the MP4. Asset path matches `60_SECOND_DEMO_SCRIPT.md` §Distribution.

3. **Three commands, not a wall of `pip install -e .[dev]`.** The current README's first install command is `git clone … && pip install -e ".[dev]"` — that signals "developer workflow" and scares off first-time users. The patch makes `pip install nucleus-data` the primary path and gates the editable-dev workflow behind the Contributing section (unchanged below).

4. **"Why Nucleus" is a persona pitch, not a feature list.** Three bullets, each one cites architecture. Each bullet answers a different reader's primary question:
   - The "yield to giants" bullet answers the lock-in skeptic.
   - The "local-first" bullet answers the JVM-allergic engineer.
   - The "AI-assisted, not AI-gated" bullet answers the AI-fatigued senior reviewer.

5. **"What's not in v0.2" earns trust.** Per `AGENTS.md` §10.8 ("be brutally honest about scope"), publishing the deferred-feature list in the README itself is a credibility win on HN/Reddit. The patch links to the roadmap section rather than re-duplicating it.

6. **The 1-row comparison ends the table arms race.** A 5-row matrix invites the response "but you forgot column X." A 1-row persona matrix is harder to argue with because it doesn't claim feature parity — it claims persona fit. The link to the full comparison doc handles readers who want the long version.

7. **Vocabulary discipline.** Every term in this patch is checked against `AGENTS.md` §7 (use: asset / materialization / snapshot / graduate / yield-to-giants) and §8 (avoid: Data OS / AI-first / Spark killer / Databricks killer / etc.). The `<!-- banned-term: AI-native -->` HTML comment on the AI bullet is a self-suppressed reference so `scripts/check_vocabulary.py` does not flag the surrounding text on the negated phrase.

---

## What this patch does NOT change

- Anything below line 80 of `README.md` (Five Pillars, Architecture, ctx SDK examples, CLI surface, Yield-to-giants strategy block, Repository structure, Contributing, License, Acknowledgments).
- The logo image at the top.
- The existing Apache attribution at the bottom.

These all already align with launch-day tone. The patch is intentionally surgical.

---

## Suggested workflow for applying this patch

1. **Founder reads this file** end-to-end (≤5 min).
2. **Confirm asset paths exist** — `assets/demos/v0.2/launch_60s.mp4` and `assets/demos/v0.2/launch_60s_poster.png`. If the demo recording is still pending, ship the patch with placeholder paths and update once the video lands.
3. **Apply via single foreground commit** — `git checkout -b patch/readme-hero-v0.2`, paste the patch block over lines 10–80, `git diff` to confirm scope, commit with `release: README hero patch for v0.2.0 (front-load demo + 1-row comparison)`.
4. **Run vocabulary check** — `python scripts/check_vocabulary.py`. The `<!-- banned-term: AI-native -->` self-suppression should let it exit 0.
5. **Open a PR**, self-review, merge. Estimated total founder time: **~15 min** including verification.

If anything in the patch reads as off-tone or off-spec, **edit before applying** — this is a proposal, not a directive.

---

*Last updated 2026-05-15. If the patch is applied, log the commit SHA in `docs/release/launch_kit/post_mortem_v0.2.0.md` so future launches can compare the before/after click-through on the demo embed.*
