# ADR-020: Object-Storage + Filesystem Connectors via DuckDB (PROPOSED)

**Status**: PROPOSED — awaiting founder ratification
**Date**: 2026-05-15
**Author**: Builder (connector expansion wave)
**Reviewers**: Founder (ratification gate)
**Related**: ADR-014 (SQL connectors via dlt), ADR-008 (storage substrate), ADR-005 (API stability)

---

## Context

Beyond SQL databases, the most common data sources for the beachhead persona (5-engineer startup, 100GB-5TB) are:

1. **S3 Parquet/CSV/JSON files** — data lake drops from ETL pipelines
2. **GCS Parquet/CSV/JSON files** — same pattern on Google Cloud
3. **Local filesystem files** — CSV exports, Parquet from Pandas/Polars jobs, ad-hoc data

These sources share a common pattern: read a file (or glob) → Arrow table → Iceberg append. No SQL schema reflection, no cursors, no connection pools. DuckDB 1.1.x handles all three natively via:

- `read_parquet()`, `read_csv_auto()`, `read_json_auto()` with local, S3 (`s3://`), and GCS (`gs://`) URIs
- `httpfs` extension (bundled, no install required) for S3
- `register_filesystem()` + `gcsfs` for GCS ADC credentials
- Glob patterns: `./data/*.parquet`, `s3://bucket/prefix/*.parquet`

DuckDB is already a core dep (`duckdb==1.1.3`). S3 support adds zero deps. GCS support requires one optional dep (`gcsfs==2026.5.0`).

---

## OSS Options Considered

| Option | License | Why rejected / chosen |
|--------|---------|----------------------|
| `dlt` file sources | Apache-2.0 | dlt is already in core, but its file sources (filesystem destination) are designed for structured pipeline state, not ad-hoc file bulk-reads; adds unnecessary complexity |
| `pyarrow.parquet.read_table` + `s3fs` | Apache-2.0 / BSD | Viable for S3 only; less ergonomic for CSV/JSON; already accessible through DuckDB's zero-copy Arrow export |
| `polars.read_parquet('s3://...')` | MIT | Polars can read S3 but requires boto3 for ADC; no GCS ADC support without gcsfs; less composable than DuckDB approach |
| **DuckDB `read_parquet/csv/json`** (chosen) | MIT | Already in core; handles all three formats; S3 built-in via httpfs; GCS via `gcsfs` + `register_filesystem`; zero-copy Arrow export; glob natively; unified across S3/GCS/local |

---

## Decision

**WRAP DuckDB's file-reading functions for all three object-storage / filesystem connectors.** Three sub-connectors under one umbrella:

### Sub-connector 1: S3 Object Source

- `src/nucleus/ctx/copy_from_s3.py`
- DuckDB httpfs extension (bundled); reads AWS credentials from env vars (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`) automatically
- No new dependencies (s3fs already in core via pyiceberg)
- Dispatcher: `copy_from("s3://bucket/file.parquet", target="ns.table", ...)`
- Direct: `ingest_s3_to_iceberg("s3://bucket/file.parquet", ...)`

### Sub-connector 2: GCS Object Source

- `src/nucleus/ctx/copy_from_gcs.py`
- DuckDB + `gcsfs==2026.5.0` (optional dep: `pip install nucleus[gcs]`)
- `gcsfs.GCSFileSystem()` provides ADC credential chain; registered with DuckDB via `conn.register_filesystem(pyarrow.fs.PyFileSystem(FSSpecHandler(gcs)))`
- Dispatcher: `copy_from("gs://bucket/file.parquet", target="ns.table", ...)`
- Direct: `ingest_gcs_to_iceberg("gs://bucket/file.parquet", ...)`

### Sub-connector 3: Local Filesystem Bulk Ingest

- `src/nucleus/ctx/copy_from_filesystem.py`
- DuckDB reads local files natively; no extensions required
- Supports globs: `./data/*.parquet`
- Supports `file://` URI prefix (stripped before passing to DuckDB)
- Dispatcher: `copy_from("./data/orders.parquet", target="ns.table", ...)` or `copy_from("file:///abs/path/file.csv", ...)`
- Direct: `ingest_filesystem_to_iceberg("./data/*.parquet", ...)`

### Common pattern across all three

- Format auto-detection from file extension; `format=` override
- `union_by_name=true` for glob patterns (mixed schemas raise `NucleusSchemaError`)
- Arrow zero-copy: `conn.execute(query).arrow()` → `iceberg_table.append(arrow_table)`
- Error translation to `NucleusError` subclasses (no DuckDB classnames in user messages)

---

## Consequences

- **LOC budget impact**: ~400 LOC total (three connectors + error translators). LOC at 82.3% of v0.1 ceiling after expansion.
- **New optional dep**: `gcsfs==2026.5.0` (BSD-3-Clause · GREEN) in `[project.optional-dependencies] gcs`. All other connectors add zero deps.
- **Maintenance**: connectors follow same error-translation pattern as Postgres/MySQL; DuckDB upgrade path documented in `docs/swap/duckdb.md`.
- **Swap target**: if DuckDB is swapped, the swap implementation reads `pyarrow.parquet.read_table` + `pyarrow.fs` as the fallback. Smoke tests in `tests/swap/test_duckdb_swap.py` already exist.
- **Tests**: 10 unit tests per connector (30 total in `tests/ctx/`). No real cloud accounts required (DuckDB mocked).
- **Known limitation**: IAM role / instance profile credentials for S3 require `SET s3_use_credential_chain=true` in DuckDB, which the caller must enable via env var passthrough; Nucleus does not invoke this automatically (no custom credential code per task spec).

---

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §5.5 (Ingestion — object storage expansion)
- `nucleus_architecture_v4.1.md` §6.4 (Error Translation Discipline)
- `docs/research/s3_duckdb.md`, `docs/research/gcs_duckdb.md`, `docs/research/filesystem_duckdb.md`
- `docs/compatibility.md` (new optional dep row for `gcsfs`)
- `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` (optional dep row added)
