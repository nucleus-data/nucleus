# ADR-019: Snowflake Source Connector via dlt `sql_database`

**Status**: ACCEPTED
**Date**: 2026-05-15
**Author**: Builder (connector expansion wave)
**Reviewers**: Founder (ratification gate)
**Related**: ADR-014 (Postgres/MySQL via dlt), ADR-005 (API stability tiers)

---

## Context

Nucleus v0.1 ships Postgres, MySQL, and SQLite source connectors. Snowflake is the most-requested enterprise source in the beachhead persona (5-engineer startup on 100GB-5TB). Without a Snowflake connector, users who have data in Snowflake cannot onboard without a manual export step.

The `dlt` library already wraps Snowflake via its `sql_database` verified source using SQLAlchemy + `snowflake-sqlalchemy`. The wrap cost is minimal (<150 LOC) and the error translation follows the established Postgres/MySQL pattern.

Ratified 2026-05-15: code shipped in commit a41a82c (v0.2.0 handover bundle).

---

## OSS Options Considered

| Option | License | Why rejected |
|--------|---------|-------------|
| `snowflake-connector-python` (direct) | Apache-2.0 | Would require building our own cursor → Arrow pipeline; dlt already does this correctly and is already pinned as a core dep |
| `dlt[snowflake]` (chosen) | Apache-2.0 | Same `sql_database` verified source used for Postgres/MySQL; adds ~60 MB optional dep (snowflake-connector-python + snowflake-sqlalchemy); mirrors existing ADR-014 pattern |
| Custom SQLAlchemy connector | — | BUILD not WRAP; violates AGENTS.md §4 |

---

## Decision

**WRAP `dlt[snowflake]` as the Snowflake source connector.** Specifically:

1. Add `dlt[snowflake]==1.26.0` to `[project.optional-dependencies] snowflake` (users install via `pip install nucleus[snowflake]`).
2. Implement `src/nucleus/ctx/copy_from_snowflake.py` mirroring the Postgres connector pattern verbatim.
3. Add `_translate_dlt_snowflake_exception` to `src/nucleus/coordination/error_translation.py`.
4. Expose `ingest_snowflake_to_iceberg()` in `nucleus.ctx` + `copy_from("snowflake://...")` dispatcher path.

### Scope (v0.1)

- **In**: Single table per call, `append` + `replace` write dispositions, username/password auth.
- **Out**: SSO/key-pair/OAuth auth (deferred to v0.5+ per ADR-010), incremental watermarks, multi-table pipelines.
- **URL format**: `snowflake://user:pass@orgname-accountname/database/schema?warehouse=WH`

---

## Consequences

- **LOC budget impact**: ~150 LOC (`copy_from_snowflake.py` + error translator additions).
- **Optional dep**: `dlt[snowflake]==1.26.0` + transitively `snowflake-connector-python` (~60 MB, C extensions). This is opt-in only — base `pip install nucleus` is unaffected.
- **License**: `snowflake-connector-python` is Apache-2.0 · GREEN. `snowflake-sqlalchemy` is Apache-2.0 · GREEN.
- **Maintenance ownership**: connector expansion builder; error translator owned by coordination layer.
- **Swap target**: if `dlt` is swapped per `docs/swap/dlt.md`, the Snowflake connector must be re-implemented. The swap interface is `ingest_snowflake_to_iceberg(conn_str, source_table, ...)`.
- **Tests**: 10 unit tests in `tests/ctx/test_copy_from_snowflake.py`; no real Snowflake account required (dlt mocked).
- **Upgrade smoke**: add `tests/upgrade_smoke/test_dlt_snowflake.py` before next `dlt` version bump.

---

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §5.5 (Ingestion — connector expansion)
- `nucleus_architecture_v4.1.md` §6.4 (Error Translation Discipline)
- `docs/research/snowflake.md` (pre-integration research per Constraint #10)
- `docs/compatibility.md` (optional dep row added)
- `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` (optional dep row added)
