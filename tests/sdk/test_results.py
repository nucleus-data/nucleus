"""Tests for :mod:`nucleus.sdk.results`.

Validates the three frozen-shape value types per
``docs/decisions/ADR-013-ctx-materialize-api.md`` §2 (MaterializationResult),
``docs/specs/nucleus_ctx_sdk_spec.md`` §3.1 + §12 (AssetRef), and
``docs/specs/nucleus_asset_model_spec.md`` §10 (CheckResult).

Discipline:
- All three types MUST be ``@dataclass(frozen=True)`` so user code
  cannot mutate fields after construction.
- Field names MUST match ADR-013 §2 verbatim — they are the public
  shape (Beta @ v0.1 → Stable @ v0.5; field-add safe per ADR-005 §1 + ADR-013 §3,
  rename/remove blocked).
- Types must round-trip via ``repr()`` for CLI rendering.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import UTC, datetime

import pytest

import nucleus
from nucleus.sdk.results import AssetRef, CheckResult, MaterializationResult


class TestMaterializationResult:
    """ADR-013 §2 — the frozen dataclass (field-additive per ADR-005 §1 + ADR-013 §3)."""

    def _make(self) -> MaterializationResult:
        return MaterializationResult(
            asset_key="staging.orders",
            snapshot_id="snap-abc",
            partition=None,
            row_count=42,
            duration_ms=120,
            lineage_event_id="evt-1",
            materialized_at=datetime(2026, 5, 13, tzinfo=UTC),
        )

    def test_is_frozen_dataclass(self) -> None:
        assert is_dataclass(MaterializationResult)
        assert MaterializationResult.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    def test_all_fields_present_in_order(self) -> None:
        names = [f.name for f in fields(MaterializationResult)]
        # Order matters because positional construction in tests + the
        # ADR-013 §2 spec lock the ordering. Field-additive per ADR-005
        # §3 — ``checks`` landed 2026-05-13 alongside the contracts
        # runtime (v4.1 §15) per docs/decisions/ADR-013-ctx-materialize-api.md §2.
        assert names == [
            "asset_key",
            "snapshot_id",
            "partition",
            "row_count",
            "duration_ms",
            "lineage_event_id",
            "materialized_at",
            "checks",
        ]

    def test_roundtrips_via_repr(self) -> None:
        mr = self._make()
        text = repr(mr)
        assert "MaterializationResult" in text
        assert "asset_key='staging.orders'" in text
        assert "row_count=42" in text

    def test_mutation_raises_frozen_instance_error(self) -> None:
        mr = self._make()
        with pytest.raises(FrozenInstanceError):
            mr.row_count = 99  # type: ignore[misc]

    def test_partition_can_be_string(self) -> None:
        mr = MaterializationResult(
            asset_key="events.clicks",
            snapshot_id="snap-z",
            partition="2026-05-13",
            row_count=0,
            duration_ms=0,
            lineage_event_id="evt-z",
            materialized_at=datetime(2026, 5, 13, tzinfo=UTC),
        )
        assert mr.partition == "2026-05-13"

    def test_reexported_from_nucleus_top_level(self) -> None:
        # docs/specs/nucleus_ctx_sdk_spec.md §1+§12 — users write
        # `nucleus.MaterializationResult`, not the qualified path.
        assert nucleus.MaterializationResult is MaterializationResult


class TestAssetRef:
    """docs/specs/nucleus_ctx_sdk_spec.md §3.1 + §12 — frozen handle to an asset."""

    def test_is_frozen_dataclass(self) -> None:
        assert is_dataclass(AssetRef)
        assert AssetRef.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    def test_str_returns_canonical_key(self) -> None:
        ref = AssetRef("marts.orders_clean")
        assert str(ref) == "marts.orders_clean"
        assert ref.key == "marts.orders_clean"

    def test_mutation_raises_frozen_instance_error(self) -> None:
        ref = AssetRef("staging.orders")
        with pytest.raises(FrozenInstanceError):
            ref.key = "other.x"  # type: ignore[misc]

    def test_reexported_from_nucleus_top_level(self) -> None:
        assert nucleus.AssetRef is AssetRef


class TestCheckResult:
    """docs/specs/nucleus_ctx_sdk_spec.md §2.4 + docs/specs/nucleus_asset_model_spec.md §10."""

    def test_is_frozen_dataclass(self) -> None:
        assert is_dataclass(CheckResult)
        assert CheckResult.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    def test_minimal_construction_uses_default_metric_and_message(self) -> None:
        cr = CheckResult(passed=True)
        assert cr.passed is True
        assert cr.metric == 0.0
        assert cr.message == ""

    def test_full_construction_keeps_all_fields(self) -> None:
        cr = CheckResult(passed=False, metric=3.0, message="3 nulls found")
        assert cr.passed is False
        assert cr.metric == 3.0
        assert cr.message == "3 nulls found"

    def test_mutation_raises_frozen_instance_error(self) -> None:
        cr = CheckResult(passed=True)
        with pytest.raises(FrozenInstanceError):
            cr.passed = False  # type: ignore[misc]

    def test_reexported_from_nucleus_top_level(self) -> None:
        assert nucleus.CheckResult is CheckResult
