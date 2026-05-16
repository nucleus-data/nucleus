# Nucleus v0.2.0 — A modern, composable data engineering platform for startup teams

*Published 2026-05-15 · Apache 2.0 · Read time: ~10 min*

---

## TL;DR

Today we are releasing **Nucleus v0.2.0**, the first publicly-available version of a local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks on open Apache foundations. Nucleus is **AI-ready by design** — Copilot and agents are optional layers, not the headline. It grows with your team. It graduates cleanly to giants like Databricks, Snowflake, or any Iceberg catalog when you outgrow your laptop.

If you are a 5–20 engineer team building a greenfield analytics stack on 100 GB–5 TB of data, Nucleus is built for you.

```bash
pip install nucleus
nucleus init my-stack && cd my-stack
nucleus up
nucleus ingest postgres://localhost/app --table public.orders --as raw.orders
nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
```

That's the 30-second pitch. Read on for what we built, why we built it this way, and how it fits into the modern data landscape.

---

## The problem

If you are building a data platform from scratch in 2026, the menu in front of you looks something like this:

- A connector tool (Fivetran, Airbyte, Singer, dlt)
- A transformation tool (dbt-core, SQLMesh)
- An orchestrator (Airflow, Dagster, Prefect)
- A warehouse or lakehouse (Snowflake, Databricks, BigQuery)
- A catalog (Hive, Glue, Polaris, Lakekeeper, Unity)
- A BI layer (Superset, Metabase, Looker, Hex)
- A metadata/observability layer (DataHub, Atlan, Soda)
- A notebook environment (Jupyter, Hex, Marimo)
- And, increasingly, "an AI layer" bolted onto everything else

For a five-engineer team this is a 9-tool integration project before a single byte of business value flows. Each tool has its own CLI, its own auth model, its own deployment story, its own opinions on how an `asset` should be defined. Your team spends month one wiring it all up; month two debugging why the orchestrator's view of an asset disagrees with the catalog's view; month three building a thin "platform layer" of glue scripts so your data engineers don't lose their minds.

The hyperscale lakehouses (Databricks, Snowflake) solve this elegantly — but at $50K-and-up annual contract sizes, with cluster boot times that make local development hell, with proprietary execution that locks your bytes into vendor formats, and with operating models built for 200-engineer central platform teams, not 5-engineer startups.

The local-first OSS stack (DuckDB, Polars, pyiceberg, Dagster) is technically excellent — but it is *parts*, not a *product*. You are still doing the integration work yourself.

**Nucleus is the integration.** One coherent surface over DuckDB, Polars, Apache Iceberg, embedded orchestration, and AI-ready ergonomics. No JVM in the default path. Apache 2.0 forever. Iceberg snapshots you can take to any catalog, any time, with zero migration.

---

## What Nucleus is

Nucleus is **three things, forever**:

1. **The asset graph** — the logical model of your data products
2. **The `ctx` SDK** — the developer contract (the only public API you import)
3. **The unified developer-first experience** — CLI + Workbench + SDK as one product

Everything else — engines, catalogs, schedulers, ingestion frameworks — is rented from open source and wrapped behind `ctx`. Per `nucleus_architecture_v4.1.md` §3, we organize this into **five layers**:

| Layer | Components | Mutability |
|---|---|---|
| **L4 Experience** | `ctx` SDK · `nucleus` CLI · Workbench · Marimo (v0.3+) | Evolves with users |
| **L3 Intelligence** | Copilot (v0.2 chat; v0.5 lineage-aware; v0.7+ agent runtime) | Continuously refined |
| **L2 Coordination** | Asset graph · Asset Materialization Adapter · Error Translation · Contracts · Lineage · Run ledger · Scheduling daemon | Stable from v1.0 |
| **L1 Engines** | DuckDB (default) / DataFusion (swap) · Polars (default) / DataFusion DF (swap) · Daft (v0.5+ optional) | Swap on-demand |
| **L0 Physics** | Apache Arrow · Apache Iceberg · Apache Parquet · Lance · S3 API · OpenLineage · OpenTelemetry | Immortal — open standards |

The asset is the **only primitive**. There are no "tables" vs "jobs" vs "pipelines vs notebooks" — just assets. A Python asset, a SQL asset, a source asset, a check, a schedule. Each one has a stable ID (`namespace.name`), a contract, a lineage, and a materialization history. That model holds from your first asset through the day you graduate to a 10-team Databricks deployment.

---

## The five pillars (frame every decision)

Per `AGENTS.md` §6 — every Nucleus design decision must serve at least one of these without harming another:

