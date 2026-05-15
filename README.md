# Nucleus


**Quickstart:** [`docs/onboarding/quickstart.md`](docs/onboarding/quickstart.md) · **Examples:** [`examples/01-ecommerce-elt/`](examples/01-ecommerce-elt/) · **Roadmap anchor:** [`nucleus_architecture_v4.1.md` section 18 — Roadmap](nucleus_architecture_v4.1.md#18-roadmap)

[![Status: v0.1 beta](https://img.shields.io/badge/status-v0.1%20beta-yellow)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue)]()

> # Ship data products from a laptop.
>
> **What:** A local-first Python SDK (`ctx`) and CLI (`nucleus`) for Iceberg-native pipelines and analytics stacks on open Apache foundations, **AI-ready by design** (Copilot and agents are optional layers — not the product headline).
>
> **Who:** Teams matching **[`nucleus_architecture_v4.1.md` section 1.5](nucleus_architecture_v4.1.md#15-the-beachhead-v01-through-v10)** — think **~5 engineers**, **~100GB–5TB** greenfield data, building net-new analytics on laptops before they graduate to a cloud warehouse.
>
> **Why:** One coherent surface over DuckDB, Polars, Iceberg, and embedded orchestration — **no JVM** in the default path, Apache-2.0 core, and Iceberg snapshots you can take to Databricks, Snowflake, or REST catalogs when you outgrow a single node.

---

## v0.1 beta — what works vs. what waits

| Works today (stabilization) | Still ahead |
|-----------------------------|------------|
| `nucleus init`, `up`, `down`, `run`, `ingest`, `query`, `version` | First-class PyPI packaging polish (install today via editable git checkout) |
| `ctx.copy_from` (SQLite / Postgres / MySQL), `ctx.sql` + Jinja `ref`, `ctx.read` | Hosted Iceberg REST catalog co-defaults (Lakekeeper / Polaris) |
| `@nucleus.asset`, `@nucleus.check`, `nucleus materialize` path via the AMA | Workbench web IDE, lineage-aware Copilot, broad connector marketplace |
| Filesystem Iceberg catalog + local warehouse | Enterprise IAM — Nucleus delegates identity to OIDC when that layer ships |

This is **beta** software: expect rough edges; pin versions and read [`docs/compatibility.md`](docs/compatibility.md) before upgrading anything.

---

## Install

**Python 3.11** is the primary supported interpreter (3.12 may work; follow `pyproject.toml`).

```bash
git clone https://github.com/nucleus-data/nucleus.git
cd nucleus
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

When publishing completes, **`pip install nucleus`** becomes the default path; until then the editable install above is the supported developer workflow.

---

## 30-second demo (condensed beachhead path)

**A — Zero external data (uses the `nucleus init` greeting asset):**

```bash
nucleus init beachhead-demo && cd beachhead-demo
nucleus up
nucleus run example.greeting
nucleus query "SELECT * FROM {{ ref('example.greeting') }} LIMIT 5"
nucleus down
```

**B — Same flow with one SQLite ingest** (create `./data/orders.db` with an `orders` table first — see [`docs/recipes/sqlite_to_iceberg.md`](docs/recipes/sqlite_to_iceberg.md)):

```bash
nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
```

The **under 30 minutes** onboarding target (postgres + object storage + BI-ready mart) is spelled out in **architecture section 1.5**; the guided walkthrough lives in [`docs/onboarding/quickstart.md`](docs/onboarding/quickstart.md), with **`examples/01-ecommerce-elt/`** as the next “real project” step.

---

## Comparison (startup team lens — honest)

| Dimension | dbt-core | Dagster | Airflow | Databricks | Nucleus |
|-----------|----------|---------|---------|--------------|---------|
| **SQL-centric transforms** | Excellent | Good via libs | DIY | Excellent | Strong via `ctx.sql` + Jinja; **smaller macro ecosystem than dbt** |
| **Asset graph + orchestration** | Needs a runner | Excellent | Excellent | Excellent | **v0.1 uses explicit `nucleus run`**; embedded orchestration stays hidden per architecture |
| **Iceberg-first laptop story** | Adapter-dependent | DIY wiring | DIY | Cloud-first | **Filesystem catalog + Iceberg writes are the default path** |
| **Operational maturity** | High | High | Very high | Very high | **Beta** — fewer integrations, less production mileage |
| **Team you optimize for** | Analytics engineering | Platform-adjacent eng | Batch ops | Enterprise + SQL devs | **Small product teams shipping from git + laptop** |

We are **not** claiming to beat Databricks on breadth or Airflow on install base — we **are** optimizing for **local Iceberg + small-team velocity**, with a clean **graduation path** when laptops stop being enough.

---

## What is Nucleus (slightly longer)

A **local-first Python SDK + CLI** that wraps DuckDB, Polars, Apache Iceberg, PyArrow, and embedded orchestration behind **`ctx`** (programmatic) and **`nucleus`** (operator). A **data product** here means an Iceberg-backed **asset** with transforms, **contracts** (`@nucleus.check`), and lineage metadata — see **`nucleus_architecture_v4.1.md` section 12.1** for the precise definition. Vocabulary guidance for docs and UI: [`AGENTS.md`](AGENTS.md) section 7.

```python
import nucleus.ctx as ctx

ctx.copy_from(
    "postgres://localhost/ecommerce",
    table="public.orders",
    target="raw.orders",
    warehouse_dir="./data/warehouse",
)
df = ctx.sql(
    "SELECT customer_id, sum(amount) AS total FROM {{ ref('raw.orders') }} GROUP BY 1",
    warehouse_dir="./data/warehouse",
).collect()
```

---

## Why Nucleus exists

| You want… | But you often get… |
|-----------|-------------------|
| Lightweight local development | Heavy cluster boot | 
| Open formats | Vendor-only exports |
| Composable engines | Opaque bundles |
| Graduate without re-writing Iceberg | Lock-in by query dialect |

Nucleus optimizes the **on-ramp**; when you exceed single-node scale, **your Iceberg assets remain portable**.

---

## The Five Pillars

Mirrored from **`nucleus_architecture_v4.1.md` section 2** and [`AGENTS.md`](AGENTS.md) section 6:

1. **High performance on minimal resources** — DuckDB + Polars + Arrow; cold start budget **under ~10s** for `nucleus up`.
2. **Composable by constitution** — Tier 1/2 dependencies expose swap interfaces + smoke tests; **full alternate implementations stay on-demand**, not preemptive.
3. **AI-ready by design** — structured errors, schemas, and `ctx` ergonomics that LLMs can steer; **AI assists, it does not replace the data path**.
4. **Familiar UX** — borrow patterns from dbt / Dagster-style assets / modern CLI tooling.
5. **Friendly to giants** — Iceberg portability lets teams **graduate** to Databricks/Snowflake/REST catalogs without re-platforming the warehouse bytes.

---

## Architecture (one page)

Five layers (bottom → top): **Physics** (Arrow, Iceberg, Parquet, S3 API) → **Engines** (DuckDB, Polars, …) → **Coordination** (materialization + lineage) → **Intelligence** (Copilot, agents — staged) → **Experience** (`ctx` + CLI + Workbench).

- [`nucleus_architecture_v4.1.md`](nucleus_architecture_v4.1.md) — source of truth (**section 18** = versioned roadmap).
- [`docs/architecture/`](docs/architecture/) — diagrams and sequences.

---

## Operator & developer surfaces

### `ctx` SDK

```python
import nucleus.ctx as ctx
from nucleus import materialize

warehouse = "./data/warehouse"
ctx.copy_from("sqlite:///./data/events.db", table="events", target="raw.events", warehouse_dir=warehouse)
ctx.sql("SELECT * FROM {{ ref('raw.events') }}", warehouse_dir=warehouse)
ctx.read("raw.events", warehouse_dir=warehouse)
materialize("marts.daily_revenue")  # after `@nucleus.asset` registration + import
```

### `nucleus` CLI (v0.1)

```bash
nucleus init my-project && cd my-project
nucleus up
nucleus ingest sqlite:///./db.sqlite --table t --as raw.events
nucleus query "SELECT * FROM {{ ref('raw.events') }} LIMIT 10"
nucleus run marts.daily_revenue
nucleus down
nucleus version
```

Detailed flag and stability text: [`nucleus_cli_spec.md`](nucleus_cli_spec.md).

---

## Yield-to-giants strategy

Nucleus **complements** Databricks/Snowflake — Iceberg bytes port first; hybrid dispatch and federation are **later roadmap items** (`nucleus_architecture_v4.1.md` section 8).

---

## Repository structure (abridged)

```
.
├── AGENTS.md                      # Contributor + vocabulary rules
├── README.md                      # This file
├── nucleus_architecture_v4.1.md # Architecture + roadmap (section 18)
├── examples/                      # Curated end-to-end samples (start at 01-ecommerce-elt)
├── src/nucleus/                   # Implementation (ctx, CLI, coordination, …)
├── docs/                          # Onboarding, recipes, patterns, decisions
├── tests/
├── poc/                           # Historical PoC snapshots
└── scripts/                       # Governance (vocabulary, pins, LOC, leak check, …)
```

---

## Contributing

**External contributions are limited** while Tier 1 stabilizes — open an issue before large changes.

When the project opens up:

1. Read [`AGENTS.md`](AGENTS.md) — hard constraints are non-negotiable.
2. Follow [`docs/conventions/engineering.md`](docs/conventions/engineering.md).
3. Architectural forks start as recorded decisions under `docs/decisions/`.

---

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

---

## Acknowledgments

Nucleus **wraps** — it does not replace — these projects:

- [Apache Arrow](https://arrow.apache.org/), [Apache Iceberg](https://iceberg.apache.org/) / [PyIceberg](https://py.iceberg.apache.org/), [Apache Parquet](https://parquet.apache.org/)
- [DuckDB](https://duckdb.org/), [Polars](https://pola.rs/)
- [Dagster](https://dagster.io/)
- [OpenLineage](https://openlineage.io/), [OpenTelemetry](https://opentelemetry.io/)

If we ship something useful, it is because these foundations exist. Support them.

---

*For **small teams** who need **Iceberg-native** assets **today** without staffing a platform org — and who want a **documented path** when laptops stop being enough.*
