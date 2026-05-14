"""Workbench API routers — wired into ``nucleus.workbench.app.create_app``.

Per ``docs/decisions/ADR-016-workbench-mvp.md`` §3 (Fork B, custom React SPA
+ FastAPI).  Each sub-module owns one slice of the ``/api/*`` surface.

``nucleus_architecture_v4.1.md`` §8.1 — Layer 4 Experience.
Workbench may import from sdk / ctx / intelligence / coordination / errors;
the reverse import direction is forbidden (scripts/check_layering.py enforces).

New endpoints for Editorial Hero v0.2:
- dashboard_router: GET /api/dashboard/summary
- schedules_router: GET /api/schedules, GET /api/schedules/{key}/preview
- catalog_router:   GET /api/catalog
- search_router:    GET /api/search

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from .assets import router as assets_router
from .catalog import router as catalog_router
from .chat import router as chat_router
from .dashboard import router as dashboard_router
from .query import router as query_router
from .runs import router as runs_router
from .schedules import router as schedules_router
from .search import router as search_router

__all__ = [
    "assets_router",
    "catalog_router",
    "chat_router",
    "dashboard_router",
    "query_router",
    "runs_router",
    "schedules_router",
    "search_router",
]
