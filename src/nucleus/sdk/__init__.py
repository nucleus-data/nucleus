"""Public Nucleus SDK package — the developer-facing decorators + entry points.

Per ``docs/specs/nucleus_architecture_v4.1.md`` §13.2 (Surface Summary) +
``docs/decisions/ADR-013-ctx-materialize-api.md`` (the materialize API)
+ ``docs/specs/nucleus_ctx_sdk_spec.md`` §2 + §12 (frozen surface) +
``docs/specs/nucleus_asset_model_spec.md`` §3 + §10 (asset + check semantics).

What lives here vs. ``nucleus.ctx``
-----------------------------------
- :mod:`nucleus.sdk` — module-level declarators (decorators) and
  module-level entry points. Imported by the user's project module
  (e.g. ``import nucleus`` and write ``@nucleus.asset(...)``,
  ``@nucleus.check(...)``, ``nucleus.materialize(...)``).
- :mod:`nucleus.ctx` — the per-asset runtime object passed by the
  Asset Materialization Adapter to every asset body. Constructed by
  the runtime, never by user code (``docs/specs/nucleus_ctx_sdk_spec.md`` §3).

Together they form the v0.1 SDK surface; both publish the same
stability tier (Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0 per
ADR-005 §2 — ``MaterializationResult`` inherits via ADR-013 §3).

Re-exports
----------
The public symbols below are also re-exported from
:mod:`nucleus` so users write ``nucleus.asset`` (not
``nucleus.sdk.asset``) per ``docs/specs/nucleus_ctx_sdk_spec.md`` §1+§12.
``nucleus/__init__.py`` aliases each name and adds the
``# Stability:`` markers required by
``scripts/check_api_stability.py``.

Layering (per ``docs/conventions/engineering.md`` §3.1)
-------------------------------------------------------
- :mod:`nucleus.sdk` may import from :mod:`nucleus.errors`,
  :mod:`nucleus._internal`, :mod:`nucleus.coordination`,
  :mod:`nucleus.engines`, :mod:`nucleus.physics` (downward only).
- :mod:`nucleus.sdk` MUST NOT import :mod:`dagster` directly — the
  ``scripts/dagster_leak_check.py`` CI guard enforces this. AMA
  delegation (when wired) goes through
  :mod:`nucleus.coordination.asset_materialization` which is the only
  layer permitted to touch Dagster.
"""

from __future__ import annotations

from nucleus.sdk.decorators import asset, check
from nucleus.sdk.materialize import materialize
from nucleus.sdk.results import AssetRef, CheckResult, MaterializationResult

__all__ = [
    "AssetRef",
    "CheckResult",
    "MaterializationResult",
    "asset",
    "check",
    "materialize",
]
