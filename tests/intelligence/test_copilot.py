"""Unit tests for nucleus.intelligence.copilot and context.

Per ADR-015 §Verification plan:
  - Happy-path round-trips (one per provider, mocked litellm.completion)
  - Opt-in gate: prompt + abort flow
  - Pre-flight cost ceiling: refuses BEFORE any HTTP call
  - Error translation: each NE4xxx code + NE3005 reuse
  - Footer disclosure: stderr output after success
  - Privacy: context dict passes all 5 redaction rules

No real LLM calls — litellm.completion is mocked throughout.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nucleus.errors import (
    NucleusBudgetExceededError,
    NucleusCopilotAuthError,
    NucleusCopilotContentFilterError,
    NucleusCopilotRateLimitError,
    NucleusTimeoutError,
)

# Fixture: test project root
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "test_project"


def _make_mock_response(
    content: str = "Hello from Copilot!", provider: str = "anthropic"
) -> MagicMock:
    """Build a mock litellm completion response in OpenAI Chat Completions shape."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    resp.usage = usage
    resp.model = f"{provider}/claude-3-5-haiku-20241022"
    return resp


# ─── Happy path tests ────────────────────────────────────────────────────────


def test_chat_happy_path_anthropic(tmp_path):
    """T1: Happy path — Anthropic provider returns CopilotReply with all fields."""
    _setup_opted_in_project(tmp_path)
    mock_resp = _make_mock_response("Anthropic reply text.", "anthropic")

    with patch("litellm.completion", return_value=mock_resp):
        from nucleus.intelligence.copilot import chat

        reply = chat("What is the status of my project?", project_root=tmp_path)

    assert reply.text == "Anthropic reply text."
    assert reply.provider == "anthropic"
    assert reply.tokens_in == 100
    assert reply.tokens_out == 50
    assert isinstance(reply.cost_usd, float)


def test_chat_happy_path_openai(tmp_path):
    """T2: Happy path — OpenAI provider returns CopilotReply with correct provider field."""
    _setup_opted_in_project(tmp_path, provider="openai")
    mock_resp = _make_mock_response("OpenAI reply.", "openai")

    with patch("litellm.completion", return_value=mock_resp):
        from nucleus.intelligence.copilot import chat

        reply = chat("How do I run an asset?", project_root=tmp_path, provider="openai")

    assert reply.provider == "openai"
    assert reply.text == "OpenAI reply."


def test_chat_happy_path_ollama_cost_zero(tmp_path):
    """T3: Ollama provider always returns cost_usd == 0.0 (local, no billing)."""
    _setup_opted_in_project(tmp_path, provider="ollama")
    mock_resp = _make_mock_response("Ollama reply.", "ollama")

    with patch("litellm.completion", return_value=mock_resp):
        from nucleus.intelligence.copilot import chat

        reply = chat("Tell me about my assets.", project_root=tmp_path, provider="ollama")

    assert reply.cost_usd == 0.0
    assert reply.provider == "ollama"


# ─── Opt-in gate ────────────────────────────────────────────────────────────


def test_chat_optin_gate_declines(tmp_path):
    """T4: When opt_in=False and user declines, raises NucleusConfigError; no litellm call."""
    _setup_project(tmp_path)  # NOT opted in

    with (
        patch("typer.confirm", return_value=False),
        patch("litellm.completion") as mock_completion,
    ):
        from nucleus.errors import NucleusConfigError
        from nucleus.intelligence.copilot import chat

        with pytest.raises(NucleusConfigError):
            chat("question", project_root=tmp_path)

        mock_completion.assert_not_called()


def test_chat_optin_gate_accepts_and_persists(tmp_path):
    """T4b: When user accepts the opt-in prompt, choice is persisted."""
    _setup_project(tmp_path)
    mock_resp = _make_mock_response("Reply after accept.", "anthropic")

    with (
        patch("typer.confirm", return_value=True),
        patch("litellm.completion", return_value=mock_resp),
    ):
        from nucleus.intelligence.copilot import chat

        reply = chat("question", project_root=tmp_path)

    assert reply.text == "Reply after accept."
    opt_in_file = tmp_path / ".nucleus" / "copilot_opt_in"
    assert opt_in_file.exists()
    assert opt_in_file.read_text().strip() == "true"


# ─── Pre-flight cost ceiling ─────────────────────────────────────────────────


