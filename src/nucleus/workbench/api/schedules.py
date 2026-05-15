"""GET /api/schedules  +  GET /api/schedules/{key}/preview — schedule endpoints.

Wraps ``nucleus.coordination.schedules.list_schedules`` and
``nucleus.coordination.schedules.preview_schedule`` (ADR-017).

Zero orchestrator types cross the boundary — enforced by
``scripts/dagster_leak_check.py`` script in CI.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience).
ADR-016 §3 — Fork B API surface.
ADR-017 — Schedule exposure v0.1.

Vocabulary: "asset", "schedule" per AGENTS.md §7.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/bigger-applications/
from fastapi import APIRouter, HTTPException

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_PREVIEW_DEFAULT = 5
_PREVIEW_MAX = 20


def _schedule_entry_to_dict(entry: Any, next_runs: list[str] | None = None) -> dict[str, Any]:
    """Serialize a :class:`ScheduleEntry` to a JSON-safe dict."""
    return {
        "asset_key": entry.asset_key,
        "cron_expression": entry.cron_expression,
        "description": entry.description,
        "next_runs": next_runs or [],
    }


@router.get("")
def list_schedules_endpoint() -> Any:
    """Return all scheduled assets with their next 3 run times.

    Wraps ``nucleus.coordination.schedules.list_schedules`` and
    ``nucleus.coordination.schedules.preview_schedule``.
    """
    try:
        from nucleus.coordination.schedules import (
            list_schedules as _list,
            preview_schedule as _preview,
        )

        entries = _list()
        result = []
        for entry in entries:
            try:
                previews = _preview(entry.asset_key, count=_PREVIEW_DEFAULT)
                next_runs = [r.isoformat() for r in previews]
            except Exception:
                next_runs = []
            result.append(_schedule_entry_to_dict(entry, next_runs))
        return result

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


@router.get("/{asset_key:path}/preview")
def preview_schedule_endpoint(asset_key: str, count: int = _PREVIEW_DEFAULT) -> Any:
    """Return the next ``count`` run times for a scheduled asset.

    Args:
        asset_key: Asset key (URL-encoded if it contains slashes).
        count:     Number of future runs to return (1–20; default 5).
    """
    count = max(1, min(count, _PREVIEW_MAX))

    try:
        from nucleus.coordination.schedules import (
            list_schedules as _list,
            preview_schedule as _preview,
        )

        # Find the entry first to validate it exists.
        entries = {e.asset_key: e for e in _list()}
        entry = entries.get(asset_key)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "NE3001",
                    "user_message": f"No schedule found for asset '{asset_key}'.",
                    "fix_hint": "Add schedule=... to @nucleus.asset to register a schedule.",
                },
            )

        previews = _preview(asset_key, count=count)
        return _schedule_entry_to_dict(entry, [r.isoformat() for r in previews])

    except HTTPException:
        raise
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
