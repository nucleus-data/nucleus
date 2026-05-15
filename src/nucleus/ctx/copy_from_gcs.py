"""GCS object storage → filesystem-Iceberg ingest helper — ``ctx.ingest_gcs_to_iceberg``.

Wraps ``duckdb.read_parquet`` / ``read_csv_auto`` / ``read_json_auto`` with GCS
URIs via ``gcsfs`` registered as a PyArrow filesystem in DuckDB. Uses the
Application Default Credentials (ADC) chain via gcsfs — no custom auth code.

The integration path: ``gcsfs.GCSFileSystem()`` → ``pyarrow.fs.PyFileSystem`` →
``duckdb.register_filesystem()`` → ``SELECT * FROM read_parquet('gs://...')`` →
Arrow table → pyiceberg append.

Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)

Architecture refs:
    nucleus_architecture_v4.1.md §5.5 (Ingestion — object storage branch)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/decisions/ADR-020-object-storage-connectors-via-duckdb.md (scope)
    docs/research/gcs_duckdb.md §3 (gcsfs + register_filesystem integration)

Pins/docs:
    duckdb==1.1.3 — https://duckdb.org/docs/api/python/dbapi
                    https://duckdb.org/docs/data/parquet/overview
    gcsfs==2026.5.0 — https://gcsfs.readthedocs.io/en/latest/
    pyarrow==18.1.0 — https://arrow.apache.org/docs/python/filesystems.html
    pyiceberg[sql-sqlite,s3fs,duckdb]==0.11.1 — https://py.iceberg.apache.org/api/
"""

from __future__ import annotations

import contextlib
from pathlib import Path, PurePosixPath
from typing import Literal

import duckdb
from pyiceberg.exceptions import (
    CommitFailedException,
    NamespaceAlreadyExistsError,
    TableAlreadyExistsError,
)

# gcsfs and pyarrow.fs are optional — activated by `pip install nucleus[gcs]`.
# Docs: https://gcsfs.readthedocs.io/en/latest/
#       https://arrow.apache.org/docs/python/filesystems.html#fsspec-filesystems
try:
    import gcsfs
    import pyarrow.fs as pafs

    _GCS_AVAILABLE = True
except ImportError:
    gcsfs = None  # type: ignore[assignment]
    pafs = None  # type: ignore[assignment]
    _GCS_AVAILABLE = False

from nucleus.ctx.copy_from import _open_catalog
from nucleus.errors import (
    NucleusCommitConflictError,
    NucleusConfigError,
    NucleusError,
    NucleusIOError,
    NucleusNetworkError,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSourceAuthError,
    NucleusSourceNotFound,
)

__all__ = ["ingest_gcs_to_iceberg"]

_FORMAT_TO_DUCKDB_FN: dict[str, str] = {
    "parquet": "read_parquet",
    "csv": "read_csv_auto",
    "json": "read_json_auto",
}

_EXTENSION_TO_FORMAT: dict[str, str] = {
    ".parquet": "parquet",
    ".pq": "parquet",
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "csv",
    ".json": "json",
    ".ndjson": "json",
    ".jsonl": "json",
}


def _detect_format(uri: str, explicit_format: str | None) -> str:
    """Resolve file format: explicit override wins; otherwise infer from extension."""
    if explicit_format and explicit_format != "auto":
        if explicit_format not in _FORMAT_TO_DUCKDB_FN:
            raise NucleusConfigError(
                user_message=(
                    f"format={explicit_format!r} is not supported. "
                    f"Supported values: {sorted(_FORMAT_TO_DUCKDB_FN)} or 'auto'."
                ),
                fix_hint=(
                    "Pass format='parquet', format='csv', format='json', "
                    "or omit format for auto-detection from the file extension."
                ),
            )
        return explicit_format

    path_part = uri.split("?", maxsplit=1)[0].split("#", maxsplit=1)[0]
    suffix = PurePosixPath(path_part).suffix.lower()
    if suffix in _EXTENSION_TO_FORMAT:
        return _EXTENSION_TO_FORMAT[suffix]

    raise NucleusConfigError(
        user_message=(
            f"Cannot auto-detect file format from URI {uri!r} "
            f"(extension {suffix!r} is not recognised)."
        ),
        fix_hint=(
            "Pass an explicit format= keyword: format='parquet', format='csv', "
            "or format='json'. Supported extensions for auto-detection: "
            f"{sorted(_EXTENSION_TO_FORMAT)}."
        ),
    )


