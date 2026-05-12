# Nucleus — Architecture v3 (DEPRECATED)

> ## ⚠️ DEPRECATED — Use v4 Instead
>
> **This document has been superseded by [`nucleus_architecture_v4.md`](./nucleus_architecture_v4.md).**
>
> v4 introduces the following changes:
> - **New thesis**: "Modern composable data engineering platform, AI-assisted, graduates cleanly to giants" (was: "local-first coordination plane for the modern open data stack")
> - **5 layers** instead of 4 (added Intelligence Layer for AI features)
> - **Composability by Constitution** as Law #1 (every dependency has a swap target)
> - **Yield-to-Giants strategy** (Modes 1/2/3 integration with Databricks/Snowflake) replaces "scale module"
> - **Lance + multimodal** added to Physics/Engines layers
> - **Workbench AI Copilot** ships in v0.1
> - **Realistic ambition recalibration**: $2-30M ARR over 5 years (not unicorn play)
>
> This file is retained for historical reference only. Do **not** use as source of truth.

## (Historical) Single Source of Truth · Locked Scope

> ~~This document supersedes `final_architecture.md` and `architecture_design_conversation.md`.~~
> ~~Any future change must explicitly reference and amend a section here.~~

---

## 0. Identity

Nucleus is **a local-first coordination plane for the modern open data stack**.

It is **not**:

- a database
- a query engine
- a Spark replacement
- a "Data OS"
- a universal compute platform
- an AI / ML platform
- a notebook-first platform

It owns three things, forever:

1. The **asset graph** (logical model of data)
2. The **`ctx` abstraction** (the developer contract)
3. The **unified experience** (CLI + Portal + SDK feeling like one product)

Everything else — SQL engine, DataFrame engine, scheduler, connectors, catalog, storage, notebooks, observability — is **rented from best-in-class open source** and hidden behind the abstractions above.

---

## 1. The Single Sentence

> **A local-first coordination plane for the modern open data stack.**

No additional adjectives. No "AI-powered". No "next-generation". This is the entire product positioning.

---

## 2. The Four-Line Decomposition

```text
Open lakehouse primitives        (Iceberg + Parquet + Arrow)
+ embedded vectorized compute    (DuckDB + Polars)
+ asset-centric coordination     (ctx SDK + Dagster, wrapped)
+ frictionless developer UX      (CLI + Portal + SDK as one product)
```

Every feature proposal — forever — must map to one of these four lines. If it does not, it is out of scope.

---

## 3. Locked Goals

| Goal | Concrete Target |
|---|---|
| Performance per resource | Beat Databricks/Snowflake on $/query for sub-10TB workloads |
| Onboarding speed | Time-to-first-pipeline < 15 minutes |
| Local-identical-to-prod | Same code, same semantics on laptop and k3s |
| Zero JVM in core path | Every always-on component is Rust/Go/C++/Python |
| Open formats forever | Iceberg + Parquet + Arrow + S3 API; never proprietary |
| Composable evolution | Engines swappable behind internal interfaces |

---

## 4. The Eight Design Laws

1. **Open formats over proprietary systems**
2. **Simplicity beats theoretical scalability**
3. **Local-first before distributed-first**
4. **SDK abstraction is the moat** — not the engine
5. **SQL + DataFrame are enough** — only two computational abstractions
6. **Engines are replaceable kernels** — never the product
7. **Friction elimination beats benchmark chasing**
8. **Operational simplicity is a feature**

A 9th meta-law: **doc length is inversely correlated with architectural maturity.** This document should never exceed ~400 lines.

---

## 5. The Four-Layer Architecture

```text
╔══════════════════════════════════════════════════════════════════╗
║   LAYER 4 — EXPERIENCE          (BUILD · the moat)               ║
║   `ctx` SDK · `nucleus` CLI · Portal · Connector UX · Templates   ║
╠══════════════════════════════════════════════════════════════════╣
║   LAYER 3 — COORDINATION        (WRAP · hidden)                  ║
║   Dagster (embedded) · dbt-duckdb · dlt · Soda · OpenLineage     ║
║   exposed only through `ctx`; users never touch them directly    ║
╠══════════════════════════════════════════════════════════════════╣
║   LAYER 2 — ENGINES             (WRAP · pluggable internally)    ║
║   DuckDB · Polars · Iceberg-rust · Lakekeeper · MinIO · Marimo   ║
║   behind internal (private, unstable) Rust interfaces            ║
╠══════════════════════════════════════════════════════════════════╣
║   LAYER 1 — PHYSICS             (IMMUTABLE)                      ║
║   Arrow · Iceberg spec · Parquet · S3 API · SQL · DataFrame algebra ║
║   never replaced; never broken                                    ║
╚══════════════════════════════════════════════════════════════════╝
```

