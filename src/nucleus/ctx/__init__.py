"""The ctx SDK — Nucleus's public Python API (L4).

This module is the **only** stable surface for SDK users from v1.0 onward.
Per ``docs/specs/nucleus_architecture_v4.1.md`` §13.1, anything not exported here is
internal and may change without notice.

Typical use::

    import nucleus.ctx as ctx

    rows = ctx.copy_from(
        "sqlite:///./data/orders.db",
        table="orders",
        target="bronze.orders",
        warehouse_dir="./warehouse",
    )

    df = ctx.sql(
        "SELECT * FROM {{ ref('bronze.orders') }}",
        warehouse_dir="./warehouse",
    ).collect()

    orders = ctx.read("bronze.orders", warehouse_dir="./warehouse").collect()

Current status (v0.1 stabilization):
    - ``copy_from()``    Beta    unified ingest dispatcher (sqlite/postgres/mysql)
    - ``sql()``          Beta    Jinja-aware SQL execution against the warehouse
    - ``read()``         Beta    lazy reader of materialized assets
    - ``ingest_sqlite_to_iceberg()``     legacy direct-ingest helper
    - ``ingest_postgres_to_iceberg()``   legacy direct-ingest helper
    - ``ingest_mysql_to_iceberg()``      legacy direct-ingest helper
    - ``NucleusError``   Stable  base exception for all SDK failures

Deferred to v0.2+ (per ADR-013 + Phase D scope):
    - ``ctx.write()``    use asset body return for now
    - ``ctx.log()``      use stdlib ``logging`` module for now
    - ``ctx.params()``   use CLI / config for now

See ``docs/specs/nucleus_ctx_sdk_spec.md`` for the full specification and the
Stability tier matrix (ADR-005).

Dependency direction (``docs/specs/nucleus_architecture_v4.1.md`` §5.5):
    ctx may import from intelligence, coordination, engines, physics, _internal,
    and the top-level ``nucleus.errors``.
    ctx must NEVER be imported by lower layers (cycle-prevention).
"""

from __future__ import annotations

from nucleus.ctx._dispatch import copy_from
from nucleus.ctx.copy_from import ingest_sqlite_to_iceberg
from nucleus.ctx.copy_from_filesystem import ingest_filesystem_to_iceberg
from nucleus.ctx.copy_from_gcs import ingest_gcs_to_iceberg
from nucleus.ctx.copy_from_mysql import ingest_mysql_to_iceberg
from nucleus.ctx.copy_from_postgres import ingest_postgres_to_iceberg
from nucleus.ctx.copy_from_s3 import ingest_s3_to_iceberg
from nucleus.ctx.copy_from_snowflake import ingest_snowflake_to_iceberg
from nucleus.ctx.read import read
from nucleus.ctx.sql import sql
from nucleus.errors import NucleusError

__all__ = [
    "NucleusError",
    "copy_from",
    "ingest_filesystem_to_iceberg",
    "ingest_gcs_to_iceberg",
    "ingest_mysql_to_iceberg",
    "ingest_postgres_to_iceberg",
    "ingest_s3_to_iceberg",
    "ingest_snowflake_to_iceberg",
    "ingest_sqlite_to_iceberg",
    "read",
    "sql",
]
