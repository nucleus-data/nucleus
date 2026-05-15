# Nucleus vs Databricks vs Snowflake — When to Use Which

*Honest comparison. v0.2.0 launch. 2026-05-15.*

> **Bottom line up front.** Nucleus is a **local-first SDK + CLI for 5–20 engineer teams shipping greenfield Iceberg pipelines on 100 GB–5 TB of data**. Databricks and Snowflake are **multi-team hyperscale lakehouse platforms** that excel at the workloads Nucleus is not built for — multi-thousand-engineer collaboration, 100 TB+ warehouses, mature lineage UI, ML platform integration, regulated-industry compliance certifications. **We yield to giants by design.** The architecturally-correct path when you outgrow Nucleus is graduation via Iceberg portability — not "find a way to make Nucleus do what Databricks does."
>
> If you are a startup data team building from scratch and the existing menu (Fivetran + dbt + Airflow + warehouse + catalog + BI = 6 tools) feels like overkill before any value flows, Nucleus may be the lighter on-ramp. If you have a 100-engineer central platform team and a 50 TB warehouse, Databricks or Snowflake is the right answer and Nucleus is the wrong tool.

---

## Capability comparison table

> Sources: `nucleus_architecture_v4.1.md`, `docs/research/scale_out_audit.md`, public Databricks docs (<https://docs.databricks.com/>), Snowflake docs (<https://docs.snowflake.com/>). Last verified 2026-05-15.

| Capability | Nucleus v0.2 | Databricks | Snowflake |
|---|---|---|---|
| **License (core)** | Apache 2.0 forever | Proprietary (Databricks Free Edition + open Spark/Delta upstream) | Proprietary |
| **Deployment** | `pip install nucleus` on a laptop | Managed cloud (AWS/Azure/GCP); Free Edition for individuals | Managed cloud (AWS/Azure/GCP) |
| **Cold start** | `nucleus up` ~6 s (PoC #4) | Cluster boot ~minutes (depends on tier; serverless faster) | Warehouse resume seconds-to-minutes |
| **Idle cost** | $0 (your laptop) | Per-cluster idle costs unless serverless / auto-suspend | Auto-suspend reduces idle; storage + compute billed |
| **Min annual contract** | $0 (OSS) | Free Edition $0; production starts low-thousands | Standard tier from low-thousands |
| **Primary table format** | Apache Iceberg (`pyiceberg`) | Delta Lake (native); Iceberg-compat (`UniForm`) | Snowflake native; Iceberg tables (read+write GA 2024) |
| **Compute engine** | DuckDB (default) + Polars (default); DataFusion swap interface | Apache Spark (Photon-accelerated); SQL warehouse | Snowflake's proprietary engine; Snowpark for Python |
| **JVM in default path** | NO (Hard Constraint #1) | YES (Spark) | NO (engine is C++) |
| **SQL templating** | Native `ctx.sql` + Jinja `{{ ref() }}` (~180 LOC, hard 2,500 LOC ceiling per v4.1 §5.6.0) | dbt-databricks adapter; LakeFlow Pipelines | dbt-snowflake adapter; Snowpark; Streams + Tasks |
| **Asset graph / orchestration** | `@nucleus.asset`; embedded orchestration (Dagster wrapped, hidden); active scheduling daemon | LakeFlow Jobs (formerly Workflows); Delta Live Tables; SDP | Tasks + Streams; Snowpark Container Services |
| **Connectors** | 7 in v0.2 (Postgres / MySQL / SQLite / Snowflake / S3 / GCS / filesystem); dlt 100+ in v0.3 | LakeFlow Connect; Partner Connect; Auto Loader; ~50+ native | Snowpark Connect; Snowflake-managed connectors |
| **Schema contracts / quality** | `@nucleus.check` decorator (v0.1); freshness/SLA in v0.5+ | Delta constraints; Lakehouse Monitoring; Unity Catalog tags | Snowflake `CONSTRAINT` (informational); Snowflake DQM |
| **Lineage** | Asset-level via OpenLineage (v0.1); column-level for SQL v0.5+ | Unity Catalog column-level lineage UI | Snowflake Object Tagging + GET_LINEAGE; Horizon |
| **Web IDE / Notebook** | Workbench v0.3 (Editorial Hero, 7 routes, ⌘K palette) | Databricks notebooks (mature); Genie / SQL Editor; Workspace | Snowflake Worksheets; Notebooks (DataChat); Streamlit |
| **AI Copilot** | v0.2 single-turn chat (BYO key, litellm); lineage-aware v0.5+ | Databricks Assistant + Genie (rich, Foundation Models) | Snowflake Cortex AI / Cortex Analyst |
| **ML platform** | NO (explicit non-goal — `AGENTS.md` §3 #7) | MLflow native; Vector Search; Model Serving; Mosaic AI | Snowpark ML; Cortex AI; ML Functions |
| **Vector search** | NO in v0.2; Lance/LanceDB optional v0.5+ | Vector Search (DBSQL native) | Cortex Search Service |
| **Catalog** | Filesystem (v0.1 default); Lakekeeper / Polaris in v0.3+ (per ADR-004) | Unity Catalog (Iceberg-compat read; native catalog) | Polaris (Iceberg REST catalog, GA); Snowflake Horizon |
| **Multi-tenant** | Single-user local in v0.1/v0.2; managed Cloud tier v1.0+ | YES (workspace + Unity Catalog) | YES (account model) |
| **Auth model** | OIDC delegation only (Hard Constraint #6); no auth in v0.2 single-user | SSO/SAML/SCIM/OIDC; Unity Catalog ACLs | SSO/SAML/SCIM/OAuth; Snowflake roles + RBAC |
| **Compliance certifications** | NONE claimed (OSS; design targets per v4.1 §15.5) | SOC 2 Type II / ISO 27001 / HIPAA / PCI / FedRAMP / etc. | SOC 2 Type II / ISO 27001 / HIPAA / PCI / FedRAMP / etc. |
| **Distributed compute** | NO (yield to giants via Mode 1/2/3) | YES (Spark cluster scale-out) | YES (multi-cluster warehouse) |
| **Single-node target envelope** | 100 GB–5 TB (per v4.1 §1.5 beachhead) | Any (designed for distributed) | Any (designed for distributed) |
| **Primary user persona** | 5–20 engineer startup data team | Multi-team enterprise + ML practitioners | Enterprise SQL + analytics teams; mixed |
| **Pricing transparency** | Free OSS forever; Cloud tier ~$20/seat/mo target | DBU-based + storage; published list price | Credit-based + storage; published list price |
| **Vendor lock-in risk** | Minimal (Apache 2.0 + Iceberg portability) | Low (Delta open spec; Iceberg UniForm; Spark portable) | Medium (proprietary engine; Iceberg tables mitigate) |
| **Time to first query** (laptop / fresh start) | <30 min for 5-engineer team (`git clone` → BI-ready Iceberg table) | Cluster provision + workspace setup | Account provision + warehouse + role setup |
| **Production maturity** | **Beta** | High (years of production mileage) | High (years of production mileage) |

---

## When to use which (500 words)

**Use Nucleus when** you are a **5–20 engineer team building greenfield analytics on 100 GB–5 TB of data**, you want **local-identical-to-prod** workflows so a junior engineer's MacBook can reproduce a production pipeline byte-for-byte, you don't want to staff a platform engineer to wire 6+ tools together, you care about **vendor neutrality** (Apache 2.0 + Iceberg portability mean your bytes are yours), and you want a **30-minute on-ramp** from `git clone` to a BI-ready Iceberg table. Nucleus is the right call when the alternative — a year-one cluster contract starting at five figures plus a six-week ramp before any value flows — does not match your runway or your team size. Per `nucleus_architecture_v4.1.md` §1.5 this is the **explicit beachhead persona**; everything else (solo consultants, enterprise domain teams, hyperscale) is incidentally served at best until v1.5+.

**Use Databricks when** you have a **multi-team enterprise scale workload** (10+ teams, 10 TB+ warehouse, multi-thousand-engineer org), you want a **mature ML platform** (MLflow, Vector Search, Mosaic AI, Model Serving) integrated with your data layer, you need **column-level lineage + governance UI** at production polish (Unity Catalog), you have **regulated-industry compliance** requirements (SOC 2 Type II, HIPAA, FedRAMP) and need vendor accountability for the certs, you want **distributed Spark** for large-scale ETL or model training, or you have **existing investment in the Databricks ecosystem** (notebooks, jobs, partner integrations). Databricks is excellent at exactly the workloads Nucleus is explicitly not designed for — and the Databricks Free Edition is a great way to evaluate without committing to spend.

**Use Snowflake when** you have a **SQL-centric analytics workload** (BI, dashboarding, ad-hoc query) at multi-team scale, you want **predictable consumption pricing** with separable compute and storage, you value **operational simplicity** ("a SQL warehouse, period — no infrastructure to manage"), you need **Snowpark + Cortex AI** for LLM-native data workflows on the same engine that holds your data, you're building **data-sharing relationships** with vendors/customers (Snowflake's data marketplace and clean-room features are best-in-class), or you have **regulated-industry compliance** requirements with Snowflake-side accountability. Snowflake's Iceberg tables (GA 2024) make graduation from Nucleus → Snowflake especially clean.

**Use all three together when** you have grown past the beachhead envelope but want to keep Nucleus as the **local development environment** that produces Iceberg snapshots your Databricks or Snowflake team consumes. Mode 1 graduation is zero effort because the bytes are already in the right format. This is the architecturally-intended end state for a team that started small with Nucleus and grew into one of the giants — your Iceberg lake stays portable, and Nucleus stays the local-first SDK that makes a junior engineer's MacBook reproduce production. None of the three competes with the other two for this combined deployment; they complement.

---

## "Yield to giants" — what we mean (and what we explicitly don't)

Per `nucleus_architecture_v4.1.md` §10:

- **Mode 1 — Graduation (today, zero effort).** Your Nucleus-managed Iceberg snapshots are vendor-neutral by definition. Point Databricks (Iceberg-compat via UniForm or native Iceberg tables), Snowflake (Iceberg tables GA 2024), or any Iceberg REST catalog (Polaris, Lakekeeper, Unity, R2) at the same S3 bucket and you are reading the same data. **No re-migration. No format translation.** This is the felt moat against vendor lock-in.
- **Mode 2 — Hybrid compute (v1.5+).** Annotate an asset with `compute="databricks"` or `compute="snowflake"` and Nucleus orchestrates the asset graph while the giant executes the heavy SQL. The result is committed back to Iceberg. The 30-min onboarding ergonomics stay; the 100 TB heavy lifting yields.
- **Mode 3 — Federation (v2.0+).** Each domain runs its own Nucleus; cross-domain queries via Trino, Databricks, or Snowflake against a federated Iceberg catalog. Data Mesh full.

What we explicitly do NOT mean by "yield to giants":

- We do NOT compete with Databricks or Snowflake on multi-team scale, ML platform, lineage UI polish, or compliance certifications. Those are their wins by design.
- We do NOT plan to "extend Nucleus until it can do what Databricks does." Per the scale-out audit (`docs/research/scale_out_audit.md`), every candidate Rust rewrite to push Nucleus into multi-team distributed-compute territory was rejected on the 8-question gate — the right answer at that scale is yield, not engine swap.
- We do NOT bash competitors. Databricks and Snowflake are excellent products, built by excellent teams, solving real problems for the personas they serve. Different personas; different right answers.

---

## Honest acknowledgments of the giants' strengths

| Capability | Where Databricks / Snowflake outshines Nucleus today |
|---|---|
| **Multi-team scale** | Both have years of production mileage with thousands of concurrent users; Nucleus targets single-server 50+ users in v0.2. |
| **Mature lineage UI** | Unity Catalog (Databricks) and Snowflake Horizon both ship rich column-level lineage today. Nucleus is asset-level only in v0.2; column-level v0.5+ for SQL. |
| **ML platform** | Databricks MLflow + Mosaic AI, Snowflake Cortex AI + Snowpark ML — both first-class ML platforms. Nucleus has NO ML platform and never will (explicit non-goal per `AGENTS.md` §3 #7). |
| **Compliance** | Both ship SOC 2 Type II, HIPAA, FedRAMP, PCI-DSS, ISO 27001. Nucleus claims none. |
| **Connector ecosystem** | LakeFlow Connect / Partner Connect / Snowflake Marketplace — hundreds of integrations. Nucleus ships 7 in v0.2; dlt's 100+ arrive in v0.3. |
| **Operational simplicity at scale** | Auto-suspend, auto-scale, multi-cluster warehouses, serverless compute. Nucleus is single-node by design until you yield. |
| **Vendor accountability** | When Databricks/Snowflake breaks, you have a paid support contract. Nucleus is OSS; you have a GitHub issue tracker. |

---

## What Nucleus offers that the giants don't (today)

| Capability | Why Nucleus has it and the giants don't |
|---|---|
| **Local-identical-to-prod** | A laptop can reproduce a production pipeline byte-for-byte. Cluster-based platforms can't fully — there's always a "developer container" gap. |
| **`$0` cost for the entire core platform** | Apache 2.0 forever. No seat licenses, no consumption pricing, no DBUs. Cluster-based platforms charge per compute unit. |
| **30-minute on-ramp** | `git clone` → BI-ready Iceberg table. Databricks Free Edition / Snowflake Trial are minutes-to-hours setup before first query. |
| **No JVM** | Boot in seconds, idle in MB. Spark on Databricks boots in tens of seconds and idles in GB. |
| **Single SDK, single CLI** | One auth model, one error namespace, one asset graph primitive across ingest + transform + serve. Databricks/Snowflake both have rich tool surfaces but more concepts to learn. |
| **AI-ready by design** | Structured `NucleusError` codes with `docs_url`, machine-introspectable `ctx` SDK, asset-DSL designed for LLM comprehension. The giants ship great Copilots but on top of more complex platforms. |

---

## Decision matrix

> Use this when you're sitting in a stack-decision meeting and someone asks "should we evaluate Nucleus?"

```
                               | Nucleus | Databricks | Snowflake
─────────────────────────────────────────────────────────────────
Team size 5–20 engineers       |   ✓     |     -      |     -
Team size 50+ engineers        |   ✗     |     ✓      |     ✓
Greenfield project             |   ✓     |     ✓      |     ✓
Existing dbt/Airflow shop      |   -     |     ✓      |     ✓
100 GB – 5 TB total data       |   ✓     |     ✓      |     ✓
> 5 TB total data              |   ✗     |     ✓      |     ✓
> 100 TB total data            |   ✗     |     ✓      |     ✓
Need ML platform               |   ✗     |     ✓      |     ✓
Need vector search             |   -     |     ✓      |     ✓
Need column-level lineage UI   |   -     |     ✓      |     ✓
Need SOC 2 / HIPAA / FedRAMP   |   ✗     |     ✓      |     ✓
Local-first development        |   ✓     |     -      |     -
Want zero $/yr core            |   ✓     |     -      |     -
Want vendor-neutral byte format|   ✓     |     ✓*     |     ✓**
Want mature web IDE today      |   -     |     ✓      |     ✓
Multi-team concurrent (50+)    |   ✗     |     ✓      |     ✓

* Databricks Iceberg support via UniForm + native Iceberg
** Snowflake Iceberg tables GA 2024
```

Legend: `✓` strong fit · `-` works but not the headline use case · `✗` not designed for; consider another tool

---

## Common questions

**"Can I migrate from Databricks to Nucleus?"**

Today, migration *to* Nucleus from Databricks works if your data is already in Iceberg-compat tables (UniForm) or you can export to Iceberg via `CREATE TABLE ... USING iceberg`. We do not provide a migration tool. Honestly, "from Databricks to Nucleus" is rarely the right direction — Nucleus is the on-ramp, not the destination.

**"Can I migrate from Nucleus to Databricks?"**

Yes, trivially. Mode 1 graduation = point Databricks at your S3 bucket + Iceberg catalog and you're reading the same data. No re-migration. This is by design.

**"Will Nucleus eventually compete with Databricks?"**

No. Per `AGENTS.md` §1.6 and §8, "Databricks competitor" is on the explicit Forbidden Framings list. Nucleus serves the persona Databricks is too heavy for; we yield to giants when the persona changes. Both products can win.

**"Is Nucleus safe to bet on for a 3-year horizon?"**

Honestly: depends on whether the founder commits to (a) raise, (b) hand off, or (c) accept indie at the Mo 24 decision gate per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.3. **The whole point of the yield-to-giants strategy is that even if Nucleus dies, your Iceberg snapshots stay portable.** Your bet is on Iceberg + open standards, not on Nucleus the company.

---

## See also

- `nucleus_architecture_v4.1.md` §10 — Yield-to-Giants Strategy (full Mode 1/2/3 detail)
- `docs/research/scale_out_audit.md` — Honest assessment of where Nucleus breaks at large-team scale (TL;DR: not a fit by design; graduation is the answer)
- `docs/cookbook/production-deployment.md` — Single-node self-hosted Nucleus production setup
- `docs/release/launch_kit/faq_launch.md` — 25 launch-day FAQs including pricing / scale-out / contributing
- Databricks docs: <https://docs.databricks.com/>
- Snowflake docs: <https://docs.snowflake.com/>
- Apache Iceberg: <https://iceberg.apache.org/>

---

*This document is honest. If you find a claim that's wrong or out of date, file an issue at <https://github.com/mtoanng/nucleus/issues> with the section and the correction. Last verified 2026-05-15.*
