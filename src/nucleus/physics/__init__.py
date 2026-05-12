"""Physics layer — immutable open standards (L0).

Adapters and helpers for the unchanging substrate that Nucleus is built on:

    - Apache Arrow      (zero-copy columnar in-memory format)
    - Apache Iceberg    (open table format)
    - Apache Parquet    (file storage)
    - FileIO            (local / S3 / GCS / Azure)

Per ``AGENTS.md`` Hard Constraint #5, this layer **delegates** atomic
commits to the configured Iceberg catalog; it does NOT implement its own
commit service.

Dependency direction (``engineering.md`` §3.1):
    physics may import from _internal only.
    physics must NEVER import from engines, coordination, intelligence, ctx, or cli.

This package is currently empty; modules land here during Tier 0 Heartbeat
(starting with the Iceberg/PyArrow write helpers).
"""

from __future__ import annotations
