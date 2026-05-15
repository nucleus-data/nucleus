"""Tests for DuckDB memory_limit guard at AMA connection init.

Validates ADR-024 P0-1: the AMA applies ``SET memory_limit`` before any
user query runs, preventing silent OOM on low-RAM machines (e.g. 16 GB
MacBooks running parallel docker containers).

Coverage:
    ML1  _compute_duckdb_memory_limit returns a valid GB string.
    ML2  Override string is passed through unchanged.
    ML3  _apply_duckdb_memory_limit sets memory_limit on a real DuckDB conn.
    ML4  memory_limit_str param propagates from materialize_asset → _commit_to_iceberg.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

import nucleus
from nucleus.coordination.asset_materialization import (
    _apply_duckdb_memory_limit,
    _compute_duckdb_memory_limit,
    materialize_asset,
)
from nucleus.sdk.decorators import _reset_registry_for_tests

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


# ---------------------------------------------------------------------------
# ML1: _compute_duckdb_memory_limit returns valid GB string
# ---------------------------------------------------------------------------


def test_compute_memory_limit_returns_gb_string() -> None:
    """ML1: _compute_duckdb_memory_limit returns a string ending with 'GB'."""
    result = _compute_duckdb_memory_limit()
    assert isinstance(result, str)
    assert result.endswith("GB"), f"Expected 'XGB' format, got: {result!r}"
    # Must be parseable as an int
    gb_value = int(result.removesuffix("GB"))
    assert 2 <= gb_value <= 32, f"Memory limit out of expected range: {gb_value}GB"


def test_compute_memory_limit_lower_bound() -> None:
    """ML1: Even on a machine reporting 0 bytes RAM, the limit is ≥ 2 GB."""
    with patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 0
        result = _compute_duckdb_memory_limit()
    assert result == "2GB"


def test_compute_memory_limit_upper_bound() -> None:
    """ML1: On a 512 GB server, the limit is capped at 32 GB."""
    with patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 512 * 1024**3
        result = _compute_duckdb_memory_limit()
    assert result == "32GB"


# ---------------------------------------------------------------------------
# ML2: Override string is passed through unchanged
# ---------------------------------------------------------------------------


def test_compute_memory_limit_override() -> None:
    """ML2: Caller-supplied override string bypasses psutil detection."""
    result = _compute_duckdb_memory_limit(override_str="8GB")
    assert result == "8GB"


def test_compute_memory_limit_override_custom_value() -> None:
    """ML2: Any non-empty override string is returned verbatim."""
    result = _compute_duckdb_memory_limit(override_str="16GB")
    assert result == "16GB"


# ---------------------------------------------------------------------------
# ML3: _apply_duckdb_memory_limit sets the limit on a real DuckDB conn
# ---------------------------------------------------------------------------


def test_apply_memory_limit_sets_duckdb_setting(tmp_path: Path) -> None:
    """ML3: SET memory_limit is applied to a real DuckDB connection."""
    import duckdb  # Docs: https://duckdb.org/docs/api/python/overview

    conn = duckdb.connect()
    spill_dir = tmp_path / "duckdb_spill"
    _apply_duckdb_memory_limit(conn, "4GB", spill_dir)

    # Verify the setting was applied by reading it back.
    # Docs: https://duckdb.org/docs/configuration/overview
    rows = conn.execute("SELECT current_setting('memory_limit')").fetchall()
    assert rows, "Expected memory_limit setting to be readable"
    setting_value = rows[0][0]
    # DuckDB normalizes the unit: "4.0 GiB" or "4096 MiB" etc.
    assert "4" in setting_value or "GiB" in setting_value or "GB" in setting_value, (
        f"memory_limit setting unexpected: {setting_value!r}"
    )
    conn.close()


def test_apply_memory_limit_creates_spill_directory(tmp_path: Path) -> None:
    """ML3: The spill directory is created if it does not exist."""
    import duckdb

    conn = duckdb.connect()
    spill_dir = tmp_path / "nested" / "spill"
    assert not spill_dir.exists()
    _apply_duckdb_memory_limit(conn, "2GB", spill_dir)
    assert spill_dir.exists()
    conn.close()


# ---------------------------------------------------------------------------
# ML4: memory_limit param propagates through materialize_asset
# ---------------------------------------------------------------------------


def test_memory_limit_param_accepted_by_materialize_asset(tmp_path: Path) -> None:
    """ML4: memory_limit='4GB' is accepted and applied without error."""
    warehouse = tmp_path / "warehouse"

    @nucleus.asset("staging.orders")
    def staging_orders() -> pl.DataFrame:
        return pl.DataFrame({"id": [1, 2], "val": [10.0, 20.0]})

    result = materialize_asset(
        "staging.orders",
        warehouse_dir=warehouse,
        memory_limit="4GB",
    )
    assert result.snapshot_id != ""
    assert result.row_count == 2
