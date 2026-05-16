# Swap target: dlt → Sling (primary) / Singer (secondary)

> **Tier**: 2 per `nucleus_architecture_v4.1.md` §3, §9.2 (Ingestion engine).
> **Current**: `dlt[sql_database,pyiceberg]==1.26.0` — **PINNED Stage 1 (2026-05-13, ADR-014)**. Postgres → Iceberg via `src/nucleus/ctx/copy_from_postgres.py`; MySQL → Iceberg via `src/nucleus/ctx/copy_from_mysql.py` (co-default landed 2026-05-14 per ADR-014 §"MySQL parity"; same `sql_database` source, +`pymysql==1.1.1` driver).
> **Swap target (primary)**: Sling (`sling-cli`) — MIT, Go-native single binary, JVM-free, lower connector breadth.
> **Swap target (secondary)**: Singer (taps + targets) — per-tap mixed licensing (some AGPL-3.0; audit gate at trigger time).
> **Stage 1 rollback (Path A)**: Native Postgres + MySQL branches on `ctx.copy_from` (~150 LOC each, SQLAlchemy + PyIceberg); triggers per §1 conditions below; see §1a.
> **Doc status**: Interface + Stage 1 implementation live (Postgres + MySQL). Full Sling/Singer adapter on-demand per v4.1 §9.3.

## 1a. Stage 1 rollback — Path A (native Postgres branch)

Per ADR-014 §Rollback. If dlt becomes unviable in Stage 1 (trigger conditions in §1 fire), the rollback is:

```bash
pip uninstall dlt
git revert <stage-1-pr>
```

Then implement path A: a native `ingest_postgres_to_iceberg(...)` in `src/nucleus/ctx/copy_from.py` mirroring the SQLite branch (~150 LOC SQLAlchemy + PyIceberg). The function signature and return type are identical; callers are unchanged.

**Trigger conditions for path A rollback** (fire ANY one):

