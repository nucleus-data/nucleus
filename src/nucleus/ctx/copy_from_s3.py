"""S3 object storage → filesystem-Iceberg ingest helper — ``ctx.ingest_s3_to_iceberg``.

Wraps ``duckdb.read_parquet`` / ``read_csv_auto`` / ``read_json_auto`` with S3
URIs via DuckDB's bundled ``httpfs`` extension. Arrow zero-copy path → pyiceberg
append. Credential resolution delegates to DuckDB's httpfs which reads AWS env
vars (``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_DEFAULT_REGION``).

Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)

Architecture refs:
    nucleus_architecture_v4.1.md §5.5 (Ingestion — object storage branch)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/decisions/ADR-020-object-storage-connectors-via-duckdb.md (scope)
    docs/internal/research/s3_duckdb.md (DuckDB httpfs + S3 credential resolution)

Pins/docs:
    duckdb==1.1.3 — https://duckdb.org/docs/extensions/httpfs/s3api
                    https://duckdb.org/docs/data/parquet/overview
                    https://duckdb.org/docs/data/csv/overview
                    https://duckdb.org/docs/data/json/overview
    pyarrow==18.1.0 — https://arrow.apache.org/docs/python/api.html
    pyiceberg[sql-sqlite,s3fs,duckdb]==0.11.1 — https://py.iceberg.apache.org/api/
    s3fs==2026.4.0 — https://s3fs.readthedocs.io/
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

__all__ = ["ingest_s3_to_iceberg"]

# Supported file formats and their DuckDB read functions.
# Docs: https://duckdb.org/docs/data/parquet/overview
#       https://duckdb.org/docs/data/csv/overview
#       https://duckdb.org/docs/data/json/overview
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

    # Strip query string, then take the last path segment's suffix.
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


def _translate_duckdb_s3_exception(exc: BaseException) -> NucleusError:
    """Translate a DuckDB/httpfs S3-source exception to a NucleusError.

    Inspects the exception message for S3 HTTP error codes and connection
    indicators. No external class names reach user_message or fix_hint per
    AGENTS.md §11.7.

    Docs:
        https://duckdb.org/docs/extensions/httpfs/s3api (DuckDB S3 errors)
        https://docs.python.org/3/library/exceptions.html (stdlib errors)
    """
    msg = str(exc).lower()
    cls = type(exc).__name__
    mod = (type(exc).__module__ or "").lower()

    # Auth / access denied — HTTP 403 or "access denied" message.
    if "403" in msg or "access denied" in msg or "accessdenied" in msg:
        return NucleusSourceAuthError(
            user_message=(
                "Access to the S3 object was denied. "
                "Check your AWS credentials and bucket permissions."
            ),
            fix_hint=(
                "Verify AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and "
                "AWS_DEFAULT_REGION environment variables. "
                "Confirm the IAM policy allows s3:GetObject on the target bucket."
            ),
            cause=exc,
        )

    # Object not found — HTTP 404 or "NoSuchKey" / "not found".
    if "404" in msg or "nosuchkey" in msg or "no such key" in msg:
        return NucleusSourceNotFound(
            user_message=(
                "The S3 object was not found. Check the bucket name, key path, and region."
            ),
            fix_hint=(
                "Verify the s3:// URI is correct and the object exists. "
                "Example: s3://my-bucket/data/orders.parquet"
            ),
            cause=exc,
        )

    # Bucket not found — HTTP 404 on bucket itself or "NoSuchBucket".
    if "nosuchbucket" in msg or "no such bucket" in msg:
        return NucleusSourceNotFound(
            user_message=(
                "The S3 bucket was not found. Check the bucket name and region in the URI."
            ),
            fix_hint=(
                "Verify the bucket name in the s3:// URI. "
                "Ensure AWS_DEFAULT_REGION matches the bucket's region."
            ),
            cause=exc,
        )

    # Network / throttling — HTTP 503 / 429 / connection errors.
    if "503" in msg or "429" in msg or "slowdown" in msg or "slow down" in msg:
        return NucleusNetworkError(
            user_message=(
                "The S3 service is temporarily unavailable or throttling requests. "
                "Retry after a short wait."
            ),
            fix_hint=(
                "Reduce request rate or retry with exponential back-off. "
                "If using high-throughput glob ingests, consider partitioning the load."
            ),
            cause=exc,
        )

    # Connection / DNS failure.
    if any(
        phrase in msg
        for phrase in ("connection refused", "could not connect", "dns", "network", "timeout")
    ):
        return NucleusSourceNotFound(
            user_message=(
                "Could not reach the S3 endpoint. Check network connectivity and the bucket region."
            ),
            fix_hint=(
                "Verify AWS_DEFAULT_REGION is set and network allows outbound HTTPS. "
                "For VPC endpoints, confirm the endpoint routing."
            ),
            cause=exc,
        )

    # Schema mismatch / type error.
    if "duckdb" in mod and cls in ("BinderException", "ConversionException"):
        return NucleusSchemaError(
            user_message=(
                "Schema mismatch or type conversion error reading S3 files. "
                "Mixed schemas across files may cause this."
            ),
            fix_hint=(
                "Ensure all files in a glob have the same schema. "
                "Use format='parquet' for strongly-typed files to avoid CSV type guessing."
            ),
            cause=exc,
        )

    # Memory limit exceeded.
    if "duckdb" in mod and cls == "OutOfMemoryException":
        return NucleusResourceError(
            user_message="Reading S3 files exceeded the memory budget.",
            fix_hint=(
                "Reduce the file size or filter earlier (e.g. use a Parquet pushdown). "
                "For large datasets, partition the ingest into smaller batches."
            ),
            cause=exc,
        )

    # Generic DuckDB IOException (file read error).
    if "duckdb" in mod and cls == "IOException":
        return NucleusIOError(
            user_message=f"Failed to read S3 object: {str(exc)[:200]}",
            fix_hint=(
                "Check the S3 URI, file format, and object integrity. "
                "Run with --debug to see the full error details."
            ),
            cause=exc,
        )

    # Stdlib errors.
    if isinstance(exc, PermissionError):
        return NucleusSourceAuthError(
            user_message="Permission denied accessing S3 credentials or local config.",
            fix_hint="Verify AWS environment variables are set and readable.",
            cause=exc,
        )
    if isinstance(exc, FileNotFoundError):
        return NucleusSourceNotFound(
            user_message=f"S3 object or local path not found: {exc}",
            fix_hint="Check the s3:// URI and verify the object exists.",
            cause=exc,
        )

    return NucleusIOError(
        user_message=f"S3 ingest failed unexpectedly: {str(exc)[:200]}",
        fix_hint=(
            "Check the s3:// URI, AWS credentials, and file format. "
            "Run with --debug to see the full error details."
        ),
        cause=exc,
    )


def ingest_s3_to_iceberg(
    s3_uri: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    format: Literal["auto", "parquet", "csv", "json"] = "auto",
) -> int:
    """Read a file (or glob) from S3; write to a filesystem Iceberg table.

    Returns the number of rows written. Uses DuckDB's bundled httpfs extension
    for S3 access. AWS credentials are read from environment variables or the
    ``~/.aws/credentials`` file via DuckDB's built-in resolution.

    Requires no extra install — S3 support is bundled in ``duckdb==1.1.3``.
    The ``s3fs==2026.4.0`` pin in core deps covers pyiceberg's S3 write path.

    Args:
        s3_uri: S3 URI to read from. Examples:
            ``s3://my-bucket/data/orders.parquet``
            ``s3://my-bucket/data/*.parquet``  (glob)
            ``s3://my-bucket/data/orders.csv``
        warehouse_dir: Filesystem catalog warehouse root directory.
        dest_namespace: Iceberg namespace for the destination table.
        dest_table: Iceberg table name within ``dest_namespace``.
        format: File format. ``"auto"`` (default) infers from the file extension.
            Pass ``"parquet"``, ``"csv"``, or ``"json"`` to override.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: Unknown format or unrecognisable URI extension (NE5001).
        NucleusSourceAuthError (NE1009): Access denied (HTTP 403) or wrong credentials.
        NucleusSourceNotFound (NE1008): Object or bucket not found (HTTP 404).
        NucleusNetworkError (NE1010): S3 throttling (HTTP 503/429) or network error.
        NucleusSchemaError (NE2001): Mixed schemas in glob files or type mismatch.
        NucleusResourceError (NE2003): Exceeds memory budget.
        NucleusIOError (NE1005): Any other read failure.
        NucleusCommitConflictError (NE1002): Concurrent Iceberg commit.
    """
    if not s3_uri.startswith("s3://"):
        raise NucleusConfigError(
            user_message=f"URI {s3_uri!r} does not start with 's3://'. ",
            fix_hint="Pass an S3 URI, e.g. s3://my-bucket/data/orders.parquet",
        )

    file_format = _detect_format(s3_uri, format if format != "auto" else None)
    duckdb_fn = _FORMAT_TO_DUCKDB_FN[file_format]
    warehouse_path = Path(warehouse_dir)

    try:
        # duckdb is a core dep (pinned at module level).
        # Docs: https://duckdb.org/docs/api/python/dbapi
        conn = duckdb.connect()

        # Load httpfs extension — bundled in duckdb 1.1.3; autoloaded on URI
        # references but explicit load is safer for clarity.
        # Docs: https://duckdb.org/docs/extensions/httpfs/overview
        conn.execute("LOAD httpfs")

        # Escape single quotes in the URI to prevent SQL injection in the
        # dynamically constructed query string.
        safe_uri = s3_uri.replace("'", "''")

        # Docs: https://duckdb.org/docs/data/parquet/overview
        #       https://duckdb.org/docs/data/csv/overview
        #       https://duckdb.org/docs/data/json/overview
        # union_by_name=true unifies schemas across glob files by column name.
        query = f"SELECT * FROM {duckdb_fn}('{safe_uri}', union_by_name=true)"
        arrow_table = conn.execute(query).arrow()
        conn.close()

    except NucleusError:
        raise
    except Exception as exc:
        raise _translate_duckdb_s3_exception(exc) from exc

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
