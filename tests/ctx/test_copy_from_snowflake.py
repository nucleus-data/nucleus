"""Tests for ``nucleus.ctx.copy_from_snowflake`` — unit tests (dlt mocked).

All tests mock ``dlt.pipeline`` and ``dlt.sources.sql_database.sql_table``
so no Snowflake account is required. A real Snowflake sandbox would be needed
for integration tests; those are deferred per ADR-019 §Sequencing.

Verifies ``ingest_snowflake_to_iceberg()``:
    1. Bad prefix: raises NucleusConfigError before any dlt call.
    2. Bad write_disposition: raises NucleusConfigError before any dlt call.
    3. Happy path: stubbed LoadInfo with 5 rows returns 5.
    4. Pipeline name is namespaced with ``sf__`` prefix.
    5. table_format="iceberg" always passed to pipeline.run.
    6. Error translation — bad password: raises NucleusSourceAuthError (NE1009).
    7. Error translation — account not found: raises NucleusSourceConnectionError (NE1001).
    8. Error translation — missing table: raises NucleusSourceNotFound (NE1008).
    9. Generic unrecognised error → NucleusInternalError (no classname leak).
    10. Schema.table split: schema kwarg passed to sql_table when qualified name given.

Architecture refs:
    ADR-019 §Verification plan
    docs/internal/research/snowflake.md §4 (error code matrix)
    docs/specs/nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nucleus.errors import (
    NucleusConfigError,
    NucleusInternalError,
    NucleusSourceAuthError,
    NucleusSourceConnectionError,
    NucleusSourceNotFound,
)

_CONN = "snowflake://user:pass@orgname-acctname/mydb/PUBLIC"
_TABLE = "PUBLIC.ORDERS"
_NS = "raw"
_DEST = "orders"


def _make_load_info(row_count: int = 5) -> Any:
    """Minimal LoadInfo stub matching _row_count_from_load_info expectations."""
    job = SimpleNamespace(row_counts={_DEST: row_count})
    pkg = SimpleNamespace(jobs={"completed_jobs": [job]})
    return SimpleNamespace(load_packages=[pkg])


def _patch_dlt(row_count: int = 5) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    mock_load_info = _make_load_info(row_count)
    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = mock_load_info
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)
    mock_resource = MagicMock()
    mock_sql_table = MagicMock(return_value=mock_resource)
    return mock_pipeline_cls, mock_sql_table, mock_pipeline, mock_resource


# ===========================================================================
# Test 1 — Bad prefix: raises NucleusConfigError, dlt NOT called
# ===========================================================================


def test_bad_prefix_raises_config_error(tmp_path):
    """URI not starting with snowflake:// → NucleusConfigError before any dlt call."""
    mock_pipeline_cls = MagicMock()

    with patch("dlt.pipeline", mock_pipeline_cls):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        with pytest.raises(NucleusConfigError) as exc_info:
            ingest_snowflake_to_iceberg(
                "postgresql://user:pass@host/db",
                _TABLE,
                warehouse_dir=tmp_path,
                dest_namespace=_NS,
                dest_table=_DEST,
            )

    mock_pipeline_cls.assert_not_called()
    assert "snowflake://" in exc_info.value.user_message


# ===========================================================================
# Test 2 — Bad write_disposition: raises NucleusConfigError before dlt call
# ===========================================================================


