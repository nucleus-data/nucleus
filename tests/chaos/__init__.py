"""Chaos test suite — pytest entry point for `scripts/release_e2e/run_chaos.py`.

Each Jn scenario in the runner has a corresponding ``test_jn_*`` pytest case
here for CI integration.  These tests are LONG-RUNNING (some take 30-90 s
because they spawn `nucleus` subprocesses and exercise real Iceberg writes);
they are marked ``@pytest.mark.chaos`` so they SKIP by default unless
``--run-chaos`` is passed or the ``RUN_CHAOS_TESTS=1`` env var is set.

Per AGENTS.md §11.8 chaos tests run on the release-gate path
(`scripts/release_e2e/e2e_full.py`) and via this pytest entry point.
"""
