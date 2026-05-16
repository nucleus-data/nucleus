# Nucleus — Press Kit

*v0.2.0 launch · 2026-05-15 · Apache 2.0*

---

## Boilerplate descriptions

### One line (≤120 chars)

> Nucleus ships data products from a laptop — a local-first Python SDK + CLI for Iceberg-native pipelines, AI-ready by design.

### One paragraph (≤90 words)

> Nucleus is a modern, composable data engineering platform for startup teams (5–20 engineers, 100 GB–5 TB of data). It wraps DuckDB, Polars, Apache Iceberg, and embedded orchestration behind a single Python SDK (`ctx`) and CLI (`nucleus`). No JVM in the default path. Apache 2.0 forever. Local-identical-to-prod by design. Iceberg snapshots stay portable to Databricks, Snowflake, or any Iceberg catalog when teams outgrow a single node. AI Copilot is an optional layer, not the headline.

### One page (~250 words)

> **Nucleus** is a local-first Python SDK + CLI that turns a laptop into a production-shaped data platform. Released as v0.2.0 in May 2026 under Apache 2.0, it is built for the gap that the modern data stack and the cloud lakehouses both leave wide open: the 5–20 engineer startup team that wants Iceberg-native pipelines today, without staffing a platform org and without a $50K-and-up annual cluster contract.
>
> Nucleus owns three things, forever: the **asset graph** (the logical model of data products), the **`ctx` SDK** (the developer contract), and the **unified developer-first experience** (CLI + Workbench + SDK as one product). Everything else is rented from open source: DuckDB and Polars for compute, Apache Iceberg for the table format, embedded orchestration (Dagster wrapped behind `ctx`) for the asset graph, OpenLineage for lineage, OpenTelemetry for observability. Every wrapped dependency exposes a clean swap interface and runs smoke tests in CI; full alternate adapters are built on demand when a trigger event fires.
>
> The headline metric is **30 minutes from `git clone` to a BI-ready Iceberg table** for a five-engineer team on MacBooks. The path to graduation is **zero effort** — Nucleus's Iceberg snapshots are vendor-neutral by construction, so when a team outgrows a single node, they point Databricks, Snowflake, or any Iceberg REST catalog at the same bucket and they are done.
>
> Built by a single founder. Validated against an 11-script governance suite. Apache 2.0. <https://github.com/nucleus-data/nucleus>.

---

## Founder bio template

> **<Founder name>** is the founder and architect of Nucleus, an Apache 2.0 local-first data engineering platform for startup teams. Before Nucleus, <he/she/they> spent <N> years building <relevant prior work — fill in: data platforms / ML infra / etc.> at <company>. <Founder> writes about local-first data architecture and the yield-to-giants strategy at <blog URL>. Reach <him/her/them> at <email> or via GitHub at <https://github.com/<handle>>.

*<Replace bracketed placeholders before publishing.>*

---

## Key stats (verified at v0.2.0 tag)

| Stat | Value | Source |
|---|---|---|
| Proprietary code (LOC under `src/nucleus/`) | **12,840 LOC** | `(Get-ChildItem ... \| Measure-Object -Line)` 2026-05-15; `docs/internal/research/scale_out_audit.md` §1.1 reports 12,944 |
| LOC budget headroom (vs 30K v1.0 ceiling) | **57% remaining** | `scripts/loc_budget.py`; `docs/internal/research/scale_out_audit.md` §1.1 |
| Test files (`tests/test_*.py`) | **66 files** | repo scan 2026-05-15 |
| Tests passing (full suite) | **873+ passed / 0 failed / ≤30 skipped** | `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md` §3.2 |
| Wrapped runtime dependencies (exact-pinned) | **23 mandatory + 2 optional-runtime** | `pyproject.toml`; `CHANGELOG.md` v0.1.0 entry |
| Governance scripts in CI | **11** | `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md` §3.3 |
| ADRs (architecture decision records) ratified | **016 ACCEPTED + 12 PROPOSED at tag time** | `docs/decisions/` |
| CLI commands (v0.2) | **8** (init/up/down/run/ingest/query/chat/version) | `src/nucleus/cli/main.py`; `docs/specs/nucleus_cli_spec.md` |
| Connectors (v0.2) | **7** (Postgres / MySQL / SQLite / Snowflake / S3 / GCS / filesystem) | `src/nucleus/ctx/copy_from_*.py` |
| Workbench routes (v0.3 frontend) | **7 interactive** (Dashboard / Assets / Asset detail / Runs / Run detail / Schedules / Catalog / Query) | `CHANGELOG.md` v0.2.0 entry |
| Public docs pages (MkDocs Material) | **~55** | `docs/site/` |
| License | **Apache 2.0** | `LICENSE` |

### Performance numbers (HONEST — empirical baseline 2026-05-15)

> *We publish empirical numbers, not aspirations. The baseline below was measured on Windows 11, 4 physical cores, 15.7 GB RAM (only 1.0 GB available at run start — host was paging). Beachhead-spec re-measurement is tracked for v0.2.1. Source: `docs/benchmarks/2026-05-15_baseline.md`.*

