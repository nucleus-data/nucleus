# NEEDS VERIFICATION Index

> **Status**: v2 — refresh after ADR-004, ADR-008, ADR-009, ADR-010, alignment sweeps 1+2, macOS SETUP. **Date**: 2026-05-13 05:10 UTC+7. **Per**: [`AGENTS.md`](../AGENTS.md) §11.12. **Supersedes v1** (Worker FF, 2026-05-13 ~02:50).
> **Method**: `Grep` for `NEEDS VERIFICATION` across `docs/`, `poc/`, `scripts/`, top-level + new compose stubs. **181 raw markers across 59 files** (excluding this index's own self-references); substantive sub-items expand to ~235.
> **Purpose**: founder's one-stop list for "what to verify when Python install lands, Docker is running, or external services are reachable".

---

## How to use

PoC #1 `pytest` cannot confirm 17/17 green until §1 markers fire on a real Python install. §3 setup markers fire when Docker Desktop is up + macOS §M1-§M8 walked. §6-§7 fire when external services land (Lakekeeper/Polaris/Marquez/OIDC at v0.3+). §8 is policy + governance scripts. Mark DONE in-place by editing the source AND removing the row here. **What's new in v2**: §3 +14 (SETUP.md macOS + docker-compose stubs), §4 +1 (v4.1 §5.8), §7 +17 (ADR-004/008/009/010), §8 +6 (governance scripts + nucleus_cli_spec.md §10); see "Resolved since v1" callout between §10 and §11.

---

## Session 2026-05-13 Delta

> **Scope**: 7-file targeted re-scan (prior worker hit resource exhaustion on full corpus). Files: `translator.py` · `ingest.py` · `measure.py` · `v01_skeleton_plan.md` · `ADR-008-storage-substrate-v01.md` · `SETUP.md` · `minio.md`. **Method**: `Grep "NEEDS VERIFICATION" -n` per file. **Additive delta only — not a full v3 refresh**; §11 raw tallies remain v2 values until next full sweep.

### Resolved this session

- `poc/p4_boot_time/measure.py:102` + `poc/p3_ingest/ingest.py:106` + `poc/p4_boot_time/README.md:44` — Worker C audit confirmed `SqlCatalog(type='sql', uri=sqlite:///…, warehouse=file://…)` kwargs against pyiceberg `docs/configuration §570-587`; aligns with v4.1 §5.7 L511 ('filesystem catalog' = SqlCatalog over `file://` warehouse). Source comments still carry literal NV text; 3 §3 PoC-code rows retire on next v3 sweep once comments are amended.
- `poc/p4_boot_time/measure.py` (psutil dep) — transitively present via existing pin chain; **explicit pin recommended** pre PoC #4 promotion (Worker C).
- `ADR-008-storage-substrate-v01.md:32`/`:35`/`:55` + `nucleus_architecture_v4.1.md:47` — **SeaweedFS pinned `chrislusf/seaweedfs:4.23` (sha256:c6d6fb84b…)** per Worker B + maintenance pass; ADR-008 acceptance pending PoC #4 S3-parity probe. Acceptance will collapse §3 setup row · §4 v4.1:47 · §9 SeaweedFS line · §10 SeaweedFS-releases watch in one gate.
- `docker-compose.minio.yml` + `SETUP.md:436` — **MinIO pin sha256:14cea493d… recorded** for `RELEASE.2025-09-07T16-13-09Z` (Worker B + maintenance pass); arm64 manifest availability still gates PoC #5 Apple Silicon dry-run (§9 row unchanged).
- `SETUP.md` §7 — **Bosch corporate-proxy `NO_PROXY` gotcha documented** (maintenance pass); previously unlogged operational friction surface, now captured.
- `poc/p3_ingest/ingest.py` Windows path → file URI — **`f"file://{posix}"` workaround landed** (PoC #3 Windows-fix worker); resolves Windows half of §3 `sequence_ingestion.md` sub-item "filesystem-catalog atomicity on Windows". ADR-001 kill-9 stress harness remains open.

### Newly surfaced this session

- `docs/architecture/v01_skeleton_plan.md:150` (§7 header) + `:158` (inline NV in item 5) — **10 enumerated NV items** at lines 154-163 from skeleton-plan worker: (1) `ctx.materialize` missing from v4.1 §13.2 → **ADR-013 candidate**, (2) asset-name 2-vs-3-level cardinality, (3) `nucleus_project_anatomy.md` v3-era stale, (4) `openlineage-python==1.47.1` unpinned (Hard Constraint #11 step-8 block), (5) `Engine` Protocol shape (`Plan` + `ExecContext` undefined), (6) `ctx.read(snapshot=…)` deferral to v0.3, (7) CLI per-file structure unspec'd, (8) Polaris JVM exclusion re-verify @ v0.3, (9) `docker compose` vs `docker-compose` host probe, (10) `check_api_stability.py` precedence — **script has now landed** per §8, half-resolved.
- `poc/p4_boot_time/measure.py:102` — sole literal NV in `measure.py` this scan. **3 PoC #4 harness gaps observed but not yet labelled in source**: (a) SeaweedFS lacks `/minio/health/live` → 404 → `measure_minio_health()` → `measure_storage_health()` generalization per ADR-008:81, (b) Windows SQLAlchemy temp-dir cleanup race, (c) `file:///` URI construction latent at `measure.py:118`. Append NV comments at next PoC #4 edit so they grep in v3.
- **`ctx.materialize(...)` API gap → ADR-013 candidate** — same surface as v01_skeleton_plan §7 item 1; flagged separately because it widens the public-API contract and warrants its own ADR (not a v0.1-skeleton hot-fix).
- **SeaweedFS internal Iceberg REST Catalog on `:8181`** — parallel-worker investigation in flight at scan time; not yet a source-logged NV. Will surface in v3 if unresolved at next sweep.
- `docs/internal/research/minio.md` lines 25 / 65 / 217 / 237 / §3.2 cosmetic date pairings (maintenance pass) — **NOT new NV markers** (grep confirms minio[BB] = 14, unchanged from §5); informational only.

### Top-5 unblock leverage (subjective, ROI-ordered)

1. `poc/p1_error_translation/translator.py:276` + `:314` — PoC #1 promotion gate (`dagster.DagsterExecutionStepExecutionError` exact class + pyiceberg `__cause__` chain). Closes index §1, gates `AGENTS.md` §11.1 phase transition, prerequisite for any `src/nucleus/` code.
2. `v01_skeleton_plan.md:154` (§7 item 1) — **`ctx.materialize` API gap / ADR-013 candidate**. Unblocks public-API surface for v0.1 skeleton; downstream of every PoC-promotion PR.
3. `ADR-008-storage-substrate-v01.md:32`/`:35`/`:55` — SeaweedFS pin acceptance (tag + sha256 already captured this session); ADR-008 acceptance closes §3 setup row + §4 v4.1:47 + §9 SeaweedFS + §10 SeaweedFS-releases watch in one gate.
4. `v01_skeleton_plan.md:157` (§7 item 4) — **`openlineage-python==1.47.1` pin in `pyproject.toml`**. Hard Constraint #11 explicitly blocks v0.1 skeleton step 8 until pin lands; trivial fix, architecturally load-bearing.
5. `poc/p3_ingest/ingest.py:106` + `poc/p4_boot_time/measure.py:102` + `poc/p4_boot_time/README.md:44` — comment refresh post-Worker-C audit; source-text removal retires 3 §3 PoC-code rows in one PR.

---

## §1. Critical / blocking for PoC #1 promotion

- `poc/p1_error_translation/translator.py` :251 — confirm `dagster.DagsterExecutionStepExecutionError` exact class name + import path in `dagster==1.9.5`
- `poc/p1_error_translation/translator.py` :289 — pyiceberg constructor + `__cause__` chaining (esp. `ValidationError` / `CommitStateUnknownException`) against `0.8.1`
- `poc/p1_error_translation/REVIEW_NOTES.md` :91 — promotion-gate checklist tracking the two markers above

**2 substantive markers + 1 promotion reference.** Resolves on first PoC run. **Unchanged from v1.**

---

## §2. Critical / blocking for PoC #2 promotion

- `poc/p2_ctx_sql/resolver.py` :40 — `NucleusInvalidAssetDefinition` reused for cycles vs new `NucleusAssetGraphError` (founder design)
- `poc/p2_ctx_sql/REVIEW_NOTES.md` :53 — "register asset first" wording — mirrors PoC #1 H4 CLI gap (now resolved by `nucleus_cli_spec.md` landing — see §11)
- `poc/p2_ctx_sql/REVIEW_NOTES.md` :61 — inline quote of the resolver.py:40 marker
- `poc/p2_ctx_sql/PROMOTION_CHECKLIST.md` :41 — promotion gate references "zero open NV markers" before removing PoC copy
- `poc/p2_ctx_sql/PROMOTION_CHECKLIST.md` :49 — `nucleus query` CLI per `nucleus_cli_spec.md` — spec doc **now in repo** per Worker GG (verify subcommand canonical name, not absence)
- `docs/architecture/sequence_query.md` :221 §7 — **5 sub**: DuckDB Iceberg ext on Win · `Table.scan().to_duckdb(name)` churn 0.8.1→0.11.x · `duckdb.ParserException` line/col · `SET timezone='UTC'` connection-init · OL event schema for read-only `ctx.sql` (cross-ref ADR-009 §NV #1)

**5 markers + 5 sequence-doc items.** (v1 had 4 markers; +1 from re-scoping `REVIEW_NOTES.md:61`.)

---

## §3. Critical / blocking for PoC #3, #4, #5 + cross-cutting setup

### PoC code

- `poc/p3_ingest/ingest.py` :106 — `SqlCatalog` accepts `type='sql'` + `uri=sqlite:///...` + `warehouse=file:///...` in 0.8.1
- `poc/p3_ingest/STATUS.md` :23 — re-verify the marker above on Win + macOS + Linux (ADR-001 cross-platform)
- `poc/p3_ingest/STATUS.md` :34 — re-run all 7 tests on 0.11.x in upgrade smoke suite (post-ADR-003)
- `docs/architecture/sequence_ingestion.md` :160 §7 — **5 sub**: SQLAlchemy reflection of PK/NOT NULL on PG/MySQL · `Table.append(arrow_table)` signature drift · OL emitter wire-up · type coverage `JSONB`/`TIMESTAMPTZ`/`NUMERIC(p,s)`/`ARRAY` · filesystem-catalog atomicity on Windows
- `poc/p4_boot_time/measure.py` :102 — v0.1 'filesystem catalog' realised as PyIceberg `SqlCatalog` over `file://` warehouse
- `poc/p4_boot_time/README.md` :44 — `measure_catalog_init` SqlCatalog kwargs verification
- `scripts/beachhead_e2e.py` :17 — `nucleus ingest` + `nucleus query` subcommand canonical names (cross-check against `nucleus_cli_spec.md` §4 now that it landed)

### Stack readiness — NEW in v2 (macOS SETUP worker + JJ-2 alignment sweep #2)

- `SETUP.md` :345/:368 — Homebrew `python@3.11` formula name + pyenv latest 3.11.x patch (macOS §M1)
- `SETUP.md` :419/:423/:427 — Homebrew Cask `docker` vs `docker-desktop` rename · `.dmg` URL stability · Apple Silicon arch for archived MinIO tag + SeaweedFS pin (macOS §M3)
- `SETUP.md` :524 — MinIO Console default-cred preservation `minioadmin/minioadmin` (cross-ref `nucleus_cli_spec.md` §10 NV #7)
- `SETUP.md` :526 — SeaweedFS S3 endpoint final pin + UI URL pending ADR-008 acceptance
- `SETUP.md` :555/:557 — `nucleus up <10s` macOS Docker overhead vs Windows · Apple Silicon image-arch parity per-substrate · Rosetta fallback as PoC #5 stuck-point flag
- `SETUP.md` :559/:561 — `nucleus doctor` availability for PoC #5 dry-run vs v0.3+ ship · Linux dry-run of §M1-§M8 (POSIX subset) pre-PoC-#5 recruitment
- `docker-compose.yml` :8/:15 — pin exact SeaweedFS docker tag per ADR-008 · S3 parity edges (sigv4, path-style, multipart chunk threshold) — PoC #4 measures
- `docker-compose.minio.yml` :19 — arm64 manifest availability for archived MinIO tag (no future builds per `minio.md` §3.2 + `SETUP.md` §M8 #2)

PoC #5 (`poc/p5_beachhead/`): **0 NV markers**. `scripts/benchmark_regression.py`: **0 NV markers**. **7 PoC + 14 setup markers + 5 sequence-doc sub.** (v1: 5; +16.)

---

## §4. Architecture-level uncertainties (`docs/architecture/*.md` + v4.1)

- **C4_component.md (5)**: :35/:164/:184 (×3) `ctx.agent` v0.5+ placeholder · :190-192 §4 5-sub: `ctx.agent` shape · `ctx.read` `as_=` polars vs arrow · `ctx.sql` macro primitives · `ctx.copy_from` `mode="append"` v0.1 vs v0.3 · `ctx.dagster_context` escape-hatch.
- **C4_container.md (2)** ← **dropped from 5 — JJ-2 cleared 3**: :175 §7 header (7-sub remain) · :196 C4 model URL.
- **sequence_asset_materialization.md (2)**: :6/:141 §5 8-sub: `ctx.materialize` spelling · Dagster↔ctx bridging · OL event shapes (now ADR-009) · AMA write path · `ctx.read` identifier translation · contract validation timing · PyIceberg drift · DuckDB connection lifecycle.
- **sequence_swap_drill.md (1)** ← **dropped from 2**: :194 §9 header (7-sub: cadence 28d-vs-90d · `scripts/drift_detection.py` n/a · `src/nucleus/swap/` + `tests/swap_smoke/` n/a · Tier 0 drill · drill-log location · license/health monitor automation · per-component walkthrough).
- **nucleus_architecture_v4.1.md (1)** NEW: :47 — SeaweedFS exact tag pin + S3 parity edges per JJ-2 alignment sweep #2 (§5.8 Object Store amendment cross-refs ADR-008).

`sequence_query.md` / `sequence_ingestion.md`: see §2 / §3. `sequence_error_translation.md` / `C4_context.md`: **0 NV markers**. **11 markers; ~32 sub.** (v1: 16; net −5.)

### §4.5 Patterns + recipes (20 markers; `slack_bot_on_data.md` alone = 11)

- `patterns/secret_management.md` :84 (1; v1: 2 — **resolved 1**) · `schema_evolution.md` (1) · `time_travel.md` (×2) · `compaction.md` :105 (1) — pyiceberg 0.8.1 follow-up + v0.1 manual rewrite NV.
- `recipes/csv_to_iceberg.md` (×2) header normalization · `postgres_to_iceberg.md` (×2) schema-inference manual override.
- `recipes/slack_bot_on_data.md` (×11) — **entire recipe forward-looking (v0.5+)**: every step carries NV (`expose_to_agents`, `agent.serve_slack`, `ctx.llm`, MCP boot).

`patterns/{partitioning,snapshot_retention}.md`: **0 NV markers**.

---

## §5. Research-doc open ends (`docs/internal/research/*.md`)

Full per-item enumeration unchanged from v1 unless flagged. Net §5 total: **76 markers across 14 active research docs** (v1: 83; −7 — see Resolved callout).

- **daft[Q] (7)** · **dbt-duckdb[S] (6)** · **dlt[D] (2)** · **marimo[E] (4)** · **observability_backends[X] (3)** · **polars[r1] (1)** · **soda[T] (11)** · **sqlglot[N] (1)** — unchanged.
- **lakekeeper[F] (4)** unchanged — cross-ref ADR-004 §NV #1 + ADR-010 Authentik smoke test.
- **lance[R] (10)** count unchanged — **phrasing fixed by Worker JJ-1** ("LF aligned" claim in v4.1 §4 corrected).
- **oidc_providers[W] (2)** unchanged — **promoted to ADR-010** (Worker MM); see §7.
- **polaris[H] (6)** unchanged — cross-ref ADR-004 NV #1 + #3.
- **minio[BB] (14)** ← **dropped from 20** (ADR-008 + v4.1 §5.8 absorbed 6). Status header now ALTERNATE. Remaining: :100 health-check 403 vs `{200,429}` · :120 path-style + single-bucket layout · :135 multipart chunk-size · :173 Win+Docker cold-start · :185-191 (×7) pyiceberg/s3fs/boto3/duckdb/polars/MinIO S3 kwargs · :223/:225 (×2) SeaweedFS parity matrix · :248 §12 open-ends header.
- **pyarrow[CC] (5)** ← **dropped from 6**: :49 method signatures 18.1.0 vs 24.0.0 · :55 `ArrowInvalid`/`ArrowIOError` ⊂ `Exception` · :64 zero-copy round-trip · :101 `Schema.equals` · :219 GIL on free-threading 3.13t+ wheels.

**Clean (0 NV)**: `dagster.md` · `duckdb.md` · `ducklake.md` · `openlineage.md` · `opentelemetry.md` · `pyiceberg.md` · `ai_hallucinations.md` · `strategic/*.md`.

---

## §6. Swap-doc uncertainties (`docs/swap/*.md`)

Each swap doc has a `## 7. NEEDS VERIFICATION` section. Header counts as 1 grep hit; substantive sub-items follow.

- **dagster (1 §7)**: mini-scheduler IOManager-equivalent design ★ · Prefect 3.x asset-vs-flow mapping · async asset support · sensor-API stability · 30-day swap claim
- **duckdb (2 §7)**: latest DataFusion Python version · `datafusion-iceberg` crate maturity · `from_arrow` zero-copy · OOM behaviour parity · Windows wheel cadence · DataFusion error class structure ★
- **dlt (1 §7)**: dual-state migration script ★ · Sling Iceberg destination maturity · Singer `target-iceberg` quality · `ctx.copy_from` always-live parity · pyiceberg floor `>=0.9.1`
- **lakekeeper (3 inline Authentik)**: Polaris management API + vended-credentials default · Polaris OIDC matrix + Idempotency-Key · cross-catalog migration script · Authentik against either ★ — cross-ref ADR-004 §NV #2/#3 + ADR-010 Authentik default
- **polars (1 §7)**: DataFusion exception decomposition ★ · `scan_iceberg` Python surface · DataFusion Python wheel cadence · window-function + dtype parity
- **pyiceberg (2 §7)**: canonical iceberg-rust Python entrypoint ★ · REST catalog endpoint coverage · Windows atomic commit (kill-9 harness) · exception class structure · PyArrow envelope + dlt blocker (cross-ref ADR-004 §NV #1)

★ = highest priority per file. **10 markers; ~28 substantive items.** Unchanged from v1.

---

## §7. ADR open questions

### Pre-v1 ADRs (counts unchanged from v1)

- **ADR-005** :50 — `nucleus_cli_spec.md` parenthetical "may not yet exist" — **doc landed by Worker GG** (stale text; CLI surface stability item remains valid).
- **ADR-005** :131-136 §NV — 3 founder sub-questions: `ctx.snapshot` tier mismatch · `ctx.agent.*` signatures · `ctx.copy_from` mode taxonomy.
- **ADR-006** :58 ftn²/³ — H10 `NucleusCommitConflictError` L0/L1 straddle (NE1002 vs split NE2004) · H17 `TimeoutError` routing contested (H14 Option B).
- **ADR-006** :62 §NV header (founder sign-off) · :86 `scripts/generate_error_docs.py` deferred to v0.2 (AST-walk half resolved by `check_error_codes.py` landing per §8).
- **ADR-007** :99 — `scripts/check_licenses.py` "to be authored" — **script landed** per §8; stale text. Tier-change CI semantics against pip metadata edge cases still TBD.

### NEW in v2: ADRs that landed since FF v1

- **ADR-004** (Worker II — catalog v0.1→v0.3, Lakekeeper default + Polaris opt-in) :102 — exact pyiceberg API for catalog-to-catalog metadata migration: no documented `Catalog.migrate(...)` on 0.8.1; verify 0.11.x post-ADR-003; fallback documented (per-table loop over `Catalog.list_namespaces` + `list_tables` + `register_table`)
- **ADR-008** (Worker HH — storage substrate, SeaweedFS default + MinIO alternate post-archival) — **6 markers**: :10/:110 MinIO archival blog + announcement URLs · :32/:35/:55 SeaweedFS exact docker tag pin + image size + compose-stub tag · :81 SeaweedFS S3 parity edges (path-style, sigv4, multipart, `/minio/health/live`-equivalent for PoC #4).
- **ADR-009** (Worker LL — OpenLineage event schema policy) :103 — `run.runId` ↔ Dagster `run_id` mapping: AMA generates UUIDv7 as canonical OL `runId`; Dagster `run_id` → `nucleus_dagster_run` custom run facet. Confirm against Dagster 1.9.5 `DagsterRun.run_id` pre-AMA prototype.
- **ADR-010** (Worker MM — OIDC delegation policy v0.3) — **9 markers**: :39/:117 Okta Workforce pricing (verify quarterly) · :60/:83/:119/:145 PyJWT==2.8.x pin against current PyPI + import-allowlist via `tools/import-policy.toml` · :87/:106 Authentik+Lakekeeper compat smoke test (cross-ref ADR-004 NV #3) — gate ADR-010 acceptance · :152 founder Q — Authentik as v0.3 self-hosted default.

ADR-001, ADR-002, ADR-003: **0 NV markers** (cleanly closed). **25 markers; ~22 substantive items.** (v1: 8; +17 from four new ADRs.)

---

## §8. AGENTS.md / cursor rules / project-level + governance scripts

These are **policy references** or **CI enforcement scripts**, not typical TODOs.

**Policy references (unchanged from v1)**: `AGENTS.md` :238/:479 — Constraint #10 + Cursor-rules workflow · `.cursor/rules/nucleus.mdc` :351 — example pattern · `nucleus_cli_spec.md` :191 §10 — internal NV section header (Worker GG; doc landed).

**Governance scripts — NEW in v2** (external worker; CI enforcement promised in ADRs):

- `scripts/check_licenses.py` :37 (module docstring §NV) · :91 (psycopg LGPL-3.0 baked-in tier per ADR-007) · :163 (pip metadata multi-field probe per ADR-007 §Risks) — implements ADR-007 §Verification step 1; **resolves v1 §7 ADR-007 "to be authored"**.
- `scripts/check_error_codes.py` :32 — implements ADR-006 §Verification step 1 (AST walk on `NucleusError.error_code` regex `^NE[1-5]\d{3}$`); **resolves v1 §7 ADR-006 :85 AST-walk half**.
- `scripts/check_api_stability.py` :29 — implements ADR-005 stability-tier enforcement (Frozen/Beta/Experimental surface diff vs locked manifest).

`nucleus_poc_plan.md`, `README.md`, `nucleus_vs_databricks.md`: **0 NV markers** (positioning docs clean — v4.1 :47 is tracked under §4). **9 markers total** (v1: 3; +6).

---

## §9. Items with explicit resolution path

- Python install: `python --version` post-`SETUP.md` (Win §1-§10 OR macOS §M1-§M8) — Day 1
- PoC #1 translator markers + PoC #3 SqlCatalog kwargs: first `pytest poc/p{1,3}_*/` green — Day 1
- pyiceberg 0.8.1→0.11.x: execute ADR-003 protocol — Post-PoC-#1
- PoC #2 sequence-doc §7 items: graduation to `coordination/sql_resolver.py` — Pre-v0.1
- `dlt[pyiceberg]` compat: auto-fires post-ADR-003 — Mo 14-20
- MinIO 403/health-check + multipart chunk size: PoC #4 measurement / first >5 GB write — Pre-v0.1 / when triggered
- **SeaweedFS exact docker tag + S3 parity edges**: ADR-008 acceptance gate (PoC #4 measures) — Pre-v0.1 ← NEW
- **MinIO arm64 manifest + macOS Homebrew formula/Cask drift**: PoC #5 Apple Silicon dry-run + Day 1 macOS testing — Pre-PoC-#5 ← NEW
- Lakekeeper / Polaris cold-start budgets: PoC #4 measurement — Pre-v0.3
- **Authentik+Lakekeeper smoke test** (ADR-004 NV #3 + ADR-010 acceptance gate): v0.3 implementation PR — Pre-v0.3 ← NEW
- **PyJWT 2.8.x pin against current PyPI** (ADR-010 NV #1): v0.3 implementation PR — Pre-v0.3 ← NEW
- **`run.runId` ↔ Dagster `run_id` mapping** (ADR-009 NV #1): AMA prototype against Dagster 1.9.5 — Pre-v0.1 AMA work ← NEW
- **`pyiceberg.Catalog.migrate(from, to)` API existence on 0.11.x** (ADR-004 NV #1): verify at v0.3 catalog-migration PR — Pre-v0.3 ← NEW
- Catalog atomicity on Windows: ADR-001 kill-9 stress harness — Pre-v0.1
- `ctx.agent.*` signatures lock: v0.5 design ADR — Mo 20-28
- `ctx.copy_from` `mode="append"`: PoC #5 telemetry / founder call — Pre-v0.1
- **`nucleus_cli_spec.md` content verification** (subcommands, exit codes, §10 internal NVs): Worker GG **landed doc**; content audit remaining ← UPDATED
- ADR-006 H10/H17 routing: founder sign-off — Pre-PoC-#1 promotion

---

## §10. Items requiring external action (not founder-side)

- iceberg-rust Python binding maturity (`apache/iceberg-rust`) — watch releases; v0.1 not needed
- `openlineage-dagster` bridge dead per Worker J — AMA emits directly per ADR-009
- OL `AsyncHttpTransport` graduates from `experimental` — async once GA; v0.5 ADR
- `dbt-duckdb materialized='iceberg'` first-class — watch; affects v0.3 optional adapter
- Soda v3 DuckDB connector `duckdb>=1.0,<2.0` (`sodadata/soda-core` v3) — low-priority PR
- pylance 6.0+ docs stabilizing — v0.5+ verification when adapter pin lands
- MinIO OSS CVE feed (`github.com/advisories?query=minio`) — quarterly per Constraint #11; **post-archival, no upstream patches**
- **SeaweedFS releases** (`github.com/seaweedfs/seaweedfs/releases`) — pin candidate post-2025-05-04 per ADR-008 ← NEW
- Marquez large-graph query latency — 10k-event/day fixture pre-v0.5
- DataFusion Python wheel cadence Win/macOS-arm64 — re-verify on PyPI at trigger
- Lakekeeper 0.12.x Authentik docs — issue/docs PR upstream when v0.3 starts (cross-ref ADR-010 gate)

---

## Resolved since v1 (delta callout — additive sub-section between §10 and §11)

Items that became green between FF v1 (~02:50) and KK v2 (05:10).

**File-level cleanups (alignment sweeps)**:

- `C4_container.md`: 5 → 2 (−3) — Worker JJ-2 removed stale Typer assumption (:134), stale "minio.md not-yet-written" note (:150), one §7 cross-ref absorbed by ADR-008.
- `sequence_swap_drill.md`: 2 → 1 (−1) — JJ-2 sweep #2.
- `docs/internal/research/minio.md`: 20 → 14 (−6) — Worker HH's ADR-008 absorbed MinIO archival posture, SeaweedFS-as-default, AGPLv3 Cloud-bundle risk; JJ-2 propagated to v4.1 §5.8. Status header now ALTERNATE.
- `docs/internal/research/pyarrow.md`: 6 → 5 (−1) — JJ-2 cleanup.
- `docs/internal/research/lance.md`: phrasing fixed (count unchanged at 10) — JJ-1 corrected v4.1 §4 "LF aligned" claim.
- `patterns/secret_management.md`: 2 → 1 (−1) — sweep cleanup.

**Cross-reference resolutions (file landings)**:

- `nucleus_cli_spec.md` LANDED (Worker GG) — resolves "doc not in repo" half of v1 §2 :60, §3 `beachhead_e2e.py:17`, §7 ADR-005 :50. Internal §10 NV tracked under §8.
- `scripts/check_licenses.py` LANDED — resolves v1 §7 ADR-007 :99 "to be authored" parenthetical. 3 internal NVs tracked under §8.
- `scripts/check_error_codes.py` LANDED — resolves AST-walk-script half of v1 §7 ADR-006 :85. 1 internal NV under §8.
- `scripts/check_api_stability.py` LANDED — implements ADR-005 stability tier enforcement. 1 internal NV under §8.

**Net file delta**: −12 resolved · +46 added (12 new files contributing markers) · net +34 file-level. Raw-marker delta 155→181 (+26) is the canonical statistic for §11; difference vs file-level +34 reflects v1 over-counting some §7 sub-items as separate markers + several cross-reference quotes counted in both v1 and v2.

---

## §11. Tally + statistics

Raw markers per section: §1 = 2 (+1 ref) · §2 = 5 (+5 seq) · §3 = 7 PoC + 14 setup (+5 seq) · §4 = 11 (+~32 sub) · §4.5 = 20 · §5 = 76 · §6 = 10 (+~28 sub) · §7 = 25 (~22 sub) · §8 = 9. **Total raw: 181 markers across 59 files** (excluding the index's own self-references). **Substantive: ~235 open items.** **PoC #1 + #2 critical-path: 7 markers**. **Files with most items**: `minio.md` (14, was 20) · `SETUP.md` (11, NEW) · `slack_bot_on_data.md` (11) · `soda.md` (11) · `lance.md` (10) · `ADR-010` (9, NEW).

**Delta vs v1 (155 → 181, +26)**: Top 3 gained — `SETUP.md` (+11), `ADR-010` (+9), `ADR-008` (+6). Top 3 lost — `minio.md` (−6), `C4_container.md` (−3), tied at −1 (`pyarrow.md`, `sequence_swap_drill.md`, `secret_management.md`). Files added: 12 (ADR-004/008/009/010, docker-compose.{yml,minio.yml}, check_{licenses,error_codes,api_stability}.py, nucleus_architecture_v4.1.md, nucleus_cli_spec.md, SETUP.md). Files removed: 0.

---

## §12. Hygiene notes

**Workers landed at scan time**: HH (ADR-008) · II (ADR-004) · LL (ADR-009) · MM (ADR-010) · JJ-1 (sweep #1: Lance phrasing + 3 nav READMEs) · JJ-2 (sweep #2: v4.1 §5.7+§5.8 propagation + docker-compose stubs + README quickstart + SETUP.md §M3) · macOS SETUP worker (§M1-§M8) · external governance worker (`check_licenses.py` + `check_error_codes.py` + `check_api_stability.py` + PR template + `ci.yml`) · GG (`nucleus_cli_spec.md`, per `SESSION_STATE_2026-05-13.md`).

**Workers in flight at v2 scan time**: **none**. All flagged workers from FF v1 §12 + SESSION_STATE-2026-05-13 queue have landed.

**Caveats**: Snapshot at 2026-05-13 05:10 UTC+7 — not live. PoC #1 promotion resolves §1. `slack_bot_on_data.md`'s 11 markers are intentional (recipe forward-looking to v0.5+ MCP). ADR-010's 9 markers resolve at v0.3 implementation PR. ADR-008's 6 track SeaweedFS pin acceptance gate. **Stale-text caveats**: ADR-005 :50 and ADR-007 :99 still carry "may not yet exist" / "to be authored" parentheticals factually outdated by Worker GG + governance scripts — next docs-hygiene PR should update the in-source text without removing the marker (the underlying verification item remains valid).

**Counting note**: Raw grep matches (181) ≠ open issues (~235). Many `## §N. NEEDS VERIFICATION` headers count as 1 grep hit but contain 5-9 sub-items (§4 sequence docs, §6 swap docs, §7 ADRs).

**12-section structure**: preserved. "Resolved since v1" is an additive callout between §10 and §11 (canonical §11/§12 numbering unchanged).

---

*Refresh by re-running `Grep` for `NEEDS VERIFICATION` across the corpus. Cite this index when proposing a fix that resolves multiple items in one PR. Trigger conditions for v3: PoC #1 promotion (resolves §1) · v0.1 ship (resolves most of §3 + §4 + §8 governance scripts firing in CI) · ADR-008 acceptance (resolves SeaweedFS pin + parity matrix) · v0.3 ship (resolves ADR-004 + ADR-010 acceptance gates + `nucleus doctor` shipping).*
