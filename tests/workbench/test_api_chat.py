"""Tests for POST /api/chat.

Docs: https://fastapi.tiangolo.com/tutorial/testing/

The chat endpoint proxies to ``nucleus.intelligence.copilot.chat`` which:
  - Requires OPENAI_API_KEY or ANTHROPIC_API_KEY to actually call an LLM.
  - Enforces an opt-in gate (writes/reads .nucleus/copilot_opt_in).
  - Has a cost ceiling pre-flight check.

Tests here validate the API surface (request shape, error translation,
vocabulary) without actually calling an LLM — we patch copilot.chat.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture()
def client():  # type: ignore[no-untyped-def]
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from nucleus.workbench.app import create_app

    return TestClient(create_app())


def test_chat_empty_question_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/chat", json={"question": ""})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "error_code" in detail


def test_chat_whitespace_question_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/chat", json={"question": "  "})
    assert r.status_code == 422


def test_chat_missing_question_field_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/chat", json={})
    assert r.status_code == 422


def test_chat_returns_reply_json_on_success(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """With copilot.chat patched, verify the response shape."""
    from nucleus.intelligence.copilot import CopilotReply

    mock_reply = CopilotReply(
        text="Here is your answer.",
        suggested_command=None,
        tokens_in=10,
        tokens_out=5,
        cost_usd=0.001,
        provider="anthropic",
        model="claude-3-5-haiku-20241022",
    )

    with patch("nucleus.intelligence.copilot.chat", return_value=mock_reply):
        r = client.post(
            "/api/chat",
            json={"question": "What assets are registered?", "project_dir": str(tmp_path)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "Here is your answer."
    assert body["provider"] == "anthropic"
    assert "tokens_in" in body
    assert "cost_usd" in body


def test_chat_translates_nucleus_error_to_json(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """NucleusError from copilot.chat must be returned as a structured JSON error."""
    from nucleus.errors import NucleusConfigError

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise NucleusConfigError(
            user_message="AI Copilot not configured.",
            fix_hint="Add OPENAI_API_KEY or ANTHROPIC_API_KEY.",
        )

    with patch("nucleus.intelligence.copilot.chat", side_effect=_raise):
        r = client.post(
            "/api/chat",
            json={"question": "What schemas exist?", "project_dir": str(tmp_path)},
        )

    assert r.status_code in (402, 500)
    detail = r.json()["detail"]
    assert "error_code" in detail
    assert "user_message" in detail


def test_chat_response_no_dagster_leak(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from nucleus.intelligence.copilot import CopilotReply

    mock_reply = CopilotReply(
        text="All good.",
        suggested_command=None,
        tokens_in=1, tokens_out=1, cost_usd=0.0,
        provider="openai", model="gpt-4o-mini",
    )

    with patch("nucleus.intelligence.copilot.chat", return_value=mock_reply):
        r = client.post(
            "/api/chat",
            json={"question": "Hello?", "project_dir": str(tmp_path)},
        )

    text = r.text.lower()
    for banned in ("dagster", "opexecutioncontext", "definitionsvalidation"):
        assert banned not in text