def _translate_duckdb_gcs_exception(exc: BaseException) -> NucleusError:
    """Translate a DuckDB/gcsfs GCS-source exception to a NucleusError.

    Walks the exception message and class for GCS-specific error patterns.
    No external class names reach user_message or fix_hint per AGENTS.md §11.7.

    Docs:
        https://gcsfs.readthedocs.io/en/stable/api.html (gcsfs errors)
        https://duckdb.org/docs/extensions/httpfs/gcs (DuckDB GCS httpfs)
    """
    msg = str(exc).lower()
    cls = type(exc).__name__
    mod = (type(exc).__module__ or "").lower()

    # Auth / access denied (GCS returns 403 for permission failures).
    if "403" in msg or "access denied" in msg or isinstance(exc, PermissionError):
        return NucleusSourceAuthError(
            user_message=(
                "Access to the GCS object was denied. "
                "Check your Google Cloud credentials and bucket permissions."
            ),
            fix_hint=(
                "Verify Application Default Credentials are configured: "
                "run 'gcloud auth application-default login' or set "
                "GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path. "
                "Confirm the IAM role includes 'roles/storage.objectViewer'."
            ),
            cause=exc,
        )

    # Object / bucket not found (HTTP 404).
    if "404" in msg or "not found" in msg or isinstance(exc, FileNotFoundError):
        return NucleusSourceNotFound(
            user_message=(
                "The GCS object or bucket was not found. Check the bucket name and object path."
            ),
            fix_hint=(
                "Verify the gs:// URI is correct and the object exists. "
                "Example: gs://my-bucket/data/orders.parquet"
            ),
            cause=exc,
        )

    # Network timeout / connectivity.
    if any(phrase in msg for phrase in ("timeout", "connection", "network", "dns")):
        return NucleusNetworkError(
            user_message=("Could not reach Google Cloud Storage. Check network connectivity."),
            fix_hint=(
                "Verify outbound HTTPS (port 443) to storage.googleapis.com is allowed. "
                "For service accounts, confirm the account has Storage access."
            ),
            cause=exc,
        )

    # Throttling / quota.
    if "429" in msg or "quota" in msg or "rate limit" in msg:
        return NucleusNetworkError(
            user_message=(
                "Google Cloud Storage returned a rate limit or quota error. "
                "Retry after a short wait."
            ),
            fix_hint=(
                "Reduce request rate or retry with exponential back-off. "
                "Check GCS quota limits in the Google Cloud Console."
            ),
            cause=exc,
        )

    # Schema mismatch / type error.
    if "duckdb" in mod and cls in ("BinderException", "ConversionException"):
        return NucleusSchemaError(
            user_message=(
                "Schema mismatch or type conversion error reading GCS files. "
                "Mixed schemas across files may cause this."
            ),
            fix_hint=(
                "Ensure all files in a glob have the same schema. "
                "Use format='parquet' for strongly-typed files."
            ),
            cause=exc,
        )

    # Memory limit.
    if "duckdb" in mod and cls == "OutOfMemoryException":
        return NucleusResourceError(
            user_message="Reading GCS files exceeded the memory budget.",
            fix_hint=("Reduce the file size or partition the ingest into smaller batches."),
            cause=exc,
        )

    # Generic DuckDB IOException.
    if "duckdb" in mod and cls == "IOException":
        return NucleusIOError(
            user_message=f"Failed to read GCS object: {str(exc)[:200]}",
            fix_hint="Check the gs:// URI and object integrity. Run with --debug for details.",
            cause=exc,
        )

    return NucleusIOError(
        user_message=f"GCS ingest failed unexpectedly: {str(exc)[:200]}",
        fix_hint=(
            "Check the gs:// URI, GCS credentials, and file format. "
            "Run with --debug to see the full error details."
        ),
        cause=exc,
    )


