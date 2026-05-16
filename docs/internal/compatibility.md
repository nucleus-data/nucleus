# Component Compatibility Matrix

> **Purpose**: Living matrix mandated by [`AGENTS.md §11.13`](../../AGENTS.md) (Hard Constraint #11 — *Upgrade-safe stack design*). Each row records the exact pin, the license tier per [ADR-007](decisions/ADR-007-dependency-license-tier-policy.md), and the next planned change citing the ADR that fires it. The canonical pin matrix lives in [ADR-012](decisions/ADR-012-runtime-dependency-pin-matrix-v01.md); this file is the derived, always-bumped snapshot consumed by humans and quarterly audits.
> **Owner**: Solo founder · **Last verified**: 2026-05-14 (ADR-012 + ADR-011 amendments — Option α-split)
> **Tracked**: 24 runtime pins + Python floor in §1 (added `croniter==3.0.4` 2026-05-14 per ADR-017) · 2 runtime extras pins (`[observability]`, `[lineage-advanced]`) + 11 dev + 3 docs pins in §2 · 2 storage-substrate container images in §3
> **Companions**: [`AGENTS.md §11.13`](../../AGENTS.md) · [`pyproject.toml`](../../pyproject.toml) · [ADR-007](decisions/ADR-007-dependency-license-tier-policy.md) (license tiers) · [ADR-008](decisions/ADR-008-storage-substrate-v01.md) (storage) · [ADR-012](decisions/ADR-012-runtime-dependency-pin-matrix-v01.md) (canonical pin matrix) · [`docs/internal/research/`](research/README.md) (research index)

**Maintenance discipline (AGENTS.md §11.13)**: ONE component per PR · no bulk upgrades · 24 h cool-down between merges · major-version bumps require an ADR first ([ADR-003](decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) is the v0.1 example) · this file is updated only via PR after the §4 workflow has been followed end-to-end.

**Python runtime**: `>=3.11,<3.13` per `pyproject.toml`; tested 3.11.x + 3.12.x (single-pin per §6 NV #1); 3.11 EOL Oct 2027, 3.12 EOL Oct 2028.

**Status**: ⏳ **Targeted** — Pre-Heartbeat / no installs yet. Promotion to ✅ **Verified** requires (a) clean `pip install -e ".[dev]"` in a fresh venv on Py 3.11 + 3.12, (b) PoC #4 boot harness passes `<10 s`, (c) all docs URLs return 200, (d) `Last verified` bumped to that date.

---

## §1. Runtime dependencies

One row per `pyproject.toml [project.dependencies]` entry. `Tested versions` is single-valued — multi-version CI matrix is v0.3 (§6 NV #1). `Last upgrade` for every row = **"initial v0.1 pin"** until the first upgrade PR lands.

| Component | Current pin | License · Tier (ADR-007) | Next planned (ADR ref) | Notes |
|-----------|-------------|--------------------------|------------------------|-------|
| `pyarrow` | `18.1.0` | Apache-2.0 · GREEN | ceiling moves with [ADR-003](decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) (capped at `<19.0.0`) | **Tier 0 immortal**. Envelopes: ≥10 for DuckDB 1.1.x · ≥11 for Polars 1.x · ≥14,<19 for PyIceberg 0.11.x |
| `duckdb` | `1.1.3` | MIT · GREEN | none v0.1; watch 1.2.x (partitioned writes, new `FROM` syntax) | SQL engine · [`research/duckdb.md`](research/duckdb.md) |
| `polars` | `1.18.0` | MIT · GREEN | none v0.1; watch 1.20+ (decimal improvements) | DataFrame engine · [`research/polars.md`](research/polars.md) |
| `pyiceberg[sql-sqlite,s3fs,duckdb]` | `0.11.1` | Apache-2.0 · GREEN | `0.12.x` review when stable · changelog read per [ADR-003](decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) | Table format · Constraint #4 · **Tested**: `0.8.1` (historical) → **`0.11.1`** (2026-05-13 stabilization; ADR-003 target). PyPI: https://pypi.org/project/pyiceberg/ · Docs: https://py.iceberg.apache.org/ · [`research/pyiceberg.md`](research/pyiceberg.md) |
| `dagster` | `1.9.5` | Apache-2.0 · GREEN | none v0.1; watch 1.10.x; mini-scheduler escalation per v4.1 §6.7 | Hidden orchestrator · Constraint #2 · [`research/dagster.md`](research/dagster.md) |
| `sqlalchemy` | `2.0.36` | MIT · GREEN | none v0.1 | Source connections (Postgres / MySQL); 2.x only |
| `psycopg[binary]` | `3.2.3` | LGPLv3+ · YELLOW (dynamic-link exempt) | NV — confirm license string vs ADR-007 LGPL row (§6 NV #4) | Postgres connector; v3 |
| `pymysql` | `1.1.1` | MIT · GREEN | none v0.1 | MySQL connector; pure-Python |
| `jinja2` | `3.1.6` | BSD-3-Clause · GREEN | none v0.1 | `ctx.sql` template resolution (PoC #2). **Bumped 2026-05-14** (`3.1.5` → `3.1.6`) — security patch (GHSA-cpwx-vrp4-4pq7: `\|attr` filter sandbox bypass fixed); no breaking changes. Blocked cold install with `litellm==1.83.14` which hard-requires `jinja2==3.1.6` in its wheel metadata. Rollback: `pip install jinja2==3.1.5` (requires downgrading litellm — not viable). Release notes: https://github.com/pallets/jinja/releases/tag/3.1.6 |
| `click` | `8.1.8` | BSD-3-Clause · GREEN | **pre-v0.3 ADR** → `8.3.0` (required by `dbt-duckdb==1.10.1`; `research/dbt-duckdb.md` §6) | CLI primitives (via typer). **Bumped 2026-05-14** (`8.1.7` → `8.1.8`) to match `litellm==1.83.14` transitive pin; see ADR-012 amendment + https://github.com/pallets/click/blob/main/CHANGES.rst §Version 8.1.8. Rollback: `pip install click==8.1.7`. |
| `typer` | `0.15.1` | MIT · GREEN | follows v0.1 CLI | CLI framework |
| `rich` | `13.9.4` | MIT · GREEN | none v0.1 | Terminal UI |
| `structlog` | `24.4.0` | Apache-2.0 / MIT dual · GREEN | v0.5 OTEL Logs bridge ADR (`research/opentelemetry.md` §5) | Structured logging |
| `opentelemetry-api` | `1.29.0` | Apache-2.0 · GREEN | v0.5 ADR (12 minors stale; gated by [ADR-011](decisions/ADR-011-telemetry-and-observability-opt-in-policy.md)) | **Tier 0 immortal**; substrate-by-API-only — produces no-op `NonRecordingSpan` when no `TracerProvider` is configured (https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html). SDK demoted to `[observability]` extras 2026-05-14 per ADR-011 amendment + `docs/internal/research/otel_day1_decision.md` §D1. |
| `s3fs` | `2026.4.0` | BSD-3-Clause · GREEN | none v0.1; CalVer cadence — review quarterly | S3 / object-store access; explicit pin landed 2026-05-13 per ADR-012 NV (b) |
| `openlineage-python` | `1.47.1` | Apache-2.0 · GREEN | none v0.1; watch monthly minors; v0.3 HttpTransport ADR for Marquez | **Tier 0 immortal** (v4.1 §4.1); asset-level lineage emit in AMA (`coordination/lineage.py`) per `research/openlineage.md` §5.1; landed 2026-05-13 |
| `fastapi` | `0.136.1` | MIT · GREEN | follows Workbench v0.2 roadmap per [ADR-016](decisions/ADR-016-workbench-mvp.md) | REST + OpenAPI backend · PyPI: https://pypi.org/project/fastapi/ · Docs: https://fastapi.tiangolo.com/ · pinned 2026-05-13 (`pip index versions`, stabilization bundle) |
| `httpx` | `0.28.1` | BSD-3-Clause · GREEN | paired with FastAPI `TestClient` per ADR-016 | PyPI: https://pypi.org/project/httpx/ · Docs: https://www.python-httpx.org/ · pinned 2026-05-13 |
| `uvicorn[standard]` | `0.46.0` | BSD-3-Clause · GREEN | ASGI server for Workbench per [ADR-016](decisions/ADR-016-workbench-mvp.md) | PyPI: https://pypi.org/project/uvicorn/ · Docs: https://www.uvicorn.org/ · pinned 2026-05-13 |
| `dlt[sql_database,pyiceberg]` | `1.26.0` | Apache-2.0 · GREEN | Stage 2 (incremental loading ADR); ConnectorX pre-commit deferred to evidence per ADR-014 OQ-5 | Stage 1 Postgres source wrap per [ADR-014](decisions/ADR-014-dlt-postgres-source.md); pinned 2026-05-13; JVM-free (pyiceberg-core = Rust); swap doc: [`docs/internal/swap/dlt.md`](swap/dlt.md); research: [`docs/internal/research/dlt.md`](research/dlt.md) |
| `croniter` | `3.0.4` | MIT · GREEN | Next upgrade requires `dagster` upgrade first (dagster 1.9.5 requires `croniter<4`; 3.0.4 is the latest `<4` release). Upgrade smoke: `tests/upgrade_smoke/` (add `test_croniter.py` before bumping). | Schedule cron parsing + preview per [ADR-017](decisions/ADR-017-schedule-exposure-v01.md). Already a transitive dep via dagster; this pin makes governance explicit. croniter `is_valid()` + `get_next()` used for decorator validation + `nucleus schedule preview`. Pinned 2026-05-14. Docs: https://pypi.org/project/croniter/ |
| `litellm` | `1.83.14` | MIT · GREEN | next upgrade requires reading changelog + running `tests/upgrade_smoke/test_litellm.py` | Intelligence layer / AI Copilot wrap per [ADR-015](decisions/ADR-015-ai-chat-mvp.md); Python `>=3.10,<3.14` (satisfies our `>=3.11,<3.13`); wraps 100+ LLM providers; pinned 2026-05-13; swap doc: [`docs/internal/swap/litellm.md`](swap/litellm.md); Upgrade smoke: `tests/upgrade_smoke/test_litellm.py` |
| `pyyaml` | `6.0.3` | MIT · GREEN | none v0.1; watch 6.1 (when stable) | YAML config parsing for `nucleus.yaml` (CLI) + `.copilot_opt_in` sentinel (Intelligence). Direct imports in `cli/main.py`, `intelligence/copilot.py`, `intelligence/context.py`. Pinned 2026-05-14 (drift-detection verifier finding; previously transitive via dlt/litellm — Constraint #11 violation). Docs: https://pyyaml.org/wiki/PyYAMLDocumentation · PyPI: https://pypi.org/project/PyYAML/ |
| `orjson` | `3.11.9` | (Apache-2.0 OR MIT) AND MPL-2.0 · YELLOW | none v0.1; FastAPI 0.116+ deprecates `default_response_class=ORJSONResponse` → revisit in v0.2.1 | Workbench FastAPI default response class (~3x faster JSON serialization) per ADR-016. Pinned 2026-05-14 (verifier finding; previously transitive — Constraint #11 violation). Docs: https://github.com/ijl/orjson · PyPI: https://pypi.org/project/orjson/ |

---

## §2. Optional / extras (`[project.optional-dependencies]`)

Two tiers per ADR-012 amendment 2026-05-14:

1. **Runtime extras** (`observability`, `lineage-advanced`) — exact pins required; checked by `scripts/check_pinning.py` with the same `==` rule as `[project] dependencies`. These are real runtime libs gated behind opt-in install, not contributor tooling.
2. **Dev / docs extras** (`dev`, `docs`) — `==` or `~=` accepted by default; `--strict` upgrades to `==`-only.

| Component | Extra | Current pin | License · Tier (ADR-007) | Notes |
|-----------|-------|-------------|--------------------------|-------|
| `opentelemetry-sdk` | observability | `1.29.0` | Apache-2.0 · GREEN | **Tier 0 immortal**. Demoted from core 2026-05-14 per [ADR-011 amendment](decisions/ADR-011-telemetry-and-observability-opt-in-policy.md) + [ADR-012 amendment](decisions/ADR-012-runtime-dependency-pin-matrix-v01.md) + `docs/internal/research/otel_day1_decision.md` §D1. Install via `pip install nucleus[observability]` for v0.5+ exporter wiring. Version-locked to `opentelemetry-api==1.29.0` in core. |
| `sqlglot` | lineage-advanced | `26.0.0` | MIT · GREEN | Tier 2 SQL parsing. Demoted from core 2026-05-14 per [ADR-012 amendment](decisions/ADR-012-runtime-dependency-pin-matrix-v01.md) + `docs/internal/research/otel_day1_decision.md` §D2. Install via `pip install nucleus[lineage-advanced]`. **Note**: `dlt[sql_database,pyiceberg]==1.26.0` already requires `sqlglot` transitively (verified 2026-05-14 via `pip show dlt`), so users running the default install receive it indirectly; this extras row exposes it as a direct, version-locked pin for projects that import `sqlglot` without depending on dlt. Pre-v0.3 upgrade to `26.8.x` planned for marimo SQL cells (`research/sqlglot.md` §6). |
| `dlt[snowflake]` | snowflake | `1.26.0` | Apache-2.0 · GREEN | Snowflake source connector per [ADR-019](decisions/ADR-019-snowflake-connector-via-dlt.md). Same dlt pin as core; adds `snowflake-connector-python` (Apache-2.0) + `snowflake-sqlalchemy` (Apache-2.0). Install via `pip install nucleus[snowflake]`. Research: [`docs/internal/research/snowflake.md`](research/snowflake.md). Pinned 2026-05-15. |
| `gcsfs` | gcs | `2026.5.0` | BSD-3-Clause · GREEN | GCS object-storage connector per [ADR-020](decisions/ADR-020-object-storage-connectors-via-duckdb.md). Provides ADC credential chain for DuckDB `register_filesystem()`. Install via `pip install nucleus[gcs]`. Research: [`docs/internal/research/gcs_duckdb.md`](research/gcs_duckdb.md). Pinned 2026-05-15 (current stable, CalVer). Docs: https://gcsfs.readthedocs.io/en/latest/ |
| `ruff` | dev | `0.15.13` | MIT · GREEN | Linter + formatter. **Upgraded 2026-05-15** `0.8.4 → 0.15.13` per [ADR-027](decisions/ADR-027-uv-ruff-toolchain.md); applied 2026 style formatter diff (107 files). Rollback: `pip install ruff==0.8.4`. Docs: https://docs.astral.sh/ruff/ |
| `mypy` | dev | `1.13.0` | MIT · GREEN | Strict-mode type checker |
| `pytest` | dev | `8.3.4` | MIT · GREEN | Test framework |
| `pytest-cov` | dev | `6.0.0` | MIT · GREEN | Coverage |
| `pytest-xdist` | dev | `3.6.1` | MIT · GREEN | Parallel tests |
| `pytest-asyncio` | dev | `0.25.0` | Apache-2.0 · GREEN | Async surface tests |
| `hypothesis` | dev | `6.123.7` | MPL-2.0 · YELLOW (file-level copyleft; safe per ADR-007) | Property tests |
| `testcontainers` | dev | `4.9.0` | Apache-2.0 · GREEN | Postgres / storage containers for integration tests |
| `pre-commit` | dev | `4.0.1` | MIT · GREEN | Git hooks |
| `psutil` | dev | `7.2.2` | BSD-3-Clause · GREEN | Boot-time + memory measurement; `poc/p4_boot_time/measure.py`. Verified 2026-05-13 (PyPI v7.2.2 current; Python >=3.6). Docs: https://psutil.readthedocs.io/ |
| `hatchling` | dev | `1.27.0` | MIT · GREEN | Build backend |
| `build` | dev | `1.2.2.post1` | MIT · GREEN | sdist / wheel runner |
| `mkdocs` | docs | `1.6.1` | BSD-2-Clause · GREEN | Docs site generator |
| `mkdocs-material` | docs | `9.5.49` | MIT · GREEN | Material theme |
| `mkdocstrings[python]` | docs | `0.27.0` | ISC · GREEN | Auto-generated API docs |

---

## §3. Storage substrate (container images, per [ADR-008](decisions/ADR-008-storage-substrate-v01.md))

Dual-track compose templates; the application layer is S3-API-agnostic so no `pyproject.toml` pin moves with the substrate choice. Both digests verified by Worker B on 2026-05-13.

| Image | Pinned tag | Digest (`sha256:`) | License · Tier | Status | Role | Compose file |
|-------|-----------|--------------------|----------------|--------|------|--------------|
| `chrislusf/seaweedfs` | `4.23` (pushed 2025-05-04) | `c6d6fb84b081f1f09bb089184ff4b45d2f163a1bfa8b354d04cf400c6e06f242` | Apache-2.0 · **GREEN** | Active (~32 k stars) | **Default** v0.1 storage | [`docker-compose.yml`](../../docker-compose.yml) |
| `quay.io/minio/minio` | `RELEASE.2025-09-07T16-13-09Z` (terminal OSS) | `14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e` | **AGPLv3** · **YELLOW** | **Archived 2026-04-25** — no future CVE patches | Alternate (opt-in only) | [`docker-compose.minio.yml`](../../docker-compose.minio.yml) |

**Cloud rule** (ADR-007 YELLOW): MinIO MUST NOT be bundled into a Nucleus Cloud distribution or offered as a managed service (AGPLv3 §13 would force source-release of the Cloud control plane). SeaweedFS has no such constraint. **Tag-drift**: ADR-008's body cites `RELEASE.2025-10-15…`; the verified digest above is for `…-09-07…`, what the compose file pins — see §6 NV #2.

---

## §4. Upgrade workflow reminder (AGENTS.md §11.13)

Canonical workflow lives in [`AGENTS.md §11.13`](../../AGENTS.md); skipping any step = rejected PR.

1. **ONE component per PR.** Reject Renovate/Dependabot batched PRs; split them.
2. **Read the changelog** from current to target (every intermediate minor, not just target); summarize behavioral changes in the PR body.
3. **Run the upgrade smoke test**: existing suite passes (Linux + macOS on Py 3.11 + 3.12) + `tests/upgrade_smoke/test_<component>_upgrade.py` (add it as part of the PR if missing) + benchmarks within ±10 % of pre-upgrade baseline.
4. **PR description must include**: changelog summary · explicit **rollback command** (e.g., `pip install "pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1"`) · observed behavioral changes · this file's row updated + CHANGELOG row.
5. **24 h cool-down** between merging a dep-upgrade PR and the next — catches regressions before stacking.
6. **Major-version bumps** (X.y.z → X+1.y.z) always require an ADR before the upgrade PR opens — [ADR-003](decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) is the v0.1 example.

---

## §5. Quarterly upgrade audit cadence (AGENTS.md §11.13)

Every **3 months**, a dedicated 1–2 day session reviews this matrix end-to-end: each row checked against the upstream release stream (stale flag = >6 months behind), next quarter's upgrades planned (one component per PR; majors as ADRs), `pip-audit` cross-checked for security advisories, `Last verified` bumped, and one row appended to §7 per change.

| Audit | Date (target) | Status |
|-------|---------------|--------|
| Audit #1 (next) | **2026-08-13** | scheduled (3 months from this publication) |
| Audit #2 | 2026-11-13 | scheduled |
| Audit #3 | 2027-02-13 | scheduled |

Slippage of an audit is itself a Stop-Condition signal per [`AGENTS.md §9`](../../AGENTS.md).

---

## §6. NEEDS VERIFICATION

Open gaps tracked until resolved:

1. **`Tested versions` is single-valued.** No multi-version CI matrix yet; AGENTS.md §11.13 implies `scripts/upgrade_smoke.py` + `tests/upgrade_smoke/test_<component>_upgrade.py` per Tier-1/2 row — target v0.3. Once it lands, the column expands to the exercised range.
2. **Storage-substrate tag drift.** [ADR-008](decisions/ADR-008-storage-substrate-v01.md) body cites MinIO `RELEASE.2025-10-15T17-29-55Z`; [`docker-compose.minio.yml`](../../docker-compose.minio.yml) pins `RELEASE.2025-09-07T16-13-09Z` (Worker B verified). Resolution: ADR-008 Trigger housekeeping PR reconciles the ADR body; this file already records the verified pin.
3. **License-tier source-of-truth.** [ADR-007](decisions/ADR-007-dependency-license-tier-policy.md) Verification §1 calls for `scripts/check_licenses.py` (~80 LOC, v0.5 release blocker) — not authored yet. Today, license rows are manual reads of PyPI / GitHub LICENSE per AGENTS.md §11.12.
4. **`psycopg[binary]==3.2.3` LGPL string.** ADR-012 NV: the `binary` extra ships pre-built `libpq`; confirm LGPLv3+ classification covers the binary-extra path (dynamic-link exempt per ADR-007 Tier 2) before ADR-012 flips PROPOSED → ACCEPTED.
5. ~~**`s3fs` explicit pin.** Currently transitive via `pyiceberg[s3fs]==0.8.1` (ADR-012 NV); promote to top-level pin in the next housekeeping PR.~~ **CLEARED 2026-05-13** — explicit pin `s3fs==2026.4.0` landed in `pyproject.toml:48`; row in §1 updated; ADR-012 matrix row updated.
6. **MinIO arm64 manifest** for the verified tag — archived upstream = no future arm64 builds; Apple-silicon consequence documented in `SETUP.md`.

---

## §7. Change history

| Date | Change | PR |
|------|--------|-----|
| 2026-05-12 | Initial v4.1-scaffold matrix (7-subsection layout) — superseded by 2026-05-13 rewrite | — |
| 2026-05-13 | Rewrote to 6-section spec per `AGENTS.md §11.13`; integrated [ADR-007](decisions/ADR-007-dependency-license-tier-policy.md), [ADR-008](decisions/ADR-008-storage-substrate-v01.md), [ADR-012](decisions/ADR-012-runtime-dependency-pin-matrix-v01.md); linked [ADR-003](decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) for `pyiceberg` next-planned. Dropped pre-existing inter-component / pinning-policy / CVE / EOL sections; folded PyArrow compat envelopes into the `pyarrow` row notes. | — |
| 2026-05-13 | Added `psutil==7.2.2` to dev extras (Worker δ); BSD-3-Clause · GREEN; boot-time + memory measurement for `poc/p4_boot_time/measure.py`. Verified same day on PyPI. | — |
| 2026-05-13 | Added `openlineage-python==1.47.1` runtime pin (asset-level lineage emitter in AMA per v4.1 §6.2 step 4); Apache-2.0 · GREEN; Python `>=3.10` (compatible with our `>=3.11,<3.13` floor); verified on PyPI same day; research/openlineage.md was already drafted 2026-05-13 0240. | — |
| 2026-05-13 | Added `dlt[sql_database,pyiceberg]==1.26.0` runtime pin (Stage 1 Postgres source wrap per ADR-014); Apache-2.0 · GREEN; JVM-free; pyiceberg-core = Rust; Python `<3.15,>=3.9.2` (compatible with our `>=3.11,<3.13`); verified on PyPI 2026-05-13; upgrade smoke in `tests/upgrade_smoke/test_dlt_upgrade.py`. | — |
| 2026-05-13 | **PyIceberg `0.8.1 → 0.11.1`** per [ADR-003](decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) (ratified target); `Last upgrade` set to 2026-05-13; `pyarrow` envelope note updated for 0.11.x; unblocks clean install with `dlt[pyiceberg]`. | — |
| 2026-05-13 | **Workbench HTTP stack**: `fastapi==0.136.1`, `httpx==0.28.1`, `uvicorn[standard]==0.46.0` — versions verified via `pip index versions` same day; [ADR-016](decisions/ADR-016-workbench-mvp.md); enables `tests/workbench/` without `importorskip`. | — |
| 2026-05-15 | **Connector expansion wave** — added `snowflake` optional extras (`dlt[snowflake]==1.26.0`) per [ADR-019](decisions/ADR-019-snowflake-connector-via-dlt.md); added `gcs` optional extras (`gcsfs==2026.5.0`) per [ADR-020](decisions/ADR-020-object-storage-connectors-via-duckdb.md). S3 and filesystem connectors add zero new deps (use existing `duckdb==1.1.3` + `s3fs==2026.4.0`). Pin count revised: 2 optional-runtime → 4 optional-runtime. | — |
| 2026-05-14 | **Option α-split per `docs/internal/research/otel_day1_decision.md`** (drift-detection verifier MEDIUM #3 — zero v0.1 callers under `src/`, `tests/`, `poc/`, `scripts/`). Founder blanket approval. (a) `opentelemetry-sdk==1.29.0` → `[project.optional-dependencies] observability` (substrate-by-API-only honored per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html `NonRecordingSpan` semantics; ADR-011 amended). (b) `sqlglot==26.0.0` → `[project.optional-dependencies] lineage-advanced` (PoC #2 promoted with jinja2 + regex + difflib; first concrete caller is v0.5+ column-lineage walker per `docs/internal/research/sqlglot.md` §10; `dlt` still requires `sqlglot` transitively). (c) `msgspec==0.18.6` REMOVED entirely (planned `NucleusError + configs` use never materialized; pure-stdlib substitutes suffice; reversible via one-line pyproject edit). Pin count revised 25 → 23 core + 2 optional. Default `pip install nucleus` install size shrinks ~2 MB (OTEL SDK + `opentelemetry-semantic-conventions` ≈ 1.5 MB; `msgspec` ≈ 0.5 MB). No source code changes. ADR-011 + ADR-012 amended in place; no new ADR. | — |
| 2026-05-14 | **`click==8.1.7` → `8.1.8`** — aligns declared pin with `litellm==1.83.14` (`click==8.1.8`). Patch release per upstream changelog (https://github.com/pallets/click/blob/main/CHANGES.rst — `Version 8.1.8`). ADR-012 + this matrix updated. Rollback: `pip install click==8.1.7`. | — |
| 2026-05-14 | **`jinja2==3.1.5` → `3.1.6`** — security patch (GHSA-cpwx-vrp4-4pq7) + unblocks cold install: `litellm==1.83.14` hard-requires `jinja2==3.1.6` in wheel metadata, making `pip install -e ".[dev]"` fail on clean envs with `3.1.5`. No breaking changes vs 3.1.5. Release notes: https://github.com/pallets/jinja/releases/tag/3.1.6. ADR-012 amended. Rollback not viable (requires downgrading litellm). Caught by WSL beachhead E2E 2026-05-14. | — |

---

*Constraint #11 in action: read this file before installing or upgrading anything.*
