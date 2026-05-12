"""Coordination layer — orchestration, lineage, contracts (L2).

This is where most of the cleverness lives. It wraps Dagster (hidden
from users) and bridges the SDK to the engines.

Planned modules (target sizes per ``docs/architecture/C4_container.md`` §9):

    - asset_materialization.py     thin Dagster wrapper             ~500 LOC
    - error_translation.py         Dagster exc → NucleusError        ~300 LOC
    - lineage.py                   asset-level lineage capture       ~400 LOC
    - contracts.py                 pre-/post-materialize schema chk  ~600 LOC

**v4.1 §6.4 (Error Translation Discipline)**: This is the ONLY layer
permitted to ``import dagster``. The ``scripts/dagster_leak_check.py`` CI
guard enforces this.

Dependency direction (``engineering.md`` §3.1):
    coordination may import from engines, physics, _internal.
    coordination must NEVER import from intelligence, ctx, or cli.

This package is currently empty; PoC #1 produces the first content
(error translation layer). See ``poc/p1_error_translation/README.md``.
"""

from __future__ import annotations