def test_bad_write_disposition_raises_config_error(tmp_path):
    """write_disposition='merge' raises NucleusConfigError before any dlt call."""
    mock_pipeline_cls = MagicMock()

    with patch("dlt.pipeline", mock_pipeline_cls):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        with pytest.raises(NucleusConfigError) as exc_info:
            ingest_snowflake_to_iceberg(
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
# Test 3 — Happy path: LoadInfo with 5 rows → function returns 5
# ===========================================================================


def test_happy_path_returns_row_count(tmp_path):
    """Mock pipeline returns LoadInfo with 5 rows → function returns 5."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt(5)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        result = ingest_snowflake_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    assert result == 5


# ===========================================================================
# Test 4 — Pipeline name uses ``sf__`` prefix + namespace + dest_table
# ===========================================================================


def test_pipeline_name_namespaced_with_sf_prefix(tmp_path):
    """dlt.pipeline called with namespaced pipeline_name='nucleus__sf__ns__dest'."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        ingest_snowflake_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    _, kwargs = mock_pipeline_cls.call_args
    assert kwargs["pipeline_name"] == f"nucleus__sf__{_NS}__{_DEST}"
    assert kwargs["dataset_name"] == _NS


# ===========================================================================
# Test 5 — table_format="iceberg" always passed to pipeline.run
# ===========================================================================


def test_table_format_iceberg_passed_to_run(tmp_path):
    """pipeline.run must always be called with table_format='iceberg'."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        ingest_snowflake_to_iceberg(
            _CONN,
            _TABLE,
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    _, kwargs = mock_pipeline.run.call_args
    assert kwargs.get("table_format") == "iceberg"


# ===========================================================================
# Test 6 — Error translation: bad password → NucleusSourceAuthError (NE1009)
# ===========================================================================


def test_bad_password_translates_to_source_auth_error(tmp_path):
    """Snowflake 251001 auth error → NucleusSourceAuthError (NE1009); no classname leak."""

    class FakePipelineError(Exception):
        pass

    class FakeSnowflakeProgrammingError(Exception):
        pass

    inner = FakeSnowflakeProgrammingError(
        "251001 (08001): Incorrect username or password was specified."
    )
    type(inner).__module__ = "snowflake.connector.errors"
    outer = FakePipelineError("pipeline step failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        with pytest.raises(NucleusSourceAuthError) as exc_info:
            ingest_snowflake_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1009"
    assert err.__cause__ is not None
    combined = (err.user_message + err.fix_hint).lower()
    # "snowflake://" is the product URL scheme — allowed in fix_hint.
    # Internal library classnames must NOT appear per AGENTS.md §11.7.
    for forbidden in ("dlt", "programmingerror", "pipelinestepfailed"):
        assert forbidden not in combined, f"leaked {forbidden!r}"


# ===========================================================================
# Test 7 — Error translation: account not found → NucleusSourceConnectionError (NE1001)
# ===========================================================================


def test_account_not_found_translates_to_connection_error(tmp_path):
    """Snowflake 250001 account error → NucleusSourceConnectionError (NE1001)."""

    class FakeSnowflakeOpError(Exception):
        pass

    inner = FakeSnowflakeOpError("250001: Account does not exist or is not accessible.")
    type(inner).__module__ = "snowflake.connector.errors"

    class FakePipelineError(Exception):
        pass

    outer = FakePipelineError("extract failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        with pytest.raises(NucleusSourceConnectionError) as exc_info:
            ingest_snowflake_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1001"
    combined = (err.user_message + err.fix_hint).lower()
    # "snowflake.md" reference in fix_hint is acceptable documentation link.
    for forbidden in ("dlt", "operationalerror", "pipelinestepfailed"):
        assert forbidden not in combined, f"leaked {forbidden!r}"


# ===========================================================================
# Test 8 — Error translation: missing table → NucleusSourceNotFound (NE1008)
# ===========================================================================


def test_missing_table_translates_to_source_not_found(tmp_path):
    """Snowflake 002003 SQL compilation error → NucleusSourceNotFound (NE1008)."""

    class FakeSnowflakeProgrammingError(Exception):
        pass

    inner = FakeSnowflakeProgrammingError(
        "002003 (42S02): SQL compilation error: Object 'ORDERS' does not exist or not authorized."
    )
    type(inner).__module__ = "snowflake.connector.errors"

    class FakePipelineError(Exception):
        pass

    outer = FakePipelineError("extract failed")
    outer.__context__ = inner  # type: ignore[attr-defined]

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = outer
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        with pytest.raises(NucleusSourceNotFound) as exc_info:
            ingest_snowflake_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    err = exc_info.value
    assert err.error_code == "NE1008"
    combined = (err.user_message + err.fix_hint).lower()
    # "Snowflake names default to UPPERCASE" is user-visible product guidance — allowed.
    for forbidden in ("dlt", "programmingerror", "pipelinestepfailed"):
        assert forbidden not in combined, f"leaked {forbidden!r}"


# ===========================================================================
# Test 9 — Generic dlt error → NucleusInternalError (no classname leak)
# ===========================================================================


def test_generic_error_wraps_as_internal_no_classname_leak(tmp_path):
    """Unrecognised exception → NucleusInternalError; external classname must not leak."""

    class FakeWeirdSnowflakeError(Exception):
        pass

    FakeWeirdSnowflakeError.__module__ = "snowflake.weird_internal"
    err = FakeWeirdSnowflakeError("some internal failure message")

    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = err
    mock_pipeline_cls = MagicMock(return_value=mock_pipeline)

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", MagicMock(return_value=MagicMock())),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        with pytest.raises(NucleusInternalError) as exc_info:
            ingest_snowflake_to_iceberg(
                _CONN, _TABLE, warehouse_dir=tmp_path, dest_namespace=_NS, dest_table=_DEST
            )

    result = exc_info.value
    assert result.error_code == "NE3001"
    assert result.__cause__ is not None
    rendered = result.rendered().lower()
    assert "fakeweirdsnowflakeerror" not in rendered


# ===========================================================================
# Test 10 — Schema.table split: schema kwarg passed when qualified name given
# ===========================================================================


def test_qualified_table_passes_schema_kwarg(tmp_path):
    """'SCHEMA.TABLE' qualified name splits into schema= kwarg for sql_table."""
    mock_pipeline_cls, mock_sql_table, mock_pipeline, _ = _patch_dlt()

    with (
        patch("dlt.pipeline", mock_pipeline_cls),
        patch("dlt.sources.sql_database.sql_table", mock_sql_table),
        patch("nucleus.ctx.copy_from_snowflake._open_catalog"),
    ):
        from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg

        ingest_snowflake_to_iceberg(
            _CONN,
            "MYSCHEMA.ORDERS",
            warehouse_dir=tmp_path,
            dest_namespace=_NS,
            dest_table=_DEST,
        )

    _, kwargs = mock_sql_table.call_args
    assert kwargs.get("schema") == "MYSCHEMA"
    assert kwargs.get("table") == "ORDERS"
