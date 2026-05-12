"""Engines layer — composable compute (L1).

Wraps the SQL / DataFrame engines that do the actual work:

    - DuckDB        SQL execution + Iceberg reads
    - Polars        DataFrame transformations
    - DataFusion    alternative SQL engine (smoke target v0.1, real impl v0.5+)
    - Daft          multimodal / distributed (post v0.5)

Each engine implements the :class:`Engine` Protocol so adapters are
swap-able (``AGENTS.md`` Constraint #9, "Composability by Constitution").

Dependency direction (``engineering.md`` §3.1):
    engines may import from physics, _internal.
    engines must NEVER import from coordination, intelligence, ctx, or cli.
    Cross-engine imports are forbidden (``engineering.md`` §3.2).

This package is currently empty; modules land here during Tier 0 Heartbeat
(starting with ``duckdb_engine.py`` and ``polars_engine.py``).
"""

from __future__ import annotations
