"""Dagster error translator promoted to production on 2026-05-13.

Promoted from `poc/p1_error_translation/translator.py` to
`src/nucleus/coordination/error_translation.py` per PoC #1 promotion.

Scope: baseline 3 handlers + fallback; iteration adds wrapped-library coverage
(Polars / DuckDB / pyiceberg / stdlib).

Pins (per AGENTS.md §11.12, see ``docs/internal/research/<lib>.md``):
dagster==1.9.5, polars==1.18.0, duckdb==1.1.3, pyiceberg==0.11.1.
Spec: ``docs/specs/nucleus_architecture_v4.1.md`` §6.4 +
``docs/architecture/sequence_error_translation.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusAssetNotMaterialized,
    NucleusCatalogError,
    NucleusCommitConflictError,
    NucleusCommitUnknownError,
    NucleusError,
    NucleusInternalError,
    NucleusIOError,
    NucleusNetworkError,
    NucleusPermissionError,
    NucleusRaceConditionDuringWrite,
    NucleusResourceError,
    NucleusSchemaError,
    NucleusSchemaEvolutionError,
    NucleusSourceAuthError,
    NucleusSourceConnectionError,
    NucleusSourceNotFound,
    NucleusSQLSyntaxError,
    NucleusTimeoutError,
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

    The chain walk skips Dagster wrapper types: for a chain like
    ``[user_exc=RuntimeError, DagsterExecutionStepExecutionError]`` the
    plain ``_unwrap_cause(exc)`` would return the wrapper as the inner —
    leaking ``DagsterExecutionStepExecutionError`` into ``user_message``
    and violating v4.1 §6.4. The filter is module-prefix-based so future
    Dagster releases that move wrapper classes between submodules still
    match without requiring an explicit class allow-list that could drift
    per AGENTS.md §11.12.
    """
    inner: BaseException | None = None
    for candidate in _iter_causes(exc):
        if (type(candidate).__module__ or "").startswith("dagster"):
            continue
        inner = candidate
        break

    if inner is None:
        inner_type = "asset body"
        inner_msg = "Asset materialization failed"
    else:
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
    """Builtin ``TimeoutError`` → ``NucleusTimeoutError`` (NE3005).

    Per ``nucleus.errors.NucleusTimeoutError`` docstring: "Per H17 founder
    ratification (Option b), builtin TimeoutError from non-source paths
    routes here (NOT to NucleusSourceConnectionError)."
    """
    msg = str(exc) or "(no message)"
    return NucleusTimeoutError(
        user_message=f"An operation exceeded its time budget: {msg}",
        fix_hint=(
            "Check network reachability if this is a source operation, "
            "or raise the timeout budget if the query / write is genuinely slow."
        ),
        cause=exc,
    )


def _file_exists_handler(exc: BaseException) -> NucleusError:
    """Builtin ``FileExistsError`` → ``NucleusRaceConditionDuringWrite`` (NE5018).

    Fires when a write path's mkdir fails because the target already
    exists as a non-directory entry. Closes chaos J3 (CF-1) translate()
    gap — see ``docs/internal/release-process/chaos_test_results.md`` §J3.

    Docs: https://docs.python.org/3/library/exceptions.html#FileExistsError
    """
    msg = str(exc) or "(no message)"
    return NucleusRaceConditionDuringWrite(
        user_message=(
            f"Could not create the write target — a non-directory entry already "
            f"exists at the path: {msg}"
        ),
        fix_hint=(
            "Remove the conflicting file (or restore the directory) at the warehouse / "
            "catalog path, then re-run. If another process is racing, retry; the AMA "
            "will serialize via the advisory lock."
        ),
        cause=exc,
    )


