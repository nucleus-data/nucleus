"""GET /api/catalog — paginated asset catalog browser endpoint.

Returns a filtered, paginated list of all registered assets with
metadata suitable for the CatalogPage table view.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience).
ADR-016 §3 — Fork B API surface.

Vocabulary: "asset", "namespace", "check", "contract" per AGENTS.md §7.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import APIRouter, HTTPException

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError
from nucleus.sdk.decorators import _registered_keys, get_asset, get_checks

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100


def _catalog_row(key: str) -> dict[str, Any] | None:
    """Build one catalog row for a registered asset key."""
    defn = get_asset(key)
    if defn is None:
        return None
    checks = get_checks(key)
    # Namespace = first segment of key (e.g. "raw" from "raw.orders").
    namespace = key.split(".", maxsplit=1)[0] if "." in key else "default"
    return {
        "key": defn.key,
        "namespace": namespace,
        "has_schedule": defn.schedule is not None,
        "has_contract": defn.contract is not None,
        "check_count": len(checks),
        "dep_count": len(defn.deps),
        "compute": defn.compute,
    }


@router.get("")
def list_catalog(
    q: str = "",
    page: int = 1,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> Any:
    """Return a paginated, filterable list of all registered assets.

    Args:
        q:         Filter substring (case-insensitive match on asset key).
        page:      1-based page number (default 1).
        page_size: Items per page (1–100; default 25).

    Response shape::

        {
            "items": [ { "key": ..., "namespace": ..., ... }, ... ],
            "total": 42,
            "page": 1,
            "page_size": 25
        }
    """
    try:
        page = max(1, page)
        page_size = max(1, min(page_size, _MAX_PAGE_SIZE))

        all_keys = _registered_keys()

        # Filter by substring match on asset key.
        q_lower = q.strip().lower()
        if q_lower:
            all_keys = [k for k in all_keys if q_lower in k.lower()]

        all_keys = sorted(all_keys)
        total = len(all_keys)

        # Paginate.
        start = (page - 1) * page_size
        page_keys = all_keys[start : start + page_size]

        items: list[dict[str, Any]] = []
        for key in page_keys:
            row = _catalog_row(key)
            if row is not None:
                items.append(row)

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    except NucleusError as err:
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,  # type: ignore[attr-defined]
                "user_message": err.user_message,  # type: ignore[attr-defined]
                "fix_hint": err.fix_hint,  # type: ignore[attr-defined]
            },
        ) from err
    except Exception as exc:
        err = translate(exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,  # type: ignore[attr-defined]
                "user_message": err.user_message,  # type: ignore[attr-defined]
                "fix_hint": err.fix_hint,  # type: ignore[attr-defined]
            },
        ) from err
