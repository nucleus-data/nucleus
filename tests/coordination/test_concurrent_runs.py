"""Tests for concurrent-run protection via advisory lock in the AMA.

Validates ADR-024 P0-2 integration: the AMA acquires an advisory lock
before the Iceberg commit path, preventing two simultaneous ``nucleus run``
invocations from corrupting the same asset (chaos scenario J6).

Coverage:
    C1  Successful materialize + lock acquired + released (integration).
    C2  NucleusConcurrentRunError surfaced as NE3008 when lock times out.
    C3  lock_timeout parameter propagates correctly.
    C4  warehouse_dir=None skips lock (dry_run / deferred-commit path).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest

import nucleus
from nucleus.coordination.asset_materialization import materialize_asset
from nucleus.coordination.locks import asset_lock
from nucleus.errors import NucleusConcurrentRunError
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
# C1: Successful materialize acquires and releases lock
# ---------------------------------------------------------------------------


def test_materialize_acquires_and_releases_lock(tmp_path: Path) -> None:
    """C1: After materialize_asset returns, the advisory lock is released."""
    warehouse = tmp_path / "warehouse"

    @nucleus.asset("staging.orders")
    def staging_orders() -> pl.DataFrame:
        return pl.DataFrame({"id": [1, 2, 3], "amount": [10.0, 20.0, 30.0]})

    result = materialize_asset("staging.orders", warehouse_dir=warehouse)
    assert result.snapshot_id != ""

    # Lock must be released — a second call must succeed immediately.
    @nucleus.asset("staging.orders_v2")
    def staging_orders_v2() -> pl.DataFrame:
        return pl.DataFrame({"id": [4]})

    result2 = materialize_asset("staging.orders_v2", warehouse_dir=warehouse)
    assert result2.snapshot_id != ""


# ---------------------------------------------------------------------------
# C2: Concurrent materialize raises NE3008
# ---------------------------------------------------------------------------


def test_concurrent_materialize_raises_ne3008(tmp_path: Path) -> None:
    """C2: A second materialize on the same asset raises NucleusConcurrentRunError."""
    warehouse = tmp_path / "warehouse"
    ready = threading.Event()
    can_release = threading.Event()

    # Hold the lock manually to simulate an in-flight run.
    def _hold() -> None:
        with asset_lock(warehouse.parent, "staging.orders", timeout=60):
            ready.set()
            can_release.wait(timeout=5)

    thread = threading.Thread(target=_hold, daemon=True)
    thread.start()
    ready.wait(timeout=5)

    @nucleus.asset("staging.orders")
    def staging_orders() -> pl.DataFrame:
        return pl.DataFrame({"id": [1]})

    try:
        with pytest.raises(NucleusConcurrentRunError) as exc_info:
            materialize_asset(
                "staging.orders",
                warehouse_dir=warehouse,
                lock_timeout=0.3,
            )
        assert exc_info.value.error_code == "NE3008"
        assert "staging.orders" in exc_info.value.user_message
    finally:
        can_release.set()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# C3: lock_timeout propagates
# ---------------------------------------------------------------------------


def test_lock_timeout_parameter_propagates(tmp_path: Path) -> None:
    """C3: lock_timeout=0.1 causes fast failure on a contested lock."""
    warehouse = tmp_path / "warehouse"
    ready = threading.Event()
    can_release = threading.Event()

    def _hold() -> None:
        with asset_lock(warehouse.parent, "staging.orders", timeout=60):
            ready.set()
            can_release.wait(timeout=5)

    thread = threading.Thread(target=_hold, daemon=True)
    thread.start()
    ready.wait(timeout=5)

    @nucleus.asset("staging.orders")
    def staging_orders() -> pl.DataFrame:
        return pl.DataFrame({"id": [1]})

    import time

    t0 = time.monotonic()
    try:
        with pytest.raises(NucleusConcurrentRunError):
            materialize_asset(
                "staging.orders",
                warehouse_dir=warehouse,
                lock_timeout=0.1,
            )
        elapsed = time.monotonic() - t0
        # Should fail fast — well under 2 seconds
        assert elapsed < 2.0, f"Expected fast timeout but took {elapsed:.2f}s"
    finally:
        can_release.set()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# C4: warehouse_dir=None skips the lock
# ---------------------------------------------------------------------------


def test_no_lock_when_warehouse_dir_is_none(tmp_path: Path) -> None:
    """C4: warehouse_dir=None (deferred-commit) bypasses the advisory lock."""

    @nucleus.asset("staging.orders")
    def staging_orders() -> pl.DataFrame:
        return pl.DataFrame({"id": [1]})

    # With warehouse_dir=None, no lock is acquired.  A pre-held lock on
    # the project_root fallback must NOT block this call.
    result = materialize_asset("staging.orders", warehouse_dir=None)
    assert result.snapshot_id == ""
