# Swap Target: LiteLLM → Direct Provider SDKs

> **Component**: `litellm==1.83.14` (Intelligence layer Copilot wrap)
> **Tier**: Tier 2 — Intelligence engine wrap (not immortal; LLM economics volatile)
> **ADR**: [ADR-015](../decisions/ADR-015-ai-chat-mvp.md)
> **Research**: [docs/internal/research/ai_copilot.md](../research/ai_copilot.md) §12
> **Composability rule**: interface + smoke tests maintained always; full swap built **on-demand only**
> (Composability by Constitution §3 — do NOT pre-implement; this doc records the swap plan)

## Trigger conditions (any one fires the on-demand swap build)

1. **License pivot**: LiteLLM changes from MIT to a non-GREEN tier (ELv2, SSPL, BUSL) — the most likely scenario given BerriAI's VC-backed trajectory
2. **Vendor death / project abandonment**: LiteLLM stops maintenance for >6 months + no active fork
3. **Performance regression >2×**: Copilot round-trip p50 exceeds 2× the baseline (>10 s p50) attributable to LiteLLM overhead
4. **Breaking API change** that requires >200 LOC rewrite of `src/nucleus/intelligence/copilot.py`

## Current swap interface (always maintained)

The swap interface is LiteLLM itself. LiteLLM's model-id string switches provider:

```python
# Anthropic → litellm.completion(model="anthropic/claude-3-5-haiku-20241022", ...)
# OpenAI    → litellm.completion(model="gpt-4o-mini", ...)
# Ollama    → litellm.completion(model="ollama/llama3.1:8b", ...)
```

Zero code change needed for provider swaps — config string only. This IS the composability interface.

## Smoke tests (always run in CI)

`tests/intelligence/test_copilot_smoke.py` — 5 tests:
- One mocked round-trip per provider (Anthropic / OpenAI / Ollama)
- Asserts `model=` kwarg flows through correctly per provider
- No network calls; CI-safe

`tests/upgrade_smoke/test_litellm.py` — runs on every litellm pin bump:
- Asserts `response.choices[0].message.content` shape stability
- Asserts `litellm.Timeout` exists (NOT `litellm.TimeoutError`)
- Asserts all exception classes used by `translate.py` still exist

## On-demand swap implementation (~200 LOC)

When a trigger fires, build this replacement inside `src/nucleus/intelligence/copilot.py`:

### Anthropic (direct SDK)
```python
# Docs: https://docs.anthropic.com/en/api/getting-started
# Pin: anthropic==<latest at swap time>
import anthropic  # noqa: PLC0415
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
response = client.messages.create(
    model=model,
    max_tokens=max_out,
    messages=[{"role": "user", "content": prompt}],
)
text = response.content[0].text
tokens_in = response.usage.input_tokens
tokens_out = response.usage.output_tokens
```

### OpenAI (direct SDK)
```python
# Docs: https://platform.openai.com/docs/api-reference/chat
# Pin: openai==<latest at swap time>
import openai  # noqa: PLC0415
client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}],
    max_tokens=max_out,
)
text = response.choices[0].message.content
tokens_in = response.usage.prompt_tokens
tokens_out = response.usage.completion_tokens
```

### Ollama (direct HTTP)
```python
# Docs: https://github.com/ollama/ollama/blob/main/docs/api.md
# No SDK needed — stdlib httpx already pinned
import httpx  # noqa: PLC0415  (already pinned httpx==0.28.1)
host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
r = httpx.post(f"{host}/api/chat", json={
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
}, timeout=timeout)
r.raise_for_status()
text = r.json()["message"]["content"]
tokens_in = r.json().get("prompt_eval_count", len(prompt) // 4)
tokens_out = r.json().get("eval_count", len(text) // 4)
```

### Exception mapping replacement (~30 LOC)
Replace `translate.py`'s litellm imports with provider-specific exception types:
- `anthropic.AuthenticationError` → `NucleusCopilotAuthError`
- `anthropic.RateLimitError` → `NucleusCopilotRateLimitError`
- `openai.AuthenticationError` → `NucleusCopilotAuthError`
- `httpx.TimeoutException` → `NucleusTimeoutError`
- `httpx.HTTPStatusError` (5xx) → `NucleusCopilotProviderError`

## Migration path

1. File an ADR referencing this doc + citing the trigger condition
2. Replace `litellm.completion(...)` calls in `copilot.py` with the per-provider direct calls above
3. Replace `translate.py`'s litellm imports with provider-specific exception types
4. Remove `litellm==<pin>` from `pyproject.toml`
5. Add the direct SDK pins (anthropic + openai) and update `docs/compatibility.md`
6. Run `tests/intelligence/` + `tests/upgrade_smoke/test_litellm.py` (delete the latter after swap)
7. Update `docs/swap/litellm.md` to "SWAPPED" status

Total estimated effort: ~4 hours (one focused engineer).
