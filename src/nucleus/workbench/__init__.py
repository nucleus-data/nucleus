"""Workbench (Experience layer) — FastAPI shell + static SPA bundle.

Promoted scaffold 2026-05-13 per ``docs/decisions/ADR-016-workbench-mvp.md``.
Nucleus architecture v4.1 §8.1 (Layer 4 Experience).

Lazy import discipline (perf doc §10 #4 + Worker B2 audit 2026-05-15)
---------------------------------------------------------------------
``create_app`` is exposed via PEP 562 ``__getattr__`` so the heavy
``fastapi`` import chain only fires when the symbol is actually
accessed (``nucleus workbench up`` calls ``uvicorn.run("...:create_app",
factory=True)`` which imports ``nucleus.workbench.app:create_app`` on
demand). Loading ``nucleus.workbench`` itself MUST stay sub-1 ms so
``nucleus --help`` and ``nucleus --version`` boot under the 500 ms
perf-doc target — otherwise FastAPI + Starlette + pydantic-core would
all land at boot via the indirect ``from nucleus.workbench.app import
create_app`` re-export.

PEP 562 quirk
-------------
``__getattr__`` only fires when the requested attribute is NOT already
defined on the module object. We therefore intentionally do NOT define
a ``def create_app`` stub at runtime — type-checkers consume the
``TYPE_CHECKING`` annotation block instead. Adding a stub function
here would shadow the lazy hook and re-eager the import.

Docs: PEP 562 — https://peps.python.org/pep-0562/

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Type-only re-export so ``nucleus.workbench.create_app`` keeps a
    # precise signature in editors / mypy without forcing FastAPI at
    # runtime. Per PEP 484 + PEP 562 the ``if TYPE_CHECKING`` body never
    # executes at import time.
    from nucleus.workbench.app import create_app as create_app

__all__ = ["create_app"]


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute hook — defers ``fastapi`` import to first access.

    Any access of ``nucleus.workbench.create_app`` (or import via
    ``from nucleus.workbench import create_app``) lands here on first
    touch; we then import the heavy ``nucleus.workbench.app`` module
    and return its ``create_app`` symbol. Python caches the resolved
    attribute on the module object so subsequent accesses are dict
    lookups and never re-enter this hook.
    """
    if name == "create_app":
        from nucleus.workbench.app import create_app as _create_app

        return _create_app
    raise AttributeError(f"module 'nucleus.workbench' has no attribute {name!r}")
