"""Raw-layer assets: copy operational sources into Iceberg (demo).

Uses ``ctx.copy_from`` (Beta) per ``docs/specs/nucleus_ctx_sdk_spec.md`` §5.3.
Postgres URLs: https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING
SQLite URIs: https://docs.python.org/3/library/sqlite3.html#sqlite3.connect
"""

from __future__ import annotations

from pathlib import Path

import nucleus
import nucleus.ctx as ctx

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = str(ROOT / "data" / "warehouse")
POSTGRES = "postgresql://nucleus:nucleus@127.0.0.1:5433/ecommerce_demo"
STRIPE_SQLITE = f"sqlite:///{(ROOT / 'data' / 'stripe_events.db').resolve().as_posix()}"


@nucleus.asset("raw.orders")
def raw_orders():
    """Load ``public.orders`` from the demo Postgres instance."""
    return ctx.copy_from(
        POSTGRES,
        table="public.orders",
        target="raw.orders",
        warehouse_dir=WAREHOUSE,
        write_disposition="replace",
    )


@nucleus.asset("raw.customers")
def raw_customers():
    """Load ``public.customers`` from the demo Postgres instance."""
    return ctx.copy_from(
        POSTGRES,
        table="public.customers",
        target="raw.customers",
        warehouse_dir=WAREHOUSE,
        write_disposition="replace",
    )


@nucleus.asset("raw.stripe_events")
def raw_stripe_events():
    """Load SQLite ``stripe_events`` (synthetic webhook log)."""
    return ctx.copy_from(
        STRIPE_SQLITE,
        table="stripe_events",
        target="raw.stripe_events",
        warehouse_dir=WAREHOUSE,
        write_disposition="replace",
    )
