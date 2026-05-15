"""Quality checks for the Nucleus demo project.

Each check is a ``@nucleus.check`` body bound to a single asset; the AMA
runs them after the asset commits and aggregates the results into the
materialization record (``MaterializationResult.checks``).

Importing this package triggers all decorators, which registers the
checks with the in-process registry. ``assets/__init__.py`` imports
``checks`` for exactly this reason.
"""

from __future__ import annotations

from . import (  # noqa: F401  -- import for decorator side-effects
    customer_id_unique,
    orders_freshness,
    revenue_non_negative,
)
