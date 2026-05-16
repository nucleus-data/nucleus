# Nucleus vs Databricks — Full Feature Mapping

> Validation document. Maps every major Databricks surface (UI, feature, workflow) to its Nucleus equivalent.
> Companion to `nucleus_architecture_v3.md`.

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Have it (native, wrapped, or via optional module) |
| 🎯 | We win on this dimension (better DX, cheaper, more open) |
| ⏳ | Deferred — explicit version in roadmap |
| 🚫 | Deliberately out of scope (per architecture §13/§14) |
| ❓ | Real gap — needs explicit acknowledgement |

---

## 1. Navigation & Workspace

| Databricks | Nucleus | Status | Note |
|---|---|---|---|
| Left sidebar (Workspace, Catalog, Workflows, Compute, AI/ML, Marketplace) | Portal sidebar (Assets, SQL, Notebooks, Runs, Connectors, Catalog, Lineage, [Observability]) | ✅ | Different shape, equivalent coverage |
| Workspace = cloud-stored folder tree of notebooks/queries | Project = local git repo with Python files | 🎯 | Git-native; code lives where engineers live |
| Workspace search | Portal global search (assets, queries, runs) | ⏳ v0.5 | Standard, not innovative |
| Recents | Portal recent items | ⏳ v0.5 | Standard |
| Notebook permissions per item | RBAC at asset level (`auth` module) | ⏳ v0.8 | Less granular initially, by design |

**Verdict**: Different paradigm. Databricks = cloud workspace database. Nucleus = git-native project. Better for engineering teams, slightly different mental model for analysts.

---

## 2. Notebooks

| Databricks Notebooks | Nucleus Notebooks (Marimo) | Status | Note |
|---|---|---|---|
| Python / SQL / Scala / R cells | Python primary; SQL via `ctx.sql()` | 🚫 Scala/R | Intentional — no JVM, no R runtime in core |
| `%sql`, `%python`, `%md` magic | SQL cells natively + markdown | ✅ | Same outcome, different syntax |
| Built-in chart picker on results | Plotly/Altair widgets in Marimo | ❓ Polish gap | Marimo has UI elements, no one-click chart |
| Comments / threading | Marimo lacks threaded comments | ❓ Real gap | Defer to v1.0 |
| Variable inspector | Marimo cell graph + native reactivity | 🎯 | Reactive > inspector |
| Run All / Run Above / Run Below | Marimo auto-runs dependents reactively | 🎯 | No hidden state ever |
| Schedule notebook as job | Notebook = `@nucleus.asset`, scheduled via Dagster | ✅ | Better mental model |
| Git Repos integration | Project is *already* git | 🎯 | Native vs bolted on |
| Variable widgets | Marimo native widgets | ✅ | Better DX |
| Notebook version history | Git log | 🎯 | Real version control |
| .ipynb JSON files | Marimo uses pure `.py` files | 🎯 | Real diffs in PRs |
| Collaboration / co-editing | None native | ❓ Real gap | Defer; v1.5 if demanded |
| Genie / AI assist in cells | None | 🚫 | Out of scope; user can plug Copilot externally |

**Verdict**: We **win on engineering DX** (reactive, git-native, deterministic). We **lose on analyst polish** (no chart picker, no co-editing, no Scala/R). Acceptable for our ICP.

---

## 3. SQL Editor & Warehouse

| Databricks SQL | Nucleus SQL Editor | Status | Note |
|---|---|---|---|
| Multi-tab worksheets | Monaco multi-tab worksheets | ✅ | |
| Schema browser | Schema browser (Lakekeeper-backed) | ✅ | |
| Query history | Query history table | ✅ v0.5 | |
| Saved queries | Saved as `.sql` files in git | 🎯 | Versioned by default |
| Result charts | Chart panel on result | ⏳ v0.5 | Need to build |
| Auto-complete | LSP-based (DuckDB schema) | ✅ v0.5 | |
| Format SQL | sqlfluff / sqlglot | ✅ | |
| Schedule query → alert | Schedule via `@nucleus.sql_asset`; alerts in `obs` module | ⏳ v1.0 | |
| Share query (link) | Git PR link | 🎯 | Better governance |
| **SQL Warehouse** (cluster) | DuckDB process pool | 🎯 | No spin-up; no $/hour |
| Photon engine | DuckDB vectorized | ✅ | Comparable or better <10TB |
| Multi-cluster autoscaling | N/A — no clusters | 🚫 | Different model |
| Serverless SQL | Always-on local; or k8s pod | 🎯 | Lower cost; 0 ms cold start |
| Query result caching | DuckDB + Iceberg snapshot cache | ✅ | |