def _pydantic_validation_handler(exc: BaseException) -> NucleusError:
    """pydantic v2 ``ValidationError`` → ``NucleusCatalogError`` (NE1007).

    The most common source is pyiceberg's ``TableMetadata`` parse: a
    corrupted ``*.metadata.json`` (truncated, empty, externally edited)
    surfaces as ``pydantic_core._pydantic_core.ValidationError`` from
    ``pyiceberg.table.metadata.parse_raw``. Closes chaos J8 (CF-2 + CF-3)
    translate() gap — see ``docs/internal/release-process/chaos_test_results.md`` §J8.

    Docs: https://docs.pydantic.dev/latest/api/pydantic_core/#pydantic_core.ValidationError
    Docs: https://py.iceberg.apache.org/api/  (pyiceberg==0.11.1)
    """
    msg = str(exc) or "(no message)"
    summary = msg.splitlines()[0] if msg else "validation failed"
    return NucleusCatalogError(
        user_message=(f"Catalog metadata is corrupt or unreadable: {summary}"),
        fix_hint=(
            "Inspect the catalog's *.metadata.json files for truncation or external "
            "edits. Restore from a recent snapshot if available, or re-materialize the "
            "asset from the source."
        ),
        cause=exc,
    )


# Lazy registry: avoids importing dagster at module load. Built on first call.
# NEEDS VERIFICATION on first PoC run: confirm
# ``dagster.DagsterExecutionStepExecutionError`` is the exact class name and
# import path in 1.9.5. Log any rename to docs/internal/research/ai_hallucinations.md.
_HANDLERS: dict[type, Handler] | None = None


def _registry() -> dict[type, Handler]:
    global _HANDLERS  # noqa: PLW0603 — lazy single-init handler map; import cost deferred per v4.1 coordination layer.
    if _HANDLERS is None:
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

        # pydantic v2 ValidationError — surfaces from pyiceberg's TableMetadata
        # parse when *.metadata.json is corrupt (J8 / CF-2 / CF-3). Registered
        # BEFORE ValueError because pydantic.ValidationError subclasses ValueError
        # in v2; isinstance dispatch order is unspecified for dict iteration, so
        # the specific handler must register before the generic ValueError.
        # Docs: https://docs.pydantic.dev/latest/api/pydantic_core/#pydantic_core.ValidationError
        try:
            from pydantic import ValidationError as _PydanticValidationError

            registry[_PydanticValidationError] = _pydantic_validation_handler
        except ImportError:
            pass

        # Stdlib exception handlers. ``PermissionError`` and ``FileNotFoundError``
        # subclass ``OSError``; ``TimeoutError`` (PEP 3151) and ``ConnectionError``
        # also subclass ``OSError``; ``FileExistsError`` likewise. Order matters
        # here only for documentation — ``translate()`` matches by ``isinstance``,
        # so the specific subclasses remain reachable.
        # Docs: https://docs.python.org/3/library/exceptions.html
        registry[FileNotFoundError] = _file_not_found_handler
        registry[FileExistsError] = _file_exists_handler
        registry[PermissionError] = _permission_error_handler
        registry[TimeoutError] = _timeout_error_handler
        registry[ConnectionError] = _connection_error_handler
        registry[ValueError] = _value_error_handler
        _HANDLERS = registry
    return _HANDLERS


# Deferred candidates (verified in research docs, skipped to stay under LOC
# budget, revisit next iteration): polars.{NoDataError, ComputeError,
# ShapeError}; duckdb.{IOException, ConversionException, ConnectionException};
# pyiceberg.{NoSuchNamespaceError, AuthorizationExpiredError}.


