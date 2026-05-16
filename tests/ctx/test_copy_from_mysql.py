"""Tests for ``nucleus.ctx.copy_from_mysql`` — unit tests (dlt + pymysql mocked).

All tests mock ``dlt.pipeline`` and ``dlt.sources.sql_database.sql_table``
so no MySQL instance is required. Integration tests with testcontainers
are deferred to a follow-up swarm per ADR-014 §"MySQL parity" sequencing.

Verifies ``ingest_mysql_to_iceberg()``:
    1. Happy path mock: stubbed LoadInfo with 10 rows returns 10.
    2. write_disposition="append": dlt called with append keyword.
    3. write_disposition="replace": dlt called with replace keyword.
    4. Bad write_disposition: raises NucleusConfigError before calling dlt.
    5. Bad scheme: raises NucleusConfigError (NE5001) before calling dlt.
    6. mysql+pymysql scheme accepted verbatim (no normalisation).
    7. Error translation — bad password: raises NucleusSourceAuthError (NE1009).
    8. Error translation — can't connect: raises NucleusSourceConnectionError (NE1001).
    9. Error translation — missing table: raises NucleusSourceNotFound (NE1008).
    10. Error translation — schema drift: raises NucleusSchemaEvolutionError (NE1004).
    11. Pipeline name + dataset name: dlt called with correct namespaced values.
    12. table_format='iceberg' always passed to pipeline.run.
    13. Generic dlt error stays NucleusInternalError (no classname leak).
    14. ``db.table`` qualified source_table forwards schema kwarg to dlt.

Architecture refs:
    ADR-014 §"MySQL parity (2026-05-14)" (Verification plan)
    docs/internal/research/dlt.md §13.8 (error translation matrix)
    docs/specs/nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nucleus.errors import (
    NucleusConfigError,
    NucleusSchemaEvolutionError,
    NucleusSourceAuthError,
    NucleusSourceConnectionError,
    NucleusSourceNotFound,
)

# Constants shared across tests.
_CONN = "mysql://user:pass@localhost:3306/mydb"
_CONN_DRIVER = "mysql+pymysql://user:pass@localhost:3306/mydb"
_NS = "raw"
_DEST = "orders"
_TABLE = "orders"
_TABLE_QUALIFIED = "shop.orders"


def _make_load_info(row_count: int = 10) -> Any:
    """Build a minimal LoadInfo stub matching _row_count_from_load_info expectations.

    The structure mirrors what _row_count_from_load_info inspects:
        load_info.load_packages[n].jobs.get("completed_jobs")[n].row_counts
    """
    job = SimpleNamespace(row_counts={_DEST: row_count})
    pkg = SimpleNamespace(jobs={"completed_jobs": [job]})
    return SimpleNamespace(load_packages=[pkg])


def _patch_dlt(row_count: int = 10) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return a tuple of mocks: (pipeline_cls, sql_table, pipeline_instance, resource)."""
    mock_load_info = _make_load_info(row_count)
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_load_info
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)
    mock_resource = MagicMock()
    mock_sql_table = MagicMock(return_value=mock_resource)
    return mock_pipeline_cls, mock_sql_table, mock_pipeline, mock_resource


# ===========================================================================
# Test 1 — Happy path: LoadInfo with 10 rows → function returns 10
# ===========================================================================


def test_happy_path_returns_row_count(tmp_path):
    """Mock pipeline returns LoadInfo with 10 completed rows → returns 10."""
    mock_pipeline_cls, mock_sql_table, _mock_pipeline, _ = _patch_dlt(10)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        result = ingest_mysql_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert result == 10


# ===========================================================================
# Test 2 — write_disposition="append": dlt called with append
# ===========================================================================


def test_write_disposition_append_passed_to_dlt(tmp_path):
    """dlt.pipeline.run must be called with write_disposition='append'."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        ingest_mysql_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
            write_disposition="append",
        )

    mock_pipeline.run.assert_called_once()
    _, kwargs = mock_pipeline.run.call_args
    assert kwargs.get("write_disposition") == "append"


# ===========================================================================
# Test 3 — write_disposition="replace": dlt called with replace
# ===========================================================================


def test_write_disposition_replace_passed_to_dlt(tmp_path):
    """dlt.pipeline.run must be called with write_disposition='replace'."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        ingest_mysql_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
            write_disposition="replace",
        )

    _, kwargs = mock_pipeline.run.call_args
    assert kwargs.get("write_disposition") == "replace"


