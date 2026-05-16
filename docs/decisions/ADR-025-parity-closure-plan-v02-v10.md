# ADR-025: Parity closure plan v0.2 → v1.0

Status: ACCEPTED
Date: 2026-05-15
Author: builder (v0.2.0 reconciliation pass)
Sources:
- `docs/internal/research/parity_vs_databricks_snowflake.md` §4 (Wave 1F)
- `docs/internal/research/parity_vs_dbt_dagster_airflow.md` §5–6 (Wave 1G)
- ADR-023, ADR-024 (this release)
- `docs/specs/nucleus_architecture_v4.1.md` §17 (yield-to-giants), §20 (non-goals)

Ratified 2026-05-15: roadmap adopted in commit a41a82c (v0.2.0 handover bundle).

## Context

Nucleus v0.1.0 ships the "Hello World" foundation: `@nucleus.asset`, `ctx.sql`, `ctx.copy_from`, `ctx.read`, asset-level OpenLineage, filesystem catalog, DuckDB/Polars engines, Dagster hidden orchestration, and the 8-command CLI. The beachhead E2E passes 8/8 gates on WSL and Windows.

However, two Wave-1 research documents produced independently-converging Top-10 closure lists that have not been ratified into the formal roadmap. This ADR deduplicates the two lists and establishes the Wave 2 implementer order so founders and contributors have a single authoritative priority stack.

**Critical framing (AGENTS.md §8)**: This is NOT a "Databricks killer" feature list. The closure plan exists to make Nucleus production-ready for the beachhead persona (5-20 engineer startup, 100GB-5TB). Every item must pass the 8-question gate in `.cursor/rules/nucleus.mdc`.

## Decision

Adopt the following ordered closure plan as the canonical v0.2 → v1.0 roadmap. Items are listed in Wave 2 implementer dispatch order.

### Tier P0 — v0.2 (next wave, no external blockers)

