"""GET /api/runs  +  GET /api/runs/{run_id}/log — run history endpoints.

Run history in v0.2 is an in-process ring-buffer (no persistent store;
persistence is deferred to v0.3 when the orchestration event log integration lands).
The buffer is populated by ``nucleus.coordination.asset_materialization`` via
:func:`record_run` called at materialization commit.

``docs/specs/nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience).
ADR-016 §3 — Fork B API surface.

Log streaming uses FastAPI ``StreamingResponse`` with ``text/event-stream``
media type (server-sent events). No extra dependencies needed — avoids adding
``sse-starlette`` per the task brief's "avoid new deps" preference.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from collections.abc import Generator
from dataclasses import asdict, dataclass, field
from typing import Any

# Docs: https://fastapi.tiangolo.com/advanced/custom-response/
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError

router = APIRouter(prefix="/api/runs", tags=["runs"])


class TriggerRunRequest(BaseModel):
    """Request body for POST /api/runs/trigger."""

    asset_key: str = Field(..., description="Key of the asset to materialize.")


# ---------------------------------------------------------------------------
# In-process run store (ring-buffer, max 200 runs)
# ---------------------------------------------------------------------------

_MAX_RUNS = 200


@dataclass
class RunRecord:
    """One recorded materialization run.

    # Stability: Internal @ v0.2
    """

    run_id: str
    asset_key: str
    status: str  # "success" | "failure" | "running"
    started_at: float  # Unix epoch seconds (UTC)
    duration_ms: int | None
    rows_written: int | None
    snapshot_id: str | None
    log_lines: list[str] = field(default_factory=list)


_runs: deque[RunRecord] = deque(maxlen=_MAX_RUNS)
_runs_by_id: dict[str, RunRecord] = {}


def record_run(
    *,
    asset_key: str,
    status: str,
    started_at: float | None = None,
    duration_ms: int | None = None,
    rows_written: int | None = None,
    snapshot_id: str | None = None,
    log_lines: list[str] | None = None,
) -> str:
    """Register a completed (or in-flight) run in the in-process store.

    Returns the assigned ``run_id`` for log-streaming references.
    Called by ``nucleus.coordination.asset_materialization`` at commit.

    # Stability: Internal @ v0.2
    """
    run_id = str(uuid.uuid4())
    record = RunRecord(
        run_id=run_id,
        asset_key=asset_key,
        status=status,
        started_at=started_at or time.time(),
        duration_ms=duration_ms,
        rows_written=rows_written,
        snapshot_id=snapshot_id,
        log_lines=log_lines or [],
    )
    _runs.appendleft(record)
    _runs_by_id[run_id] = record
    # Keep _runs_by_id bounded to _MAX_RUNS to avoid unbounded growth.
    if len(_runs_by_id) > _MAX_RUNS * 2:
        oldest_ids = set(r.run_id for r in _runs)
        stale = [k for k in _runs_by_id if k not in oldest_ids]
        for k in stale:
            _runs_by_id.pop(k, None)
    return run_id


def _run_to_dict(r: RunRecord) -> dict[str, Any]:
    d = asdict(r)
    d.pop("log_lines")  # logs served via separate endpoint
    return d


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_runs(limit: int = 50) -> Any:
    """Return recent runs (most-recent first).

    Args:
        limit: Max runs to return (1-200; default 50).
    """
    try:
        n = max(1, min(limit, _MAX_RUNS))
        return [_run_to_dict(r) for r in list(_runs)[:n]]
    except NucleusError as err:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,
                "user_message": err.user_message,
                "fix_hint": err.fix_hint,
            },  # type: ignore[attr-defined]
        ) from err
    except Exception as exc:
        from fastapi import HTTPException

        err = translate(exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": err.error_code,
                "user_message": err.user_message,
                "fix_hint": err.fix_hint,
            },  # type: ignore[attr-defined]
        ) from err


@router.get("/{run_id}/log")
def stream_run_log(run_id: str) -> Any:
    """Stream log lines for a run as server-sent events.

    Returns ``text/event-stream`` (SSE) so the Workbench can display live
    log output.  For completed runs, all lines are emitted immediately then
    the stream closes with a ``data: [DONE]`` sentinel.

    Uses FastAPI ``StreamingResponse`` (no extra SSE dep needed).
    Docs: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
    """
    from fastapi import HTTPException

    record = _runs_by_id.get(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "NE3001",
                "user_message": f"Run '{run_id}' not found.",
                "fix_hint": "Check the run ID from GET /api/runs.",
            },
        )

    def _generate() -> Generator[str, None, None]:
        for line in record.log_lines:
            payload = json.dumps({"line": line})
            yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/trigger")
def trigger_run(req: TriggerRunRequest) -> Any:
    """Trigger an immediate (non-scheduled) materialization of an asset.

    Records the run in the in-process store and returns its ``run_id``
    for log-stream polling.  The actual materialization is a best-effort
    fire-and-forget in v0.2 (background threading).

    In v0.3+ this will delegate to the embedded orchestration layer.

    Args:
        req.asset_key: Key of the asset to materialize.

    Returns:
        JSON object with ``run_id``, ``asset_key``, ``status``, ``started_at``.
    """
    from nucleus.sdk.decorators import get_asset

    # Validate asset exists.
    defn = get_asset(req.asset_key)
    if defn is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "NE3001",
                "user_message": f"Asset '{req.asset_key}' is not registered.",
                "fix_hint": "Check that the module defining this asset is imported.",
            },
        )

    started = time.time()

    # Record a "running" entry immediately so the UI can poll it.
    run_id = record_run(
        asset_key=req.asset_key,
        status="running",
        started_at=started,
        log_lines=[f"[trigger] Materialization of '{req.asset_key}' queued via Workbench."],
    )

    # Fire-and-forget materialization in background thread.
    import threading

    def _run_in_background() -> None:
        try:
            from nucleus.sdk.decorators import get_asset as _ga

            defn_ = _ga(req.asset_key)
            if defn_ is None:
                return
            # Call the asset function directly (v0.1 simple path).
            # v0.3 will route through the embedded orchestration layer instead.
            result = defn_.fn()  # type: ignore[call-arg]
            end = time.time()
            rec = _runs_by_id.get(run_id)
            if rec:
                rec.status = "success"
                rec.duration_ms = int((end - started) * 1000)
                if hasattr(result, "rows_written"):
                    rec.rows_written = result.rows_written
                rec.log_lines.append(f"[trigger] Completed in {rec.duration_ms}ms.")
        except Exception as exc:
            end = time.time()
            rec = _runs_by_id.get(run_id)
            if rec:
                rec.status = "failure"
                rec.duration_ms = int((end - started) * 1000)
                rec.log_lines.append(f"[trigger] Failed: {exc}")

    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()

    return {
        "run_id": run_id,
        "asset_key": req.asset_key,
        "status": "running",
        "started_at": started,
    }