1. **High performance on minimal resources.** DuckDB + Polars + Arrow do the heavy lifting. We measured `nucleus up` cold boot at **5.82 s** in PoC #4 (target was <10 s) on a 16 GB MacBook-class host. Idle RSS sits at **117 MB**.
2. **Composable by constitution.** Every Tier 1/2 dependency exposes a swap interface and runs basic smoke tests in CI. We do not maintain second implementations preemptively (that's "Composability Tax"); we build the full adapter on demand when a trigger fires (vendor death, license pivot, perf regression >2x). See `docs/swap/dagster.md`.
3. **AI-ready by design.** Structured errors, predictable schemas, machine-introspectable `ctx` SDK. The platform is engineered for LLM comprehension. Copilot is a *feature*, not the headline.
4. **Familiar UX from proven giants.** SQL templating feels like dbt. Asset graph feels like Dagster. Local-identical-to-prod feels like Supabase. CLI ergonomics feel like Vercel/Linear/Cursor. We do not invent vocabulary.
5. **Friendly to giants, hostile to no-one.** Iceberg portability means your bytes stay yours. The day you outgrow Nucleus, you point Databricks/Snowflake at the same S3 + catalog and you're done. No re-migration. No format lock-in.

---

## What's in v0.2.0

This release ships **everything you need to build a production-shaped pipeline on a single laptop**, plus a Workbench so your team can collaborate without leaving the browser.

### The `ctx` SDK

```python
import nucleus
import nucleus.ctx as ctx

@nucleus.asset(schedule="@daily")
def fct_orders(ctx):
    raw = ctx.read("raw.orders")
    return raw.filter(pl.col("status") == "completed")

@nucleus.check(asset="fct_orders")
def orders_have_amount(ctx):
    return ctx.sql("SELECT count(*) FROM {{ ref('fct_orders') }} WHERE amount IS NULL").collect()[0, 0] == 0
```

Surface stable from v0.1: `ctx.read`, `ctx.sql`, `ctx.copy_from`, `ctx.params`. Schema contracts via `@nucleus.check` (`src/nucleus/sdk/decorators.py`). Programmatic materialization via `materialize()` (`src/nucleus/sdk/materialize.py`).

### Eight-command CLI

Per `nucleus_cli_spec.md` and `src/nucleus/cli/main.py`:

| Command | Purpose |
|---|---|
| `nucleus init <project>` | Scaffold a new Nucleus project |
| `nucleus up` | Boot local stack (storage + catalog + orchestration) |
| `nucleus down` | Tear down local stack |
| `nucleus run <asset>` | Materialize one asset on demand |
| `nucleus ingest <source>` | One-liner Postgres / MySQL / SQLite / S3 / GCS / Snowflake / filesystem ingest |
| `nucleus query "<SQL>"` | Run a Jinja-templated SQL query against the warehouse |
| `nucleus chat "<prompt>"` | Talk to the AI Copilot (anthropic / openai / ollama via litellm) |
| `nucleus version` | Print version + diagnostic banner |

Plus `nucleus runs`, `nucleus schedule`, and `nucleus snapshot` subcommand groups for run history, scheduling lifecycle, and Iceberg branch/tag management.

### Seven connectors via `ctx.copy_from`

| Source | Module | Extras |
|---|---|---|
| PostgreSQL | `src/nucleus/ctx/copy_from_postgres.py` | `nucleus[postgres]` |
| MySQL | `src/nucleus/ctx/copy_from_mysql.py` | `nucleus[mysql]` |
| SQLite | `src/nucleus/ctx/copy_from.py` | core |
| Snowflake | `src/nucleus/ctx/copy_from_snowflake.py` | `nucleus[snowflake]` |
| Amazon S3 | `src/nucleus/ctx/copy_from_s3.py` | core (DuckDB httpfs) |
| Google Cloud Storage | `src/nucleus/ctx/copy_from_gcs.py` | `nucleus[gcs]` |
| Local filesystem (Parquet/CSV/JSON, glob) | `src/nucleus/ctx/copy_from_filesystem.py` | core |

All seven funnel through one user-facing dispatcher and emit consistent `NucleusError` subclasses on failure (no `psycopg.OperationalError` or `dlt._internal.errors.LoadError` ever leaks to the user).

### Workbench v0.3 — editorial dashboard

A web IDE that opens with `nucleus workbench up`. Editorial gradient hero with the day's pipeline summary, a 3-column body grid (recent runs, pipeline DAG, AI Copilot), seven interactive routes (Dashboard / Assets / Asset detail / Runs / Run detail / Schedules / Catalog / Query), live SSE log streaming for in-flight materializations, and a real ⌘K command palette that searches assets, runs, and schedules. Single uvicorn worker out of the box; horizontal scaling via `--workers=N` per the production-deployment cookbook (`docs/cookbook/production-deployment.md`).

### Active scheduling daemon + durable run ledger

`@nucleus.asset(schedule="@daily")` and `@nucleus.asset(schedule="0 2 * * *")` now actually run on schedule. A 5-second-poll daemon (`src/nucleus/coordination/daemon.py`) backed by `croniter==3.0.4` materializes due assets via the AMA. Lifecycle: `nucleus schedule on` (background subprocess), `nucleus schedule off`, `nucleus schedule trigger <key>`, `nucleus schedule status`. Cross-platform — Windows uses `psutil.TerminateProcess`; POSIX uses SIGTERM.

Every materialization writes a typed record to a durable NDJSON ledger at `<project>/.nucleus/runs/runs.ndjson` (`src/nucleus/coordination/run_ledger.py`). `nucleus runs list / show / cancel / tail --follow` exposes the history.

### Reliability hardening (Wave 2 P0 work)

Per ADR-024 + ADR-025:

- **DuckDB `memory_limit` guard at AMA init** — set to 80% of total RAM, clamped [2 GB, 32 GB], overridable in `nucleus_project.yaml`. OOM conditions now surface as `NucleusMemoryLimitExceeded` (NE2007) instead of opaque crashes.
- **Advisory filesystem lock for concurrent runs** — cross-platform context manager (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows). Stale locks (dead PID) auto-reclaimed. `NucleusConcurrentRunError` (NE3008) after a 30 s timeout. *Note: B4 concurrent-run safety still FAILs on Windows in our 2026-05-15 baseline because NTFS lock semantics differ from POSIX (`docs/benchmarks/2026-05-15_baseline.md` §B4); fix tracked for v0.2.1.*
- **`expire_old_snapshots` post-commit maintenance** — keeps the most recent 10 snapshots, expires older ones beyond `retain_days`. Maintenance failures are non-fatal.
- **Error-budget SLO definitions** — per-operation `target_p95` thresholds for boot, materialize, query, ingest. OTEL enforcement deferred to v0.5+.

### `nucleus.db` BI handshake (ADR-026)

Every `nucleus up` writes a single DuckDB file at `<project>/nucleus.db` containing one native table per materialized Iceberg asset, plus a `_nucleus_catalog_info` metadata table. Connect Superset, Evidence, Rill, or Streamlit by pointing at one file path. Recipe: `docs/cookbook/bi-connectivity.md`.

### Iceberg branch + tag CLI (ADR-028, Beta)

`nucleus snapshot branch create/delete` and `nucleus snapshot tag create/delete` expose PyIceberg's `manage_snapshots()` for write-audit-publish workflows and EOM/EOW compliance archiving. Full WAP semantics arrive with Lakekeeper in v0.3.

### AI Copilot v0.2

Single-turn chat via `litellm==1.83.14` (`src/nucleus/intelligence/copilot.py`). Built-in providers: `anthropic`, `openai`, `ollama`. API keys come from your shell, never logged, never sent to Nucleus servers (we don't have any). Opt-in consent stored at `.nucleus/copilot_opt_in`. Cost ceiling defaults to $0.10/call. Setup recipe: `docs/cookbook/ai-copilot-setup.md`.

This is *intentionally thin*. v0.2 ships the smallest useful Copilot. Schema-aware completion arrives in v0.3; lineage-aware refactoring + `ctx.agent` runtime arrive in v0.5. We are not selling AI as the headline.

### Install-size split (ADR-039)

```bash
pip install nucleus              # lean core, <30 deps, <60 s install
pip install nucleus[postgres]    # + psycopg
pip install nucleus[snowflake]   # + dlt[snowflake]
pip install nucleus[gcs]         # + gcsfs
pip install nucleus[ai]          # + litellm + anthropic + openai
pip install nucleus[workbench]   # + fastapi + uvicorn
pip install nucleus[all]         # everything
```

Lazy-import boundary at `pyproject.toml` lines 134-139 enforced by `scripts/check_lazy_imports.py` and `scripts/check_install_size.py` in CI.

### 11-script governance suite

`scripts/check_vocabulary.py`, `check_pinning.py`, `loc_budget.py`, `dagster_leak_check.py`, `check_error_codes.py`, `check_api_stability.py`, `check_licenses.py`, `check_layering.py`, `check_lazy_imports.py`, `check_install_size.py`, `check_perf_budget.py`. All eleven gate the CI build. The vocabulary scanner blocks the usual forbidden framings (per `AGENTS.md` §7 and §8). The `dagster_leak_check.py` blocks any release where an external classname leaks into a user-facing string.

### Public docs site

~55 pages, MkDocs Material, served at `mkdocs serve` locally. Installation, quickstart, concepts, guides, cookbook, CLI reference, API reference, errors, governance, philosophy. Built and deployed from `docs/site/` via `.github/workflows/docs.yml`.

---

## How to graduate (yield-to-giants)

The day Nucleus is the wrong tool, here is how you leave — without re-migrating a single byte. Per `nucleus_architecture_v4.1.md` §10:

**Mode 1 — Graduation (zero effort, available today).** Your Iceberg snapshots in S3 are vendor-neutral by definition. Point Databricks, Snowflake, or any Iceberg REST catalog (Polaris, Lakekeeper, Unity, R2) at the same bucket + catalog and you are done. Mode 1 ships with v0.2 because it is just Iceberg + S3 + the open standards on which Nucleus runs.

**Mode 2 — Hybrid compute (v1.5+).** Annotate an asset with `compute="databricks"` or `compute="snowflake"` and Nucleus orchestrates while the giant executes the heavy SQL. Result committed back to Iceberg. The 30-min onboarding ergonomics stay. The 100-TB heavy lifting yields. This is the architecturally-correct answer for the upper edge of the documented data envelope (>5 TB).

**Mode 3 — Federation (v2.0+).** Each domain runs its own Nucleus; cross-domain queries via Trino, Databricks, or Snowflake against the federated Iceberg catalog. Data Mesh full.

Per `docs/internal/research/scale_out_audit.md`, **none of these modes require rewriting Nucleus internals**. Nucleus is glue; the real work happens in C++ (DuckDB, pyarrow), Rust (Polars), or wire-bound network I/O. At any meaningful workload, ~95% of execution time is already in code that Nucleus does not own. Yield is a feature of the architecture, not a future migration.

---

## What's next (v0.3 teaser)

Per the v4.1 roadmap (§18.3):

- **Lakekeeper REST catalog** — production-grade catalog with OIDC delegation; co-default with Polaris alternate per ADR-004
- **dlt v0.3+ integration** — 100+ connectors (Stripe, Salesforce, Hubspot, …) wrapped behind `@nucleus.source(engine="dlt")`
- **Marimo notebooks** — reactive deterministic notebooks that share the asset graph
- **Schema-aware Copilot** — completion that knows your asset shapes and contracts
- **dbt-duckdb optional adapter** — for teams migrating from a dbt-core setup
- **Sensors** — event-triggered materializations
- **Incremental materialization** + `ctx.snapshot()`

We do not promise dates. We *do* promise that every v0.3 commit will pass the same 11 governance gates and respect the same 30-min beachhead metric.

---

## Call to action

```bash
# Get started in 30 seconds:
git clone https://github.com/nucleus-data/nucleus.git
cd nucleus
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# Or, after the release workflow publishes to PyPI:
pip install nucleus
```

- **Repo & quickstart**: <https://github.com/nucleus-data/nucleus>
- **Docs**: <https://nucleus-data.github.io/nucleus/> once GitHub Pages is enabled; until then use `docs/site/` locally with `mkdocs serve`
- **Architecture deep-dive**: `nucleus_architecture_v4.1.md` (~50 min read)
- **License**: Apache 2.0
- **First example**: `examples/01-ecommerce-elt/`

If you build something useful with Nucleus, tell us. If something breaks, file an issue with the `NE####` error code from the failure — every error has a `docs_url` pointing to a fix recipe.

We built Nucleus for ourselves first. We hope it works for you too.

---

*Honest disclosures (because credibility matters).* Nucleus v0.2.0 is **beta software**. The empirical benchmark baseline at `docs/benchmarks/2026-05-15_baseline.md` documents 11 measured failures vs the aspirational performance targets in `docs/internal/research/performance_reliability_targets.md` — boot time runs ~2 s on a contention-loaded host vs the original <500 ms claim, and the B4 concurrent-run safety test FAILs on Windows due to NTFS lock semantics. We are documenting these honestly rather than re-running until numbers improve. Re-measurements on freshly-booted beachhead-spec hardware are tracked for v0.2.1.

*Nucleus is built on the work of [Apache Arrow](https://arrow.apache.org), [Apache Iceberg](https://iceberg.apache.org), [Apache Parquet](https://parquet.apache.org), [DuckDB](https://duckdb.org), [Polars](https://pola.rs), [Dagster](https://dagster.io), [OpenLineage](https://openlineage.io), and [OpenTelemetry](https://opentelemetry.io). If we ship something useful, it is because these foundations exist. Support them.*
