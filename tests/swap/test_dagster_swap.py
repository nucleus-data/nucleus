"""Swap smoke tests — Dagster → ``nucleus-mini-scheduler``.

Per AGENTS.md Hard Constraint #9 + ``docs/specs/nucleus_architecture_v4.1.md`` §6.7,
§9.3. Tests Dagster transitively through the AMA's public surface — NO
direct ``import dagster`` here because ``scripts/dagster_leak_check.py``
forbids it outside ``src/nucleus/coordination/`` + ``tests/coordination/``.
``tests/internal/swap/`` is intentionally NOT in the allow-list.
Reference: ``docs/internal/swap/dagster.md`` · Docs: https://docs.dagster.io/api/python-api/
"""

from __future__ import annotations

import importlib.util

import pytest

import nucleus
from nucleus.coordination import asset_materialization as ama
from nucleus.errors import NucleusAssetNotFound, NucleusError
from nucleus.sdk.decorators import _reset_registry_for_tests

_SKIP = "swap target — full impl on-demand only per .cursor/rules/nucleus.mdc Composability Constitution"


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    _reset_registry_for_tests()


def test_ama_materialize_happy_path_returns_result() -> None:
    @nucleus.asset("swap.smoke")
    def _smoke() -> int:
        return 42

    result = ama.materialize_asset("swap.smoke")
    assert result.asset_key == "swap.smoke" and result.duration_ms >= 0


def test_ama_dry_run_returns_sentinels() -> None:
    """dry_run=True executes the body but skips the Iceberg commit (sentinels)."""

    @nucleus.asset("swap.dry")
    def _dry() -> int:
        return 1

    result = ama.materialize_asset("swap.dry", dry_run=True)
    assert result.asset_key == "swap.dry" and result.snapshot_id == ""


def test_ama_unknown_key_raises_nucleus_error_no_dagster_leak() -> None:
    """Error translation produces NucleusError with no `dagster.` leak."""
    with pytest.raises(NucleusAssetNotFound) as exc_info:
        ama.materialize_asset("does.not.exist")
    rendered = (
        exc_info.value.rendered() if hasattr(exc_info.value, "rendered") else str(exc_info.value)
    )
    assert "dagster" not in rendered.lower()
    assert isinstance(exc_info.value, NucleusError)


def test_ama_helpers_present_as_swap_unit_boundary() -> None:
    """AMA helpers form the swap unit per docs/internal/swap/dagster.md (Option A, 2026-05-14).

    The Dagster swap boundary now uses direct asset-body invocation
    (_invoke_asset_body) + pyiceberg commit (_commit_to_iceberg) instead
    of the former _build_dagster_assets_definition / _run_dagster_in_process
    path. The public AMA contract (materialize_asset signature) is unchanged.
    """
    for fn in (
        "_resolve_asset_from_registry",
        "_invoke_asset_body",
        "_commit_to_iceberg",
        "materialize_asset",
    ):
        assert hasattr(ama, fn), f"AMA helper {fn} missing — swap boundary broken."


def test_dagster_runtime_dep_discoverable_via_find_spec() -> None:
    """Verify dagster is discoverable without importing it (leak check)."""
    assert importlib.util.find_spec("dagster") is not None


def test_mini_scheduler_swap_target_not_yet_built() -> None:
    """Per v4.1 §6.7, mini-scheduler lands by v1.0 OR on trigger. Pre-trigger
    it must NOT exist (full swap on-demand only per v4.1 §9.3)."""
    assert importlib.util.find_spec("nucleus.coordination.mini_scheduler") is None


@pytest.mark.skip(reason=_SKIP)
def test_mini_scheduler_materialize_happy_path() -> None:
    """Port test_ama_materialize_happy_path when triggered."""


@pytest.mark.skip(reason=_SKIP)
def test_mini_scheduler_error_translation_no_leak() -> None:
    """Verify mini-scheduler unwrapped errors translate cleanly when triggered."""
