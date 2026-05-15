"""Tests for nucleus.coordination.bi_handshake — nucleus.db generation (ADR-026).

Architecture refs:
    nucleus_architecture_v4.1.md §3 (Experience layer)
    ADR-026 (nucleus.db BI handshake)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from nucleus.coordination.bi_handshake import generate_nucleus_db, _CATALOG_META_TABLE
from nucleus.errors import NucleusCatalogError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_catalog(namespaces: list[str], tables: dict[str, pa.Table]) -> MagicMock:
    """Build a minimal mock pyiceberg Catalog for testing."""
    catalog = MagicMock()
    # list_namespaces returns list of 1-tuples per pyiceberg API
    catalog.list_namespaces.return_value = [(ns,) for ns in namespaces]

    def _list_tables(ns: str) -> list[tuple[str, str]]:
        return [(ns, name) for name in [k.split(".", 1)[1] for k in tables if k.startswith(f"{ns}.")]]

    catalog.list_tables.side_effect = _list_tables

    def _load_table(ident: tuple[str, str]) -> MagicMock:
        key = f"{ident[0]}.{ident[1]}"
        tbl = MagicMock()
        arrow_tbl = tables[key]
        tbl.current_snapshot.return_value = MagicMock(snapshot_id=42)
        tbl.location.return_value = f"s3://warehouse/{ident[0]}/{ident[1]}"
        tbl.scan.return_value.to_arrow.return_value = arrow_tbl
        return tbl

    catalog.load_table.side_effect = _load_table
    return catalog


def _sample_table() -> pa.Table:
    return pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})


# ---------------------------------------------------------------------------
# Test: file is created at the right path
# ---------------------------------------------------------------------------


def test_generate_nucleus_db_creates_file(tmp_path: Path) -> None:
    """generate_nucleus_db() creates nucleus.db under project_root."""
    catalog = _make_catalog(["raw"], {"raw.users": _sample_table()})
    db_path = generate_nucleus_db(tmp_path, catalog)
    assert db_path == tmp_path / "nucleus.db"
    assert db_path.exists()


# ---------------------------------------------------------------------------
# Test: asset table is queryable from external DuckDB client
# ---------------------------------------------------------------------------


def test_asset_table_queryable(tmp_path: Path) -> None:
    """The written DuckDB table is queryable by an external DuckDB connection."""
    import duckdb

    catalog = _make_catalog(["raw"], {"raw.users": _sample_table()})
    db_path = generate_nucleus_db(tmp_path, catalog)

    with duckdb.connect(str(db_path)) as conn:
        rows = conn.execute("SELECT * FROM raw__users ORDER BY id").fetchall()

    assert len(rows) == 3
    assert rows[0][0] == 1
    assert rows[2][1] == "c"


# ---------------------------------------------------------------------------
# Test: metadata table is present
# ---------------------------------------------------------------------------


def test_metadata_table_present(tmp_path: Path) -> None:
    """_nucleus_catalog_info table is written with correct columns."""
    import duckdb

    catalog = _make_catalog(["raw"], {"raw.users": _sample_table()})
    db_path = generate_nucleus_db(tmp_path, catalog)

    with duckdb.connect(str(db_path)) as conn:
        meta = conn.execute(f'SELECT asset_key, duckdb_table, row_count FROM "{_CATALOG_META_TABLE}"').fetchall()

    assert len(meta) == 1
    assert meta[0][0] == "raw.users"
    assert meta[0][1] == "raw__users"
    assert meta[0][2] == 3


# ---------------------------------------------------------------------------
# Test: idempotent re-run
# ---------------------------------------------------------------------------


def test_generate_is_idempotent(tmp_path: Path) -> None:
    """Calling generate_nucleus_db() twice on the same project_root is safe."""
    import duckdb

    catalog = _make_catalog(["raw"], {"raw.users": _sample_table()})
    generate_nucleus_db(tmp_path, catalog)
    generate_nucleus_db(tmp_path, catalog)  # second run — should not raise

    with duckdb.connect(str(tmp_path / "nucleus.db")) as conn:
        rows = conn.execute("SELECT count(*) FROM raw__users").fetchone()

    assert rows is not None
    assert rows[0] == 3


# ---------------------------------------------------------------------------
# Test: empty catalog (no assets yet) produces valid empty metadata table
# ---------------------------------------------------------------------------


def test_empty_catalog_creates_valid_db(tmp_path: Path) -> None:
    """A catalog with no materialised assets still creates a valid nucleus.db."""
    import duckdb

    catalog = MagicMock()
    catalog.list_namespaces.return_value = []

    db_path = generate_nucleus_db(tmp_path, catalog)
    assert db_path.exists()

    with duckdb.connect(str(db_path)) as conn:
        rows = conn.execute(f'SELECT count(*) FROM "{_CATALOG_META_TABLE}"').fetchone()
    assert rows is not None and rows[0] == 0


# ---------------------------------------------------------------------------
# Test: catalog unavailable raises NucleusCatalogError (error translation)
# ---------------------------------------------------------------------------


def test_catalog_error_raises_nucleus_error(tmp_path: Path) -> None:
    """If catalog.list_namespaces() fails, a NucleusCatalogError is raised."""
    catalog = MagicMock()
    catalog.list_namespaces.side_effect = RuntimeError("catalog DB locked")

    with pytest.raises(NucleusCatalogError) as exc_info:
        generate_nucleus_db(tmp_path, catalog)

    assert "namespace" in exc_info.value.user_message.lower()
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# Test: asset scan failure raises NucleusCatalogError
# ---------------------------------------------------------------------------


def test_scan_failure_raises_nucleus_error(tmp_path: Path) -> None:
    """If an asset scan fails, a NucleusCatalogError is raised with context."""
    catalog = MagicMock()
    catalog.list_namespaces.return_value = [("raw",)]
    catalog.list_tables.return_value = [("raw", "broken")]

    broken_table = MagicMock()
    broken_table.current_snapshot.return_value = MagicMock(snapshot_id=1)
    broken_table.location.return_value = "s3://bucket/raw/broken"
    broken_table.scan.return_value.to_arrow.side_effect = OSError("parquet read error")
    catalog.load_table.return_value = broken_table

    with pytest.raises(NucleusCatalogError) as exc_info:
        generate_nucleus_db(tmp_path, catalog)

    assert "raw.broken" in exc_info.value.user_message
