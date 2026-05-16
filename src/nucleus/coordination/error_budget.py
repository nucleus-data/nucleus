"""Error-budget SLO definitions per operation type.

Per ``docs/specs/nucleus_architecture_v4.1.md`` §6.2 (AMA) and
``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-5.

These are v0.2 *definitions* only — the enforcement layer (OpenTelemetry
budget checks + alerting) lands at v0.3+ per ADR-024 §Consequences.

Budgets define per-operation ``target_p95_ms`` / ``target_p95_s`` and
``max_failure_rate`` thresholds.  ``check_against_budget`` returns True when
the observed metrics are within the budget.

OTEL tracking is v0.3+ — just definitions now.

# Stability: Beta (v0.2)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SLO table
# ---------------------------------------------------------------------------
# Key: operation name (string used in OTEL span names)
# Value: dict with either "target_p95_ms" or "target_p95_s" (never both),
#        plus "max_failure_rate" (0.0–1.0 fraction).
#
# Times are the *wall-clock* budget for the p95 of that operation category.
# Failure rates are the maximum fraction of ops that may fail (raise any
# NucleusError) across a 5-minute window.
#
# Per ADR-024 P0-5 spec.

ERROR_BUDGETS: dict[str, dict[str, float]] = {
    # ``nucleus up`` boot time — from CLI entry-point to "ready" log line.
    "boot": {
        "target_p95_ms": 1500,
        "max_failure_rate": 0.001,
    },
    # Materialise an asset that returns an empty DataFrame (schema-only write).
    "materialize_empty": {
        "target_p95_ms": 1000,
        "max_failure_rate": 0.001,
    },
    # Materialise a 1 GB asset (DuckDB read + Iceberg append).
    "materialize_1gb": {
        "target_p95_s": 30,
        "max_failure_rate": 0.01,
    },
    # ``ctx.sql`` / ``nucleus query`` on a 100 MB Iceberg table.
    "query_100mb": {
        "target_p95_ms": 500,
        "max_failure_rate": 0.001,
    },
    # ``nucleus ingest`` — 1 million rows from Postgres (network-bound).
    "ingest_postgres_1m_rows": {
        "target_p95_s": 300,
        "max_failure_rate": 0.01,
    },
    # Schedule-resolution latency (daemon tick → first matching asset).
    "schedule_resolution": {
        "target_p95_ms": 500,
        "max_failure_rate": 0.0001,
    },
}


# ---------------------------------------------------------------------------
# Accessor helpers
# ---------------------------------------------------------------------------


def get_budget(op: str) -> dict[str, float]:
    """Return the SLO budget dict for *op*.

    Args:
        op: One of the keys in :data:`ERROR_BUDGETS`.

    Returns:
        A dict with ``target_p95_ms`` or ``target_p95_s``
        and ``max_failure_rate``.

    Raises:
        KeyError: *op* is not a known operation name.
    """
    return ERROR_BUDGETS[op]


def check_against_budget(op: str, p95_ms: float, failure_rate: float) -> bool:
    """Return True if the observed metrics are within the SLO budget for *op*.

    Normalises the budget's ``target_p95_s`` to milliseconds before comparison
    so callers always pass ``p95_ms``.

    Args:
        op: Operation name (key in :data:`ERROR_BUDGETS`).
        p95_ms: Observed 95th-percentile latency in **milliseconds**.
        failure_rate: Observed failure rate as a fraction (0.0–1.0).

    Returns:
        True when both ``p95_ms ≤ budget_p95_ms`` and
        ``failure_rate ≤ max_failure_rate``.

    Raises:
        KeyError: *op* is not a known operation name.
    """
    budget = get_budget(op)

    if "target_p95_ms" in budget:
        budget_p95_ms = budget["target_p95_ms"]
    else:
        budget_p95_ms = budget["target_p95_s"] * 1000.0

    latency_ok = p95_ms <= budget_p95_ms
    failure_ok = failure_rate <= budget["max_failure_rate"]
    return latency_ok and failure_ok


__all__ = ["ERROR_BUDGETS", "check_against_budget", "get_budget"]
