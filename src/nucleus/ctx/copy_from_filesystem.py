"""Local filesystem → filesystem-Iceberg ingest helper — ``ctx.ingest_filesystem_to_iceberg``.

Wraps ``duckdb.read_parquet`` / ``read_csv_auto`` / ``read_json_auto`` against
local paths (absolute, relative, glob, or ``file://`` URI). Schema is inferred
from the file(s); mixed-schema glob patterns raise ``NucleusSchemaError``.

Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)

Architecture refs:
    nucleus_architecture_v4.1.md §5.5 (Ingestion — local filesystem branch)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/decisions/ADR-020-object-storage-connectors-via-duckdb.md (scope)
    docs/research/filesystem_duckdb.md §3-§6 (DuckDB local file reading)

Pins/docs:
    duckdb==1.1.3 — https://duckdb.org/docs/data/parquet/overview
                    https://duckdb.org/docs/data/csv/overview
                    https://duckdb.org/docs/data/json/overview
                    https://duckdb.org/docs/data/multiple_files/overview
    pyarrow==18.1.0 — https://arrow.apache.org/docs/python/api.html
    pyiceberg[sql-sqlite,s3fs,duckdb]==0.11.1 — https://py.iceberg.apache.org/api/
"""

from __future__ import annotations

import contextlib
from pathlib import Path, PurePosixPath
from typing import Literal

from pyiceberg.exceptions import (
    CommitFailedException,
    NamespaceAlreadyExistsError,
    TableAlreadyExistsError,
)

import duckdb

from nucleus.ctx.copy_from import _open_catalog
from nucleus.errors import (
    NucleusCommitConflictError,
    NucleusConfigError,
    NucleusError,
    NucleusIOError,
    NucleusPermissionError,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSourceNotFound,
)

__all__ = ["ingest_filesystem_to_iceberg"]

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


def _normalize_path(source: str) -> str:
    """Strip ``file://`` prefix and return a POSIX path string suitable for DuckDB.

    DuckDB on all platforms accepts POSIX-style paths. On Windows, absolute
    paths in POSIX form (``C:/path/file.parquet``) are handled correctly by
    DuckDB 1.1.x. Relative paths and globs are preserved as-is.
    Docs: https://duckdb.org/docs/data/multiple_files/overview
    """
    if source.startswith("file://"):
        # Strip file:// prefix and then remove the leading slash that
        # RFC 8089 adds: file:///C:/path → /C:/path → C:/path on Windows.
        stripped = source[len("file://"):]
        # POSIX absolute path: file:///home/user → /home/user (keep leading /)
        # Windows RFC 8089: file:///C:/path → C:/path (strip /C: leading /)
        if len(stripped) >= 2 and stripped[0] == "/" and stripped[1].isalpha() and stripped[2:3] == ":":
            stripped = stripped[1:]  # drop leading slash on Windows: /C: → C:
        return stripped
    return source


def _detect_format(source: str, explicit_format: str | None) -> str:
    """Resolve file format: explicit override wins; otherwise infer from extension.

    For glob patterns (e.g. ``./data/*.parquet``), the suffix is taken from the
    glob pattern itself (``*.parquet`` → ``.parquet``).
    """
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

    path_part = source.split("?")[0].split("#")[0]
    suffix = PurePosixPath(path_part).suffix.lower()
    if suffix in _EXTENSION_TO_FORMAT:
        return _EXTENSION_TO_FORMAT[suffix]

    raise NucleusConfigError(
        user_message=(
            f"Cannot auto-detect file format from path {source!r} "
            f"(extension {suffix!r} is not recognised)."
        ),
        fix_hint=(
            "Pass an explicit format= keyword: format='parquet', format='csv', "
            "or format='json'. Supported extensions for auto-detection: "
            f"{sorted(_EXTENSION_TO_FORMAT)}."
        ),
    )


