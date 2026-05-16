---
title: Start Here
description: Single entry-point document for Nucleus users, contributors, AI agents, evaluators, and skeptics.
---

# Start Here

This is the **one** entry point for everything Nucleus. The canonical source is at the repository root: **[`docs/START_HERE.md` on GitHub →](https://github.com/nucleus-data/nucleus/blob/main/docs/START_HERE.md)**.

## Pick your branch

You are most likely one of:

- **[I'm a user wanting to try Nucleus]** → [30-minute Quickstart](getting-started/quickstart.md) — `git clone` to a real BI-ready Iceberg table on your laptop.
- **[I'm a developer wanting to contribute]** → [Contributing](community/contributing.md) + the developer guides ([source on GitHub](https://github.com/nucleus-data/nucleus/tree/main/docs/dev-guides)).
- **[I'm an AI coding agent]** → read [`AGENTS.md`](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md) (the universal AI handover) and [`.cursor/rules/nucleus.mdc`](https://github.com/nucleus-data/nucleus/blob/main/.cursor/rules/nucleus.mdc) (vocabulary + 8-question gate).
- **[I'm evaluating Nucleus vs Databricks / Snowflake / dbt]** → [Why Nucleus](why-nucleus.md) + [parity research](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/research/parity_vs_databricks_snowflake.md).
- **[I'm a skeptic — show me proof]** → [Empirical benchmarks](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/benchmarks/2026-05-15_baseline.md) (11 measured deltas vs aspirational targets, honest).
- **[I want the deep architecture]** → [`docs/specs/nucleus_architecture_v4.1.md`](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md) — the single source of truth.
- **[I want the roadmap]** → [Roadmap](community/roadmap.md).
- **[I'm the solo founder, six months in]** → [Long-term Handover](community/handover.md).

## What Nucleus is

**Nucleus ships data products from a laptop.** A local-first Python SDK (`ctx`) + CLI (`nucleus`) for Iceberg-native pipelines and analytics stacks, AI-ready by design, that graduates cleanly to any Iceberg catalog (Polaris, Lakekeeper, Unity, R2, Databricks, Snowflake) when teams outgrow the laptop.

Designed for the **beachhead persona**: a **5-engineer startup data team**, **100GB–5TB total data**, **greenfield project**, building a **BI-ready Iceberg table in <30 minutes** from `git clone`.

## Beta status

v0.2 is beta. The `ctx` SDK surface is stabilising but **not yet locked under semver** — that happens at v1.0. Pin your installs (`pip install nucleus==0.2.0`) and read the [Changelog](changelog.md) before upgrading.

---

*If anything above is wrong or stale, file an Issue with the label `docs` — this file is the master entry point and should never be wrong.*
