"""Register every demo asset and check via import side-effects.

The Nucleus CLI walks ``assets/*.py`` and imports each module so the
``@nucleus.asset`` and ``@nucleus.check`` decorators register their bodies
in the in-process registry before ``nucleus run <key>`` executes.

We also pull in the sibling ``checks/`` package so check decorators land
in the same registration pass — see ``checks/__init__.py``.
"""

from __future__ import annotations

import checks  # noqa: F401  -- import for decorator side-effects

from . import (  # noqa: F401  -- import for decorator side-effects
    bronze_customers,
    bronze_orders,
    bronze_products,
    gold_customer_segments,
    gold_revenue_dashboard,
    silver_customer_ltv,
    silver_daily_revenue,
    silver_top_products,
)
