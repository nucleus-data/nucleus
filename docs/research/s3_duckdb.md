# S3 Object Storage (DuckDB httpfs) Research Notes

> **Purpose**: Pre-integration research per AGENTS.md §11.12 (Constraint #10).
> **Component**: S3 → Iceberg ingest via `duckdb.read_parquet/read_csv/read_json` + httpfs
> **Date**: 2026-05-15
> **ADR**: ADR-020-object-storage-connectors-via-duckdb.md (PROPOSED)

---

## §1. Official Documentation Sources

| Source | URL |
|--------|-----|
| DuckDB httpfs extension overview | https://duckdb.org/docs/extensions/httpfs/overview |
| DuckDB S3 API docs | https://duckdb.org/docs/extensions/httpfs/s3api |
| DuckDB `read_parquet` | https://duckdb.org/docs/data/parquet/overview |
| DuckDB `read_csv_auto` | https://duckdb.org/docs/data/csv/overview |
| DuckDB `read_json_auto` | https://duckdb.org/docs/data/json/overview |
| DuckDB Python API `.arrow()` | https://duckdb.org/docs/api/python/result_conversion |
| PyArrow `write_to_dataset` | https://arrow.apache.org/docs/python/api.html |

---

## §2. DuckDB httpfs Extension

DuckDB 1.1.x ships with `httpfs` as a **core** (bundled) extension. It does **not** require `install_extension()` — only `load_extension("httpfs")` (or `LOAD httpfs` in SQL).

**Autoloading**: DuckDB 1.1.x has autoloading enabled by default. Referencing an S3 URI in a query automatically triggers httpfs loading. Explicit `LOAD httpfs` in code is still recommended for clarity.

---

## §3. S3 Credential Resolution

DuckDB httpfs reads credentials in this order (verified against DuckDB 1.1.x docs at §3.1):

1. **Explicit DuckDB settings** (`SET s3_access_key_id='...'`, etc.)
2. **Environment variables**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_SESSION_TOKEN`
3. **`~/.aws/credentials` file** (via AWS SDK chain — requires `SET s3_use_credential_chain=true` in DuckDB 1.1.x; NOT automatic)

**Nucleus v0.1 approach**: rely on environment variables (items 1-2 above). IAM roles / instance profiles require `SET s3_use_credential_chain=true` which the caller can configure via environment. The Nucleus connector does NOT read AWS credentials explicitly — it defers to DuckDB's resolution.

```sql
-- DuckDB 1.1.x: explicit httpfs load
LOAD httpfs;
-- After this, read_parquet('s3://...') works if AWS env vars are set
```

---

## §4. Supported File Formats and Auto-Detection

DuckDB reads these formats from S3:

| Format | DuckDB function | Extension |
|--------|----------------|-----------|
| Parquet | `read_parquet()` | `.parquet`, `.pq` |
| CSV | `read_csv_auto()` | `.csv`, `.tsv`, `.txt` |
| JSON (newline-delimited) | `read_json_auto()` | `.json`, `.ndjson`, `.jsonl` |

Nucleus auto-detects from file extension (case-insensitive). `format="auto"` is the default.

Glob patterns are supported: `s3://bucket/prefix/*.parquet`.

---

## §5. Arrow Zero-Copy Path

DuckDB query result → Arrow Table is zero-copy via:
```python
conn = duckdb.connect()
result = conn.execute("SELECT * FROM read_parquet('s3://...')")
arrow_table = result.arrow()  # Returns pyarrow.Table — zero-copy where possible
```

Arrow → pyiceberg.append is the write path (same as SQLite/Postgres connectors):
```python
iceberg_table.append(arrow_table)
```

---

## §6. Error Classification

| DuckDB Exception Class | Trigger | Nucleus Translation |
|-----------------------|---------|---------------------|
| `duckdb.IOException` | File not found, access denied, network | `NucleusIOError` or `NucleusSourceAuthError` |
| `duckdb.BinderException` | Schema mismatch, column not found | `NucleusSchemaError` |
| `duckdb.ConversionException` | Type coercion failure | `NucleusSchemaError` |
| `duckdb.OutOfMemoryException` | File too large for memory | `NucleusResourceError` |
| `duckdb.InvalidInputException` | Malformed file | `NucleusIOError` |

The `IOException` message pattern for S3 errors:
- `"403"` or `"Access Denied"` → `NucleusSourceAuthError`
- `"404"` or `"NoSuchKey"` or `"not found"` → `NucleusSourceNotFound`
- `"503"` or `"503 Slow Down"` → `NucleusNetworkError`
- Connection refused / DNS → `NucleusSourceConnectionError`

---

## §7. Known Limitations (v0.1)

1. **IAM role / instance profile credentials** require the caller to set `AWS_ACCESS_KEY_ID` from boto3 chain manually; DuckDB's `s3_use_credential_chain` is not triggered automatically.
2. **Glob schema union** — DuckDB unifies schemas across files via `union_by_name=true` option; mixed schemas raise `BinderException`.
3. **Streaming large files** — DuckDB reads fully into memory; no chunked-streaming in v0.1.
4. **Multi-part upload** — handled entirely by pyiceberg; Nucleus passes Arrow tables only.

---

## §8. License

`duckdb==1.1.3`: MIT · GREEN (already in core deps)
`s3fs==2026.4.0`: BSD-3-Clause · GREEN (already in core deps via pyiceberg[s3fs])
