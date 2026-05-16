# ADR-012: Runtime Dependency Pin Matrix v0.1

> **Status**: AMENDED — 2026-05-14 — three rows demoted / removed per `docs/internal/research/otel_day1_decision.md` Option α-split; `opentelemetry-sdk` and `sqlglot` shifted to `[project.optional-dependencies]`; `msgspec` removed entirely. Originally ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0).
> **Date**: 2026-05-13 (original) · 2026-05-14 (amendment) · **Decider**: Solo founder
> **Tags**: dependencies, pins, governance, license-tier, constraint-11
> **Related**: ADR-003, ADR-004, ADR-007, ADR-008, ADR-010, ADR-011; [AGENTS.md §3 Constraint #11](../../AGENTS.md); [`pyproject.toml`](../../pyproject.toml); `docs/internal/research/*.md`; `docs/internal/compatibility.md`

## Context

The 2026-05 research wave delivered ~20 component research docs (`dagster`, `pyiceberg`, `duckdb`, `polars`, `pyarrow`, `dlt`, `openlineage`, `opentelemetry`, `sqlglot`, `polaris`, `lakekeeper`, `marimo`, `dbt-duckdb`, `soda`, `minio`, `daft`, `lance`, `oidc_providers`, `observability_backends`, `ducklake`); each surfaced a pin candidate + license + JVM-free check + tier classification. `pyproject.toml` already pins 17 runtime deps but holds no inline tier metadata and no link back to the research doc that justifies each pin.

**AGENTS.md §3 Constraint #11** (*"exact version pins in `pyproject.toml`, one-component-per-PR upgrades, mandatory upgrade smoke tests in CI, documented rollback command, major-version-upgrade ADR requirement"*) treats the pin list as canonical operational state; **ADR-007** classifies each dep into GREEN / YELLOW / RED license tiers. This ADR is the **single consolidation point** (pin × research × license tier × Tier-0/1/2 swap class per Constraint #9). Once accepted, `pyproject.toml`, `scripts/check_pinning.py`, `scripts/check_licenses.py`, and `docs/internal/compatibility.md` all derive from this matrix; drift is a CI-detected bug.

## Decision

> **The v0.1 runtime dependency pin matrix is locked at the state below. Each pin is justified by its research doc; license tier per ADR-007 + Tier-0/1/2 per Constraint #9 are mandatory metadata. ADR-003 (PyIceberg `0.8.1` → `0.11.x`) is the only pre-approved exception; all other upgrades follow Constraint #11 (one-component-per-PR + ADR for any major-version bump).**

### Runtime pin matrix (currently in `pyproject.toml`)

| Component | Pin | License | Tier (ADR-007) | Research | Upgrade ADR | Tier 0/1/2 |
|---|---|---|---|---|---|---|
| python | `>=3.11,<3.13` | PSF | GREEN | n/a | major → ADR | Tier 0 substrate |
| litellm | `litellm==1.83.14` | MIT | GREEN | [`ai_copilot.md`](../research/ai_copilot.md) | follow-on upgrade ADR per Constraint #11; upgrade smoke: `tests/upgrade_smoke/test_litellm.py` | Tier 2 Intelligence wrap (ADR-015, 2026-05-13) |
| duckdb | `duckdb==1.1.3` | MIT | GREEN | [`duckdb.md`](../research/duckdb.md) | none v0.1 | Tier 1 Engine (swap → DataFusion) |
| polars | `polars==1.18.0` | MIT | GREEN | [`polars.md`](../research/polars.md) | none v0.1 | Tier 1 Engine (swap → DataFusion DF) |
| pyarrow | `pyarrow==18.1.0` | Apache-2.0 | GREEN | [`pyarrow.md`](../research/pyarrow.md) | gated by **ADR-003** (`pyiceberg<19.0.0` ceiling) | **Tier 0** immortal |
| pyiceberg | `pyiceberg[sql-sqlite,s3fs,duckdb]==0.11.1` | Apache-2.0 | GREEN | [`pyiceberg.md`](../research/pyiceberg.md) | **[ADR-003](./ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md)** FIRED 2026-05-13 (`0.8.1`→`0.11.1`) — required by `dlt[pyiceberg]>=0.9.1` per ADR-014. Next ADR gates the `0.12.x` move. | Tier 2 (wraps Iceberg Tier 0) |
| s3fs | `s3fs==2026.4.0` (explicit, plus extra via `pyiceberg[s3fs]==0.8.1`) | BSD-3-Clause | GREEN | [`minio.md`](../research/minio.md) §2.2 | Explicit pin landed 2026-05-13 in `pyproject.toml:48`; NV (b) CLEARED | Tier 2 |
| dagster | `dagster==1.9.5` | Apache-2.0 | GREEN | [`dagster.md`](../research/dagster.md) | none; mini-scheduler escalation per v4.1 §6.7 | Tier 2 Coordination (wrap; hidden behind `ctx`) |
| sqlalchemy | `sqlalchemy==2.0.36` | MIT | GREEN | n/a (`ctx.copy_from`) | none | Tier 2 |
| psycopg | `psycopg[binary]==3.2.3` | LGPLv3+ (dynamic-link exempt per ADR-007 §Tier 2) | YELLOW | n/a | NV — confirm psycopg3 license string vs ADR-007 LGPL row | Tier 2 Postgres driver |
| pymysql | `pymysql==1.1.1` | MIT | GREEN | n/a | none | Tier 2 MySQL driver |
| jinja2 | `jinja2==3.1.6` | BSD-3-Clause | GREEN | n/a (`ctx.sql` resolver, PoC #2) | none; **3.1.5 → 3.1.6 2026-05-14** (security patch, no breaking changes — see amendment below) | Tier 2 templating |
| sqlglot | `sqlglot==26.0.0` (Optional `[lineage-advanced]` 2026-05-14) | MIT | GREEN | [`sqlglot.md`](../research/sqlglot.md) | pre-v0.3 ADR `26.0.0` → `26.8.x[c]` for marimo SQL cells (`sqlglot.md` §6); on demotion to extras, the row stays version-locked because `dlt[sql_database,pyiceberg]==1.26.0` pulls `sqlglot` transitively (verified 2026-05-14 via `pip show dlt`) — the `[lineage-advanced]` extra exists for projects that import `sqlglot` directly without depending on dlt | Tier 2 Lineage / SQL parsing — **demoted to `[project.optional-dependencies] lineage-advanced` 2026-05-14** per `docs/internal/research/otel_day1_decision.md` §D2 + ADR-011 amendment 2026-05-14 |
| click | `click==8.1.8` | BSD-3-Clause | GREEN | n/a (explicit pin for resolver determinism) | **future ADR pre-v0.3 dbt-duckdb** → `8.3.0` ([`dbt-duckdb.md`](../research/dbt-duckdb.md) §6) | Tier 2 CLI substrate |
| structlog | `structlog==24.4.0` | Apache-2.0 / MIT dual | GREEN | n/a | none v0.1; OTEL Logs bridge in v0.5 ADR ([`opentelemetry.md`](../research/opentelemetry.md) §5) | Tier 2 logging |
| ~~msgspec~~ | **REMOVED 2026-05-14** | BSD-3-Clause | GREEN | n/a | n/a | **Removed** per `docs/internal/research/otel_day1_decision.md` §D3 + ADR-011 amendment 2026-05-14 — zero callers under `src/`, `tests/`, `poc/`, `scripts/`; planned `NucleusError + configs` use never materialized (Frozen `errors.py` uses pure-Python `class NucleusError(Exception)` per ADR-005). Pure-stdlib substitutes (`json`, `dataclasses`, `tomllib`) suffice. Reversible via one-line pyproject edit if v0.5+ run-event serializer benchmarks warrant it. |
| typer | `typer==0.15.1` | MIT | GREEN | n/a | follows v0.1 CLI | Tier 2 CLI ergonomics |
| rich | `rich==13.9.4` | MIT | GREEN | n/a | none | Tier 2 terminal UI |
| opentelemetry-api | `opentelemetry-api==1.29.0` (core — kept) | Apache-2.0 | GREEN | [`opentelemetry.md`](../research/opentelemetry.md) | future v0.5 ADR (12 minors stale; gated by [ADR-011](./ADR-011-telemetry-and-observability-opt-in-policy.md) opt-in) | **Tier 0** immortal — substrate-by-API-only honored 2026-05-14 per ADR-011 amendment (no `TracerProvider` set → `NonRecordingSpan` no-op per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html) |
| opentelemetry-sdk | `opentelemetry-sdk==1.29.0` (Optional `[observability]` 2026-05-14) | Apache-2.0 | GREEN | same | version-locked to `-api`; only matters once an exporter is configured (v0.5+ per ADR-011 §5) | **Tier 0** immortal — **demoted to `[project.optional-dependencies] observability` 2026-05-14** per `docs/internal/research/otel_day1_decision.md` §D1 + ADR-011 amendment 2026-05-14. Install via `pip install nucleus[observability]`. |
| openlineage-python | `openlineage-python==1.47.1` | Apache-2.0 | GREEN | [`openlineage.md`](../research/openlineage.md) §1 | follows OTEL cadence; no v0.1 ADR | Tier 1 lineage emitter (AMA wires START/COMPLETE/FAIL per v4.1 §6.2 step 4; promoted 2026-05-12) |
| dlt | `dlt[sql_database,pyiceberg]==1.26.0` | Apache-2.0 | GREEN | [`dlt.md`](../research/dlt.md) | follow-on per Constraint #11; upgrade smoke: `tests/upgrade_smoke/test_dlt_upgrade.py` | Tier 2 ingest source (ADR-014, 2026-05-13) — JVM-free via pyiceberg-core Rust |
| fastapi | `fastapi==0.136.1` | MIT | GREEN | n/a (Workbench v0.2 HTTP shell, ADR-016) | follow-on per Constraint #11 | Tier 2 Workbench HTTP framework (ADR-016, 2026-05-13) |
| uvicorn | `uvicorn[standard]==0.46.0` | BSD-3-Clause | GREEN | n/a (ASGI server for FastAPI shell) | version-paired with FastAPI | Tier 2 Workbench ASGI runtime (ADR-016, 2026-05-13) |
| httpx | `httpx==0.28.1` | BSD-3-Clause | GREEN | n/a (Workbench HTTP testing + AI Copilot transport floor for litellm) | follow-on per Constraint #11 | Tier 2 HTTP client (ADR-016 + ADR-015, 2026-05-13) |
| pyyaml | `pyyaml==6.0.3` | MIT | GREEN | n/a (YAML config parsing for `nucleus.yaml` + Copilot opt-in sentinel) | none v0.1 | Tier 2 config parser. **Added 2026-05-14** — drift-detection verifier surfaced as CRITICAL (Constraint #11 violation: directly imported in 3 source modules, previously transitive via dlt/litellm). |
| orjson | `orjson==3.11.9` | (Apache-2.0 OR MIT) AND MPL-2.0 | YELLOW | none v0.1; FastAPI 0.116+ deprecates `default_response_class=ORJSONResponse` → revisit in v0.2.1 | Tier 2 Workbench JSON serializer (ADR-016). **Added 2026-05-14** — second hallucinated-success catch (external-feedback swarm claimed to add but did not; verified by `pip show orjson` returning 3.11.9 installed but `pyproject.toml` had no row). License YELLOW per ADR-007 (MPL-2.0 file-level copyleft compound; OSS OK, Cloud-bundle OK per dynamic-link rule). |
| croniter | `croniter==3.0.4` | MIT | GREEN | next upgrade requires dagster upgrade first (`dagster==1.9.5` requires `croniter<4`); `3.0.4` is latest `<4` release | **Added 2026-05-14** per ADR-017 (schedule exposure façade). Cron parsing + validation + preview for `@nucleus.asset(schedule=...)` + `nucleus schedule` CLI. croniter is a transitive dep via dagster; this row makes governance explicit. Upgrade smoke: add `tests/upgrade_smoke/test_croniter.py` before bumping. Docs: https://pypi.org/project/croniter/ Tier 2 scheduling utility. |
| gcsfs | `gcsfs==2026.5.0` (Optional `[gcs]` extra) | BSD-3-Clause | GREEN | follow-on per Constraint #11; pair with `s3fs==2026.4.0` cadence (both fsspec-family) — same upstream release rhythm; upgrade smoke can ride `tests/upgrade_smoke/test_optional_extras.py` once the extras are exercised | **Added 2026-05-15** per [ADR-020](./ADR-020-object-storage-connectors-via-duckdb.md) (GCS connector via DuckDB `httpfs` + fsspec). Promoted from amendment paragraph to the canonical matrix during the 2026-05-16 close-out builder pass so the cross-check (`scripts/upgrade_smoke.py adr_012_cross_check`) no longer depends on the amendment-paragraph fallback. Docs: https://gcsfs.readthedocs.io/en/latest/ Tier 2 object-storage adapter — JVM-free pure-Python fsspec implementation. |

**Pin count (v0.1 active)**: **24 explicit core pins** (23 runtime + Python floor) + 2 optional-extras pins (`[observability]` + `[lineage-advanced]`). (Added `croniter==3.0.4` 2026-05-14 per ADR-017.)

> **Pin count revised 2026-05-14** per `docs/internal/research/otel_day1_decision.md` Option α-split (founder blanket approval): was 25 explicit core pins; now 23 (−1 `msgspec` removed entirely; −2 `opentelemetry-sdk` + `sqlglot` demoted to extras). Optional extras tally: `[observability]` 1 pin (`opentelemetry-sdk==1.29.0`), `[lineage-advanced]` 1 pin (`sqlglot==26.0.0`). `[dev]` and `[docs]` extras unchanged. The `[lineage-advanced]` group is partially redundant for users who install `dlt` (which transitively requires `sqlglot` per `pip show dlt` 2026-05-14), but the extra still version-locks the pin for projects that import `sqlglot` directly without depending on dlt. Rationale: `docs/internal/research/otel_day1_decision.md` §D4-D5; ADR-011 amendment 2026-05-14.

### v0.1-OUT-OF-SCOPE / future-pin candidates (locked for v0.3+ / v0.5+)

| Component | Pin candidate | License | Tier | When / blocker | Research |
|---|---|---|---|---|---|
| dbt-duckdb | `dbt-duckdb==1.10.1` | Apache-2.0 | GREEN | v0.3+ optional (blocked on click `8.1.8` → `>=8.3.0` ADR) | [`dbt-duckdb.md`](../research/dbt-duckdb.md) §6 |
| dbt-core | `dbt-core==1.11.9` | Apache-2.0 (PyPI metadata blank — NV) | GREEN (verify) | follows dbt-duckdb | [`dbt-duckdb.md`](../research/dbt-duckdb.md) §1 |
| soda-core | `soda-core==3.5.6` (**NEVER v4+**) | Apache-2.0 (v3 terminal) | GREEN v3 only | v0.5+ optional | [`soda.md`](../research/soda.md) + ADR-007 |
| marimo | `marimo==0.23.6` | Apache-2.0 | GREEN | v0.3+ optional notebook wrap | [`marimo.md`](../research/marimo.md) |
| Lakekeeper binary | `lakekeeper==0.12.2` (Rust container; verify Helm chart) | Apache-2.0 | GREEN | v0.3 default catalog per ADR-004 | [`lakekeeper.md`](../research/lakekeeper.md) |
| Polaris binary | `apache/polaris:apache-polaris-1.4.1` | Apache-2.0 | GREEN | v0.3 alternate catalog per ADR-004 | [`polaris.md`](../research/polaris.md) |
| SeaweedFS binary | `chrislusf/seaweedfs:<NV exact tag>` (release 2025-05-04) | Apache-2.0 | GREEN | v0.1 storage **DEFAULT** per ADR-008 | [ADR-008](./ADR-008-storage-substrate-v01.md) + [`minio.md`](../research/minio.md) §10 |
| MinIO binary | `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` | **AGPLv3** | YELLOW | v0.1 storage **ALTERNATE** per ADR-008; upstream archived 2026-04-25 | [`minio.md`](../research/minio.md) + ADR-008 |
| Authentik sidecar | `2026.2` (CalVer) | MIT (core) | GREEN | v0.3 self-hosted default per ADR-010 | [`oidc_providers.md`](../research/oidc_providers.md) §6.1 |
| Keycloak sidecar | `quay.io/keycloak/keycloak:26.6.1` | Apache-2.0 | GREEN | v0.3 self-hosted alternate per ADR-010 | [`oidc_providers.md`](../research/oidc_providers.md) §6.2 |
| pyjwt | `pyjwt==2.8.x` (NV at v0.3 ADR time) | MIT | GREEN | v0.3+ per ADR-010 | [`oidc_providers.md`](../research/oidc_providers.md) §5 |
| daft | provisional `daft==0.7.11` (re-verify at v0.5 ADR; pre-1.0 monthly minors) | Apache-2.0 | GREEN | v0.5+ optional engine | [`daft.md`](../research/daft.md) |
| pylance | `pylance==6.0.0` (PyPI; not VS Code product) | Apache-2.0 | GREEN | v0.5+ multimodal | [`lance.md`](../research/lance.md) |
| lancedb | `lancedb==0.30.2` | Apache-2.0 | GREEN | v0.5+ vector / Copilot retrieval | [`lance.md`](../research/lance.md) |
| Marquez sidecar | `marquezproject/marquez:0.50.0` (last released; 18 mo stalled — Mo 24 swap-to-DataHub trigger logged) | Apache-2.0 | GREEN watch | v0.5+ lineage backend per ADR-011 | [`observability_backends.md`](../research/observability_backends.md) |
| VictoriaMetrics sidecar | `victoriametrics/victoria-metrics:v1.143.0` | Apache-2.0 | GREEN | v0.5+ metrics per ADR-011 | [`observability_backends.md`](../research/observability_backends.md) |
| VictoriaLogs sidecar | `victoriametrics/victoria-logs:v1.50.0` | Apache-2.0 | GREEN | v0.5+ logs per ADR-011 | [`observability_backends.md`](../research/observability_backends.md) |
| Postgres (Dagster + Lakekeeper backing DB) | `15+` | PostgreSQL License | GREEN | external service; v0.3+ | [`dagster.md`](../research/dagster.md) + [`lakekeeper.md`](../research/lakekeeper.md) |
| boto3 | not pinned; `s3fs` covers | Apache-2.0 | GREEN | add only if a feature needs AWS SDK beyond `s3fs` | [`minio.md`](../research/minio.md) §2.2 |
| dagster-postgres | not pinned; transitive when Dagster instance DB ships v0.3 | Apache-2.0 | GREEN | follows dagster | [`dagster.md`](../research/dagster.md) |

**Pin count (future-state)**: **20 future-pin candidates** spanning v0.3 / v0.5+. Adoption gated by their respective ADRs; never bulk-added.

### Forbidden runtime pins (ADR-007 RED tier + AGENTS.md §9)

| Component | Why blocked |
|---|---|
| `soda-core>=4.0` | Elastic License 2.0 (RED); Cloud bundling forbidden; v3 (`==3.5.6`) is terminal. See [`soda.md`](../research/soda.md) §1.2. |
| `openlineage-dagster` (any version) | Package archived Oct 2025; `1.38.0` requires `dagster<=1.6.9` (incompatible with our `dagster==1.9.5`); AMA emits OL events directly. Logged in [`ai_hallucinations.md`](../research/ai_hallucinations.md). |
| `dbt-fusion` (Rust dbt rewrite preview) | Source-available, not OSI-approved → RED until reclassified per ADR-007 §Tier 3. |
| `mongodb`, `redis>=7.4`, `cockroachdb>=2024`, `elasticsearch>=7.11`, `kibana>=7.11` | SSPL / BUSL / ELv2 — all RED; Cloud bundling forbidden. |
| Anything matching a forbidden license expression in `scripts/check_licenses.py` | CI-enforced per ADR-007. |

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Renovate / Dependabot bulk PRs | Reject per AGENTS.md §11.13; one-component-per-PR; PR template checkbox |
| Transitive dep silently changes license | `scripts/check_licenses.py` (ADR-007) lock-file watching; CI fails on tier shift |
| `pyiceberg` upgrade blocks PoC #1 promo + v0.3 dlt | ADR-003 protocol; `tests/upgrade_smoke/test_iceberg_upgrade.py` |
| AI agent proposes a RED tier dep | This ADR + `scripts/check_licenses.py` + PR template checklist |
| Pin staleness compounds (e.g., OTEL 12 minors behind) | Quarterly upgrade audit per AGENTS.md §11.13; tracked in `docs/internal/compatibility.md` |
| `docs/internal/compatibility.md` drifts from this matrix | This ADR is canonical; `compatibility.md` is the derived snapshot |
| Storage-substrate dual-track confuses users | ADR-008 docs sweep; SeaweedFS = default, MinIO = `-f docker-compose.minio.yml` opt-in |
| NEEDS VERIFICATION items merge silently | Each NV listed in Open Questions; resolve before that row's status flips PROPOSED → ACCEPTED |

## Verification plan

1. `scripts/check_pinning.py` — extend to assert this matrix verbatim against `[project.dependencies]`; fails CI on drift.
2. `scripts/check_licenses.py` (ADR-007) — cross-references License + Tier columns; fails CI on tier shift vs lock file.
3. `tests/integration/dependencies/test_imports.py` (post-PoC promotion) — `import <pkg>` + one canonical API call per pinned dep (AGENTS.md §11.12).
4. `docs/internal/compatibility.md` — derived view; quarterly snapshot per AGENTS.md §11.13.
5. `.github/PULL_REQUEST_TEMPLATE.md` — dependency-upgrade checkbox cites this ADR.

## Rollback

ADR-012a amends a specific row if a PoC empirically forces a pin change (e.g., PoC #4 finds `duckdb==1.1.3` too slow → separate ADR for `1.4.x`). Amendments follow Constraint #11 (one-component-per-PR + ADR for major bumps). No emergency rollback for the matrix as a whole — it is the consolidation point; individual rows are the unit of change.

## Trigger

Status flips **PROPOSED → ACCEPTED** when: (1) founder signs off; (2) NEEDS VERIFICATION items resolved per Open Questions OR explicitly marked deferred-OK; (3) `scripts/check_pinning.py` extended to assert this matrix verbatim; (4) `docs/internal/compatibility.md` either deprecated in favour of this ADR OR regenerated as a derived snapshot. **Not gated on any PoC** — documentation governance; can ACCEPT immediately.

## Downstream consumers

| Consumer | When affected |
|---|---|
| `pyproject.toml` `[project.dependencies]` | THIS matrix is canonical; drift is a CI bug |
| `scripts/check_pinning.py` | reads this matrix, asserts pins verbatim |
| `scripts/check_licenses.py` (ADR-007) | cross-references License + Tier columns |
| `docs/internal/compatibility.md` | derived quarterly snapshot |
| All future ADRs proposing upgrades | cite the row they touch |
| `.github/PULL_REQUEST_TEMPLATE.md` | dependency-upgrade checkbox cites this ADR |
| AI agents | cite this ADR for "what is the current pin of X" — never answer from training memory (AGENTS.md §11.12) |
| `tests/upgrade_smoke/` (AGENTS.md §11.13) | one test file per Tier 1/2 row |

## Open questions for founder

1. **Enumerate transitive pins** (`pyarrow`, `click`, `s3fs`) as first-class rows, or stay top-level only? *Default*: include both; CI lint enforces only top-level. (`pyarrow` + `click` already explicit; `s3fs` flagged for explicit pin.) — **RESOLVED 2026-05-13**: keep default (include both rows; CI lint top-level only) per founder blanket approval.
2. **Should Tier 0 immortal rows** (`pyarrow`, `opentelemetry-api/sdk`) **override the upgrade-ADR requirement** since immortal = never swap, only upgrade? *Default*: still require ADR for major bumps (ABI / API churn risk); minor/patch follow normal Constraint #11. — **RESOLVED 2026-05-13**: keep default (ADR required for major bumps) per founder blanket approval.
3. **Retire `docs/internal/compatibility.md`** in favour of this ADR? *Default*: keep `compatibility.md` as a quarterly human snapshot; ADR-012 is the policy lock consumed by CI. — **RESOLVED 2026-05-13**: keep `compatibility.md` as derived quarterly snapshot per founder blanket approval.
4. **Resolve NEEDS VERIFICATION items before ACCEPT?** (a) `psycopg[binary]==3.2.3` license string vs ADR-007 LGPL row (Cloud-impact); (b) explicit `s3fs` pin (currently via `pyiceberg[s3fs]` extra); (c) `dbt-core` PyPI license-field-blank Apache-2.0 confirmation; (d) SeaweedFS exact docker tag per ADR-008; (e) `pyjwt==2.8.x` exact patch at v0.3 ADR time. *Default*: (a) + (b) before ACCEPT (v0.1 surface); (c)-(e) deferred-OK to their adoption ADRs. — **RESOLVED 2026-05-13** per founder blanket approval (FOUNDER_ACTION_QUEUE.md §1 A1.15): (a) **resolved-before-ACCEPT** — `psycopg[binary]==3.2.3` license = LGPLv3+ (dynamic-link exempt) per ADR-007 §Tier 2 YELLOW row; matrix row already records this. (b) **FLAGGED — surfaced for founder action** — `s3fs` currently transitive via `pyiceberg[s3fs]==0.8.1` extra in `pyproject.toml:47`, **not** an explicit top-level pin row; making `s3fs` explicit requires a `pyproject.toml` edit which is out of this PR's scope (founder must add `s3fs==<NV exact version>` to `[project.dependencies]` in a one-line follow-up PR per AGENTS.md §11.13 one-component-per-PR; record matching row in the matrix above). (c)+(d)+(e) **deferred-OK** to their adoption ADRs (dbt-duckdb v0.3+ ADR, ADR-008 SeaweedFS housekeeping PR, v0.3 OIDC ADR-010 implementation PR respectively).

---

*Last verified 2026-05-14 (amendment). Re-verify against `pyproject.toml`, `docs/internal/research/*.md`, and ADR-003 / ADR-004 / ADR-007 / ADR-008 / ADR-010 / ADR-011 on every dependency-upgrade PR.*

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.

**Amended**: 2026-05-14 — Option α-split per `docs/internal/research/otel_day1_decision.md` (founder blanket approval — "approve all recommendations and proposals"): `opentelemetry-sdk` + `sqlglot` demoted to `[project.optional-dependencies]` (`observability` + `lineage-advanced`); `msgspec` removed entirely; pin count revised from 25 → 23 core + 2 optional. Trigger: drift-detection verifier MEDIUM #3 (zero v0.1 callers under `src/`, `tests/`, `poc/`, `scripts/`). See ADR-011 amendment 2026-05-14 for the substrate-by-API-only clarification that justifies keeping `opentelemetry-api` in core.

**Amended**: 2026-05-14 — `click==8.1.7` → `click==8.1.8` to align the declared pin with `litellm==1.83.14`’s transitive requirement (`click==8.1.8`) so default resolves match Constraint #11 intent. Release notes (no breaking changes called out for this patch — bugfixes for typing, help display, `Path` errors, Windows/colorama/bash): https://github.com/pallets/click/blob/main/CHANGES.rst (`Version 8.1.8`, released 2024-12-19). **Rollback:** `pip install click==8.1.7`

**Amended**: 2026-05-14 -- `jinja2==3.1.5` -> `jinja2==3.1.6` to unblock cold `pip install -e ".[dev]"` on clean environments. `litellm==1.83.14` hard-locks `jinja2==3.1.6` in its wheel metadata; `pip` resolver rejects `3.1.5` when `litellm` is in the same env, making the install fail entirely. Security context: 3.1.6 is a security release that patches GHSA-cpwx-vrp4-4pq7 (the `|attr` filter bypassing sandbox attribute lookup) -- no behavioral or API changes vs 3.1.5. Release notes: https://github.com/pallets/jinja/releases/tag/3.1.6 (published 2025-03-05). **Rollback:** `pip install jinja2==3.1.5` requires also downgrading `litellm` -- not a viable rollback; the forward-only path is correct here. Caught by WSL beachhead E2E 2026-05-14.

**Amended**: 2026-05-15 — Connector expansion wave. Added two new `[project.optional-dependencies]` extras: `snowflake = ["dlt[snowflake]==1.26.0"]` (Apache-2.0 · GREEN; per [ADR-019](ADR-019-snowflake-connector-via-dlt.md)) and `gcs = ["gcsfs==2026.5.0"]` (BSD-3-Clause · GREEN; per [ADR-020](ADR-020-object-storage-connectors-via-duckdb.md)). S3 and local-filesystem connectors use existing core deps (`duckdb==1.1.3`, `s3fs==2026.4.0`) — no new pins. Optional pin count revised: 2 → 4 optional-runtime pins. `all = ["nucleus[dev,docs,observability,lineage-advanced,snowflake,gcs]"]` updated. `docs/internal/compatibility.md` §2 and §7 updated accordingly. Rollback for `gcsfs`: `pip uninstall gcsfs`. Rollback for `dlt[snowflake]`: no action needed (dlt itself stays; Snowflake dialect extras are uninstalled by pip if `nucleus[snowflake]` is removed).
