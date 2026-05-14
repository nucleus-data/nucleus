"""Nucleus AI Copilot — single-turn chat against the project context.

Public surface: :func:`chat` + :class:`CopilotReply`.

Per ADR-015 §1: single-turn synchronous `nucleus chat "<question>"`.
Privacy: opt-in gate mirrors ADR-011 §1; NO outbound bytes before opt-in.
Cost: pre-flight ceiling enforced BEFORE any HTTP call (ADR-015 §4).

Docs (verified 2026-05-13 per AGENTS.md §11.12):
  LiteLLM Getting Started: https://docs.litellm.ai/docs/
  LiteLLM completion output: https://docs.litellm.ai/docs/completion/output
  LiteLLM exception mapping: https://docs.litellm.ai/docs/exception_mapping
  LiteLLM providers: https://docs.litellm.ai/docs/providers

Architecture ref: ``nucleus_architecture_v4.1.md`` §7.2 + ADR-015
Pin: ``litellm==1.83.14`` (single new runtime dep per AGENTS.md §11.13)

# Stability: Beta
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml  # type: ignore[import-untyped]

from nucleus.errors import (
    NucleusBudgetExceededError,
    NucleusConfigError,
)
from nucleus.intelligence.context import gather_context
from nucleus.intelligence.translate import translate_litellm_exception

# Default configuration (per ADR-015 §4 + §7).
_DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-3-5-haiku-20241022",  # NEEDS VERIFICATION: verify model ID at ratification
    "openai": "gpt-4o-mini",                    # NEEDS VERIFICATION: verify model ID at ratification
    "ollama": "llama3.1:8b",                    # NEEDS VERIFICATION: verify model + memory at ratification
}
_DEFAULT_INPUT_TOKENS = 2000
_DEFAULT_OUTPUT_TOKENS = 1000
_DEFAULT_COST_CEILING = 0.10

# Rough per-token pricing in USD per 1M tokens (NEEDS VERIFICATION at ratification).
# Baked here as defaults only; override via nucleus_project.yaml copilot.pricing.
_PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    "anthropic": {"input": 0.80, "output": 4.00},     # claude-3-5-haiku approximate
    "openai": {"input": 0.15, "output": 0.60},         # gpt-4o-mini approximate
    "ollama": {"input": 0.0, "output": 0.0},            # local — always free
}

_OPT_IN_FILE = ".nucleus/copilot_opt_in"


@dataclass(frozen=True)
class CopilotReply:
    """Frozen result of a single-turn Copilot exchange.

    Per ADR-015 §1 + ADR-005 §3 (frozen=True from first ship).

    # Stability: Beta
    """

    text: str
    suggested_command: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    provider: str
    model: str

    error_code: ClassVar[str] = "reply"  # not a NucleusError; satisfies type completeness only


def _locate_project_root(start: Path | None) -> Path:
    """Walk up to find nucleus_project.yaml; return its parent."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents)[:4]:
        if (candidate / "nucleus_project.yaml").is_file():
            return candidate
    return here


def _load_copilot_config(project_root: Path) -> dict[str, Any]:
    """Read [copilot] section from nucleus_project.yaml (default: empty dict)."""
    cfg_path = project_root / "nucleus_project.yaml"
    if not cfg_path.exists():
        return {}
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data.get("copilot") or {}


def _is_opted_in(project_root: Path, copilot_cfg: dict[str, Any]) -> bool:
    """Return True if the user has previously opted in to sending context."""
    # Persistent opt-in file takes precedence.
    opt_in_file = project_root / _OPT_IN_FILE
    if opt_in_file.exists():
        return opt_in_file.read_text(encoding="utf-8").strip().lower() == "true"
    # YAML config flag.
    return bool(copilot_cfg.get("opt_in", False))


def _persist_opt_in(project_root: Path, value: bool) -> None:
    """Persist the opt-in choice to .nucleus/copilot_opt_in."""
    try:
        opt_in_file = project_root / _OPT_IN_FILE
        opt_in_file.parent.mkdir(parents=True, exist_ok=True)
        opt_in_file.write_text("true" if value else "false", encoding="utf-8")
    except OSError:
        pass  # Non-fatal; user can re-consent on next call.


