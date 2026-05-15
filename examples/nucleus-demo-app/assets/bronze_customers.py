"""Bronze layer asset — copy ``public.customers`` from Postgres into Iceberg."""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import POSTGRES_URL, WAREHOUSE_DIR


@nucleus.asset("bronze.customers")
def bronze_customers():
    """Land Postgres ``public.customers`` as a fresh Iceberg snapshot."""
    return ctx.copy_from(
        POSTGRES_URL,
        table="public.customers",
        target="bronze.customers",
        warehouse_dir=WAREHOUSE_DIR,
        write_disposition="replace",
    )