def _translate_dlt_postgres_exception(exc: BaseException) -> NucleusError:  # noqa: PLR0911
    """Translate a dlt / psycopg / sqlalchemy Postgres-source exception to a NucleusError.

    Implements the two-level ``__context__`` walk for dlt's ``PipelineStepFailed``
    per ``docs/internal/research/dlt.md`` §5.4 + §13.8. Maps Postgres-source-specific
    errors to existing NE-codes per ADR-014 §Scope (no new code allocations).

    User-facing ``user_message`` and ``fix_hint`` MUST NOT contain the strings
    "dlt", "psycopg", "sqlalchemy", or "PipelineStepFailed" per AGENTS.md §11.7.
    The full exception chain is preserved in ``cause``.

    Docs: https://dlthub.com/docs/general-usage/schema-contracts
          (PipelineStepFailed two-level __context__ pattern documented at §5.4)
    """
    # Walk the full cause chain (outer PipelineStepFailed → sqlalchemy wrapper →
    # psycopg inner). _iter_causes handles both __cause__ and __context__ links,
    # matching the two-level walk required per docs/internal/research/dlt.md §5.4.
    for candidate in _iter_causes(exc):
        mod = (type(candidate).__module__ or "").lower()
        cls = type(candidate).__name__
        msg = str(candidate).lower()

        # ------------------------------------------------------------------ #
        # psycopg errors
        # Docs: https://www.psycopg.org/psycopg3/docs/api/errors.html
        # ------------------------------------------------------------------ #
        if "psycopg" in mod:
            # Auth: InvalidPassword / "password authentication failed" message.
            if cls == "InvalidPassword" or "password authentication" in msg:
                return NucleusSourceAuthError(
                    user_message=(
                        "The data source rejected the provided credentials. "
                        "Check your username and password."
                    ),
                    fix_hint=(
                        "Verify the username and password in your connection string. "
                        "Connection strings take the form: "
                        "postgresql://user:pass@host:5432/db"
                    ),
                    cause=exc,
                )
            # Database does not exist.
            if cls == "InvalidCatalogName":
                return NucleusSourceConnectionError(
                    user_message=(
                        "The database name in the connection string does not exist. "
                        "Check the database name and try again."
                    ),
                    fix_hint=(
                        "Verify the database name in your connection string. "
                        "Form: postgresql://user:pass@host:5432/mydb"
                    ),
                    cause=exc,
                )
            # Network / host reachability.
            if any(
                phrase in msg
                for phrase in (
                    "could not translate host name",
                    "connection refused",
                    "could not connect",
                    "name or service not known",
                    "no route to host",
                )
            ):
                return NucleusSourceConnectionError(
                    user_message=(
                        "Could not reach the data source. "
                        "Check the host, port, and network connectivity."
                    ),
                    fix_hint=(
                        "Verify the host and port in your connection string are reachable. "
                        "Try: postgresql://user:pass@host:5432/db"
                    ),
                    cause=exc,
                )
            # SSL / TLS handshake.
            if "ssl" in msg or "tls" in msg:
                return NucleusNetworkError(
                    user_message=(
                        "A secure connection to the data source could not be established. "
                        "Check your SSL/TLS settings."
                    ),
                    fix_hint=(
                        "Verify ?sslmode= and ?sslrootcert= in your connection string. "
                        "See https://www.postgresql.org/docs/current/libpq-ssl.html"
                    ),
                    cause=exc,
                )
            # Schema drift: column removed between reflection and read.
            if cls == "UndefinedColumn" or ("column" in msg and "does not exist" in msg):
                return NucleusSchemaEvolutionError(
                    user_message=(
                        "A column referenced in the source table no longer exists. "
                        "The source schema may have changed during ingest."
                    ),
                    fix_hint=(
                        "Inspect the source table schema and retry. "
                        "If the column was removed intentionally, update the ingest."
                    ),
                    cause=exc,
                )

        # ------------------------------------------------------------------ #
        # sqlalchemy errors
        # Docs: https://docs.sqlalchemy.org/en/20/core/exceptions.html
        # ------------------------------------------------------------------ #
        if "sqlalchemy" in mod:
            if cls == "NoSuchTableError":
                return NucleusSourceNotFound(
                    user_message=(
                        "The source table was not found in the database. "
                        "Verify the table name and schema."
                    ),
                    fix_hint=(
                        "Pass the fully-qualified table name as 'schema.table', "
                        "e.g. 'public.orders'. Check the table exists in the database."
                    ),
                    cause=exc,
                )
            # Operational errors (host/port/DNS) also surface wrapped in sqlalchemy.
            if cls == "OperationalError" and any(
                phrase in msg
                for phrase in (
                    "could not connect",
                    "connection refused",
                    "could not translate host",
                )
            ):
                return NucleusSourceConnectionError(
                    user_message=(
                        "Could not connect to the data source. Check host, port, and credentials."
                    ),
                    fix_hint=(
                        "Verify the connection string. Form: postgresql://user:pass@host:5432/db"
                    ),
                    cause=exc,
                )

    # Catch-all → NucleusInternalError (NE3001).
    # Strips external classnames from user_message per AGENTS.md §11.7.
    inner_msg = str(exc) or "(no message)"
    return NucleusInternalError(
        user_message=f"Data source ingest failed unexpectedly: {inner_msg}",
        fix_hint=(
            "Check the connection string, table name, and destination configuration. "
            "Run with --debug to see the full traceback."
        ),
        cause=exc,
    )