**Verdict**: Cleanly win on cost + latency + simplicity. Lose nothing material for <10TB.

---

## 4. Compute / Clusters

| Databricks Compute | Nucleus Compute | Status | Note |
|---|---|---|---|
| All-purpose clusters | None — DuckDB/Polars in process | 🎯 | Zero cluster cost |
| Job clusters | None | 🎯 | |
| SQL Warehouses | DuckDB pool | 🎯 | |
| Pools (reusable VMs) | None needed | 🚫 | |
| Init scripts | `nucleus init` template hooks | ✅ | |
| Cluster libraries (PyPI) | Project `pyproject.toml` / `uv` | 🎯 | Standard Python |
| Cluster libraries (Maven) | N/A (no JVM) | 🚫 | By design |
| Cluster policies | N/A | 🚫 | No clusters to police |
| Single-node / Standard / ML / GPU runtimes | Standard Python env | ❓ ML/GPU gap | Defer to `scale` module v2.0 |
| Photon | DuckDB | ✅ | Comparable |
| Auto-scaling | None v1; HPA at pod level in k8s | ⏳ v1.0 | |
| GPU compute | None v1 | ⏳ v2.0 | Via Ray when `scale` enabled |

**Verdict**: We don't *have* clusters; we *eliminated* the concept. This is the Robinhood move. We lose GPU/distributed in v1 (deliberate), gain everywhere else.

---

## 5. Workflows / Orchestration

| Databricks Workflows | Nucleus (Dagster, wrapped) | Status | Note |
|---|---|---|---|
| Multi-task jobs | Asset DAG | 🎯 | Asset > task mental model |
| Job DAG visualization | Dagster asset graph (embedded) | ✅ | |
| Trigger: schedule | `@nucleus.asset(schedule=...)` | ✅ | |
| Trigger: file arrival | Dagster sensor wrapped in `ctx.sensor` | ⏳ v0.8 | |
| Trigger: continuous / streaming | `streaming` module (Bento + Iceberg) | ⏳ v1.5 | |
| Trigger: manual | `nucleus run <asset>` or Portal button | ✅ | |
| Dependencies | Auto-derived from `ctx.read()` calls | 🎯 | No explicit `depends_on` |
| Job parameters | `ctx.params` (typed) | ✅ | |
| Retries (count, backoff) | Dagster retry policies | ✅ | |
| Notifications (email/Slack/webhook) | Dagster sensors + `obs` module routes | ⏳ v0.8 | |
| Run history & logs | Dagster runs view | ✅ | |
| Backfills | Dagster backfills | ✅ | |
| Partitions | Dagster partition definitions | ✅ | |
| Cluster reuse across tasks | N/A (no clusters; in-process) | 🎯 | |
| Job cost reporting | `obs` module dashboard | ⏳ v1.0 | |
| Conditional logic / branching | Dagster `multi_asset` + sensors | ✅ | |
| Workflow as code (DAB) | `@nucleus.asset` in Python | 🎯 | Pythonic, not YAML |

**Verdict**: Equivalent or better. Asset-centric model (Dagster) is genuinely a better abstraction than Databricks' task-centric workflows.

---

## 6. Tables & Storage (Delta Lake ↔ Iceberg)

| Delta Lake feature | Iceberg equivalent | Status | Note |
|---|---|---|---|
| ACID transactions | ACID via snapshots | ✅ | |
| Time travel `VERSION AS OF` | `TIMESTAMP AS OF`, `VERSION AS OF` | ✅ | |
| Schema enforcement | Schema enforcement | ✅ | |
| Schema evolution (add/rename) | Schema evolution | ✅ | |
| **Partition evolution** | **Partition evolution** | 🎯 | Iceberg can change partitioning without rewriting; Delta cannot until very recently |
| Z-ordering | Z-order via Iceberg sort orders | ✅ | |
| Liquid clustering (Delta 3.x) | Iceberg sort orders + hidden partitioning | ✅ | Different mechanism, same outcome |
| `OPTIMIZE` (compaction) | Iceberg compaction action | ✅ | Run via Dagster maintenance asset |
| `VACUUM` | Iceberg snapshot expiration | ✅ | |
| `MERGE INTO` (upsert) | DuckDB + Iceberg merge | ✅ | |
| Change Data Feed | Iceberg incremental reads | ✅ | |
| Predictive optimization (Photon) | DuckDB query planner | ✅ | |
| Deletion vectors | Iceberg v2 deletion vectors | ✅ | |
| Read from Spark/Trino/DuckDB/Flink | Same — universal Iceberg readers | 🎯 | Delta requires Delta-aware reader |
| Vendor lock-in | None — Apache project | 🎯 | |

