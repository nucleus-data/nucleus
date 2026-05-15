"""Coordination layer — orchestration, lineage, contracts (L2).

This is where most of the cleverness lives. It wraps Dagster (hidden
from users) and bridges the SDK to the engines.

Modules (target sizes per ``docs/architecture/C4_container.md`` §9):

    - asset_materialization.py     thin Dagster wrapper             ~500 LOC  (PROMOTED)
    - error_translation.py         Dagster exc → NucleusError        ~300 LOC  (PROMOTED)
    - sql_resolver.py              ctx.sql Jinja resolver            ~200 LOC  (PROMOTED)
    - lineage.py                   asset-level lineage capture       ~400 LOC  (pending)
    - contracts.py                 pre-/post-materialize schema chk  ~600 LOC  (pending)

**v4.1 §6.4 (Error Translation Discipline)**: This is the ONLY layer
permitted to ``import dagster``. The ``scripts/dagster_leak_check.py`` CI
guard enforces this.

Dependency direction (``engineering.md`` §3.1):
    coordination may import from engines, physics, _internal.
    coordination must NEVER import from intelligence, ctx, or cli.
"""

from __future__ import annotations

# Re-export the Asset Materialization Adapter entry point so callers can
# write ``from nucleus.coordination import materialize_asset`` without
# reaching into the submodule. The function itself is Beta-tier per
# ADR-013 §3 and is an *internal* helper — the public surface remains
# :func:`nucleus.materialize` in :mod:`nucleus.sdk.materialize`.
# Stability: Beta.
from nucleus.coordination.asset_materialization import materialize_asset

# Mini-scheduler daemon (ADR-017 v0.2.1).
# Stability: Beta.
from nucleus.coordination.daemon import (
    DaemonStatus,
    get_daemon_status,
    start_daemon,
    stop_daemon,
    trigger_asset,
)

# Run ledger — durable NDJSON persistence (ADR-025 §P0-2).
# Stability: Beta.
from nucleus.coordination.run_ledger import RunLedger, RunRecord

__all__ = [
    "DaemonStatus",
    "RunLedger",
    "RunRecord",
    "get_daemon_status",
    "materialize_asset",
    "start_daemon",
    "stop_daemon",
    "trigger_asset",
]
