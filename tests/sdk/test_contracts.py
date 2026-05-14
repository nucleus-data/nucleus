# ruff: noqa: E402, I001 -- importorskip("dagster") inside class is load-bearing.
"""Tests for :mod:`nucleus.sdk.contracts` — schema-contracts runtime.

Validates the v0.1 wire-up of ``@nucleus.check`` execution per
``nucleus_architecture_v4.1.md`` §15 +
``nucleus_asset_model_spec.md`` §10 + the file's docstring contract:

    - registration discovery via :func:`list_registered_checks`
    - sequential execution + result normalisation via
      :func:`run_checks_for_asset`
    - error translation: raise → :class:`NucleusCheckExecutionError`
      (NE3007) folded into a failing :class:`CheckResult`
    - end-to-end integration via the Asset Materialization Adapter
      (:mod:`nucleus.coordination.asset_materialization`), so the v0.1
      ``MaterializationResult.checks`` field is no longer dead code.

The registry is module-level state (``_CHECKS`` dict in
``nucleus.sdk.decorators``); the ``_clean_registry`` autouse fixture
clears it before AND after every test for cross-test isolation, the same
pattern :mod:`tests.sdk.test_decorators` and :mod:`tests.sdk.test_materialize`
already use.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import nucleus
from nucleus.errors import (
    NucleusCheckExecutionError,
    NucleusError,
    NucleusSchemaError,
)
from nucleus.sdk import contracts
from nucleus.sdk.decorators import _reset_registry_for_tests
from nucleus.sdk.results import CheckResult


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Wipe asset + check registries before each test for isolation."""
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


# ---------------------------------------------------------------------------
# Registration discovery — list_registered_checks
# ---------------------------------------------------------------------------


class TestRegistrationDiscovery:
    """:func:`contracts.list_registered_checks` walks the decorator registry."""

    def test_single_check_registered_returns_one_name(self) -> None:
        @nucleus.check("staging.orders")
        def chk_amounts_non_negative() -> CheckResult:
            return CheckResult(passed=True)

        names = contracts.list_registered_checks("staging.orders")
        assert len(names) == 1
        # __qualname__ is what the contracts runtime uses; mirror that here
        # rather than asserting a bare name so nested/method checks work.
        assert "chk_amounts_non_negative" in names[0]

    def test_multiple_checks_returned_in_registration_order(self) -> None:
        @nucleus.check("staging.orders")
        def first_check() -> CheckResult:
            return CheckResult(passed=True)

        @nucleus.check("staging.orders", severity="warn")
        def second_check() -> CheckResult:
            return CheckResult(passed=True)

        names = contracts.list_registered_checks("staging.orders")
        assert len(names) == 2
        # Order is registration order per the docstring contract.
        assert "first_check" in names[0]
        assert "second_check" in names[1]

    def test_unknown_asset_returns_empty_tuple(self) -> None:
        assert contracts.list_registered_checks("does.not_exist") == ()


# ---------------------------------------------------------------------------
# Execution happy paths — run_checks_for_asset return-shape handling
# ---------------------------------------------------------------------------


class TestExecutionHappyPaths:
    """``run_checks_for_asset`` normalises the supported return shapes."""

    def test_bool_true_return_wrapped_as_passing(self) -> None:
        @nucleus.check("staging.x")
        def chk() -> bool:
            return True

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 1
        assert results[0].passed is True

    def test_bool_false_return_wrapped_as_failing(self) -> None:
        @nucleus.check("staging.x")
        def chk() -> bool:
            return False

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].metric == 0.0
        assert results[0].message == ""

    def test_native_check_result_passed_through(self) -> None:
        @nucleus.check("staging.x")
        def chk() -> CheckResult:
            return CheckResult(passed=False, metric=3.0, message="3 nulls found")

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].metric == 3.0
        assert results[0].message == "3 nulls found"

    def test_dict_return_rejected_as_failing_with_unsupported_type(self) -> None:
        # The decorator only accepts callables, not dicts. The check body
        # returning a dict is a common author mistake. Surface as a failing
        # CheckResult so the user sees what went wrong on the result, not
        # an exception.
        @nucleus.check("staging.x")
        def chk() -> dict[str, bool]:
            return {"passed": True}  # type: ignore[return-value]

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 1
        assert results[0].passed is False
        assert NucleusCheckExecutionError.error_code in results[0].message
        assert "dict" in results[0].message


# ---------------------------------------------------------------------------
# Error translation per AGENTS.md §11.7 + v4.1 §6.4
# ---------------------------------------------------------------------------