The seam between Layer 2 and Layer 3 is the **composability boundary**. Engines change. `ctx` does not.

---

## 6. Build vs Wrap — The Critical Split

### What we build (~15–20K LOC total)

| Component | Language | LOC | Purpose |
|---|---|---|---|
| `ctx` SDK | Python | ~3–5K | The user-facing API. The product. |
| `nucleus` CLI | Rust | ~2–3K | One verb per concept; git-like ergonomics |
| Portal shell | TypeScript (Next.js) | ~8–10K | Embeds Dagster UI, dbt docs, Marimo, Monaco; one navbar |
| Asset Registry | Rust + Postgres | ~1–2K | `logical_name → Iceberg location + ownership` |
| Project scaffolder | Rust | ~1K | `nucleus init` templates |

**Total proprietary code ≈ 20K LOC of glue.** No novel scheduler. No novel lineage engine. No novel cache layer. No distributed systems work.

### What we wrap (rent)

| Concern | Wrapped Component | Notes |
|---|---|---|
| Orchestration / scheduling / retries / backfills | **Dagster** (embedded as library) | Hidden behind `ctx` |
| SQL transformations | **dbt-duckdb** | First-class; users keep their dbt projects |
| Ingestion / connectors | **dlt** | 100+ verified sources, schema inference |
| SQL execution | **DuckDB** | Default analytical engine |
| DataFrame execution | **Polars** | Default procedural engine |
| Table format | **iceberg-rust** + **pyiceberg** | ACID truth |
| Catalog | **Lakekeeper** (Rust) | Replaces Polaris (JVM-based, rejected) |
| Object storage | **MinIO** (embedded) / S3-compatible | |
| Notebooks | **Marimo** (embedded) | Replaces JupyterLite |
| Lineage | **OpenLineage spec** + **sqlglot** | Standard data model |
| Data quality | **Soda Core** / dbt tests | Behind `ctx.contract(...)` |
| SQL editor UI | **Monaco** | Embedded in Portal |
| Graph viz | **reactflow** / **cytoscape.js** | For asset + lineage views |
| Metrics emit | **OpenTelemetry** | Sinks pluggable |

---

## 7. The Core Stack (Always-On)

Boots with `nucleus up`. Zero JVM. Single binary or docker-compose.

| Layer | Choice | Why |
|---|---|---|
| Memory | Apache Arrow | Zero-copy contract |
| Files | Parquet (ZSTD-3) | Boring, perfect, ubiquitous |
| Tables | Apache Iceberg | Won the open table war |
| Storage | MinIO (embedded) | S3-compatible, lightweight |
| Catalog | Lakekeeper | Rust, fully Iceberg REST |
| SQL | DuckDB | Vectorized, embedded, no JVM |
| DataFrame | Polars | Rust + SIMD + Arrow-native |
| Orchestration | Dagster (embedded, hidden) | Production-grade, asset-centric |
| Connectors | dlt | 100+ sources free |
| Transformations | dbt-duckdb + `ctx` native | Familiar + powerful |
| Notebook | Marimo | Reactive, modern, no kernel hell |
| Metadata | SQLite → Postgres | Embedded → production migration |

---

## 8. Optional Modules (`nucleus enable <module>`)

The core stays tiny. Enterprise complexity is opt-in.

| Module | Adds | When to enable |
|---|---|---|
| `obs` | OTel Collector + VictoriaMetrics + VictoriaLogs + Grafana | Production deploy |
| `auth` | Authentik / OIDC, Casbin RBAC | Multi-user environments |
| `secrets` | Infisical (lightweight Vault alternative) | When env vars insufficient |
| `streaming` | Bento (CDC routing), Iceberg streaming writes | Real streaming requirement |
| `vector` | LanceDB | Vector retrieval workloads |
| `scale` | Daft + Ray distributed substrate | Empirical >10TB bottleneck |
| `federation` | Trino for cross-catalog queries | Multi-source unified queries |
| `governance` | Column-lineage UI, contract enforcement, PII scanner | Compliance requirements |
| `compat-dagster` | Expose Dagster UI directly for power users | Migration from existing Dagster |
| `compat-airflow` | Run Airflow DAGs as Nucleus assets | Brownfield adoption |

