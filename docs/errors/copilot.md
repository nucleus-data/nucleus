# Copilot Error Codes (NE4xxx)

> **Layer**: L3 Intelligence (AI Copilot v0.2+, `ctx.agent` v0.5+)
> **Range**: `NE4xxx` per ADR-006 §Decision + ADR-015 ratification 2026-05-13
> **Stability**: Beta tier (ADR-005 §2) — wording may change through v0.4; code-to-class binding permanent

---

## NE4001 — NucleusCopilotAuthError

**When it fires**: The configured AI provider rejected the API key or authentication token (HTTP 401 / 403).

**What the user sees**:
```
Error: Copilot authentication failed for the configured provider.
Fix:   Check that the relevant API key env var is set and valid
       (ANTHROPIC_API_KEY / OPENAI_API_KEY / OLLAMA_HOST).
Docs:  https://nucleus.dev/errors/copilot-auth
```

**How to fix**:
1. Set the appropriate environment variable before running `nucleus chat`:
   - Anthropic (default): `export ANTHROPIC_API_KEY=sk-ant-...`
   - OpenAI: `export OPENAI_API_KEY=sk-...`
   - Ollama (local, no key needed): `export OLLAMA_HOST=http://localhost:11434`
2. Verify the key is valid at the provider's dashboard.
3. For Ollama: ensure `ollama serve` is running (`ollama --version`).

**Provider status pages**:
- Anthropic: https://status.anthropic.com/
- OpenAI: https://status.openai.com/
- Ollama: local — check `ollama serve` logs

---

## NE4002 — NucleusCopilotRateLimitError

**When it fires**: The provider returned HTTP 429 (too many requests in the current window).

**What the user sees**:
```
Error: Copilot was rate-limited by the provider. Retry in a moment.
Fix:   Wait a few seconds and retry, or switch to --provider ollama
       for an offline path with no rate limits.
Docs:  https://nucleus.dev/errors/copilot-rate-limit
```

**How to fix**:
1. Wait 10–30 seconds and retry.
2. Switch to Ollama for development: `nucleus chat "<question>" --provider ollama`
3. If this happens repeatedly, check your API tier limits at the provider dashboard.

**Provider rate limit docs**:
- Anthropic: https://docs.anthropic.com/docs/en/api/rate-limits
- OpenAI: https://platform.openai.com/docs/guides/rate-limits

---

## NE4003 — NucleusCopilotProviderError

**When it fires**: The provider returned a server-side error (HTTP 5xx), a connection failure, a bad request error (non-content-filter), or any unmapped LiteLLM exception.

**What the user sees**:
```
Error: Copilot provider returned an error. <detail>
Fix:   The provider may be temporarily unavailable.
       Try --provider ollama for an offline fallback.
Docs:  https://nucleus.dev/errors/copilot-provider
```

**How to fix**:
1. Check the provider's status page (links in NE4001 above).
2. Retry after a few minutes.
3. Use `--provider ollama` for fully offline usage.
4. If the error persists, file a bug — the `cause` field in debug mode (`--debug`) contains the full original exception.

---

## NE4004 — NucleusCopilotContentFilterError

**When it fires**: The provider's content safety system rejected the request (`litellm.ContentPolicyViolationError`). This usually means the question or the injected project context triggered a content filter.

**What the user sees**:
```
Error: Copilot request rejected by the provider's content policy.
Fix:   Rephrase the question or remove context items that may trigger content filters.
Docs:  https://nucleus.dev/errors/copilot-content-filter
```

**How to fix**:
1. Rephrase the question to avoid triggering keywords.
2. If your error messages or asset names contain flagged content, consider renaming them.
3. Use Ollama (`--provider ollama`) which has more permissive (or configurable) content filters.

**Note**: Nucleus automatically redacts SQL, usernames, and absolute paths from the injected context (ADR-015 §4 / ADR-011 §3). Content filter triggers are typically from the question itself, not the context.

---

## NE4005 — NucleusBudgetExceededError

**When it fires**: The pre-flight cost estimate for the Copilot request exceeds the configured ceiling. This check happens **before any HTTP call** — no tokens are ever billed when this error fires.

**What the user sees**:
```
Error: Estimated cost $0.1234 exceeds the ceiling $0.10.
Fix:   Raise `copilot.cost_ceiling_usd` in nucleus_project.yaml,
       shorten the question, or switch to --provider ollama (free).
Docs:  https://nucleus.dev/errors/copilot-budget
```

**How to fix**:
1. Raise the ceiling in `nucleus_project.yaml`:
   ```yaml
   copilot:
     cost_ceiling_usd: 0.25  # default is 0.10
   ```
2. Shorten the question — fewer input tokens lower the estimate.
3. Use `--provider ollama` for zero-cost local inference.

**Why a pre-flight check?** Cost surprises are a real risk (ADR-015 §Risks row 4). The `len(prompt) // 4` token estimate is a heuristic (1 token ≈ 4 characters). The actual billed cost may differ slightly from the estimate.

---

## Related errors

- `NE3005` `NucleusTimeoutError` — reused for Copilot timeouts (ADR-015 §6). The provider did not respond within the configured `timeout_s` (default 30 s). Retry or increase the timeout in `nucleus_project.yaml`.
