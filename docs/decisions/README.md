# Architecture Decision Records (ADRs)

Per AGENTS.md §11.5, every "build" decision and every architectural amendment to `docs/specs/nucleus_architecture_v4.1.md` lands here as an ADR. Statuses: PROPOSED, ACCEPTED, SUPERSEDED, REJECTED. Cite ADRs by number (e.g., "per ADR-003") in code comments and PR descriptions.

---

## Master index

| ADR | Status | Title | Date |
|---|---|---|---|
| [ADR-001](./ADR-001-no-iceberg-commit-service.md) | ACCEPTED | No Iceberg Commit Service — delegate to catalog | 2026-05-12 |
| [ADR-002](./ADR-002-positioning-decision-2026-05.md) | ACCEPTED w/ amendments | Positioning Decision — Mid-2026 Strategic Refresh | 2026-05-12 |
| [ADR-003](./ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) | ACCEPTED | PyIceberg Upgrade 0.8.1 → 0.11.x | 2026-05-12 |
| [ADR-004](./ADR-004-catalog-migration-v01-to-v03.md) | ACCEPTED | Iceberg Catalog Migration Path v0.1 → v0.3 | 2026-05-13 |
| [ADR-005](./ADR-005-ctx-sdk-api-freeze-policy.md) | ACCEPTED | `ctx` SDK API Freeze Policy | 2026-05-13 |
| [ADR-006](./ADR-006-nucleus-error-code-numbering.md) | ACCEPTED | NucleusError Error Code Numbering Scheme | 2026-05-13 |
| [ADR-007](./ADR-007-dependency-license-tier-policy.md) | ACCEPTED | Dependency License Tier Policy | 2026-05-13 |
| [ADR-008](./ADR-008-storage-substrate-v01.md) | ACCEPTED | Storage Substrate Triage Post-MinIO Archival (Pre-v0.1) | 2026-05-13 |
| [ADR-009](./ADR-009-openlineage-event-schema-policy.md) | ACCEPTED | OpenLineage Event Schema Policy | 2026-05-13 |
| [ADR-010](./ADR-010-oidc-delegation-policy-v03.md) | ACCEPTED | OIDC Delegation Policy (v0.3+) | 2026-05-13 |
| [ADR-011](./ADR-011-telemetry-and-observability-opt-in-policy.md) | ACCEPTED | Telemetry & Observability Opt-In Policy | 2026-05-13 |
| [ADR-012](./ADR-012-runtime-dependency-pin-matrix-v01.md) | ACCEPTED | Runtime Dependency Pin Matrix v0.1 | 2026-05-13 |
| [ADR-013](./ADR-013-ctx-materialize-api.md) | ACCEPTED | `ctx.materialize()` API Surface for Asset Materialization | 2026-05-13 |
| [ADR-014](./ADR-014-dlt-postgres-source.md) | ACCEPTED | Postgres source via dlt wrap (Stage 1 wave) | 2026-05-13 |
| [ADR-015](./ADR-015-ai-chat-mvp.md) | ACCEPTED | AI Copilot Chat MVP (v0.2 CLI-only) | 2026-05-13 |
| [ADR-016](./ADR-016-workbench-mvp.md) | ACCEPTED | Workbench MVP — Custom React SPA + FastAPI (Fork B) | 2026-05-13 |

---

## By topic

### Strategy & positioning

- **[ADR-002](./ADR-002-positioning-decision-2026-05.md)** — Locks positioning: laptop-first SDK + CLI, Iceberg as substrate (not category), AI-ready (not AI-native). Retires Angles C and D; amends v4.1 §1, §5.7, §17.2, §18.4.

### Catalog & storage

- **[ADR-001](./ADR-001-no-iceberg-commit-service.md)** — Atomic-commit responsibility delegates to the catalog per Hard Constraint #5; removes the v4.0 coordinator three reviewers flagged as the most over-built piece of the design.
- **[ADR-004](./ADR-004-catalog-migration-v01-to-v03.md)** — v0.1 ships filesystem `pyiceberg.SqlCatalog`; v0.3+ co-defaults Lakekeeper (Rust) + Polaris (JVM, ASF top-level) via `pyiceberg.RestCatalog` — swap is config-only.
- **[ADR-008](./ADR-008-storage-substrate-v01.md)** — `github.com/minio/minio` archived 2026-04-25; SeaweedFS becomes the documented default and MinIO is preserved as alternate "archived upstream". Trips AGENTS.md §9 Stop Conditions.

### Dependency & compatibility

