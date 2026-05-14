"""dlt + pymysql upgrade smoke tests — MySQL column type round-trip regression lock.

Per AGENTS.md §11.13 (Hard Constraint #11 — Upgrade-safe stack design).
Mirrors ``tests/upgrade_smoke/test_dlt_upgrade.py`` for the MySQL co-default
landed 2026-05-14 per ADR-014 §"MySQL parity".

Two purposes:

1. **API surface lock** (always-runnable): Verify that the dlt API surface we
   wrap (``dlt.sources.sql_database.sql_table``, ``dlt.pipeline``) exists and
   accepts the kwargs the Nucleus MySQL helper uses. Catches API churn on a
   dlt minor bump before the integration test would fire.
2. **Column-type round-trip** (testcontainers, SKIP-BY-DEFAULT): Locks the 6
   common MySQL types: BIGINT, TEXT, DECIMAL(10,2), DATETIME(6), JSON, BLOB.
   Reserved for a follow-up swarm that wires the MySQL testcontainer.

To run manually (requires Docker + testcontainers):
    pytest tests/upgrade_smoke/test_dlt_mysql.py -m upgrade --no-skip-upgrade

Architecture refs:
    docs/decisions/ADR-014-dlt-postgres-source.md §"MySQL parity"
    docs/research/dlt.md §13.6 (column type round-trip table — Postgres analog)
    AGENTS.md §11.13 (upgrade workflow — add upgrade smoke test as part of the PR)
"""

from __future__ import annotations

import pytest

# Skip the import-heavy block gracefully if dlt / pymysql aren't installed in
# this environment. CI installs them; local lightweight runs may not. This
# matches the ``pytest.importorskip`` pattern in tests/upgrade_smoke/test_litellm.py.
dlt = pytest.importorskip("dlt", reason="dlt not installed — skip upgrade smoke")
pymysql = pytest.importorskip("pymysql", reason="pymysql not installed — skip upgrade smoke")


# ---------------------------------------------------------------------------
# Pin assertions — lock the version we tested against
# ---------------------------------------------------------------------------


def test_dlt_pinned_version_matches_pyproject():
    """dlt installed version must match the pin in pyproject.toml (==1.26.0).

    Loosely tied via the major.minor so patch bumps don't break this; a
    minor bump (1.26 → 1.27) requires reading the dlt changelog per
    AGENTS.md §11.13 and updating this assertion.
    """
    parts = dlt.__version__.split(".")
    assert parts[0] == "1", f"dlt major version drift: got {dlt.__version__}, expected 1.26.x"
    assert parts[1] == "26", (
        f"dlt minor version drift: got {dlt.__version__}, expected 1.26.x. "
        "Read https://github.com/dlt-hub/dlt/releases and update the pin per AGENTS.md §11.13."
    )


def test_pymysql_pinned_version_matches_pyproject():
    """pymysql installed version must remain in the 1.x major line.

    The exact patch/minor is governed by ``pyproject.toml`` (pinned 1.1.1 at
    write time). Major version drift requires an ADR per AGENTS.md §11.13;
    minor drift is an install-time concern caught by ``scripts/check_pinning.py``
    at PR review, not at runtime. This smoke test guards only the major boundary
    so a stale local venv (1.x.y mismatched against the pin) does not generate
    spurious failures while still catching ``pymysql>=2.0`` regressions.

    NEEDS VERIFICATION (AGENTS.md §11.12): pyproject pin is 1.1.1 but local
    venvs may have any 1.x; see `scripts/check_pinning.py` for the install
    boundary that does enforce exact pin.
    """
    parts = pymysql.__version__.split(".")
    assert parts[0] == "1", (
        f"pymysql major version drift: got {pymysql.__version__}, expected 1.x. "
        "Read https://github.com/PyMySQL/PyMySQL/releases and the dlt sql_database "
        "docs (https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database) "
        "before updating the pin per AGENTS.md §11.13."
    )


