"""FastAPI application factory for the Workbench API.

Per ``docs/decisions/ADR-016-workbench-mvp.md`` Fork B (React SPA + FastAPI).
``nucleus_architecture_v4.1.md`` §8.1 — Layer 4 Experience.

Routes:
    /api/health            — health check (always available)
    /api/version           — version info
    /api/assets            — list registered assets
    /api/assets/{key}      — single asset detail
    /api/runs              — run history (ring-buffer, latest-first)
    /api/runs/{id}/log     — SSE log stream for a run
    /api/query             — POST: execute SQL via ctx.sql + DuckDB
    /api/chat              — POST: proxy to Nucleus AI Copilot (ADR-015)
    /                      — static SPA (React build or CDN fallback)

CORS is allowed for the Vite dev server (localhost:5173) so ``npm run dev``
works against the FastAPI backend on :8000 / :8765 without a proxy.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from pathlib import Path

# Docs: https://fastapi.tiangolo.com/tutorial/first-steps/
# Docs: https://fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Docs: https://fastapi.tiangolo.com/tutorial/static-files/
from fastapi.staticfiles import StaticFiles

from nucleus import __version__ as nucleus_version

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# Dev origins: Vite default port + localhost variants.
_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://localhost:8765",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8765",
]


def create_app() -> FastAPI:
    """Return a configured FastAPI app (API routers + static bundle mount)."""
    app = FastAPI(
        title="Nucleus Workbench",
        version="0.2.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS — allow Vite dev server to call the API without a proxy.
    # Docs: https://fastapi.tiangolo.com/tutorial/cors/
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Built-in health / version endpoints (unchanged from scaffold).
    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": nucleus_version}

    @app.get("/api/version", tags=["system"])
    def version_info() -> dict[str, str]:
        return {
            "nucleus": nucleus_version,
            "workbench_api": "v0.2-scaffold",
        }

    # Wire the API routers (Editorial Hero v0.2 — all endpoints).
    from nucleus.workbench.api import (
        assets_router,
        catalog_router,
        chat_router,
        dashboard_router,
        query_router,
        runs_router,
        schedules_router,
        search_router,
    )

    app.include_router(assets_router)
    app.include_router(runs_router)
    app.include_router(query_router)
    app.include_router(chat_router)
    app.include_router(dashboard_router)
    app.include_router(schedules_router)
    app.include_router(catalog_router)
    app.include_router(search_router)

    _ensure_static_dir()
    app.mount(
        "/",
        StaticFiles(directory=str(_STATIC_DIR), html=True),
        name="static",
    )
    return app


def _ensure_static_dir() -> None:
    """Ensure the static directory exists (empty except ``.gitkeep`` pre-build)."""
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
