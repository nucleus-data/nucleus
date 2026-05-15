"""Bronze layer asset — copy ``public.orders`` from Postgres into Iceberg.

The Postgres source is seeded by ``scripts/seed_postgres.py`` (or by the
``docker-entrypoint-initdb.d`` mount on first container boot). Bronze
preserves the source schema as-is; cleaning happens in silver.
"""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import POSTGRES_URL, WAREHOUSE_DIR


@nucleus.asset("bronze.orders")
def bronze_orders():
    """Land Postgres ``public.orders`` as a fresh Iceberg snapshot.

    ``write_disposition="replace"`` means each materialization rewrites the
    bronze snapshot from scratch — appropriate for a small demo. Production
    pipelines typically use ``"append"`` plus a watermark column.
    """
    return ctx.copy_from(
        POSTGRES_URL,
        table="public.orders",
        target="bronze.orders",
        warehouse_dir=WAREHOUSE_DIR,
        write_disposition="replace",
    )