- **[ADR-003](./ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md)** — Trigger-fires when PoC #1 passes (17/17 green pytest). Hard prerequisite for both PoC #1 promotion and v0.3 dlt integration (`dlt[pyiceberg]>=1.26.0` floor).
- **[ADR-007](./ADR-007-dependency-license-tier-policy.md)** — GREEN / YELLOW / RED license tiering after MinIO (AGPLv3) and Soda Core v4 (Elastic 2.0) findings; gates the v0.5+ Cloud-tier path.
- **[ADR-012](./ADR-012-runtime-dependency-pin-matrix-v01.md)** — Single consolidation point for the 17 runtime pins × research × license tier × Tier 0/1/2 swap class; drives `pyproject.toml` and the CI pinning + license scripts.

### SDK & API governance

- **[ADR-005](./ADR-005-ctx-sdk-api-freeze-policy.md)** — Four-tier API ladder (Internal / Beta / Stable / Frozen) plus per-family freeze schedule and a CI-enforceable breaking-change protocol; AI APIs carve out a 6-month deprecation window.
- **[ADR-006](./ADR-006-nucleus-error-code-numbering.md)** — Hierarchical 6-character codes `NE[L][CCC]` introduced in the PoC #1 promotion PR before any user-facing identifier escapes; codes are PERMANENT and never recycled.
- **[ADR-013](./ADR-013-ctx-materialize-api.md)** — Adds the singular `ctx.materialize(...)` to the public surface; wraps `dagster.materialize` per v4.1 §6.2 + ADR-001 and unblocks `cli/commands/run.py`.

### Connectors (Stage 1+)

- **[ADR-014](./ADR-014-dlt-postgres-source.md)** — Wrap `dlt.sources.sql_database` for Postgres → Iceberg; adds `dlt==1.26.0` runtime dep + `ctx.ingest_postgres_to_iceberg()` + `nucleus ingest postgresql://...` dispatch. Foundation for Stage 2 incremental + v0.3+ connector breadth without re-architecture.

### Workbench (v0.2+)

- **[ADR-016](./ADR-016-workbench-mvp.md)** — Fork B (custom React 18 + Vite + TypeScript SPA served by FastAPI). Rejects Fork A (Dagster UI + Marquez wrap) — JVM violation + Dagster vocabulary leak. Resolves v4.1 Appendix B Q3.

### Intelligence layer (v0.2+)

- **[ADR-015](./ADR-015-ai-chat-mvp.md)** — Wrap `litellm==1.83.14` for `nucleus chat` CLI; Anthropic default + OpenAI alt + Ollama offline. CLI-only MVP in v0.2 (Workbench AI sidebar deferred to v0.2.1/v0.3 per ADR-016 Open Question 2). Introduces `NE4xxx` Intelligence-layer error code range (co-amends ADR-006 §NV).

### Observability & auth

- **[ADR-009](./ADR-009-openlineage-event-schema-policy.md)** — `openlineage.client.event_v2` only (never v1); `FileTransport` JSONL for v0.1, `HttpTransport` opt-in for v0.3+. Always emit from the Asset Materialization Adapter.
- **[ADR-010](./ADR-010-oidc-delegation-policy-v03.md)** — v0.1 ships no auth. v0.3+ supports Authentik (default), Keycloak, Okta, Entra ID through one `[auth]` block; `PyJWT` validates only — Nucleus never issues tokens.
- **[ADR-011](./ADR-011-telemetry-and-observability-opt-in-policy.md)** — Telemetry OPT-IN for v0.1 → v0.5 OSS; OTEL wired with no-op sink Day 1. Cloud MAY flip to OPT-OUT for paying customers only. Cardinality budget enforced in CI.

---

## Conventions

- **Numbers are immortal** — never re-used; superseded ADRs keep their number with status `SUPERSEDED` and a `Supersedes:` / `Superseded by:` cross-link.
- **One decision per ADR.** Multi-decision PRs split into multiple ADRs.
- **PROPOSED → ACCEPTED gate**: founder review only. AI agents may draft, never accept.
- **Architectural changes** to `docs/specs/nucleus_architecture_v4.1.md` MUST cite the amending ADR in the changelog.
- **Build vs. wrap** (AGENTS.md §11.5): every "build" ADR needs the OSS-options-considered grid filled in honestly.

---

[← `docs/specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) · [AGENTS.md §11.5](../../AGENTS.md) · [ADR template](./_template.md)

*Last updated 2026-05-13 (alignment sweep #3 — ADR-003 through ADR-013 ratified via founder blanket approval per FOUNDER_ACTION_QUEUE.md §0). Add new ADRs by appending to the master index and the matching topic group; do not renumber.*