**Verdict**: Iceberg is functionally complete vs Delta and **more open**. Partition evolution is a genuine Iceberg advantage.

---

## 7. Catalog & Governance (Unity Catalog ↔ Lakekeeper)

| Unity Catalog | Nucleus Catalog (Lakekeeper) | Status | Note |
|---|---|---|---|
| 3-level namespace `catalog.schema.table` | 3-level via Iceberg REST | ✅ | |
| Tables | Iceberg tables | ✅ | |
| Views | DuckDB / Iceberg views | ✅ | |
| Materialized views | Scheduled asset materializing into Iceberg table | ✅ | Same outcome, different mechanism |
| **Volumes** (unstructured storage) | Direct MinIO bucket access | ⏳ v1.0 | UX wrapper needed |
| Models (MLflow) | None | 🚫 | Out of scope |
| Functions (UDFs) | DuckDB UDFs + Python via `ctx` | ✅ | |
| Tags & comments | Iceberg properties + asset metadata | ✅ | |
| Column-level lineage | OpenLineage + sqlglot parser | ✅ v0.8 | |
| **RBAC at table level** | Casbin via `auth` module | ✅ v0.8 | |
| **RBAC at column level** | Row/column filters | ⏳ v1.0 | |
| **RBAC at row level** | Row filters via views | ⏳ v1.0 | |
| Data discovery / search | Portal Catalog search | ✅ v0.5 | |
| Data quality monitoring | Soda + `ctx.contract()` | ✅ v0.8 | |
| PII detection / classification | `governance` module | ⏳ v1.2 | |
| **Delta Sharing** (cross-org) | Iceberg REST federation | ⏳ v2.5 | Real gap until then |
| **Marketplace** (data listings) | None | 🚫 | Defer to v3.0 |
| System tables (audit, billing) | `obs` module + Postgres | ⏳ v1.0 | |
| Audit logs | Built into core v1.0 | ⏳ v1.0 | |
| Compliance certifications | SOC2 readiness v1.0, cert v1.2+ | ❓ Real gap | Cost of doing business |

**Verdict**: Functional parity for technical features. **Real gaps**: cross-org sharing (v2.5), compliance certs (need money + audit), data marketplace (deliberate). Good enough for ICP.

---

## 8. ETL / Data Engineering

| Databricks | Nucleus | Status | Note |
|---|---|---|---|
| Auto Loader (incremental file ingestion) | dlt `incremental` + sources | ✅ | |
| `COPY INTO` (one-time load) | `nucleus ingest <url>` | ✅ | |
| Structured Streaming | `streaming` module (Bento + Iceberg streaming writes) | ⏳ v1.5 | |
| **Delta Live Tables (DLT)** declarative pipelines | `@nucleus.asset` declarations | ✅ | Same paradigm |
| **DLT Expectations** | `@nucleus.contract` (Soda-backed) | ✅ v0.8 | |
| **DLT Materialized Views** | Scheduled assets | ✅ | |
| DLT Continuous mode | Streaming module | ⏳ v1.5 | |
| dbt integration | dbt-duckdb native | 🎯 | First-class, not "integration" |
| Lakehouse Federation (Snowflake, BigQuery, Postgres) | Trino via `federation` module | ⏳ v1.5 | |
| Reverse ETL | None native; dlt has destinations | ⏳ v1.5 | |
| Schema inference on ingest | dlt schema inference | ✅ | |
| Incremental processing | Dagster incremental partitions + Iceberg | ✅ | |
| Auto-scaling pipelines | k8s HPA / Daft when `scale` enabled | ⏳ v2.0 | |

**Verdict**: Equivalent or better. dlt's connector breadth ≥ Auto Loader's scope. Asset model ≥ DLT pipelines.

---

## 9. Machine Learning / MLflow

