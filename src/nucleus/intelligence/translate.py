"""LiteLLM exception translator — private to ``nucleus.intelligence``.

Maps ``litellm.*`` exceptions to ``NucleusError`` subclasses per
ADR-015 §6 and v4.1 §6.4.

IMPORTANT — verified against docs 2026-05-13:
  ``litellm.Timeout``  (NOT ``litellm.TimeoutError``) — see
  ``docs/internal/research/ai_hallucinations.md`` entry for the catch.

Docs: https://docs.litellm.ai/docs/exception_mapping
Architecture ref: ``nucleus_architecture_v4.1.md`` §6.4 + ADR-015 §6
"""

from __future__ import annotations

import re

from nucleus.errors import (
    NucleusCopilotAuthError,
    NucleusCopilotContentFilterError,
    NucleusCopilotProviderError,
    NucleusCopilotRateLimitError,
    NucleusError,
    NucleusTimeoutError,
)

# Regex: strip *_API_KEY patterns so they never appear in user_message.
_API_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9_]*_API_KEY\b")
# Provider class names that must never appear in user-facing strings.
# `re.IGNORECASE` covers capitalized variants (Anthropic, OpenAI, Ollama,
# LiteLLM, ...) without enumerating every case combination by hand.
_BANNED_NAMES = re.compile(
    r"\b(litellm|anthropic|openai|ollama|"
    r"AnthropicError|OpenAIError|APIError|APIConnectionError|"
    r"BadRequestError|ServiceUnavailableError|AuthenticationError|"
    r"RateLimitError|ContentPolicyViolationError|Timeout)\b",
    re.IGNORECASE,
)


def _clean(msg: str) -> str:
    """Strip banned class names and API key patterns from a message string."""
    msg = _API_KEY_RE.sub("<API_KEY>", msg)
    msg = _BANNED_NAMES.sub("<provider>", msg)
    return msg.strip() or "(provider error)"


def translate_litellm_exception(exc: Exception) -> NucleusError:  # noqa: PLR0911
    """Translate a ``litellm.*`` exception to a typed ``NucleusError``.

    Mapping (ADR-015 §6):
    - ``litellm.AuthenticationError``          → NucleusCopilotAuthError   (NE4001)
    - ``litellm.RateLimitError``               → NucleusCopilotRateLimitError (NE4002)
    - ``litellm.APIError`` / connection / 5xx  → NucleusCopilotProviderError (NE4003)
    - ``litellm.ContentPolicyViolationError``   → NucleusCopilotContentFilterError (NE4004)
    - ``litellm.Timeout``                      → NucleusTimeoutError (NE3005, reused)

    User-facing ``user_message`` contains NO ``litellm`` / provider class names
    and NO ``*_API_KEY`` patterns. Full cause chain is in ``error.cause``.

    Docs: https://docs.litellm.ai/docs/exception_mapping
    """
    # Already translated — idempotent.
    if isinstance(exc, NucleusError):
        return exc

    # Lazy import: litellm is only imported at chat-time, never at boot.
    # Docs: https://docs.litellm.ai/docs/exception_mapping
    try:
        import litellm
    except ImportError:
        return NucleusCopilotProviderError(
            user_message="Copilot provider library is not installed.",
            fix_hint=(
                "The Copilot provider library is bundled with `pip install nucleus`. "
                "Reinstall the package and retry."
            ),
            cause=exc,
        )

    raw = str(exc) or "(provider error)"
    msg = _clean(raw)

    # litellm.Timeout — NOT litellm.TimeoutError per ai_hallucinations.md.
    # Docs: https://docs.litellm.ai/docs/exception_mapping
    if isinstance(exc, litellm.Timeout):
        return NucleusTimeoutError(
            user_message=f"Copilot request timed out. {msg}",
            fix_hint="The provider did not respond in time. Retry or use a local offline provider.",
            cause=exc,
        )

    # Content policy (subclass of BadRequestError — check before APIError).
    # Docs: https://docs.litellm.ai/docs/exception_mapping
    if isinstance(exc, litellm.ContentPolicyViolationError):
        return NucleusCopilotContentFilterError(
            user_message="Copilot request rejected by the provider's content policy.",
            fix_hint="Rephrase the question or remove context items that may trigger content filters.",
            cause=exc,
        )

    # Authentication failure.
    if isinstance(exc, litellm.AuthenticationError):
        return NucleusCopilotAuthError(
            user_message="Copilot authentication failed for the configured provider.",
            fix_hint=(
                "Check your API key environment variable for the configured provider. "
                "See https://nucleus.dev/errors/copilot-auth for the required variable names."
            ),
            cause=exc,
        )

    # Rate limit.
    if isinstance(exc, litellm.RateLimitError):
        return NucleusCopilotRateLimitError(
            user_message="Copilot was rate-limited by the provider. Retry in a moment.",
            fix_hint=(
                "Wait a few seconds and retry, or switch to `--provider ollama` "
                "for an offline path with no rate limits."
            ),
            cause=exc,
        )

    # General provider error (APIError, APIConnectionError, BadRequestError,
    # ServiceUnavailableError, and any other litellm exception).
    # Docs: https://docs.litellm.ai/docs/exception_mapping
    hint = (
        "The provider may be temporarily unavailable. Try a local provider for an offline fallback."
        if isinstance(exc, litellm.APIError)
        else "Check provider configuration and retry. A local provider is available for offline use."
    )
    return NucleusCopilotProviderError(
        user_message=f"Copilot provider returned an error. {msg}",
        fix_hint=hint,
        cause=exc,
    )
