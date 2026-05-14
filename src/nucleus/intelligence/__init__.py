"""Nucleus Intelligence layer — AI Copilot (v0.2+).

Layer 5 per ``nucleus_architecture_v4.1.md`` §7 (AI Copilot staging:
v0.2 = inline chat, CLI-only, single-turn; v0.5+ adds ``ctx.agent`` runtime).

Per ADR-015: the **only** public surface is :func:`chat` and
:class:`CopilotReply`. Internal helpers (``gather_context``,
``build_prompt``, ``translate_litellm_exception``) are private to this
package and must NOT be imported externally.

# Stability: Internal @ v0.2 → Beta @ v0.2 ship → Stable @ v0.5

Architecture ref: ``nucleus_architecture_v4.1.md`` §7.2 (v0.2 CLI chat MVP)
Decision: ``docs/decisions/ADR-015-ai-chat-mvp.md``
"""

from nucleus.intelligence.copilot import CopilotReply, chat

__all__ = ["CopilotReply", "chat"]
