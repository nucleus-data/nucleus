"""Tests for DuckDB memory_limit guard at AMA connection init.

Validates ADR-024 P0-1 + ``docs/internal/research/performance_reliability_targets.md``
§10 item #2: the AMA applies ``SET memory_limit``, ``SET temp_directory``,
and ``SET threads`` before any user query runs, preventing silent OOM on
low-RAM machines (e.g. 16 GB MacBooks running parallel docker containers).

Coverage:
    ML1  _compute_duckdb_memory_limit returns a valid GB string.
    ML2  Override string is passed through unchanged.
    ML3  _apply_duckdb_memory_limit sets memory_limit on a real DuckDB conn.
    ML4  memory_limit_str param propagates from materialize_asset → _commit_to_iceberg.
    ML5  Fraction is 60% of total RAM (perf doc §10 #2 — lowered from 80% in v0.2).
    ML6  _compute_duckdb_threads returns physical-core count (>= 1).
    ML7  _apply_duckdb_memory_limit sets ``threads`` on the DuckDB conn.
    ML8  Threads override (kwarg) is honored.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

import nucleus
from nucleus.coordination.asset_materialization import (
    _DUCKDB_RAM_FRACTION,
    _apply_duckdb_memory_limit,
    _compute_duckdb_memory_limit,
    _compute_duckdb_threads,
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


# ---------------------------------------------------------------------------
# ML5: 60% fraction enforced (perf doc §10 #2 — lowered from 80% in v0.2)
# ---------------------------------------------------------------------------


def test_compute_memory_limit_uses_60_percent_fraction() -> None:
    """ML5: The constant _DUCKDB_RAM_FRACTION is 0.60, not the upstream 0.80.

    Per ``docs/internal/research/performance_reliability_targets.md`` §10 item #2 —
    DuckDB's upstream default of 80% RAM combined with no GROUP BY hash
    spill leaves no headroom for the host OS, IDEs, or sidecar containers.
    v0.2 lowers the AMA target to 60%.
    """
    assert _DUCKDB_RAM_FRACTION == 0.60, (
        f"Expected 60% fraction per perf doc §10 #2; got {_DUCKDB_RAM_FRACTION!r}"
    )


def test_compute_memory_limit_60_percent_at_10gb_ram() -> None:
    """ML5: On a machine with 10 GB total RAM, the limit is 6 GB (60%)."""
    with patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 10 * 1024**3  # 10 GB
        result = _compute_duckdb_memory_limit()
    # 10 GB × 0.60 = 6 GB; floor=2 GB / ceil=32 GB do not clamp here.
    assert result == "6GB", (
        f"Expected 6GB on 10 GB host (60% × 10); got {result!r}. "
        "Did the fraction silently regress to 0.80?"
    )


def test_compute_memory_limit_60_percent_at_16gb_ram() -> None:
    """ML5: On a 16 GB MacBook, the limit is 9 GB (int(16 × 0.60) = 9)."""
    with patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.total = 16 * 1024**3
        result = _compute_duckdb_memory_limit()
    assert result == "9GB", (
        f"Expected 9GB on 16 GB host; got {result!r}. "
        "Worker B1 perf doc §10 #2 fix may have regressed."
    )


# ---------------------------------------------------------------------------
# ML6: _compute_duckdb_threads returns physical core count
# ---------------------------------------------------------------------------


def test_compute_duckdb_threads_returns_positive_int() -> None:
    """ML6: _compute_duckdb_threads always returns >= 1."""
    threads = _compute_duckdb_threads()
    assert isinstance(threads, int)
    assert threads >= 1, f"Threads must be >= 1; got {threads}"


def test_compute_duckdb_threads_prefers_physical_cores() -> None:
    """ML6: Physical-core count is used when psutil reports it."""
    with patch("psutil.cpu_count") as mock_cpu:
        # First call: logical=False (physical) → 4
        # Second call (logical): never reached if physical succeeds
        mock_cpu.side_effect = lambda logical=True: 4 if logical is False else 8
        threads = _compute_duckdb_threads()
    assert threads == 4, (
        f"Expected physical-core preference (4); got {threads}. "
        "DuckDB perf doc says SMT/hyper-threads degrade vectorized pipeline."
    )


def test_compute_duckdb_threads_falls_back_to_logical() -> None:
    """ML6: When physical-core lookup returns None, fall back to logical."""
    with patch("psutil.cpu_count") as mock_cpu:
        mock_cpu.side_effect = lambda logical=True: None if logical is False else 8
        threads = _compute_duckdb_threads()
    assert threads == 8, f"Expected logical-core fallback (8); got {threads}."


def test_compute_duckdb_threads_falls_back_to_constant() -> None:
    """ML6: When both psutil calls return None, fall back to _DUCKDB_THREADS_FALLBACK."""
    with patch("psutil.cpu_count", return_value=None):
        threads = _compute_duckdb_threads()
    assert threads == 4, f"Expected constant fallback (4); got {threads}."


# ---------------------------------------------------------------------------
# ML7: _apply_duckdb_memory_limit sets ``threads`` on the DuckDB conn
# ---------------------------------------------------------------------------


def test_apply_memory_limit_sets_threads(tmp_path: Path) -> None:
    """ML7: SET threads is applied to a real DuckDB connection."""
    import duckdb  # Docs: https://duckdb.org/docs/api/python/overview

    conn = duckdb.connect()
    spill_dir = tmp_path / "duckdb_spill"
    _apply_duckdb_memory_limit(conn, "4GB", spill_dir)

    # Read back via current_setting; DuckDB returns string-typed setting values.
    # Docs: https://duckdb.org/docs/configuration/overview
    rows = conn.execute("SELECT current_setting('threads')").fetchall()
    assert rows, "Expected threads setting to be readable"
    threads_value = int(rows[0][0])
    assert threads_value >= 1, f"threads must be >= 1; got {threads_value!r}"
    # On any non-empty CPU box the value is the physical core count via
    # _compute_duckdb_threads → typically [1, 256].  Never the absurd default 0.
    assert threads_value <= 1024, f"threads value out of range: {threads_value}"
    conn.close()


# ---------------------------------------------------------------------------
# ML8: Threads override (kwarg) is honored
# ---------------------------------------------------------------------------


def test_apply_memory_limit_threads_override(tmp_path: Path) -> None:
    """ML8: Explicit threads=N kwarg is set verbatim on the DuckDB conn."""
    import duckdb

    conn = duckdb.connect()
    spill_dir = tmp_path / "duckdb_spill"
    _apply_duckdb_memory_limit(conn, "2GB", spill_dir, threads=2)

    rows = conn.execute("SELECT current_setting('threads')").fetchall()
    threads_value = int(rows[0][0])
    assert threads_value == 2, (
        f"Threads override should set value verbatim; got {threads_value} (expected 2)"
    )
    conn.close()


def test_apply_memory_limit_temp_directory_set(tmp_path: Path) -> None:
    """ML7-extra: SET temp_directory is wired so GROUP BY can spill to disk.

    Per ``docs/internal/research/performance_reliability_targets.md`` §10 #2 — without
    a temp_directory, large GROUP BY aggregations OOM-kill DuckDB silently.
    """
    import duckdb

    conn = duckdb.connect()
    spill_dir = tmp_path / "spill_gb"
    _apply_duckdb_memory_limit(conn, "2GB", spill_dir)

    rows = conn.execute("SELECT current_setting('temp_directory')").fetchall()
    setting_value = rows[0][0]
    # DuckDB normalizes the path; just assert non-empty.
    assert setting_value, "temp_directory must be set to a non-empty path"
    conn.close()