# ===========================================================================
# Test 4 — Bad write_disposition: raises NucleusConfigError, dlt NOT called
# ===========================================================================


def test_bad_write_disposition_raises_config_error_no_dlt_call(tmp_path):
    """write_disposition='merge' raises NucleusConfigError before any dlt call."""
    mock_pipeline_cls = MagicMock()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusConfigError) as exc_info:
            ingest_mysql_to_iceberg(
                _CONN,
                _TABLE,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
                write_disposition="merge",  # type: ignore[arg-type]
            )

    mock_pipeline_cls.assert_not_called()
    assert "merge" in exc_info.value.user_message


# ===========================================================================
# Test 5 — Bad scheme: raises NucleusConfigError (NE5001), dlt NOT called
# ===========================================================================


def test_bad_scheme_raises_config_error_no_dlt_call(tmp_path):
    """A non-mysql URI raises NucleusConfigError with NE5001 before dlt is touched."""
    mock_pipeline_cls = MagicMock()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusConfigError) as exc_info:
            ingest_mysql_to_iceberg(
                "postgresql://user:pw@localhost/db",
                _TABLE,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    err = exc_info.value
    assert err.error_code == "NE5001"
    assert "mysql" in err.user_message.lower()
    mock_pipeline_cls.assert_not_called()


# ===========================================================================
# Test 6 — mysql+pymysql:// is accepted verbatim (driver-qualified)
# ===========================================================================


def test_mysql_pymysql_scheme_accepted(tmp_path):
    """A ``mysql+pymysql://`` URI passes validation and reaches dlt."""
    mock_pipeline_cls, mock_sql_table, _mock_pipeline, _ = _patch_dlt(7)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        result = ingest_mysql_to_iceberg(
            _CONN_DRIVER,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert result == 7
    _, kwargs = mock_sql_table.call_args
    assert kwargs["credentials"] == _CONN_DRIVER


# ===========================================================================
# Test 7 — Error translation: bad password → NucleusSourceAuthError (NE1009)
# ===========================================================================


def test_bad_password_translates_to_source_auth_error(tmp_path):
    """pymysql 'Access denied' / code 1045 → NucleusSourceAuthError (NE1009).

    The exception chain mirrors dlt's PipelineStepFailed wrapping pymysql:
        PipelineStepFailed.__context__ = pymysql.OperationalError(1045, "Access denied")
    """

    class FakePipelineError(Exception):
        pass

    class FakePyMySQLOpError(Exception):
        pass

    inner = FakePyMySQLOpError(1045, "Access denied for user 'admin'@'localhost'")
    type(inner).__module__ = "pymysql.err"

    outer = FakePipelineError("pipeline failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)
    mock_sql_table = MagicMock(return_value=MagicMock())

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusSourceAuthError) as exc_info:
            ingest_mysql_to_iceberg(
                _CONN,
                _TABLE,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    err = exc_info.value
    assert err.error_code == "NE1009"
    assert err.__cause__ is not None
    user_msg = err.user_message.lower()
    for forbidden in ("pymysql", "pipelinestepfailed", "dlt", "mysql"):
        assert forbidden not in user_msg, f"leaked {forbidden!r} in user_message"


# ===========================================================================
# Test 8 — Error translation: can't connect → NucleusSourceConnectionError (NE1001)
# ===========================================================================


def test_cant_connect_translates_to_connection_error(tmp_path):
    """pymysql 2003 'Can't connect' → NucleusSourceConnectionError (NE1001)."""

    class FakePipelineError(Exception):
        pass

    class FakePyMySQLOpError(Exception):
        pass

    inner = FakePyMySQLOpError(2003, "Can't connect to MySQL server on 'badhost' (timed out)")
    type(inner).__module__ = "pymysql"

    outer = FakePipelineError("extract step failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusSourceConnectionError) as exc_info:
            ingest_mysql_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1001"
    user_msg = err.user_message.lower()
    for forbidden in ("pymysql", "mysql", "dlt"):
        assert forbidden not in user_msg, f"leaked {forbidden!r} in user_message"


# ===========================================================================
# Test 9 — Error translation: missing table → NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_missing_table_translates_to_source_not_found(tmp_path):
    """pymysql 1146 / sqlalchemy.exc.NoSuchTableError → NucleusSourceNotFound (NE1008)."""

    class FakePipelineError(Exception):
        pass

    class FakeNoSuchTableError(Exception):
        pass

    FakeNoSuchTableError.__name__ = "NoSuchTableError"
    FakeNoSuchTableError.__module__ = "sqlalchemy.exc"
    inner = FakeNoSuchTableError("orders")

    outer = FakePipelineError("extract failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_mysql_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1008"
    assert "sqlalchemy" not in err.user_message.lower()
    assert "dlt" not in err.user_message.lower()


# ===========================================================================
# Test 10 — Error translation: schema drift → NucleusSchemaEvolutionError (NE1004)
# ===========================================================================


def test_unknown_column_translates_to_schema_evolution_error(tmp_path):
    """pymysql 1054 'Unknown column' → NucleusSchemaEvolutionError (NE1004)."""

    class FakePipelineError(Exception):
        pass

    class FakePyMySQLProgError(Exception):
        pass

    inner = FakePyMySQLProgError(1054, "Unknown column 'created_at' in 'field list'")
    type(inner).__module__ = "pymysql.err"

    outer = FakePipelineError("normalize step failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusSchemaEvolutionError) as exc_info:
            ingest_mysql_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1004"
    user_msg = err.user_message.lower()
    for forbidden in ("pymysql", "mysql", "dlt"):
        assert forbidden not in user_msg, f"leaked {forbidden!r} in user_message"


# ===========================================================================
# Test 11 — Pipeline name + dataset name match ADR-014 spec
# ===========================================================================


def test_pipeline_name_and_dataset_name(tmp_path):
    """dlt.pipeline called with namespaced pipeline_name and dataset_name=namespace."""
    mock_pipeline_cls, mock_sql_table, _mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        ingest_mysql_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert mock_pipeline_cls.called
    _, kwargs = mock_pipeline_cls.call_args
    # ``my`` prefix differentiates from Postgres ``pg`` to avoid state collisions
    # when two ingest paths target the same dest namespace+table.
    assert kwargs["pipeline_name"] == f"nucleus__my__{_NS}__{_DEST}"
    assert kwargs["dataset_name"] == _NS


# ===========================================================================
# Test 12 — table_format='iceberg' always passed to pipeline.run
# ===========================================================================


def test_table_format_iceberg_passed_to_run(tmp_path):
    """pipeline.run must always be called with table_format='iceberg'."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        ingest_mysql_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    _, kwargs = mock_pipeline.run.call_args
    assert kwargs.get("table_format") == "iceberg"


# ===========================================================================
# Test 13 — Generic dlt error stays as NucleusInternalError (no leak)
# ===========================================================================


def test_generic_error_wraps_as_internal_no_classname_leak(tmp_path):
    """Any unrecognised exception → NucleusInternalError; classname must not leak."""
    from nucleus.errors import NucleusInternalError

    class FakeWeirdDltError(Exception):
        pass

    FakeWeirdDltError.__module__ = "dlt.weird_internal"
    err = FakeWeirdDltError("some internal dlt failure message")

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = err
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        with pytest.raises(NucleusInternalError) as exc_info:
            ingest_mysql_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    result = exc_info.value
    assert result.error_code == "NE3001"
    assert result.__cause__ is not None
    rendered = result.rendered().lower()
    assert "fakeweirddlterror" not in rendered


# ===========================================================================
# Test 14 — db.table qualifier splits into schema kwarg for dlt
# ===========================================================================


def test_qualified_source_table_passes_schema_kwarg(tmp_path):
    """``db.table`` source_table is split: dlt receives schema='db', table='table'."""
    mock_pipeline_cls, mock_sql_table, _mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        ingest_mysql_to_iceberg(
            _CONN,
            _TABLE_QUALIFIED,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    _, kwargs = mock_sql_table.call_args
    assert kwargs["table"] == "orders"
    assert kwargs["schema"] == "shop"


# ===========================================================================
# Test 15 — Unqualified table: no schema kwarg forwarded (URL default)
# ===========================================================================


def test_unqualified_source_table_omits_schema_kwarg(tmp_path):
    """Unqualified ``orders`` → dlt called WITHOUT schema kwarg (URL default DB)."""
    mock_pipeline_cls, mock_sql_table, _mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_mysql._open_catalog"),
    ):
        from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg

        ingest_mysql_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    _, kwargs = mock_sql_table.call_args
    assert kwargs["table"] == "orders"
    assert "schema" not in kwargs
