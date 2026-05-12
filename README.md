# Nucleus

> **Modern composable data engineering platform — AI-assisted, built on open Apache foundations, graduates cleanly when you outgrow it.**

[![Status: Pre-Heartbeat](https://img.shields.io/badge/status-pre--heartbeat-orange)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)]()

---

## What is Nucleus?

A lightweight, AI-assisted data platform for small-to-mid data teams that **complements** Databricks/Snowflake instead of competing with them. Built by wrapping the best of the modern data stack — **DuckDB, Polars, Apache Iceberg, PyArrow, Dagster** — behind a single clean SDK and a single CLI.

```python
import nucleus as nx

ctx = nx.context()

# One-liner ingestion — Postgres to Iceberg
ctx.copy_from(
    source="postgres://localhost/orders",
    table="public.orders",
    target="raw.orders",
)

# SQL transformation with Jinja
ctx.sql("""
    SELECT customer_id, SUM(amount) AS total
    FROM {{ ref('raw.orders') }}
    GROUP BY 1
""", target="marts.customer_totals")

# Or Python with Polars
@nucleus.asset
def customer_segments(orders: pl.DataFrame) -> pl.DataFrame:
    return orders.group_by("customer_id").agg(
        pl.col("amount").sum().alias("ltv")
    )
```

That's it. No clusters to manage. No JVM. No vendor lock-in. **Open table format from day one.**

---

## Why Nucleus exists

Existing data platforms force you to choose:

| You want… | But you get… |
|-----------|--------------|
| Lightweight & local-dev friendly | Heavyweight cluster setup |
| Open formats & no lock-in | Vendor-specific everything |
| Modern composable engines | Monolithic black box |
| AI-assisted authoring | Plain notebooks + IntelliSense |
| Production-grade orchestration | DIY cron/Airflow |
| Graduate cleanly when you scale | Forklift rewrite to Spark/Snowflake |

Nucleus gives you **all of the above** by wrapping proven OSS components behind two abstractions: `ctx` (the SDK) and `nucleus` (the CLI).

When your data outgrows a single laptop or node — your **Iceberg tables come with you**. Point Databricks/Snowflake/Trino at the same warehouse path. Zero rewrite.

---

## The Five Pillars

Nucleus is designed around five non-negotiable principles, mirrored verbatim from [`nucleus_architecture_v4.1.md`](nucleus_architecture_v4.1.md) §2 and [`AGENTS.md`](AGENTS.md) §6.

1. **High performance on minimal resources** — DuckDB + Polars + Arrow zero-copy. Laptop → 100GB. Single node → 5TB. No JVM, no cluster.
2. **Composable by constitution** — Every Tier 1/2 dependency has a clean swap interface and CI smoke tests. Full adapter built on-demand, not pre-emptively.
3. **AI-assisted by design** — Errors, lineage, schemas, and the `ctx` SDK are all engineered for LLM comprehension. We assist with AI; we are not an AI/ML platform.
4. **Familiar UX from proven giants** — Borrow vocabulary and ergonomics from dbt / Dagster / Cursor. No new mental models we don't need.
5. **Friendly to giants, hostile to no-one** — Iceberg portability means users graduate to Databricks/Snowflake without rewriting; we never compete head-on.

---

## Status: Pre-Heartbeat

**This repository is in the planning + scaffolding phase.** No runnable code yet.

| Tier | What | Status | ETA |
|------|------|--------|-----|
| **Pre-code** | Architecture + specs + scaffolding | In progress | Month 0 (now) |
| **Tier 0: Heartbeat** | First working slice (Postgres → Iceberg → SELECT) | Not started | Month 1-2 |
| **Tier 1: Foundation** | v0.1 — beachhead-ready (5-20 person teams, <30 min onboarding) | Not started | Month 2-8 |
| **Tier 2: Workbench** | v0.2 — web IDE + simple Copilot | Not started | Month 8-14 |
| **Tier 3: Connectors** | v0.3 — Lakekeeper, more sources/sinks, dbt-duckdb adapter | Not started | Month 14-20 |
| **Tier 4: Intelligence** | v0.5 — lineage-aware Copilot + `ctx.agent` runtime (Semantic Knowledge Graph lands v0.7+) | Not started | Month 20-28 |
| **v1.0 GA** | Public stable release | Not started | Month 28-36 |

**Reality check**: This is a solo-founder project, paced for one person + AI agents. See [`nucleus_poc_plan.md`](nucleus_poc_plan.md) for the 5 Proof-of-Concept validations that must pass before Heartbeat.

---

## Architecture (one-page)

Five layers, top-to-bottom:

```
┌────────────────────────────────────────────────────────┐
│  L4: EXPERIENCE     ctx SDK · nucleus CLI · Workbench  │
├────────────────────────────────────────────────────────┤
│  L3: INTELLIGENCE   Copilot · ctx.agent · Semantic KG  │
├────────────────────────────────────────────────────────┤
│  L2: COORDINATION   Asset Materialization (Dagster)    │
├────────────────────────────────────────────────────────┤
│  L1: ENGINES        DuckDB · Polars · DataFusion · Daft │
├────────────────────────────────────────────────────────┤
│  L0: PHYSICS        Arrow · Iceberg · Parquet · S3 API  │
└────────────────────────────────────────────────────────┘
```

See:
- [`nucleus_architecture_v4.1.md`](nucleus_architecture_v4.1.md) — the full source-of-truth (1678 lines)
- [`docs/architecture/`](docs/architecture/) — C4 diagrams and sequence flows
- [`docs/decisions/`](docs/decisions/) — Architecture Decision Records (ADRs)

---

## Two abstractions, zero surprises

Everything users touch is one of two things:

### 1. The `ctx` SDK — Python API for assets

```python
ctx.copy_from(source=..., target="raw.events")   # Ingest
ctx.sql(query, target="marts.daily_revenue")     # Transform (SQL+Jinja)
ctx.read("marts.daily_revenue").to_polars()      # Read
ctx.run("marts.daily_revenue")                   # Materialize
ctx.lineage("marts.daily_revenue")               # Inspect
```

### 2. The `nucleus` CLI — operator interface

```bash
nucleus up                           # Boot local stack <10s
nucleus init my-project              # Scaffold project
nucleus run                          # Materialize all assets
nucleus run marts.daily_revenue      # Materialize one
nucleus lineage marts.daily_revenue  # Show DAG
nucleus inspect raw.events           # Show schema/snapshots
nucleus catalog list                 # List tables
nucleus down                         # Tear down
```

**No third surface.** No `nucleus dagster ...`, no escape hatches except behind a clearly-labeled `ctx._advanced` namespace. The boundary is the product.

---

## Five non-negotiables (Hard Constraints)

From [`AGENTS.md`](AGENTS.md), there are **11 hard constraints** every contribution must satisfy. The top five for users to know:

1. **No JVM.** Pure Python + native binaries. Cold start <10s.
2. **No custom scheduler.** Dagster handles orchestration. We never reinvent it.
3. **No custom commit service.** Iceberg catalog handles atomic commits. We never reinvent it.
4. **Iceberg is the only table format we materialize to.** Open. Portable. Forever.
5. **The `ctx` SDK is the only public surface.** No leaking Dagster/PyIceberg/DuckDB types past v1.0.

The other six cover observability, composability, AI workflow discipline, LOC budget, documentation, and upgrade safety. See [`AGENTS.md`](AGENTS.md) §3.

---

## Yield-to-Giants strategy

Nucleus does **not** compete with Databricks, Snowflake, or BigQuery. We complement them.

| Mode | What | When |
|------|------|------|
| **1. Graduation** | Your Iceberg tables work directly with Databricks/Snowflake. Stop using Nucleus, keep your data. | When you exceed single-node scale (~5-10TB hot data, 100+ users) |
| **2. Hybrid Dispatch** | `@nucleus.sql_asset(compute="databricks")` ships heavy queries to Databricks; local stays for dev/small jobs. | Per-asset (planned v0.5, per v4.1 §10.2) |
| **3. Federation** | Nucleus orchestrates assets that live in Databricks/Snowflake. We're the control plane; they're the engines. | Data mesh setup (planned v1.0) |

We are **the on-ramp**, not the destination. This is intentional and is the core of our acquisition thesis. See [`nucleus_architecture_v4.1.md`](nucleus_architecture_v4.1.md) §8.

---

## Quickstart (when Tier 0 ships)

> **Not runnable yet.** Tier 0 ETA: Month 1-2.

```bash
# Install
pip install nucleus

# Boot local stack
nucleus up                          # <10s — Iceberg + DuckDB + Dagster wired up

# Scaffold a project
nucleus init my-project
cd my-project

# Ingest from Postgres
nucleus ingest postgres://localhost/db --table=orders --target=raw.orders

# Open Workbench (v0.2+) or use SDK
nucleus workbench                   # http://localhost:3000
```

Target: **From `git clone` to a BI-ready Iceberg table in under 30 minutes** for a competent data engineer. This is the v0.1 success metric.

---

## Repository structure

```
.
├── AGENTS.md                       # Universal AI-agent instructions
├── README.md                       # This file
├── LICENSE                         # Apache 2.0
├── pyproject.toml                  # Dependencies + tool config
├── nucleus_architecture_v4.1.md    # Source-of-truth architecture (1678 lines)
├── nucleus_poc_plan.md             # 5 PoCs before v0.1 implementation
├── nucleus_architecture_v4.md      # DEPRECATED — see v4.1
├── nucleus_architecture_v3.md      # DEPRECATED — see v4.1
│
├── .cursor/rules/                  # Cursor-specific agent rules
│   └── nucleus.mdc
│
├── docs/
│   ├── architecture/               # C4 diagrams, sequence flows
│   ├── conventions/                # Engineering conventions
│   ├── decisions/                  # ADRs (Architecture Decision Records)
│   ├── patterns/                   # Big data patterns (type mapping, partitioning, …)
│   ├── research/                   # Library research notes (Constraint #10)
│   ├── security/                   # Threat model + security review
│   └── compatibility.md            # Tested version matrix (Constraint #11)
│
├── src/nucleus/                    # Source code (does not exist yet)
│   ├── ctx/                        # ctx SDK
│   ├── cli/                        # nucleus CLI
│   ├── engines/                    # Engine adapters
│   ├── coordination/               # Dagster wrappers
│   ├── intelligence/               # AI Layer (post v0.2)
│   └── physics/                    # Iceberg, Arrow, format adapters
│
├── tests/                          # pytest suite
├── poc/                            # PoC validations (5 of them, see poc_plan)
└── scripts/                        # Maintenance scripts (LOC budget, leak check, …)
```

---

## Contributing

**Not yet open to external contributions.** The project is in single-author phase until Tier 1 ships.

When external contributions open:
1. Read [`AGENTS.md`](AGENTS.md) — every PR must satisfy the 11 hard constraints
2. Read [`docs/conventions/engineering.md`](docs/conventions/engineering.md) — coding standards
3. Open an issue before writing code for anything >50 LOC
4. Every architectural change starts with an ADR in [`docs/decisions/`](docs/decisions/)

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

---

## Acknowledgments

Nucleus stands on the shoulders of giants. We **wrap** these projects, we don't build over them:

- [Apache Arrow](https://arrow.apache.org/) — columnar in-memory format
- [Apache Iceberg](https://iceberg.apache.org/) / [PyIceberg](https://py.iceberg.apache.org/) — open table format
- [Apache Parquet](https://parquet.apache.org/) — columnar storage
- [DuckDB](https://duckdb.org/) — embedded analytical engine
- [Polars](https://pola.rs/) — Rust-based DataFrame
- [Dagster](https://dagster.io/) — asset-based orchestration
- [DataFusion](https://datafusion.apache.org/) — distributed query engine (future)
- [OpenLineage](https://openlineage.io/) / [OpenTelemetry](https://opentelemetry.io/) — observability standards

If we build value, it's because these projects exist. Donate to them.

---

*Made for solo data engineers and small teams who want power without weight.*
