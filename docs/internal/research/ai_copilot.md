# AI Copilot — Research Notes (v0.2 MVP Design)

> **Pin candidate**: `litellm==1.83.14` (released 2026-04, verified on PyPI 2026-05-13) — single new runtime dep wrapping 100+ provider APIs in OpenAI Chat-Completions shape.  •  **License**: MIT (LiteLLM); MIT (Anthropic SDK 0.101.0); Apache-2.0 (OpenAI SDK 2.36.0); MIT (Ollama 0.6.2).  •  **JVM-free**: YES — all pure Python.
> **Status in Nucleus**: **v0.2 Intelligence Layer 5** per `docs/specs/nucleus_architecture_v4.1.md` §7.2 (4-week chat MVP). Not in v0.1. v0.5+ adds the `ctx.agent` runtime + lineage-aware Copilot (§7.3, §7.4).
> **Research date**: 2026-05-13 — verified against AI training cutoff caveat per AGENTS.md §11.12.
> **Used in (planned)**: `src/nucleus/intelligence/copilot.py` — the only module that imports `litellm`; `cli/commands/chat.py` (v0.2) calls `copilot.chat(question)` and prints.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening the v0.2 implementation PR or any major-version upgrade of `litellm`. The LLM-SDK landscape moves at minor-version-per-week pace; this doc reflects **PyPI state on 2026-05-13** and **must be re-verified at the v0.2 ADR-015 ratification gate**.

---

## §1. What "AI Copilot" means for Nucleus