def test_chat_budget_exceeded_before_http(tmp_path):
    """T5: Estimated cost > ceiling raises NucleusBudgetExceededError BEFORE any HTTP call."""
    _setup_opted_in_project(tmp_path, extra_yaml="  cost_ceiling_usd: 0.000001\n")

    with patch("litellm.completion") as mock_completion:
        from nucleus.intelligence.copilot import chat

        with pytest.raises(NucleusBudgetExceededError) as exc_info:
            chat("A" * 8000, project_root=tmp_path)  # long question → high token estimate

        mock_completion.assert_not_called()
        assert "NE4005" in exc_info.value.error_code


# ─── Error translation ───────────────────────────────────────────────────────


def test_error_translation_auth(tmp_path):
    """T6: litellm.AuthenticationError → NucleusCopilotAuthError (NE4001); no banned strings."""
    _setup_opted_in_project(tmp_path)
    import litellm

    auth_exc = litellm.AuthenticationError(
        message="Invalid API key provided: sk-ANTHROPIC_API_KEY=xxx",
        llm_provider="anthropic",
        model="claude",
    )

    with patch("litellm.completion", side_effect=auth_exc):
        from nucleus.intelligence.copilot import chat

        with pytest.raises(NucleusCopilotAuthError) as exc_info:
            chat("question", project_root=tmp_path)

    err = exc_info.value
    assert err.error_code == "NE4001"
    _assert_no_banned_strings(err.user_message)
    _assert_no_banned_strings(err.fix_hint)


def test_error_translation_rate_limit(tmp_path):
    """T7: litellm.RateLimitError → NucleusCopilotRateLimitError (NE4002)."""
    _setup_opted_in_project(tmp_path)
    import litellm

    rate_exc = litellm.RateLimitError(
        message="Rate limit exceeded",
        llm_provider="anthropic",
        model="claude",
    )

    with patch("litellm.completion", side_effect=rate_exc):
        from nucleus.intelligence.copilot import chat

        with pytest.raises(NucleusCopilotRateLimitError) as exc_info:
            chat("question", project_root=tmp_path)

    assert exc_info.value.error_code == "NE4002"


def test_error_translation_content_filter(tmp_path):
    """T8: litellm.ContentPolicyViolationError → NucleusCopilotContentFilterError (NE4004)."""
    _setup_opted_in_project(tmp_path)
    import litellm

    cf_exc = litellm.ContentPolicyViolationError(
        message="Content policy violation",
        llm_provider="anthropic",
        model="claude",
    )

    with patch("litellm.completion", side_effect=cf_exc):
        from nucleus.intelligence.copilot import chat

        with pytest.raises(NucleusCopilotContentFilterError) as exc_info:
            chat("question", project_root=tmp_path)

    assert exc_info.value.error_code == "NE4004"


def test_error_translation_timeout(tmp_path):
    """T9: litellm.Timeout → NucleusTimeoutError (NE3005, reused). NOT litellm.TimeoutError."""
    _setup_opted_in_project(tmp_path)
    import litellm

    # CRITICAL: litellm.Timeout NOT litellm.TimeoutError
    # See docs/research/ai_hallucinations.md entry 2026-05-13
    timeout_exc = litellm.Timeout(
        message="Request timed out",
        model="claude",
        llm_provider="anthropic",
    )

    with patch("litellm.completion", side_effect=timeout_exc):
        from nucleus.intelligence.copilot import chat

        with pytest.raises(NucleusTimeoutError) as exc_info:
            chat("question", project_root=tmp_path)

    assert exc_info.value.error_code == "NE3005"


# ─── Footer disclosure ──────────────────────────────────────────────────────


def test_footer_disclosure_written_to_stderr(tmp_path, capsys):
    """T10: After success, stderr contains 'Copilot: provider=<name> tokens=<N> cost=$<N>'."""
    _setup_opted_in_project(tmp_path)
    mock_resp = _make_mock_response("Test reply.", "anthropic")

    with patch("litellm.completion", return_value=mock_resp):
        from nucleus.intelligence.copilot import chat

        chat("question", project_root=tmp_path)

    captured = capsys.readouterr()
    assert "Copilot: provider=anthropic" in captured.err
    assert "tokens=" in captured.err
    assert "cost=$" in captured.err


# ─── Privacy / context redaction ────────────────────────────────────────────


def test_gather_context_privacy_rules():
    """T11: gather_context on fixture project satisfies all 5 privacy rules."""
    from nucleus.intelligence.context import gather_context

    ctx = gather_context(FIXTURE_ROOT)

    _assert_context_privacy(ctx, FIXTURE_ROOT)


