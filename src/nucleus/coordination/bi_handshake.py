"""BI handshake — generate ``nucleus.db`` after ``nucleus up``.

Per ADR-026: ``nucleus up`` emits ``<project_root>/nucleus.db``, a DuckDB file
containing one table per materialised Iceberg asset (snapshot at boot time).
Any DuckDB-compatible BI tool (Superset, Evidence, Rill, Streamlit) connects
with a single file path — zero extra configuration.

Implementation note: rather than using ``CREATE OR REPLACE VIEW … iceberg_scan()``
(which requires the DuckDB iceberg extension, itself a network download), we
pre-materialise each asset's current snapshot as a native DuckDB table.  This
makes ``nucleus.db`` self-contained and usable offline.  If users prefer live
iceberg_scan() views they can load the DuckDB iceberg extension and use::

    -- live view (requires: INSTALL iceberg; LOAD iceberg)
    CREATE OR REPLACE VIEW raw__users AS
        SELECT * FROM iceberg_scan('<iceberg_table_location>');

Architecture refs:
    nucleus_architecture_v4.1.md §3 (Experience layer)
    nucleus_architecture_v4.1.md §1.5 (beachhead <30-min metric)
    ADR-026 (nucleus.db BI handshake)

Docs (AGENTS.md §11.12):
    pyiceberg Catalog.list_tables: https://py.iceberg.apache.org/api/catalog/
    pyiceberg Table.location: https://py.iceberg.apache.org/api/#pyiceberg.table.Table.location
    duckdb Python API: https://duckdb.org/docs/api/python/overview
    duckdb iceberg extension (for live-view users): https://duckdb.org/docs/extensions/iceberg
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nucleus.errors import NucleusCatalogError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Name of the metadata table written into nucleus.db alongside asset tables.
_CATALOG_META_TABLE = "_nucleus_catalog_info"


def generate_nucleus_db(project_root: Path, catalog: Any) -> Path:
    """Generate (or refresh) ``nucleus.db`` at ``project_root``.

    Opens DuckDB at ``<project_root>/nucleus.db`` and writes one DuckDB table
    per materialised Iceberg asset in the catalog.  Idempotent: re-running
    drops and recreates the tables so the file stays in sync with the current
    snapshot.

    Also writes a ``_nucleus_catalog_info`` table that records asset names,
    Iceberg table locations, and snapshot IDs for audit/debugging.

    Args:
        project_root: Absolute path to the Nucleus project root.
        catalog: An open ``pyiceberg.catalog.Catalog`` instance.
            Docs: https://py.iceberg.apache.org/api/catalog/

    Returns:
        Path to the generated ``nucleus.db`` file.

    Raises:
        NucleusCatalogError: If the catalog cannot be listed or a table
            cannot be scanned (original cause preserved as ``error.cause``).
    """
    # Docs: https://duckdb.org/docs/api/python/overview  (duckdb==1.1.3)
    import duckdb

    db_path = project_root / "nucleus.db"

    try:
        namespaces = catalog.list_namespaces()
    except Exception as exc:  # noqa: BLE001
        raise NucleusCatalogError(
            user_message="Could not list namespaces from the Iceberg catalog.",
            fix_hint="Verify the warehouse directory is accessible and `nucleus up` completed successfully.",
            cause=exc,
        ) from exc

    asset_rows: list[dict[str, str]] = []

    with duckdb.connect(str(db_path.resolve())) as conn:
        for ns_tuple in namespaces:
            ns = ns_tuple[0] if isinstance(ns_tuple, (list, tuple)) and ns_tuple else str(ns_tuple)
            if not ns:
                continue

            try:
                table_idents = catalog.list_tables(ns)
            except Exception as exc:  # noqa: BLE001
                raise NucleusCatalogError(
                    user_message=f"Could not list assets in namespace '{ns}'.",
                    fix_hint="Check that the catalog database is not locked by another process.",
                    cause=exc,
                ) from exc

            for ident in table_idents:
                tbl_name = ident[-1] if isinstance(ident, (list, tuple)) else str(ident)
                # Use flat duckdb table name: <namespace>__<asset_name>
                duckdb_table = f"{ns}__{tbl_name}"

                try:
                    ice_table = catalog.load_table(ident)
                    snapshot = ice_table.current_snapshot()
                    snapshot_id = str(snapshot.snapshot_id) if snapshot else "no_snapshot"
                    table_location = ice_table.location()

                    if snapshot is None:
                        logger.debug("Asset %s.%s has no snapshot yet — skipping nucleus.db entry.", ns, tbl_name)
                        continue

                    arrow_table = ice_table.scan().to_arrow()
                except Exception as exc:  # noqa: BLE001
                    raise NucleusCatalogError(
                        user_message=f"Could not scan asset '{ns}.{tbl_name}' for nucleus.db generation.",
                        fix_hint=(
                            "Run `nucleus run "
                            + f"{ns}.{tbl_name}"
                            + "` first to materialise a snapshot, then retry `nucleus up`."
                        ),
                        cause=exc,
                    ) from exc

                conn.execute(f'DROP TABLE IF EXISTS "{duckdb_table}"')
                conn.register("_bi_tmp_arrow", arrow_table)
                conn.execute(f'CREATE TABLE "{duckdb_table}" AS SELECT * FROM _bi_tmp_arrow')
                conn.unregister("_bi_tmp_arrow")

                asset_rows.append(
                    {
                        "asset_key": f"{ns}.{tbl_name}",
                        "duckdb_table": duckdb_table,
                        "iceberg_location": table_location,
                        "snapshot_id": snapshot_id,
                        "row_count": str(len(arrow_table)),
                    }
                )
                logger.debug("nucleus.db: wrote table '%s' (%d rows).", duckdb_table, len(arrow_table))

        # Write the metadata table.
        conn.execute(f'DROP TABLE IF EXISTS "{_CATALOG_META_TABLE}"')
        if asset_rows:
            import pyarrow as pa  # Docs: https://arrow.apache.org/docs/python/

            meta_table = pa.table(
                {
                    "asset_key": [r["asset_key"] for r in asset_rows],
                    "duckdb_table": [r["duckdb_table"] for r in asset_rows],
                    "iceberg_location": [r["iceberg_location"] for r in asset_rows],
                    "snapshot_id": [r["snapshot_id"] for r in asset_rows],
                    "row_count": [int(r["row_count"]) for r in asset_rows],
                }
            )
            conn.register("_meta_tmp", meta_table)
            conn.execute(f'CREATE TABLE "{_CATALOG_META_TABLE}" AS SELECT * FROM _meta_tmp')
            conn.unregister("_meta_tmp")
        else:
            conn.execute(
                f'CREATE TABLE "{_CATALOG_META_TABLE}" ('
                "asset_key VARCHAR, duckdb_table VARCHAR, iceberg_location VARCHAR, "
                "snapshot_id VARCHAR, row_count BIGINT)"
            )

    n = len(asset_rows)
    logger.info("nucleus.db updated: %d asset table(s) at %s", n, db_path)
    return db_path
