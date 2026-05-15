# AI Copilot — LLM provider setup

Nucleus's AI Copilot calls [LiteLLM](https://docs.litellm.ai/) (`litellm==1.83.14`, see [`docs/compatibility.md`](../compatibility.md)), which routes requests to 100+ providers using a unified completion API.

Use this guide to configure API keys and models for `nucleus chat` and the Workbench Copilot panel (`nucleus workbench up`).

## How configuration flows

- **Provider and model** resolve in this order: CLI flags (`--provider`, `--model`) → `copilot` keys in `nucleus_project.yaml` → built-in defaults (`src/nucleus/intelligence/copilot.py`).
- **API keys** are not read from Nucleus config files. LiteLLM picks them up from normal provider environment variables (same names as upstream docs). Nucleus never logs key values.
- **Opt-in**: the first successful chat path prompts to send project metadata; consent is stored under `.nucleus/copilot_opt_in` or `copilot.opt_in` in `nucleus_project.yaml` (see [ADR-015](../decisions/ADR-015-ai-chat-mvp.md)).
- **Shell env files**: Nucleus does **not** auto-load `.env` or `.env.local`. Export variables in your shell, use your OS settings, or use a tool like [direnv](https://direnv.net/) if you keep secrets in a file.

## Quick check — is Copilot reachable?

```bash
nucleus chat --help
```

Run a one-line test (after keys and opt-in are set):

```bash
nucleus chat "What commands should I run next?"
```

Typical issues:

| Symptom | Meaning | Fix |
|--------|---------|-----|
| Help prints but chat says the provider library is missing | `litellm` import failed | Reinstall the matching Nucleus wheel/sdist so `litellm==1.83.14` is present (`pyproject.toml`). |
| Copilot opt-in declined | No consent for outbound context | Run again and accept the prompt, or set `copilot.opt_in: true` in `nucleus_project.yaml`. |
| Authentication / rate limit errors | Provider response | See [Troubleshooting](#troubleshooting-by-error-code) (NE4001 / NE4002). |

## First-class providers (CLI `--provider`)

The `nucleus chat` help documents three built-in provider names: `anthropic`, `openai`, and `ollama`. Azure and other LiteLLM backends work by setting `copilot.provider` / `copilot.model` in `nucleus_project.yaml` (see below).

### Common `nucleus_project.yaml` snippet

```yaml
copilot:
  opt_in: true
  provider: anthropic          # anthropic | openai | ollama | azure (azure: set model per LiteLLM)
  model: claude-3-5-haiku-20241022   # short id; Nucleus prefixes anthropic/ automatically
  cost_ceiling_usd: 0.10       # pre-flight estimate cap (default 0.10)
  output_token_budget: 1000    # max output tokens passed to LiteLLM (default 1000)
  timeout_s: 30               # request timeout seconds (default 30)
```

CLI overrides for one-off use:

```bash
nucleus chat "Hello" --provider openai --model gpt-4o-mini
```

---

## Provider 1 — OpenAI

LiteLLM expects the standard OpenAI API key environment variable:

```bash
# bash/zsh — set for the current shell before `nucleus chat` or `nucleus workbench up`
export OPENAI_API_KEY="sk-..."
```

`nucleus_project.yaml` example (model id without `openai/` prefix; that is how `_to_litellm_model` passes it through to LiteLLM):

```yaml
copilot:
  opt_in: true
  provider: openai
  model: gpt-4o-mini
```

```bash
nucleus chat "Summarize my asset graph" --provider openai
```

Model strings follow [LiteLLM OpenAI](https://docs.litellm.ai/docs/providers/openai) (`gpt-4o-mini`, `gpt-4o`, etc.).

---

## Provider 2 — Anthropic (CLI default)

Default provider in code is Anthropic. Set:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

```yaml
copilot:
  opt_in: true
  provider: anthropic
  model: claude-3-5-haiku-20241022
```

```bash
nucleus chat "Generate a check suggestion for my orders asset"
```

Nucleus converts that to LiteLLM form `anthropic/claude-3-5-haiku-20241022`. Other Claude model ids: see [LiteLLM Anthropic](https://docs.litellm.ai/docs/providers/anthropic).

---

## Provider 3 — Azure OpenAI

Nucleus maps `provider: azure` to LiteLLM by passing your `copilot.model` string through unchanged (`src/nucleus/intelligence/copilot.py` `_to_litellm_model`). Use LiteLLM’s `azure/<deployment_name>` convention.

Environment variables (from [LiteLLM Azure](https://docs.litellm.ai/docs/providers/azure)):

```bash
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://<your-resource>.openai.azure.com"
export AZURE_API_VERSION="2024-08-01-preview"   # match your Azure resource/deployment API version
```

`nucleus_project.yaml`:

```yaml
copilot:
  opt_in: true
  provider: azure
  model: azure/my-gpt4o-deployment    # deployment name after azure/
```

Test:

```bash
nucleus chat "Hello from Azure"
```

Optional Entra ID token auth is supported by LiteLLM via `AZURE_AD_TOKEN` (see same doc); Nucleus does not set those fields—it relies on LiteLLM reading the environment.

---

## Provider 4 — Local LLM via Ollama

1. Install and start [Ollama](https://ollama.com/).
2. Pull a model (example: Llama 3.1 8B).
3. Point LiteLLM at your daemon if not on localhost (default):

```bash
export OLLAMA_HOST="http://localhost:11434"
```

Defaults in Nucleus use `llama3.1:8b`; the Copilot prefixes `ollama/` for LiteLLM:

```yaml
copilot:
  opt_in: true
  provider: ollama
  model: llama3.1:8b
```

```bash
nucleus chat "Hello" --provider ollama
```

Trade-offs:

- No cloud API key; useful for offline or compliance-sensitive workstations.
- Smaller weights may hallucinate SQL or CLI suggestions—always verify before running suggested commands.

---

## Provider 5 — Together AI, Groq, Mistral (and the rest of the LiteLLM catalog)

The CLI `--provider` switch only lists `anthropic`, `openai`, and `ollama`, but LiteLLM still routes any **full model id** you place in `copilot.model`. For backends like Groq or Together:

1. Export the vendor key LiteLLM documents (examples—confirm names on [LiteLLM providers](https://docs.litellm.ai/docs/providers)):
   - Groq: `GROQ_API_KEY` ([Groq provider doc](https://docs.litellm.ai/docs/providers/groq))
   - Together AI: `TOGETHERAI_API_KEY` ([Together AI provider doc](https://docs.litellm.ai/docs/providers/togetherai))
   - Mistral AI: `MISTRAL_API_KEY` ([Mistral provider doc](https://docs.litellm.ai/docs/providers/mistral))
2. Set `copilot.model` to the exact LiteLLM model string (for example `groq/llama-3.3-70b-versatile`, `together_ai/togethercomputer/Llama-2-7B-32K-Instruct`, or `mistral/mistral-small-latest`).
3. Set `copilot.provider` to match a **pricing bucket** you configure under `copilot.pricing`, or accept that pre-flight **cost estimates** fall back to generic defaults until you add accurate per-million-token rates.

Example shape (illustrative model id — verify against current LiteLLM docs):

```yaml
copilot:
  opt_in: true
  provider: openai        # informational for pricing fallback only; LiteLLM uses the model prefix
  model: groq/llama-3.3-70b-versatile
  pricing:
    openai:
      input: 0.15        # tune to your provider’s actual $/MTok when you rely on ceilings
      output: 0.60
```

If unsure about naming, search your provider on the [providers index](https://docs.litellm.ai/docs/providers).

---

## Cost and token limits

These **`nucleus_project.yaml`** keys are enforced by `nucleus.intelligence.copilot.chat` (`src/nucleus/intelligence/copilot.py`):

| Key | Role |
|-----|------|
| `copilot.cost_ceiling_usd` | Blocks the HTTP call when the rough pre-flight estimate exceeds this value (`NucleusBudgetExceededError`, **NE4005**). Default `0.10`. |
| `copilot.output_token_budget` | Passed to LiteLLM as `max_tokens`. Default `1000`. |
| `copilot.pricing` | USD per million input/output tokens used for estimates and footer cost math. |

There is **no** `nucleus chat --stats` flag in the CLI today; inspect usage via the stderr footer printed after each reply (`Copilot: provider=… tokens=… cost=$…`) or via `nucleus chat "..." --json` for structured counts.

Daily spend caps enforced inside LiteLLM’s **proxy** are out of scope for the embedded CLI path ([LiteLLM proxy env](https://docs.litellm.ai/docs/proxy/configs) applies only if you run that proxy separately).

---

## Conversation persistence

v0.2 Copilot is **single-turn**: each `nucleus chat` invocation is independent (see [ADR-015](../decisions/ADR-015-ai-chat-mvp.md)). Neither the CLI nor `POST /api/chat` persists chat transcripts under `.nucleus/` beyond the consent flag `.nucleus/copilot_opt_in`. The browser Workbench keeps messages only while the SPA session lasts.

Clear or reset consent by deleting `.nucleus/copilot_opt_in` or toggling `copilot.opt_in` and re-running chat.

---

## Troubleshooting by error code

Stable bindings live in `src/nucleus/errors.py` (`NucleusCopilot*` + `NucleusBudgetExceededError`). Expanded narrative: [`docs/errors/copilot.md`](../errors/copilot.md).

| Code | Typical cause | Fix |
|------|----------------|-----|
| **NE4001** `NucleusCopilotAuthError` | Missing/invalid API key or Azure settings | Export the provider key or fix Azure env vars (`AZURE_*`). |
| **NE4002** `NucleusCopilotRateLimitError` | HTTP 429 from provider | Back off or switch (`--provider ollama` for local zero-quota inference). |
| **NE4003** `NucleusCopilotProviderError` | 5xx / bad request / network / LiteLLM setup | Check outage pages; verify deployment names; retry offline provider. |
| **NE4004** `NucleusCopilotContentFilterError` | Provider policy rejected prompt/context | Rephrase; remove sensitive words from asset names/errors in context. |
| **NE4005** `NucleusBudgetExceededError` | Pre-flight estimate over `cost_ceiling_usd` | Raise ceiling, shorten prompt, or use Ollama. |
| **NE3005** `NucleusTimeoutError` (reused) | Request exceeded `timeout_s` | Increase `copilot.timeout_s` or use a faster/local model. |
| **NE5001** `NucleusConfigError` | Opt-in declined, missing `litellm`, or invalid user input paths | Accept opt-in / reinstall dependencies / fix config per message. |

---

## Security

- Never commit secrets. Project templates ignore `.env` / `.env.*` (see `src/nucleus/templates/v01/gitignore`).
- Production deployments should inject keys via your platform’s secret store (OIDC-backed vaults, CI secret managers) rather than shell history.
- Rotate cloud keys on a regular cadence and monitor provider audit logs.

---

## Workbench integration

1. Export the same provider environment variables in the shell that launches the server.
2. Run `nucleus workbench up` (default [http://localhost:8765](http://localhost:8765) per `src/nucleus/workbench/cli.py`).
3. Open the Copilot panel (sparkle icon). UI calls `POST /api/chat`, which wraps `nucleus.intelligence.copilot.chat` — identical env + `nucleus_project.yaml` behavior as the CLI (`src/nucleus/workbench/api/chat.py`).

---

## See also

- [ADR-015 — AI Chat MVP](../decisions/ADR-015-ai-chat-mvp.md) — scope, privacy, LiteLLM decision
- [`docs/errors/copilot.md`](../errors/copilot.md) — NE4001–NE4005 + NE3005 Copilot timeout notes
- [`docs/swap/litellm.md`](../swap/litellm.md) — composability / swap plan
- [LiteLLM providers](https://docs.litellm.ai/docs/providers) — authoritative model strings + env names
- [LiteLLM proxy configuration](https://docs.litellm.ai/docs/proxy/configs) — only if you operate the optional proxy