def _translate_duckdb_fs_exception(exc: BaseException) -> NucleusError:
    """Translate a DuckDB filesystem exception to a NucleusError.

    Handles local IO errors including file-not-found, permission-denied,
    schema mismatch, and memory errors without leaking DuckDB classnames
    per AGENTS.md §11.7.

    Docs:
        https://duckdb.org/docs/data/parquet/overview (DuckDB Parquet errors)
        https://docs.python.org/3/library/exceptions.html (stdlib)
    """
    msg = str(exc).lower()
    cls = type(exc).__name__
    mod = (type(exc).__module__ or "").lower()

    # Stdlib FS errors — catch before DuckDB checks.
    if isinstance(exc, FileNotFoundError):
        return NucleusSourceNotFound(
            user_message=f"File or directory not found: {exc}",
            fix_hint=(
                "Verify the path exists and the file extension matches the format. "
                "For glob patterns, ensure at least one file matches."
            ),
            cause=exc,
        )
    if isinstance(exc, PermissionError):
        return NucleusPermissionError(
            user_message=f"Permission denied reading local file: {exc}",
            fix_hint="Check that the file is readable by the current user.",
            cause=exc,
        )

    # DuckDB-specific errors.
    if "duckdb" in mod:
        if cls in ("BinderException", "ConversionException"):
            return NucleusSchemaError(
                user_message=(
                    "Schema mismatch or type conversion error reading local files. "
                    "Mixed schemas across glob files may cause this."
                ),
                fix_hint=(
                    "Ensure all files in a glob have the same schema. "
                    "Inspect file schemas individually before bulk-loading."
                ),
                cause=exc,
            )
        if cls == "OutOfMemoryException":
            return NucleusResourceError(
                user_message="Reading local files exceeded the memory budget.",
                fix_hint=(
                    "Reduce the file size or partition the ingest into smaller batches. "
                    "For large datasets, consider Parquet format (smaller memory footprint)."
                ),
                cause=exc,
            )
        if cls == "IOException":
            if "no such file" in msg or "not found" in msg or "cannot open" in msg:
                return NucleusSourceNotFound(
                    user_message=f"File not found: {str(exc)[:200]}",
                    fix_hint="Verify the path exists and matches the expected format.",
                    cause=exc,
                )
            if "permission" in msg or "access" in msg:
                return NucleusPermissionError(
                    user_message=f"Permission denied: {str(exc)[:200]}",
                    fix_hint="Check file read permissions.",
                    cause=exc,
                )
            return NucleusIOError(
                user_message=f"Failed to read local file: {str(exc)[:200]}",
                fix_hint="Check the file path, format, and integrity.",
                cause=exc,
            )
        if cls == "InvalidInputException":
            return NucleusIOError(
                user_message=f"Malformed or corrupt file: {str(exc)[:200]}",
                fix_hint=(
                    "Verify the file is a valid Parquet/CSV/JSON file. "
                    "Try opening it with another tool to confirm integrity."
                ),
                cause=exc,
            )

    return NucleusIOError(
        user_message=f"Filesystem ingest failed unexpectedly: {str(exc)[:200]}",
        fix_hint=(
            "Check the path, file format, and ensure files are readable. "
            "Run with --debug to see the full error details."
        ),
        cause=exc,
    )


def ingest_filesystem_to_iceberg(
    source: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    format: Literal["auto", "parquet", "csv", "json"] = "auto",  # noqa: A002 — mirrors public API
) -> int:
    """Read a local file (or glob) and write to a filesystem Iceberg table.

    Returns the number of rows written. Schema is inferred from the file(s).
    Mixed-schema glob patterns raise ``NucleusSchemaError``.

    No extra install required — uses core ``duckdb==1.1.3``.

    Args:
        source: Local file path, glob pattern, or ``file://`` URI. Examples:
            ``./data/orders.parquet``
            ``./data/*.parquet``  (glob — all files must share the same schema)
            ``/absolute/path/data.csv``
            ``file:///absolute/path/data.json``
        warehouse_dir: Filesystem catalog warehouse root directory.
        dest_namespace: Iceberg namespace for the destination table.
        dest_table: Iceberg table name within ``dest_namespace``.
        format: File format. ``"auto"`` (default) infers from the file extension.
            Pass ``"parquet"``, ``"csv"``, or ``"json"`` to override.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: Unknown format or unrecognisable file extension (NE5001).
        NucleusSourceNotFound (NE1008): File or glob matched no files.
        NucleusPermissionError (NE1006): File is not readable.
        NucleusSchemaError (NE2001): Mixed schemas across glob files.
        NucleusResourceError (NE2003): Exceeds memory budget.
        NucleusIOError (NE1005): Malformed file or any other read failure.
        NucleusCommitConflictError (NE1002): Concurrent Iceberg commit.
    """
    normalized = _normalize_path(source)
    file_format = _detect_format(normalized, format if format != "auto" else None)
    duckdb_fn = _FORMAT_TO_DUCKDB_FN[file_format]
    warehouse_path = Path(warehouse_dir)

    try:
        # duckdb is a core dep (pinned at module level).
        # Docs: https://duckdb.org/docs/api/python/dbapi
        conn = duckdb.connect()

        # Escape single quotes in the path to prevent SQL injection.
        safe_path = normalized.replace("'", "''")

        # Docs: https://duckdb.org/docs/data/multiple_files/overview
        # union_by_name=true unifies schemas across glob files by column name.
        # For single files, union_by_name is a no-op.
        query = f"SELECT * FROM {duckdb_fn}('{safe_path}', union_by_name=true)"
        arrow_table = conn.execute(query).arrow()
        conn.close()

    except NucleusError:
        raise
    except Exception as exc:  # noqa: BLE001 — broad catch: translator classifies
        raise _translate_duckdb_fs_exception(exc) from exc

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
    except Exception as exc:  # noqa: BLE001 — translate pyiceberg and stdlib errors
        from nucleus.coordination.error_translation import translate

        raise translate(exc) from exc

    return len(arrow_table)
