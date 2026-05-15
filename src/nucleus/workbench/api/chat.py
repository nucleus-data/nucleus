"""POST /api/chat — Copilot proxy endpoint.

Wraps ``nucleus.intelligence.copilot.chat`` (the single-turn AI function
per ADR-015) and streams the reply as server-sent events so the Workbench
Copilot side panel can display responses progressively.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience) + §7.2 (Copilot).
ADR-016 §3 — Fork B API surface.
ADR-015 — Copilot single-turn chat.

Privacy gate: the same opt-in check in ``nucleus.intelligence.copilot`` is
enforced.  No bytes are sent to the LLM before the user has opted in.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/body/
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

# Docs: https://docs.pydantic.dev/latest/concepts/models/  (pydantic v2)
from pydantic import BaseModel, Field

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    question: str = Field(..., description="Natural language question for the AI Copilot.")
    project_dir: str = Field(
        "",
        description="Project root directory (resolved from cwd when empty).",
    )
    stream: bool = Field(
        default=False,
        description="When true, return server-sent events stream instead of JSON.",
    )


def _resolve_project_dir(project_dir: str) -> Any:
    """Resolve project root from explicit path or cwd walk."""
    from pathlib import Path

    if project_dir:
        return Path(project_dir)
    import os

    here = Path(os.getcwd()).resolve()
    for candidate in (here, *here.parents)[:4]:
        if (candidate / "nucleus_project.yaml").is_file():
            return candidate
    return here


@router.post("/chat")
def ask_copilot(req: ChatRequest) -> Any:
    """Forward a question to the Nucleus AI Copilot and return the reply.

    The Copilot reads project context (schema, recent runs, assets) and
    answers in the Nucleus vocabulary.  Requires the user to have opted in
    to sending context (ADR-015 §3 + ADR-011).

    When ``stream=true`` returns ``text/event-stream``; otherwise returns
    a JSON object with ``text``, ``suggested_command``, ``tokens_in``,
    ``tokens_out``, ``cost_usd``, ``provider``, ``model``.
    """
    if not req.question or not req.question.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "NE5001",
                "user_message": "A question is required.",
                "fix_hint": "Pass the question in the 'question' field.",
            },
        )

    try:
        from nucleus.intelligence.copilot import chat as copilot_chat

        project_root = _resolve_project_dir(req.project_dir)
        reply = copilot_chat(req.question, project_root=project_root)

        if req.stream:
            # Emit the single reply as an SSE event then [DONE].
            def _stream() -> Generator[str, None, None]:
                payload = json.dumps(
                    {
                        "text": reply.text,
                        "suggested_command": reply.suggested_command,
                        "tokens_in": reply.tokens_in,
                        "tokens_out": reply.tokens_out,
                        "cost_usd": reply.cost_usd,
                        "provider": reply.provider,
                        "model": reply.model,
                    }
                )
                yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                _stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        return {
            "text": reply.text,
            "suggested_command": reply.suggested_command,
            "tokens_in": reply.tokens_in,
            "tokens_out": reply.tokens_out,
            "cost_usd": reply.cost_usd,
            "provider": reply.provider,
            "model": reply.model,
        }

    except NucleusError as err:
        code = 402 if "Budget" in type(err).__name__ else 500
        raise HTTPException(
            status_code=code,
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