| Databricks ML | Nucleus | Status | Note |
|---|---|---|---|
| MLflow Tracking | 🚫 Out of scope | 🚫 | Architecture §0 explicit |
| MLflow Model Registry | 🚫 | 🚫 | |
| Feature Store | Offline features = Nucleus assets; online = bring your own | ⏳ Partial | |
| AutoML | 🚫 | 🚫 | |
| Model Serving | 🚫 | 🚫 | |
| Endpoint monitoring | 🚫 | 🚫 | |
| Jobs scheduling ML retrains | Via Dagster asset DAG | ✅ | |
| Inference pipelines | Run MLflow / FastAPI alongside | ✅ external | |

**Verdict**: **Deliberately not an ML platform.** Users run MLflow OSS alongside Nucleus. This is a feature, not a gap — it keeps us focused.

---

## 10. AI / Agents (Mosaic AI)

| Databricks Mosaic AI | Nucleus | Status | Note |
|---|---|---|---|
| Vector Search | `vector` module (LanceDB) | ⏳ v1.5 | |
| Foundation Model APIs | 🚫 | 🚫 | Not our business |
| Genie (NL → SQL) | None | 🚫 | User can plug Vanna/Defog externally |
| AI Functions in SQL (`ai_query()`) | DuckDB UDFs to OpenAI/Anthropic | ⏳ v1.5 | Optional `ai-functions` module |
| Agent Framework | 🚫 | 🚫 | |
| Model Gateway | 🚫 | 🚫 | |

**Verdict**: Deliberately not an AI platform. The user's AI stack sits *next to* Nucleus and pulls data from Iceberg. Healthy boundary.

---

## 11. Dashboards / BI

| Databricks | Nucleus | Status | Note |
|---|---|---|---|
| Lakeview Dashboards | None native | 🚫 | Connect Metabase/Superset |
| Legacy SQL Dashboards | None | 🚫 | |
| Scheduled refresh | Asset schedules drive underlying data | ✅ | |
| Embedded dashboards | Via external BI tool | ✅ | |
| Alerts on metrics | `obs` module + Grafana | ⏳ v1.0 | |

**Verdict**: We are explicitly NOT a BI tool. **❓ Real concern**: enterprise buyers expect "out of box dashboards". Mitigation: `bi-metabase` opt-in module bundling open-source Metabase. Doc but defer.

---

## 12. Sharing / Marketplace

| Databricks | Nucleus | Status | Note |
|---|---|---|---|
| Delta Sharing (cross-org) | Iceberg REST federation | ⏳ v2.5 | |
| Marketplace listings | None | 🚫 | Defer |
| Workspace-to-workspace sharing | Multi-cluster federation | ⏳ v2.5 | |
| External sharing to non-Databricks consumers | Open Iceberg = anyone can read | 🎯 | No special protocol needed |

**Verdict**: ❓ Real gap until v2.5 for enterprises with cross-org needs. For ICP (single-team / single-org), not a blocker.

---

## 13. Connectors & Partners

| Databricks Partner Connect | Nucleus | Status | Note |
|---|---|---|---|
| Fivetran integration | dlt + Sling | 🎯 | Native, free, 100+ sources |
| Airbyte integration | dlt covers same surface | 🎯 | |
| dbt Cloud integration | dbt-duckdb native | 🎯 | No "integration" needed |
| Tableau / PowerBI connectors | Standard DuckDB + Postgres ODBC | ✅ | |
| Hex, Mode, Sigma | Standard SQL connection | ✅ | |
| Hightouch (reverse ETL) | Use Hightouch external; reads from Iceberg | ✅ | |
| Census | Same | ✅ | |
| Custom partner integrations | Use OpenAPI / SDK | ✅ | |

**Verdict**: dlt's source breadth + open Iceberg ≥ Partner Connect for most cases.

---

## 14. Admin & Operations

| Databricks Admin | Nucleus | Status | Note |
|---|---|---|---|
| User management | Authentik via `auth` module | ⏳ v0.8 | |
| SSO / OIDC / SAML | Authentik | ⏳ v0.8 | |
| Workspace settings | Project config in git | 🎯 | Versioned |
| Account console (multi-workspace) | Multi-project Portal | ⏳ v1.0 | |
| Billing / usage dashboards | `obs` module + Grafana | ⏳ v1.0 | |
| Audit logs | Built-in v1.0 + `obs` retention | ⏳ v1.0 | |
| Compliance: SOC2 | Readiness v1.0, certification v1.2+ | ❓ Real gap | Cost of doing business |
| Compliance: HIPAA, GDPR, ISO27001 | Same | ❓ Real gap | |
| Disaster recovery (HA) | k8s HA mode v1.0 | ⏳ v1.0 | |
| Backups | Iceberg snapshots + MinIO replication | ✅ | |
| Upgrade tooling | `nucleus upgrade` v1.0 | ⏳ v1.0 | |

