# Research Synthesis: Adoption Shortlist — Nucleus v0.2 → v1.0

> **Synthesized**: 2026-05-15  
> **Inputs**: R1–R8 (8 research docs, all verified 2026-05-15 against live official docs)  
> **ADR number range**: ADR-026 → ADR-036 (highest existing = ADR-025, confirmed by `ls docs/decisions/`)  
> **Status**: CAPSTONE — decision-ready for founder ratification  
> **Do NOT modify R1–R8** — they are immutable inputs to this synthesis.

---

## Section 1: Executive Summary

### Thesis

The 8-lane research sweep confirms Nucleus's architectural bets are correct. The top five adoptions for v0.2/v0.3 share a single unifying logic: **reduce the gap between "asset materialised" and "BI-ready, AI-readable, lineage-tracked"** at zero architecture risk and minimal LOC. None of these items require new dependency tiers, none violate Hard Constraints, and none require founder research beyond what is documented below.

**Top 5 (ADOPT NOW — v0.2):**
1. **uv + ruff 0.15 toolchain** — 8s CI vs 2m 15s; zero pyproject changes; OpenAI/Astral backing; single-PR swap.
2. **`nucleus.db` BI handshake** — 50 LOC generates a DuckDB file that connects Superset, Rill, Evidence, Streamlit to every Nucleus asset in under 5 minutes. Directly serves the <30-min beachhead metric.
3. **Iceberg v3 read documentation** — PyIceberg 0.11.1 already reads v3 tables; zero LOC; document in Wave 2 guide so users know upstream Databricks/Trino v3 tables are readable.
4. **Iceberg branch + tag CLI verbs** — `nucleus tag` / `nucleus branch` expose write-audit-publish (WAP) workflows; ~50 LOC wrapping existing `table.manage_snapshots()` API; concrete team-safety payoff.
5. **Rill `<asset>_metrics_view.yaml` auto-generation** — 150 LOC auto-generates a Rill dashboard descriptor from asset schema on every `nucleus run`. BI tool launched in < 5 seconds from materialization.

### Top-15 Prioritisation Table

| Rank | Item | Source | Phase | Effort | Pillar(s) | 8-Gate | ADR# |
|---|---|---|---|---|---|---|---|
| **1** | Adopt uv + ruff 0.15 toolchain | R5 | v0.2 | S | P1, P4 | **PASS** | ADR-027 |
| **2** | `nucleus.db` BI handshake + Rill YAML | R7 | v0.2 | S | P1, P4, P5 | **PASS** | ADR-026 |
| **3** | Iceberg v3 read documentation (0 LOC) | R1, R8 | v0.2 Wave 2 | S | P2, P5 | **PASS** | (docs only) |
| **4** | Iceberg branch + tag CLI verbs | R1 | v0.2 | S | P3, P4 | **PASS** | ADR-028 |
| **5** | Lakekeeper v0.3 catalog swap (confirmed) | R1 | v0.3 | M | P1, P2 | **PASS** | existing ADR |
| **6** | Marquez v0.54 Rust lineage viewer | R4 | v0.3 | S | P2, P3 | **PASS** | ADR-033 |
| **7** | MetricFlow `nucleus_semantic.yaml` | R7, R3 | v0.3 | M | P3, P5 | **COND** | ADR-029 |
| **8** | Iceberg v3 DV writes + migration helper | R1, R8 | v0.3 | M | P2 | **COND** | ADR-031 |
| **9** | Asset description sidecar (AI context doc) | R3 | v0.3 | S | P3 | **COND** | (no ADR) |
| **10** | Arrow Flight SQL Workbench endpoint | R8, R7 | v0.3 | M | P1, P4, P5 | **PASS** | ADR-034 |
| **11** | sqlglot 26→30 upgrade for column lineage | R4 | v0.5 gate | S | P2, P3 | **PASS** | ADR-032 |
| **12** | OpenLineage explicit lineage facets | R4 | v0.5 | S | P2 | **PASS** | (no ADR) |
| **13** | `nucleus-mcp-server` | R3, R4, R7 | v0.5 | M | P3, P4, P5 | **COND** | ADR-030 |
| **14** | `pyiceberg[pyiceberg-core]` Rust extra | R1 | v0.3 | S | P1 | **COND** | (1-line pin, no ADR) |
| **15** | Iceberg WAP workflow docs (fast-forward) | R1 | v0.3 | S | P3, P4 | **PASS** | (docs only) |

