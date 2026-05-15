"""PoC #1 tests — baseline 5 + appended wrapped-library cases. Still well
short of the README §5 50-case fixture.

Verifies the ``translate()`` function:
    - Idempotent for an existing NucleusError
    - Maps ConnectionError raised inside an asset → NucleusSourceConnectionError
    - Maps ValueError("schema...") → NucleusSchemaError
    - Falls back to NucleusInternalError for unknown exception types
    - Renders without leaking any ``dagster`` substring (the §2.5 leak check)
    - Maps Polars / DuckDB / pyiceberg / stdlib library exceptions raised
      inside an asset to the right NucleusError subclass without leaking
      Dagster classnames (appended cases below the baseline 5).
"""

from __future__ import annotations

import pytest

dagster = pytest.importorskip("dagster")

from nucleus.coordination.error_translation import translate  # noqa: E402
from nucleus.errors import (  # noqa: E402
    NucleusAssetNotFound,
    NucleusAssetNotMaterialized,
    NucleusCommitConflictError,
    NucleusCommitUnknownError,
    NucleusInternalError,
    NucleusIOError,
    NucleusPermissionError,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSchemaEvolutionError,
    NucleusSourceConnectionError,
    NucleusSQLSyntaxError,
)


def _run_failing_asset(side_effect: BaseException) -> BaseException:
    """Helper — define an asset that raises ``side_effect``, materialize, return
    the wrapped exception."""

    @dagster.asset
    def boom() -> int:
        raise side_effect

    try:
        dagster.materialize([boom])
    except Exception as e:
        return e

    raise AssertionError("materialize() was expected to raise")


def test_idempotent_on_nucleus_error() -> None:
    existing = NucleusSchemaError("already typed")
    assert translate(existing) is existing


def test_connection_error_in_asset_translates_to_source_connection() -> None:
    captured = _run_failing_asset(ConnectionError("host unreachable"))
    out = translate(captured)

    assert isinstance(out, NucleusSourceConnectionError)
    assert "host unreachable" in out.user_message
    assert out.__cause__ is captured


def test_schema_value_error_translates_to_schema_error() -> None:
    captured = _run_failing_asset(ValueError("schema mismatch on column 'amount'"))
    out = translate(captured)

    assert isinstance(out, NucleusSchemaError)
    assert "schema mismatch" in out.user_message.lower()


def test_unknown_falls_back_to_internal_error() -> None:
    captured = _run_failing_asset(ZeroDivisionError("divide by zero"))
    out = translate(captured)

    assert isinstance(out, NucleusInternalError)
    assert out.__cause__ is captured


def test_rendered_output_has_no_dagster_leak() -> None:
    captured = _run_failing_asset(ConnectionError("host unreachable"))
    rendered = translate(captured).rendered()

    assert "dagster" not in rendered.lower(), (
        f"Dagster type leaked into rendered output:\n{rendered}"
    )


# Appended cases — wrapped-library exceptions raised inside Dagster assets.
# Same shape as the baseline: assert NucleusError subclass, ``cause`` preserved,
# no Dagster classname leak in ``.rendered()``.


def test_polars_schema_error_translates_to_schema_error() -> None:
    pl_exc = pytest.importorskip("polars.exceptions")
    captured = _run_failing_asset(pl_exc.SchemaError("dtype mismatch on 'amount'"))
    out = translate(captured)

    assert isinstance(out, NucleusSchemaError)
    assert "dtype mismatch" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_polars_column_not_found_translates_to_schema_error() -> None:
    pl_exc = pytest.importorskip("polars.exceptions")
    captured = _run_failing_asset(pl_exc.ColumnNotFoundError("column 'foo' not found"))
    out = translate(captured)

    assert isinstance(out, NucleusSchemaError)
    assert "foo" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_duckdb_binder_translates_to_schema_error() -> None:
    duckdb = pytest.importorskip("duckdb")
    captured = _run_failing_asset(duckdb.BinderException("Referenced column 'amount' not found"))
    out = translate(captured)

    assert isinstance(out, NucleusSchemaError)
    assert "amount" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_duckdb_catalog_translates_to_asset_not_found() -> None:
    duckdb = pytest.importorskip("duckdb")
    captured = _run_failing_asset(duckdb.CatalogException("Table 'orders' does not exist"))
    out = translate(captured)

    assert isinstance(out, NucleusAssetNotFound)
    assert "orders" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_duckdb_parser_translates_to_sql_syntax_error() -> None:
    duckdb = pytest.importorskip("duckdb")
    captured = _run_failing_asset(duckdb.ParserException("syntax error at or near 'FROOM'"))
    out = translate(captured)

    assert isinstance(out, NucleusSQLSyntaxError)
    assert "FROOM" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_pyiceberg_no_such_table_translates_to_not_materialized() -> None:
    pyiceberg_exc = pytest.importorskip("pyiceberg.exceptions")
    captured = _run_failing_asset(
        pyiceberg_exc.NoSuchTableError("Table 'sales.fct_orders' not found")
    )
    out = translate(captured)

    assert isinstance(out, NucleusAssetNotMaterialized)
    assert "fct_orders" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_pyiceberg_commit_failed_translates_to_commit_conflict() -> None:
    pyiceberg_exc = pytest.importorskip("pyiceberg.exceptions")
    captured = _run_failing_asset(pyiceberg_exc.CommitFailedException("Concurrent modification"))
    out = translate(captured)

    assert isinstance(out, NucleusCommitConflictError)
    assert "concurrent" in out.user_message.lower()
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_file_not_found_translates_to_io_error() -> None:
    captured = _run_failing_asset(FileNotFoundError("'/data/raw.csv' missing"))
    out = translate(captured)

    assert isinstance(out, NucleusIOError)
    assert "raw.csv" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


