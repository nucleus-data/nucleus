"""Tests for ``nucleus.ctx.copy_from_postgres`` — unit tests (dlt mocked).

All tests mock ``dlt.pipeline`` and ``dlt.sources.sql_database.sql_table``
so no Postgres instance is required. Integration tests with testcontainers
are deferred to a follow-up swarm per ADR-014 §Sequencing step 3.

Verifies ``ingest_postgres_to_iceberg()``:
    1. Happy path mock: stubbed LoadInfo with 10 rows returns 10.
    2. write_disposition="append": dlt called with append keyword.
    3. write_disposition="replace": dlt called with replace keyword.
    4. Bad write_disposition: raises NucleusConfigError before calling dlt.
    5. Error translation — bad password: raises NucleusSourceAuthError (NE1009).
    6. Error translation — missing host: raises NucleusSourceConnectionError (NE1001).
    7. Error translation — missing table: raises NucleusSourceNotFound (NE1008).
    8. Pipeline name + dataset name: dlt called with correct namespaced values.
    9. table_format iceberg passed to pipeline.run.
    10. Generic unrecognised errors → NucleusInternalError without classname leak.
    11. Construction-time InvalidPassword → NE1009.
    12. Construction-time OperationalError → NE1001.
    13. Construction-time InvalidCatalogName → NE1001.

Architecture refs:
    ADR-014 §Verification plan (adapted to mocked unit tests)
    docs/internal/research/dlt.md §13.8 (error translation matrix)
    docs/specs/nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from nucleus.errors import (
    NucleusConfigError,
    NucleusSourceAuthError,
    NucleusSourceConnectionError,
    NucleusSourceNotFound,
)

# Constant shared across tests.
_CONN = "postgresql://user:pass@localhost:5432/mydb"
_WAREHOUSE = "/tmp/test_wh"
_NS = "raw"
_DEST = "orders"
_TABLE = "public.orders"


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
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt(10)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        result = ingest_postgres_to_iceberg(
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
    mock_pipeline_cls, mock_sql_table, mock_pipeline, mock_resource = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        ingest_postgres_to_iceberg(
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
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        ingest_postgres_to_iceberg(
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
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusConfigError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN,
                _TABLE,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
                write_disposition="merge",  # type: ignore[arg-type]
            )

    # dlt.pipeline must never have been called
    mock_pipeline_cls.assert_not_called()
    assert "merge" in exc_info.value.user_message


# ===========================================================================
# Test 5 — Error translation: bad password → NucleusSourceAuthError (NE1009)
# ===========================================================================


def test_bad_password_translates_to_source_auth_error(tmp_path):
    """psycopg 'password authentication failed' → NucleusSourceAuthError (NE1009).

    The exception chain mirrors dlt's PipelineStepFailed wrapping psycopg:
        PipelineStepFailed.__context__ = psycopg.OperationalError("password authentication failed")
    """

    class FakePipelineError(Exception):
        pass

    class FakePsycopgOpError(Exception):
        pass

    inner = FakePsycopgOpError("password authentication failed for user 'admin'")
    # Fake the module so _translate_dlt_postgres_exception matches "psycopg" in mod
    type(inner).__module__ = "psycopg.errors"

    outer = FakePipelineError("pipeline failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)
    mock_sql_table = MagicMock(return_value=MagicMock())

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusSourceAuthError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN,
                _TABLE,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    err = exc_info.value
    assert err.error_code == "NE1009"
    assert err.__cause__ is not None  # original chain preserved
    # User-facing message must not contain external classnames (AGENTS.md §11.7)
    user_msg = err.user_message.lower()
    assert "psycopg" not in user_msg
    assert "pipelinestepfailed" not in user_msg
    assert "dlt" not in user_msg


# ===========================================================================
# Test 6 — Error translation: missing host → NucleusSourceConnectionError (NE1001)
# ===========================================================================


def test_missing_host_translates_to_connection_error(tmp_path):
    """'could not translate host name' → NucleusSourceConnectionError (NE1001)."""

    class FakePipelineError(Exception):
        pass

    class FakePsycopgOpError(Exception):
        pass

    inner = FakePsycopgOpError("could not translate host name 'badhost' to address")
    type(inner).__module__ = "psycopg"

    outer = FakePipelineError("extract step failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusSourceConnectionError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1001"
    # No external classnames in user message
    assert "psycopg" not in err.user_message.lower()
    assert "dlt" not in err.user_message.lower()


# ===========================================================================
# Test 7 — Error translation: missing table → NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_missing_table_translates_to_source_not_found(tmp_path):
    """sqlalchemy.exc.NoSuchTableError → NucleusSourceNotFound (NE1008)."""

    class FakePipelineError(Exception):
        pass

    class FakeNoSuchTableError(Exception):
        pass

    # Set class attributes directly (type(Class) is the metaclass `type` — immutable)
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
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1008"
    assert "sqlalchemy" not in err.user_message.lower()
    assert "dlt" not in err.user_message.lower()


# ===========================================================================
# Test 8a — Construction-time: InvalidPassword → NE1009 (reflection / connect)
# ===========================================================================


def test_bad_credentials_raises_nucleus_source_auth_error(tmp_path):
    """sql_table() raises psycopg InvalidPassword before pipeline.run → NE1009."""

    class FakeInvalidPassword(Exception):
        pass

    FakeInvalidPassword.__module__ = "psycopg.errors"
    FakeInvalidPassword.__name__ = "InvalidPassword"

    inner = FakeInvalidPassword('password authentication failed for user "u"')
    mock_sql_table = MagicMock(side_effect=inner)
    mock_pipeline_cls = MagicMock()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusSourceAuthError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1009"
    assert err.__cause__ is not None
    assert err.fix_hint.strip()
    combined = (err.user_message + err.fix_hint).lower()
    for forbidden in ("sqlalchemy", "psycopg", "operationalerror", "dlt", "pipeline"):
        assert forbidden not in combined, f"leaked {forbidden!r}"
    mock_pipeline_cls.assert_not_called()


# ===========================================================================
# Test 8b — Construction-time: sqlalchemy OperationalError → NE1001
# ===========================================================================


def test_unreachable_host_raises_nucleus_source_connection_error(tmp_path):
    """sql_table() raises sqlalchemy OperationalError (connection refused) → NE1001."""

    op_exc = OperationalError(
        "(psycopg.OperationalError) could not connect to server: Connection refused",
        None,
        None,
    )
    mock_sql_table = MagicMock(side_effect=op_exc)
    mock_pipeline_cls = MagicMock()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusSourceConnectionError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1001"
    assert err.__cause__ is not None
    assert err.fix_hint.strip()
    combined = (err.user_message + err.fix_hint).lower()
    for forbidden in ("sqlalchemy", "psycopg", "operationalerror", "dlt", "pipeline"):
        assert forbidden not in combined, f"leaked {forbidden!r}"
    mock_pipeline_cls.assert_not_called()


# ===========================================================================
# Test 8c — Construction-time: InvalidCatalogName → NE1001
# ===========================================================================


def test_missing_database_raises_nucleus_source_connection_error(tmp_path):
    """sql_table() raises psycopg InvalidCatalogName → NE1001 (unknown database)."""

    class FakeInvalidCatalogName(Exception):
        pass

    FakeInvalidCatalogName.__module__ = "psycopg.errors"
    FakeInvalidCatalogName.__name__ = "InvalidCatalogName"

    inner = FakeInvalidCatalogName('database "ghost" does not exist')
    mock_sql_table = MagicMock(side_effect=inner)
    mock_pipeline_cls = MagicMock()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusSourceConnectionError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1001"
    assert err.__cause__ is not None
    assert err.fix_hint.strip()
    combined = (err.user_message + err.fix_hint).lower()
    for forbidden in ("sqlalchemy", "psycopg", "operationalerror", "dlt", "pipeline"):
        assert forbidden not in combined, f"leaked {forbidden!r}"
    mock_pipeline_cls.assert_not_called()


# ===========================================================================
# Test 11 — Pipeline name + dataset name match ADR-014 spec
# ===========================================================================


def test_pipeline_name_and_dataset_name(tmp_path):
    """dlt.pipeline called with namespaced pipeline_name and dataset_name=namespace."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        ingest_postgres_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert mock_pipeline_cls.called
    _, kwargs = mock_pipeline_cls.call_args
    assert kwargs["pipeline_name"] == f"nucleus__pg__{_NS}__{_DEST}"
    assert kwargs["dataset_name"] == _NS


# ===========================================================================
# Test 12 — table_format="iceberg" always passed to pipeline.run
# ===========================================================================


def test_table_format_iceberg_passed_to_run(tmp_path):
    """pipeline.run must always be called with table_format='iceberg'."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        ingest_postgres_to_iceberg(
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

    # Set module on the class itself (type(FakeWeirdDltError) is metaclass `type` — immutable)
    FakeWeirdDltError.__module__ = "dlt.weird_internal"
    err = FakeWeirdDltError("some internal dlt failure message")

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = err
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_postgres._open_catalog"),
    ):
        from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg

        with pytest.raises(NucleusInternalError) as exc_info:
            ingest_postgres_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    result = exc_info.value
    assert result.error_code == "NE3001"
    assert result.__cause__ is not None
    rendered = result.rendered().lower()
    assert "fakeweirddlterror" not in rendered
