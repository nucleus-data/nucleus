"""PoC #3 tests — 7 cases, not 70. Iterate from here.

Verifies ``ingest_sqlite_to_iceberg()``:
    - Round-trips a small typed table (write 3, read 3)
    - Auto-infers Iceberg schema field types (Long, Double, String, Binary)
    - Calling twice is safe (idempotent namespace + table creation)
    - Missing source table → NucleusSourceNotFound
    - Unsupported column type → NucleusUnsupportedTypeError
    - Rendered error never leaks the substring 'pyiceberg' (mirrors PoC #1 §2.5)
    - Two appends double the row count (proves ``append`` semantics, not overwrite)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("pyiceberg")
pytest.importorskip("pyarrow")

from pyiceberg.types import BinaryType, DoubleType, LongType, StringType

from nucleus.errors import (
    NucleusError,
    NucleusSourceNotFound,
    NucleusUnsupportedTypeError,
)
from poc.p3_ingest.ingest import _open_catalog, ingest_sqlite_to_iceberg


def _exec(sqlite_path: Path, *statements: str) -> None:
    """Execute one or more SQL statements against ``sqlite_path``."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        for sql in statements:
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _seed_orders(sqlite_path: Path, n_rows: int = 3) -> None:
    """Create ``orders(id INTEGER, amount REAL, note TEXT)`` with ``n_rows`` rows."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        conn.execute("CREATE TABLE orders (id INTEGER, amount REAL, note TEXT)")
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?, ?)",
            [(i, float(i) + 0.5, f"note-{i}") for i in range(n_rows)],
        )
        conn.commit()
    finally:
        conn.close()


def _ingest_orders(sqlite_path: Path, warehouse: Path) -> int:
    return ingest_sqlite_to_iceberg(
        sqlite_path,
        "orders",
        warehouse_dir=warehouse,
        dest_namespace="raw",
        dest_table="orders",
    )


def test_round_trip_simple_table(tmp_path: Path) -> None:
    _seed_orders(tmp_path / "src.db", n_rows=3)
    written = _ingest_orders(tmp_path / "src.db", tmp_path / "wh")

    assert written == 3
    arrow = _open_catalog(tmp_path / "wh").load_table(("raw", "orders")).scan().to_arrow()
    assert arrow.num_rows == 3
    assert set(arrow.column_names) == {"id", "amount", "note"}


def test_schema_auto_inferred(tmp_path: Path) -> None:
    _exec(
        tmp_path / "src.db",
        "CREATE TABLE typed (id INTEGER, amount REAL, name TEXT, payload BLOB)",
        "INSERT INTO typed VALUES (1, 1.5, 'foo', X'0102')",
    )
    ingest_sqlite_to_iceberg(
        tmp_path / "src.db",
        "typed",
        warehouse_dir=tmp_path / "wh",
        dest_namespace="raw",
        dest_table="typed",
    )

    schema = _open_catalog(tmp_path / "wh").load_table(("raw", "typed")).schema()
    by_name = {field.name: field.field_type for field in schema.fields}
    assert isinstance(by_name["id"], LongType)
    assert isinstance(by_name["amount"], DoubleType)
    assert isinstance(by_name["name"], StringType)
    assert isinstance(by_name["payload"], BinaryType)


def test_idempotent_namespace_and_table_create(tmp_path: Path) -> None:
    _seed_orders(tmp_path / "src.db", n_rows=2)
    _ingest_orders(tmp_path / "src.db", tmp_path / "wh")
    # Second call must not raise on the existing namespace + table.
    _ingest_orders(tmp_path / "src.db", tmp_path / "wh")


def test_missing_source_table_raises_source_not_found(tmp_path: Path) -> None:
    sqlite3.connect(str(tmp_path / "src.db")).close()  # empty db, no tables

    with pytest.raises(NucleusSourceNotFound) as exc_info:
        ingest_sqlite_to_iceberg(
            tmp_path / "src.db",
            "nonexistent",
            warehouse_dir=tmp_path / "wh",
            dest_namespace="raw",
            dest_table="x",
        )
    assert "nonexistent" in exc_info.value.user_message
    assert exc_info.value.fix_hint


def test_unsupported_type_raises_unsupported_type_error(tmp_path: Path) -> None:
    # NUMERIC is outside the v0 supported set {INTEGER, REAL, TEXT, BLOB}.
    _exec(tmp_path / "src.db", "CREATE TABLE bad (id INTEGER, weird NUMERIC)")

    with pytest.raises(NucleusUnsupportedTypeError) as exc_info:
        ingest_sqlite_to_iceberg(
            tmp_path / "src.db",
            "bad",
            warehouse_dir=tmp_path / "wh",
            dest_namespace="raw",
            dest_table="bad",
        )
    assert "weird" in exc_info.value.user_message
    assert "NUMERIC" in exc_info.value.user_message


def test_rendered_error_has_no_pyiceberg_leak(tmp_path: Path) -> None:
    sqlite3.connect(str(tmp_path / "src.db")).close()  # empty db

    with pytest.raises(NucleusError) as exc_info:
        ingest_sqlite_to_iceberg(
            tmp_path / "src.db",
            "missing",
            warehouse_dir=tmp_path / "wh",
            dest_namespace="raw",
            dest_table="x",
        )
    rendered = exc_info.value.rendered().lower()
    assert "pyiceberg" not in rendered, rendered
    assert "iceberg.exceptions" not in rendered, rendered


def test_two_appends_double_row_count(tmp_path: Path) -> None:
    _seed_orders(tmp_path / "src.db", n_rows=3)
    assert _ingest_orders(tmp_path / "src.db", tmp_path / "wh") == 3
    assert _ingest_orders(tmp_path / "src.db", tmp_path / "wh") == 3

    arrow = _open_catalog(tmp_path / "wh").load_table(("raw", "orders")).scan().to_arrow()
    assert arrow.num_rows == 6
