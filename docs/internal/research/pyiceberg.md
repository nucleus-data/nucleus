# Research: PyIceberg

> **Pinned**: `pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1`
> **Verified**: 2026-05-12
> **Docs**: https://py.iceberg.apache.org/  •  **Repo**: https://github.com/apache/iceberg-python
> **Used in**: `src/nucleus/physics/`, `src/nucleus/coordination/`. ADR-001 delegates atomic commits here.

Single research anchor for PyIceberg per AGENTS.md Hard Constraint #10. Terse, link-heavy. Read before M1.2 (Iceberg module), PoC #1, and any Tier 0 Heartbeat code. **Do not write Iceberg code from memory — start here.**

---

## §1. At a glance

- Apache Software Foundation; Apache 2.0 license. Broad industry investment (AWS, Tabular, Dremio).
- Pure-Python implementation of the [Iceberg table spec](https://iceberg.apache.org/spec/). **No JVM** — satisfies Constraint #1.
- Tier 0 dependency in Nucleus (immortal, like Arrow / Iceberg / Parquet).
- Our pin: `pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1`. Extras: `sql-sqlite` (SqlCatalog on SQLite); `s3fs` (S3/MinIO FileIO); `duckdb` (zero-copy `to_duckdb(...)`).
- One-line: direct Python read/write/commit access to Iceberg tables, no JVM. The **only** library Nucleus uses to write tables.

---

## §2. Version verification (2026-05-12)

Source: `https://pypi.org/pypi/pyiceberg/0.8.1/json` + `https://pypi.org/simple/pyiceberg/`.

| Fact | Value |
|---|---|
| `0.8.1` real release | ✓ Yes (uploaded 2024-11-27) |
| Yanked? | ✗ No |
| Python (0.8.1) | 3.9-3.13 — our 3.11/3.12 pin inside ✓ |
| PyArrow constraint | `<19.0.0,>=14.0.0` — our `18.1.0` inside ✓ |
| Windows wheels | ✓ Yes (`cp311-win_amd64`, `cp312-win_amd64`) |
| License | Apache-2.0 |
| Latest stable on PyPI | **0.11.1** (also: 0.9.0, 0.9.1, 0.10.0, 0.11.0) |
| Distance from latest | **3 minor versions behind** |

**Implication**: 0.8.1 was the right pin at project-start but is now stale. Per Constraint #11 and `docs/compatibility.md`, the 0.8.1 → 0.9.x upgrade is queued and requires a migration ADR — PyIceberg's Schema and write APIs have churned across 0.8 → 0.11. **Do not upgrade unilaterally.** Wait for the planned ADR + smoke test.

---

## §3. Why Nucleus uses PyIceberg

- **Layer**: L0 (Physics). Wrapped at L2 by the Asset Materialization Adapter.
- **Only way Nucleus writes tables** — Constraint #4 forbids a custom table format.
- **Atomic commits delegated** — per [ADR-001](../decisions/ADR-001-no-iceberg-commit-service.md), no custom commit service. PyIceberg + its configured catalog handle atomicity.
- **Catalog-pluggable from day 1** — filesystem (v0.1) → SQL (v0.3) → REST/Lakekeeper (v0.3+) is a config swap, not a code rewrite. Satisfies Constraint #9.
- **Graduation-friendly** — tables are bit-identical to those written by Spark/Trino/Snowflake/Databricks. Yield-to-giants Mode 1 free.
- **Alternative rejected for v0.1**: [iceberg-rust](https://github.com/apache/iceberg-rust) — fewer catalog backends, less mature write path. Tracked as a long-horizon swap target.

---

## §4. Core concepts

- **Iceberg spec v2** — the format version we read/write. PyIceberg 0.8.x writes v2 by default. See [spec](https://iceberg.apache.org/spec/).
- **Iceberg spec v3** — adds `timestamp_ns`, `timestamptz_ns`, geo, default values, variant. **Not used in v0.1**; revisit when PyIceberg v3 write support is stable (post-v0.5).
- **Schema / NestedField** — column model. Each field has an immutable integer ID, a name, a type, a nullable flag. Field IDs (not names) are the source of truth for evolution. See [`pyiceberg.schema`](https://py.iceberg.apache.org/api/#schemas).
- **Catalog** — maps `(namespace, table) → metadata_location`. Owner of atomic commits. See [Catalog API](https://py.iceberg.apache.org/configuration/#catalogs).
- **`SqlCatalog`** (SQLite/Postgres-backed) — our v0.1 default catalog uses `SqlCatalog` with a SQLite URI; v0.3+ swaps the URI to Postgres for shared dev.
- **`RestCatalog`** — Lakekeeper, Polaris, Tabular, Unity Catalog (v0.3+). See [REST catalog spec](https://iceberg.apache.org/spec/#rest-catalog-spec).
- **Table** — runtime handle returned by `Catalog.load_table(...)`. All ops go through it.
- **Snapshot** — immutable point-in-time (manifest list + timestamp + parent snapshot ID). One per commit.
- **Manifest** — file listing data files belonging to a snapshot, with per-file stats. Manifest list = list of manifests.
- **Metadata file** (`vN.metadata.json`) — the atomically-swapped pointer. The catalog's job is to swap it atomically.
- **PartitionSpec** — declares transforms (`identity`, `bucket`, `truncate`, `year`, `month`, `day`, `hour`). Evolvable: spec can change; old snapshots keep their original spec.
- **FileIO** — storage abstraction (`LocalFileSystem`, `S3FileSystem` via `s3fs`, `GCSFileSystem` via `gcsfs`, etc.). Wraps `fsspec`.
- **Transaction** — `Table.transaction()` context manager batches multiple ops (append + schema update + spec update) into a single atomic commit. See [transactions](https://py.iceberg.apache.org/api/#transactions).

---

## §5. Critical API surface

The minimal set Nucleus calls. Cite docs URL alongside each call in source code.

Catalog (see [Catalog API](https://py.iceberg.apache.org/api/#catalogs)):

- `pyiceberg.catalog.load_catalog(name, **config) -> Catalog` — entrypoint; reads `~/.pyiceberg.yaml` or kwargs.
- `Catalog.create_namespace(namespace, properties=None)`
- `Catalog.create_table(identifier, schema, *, location=None, partition_spec=None, sort_order=None, properties=None) -> Table`
- `Catalog.load_table(identifier) -> Table` / `Catalog.table_exists(identifier) -> bool`

Table (see [Table API](https://py.iceberg.apache.org/api/#tables)):

- `Table.append(df: pa.Table)` — single-snapshot append from Arrow.
- `Table.overwrite(df: pa.Table, overwrite_filter=AlwaysTrue())` — replace matching rows.
- `Table.scan(row_filter=AlwaysTrue(), selected_fields=("*",), snapshot_id=None, limit=None) -> DataScan`. Materialize via `.to_arrow()`, `.to_arrow_batch_reader()` (streaming, per `engineering.md` §11.3 for >100 MB), `.to_polars()`, `.to_duckdb(table_name, connection=None)` (zero-copy registration).
- `Table.refresh()` — re-read metadata from catalog (required before reading if another writer has committed).
- `Table.snapshots()` / `Table.current_snapshot()` / `Table.history()`
- `Table.transaction() -> Transaction` — batch container. Then `.append(...)`, `.overwrite(...)`, `.update_schema(...)`, `.update_spec(...)`, finally `.commit_transaction()`.
- `Table.update_schema() -> UpdateSchema` — fluent schema-evolution builder. See [schema evolution](https://py.iceberg.apache.org/api/#schema-evolution).

Vocabulary (per `engineering.md` §15): **tables** when raw Iceberg, **assets** when wrapped by `ctx.asset`.

---

## §6. Exception types we'll translate (critical for PoC #1)

All defined in [`pyiceberg.exceptions`](https://py.iceberg.apache.org/api/#exceptions). Mappings authoritative in [`sequence_error_translation.md` §4.4](../architecture/sequence_error_translation.md).

| PyIceberg exception | When raised | NucleusError target | Note |
|---|---|---|---|
| `NoSuchTableError` | `Catalog.load_table(...)` on missing identifier | `NucleusAssetNotMaterialized` | distinct from "not defined" |
| `NoSuchNamespaceError` | namespace ops on missing namespace | `NucleusCatalogError` | may auto-create or instruct |
| `CommitFailedException` | optimistic-concurrency conflict on commit | `NucleusCommitConflictError` | **retry candidate** — `tenacity`, max 3, exp backoff |
| `CommitStateUnknownException` | network failure mid-commit; swap landed status unknown | `NucleusCommitUnknownError` | **DO NOT retry blindly**; user verifies catalog state |
| `ValidationError` | invalid schema evolution (drop required, narrow type, nullable→required) | `NucleusSchemaEvolutionError` | translator explains violated rule |
| `AuthorizationExpiredError` | cloud creds expired (S3, REST) | `NucleusAuthError` | not our auth problem (Constraint #6) |

Lower-priority types (still translate, just less critical for v0.1):

- `TableAlreadyExistsError`, `NamespaceAlreadyExistsError`, `NamespaceNotEmptyError` → `NucleusCatalogError`.
- REST: `RESTError`, `BadRequestError`, `UnauthorizedError`, `ForbiddenError`, `ServerError`, `ServiceUnavailableError` → `NucleusCatalogError` or `NucleusAuthError` (route by HTTP code).
- `SignError` → S3 signing failure → `NucleusAuthError`.

> **AI-drift caveat (PoC #1 verifies on real instances)**: exact import paths (`pyiceberg.exceptions.X` vs `pyiceberg.X`), constructor signatures, and `__cause__` chaining for `CommitFailedException` must be confirmed by **actually triggering each exception** in PoC #1 — see `nucleus_poc_plan.md` and log any drift in `docs/internal/research/ai_hallucinations.md`. Do not register translators from this doc's class names alone. Import them, raise them, catch them, then write the translator.

---

## §7. Known gotchas / pitfalls

- **Timestamp precision**: spec v2 caps `timestamp`/`timestamptz` at **microseconds**. PyIceberg 0.8.x writes v2 by default. Nanosecond source data loses precision on ingest. Spec v3 adds `timestamp_ns`; revisit post-v0.5.
- **Filesystem-catalog atomicity on Windows**: filesystem-style catalogs rely on `os.rename` / `os.replace` for the metadata-pointer swap. Windows `os.rename` differs from POSIX (it can fail if target exists; `os.replace` is the cross-platform call). This is the **#1 risk** for ADR-001 on Windows; PoC #1 includes a kill-9 stress test on Windows + macOS + Linux.
- **Field IDs are immutable, names are not**: schema evolution tracks columns by integer field ID. Renaming preserves the ID. Dropping then re-adding the same name gets a new ID and reads `null` for old snapshots.
- **Schema-evolution rules** (see https://iceberg.apache.org/spec/#schema-evolution): ✓ add column (nullable for old snapshots), drop column, rename (ID preserved), widen type (`int`→`long`, `float`→`double`, `decimal(P,S)` widening `P`). ✗ narrow type; nullable→required; incompatible reorder of required fields.
- **`Table.refresh()` before concurrent reads**: in-memory `Table` goes stale after another writer commits. Refresh before reads in multi-process scenarios (v0.3+ on Lakekeeper). Rare in single-process v0.1.
- **PyArrow upper bound**: 0.8.x requires `pyarrow<19.0.0`. Bumping PyArrow to 19.x **forces** bumping PyIceberg first. Plan upgrades pairwise.
- **Partition columns must be primitive**: no struct/list/map in partition spec. Transforms consume primitive source fields.
- **`Table.append` requires schema-compatible Arrow**: column count, names, and types must match the table's current schema. Cast or project before calling; fail fast rather than auto-cast in the Adapter.
- **No multi-table transactions**: `Transaction` is per-table. Cross-table atomicity is not provided, and we will not build it (the whole point of ADR-001). Sequence commits and accept the brief inconsistency window.

---

## §8. Interaction with other Nucleus components

- **Ingest (write)**: source (Postgres/MySQL via SQLAlchemy + `ctx.copy_from`) → Arrow `RecordBatch` stream → `Table.append(arrow_table)`. Zero pandas hop, zero-copy through Arrow.
- **Query (read)**: `.to_duckdb("orders")` → DuckDB engine (L1) runs SQL; `.to_polars()` → Polars-DataFrame assets; `.to_arrow_batch_reader()` → streaming for >100 MB.
- **Asset Materialization Adapter** (`coordination/asset_materialization.py`, ~500 LOC) is the **only** module that calls PyIceberg. Per ADR-001, no separate commit service.
- **Catalog swap is config-only**: filesystem (v0.1) → Lakekeeper (v0.3+) changes `nucleus.toml` `[catalog]`, nothing in `src/`.
- **Error Translation Layer** registers translators for the §6 exceptions. AMA catches, hands to ETL with `ErrorContext`, returns a `NucleusError`. **No PyIceberg classname appears in user-facing text** — validated by `scripts/dagster_leak_check.py` (extended to `pyiceberg.` too).
- **Observability**: structured-log events `commit.attempted` / `commit.succeeded` / `commit.failed` / `commit.conflict_retry` wrap every `commit_transaction()`. OTel spans cover the same boundary.
- **Schema contracts**: `@nucleus.check` runs against post-scan Arrow; Iceberg's schema is the source of truth for column IDs and nullability. Drift → `NucleusSchemaError`.

---

## §9. Upgrade considerations

When planning the 0.8.1 → 0.9.x upgrade (ADR required, Constraint #11):

- **Schema API churn**: 0.8 → 0.9 changed parts of `Schema` construction and `UpdateSchema`. Read https://github.com/apache/iceberg-python/releases per minor.
- **`SqlCatalog` URI parsing** has tightened across 0.9-0.11. Smoke test with real SQLite + Postgres.
- **PyArrow envelope**: re-check the upper bound on every upgrade. Re-pin pairwise.
- **Spec v3 readiness**: ask "is this minor the first to write v3 by default?" Defer until our downstream consumers (BI tools, Spark, Trino) all read v3.
- **Required pre-upgrade artifacts**: changelog summary in PR; `pytest tests/upgrade_smoke/test_iceberg_upgrade.py` green on Win + macOS + Linux; rollback command (`pip install pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1`); major-version bump → ADR + benchmark re-run + canary flag.
- **Cadence**: one component per PR; 24 h between merges (Constraint #11). Never bulk-upgrade PyIceberg + Dagster + DuckDB in one go.

---

## §10. Useful links

- [PyIceberg docs root](https://py.iceberg.apache.org/) — start here
- [API reference](https://py.iceberg.apache.org/api/) (catalog + table + scan + transaction)
- [Exceptions reference](https://py.iceberg.apache.org/api/#exceptions) — the §6 classes
- [Catalog configuration](https://py.iceberg.apache.org/configuration/)
- [Iceberg table spec (v2 + v3)](https://iceberg.apache.org/spec/) and [commit-concurrency contract](https://iceberg.apache.org/spec/#commit-concurrency) (basis for ADR-001)
- [Release notes / changelog](https://github.com/apache/iceberg-python/releases) • [GitHub source](https://github.com/apache/iceberg-python) • [PyPI project](https://pypi.org/project/pyiceberg/)

---

*Maintained by: Solo founder. Next review trigger: any PyIceberg upgrade PR, or when an ADR is opened to bump 0.8.1 → 0.9.x. Log hallucinated PyIceberg APIs caught in review in [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