Per `docs/specs/nucleus_architecture_v4.1.md` §7 + Forbidden Mental Models in `.cursor/rules/nucleus.mdc`: Nucleus is **AI-assisted**, not the banned framings. We **use** models; we do **not** host, train, or run agent frameworks (Hard Constraint #7). The v0.2 Copilot is a thin wrapper around (a) an LLM HTTP client and (b) auto-injected project context — no more. It is a CLI feature, not a product headline.

Concretely: zero multi-step autonomous loops, zero tool-calls, zero RAG framework, zero vector store, zero memory beyond what each invocation injects. Single round-trip. Inline context. This is the Anti-Over-Engineering ceiling for v0.2 (`.cursor/rules/nucleus.mdc` §Anti-Over-Engineering: *"no speculative code … if there is no v0.1 caller today, the code is not added today"*).

The v0.5+ `ctx.agent` sandbox (v4.1 §7.3) is a **separate ADR**, not in scope here. v0.7+ lineage-aware Copilot (v4.1 §7.4) is **separate ADR**, not in scope here.

---

## §2. v0.2 MVP scope (CLI-only, single-turn)

| Aspect | Decision |
|---|---|
| Surface | `nucleus chat "<question>"` — single CLI command, eighth command (after the v0.1 seven per AGENTS.md §1). Workbench chat (v4.1 §7.2 wording) **de-scoped from v0.2** to v0.3 per Anti-Over-Engineering (Workbench shell adds its own 4-6 weeks). |
| Mode | Single-turn synchronous request → reply. No multi-turn history file. No tool calls. |
| Auto-inject | (a) `nucleus_project.yaml`; (b) asset graph summary — `asset_key` + columns + freshness; (c) last 3 lines of `.nucleus/errors.log`. NO data values; NO source code; NO secrets. |
| Output | Plain text to stdout via `rich==13.9.4` markdown rendering (already pinned). Optional second-line: a single `nucleus <cmd>` suggestion when the reply explicitly proposes a command. |
| Latency target | ≤ 5 s p50 end-to-end. Provider-dependent — Anthropic Messages typical 2-4 s for ≤ 2K-token prompts ([rate-limits docs](https://docs.anthropic.com/docs/en/api/rate-limits)). Ollama local depends on model + hardware. |
| Token budget | Hard ceiling: 2K input + 1K output by default. Configurable via `chat.token_budget` in `nucleus.toml`. |
| Cost ceiling | Hard per-query ceiling: `0.10 USD-equivalent` default; refuse the call (`NucleusBudgetExceededError` per §8 below) if pre-estimate exceeds. Configurable. |
| Privacy default | **Opt-in to send context** mirroring ADR-011 telemetry. First `nucleus chat` invocation prompts `[y/N]: send project metadata to <provider>?` and persists choice to `.nucleus/copilot_opt_in`. Ollama path is opt-in to localhost only; no remote bytes ever. |

Out of v0.2 (explicit, per AGENTS.md §10 r4): multi-turn, tool-calls, lineage-aware context, schema-aware completion, fine-tuning, agent runtime, vector retrieval, semantic graph queries, replay/time-travel debugger (v4.1 §7.4-§7.6 — all v0.5+).

---

## §3. LLM provider abstraction

Three first-class providers, one wrap.

### §3.1 Anthropic Claude API — recommended cloud default

| Field | Value |
|---|---|
| SDK pin candidate | `anthropic==0.101.0` (2026-05-11) — `<https://pypi.org/project/anthropic/>` |
| License | MIT |
| Python | `>=3.9` (our `>=3.11,<3.13` satisfies) |
| Endpoint | `POST https://api.anthropic.com/v1/messages` ([Messages API](https://docs.anthropic.com/docs/en/api/messages)) |
| Auth | `x-api-key` header from `ANTHROPIC_API_KEY` env ([Auth docs](https://docs.anthropic.com/docs/en/manage-claude/authentication)) |
| Canonical SDK call | `client.messages.create(model=..., max_tokens=..., messages=[...])` ([Getting started](https://docs.anthropic.com/en/api/getting-started)) |
| Errors | Documented at [errors](https://docs.anthropic.com/docs/en/api/errors); auth → 401, rate → 429, content filter → 400 with `error.type`. |
| Pricing | Per-token; see [pricing](https://docs.anthropic.com/docs/en/build-with-claude/pricing). **NEEDS VERIFICATION** for the exact 2026-05 numbers — pin into `nucleus.toml.copilot.cost_per_input_mtok` at v0.2 implementation time. |
| Model surface | [Models docs](https://docs.anthropic.com/docs/en/build-with-claude/models); v0.2 default = mid-tier (Sonnet-class) for cost/latency balance. **NEEDS VERIFICATION** for exact model id at v0.2 implementation time (Anthropic re-IDs frequently). |

Pros: highest reasoning quality among the three providers (Nucleus is an engineering tool; reply quality > latency); good streaming if v0.3 adds it; SDK is stable (v0.7x → v0.101.x is incremental, no breaking renames at Messages surface). Cons: hard dependency on cloud connectivity; cost compounds in heavy use; provider lock-in unless wrapped (§3.4 fixes this).

### §3.2 OpenAI API — alternative cloud

| Field | Value |
|---|---|
| SDK pin candidate | `openai==2.36.0` — `<https://pypi.org/project/openai/>` |
| License | Apache-2.0 |
| Python | `>=3.9` |
| Endpoints | [Responses API](https://platform.openai.com/docs/api-reference/responses) (new primary); [Chat Completions](https://platform.openai.com/docs/api-reference/chat) ("supported indefinitely" per SDK readme) |
| Auth | `OPENAI_API_KEY` env |
| Errors | [error-codes](https://platform.openai.com/docs/guides/error-codes) — `AuthenticationError`, `RateLimitError`, `APIError`. |
| Pricing | [pricing](https://platform.openai.com/docs/pricing). **NEEDS VERIFICATION** for exact 2026-05 numbers. |
| Models | [models docs](https://platform.openai.com/docs/models). |

Pros: ubiquitous; widest tool-call ecosystem if we ever add it (v0.5+); SDK Apache-2.0 license is GREEN-tier per ADR-007 (vs MIT for Anthropic — both green). Cons: same lock-in risk; LiteLLM wraps it identically (§3.4).

### §3.3 Ollama — local / private / offline default for v0.2 power users

| Field | Value |
|---|---|
| SDK pin candidate | `ollama==0.6.2` (2026-04-29) — `<https://pypi.org/project/ollama/>` |
| License | MIT |
| Python | `>=3.8` |
| Server | User runs `ollama serve` separately (binary install from `<https://ollama.com>`); default port `11434` ([REST API](https://github.com/ollama/ollama/blob/main/docs/api.md)). |
| Canonical SDK call | `ollama.chat(model='gemma3', messages=[{"role": "user", "content": ...}])` — returns `ChatResponse`. |
| Errors | `ollama.ResponseError` with `status_code`. |
| Hardware | `llama3.1:8b` ≈ 5 GB RAM (4-bit quant); `gemma3:4b` ≈ 3 GB. **NEEDS VERIFICATION** — exact memory budget depends on quant + ctx-window; refer to per-model card on `<https://ollama.com/library>` before recommending defaults. |

Pros: **zero outbound bytes** (Constraint #10's privacy-first principle, mirrors ADR-011 §6 bedrock); free per-query cost; works offline. Cons: reply quality below cloud frontier models for complex reasoning; user must install + run a separate binary (we do NOT ship Ollama — that would violate Hard Constraint #7 "no agent hosting platform"; we only **call** the user-hosted server).

Hard Constraint #7 check passes: Ollama is the *user's* choice to host locally. We never ship a model, never train one, never serve one. We make one HTTP call to a user-managed endpoint.

### §3.4 Decision: LiteLLM as the abstraction layer

> **Wrap LiteLLM as the single Python entry point. All three providers are configured by string model id (`anthropic/<id>`, `openai/<id>`, `ollama/<id>`). Provider swap = config edit, zero code change.**

LiteLLM is the canonical wrap-not-build choice (Pillar #2 Composability):

| LiteLLM property | Value |
|---|---|
| Pin candidate | `litellm==1.83.14` ([PyPI](https://pypi.org/project/litellm/)) |
| License | MIT |
| Python | `>=3.10,<3.14` (our `>=3.11,<3.13` is inside) |
| API | `from litellm import completion; completion(model="anthropic/<id>", messages=[...])` ([Getting Started](https://docs.litellm.ai/docs/)) |
| Response shape | OpenAI Chat-Completions format: `response.choices[0].message.content` ([output format](https://docs.litellm.ai/docs/completion/output)) — uniform across all 100+ providers, eliminates per-provider parsing in Nucleus |
| Exception mapping | All provider errors mapped to OpenAI exception types: `litellm.AuthenticationError`, `RateLimitError`, `APIError` ([exception_mapping](https://docs.litellm.ai/docs/exception_mapping)) — one error-translation handler covers all three providers |
| Providers wrapped | 100+ ([providers](https://docs.litellm.ai/docs/providers)) — includes Anthropic, OpenAI, Ollama (local), Bedrock, Vertex, Azure OpenAI |
| Cost tracking | Built-in `response_cost` callback ([cost tracking](https://docs.litellm.ai/docs/proxy/cost_tracking)) — directly feeds the v0.5+ Cost Meter (§10) |

Anti-Over-Engineering note: **One pin gets us three providers + cost tracking + uniform errors.** Without LiteLLM we'd need three SDKs + three error handlers + three response parsers + a custom cost meter — call it 600-800 LOC of glue. With LiteLLM the Copilot module is ≤ 200 LOC.

We do **not** depend on `anthropic`, `openai`, or `ollama` Python SDKs directly. LiteLLM speaks HTTP to each provider; no transitive bundling of the official SDKs in the base install. (User may install `anthropic` separately for IDE type hints — never imported in `src/nucleus/`.)

**Why not LangChain?** ([LangChain intro](https://python.langchain.com/docs/get_started/introduction)) LangChain is an agent / chains / memory / tool-calling framework — 200+ KLOC, 50+ transitive deps, weekly breaking changes. We need none of it for single-turn chat. Adding LangChain would violate Constraint #8 (LOC ceiling — its surface alone exceeds Nucleus's 30K budget) and Constraint #7 (it markets itself as an agent framework). REJECT for v0.2-v1.0. ([LangChain GitHub](https://github.com/langchain-ai/langchain) — for reference only.)

---

## §4. Context injection design (the prompt structure)

The Copilot is **prompt-as-product**. One template file at `src/nucleus/intelligence/prompts/system.j2` (Jinja2 — already pinned `jinja2==3.1.5`), rendered per call:

```text
You are the Nucleus Copilot. You answer questions about ONE Nucleus
project. You DO NOT have access to the data inside assets, only to
the asset graph, project config, and recent errors. When you suggest
a fix, prefer concrete `nucleus <command>` invocations.

PROJECT CONFIG (`nucleus_project.yaml`):
{{ project_yaml }}

ASSET GRAPH SUMMARY ({{ asset_count }} assets):
{% for a in assets %}
- {{ a.key }} (cols: {{ a.column_names | join(", ") }};
  last materialized: {{ a.freshness_iso }})
{% endfor %}

RECENT ERRORS (last 3 from `.nucleus/errors.log`):
{% for e in recent_errors %}
- [{{ e.timestamp }}] NE{{ e.code }} {{ e.user_message_oneline }}
{% endfor %}

USER QUESTION:
{{ question }}
```

Rationale: explicit, debuggable, reviewable in PR. No black-box prompt-as-code (Anti-Over-Engineering #3: *"no black-box surfaces"*). The template lives in `src/nucleus/intelligence/prompts/system.j2`, version-controlled, lint-checked by `scripts/check_vocabulary.py`.

System prompt LOC budget: ≤ 60 lines. If it grows past 100, refactor — the prompt is doing too much.

---

## §5. Project context extraction

A pure function: `gather_context(project_root: Path) -> CopilotContext`. Owned by the AMA's read side, not by the Copilot module (single-responsibility).

| Field | Source | Privacy | Size estimate |
|---|---|---|---|
| `project_yaml` | `nucleus_project.yaml` verbatim | Already public to provider once opt-in granted; secrets must live in `.env` per v4.1 §11.5, not in YAML | ~1 KB |
| `assets[]` | catalog `list_namespaces()` + `list_tables()` + per-table `current_snapshot()` ([pyiceberg](https://py.iceberg.apache.org/api/catalog/)) | Asset names + column names + freshness only; **no row counts, no data values** (mirrors ADR-011 §3 rule 2) | ~50 B per asset; cap at ~50 assets |
| `recent_errors[]` | tail-3 of `.nucleus/errors.log` (asset-level lineage hook writes these per v4.1 §6.4) | `NucleusError.user_message` only — NE-code + message; never `repr(__cause__)` (ADR-011 §3 rule 5) | ~200 B per error |

**Hard size cap**: total context ≤ 4 KB. If asset graph exceeds the cap, sort by freshness and truncate to top 50 most-recent. Pre-flight token-count via [`messages/count_tokens`](https://docs.anthropic.com/docs/en/api/messages-count-tokens) when the provider is Anthropic.

**Excluded by design** (privacy-first):
- Asset source code (`.py` / `.sql` files) — would leak business logic
- Data values from inside any asset — would leak PII / secrets
- Absolute file paths — relativize to project root (mirrors ADR-011 §3 rule 4)
- OS username, hostname (mirrors ADR-011 §3 rule 3)
- Secrets — `.env` is `.gitignore`d already; we never read it for context

---

## §6. Token budget management

Per-call:
- **Input budget**: hard ceiling 2K tokens default; user-configurable via `chat.input_token_budget` in `nucleus.toml`. Pre-flight count via provider's count endpoint OR `tiktoken==<latest>` (NEEDS VERIFICATION at v0.2 — extra optional dep, not yet pinned).
- **Output budget**: hard ceiling 1K tokens default; passed as `max_tokens` to provider.
- **Cost ceiling**: pre-flight cost = `input_tokens × cost_per_input_mtok / 1e6 + max_output_tokens × cost_per_output_mtok / 1e6`. If > `chat.cost_ceiling_usd` (default `0.10`), raise `NucleusBudgetExceededError` before HTTP call.
- **Provider pricing**: NEEDS VERIFICATION 2026-05; pull from Anthropic + OpenAI pricing pages cited in §3; Ollama = `0.0` (local). Numbers baked into `nucleus.toml.copilot.pricing` so we never hard-code stale values in source.

Per AGENTS.md §9 stop-condition row 9 (*"AI Copilot economics break (token cost > 30% of Cloud margin)"*): track via OTEL counter `nucleus.copilot.cost_usd` (opt-in per ADR-011); trigger a Drift Detection pass if cumulative monthly cost exceeds founder-set ceiling.

---

## §7. Configuration

API keys live in **environment variables only**. We do not store secrets in `~/.nucleus/config.yaml` (would normalize secret-in-file).

```toml
# nucleus.toml (project-level)
[copilot]
provider = "anthropic"             # "anthropic" | "openai" | "ollama"
model = "claude-<id-NEEDS-VERIFICATION>"
input_token_budget = 2000
output_token_budget = 1000
cost_ceiling_usd = 0.10
opt_in = false                     # ADR-011 §1 mirror — opt-in for OSS
```

Env vars (read at chat-time, never logged):
- `ANTHROPIC_API_KEY` ([docs](https://docs.anthropic.com/docs/en/manage-claude/authentication))
- `OPENAI_API_KEY` ([docs](https://platform.openai.com/docs/api-reference/authentication))
- `OLLAMA_HOST` (defaults to `http://localhost:11434`)
- `NUCLEUS_COPILOT_OPT_IN=1` overrides `nucleus.toml`

Missing key + cloud provider → `NucleusEnvironmentError(NE_to_be_assigned, "Set ANTHROPIC_API_KEY...")` — never log the (absent) key.

---

## §8. Error translation

Per v4.1 §6.4 + ADR-006: every LiteLLM exception MUST translate to a `NucleusError` subclass with NE-code. No `litellm.AuthenticationError` ever reaches the user. Proposed mapping (new codes pending ADR-006 owner):

| LiteLLM exception | `NucleusError` subclass | NE-code (proposed) | User message shape |
|---|---|---|---|
| `litellm.AuthenticationError` | `NucleusCopilotAuthError` (new) | `NE4001` (proposed; defer to ADR-006 §NV) | "Copilot auth failed for provider `<name>`. Check the relevant API-key env var." |
| `litellm.RateLimitError` | `NucleusCopilotRateLimitError` (new) | `NE4002` (proposed) | "Copilot rate-limited by `<provider>`. Retry in N s." |
| `litellm.APIError` (5xx) | `NucleusCopilotProviderError` (new) | `NE4003` (proposed) | "Copilot provider `<name>` returned an error. Try `--provider ollama` for offline path." |
| `litellm.Timeout` | `NucleusTimeoutError` (existing) | `NE3005` (reused per ADR-013) | "Copilot request timed out after `N`s." |
| `litellm.ContentPolicyViolationError` | `NucleusCopilotContentFilterError` (new) | `NE4004` (proposed) | "Copilot rejected the request (content policy). Rephrase or remove sensitive context." |
| (pre-flight budget) | `NucleusBudgetExceededError` (new) | `NE4005` (proposed) | "Estimated cost `$X` > ceiling `$Y`. Raise `chat.cost_ceiling_usd` or shrink the question." |

`NE4xxx` is a fresh range to keep Intelligence Layer errors out of the existing 1xxx (commit) / 2xxx (schema) / 3xxx (resource) families per ADR-006 §Decision. Founder + ADR-006 owner co-acceptance required before assignment is final.

**Discipline**: `litellm.*` class names MUST NOT appear in `NucleusError.user_message`. Original exception preserved as `error.cause`. Validated by `scripts/dagster_leak_check.py` (extend the leak-list to include `litellm`/`anthropic`/`openai`/`ollama` class names — small PR at v0.2 time).

---

## §9. Wrap point in Nucleus

| Field | Value |
|---|---|
| Module | `src/nucleus/intelligence/copilot.py` (new package; v4.1 §7 Layer 5 Intelligence) |
| Public API | `def chat(question: str, *, project_root: Path \| None = None) -> CopilotReply` |
| Return type | `@dataclass(frozen=True) class CopilotReply: text: str; suggested_command: str \| None; tokens_in: int; tokens_out: int; cost_usd: float; provider: str; model: str` |
| Stability | Beta @ v0.2 → Stable @ v0.5 (per ADR-005 §2 ladder) |
| LOC budget | ≤ 250 LOC total: `copilot.py` ≤ 150 + `prompts/system.j2` ≤ 60 + `context.py` (gather_context) ≤ 100 + `cli/commands/chat.py` ≤ 80. Total ~390 LOC, well under per-feature 500 ceiling (AGENTS.md §11.4 step 3). |
| Tests | `tests/intelligence/test_copilot.py` — mocked `litellm.completion`; happy path, each error class, budget refusal, context truncation, opt-in gate. |
| Phase Gate | v0.2 ONLY — out of scope for v0.1 per AGENTS.md §1 + v4.1 §7.2. ADR-015 PROPOSED status keeps the module unbuilt until founder ratifies. |

The Copilot is **NOT** part of the `ctx` SDK. Users do not call `ctx.chat(...)` from inside `@nucleus.asset` bodies. The Copilot is a CLI-only feature for the human operator, not a programmable runtime. (`ctx.agent` v0.5+ per v4.1 §7.3 is the separate programmable surface — different ADR, different sandbox.)

---

## §10. Cost Meter integration (v0.5+, mentioned for design continuity)

Not v0.2 scope. Forward-compatibility only:

- `CopilotReply.cost_usd` is recorded today (computed locally from `response.usage.tokens` × pricing) so the v0.5 Cost Meter (v4.1 §7.5 + §6.3) can aggregate it without retroactive instrumentation.
- LiteLLM's [cost tracking callback](https://docs.litellm.ai/docs/proxy/cost_tracking) is the v0.5 hook (per-key spend, per-model rollups) — not wired in v0.2.
- Stop-condition (AGENTS.md §9 row 9): if cumulative monthly cost > 30% of Cloud margin, Drift Detection Pass fires per AGENTS.md §11.11.

No speculative code in v0.2. The cost field is a 1-line dataclass attribute, not a service.

---

## §11. Forbidden mental models check

Verified against `.cursor/rules/nucleus.mdc` §"Forbidden Framings" + AGENTS.md §8 + `scripts/check_vocabulary.py`:

- ❌ Did NOT frame Nucleus with the script-banned `AI-native` / `AI-first` framings — used **AI-assisted** throughout (per `pyproject.toml.tool.nucleus.forbidden_terms_in_docs`). <!-- banned-term: multiple -->
- ❌ Did NOT propose an agent-runtime surface for v0.2 — explicitly de-scoped to v0.5+ per v4.1 §7.3.
- ❌ Did NOT propose model hosting / training / fine-tuning — Hard Constraint #7 respected; Ollama is user's own host.
- ❌ Did NOT propose multi-agent, A2A protocol, MCP server in v0.2 — those are v0.5+ ADRs.
- ❌ Did NOT propose vector store / RAG — single-turn inline context only.
- ❌ Did NOT propose memory across calls — stateless by design.
- ✅ Used vocabulary `Copilot` (capital C, per AGENTS.md §7) consistently for the Nucleus feature throughout; never used the forbidden alternatives from the AGENTS.md §7 vocabulary table.

---

## §12. Composability by Constitution

| Constitution requirement | This proposal |
|---|---|
| Clean swap **interface** | LiteLLM IS the swap interface: any new provider that LiteLLM supports is a config-string change, no Python edit. |
| Smoke tests (5-10) | `tests/intelligence/test_copilot_smoke.py` — one round-trip per provider with mocked HTTP (no network); proves the wrap survives a provider swap. |
| Full swap **implementation** | LiteLLM owns it. If LiteLLM dies (license pivot, vendor death — `.cursor/rules/nucleus.mdc` §Constitution §3 triggers), swap target is **direct `anthropic` SDK + `httpx` for OpenAI + Ollama HTTP** — ~200 LOC of glue, deferred until trigger fires (Constitution §3 "on-demand, not pre-emptively"). |
| Swap doc | `docs/internal/swap/litellm.md` to be drafted at v0.2 implementation time (≤ 100 LOC). |

Tier classification (per ADR-007 + Constraint #9): **Tier 2 — Intelligence engine wrap.** Not Tier 0 (LLMs are not immortal substrates the way Iceberg/Arrow/OL are; provider economics could pivot at any time). License GREEN (MIT).

---

## §13. Effort estimate

| Slice | Effort | Owner |
|---|---|---|
| Research + ADR (this doc + ADR-015) | 1 day | Researcher |
| `intelligence/copilot.py` + `cli/commands/chat.py` wire-up + mocked tests | ~1 week | Builder tier |
| Prompt tuning + privacy review (opt-in flow, redaction edge cases) + cost-ceiling unit tests | ~1 week | Swarm tier |
| `docs/internal/swap/litellm.md` + `docs/internal/research/ai_hallucinations.md` audit + `docs/specs/nucleus_cli_spec.md` amendment (chat = 8th command) + ADR-006 NE4xxx allocation + README + SETUP changes | ~0.5 week | Swarm tier |
| **Total** | **~2.5-3 weeks at max velocity** | mixed |

Architecture v4.1 §7.2 says "4 weeks" — that number assumes Workbench integration. CLI-only de-scopes 1+ week of Workbench wiring (no Monaco editor, no streaming SSE plumbing, no auth proxy). Open question §14 #1 below.

---

## §14. Open questions for founder

1. **Provider default**: Anthropic (highest quality) vs OpenAI (widest ecosystem) vs Ollama (private). Recommend **Anthropic** for cloud default + **Ollama** documented as the offline alternative; OpenAI listed but not default. Aligns with v4.1 §7.2 wording ("Claude API").
2. **Workbench scope**: Architecture §7.2 implies Workbench-first; this proposal de-scopes Workbench from v0.2 to v0.3. Confirm de-scope.
3. **Token budget defaults**: 2K in / 1K out — bigger? Smaller? Should `chat.cost_ceiling_usd` default to `0.10` or `0.05`?
4. **Privacy default**: explicit opt-in (`opt_in=false`) for v0.2, mirroring ADR-011. Or always-prompt-once-and-cache? Recommend opt-in to match ADR-011.
5. **API-key storage**: env var only (this doc's recommendation) vs `~/.nucleus/secrets.yaml` (secret-in-file) vs OS keyring (`keyring` PyPI pkg — new dep). Recommend env var only.
6. **CLI command name**: `nucleus chat` vs `nucleus ask` vs `nucleus copilot`. Recommend `nucleus chat`.
7. **NE-code range**: claim `NE4xxx` for Intelligence Layer? — needs ADR-006 §NV co-acceptance.
8. **Lazy-import official SDKs**: extras `[copilot-typed]` for IDE hints? Recommend NO (Anti-Over-Engineering — LiteLLM alone is enough).

---

## §15. AI hallucinations watch

APIs I almost suggested but verified before writing:

- ✓ `anthropic.Anthropic.messages.create(...)` — verified at PyPI 2026-05-13 against `anthropic==0.101.0` readme. Real.
- ✓ `client.responses.create(...)` (OpenAI) — verified at `openai==2.36.0` readme. The new Responses API exists; previous Chat Completions API also supported indefinitely. Real.
- ✓ `ollama.chat(model=..., messages=[...])` — verified at `ollama==0.6.2` readme. Real. Returns `ChatResponse`.
- ✓ `litellm.completion(model="anthropic/<id>", messages=[...])` — verified at LiteLLM docs Getting Started. Real.
- ✓ `litellm.AuthenticationError`, `RateLimitError`, `APIError`, `Timeout` (note: `Timeout`, not `TimeoutError`) — verified against [LiteLLM Exception Mapping](https://docs.litellm.ai/docs/exception_mapping) 2026-05-13. Real.
- ✓ `litellm.ContentPolicyViolationError` — verified against same docs page; inherits from `litellm.BadRequestError`. §8 NE4004 binding is sound.
- ✓ `litellm.BudgetExceededError` exists too — separate from our `NucleusBudgetExceededError` (ours is pre-flight; LiteLLM's is proxy-side). Name collision noted; we keep ours since the proxy isn't in scope.
- ⚠ `tiktoken==<latest>` for OpenAI-compatible local token counting — **NEEDS VERIFICATION** at v0.2 implementation time; not pinned today; only add if Anthropic's count-tokens endpoint proves insufficient.
- ⚠ Exact Anthropic + OpenAI model IDs and per-token pricing as of 2026-05-13 — **NEEDS VERIFICATION** at ratification. Both providers re-issue model IDs frequently; AI training cutoff (mine: pre-2026-05) cannot be trusted for these.

Log to `docs/internal/research/ai_hallucinations.md` at first miss during implementation. No hallucinations to log from this research pass — every API surface above was double-checked against PyPI readme + linked docs.

---

## NEEDS VERIFICATION (founder, before ADR-015 ratification)

1. **Exact pricing per provider as of 2026-05-13** — Anthropic + OpenAI pricing pages cited in §3; numbers baked into `nucleus.toml.copilot.pricing`. Don't hard-code.
2. **Exact model IDs** for the default Anthropic + OpenAI models — both providers re-issue IDs frequently. Verify at <https://platform.claude.com/docs/en/build-with-claude/models> + <https://platform.openai.com/docs/models> at v0.2 implementation time.
3. **NE-code range `NE4xxx`** — ADR-006 §NV must co-accept; alternative is to extend `NE3xxx` (overloads Resource family).
4. **Workbench-vs-CLI scope** for v0.2 — architecture §7.2 says Workbench; this doc proposes CLI-only. Confirm ADR-015 §Scope.
5. **`tiktoken` need** — only add if Anthropic's [count_tokens endpoint](https://docs.anthropic.com/docs/en/api/messages-count-tokens) is insufficient for pre-flight budgeting OR Ollama context needs local counting.
6. **Ollama model defaults + memory budget** — verify per-model card on `<https://ollama.com/library>` before suggesting a recommended default in user-facing docs.

---

## §References

All docs URLs cited in this report (one place, for upgrade-PR drift checks).

**Anthropic**: <https://docs.anthropic.com/en/api/getting-started> · <https://docs.anthropic.com/docs/en/api/messages> · <https://docs.anthropic.com/docs/en/api/messages-count-tokens> · <https://docs.anthropic.com/docs/en/api/rate-limits> · <https://docs.anthropic.com/docs/en/api/errors> · <https://docs.anthropic.com/docs/en/build-with-claude/pricing> · <https://docs.anthropic.com/docs/en/build-with-claude/models> · <https://docs.anthropic.com/docs/en/manage-claude/authentication> · <https://docs.anthropic.com/en/api/client-sdks> · <https://docs.anthropic.com/en/api/versioning> · <https://github.com/anthropics/anthropic-sdk-python> · <https://pypi.org/project/anthropic/>

**OpenAI**: <https://platform.openai.com/docs/api-reference> · <https://platform.openai.com/docs/api-reference/chat> · <https://platform.openai.com/docs/api-reference/responses> · <https://platform.openai.com/docs/api-reference/authentication> · <https://platform.openai.com/docs/guides/error-codes> · <https://platform.openai.com/docs/pricing> · <https://platform.openai.com/docs/models> · <https://github.com/openai/openai-python> · <https://pypi.org/project/openai/>

**Ollama**: <https://github.com/ollama/ollama/blob/main/docs/api.md> · <https://github.com/ollama/ollama-python> · <https://ollama.com> · <https://ollama.com/library> · <https://pypi.org/project/ollama/>

**LiteLLM**: <https://docs.litellm.ai/docs/> · <https://docs.litellm.ai/docs/providers> · <https://docs.litellm.ai/docs/exception_mapping> · <https://docs.litellm.ai/docs/completion/output> · <https://docs.litellm.ai/docs/proxy/cost_tracking> · <https://github.com/BerriAI/litellm> · <https://pypi.org/project/litellm/>

**LangChain (for comparison; NOT used)**: <https://python.langchain.com/docs/get_started/introduction> · <https://github.com/langchain-ai/langchain>

**Nucleus internal**: `docs/specs/nucleus_architecture_v4.1.md` §7.2-§7.6 + §8.1 + §11 + §20.1 · `AGENTS.md` §3 (Hard Constraints) + §7 (vocabulary) + §8 (forbidden framings) + §9 (stop conditions row 9) + §11.4 + §11.12 · `.cursor/rules/nucleus.mdc` §"Forbidden Framings" + §Anti-Over-Engineering · ADR-002 (positioning) · ADR-005 (tier ladder) · ADR-006 (NE-codes) · ADR-007 (license tiers) · ADR-011 (telemetry opt-in — privacy mirror)

---

*Last verified: 2026-05-13. Next re-verification: at ADR-015 ratification gate. The LLM-SDK landscape moves at minor-version-per-week pace; assume drift between this doc and reality after any 30-day window.*
