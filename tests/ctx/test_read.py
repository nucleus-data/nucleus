"""Tests for ``nucleus.ctx.read`` — lazy Iceberg table reader.

Covers ``read()`` in ``src/nucleus/ctx/read.py``:

    1. Happy path — returns polars.LazyFrame (default as_="polars").
    2. as_="arrow" — returns pyarrow.Table.
    3. as_="duckdb" — returns a DuckDB relation.
    4. Correct column count and row count in returned data.
    5. NucleusAssetNotMaterialized for missing table (NE3003).
    6. NucleusConfigError for unknown as_ value (NE5001).
    7. NucleusInvalidAssetDefinition for bad asset_ref format.
    8. Accepts AssetRef (nucleus.AssetRef) in addition to bare string.

Architecture refs:
    docs/specs/nucleus_architecture_v4.1.md §5.4 (Iceberg read path)
    docs/specs/nucleus_ctx_sdk_spec.md §4.1 (ctx.read signature + as_ formats)
    docs/decisions/ADR-005-api-stability-tiering.md §2 (Beta tier)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("pyiceberg")
pytest.importorskip("pyarrow")

from nucleus.ctx.copy_from import ingest_sqlite_to_iceberg
from nucleus.ctx.read import read
from nucleus.errors import (
    NucleusAssetNotMaterialized,
    NucleusConfigError,
    NucleusInvalidAssetDefinition,
)
from nucleus.sdk.results import AssetRef

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_and_ingest(
    tmp_path: Path,
    *,
    table: str = "orders",
    ns: str = "raw",
    rows: int = 4,
) -> Path:
    """Seed a SQLite table and ingest it; returns warehouse path."""
    db_path = tmp_path / "src.db"
    wh = tmp_path / "wh"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"CREATE TABLE {table} (id INTEGER NOT NULL, note TEXT)")
        conn.executemany(
            f"INSERT INTO {table} VALUES (?, ?)",
            [(i, f"row-{i}") for i in range(1, rows + 1)],
        )
        conn.commit()
    finally:
        conn.close()
    ingest_sqlite_to_iceberg(
        db_path,
        table,
        warehouse_dir=wh,
        dest_namespace=ns,
        dest_table=table,
    )
    return wh


# ---------------------------------------------------------------------------
# Format tests
# ---------------------------------------------------------------------------


class TestOutputFormats:
    """read() returns the correct Python type for each as_ value."""

    def test_default_returns_polars_lazy_frame(self, tmp_path: Path) -> None:
        import polars as pl

        wh = _seed_and_ingest(tmp_path, rows=3)
        result = read("raw.orders", warehouse_dir=wh)
        assert isinstance(result, pl.LazyFrame)

    def test_polars_collect_yields_rows(self, tmp_path: Path) -> None:
        wh = _seed_and_ingest(tmp_path, rows=5)
        result = read("raw.orders", warehouse_dir=wh, as_="polars")
        df = result.collect()
        assert len(df) == 5

    def test_as_arrow_returns_pyarrow_table(self, tmp_path: Path) -> None:
        import pyarrow as pa

        wh = _seed_and_ingest(tmp_path, rows=2)
        result = read("raw.orders", warehouse_dir=wh, as_="arrow")
        assert isinstance(result, pa.Table)
        assert result.num_rows == 2

    def test_as_duckdb_returns_relation(self, tmp_path: Path) -> None:
        pytest.importorskip("duckdb")
        import duckdb

        wh = _seed_and_ingest(tmp_path, rows=3)
        result = read("raw.orders", warehouse_dir=wh, as_="duckdb")
        # DuckDB relation is consumable — use .arrow() to avoid numpy dependency.
        assert isinstance(result, duckdb.DuckDBPyRelation)
        arrow_result = result.arrow()
        assert arrow_result.num_rows == 3

    def test_column_names_preserved(self, tmp_path: Path) -> None:
        wh = _seed_and_ingest(tmp_path, rows=1)
        result = read("raw.orders", warehouse_dir=wh)
        df = result.collect()
        assert "id" in df.columns
        assert "note" in df.columns


# ---------------------------------------------------------------------------
# AssetRef support
# ---------------------------------------------------------------------------


class TestAssetRefInput:
    """read() accepts both bare strings and AssetRef objects."""

    def test_asset_ref_input(self, tmp_path: Path) -> None:
        import polars as pl

        wh = _seed_and_ingest(tmp_path, rows=2)
        ref = AssetRef(key="raw.orders")
        result = read(ref, warehouse_dir=wh)
        assert isinstance(result, pl.LazyFrame)

    def test_asset_ref_and_string_return_same_rows(self, tmp_path: Path) -> None:
        wh = _seed_and_ingest(tmp_path, rows=3)
        from_str = read("raw.orders", warehouse_dir=wh).collect()
        from_ref = read(AssetRef("raw.orders"), warehouse_dir=wh).collect()
        assert len(from_str) == len(from_ref)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """read() raises typed NucleusError for all failure modes."""

    def test_missing_table_raises_asset_not_materialized(self, tmp_path: Path) -> None:
        from nucleus.ctx.copy_from import _open_catalog

        # Create a warehouse with no tables.
        _open_catalog(tmp_path / "wh")

        with pytest.raises(NucleusAssetNotMaterialized) as exc_info:
            read("raw.orders", warehouse_dir=tmp_path / "wh")
        err = exc_info.value
        assert err.error_code == "NE3003"
        assert "orders" in err.user_message
        assert err.fix_hint

    def test_unknown_as_value_raises_config_error(self, tmp_path: Path) -> None:
        wh = _seed_and_ingest(tmp_path, rows=1)
        with pytest.raises(NucleusConfigError) as exc_info:
            read("raw.orders", warehouse_dir=wh, as_="excel")
        err = exc_info.value
        assert err.error_code == "NE5001"
        assert "excel" in err.user_message

    def test_bad_asset_ref_raises_invalid_asset(self, tmp_path: Path) -> None:
        from nucleus.ctx.copy_from import _open_catalog

        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusInvalidAssetDefinition):
            read("no_dot_here", warehouse_dir=tmp_path / "wh")

    def test_empty_asset_ref_raises_invalid_definition(self, tmp_path: Path) -> None:
        from nucleus.ctx.copy_from import _open_catalog

        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusInvalidAssetDefinition):
            read("", warehouse_dir=tmp_path / "wh")

    def test_no_external_classnames_in_materialized_error(self, tmp_path: Path) -> None:
        """Error messages must not leak external library class names."""
        from nucleus.ctx.copy_from import _open_catalog

        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusAssetNotMaterialized) as exc_info:
            read("raw.missing", warehouse_dir=tmp_path / "wh")
        rendered = exc_info.value.rendered().lower()
        for forbidden in ("pyiceberg", "duckdb", "dagster", "polars"):
            assert forbidden not in rendered, f"leaked {forbidden!r} in error"
