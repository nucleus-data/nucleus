---
title: Use AI Copilot
description: nucleus chat — single-turn AI assistance with privacy gate, opt-in, and local Ollama support.
---

# Use AI Copilot

The Nucleus AI Copilot is a single-turn assistant that answers questions about your project, helps write assets, and explains errors. It is **opt-in**, **privacy-gated**, and ships in v0.2.

!!! info "v0.2 feature"
    `nucleus chat` is available in v0.2+. It is wired in v0.1 but raises `NucleusFeatureDeferredError` (NE5008) with a "v0.2 ships active chat" message.

## Enabling the Copilot

```bash
nucleus chat "What assets depend on raw.orders?"
```

On first use, Nucleus displays the **privacy gate**:

```
Nucleus AI Copilot — Privacy Gate

Before continuing, confirm:
1. Project context (asset names + schema) will be sent to your LLM provider.
2. No raw data rows are ever sent. Only metadata (asset names, schemas, error messages).
3. You are responsible for your LLM provider's data retention policies.

Type 'yes' to continue, 'no' to cancel: yes

Saved consent to .nucleus/copilot_consent.json
```

## Providers

| Provider | Flag | Env var |
|----------|------|---------|
| Anthropic Claude (default) | `--provider anthropic` | `ANTHROPIC_API_KEY` |
| OpenAI | `--provider openai` | `OPENAI_API_KEY` |
| Ollama (local) | `--provider ollama` | `OLLAMA_HOST` (default `http://localhost:11434`) |

```bash
# Use OpenAI
OPENAI_API_KEY=sk-... nucleus chat "Explain NE1002" --provider openai

# Use local Ollama (no data leaves your machine)
nucleus chat "Show me how to write an incremental asset" \
  --provider ollama --model llama3
```

## Example prompts

```bash
# Ask about your asset graph
nucleus chat "Which assets depend on raw.orders?"

# Get an error explained
nucleus chat "I got NE1002 on mart.daily_revenue. What does it mean?"

# Generate an asset scaffold
nucleus chat "Write a @nucleus.asset that computes 7-day rolling average revenue"

# Debug a query
nucleus chat "Why is my daily revenue query returning duplicates?"
```

## Cost ceiling

Before any API call, Nucleus estimates the token count and checks it against your configured cost ceiling:

```yaml
# nucleus_project.yaml
copilot:
  max_cost_usd_per_call: 0.10   # abort if estimated cost > $0.10
```

If the estimate exceeds the ceiling, the call is aborted with `NucleusBudgetExceededError` (NE4005).

## What context is sent

Nucleus injects:
- Asset graph summary (asset keys + dependencies)
- Recent materialization errors (NE-codes + user messages, never raw data)
- Schema of assets mentioned in the question

Nucleus never sends:
- Raw data rows
- Connection strings or secrets
- Personal information

## Errors

| Error | Code | Fix |
|-------|------|-----|
| `NucleusCopilotAuthError` | NE4001 | Check your API key env variable |
| `NucleusCopilotRateLimitError` | NE4002 | Wait and retry; or switch provider |
| `NucleusBudgetExceededError` | NE4005 | Increase `max_cost_usd_per_call` or shorten the question |

## Related

- [CLI reference: nucleus chat](../cli-reference/chat.md)
- [ADR-015: AI chat MVP](../governance/architecture-decisions.md)