class TestErrorTranslation:
    """Every raise inside a check body becomes a failing CheckResult."""

    def test_value_error_caught_and_wrapped_with_ne2006(self) -> None:
        @nucleus.check("staging.x")
        def chk_divide_zero() -> CheckResult:
            raise ValueError("amounts contain a non-numeric value")

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 1
        assert results[0].passed is False
        assert NucleusCheckExecutionError.error_code == "NE3007"
        assert "NE3007" in results[0].message
        # Original message must surface so the user sees what failed.
        assert "non-numeric" in results[0].message

    def test_already_typed_nucleus_error_not_double_translated(self) -> None:
        # If a check body raises a NucleusError, preserve the original
        # error_code rather than re-wrap as NE3007. Mirrors the
        # error_translation.translate() idempotency contract.
        @nucleus.check("staging.x")
        def chk_schema() -> CheckResult:
            raise NucleusSchemaError(
                user_message="amounts column missing",
                fix_hint="Add the amounts column.",
            )

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 1
        assert results[0].passed is False
        assert "NE2001" in results[0].message
        assert "NE3007" not in results[0].message
        assert "amounts column missing" in results[0].message

    def test_one_failing_check_does_not_block_remaining_checks(self) -> None:
        # 3 checks, middle raises. The other two must still execute and
        # return their own results — this is the v0.1 contract that lets
        # users see the full picture in one materialization.
        @nucleus.check("staging.x")
        def chk_a() -> CheckResult:
            return CheckResult(passed=True, metric=1.0)

        @nucleus.check("staging.x")
        def chk_b() -> CheckResult:
            raise RuntimeError("intermittent")

        @nucleus.check("staging.x")
        def chk_c() -> CheckResult:
            return CheckResult(passed=True, metric=3.0)

        results = contracts.run_checks_for_asset("staging.x")
        assert len(results) == 3
        assert results[0].passed is True
        assert results[0].metric == 1.0
        assert results[1].passed is False
        assert "NE3007" in results[1].message
        assert results[2].passed is True
        assert results[2].metric == 3.0


# ---------------------------------------------------------------------------
# AMA integration — closes the v0.1 loop
# Dagster is the only Coordination-layer module permitted to import dagster
# (v4.1 §6.4), so its integration tests share the same precondition as
# tests/coordination/test_asset_materialization.py.
# ---------------------------------------------------------------------------

dagster = pytest.importorskip("dagster")

from nucleus.coordination.asset_materialization import materialize_asset


class TestAMAIntegration:
    """End-to-end: ``materialize_asset`` populates ``result.checks``."""

    def test_result_checks_populated_after_successful_materialization(self) -> None:
        @nucleus.asset("staging.with_checks")
        def staging_with_checks() -> None:
            return None

        @nucleus.check("staging.with_checks")
        def chk_basic() -> CheckResult:
            return CheckResult(passed=True, metric=10.0, message="ten rows ok")

        result = materialize_asset("staging.with_checks")
        # The PHASE C commitment: result.checks is no longer dead code.
        assert len(result.checks) == 1
        assert result.checks[0].passed is True
        assert result.checks[0].metric == 10.0
        assert result.checks[0].message == "ten rows ok"

    def test_multiple_checks_each_attached_with_correct_outcome(self) -> None:
        @nucleus.asset("staging.multi")
        def staging_multi() -> None:
            return None

        @nucleus.check("staging.multi")
        def passing_check() -> CheckResult:
            return CheckResult(passed=True)

        @nucleus.check("staging.multi", severity="warn")
        def failing_check() -> CheckResult:
            return CheckResult(passed=False, metric=5.0, message="warn-only fail")

        result = materialize_asset("staging.multi")
        assert len(result.checks) == 2
        # Order is registration order per the contracts.run_checks_for_asset contract.
        assert result.checks[0].passed is True
        assert result.checks[1].passed is False
        assert result.checks[1].message == "warn-only fail"

    def test_dry_run_skips_checks_and_returns_empty_tuple(self) -> None:
        # Per the v0.1 design (asset_materialization.py inline comment):
        # checks need real materialized data, so dry_run leaves the default.
        @nucleus.asset("staging.dryrun")
        def staging_dryrun() -> None:
            return None

        @nucleus.check("staging.dryrun")
        def chk() -> CheckResult:
            return CheckResult(passed=False, message="should NOT see this on dry_run")

        result = materialize_asset("staging.dryrun", dry_run=True)
        assert result.checks == ()

    def test_failing_check_does_not_abort_materialization(self) -> None:
        # Materialize succeeds (returns normally) even when a check fails —
        # the user inspects result.checks to decide BI-readiness.
        @nucleus.asset("staging.fail_chk")
        def staging_fail_chk() -> None:
            return None

        @nucleus.check("staging.fail_chk")
        def chk_raises() -> CheckResult:
            raise RuntimeError("simulated bad data")

        # No raise from materialize_asset itself.
        result = materialize_asset("staging.fail_chk")
        assert result.asset_key == "staging.fail_chk"
        assert len(result.checks) == 1
        assert result.checks[0].passed is False
        assert "NE3007" in result.checks[0].message

    def test_no_external_classnames_leak_into_check_messages(self) -> None:
        # v4.1 §6.4 + scripts/dagster_leak_check.py: the rendered user-facing
        # surface must NEVER contain external classnames. CheckResult.message
        # is on that surface.
        @nucleus.asset("staging.leak_check")
        def staging_leak_check() -> None:
            return None

        @nucleus.check("staging.leak_check")
        def chk() -> CheckResult:
            raise RuntimeError("simulated failure for leak inspection")

        result = materialize_asset("staging.leak_check")
        rendered = " ".join(c.message.lower() for c in result.checks)
        assert "dagster" not in rendered
        assert "duckdb" not in rendered
        assert "polars" not in rendered
        assert "pyiceberg" not in rendered