def _translate_dlt_mysql_exception(exc: BaseException) -> NucleusError:  # noqa: PLR0911
    """Translate a dlt / pymysql / sqlalchemy MySQL-source exception to a NucleusError.

    Mirrors :func:`_translate_dlt_postgres_exception` per ADR-014
    §"MySQL parity (2026-05-14)". Implements the two-level ``__context__`` walk
    for dlt's ``PipelineStepFailed`` per ``docs/internal/research/dlt.md`` §5.4 + §13.8
    and maps MySQL-source-specific errors to existing NE-codes (no new
    code allocations).

    User-facing ``user_message`` and ``fix_hint`` MUST NOT contain the strings
    "dlt", "pymysql", "sqlalchemy", "MySQL", or "PipelineStepFailed" per
    AGENTS.md §11.7. The full exception chain is preserved in ``cause``.

    Docs:
        https://pymysql.readthedocs.io/en/latest/modules/err.html
        https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html
    """
    for candidate in _iter_causes(exc):
        mod = (type(candidate).__module__ or "").lower()
        cls = type(candidate).__name__
        msg = str(candidate).lower()

        # ------------------------------------------------------------------ #
        # pymysql errors
        # Docs: https://pymysql.readthedocs.io/en/latest/modules/err.html
        # MySQL error codes:
        #   1045 — access denied (auth)
        #   1049 — unknown database
        #   2003 — can't connect to MySQL server
        #   1146 — table doesn't exist
        #   1054 — unknown column (schema drift)
        # ------------------------------------------------------------------ #
        if "pymysql" in mod:
            # PyMySQL errors carry the numeric MySQL error code in args[0].
            code: int | None = None
            args = getattr(candidate, "args", None)
            if args and isinstance(args[0], int):
                code = args[0]

            # Auth: 1045 or "access denied".
            if code == 1045 or "access denied" in msg:
                return NucleusSourceAuthError(
                    user_message=(
                        "The data source rejected the provided credentials. "
                        "Check your username and password."
                    ),
                    fix_hint=(
                        "Verify the username and password in your connection string. "
                        "Connection strings take the form: "
                        "mysql://user:pass@host:3306/db"
                    ),
                    cause=exc,
                )
            # Unknown database: 1049 or "unknown database".
            if code == 1049 or "unknown database" in msg:
                return NucleusSourceConnectionError(
                    user_message=(
                        "The database name in the connection string does not exist. "
                        "Check the database name and try again."
                    ),
                    fix_hint=(
                        "Verify the database name in your connection string. "
                        "Form: mysql://user:pass@host:3306/mydb"
                    ),
                    cause=exc,
                )
            # Host/port reachability: 2003 or message-string forms.
            if code == 2003 or any(
                phrase in msg
                for phrase in (
                    "can't connect to",
                    "cannot connect to",
                    "connection refused",
                    "could not connect",
                    "name or service not known",
                    "no route to host",
                )
            ):
                return NucleusSourceConnectionError(
                    user_message=(
                        "Could not reach the data source. "
                        "Check the host, port, and network connectivity."
                    ),
                    fix_hint=(
                        "Verify the host and port in your connection string are reachable. "
                        "Try: mysql://user:pass@host:3306/db"
                    ),
                    cause=exc,
                )
            # Missing table: 1146 or "table ... doesn't exist".
            if code == 1146 or ("doesn't exist" in msg and "table" in msg):
                return NucleusSourceNotFound(
                    user_message=(
                        "The source table was not found in the database. "
                        "Verify the table name and database."
                    ),
                    fix_hint=(
                        "Confirm the table exists in the configured database. "
                        "Pass 'db.table' to override the URL's default database."
                    ),
                    cause=exc,
                )
            # SSL / TLS handshake.
            if "ssl" in msg or "tls" in msg:
                return NucleusNetworkError(
                    user_message=(
                        "A secure connection to the data source could not be established. "
                        "Check your SSL/TLS settings."
                    ),
                    fix_hint=(
                        "Verify ?ssl_disabled=false (and matching CA params) in your "
                        "connection string. See "
                        "https://dev.mysql.com/doc/refman/8.0/en/encrypted-connections.html"
                    ),
                    cause=exc,
                )
            # Schema drift: column removed between reflection and read (1054).
            if code == 1054 or ("unknown column" in msg):
                return NucleusSchemaEvolutionError(
                    user_message=(
                        "A column referenced in the source table no longer exists. "
                        "The source schema may have changed during ingest."
                    ),
                    fix_hint=(
                        "Inspect the source table schema and retry. "
                        "If the column was removed intentionally, update the ingest."
                    ),
                    cause=exc,
                )

        # ------------------------------------------------------------------ #
        # sqlalchemy errors (shared with Postgres translator — same classes
        # surface for any SQL dialect via the SQLAlchemy core).
        # Docs: https://docs.sqlalchemy.org/en/20/core/exceptions.html
        # ------------------------------------------------------------------ #
        if "sqlalchemy" in mod:
            if cls == "NoSuchTableError":
                return NucleusSourceNotFound(
                    user_message=(
                        "The source table was not found in the database. "
                        "Verify the table name and database."
                    ),
                    fix_hint=(
                        "Confirm the table exists in the configured database. "
                        "Pass 'db.table' to override the URL's default database."
                    ),
                    cause=exc,
                )
            if cls == "OperationalError" and any(
                phrase in msg
                for phrase in (
                    "could not connect",
                    "can't connect",
                    "cannot connect",
                    "connection refused",
                    "could not translate host",
                )
            ):
                return NucleusSourceConnectionError(
                    user_message=(
                        "Could not connect to the data source. Check host, port, and credentials."
                    ),
                    fix_hint=("Verify the connection string. Form: mysql://user:pass@host:3306/db"),
                    cause=exc,
                )

    inner_msg = str(exc) or "(no message)"
    return NucleusInternalError(
        user_message=f"Data source ingest failed unexpectedly: {inner_msg}",
        fix_hint=(
            "Check the connection string, table name, and destination configuration. "
            "Run with --debug to see the full traceback."
        ),
        cause=exc,
    )


