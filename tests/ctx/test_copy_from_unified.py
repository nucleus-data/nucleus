"""Tests for ``nucleus.ctx.copy_from`` — unified scheme-dispatching entry point.

Covers ``copy_from()`` in ``src/nucleus/ctx/_dispatch.py``:

    1. SQLite happy path — dispatches to ingest_sqlite_to_iceberg, returns row count.
    2. Postgres happy path — dispatches to ingest_postgres_to_iceberg, returns row count.
    3. postgres:// scheme normalised the same as postgresql://.
    4. MySQL happy path — dispatches to ingest_mysql_to_iceberg, returns row count.
    5. mysql+pymysql:// driver-qualified scheme dispatches to MySQL too.
    6. Unsupported scheme → NucleusConfigError (NE5001).
    7. Bad write_disposition → NucleusConfigError (NE5001).
    8. Target without dot → NucleusInvalidAssetDefinition (NE3004).
    9. Target with extra dots → NucleusInvalidAssetDefinition (NE3004).
    10. SQLite path extraction from sqlite:///absolute/path works correctly.
    11. Postgres error propagation — NucleusSourceAuthError bubbles up.
    12. Integration: sqlite end-to-end round-trip via the unified copy_from().

Architecture refs:
    docs/specs/nucleus_architecture_v4.1.md §5.5.1 (ctx.copy_from ingestion helper)
    docs/specs/nucleus_ctx_sdk_spec.md §0 Principle 1 (ctx is the only thing users import)
    docs/decisions/ADR-005-api-stability-tiering.md §2 (Beta tier)
    docs/decisions/ADR-014-dlt-postgres-source.md §"MySQL parity (2026-05-14)"
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from nucleus.ctx._dispatch import copy_from
from nucleus.ctx.copy_from import _open_catalog
from nucleus.errors import (
    NucleusConfigError,
    NucleusInvalidAssetDefinition,
    NucleusSourceAuthError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_sqlite(db_path: Path, rows: int = 3) -> None:
    """Create a minimal ``orders(id INTEGER, amount REAL)`` table."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE orders (id INTEGER, amount REAL)")
        conn.executemany(
            "INSERT INTO orders VALUES (?, ?)",
            [(i, float(i) + 0.5) for i in range(1, rows + 1)],
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SQLite dispatch tests
# ---------------------------------------------------------------------------


class TestSQLiteDispatch:
    """copy_from dispatches to ingest_sqlite_to_iceberg for sqlite:// scheme."""

    def test_happy_path_returns_row_count(self, tmp_path: Path) -> None:
        _seed_sqlite(tmp_path / "src.db", rows=3)
        result = copy_from(
            f"sqlite:///{(tmp_path / 'src.db').as_posix()}",
            table="orders",
            target="raw.orders",
            warehouse_dir=tmp_path / "wh",
        )
        assert result == 3

    def test_dispatches_via_correct_internal_function(self, tmp_path: Path) -> None:
        """copy_from calls ingest_sqlite_to_iceberg, not ingest_postgres_to_iceberg."""
        _seed_sqlite(tmp_path / "src.db", rows=1)
        with (
            patch("nucleus.ctx._dispatch.ingest_sqlite_to_iceberg", return_value=1) as mock_sqlite,
            patch("nucleus.ctx._dispatch.ingest_postgres_to_iceberg") as mock_pg,
        ):
            copy_from(
                "sqlite:///some.db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        mock_sqlite.assert_called_once()
        mock_pg.assert_not_called()

    def test_target_is_split_into_namespace_and_table(self, tmp_path: Path) -> None:
        """copy_from passes namespace + table_name to ingest_sqlite_to_iceberg."""
        _seed_sqlite(tmp_path / "src.db", rows=1)
        with patch("nucleus.ctx._dispatch.ingest_sqlite_to_iceberg", return_value=1) as mock_sqlite:
            copy_from(
                "sqlite:///some.db",
                table="orders",
                target="staging.fact_orders",
                warehouse_dir=tmp_path / "wh",
            )
        call_kwargs = mock_sqlite.call_args[1]
        assert call_kwargs["dest_namespace"] == "staging"
        assert call_kwargs["dest_table"] == "fact_orders"

    def test_integration_round_trip(self, tmp_path: Path) -> None:
        """End-to-end: sqlite source → Iceberg table via copy_from."""
        pytest.importorskip("pyiceberg")
        pytest.importorskip("pyarrow")

        _seed_sqlite(tmp_path / "src.db", rows=5)
        result = copy_from(
            f"sqlite:///{(tmp_path / 'src.db').as_posix()}",
            table="orders",
            target="raw.orders",
            warehouse_dir=tmp_path / "wh",
        )
        assert result == 5

        # Verify the data landed in the Iceberg table.
        catalog = _open_catalog(tmp_path / "wh")
        arrow = catalog.load_table(("raw", "orders")).scan().to_arrow()
        assert arrow.num_rows == 5


# ---------------------------------------------------------------------------
# Postgres dispatch tests
# ---------------------------------------------------------------------------


class TestPostgresDispatch:
    """copy_from dispatches to ingest_postgres_to_iceberg for postgresql/postgres scheme."""

    def test_postgresql_scheme_dispatches_to_postgres_function(self, tmp_path: Path) -> None:
        with (
            patch("nucleus.ctx._dispatch.ingest_postgres_to_iceberg", return_value=10) as mock_pg,
            patch("nucleus.ctx._dispatch.ingest_sqlite_to_iceberg") as mock_sqlite,
        ):
            result = copy_from(
                "postgresql://user:pass@localhost/db",
                table="public.orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        assert result == 10
        mock_pg.assert_called_once()
        mock_sqlite.assert_not_called()

    def test_postgres_scheme_alias_dispatches_correctly(self, tmp_path: Path) -> None:
        """``postgres://`` is equivalent to ``postgresql://``."""
        with patch("nucleus.ctx._dispatch.ingest_postgres_to_iceberg", return_value=5) as mock_pg:
            result = copy_from(
                "postgres://user:pass@host/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        assert result == 5
        mock_pg.assert_called_once()

    def test_write_disposition_forwarded_to_postgres(self, tmp_path: Path) -> None:
        with patch("nucleus.ctx._dispatch.ingest_postgres_to_iceberg", return_value=3) as mock_pg:
            copy_from(
                "postgresql://user:pass@host/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
                write_disposition="replace",
            )
        call_kwargs = mock_pg.call_args[1]
        assert call_kwargs["write_disposition"] == "replace"

    def test_postgres_error_propagates_as_nucleus_error(self, tmp_path: Path) -> None:
        """copy_from propagates NucleusError from the underlying ingest function."""
        side = NucleusSourceAuthError(
            user_message="Authentication failed.",
            fix_hint="Check credentials.",
        )
        with (
            patch(
                "nucleus.ctx._dispatch.ingest_postgres_to_iceberg",
                side_effect=side,
            ),
            pytest.raises(NucleusSourceAuthError) as exc_info,
        ):
            copy_from(
                "postgresql://user:wrong_pass@host/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        assert exc_info.value.error_code == "NE1009"


# ---------------------------------------------------------------------------
# MySQL dispatch tests (ADR-014 §"MySQL parity (2026-05-14)")
# ---------------------------------------------------------------------------


class TestMySQLDispatch:
    """copy_from dispatches to ingest_mysql_to_iceberg for mysql / mysql+pymysql schemes."""

    def test_mysql_scheme_dispatches_to_mysql_function(self, tmp_path: Path) -> None:
        with (
            patch("nucleus.ctx._dispatch.ingest_mysql_to_iceberg", return_value=12) as mock_my,
            patch("nucleus.ctx._dispatch.ingest_postgres_to_iceberg") as mock_pg,
            patch("nucleus.ctx._dispatch.ingest_sqlite_to_iceberg") as mock_sqlite,
        ):
            result = copy_from(
                "mysql://user:pass@localhost/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        assert result == 12
        mock_my.assert_called_once()
        mock_pg.assert_not_called()
        mock_sqlite.assert_not_called()

    def test_mysql_pymysql_driver_scheme_dispatches_to_mysql_function(self, tmp_path: Path) -> None:
        """``mysql+pymysql://`` (driver-qualified) routes to the MySQL helper."""
        with patch("nucleus.ctx._dispatch.ingest_mysql_to_iceberg", return_value=4) as mock_my:
            result = copy_from(
                "mysql+pymysql://user:pass@host/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        assert result == 4
        mock_my.assert_called_once()

    def test_mysql_write_disposition_forwarded(self, tmp_path: Path) -> None:
        with patch("nucleus.ctx._dispatch.ingest_mysql_to_iceberg", return_value=2) as mock_my:
            copy_from(
                "mysql://user:pass@host/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
                write_disposition="replace",
            )
        call_kwargs = mock_my.call_args[1]
        assert call_kwargs["write_disposition"] == "replace"


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """copy_from rejects invalid inputs with typed NucleusError subclasses."""

    def test_unsupported_scheme_raises_config_error(self, tmp_path: Path) -> None:
        """``oracle://`` is not in the supported set; raise NE5001."""
        # NOTE: mysql:// was historically the unsupported example here; MySQL
        # joined the supported set on 2026-05-14 (ADR-014 §"MySQL parity").
        # ``oracle://`` is the current placeholder for a v0.3+ source.
        with pytest.raises(NucleusConfigError) as exc_info:
            copy_from(
                "oracle://user:pass@host/db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        err = exc_info.value
        assert err.error_code == "NE5001"
        assert "oracle" in err.user_message
        assert err.fix_hint

    def test_invalid_write_disposition_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(NucleusConfigError) as exc_info:
            copy_from(
                "sqlite:///some.db",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
                write_disposition="merge",
            )
        err = exc_info.value
        assert err.error_code == "NE5001"
        assert "merge" in err.user_message

    def test_target_without_dot_raises_invalid_asset(self, tmp_path: Path) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            copy_from(
                "sqlite:///some.db",
                table="orders",
                target="raworders",
                warehouse_dir=tmp_path / "wh",
            )
        assert exc_info.value.error_code == "NE3004"

    def test_target_with_extra_dots_raises_invalid_asset(self, tmp_path: Path) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            copy_from(
                "sqlite:///some.db",
                table="orders",
                target="raw.orders.extra",
                warehouse_dir=tmp_path / "wh",
            )

    def test_empty_target_raises_invalid_asset(self, tmp_path: Path) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            copy_from(
                "sqlite:///some.db",
                table="orders",
                target="",
                warehouse_dir=tmp_path / "wh",
            )

    def test_no_external_classnames_in_config_error(self, tmp_path: Path) -> None:
        """Error messages must not contain external library class names."""
        with pytest.raises(NucleusConfigError) as exc_info:
            copy_from(
                "ftp://some.ftp.server",
                table="orders",
                target="raw.orders",
                warehouse_dir=tmp_path / "wh",
            )
        rendered = exc_info.value.rendered().lower()
        for forbidden in ("duckdb", "pyiceberg", "dagster", "polars"):
            assert forbidden not in rendered, f"leaked {forbidden!r} in error"