---

## 9. The `ctx` SDK — The Product

This is the only API users see. Everything else is implementation detail.

```python
import nucleus
import polars as pl

@nucleus.asset(table="sales.orders", schedule="@daily")
def orders(ctx):
    raw = ctx.read("raw.orders")
    return (
        raw.filter(pl.col("date") >= ctx.params.start_date)
           .join(ctx.read("dim.customers"), on="customer_id")
    )

@nucleus.sql_asset(table="sales.daily_revenue")
def daily_revenue(ctx):
    return """
        SELECT date, SUM(amount) AS revenue
        FROM {{ ref('sales.orders') }}
        GROUP BY 1
    """

@nucleus.contract("sales.orders")
def orders_contract():
    return [
        nucleus.expect("order_id").is_unique(),
        nucleus.expect("amount").gt(0),
        nucleus.expect("date").freshness("1 day"),
    ]
```

### `ctx` surface (frozen for v1)

| API | Purpose |
|---|---|
| `ctx.read(name)` | Read asset → Arrow / Polars / DuckDB relation |
| `ctx.write(name, df)` | Atomic Iceberg commit |
| `ctx.sql(query)` | DuckDB execution with `{{ ref() }}` resolution |
| `ctx.params` | Pipeline parameters (typed) |
| `ctx.log` | Structured logging |
| `ctx.metrics` | Custom metrics emission |
| `ctx.secrets` | Secret retrieval |
| `ctx.snapshot(name)` | Iceberg time-travel access |

Users **never** see: `iceberg.catalog`, `dagster.AssetIn`, `dlt.pipeline`, `duckdb.connect`, `s3://...` paths. Those are leaks.

---

## 10. The CLI Surface — `nucleus`

Git-like ergonomics. One verb per concept.

```bash
nucleus init my-project           # scaffold project
nucleus up                        # boot full local stack (<30s)
nucleus connect postgres://...    # add ingestion source
nucleus sql "SELECT ..."          # ad-hoc query
nucleus build                     # materialize all assets
nucleus run <asset>               # run one asset
nucleus lineage <asset>           # show lineage
nucleus snapshot list             # Iceberg time-travel
nucleus snapshot revert <id>      # rollback
nucleus enable <module>           # turn on optional module
nucleus deploy --target k3s       # ship to production
```

The local and production code paths are **byte-identical**. Same SDK, same `ctx`, same Iceberg semantics, same engines.

---

## 11. The Portal — Familiarity Mapping

Every tab maps 1:1 to a tool users already know. Zero new mental models forced on users.

| Portal Tab | Familiar Tool | Implementation |
|---|---|---|
| **Assets** | Dagster asset graph + dbt docs | Embed Dagster UI panel; overlay our asset registry |
| **SQL Editor** | Snowflake worksheets | Monaco editor + DuckDB Arrow Flight backend |
| **Notebooks** | Databricks notebooks | Embed Marimo (reactive, deterministic) |
| **Runs** | Dagster / Airflow runs | Embed Dagster runs view |
| **Connectors** | Fivetran source catalog | UX wrapper around dlt verified sources + OAuth |
| **Catalog** | dbt docs + Snowflake info_schema | Schema browser, column docs, ownership |
| **Lineage** | OpenLineage / Marquez | reactflow graph fed by OpenLineage events |
| **Observability** | Grafana | Embedded panels when `obs` module enabled |

---

## 12. Composability Model — Internal Interfaces Only

Engines are pluggable, but **only for ourselves in v1**. There is **no public plugin SDK** until ecosystem demand is empirically demonstrated.

```rust
// crates/nucleus-core/src/internal/
//   query_engine.rs    — private, unstable
//   catalog.rs         — private, unstable
//   connector.rs       — private, unstable
//   storage.rs         — private, unstable
```

These interfaces let us swap DuckDB → chDB, Polars → Daft, MinIO → S3, Lakekeeper → Polaris **internally** without rewriting `ctx`. But they are **not** documented as a public API, **not** versioned as a contract, **not** part of any ecosystem promise.

Public plugin SDK becomes a goal **only when**:

1. ≥ 3 paying customers request the same extension point
2. The pattern has emerged naturally from internal usage
3. There are resources to maintain backward compatibility

Until then: internal, undocumented, refactorable at will.

---

## 13. What We Explicitly Do NOT Build

| Not built | Reason |
|---|---|
| Custom scheduler | Dagster has 50+ engineer-years of edge cases |
| Custom orchestration engine | Same as above |
| Custom lineage parser | OpenLineage + sqlglot suffice |
| Custom connectors | dlt covers 100+ sources free |
| Custom SQL engine | DuckDB is correct |
| Custom DataFrame engine | Polars is correct |
| Custom table format | Iceberg is correct |
| Custom catalog implementation | Lakekeeper is correct |
| Custom notebook runtime | Marimo is correct |
| Custom data quality framework | Soda + dbt tests are correct |
| Custom auth/RBAC | Authentik + Casbin are correct |
| Custom observability backend | VictoriaMetrics + VictoriaLogs are correct |
| Distributed execution v1 | Defer until empirical trigger |
| Public plugin SDK v1 | Defer until ecosystem demand |
| Multi-tenant cloud control plane | Different product; defer |

If any of these end up in a future doc as "we should build", that doc must explain why the wrapped alternative failed in production telemetry, not in theory.

---

## 14. Removed from the Mental Model

These framings, if they appear in any future README, pitch deck, or design doc, will quietly drag the product into the wrong category. Strike them on sight.

- ❌ "Data OS"
- ❌ "Spark killer"
- ❌ "Universal compute platform"
- ❌ "Own every layer"
- ❌ "AI-first platform"
- ❌ "Distributed-first" (in v1)
- ❌ "Plugin marketplace" (in v1)
- ❌ "Better Databricks" (we are *different*, not *better-of-the-same*)

The correct framing: **the easiest way to operate modern open data infrastructure.**

---

## 15. Roadmap

Each milestone adds layers without breaking the `ctx` contract. The asset model never changes.

| Version | Capability | Audience | ETA |
|---|---|---|---|
| **v0.1** | Single binary; `nucleus up` boots DuckDB + Iceberg + MinIO + Lakekeeper + `ctx` SDK; one asset runs end-to-end | Internal alpha | 2–3 mo |
| **v0.3** | Dagster embedded & hidden; dbt-duckdb first-class; dlt connector UX; basic Portal (assets + SQL) | 5–10 design partners | 4–5 mo |
| **v0.5** | Portal complete (assets, SQL, Marimo, lineage); multi-user auth; project deploy via k3s | Closed beta, 20–50 teams | 7–9 mo |
| **v0.8** | `obs` + `auth` modules; snapshot mgmt; upgrade tooling; contract API | Open beta | 10–12 mo |
| **v1.0** | HA mode; RBAC at column level; alerting; production runbooks; SOC2 readiness | **GA production-ready** | 14–18 mo |
| **v1.5** | CDC + streaming module; dbt → SQLMesh migration; BI tool integrations (Metabase, Superset) | Stack-replacement deployments | 20–24 mo |
| **v2.0** | `scale` module (Daft + Ray); distributed catalog | Teams approaching 10TB+ | 30+ mo |
| **v2.5** | Federation: multiple Nucleus clusters share assets via Iceberg REST | Multi-region / multi-team | — |
| **v3.0** | Public plugin SDK; community engines & connectors | Ecosystem play | — |

**Feature-freeze rule**: between major versions, no feature ships unless it maps to one of the four lines in §2 and is justified by telemetry from real users, not by hypothetical scenarios.

---

## 16. Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| Dagster upstream breaking changes | Medium | Pin version, integration test suite, contribute upstream |
| Lakekeeper maturity gaps | Medium | Fallback path to Polaris or file-based catalog |
| iceberg-rust spec coverage gaps | Medium | Fallback to pyiceberg for missing features |
| Portal UI underestimated effort | High | Phase 1 embeds Dagster UI in iframe; native panels replace later |
| Compliance (SOC2/HIPAA) takes long | High | Outsource audit (Vanta/Drata); v1.0 = readiness, certification = v1.2 |
| DuckDB concurrency / multi-tenant | Medium | Process-pool routing per user; chDB swap as alternative |
| dbt-duckdb adapter gaps | Low | Active community; contribute back |
| Marimo ecosystem maturity | Low | Fallback to embedded Jupyter if blocking |

