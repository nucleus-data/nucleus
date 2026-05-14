# Research Index

Per AGENTS.md Hard Constraint #10 ("Read official docs before integration. Never rely on AI memory."), every wrapped OSS component has an anchor file here. Each anchor is the single source of truth for that library's pin, license, surface area, and known hallucinations — read it before writing code that imports the library, and re-verify against the live docs URL before shipping.

This file is a navigation index only. **Do not** treat one-line summaries below as authoritative; click through to the anchor for any non-trivial decision.

---

## Tier 0 — Immortal substrates

Open standards and reference implementations Nucleus treats as durable per `nucleus_architecture_v4.1.md` §4. **No swap target ever.**

- **[lance.md](./lance.md)** (pin: deferred to v0.5+; candidate `pylance==6.0.0` / `lancedb==0.30.2`, license: Apache-2.0, tier: 0 format / 1 library) — Open multimodal lakehouse format + embedded vector library; Tier 0 case stands on ASF-inspired governance + open spec (LF-alignment claim flagged unverified, §9 item 7). *Worker R, 2026-05-13.*
- **[openlineage.md](./openlineage.md)** (pin: candidate `openlineage-python==1.47.1`, license: Apache-2.0, tier: 0) — Open lineage event spec; AMA is the only call site. *2026-05-13.*
- **[opentelemetry.md](./opentelemetry.md)** (pin: `opentelemetry-api==1.29.0` / `opentelemetry-sdk==1.29.0`, license: Apache-2.0, tier: 0) — Wire-format protocol for boot-time tracing today; full collector stack v0.5+. *2026-05-13.*
- **[pyarrow.md](./pyarrow.md)** (pin: `pyarrow==18.1.0`, license: Apache-2.0, tier: 0) — Universal in-memory columnar format; the zero-copy interop contract every L0/L1 boundary uses. *2026-05-13.*
- **[pyiceberg.md](./pyiceberg.md)** (pin: `pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1`, license: Apache-2.0, tier: 0) — Pure-Python Iceberg implementation; ADR-001 delegates atomic commits here; ADR-003 queues 0.11.x upgrade. *2026-05-12.*

## Tier 1 — Wrappable engines + libraries

Default OSS we wrap behind `ctx`. Every entry has a swap interface + smoke tests in `docs/swap/` per Hard Constraint #9; full adapters built on-demand only.