| Metric | Claim (perf doc) | Empirical | Verdict |
|---|---|---|---|
| `nucleus up` cold boot (PoC #4 measurement) | <10 s | **5.82 s** | PASS |
| `nucleus up` idle RSS (PoC #4 measurement) | <500 MB | **117 MB** | PASS |
| `nucleus --version` cold (B5 baseline) | <500 ms | 2.11 s | FAIL — re-measure on freshly-booted host |
| Materialize 1 GB synthetic / 10M rows wall-clock (B2) | <30 s | 38.77 s | FAIL — within 30% of target |
| Materialize 1 GB synthetic / 10M rows peak RSS (B2) | <3 GB | 1.48 GB | PASS |
| Concurrent-run safety winner/loser split (B4) | exactly 1 winner | **BOTH committed snapshots on Windows** | FAIL — NTFS lock semantics; Linux/WSL passes |
| TPC-H 10 GB suite median across 8 queries (B1) | <3 s | FOUNDER ACTION: remeasure on a clean network; prior run blocked by HTTP 407 proxy auth for DuckDB `tpch` extension install | SKIP-DEPS |
| Postgres ingest 1M rows (B3) | FOUNDER ACTION: set target before v0.2.1 remeasurement | FOUNDER ACTION: remeasure after Docker pull 500 clears | SKIP-DEPS |
| WSL beachhead E2E (8 gates) | 8/8 PASS, <30 min | **8/8 PASS, ~7 min boot** | PASS |
| Real Iceberg snapshot ID written by E2E | non-zero | `7070059669214185406` (v0.1) | PASS |

---

## Logo & screenshot assets

| Asset | Path | Purpose |
|---|---|---|
| Primary logo (raster) | `assets/logo.png` | High-res launch artwork |
| Brand directory | `assets/brand/` | Variants, monochrome, lockups |
| Compositional logo (alt) | `assets/nucleus-logo-option-2-composable.png` | Alternative for "composable" framing |
| README hero logo | `assets/brand/nucleus-logo.png` | Used in README.md |

> *WORKSTREAM C ACTION: capture Workbench Editorial Hero screenshots from running Workbench v0.3 against `examples/01-ecommerce-elt/` after `nucleus workbench up`. Suggested captures: (1) hero dashboard with stat chips, (2) Assets page with detail slide-over open, (3) Runs page with live SSE log streaming, (4) command palette open. Save to `assets/screenshots/v0.2/` before press distribution.*

> *WORKSTREAM C ACTION: record CLI animated demo (asciinema or terminalizer) for `nucleus init demo && cd demo && nucleus up && nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders && nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"`. Save to `assets/demos/v0.2/`.*

---

## Quotable claims (sanity-checked)

> "Nucleus ships data products from a laptop — local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks, AI-ready by design, graduating cleanly to any Iceberg catalog when users outgrow their laptop." — *official tagline per ADR-002 §8.1; final tagline locks after PoC #5 external-tester field test.*

> "We do not build a database, a SQL engine, a DataFrame engine, an orchestrator, a Spark replacement, or a Databricks competitor. We integrate best-of-breed open source into one coherent product." — *`docs/specs/nucleus_architecture_v4.1.md` TL;DR.*

> "30 minutes from `git clone` to a BI-ready Iceberg table for a five-engineer startup team." — *v4.1 §1.5 beachhead metric; validated 2026-05-14 via WSL E2E.*

> "Composability by Constitution. Every Tier 1/2 dependency has a clean swap interface and smoke tests in CI; the full adapter is built on demand when a trigger event fires." — *v4.1 §9; ADR-002.*

> "We do not compete with Databricks or Snowflake. We integrate. Mode 1 — Iceberg portability. Mode 2 — hybrid dispatch. Mode 3 — federation." — *v4.1 §10.*

---

## Forbidden framings (do NOT use in coverage)

For accuracy, please avoid these characterizations of Nucleus. They are explicitly disclaimed in `AGENTS.md` §8 and `docs/specs/nucleus_architecture_v4.1.md` §1.6:

- ❌ "Data OS" / "universal compute platform" <!-- banned-term: Data OS --> <!-- banned-term: universal compute -->
- ❌ "Spark killer" / "Databricks killer / replacement" / "better Databricks" <!-- banned-term: Spark killer --> <!-- banned-term: Databricks killer --> <!-- banned-term: better Databricks -->
- ❌ "AI-first" / "AI-native data platform" — Nucleus is **AI-ready**, not "AI-native" <!-- banned-term: AI-first --> <!-- banned-term: AI-native -->
- ❌ "Agent data substrate" / "Workbench for agents"
- ❌ "Iceberg company" — Iceberg is our substrate, not our category
- ❌ "ML platform" / "feature store" / "model registry" — Nucleus does not host or train models
- ❌ "Distributed-first" — Nucleus yields to giants for distributed
- ❌ "Plugin marketplace" — out of scope for v1
- ❌ Vocabulary: "table" (as primitive), "job", "task", "metastore" — use **asset**, **materialization**, **catalog** <!-- banned-term: metastore -->

Correct framing in one line: *"a modern, composable data engineering platform that solves persistent pains, AI-assisted by design, graduates cleanly to giants."*

---

## Architecture one-liner

> Five layers, bottom-up: **Physics** (Apache Arrow, Iceberg, Parquet, Lance, S3, OpenLineage, OpenTelemetry — immortal) → **Engines** (DuckDB, Polars; Daft optional v0.5+) → **Coordination** (asset graph, AMA, error translation, contracts, lineage, run ledger, scheduling daemon) → **Intelligence** (Copilot v0.2 chat; lineage-aware v0.5; agent runtime v0.5) → **Experience** (`ctx` SDK, CLI, Workbench, Marimo).

Full diagram + sequence: `docs/architecture/`. Source of truth: `docs/specs/nucleus_architecture_v4.1.md`.

---

## Roadmap snapshot

| Version | Window | Headline | Status |
|---|---|---|---|
| **v0.1** Tier 1 Foundation | Mo 2–8 (released 2026-05-14, beta) | CLI E2E: `git clone → first BI-ready Iceberg table <30 min` | RELEASED |
| **v0.2** Tier 2 Workbench | Mo 8–14 (**RELEASED 2026-05-15**) | Workbench + 4 new connectors + scheduling daemon + run ledger + AI Copilot v0.2 | **CURRENT** |
| **v0.3** Tier 3 Connectors | Mo 14–20 | Lakekeeper / Polaris co-default + dlt + dbt-duckdb adapter + Marimo + schema-aware Copilot | NEXT |
| **v0.5** Tier 4 Intelligence | Mo 20–28 | Lineage-aware Copilot, `ctx.agent` runtime, `nucleus-mcp-server`, Lance + multimodal | PLANNED |
| **v1.0 GA** | Mo 28–36 (best-case, contingent on Mo 24 gate) | Public stable SDK, OIDC enterprise, Cloud offering | PLANNED |

Mo 24 decision gate (per ADR-002 §8.3): founder commits to (a) raise, (b) hand off, or (c) cap as indie.

---

## Press contacts

| Channel | Contact |
|---|---|
| Press inquiries | FOUNDER ACTION: add founder email before distributing externally |
| GitHub | <https://github.com/nucleus-data/nucleus> |
| Issues / bug reports | <https://github.com/nucleus-data/nucleus/issues> |
| Security disclosure | per `SECURITY.md` (90-day responsible disclosure) |
| Discussions | <https://github.com/nucleus-data/nucleus/discussions> |
| Twitter/X | FOUNDER ACTION: add founder handle before distributing externally |
| LinkedIn | FOUNDER ACTION: add founder profile URL before distributing externally |
| Hacker News thread | FOUNDER ACTION: paste Show HN URL after submission |

---

## Compliance & licensing notes

- **Apache 2.0 forever** — no BSL/SSPL pivot. License pivot is explicitly forbidden by `AGENTS.md` Hard Constraint #11 trajectory.
- **No telemetry by default.** AI Copilot is opt-in (`copilot.opt_in` consent) and never sends data without explicit user consent.
- **No identity stored by Nucleus.** All authentication delegates to OIDC providers (Authentik / Keycloak / Okta / Azure AD) per Hard Constraint #6 and v4.1 §15.1.
- **Dependencies audited for license compatibility.** `scripts/check_licenses.py` enforces only permissive (Apache 2.0 / MIT / BSD / MPL-2.0 / LGPLv3 with documented Tier 2 exception) dependencies in CI.
- **No certifications claimed.** SOC 2, GDPR, HIPAA, CCPA postures are *design targets* per v4.1 §15.5 — Nucleus is OSS and does not claim certification until audited.

---

## Acknowledgments

Nucleus wraps — it does not replace — these projects. If we ship something useful, it is because these foundations exist:

- [Apache Arrow](https://arrow.apache.org/), [Apache Iceberg](https://iceberg.apache.org/) / [PyIceberg](https://py.iceberg.apache.org/), [Apache Parquet](https://parquet.apache.org/)
- [DuckDB](https://duckdb.org/), [Polars](https://pola.rs/)
- [Dagster](https://dagster.io/), [dlt](https://dlthub.com/), [Marimo](https://marimo.io/) (v0.3+)
- [OpenLineage](https://openlineage.io/), [OpenTelemetry](https://opentelemetry.io/)
- [LiteLLM](https://docs.litellm.ai/) (Copilot routing)
- [SeaweedFS](https://github.com/seaweedfs/seaweedfs) (default object store), [Caddy](https://caddyserver.com/) (production reverse proxy reference)

Please support them.

---

*Last updated 2026-05-15. Source of truth for stats: `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md` + `docs/benchmarks/2026-05-15_baseline.md` + repo scans 2026-05-15.*