def _translate_dlt_snowflake_exception(exc: BaseException) -> NucleusError:  # noqa: PLR0911
    """Translate a dlt / snowflake-connector / sqlalchemy Snowflake-source exception to a NucleusError.

    Implements the two-level ``__context__`` walk for dlt's ``PipelineStepFailed``
    per ``docs/internal/research/dlt.md`` §5.4. Maps Snowflake-source-specific errors to
    existing NE-codes per ADR-019 §Scope (no new code allocations).

    User-facing ``user_message`` and ``fix_hint`` MUST NOT contain the strings
    "dlt", "snowflake", "sqlalchemy", or "PipelineStepFailed" per AGENTS.md §11.7.

    Docs:
        https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-error-codes
        https://dlthub.com/docs/general-usage/schema-contracts (PipelineStepFailed)
    """
    for candidate in _iter_causes(exc):
        mod = (type(candidate).__module__ or "").lower()
        cls = type(candidate).__name__
        msg = str(candidate).lower()

        # ------------------------------------------------------------------ #
        # Snowflake connector errors
        # Docs: https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-error-codes
        # Error codes (in message string from snowflake.connector.errors):
        #   250001 — Account does not exist or is not accessible
        #   251001 — Incorrect username or password (auth)
        #   251006 — User is disabled
        #   002003 — SQL compilation: object not found (table not found)
        # ------------------------------------------------------------------ #
        if "snowflake" in mod:
            # Auth errors — wrong credentials.
            if (
                "251001" in msg
                or "incorrect username or password" in msg
                or "password was specified" in msg
                or "authentication" in msg
            ):
                return NucleusSourceAuthError(
                    user_message=(
                        "The data source rejected the provided credentials. "
                        "Check your username and password."
                    ),
                    fix_hint=(
                        "Verify the username and password in your connection string. "
                        "Connection strings take the form: "
                        "snowflake://user:pass@orgname-accountname/db/schema. "
                        "See docs/internal/research/snowflake.md §2 for account identifier formats."
                    ),
                    cause=exc,
                )
            # Account does not exist / not accessible.
            if "250001" in msg or "account does not exist" in msg or "not accessible" in msg:
                return NucleusSourceConnectionError(
                    user_message=(
                        "The account identifier in the connection string does not exist. "
                        "Check the account name and try again."
                    ),
                    fix_hint=(
                        "Verify the account identifier. Preferred form: 'orgname-accountname'. "
                        "See docs/internal/research/snowflake.md §2 for supported formats."
                    ),
                    cause=exc,
                )
            # Object (table) not found — SQL compilation error 002003.
            if "002003" in msg or (
                ("does not exist" in msg or "not found" in msg)
                and ("table" in msg or "view" in msg or "object" in msg)
            ):
                return NucleusSourceNotFound(
                    user_message=(
                        "The source table was not found in the data source. "
                        "Verify the table name and schema."
                    ),
                    fix_hint=(
                        "Pass the fully-qualified table name as 'SCHEMA.TABLE', e.g. "
                        "'PUBLIC.ORDERS'. Snowflake names default to UPPERCASE."
                    ),
                    cause=exc,
                )
            # Network / timeout / host unreachable.
            if any(
                phrase in msg
                for phrase in (
                    "connection timed out",
                    "could not connect",
                    "connection refused",
                    "could not resolve host",
                    "network",
                )
            ):
                return NucleusSourceConnectionError(
                    user_message=(
                        "Could not reach the data source. "
                        "Check the account identifier and network connectivity."
                    ),
                    fix_hint=(
                        "Verify the account identifier in your connection string. "
                        "Confirm outbound HTTPS (port 443) is allowed to your account. "
                        "See docs/internal/research/snowflake.md §2."
                    ),
                    cause=exc,
                )
            # SSL/TLS errors.
            if "ssl" in msg or "tls" in msg or "certificate" in msg:
                return NucleusNetworkError(
                    user_message=(
                        "A secure connection to the data source could not be established. "
                        "Check your SSL/TLS settings."
                    ),
                    fix_hint=(
                        "Verify the connection string does not disable TLS. "
                        "See docs/internal/research/snowflake.md §3 for auth options."
                    ),
                    cause=exc,
                )

        # ------------------------------------------------------------------ #
        # sqlalchemy errors — shared with Postgres/MySQL translator pattern.
        # Docs: https://docs.sqlalchemy.org/en/20/core/exceptions.html
        # ------------------------------------------------------------------ #
        if "sqlalchemy" in mod:
            if cls == "NoSuchTableError":
                return NucleusSourceNotFound(
                    user_message=(
                        "The source table was not found in the data source. "
                        "Verify the table name and schema."
                    ),
                    fix_hint=(
                        "Pass the fully-qualified table name as 'SCHEMA.TABLE'. "
                        "Snowflake names default to UPPERCASE."
                    ),
                    cause=exc,
                )
            if cls == "OperationalError" and any(
                phrase in msg
                for phrase in ("could not connect", "connection refused", "could not resolve")
            ):
                return NucleusSourceConnectionError(
                    user_message=(
                        "Could not connect to the data source. "
                        "Check the account identifier, host, and credentials."
                    ),
                    fix_hint=(
                        "Verify the connection string. "
                        "Form: snowflake://user:pass@orgname-accountname/db/schema"
                    ),
                    cause=exc,
                )

    inner_msg = str(exc) or "(no message)"
    return NucleusInternalError(
        user_message=f"Data source ingest failed unexpectedly: {inner_msg}",
        fix_hint=(
            "Check the connection string, table name, and destination configuration. "
            "Run with --debug to see the full traceback."
        ),
        cause=exc,
    )


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