**Risks that no longer exist** (versus building from scratch):

- ✅ Scheduler correctness — Dagster's problem
- ✅ Backfill semantics — Dagster's problem
- ✅ Connector breadth — dlt's problem
- ✅ SQL transformation engine — dbt's problem
- ✅ Iceberg correctness — Apache project's problem
- ✅ Query performance — DuckDB's problem
- ✅ DataFrame performance — Polars' problem

---

## 17. Success Metrics

The only metrics we optimize:

| Metric | Target |
|---|---|
| Time-to-first-pipeline | < 15 minutes (cold start to first asset materialized) |
| `nucleus up` boot time | < 30 seconds on a modern laptop |
| Local → prod parity | 100% (same code, byte-identical semantics) |
| Memory footprint at idle (core only) | < 500 MB |
| Cost vs Databricks at 1TB workload | < 20% (4–10× cheaper) |
| Lines of proprietary code | < 25K (discipline metric) |
| Always-on core components | ≤ 8 (discipline metric) |

Benchmark charts are not a metric. "TPC-H 12% faster" is not a metric. **Friction elimination is the metric**, measured by adoption and time-to-value.

---

## 18. The Decision Frame (For Every Future Choice)

Before adding any feature, component, or abstraction, answer:

1. Does it map to one of the four lines in §2?
2. Does it serve the < 15-minute onboarding target?
3. Can we wrap it instead of building it?
4. Does it preserve the no-JVM constraint?
5. Does it preserve local-identical-to-prod?
6. Does it remain inside the < 25K LOC proprietary budget?
7. Is it triggered by empirical user telemetry, or by anxiety?

If any answer is "no" or "unclear" → not now.

---

## 19. Final Conclusion

Nucleus is not a stack of cool tools. It is a **coherent product** with three locked-in things:

```text
1. The asset graph        (logical model of data)
2. The ctx abstraction    (developer contract)
3. The unified experience (CLI + Portal + SDK as one)
```

Everything else — every engine, every format, every binary — is a **commodity** wrapped behind those three.

The bet, in one line:

> Users will not adopt Nucleus because we built the best engine.
> They will adopt Nucleus because **modern open data infrastructure finally feels coherent.**

That is small enough to build, large enough to win, and structured to evolve for a decade as engines beneath it change.

---

## Appendix A — Locked Component Decisions

| Concern | Choice | Rejected Alternatives |
|---|---|---|
| Memory format | Arrow | — |
| File format | Parquet | Vortex (defer, premature) |
| Table format | Iceberg | Delta (less open), Hudi (smaller community) |
| Storage | MinIO + S3-compatible | — |
| Catalog | Lakekeeper | Polaris (JVM), Nessie (branching complexity), Glue (cloud lock-in) |
| SQL engine | DuckDB | chDB (optional swap), DataFusion (optional swap) |
| DataFrame engine | Polars | Daft (dormant scale seam), pandas (no) |
| Orchestrator | Dagster (embedded, hidden) | Airflow (JVM-ish, dated), Prefect (cloud-oriented), Temporal (not data-native) |
| Connectors | dlt | Airbyte (heavy), Fivetran (proprietary), custom (tarpit) |
| Transformations | dbt-duckdb + `ctx` native | SQLMesh (defer to v1.5) |
| Notebook | Marimo | JupyterLite (gimmicky), JupyterHub (heavy) |
| Lineage | OpenLineage + sqlglot | Custom parser (overbuilding) |
| Data quality | Soda Core / dbt tests | Great Expectations (heavy), custom (overbuilding) |
| Metadata DB | SQLite → Postgres | — |
| Metrics (addon) | VictoriaMetrics | Prometheus (heavier), InfluxDB (proprietary tendency) |
| Logs (addon) | VictoriaLogs | Loki (indexing issues), Elasticsearch (JVM monster) |
| Auth (addon) | Authentik + Casbin | Vault HA (overkill), OPA (latency) — both as optional only |

## Appendix B — Document Discipline

If this document grows past 400 lines, scope has leaked. Trim before adding.

If a future doc proposes building anything in §13 ("What We Explicitly Do NOT Build"), it must first explain why the wrapped alternative failed **in production telemetry**, not in theory.

If a future doc reintroduces any framing in §14 ("Removed from the Mental Model"), strike it.

---

*End of Nucleus Architecture v3. This is the single source of truth.*
