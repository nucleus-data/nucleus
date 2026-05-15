"""GET /api/assets  +  GET /api/assets/{key} — asset registry endpoints.

Reads the in-process ``@nucleus.asset`` registry via
``nucleus.sdk.decorators.get_asset`` / ``_registered_keys`` and surfaces
the metadata as JSON for the Workbench Asset Explorer page.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience).
ADR-016 §3 — Fork B API surface.

Vocabulary: uses "asset" / "materialization" / "snapshot" / "check" per
AGENTS.md §7. No banned terms or orchestrator class names in API responses.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import APIRouter, HTTPException

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError
from nucleus.sdk.decorators import _registered_keys, get_asset, get_checks

router = APIRouter(prefix="/api/assets", tags=["assets"])


def _asset_to_dict(key: str) -> dict[str, Any]:
    """Serialize one registered asset to a JSON-safe dict."""
    defn = get_asset(key)
    if defn is None:
        return {"key": key}
    checks = get_checks(key)
    return {
        "key": defn.key,
        "deps": list(defn.deps),
        "schedule": defn.schedule,
        "compute": defn.compute,
        "has_contract": defn.contract is not None,
        "checks": [{"severity": c.severity, "fn_name": c.fn.__name__} for c in checks],
    }


@router.get("")
def list_assets() -> Any:
    """Return all registered assets as a JSON array.

    Each item contains: key, deps, schedule (cron or null), compute,
    has_contract (bool), checks (list of {severity, fn_name}).

    Per ADR-016 §3: asset registry is in-process; data reflects the
    current imported module state, not a persisted catalog.
    """
    try:
        keys = _registered_keys()
        return [_asset_to_dict(k) for k in keys]
    except NucleusError as err:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,
                "user_message": err.user_message,
                "fix_hint": err.fix_hint,
            },  # type: ignore[attr-defined]
        ) from err
    except Exception as exc:
        err = translate(exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,
                "user_message": err.user_message,
                "fix_hint": err.fix_hint,
            },  # type: ignore[attr-defined]
        ) from err


@router.get("/{asset_key:path}")
def get_asset_detail(asset_key: str) -> Any:
    """Return detailed metadata for a single asset.

    Returns 404 when the key is not in the in-process registry.
    """
    try:
        defn = get_asset(asset_key)
        if defn is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "NE3001",
                    "user_message": f"Asset '{asset_key}' is not registered.",
                    "fix_hint": "Check that the module defining this asset is imported.",
                },
            )
        return _asset_to_dict(asset_key)
    except HTTPException:
        raise
    except NucleusError as err:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,
                "user_message": err.user_message,
                "fix_hint": err.fix_hint,
            },  # type: ignore[attr-defined]
        ) from err
    except Exception as exc:
        err = translate(exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,
                "user_message": err.user_message,
                "fix_hint": err.fix_hint,
            },  # type: ignore[attr-defined]
        ) from err
