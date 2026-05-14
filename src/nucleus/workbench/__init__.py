"""Workbench (Experience layer) — FastAPI shell + static SPA bundle.

Promoted scaffold 2026-05-13 per ``docs/decisions/ADR-016-workbench-mvp.md``.
Nucleus architecture v4.1 §8.1 (Layer 4 Experience).

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from nucleus.workbench.app import create_app

__all__ = ["create_app"]
