"""Tests for ``nucleus.ctx.sql`` — Jinja-resolved SQL execution via DuckDB.

Covers ``sql()`` in ``src/nucleus/ctx/sql.py``:

    1. Simple SELECT without refs — executes and returns polars.LazyFrame.
    2. SELECT with {{ ref('schema.name') }} — resolves to catalog view.
    3. User bindings {{ key }} — Jinja variables substituted correctly.
    4. Ref and binding in same query — combined rendering works.
    5. SQL syntax error → NucleusSQLSyntaxError (NE2002) from DuckDB.
    6. Unknown {{ ref('...') }} → NucleusAssetNotFound (NE3002).
    7. Malformed Jinja (undefined binding, StrictUndefined) → NucleusSQLSyntaxError.
    8. Invalid ref name pattern → NucleusSQLSyntaxError.
    9. Empty warehouse dir (no tables) — simple SQL without refs still works.
    10. NucleusCatalogError on bad warehouse path.

Architecture refs:
    docs/specs/nucleus_architecture_v4.1.md §5.6.0 (ctx.sql scope ceiling)
    docs/specs/nucleus_ctx_sdk_spec.md §6.1 + §6.2 (SQL API + ref resolution)
    docs/decisions/ADR-005-api-stability-tiering.md §2 (Beta tier)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("pyiceberg")
pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")
pytest.importorskip("polars")

from nucleus.ctx.copy_from import _open_catalog, ingest_sqlite_to_iceberg
from nucleus.ctx.sql import sql
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusCatalogError,
    NucleusSQLSyntaxError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_sqlite_and_ingest(
    tmp_path: Path, table: str = "orders", ns: str = "raw", rows: int = 3
) -> None:
    """Create a SQLite source and ingest it into the filesystem catalog."""
    db_path = tmp_path / "src.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER, amount REAL)")
        conn.executemany(
            f"INSERT INTO {table} VALUES (?, ?)",
            [(i, float(i) + 0.5) for i in range(1, rows + 1)],
        )
        conn.commit()
    finally:
        conn.close()
    ingest_sqlite_to_iceberg(
        db_path,
        table,
        warehouse_dir=tmp_path / "wh",
        dest_namespace=ns,
        dest_table=table,
    )


# ---------------------------------------------------------------------------
# Basic execution tests (no refs)
# ---------------------------------------------------------------------------


class TestBasicSQLExecution:
    """sql() executes simple SQL and returns polars.LazyFrame."""

    def test_simple_select_returns_lazy_frame(self, tmp_path: Path) -> None:
        import polars as pl

        _seed_sqlite_and_ingest(tmp_path, rows=3)
        result = sql(
            "SELECT 1 AS one, 2 AS two",
            warehouse_dir=tmp_path / "wh",
        )
        assert isinstance(result, pl.LazyFrame)

    def test_collect_materialises_rows(self, tmp_path: Path) -> None:
        _seed_sqlite_and_ingest(tmp_path, rows=3)
        result = sql(
            "SELECT 42 AS answer",
            warehouse_dir=tmp_path / "wh",
        )
        df = result.collect()
        assert df["answer"][0] == 42

    def test_empty_warehouse_with_literal_sql(self, tmp_path: Path) -> None:
        """sql() works on a fresh (empty) warehouse for SQL without refs."""
        # Ensure the warehouse dir exists with a catalog.
        _open_catalog(tmp_path / "wh")
        result = sql(
            "SELECT 99 AS value",
            warehouse_dir=tmp_path / "wh",
        )
        df = result.collect()
        assert df["value"][0] == 99


# ---------------------------------------------------------------------------
# Ref resolution tests
# ---------------------------------------------------------------------------


class TestRefResolution:
    """{{ ref('schema.name') }} is resolved against the warehouse catalog."""

    def test_ref_resolves_to_catalog_view(self, tmp_path: Path) -> None:
        _seed_sqlite_and_ingest(tmp_path, table="orders", ns="raw", rows=3)
        result = sql(
            "SELECT COUNT(*) AS n FROM {{ ref('raw.orders') }}",
            warehouse_dir=tmp_path / "wh",
        )
        df = result.collect()
        assert df["n"][0] == 3

    def test_ref_returns_correct_columns(self, tmp_path: Path) -> None:
        _seed_sqlite_and_ingest(tmp_path, table="orders", ns="raw", rows=2)
        result = sql(
            "SELECT id, amount FROM {{ ref('raw.orders') }} ORDER BY id",
            warehouse_dir=tmp_path / "wh",
        )
        df = result.collect()
        assert "id" in df.columns
        assert "amount" in df.columns
        assert len(df) == 2

    def test_unknown_ref_raises_asset_not_found(self, tmp_path: Path) -> None:
        _open_catalog(tmp_path / "wh")  # empty warehouse
        with pytest.raises(NucleusAssetNotFound) as exc_info:
            sql(
                "SELECT * FROM {{ ref('raw.nonexistent') }}",
                warehouse_dir=tmp_path / "wh",
            )
        err = exc_info.value
        assert err.error_code == "NE3002"
        assert "nonexistent" in err.user_message


# ---------------------------------------------------------------------------
# Jinja bindings tests
# ---------------------------------------------------------------------------


class TestJinjaBindings:
    """User **bindings are substituted as Jinja template variables."""

    def test_binding_substituted_in_query(self, tmp_path: Path) -> None:
        _open_catalog(tmp_path / "wh")
        # Binding substituted as a literal; use integer for clean comparison.
        result = sql(
            "SELECT {{ my_value }} AS val",
            warehouse_dir=tmp_path / "wh",
            my_value=123,
        )
        df = result.collect()
        assert df["val"][0] == 123

    def test_ref_and_binding_combined(self, tmp_path: Path) -> None:
        _seed_sqlite_and_ingest(tmp_path, table="orders", ns="raw", rows=5)
        result = sql(
            "SELECT id FROM {{ ref('raw.orders') }} WHERE id > {{ min_id }}",
            warehouse_dir=tmp_path / "wh",
            min_id=3,
        )
        df = result.collect()
        assert all(df["id"] > 3)


# ---------------------------------------------------------------------------
# Error translation tests
# ---------------------------------------------------------------------------


class TestErrorTranslation:
    """sql() translates DuckDB and Jinja failures to typed NucleusError subclasses."""

    def test_sql_syntax_error_raises_nucleus_error(self, tmp_path: Path) -> None:
        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusSQLSyntaxError) as exc_info:
            sql(
                "SELEC * FRUM nowhere",
                warehouse_dir=tmp_path / "wh",
            )
        err = exc_info.value
        assert err.error_code == "NE2002"

    def test_undefined_jinja_variable_raises_sql_syntax_error(self, tmp_path: Path) -> None:
        """StrictUndefined raises for undeclared bindings."""
        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusSQLSyntaxError) as exc_info:
            sql(
                "SELECT {{ undefined_var }}",
                warehouse_dir=tmp_path / "wh",
                # Note: undefined_var NOT passed as a binding
            )
        assert exc_info.value.error_code == "NE2002"

    def test_invalid_ref_name_raises_sql_syntax_error(self, tmp_path: Path) -> None:
        """ref() names must match <lowercase>.<lowercase>."""
        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusSQLSyntaxError) as exc_info:
            sql(
                "SELECT * FROM {{ ref('INVALID-NAME') }}",
                warehouse_dir=tmp_path / "wh",
            )
        assert exc_info.value.error_code == "NE2002"

    def test_ref_with_bad_arity_raises_sql_syntax_error(self, tmp_path: Path) -> None:
        """ref() must be called with exactly one argument."""
        _open_catalog(tmp_path / "wh")
        with pytest.raises(NucleusSQLSyntaxError) as exc_info:
            sql(
                "SELECT * FROM {{ ref('a.b', 'extra') }}",
                warehouse_dir=tmp_path / "wh",
            )
        assert exc_info.value.error_code == "NE2002"

    def test_nonexistent_warehouse_raises_catalog_error(self, tmp_path: Path) -> None:
        # Passing a completely non-existent path that can't open a catalog.
        nonexistent = tmp_path / "does_not_exist" / "nested"
        # This should either create the catalog (mkdir) or raise catalog error.
        # Since _open_catalog creates the directory, test that a truly bad path
        # (e.g. an empty string path) fails gracefully.
        with pytest.raises(NucleusCatalogError):
            sql("SELECT 1", warehouse_dir=nonexistent / "\x00invalid")
