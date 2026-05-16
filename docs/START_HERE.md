# Welcome to Nucleus — Start Here

> *This file is the **one** entry point. Every other doc cross-references back here. If you only read one document, read this one — then follow the branch that matches your situation.*

---

## Pick your branch

You are most likely one of:

- **[I'm a user wanting to try Nucleus]** → start with the [30-minute quickstart](onboarding/quickstart.md) — `git clone` to a real BI-ready Iceberg table on your laptop. Empirically validated at 7 s boot, 8/8 gates PASS on WSL ([baseline](benchmarks/2026-05-15_baseline.md)).
- **[I'm a developer wanting to contribute]** → read [`CONTRIBUTING.md`](../CONTRIBUTING.md) (governance + PR process), then [`docs/dev-guides/`](dev-guides/README.md) (15 step-by-step runbooks: connectors, CLI commands, ADRs, upgrades, AI pair programming).
- **[I'm an AI coding agent]** → read [`AGENTS.md`](../AGENTS.md) (full file; the universal AI handover) and [`.cursor/rules/nucleus.mdc`](../.cursor/rules/nucleus.mdc) (Cursor-specific rules + vocabulary + 8-question gate).
- **[I'm evaluating Nucleus vs Databricks / Snowflake / dbt]** → read [`README.md`](../README.md) §Comparison + [`docs/specs/nucleus_vs_databricks.md`](specs/nucleus_vs_databricks.md) (feature-parity matrix) + [`docs/internal/research/parity_vs_databricks_snowflake.md`](research/parity_vs_databricks_snowflake.md) + [`docs/release/launch_kit/comparison_vs_databricks_snowflake.md`](release/launch_kit/comparison_vs_databricks_snowflake.md).
- **[I'm a skeptic — show me proof]** → read [`docs/internal/benchmarks/2026-05-15_baseline.md`](benchmarks/2026-05-15_baseline.md) (11 measured deltas vs aspirational targets, honest), [`docs/release/v0.2.0_RELEASE_NOTES.md`](release/v0.2.0_RELEASE_NOTES.md) §"Known issues", and [`docs/internal/release-process/chaos_test_results.md`](release/chaos_test_results.md). All numbers cited with paths; nothing dressed up.
- **[I want the deep architecture]** → [`docs/specs/nucleus_architecture_v4.1.md`](specs/nucleus_architecture_v4.1.md) is the single source of truth (~3 hours total reading; start with §1 identity, §3 layers, §6 error translation, §9 composability, §18 roadmap, §20 non-goals).
- **[I want the roadmap]** → [`docs/roadmap/overview.md`](roadmap/overview.md) (one-page version timeline through v2.0) and the per-phase docs ([`v0.2`](roadmap/v0.2-public-launch.md) [current], [`v0.3`](roadmap/v0.3-hardening.md), [`v0.5`](roadmap/v0.5-multimodal.md), [`v0.7`](roadmap/v0.7-cloud-tier-mvp.md), [`v1.0`](roadmap/v1.0-production-ready.md), [`v1.5`](roadmap/v1.5-enterprise-gateway.md), [`v2.0`](roadmap/v2.0-federation-mesh.md)).
- **[I'm the solo founder, six months in]** → read [`docs/HANDOVER.md`](HANDOVER.md) (steady-state ops manual: daily / weekly / monthly / quarterly / annual cadence + 8 crisis playbooks + AI workflow + OSS economics).
- **[I'm the founder on launch day]** → read [`docs/internal/release-process/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) (7-phase launch-day runbook, ~2h founder hands-on time).

**If you are unsure, start with [`README.md`](../README.md).** It is honest about what v0.2 ships, what's deferred, and which tradeoffs we have already made for you.

---

## What Nucleus is (in one paragraph)

**Nucleus ships data products from a laptop.** A local-first Python SDK (`ctx`) and CLI (`nucleus`) for building Iceberg-native pipelines and analytics stacks — built on open Apache foundations (DuckDB, Polars, Apache Iceberg, Apache Arrow, embedded Dagster), AI-ready by design. It grows with the team. It **graduates cleanly to any Iceberg catalog** — Databricks, Snowflake, Polaris, Lakekeeper, Unity, R2 — when users outgrow their laptop. v0.2 is the first publicly available release.

A *data product* in Nucleus terms = an Iceberg-backed **asset** with transformations, **contracts**, and lineage, consumable by BI tools, applications, or AI agents via the `ctx` SDK. The precise definition is in [`docs/specs/nucleus_architecture_v4.1.md`](specs/nucleus_architecture_v4.1.md) §12.1.

It is **not** a database, a SQL engine, a DataFrame engine, an orchestrator, a Spark replacement, a Databricks competitor, a "Data OS", an ML platform, an "AI-native data CLI", or a vector database. Treat any drift toward those framings as a bug — full forbidden list in [`AGENTS.md`](../AGENTS.md) §8. <!-- banned-term: multiple -->

---

## Who it's for

Per [`docs/specs/nucleus_architecture_v4.1.md`](specs/nucleus_architecture_v4.1.md) §1.5 — the **beachhead persona**, exclusively:

> A **5-engineer startup data team**, **100GB–5TB total data**, **greenfield project**, on **MacBooks or Linux laptops**, building a **BI-ready Iceberg table in <30 minutes** from `git clone`.

Other personas (solo consultant, mid-enterprise platform team, large-enterprise data mesh) are v1.5+ — not because they don't matter, but because shipping for one persona first is how OSS projects survive. See [`docs/roadmap/non-goals.md`](roadmap/non-goals.md) for the explicit "we won't do this in v0.x" list.

---

## Vocabulary primer (so we can talk)

Consistency in language prevents architecture drift. From [`AGENTS.md`](../AGENTS.md) §7 — enforced in CI by [`scripts/check_vocabulary.py`](../scripts/check_vocabulary.py):

| Use | Not |
|---|---|
| **asset** | "table" / "job" / "task" / "pipeline output" |
| **materialization** | "run output" / "result" |
| **snapshot** | "version" / "checkpoint" |
| **contract** | "expectation" / "constraint" |
| **check** | "test" / "assertion" (in asset context) |
| **catalog** | "metastore" <!-- banned-term: metastore --> |
| **`ctx`** | "context" / "session" |
| **Copilot** | "AI helper" / "assistant" |
| **graduate** | "migrate" (in graduation context) |
| **yield to giants** | "scale out" / "go big" |

If you write docs, contribute code, or open an Issue with one of the "Not" terms, expect a polite ping pointing you back here. It's a contract, not a stylistic preference.

---

## What this repository contains (abridged)

```
.
├── README.md                          # Hero + comparison + install + 30-second demo
├── AGENTS.md                          # Universal AI handover + 11 hard constraints
├── docs/specs/nucleus_architecture_v4.1.md       # Architecture source of truth (~3h read)
├── CONTRIBUTING.md / CODE_OF_CONDUCT.md / SECURITY.md / SUPPORT.md / GOVERNANCE.md / MAINTAINERS.md
├── docs/
│   ├── START_HERE.md                  # This file
│   ├── HANDOVER.md                    # Solo-founder long-term ops
│   ├── onboarding/quickstart.md       # 30-minute beachhead path
│   ├── roadmap/                       # v0.2 through v2.0, per-phase docs
│   ├── dev-guides/                    # 15 step-by-step contributor runbooks
│   ├── cookbook/                      # 5 recipes + 4 production cookbooks
│   ├── decisions/                     # ADR-001 through ADR-040
│   ├── research/                      # 39 wrapped-library + ecosystem notes
│   ├── errors/                        # NE-code reference + remediation
│   ├── benchmarks/                    # Empirical baseline numbers
│   ├── release/                       # v0.2 launch kit + readiness + runbooks
│   └── site/                          # MkDocs Material public docs site
├── src/nucleus/                       # Implementation (~8.3K LOC at v0.2 ship)
├── tests/                             # Unit + integration + chaos + upgrade smoke
├── poc/                               # Historical PoC snapshots (#1 - #5)
├── scripts/                           # 11 governance + benchmark + release scripts
└── examples/                          # Curated end-to-end sample projects
```

---

## How to get help

- **Bug** → [GitHub Issues](https://github.com/nucleus-data/nucleus/issues), label `bug`.
- **Question** → [GitHub Discussions](https://github.com/nucleus-data/nucleus/discussions) — preferred over Issues for non-bug topics.
- **Security concern** → [`SECURITY.md`](../SECURITY.md) (private reporting via GitHub Security Advisories).
- **Feature request** → first run the [8-question gate](roadmap/overview.md#the-8-question-gate); if it passes, open an Issue with the answers.
- **Commercial / Cloud-tier inquiry** → see [`SUPPORT.md`](../SUPPORT.md) (Cloud tier is v0.7+; not yet available).

---

## Beta status

**v0.2 is beta.** The `ctx` SDK API surface is stabilising but **not yet locked under semver** — that happens at v1.0 per the [versioning policy](../CHANGELOG.md#versioning-policy). Breaking changes within `0.y.z` are explicitly permitted per Keep a Changelog. Pin your installs (`pip install nucleus==0.2.0`) and read [`docs/compatibility.md`](compatibility.md) before upgrading.

---

*Last updated: 2026-05-15 (v0.2.0 ship). If a section above goes stale, file an Issue with the label `docs` — this file is the master entry point and should never be wrong.*
