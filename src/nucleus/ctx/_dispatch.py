"""Unified ``ctx.copy_from()`` — scheme-dispatching ingestion helper (L4).

Per ``docs/specs/nucleus_architecture_v4.1.md`` §5.5.1 (ctx.copy_from ingestion helper)
and ``docs/specs/nucleus_ctx_sdk_spec.md`` §0 (Principles) + §9 (Connectors).

This module provides a single ``copy_from()`` entry point that is the
user-facing surface for the ``nucleus ingest`` flow. The per-source helpers
remain internal implementation; this dispatcher owns the URL-scheme routing.

Stability (per ADR-005 §2):
    Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0

Architecture refs:
    docs/specs/nucleus_architecture_v4.1.md §5.5.1 (Ingestion helper)
    docs/specs/nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/specs/nucleus_ctx_sdk_spec.md §0 Principle 1 (ctx is the only thing users import)
    docs/decisions/ADR-005-api-stability-tiering.md §2 (Beta tier)
    docs/decisions/ADR-014-dlt-postgres-source.md §"MySQL parity (2026-05-14)"
    docs/decisions/ADR-019-snowflake-connector-via-dlt.md (Snowflake branch)
    docs/decisions/ADR-020-object-storage-connectors-via-duckdb.md (S3/GCS/FS)

Pins / docs:
    urllib.parse — https://docs.python.org/3/library/urllib.parse.html
    nucleus.ctx.copy_from (SQLite branch)
    nucleus.ctx.copy_from_postgres (Postgres branch, dlt==1.26.0)
    nucleus.ctx.copy_from_mysql (MySQL branch, dlt==1.26.0 + pymysql==1.1.1)
    nucleus.ctx.copy_from_snowflake (Snowflake branch, dlt[snowflake]==1.26.0)
    nucleus.ctx.copy_from_s3 (S3 branch, duckdb==1.1.3 httpfs)
    nucleus.ctx.copy_from_gcs (GCS branch, gcsfs==2026.5.0)
    nucleus.ctx.copy_from_filesystem (local filesystem branch, duckdb==1.1.3)
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from nucleus.ctx.copy_from import ingest_sqlite_to_iceberg
from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg
from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg
from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg
from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg
from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg
from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg
from nucleus.errors import NucleusConfigError, NucleusInvalidAssetDefinition

# Accepted write-disposition values (shared subset across source branches).
_VALID_WRITE_DISPOSITIONS: frozenset[str] = frozenset({"append", "replace"})

# URL schemes this dispatcher supports. Object-storage + Snowflake added in
# the connector expansion wave (ADR-019, ADR-020). File/relative-path sources
# use a sentinel scheme "file" and a separate relative-path detection path.
_SUPPORTED_SCHEMES: frozenset[str] = frozenset(
    {
        "sqlite",
        "postgresql",
        "postgres",
        "mysql",
        "mysql+pymysql",
        "snowflake",
        "s3",
        "gs",
        "file",
    }
)


def copy_from(  # noqa: PLR0911 — scheme-dispatcher: 1 return per supported scheme is the natural shape.
    source: str,
    *,
    table: str = "",
    target: str,
    warehouse_dir: str | Path,
    write_disposition: str = "append",
    format: str = "auto",
) -> int:
    """Ingest from a source into a filesystem Iceberg asset.

    # Stability: Beta

    Unified entry point per ``docs/specs/nucleus_ctx_sdk_spec.md`` §0 (Principle 1 —
    ctx is the only thing users import) and
    ``docs/specs/nucleus_architecture_v4.1.md`` §5.5.1 (ingestion helper scope).
    Dispatches to the correct per-source internal function by URL scheme;
    per-source functions stay internal and are not part of the public surface.

    Docs: nucleus.dev/api/ctx.copy_from

    Args:
        source: Source connection URL or file path. Supported schemes:
            - ``sqlite:///absolute/path/to/db.sqlite``
            - ``postgresql://user:pass@host:5432/db``
            - ``postgres://user:pass@host:5432/db``
            - ``mysql://user:pass@host:3306/db``
            - ``mysql+pymysql://user:pass@host:3306/db``
            - ``snowflake://user:pass@account/db/schema`` (requires nucleus[snowflake])
            - ``s3://bucket/prefix/file.parquet`` (or glob)
            - ``gs://bucket/prefix/file.parquet`` (requires nucleus[gcs])
            - ``file:///absolute/path/to/file.parquet``
            - ``./relative/path/to/file.parquet`` (relative paths also work)
        table: Source table name (required for SQL sources: sqlite, postgres,
            mysql, snowflake). Not used for object-storage sources (s3, gs, file).
        target: Destination asset key in ``<namespace>.<name>`` form
            (e.g. ``"raw.orders"``). Maps to Iceberg namespace + table name.
        warehouse_dir: Filesystem catalog warehouse root directory.
        write_disposition: ``"append"`` (default) adds rows; ``"replace"``
            truncates and reloads. SQL sources only; object-storage branches
            always append.
        format: File format for object-storage and filesystem sources.
            ``"auto"`` (default) infers from the file extension. Pass
            ``"parquet"``, ``"csv"``, or ``"json"`` to override.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: Unsupported source scheme or invalid args (NE5001).
        NucleusInvalidAssetDefinition: ``target`` not in ``<ns>.<name>`` form (NE3004).
        NucleusSourceNotFound: Source table / object not found (NE1008).
        NucleusSourceConnectionError: Cannot connect to source (NE1001).
        NucleusSourceAuthError: Credentials rejected by source (NE1009).
        NucleusCommitConflictError: Concurrent Iceberg commit (NE1002).
        NucleusIOError: Read/write failure (NE1005).
    """
    if write_disposition not in _VALID_WRITE_DISPOSITIONS:
        raise NucleusConfigError(
            user_message=(
                f"write_disposition={write_disposition!r} is not supported. "
                "v0.1 accepts 'append' or 'replace' only."
            ),
            fix_hint=(
                "Pass write_disposition='append' (default) to add rows, "
                "or write_disposition='replace' to truncate and reload."
            ),
        )

    # Docs: https://docs.python.org/3/library/urllib.parse.html
    parsed = urlparse(source)
    scheme = parsed.scheme.lower()

    # Object-storage and filesystem sources (s3://, gs://, file://, relative paths)
    # do NOT use a table name — they read directly from the URI.
    is_relative_path = not scheme or scheme not in _SUPPORTED_SCHEMES

    if scheme not in _SUPPORTED_SCHEMES and not is_relative_path:
        raise NucleusConfigError(
            user_message=(
                f"Source scheme {scheme!r} is not supported. "
                f"Supported schemes: {sorted(_SUPPORTED_SCHEMES)}."
            ),
            fix_hint=(
                "Use a supported source URL: sqlite:///path/to/db, "
                "postgresql://user:pass@host/db, mysql://user:pass@host/db, "
                "snowflake://user:pass@account/db/schema, "
                "s3://bucket/file.parquet, gs://bucket/file.parquet, "
                "file:///abs/path/file.parquet, or ./relative/path/file.parquet."
            ),
        )

    if not target or "." not in target or target.count(".") != 1:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"target={target!r} must be in '<namespace>.<name>' form (e.g. 'raw.orders')."
            ),
            fix_hint=("Pass a 2-level v0.1 asset key as target=. Example: target='raw.orders'."),
        )

    namespace, dest_table = target.split(".", 1)
    warehouse_path = Path(warehouse_dir)

    if scheme == "sqlite":
        raw_path = parsed.path
        sqlite_path = Path(raw_path[1:] if raw_path.startswith("/") else raw_path)
        return ingest_sqlite_to_iceberg(
            sqlite_path,
            table,
            warehouse_dir=warehouse_path,
            dest_namespace=namespace,
            dest_table=dest_table,
        )

    if scheme in {"mysql", "mysql+pymysql"}:
        return ingest_mysql_to_iceberg(
            source,
            table,
            warehouse_dir=warehouse_path,
            dest_namespace=namespace,
            dest_table=dest_table,
            write_disposition=write_disposition,  # type: ignore[arg-type]
        )

    if scheme == "snowflake":
        return ingest_snowflake_to_iceberg(
            source,
            table,
            warehouse_dir=warehouse_path,
            dest_namespace=namespace,
            dest_table=dest_table,
            write_disposition=write_disposition,  # type: ignore[arg-type]
        )

    if scheme == "s3":
        return ingest_s3_to_iceberg(
            source,
            warehouse_dir=warehouse_path,
            dest_namespace=namespace,
            dest_table=dest_table,
            format=format,  # type: ignore[arg-type]
        )

    if scheme == "gs":
        return ingest_gcs_to_iceberg(
            source,
            warehouse_dir=warehouse_path,
            dest_namespace=namespace,
            dest_table=dest_table,
            format=format,  # type: ignore[arg-type]
        )

    if scheme == "file" or is_relative_path:
        # file:///path/to/file.parquet or ./relative/path.parquet or /absolute/path.parquet
        return ingest_filesystem_to_iceberg(
            source,
            warehouse_dir=warehouse_path,
            dest_namespace=namespace,
            dest_table=dest_table,
            format=format,  # type: ignore[arg-type]
        )

    # postgresql / postgres branch — delegates to the dlt-backed Postgres helper.
    return ingest_postgres_to_iceberg(
        source,
        table,
        warehouse_dir=warehouse_path,
        dest_namespace=namespace,
        dest_table=dest_table,
        write_disposition=write_disposition,  # type: ignore[arg-type]
    )


__all__ = ["copy_from"]
