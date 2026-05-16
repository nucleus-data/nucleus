# Swap Index

Per `docs/specs/nucleus_architecture_v4.1.md` §9.3 + AGENTS.md Hard Constraint #9 ("Composability by Constitution"), every Tier 1/2 wrapped component has a swap interface + smoke tests documented here. **Full adapters are built on-demand only** — when a trigger condition fires (vendor death, license pivot, perf regression >2×, community demand), not pre-emptively.

This file is a navigation index. Read the linked swap doc for the actual interface Protocol, trigger conditions, and migration steps. Smoke tests for v0.1 deps live at `tests/swap/` (duckdb/polars/dagster landed 2026-05-13); v0.3+ deps land their smoke tests there when promoted. Order below matches the composability constitution table in `docs/specs/nucleus_architecture_v4.1.md` §9.2 (Tier 0 substrate → Tier 1 engines → Tier 2 wrapped capabilities).

---

## Tier 0 — Storage substrate (format immortal; binding swappable)

- **[pyiceberg.md](./pyiceberg.md)** — PyIceberg → iceberg-rust (PyO3 binding). Trigger: `iceberg-python` dormant >12 mo / `Catalog.commit_table()` p99 >500 ms / spec-v3 lag >12 mo / JVM dep. Iceberg the **format** is Tier 0 immortal; the Python binding is the swap unit. Tier 0 format / Tier 1 binding, ~3 KB.

## Tier 1 — First-class engines (clean interface, on-demand swap)

- **[duckdb.md](./duckdb.md)** — DuckDB → Apache DataFusion. Trigger: vendor death / MIT→BSL pivot / TPCH-10GB >2× regression / `:memory:` >50 ms / Iceberg-extension health. Tier 1, ~3 KB.
- **[polars.md](./polars.md)** — Polars → Apache DataFusion DataFrame API. Trigger: vendor death / MIT→BSL pivot / 100M-row aggregation >2× regression / Arrow C-data zero-copy break. Tier 1, ~2.5 KB.
- **[lakekeeper.md](./lakekeeper.md)** — Lakekeeper → Apache Polaris (catalog co-default flip). Trigger: Vakamo abandons `main` >12 mo / Apache-2.0→BSL pivot / commit p99 >2× regression / spec-v3 divergence. Both co-default from v0.3 per ADR-002 §6 + ADR-004; data plane is shared via `pyiceberg.RestCatalog`. Tier 1, ~2.5 KB.

## Tier 2 — Wrapped capabilities (fully replaceable)

- **[dagster.md](./dagster.md)** — Dagster → `nucleus-mini-scheduler` (primary) / Prefect 3.x (fallback). Trigger: vendor death / Apache-2.0→AGPL pivot / `nucleus up` >2× regression / PoC #1 fails ≥6/8 scenarios. Tier 2, ~3 KB.
- **[dlt.md](./dlt.md)** — dlt → Sling (primary) / Singer (secondary). Trigger: dltHub dissolves / Apache-2.0→AGPL pivot / Postgres→Iceberg >2× regression / `pyiceberg` floor incompat. v0.1's `ctx.copy_from` is the always-live floor; dlt enters at v0.3. Tier 2, ~3 KB.
- **[workbench.md](./workbench.md)** — Workbench sub-component swaps (xyflow ↔ Cytoscape, Monaco ↔ CodeMirror, FastAPI ↔ Litestar, web ↔ Tauri) within the Fork B custom React SPA decided by [ADR-016](../decisions/ADR-016-workbench-mvp.md). Each sub-swap is fully replaceable; v0.2 ships Fork B and treats the four sub-components as Tier 2. Tier 2, ~4 KB.

## Tier 3 — Optional capabilities (opt-in extras)

- **[litellm.md](./litellm.md)** — LiteLLM → vendor SDK direct (Anthropic SDK / OpenAI SDK / Ollama HTTP). Trigger: BerriAI dissolves / Apache-2.0→non-OSI pivot / provider-error translation gap / `nucleus chat` cost-meter regression. AI Copilot is v0.2+ Beta surface per [ADR-015](../decisions/ADR-015-ai-chat-mvp.md); LiteLLM is the install-everywhere wrapper and the only Tier 3 entry today. Tier 3, ~3 KB.

---

[← `docs/specs/nucleus_architecture_v4.1.md` §9](../specs/nucleus_architecture_v4.1.md) · [ADR-002 §6 (catalog co-default)](../decisions/ADR-002-positioning-decision-2026-05.md) · [ADR-004 (catalog migration)](../decisions/ADR-004-catalog-migration-v01-to-v03.md) · [ADR-015 (AI Chat MVP)](../decisions/ADR-015-ai-chat-mvp.md) · [ADR-016 (Workbench MVP)](../decisions/ADR-016-workbench-mvp.md)

*Last updated 2026-05-14 (alignment sweep #3 — added `workbench.md` (Tier 2, Fork B sub-component swaps) and `litellm.md` (Tier 3, v0.2 AI Copilot wrapper) to the index after they landed in `docs/swap/` but were not referenced here). Add new swap docs here as they land. Tier 0 substrates (Arrow, Iceberg the format, Parquet, Lance, S3 API, OpenLineage, OpenTelemetry) deliberately have no swap doc — they are the substrate, not the wrap.*
