---
title: NE4xxx — Intelligence Layer Errors
description: Errors from the Intelligence layer — AI Copilot, agent runtime (v0.2+).
---

# NE4xxx — Intelligence Layer Errors

Errors from the Intelligence layer — AI Copilot and agent runtime (architecture v4.1 §7). These errors only occur when using `nucleus chat` (v0.2+) or the Copilot API.

---

## NE4001 — NucleusCopilotAuthError {#ne4001}

LLM provider authentication failed.

**Fix:** Check your API key environment variable:

```bash
# Anthropic
echo $ANTHROPIC_API_KEY

# OpenAI
echo $OPENAI_API_KEY

# Set if missing
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## NE4002 — NucleusCopilotRateLimitError {#ne4002}

LLM provider rate limit hit.

**Fix:** Wait 30-60 seconds and retry. If persistent, switch providers:

```bash
nucleus chat "..." --provider openai
nucleus chat "..." --provider ollama   # local, no rate limits
```

---

## NE4003 — NucleusCopilotProviderError {#ne4003}

LLM provider returned a 5xx error.

**Fix:** This is a transient provider issue. Retry after a few minutes. Check provider status pages:
- Anthropic: https://status.anthropic.com
- OpenAI: https://status.openai.com

---

## NE4004 — NucleusCopilotContentFilterError {#ne4004}

The response was blocked by the provider's content filter.

**Fix:** Rephrase your question to be more specific about data engineering context.

---

## NE4005 — NucleusBudgetExceededError {#ne4005}

Estimated cost of the Copilot call exceeds your configured ceiling.

**Fix:**

```yaml
# nucleus_project.yaml — increase the ceiling
copilot:
  max_cost_usd_per_call: 0.25   # default: 0.10
```

Or shorten your question to reduce token count.
