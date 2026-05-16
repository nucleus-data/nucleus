"""PROMOTED 2026-05-13 to ``src/nucleus/ctx/copy_from.py``. This directory
remains as canonical PoC reference.

Minimal SQLite → filesystem-Iceberg ingestor — PoC #3 (steps 2-3 of
``docs/specs/nucleus_poc_plan.md`` §3).

Scope (deliberately minimal):
    - ONE source: SQLite via stdlib ``sqlite3``. No Postgres/MySQL/CSV/
      Parquet/JSON in v0.
    - ONE destination: filesystem-backed Iceberg via PyIceberg's SQL catalog
      (SQLite-backed catalog + ``file://`` warehouse).
    - 5-7 tests, not 50.
    - Will graduate to ``src/nucleus/ctx/copy_from.py`` (~200 LOC) only after
      PoC #3 acceptance criteria pass.

Pins/docs:
    - ``pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1`` — https://py.iceberg.apache.org/api/
    - ``pyarrow==18.1.0`` — https://arrow.apache.org/docs/python/api.html
    - ``sqlite3`` (stdlib) — https://docs.python.org/3/library/sqlite3.html
    - ``docs/specs/nucleus_architecture_v4.1.md`` §6.4 — Error Translation Discipline
    - ``docs/internal/research/pyiceberg.md`` §4-§6 — catalog + exception map
    - ``docs/patterns/type_mapping.md`` §3 — SQLite ↔ Arrow ↔ Iceberg
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Any

import pyarrow as pa
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.exceptions import (
    CommitFailedException,
    NamespaceAlreadyExistsError,
    TableAlreadyExistsError,
)
from pyiceberg.schema import Schema
from pyiceberg.types import (
    BinaryType,
    DoubleType,
    IcebergType,
    LongType,
    NestedField,
    StringType,
)

from nucleus.errors import (
    NucleusCommitConflictError,
    NucleusIOError,
    NucleusSourceNotFound,
    NucleusUnsupportedTypeError,
)

# SQLite declared type (normalized, uppercase) → (Arrow type, Iceberg type
# factory). Adapted from ``docs/patterns/type_mapping.md`` §3 for SQLite's
# four storage classes. Anything outside this set raises NucleusUnsupportedTypeError.
_SQLITE_TYPE_MAP: dict[str, tuple[pa.DataType, type[IcebergType]]] = {
    "INTEGER": (pa.int64(), LongType),
    "REAL": (pa.float64(), DoubleType),
    "TEXT": (pa.string(), StringType),
    "BLOB": (pa.binary(), BinaryType),
}


def _normalize_sqlite_type(declared: str) -> str:
    """Uppercase a SQLite declared type and strip any ``(...)`` suffix."""
    normalized = declared.strip().upper()
    paren = normalized.find("(")
    return (normalized[:paren] if paren != -1 else normalized).strip()


def _build_schemas(
    columns: list[tuple[int, str, str, int, Any, int]],
    source_table: str,
) -> tuple[Schema, pa.Schema]:
    """Build matched Iceberg + Arrow schemas from a ``PRAGMA table_info`` row set."""
    iceberg_fields: list[NestedField] = []
    arrow_fields: list[pa.Field] = []
    for cid, name, declared_type, notnull, _dflt, _pk in columns:
        normalized = _normalize_sqlite_type(declared_type)
        if normalized not in _SQLITE_TYPE_MAP:
            raise NucleusUnsupportedTypeError(
                user_message=(
                    f"Column '{name}' in source table '{source_table}' has declared "
                    f"type '{declared_type}', which v0 does not support."
                ),
                fix_hint=(
                    "v0 ingest supports INTEGER, REAL, TEXT, BLOB. Cast the column "
                    "via a SQLite view (e.g. CAST(col AS TEXT)) before ingesting."
                ),
            )
        arrow_type, iceberg_type_cls = _SQLITE_TYPE_MAP[normalized]
        required = bool(notnull)
        # PRAGMA cid is 0-based; Iceberg field IDs must be ≥ 1.
        iceberg_fields.append(NestedField(cid + 1, name, iceberg_type_cls(), required=required))
        arrow_fields.append(pa.field(name, arrow_type, nullable=not required))
    return Schema(*iceberg_fields), pa.schema(arrow_fields)


def _open_catalog(warehouse_dir: Path) -> Catalog:
    """Open the filesystem-backed SQL catalog for ``warehouse_dir``.

    Uses PyIceberg's built-in ``SqlCatalog`` (SQLite-backed catalog) with a ``file://``
    warehouse. v0.1 default per ``docs/internal/research/pyiceberg.md`` §4.

    NEEDS VERIFICATION on first PoC run: confirm ``load_catalog`` accepts
    ``type='sql'`` + ``uri=sqlite:///...`` + ``warehouse=file:///...`` as plain
    string kwargs in 0.8.1. Log any drift to ``docs/internal/research/ai_hallucinations.md``.
    """
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    catalog_db = warehouse_dir / "catalog.db"
    # Warehouse URI uses two slashes after ``file:``, not three. ``as_posix()``
    # already includes the leading ``/`` on POSIX (yielding the RFC 8089 form
    # ``file:///home/...``), and on Windows yields ``C:/...`` so the URI becomes
    # ``file://C:/...`` — the non-standard but pyiceberg-parseable form. The
    # canonical RFC form ``file:///C:/...`` is rejected by pyiceberg 0.8.1's
    # ``PyArrowFileIO.parse_location`` which leaves ``/C:/...`` and explodes
    # inside ``pyarrow.fs.LocalFileSystem`` with ``WinError 123``.
    # Upstream: https://github.com/apache/iceberg-python/issues/1005
    #           https://github.com/apache/iceberg-python/pull/996  (never merged)
    #           https://github.com/apache/iceberg-python/issues/2477
    # As of pyiceberg 0.11.x main branch (May 2026) the bug is unfixed, so this
    # workaround stays even after ADR-003 upgrade. RFC 8089 §E.2 acknowledges
    # the two-slash Windows form: https://datatracker.ietf.org/doc/html/rfc8089
    # Docs: https://py.iceberg.apache.org/configuration/#fileio
    return load_catalog(
        "default",
        type="sql",
        uri=f"sqlite:///{catalog_db.resolve().as_posix()}",
        warehouse=f"file://{warehouse_dir.resolve().as_posix()}",
    )


def _read_sqlite(
    sqlite_path: Path, source_table: str
) -> tuple[list[tuple[int, str, str, int, Any, int]], list[tuple[Any, ...]]]:
    """Read PRAGMA columns + all rows from ``source_table``. Translate sqlite3 errors."""
    try:
        conn = sqlite3.connect(str(sqlite_path))
        try:
            cols = conn.execute(f'PRAGMA table_info("{source_table}")').fetchall()
            if not cols:
                raise NucleusSourceNotFound(
                    user_message=f"Source table '{source_table}' was not found in '{sqlite_path}'.",
                    fix_hint=(
                        f"List tables with `sqlite3 {sqlite_path} '.tables'` and "
                        "verify the name (case-sensitive)."
                    ),
                )
            rows = conn.execute(f'SELECT * FROM "{source_table}"').fetchall()
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            raise NucleusSourceNotFound(
                user_message=f"Source table '{source_table}' does not exist in '{sqlite_path}'.",
                fix_hint=f"Verify the table name in {sqlite_path}.",
                cause=exc,
            ) from exc
        raise NucleusIOError(
            user_message=f"Failed to read SQLite source: {exc}",
            fix_hint="Check that the SQLite file is readable and not corrupt.",
            cause=exc,
        ) from exc
    except sqlite3.Error as exc:
        raise NucleusIOError(
            user_message=f"Failed to read SQLite source: {exc}",
            fix_hint="Check that the SQLite file is readable and not corrupt.",
            cause=exc,
        ) from exc
    return cols, rows


def ingest_sqlite_to_iceberg(
    sqlite_path: str | Path,
    source_table: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
) -> int:
    """Read all rows from a SQLite table; write them to a filesystem Iceberg
    table. Returns the row count written.

    Auto-infers the Iceberg schema from SQLite's ``PRAGMA table_info``. Creates
    the destination namespace + table if absent. Idempotent in spirit but NOT
    atomic across runs — each call appends.

    Raises:
        NucleusSourceNotFound: ``source_table`` does not exist.
        NucleusUnsupportedTypeError: A column has a type outside the v0 set.
        NucleusCommitConflictError: Concurrent Iceberg commit lost the race.
        NucleusIOError: Any other failure reading SQLite or writing Iceberg.
    """
    sqlite_path = Path(sqlite_path)
    warehouse_dir = Path(warehouse_dir)

    columns, rows = _read_sqlite(sqlite_path, source_table)
    iceberg_schema, arrow_schema = _build_schemas(columns, source_table)

    column_data: dict[str, list[Any]] = {field.name: [] for field in arrow_schema}
    for row in rows:
        for index, field in enumerate(arrow_schema):
            column_data[field.name].append(row[index])
    arrow_table = pa.Table.from_pydict(column_data, schema=arrow_schema)

    # Translate every PyIceberg error at this boundary; no raw pyiceberg
    # classname reaches the caller (mirrors PoC #1; v4.1 §6.4).
    try:
        catalog = _open_catalog(warehouse_dir)
        with contextlib.suppress(NamespaceAlreadyExistsError):
            catalog.create_namespace(dest_namespace)
        identifier = (dest_namespace, dest_table)
        try:
            iceberg_table = catalog.create_table(identifier, schema=iceberg_schema)
        except TableAlreadyExistsError:
            iceberg_table = catalog.load_table(identifier)
        iceberg_table.append(arrow_table)
    except CommitFailedException as exc:
        raise NucleusCommitConflictError(
            user_message=f"Concurrent commit on '{dest_namespace}.{dest_table}' lost the race.",
            fix_hint="Retry the ingest; ensure no other writer targets the same table.",
            cause=exc,
        ) from exc
    except Exception as exc:
        # Catch-all for any other PyIceberg failure (FileIO, schema parse,
        # validation, REST). Surface a typed NucleusIOError, not the raw type.
        raise NucleusIOError(
            user_message=f"Failed to write Iceberg table '{dest_namespace}.{dest_table}': {exc}",
            fix_hint=(
                "Verify the warehouse directory is writable, the namespace and "
                "table names are valid, and disk space is available."
            ),
            cause=exc,
        ) from exc

    return len(rows)
