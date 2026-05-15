---
title: nucleus chat
description: Single-turn AI Copilot — v0.2 feature.
---

# `nucleus chat`

Single-turn AI Copilot. <span class="badge badge-beta">Beta</span> <span class="badge badge-v05">v0.2+</span>

## Synopsis

```
nucleus chat "<question>" [--provider anthropic|openai|ollama] [--model ID] [--json]
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `<question>` | Required | Your question |
| `--provider` | `anthropic` | LLM provider: `anthropic`, `openai`, `ollama` |
| `--model ID` | Provider default | Model ID override |
| `--json` | false | Return structured JSON instead of Markdown |

## Providers and env vars

| Provider | Env var | Model default |
|----------|---------|---------------|
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `ollama` | `OLLAMA_HOST` (default `http://localhost:11434`) | `llama3` |

## Privacy gate

On first use, Nucleus displays an opt-in consent prompt. You must type `yes` to continue. Consent is stored in `.nucleus/copilot_consent.json`.

Data sent: asset keys, schemas, recent error messages. **Raw data rows are never sent.**

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusFeatureDeferredError` | NE5008 | Called in v0.1 — ships in v0.2 |
| `NucleusCopilotAuthError` | NE4001 | Invalid API key |
| `NucleusCopilotRateLimitError` | NE4002 | Provider rate limit |
| `NucleusBudgetExceededError` | NE4005 | Estimated cost exceeds ceiling |

## Examples

```bash
# Default provider (Anthropic)
nucleus chat "Which assets depend on raw.orders?"

# Local Ollama (no data leaves machine)
nucleus chat "Explain NE1002" --provider ollama --model llama3

# JSON output
nucleus chat "List all assets with @daily schedule" --json
```

## Related

- [Guide: Use AI Copilot](../guides/use-ai-copilot.md)
- [ADR-015: AI chat MVP](../governance/architecture-decisions.md)
