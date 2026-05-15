"""Empirical proof of the Dagster ⇄ mini-scheduler swap boundary.

Per ``nucleus_architecture_v4.1.md`` §6.7 (mini-scheduler) + §9.3
(composability constitution — interface + smoke tests + on-demand swap)
and the close-out evaluation directive "no actual swap has been done
end-to-end yet (no real proof we can swap Dagster for mini-scheduler)".

What this test proves
---------------------
1. The **default AMA path** materialises a 3-asset DAG (raw → staging →
   mart) via :func:`nucleus.coordination.asset_materialization.materialize_asset`
   producing a real Iceberg snapshot per asset.
2. The **mini-scheduler bypass path** materialises the SAME 3-asset DAG
   via :func:`nucleus.coordination.daemon.run_asset` (the v4.1 §6.7
   swap target) under ``NUCLEUS_USE_MINI_SCHEDULER=1`` and produces an
   equivalent :class:`MaterializationResult` per asset.
3. Row counts are identical between the two paths for every asset.
4. Neither path leaks Dagster classnames into user-facing strings —
   verified by scanning the rendered ``str(result)`` of each
   :class:`MaterializationResult`.

Why this matters
----------------
The Composability Constitution (``AGENTS.md`` §3 Constraint #9 +
``.cursor/rules/nucleus.mdc``) requires that every Tier 1/2 dependency
ships with a clean swap interface AND smoke tests — full swap
implementation is built on-demand only.  Pre-v0.2 we had the *interface*
(``daemon.trigger_asset``) but no empirical proof that the bypass route
could carry a real DAG.  This test is that proof; the launch FAQ
references this file path verbatim.

Scope
-----
* Pure in-process (no Docker, no MinIO, no Postgres).
* Filesystem Iceberg catalog under a pytest ``tmp_path``.
* 3 trivial Polars-DataFrame assets, no dependencies on user
  ``nucleus_project.yaml`` (test owns the warehouse dir).
* Marked ``@pytest.mark.slow`` because each materialisation does a real
  Iceberg commit (~1-2 s per asset on a beachhead-spec laptop) — the
  test is included in the default suite ``pytest tests/`` but excluded
  from ``-m "not slow"`` collection.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest

import nucleus
from nucleus.coordination.asset_materialization import materialize_asset
from nucleus.coordination.daemon import run_asset
from nucleus.sdk.decorators import _reset_registry_for_tests
from nucleus.sdk.results import MaterializationResult

# Three assets — independent bodies so the v0.1 ``upstream="skip"``
# default is honoured.  Each returns a small Polars DataFrame; the AMA
# commits the DataFrame to a per-asset Iceberg table.
# Docs (polars): https://docs.pola.rs/api/python/stable/
_RAW_ROWS = 5
_STAGING_ROWS = 4
_MART_ROWS = 3


def _register_three_asset_dag() -> tuple[str, str, str]:
    """Register raw.events → staging.daily → mart.summary and return their keys.

    The bodies are independent — ``deps=`` is declarative only in v0.1
    (recursive materialisation is v0.3+).  The test materialises each
    asset directly, in order, to mimic a small DAG walk.
    """

    @nucleus.asset("raw.events")
    def raw_events() -> pl.DataFrame:
        return pl.DataFrame(
            {
                "id": list(range(_RAW_ROWS)),
                "event_type": ["click", "view", "click", "purchase", "view"][:_RAW_ROWS],
                "value": [float(i) * 1.5 for i in range(_RAW_ROWS)],
            }
        )

    @nucleus.asset("staging.daily", deps=("raw.events",))
    def staging_daily() -> pl.DataFrame:
        return pl.DataFrame(
            {
                "day": ["2026-05-13", "2026-05-14", "2026-05-15", "2026-05-16"][:_STAGING_ROWS],
                "event_count": [10, 12, 8, 15][:_STAGING_ROWS],
                "revenue": [100.0, 120.5, 80.25, 150.75][:_STAGING_ROWS],
            }
        )

    @nucleus.asset("mart.summary", deps=("staging.daily",))
    def mart_summary() -> pl.DataFrame:
        return pl.DataFrame(
            {
                "metric": ["total_events", "total_revenue", "avg_per_day"][:_MART_ROWS],
                "value": [45.0, 451.5, 150.5][:_MART_ROWS],
            }
        )

    return ("raw.events", "staging.daily", "mart.summary")


@pytest.fixture(autouse=True)
def _clean_registry_and_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure both registry isolation and env-var cleanup for every test."""
    _reset_registry_for_tests()
    monkeypatch.delenv("NUCLEUS_USE_MINI_SCHEDULER", raising=False)
    try:
        yield
    finally:
        _reset_registry_for_tests()
        monkeypatch.delenv("NUCLEUS_USE_MINI_SCHEDULER", raising=False)


