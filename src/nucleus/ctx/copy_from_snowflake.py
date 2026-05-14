"""Snowflake → filesystem-Iceberg ingest helper — ``ctx.copy_from_snowflake`` v0 path.

Wraps dlt's ``sql_database`` verified source (ADR-019) with a Snowflake SQLAlchemy
credential URL. Mirrors ``src/nucleus/ctx/copy_from_postgres.py`` shape verbatim —
same public signature, same return type (row count), same error translation discipline.

Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)

Architecture refs:
    nucleus_architecture_v4.1.md §5.5 (Ingestion — Snowflake source branch)
    nucleus_architecture_v4.1.md §6.3 (Coordination — dlt translator boundary)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/decisions/ADR-019-snowflake-connector-via-dlt.md (scope contract)
    docs/research/snowflake.md §4 (Snowflake error codes + exception hierarchy)

Pins/docs:
    dlt==1.26.0 — https://dlthub.com/docs/general-usage/pipeline
                  https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
                  https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
    snowflake-sqlalchemy — https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy
    snowflake-connector-python — https://docs.snowflake.com/en/developer-guide/python-connector/python-connector
    sqlalchemy==2.0.36 — https://docs.sqlalchemy.org/en/20/dialects/
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from nucleus.coordination.error_translation import _translate_dlt_snowflake_exception
from nucleus.ctx.copy_from import _open_catalog
from nucleus.errors import NucleusConfigError, NucleusError

__all__ = ["ingest_snowflake_to_iceberg"]

_VALID_WRITE_DISPOSITIONS: frozenset[str] = frozenset({"append", "replace"})
_VALID_PREFIXES: tuple[str, ...] = ("snowflake://",)


def _row_count_from_load_info(load_info: Any) -> int:
    """Extract total row count from a dlt LoadInfo result.

    # NEEDS VERIFICATION: dlt 1.26.0 LoadInfo.load_packages[n].jobs shape.
    # Mirrors copy_from_postgres._row_count_from_load_info — same dlt shape
    # regardless of source dialect per docs/research/dlt.md §13. The
    # integration test in tests/upgrade_smoke/test_dlt_upgrade.py verifies this.
    """
    total = 0
    try:
        for pkg in load_info.load_packages:
            jobs_map = pkg.jobs
            completed = jobs_map.get("completed_jobs", []) if hasattr(jobs_map, "get") else []
            for job in completed:
                row_counts = getattr(job, "row_counts", None) or {}
                if isinstance(row_counts, dict):
                    total += sum(row_counts.values())
    except Exception:  # broad catch OK: _row_count is best-effort; real errors surface in pipeline.run
        pass
    return total


def ingest_snowflake_to_iceberg(
    conn_str: str,
    source_table: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    write_disposition: Literal["append", "replace"] = "append",
) -> int:
    """Read all rows from a Snowflake table; write to a filesystem Iceberg table.

    Returns row count written. Mirrors ``ingest_postgres_to_iceberg(...)`` shape.

    Scope (ADR-019): single table per call, ``append`` + ``replace`` write
    dispositions, username/password auth via connection URL. No SSO/key-pair/
    IAM — those land with ADR-010 at v0.5+.

    Requires: ``pip install nucleus[snowflake]`` to activate the Snowflake extras
    (installs ``snowflake-connector-python`` and ``snowflake-sqlalchemy``).

    Args:
        conn_str: Snowflake SQLAlchemy URL in the form:
            ``snowflake://user:pass@account/database/schema``
            Optional URL params: ``?warehouse=COMPUTE_WH&role=ANALYST``
            Where ``account`` is ``orgname-accountname`` (preferred) or
            legacy ``accountid.region.cloud`` form.
            See https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy
        source_table: Qualified source table name, e.g. ``PUBLIC.ORDERS``.
            If unqualified (no ``.``), the schema from the URL is assumed.
            Snowflake table names default to UPPERCASE unless double-quoted.
        warehouse_dir: Filesystem catalog warehouse root (same as other branches).
            Windows file:// URI workaround applied inside ``_open_catalog``.
        dest_namespace: Iceberg namespace for the destination table.
        dest_table: Iceberg table name within ``dest_namespace``.
        write_disposition: ``"append"`` (default) adds rows; ``"replace"``
            truncates and reloads.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: Source URI does not start with ``snowflake://`` or
            ``write_disposition`` is not ``"append"``/``"replace"`` (NE5001).
        NucleusSourceAuthError (NE1009): Wrong Snowflake credentials (code 251001).
        NucleusSourceConnectionError (NE1001): Account does not exist (code 250001),
            unknown host, or network unreachable.
        NucleusSourceNotFound (NE1008): Source table does not exist.
        NucleusSchemaEvolutionError (NE1004): Column type incompatibility.
        NucleusNetworkError (NE1010): SSL/TLS or connection timeout.
        NucleusCommitConflictError (NE1002): Concurrent Iceberg commit.
        NucleusInternalError (NE3001): Unrecognised failure — see debug trace.
    """
    if not conn_str.startswith("snowflake://"):
        raise NucleusConfigError(
            user_message=(
                f"Source URI {conn_str!r} is not a recognised Snowflake connection string. "
                "Accepted prefix: 'snowflake://'."
            ),
            fix_hint=(
                "Use a Snowflake SQLAlchemy URL, e.g. "
                "'snowflake://user:pass@orgname-accountname/mydb/PUBLIC'"
                "?warehouse=COMPUTE_WH'. "
                "See docs/research/snowflake.md §2 for account identifier formats."
            ),
        )

    if write_disposition not in _VALID_WRITE_DISPOSITIONS:
        raise NucleusConfigError(
            user_message=(
                f"write_disposition={write_disposition!r} is not supported. "
                "Snowflake branch accepts 'append' or 'replace' only."
            ),
            fix_hint=(
                "Pass write_disposition='append' (default) to add rows, "
                "or write_disposition='replace' to truncate and reload."
            ),
        )

    warehouse_path = Path(warehouse_dir)
    _open_catalog(warehouse_path)

    # Lazy imports — never at CLI startup per docs/research/dlt.md §6 + PoC #4
    # boot-time discipline. ``import dlt`` ≈ 200-400 ms cold.
    # Docs: https://dlthub.com/docs/general-usage/pipeline
    import dlt  # lazy-import; PLC0415 not enabled in this project's ruff config

    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration
    from dlt.sources.sql_database import sql_table

    # Snowflake uses the schema as part of the table identifier.
    # If qualified as "SCHEMA.TABLE", split accordingly. Unqualified names
    # defer to the schema embedded in the connection URL path segment 3.
    if "." in source_table:
        schema, table = source_table.split(".", 1)
        schema_kwarg: dict[str, str] = {"schema": schema}
    else:
        table = source_table
        schema_kwarg = {}

    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/setup
    # credentials= accepts a SQLAlchemy URL string. backend="sqlalchemy" pinned
    # explicitly — default has flipped in prior dlt releases; pin behavior per
    # docs/research/dlt.md §13.3. reflection_level="full_with_precision" ensures
    # NUMBER(p,s) / TIMESTAMP_TZ round-trip cleanly per docs/research/snowflake.md §6.
    try:
        resource = sql_table(
            credentials=conn_str,
            table=table,
            backend="sqlalchemy",
            reflection_level="full_with_precision",
            **schema_kwarg,
        )

        # Docs: https://dlthub.com/docs/general-usage/pipeline
        # destination="filesystem" + table_format="iceberg" is the correct activation.
        # NOT destination="iceberg" — see docs/research/dlt.md §9 (known gotcha).
        # pipeline_name namespaced with ``sf`` prefix to avoid collision with
        # Postgres/MySQL pipelines per docs/research/dlt.md §9.
        pipeline = dlt.pipeline(
            pipeline_name=f"nucleus__sf__{dest_namespace}__{dest_table}",
            destination="filesystem",
            dataset_name=dest_namespace,
            pipelines_dir=str(warehouse_path / "_dlt_state"),
            restore_from_destination=False,
        )

        # Docs: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
        load_info = pipeline.run(
            resource,
            write_disposition=write_disposition,
            table_name=dest_table,
            table_format="iceberg",
        )
    except NucleusError:
        raise
    except Exception as exc:  # noqa: BLE001 — broad catch intentional: translator classifies all failures
        raise _translate_dlt_snowflake_exception(exc) from exc

    return _row_count_from_load_info(load_info)
