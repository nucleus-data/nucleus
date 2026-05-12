"""The ctx SDK — Nucleus's public Python API (L4).

This module is the **only** stable surface for SDK users from v1.0 onward.
Per ``nucleus_architecture_v4.1.md`` §13.1, anything not exported here is
internal and may change without notice.

Typical use::

    import nucleus.ctx as nx

    ctx = nx.context()
    ctx.copy_from(source="postgres://...", table="public.orders", target="raw.orders")
    ctx.sql("SELECT * FROM {{ ref('raw.orders') }}", target="staging.orders")
    ctx.run("staging.orders")

Current status (v0.0.0, Pre-Heartbeat): the public surface is empty
except for re-exporting :class:`NucleusError` so users can write
``except nucleus.ctx.NucleusError as exc:``.

Planned content (lands progressively through Tier 0 → Tier 1):
    - ``context()`` lifecycle constructor
    - ``copy_from()`` ingestion helper
    - ``sql()`` SQL transformation (Jinja-aware)
    - ``read()`` lazy reader
    - ``run()`` materialization
    - ``lineage()`` / ``history()`` / ``schema()`` inspection
    - ``@asset`` decorator
    - ``NucleusError`` and all named subclasses

See ``nucleus_ctx_sdk_spec.md`` for the full specification.

Dependency direction (``engineering.md`` §3.1):
    ctx may import from intelligence, coordination, engines, physics, _internal,
    and the top-level ``nucleus.errors``.
    ctx must NEVER be imported by lower layers (cycle-prevention).
"""

from __future__ import annotations

from nucleus.errors import NucleusError

__all__ = [
    "NucleusError",
]
