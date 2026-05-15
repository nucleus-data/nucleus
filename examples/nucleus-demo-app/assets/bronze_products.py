"""Bronze layer asset — copy ``public.products`` from Postgres into Iceberg."""

from __future__ import annotations

import nucleus
import nucleus.ctx as ctx

from assets._common import POSTGRES_URL, WAREHOUSE_DIR


@nucleus.asset("bronze.products")
def bronze_products():
    """Land Postgres ``public.products`` as a fresh Iceberg snapshot."""
    return ctx.copy_from(
        POSTGRES_URL,
        table="public.products",
        target="bronze.products",
        warehouse_dir=WAREHOUSE_DIR,
        write_disposition="replace",
    )