| # | Title | Beachhead impact | Effort | Wrap target | Both research lists? |
|---|---|---|---|---|---|
| P0-1 | **Active scheduling daemon** — wire Dagster daemon; `nucleus schedule on/off/trigger` commands | Pipeline that declares `schedule=` but never executes is a script, not a platform. Day-2 trust blocker. | S (1-2 wk) | Dagster `ScheduleDefinition` + daemon (ADR-017 §1 already wraps it) | YES (Wave 1F §4 P0-1; Wave 1G §5 P0 #1) |
| P0-2 | **Basic run monitoring** — `nucleus runs list/show`, run history in Workbench, failure surfaced in CLI | "Did my pipeline run last night?" is unanswerable in v0.1. | M (1-2 wk) | `workbench/api/runs.py` already exists; gap is `nucleus` CLI surface + persistence | YES (Wave 1G §5 P1 #3) |
| P0-3 | **ADR-024 reliability items** — DuckDB `SET memory_limit`, concurrent-run lock, `expire_snapshots` hook, Windows rename doc, execution timeout | Prevent silent OOM and data corruption on first real Postgres→S3 run | S per item | See ADR-024 for per-item wrap targets | Wave 1E audit + Wave 1H research |

### Tier P1 — v0.2 / v0.3 (can start Wave 2 in parallel with P0)

| # | Title | Beachhead impact | Effort | Wrap target |
|---|---|---|---|---|
| P1-1 | **Postgres full CDC via dlt** — `--mode cdc` incremental using `pgoutput` logical decoding | 1M+ row tables need incremental reads; full_refresh on every run is unsustainable | M | dlt `sql_database` verified source (https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database) |
| P1-2 | **Partition execution** — `nucleus run <key> --partition 2026-01-15` actually executes | Daily event tables are the first real incremental use case | M-L | Dagster `DailyPartitionsDefinition` + AMA extension (ADR-013 NV #6) |
| P1-3 | **SCD2 snapshot** — `materialized="snapshot"` writes Slowly Changing Dimension rows | ~80% of startup stacks have dimension tables; hand-rolled SCD2 is the worst anti-pattern | M | pyiceberg row-level delete + append (NEEDS pyiceberg 0.8.1 → 0.11.x migration; ADR-003) |
| P1-4 | **`nucleus plan` diff command** — show what would change before materialising | Prevents accidental full-refresh overwrites; mimics dbt's `dbt build --dry-run` + Terraform `plan` | S | DuckDB `EXPLAIN` + Iceberg schema diff (no new dep) |
| P1-5 | **Run failure alerting** — Slack/email webhook on materialization failure | Production teams can't operate blind; filing bug: "Nucleus is not production-ready" | S | Dagster `@failure_hook` API (NEEDS VERIFICATION against `dagster==1.9.5`; see Wave 1G NV-5) |

### Tier P2 — v0.5+ (post-beachhead stabilisation)

| # | Title | Effort | Wrap target | Architecture ref |
|---|---|---|---|---|
| P2-1 | **Column-level lineage (SQL)** | M | OpenLineage + sqlglot (v4.1 §13.2) | v0.5+ |
| P2-2 | **RBAC / OIDC skeleton** | M | Authentik / Keycloak / Okta (v4.1 §11) | v0.8+ |
| P2-3 | **Observability (OTEL → VictoriaMetrics)** | L | OpenTelemetry + VictoriaMetrics (v4.1 §14) | v0.5+ |
| P2-4 | **Marimo notebook integration** | M | Marimo (Tier 2, https://marimo.io) | v0.3+ |
| P2-5 | **AI Copilot schema+lineage-aware** | L | litellm + schema + lineage context injection | v0.5+ |
| P2-6 | **Zero-copy branch/clone (Iceberg)** | M | pyiceberg Iceberg spec v2 branch/tag | v0.5+ |

### Intentional non-closes (permanent yield-to-giants, AGENTS.md §4)

| Item | Why NOT closing |
|---|---|
| Streaming ingest (Kafka/Kinesis) | v1.5+; yield via Mode 2 dispatch to Databricks Structured Streaming |
| Distributed compute | Mode 2 yield-to-giants; `compute=databricks` dispatch |
| ML platform / model registry | Out of scope per v4.1 §20.1 |
| Multi-tenant cloud control plane | Cloud tier only; out of OSS scope |
| Macro ecosystem (2500+ dbt macros) | v4.1 §20 non-goal; intentional non-match |

## OSS Options Considered (deduplicated from Wave 1F + 1G)

| Capability | WRAP target | BUILD? | Reason |
|---|---|---|---|
| Active scheduling daemon | Dagster daemon (already in dep tree) | No | Already wrapped in `coordination/schedules.py` |
| Run history persistence | SQLite (stdlib-adjacent) | No | Reuse Dagster event log; wrap only |
| CDC ingest | dlt `sql_database` verified source | No | dlt already pinned; incremental is documented and maintained |
| Partition execution | Dagster `DailyPartitionsDefinition` | No | Part of Dagster dep |
| SCD2 | pyiceberg row-level delete | Minimal | ~300 LOC AMA extension; no new dep |
| Column-level lineage | sqlglot (already in dep tree, Tier 0) | No | Parse SQL AST → OL column facet |

## Consequences

**Positive:**

- Wave 2 implementer dispatch order is explicit; no ambiguity about what to build next.
- P0-1 (active scheduling daemon) closes the single largest "this is a demo, not a platform" gap.
- All P0/P1 items pass the 8-question gate (they are v0.2 Hello World, wrap-not-build, serve beachhead, stay within LOC budget).

**Negative / Open:**

- ADR-003 (pyiceberg upgrade 0.8.1 → 0.11.x) is a prerequisite for P1-3 (SCD2). That upgrade requires its own ADR + smoke tests per AGENTS.md §11.13.
- Dagster daemon boot latency NEEDS VERIFICATION that the daemon can start within PoC #4's 5.82 s boot budget. If daemon startup pushes `nucleus up` past 10 s, the strategy is lazy-start (daemon starts on first `schedule on` command, not at `nucleus up`).
- `nucleus schedule on/off/trigger` command surface needs CLI spec update in `docs/specs/nucleus_cli_spec.md` before Wave 2 implementation begins.

## Architecture Sections Touched

- `docs/specs/nucleus_architecture_v4.1.md` §17 (yield-to-giants — confirm every P0/P1 item respects the yield boundary)
- `docs/specs/nucleus_architecture_v4.1.md` §18 (roadmap — v0.2 milestone)
- `docs/specs/nucleus_architecture_v4.1.md` §20 (non-goals — intentional non-closes above)
- `AGENTS.md` §4 ("Do NOT Build" list — verify no P0/P1 item is on the list)
- ADR-003 (pyiceberg), ADR-013 (partition execution NV #6), ADR-017 (schedule exposure), ADR-024 (reliability)
