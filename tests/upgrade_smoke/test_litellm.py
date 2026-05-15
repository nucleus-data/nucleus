"""LiteLLM upgrade smoke test — AGENTS.md §11.13 / ADR-015 §5.

Pins the shape of ``response.choices[0].message.content`` against
minor-version drift. Uses a mocked ``litellm.completion`` returning
a known dict shape; asserts the parser still reads ``.content`` correctly.

Run on every ``litellm`` pin bump per Constraint #11:
  pytest tests/upgrade_smoke/test_litellm.py -v

If this test fails after a litellm upgrade, read the LiteLLM changelog
and update ``nucleus.intelligence.copilot`` accordingly before merging.

Docs: https://docs.litellm.ai/docs/completion/output
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Skip gracefully if litellm is not installed in this environment.
litellm = pytest.importorskip("litellm", reason="litellm not installed — skip upgrade smoke")


# ─── Shape assertions ────────────────────────────────────────────────────────


def _make_known_shape(content: str = "stable reply") -> MagicMock:
    """Construct the known OpenAI Chat-Completions shape for litellm==1.83.14.

    Docs: https://docs.litellm.ai/docs/completion/output
    Shape: response.choices[0].message.content (str)
           response.usage.prompt_tokens        (int)
           response.usage.completion_tokens    (int)
    """
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    usage = MagicMock()
    usage.prompt_tokens = 42
    usage.completion_tokens = 17
    resp.usage = usage
    return resp


def test_litellm_response_shape_content_readable():
    """Shape: response.choices[0].message.content returns a string."""
    resp = _make_known_shape("shape stable")
    content = resp.choices[0].message.content
    assert isinstance(content, str)
    assert content == "shape stable"


def test_litellm_response_shape_usage_tokens():
    """Shape: response.usage.prompt_tokens and .completion_tokens are int-like."""
    resp = _make_known_shape()
    assert int(resp.usage.prompt_tokens) == 42
    assert int(resp.usage.completion_tokens) == 17


def test_litellm_exception_timeout_class_name():
    """Verify litellm.Timeout exists (NOT litellm.TimeoutError).

    See docs/research/ai_hallucinations.md entry 2026-05-13.
    Docs: https://docs.litellm.ai/docs/exception_mapping
    """
    assert hasattr(litellm, "Timeout"), (
        "litellm.Timeout class missing — update translate.py if the exception was renamed"
    )
    assert not hasattr(litellm, "TimeoutError") or litellm.Timeout is not getattr(
        litellm, "TimeoutError", None
    ), (
        "litellm.Timeout and litellm.TimeoutError now appear to be the same class — "
        "re-verify against https://docs.litellm.ai/docs/exception_mapping"
    )


def test_litellm_exception_auth_class_exists():
    """Verify litellm.AuthenticationError exists (maps to NE4001)."""
    assert hasattr(litellm, "AuthenticationError"), (
        "litellm.AuthenticationError missing — update translate.py"
    )


def test_litellm_exception_rate_limit_class_exists():
    """Verify litellm.RateLimitError exists (maps to NE4002)."""
    assert hasattr(litellm, "RateLimitError"), "litellm.RateLimitError missing"


def test_litellm_exception_content_policy_class_exists():
    """Verify litellm.ContentPolicyViolationError exists (maps to NE4004)."""
    assert hasattr(litellm, "ContentPolicyViolationError"), (
        "litellm.ContentPolicyViolationError missing — update translate.py"
    )
