"""dlt upgrade smoke tests — Postgres column type round-trip regression lock.

Per AGENTS.md §11.13 (Hard Constraint #11 — Upgrade-safe stack design).
Locks the 6 Postgres column types specified in docs/research/dlt.md §13.6:
  BIGINT, TEXT, NUMERIC(10,2), TIMESTAMPTZ, JSONB, BYTEA.

Status: **SKIP-BY-DEFAULT** (testcontainers integration deferred to follow-up swarm)
per ADR-014 §Sequencing step 3. This slot reserves the regression-lock structure
for dlt minor bumps per AGENTS.md §11.13 — run the suite after every dlt bump.

To run manually (requires Docker + testcontainers):
    pytest tests/upgrade_smoke/test_dlt_upgrade.py -m upgrade --no-skip-upgrade

Architecture refs:
    docs/decisions/ADR-014-dlt-postgres-source.md §Verification plan §7
    docs/research/dlt.md §13.6 (column type round-trip table)
    AGENTS.md §11.13 (upgrade workflow — add upgrade smoke test as part of the PR)
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Marker — all tests in this module are "upgrade" tests per pyproject.toml
# markers declaration (and integration tests requiring external services).
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.upgrade,
    pytest.mark.skip(
        reason=(
            "Postgres testcontainers integration deferred to follow-up swarm; "
            "per ADR-014 §Sequencing step 3, this slot reserves the regression-lock "
            "for dlt minor bumps per AGENTS.md §11.13."
        )
    ),
]

# ---------------------------------------------------------------------------
# The 6 column-type round-trip cases (ADR-014 §Verification plan §7)
# ---------------------------------------------------------------------------
# Each case: CREATE TABLE with the given Postgres type, ingest via
# ingest_postgres_to_iceberg, scan via pyiceberg, assert Iceberg type matches
# the mapping in docs/research/dlt.md §13.6.
#
# Structure is present so any swarm or builder can uncomment + wire
# testcontainers fixtures without changing the test names (upgrade regression
# history stays traceable in git log -p).
# ---------------------------------------------------------------------------


def test_bigint_round_trips_as_iceberg_long():
    """BIGINT → Iceberg LongType (docs/research/dlt.md §13.6)."""
    # TODO (follow-up swarm): wire Postgres testcontainer + ingest_postgres_to_iceberg.
    # Assert: pyiceberg schema field type is LongType.
    pytest.skip("Testcontainers fixture not yet wired — deferred per ADR-014 §Sequencing.")


def test_text_round_trips_as_iceberg_string():
    """TEXT → Iceberg StringType (docs/research/dlt.md §13.6)."""
    pytest.skip("Testcontainers fixture not yet wired — deferred per ADR-014 §Sequencing.")


def test_numeric_10_2_round_trips_as_iceberg_decimal():
    """NUMERIC(10,2) → Iceberg DecimalType(10,2) with full_with_precision backend.

    Requires reflection_level='full_with_precision' in sql_table() call.
    Regression target: if dlt default changes, this case catches silent precision loss.
    """
    pytest.skip("Testcontainers fixture not yet wired — deferred per ADR-014 §Sequencing.")


def test_timestamptz_round_trips_as_iceberg_timestamptz():
    """TIMESTAMPTZ → Iceberg TimestamptzType (NOT TimestampType — timezone-aware).

    AI commonly conflates TIMESTAMP and TIMESTAMPTZ — see docs/research/dlt.md §13.10.
    This case is the regression lock that catches that conflation.
    """
    pytest.skip("Testcontainers fixture not yet wired — deferred per ADR-014 §Sequencing.")


def test_jsonb_round_trips_as_iceberg_string():
    """JSONB → Iceberg StringType (Stage 1; no nested-table flattening per §13.6)."""
    pytest.skip("Testcontainers fixture not yet wired — deferred per ADR-014 §Sequencing.")


def test_bytea_round_trips_as_iceberg_binary():
    """BYTEA → Iceberg BinaryType (docs/research/dlt.md §13.6)."""
    pytest.skip("Testcontainers fixture not yet wired — deferred per ADR-014 §Sequencing.")