def _estimate_cost(
    prompt: str,
    max_output_tokens: int,
    provider: str,
    pricing: dict[str, dict[str, float]],
) -> float:
    """Rough pre-flight cost estimate in USD (no network call required)."""
    input_tokens = len(prompt) // 4  # 1 token ≈ 4 chars heuristic
    rates = pricing.get(provider, pricing.get("anthropic", {"input": 1.0, "output": 5.0}))
    return (
        input_tokens * rates["input"] / 1_000_000
        + max_output_tokens * rates["output"] / 1_000_000
    )


def _extract_suggested_command(text: str) -> str | None:
    """Return the first ``Run: nucleus <cmd>`` suggestion from the reply."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("Run: nucleus ", "Run:nucleus ")):
            return stripped.removeprefix("Run:").strip()
    return None


def _build_prompt(question: str, ctx: dict[str, Any]) -> str:
    """Render the Jinja2 system prompt template with project context.

    Docs: https://jinja.palletsprojects.com/en/3.1.x/  (jinja2==3.1.5)
    """
    from importlib.resources import files as _res_files

    import jinja2

    tmpl_bytes = (_res_files("nucleus.intelligence.prompts") / "system.j2").read_text(encoding="utf-8")
    env = jinja2.Environment(autoescape=False, undefined=jinja2.Undefined)
    template = env.from_string(tmpl_bytes)
    return template.render(question=question, **ctx)


def chat(
    question: str,
    *,
    project_root: Path | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> CopilotReply:
    """Single-turn AI Copilot chat against the current Nucleus project.

    Injects project metadata (asset graph, recent errors) as context.
    Enforces opt-in gate and pre-flight cost ceiling before any HTTP call.

    Per ADR-015 §1; wraps LiteLLM for provider abstraction.
    Docs: https://docs.litellm.ai/docs/

    Args:
        question:     The user's question (max ~2K tokens).
        project_root: Path to the Nucleus project root. Auto-detected if None.
        provider:     Override the configured provider (anthropic/openai/ollama).
        model:        Override the configured model id string.

    Returns:
        CopilotReply with text, optional suggested command, token counts,
        cost_usd (0.0 for Ollama), provider, and model.

    Raises:
        NucleusConfigError        if opt-in gate is declined.
        NucleusBudgetExceededError if estimated cost > ceiling (pre-flight).
        NucleusCopilotAuthError    if API key / token rejected (NE4001).
        NucleusCopilotRateLimitError if rate-limited (NE4002).
        NucleusCopilotProviderError  if provider returns 5xx or unmapped error (NE4003).
        NucleusCopilotContentFilterError if content policy violated (NE4004).
        NucleusTimeoutError       if request times out (NE3005, reused).
    """
    root = _locate_project_root(project_root)
    copilot_cfg = _load_copilot_config(root)

    # Resolve provider and model from args > config > defaults.
    resolved_provider = provider or copilot_cfg.get("provider", _DEFAULT_PROVIDER)
    resolved_model = model or copilot_cfg.get("model", _DEFAULT_MODELS.get(resolved_provider, ""))
    if not resolved_model:
        resolved_model = _DEFAULT_MODELS.get(resolved_provider, "anthropic/claude-3-5-haiku-20241022")

    # For LiteLLM: prepend provider prefix when using Anthropic/OpenAI.
    # Ollama uses "ollama/<model>" format.
    # Docs: https://docs.litellm.ai/docs/providers
    litellm_model = _to_litellm_model(resolved_provider, resolved_model)

    # === OPT-IN GATE (ADR-015 §4 privacy bedrock) ===
    # NO outbound bytes before the user consents.
    if not _is_opted_in(root, copilot_cfg):
        import typer

        try:
            confirmed = typer.confirm(
                f"[Copilot] Send project metadata to {resolved_provider}?",
                default=False,
            )
        except Exception:
            confirmed = False
        _persist_opt_in(root, confirmed)
        if not confirmed:
            raise NucleusConfigError(
                user_message="Copilot opt-in declined. No data was sent.",
                fix_hint=(
                    "To use Copilot, re-run `nucleus chat` and accept the prompt, "
                    "or set `copilot.opt_in: true` in nucleus_project.yaml."
                ),
            )

    # Gather project context (privacy redactions applied inside gather_context).
    ctx = gather_context(root)

    # Build the rendered system prompt.
    prompt = _build_prompt(question, ctx)

    # === PRE-FLIGHT COST CHECK (ADR-015 §4) ===
    max_out = int(copilot_cfg.get("output_token_budget", _DEFAULT_OUTPUT_TOKENS))
    pricing = copilot_cfg.get("pricing", _PRICING_PER_MTOK)
    if not isinstance(pricing, dict):
        pricing = _PRICING_PER_MTOK
    cost_ceiling = float(copilot_cfg.get("cost_ceiling_usd", _DEFAULT_COST_CEILING))
    cost_estimate = _estimate_cost(prompt, max_out, resolved_provider, pricing)
    if cost_estimate > cost_ceiling:
        raise NucleusBudgetExceededError(
            user_message=(
                f"Estimated cost ${cost_estimate:.4f} exceeds the ceiling ${cost_ceiling:.2f}."
            ),
            fix_hint=(
                "Raise `copilot.cost_ceiling_usd` in nucleus_project.yaml, "
                "shorten the question, or switch to `--provider ollama` (free)."
            ),
        )

    timeout = float(copilot_cfg.get("timeout_s", 30.0))

    # === LLM CALL (lazy import — never imported at boot) ===
    # Docs: https://docs.litellm.ai/docs/
    try:
        import litellm
    except ImportError as exc:
        raise NucleusConfigError(
            user_message="The Copilot provider library is not installed.",
            fix_hint=(
                "The Copilot provider library is bundled with `pip install nucleus`. "
                "Reinstall the package and retry, or use `--provider ollama` for an offline path."
            ),
            cause=exc,
        ) from exc

    try:
        # Docs: https://docs.litellm.ai/docs/
        response = litellm.completion(  # type: ignore[attr-defined]
            model=litellm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_out,
            timeout=timeout,
        )
    except Exception as exc:
        raise translate_litellm_exception(exc) from exc

    # Parse response per OpenAI Chat Completions shape.
    # Docs: https://docs.litellm.ai/docs/completion/output
    text: str = response.choices[0].message.content or ""  # type: ignore[union-attr]
    usage = getattr(response, "usage", None)
    tokens_in = int(getattr(usage, "prompt_tokens", 0) or (len(prompt) // 4))
    tokens_out = int(getattr(usage, "completion_tokens", 0) or (len(text) // 4))
    # Cost: 0.0 for Ollama; approximate for cloud providers.
    if resolved_provider == "ollama":
        actual_cost = 0.0
    else:
        rates = pricing.get(resolved_provider, {"input": 1.0, "output": 5.0})
        if not isinstance(rates, dict):
            rates = {"input": 1.0, "output": 5.0}
        actual_cost = (
            tokens_in * float(rates.get("input", 0)) / 1_000_000
            + tokens_out * float(rates.get("output", 0)) / 1_000_000
        )

    suggested = _extract_suggested_command(text)

    # ADR-015 §4 disclosure: one-line footer to stderr.
    print(
        f"Copilot: provider={resolved_provider} tokens={tokens_in}+{tokens_out} cost=${actual_cost:.6f}",
        file=sys.stderr,
    )

    return CopilotReply(
        text=text,
        suggested_command=suggested,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=actual_cost,
        provider=resolved_provider,
        model=resolved_model,
    )


def _to_litellm_model(provider: str, model: str) -> str:
    """Construct the LiteLLM model string from provider + model.

    Docs: https://docs.litellm.ai/docs/providers
    """
    if provider == "ollama":
        return f"ollama/{model}" if not model.startswith("ollama/") else model
    if provider == "anthropic":
        return f"anthropic/{model}" if not model.startswith("anthropic/") else model
    if provider in ("openai", "azure"):
        return model  # OpenAI models don't need prefix in LiteLLM
    return model