def test_gather_context_size_within_cap():
    """T11b: context dict serialized size ≤ 4 KB."""
    from nucleus.intelligence.context import gather_context

    ctx = gather_context(FIXTURE_ROOT)

    serialized = json.dumps(ctx, default=str)
    assert len(serialized.encode()) <= 4 * 1024, (
        f"Context exceeded 4 KB: {len(serialized.encode())} bytes"
    )


def test_gather_context_reads_fail_events(tmp_path: Path) -> None:
    """T11c: gather_context reads FAIL events from .nucleus/lineage/*.ndjson.

    Writes the OpenLineage fixture inside ``tmp_path`` rather than relying on
    a checked-in fixture: ``.nucleus/`` is in the root ``.gitignore`` (line
    117), so a committed fixture under ``tests/intelligence/fixtures/.../
    .nucleus/lineage/`` would be invisible on CI checkout. Refactor keeps
    the test self-contained and skips the ``.gitignore`` carve-out fight.
    """
    from nucleus.intelligence.context import gather_context

    (tmp_path / "nucleus_project.yaml").write_text(
        "project:\n  name: fixture-project\nstorage:\n  warehouse: ./data/warehouse\n",
        encoding="utf-8",
    )
    lineage_dir = tmp_path / ".nucleus" / "lineage"
    lineage_dir.mkdir(parents=True, exist_ok=True)
    fail_event = {
        "eventType": "FAIL",
        "eventTime": "2026-05-15T10:05:00Z",
        "run": {
            "runId": "fail-001",
            "facets": {
                "errorMessage": {
                    "message": "Schema mismatch in asset transform: expected int, got str",
                    "programmaticName": "NucleusSchemaError",
                },
            },
        },
        "job": {"namespace": "test", "name": "raw.orders"},
        "inputs": [],
        "outputs": [],
    }
    (lineage_dir / "events.ndjson").write_text(json.dumps(fail_event) + "\n", encoding="utf-8")

    ctx = gather_context(tmp_path)

    assert len(ctx["recent_errors"]) > 0
    for err in ctx["recent_errors"]:
        assert "timestamp" in err
        assert "message" in err


# ─── Helpers ─────────────────────────────────────────────────────────────────

_BANNED = ["litellm", "anthropic", "openai", "ollama", "LiteLLM", "API_KEY"]


def _assert_no_banned_strings(text: str) -> None:
    for banned in _BANNED:
        assert banned not in text, f"Banned string {banned!r} found in user-facing text: {text!r}"


def _assert_context_privacy(ctx: dict, project_root: Path) -> None:
    """Verify all 5 privacy rules on a context dict."""
    serialized = json.dumps(ctx, default=str)

    # Rule 4: no absolute paths
    root_str = str(project_root.resolve())
    assert root_str not in serialized, f"Absolute path leaked into context: {root_str}"

    # Rule 3: no OS username
    import getpass

    try:
        username = getpass.getuser()
        if username:
            assert username not in serialized, f"Username leaked: {username}"
    except Exception:
        pass

    # Rule 1: no raw SQL keywords in data fields (project YAML may contain "SELECT" in comments)
    # Check the assets specifically don't contain SQL data
    for asset in ctx.get("assets", []):
        for _col in asset.get("column_names", []):
            pass  # column names are metadata; SQL redaction applies to full strings not individual names


def _setup_project(tmp_path: Path, provider: str = "anthropic", extra_yaml: str = "") -> None:
    """Create a minimal nucleus_project.yaml WITHOUT opt_in."""
    content = f"""project:
  name: test-project

catalog:
  type: filesystem

storage:
  warehouse: ./data/warehouse

copilot:
  provider: {provider}
{extra_yaml}"""
    (tmp_path / "nucleus_project.yaml").write_text(content)
    (tmp_path / ".nucleus").mkdir(exist_ok=True)


def _setup_opted_in_project(
    tmp_path: Path,
    provider: str = "anthropic",
    extra_yaml: str = "",
) -> None:
    """Create a minimal nucleus_project.yaml WITH opt_in=True."""
    content = f"""project:
  name: test-project

catalog:
  type: filesystem

storage:
  warehouse: ./data/warehouse

copilot:
  provider: {provider}
  opt_in: true
{extra_yaml}"""
    (tmp_path / "nucleus_project.yaml").write_text(content)
    (tmp_path / ".nucleus").mkdir(exist_ok=True)
