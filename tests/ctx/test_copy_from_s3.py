"""Tests for ``nucleus.ctx.copy_from_s3`` — unit tests (DuckDB mocked).

All tests mock ``duckdb.connect`` and the pyiceberg catalog so no real S3
account or MinIO instance is required.

Verifies ``ingest_s3_to_iceberg()``:
    1. Bad prefix (not s3://): raises NucleusConfigError.
    2. Unknown extension without explicit format: raises NucleusConfigError.
    3. Explicit format override (parquet): uses read_parquet function.
    4. Happy path parquet: DuckDB + catalog mocked, returns row count.
    5. Auth error (403 Access Denied): raises NucleusSourceAuthError (NE1009).
    6. Object not found (NoSuchKey): raises NucleusSourceNotFound (NE1008).
    7. Network error (503 Slow Down): raises NucleusNetworkError (NE1010).
    8. Schema mismatch (BinderException): raises NucleusSchemaError (NE2001).
    9. Memory limit (OutOfMemoryException): raises NucleusResourceError (NE2003).
    10. union_by_name=true passed in the DuckDB query.

Architecture refs:
    docs/research/s3_duckdb.md §6 (error classification)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pyarrow as pa
import pytest

from nucleus.errors import (
    NucleusConfigError,
    NucleusNetworkError,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSourceAuthError,
    NucleusSourceNotFound,
)

_S3_URI = "s3://my-bucket/data/orders.parquet"
_NS = "raw"
_DEST = "orders"


def _make_arrow_table(n: int = 3) -> pa.Table:
    return pa.table({"id": pa.array(range(n)), "name": pa.array([f"row_{i}" for i in range(n)])})


def _patch_duckdb_and_catalog(arrow_table: pa.Table) -> tuple[MagicMock, MagicMock]:
    """Return (mock_duckdb_module, mock_catalog) ready to patch."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.arrow.return_value = arrow_table
    mock_duckdb = MagicMock()
    mock_duckdb.connect.return_value = mock_conn
    return mock_duckdb, mock_conn


# ===========================================================================
# Test 1 — Bad prefix: raises NucleusConfigError
# ===========================================================================


