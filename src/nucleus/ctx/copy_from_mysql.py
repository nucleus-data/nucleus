"""MySQL → filesystem-Iceberg ingest helper — ``ctx.copy_from_mysql`` v0 path.

Wraps dlt's ``sql_database`` verified source per ADR-014 §"MySQL parity (2026-05-14)".
Mirrors ``src/nucleus/ctx/copy_from_postgres.py`` shape verbatim — same public
signature, same return type (row count), same error translation discipline.

Stability: Beta @ v0.2 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)

Architecture refs:
    nucleus_architecture_v4.1.md §5.5 (Ingestion — MySQL co-default branch)
    nucleus_architecture_v4.1.md §6.3 (Coordination — dlt translator boundary)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/decisions/ADR-014-dlt-postgres-source.md §"MySQL parity (2026-05-14)"
    docs/internal/research/dlt.md §13 (sql_database source — multi-dialect coverage)

Pins/docs:
    dlt==1.26.0 — https://dlthub.com/docs/general-usage/pipeline
                  https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
                  https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
    pymysql==1.1.1 — https://pymysql.readthedocs.io/en/latest/
    sqlalchemy==2.0.36 — https://docs.sqlalchemy.org/en/20/dialects/mysql.html
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from nucleus.coordination.error_translation import _translate_dlt_mysql_exception
from nucleus.ctx.copy_from import _open_catalog
from nucleus.errors import NucleusConfigError

__all__ = ["ingest_mysql_to_iceberg"]

_VALID_WRITE_DISPOSITIONS: frozenset[str] = frozenset({"append", "replace"})
_VALID_PREFIXES: tuple[str, ...] = ("mysql://", "mysql+pymysql://")


def _normalize_conn_str(conn_str: str) -> str:
    """Normalize ``mysql://`` to ``mysql+pymysql://``.

    SQLAlchemy 2.0 has no default driver for the bare ``mysql://`` scheme and
    will fail to dispatch. Nucleus pins ``pymysql==1.1.1`` so the driver
    specifier ``+pymysql`` must be explicit per
    https://docs.sqlalchemy.org/en/20/dialects/mysql.html
    URLs that already include a driver specifier (``mysql+pymysql://``,
    ``mysql+mysqldb://``) are left unchanged.
    """
    if conn_str.startswith("mysql://"):
        return "mysql+pymysql://" + conn_str[len("mysql://") :]
    return conn_str


def _row_count_from_load_info(load_info: Any) -> int:
    """Extract total row count from a dlt LoadInfo result.

    # NEEDS VERIFICATION: dlt 1.26.0 LoadInfo.load_packages[n].jobs shape.
    # Mirrors copy_from_postgres._row_count_from_load_info — same dlt shape
    # regardless of source dialect per docs/internal/research/dlt.md §13. The
    # integration test in tests/upgrade_smoke/test_dlt_mysql.py verifies this.
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
    except (
        Exception
    ):  # broad catch OK: _row_count is best-effort; real errors surface in pipeline.run
        pass
    return total


def ingest_mysql_to_iceberg(
    conn_str: str,
    source_table: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    write_disposition: Literal["append", "replace"] = "append",
) -> int:
    """Read all rows from a MySQL table; write to a filesystem Iceberg table.

    Returns row count written. Mirrors ``ingest_postgres_to_iceberg(...)`` shape.

    Scope (ADR-014 §"MySQL parity"): single table per call, ``append`` +
    ``replace`` write dispositions, TLS via libmysqlclient URL params
    (``?ssl_disabled=false``). No SSH/IAM/Vault — those land with ADR-010 at
    v0.5+.

    Args:
        conn_str: SQLAlchemy MySQL URL, e.g.
            ``mysql://user:pass@host:3306/db`` or
            ``mysql+pymysql://user:pass@host:3306/db``.
            The bare ``mysql://`` scheme is normalised to ``mysql+pymysql://``
            because Nucleus pins ``pymysql==1.1.1`` as the driver.
        source_table: Source table name within the database. When unqualified
            (no ``.``), the table is looked up in the connection's default
            database from the URL. ``db.table`` form overrides the default.
        warehouse_dir: Filesystem catalog warehouse root (same as Postgres
            and SQLite branches). Windows ``file://`` URI workaround applied
            inside ``_open_catalog``.
        dest_namespace: Iceberg namespace for the destination table.
        dest_table: Iceberg table name within ``dest_namespace``.
        write_disposition: ``"append"`` (default) adds rows; ``"replace"``
            truncates and reloads.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: Source URI does not start with ``mysql://`` or
            ``mysql+pymysql://``; or ``write_disposition`` is not
            ``"append"``/``"replace"`` (NE5001).
        NucleusSourceAuthError (NE1009): Wrong MySQL credentials (error 1045).
        NucleusSourceConnectionError (NE1001): Host/port/DNS failure or
            database does not exist (errors 2003 / 1049).
        NucleusSourceNotFound (NE1008): Source table does not exist in the
            database (error 1146).
        NucleusSchemaEvolutionError (NE1004): Column type incompatibility or
            schema changed mid-ingest (error 1054).
        NucleusNetworkError (NE1010): SSL/TLS handshake failure.
        NucleusCommitConflictError (NE1002): Concurrent Iceberg commit.
        NucleusInternalError (NE3001): Unrecognised failure — see debug trace.
    """
    if not any(conn_str.startswith(p) for p in _VALID_PREFIXES):
        raise NucleusConfigError(
            user_message=(
                f"Source URI {conn_str!r} is not a recognised MySQL connection string. "
                "Accepted prefixes: 'mysql://' or 'mysql+pymysql://'."
            ),
            fix_hint=(
                "Use a SQLAlchemy MySQL URL, e.g. "
                "'mysql://user:pass@host:3306/db' or "
                "'mysql+pymysql://user:pass@host:3306/db'."
            ),
        )

    if write_disposition not in _VALID_WRITE_DISPOSITIONS:
        raise NucleusConfigError(
            user_message=(
                f"write_disposition={write_disposition!r} is not supported. "
                "MySQL parity accepts 'append' or 'replace' only."
            ),
            fix_hint=(
                "Pass write_disposition='append' (default) to add rows, "
                "or write_disposition='replace' to truncate and reload."
            ),
        )

    conn_str = _normalize_conn_str(conn_str)
    warehouse_path = Path(warehouse_dir)

    # Ensure warehouse directory and catalog.db exist before dlt touches the FS.
    # Reuses the filesystem catalog opener from copy_from.py per ADR-014 §sketch.
    # Windows file:// URI workaround applied inside _open_catalog (copy_from.py:131).
    _open_catalog(warehouse_path)

    # Lazy import — never at CLI startup per docs/internal/research/dlt.md §6 + PoC #4
    # boot-time discipline. ``import dlt`` ≈ 200-400 ms cold.
    # Docs: https://dlthub.com/docs/general-usage/pipeline
    import dlt  # lazy-import; PLC0415 not enabled in this project's ruff config

    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration
    from dlt.sources.sql_database import sql_table

    # In MySQL the "schema" concept is the database — typically taken from the
    # connection URL path. Allow ``db.table`` to override (mirrors Postgres
    # ``schema.table`` split). Unqualified table names defer to the URL's DB.
    if "." in source_table:
        schema, table = source_table.split(".", 1)
        schema_kwarg: dict[str, str] = {"schema": schema}
    else:
        table = source_table
        schema_kwarg = {}

    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/setup
    # credentials= accepts a SQLAlchemy URL string. backend="sqlalchemy" pinned
    # explicitly — same rationale as Postgres branch (default has flipped in
    # prior dlt releases). reflection_level="full_with_precision" ensures
    # NUMERIC(p,s) / DATETIME(6) / TIMESTAMP round-trip cleanly.
    resource = sql_table(
        credentials=conn_str,
        table=table,
        backend="sqlalchemy",
        reflection_level="full_with_precision",
        **schema_kwarg,
    )

    # Docs: https://dlthub.com/docs/general-usage/pipeline
    # destination="filesystem" + table_format="iceberg" is the correct activation.
    # NOT destination="iceberg" — see docs/internal/research/dlt.md §9 (known gotcha).
    # pipeline_name namespaced with ``my`` prefix to avoid collision with
    # Postgres pipelines that target the same dest namespace+table per
    # docs/internal/research/dlt.md §9 ("pipeline_name is the state key").
    pipeline = dlt.pipeline(
        pipeline_name=f"nucleus__my__{dest_namespace}__{dest_table}",
        destination="filesystem",
        dataset_name=dest_namespace,
        pipelines_dir=str(warehouse_path / "_dlt_state"),
        restore_from_destination=False,  # MySQL parity: no incremental state to restore.
    )

    # Docs: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
    # table_format="iceberg" routes writes through PyIceberg (our catalog, per ADR-001).
    # write_disposition validated above; only "append" and "replace" reach this call.
    try:
        load_info = pipeline.run(
            resource,
            write_disposition=write_disposition,
            table_name=dest_table,
            table_format="iceberg",
        )
    except Exception as exc:  # broad catch intentional: translator classifies all dlt failures
        raise _translate_dlt_mysql_exception(exc) from exc

    return _row_count_from_load_info(load_info)
