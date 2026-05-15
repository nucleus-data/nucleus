"""GET /api/dashboard/summary — dashboard hero stat chips endpoint.

Aggregates asset count, total row estimate, check health, and last-run
time into a single response to power the Editorial Hero stat chips.

Also returns recent_runs from the in-process run store so the
DashboardPage makes only ONE round-trip instead of two.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience).
ADR-016 §3 — Fork B API surface.

Vocabulary: "asset", "materialization", "check" per AGENTS.md §7.
No banned terms or orchestrator class names in API responses.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

import time
from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import APIRouter

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError
from nucleus.sdk.decorators import _registered_keys, get_checks

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary() -> Any:
    """Return aggregated summary for the hero stat chips and recent runs.

    Response shape::

        {
            "total_assets": 12,
            "total_rows": None,         # row counts are runtime data; null in dev
            "checks_green": 8,
            "checks_total": 8,
            "last_run_ago_seconds": 120.5,
            "recent_runs": [ ...RunRecord dicts (max 8)... ]
        }

    Row counts are always ``null`` in v0.1 — the Iceberg catalog integration
    that tracks this lives in v0.3+.  The frontend renders ``—`` in that case.
    """
    from fastapi import HTTPException

    try:
        from nucleus.workbench.api.runs import _runs

        keys = _registered_keys()
        total_assets = len(keys)

        # Count checks across all assets.
        checks_total = 0
        checks_green = 0
        for key in keys:
            asset_checks = get_checks(key)
            checks_total += len(asset_checks)
            # In v0.1 all checks are "green" until a run reports otherwise.
            # A real check-result store lands in v0.3.
            checks_green += len(asset_checks)

        # Last run timing from in-process ring-buffer.
        last_run_ago: float | None = None
        recent_run_list: list[dict[str, Any]] = []
        if _runs:
            sorted_runs = sorted(_runs, key=lambda r: r.started_at, reverse=True)
            last_run_ago = time.time() - sorted_runs[0].started_at
            recent_run_list = [
                {
                    "run_id": r.run_id,
                    "asset_key": r.asset_key,
                    "status": r.status,
                    "started_at": r.started_at,
                    "duration_ms": r.duration_ms,
                    "rows_written": r.rows_written,
                    "snapshot_id": r.snapshot_id,
                }
                for r in sorted_runs[:8]
            ]

        return {
            "total_assets": total_assets,
            "total_rows": None,  # v0.3: Iceberg catalog row-count tracking
            "checks_green": checks_green,
            "checks_total": checks_total,
            "last_run_ago_seconds": last_run_ago,
            "recent_runs": recent_run_list,
        }

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