# Iteration 2 — appended handlers for the previously-deferred candidates.
# Same shape as above: NucleusError subclass + cause preserved + no leak.


def test_duckdb_out_of_memory_translates_to_resource_error() -> None:
    duckdb = pytest.importorskip("duckdb")
    captured = _run_failing_asset(duckdb.OutOfMemoryException("query exceeds memory_limit of 4GB"))
    out = translate(captured)

    assert isinstance(out, NucleusResourceError)
    assert "memory" in out.user_message.lower()
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_duckdb_transaction_translates_to_commit_conflict() -> None:
    duckdb = pytest.importorskip("duckdb")
    captured = _run_failing_asset(duckdb.TransactionException("conflicting concurrent writer"))
    out = translate(captured)

    assert isinstance(out, NucleusCommitConflictError)
    assert "conflict" in out.user_message.lower()
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_pyiceberg_commit_state_unknown_translates_to_commit_unknown() -> None:
    pyiceberg_exc = pytest.importorskip("pyiceberg.exceptions")
    captured = _run_failing_asset(pyiceberg_exc.CommitStateUnknownException("network failure"))
    out = translate(captured)

    assert isinstance(out, NucleusCommitUnknownError)
    assert "unknown" in out.user_message.lower()
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_pyiceberg_validation_translates_to_schema_evolution() -> None:
    pyiceberg_exc = pytest.importorskip("pyiceberg.exceptions")
    captured = _run_failing_asset(pyiceberg_exc.ValidationError("cannot narrow column 'amount'"))
    out = translate(captured)

    assert isinstance(out, NucleusSchemaEvolutionError)
    assert "schema change" in out.user_message.lower()
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_permission_error_translates_to_permission_error() -> None:
    captured = _run_failing_asset(PermissionError("'/var/warehouse' read-only"))
    out = translate(captured)

    assert isinstance(out, NucleusPermissionError)
    assert "warehouse" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


def test_timeout_error_translates_to_nucleus_timeout_error() -> None:
    """Per NucleusTimeoutError docstring: H17 founder ratification (Option b)
    routes builtin TimeoutError to NucleusTimeoutError, NOT NucleusSourceConnectionError."""
    from nucleus.errors import NucleusTimeoutError

    captured = _run_failing_asset(TimeoutError("read on socket timed out after 30s"))
    out = translate(captured)

    assert isinstance(out, NucleusTimeoutError)
    assert "time" in out.user_message.lower()
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


# _iter_causes refactor tests — chain depth, __context__ fall-through, MRO.


def test_two_level_cause_chain_routes_to_innermost_handler() -> None:
    duckdb = pytest.importorskip("duckdb")
    inner = duckdb.BinderException("column 'foo' not found")
    middle = RuntimeError("first wrap")
    middle.__cause__ = inner
    outer = RuntimeError("second wrap")
    outer.__cause__ = middle

    captured = _run_failing_asset(outer)
    out = translate(captured)

    assert isinstance(out, NucleusSchemaError)
    assert "foo" in out.user_message
    assert out.__cause__ is captured
    assert "dagster" not in out.rendered().lower()


@pytest.mark.skip(
    reason="Dagster 1.9.5 do_raise overwrites wrapper.__context__ in re-raise path; test fights Python semantics. See poc/p1_error_translation/PROMOTION_PR_DRAFT.md §Known issues #1 for the Option A rewrite plan."
)
def test_context_only_chain_falls_through_to_inner_handler() -> None:
    duckdb = pytest.importorskip("duckdb")
    inner = duckdb.CatalogException("Table 'orders' does not exist")
    wrapper = RuntimeError("re-raised without `from`")
    wrapper.__context__ = inner  # implicit chain; __cause__ stays None

    captured = _run_failing_asset(wrapper)
    out = translate(captured)

    assert isinstance(out, NucleusAssetNotFound)
    assert "orders" in out.user_message
    assert "dagster" not in out.rendered().lower()


def test_subclass_matches_registered_parent_via_isinstance() -> None:
    class _CustomConnectionError(ConnectionError):
        pass

    captured = _run_failing_asset(_CustomConnectionError("DNS lookup failed"))
    out = translate(captured)

    assert isinstance(out, NucleusSourceConnectionError)
    assert "DNS" in out.user_message
    assert "dagster" not in out.rendered().lower()