Effort: S = < 200 LOC / 1 day. M = 200–600 LOC / 2–5 days. L = 600+ LOC / > 1 week.  
COND = CONDITIONAL PASS: 7/8 questions clear; one Q requires empirical trigger before implementation.

**Top 5 ADOPT NOW items are bolded above (Ranks 1–4 + confirmed Rank 5 Lakekeeper which was already in the architecture).**

---

## Section 2: Deduplication + Cross-Cutting Themes

### 2.1 Semantic Layer Convergence (R3 + R7 + R4)

R7 (§9 MetricFlow) recommends adopting MetricFlow YAML as `nucleus_semantic.yaml`, aligned with dbt Core v1.12 (May 2026). R3 (§3.1) shows that adding a 4 KB semantic document raises text-to-SQL accuracy by +17–23 pp across all frontier models — a larger gain than any model upgrade. R4 (§8.1) notes that structured lineage context grounds AI Copilot responses, preventing hallucinated column names. All three converge on the same prescription: **a per-asset machine-readable semantic descriptor, designed in at v0.1 even if full YAML output ships at v0.3.**

**Decision**: Single ADR-029 (`MetricFlow-compatible nucleus_semantic.yaml`). The `@nucleus.asset` decorator should accept `measures=` / `dimensions=` parameters at v0.1 even if the YAML is only emitted at v0.3. Cube.dev's BSL license blocks direct integration; MetricFlow (Apache-2.0) is the correct reference standard.

### 2.2 `nucleus.db` / DuckDB BI Handshake (R7 + R2)

R7 (§7 "BI-ready asset checklist") proposes emitting a DuckDB `nucleus.db` file as the universal BI handshake — every DuckDB-compatible tool (Rill, Superset, Evidence, Streamlit) connects with one file path. R2 (§6 MotherDuck) independently identifies MotherDuck's dual-execution architecture as the reference Mode 2 yield-to-giants pattern, enabled by exactly this DuckDB attachment mechanism. The two docs converge: `nucleus.db` is both the v0.1 BI handshake AND the foundation for v1.5+ Mode 2 dispatch.

**Decision**: Single ADR-026. Include both the `nucleus.db` generation (50 LOC) and the Rill `<asset>_metrics_view.yaml` auto-generation (150 LOC) since they share the same v0.2 deliverable and are triggered by the same `nucleus run` materialization event. R7's prior ADR suggestion of "ADR-027 for metrics_view.yaml" is folded into ADR-026 to avoid a two-ADR overhead for what is one cohesive BI output bundle.

### 2.3 MCP Server Convergence (R3 + R7 + R4)

R3 (§5) describes `nucleus-mcp-server` (~500 LOC, v0.5): four MCP tools, stdio transport, hard guardrails. R7 (§5) notes BI tools may consume Nucleus assets via MCP. R4 (§8 dbt MCP) shows lineage context prevents LLM hallucinations — exactly the Nucleus Copilot use case. MCP: 97M monthly SDK downloads, 10,000+ servers, all major AI hosts (per R3 §5.1).

