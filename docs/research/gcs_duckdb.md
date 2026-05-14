# GCS Object Storage (gcsfs + DuckDB) Research Notes

> **Purpose**: Pre-integration research per AGENTS.md §11.12 (Constraint #10).
> **Component**: GCS → Iceberg ingest via `gcsfs` + `duckdb.register_filesystem`
> **Date**: 2026-05-15
> **ADR**: ADR-020-object-storage-connectors-via-duckdb.md (PROPOSED)

---

## §1. Official Documentation Sources

| Source | URL |
|--------|-----|
| gcsfs official docs | https://gcsfs.readthedocs.io/en/latest/ |
| gcsfs API reference | https://gcsfs.readthedocs.io/en/stable/api.html |
| DuckDB `register_filesystem` (Python API) | https://duckdb.org/docs/api/python/dbapi |
| DuckDB GCS httpfs (HMAC mode) | https://duckdb.org/docs/extensions/httpfs/gcs |
| PyArrow FSSpec integration | https://arrow.apache.org/docs/python/filesystems.html#fsspec-filesystems |
| Google Application Default Credentials | https://cloud.google.com/docs/authentication/application-default-credentials |

---

## §2. gcsfs Overview

`gcsfs==2026.5.0` (current stable as of 2026-05-15) implements the Python `fsspec` filesystem interface for Google Cloud Storage.

**License**: BSD-3-Clause · GREEN (per ADR-007)
**Python compatibility**: `>=3.10` (satisfies Nucleus `>=3.11,<3.13`)

**GCSFileSystem construction**:
```python
import gcsfs

# Uses ADC — reads from:
#   1. GOOGLE_APPLICATION_CREDENTIALS env var (path to service account JSON)
#   2. gcloud application-default credentials (~/.config/gcloud/application_default_credentials.json)
#   3. Metadata server (GCE/GKE workload identity)
gcs = gcsfs.GCSFileSystem()
```

No custom credential code is needed — gcsfs handles the full ADC chain.

---

## §3. DuckDB + gcsfs Integration

DuckDB 1.1.x supports registering PyArrow filesystems via `conn.register_filesystem(fs)`. This allows DuckDB to read from any fsspec-compatible filesystem (including GCS) using `gs://` URIs.

```python
import duckdb
import gcsfs
import pyarrow.fs as pafs

conn = duckdb.connect()
gcs = gcsfs.GCSFileSystem()  # ADC chain
pa_fs = pafs.PyFileSystem(pafs.FSSpecHandler(gcs))
conn.register_filesystem(pa_fs)

# Now DuckDB can read gs:// URIs via gcsfs
arrow_table = conn.execute("SELECT * FROM read_parquet('gs://bucket/key.parquet')").arrow()
```

**`pafs.FSSpecHandler`** (pyarrow==18.1.0): bridges any fsspec filesystem to PyArrow's filesystem interface. Documented at https://arrow.apache.org/docs/python/filesystems.html#fsspec-filesystems.

**`conn.register_filesystem`** (duckdb==1.1.3): registered since DuckDB 0.7.0 per DuckDB release notes. Accepts a `pyarrow.fs.FileSystem` instance.

---

## §4. Authentication Chain

gcsfs ADC resolution order (per Google docs):
1. `GOOGLE_APPLICATION_CREDENTIALS` env var → service account JSON file
2. `~/.config/gcloud/application_default_credentials.json` (from `gcloud auth application-default login`)
3. GCE/GKE metadata server (workload identity)
4. Cloud Shell credentials

Nucleus v0.1 delegates entirely to gcsfs; no custom auth code.

---

## §5. Supported File Formats

Same auto-detection logic as S3 connector:

| Format | DuckDB function | Extension |
|--------|----------------|-----------|
| Parquet | `read_parquet()` | `.parquet`, `.pq` |
| CSV | `read_csv_auto()` | `.csv`, `.tsv`, `.txt` |
| JSON | `read_json_auto()` | `.json`, `.ndjson`, `.jsonl` |

Glob patterns: `gs://bucket/prefix/*.parquet` — supported via gcsfs glob + DuckDB.

---

## §6. Error Classification

| gcsfs/DuckDB Exception | Trigger | Nucleus Translation |
|-----------------------|---------|---------------------|
| `gcsfs.core.HttpError` (403) | Access denied | `NucleusSourceAuthError` |
| `gcsfs.core.HttpError` (404) | Object not found | `NucleusSourceNotFound` |
| `FileNotFoundError` (from gcsfs) | Bucket/path not found | `NucleusSourceNotFound` |
| `PermissionError` (from gcsfs) | IAM permission denied | `NucleusSourceAuthError` |
| `duckdb.IOException` | DuckDB IO layer error | `NucleusIOError` |
| `duckdb.BinderException` | Schema mismatch | `NucleusSchemaError` |
| Network timeout | gcsfs requests timeout | `NucleusNetworkError` |

---

## §7. Known Limitations (v0.1)

1. **gcsfs `HttpError`** — the class lives at `gcsfs.core.HttpError` or may surface as `aiohttp.ClientResponseError`; error translation walks the cause chain for status codes.
2. **Glob via gcsfs** — gcsfs glob API is async-first; synchronous access works via the `open_local_dir` path in DuckDB. For large buckets, listing can be slow.
3. **Streaming** — DuckDB reads fully into memory; no chunked streaming in v0.1.
4. **Requester-pays buckets** — not supported in v0.1 (requires `requester_pays=True` in gcsfs constructor).

---

## §8. License

`gcsfs==2026.5.0`: BSD-3-Clause · GREEN (new optional dep)
`duckdb==1.1.3`: MIT · GREEN (already in core)
`pyarrow==18.1.0`: Apache-2.0 · GREEN (already in core)
