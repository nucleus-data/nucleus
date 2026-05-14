"""Tests for ``nucleus.ctx.copy_from_filesystem`` — unit tests (DuckDB mocked).

All tests mock ``duckdb.connect`` and the pyiceberg catalog so no real
filesystem data or Iceberg catalog is required.

Verifies ``ingest_filesystem_to_iceberg()``:
    1. Unknown extension without explicit format: raises NucleusConfigError.
    2. Happy path parquet: DuckDB + catalog mocked, returns row count.
    3. File not found (FileNotFoundError): raises NucleusSourceNotFound (NE1008).
    4. Permission denied (PermissionError): raises NucleusPermissionError (NE1006).
    5. Schema mismatch (BinderException): raises NucleusSchemaError (NE2001).
    6. Memory limit (OutOfMemoryException): raises NucleusResourceError (NE2003).
    7. file:// URI prefix is stripped before passing to DuckDB.
    8. union_by_name=true in DuckDB query for glob support.
    9. Malformed file (InvalidInputException): raises NucleusIOError (NE1005).
    10. format='json' → read_json_auto in query.

Architecture refs:
    docs/research/filesystem_duckdb.md §6 (error classification)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from nucleus.errors import (
    NucleusConfigError,
    NucleusIOError,
    NucleusPermissionError,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSourceNotFound,
)

_NS = "raw"
_DEST = "orders"
_LOCAL_URI = "./data/orders.parquet"


def _make_arrow_table(n: int = 2) -> pa.Table:
    return pa.table({"id": pa.array(range(n)), "val": pa.array([f"v{i}" for i in range(n)])})


def _patch_duckdb_and_catalog(arrow_table: pa.Table) -> tuple[MagicMock, MagicMock]:
    mock_conn = MagicMock()
    mock_conn.execute.return_value.arrow.return_value = arrow_table
    mock_duckdb = MagicMock()
    mock_duckdb.connect.return_value = mock_conn
    return mock_duckdb, mock_conn


# ===========================================================================
# Test 1 — Unknown extension: raises NucleusConfigError
# ===========================================================================


def test_unknown_extension_raises_config_error(tmp_path):
    """./data/file.xyz with no explicit format raises NucleusConfigError."""
    from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

    with pytest.raises(NucleusConfigError) as exc_info:
        ingest_filesystem_to_iceberg(
            "./data/orders.xyz",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert "format=" in exc_info.value.fix_hint


# ===========================================================================
# Test 2 — Happy path: returns correct row count
# ===========================================================================


def test_happy_path_returns_row_count(tmp_path):
    """DuckDB returns 2-row Arrow table → ingest_filesystem_to_iceberg returns 2."""
    arrow_table = _make_arrow_table(2)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_iceberg_table = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = mock_iceberg_table

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        result = ingest_filesystem_to_iceberg(
            _LOCAL_URI,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert result == 2
    mock_iceberg_table.append.assert_called_once_with(arrow_table)


# ===========================================================================
# Test 3 — File not found (FileNotFoundError): raises NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_file_not_found_translates_to_source_not_found(tmp_path):
    """FileNotFoundError → NucleusSourceNotFound (NE1008); no internal path leak."""
    err = FileNotFoundError("[Errno 2] No such file or directory: './data/orders.parquet'")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog"),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_filesystem_to_iceberg(
                _LOCAL_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    err_out = exc_info.value
    assert err_out.error_code == "NE1008"
    assert err_out.__cause__ is not None
    combined = (err_out.user_message + err_out.fix_hint).lower()
    for forbidden in ("duckdb", "ioexception"):
        assert forbidden not in combined, f"leaked {forbidden!r}"


# ===========================================================================
# Test 4 — Permission denied: raises NucleusPermissionError (NE1006)
# ===========================================================================


def test_permission_denied_translates_to_permission_error(tmp_path):
    """PermissionError → NucleusPermissionError (NE1006)."""
    err = PermissionError("[Errno 13] Permission denied: './data/orders.parquet'")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog"),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        with pytest.raises(NucleusPermissionError) as exc_info:
            ingest_filesystem_to_iceberg(
                _LOCAL_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE1006"


# ===========================================================================
# Test 5 — Schema mismatch (BinderException): raises NucleusSchemaError (NE2001)
# ===========================================================================


def test_schema_mismatch_translates_to_schema_error(tmp_path):
    """DuckDB BinderException → NucleusSchemaError (NE2001)."""

    class FakeDuckDBBinderError(Exception):
        pass

    FakeDuckDBBinderError.__module__ = "duckdb"
    FakeDuckDBBinderError.__name__ = "BinderException"
    err = FakeDuckDBBinderError("Column type mismatch across glob files")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog"),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        with pytest.raises(NucleusSchemaError) as exc_info:
            ingest_filesystem_to_iceberg(
                "./data/*.parquet",
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE2001"


# ===========================================================================
# Test 6 — Memory limit (OutOfMemoryException): raises NucleusResourceError (NE2003)
# ===========================================================================


def test_out_of_memory_translates_to_resource_error(tmp_path):
    """DuckDB OutOfMemoryException → NucleusResourceError (NE2003)."""

    class FakeDuckDBOOMError(Exception):
        pass

    FakeDuckDBOOMError.__module__ = "duckdb"
    FakeDuckDBOOMError.__name__ = "OutOfMemoryException"
    err = FakeDuckDBOOMError("Out of Memory Error: could not allocate block of 512 MB")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog"),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        with pytest.raises(NucleusResourceError) as exc_info:
            ingest_filesystem_to_iceberg(
                _LOCAL_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE2003"


# ===========================================================================
# Test 7 — file:// URI prefix is stripped
# ===========================================================================


def test_file_uri_prefix_stripped_before_duckdb(tmp_path):
    """file:///path/orders.parquet → /path/orders.parquet passed to DuckDB."""
    arrow_table = _make_arrow_table(1)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        ingest_filesystem_to_iceberg(
            "file:///tmp/orders.parquet",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    executed_query = mock_conn.execute.call_args[0][0]
    # file:// prefix must be stripped — DuckDB receives the bare path.
    assert "file://" not in executed_query
    assert "/tmp/orders.parquet" in executed_query


# ===========================================================================
# Test 8 — union_by_name=true in DuckDB query
# ===========================================================================


def test_union_by_name_in_query(tmp_path):
    """DuckDB query must include union_by_name=true."""
    arrow_table = _make_arrow_table(1)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        ingest_filesystem_to_iceberg(
            _LOCAL_URI,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    executed_query = mock_conn.execute.call_args[0][0]
    assert "union_by_name=true" in executed_query


# ===========================================================================
# Test 9 — Malformed file (InvalidInputException): raises NucleusIOError (NE1005)
# ===========================================================================


def test_malformed_file_translates_to_io_error(tmp_path):
    """DuckDB InvalidInputException (corrupt file) → NucleusIOError (NE1005)."""

    class FakeDuckDBInvalidInputError(Exception):
        pass

    FakeDuckDBInvalidInputError.__module__ = "duckdb"
    FakeDuckDBInvalidInputError.__name__ = "InvalidInputException"
    err = FakeDuckDBInvalidInputError("Invalid Input Error: corrupt parquet file")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog"),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        with pytest.raises(NucleusIOError) as exc_info:
            ingest_filesystem_to_iceberg(
                _LOCAL_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE1005"
    assert "duckdb" not in exc_info.value.user_message.lower()


# ===========================================================================
# Test 10 — format='json' → read_json_auto in DuckDB query
# ===========================================================================


def test_explicit_json_format_uses_read_json_auto(tmp_path):
    """format='json' passes read_json_auto to DuckDB query."""
    arrow_table = _make_arrow_table(1)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_filesystem.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_filesystem._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg

        ingest_filesystem_to_iceberg(
            "./data/events.noext",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
            format="json",
        )

    executed_query = mock_conn.execute.call_args[0][0]
    assert "read_json_auto" in executed_query