- [ ] dltHub Inc. dissolves or `dlt-hub/dlt` main branch silent >12 months.
- [ ] Apache-2.0 → BSL / SSPL / AGPL pivot.
- [ ] Postgres→Iceberg throughput regresses >2x against Stage 1 baseline (`tests/upgrade_smoke/test_dlt_upgrade.py`).
- [ ] `import dlt` cold-start breaks `nucleus up <10s` boot target on lazy-import paths (PoC #4 regression).
- [ ] JVM dependency added to dlt core.

**Path A pre-sizing** (ADR-014 §2, Option A rejected-for-Stage-1 but documented for rollback):

```python
# ~150 LOC — mirrors ingest_sqlite_to_iceberg() shape verbatim.
# Uses: sqlalchemy==2.0.36 + psycopg[binary]==3.2.3 (already pinned) + pyiceberg.
# No new runtime dependencies; drops dlt==1.26.0.
# Reference: docs/internal/research/dlt.md §13.11 Q1.
def ingest_postgres_to_iceberg(conn_str, source_table, *, warehouse_dir, ...) -> int: ...
```

User-side data is unaffected — Iceberg tables remain readable (Tier 0 immortal substrate). No data migration required; the table format is the contract, dlt is the loader.

## 1. Trigger conditions

Per v4.1 §9.3, swap fires only on:

- [ ] **Vendor death / license pivot** — dltHub Inc. dissolves OR `dlt-hub/dlt` `main` silent >12 mo (single VC-backed concentration — `docs/internal/research/dlt.md` §8), OR Apache-2.0 → BSL/SSPL/AGPL.
- [ ] **Performance regression** — Postgres→Iceberg throughput regresses >2x against v0.3 baseline (`docs/internal/research/dlt.md` §6), OR `import dlt` cold-start breaks `nucleus up <10s` on lazy-import paths.
- [ ] **Community demand** — ≥30% of `@nucleus.source(engine="dlt")` users request Sling/Singer.
- [ ] **Constraint violation** — dlt adds JVM dep, drops `pyiceberg>=0.9.1` floor incompatible with our PyIceberg pin (`docs/internal/research/dlt.md` §7), or Iceberg destination drops partition-evolution / merge parity (§5.2).

## 2. Swap interface

`coordination/source_adapter.py` depends on this Protocol; `ctx` never imports `dlt` / `sling` / `singer` (v4.1 §6.4).

```python
# Sketch — implementation lands in src/nucleus/connectors/source_engine_protocol.py
# Per v4.1 §5.5.

from typing import Protocol
import pyarrow as pa


class SourceEngineProtocol(Protocol):
    @classmethod
    def from_definition(cls, source_def: "SourceAssetDef") -> "SourceEngineProtocol": ...
    def discover(self) -> list["ResourceDescriptor"]: ...
    def materialize(
        self,
        resource: "ResourceDescriptor",
        *,
        destination: "IcebergDestinationProtocol",
        cursor_state: "CursorState | None" = None,
    ) -> "MaterializationResult": ...


class ResourceDescriptor(Protocol):
    name: str
    write_disposition: str          # "append" | "replace" | "merge"
    primary_key: tuple[str, ...]
    incremental_key: str | None


class IcebergDestinationProtocol(Protocol):
    """Hand-off boundary. Commits routed through ADR-001."""
    def append(self, table_id: str, batch: pa.Table) -> "Snapshot": ...
    def merge(
        self, table_id: str, batch: pa.Table, *, on: list[str], strategy: str
    ) -> "Snapshot": ...


class CursorState(Protocol):
    """Per-resource incremental state; single Nucleus-owned location (§5 risk 1)."""
    resource_name: str
    last_value: object              # JSON-serializable per dlt convention
```

Critical methods: `from_definition`, `discover`, `materialize`, `IcebergDestinationProtocol.{append, merge}`, single-location `CursorState`. Out of scope: dlt `schema_contract` modes (Nucleus surfaces contracts via `@nucleus.check` per v4.1 §15), `dlt.current.*` introspection, Singer stdio state-streaming.

## 3. Smoke-test sketch (CI)

`tests/swap/test_source_engine_swap.py` *(TBD — lands when dlt enters as the v0.3 connector engine per ADR-014; v0.1's `ctx.copy_from` SQLite + Postgres paths are already exercised by `tests/cli/test_init.py` + `poc/p3_*` + the workbench API-surface suite, so this smoke test is a sketch in this doc rather than a current path on disk)*:

```python
import pytest


@pytest.fixture(params=["dlt", "sling", "singer", "copy_from"])
def source_impl(request):
    if request.param != "copy_from" and not _has_source_adapter(request.param):
        pytest.skip(f"{request.param} adapter not built; swap doc only (v4.1 §9.3).")
    return _load_source_engine(request.param)


def test_discover_lists_resources(source_impl): ...
def test_append_resource_produces_snapshot(source_impl): ...
def test_merge_upserts_on_primary_key(source_impl): ...
def test_incremental_cursor_advances_and_persists(source_impl): ...
def test_schema_drift_translates_to_NucleusSchemaError(source_impl): ...
def test_missing_table_translates_to_NucleusAssetNotFound(source_impl): ...
def test_credential_missing_translates_to_NucleusConfigError(source_impl): ...
```

7 tests across all four engines. `ctx.copy_from` runs in every CI build — keeps the interface honest when no full adapter exists.

## 4. Swap-cost estimate

| Phase | Sling | Singer |
|---|---|---|
| Protocol formalization + dlt adapter cleanup | 2 days | 2 days |
| Subprocess wrapper (`sling run` YAML / Singer tap+target stdio) | 5 days | 7 days |
| Iceberg write path (Sling Parquet → commit / target-iceberg audit) | 4 days | 6 days |
| Incremental cursor + state migration from dlt's dual store | 5 days | 8 days |
| Schema-drift + error translation + benchmark | 6 days | 6 days |
| Per-tap license audit (Singer only — some AGPL-3.0) + docs | 1 day | 3 days |
| **Total LOC** | **~1500-2500** | **~2500-4000** |
| **Total calendar time** | **~4 weeks** | **~6 weeks** |

**Default trigger response**: Sling first, Singer only if connector-breadth forces it. v0.1 `ctx.copy_from` stays as escape hatch for sources neither covers.

## 5. Critical risks specific to this swap

1. **State-location reconciliation — THE central design risk.** Per `docs/internal/research/dlt.md` §5.3 (KEY FINDING), dlt holds state in two places: `~/.dlt/pipelines/<name>/state.json` *and* a `_dlt_pipeline_state` table at the destination. Sling uses one state file; Singer uses state.json over stdio. **Mid-flight migration loses cursors** unless the script reads BOTH dlt stores, reconciles, and writes Nucleus-owned `CursorState` before the first Sling/Singer run. Trigger-time cost: 3-5 days; one shot to get right.
2. **Iceberg write-path depth.** dlt's `filesystem + table_format="iceberg"` calls PyIceberg directly (`docs/internal/research/dlt.md` §5.2). Sling/Singer typically stage Parquet first then load into Iceberg (`target-iceberg` for Singer; Sling Iceberg maturity unverified). Partition evolution, merge upserts, schema-evolution-with-merge — parity-tested at trigger time.
3. **Connector breadth gap.** dlt 8000+ sources (`docs/internal/research/dlt.md` §1); Sling <100; Singer 600+ mixed quality. Some user source assets may have no Sling tap — `ctx.copy_from` fallback or custom Python required.
4. **Schema-contract + license audit.** dlt ships `evolve / freeze / discard_value / discard_row` modes (`docs/internal/research/dlt.md` §5.4); Sling has `add_new_columns`; Singer relies on per-tap schemas. Nucleus routes user contracts through `@nucleus.check` (v4.1 §15) so engine-level is best-effort. Singer-only: taps independently licensed with AGPL-3.0 entries (`docs/internal/research/dlt.md` §8) — each shipped tap audited individually.

## 6. Cited docs

- Current (dlt): https://dlthub.com/docs/intro (subpages `/general-usage/{pipeline,state}`, `/dlt-ecosystem/destinations/iceberg`)
- Swap targets: https://docs.slingdata.io/ • https://github.com/slingdata-io/sling • https://www.singer.io/ • https://github.com/MeltanoLabs
- Research: `docs/internal/research/dlt.md` • `docs/internal/research/pyiceberg.md` §B.3
- Related: `docs/decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md` • `docs/swap/pyiceberg.md` §7

## 7. NEEDS VERIFICATION

- **Dual-state migration script.** §5 risk 1 sketched but not implemented. Requires running real dlt pipelines, reconciling `_dlt_pipeline_state` with `~/.dlt/pipelines/<name>/state.json`, and demonstrating zero cursor loss on a Postgres source — highest-priority verification.
- **Sling Iceberg destination maturity.** Whether `sling run --tgt-conn iceberg` ships native writes through PyIceberg / Lakekeeper REST, or stages Parquet + manual register-table. If staged-Parquet-only, §4 row 3 grows by 3-4 days.
- **Singer `target-iceberg` quality + ADR-001 atomicity.** Whether a canonical `target-iceberg` exists, its commit semantics, and single-table-atomicity compliance. Expect to write or fork.
- **`ctx.copy_from` always-live parity.** Confirm v0.1 `SourceEngineProtocol` for `ctx.copy_from` matches the v0.3 dlt adapter — if they drift, the §3 matrix loses its in-house baseline and Constraint #9 is hollow.
- **PyIceberg floor.** dlt's `pyiceberg>=0.9.1` floor (`docs/internal/research/dlt.md` §7); if swap fires **before** ADR-003 lands, the dlt path is already broken. Sequence after ADR-003 or document rollback to `ctx.copy_from`.
