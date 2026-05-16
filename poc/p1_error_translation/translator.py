"""Minimal Dagster error translator — PoC #1 (steps 2-3 of README §3).

Scope: baseline 3 handlers + fallback; iteration adds wrapped-library coverage
(Polars / DuckDB / pyiceberg / stdlib). Still short of the 50-case fixture
(README §5). Graduates to ``src/nucleus/coordination/error_translation.py``
once the PoC acceptance criteria (README §2) pass.

Pins (per AGENTS.md §11.12, see ``docs/internal/research/<lib>.md``):
dagster==1.9.5, polars==1.18.0, duckdb==1.1.3, pyiceberg==0.8.1.
Spec: ``docs/specs/nucleus_architecture_v4.1.md`` §6.4 +
``docs/architecture/sequence_error_translation.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusAssetNotMaterialized,
    NucleusCommitConflictError,
    NucleusCommitUnknownError,
    NucleusError,
    NucleusInternalError,
    NucleusIOError,
    NucleusPermissionError,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSchemaEvolutionError,
    NucleusSourceConnectionError,
    NucleusSQLSyntaxError,
)

# A handler takes the original exception and returns a typed NucleusError.
# Handlers MUST NOT raise; if translation fails, return NucleusInternalError.
Handler = Callable[[BaseException], NucleusError]


# Bounded depth so a malformed __cause__ chain can't loop forever.
_MAX_CAUSE_DEPTH = 8


def _iter_causes(exc: BaseException) -> Iterator[BaseException]:
    """Yield ``exc`` then walk its cause chain outer→inner. Walks ``__cause__``
    first; falls through to ``__context__`` when ``__cause__`` is None, unless
    ``__suppress_context__`` is set (``raise X from None``). Bounded by
    ``_MAX_CAUSE_DEPTH`` and cycle-safe so a malformed chain can't loop.
    """
    cur: BaseException | None = exc
    seen: set[int] = set()
    for _ in range(_MAX_CAUSE_DEPTH):
        if cur is None or id(cur) in seen:
            return
        seen.add(id(cur))
        yield cur
        if cur.__cause__ is not None:
            cur = cur.__cause__
        elif getattr(cur, "__suppress_context__", False):
            cur = None
        else:
            cur = cur.__context__


def _unwrap_cause(exc: BaseException) -> BaseException:
    """Return the innermost exception per :func:`_iter_causes` — back-compat
    shape used by ``_dagster_step_handler``; now also walks ``__context__``.
    """
    last = exc
    for c in _iter_causes(exc):
        last = c
    return last


def _dagster_step_handler(exc: BaseException) -> NucleusError:
    """Generic fallback for a Dagster step-execution failure.

    Reached only when ``translate()`` could not match the inner cause to a
    specific library handler (registered ``ConnectionError`` /
    ``ValueError`` / pyiceberg / duckdb / polars / stdlib types). At this
    point all we know is "an asset op failed somewhere"; surface the
    innermost reachable type/message and route to ``NucleusInternalError``.
    """
    inner = _unwrap_cause(exc)
    inner_type = type(inner).__name__
    inner_msg = str(inner) or "(no message)"

    return NucleusInternalError(
        user_message=f"Asset execution failed ({inner_type}): {inner_msg}",
        fix_hint=(
            "If this is unexpected, please file a bug. Run with --debug to see the full traceback."
        ),
        cause=exc,
    )


def _connection_error_handler(exc: BaseException) -> NucleusError:
    """Builtin ``ConnectionError`` (or subclass) raised during source IO."""
    msg = str(exc) or "(no message)"
    return NucleusSourceConnectionError(
        user_message=f"Could not connect to source: {msg}",
        fix_hint="Check host, port, and credentials in your source config.",
        cause=exc,
    )


def _value_error_handler(exc: BaseException) -> NucleusError:
    """Builtin ``ValueError``: schema-flavored messages → ``NucleusSchemaError``,
    everything else routes to ``NucleusInternalError`` (preserves baseline
    behavior for unrelated ValueError surface).
    """
    msg = str(exc) or "(no message)"
    if "schema" in msg.lower():
        return NucleusSchemaError(
            user_message=f"Schema validation failed: {msg}",
            fix_hint="Verify column types and nullability in your asset's return value.",
            cause=exc,
        )
    return NucleusInternalError(
        user_message=f"Asset execution failed (ValueError): {msg}",
        fix_hint=(
            "If this is unexpected, please file a bug. Run with --debug to see the full traceback."
        ),
        cause=exc,
    )


# Appended handlers (DRAFT — Risky tier per AGENTS.md §11.3, human review).
# Each accepts the OUTER exc (preserves ``cause`` chain) and inspects the
# unwrapped inner. Class names verified against the cited research docs.


def _polars_schema_handler(exc: BaseException) -> NucleusError:
    """Polars expression schema mismatch (wrong-typed column in expression)."""
    msg = str(exc) or "(no message)"
    return NucleusSchemaError(
        user_message=f"Schema mismatch in asset transform: {msg}",
        fix_hint="Verify column names and dtypes in your asset's return value match the declared schema.",
        cause=exc,
    )


def _polars_column_not_found_handler(exc: BaseException) -> NucleusError:
    """Polars expression refers to a missing column."""
    msg = str(exc) or "(no message)"
    return NucleusSchemaError(
        user_message=f"Column not found in asset transform: {msg}",
        fix_hint="Check the column name spelling against the upstream asset's schema.",
        cause=exc,
    )


def _duckdb_binder_handler(exc: BaseException) -> NucleusError:
    """DuckDB SQL binder failure (unknown column / type mismatch / ambiguous reference)."""
    msg = str(exc) or "(no message)"
    return NucleusSchemaError(
        user_message=f"SQL binding failed: {msg}",
        fix_hint="Check column and table names referenced in the SQL against the upstream asset's schema.",
        cause=exc,
    )


def _duckdb_catalog_handler(exc: BaseException) -> NucleusError:
    """DuckDB catalog miss (table / view / schema / function not found)."""
    msg = str(exc) or "(no message)"
    return NucleusAssetNotFound(
        user_message=f"SQL referenced an unknown object: {msg}",
        fix_hint="Verify the asset / table / view name is registered. List available assets with `nucleus list`.",
        cause=exc,
    )


def _duckdb_parser_handler(exc: BaseException) -> NucleusError:
    """DuckDB SQL parser failure (invalid syntax)."""
    msg = str(exc) or "(no message)"
    return NucleusSQLSyntaxError(
        user_message=f"SQL syntax error: {msg}",
        fix_hint="Check the SQL for typos, missing FROM clauses, or unclosed quotes. The dialect is not Postgres.",
        cause=exc,
    )


def _pyiceberg_no_such_table_handler(exc: BaseException) -> NucleusError:
    """pyiceberg ``Catalog.load_table`` on a missing identifier."""
    msg = str(exc) or "(no message)"
    return NucleusAssetNotMaterialized(
        user_message=f"Asset has not been materialized yet: {msg}",
        fix_hint="Run the upstream asset first: `nucleus run <asset>`. If you expect it to exist, check the catalog config.",
        cause=exc,
    )


def _pyiceberg_commit_failed_handler(exc: BaseException) -> NucleusError:
    """pyiceberg optimistic-concurrency conflict on commit."""
    msg = str(exc) or "(no message)"
    return NucleusCommitConflictError(
        user_message=f"Concurrent write conflict on the asset's table: {msg}",
        fix_hint="Another writer committed to the same table. Retry the run; if it persists, check for overlapping schedules.",
        cause=exc,
    )


def _file_not_found_handler(exc: BaseException) -> NucleusError:
    """Builtin ``FileNotFoundError`` raised during local IO."""
    msg = str(exc) or "(no message)"
    return NucleusIOError(
        user_message=f"File or path not found: {msg}",
        fix_hint="Check the path exists and is reachable. For source files, verify any glob patterns and credentials.",
        cause=exc,
    )


def _duckdb_out_of_memory_handler(exc: BaseException) -> NucleusError:
    """DuckDB query exceeded ``memory_limit`` and could not spill."""
    msg = str(exc) or "(no message)"
    return NucleusResourceError(
        user_message=f"Query exceeded the memory budget: {msg}",
        fix_hint="Reduce the working set (filter / project earlier) or raise the engine `memory_limit`.",
        cause=exc,
    )


def _duckdb_transaction_handler(exc: BaseException) -> NucleusError:
    """DuckDB concurrent-write conflict on the engine connection."""
    msg = str(exc) or "(no message)"
    return NucleusCommitConflictError(
        user_message=f"Concurrent write conflict in the SQL engine: {msg}",
        fix_hint="Retry the run; if it persists, check whether two materializations target the same asset at once.",
        cause=exc,
    )


def _pyiceberg_commit_state_unknown_handler(exc: BaseException) -> NucleusError:
    """pyiceberg commit failed mid-write — final landed state unknown."""
    msg = str(exc) or "(no message)"
    return NucleusCommitUnknownError(
        user_message=f"Commit status unknown — the write may or may not have landed: {msg}",
        fix_hint="Do NOT blindly retry. Inspect the asset's snapshot history (`nucleus catalog inspect`) first.",
        cause=exc,
    )


def _pyiceberg_validation_handler(exc: BaseException) -> NucleusError:
    """pyiceberg invalid schema evolution (narrowing, required-from-nullable, ...)."""
    msg = str(exc) or "(no message)"
    return NucleusSchemaEvolutionError(
        user_message=f"Schema change rejected as an invalid evolution: {msg}",
        fix_hint="Iceberg allows adding/widening fields; narrowing or nullable→required is not allowed. Review the contract.",
        cause=exc,
    )


def _permission_error_handler(exc: BaseException) -> NucleusError:
    """Builtin ``PermissionError`` from local FS or storage operation."""
    msg = str(exc) or "(no message)"
    return NucleusPermissionError(
        user_message=f"Permission denied on a filesystem operation: {msg}",
        fix_hint="Check that the catalog / warehouse path is writable by the current user.",
        cause=exc,
    )


def _timeout_error_handler(exc: BaseException) -> NucleusError:
    """Builtin ``TimeoutError`` → source connection per task spec; revisit vs.
    ``NucleusTimeoutError`` (query-budget) once we see real telemetry."""
    msg = str(exc) or "(no message)"
    return NucleusSourceConnectionError(
        user_message=f"Connection to a data source timed out: {msg}",
        fix_hint="Check network reachability and credentials; raise the source timeout if the source is genuinely slow.",
        cause=exc,
    )


# Lazy registry: avoids importing dagster at module load. Built on first call.
# NEEDS VERIFICATION on first PoC run: confirm
# ``dagster.DagsterExecutionStepExecutionError`` is the exact class name and
# import path in 1.9.5. Log any rename to docs/internal/research/ai_hallucinations.md.
# Single-element cell avoids ``global`` while preserving lazy init (PLW0603).
_HANDLERS_CELL: list[dict[type, Handler] | None] = [None]


def _registry() -> dict[type, Handler]:
    if _HANDLERS_CELL[0] is None:
        import dagster as dg

        registry: dict[type, Handler] = {
            dg.DagsterExecutionStepExecutionError: _dagster_step_handler,
        }

        # Polars exceptions per docs/internal/research/polars.md §6.
        # Docs: https://docs.pola.rs/api/python/stable/reference/exceptions.html
        try:
            from polars.exceptions import ColumnNotFoundError, SchemaError

            registry[SchemaError] = _polars_schema_handler
            registry[ColumnNotFoundError] = _polars_column_not_found_handler
        except ImportError:
            pass

        # DuckDB exceptions per docs/internal/research/duckdb.md §6 (all inherit from duckdb.Error).
        # Docs: https://duckdb.org/docs/stable/clients/python/dbapi
        try:
            import duckdb

            registry[duckdb.BinderException] = _duckdb_binder_handler
            registry[duckdb.CatalogException] = _duckdb_catalog_handler
            registry[duckdb.ParserException] = _duckdb_parser_handler
            registry[duckdb.OutOfMemoryException] = _duckdb_out_of_memory_handler
            registry[duckdb.TransactionException] = _duckdb_transaction_handler
        except ImportError:
            pass

        # pyiceberg exceptions per docs/internal/research/pyiceberg.md §6. NEEDS VERIFICATION
        # on first PoC run — research doc flags constructor + __cause__ chaining,
        # especially the ValidationError / CommitStateUnknownException pair.
        # Docs: https://py.iceberg.apache.org/api/#exceptions
        try:
            from pyiceberg.exceptions import (
                CommitFailedException,
                CommitStateUnknownException,
                NoSuchTableError,
                ValidationError,
            )

            registry[NoSuchTableError] = _pyiceberg_no_such_table_handler
            registry[CommitFailedException] = _pyiceberg_commit_failed_handler
            registry[CommitStateUnknownException] = _pyiceberg_commit_state_unknown_handler
            registry[ValidationError] = _pyiceberg_validation_handler
        except ImportError:
            pass

        # Stdlib exception handlers. ``PermissionError`` and ``FileNotFoundError``
        # subclass ``OSError``; ``TimeoutError`` (PEP 3151) and ``ConnectionError``
        # also subclass ``OSError``. Order matters here only for documentation —
        # ``translate()`` matches by ``isinstance``, so the specific subclasses
        # remain reachable. Docs: https://docs.python.org/3/library/exceptions.html
        registry[FileNotFoundError] = _file_not_found_handler
        registry[PermissionError] = _permission_error_handler
        registry[TimeoutError] = _timeout_error_handler
        registry[ConnectionError] = _connection_error_handler
        registry[ValueError] = _value_error_handler
        _HANDLERS_CELL[0] = registry
    assert _HANDLERS_CELL[0] is not None
    return _HANDLERS_CELL[0]


# Deferred candidates (verified in research docs, skipped to stay under LOC
# budget, revisit next iteration): polars.{NoDataError, ComputeError,
# ShapeError}; duckdb.{IOException, ConversionException, ConnectionException};
# pyiceberg.{NoSuchNamespaceError, AuthorizationExpiredError}.


def translate(exc: BaseException) -> NucleusError:
    """Translate any exception to a NucleusError.

    Walks ``__cause__`` / ``__context__`` and prefers a *specific* library
    handler over the generic Dagster-wrapper fallback. This matters for
    Dagster 1.9.5: ``materialize()`` re-raises the user's original exception
    (e.g. ``duckdb.BinderException``) with a ``DagsterExecutionStepExecutionError``
    on its ``__context__`` (and a back-edge ``__cause__``), so the captured
    chain is two hops with a synthetic cycle. We need to route to the
    library handler for the original, not the generic Dagster handler.

    Idempotent for an already-typed NucleusError; falls back to
    ``NucleusInternalError`` when nothing in the registry matches.
    """
    if isinstance(exc, NucleusError):
        return exc

    registry = _registry()
    candidates = list(_iter_causes(exc))

    # The Dagster step-wrapper is treated as a generic fallback so it does not
    # hide a more-specific library handler that matched a deeper candidate.
    import dagster as dg

    dagster_wrapper_type = dg.DagsterExecutionStepExecutionError

    # First pass: any specific (non-Dagster-wrapper) handler that matches a
    # candidate wins. We pass the *matched candidate* (not the outer ``exc``)
    # so handlers see the original library message, then preserve the outer
    # chain on the result via ``__cause__``.
    for candidate in candidates:
        if isinstance(candidate, dagster_wrapper_type):
            continue
        for exc_type, handler in registry.items():
            if exc_type is dagster_wrapper_type:
                continue
            if isinstance(candidate, exc_type):
                result = handler(candidate)
                if exc is not candidate:
                    result.__cause__ = exc
                return result

    # Second pass: only the Dagster wrapper matched. Use its generic handler.
    for candidate in candidates:
        if isinstance(candidate, dagster_wrapper_type):
            return registry[dagster_wrapper_type](exc)

    return NucleusInternalError(
        user_message=f"Unexpected error ({type(exc).__name__}): {exc}",
        fix_hint="No translator registered for this exception type. Please file a bug.",
        cause=exc,
    )