# ---------------------------------------------------------------------------
# dlt API surface lock — the wrapped APIs we use
# Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
# ---------------------------------------------------------------------------


def test_dlt_sql_database_sql_table_exists():
    """``dlt.sources.sql_database.sql_table`` is the wrapped factory; must exist.

    If this fails, dlt has renamed/moved the function — read the changelog
    and update ``src/nucleus/ctx/copy_from_mysql.py`` before merging the bump.
    """
    from dlt.sources.sql_database import sql_table

    assert callable(sql_table), (
        "dlt.sources.sql_database.sql_table is not callable; API surface drift detected"
    )


def test_dlt_pipeline_factory_exists():
    """``dlt.pipeline`` is the pipeline factory; must remain callable on the dlt root."""
    assert hasattr(dlt, "pipeline"), "dlt.pipeline missing on the top-level module"
    assert callable(dlt.pipeline), "dlt.pipeline is no longer callable"


def test_pymysql_err_module_present():
    """pymysql.err is the canonical exception module; needed by translator.

    Docs: https://pymysql.readthedocs.io/en/latest/modules/err.html
    """
    err_mod = getattr(pymysql, "err", None)
    assert err_mod is not None, "pymysql.err submodule missing — translator mapping at risk"
    # OperationalError is the class we map for code 1045 / 2003 / 1049.
    assert hasattr(err_mod, "OperationalError"), (
        "pymysql.err.OperationalError missing — error translation map needs review"
    )


# ---------------------------------------------------------------------------
# Column-type round-trip cases (SKIP-BY-DEFAULT until testcontainer fixtures
# land for MySQL — same pattern as tests/upgrade_smoke/test_dlt_upgrade.py).
# ---------------------------------------------------------------------------

_TESTCONTAINER_SKIP_REASON = (
    "MySQL testcontainer fixture not yet wired — deferred per ADR-014 "
    "§'MySQL parity' sequencing; structure preserved so a follow-up swarm "
    "can wire the fixture without changing test names (regression history "
    "stays traceable in git log -p)."
)


@pytest.mark.upgrade
def test_bigint_round_trips_as_iceberg_long():
    """BIGINT → Iceberg LongType (parity with Postgres BIGINT case)."""
    pytest.skip(_TESTCONTAINER_SKIP_REASON)


@pytest.mark.upgrade
def test_text_round_trips_as_iceberg_string():
    """TEXT → Iceberg StringType (parity with Postgres TEXT case)."""
    pytest.skip(_TESTCONTAINER_SKIP_REASON)


@pytest.mark.upgrade
def test_decimal_10_2_round_trips_as_iceberg_decimal():
    """DECIMAL(10,2) → Iceberg DecimalType(10,2) with full_with_precision backend.

    Requires reflection_level='full_with_precision' in sql_table() call.
    Regression target: if dlt default changes, this case catches silent precision loss.
    """
    pytest.skip(_TESTCONTAINER_SKIP_REASON)


@pytest.mark.upgrade
def test_datetime6_round_trips_as_iceberg_timestamp():
    """DATETIME(6) → Iceberg TimestampType (microsecond precision).

    MySQL DATETIME is naive (no timezone). TIMESTAMP would map to TimestamptzType;
    this case locks the naive-vs-aware distinction for upgrade-time review.
    """
    pytest.skip(_TESTCONTAINER_SKIP_REASON)


@pytest.mark.upgrade
def test_json_round_trips_as_iceberg_string():
    """JSON → Iceberg StringType (parity with Postgres JSONB case; no nested-table flattening)."""
    pytest.skip(_TESTCONTAINER_SKIP_REASON)


@pytest.mark.upgrade
def test_blob_round_trips_as_iceberg_binary():
    """BLOB → Iceberg BinaryType (parity with Postgres BYTEA case)."""
    pytest.skip(_TESTCONTAINER_SKIP_REASON)
