"""Tests for :mod:`nucleus.coordination.error_budget`.

Validates the SLO definitions per
``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-5.

Coverage:
    EB1  All expected operation keys are present.
    EB2  get_budget returns correct dict for known operation.
    EB3  get_budget raises KeyError for unknown operation.
    EB4  check_against_budget returns True when within SLO.
    EB5  check_against_budget returns False when latency exceeds budget.
    EB6  check_against_budget returns False when failure_rate exceeds budget.
    EB7  check_against_budget normalises target_p95_s to ms correctly.
"""

from __future__ import annotations

import pytest

from nucleus.coordination.error_budget import (
    ERROR_BUDGETS,
    check_against_budget,
    get_budget,
)

EXPECTED_OPS = {
    "boot",
    "materialize_empty",
    "materialize_1gb",
    "query_100mb",
    "ingest_postgres_1m_rows",
    "schedule_resolution",
}


# ---------------------------------------------------------------------------
# EB1: All expected keys present
# ---------------------------------------------------------------------------


def test_all_expected_operations_present() -> None:
    """EB1: ERROR_BUDGETS contains all six required operation keys."""
    for op in EXPECTED_OPS:
        assert op in ERROR_BUDGETS, f"Missing operation key: {op!r}"


def test_all_budgets_have_max_failure_rate() -> None:
    """EB1: Every budget entry has a max_failure_rate field."""
    for op, budget in ERROR_BUDGETS.items():
        assert "max_failure_rate" in budget, f"Missing max_failure_rate for {op!r}"


def test_all_budgets_have_latency_target() -> None:
    """EB1: Every budget entry has either target_p95_ms or target_p95_s."""
    for op, budget in ERROR_BUDGETS.items():
        has_ms = "target_p95_ms" in budget
        has_s = "target_p95_s" in budget
        assert has_ms or has_s, f"Missing latency target for {op!r}"
        assert not (has_ms and has_s), f"Both target_p95_ms and target_p95_s set for {op!r}"


# ---------------------------------------------------------------------------
# EB2: get_budget returns correct dict
# ---------------------------------------------------------------------------


def test_get_budget_boot() -> None:
    """EB2: Boot budget has target_p95_ms=1500."""
    budget = get_budget("boot")
    assert budget["target_p95_ms"] == 1500
    assert budget["max_failure_rate"] == 0.001


def test_get_budget_materialize_1gb() -> None:
    """EB2: 1 GB materialize budget has target_p95_s=30."""
    budget = get_budget("materialize_1gb")
    assert budget["target_p95_s"] == 30
    assert budget["max_failure_rate"] == 0.01


# ---------------------------------------------------------------------------
# EB3: KeyError for unknown operation
# ---------------------------------------------------------------------------


def test_get_budget_unknown_raises_keyerror() -> None:
    """EB3: get_budget raises KeyError for unregistered operations."""
    with pytest.raises(KeyError):
        get_budget("nonexistent_operation")


# ---------------------------------------------------------------------------
# EB4: check_against_budget returns True within SLO
# ---------------------------------------------------------------------------


def test_check_within_budget_returns_true() -> None:
    """EB4: check_against_budget returns True when both metrics are within budget."""
    # boot: target_p95_ms=1500, max_failure_rate=0.001
    assert check_against_budget("boot", p95_ms=1000, failure_rate=0.0005) is True


def test_check_within_budget_exactly_at_limit() -> None:
    """EB4: check_against_budget returns True when exactly at the budget limit."""
    assert check_against_budget("boot", p95_ms=1500, failure_rate=0.001) is True


# ---------------------------------------------------------------------------
# EB5: Latency violation
# ---------------------------------------------------------------------------


def test_check_latency_violation_returns_false() -> None:
    """EB5: check_against_budget returns False when p95_ms exceeds target."""
    # boot: target_p95_ms=1500
    assert check_against_budget("boot", p95_ms=1501, failure_rate=0.0) is False


# ---------------------------------------------------------------------------
# EB6: Failure rate violation
# ---------------------------------------------------------------------------


def test_check_failure_rate_violation_returns_false() -> None:
    """EB6: check_against_budget returns False when failure_rate exceeds budget."""
    # boot: max_failure_rate=0.001
    assert check_against_budget("boot", p95_ms=500, failure_rate=0.002) is False


# ---------------------------------------------------------------------------
# EB7: target_p95_s normalised to ms
# ---------------------------------------------------------------------------


def test_check_normalises_target_p95_s_to_ms() -> None:
    """EB7: target_p95_s is correctly converted to ms for comparison."""
    # materialize_1gb: target_p95_s=30 → 30_000 ms
    assert check_against_budget("materialize_1gb", p95_ms=29_000, failure_rate=0.0) is True
    assert check_against_budget("materialize_1gb", p95_ms=31_000, failure_rate=0.0) is False