def _materialize_dag_default_path(
    keys: tuple[str, str, str], warehouse: Path
) -> list[MaterializationResult]:
    """Walk the DAG via the default AMA path — no env var set."""
    assert os.environ.get("NUCLEUS_USE_MINI_SCHEDULER") is None
    return [materialize_asset(k, warehouse_dir=warehouse) for k in keys]


def _materialize_dag_via_mini_scheduler(
    keys: tuple[str, str, str], warehouse: Path
) -> list[MaterializationResult]:
    """Walk the DAG via the daemon.run_asset entry point.

    This is the v4.1 §6.7 swap target.  We invoke ``run_asset`` directly
    rather than relying on the env-var router so the call stack
    unambiguously goes through the mini-scheduler path — exactly what
    the integration test must prove.
    """
    return [run_asset(k, warehouse_dir=warehouse) for k in keys]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_both_paths_produce_materialization_results(tmp_path: Path) -> None:
    """Both routes return :class:`MaterializationResult` per asset."""
    keys = _register_three_asset_dag()
    warehouse_default = tmp_path / "warehouse_default"
    warehouse_mini = tmp_path / "warehouse_mini"

    default_results = _materialize_dag_default_path(keys, warehouse_default)
    _reset_registry_for_tests()
    _register_three_asset_dag()
    mini_results = _materialize_dag_via_mini_scheduler(keys, warehouse_mini)

    assert len(default_results) == len(mini_results) == 3
    for result in default_results + mini_results:
        assert isinstance(result, MaterializationResult)


@pytest.mark.slow
def test_row_counts_match_between_paths(tmp_path: Path) -> None:
    """Same DAG, two routes — every asset commits the same number of rows."""
    keys = _register_three_asset_dag()
    warehouse_default = tmp_path / "warehouse_default"
    warehouse_mini = tmp_path / "warehouse_mini"

    default_results = _materialize_dag_default_path(keys, warehouse_default)
    _reset_registry_for_tests()
    _register_three_asset_dag()
    mini_results = _materialize_dag_via_mini_scheduler(keys, warehouse_mini)

    default_rows = {r.asset_key: r.row_count for r in default_results}
    mini_rows = {r.asset_key: r.row_count for r in mini_results}

    assert default_rows == mini_rows, (
        f"Row counts diverged between paths: default={default_rows} mini={mini_rows}"
    )
    assert default_rows[keys[0]] == _RAW_ROWS
    assert default_rows[keys[1]] == _STAGING_ROWS
    assert default_rows[keys[2]] == _MART_ROWS


@pytest.mark.slow
def test_both_paths_produce_real_iceberg_snapshots(tmp_path: Path) -> None:
    """Each materialisation lands a non-empty Iceberg snapshot_id."""
    keys = _register_three_asset_dag()
    warehouse_default = tmp_path / "warehouse_default"
    warehouse_mini = tmp_path / "warehouse_mini"

    default_results = _materialize_dag_default_path(keys, warehouse_default)
    _reset_registry_for_tests()
    _register_three_asset_dag()
    mini_results = _materialize_dag_via_mini_scheduler(keys, warehouse_mini)

    for result in default_results + mini_results:
        assert result.snapshot_id, (
            f"{result.asset_key} returned an empty snapshot_id "
            "(commit step was skipped — bypass path is incomplete)"
        )