- **[daft.md](./daft.md)** (pin: candidate `daft==0.7.11`, license: Apache-2.0, tier: 1, v0.5+ optional) — Multimodal DataFrame engine for the v0.5 ADR; opt-in via `@nucleus.asset(engine="daft")`. *2026-05-13.*
- **[dbt-duckdb.md](./dbt-duckdb.md)** (pin: candidate `dbt-duckdb==1.10.1` + `dbt-core==1.10.x`, license: Apache-2.0, tier: 1, v0.3+ optional) — Forward-leverage adapter for "drop your existing dbt project in"; PoC #2 fallback only — **do not import in v0.1**. *2026-05-13.*
- **[dlt.md](./dlt.md)** (pin: candidate `dlt==1.26.0`, license: Apache-2.0, tier: 1, v0.3+) — Python ELT framework wrapping 100+ source connectors; v0.1 stays on `ctx.copy_from` (~200 LOC). *2026-05-13.*
- **[duckdb.md](./duckdb.md)** (pin: `duckdb==1.1.3`, license: MIT, tier: 1) — Default SQL engine; wrapped behind `ctx.sql`; users never `import duckdb`. *2026-05-12.*
- **[lakekeeper.md](./lakekeeper.md)** (pin: server `0.12.2` (external service; Python via `pyiceberg.RestCatalog`), license: Apache-2.0, tier: 1, v0.3+) — Rust-native Iceberg REST catalog; v0.3 documented default per ADR-004. *Worker F, 2026-05-13.*
- **[marimo.md](./marimo.md)** (pin: candidate `marimo==0.23.6`, license: Apache-2.0, tier: 1, v0.3+) — Reactive Python notebook runtime; replaces Jupyter; coexists with v0.2 Workbench. *2026-05-13.*
- **[polaris.md](./polaris.md)** (pin: server `1.4.1` (external JVM service; Python via `pyiceberg.RestCatalog`), license: Apache-2.0, tier: 1, v0.3+) — ASF Top-Level Iceberg REST catalog; v0.3 alternate per ADR-004; JVM exemption per ADR-002 §6. *Worker H, 2026-05-13.*
- **[polars.md](./polars.md)** (pin: `polars==1.18.0`, license: MIT, tier: 1) — Default DataFrame engine; Rust core, zero-copy Arrow interop. *2026-05-12.*
- **[soda.md](./soda.md)** (pin: candidate `soda-core==3.5.6` (last Apache-2.0 release; v4.x = Elastic License), license: Apache-2.0 (v3) / Elastic-2.0 (v4), tier: 1, v0.5+ optional) — License-boundary watch item; v0.1 ships native `@nucleus.check` + `@nucleus.contract`. *Worker T, 2026-05-13.*
- **[sqlglot.md](./sqlglot.md)** (pin: `sqlglot==26.0.0`, license: MIT, tier: 1) — Pure-Python SQL parser; powers `ctx.sql` Jinja resolver (PoC #2) + asset dependency graph; column-lineage v0.5+. *2026-05-13.*

## Tier 2 — Services + protocols (operationally swappable)

External binaries / services + per-protocol provider notes; not Python deps.

- **[dagster.md](./dagster.md)** (pin: `dagster==1.9.5`, license: Apache-2.0, tier: 2) — Wrapped + hidden orchestration runtime; PoC #1 validates the Error Translation Layer; users never `import dagster`. *2026-05-12.*
- **[minio.md](./minio.md)** (pin: server `RELEASE.2025-09-07T16-13-09Z` (terminal OSS — **archived 2026-04-25**), license: AGPL-3.0, tier: 2 implementation / 0 protocol) — Local S3-API substrate; SeaweedFS promoted to default per ADR-008; Nucleus does not `import minio`. *Worker BB, 2026-05-13.*
- **[observability_backends.md](./observability_backends.md)** (pin: VictoriaMetrics + VictoriaLogs + Marquez (external services), license: Apache-2.0 (all three), tier: 2, v0.5+ optional) — OTEL + OpenLineage backend bundle; opt-in via `nucleus enable obs`. *2026-05-13.*
- **[oidc_providers.md](./oidc_providers.md)** (pin: external (Authentik 2026.2 MIT / Keycloak 26.6.1 Apache-2.0 / Okta / Entra ID); client-side `PyJWT==2.8.x` candidate, license: per-provider, tier: 2, v0.3+) — Four-provider OIDC delegation matrix; Hard Constraint #6 — never own identity. *Worker W, 2026-05-13.*

## Watch items + meta

Not pinned, not wrapped — included for completeness.

- **[ducklake.md](./ducklake.md)** — Watch item (DuckDB Labs lakehouse format); not a swap target — Iceberg remains Tier 0 immortal. Re-evaluate before v0.3 ship. *2026-05-12.*
- **[seaweedfs.md](./seaweedfs.md)** — Watch item (SeaweedFS 4.23 bundled Iceberg REST Catalog probe); YELLOW — REST spec compliance verified, pyiceberg E2E blocked on a fixable auth coupling; ADR-008 + ADR-004 ladder stands. Re-probe at v0.3 milestone. *Worker, 2026-05-13.*
- **[ai_hallucinations.md](./ai_hallucinations.md)** — Append-only log of AI-fabricated APIs caught during development per AGENTS.md §11.12. Add a new entry on every catch.

## Strategic research (positioning, not wrapped libraries)

Inputs to ADR-002 (Mid-2026 Strategic Refresh).

- **[strategic/ai_agent_data_infra_2026.md](./strategic/ai_agent_data_infra_2026.md)** — Market reality check on AI/agent positioning angles C/D vs. status quo angle A. *2026-05-12.*
- **[strategic/competitive_landscape_2026.md](./strategic/competitive_landscape_2026.md)** — Five positioning angles (A-E) competitive analysis; recommends combined B+E pitch. *2026-05-12.*
- **[strategic/solo_oss_patterns_and_iceberg_2026.md](./strategic/solo_oss_patterns_and_iceberg_2026.md)** — Solo OSS execution patterns + Iceberg ecosystem maturity 2026. *2026-05-12.*

---

*Last updated 2026-05-13 (alignment sweep #1). Add new research files here as they land — keep entries to one line, group by tier, and link `docs/swap/<component>.md` from the anchor (not from this index).*
