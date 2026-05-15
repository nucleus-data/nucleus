"""Copilot swap-interface smoke tests — ADR-015 §5 / Composability Constitution.

Per Composability by Constitution §2: smoke tests prove that the swap
interface (LiteLLM model-id string switching) works across all three
first-class providers without touching real APIs.

One mocked round-trip per provider; asserts the ``model=`` kwarg flows
through to ``litellm.completion`` and the response shape is consumed
correctly. No network calls.

Architecture ref: ``nucleus_architecture_v4.1.md`` §9.3 + ADR-015 §5
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# ─── Fixture ─────────────────────────────────────────────────────────────────


def _mock_response(content: str = "Smoke test reply.") -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    usage = MagicMock()
    usage.prompt_tokens = 50
    usage.completion_tokens = 20
    resp.usage = usage
    return resp


def _opted_in_project(tmp_path: Path, provider: str = "anthropic") -> Path:
    content = f"""project:
  name: smoke-project

storage:
  warehouse: ./data/warehouse

copilot:
  provider: {provider}
  opt_in: true
"""
    (tmp_path / "nucleus_project.yaml").write_text(content)
    (tmp_path / ".nucleus").mkdir(exist_ok=True)
    return tmp_path


# ─── Smoke tests ─────────────────────────────────────────────────────────────


def test_smoke_anthropic_provider(tmp_path):
    """S1: Anthropic provider — litellm.completion called with anthropic/* model prefix."""
    _opted_in_project(tmp_path, provider="anthropic")

    with patch("litellm.completion", return_value=_mock_response()) as mock_comp:
        from nucleus.intelligence.copilot import chat

        reply = chat("smoke test question", project_root=tmp_path, provider="anthropic")

    assert reply.provider == "anthropic"
    model_arg = mock_comp.call_args[1]["model"] or mock_comp.call_args[0][0]
    assert "anthropic" in model_arg, f"Expected 'anthropic' in model={model_arg!r}"


def test_smoke_openai_provider(tmp_path):
    """S2: OpenAI provider — litellm.completion called with correct model id."""
    _opted_in_project(tmp_path, provider="openai")

    with patch("litellm.completion", return_value=_mock_response()) as mock_comp:
        from nucleus.intelligence.copilot import chat

        reply = chat("smoke test question", project_root=tmp_path, provider="openai")

    assert reply.provider == "openai"
    # model arg should not contain "anthropic"
    model_arg = mock_comp.call_args[1]["model"]
    assert "anthropic" not in model_arg, (
        f"OpenAI call should not use anthropic model: {model_arg!r}"
    )


def test_smoke_ollama_provider_cost_zero(tmp_path):
    """S3: Ollama provider — model prefixed with 'ollama/' and cost=0."""
    _opted_in_project(tmp_path, provider="ollama")

    with patch("litellm.completion", return_value=_mock_response()) as mock_comp:
        from nucleus.intelligence.copilot import chat

        reply = chat("smoke test question", project_root=tmp_path, provider="ollama")

    assert reply.cost_usd == 0.0
    model_arg = mock_comp.call_args[1]["model"]
    assert model_arg.startswith("ollama/"), (
        f"Ollama model should start with 'ollama/': {model_arg!r}"
    )


def test_smoke_provider_swap_via_kwarg(tmp_path):
    """S4: Provider swap via --provider kwarg changes the litellm model string."""
    _opted_in_project(tmp_path, provider="anthropic")  # default anthropic

    with patch("litellm.completion", return_value=_mock_response()) as mock_comp:
        from nucleus.intelligence.copilot import chat

        # Override to openai via kwarg — proves swap is config-string only.
        reply = chat("swap test", project_root=tmp_path, provider="openai", model="gpt-4o-mini")

    assert reply.provider == "openai"
    model_arg = mock_comp.call_args[1]["model"]
    assert "gpt-4o-mini" in model_arg


def test_smoke_reply_shape_stable(tmp_path):
    """S5: CopilotReply fields are all present and have correct types."""
    _opted_in_project(tmp_path)

    with patch("litellm.completion", return_value=_mock_response("The answer is 42.")):
        from nucleus.intelligence.copilot import CopilotReply, chat

        reply = chat("question", project_root=tmp_path)

    assert isinstance(reply, CopilotReply)
    assert isinstance(reply.text, str)
    assert reply.suggested_command is None or isinstance(reply.suggested_command, str)
    assert isinstance(reply.tokens_in, int)
    assert isinstance(reply.tokens_out, int)
    assert isinstance(reply.cost_usd, float)
    assert isinstance(reply.provider, str)
    assert isinstance(reply.model, str)