def ingest_gcs_to_iceberg(
    gcs_uri: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    format: Literal["auto", "parquet", "csv", "json"] = "auto",
) -> int:
    """Read a file (or glob) from Google Cloud Storage; write to a filesystem Iceberg table.

    Returns the number of rows written. Uses ``gcsfs`` for ADC credential resolution
    and registers the GCS filesystem with DuckDB via ``duckdb.register_filesystem()``.

    Requires: ``pip install nucleus[gcs]`` to activate the GCS extras
    (installs ``gcsfs==2026.5.0``).

    Args:
        gcs_uri: GCS URI to read from. Examples:
            ``gs://my-bucket/data/orders.parquet``
            ``gs://my-bucket/data/*.parquet``  (glob)
            ``gs://my-bucket/data/orders.csv``
        warehouse_dir: Filesystem catalog warehouse root directory.
        dest_namespace: Iceberg namespace for the destination table.
        dest_table: Iceberg table name within ``dest_namespace``.
        format: File format. ``"auto"`` (default) infers from the file extension.
            Pass ``"parquet"``, ``"csv"``, or ``"json"`` to override.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: Unknown format or unrecognisable URI extension (NE5001).
        NucleusSourceAuthError (NE1009): Access denied (403) or ADC not configured.
        NucleusSourceNotFound (NE1008): Object or bucket not found (404).
        NucleusNetworkError (NE1010): GCS throttling or network error.
        NucleusSchemaError (NE2001): Mixed schemas in glob files or type mismatch.
        NucleusResourceError (NE2003): Exceeds memory budget.
        NucleusIOError (NE1005): Any other read failure.
        NucleusCommitConflictError (NE1002): Concurrent Iceberg commit.
    """
    if not gcs_uri.startswith("gs://"):
        raise NucleusConfigError(
            user_message=f"URI {gcs_uri!r} does not start with 'gs://'. ",
            fix_hint="Pass a GCS URI, e.g. gs://my-bucket/data/orders.parquet",
        )

    file_format = _detect_format(gcs_uri, format if format != "auto" else None)
    duckdb_fn = _FORMAT_TO_DUCKDB_FN[file_format]
    warehouse_path = Path(warehouse_dir)

    if not _GCS_AVAILABLE:
        raise NucleusConfigError(
            user_message="Google Cloud Storage support is not installed.",
            fix_hint=(
                "Run: pip install nucleus[gcs]  "
                "This installs gcsfs==2026.5.0 for GCS access via ADC credentials."
            ),
        )

    try:
        # duckdb, gcsfs, and pafs are module-level (core + optional deps).
        # GCSFileSystem() uses ADC chain — no custom credential code.
        # Docs: https://gcsfs.readthedocs.io/en/latest/ (authentication section)
        gcs = gcsfs.GCSFileSystem()

        # Register gcsfs with DuckDB so gs:// URIs resolve via the GCS filesystem.
        # Docs: https://duckdb.org/docs/api/python/dbapi (register_filesystem)
        # Available since DuckDB 0.7.0 per DuckDB release notes.
        pa_fs = pafs.PyFileSystem(pafs.FSSpecHandler(gcs))  # type: ignore[union-attr]
        conn = duckdb.connect()
        conn.register_filesystem(pa_fs)

        safe_uri = gcs_uri.replace("'", "''")
        query = f"SELECT * FROM {duckdb_fn}('{safe_uri}', union_by_name=true)"
        arrow_table = conn.execute(query).arrow()
        conn.close()

    except NucleusError:
        raise
    except Exception as exc:
        raise _translate_duckdb_gcs_exception(exc) from exc

    # Write to Iceberg catalog.
    # Docs: https://py.iceberg.apache.org/api/
    try:
        catalog = _open_catalog(warehouse_path)
        with contextlib.suppress(NamespaceAlreadyExistsError):
            catalog.create_namespace(dest_namespace)
        identifier = (dest_namespace, dest_table)
        try:
            iceberg_table = catalog.create_table(identifier, schema=arrow_table.schema)
        except TableAlreadyExistsError:
            iceberg_table = catalog.load_table(identifier)
        iceberg_table.append(arrow_table)
    except CommitFailedException as exc:
        raise NucleusCommitConflictError(
            user_message=f"Concurrent commit on '{dest_namespace}.{dest_table}' lost the race.",
            fix_hint="Retry the ingest; ensure no other writer targets the same table.",
            cause=exc,
        ) from exc
    except NucleusError:
        raise
    except Exception as exc:
        from nucleus.coordination.error_translation import translate

        raise translate(exc) from exc

    return len(arrow_table)
