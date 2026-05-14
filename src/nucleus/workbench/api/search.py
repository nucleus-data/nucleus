"""GET /api/search?q=... — global cross-entity search endpoint.

Searches assets (by key), recent runs (by asset key + run ID prefix),
and scheduled assets (by key) in a single call.  Used by the ⌘K
Command Palette in the Workbench frontend.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience).
ADR-016 §3 — Fork B API surface.

Returns up to 15 results to keep the palette snappy.  No pagination
(the palette is a speed surface, not a browse surface).

Vocabulary: "asset", "run", "schedule" per AGENTS.md §7.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from nucleus.coordination.error_translation import translate
from nucleus.sdk.decorators import _registered_keys, get_asset

router = APIRouter(prefix="/api/search", tags=["search"])

_MAX_RESULTS = 15


@router.get("", response_class=ORJSONResponse)
def global_search(q: str = "") -> Any:
    """Search assets, runs, and schedules by a query string.

    Response shape::

        {
            "query": "orders",
            "items": [
                {
                    "kind":      "asset",
                    "key":       "raw.orders",
                    "label":     "raw.orders",
                    "secondary": "asset",
                    "url":       "/assets/raw.orders"
                },
                ...
            ]
        }

    When ``q`` is empty or shorter than 2 chars, returns an empty list
    (the frontend shows quick-nav instead).
    """
    q_stripped = q.strip()
    if len(q_stripped) < 2:
        return {"query": q_stripped, "items": []}

    q_lower = q_stripped.lower()
    results: list[dict[str, Any]] = []

    # ── Assets ────────────────────────────────────────────────────
    try:
        all_keys = _registered_keys()
        matched_assets = [k for k in all_keys if q_lower in k.lower()]
        for key in matched_assets[:8]:
            defn = get_asset(key)
            secondary = "scheduled" if (defn and defn.schedule) else "asset"
            results.append({
                "kind":      "asset",
                "key":       key,
                "label":     key,
                "secondary": secondary,
                "url":       f"/assets/{key}",
            })
    except Exception:
        pass  # graceful degradation; don't fail the whole search

    # ── Runs ───────────────────────────────────────────────────────
    try:
        from nucleus.workbench.api.runs import _runs

        matched_runs = [
            r for r in _runs
            if q_lower in r.asset_key.lower() or r.run_id.lower().startswith(q_lower)
        ]
        for run in matched_runs[:4]:
            results.append({
                "kind":      "run",
                "key":       run.run_id,
                "label":     run.asset_key,
                "secondary": run.status,
                "url":       f"/runs/{run.run_id}",
            })
    except Exception:
        pass

    # ── Schedules ──────────────────────────────────────────────────
    try:
        from nucleus.coordination.schedules import list_schedules as _ls

        matched_schedules = [
            e for e in _ls()
            if q_lower in e.asset_key.lower()
        ]
        for entry in matched_schedules[:3]:
            results.append({
                "kind":      "schedule",
                "key":       entry.asset_key,
                "label":     entry.asset_key,
                "secondary": entry.cron_expression,
                "url":       "/schedules",
            })
    except Exception:
        pass

    # Deduplicate by (kind, key) preserving order.
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in results:
        ident = (item["kind"], item["key"])
        if ident not in seen:
            seen.add(ident)
            deduped.append(item)

    return {"query": q_stripped, "items": deduped[:_MAX_RESULTS]}
