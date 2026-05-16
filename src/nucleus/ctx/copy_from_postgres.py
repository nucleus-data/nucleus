"""Postgres → filesystem-Iceberg ingest helper — ``ctx.copy_from_postgres`` v0 path.

Wraps dlt's ``sql_database`` verified source (Stage 1 wave per ADR-014).
Mirrors ``src/nucleus/ctx/copy_from.py`` shape verbatim — same public signature,
same return type (row count), same error translation discipline.

Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)

Architecture refs:
    nucleus_architecture_v4.1.md §5.5 (Ingestion — Stage 1 Postgres branch)
    nucleus_architecture_v4.1.md §6.3 (Coordination — dlt translator boundary)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/decisions/ADR-014-dlt-postgres-source.md (scope contract)
    docs/internal/research/dlt.md §13 (Postgres-source integration notes)

Pins/docs:
    dlt==1.26.0 — https://dlthub.com/docs/general-usage/pipeline
                  https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
                  https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
    psycopg[binary]==3.2.3 — https://www.psycopg.org/psycopg3/docs/
    sqlalchemy==2.0.36 — https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from nucleus.coordination.error_translation import _translate_dlt_postgres_exception
from nucleus.ctx.copy_from import _open_catalog
from nucleus.errors import NucleusConfigError, NucleusError

__all__ = ["ingest_postgres_to_iceberg"]

_VALID_WRITE_DISPOSITIONS: frozenset[str] = frozenset({"append", "replace"})


def _normalize_conn_str(conn_str: str) -> str:
    """Normalize ``postgresql://`` / ``postgres://`` to ``postgresql+psycopg://``.

    SQLAlchemy 2.0 defaults to psycopg2 for ``postgresql://`` scheme.
    Nucleus pins psycopg3 (``psycopg[binary]==3.2.3``), so the driver
    specifier ``+psycopg`` must be explicit per
    https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
    Stage 1 only normalises the bare scheme; URLs that already include
    a driver specifier (e.g. ``postgresql+psycopg2://``) are left unchanged.
    """
    for prefix in ("postgres://", "postgresql://"):
        if conn_str.startswith(prefix):
            return "postgresql+psycopg://" + conn_str[len(prefix) :]
    return conn_str


def _row_count_from_load_info(load_info: Any) -> int:
    """Extract total row count from a dlt LoadInfo result.

    # NEEDS VERIFICATION: dlt 1.26.0 LoadInfo.load_packages[n].jobs shape.
    # The completed_jobs list contains job objects with row_counts dicts.
    # See https://github.com/dlt-hub/dlt/blob/v1.26.0/dlt/common/pipeline.py
    # Fallback returns 0 when the structure differs from expectation — the
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
    except (
        Exception
    ):  # broad catch OK: _row_count is best-effort; real errors surface in pipeline.run
        pass
    return total


def ingest_postgres_to_iceberg(
    conn_str: str,
    source_table: str,
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    write_disposition: Literal["append", "replace"] = "append",
) -> int:
    """Read all rows from a Postgres table; write to a filesystem Iceberg table.

    Returns row count written. Mirrors ``ingest_sqlite_to_iceberg(...)`` shape.

    Stage 1 scope (ADR-014): single table per call, ``append`` + ``replace``
    write dispositions, TLS via libpq URL params (``?sslmode=require``).
    No SSH/IAM/Vault — those land with ADR-010 at v0.5+.

    Args:
        conn_str: SQLAlchemy Postgres URL, e.g.
            ``postgresql://user:pass@host:5432/db?sslmode=require``.
            Also accepts ``postgres://...`` (normalised to ``postgresql://``).
        source_table: Qualified source table name, e.g. ``public.orders``.
            If unqualified (no ``.``), ``public`` schema is assumed.
        warehouse_dir: Filesystem catalog warehouse root (same as SQLite branch).
            Windows file:// URI workaround applied inside ``_open_catalog``.
        dest_namespace: Iceberg namespace for the destination table.
        dest_table: Iceberg table name within ``dest_namespace``.
        write_disposition: ``"append"`` (default) adds rows; ``"replace"``
            truncates and reloads.

    Returns:
        Number of rows written to the Iceberg table.

    Raises:
        NucleusConfigError: ``write_disposition`` is not ``"append"`` or
            ``"replace"``.
        NucleusSourceAuthError (NE1009): Wrong Postgres credentials.
        NucleusSourceConnectionError (NE1001): Host/port/DNS failure or
            database does not exist.
        NucleusSourceNotFound (NE1008): Source table does not exist in the
            database.
        NucleusSchemaEvolutionError (NE1004): Column type incompatibility or
            schema changed mid-ingest.
        NucleusNetworkError (NE1010): SSL/TLS handshake failure.
        NucleusCommitConflictError (NE1002): Concurrent Iceberg commit.
        NucleusInternalError (NE3001): Unrecognised failure — see debug trace.
    """
    if write_disposition not in _VALID_WRITE_DISPOSITIONS:
        raise NucleusConfigError(
            user_message=(
                f"write_disposition={write_disposition!r} is not supported. "
                "Stage 1 accepts 'append' or 'replace' only."
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
    # NEEDS VERIFICATION: confirm dlt's Iceberg destination picks up the SQLite
    # catalog at warehouse_path/catalog.db via DESTINATION__FILESYSTEM__BUCKET_URL.
    # See https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg (catalog config)
    _open_catalog(warehouse_path)

    # Lazy import — never at CLI startup per docs/internal/research/dlt.md §6 + PoC #4
    # boot-time discipline. ``import dlt`` ≈ 200-400 ms cold.
    # Docs: https://dlthub.com/docs/general-usage/pipeline
    import dlt  # lazy-import; PLC0415 not enabled in this project's ruff config

    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration
    from dlt.sources.sql_database import sql_table

    schema, table = source_table.split(".", 1) if "." in source_table else ("public", source_table)

    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/setup
    # credentials= accepts a SQLAlchemy URL string (Stage 1 default per ADR-014 §13.5).
    # backend="sqlalchemy" pinned explicitly — default has flipped in prior dlt releases;
    # pin behavior per docs/internal/research/dlt.md §13.3.
    # reflection_level="full_with_precision" ensures NUMERIC(p,s) / TIMESTAMPTZ
    # round-trip cleanly per docs/internal/research/dlt.md §13.6.
    #
    # With reflection_level="full_with_precision", SQLAlchemy may connect and reflect
    # at resource construction time (not only inside pipeline.run).
    # Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
    try:
        resource = sql_table(
            credentials=conn_str,
            table=table,
            schema=schema,
            backend="sqlalchemy",
            reflection_level="full_with_precision",
        )

        # Docs: https://dlthub.com/docs/general-usage/pipeline
        # destination="filesystem" + table_format="iceberg" is the correct activation.
        # NOT destination="iceberg" — see docs/internal/research/dlt.md §9 (known gotcha).
        # pipeline_name namespaced per docs/internal/research/dlt.md §9 ("pipeline_name is the
        # state key" — two assets sharing one name overwrite each other's state).
        pipeline = dlt.pipeline(
            pipeline_name=f"nucleus__pg__{dest_namespace}__{dest_table}",
            destination="filesystem",
            dataset_name=dest_namespace,
            pipelines_dir=str(warehouse_path / "_dlt_state"),
            restore_from_destination=False,  # Stage 1: no incremental state to restore.
        )

        # Docs: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
        # table_format="iceberg" routes writes through PyIceberg (our catalog, per ADR-001).
        # write_disposition validated above; only "append" and "replace" reach this call.
        load_info = pipeline.run(
            resource,
            write_disposition=write_disposition,
            table_name=dest_table,
            table_format="iceberg",
        )
    except NucleusError:
        raise
    except Exception as exc:
        raise _translate_dlt_postgres_exception(exc) from exc

    return _row_count_from_load_info(load_info)
