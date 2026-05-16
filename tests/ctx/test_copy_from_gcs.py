"""Tests for ``nucleus.ctx.copy_from_gcs`` — unit tests (DuckDB + gcsfs mocked).

All tests mock ``duckdb.connect``, ``gcsfs.GCSFileSystem``, and the pyiceberg
catalog so no real GCS account is required. A real GCS sandbox would be needed
for integration tests; those are deferred per ADR-020.

Verifies ``ingest_gcs_to_iceberg()``:
    1. Bad prefix (not gs://): raises NucleusConfigError.
    2. Unknown extension without explicit format: raises NucleusConfigError.
    3. Happy path parquet: DuckDB + catalog mocked, returns row count.
    4. GCS filesystem registered with DuckDB via register_filesystem.
    5. Auth error (403): raises NucleusSourceAuthError (NE1009).
    6. Object not found (404): raises NucleusSourceNotFound (NE1008).
    7. Network timeout: raises NucleusNetworkError (NE1010).
    8. Schema mismatch (BinderException): raises NucleusSchemaError (NE2001).
    9. Memory limit (OutOfMemoryException): raises NucleusResourceError (NE2003).
    10. FileNotFoundError from gcsfs: raises NucleusSourceNotFound (NE1008).

Architecture refs:
    docs/internal/research/gcs_duckdb.md §6 (error classification)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

_GCS_URI = "gs://my-bucket/data/orders.parquet"
_NS = "raw"
_DEST = "orders"


def _make_arrow_table(n: int = 4) -> pa.Table:
    return pa.table({"id": pa.array(range(n)), "val": pa.array([float(i) for i in range(n)])})


# ===========================================================================
# Test 1 — Bad prefix: raises NucleusConfigError
# ===========================================================================


def test_bad_prefix_raises_config_error(tmp_path):
    """URI not starting with gs:// raises NucleusConfigError."""
    from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

    with pytest.raises(NucleusConfigError) as exc_info:
        ingest_gcs_to_iceberg(
            "s3://bucket/file.parquet",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert "gs://" in exc_info.value.fix_hint


# ===========================================================================
# Test 2 — Unknown extension without explicit format: raises NucleusConfigError
# ===========================================================================


def test_unknown_extension_raises_config_error(tmp_path):
    """gs://bucket/file.xyz with no explicit format raises NucleusConfigError."""
    from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

    with pytest.raises(NucleusConfigError) as exc_info:
        ingest_gcs_to_iceberg(
            "gs://my-bucket/data/orders.xyz",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert "format=" in exc_info.value.fix_hint


# ===========================================================================
# Test 3 — Happy path: returns correct row count
# ===========================================================================


def test_happy_path_returns_row_count(tmp_path):
    """DuckDB returns 4-row Arrow table → ingest_gcs_to_iceberg returns 4."""
    arrow_table = _make_arrow_table(4)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.arrow.return_value = arrow_table
    mock_duckdb = MagicMock()
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()

    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    mock_iceberg_table = MagicMock()
    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = mock_iceberg_table

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        result = ingest_gcs_to_iceberg(
            _GCS_URI,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert result == 4
    mock_iceberg_table.append.assert_called_once_with(arrow_table)


# ===========================================================================
# Test 4 — GCS filesystem registered with DuckDB
# ===========================================================================


def test_gcs_filesystem_registered_with_duckdb(tmp_path):
    """conn.register_filesystem must be called with a PyArrow filesystem."""
    arrow_table = _make_arrow_table(1)

    mock_conn = MagicMock()
    mock_conn.execute.return_value.arrow.return_value = arrow_table
    mock_duckdb = MagicMock()
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcs_instance = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = mock_gcs_instance

    mock_pafs = MagicMock()
    mock_pa_fs = MagicMock()
    mock_pafs.PyFileSystem.return_value = mock_pa_fs
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    mock_catalog = MagicMock()
    mock_catalog.create_table.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog", return_value=mock_catalog),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        ingest_gcs_to_iceberg(
            _GCS_URI,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    # Verify GCSFileSystem was constructed (ADC chain) and registered.
    mock_gcsfs.GCSFileSystem.assert_called_once()
    mock_conn.register_filesystem.assert_called_once_with(mock_pa_fs)


# ===========================================================================
# Test 5 — Auth error (403): raises NucleusSourceAuthError (NE1009)
# ===========================================================================


def test_access_denied_translates_to_source_auth_error(tmp_path):
    """PermissionError from gcsfs → NucleusSourceAuthError (NE1009)."""
    err = PermissionError("403 Forbidden: Access denied to bucket 'my-bucket'")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()
    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog"),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        with pytest.raises(NucleusSourceAuthError) as exc_info:
            ingest_gcs_to_iceberg(
                _GCS_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    err_out = exc_info.value
    assert err_out.error_code == "NE1009"
    combined = (err_out.user_message + err_out.fix_hint).lower()
    for forbidden in ("gcsfs", "duckdb", "permissionerror"):
        assert forbidden not in combined, f"leaked {forbidden!r}"


# ===========================================================================
# Test 6 — Object not found (FileNotFoundError): raises NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_object_not_found_translates_to_source_not_found(tmp_path):
    """FileNotFoundError from gcsfs → NucleusSourceNotFound (NE1008)."""
    err = FileNotFoundError("gs://my-bucket/data/missing.parquet: 404 Not Found")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()
    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog"),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_gcs_to_iceberg(
                _GCS_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE1008"


# ===========================================================================
# Test 7 — Network timeout: raises NucleusNetworkError (NE1010)
# ===========================================================================


def test_network_timeout_translates_to_network_error(tmp_path):
    """Connection timeout from gcsfs → NucleusNetworkError (NE1010)."""
    err = TimeoutError("connection timed out connecting to storage.googleapis.com")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()
    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog"),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        with pytest.raises(NucleusNetworkError) as exc_info:
            ingest_gcs_to_iceberg(
                _GCS_URI,
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
    err = FakeDuckDBBinderError("Column mismatch across GCS files")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()
    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog"),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        with pytest.raises(NucleusSchemaError) as exc_info:
            ingest_gcs_to_iceberg(
                "gs://my-bucket/data/*.parquet",
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
    err = FakeDuckDBOOMError("Out of Memory Error")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()
    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog"),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        with pytest.raises(NucleusResourceError) as exc_info:
            ingest_gcs_to_iceberg(
                _GCS_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE2003"


# ===========================================================================
# Test 10 — 404 message error: raises NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_not_found_message_translates_to_source_not_found(tmp_path):
    """Generic '404' message in exception → NucleusSourceNotFound (NE1008)."""
    err = Exception("404: Object gs://my-bucket/data/missing.parquet not found")

    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = err
    mock_duckdb.connect.return_value = mock_conn

    mock_gcsfs = MagicMock()
    mock_gcsfs.GCSFileSystem.return_value = MagicMock()
    mock_pafs = MagicMock()
    mock_pafs.PyFileSystem.return_value = MagicMock()
    mock_pafs.FSSpecHandler.return_value = MagicMock()

    with (
        patch("nucleus.ctx.copy_from_gcs._GCS_AVAILABLE", True),
        patch("nucleus.ctx.copy_from_gcs.duckdb", mock_duckdb),
        patch("nucleus.ctx.copy_from_gcs.gcsfs", mock_gcsfs),
        patch("nucleus.ctx.copy_from_gcs.pafs", mock_pafs),
        patch("nucleus.ctx.copy_from_gcs._open_catalog"),
    ):
        from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_gcs_to_iceberg(
                _GCS_URI,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    assert exc_info.value.error_code == "NE1008"
