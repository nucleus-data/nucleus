# Local Filesystem Ingest (DuckDB) Research Notes

> **Purpose**: Pre-integration research per AGENTS.md §11.12 (Constraint #10).
> **Component**: Local filesystem CSV/JSON/Parquet → Iceberg via `duckdb.read_parquet/read_csv/read_json`
> **Date**: 2026-05-15
> **ADR**: ADR-020-object-storage-connectors-via-duckdb.md (PROPOSED)

---

## §1. Official Documentation Sources

| Source | URL |
|--------|-----|
| DuckDB `read_parquet` | https://duckdb.org/docs/data/parquet/overview |
| DuckDB `read_csv_auto` | https://duckdb.org/docs/data/csv/overview |
| DuckDB `read_json_auto` | https://duckdb.org/docs/data/json/overview |
| DuckDB glob support | https://duckdb.org/docs/data/multiple_files/overview |
| DuckDB Python result conversion | https://duckdb.org/docs/api/python/result_conversion |

---

## §2. DuckDB Local File Reading

DuckDB 1.1.x reads local files natively without any extensions:

```python
import duckdb

conn = duckdb.connect()

# Parquet — single file or glob
arrow_table = conn.execute("SELECT * FROM read_parquet('./data/orders.parquet')").arrow()

# Parquet glob
arrow_table = conn.execute("SELECT * FROM read_parquet('./data/*.parquet')").arrow()

# CSV with auto-detection
arrow_table = conn.execute("SELECT * FROM read_csv_auto('./data/orders.csv')").arrow()

# JSON / NDJSON
arrow_table = conn.execute("SELECT * FROM read_json_auto('./data/orders.json')").arrow()
```

---

## §3. Glob Support

DuckDB supports glob patterns in file paths:

- `./data/*.parquet` — all parquet files in a directory
- `./data/**/*.parquet` — recursive
- `./data/2026-*/*.csv` — date-partitioned directories

**Schema unification across glob files**:
- DuckDB uses `union_by_name=true` (optional parameter) to unify columns by name rather than position
- When schemas differ across files, DuckDB raises `duckdb.BinderException`
- Nucleus raises `NucleusSchemaError` for schema mismatches in glob patterns

---

## §4. Format Auto-Detection

Extension → function mapping:

| Extension | DuckDB function | Notes |
|-----------|----------------|-------|
| `.parquet`, `.pq` | `read_parquet()` | Binary; zero-copy Arrow |
| `.csv`, `.tsv`, `.txt` | `read_csv_auto()` | Header auto-detected |
| `.json` | `read_json_auto()` | NDJSON supported |
| `.ndjson`, `.jsonl` | `read_json_auto()` | Alias for NDJSON |

Unknown extension → `NucleusConfigError` with fix_hint to pass `format="parquet"` or `format="csv"` or `format="json"`.

---

## §5. Path Handling

DuckDB accepts:
- Absolute paths: `/home/user/data/orders.parquet`
- Relative paths: `./data/orders.parquet` (relative to current working directory)
- `file://` URIs: DuckDB strips the `file://` prefix automatically
- Glob patterns with any of the above

Nucleus normalizes:
- `file://` prefix is stripped before passing to DuckDB
- Relative paths are passed as-is (DuckDB resolves from CWD)
- Path objects are converted to POSIX strings

---

## §6. Error Classification

| DuckDB Exception | Trigger | Nucleus Translation |
|-----------------|---------|---------------------|
| `duckdb.IOException` | File not found, permission denied | `NucleusIOError` or `NucleusPermissionError` |
| `duckdb.BinderException` | Schema mismatch across files | `NucleusSchemaError` |
| `duckdb.ConversionException` | Type coercion failure | `NucleusSchemaError` |
| `duckdb.InvalidInputException` | Malformed file (corrupt parquet, bad CSV) | `NucleusIOError` |
| `duckdb.OutOfMemoryException` | File too large for memory | `NucleusResourceError` |

The existing `translate()` function in `coordination/error_translation.py` handles `FileNotFoundError` and `PermissionError` which may surface from Python's os layer before DuckDB is called (e.g., path validation).

---

## §7. Known Limitations (v0.1)

1. **Mixed schemas** in glob patterns — raises `NucleusSchemaError`; use `format="parquet", union_by_name=True` for schema-flexible ingest (not exposed in v0.1 API surface).
2. **Windows paths** — DuckDB on Windows accepts both `C:/path/file.parquet` and POSIX-style paths; Nucleus converts Path objects to POSIX strings.
3. **Large files** — fully loaded into memory; no chunked streaming in v0.1.
4. **Relative path ambiguity** — relative paths resolve from CWD at call time; prefer absolute paths in production.

---

## §8. License

`duckdb==1.1.3`: MIT · GREEN (already in core deps)