**Decision**: Single ADR-030. Gate: verify MCP Python SDK package name on PyPI before writing ADR body (R3 NV #3).

### 2.4 Iceberg v3 Readiness (R1 + R8 + R6)

R1 (§2) confirms PyIceberg 0.11.1 reads v3 tables. R8 (§2 engine table): DuckDB reads+writes DVs (Feb–Mar 2026); Trino GA'd March 2025. R6 (§7): Paimon LSM tables expose via Iceberg REST catalog v3 compatibility — CDC-heavy upstream tables arrive as readable source assets without format translation.

**Decision**: Two-phase ADR-031. Phase 1 (v0.3): document v3 readability + opt-in `format_version=3` flag. Phase 2: unlock DV writes once pyiceberg PR #2822 merge confirmed (NV-2). One-way door — flag BREAKING in ADR.

### 2.5 sqlglot Upgrade for Column Lineage (R4 + R3)

R4 (§3 column-level lineage) explicitly documents: `sqlglot==26.0.0` is 4 major versions behind current `30.7.0`; the `lineage()` API is stable but a major-version upgrade ADR is required before v0.5 column lineage work begins. `UNION BY NAME` is a known failure mode fixed in a recent 30.x version (NV #5 in R4). R3 (§3.2 MetricFlow / semantic layer) also benefits from sqlglot's SQL AST capabilities.

**Decision**: ADR-032 (single component upgrade per AGENTS.md §11.13). Must read sqlglot changelog from 26.x → 30.x for breaking changes before writing the ADR decision. Gate condition: gate-test `UNION BY NAME` (known failure) before enabling column lineage at v0.5.

### 2.6 uv + ruff Toolchain (R5 — standalone)

R5 (§1, §2) is unambiguous: uv 0.11.x replaces pip+venv in one binary (~8s vs ~2m 15s CI install); ruff 0.15.x has a 7-version gap from our current 0.8.4 with a style-guide breaking change at 0.15.0. Both are ADOPT NOW at v0.2, single-component PR each. Pillar 1 (performance) and Pillar 4 (familiar UX). Zero LOC impact on `src/nucleus/`. Migration cost: ~90 min total.

**Decision**: ADR-027. Bundle uv adoption + ruff pin upgrade into one ADR since they come from the same Astral toolchain and ship together as one CI change.

### 2.7 Arrow Flight SQL (R8 + R7)

R8 (§8 Arrow Flight SQL) defines ~500 LOC effort using `pyarrow.FlightServerBase` (already in our `pyarrow==18.1.0` pin) to implement a binary SQL endpoint for Workbench. R7 (§10 workbench sketch) includes "Open in Rill" and broader BI connectivity as v0.3 goals. Per R8 §8.2: no native Python Flight SQL server library — the `FlightServerBase` provides raw Flight RPC but NOT the Flight SQL protocol layer; ~150 LOC of protocol glue required. 80%+ serialization overhead reduction vs JSON REST for bulk result sets.

**Decision**: ADR-034. Additive endpoint only — existing JSON REST stays for CLI and browser clients. 1 new dev dependency: `adbc-driver-flight-sql` (verify NV-7 in R8 before pinning).

### 2.8 Substrait Swap IR (R2 vs R6 — resolved)

R2 (§7.3) says DEFER (Polars "not_planned"; DuckDB community extension only). R6 (§8.3) says ADOPT as DuckDB↔DataFusion swap interface. **Resolution**: R2 is right for full round-trip; R6 is right for the DuckDB↔DataFusion subset. **Decision**: WATCH as potential swap CI contract for DuckDB→DataFusion only; NOT as dispatch wire protocol or Polars swap IR. No ADR required.

### 2.9 MotherDuck vs Modal for Mode 2 (R2 vs R6 — resolved)

R2 (§6.3) positions MotherDuck as the Mode 2 reference (transparent SQL overflow via `ATTACH 'md:'`). R6 (§10) rates Modal P2 (Python-function serverless escape hatch) and MotherDuck P3. **Resolution**: These are complementary sub-modes — MotherDuck = DuckDB-native SQL overflow; Modal = Python function dispatch for RAM-heavy assets. Both watch-listed at v1.5+ gated on Lakekeeper. R6 NV-6: verify MotherDuck DuckLake/Iceberg format compatibility before committing order. ADR-035 (MotherDuck) + ADR-036 (Modal), both P2 watch.

---

## Section 3: Top-15 Items — Deep Dive

### #1 — Adopt uv + ruff 0.15 Toolchain

**What it is**: uv is a single Rust binary replacing pip/pip-tools/venv/pyenv (Astral, OpenAI-acquired March 2026). ruff is the Rust linter/formatter Nucleus already uses — the gap from 0.8.4 to 0.15.12 introduces a "2026 style guide" (per R5 §2).

**Why now**: 8s vs 2m 15s CI install (per R5 BENCHMARKS.md). 126M monthly downloads; 74.2% "admired" (Stack Overflow 2025). Ruff 0.15.0 breaks formatter output; staying on 0.8.4 grows diff with every new file. OpenAI-backed (R5 §1) — low governance risk.

**8-Gate**: All 8 PASS. 0 LOC on `src/nucleus/`. Q7 = measured 2m 15s CI install. Q8 = v0.2 correctly deferred. Effort: ~90 min (pyproject + lockfile + CI action + pre-commit rev bump). **ADR-027.**

### #2 — `nucleus.db` BI Handshake + Rill Metrics View YAML

**What it is**: On `nucleus up`, generate a local `nucleus.db` DuckDB file containing `CREATE OR REPLACE VIEW` statements for each materialised Iceberg asset (per R7 §7). On `nucleus run <asset>`, auto-generate `<asset>_metrics_view.yaml` with measures and dimensions inferred from the schema (per R7 §1 Pattern 2).

**Why now**: Without this, BI tools require custom connector setup. With it, they connect via a single file path — directly serves the <30 min beachhead metric (R7 §1: "under 5 minutes from `nucleus up`"). Superset official DuckDB support with catalog browsing since April 2025 (R7 §5). Rill reads `nucleus.db` directly with zero configuration (R7 §1).

**8-Gate**:
| Q | Result | Justification |
|---|---|---|
| 1. Architectural layer? | ✅ | Experience layer (v4.1 §3) |
| 2. Serves <30 min beachhead? | ✅ | Directly — BI connection in < 5 min |
**8-Gate**: All 8 PASS. Directly serves <30 min beachhead metric. 0 new runtime deps; ~200 LOC total. NV: `ATTACH ... TYPE ICEBERG` syntax (R7 NV-6). **ADR-026.**

### #3 — Iceberg v3 Read Documentation (0 LOC)

**What it is**: PyIceberg 0.11.1 (our current pin) already reads v3 tables transparently (PR #1554, merged Jan 2025). DuckDB reads v3 deletion vectors (Feb 2026, PR #327). No code change needed — this is a documentation + capability announcement.

**Why now**: Upstream sources (Databricks, Trino, Snowflake) produce v3 tables. Without documentation, users silently succeed but don't know they can rely on v3 reads. A Wave 2 doc entry costs nothing.

**8-Gate**: All 8 PASS. Wrap = 0 LOC (already wrapped). Q7 = real adoption driver (96.4% of warehouse workloads are Spark/Databricks; per R1 §2.2 survey). **No ADR required — document in Wave 2 migration guide.**

**Effort**: 0 LOC. 1 documentation bullet in `docs/onboarding/quickstart.md` and asset-materialization guide.

### #4 — Iceberg Branch + Tag CLI Verbs

**What it is**: `nucleus tag create <asset> <name>` and `nucleus branch create <asset> <name>` wrapping `table.manage_snapshots().create_tag()` and `create_branch()` from PyIceberg 0.11.1 (per R1 §3.2).

**Why now**: Teams need pre-commit validation (WAP pattern per R1 §3.3). `nucleus tag` enables compliance archiving (EOW/EOM snapshots, immutable). API confirmed at https://py.iceberg.apache.org/api/#snapshot-management.

**8-Gate**: 7/8 PASS. Q8 ⚠️ (not v0.1 Hello World — correctly v0.2). API confirmed at https://py.iceberg.apache.org/api/#snapshot-management. CRITICAL: `table.append(branch=...)` NOT yet in PyIceberg 0.11.1; document limitation. Effort: S (~50 LOC CLI + ~30 LOC tests). **ADR-028.**

### #5 — Lakekeeper v0.3 Catalog Swap (Confirmed)

**What it is**: Replace the v0.1 filesystem catalog with Lakekeeper 0.12.x (Rust, JVM-free, Cedar RBAC, vended S3 credentials) via a config-only swap in `nucleus.toml` (per R1 §5.3).

**Why now**: Filesystem catalog has no RBAC — unacceptable for multi-engineer teams. Only catalog satisfying Hard Constraint #1 (no JVM). R1 §5.5: "This research confirms the prior plan." 0 proprietary LOC (pure REST config swap).

**8-Gate**: All 8 PASS. **No new ADR required** — already scoped in v4.1 §9.3.

### #6 — Marquez v0.54 Rust Lineage Viewer

**What it is**: ilum-cloud fork of Marquez with a complete Rust backend rewrite (v0.54.0, March 2026). 100% API-compatible with upstream. Default Docker image has zero JVM; upstream project stalled at v0.50.0 (18 months, per R4 §2). Pin: `ilum/marquez:0.54.0`, NOT `marquezproject/marquez:latest`.

**Why now**: Resolves the JVM-sidecar problem. ~1 GB RAM vs DataHub's ~8 GB stack. `lineageStatistics` facet answers "how many assets depend on this?" directly.

**8-Gate**: All 8 PASS. Wrap = Docker config + `HttpTransport` (already used). 0 Nucleus LOC. Verify: Dockerfile-api base image has zero JVM (R4 NV #2). **ADR-033.**

### #7 — MetricFlow `nucleus_semantic.yaml` Contract

**What it is**: Per-asset YAML defining `measures` / `dimensions`, aligned with MetricFlow Apache-2.0 spec (dbt Core v1.12, May 2026). `@nucleus.asset(measures=..., dimensions=...)` kwargs designed at v0.2; YAML emitted on `nucleus run` at v0.3 (per R7 §9 + R3 §3.2).

**Why now**: Cube.dev benchmark (R3 §3.1): 4 KB semantic doc raises text-to-SQL accuracy +17–23 pp across all frontier models — larger than any model upgrade. MetricFlow is Apache-2.0 and the converging open standard as of 2026. Cube.dev's BSL license blocks integration; MetricFlow does not.

**8-Gate**: 7/8 PASS. Q7 ⚠️: add telemetry hook at v0.3 to confirm demand. Effort: M (~200 LOC at v0.3). Gate: dbt Core v1.12 GA (R7 NV-5). **ADR-029.** CONDITIONAL.

### #8 — Iceberg v3 DV Writes + Migration Helper

**What it is**: `nucleus migrate-format --table <asset> --version 3` CLI helper for explicit opt-in v3 migration. Enables 10× faster UPDATE/DELETE/MERGE via deletion vectors (per R8 §2). One-way door — tables cannot downgrade.

**Why now**: DuckDB 1.5.x reads+writes DVs (confirmed). Trino/Databricks GA'd v3. High-churn CDC users hit UPDATE latency walls without DVs.

**8-Gate**: 7/8 PASS. Q2 ⚠️ (less urgent for beachhead). CONDITIONAL: gated on pyiceberg DV write PR #2822 merge (R8 NV-2: verify at `CHANGES.md`). Effort: M (~80 LOC Phase 1 + ~120 LOC Phase 2). **ADR-031.**

### #9 — Asset Description Sidecar (AI Context Document)

**What it is**: `.nucleus/asset_docs/<key>.md` per-asset file with metric definitions, disambiguation rules, join conventions, example Q–SQL pairs. Read by the Copilot on each query. No vector DB needed for < 50 assets (Vanna AI pattern, per R3 §2.1). ~200 LOC.

**Why now**: Cube.dev benchmark (R3 §3.1) is decisive — same +17–23 pp effect as MetricFlow YAML above (the mechanism is the same: injecting structured semantic context). Can be hand-authored initially; auto-generated from MetricFlow YAML at v0.3.

**8-Gate**: 7/8 PASS. Q7 ⚠️: add telemetry to confirm demand before implementation. **No ADR required** — implement as v0.3 Copilot enhancement after usage data confirms demand.

### #10 — Arrow Flight SQL Workbench Endpoint

**What it is**: `pyarrow.FlightServerBase`-powered binary SQL endpoint on port `:8766`. Allows BI tools with ADBC clients (Superset, DBeaver, Tableau) to connect. 80%+ serialisation reduction vs JSON REST for analytics-scale result sets (R8 §8.1). Additive only — JSON REST unchanged.

**Why now**: `pyarrow==18.1.0` is already pinned — no new runtime dep. ADBC client lets any BI tool connect without custom drivers. Effort: M (~500 LOC). Important constraint per R8 §8.2: no native Python Flight SQL server library; ~150 LOC protocol glue required above `FlightServerBase`.

**8-Gate**: All 8 PASS. Verify `adbc-driver-flight-sql` PyPI version + Python 3.11 compatibility (R8 NV-7). Read official spec before writing code. **ADR-034.**

### #11 — sqlglot 26→30 Upgrade for Column Lineage

**What it is**: Upgrade `sqlglot==26.0.0` → `sqlglot==30.7.0`. 4 major versions. Unlocks `sqlglot.lineage()` API for v0.5 column-level lineage. Per AGENTS.md §11.13 this requires a dedicated upgrade ADR with changelog review. Must gate-test `UNION BY NAME` (known failure fixed in 30.x — R4 NV #5).

**Why now**: v0.5 column lineage implementation is blocked on this. The sooner the changelog is read and the ADR written, the sooner v0.5 planning can proceed.

**8-Gate**: All 8 PASS. Effort: S (pin change + changelog review + upgrade smoke tests). **ADR-032.** Must complete BEFORE any v0.5 column lineage code.

### #12 — OpenLineage Explicit Lineage Facets

**What it is**: Emit `LineageRunFacet`, `LineageJobFacet`, `LineageDatasetFacet` alongside existing inputs/outputs using `compatibility=both` mode (per R4 §1.2). Eliminates false-positive lineage edges in multi-engine chains. `openlineage-python==1.47.1` already includes these facets.

**Why now**: v0.1 assets are clean (1 job → 1 output). Explicit facets matter at v0.5+ for cross-engine dispatch. Additive, low effort. Verify: `LineageRunFacet` Python class path in `openlineage-python>=1.47.1` (R4 NV #4). **No ADR required** — add in AMA as part of v0.5 column lineage wave.

### #13 — `nucleus-mcp-server`

**What it is**: ~500 LOC exposing four MCP tools (`list_assets`, `query_asset`, `get_lineage`, `get_runs`) + four read-only resources via stdio transport. Hard guardrails: read-only DuckDB, DDL/DML blocking, 10 tool-call budget per session, audit log (per R3 §5.3 + R3 §7.3).

**Why now**: MCP is the ambient AI protocol in 2026 (97M monthly SDK downloads, all major AI hosts). Nucleus's differentiation vs existing Iceberg MCP servers: surfaces asset graph, contract status, lineage, freshness — not raw SQL. Security guardrails are non-negotiable.

**8-Gate**: 7/8 PASS. Q7 ⚠️: Nucleus-specific MCP demand requires v0.5 usage data. Verify MCP Python SDK package name before ADR body (R3 NV #3). **ADR-030.** CONDITIONAL.

### #14 — `pyiceberg[pyiceberg-core]` Rust Extra

**What it is**: `pip install "pyiceberg[pyiceberg-core]"` to use `iceberg-rust` 0.9.0 Rust core for performance-critical read paths. Transparent acceleration; zero API change.

**Why now**: Defer. 5 GB beachhead tables have not hit the read performance ceiling. Per R1 §7.4, Q7 fails (no measured bottleneck). Add to `FOUNDER_ACTION_QUEUE.md` as a 1-line pin contingent on empirical slow-read reports. **No ADR required.**

### #15 — Iceberg WAP Workflow Docs (Fast-Forward Pattern)

**What it is**: Documentation of the write-audit-publish pattern (R1 §3.3): create branch → write to branch → validate → `fast_forward` main. Available at v0.3 once Lakekeeper provides server-side branch isolation. Note: `table.append(branch=...)` is NOT yet in PyIceberg 0.11.1; branch creation (ADR-028) is ready but branch-targeted writes need tracking at https://github.com/apache/iceberg-python/issues/737.

**8-Gate**: All 8 PASS. **No ADR required — documentation only at v0.3.**

---

## Section 4: REJECTED + DEFER Items

**Vortex (DEFER v1.0+)** — R2 §8 + R8 §4. LFAI incubation; DuckDB extension scope unconfirmed (R8 NV-6). No beachhead random-access bottleneck justifies the 3–5 year maturation wait. Re-evaluate at v1.0 if LFAI graduates Vortex and DuckDB extension reaches read+write maturity.

**Velox (REJECT)** — R2 §3. Execution kernel, not a standalone database. Requires a host query system. PyVelox x86_64 only — incompatible with MacBook beachhead. Fails Q2, Q3, Q5 of 8-gate.

**chDB / ClickHouse-Local (REJECT for `ctx.sql`)** — R2 §4. Wheel 90–150 MB vs DuckDB's 30 MB; no Iceberg extension (R2 NV-3). Beachhead needs file-backed SQL over Iceberg. DEFER to v0.5+ evaluation for in-memory Pandas `ctx.execute_inline()` only.

**GlareDB (REJECT — DEAD)** — R2 §5. Company abandoned project November 2025.

**Ray as embedded engine (REJECT)** — R6 §2.3. Local mode ~200–400 MB idle RAM — violates PoC #4 boot budget. Correct path: Daft→Ray at v0.5+, not Nucleus→Ray direct.

**Coiled / Dask (DEFER indefinitely)** — R6 §4–5. Polars-first stack extracts zero Dask value. 30–90s spinup worse than Modal's <4s. Not a Mode 2 target.

**Mojo (DEFER v1.5+)** — R6 §6. 1.0 beta May 2026, GA "Fall 2026". Not a first-party language for Nucleus; awareness only for downstream Rust kernel evolution.

**Apache Paimon (DEFER — JVM blocker)** — R6 §7 + R8 §7. Requires Flink (JVM — HC#1). No DuckDB native support. Monitor Iceberg compatibility layer (R6 NV-1) for v0.5 CDC-heavy use case.

**Cube.dev (DOCUMENT-ONLY — BSL)** — R3 §3.2. Elastic License 2.0 blocks integration. Emit Cube-compatible YAML as a documentation guide only; do NOT link as runtime dep.

**Atlan (REJECT — NOT OSS)** — R4 §2. Proprietary SaaS, $49,764/yr median contract.

**Iceberg Materialized Views (DEFER until spec ratified)** — R1 §4. Spec PR #11041 unvoted as of April 2026. `@nucleus.asset` + `ctx.sql()` + `overwrite()` already covers 95% of MV semantics.

**Nessie / Gravitino / Unity Catalog OSS (REJECT — JVM)** — R1 §5.2. All require Java 17. HC#1 non-negotiable. Nessie's catalog-level branching is powerful but JVM blocker is permanent for Nucleus v0.x.

**ty (REVISIT after ty 1.0)** — R5 §3. Beta; 10–100× speedup compelling when stable. Stay on `mypy==1.13.0`; revisit at v1.0.

**CrewAI / LangGraph (REJECT — LOC budget)** — R3 §4.1. LangGraph + LangChain = 50K+ LOC transitive — exceeds our entire 30K LOC ceiling. Borrow the "pair programmer propose-approve" pattern; do not depend on either framework.

**Malloy, Observable DuckDB-WASM, DataFusion default** — R7 §9, R7 §8, R2 §2. Monitor only. DataFusion stays as documented swap target (v4.1 §9.3); CI smoke test only, no full adapter. Malloy re-evaluate at stable PyPI + 5K stars. Observable DuckDB-WASM re-evaluate at Workbench v0.3.

---

## Section 5: ADR Bundle Proposed

### ADR Number Assignment (final — non-collision)

Highest existing ADR is **ADR-025** (`docs/decisions/ADR-025-parity-closure-plan-v02-v10.md`). New ADRs start at **ADR-026**.

The research docs contained conflicting suggestions:
- R7 proposed: ADR-026 (nucleus.db), ADR-027 (metrics_view.yaml), ADR-028 (MetricFlow)
- R2 proposed: ADR-026 (DataFusion), ADR-027 (MotherDuck), ADR-028 (Vortex), ADR-029 (Substrait)

**Deduplication decisions:**
- R7's `metrics_view.yaml` (ADR-027 per R7) is **folded into ADR-026** (nucleus.db BI handshake). Both ship in the same `nucleus run` output bundle; a separate ADR adds ceremony without clarity.
- R2's DataFusion CI smoke test does NOT require a standalone ADR (composability obligation already covers it per v4.1 §9.3). Fold into existing composability docs when the adapter is triggered.
- R2's Substrait (ADR-029 per R2) is WATCH-only — not adopted. No ADR required.
- R2's Vortex (ADR-028 per R2) is DEFER v1.0+ — no ADR required yet.
- R2's MotherDuck is split into ADR-035 (Mode 2 reference architecture) at v1.5+.

### Final ADR Table

| ADR# | Title | P0/P1/P2 | Phase | Depends On |
|---|---|---|---|---|
| **ADR-026** | `nucleus.db` BI handshake + Rill metrics_view.yaml | **P0** | v0.2 | none |
| **ADR-027** | Adopt uv + ruff 0.15 toolchain | **P0** | v0.2 | none |
| **ADR-028** | Iceberg branch + tag CLI verbs | P1 | v0.2 | none |
| **ADR-029** | MetricFlow-compatible `nucleus_semantic.yaml` | **P0** | v0.3 | ADR-026, ADR-028 |
| **ADR-030** | `nucleus-mcp-server` | P1 | v0.5 | ADR-029 |
| **ADR-031** | Iceberg v3 format migration helper | P1 | v0.3 | pyiceberg DV write confirmation |
| **ADR-032** | sqlglot 26→30 upgrade for column lineage | P1 | v0.5 gate | none |
| **ADR-033** | Marquez v0.54 Rust as v0.3+ lineage viewer | P1 | v0.3 | none |
| **ADR-034** | Arrow Flight SQL endpoint for Workbench | P2 | v0.3 | ADR-026 |
| **ADR-035** | MotherDuck Mode 2 dispatch reference | P2 | v1.5+ watch | ADR-029, Lakekeeper ADR |
| **ADR-036** | Modal Mode 2 dispatch target | P2 | v1.5+ watch | ADR-035, Lakekeeper ADR |

### ADR Stubs

All 11 stub files are created at `docs/decisions/ADR-026-*.md` through `docs/decisions/ADR-036-*.md` (STATUS=PROPOSED). The decision placeholders require founder ratification. See Section 6 for recommended fire order.

---

## Section 6: Roadmap Impact

### `docs/internal/research/inspiration/README.md`

The ADOPTION_SHORTLIST.md file is added as the first entry in the index with description: *"8-lane synthesis capstone — Top-15 adoption shortlist + 11 ADR stubs, decision-ready for v0.2→v1.0."*

### Proposed Updates to Roadmap Docs (FOUNDER_ACTION_QUEUE items — do NOT edit roadmap files directly)

The following updates are surfaced as `FOUNDER_ACTION_QUEUE.md` items rather than direct edits:

1. **`docs/roadmap/v0.2.md`**: Add entries for ADR-026 (`nucleus.db` BI handshake + Rill YAML) and ADR-027 (uv + ruff toolchain) as P0 items. Add ADR-028 (Iceberg branch+tag) as P1.

2. **`docs/roadmap/v0.3.md`**: Add entries for ADR-029 (MetricFlow semantic YAML), ADR-031 (Iceberg v3 migration), ADR-033 (Marquez v0.54), ADR-034 (Arrow Flight SQL) as the BI + lineage cluster.

3. **`docs/roadmap/v0.5.md`** (if it exists): Add ADR-030 (`nucleus-mcp-server`) and ADR-032 (sqlglot upgrade) as prerequisites for column lineage and MCP server.

4. **`docs/roadmap/v1.5_plus.md`** (if it exists): Add ADR-035 (MotherDuck) and ADR-036 (Modal) as Mode 2 dispatch targets.

### Recommended Fire Order for v0.2 Wave

```
Fire immediately (zero architecture risk):
  → ADR-027 (uv + ruff) — single-PR toolchain swap
  → ADR-026 (nucleus.db + Rill YAML) — 200 LOC, pure additive

Fire after v0.2 toolchain stable:
  → ADR-028 (branch + tag CLI) — 50 LOC, docs note on WAP limitation

Gate v0.3 wave on ADR ratifications:
  → ADR-031 (pending pyiceberg DV write NV-2)
  → ADR-033 (Marquez Rust — verify Dockerfile base image NV from R4)
  → ADR-029 (MetricFlow YAML — after dbt v1.12 GA confirmed R7 NV-5)
  → ADR-034 (Flight SQL — verify adbc-driver-flight-sql R8 NV-7)

Gate v0.5 wave:
  → ADR-032 (sqlglot upgrade — read changelog 26→30 first)
  → ADR-030 (MCP server — verify MCP Python SDK package name R3 NV-3)

Watch-list (no action until trigger fires):
  → ADR-035, ADR-036 (Mode 2 — gate on Lakekeeper + empirical user demand)
```

---

## Section 7: Conflicts Surfaced and Resolved

| Conflict | Documents | Resolution |
|---|---|---|
| MotherDuck vs Modal as Mode 2 P2 | R2 §6.3 (MotherDuck = Mode 2 reference) vs R6 §10 (Modal = P2, MotherDuck = P3) | MotherDuck = DuckDB-native continuous overflow; Modal = Python-function escape hatch. Both v1.5+ watch. ADR-035 + ADR-036. |
| Substrait: swap interface vs WATCH | R2 §7.3 (DEFER — Polars "not_planned") vs R6 §8.3 (ADOPT as DuckDB↔DataFusion swap IR) | R6 is right at the DuckDB↔DataFusion layer; R2 is right about full round-trip. Use as swap interface only, not full dispatch protocol. No ADR needed. |
| `nucleus.db` BI handshake ADR number | R7 proposes ADR-026; R2 proposes ADR-026 for DataFusion | R7's nucleus.db wins ADR-026 (higher beachhead impact). DataFusion composability docs fold into existing swap/ documentation. |
| metrics_view.yaml as standalone ADR vs bundle | R7 proposes separate ADR-027; task description bundles under ADR-026 | Bundled into ADR-026 — same deliverable, same trigger event, same PR. |
| Iceberg v3: "already readable" vs "requires action" | R1 (document only, 0 LOC) vs R8 (plan `nucleus migrate-format` helper) | Both correct at different phases: R1 = v0.2 docs (0 LOC); R8 = v0.3 migration helper (ADR-031). Not a conflict — a sequence. |

---

*Sources: R1=iceberg_catalog_deep_dive.md · R2=modern_query_engines.md · R3=ai_data_tooling_2026.md · R4=observability_lineage_2026.md · R5=modern_python_ecosystem.md · R6=distributed_compute_2026.md · R7=embedded_analytics_bi.md · R8=storage_formats_2026.md. All docs verified 2026-05-15.*