def test_bad_prefix_raises_config_error(tmp_path):
    """URI not starting with s3:// raises NucleusConfigError before DuckDB is called."""
    from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

    with pytest.raises(NucleusConfigError) as exc_info:
        ingest_s3_to_iceberg(
            "gs://bucket/file.parquet",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert "s3://" in exc_info.value.fix_hint


# ===========================================================================
# Test 2 — Unknown extension without explicit format: raises NucleusConfigError
# ===========================================================================


def test_unknown_extension_raises_config_error(tmp_path):
    """s3://bucket/file.xyz with no explicit format raises NucleusConfigError."""
    from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

    with pytest.raises(NucleusConfigError) as exc_info:
        ingest_s3_to_iceberg(
            "s3://my-bucket/data/orders.xyz",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert "format=" in exc_info.value.fix_hint


# ===========================================================================
# Test 3 — Explicit format override: uses correct DuckDB read function
# ===========================================================================


def test_explicit_format_uses_correct_duckdb_function(tmp_path):
    """format='csv' passes read_csv_auto to DuckDB query."""
    arrow_table = _make_arrow_table(2)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_iceberg_table = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = mock_iceberg_table

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        ingest_s3_to_iceberg(
            "s3://my-bucket/data/orders.noext",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
            format="csv",
        )

    executed_query = mock_conn.execute.call_args[0][0]
    assert "read_csv_auto" in executed_query


# ===========================================================================
# Test 4 — Happy path: returns correct row count
# ===========================================================================


def test_happy_path_returns_row_count(tmp_path):
    """DuckDB returns 3-row Arrow table → ingest_s3_to_iceberg returns 3."""
    arrow_table = _make_arrow_table(3)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_iceberg_table = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = mock_iceberg_table

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        result = ingest_s3_to_iceberg(
            _S3_URI,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert result == 3
    mock_iceberg_table.append.assert_called_once_with(arrow_table)


# ===========================================================================
# Test 5 — Auth error (403): raises NucleusSourceAuthError (NE1009)
# ===========================================================================


def test_access_denied_translates_to_source_auth_error(tmp_path):
    """DuckDB IOException with '403 Access Denied' → NucleusSourceAuthError (NE1009)."""

    class FakeDuckDBIOError(Exception):
        pass

    FakeDuckDBIOError.__module__ = "duckdb"
    FakeDuckDBIOError.__name__ = "IOException"
    err = FakeDuckDBIOError("HTTP 403: Access Denied for key orders.parquet")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog"),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        with pytest.raises(NucleusSourceAuthError) as exc_info:
            ingest_s3_to_iceberg(
                _S3_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    err_out = exc_info.value
    assert err_out.error_code == "NE1009"
    combined = (err_out.user_message + err_out.fix_hint).lower()
    for forbidden in ("duckdb", "ioexception", "dlt"):
        assert forbidden not in combined, f"leaked {forbidden!r}"


# ===========================================================================
# Test 6 — Object not found (NoSuchKey): raises NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_object_not_found_translates_to_source_not_found(tmp_path):
    """DuckDB IOException with 'NoSuchKey' → NucleusSourceNotFound (NE1008)."""

    class FakeDuckDBIOError(Exception):
        pass

    FakeDuckDBIOError.__module__ = "duckdb"
    FakeDuckDBIOError.__name__ = "IOException"
    err = FakeDuckDBIOError("HTTP 404: NoSuchKey: key orders.parquet does not exist")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog"),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_s3_to_iceberg(
                _S3_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE1008"


# ===========================================================================
# Test 7 — Network throttle (503): raises NucleusNetworkError (NE1010)
# ===========================================================================


def test_s3_throttle_translates_to_network_error(tmp_path):
    """DuckDB IOException with '503 Slow Down' → NucleusNetworkError (NE1010)."""

    class FakeDuckDBIOError(Exception):
        pass

    FakeDuckDBIOError.__module__ = "duckdb"
    FakeDuckDBIOError.__name__ = "IOException"
    err = FakeDuckDBIOError("HTTP 503: Slow Down")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog"),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        with pytest.raises(NucleusNetworkError) as exc_info:
            ingest_s3_to_iceberg(
                _S3_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE1010"


# ===========================================================================
# Test 8 — Schema mismatch (BinderException): raises NucleusSchemaError (NE2001)
# ===========================================================================


def test_schema_mismatch_translates_to_schema_error(tmp_path):
    """DuckDB BinderException → NucleusSchemaError (NE2001)."""

    class FakeDuckDBBinderError(Exception):
        pass

    FakeDuckDBBinderError.__module__ = "duckdb"
    FakeDuckDBBinderError.__name__ = "BinderException"
    err = FakeDuckDBBinderError("Column type mismatch across files")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog"),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        with pytest.raises(NucleusSchemaError) as exc_info:
            ingest_s3_to_iceberg(
                "s3://my-bucket/data/*.parquet",
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE2001"


# ===========================================================================
# Test 9 — Memory limit (OutOfMemoryException): raises NucleusResourceError (NE2003)
# ===========================================================================


def test_out_of_memory_translates_to_resource_error(tmp_path):
    """DuckDB OutOfMemoryException → NucleusResourceError (NE2003)."""

    class FakeDuckDBOOMError(Exception):
        pass

    FakeDuckDBOOMError.__module__ = "duckdb"
    FakeDuckDBOOMError.__name__ = "OutOfMemoryException"
    err = FakeDuckDBOOMError("Out of Memory Error: could not allocate block")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog"),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        with pytest.raises(NucleusResourceError) as exc_info:
            ingest_s3_to_iceberg(
                _S3_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE2003"


# ===========================================================================
# Test 10 — union_by_name=true in DuckDB query
# ===========================================================================


def test_union_by_name_in_query(tmp_path):
    """DuckDB query must include union_by_name=true for glob-safe schema unification."""
    arrow_table = _make_arrow_table(1)
    mock_duckdb, mock_conn = _patch_duckdb_and_catalog(arrow_table)

    mock_iceberg_table = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = mock_iceberg_table

    with (
        patch("nucleus.ctx.copy_from_s3.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_s3._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg

        ingest_s3_to_iceberg(
            _S3_URI,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    executed_query = mock_conn.execute.call_args[0][0]
    assert "union_by_name=true" in executed_query
