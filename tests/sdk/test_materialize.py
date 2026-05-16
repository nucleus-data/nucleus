"""Tests for :mod:`nucleus.sdk.materialize` — the ``nucleus.materialize`` API.

Validates the public signature per
``docs/decisions/ADR-013-ctx-materialize-api.md`` §1 +
``docs/specs/nucleus_architecture_v4.1.md`` §13.2 — every input is checked at the
SDK boundary, and the call forwards to the Asset Materialization Adapter
(``coordination/asset_materialization.py``,
``v01_skeleton_plan.md`` §3.1 r3) which drives the wrapped Dagster runtime.

ADR-013 §4 promises specific NucleusError subclasses for specific input
errors; the test suite below exercises each of those branches.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import nucleus
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusInternalError,
    NucleusInvalidAssetDefinition,
)
from nucleus.sdk.decorators import _reset_registry_for_tests


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


@pytest.fixture()
def registered_asset() -> str:
    """Register a single asset and return its key."""

    @nucleus.asset("staging.orders")
    def staging_orders(_ctx: object) -> None:
        return None

    return "staging.orders"


# ---------------------------------------------------------------------------
# Public surface — re-export sanity
# ---------------------------------------------------------------------------


class TestPublicSurface:
    def test_materialize_is_re_exported_from_nucleus(self) -> None:
        from nucleus.sdk.materialize import materialize as direct

        assert nucleus.materialize is direct

    def test_materialize_present_in_nucleus_all(self) -> None:
        assert "materialize" in nucleus.__all__


# ---------------------------------------------------------------------------
# Input validation — typed errors per ADR-013 §4
# ---------------------------------------------------------------------------


class TestArgumentValidation:
    def test_empty_asset_string_raises_invalid(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.materialize("")

    def test_non_string_non_assetref_asset_raises_invalid(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.materialize(42)  # type: ignore[arg-type]

    def test_unknown_asset_key_raises_asset_not_found(self, registered_asset: str) -> None:
        # Per ADR-013 §4: NE3002 (NucleusAssetNotFound) when key unresolvable.
        del registered_asset  # registers something else; the lookup below misses
        with pytest.raises(NucleusAssetNotFound) as exc_info:
            nucleus.materialize("does.not_exist")
        assert exc_info.value.asset == "does.not_exist"
        assert "does.not_exist" in exc_info.value.user_message

    def test_assetref_form_is_accepted(self, registered_asset: str) -> None:
        # Per ADR-013 §1: asset accepts `str | AssetRef`. After AMA promotion
        # (v01_skeleton_plan §3.1 r3) the call resolves to a real
        # MaterializationResult; the SDK boundary's responsibility here is
        # purely to unwrap AssetRef → str without losing identity.
        from nucleus.sdk.results import MaterializationResult

        ref = nucleus.AssetRef(registered_asset)
        result = nucleus.materialize(ref)
        assert isinstance(result, MaterializationResult)
        assert result.asset_key == registered_asset

    def test_invalid_upstream_value_raises_invalid(self, registered_asset: str) -> None:
        # Per ADR-013 §1: upstream must be one of the three Literal values.
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            nucleus.materialize(registered_asset, upstream="recursive")
        assert "upstream" in exc_info.value.user_message

    def test_default_upstream_is_skip(self, registered_asset: str) -> None:
        # Per ADR-013 §NV #6: v0.1 accepts upstream='skip' only.
        # The default upstream kwarg must reach the AMA without triggering
        # the "deferred to v0.3+" path that 'materialize' / 'validate' take.
        from nucleus.sdk.results import MaterializationResult

        result = nucleus.materialize(registered_asset)
        assert isinstance(result, MaterializationResult)
        assert result.asset_key == registered_asset

    def test_upstream_materialize_deferred_to_v03(self, registered_asset: str) -> None:
        # Per ADR-013 §NV #6: 'materialize' deferred to v0.3+.
        with pytest.raises(NucleusInternalError) as exc_info:
            nucleus.materialize(registered_asset, upstream="materialize")
        assert "v0.3" in exc_info.value.user_message
        assert (
            "upstream='materialize'" in exc_info.value.user_message
            or "materialize" in exc_info.value.user_message
        )

    def test_upstream_validate_deferred_to_v03(self, registered_asset: str) -> None:
        with pytest.raises(NucleusInternalError) as exc_info:
            nucleus.materialize(registered_asset, upstream="validate")
        assert "v0.3" in exc_info.value.user_message

    def test_negative_timeout_raises_invalid(self, registered_asset: str) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            nucleus.materialize(registered_asset, timeout_seconds=-1)
        assert (
            "> 0" in exc_info.value.user_message or "timeout_seconds" in exc_info.value.user_message
        )

    def test_zero_timeout_raises_invalid(self, registered_asset: str) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.materialize(registered_asset, timeout_seconds=0)

    def test_non_integer_timeout_raises_invalid(self, registered_asset: str) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.materialize(registered_asset, timeout_seconds=3.14)  # type: ignore[arg-type]

    def test_bool_timeout_rejected(self, registered_asset: str) -> None:
        # bool is a subclass of int — must be explicitly rejected at runtime
        # so `timeout_seconds=True` doesn't silently mean 1 second. mypy
        # treats this as int-compatible so no `# type: ignore` is needed.
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.materialize(registered_asset, timeout_seconds=True)

    def test_non_string_partition_raises_invalid(self, registered_asset: str) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.materialize(registered_asset, partition=("2026-05-13",))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SDK → AMA delegation — once the Asset Materialization Adapter is promoted
# (``coordination/asset_materialization.py``; v01_skeleton_plan §3.1 r3) the
# SDK boundary's only job for a known-good asset is to forward the call and
# return the typed ``MaterializationResult`` unchanged. End-to-end behaviour
# (Dagster wrap, error translation, sentinel field values) is exercised in
# ``tests/coordination/test_asset_materialization.py``; the cases below
# verify only the contract this module owns.
# ---------------------------------------------------------------------------


class TestSDKDelegation:
    def test_delegation_returns_materialization_result(self, registered_asset: str) -> None:
        from nucleus.sdk.results import MaterializationResult

        result = nucleus.materialize(registered_asset)
        assert isinstance(result, MaterializationResult)

    def test_result_carries_asset_key(self, registered_asset: str) -> None:
        result = nucleus.materialize(registered_asset)
        assert result.asset_key == registered_asset

    def test_no_dagster_strings_in_result_repr(self, registered_asset: str) -> None:
        # v4.1 §6.4: user-facing strings must NEVER carry external classnames.
        # The rendered ``MaterializationResult`` is part of the user-visible
        # surface (logged, returned, str-formatted in CLI output), so a
        # Dagster string here would be the same release-blocker leak the
        # rendered NucleusError forbids.
        result = nucleus.materialize(registered_asset)
        rendered = repr(result).lower() + " " + str(result).lower()
        assert "dagster" not in rendered
        assert "duckdb" not in rendered
        assert "polars" not in rendered
        assert "pyiceberg" not in rendered
