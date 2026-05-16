---
name: nucleus-wrapped-api-verify
description: >-
  Verify wrapped-library API surface before suggesting code. Use when about to
  suggest, write, or modify code calling pyiceberg, dagster, duckdb, polars,
  dlt, sqlglot, pyarrow, openlineage, soda-core, lance, lancedb, daft, or any
  wrapped Tier 0/1/2 dependency listed in `nucleus_architecture_v4.1.md` §4-§5.
---

# Wrapped-Library API Verification

AI memory drifts. Pins lag. Wrapped libraries evolve faster than expected.
This skill enforces `@AGENTS.md §11.12` (read official docs before
integration) and `@AGENTS.md §11.13` (one-component-per-PR upgrades).

## Required before suggesting any wrapped-library call

1. **Cite the docs URL inline**: every external import gets a docs-URL
   comment. Pattern from `@AGENTS.md §11.12`:
   ```python
   from pyiceberg.catalog import load_catalog
   # Docs: https://py.iceberg.apache.org/api/catalog/
   ```
2. **Pin-aware**: verify the API exists in the pinned version (per
   `pyproject.toml` and `@docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md`),
   NOT "latest". The pin is the ground truth.
3. **Uncertain? Flag it.** Write `# NEEDS VERIFICATION:` inline and surface
   to the user. Never fabricate APIs that "should exist".
4. **Major version mismatch = refuse.** If the suggested method belongs to
   `X+1.y` while the pin is `X.y.z`, stop and cite Hard Constraint #11
   (`@AGENTS.md §11.13`). Major upgrades require an ADR.

## Per-library research doc index

`@docs/internal/research/README.md` is the master index. Each anchor carries pin,
license, surface area, known hallucinations, and the live docs URL. Read
the relevant anchor before writing code that imports the library:

- Tier 0: `@docs/internal/research/pyiceberg.md`, `@docs/internal/research/pyarrow.md`,
  `@docs/internal/research/openlineage.md`, `@docs/internal/research/opentelemetry.md`,
  `@docs/internal/research/lance.md`
- Tier 1: `@docs/internal/research/duckdb.md`, `@docs/internal/research/polars.md`,
  `@docs/internal/research/sqlglot.md`, `@docs/internal/research/dlt.md`,
  `@docs/internal/research/daft.md`, `@docs/internal/research/soda.md`,
  `@docs/internal/research/dbt-duckdb.md`, `@docs/internal/research/marimo.md`
- Tier 2: `@docs/internal/research/dagster.md`

## Known hallucinations — never repeat

Cite by name when rejecting AI-suggested usages. Full entries with detection
and fix are in `@docs/internal/research/ai_hallucinations.md`.

- `pyiceberg.commit_atomic()` — does NOT exist. Use `Catalog.commit_table()`
  + app-level coordination (per `@docs/decisions/ADR-001-no-iceberg-commit-service.md`).
- `openlineage-dagster` (and `dagster-openlineage`) — DEAD package; caps at
  `dagster<=1.6.9`, removed from OpenLineage main repo Oct 2025. Emit
  OpenLineage events directly from the AMA per
  `@nucleus_architecture_v4.1.md §6.2` step 4.
- `quay.io/minio/minio:RELEASE.2025-10-15T17-29-55Z` — fabricated tag. Actual
  terminal release is `RELEASE.2025-09-07T16-13-09Z`.
- `dataframe.to_iceberg()` — fabricated. Not on Polars or PyArrow. Route
  writes through `pyiceberg` (`Catalog.create_table()` + `Table.append()`).
- Cross-pollinated pandas methods on Polars frames (`.iloc`, `.loc`,
  `.apply()` returning DataFrames). Polars has its own surface; check
  `@docs/internal/research/polars.md`.

## When you catch a new hallucination

Append to `@docs/internal/research/ai_hallucinations.md` using the established format:

```markdown
## YYYY-MM-DD: library.method_or_class

AI suggested: `<fabricated API>`
Reality: `<actual API or non-existent>`
Where caught: <PR # / file / commit>
Detection: <how>
Fix: <what we did>
```

The 2026-05-13 entries (Dagster `__cause__` shape, `openlineage-dagster`,
MinIO tag) are model entries.

## Bulk upgrade requests = refuse

If the user asks "upgrade all dependencies", split into one-component-per-PR
per `@AGENTS.md §11.13`. Suggest order by staleness from
`@docs/compatibility.md`. Never bulk-upgrade.