# ---------------------------------------------------------------------------
# Edge cases — explicit v0.1 contracts the architect should defend
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Explicit v0.1 semantics for ambiguous cases."""

    def test_asset_with_no_registered_checks_has_empty_checks_tuple(self) -> None:
        @nucleus.asset("staging.no_checks")
        def staging_no_checks() -> None:
            return None

        result = materialize_asset("staging.no_checks")
        # Default factory tuple = empty; no allocation surprise.
        assert result.checks == ()

    def test_same_check_function_registered_twice_executes_twice(self) -> None:
        # The decorator appends to a per-asset_key list; a re-registered
        # check is a separate entry. v0.1 surfaces this honestly so users
        # see the duplicate; v0.5 may add a dedup pass once telemetry
        # shows the failure mode is real.
        def chk_dup() -> CheckResult:
            return CheckResult(passed=True, message="dup")

        nucleus.check("staging.dup")(chk_dup)
        nucleus.check("staging.dup")(chk_dup)

        results = contracts.run_checks_for_asset("staging.dup")
        assert len(results) == 2
        assert all(r.passed is True for r in results)
        assert all(r.message == "dup" for r in results)

    def test_check_returning_none_treated_as_failure_with_explicit_message(self) -> None:
        # Forgetting to `return` is a common Python mistake; surface a
        # clear failure rather than silently treat as passing.
        @nucleus.check("staging.none")
        def chk_forgot_return() -> None:
            _ = "no return statement"

        results = contracts.run_checks_for_asset("staging.none")
        assert len(results) == 1
        assert results[0].passed is False
        # Error message names the offending return type so the author
        # can locate the bug quickly.
        assert "NoneType" in results[0].message
        assert NucleusCheckExecutionError.error_code in results[0].message


# ---------------------------------------------------------------------------
# Translation-layer regression — NucleusError is a real subclass
# ---------------------------------------------------------------------------


class TestErrorClassRegression:
    """Direct construction + isinstance checks on NucleusCheckExecutionError."""

    def test_ne3007_is_coordination_error_subclass(self) -> None:
        # ADR-006 §1: NE3xxx is the L2 Coordination layer, which explicitly
        # enumerates "contracts" as one of its capabilities. The class
        # hierarchy inherits directly from NucleusError (the L2 convention
        # — no NucleusCoordinationError base class exists in v0.1).
        assert issubclass(NucleusCheckExecutionError, NucleusError)
        assert NucleusCheckExecutionError.error_code == "NE3007"

    def test_ne3007_is_not_an_engine_error(self) -> None:
        # Regression: Phase C originally placed this under NucleusEngineError
        # (NE2006). Verifier (Sonnet 4.6 max-thinking) caught the layer
        # misclassification per ADR-006 §1. This test fixes the chain
        # in place so a future refactor cannot silently re-engine-classify
        # without also tripping the ADR-006 §1 enumerated list.
        from nucleus.errors import NucleusEngineError

        assert not issubclass(NucleusCheckExecutionError, NucleusEngineError)