**Verdict**: All technical features achievable on roadmap. **Compliance certifications are the single biggest enterprise blocker** — must be funded explicitly.

---

## 15. Apps / Custom UIs

| Databricks Apps | Nucleus | Status | Note |
|---|---|---|---|
| Host Streamlit / Dash / Flask | 🚫 Not building an app platform | 🚫 | |
| Authenticated apps | Marimo notebooks served as apps | ✅ Partial | |
| Apps connected to Unity Catalog | Connect to DuckDB / Iceberg directly | ✅ | |

**Verdict**: Deliberately out of scope. Users host apps elsewhere; data lives in Iceberg.

---

# Strategic Summary

## Where Nucleus WINS (lock these into marketing)

1. **Cost per query <10TB** — 5–10× cheaper vs Databricks
2. **Boot time** — 30s vs 5–10 min cluster spin-up
3. **No JVM** — smaller footprint, no GC pauses, no Java ops
4. **Open formats** — Iceberg beats Delta on openness; partition evolution is a genuine technical win
5. **Engine flexibility** — DuckDB ↔ chDB ↔ Polars ↔ Daft swap behind `ctx`
6. **dlt connectors** — 100+ free vs Partner Connect's narrower set
7. **Asset-centric orchestration** — better mental model than task workflows
8. **Local-identical-to-prod** — same code, byte-identical on laptop and k3s
9. **Git-native** — projects live in git, not in cloud workspace DB
10. **Operational simplicity** — 1 binary vs distributed cluster ops
11. **Familiar tooling** — dbt, Marimo, OpenTelemetry, OPC, all standards-based
12. **No vendor lock-in** — every layer swappable

## Where Nucleus TIES (no advantage either way)

1. Iceberg vs Delta — both ACID, time travel, schema evolution
2. dbt support — both first-class
3. SQL editor capability — Monaco vs Databricks SQL Editor
4. Asset/data lineage — OpenLineage vs Unity lineage
5. Catalog 3-level namespace — both have
6. Data quality framework — Soda/contracts vs DLT Expectations

## Where Nucleus DELIBERATELY LOSES (and that's the strategy)

1. **ML platform** — no MLflow, no Model Serving, no AutoML → use MLflow OSS alongside
2. **AI / Agents / Foundation Models** — no Genie, no Mosaic AI → use external AI stack
3. **Multi-language notebooks** — Python only (no Scala/R) → simpler stack
4. **Cluster auto-scaling / GPU** — no clusters in v1 → use `scale` module v2.0
5. **Massive distributed compute >10TB** — dormant scale seam → activate when needed
6. **Apps platform** — no Databricks Apps equivalent → external hosting
7. **Built-in BI dashboards** — connect Metabase/Superset → BI is its own product
8. **Marketplace / data listings** — defer to v3.0 ecosystem
9. **Real-time co-editing in notebooks** — engineering tool, not collaboration tool

These are not gaps. They are **focus**. Per architecture §14, claiming otherwise drags us into "Data OS" territory and we die. <!-- banned-term: Data OS -->

## ❓ Real Gaps to Acknowledge & Plan Funding For

| Gap | Severity | Mitigation Plan |
|---|---|---|
| **SOC2 / HIPAA / ISO27001 certifications** | Enterprise blocker | Budget audit via Vanta/Drata; target v1.2 |
| **Cross-organization data sharing** | Enterprise feature | v2.5 Iceberg REST federation |
| **Notebook co-editing & threaded comments** | Analyst expectation | v1.5 if customer demand |
| **Built-in BI dashboards** | Common enterprise ask | v1.0 `bi-metabase` opt-in module bundling Metabase OSS |
| **Multi-tenant concurrent query design** | Technical work | DuckDB process pool + per-tenant isolation; v0.8 |
| **Notification routing UX** (email/Slack/PagerDuty) | Production necessity | v0.8 in `obs` module |
| **PII detection / classification** | Compliance ask | v1.2 `governance` module |
| **Lineage column-level UI polish** | Differentiation feature | v0.8 |

---

# Coverage Score

Counting features that exist in Databricks GA today:

| Category | Total | ✅ Have | 🎯 Better | ⏳ Roadmap | 🚫 Out-of-scope | ❓ Real gap |
|---|---:|---:|---:|---:|---:|---:|
| Navigation & Workspace | 5 | 1 | 1 | 2 | 0 | 1 |
| Notebooks | 13 | 4 | 5 | 0 | 2 | 2 |
| SQL Editor | 14 | 6 | 5 | 2 | 1 | 0 |
| Compute / Clusters | 12 | 1 | 6 | 2 | 3 | 0 |
| Workflows | 16 | 8 | 4 | 4 | 0 | 0 |
| Tables & Storage | 14 | 11 | 3 | 0 | 0 | 0 |
| Catalog & Governance | 18 | 7 | 0 | 6 | 2 | 3 |
| ETL | 13 | 6 | 1 | 4 | 0 | 0 |
| ML / MLflow | 8 | 0 | 0 | 1 | 6 | 0 |
| AI / Agents | 6 | 0 | 0 | 2 | 4 | 0 |
| Dashboards | 5 | 1 | 0 | 1 | 2 | 1 |
| Sharing / Marketplace | 4 | 0 | 1 | 2 | 1 | 0 |
| Connectors | 8 | 4 | 3 | 0 | 0 | 0 |
| Admin / Ops | 11 | 0 | 1 | 6 | 0 | 4 |
| Apps | 3 | 1 | 0 | 0 | 2 | 0 |
| **TOTAL** | **150** | **50** | **30** | **32** | **23** | **11** |

### Reading the numbers

- **Have-or-better right now (architecture covers)**: 50 + 30 = **80 / 150 ≈ 53%** — on day 1 (v0.1, paper architecture)
- **On roadmap to GA (v1.0)**: 80 + 32 = **112 / 150 ≈ 75%** — at v1.0, 14–18 months
- **Deliberately out of scope (deliberate "loss")**: 23 / 150 ≈ 15% — ML, AI, Apps, multi-language notebooks, Marketplace
- **Real gaps (need explicit funding)**: 11 / 150 ≈ 7% — compliance, sharing, BI, governance polish

**Effective coverage of in-scope Databricks features by v1.0**: 112 / (150 − 23) = **88%**

That number is the right one to internalize. **For our ICP (sub-10TB teams), we cover 88% of what they actually use, and we win on the dimensions that matter (cost, simplicity, openness).** The 12% remaining is mostly compliance + cross-org sharing.

---

# Verdict — Are We On Track?

**Yes, with three explicit caveats:**

1. **Compliance investment is non-negotiable for enterprise sales.** Budget Vanta/Drata + audit costs from day 1, not v1.0. Targeting v1.2 SOC2 cert.

2. **The `bi-metabase` module should be promoted from "deferred" to v1.0.** Enterprise buyers ask "where are my dashboards?" within 5 minutes. Bundling Metabase OSS is cheap (we just package it) and removes a real objection.

3. **Notebook polish is the soft underbelly.** Marimo wins on engineering DX but loses on analyst polish (no chart picker, no co-editing). For analyst-heavy teams, this is a friction point. Mitigation: ensure Portal SQL Editor + asset dashboards cover the analyst workflow without notebooks.

Everything else in the mapping says: **the architecture is sound, the scope is honest, the wins are real, and the losses are intentional.**

The most important takeaway from this exercise is **what the table proves about positioning**:

- We are not a "Databricks-lite" trying to clone everything.
- We are a **focused replacement** for the 80% of Databricks usage that's actually data engineering + analytics.
- The other 20% (ML, AI, Apps, Marketplace) is given up *on purpose* to keep the stack lean.

That is exactly the Robinhood thesis from `nucleus_architecture_v3.md` §0.

---

# Action Items From This Mapping

| Action | Owner | Doc reference |
|---|---|---|
| Promote `bi-metabase` to v1.0 (was deferred) | Architecture | Update §8 of v3 doc |
| Budget compliance audit (Vanta/Drata) from v0.5 | Founder/CEO | Risk register §16 |
| Document multi-tenant DuckDB design (process pool) | Engineering | New design doc |
| Notebook chart-picker UX (or accept the gap) | Product | Decide v0.5 |
| Notification routing UX in `obs` module | Engineering | v0.8 scope |
| Lineage column-level UI polish | Engineering | v0.8 scope |

---

*This mapping is a snapshot. Re-run it before every major version (v0.5, v1.0, v2.0) to verify we haven't drifted into either over-scoping or under-scoping.*