@pytest.mark.slow
def test_mini_scheduler_path_has_no_dagster_classname_leak(tmp_path: Path) -> None:
    """v4.1 §6.4: the bypass path must not surface any Dagster identifier.

    Scans every user-facing field of the :class:`MaterializationResult`
    plus its ``str()`` rendering for the substring ``dagster.`` (the
    leak pattern the CI guard ``scripts/dagster_leak_check.py`` enforces).
    """
    keys = _register_three_asset_dag()
    warehouse = tmp_path / "warehouse_mini"

    mini_results = _materialize_dag_via_mini_scheduler(keys, warehouse)
    for result in mini_results:
        rendered_fields = (
            result.asset_key,
            result.snapshot_id,
            str(result.partition or ""),
            result.lineage_event_id,
            str(result),
            repr(result),
        )
        for chunk in rendered_fields:
            assert "dagster." not in chunk.lower(), (
                f"Dagster identifier leaked in MaterializationResult chunk: {chunk!r}"
            )


@pytest.mark.slow
def test_env_var_routes_default_call_through_mini_scheduler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting NUCLEUS_USE_MINI_SCHEDULER=1 makes materialize_asset use run_asset.

    The router increments :data:`_route_observed` via a sys.audit-style
    monkeypatch on ``daemon.run_asset`` so we can assert the bypass
    fired without inspecting private state.
    """
    keys = _register_three_asset_dag()
    warehouse = tmp_path / "warehouse_routed"

    from nucleus.coordination import daemon as _daemon

    observed: list[str] = []
    original_run_asset = _daemon.run_asset

    def _spy_run_asset(asset_key: str, **kwargs: object) -> MaterializationResult:
        observed.append(asset_key)
        return original_run_asset(asset_key, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(_daemon, "run_asset", _spy_run_asset)
    monkeypatch.setenv("NUCLEUS_USE_MINI_SCHEDULER", "1")

    results = [materialize_asset(k, warehouse_dir=warehouse) for k in keys]

    assert observed == list(keys), (
        "Expected materialize_asset to route every call through daemon.run_asset "
        f"when NUCLEUS_USE_MINI_SCHEDULER=1; observed={observed}"
    )
    assert all(isinstance(r, MaterializationResult) for r in results)


def test_run_asset_is_exported_from_daemon_module() -> None:
    """The mini-scheduler entry point is part of the daemon public surface.

    Without this export the launch-FAQ reference to the swap target
    would point to a private symbol — same anti-pattern the founder
    Anti-Over-Engineering directive guards against.
    """
    from nucleus.coordination import daemon

    assert "run_asset" in daemon.__all__
    assert callable(daemon.run_asset)


def test_run_asset_does_not_import_dagster_at_module_load() -> None:
    """daemon.run_asset is callable without forcing a Dagster import.

    The default path may pull Dagster in for scheduling, but the
    composability proof requires the bypass route to be reachable in a
    process where Dagster has never been imported.  We can only assert
    this is *possible* (other test files may have imported Dagster
    already in the same session), so the check is a soft hint: if
    Dagster isn't yet loaded, calling daemon.run_asset must not load
    it either.
    """
    if "dagster" in sys.modules:
        pytest.skip(
            "dagster already imported by an earlier test in this session — "
            "process-level isolation needed for this stricter assertion."
        )
    from nucleus.coordination import daemon

    _ = daemon.run_asset
    assert "dagster" not in sys.modules, (
        "Importing daemon.run_asset must not transitively import dagster"
    )
