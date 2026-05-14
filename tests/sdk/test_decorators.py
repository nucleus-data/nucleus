"""Tests for :mod:`nucleus.sdk.decorators` — ``@nucleus.asset`` + ``@nucleus.check``.

Validates the v0.1 surface per ``nucleus_ctx_sdk_spec.md`` §2.1 + §2.4 +
``nucleus_asset_model_spec.md`` §3 + §10. Decoration-time validation
(NucleusInvalidAssetDefinition) is exercised on every malformed input
shape so users see errors on import, not at runtime.

The registry is module-level state (``_ASSETS`` / ``_CHECKS`` dicts in
``nucleus.sdk.decorators``); the ``_clean_registry`` autouse fixture
clears both before AND after every test for cross-test isolation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import nucleus
from nucleus.errors import NucleusInvalidAssetDefinition
from nucleus.sdk.decorators import (
    _ASSET_MARKER,
    _CHECK_MARKER,
    _registered_keys,
    _reset_registry_for_tests,
    get_asset,
    get_checks,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Wipe asset + check registries before each test for isolation."""
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


# ---------------------------------------------------------------------------
# @nucleus.asset registration
# ---------------------------------------------------------------------------


class TestAssetRegistration:
    """``@nucleus.asset`` happy + invalid paths."""

    def test_registers_minimal_asset(self) -> None:
        @nucleus.asset("staging.orders")
        def staging_orders(_ctx: object) -> None:
            return None

        record = get_asset("staging.orders")
        assert record is not None
        assert record.key == "staging.orders"
        assert record.fn is staging_orders
        assert record.deps == ()
        assert record.partitions is None
        assert record.compute is None
        assert record.contract is None

    def test_decorator_returns_original_function_unchanged(self) -> None:
        @nucleus.asset("staging.orders")
        def fn(_ctx: object) -> int:
            return 42

        # Calling the decorated function still returns the body's value
        # (the registry stores the function; it does not wrap it).
        assert fn(object()) == 42
        assert getattr(fn, _ASSET_MARKER) == "staging.orders"

    def test_explicit_deps_validated_and_stored_as_tuple(self) -> None:
        @nucleus.asset(
            "marts.orders_clean",
            deps=["staging.orders", "dim.customers"],
        )
        def marts(_ctx: object) -> None:
            return None

        record = get_asset("marts.orders_clean")
        assert record is not None
        assert record.deps == ("staging.orders", "dim.customers")

    def test_passes_partitions_and_contract_through_unchanged(self) -> None:
        sentinel_partition = object()
        sentinel_contract = object()

        @nucleus.asset(
            "staging.events",
            partitions=sentinel_partition,
            contract=sentinel_contract,
        )
        def events(_ctx: object) -> None:
            return None

        record = get_asset("staging.events")
        assert record is not None
        assert record.partitions is sentinel_partition
        assert record.contract is sentinel_contract

    def test_compute_local_accepted(self) -> None:
        @nucleus.asset("staging.x", compute="local")
        def x(_ctx: object) -> None:
            return None

        assert get_asset("staging.x").compute == "local"  # type: ignore[union-attr]

    def test_invalid_key_shape_raises(self) -> None:
        # 1-level key — invalid in v0.1 (cli_spec §10 NV #6).
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            nucleus.asset("orders")
        msg = exc_info.value.user_message
        assert "orders" in msg
        assert "2-level" in msg or "<schema>" in msg

    def test_empty_key_raises(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.asset("")

    def test_non_string_key_raises(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.asset(42)  # type: ignore[arg-type]

    def test_deps_with_self_reference_raises(self) -> None:
        # asset model spec §6.3 — self-edges are forbidden.
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            nucleus.asset("staging.x", deps=["staging.x"])
        assert "self" in exc_info.value.user_message.lower()

    def test_deps_with_invalid_entry_shape_raises(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.asset("staging.x", deps=["not a key"])

    def test_deps_string_argument_rejected(self) -> None:
        # Bare-string deps is a footgun — every char becomes one dep.
        # mypy treats ``str`` as ``Sequence[str]``; the runtime guard catches
        # the case mypy cannot, so this branch must hold even when typed.
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.asset("staging.x", deps="raw.orders")

    def test_compute_invalid_value_raises(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            nucleus.asset("staging.x", compute="databricks")
        assert "v0.1" in exc_info.value.user_message
        assert "databricks" in exc_info.value.user_message

    def test_lambda_target_rejected(self) -> None:
        decorator = nucleus.asset("staging.x")
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            decorator(lambda _ctx: None)
        assert "lambda" in exc_info.value.user_message.lower()

    def test_duplicate_key_with_different_function_raises(self) -> None:
        @nucleus.asset("staging.dup")
        def first(_ctx: object) -> None:
            return None

        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:

            @nucleus.asset("staging.dup")
            def second(_ctx: object) -> None:
                return None

        assert "already defined" in exc_info.value.user_message
        # First definition is still the one in the registry.
        assert get_asset("staging.dup").fn is first  # type: ignore[union-attr]

    def test_re_decoration_of_same_function_is_idempotent(self) -> None:
        # Re-importing the same module should not raise.
        def fn(_ctx: object) -> None:
            return None

        nucleus.asset("staging.idem")(fn)
        nucleus.asset("staging.idem")(fn)
        assert get_asset("staging.idem").fn is fn  # type: ignore[union-attr]

    def test_registered_keys_helper_returns_sorted_tuple(self) -> None:
        @nucleus.asset("staging.b")
        def b(_ctx: object) -> None: ...

        @nucleus.asset("staging.a")
        def a(_ctx: object) -> None: ...

        assert _registered_keys() == ("staging.a", "staging.b")


# ---------------------------------------------------------------------------
# @nucleus.check registration
# ---------------------------------------------------------------------------


class TestCheckRegistration:
    """``@nucleus.check`` happy + invalid paths."""

    def test_registers_default_severity_error(self) -> None:
        @nucleus.check("staging.orders")
        def chk(_ctx: object) -> nucleus.CheckResult:
            return nucleus.CheckResult(passed=True)

        records = get_checks("staging.orders")
        assert len(records) == 1
        assert records[0].severity == "error"
        assert records[0].fn is chk
        assert getattr(chk, _CHECK_MARKER) == "staging.orders"

    def test_severity_warn_accepted(self) -> None:
        @nucleus.check("staging.orders", severity="warn")
        def chk(_ctx: object) -> nucleus.CheckResult:
            return nucleus.CheckResult(passed=True)

        assert get_checks("staging.orders")[0].severity == "warn"

    def test_unknown_severity_rejected(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
            nucleus.check("staging.orders", severity="critical")
        msg = exc_info.value.user_message
        assert "critical" in msg
        assert "v0.1" in msg

    def test_block_consumers_severity_deferred(self) -> None:
        # asset model spec §9.2 row 3 — deferred to v0.3+.
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.check("staging.orders", severity="block_consumers")

    def test_invalid_asset_key_rejected(self) -> None:
        with pytest.raises(NucleusInvalidAssetDefinition):
            nucleus.check("not a key")

    def test_multiple_checks_per_asset_collected_in_order(self) -> None:
        @nucleus.check("staging.orders")
        def chk_a(_ctx: object) -> nucleus.CheckResult:
            return nucleus.CheckResult(passed=True)

        @nucleus.check("staging.orders", severity="warn")
        def chk_b(_ctx: object) -> nucleus.CheckResult:
            return nucleus.CheckResult(passed=True)

        records = get_checks("staging.orders")
        assert [r.fn for r in records] == [chk_a, chk_b]
        assert [r.severity for r in records] == ["error", "warn"]

    def test_lambda_check_target_rejected(self) -> None:
        decorator = nucleus.check("staging.orders")
        with pytest.raises(NucleusInvalidAssetDefinition):
            decorator(lambda _ctx: nucleus.CheckResult(passed=True))

    def test_get_checks_for_unknown_asset_returns_empty_tuple(self) -> None:
        assert get_checks("does.not_exist") == ()
