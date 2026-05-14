# ADR-015: AI Copilot Chat MVP (v0.2)

> **Status**: ACCEPTED — 2026-05-13 (founder ratified all 8 Open Questions per ADR recommendations; see `docs/FOUNDER_ACTION_QUEUE.md §0` ratification record)
> **Date**: 2026-05-13 · **Decider**: Solo founder

> **Founder ratification (2026-05-13)** — Open Questions resolved per ADR recommendations:
> 1. **Default provider** = Anthropic Claude (cloud) + Ollama (documented offline path); matches v4.1 §7.2.
> 2. **Workbench scope** = AI chat is **CLI-only in v0.2**; Workbench AI chat sidebar deferred to **v0.2.1 patch or v0.3** per ADR-016 §Founder ratification #2. Reconciliation: Workbench v0.2 still ships (per ADR-016) but without AI sidebar; AI chat ships as `nucleus chat` CLI in v0.2.
> 3. **Token / cost defaults** = 2K-in / 1K-out / `$0.10` per-query ceiling; configurable in `nucleus.toml`.
> 4. **Privacy default** = **opt-in** (mirrors ADR-011 §1); first invocation prompts `[y/N]` and persists.
> 5. **API-key storage** = **env var only** (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_HOST`); no secrets file, no OS keyring. Anti-Over-Engineering.
> 6. **NE-code range `NE4xxx`** = ACCEPTED for the Intelligence layer; ADR-006 §NV amendment lands in the same implementation PR.
> 7. **CLI command name** = `nucleus chat`.
> 8. **Lazy-import extras `[copilot-typed]`** = **NO** (Anti-Over-Engineering); LiteLLM is the only runtime dep needed.
> **Tags**: copilot, intelligence-layer, v0.2, ai-assisted, litellm, wow-factor
> **Layer**: L5 Intelligence (primary) + L4 Experience (CLI surface)
> **Architecture refs**: `nucleus_architecture_v4.1.md` §7.2 (Copilot staging — v0.2 = "Inline AI chat … Claude API + project file context"); §7.7 (why this layer is the moat); §8.1 (surfaces by release — Workbench `❌` in v0.1 / `✅` in v0.2); §20.1 (Non-Goals: "Full AI Copilot (lineage-aware, schema-aware) in v0.1"); §11.5 (secrets never in logs / AI context); `AGENTS.md` §3 Constraint #7 (no ML platform / AI training / agent hosting), §8 Forbidden Mental Models, §11.4 (per-feature workflow), §11.12 (docs-before-integration); `.cursor/rules/nucleus.mdc` §Anti-Over-Engineering + §Forbidden Framings; ADR-002 §8 (positioning — AI-assisted demoted from headline to pillar); ADR-005 §2 (tier ladder); ADR-006 (NE-codes); ADR-007 (license tiers); ADR-011 (telemetry opt-in — privacy mirror); `docs/research/ai_copilot.md` (research substrate this ADR ratifies).

## Context

Founder greenlit a 4-6 month ladder to v1.0 with "wow factor"; architect named **AI chat that knows your project** as the #1 wow item after the 30-minute beachhead. Architecture v4.1 §7.2 already pre-allocates v0.2 (Mo 4-8) for inline AI chat against Claude API with project file context (no schema introspection). What is missing today: the API surface, provider abstraction choice, privacy posture, error contract, and the WRAP-vs-BUILD record. `docs/research/ai_copilot.md` (2026-05-13) provides the substrate; this ADR binds the v0.2 implementation contract before any code lands under `src/nucleus/intelligence/`. AGENTS.md §11.1 Phase Gate is satisfied — PoC #1 is PROMOTED (2026-05-13) so v0.1 production work is unblocked; v0.2 work begins after v0.1 ships, but the design lock can happen now.

The 8-question gate (AGENTS.md §5):

| # | Question | Answer |
|---|---|---|
| 1 | Maps to architectural layer? | YES — L5 Intelligence (v4.1 §7) |
| 2 | Serves <30-min beachhead? | NEUTRAL — v0.2 is *after* v0.1 ships; this feature does not gate the 30-min metric, only **augments** the post-clone experience |
| 3 | Wrap, not build? | YES — wrap LiteLLM (100+ provider abstraction) |
| 4 | No-JVM preserved? | YES — pure-Python LiteLLM + HTTP |
| 5 | Local-identical-to-prod? | YES — Ollama path enables full local; cloud providers identical in dev/prod |
| 6 | Stays in 30K LOC? | YES — ≤ 390 LOC across module + CLI + prompt (per research §9) |
| 7 | Triggered by telemetry or anxiety? | **TRIGGERED BY FOUNDER WOW-FACTOR DIRECTIVE** — architect-greenlit; not anxiety. Empirical post-ship: track `nucleus.copilot.calls` (opt-in) to confirm usage. |
| 8 | Required for v0.1, or defer? | DEFER to v0.2 (Mo 4-8) — explicit non-goal in v4.1 §20.1 row for v0.1 |

All 8 PASS or DEFER cleanly; no "no" or "unclear."

## OSS / Surface Options Considered

| Option | Shape | Verdict |
|---|---|---|
| **A** — Direct `anthropic` SDK only | One provider; no swap interface; tight cloud coupling | REJECT — violates Composability Constitution (Constraint #9); no offline path; provider lock-in. |
| **B** — Roll our own HTTP client for all providers (`httpx` + provider-specific JSON) | Maximum control; no third-party LLM dep | REJECT — re-implements 100+ provider quirks (error mapping, streaming, tool calls) that LiteLLM already owns; LOC blow-up; violates wrap-not-build (AGENTS.md §4). |
| **C** — LangChain (`langchain==<latest>`) | Agent / chains / memory framework; widest ecosystem | REJECT — 200+ KLOC surface alone exceeds Nucleus 30K LOC ceiling (Constraint #8); markets itself as agent framework (Constraint #7 risk); weekly breaking changes (Constraint #11 risk); we don't need agents in v0.2. |
| **D** — Wrap LiteLLM (`litellm==1.83.14`); lazy direct providers | One Python entry; OpenAI Chat-Completions response shape across all 100+ providers; uniform exception types | **ACCEPT** — single pin, three first-class providers (Anthropic/OpenAI/Ollama), built-in cost tracking, swap is config-string. |

## Decision

> **Wrap LiteLLM as the v0.2 Copilot provider abstraction. Default provider = Anthropic Claude (per v4.1 §7.2). Surface = single-turn synchronous `nucleus chat "<question>"` CLI command. Project context auto-injected: `nucleus_project.yaml` + asset graph summary + last 3 errors — NO data values, NO source code. Cost ceiling per query enforced pre-flight (default `0.10` USD-equivalent). Privacy default = opt-in, mirroring ADR-011 §1. Pin: `litellm==1.83.14` (single new runtime dep — no separate `anthropic`/`openai`/`ollama` pins required).**

### 1. Public surface

```python
# src/nucleus/intelligence/copilot.py  (new module, Layer 5 per v4.1 §7)
def chat(question: str, *, project_root: Path | None = None) -> CopilotReply: ...

@dataclass(frozen=True)
class CopilotReply:
    text: str                       # Markdown-rendered to stdout via rich
    suggested_command: str | None   # e.g. "nucleus run marts.orders"
    tokens_in: int
    tokens_out: int
    cost_usd: float                 # 0.0 for Ollama
    provider: str                   # "anthropic" | "openai" | "ollama"
    model: str
```

Stability: **Beta @ v0.2 → Stable @ v0.5** (per ADR-005 §2). `frozen=True` per ADR-005 §3.

CLI: `nucleus chat "<question>"` — the eighth command after v0.1's seven (per AGENTS.md §1). Requires `nucleus_cli_spec.md` amendment in the implementation PR.

### 2. Scope

**In v0.2** (Mo 4-8 per v4.1 §18):

- `nucleus chat "<question>"` CLI command (single-turn, synchronous, ≤5s p50)
- Project context auto-injection per research §5 (project YAML + asset graph summary + recent errors)
- Three providers via LiteLLM: Anthropic (cloud default), OpenAI (alt cloud), Ollama (local)
- Cost ceiling per query (configurable `chat.cost_ceiling_usd`; default `0.10`)
- Token budget enforcement (input 2K / output 1K defaults)
- Opt-in privacy gate (mirrors ADR-011)

**Out (deferred, explicit)**:

- Multi-turn conversation → v0.5+ (separate ADR)
- Tool calls / function calling → v0.5+ (would need a sandbox per v4.1 §7.3)
- Lineage-aware context → v0.5+ per v4.1 §7.2 row
- Schema-aware completion → v0.3+ per v4.1 §7.2 row
- Workbench chat integration → v0.3+ (de-scoped from v0.2; CLI-only MVP)
- Streaming SSE → v0.3+
- Fine-tuning, model hosting → **NEVER** per Hard Constraint #7
- `ctx.agent` runtime → v0.5+ per v4.1 §7.3 (separate ADR)
- MCP server tool exposure → v0.5+ per `nucleus_architecture_v4.1.md` (separate ADR)

### 3. Pin matrix amendment

Per Constraint #11 + ADR-012:

| Component | Pin | License | Tier (ADR-007) | Notes |
|---|---|---|---|---|
| litellm | `litellm==1.83.14` | MIT | GREEN | new runtime dep; Python `>=3.10,<3.14` (satisfies our `>=3.11,<3.13`); replaces 3 separate SDK pins |

No `anthropic` / `openai` / `ollama` runtime pin — LiteLLM talks HTTP directly. (Open Question §6 below: founder may opt for `anthropic`/`openai` lazy extras under `[copilot-typed]` for IDE hints; recommend NO — Anti-Over-Engineering.)

### 4. Privacy / safety (the bedrock — mirrors ADR-011 §6)

| Posture | Rule |
|---|---|
| **Opt-in default** | `copilot.opt_in=false` in `nucleus.toml`; first `nucleus chat` invocation prompts `[y/N]: send project metadata to <provider>?` and persists choice. NO outbound bytes before opt-in. |
| **API keys via env var ONLY** | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_HOST` — never stored in any Nucleus config file. Never logged. Never echoed in error messages. |
| **Context shape** | Project YAML + asset graph summary (key + columns + freshness) + last 3 error messages. **NO data values, NO source code, NO secrets.** Hard cap: 4 KB total context. |
| **Privacy redactions** | Same five rules as ADR-011 §3: no raw SQL strings, no row counts as attributes, no OS username/hostname, no absolute paths (relativize), no stack traces with locals. |
| **Offline path** | Ollama target = `http://localhost:11434` by default; zero outbound bytes possible. Documented as the privacy-first choice. |
| **Disclosure** | `nucleus chat` prints a one-line footer `Copilot: provider=<name> tokens=<N> cost=$<N>` so users see what left (mirrors ADR-011 §6 `telemetry.disclose=true`). |

### 5. Composability (Constitution §1 / Constraint #9)

| Requirement | Realized by |
|---|---|
| Clean swap **interface** | LiteLLM IS the interface — model id string switches provider, zero code edit. |
| Smoke tests | `tests/intelligence/test_copilot_smoke.py` — one mocked round-trip per provider; ≤ 10 tests; runs in CI. |
| Full swap impl | On-demand only (Constitution §3). If LiteLLM dies / license-pivots, swap target = direct `anthropic` SDK + `httpx` for OpenAI + Ollama HTTP (~200 LOC). |
| Swap doc | `docs/swap/litellm.md` at v0.2 implementation time. |

Tier per Constraint #9: **Tier 2 (Intelligence engine wrap).** Not Tier 0 — LLM provider economics are volatile; pre-emptive full-second-impl is "Composability Tax" (v4.1 §9 amendment).

### 6. Error translation contract (v4.1 §6.4 + ADR-006)

Every `litellm.*` exception → `NucleusError` subclass; `error.cause = original`; user_message contains NO `litellm`/`anthropic`/`openai`/`ollama` class name. Proposed NE-codes (new range, co-acceptance with ADR-006):

- `NE4001` `NucleusCopilotAuthError` — auth failure
- `NE4002` `NucleusCopilotRateLimitError` — provider rate-limit
- `NE4003` `NucleusCopilotProviderError` — provider 5xx / unmapped
- `NE4004` `NucleusCopilotContentFilterError` — content policy
- `NE4005` `NucleusBudgetExceededError` — pre-flight cost > ceiling
- `NE3005` (reuse per ADR-013) — `NucleusTimeoutError`

Extends `scripts/dagster_leak_check.py` to ban `litellm`/`anthropic`/`openai`/`ollama` class names in user-facing strings (small PR at v0.2 time).

## Risks & mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Provider outage / rate-limit storm** | MED (Anthropic + OpenAI have had 1-hour outages in 2025-2026) | MED — Copilot unavailable but no impact on core data pipelines | Ollama documented as offline alternative; LiteLLM `RateLimitError` translated; status-page link in error message |
| 2 | **API-key leakage** (logs, error strings, OTEL attrs) | MED — easiest mistake to make | HIGH — credential exposure | Env-var-only policy (§4); CI lint extending `dagster_leak_check.py` to scan for `*_API_KEY` patterns in `user_message`; OTEL allowlist forbids the keys |
| 3 | **Prompt injection** via asset/error metadata containing adversarial text | MED — users may have user-supplied data in error messages | LOW-MED — model produces wrong output; no data corruption since we don't tool-call | System prompt explicitly bounds scope; output is text-only (no code execution); v0.5 sandbox per v4.1 §7.3 |
| 4 | **Cost runaway** (chatty user, huge asset graph, max output) | HIGH if uncapped | MED-HIGH — credit-card drain | Pre-flight cost ceiling (§4) refuses call before HTTP; OTEL `nucleus.copilot.cost_usd` counter; AGENTS.md §9 stop-condition row 9 triggers Drift Detection if monthly > 30% margin |
| 5 | **Model behaviour drift on minor-version SDK upgrade** | MED — LiteLLM ships weekly; providers re-id models monthly | MED — replies degrade silently | Constraint #11 single-component-per-PR + `tests/upgrade_smoke/test_litellm.py` (mocked HTTP, asserts response-shape stability); model IDs in `nucleus.toml` not source code |
| 6 | **Hallucinated `nucleus <cmd>` suggestions** | MED — LLM may suggest non-existent flags | LOW — user runs the command, sees "unknown flag" | System prompt instructs model to suggest only commands enumerated in `cli_spec`; user-visible footer `Copilot: <provider>` reminds the suggestion is model-generated, not validated |

## Effort

**~2.5-3 weeks at max velocity** (research §13 breakdown). Architecture §7.2 estimated 4 weeks — this proposal de-scopes Workbench wiring to v0.3, saving ~1 week.

LOC impact: ~390 LOC across `src/nucleus/intelligence/copilot.py` (≤ 150), `src/nucleus/intelligence/context.py` (≤ 100), `src/nucleus/intelligence/prompts/system.j2` (≤ 60), `src/nucleus/cli/commands/chat.py` (≤ 80). Well under per-feature 500 ceiling (AGENTS.md §11.4) and inside v0.2 phase budget (~10 KLOC headroom from v0.1 ship target ~8K → v0.5 ship target ~18K per ADR-012 cite of phase ceilings).

## Verification plan

1. **`tests/intelligence/test_copilot.py`** — happy path (one round-trip per provider via mocked `litellm.completion`); each error class → correct NE-code translation; budget-refusal pre-flight; opt-in gate; context-size truncation.
2. **`tests/intelligence/test_copilot_smoke.py`** — 3-5 smoke tests (one per provider, mocked HTTP) proving swap interface; runs in CI per Constitution §2.
3. **`tests/upgrade_smoke/test_litellm.py`** — pins shape of `response.choices[0].message.content` against minor version drift; runs on every `litellm` bump per Constraint #11.
4. **`scripts/dagster_leak_check.py`** extension — ban `litellm`/`anthropic`/`openai`/`ollama` class names in `NucleusError.user_message`; ban `*_API_KEY` patterns in user-facing strings.
5. **Manual privacy review** at implementation PR time — diff every `gather_context(...)` field against ADR-011 §3 five rules; confirm no path leaks.

## Open questions (founder, before ratification)

1. **Default provider**: Anthropic Claude (recommended; matches v4.1 §7.2) vs OpenAI vs Ollama. Recommend **Anthropic** cloud default + **Ollama** documented as offline path.
2. **Workbench scope**: de-scoping Workbench chat from v0.2 to v0.3 — confirm. Architecture §7.2 implies Workbench-first; this ADR proposes CLI-only MVP first.
3. **Token / cost defaults**: 2K-in / 1K-out / `$0.10` ceiling. Acceptable?
4. **Privacy default**: opt-in (recommended, mirrors ADR-011) vs prompt-once-and-cache.
5. **API-key storage**: env var only (recommended) vs `~/.nucleus/secrets.yaml` vs OS keyring.
6. **NE-code range `NE4xxx`**: needs ADR-006 §NV co-acceptance; alternative is to extend `NE3xxx`.
7. **CLI command name**: `nucleus chat` vs `ask` vs `copilot`. Recommend `chat`.
8. **Lazy-import extras `[copilot-typed]`**: recommend NO (Anti-Over-Engineering).

## Rollback

- **Behavioural regret** (model output too noisy / replies wrong shape): bump LiteLLM-pin OR swap default provider via `nucleus.toml` — zero code edit, instant rollback per Constitution §1.
- **Provider regret** (cost spike, vendor death): swap to Ollama default; users keep using offline path.
- **Wholesale regret** (Copilot proves not the wow we hoped): remove `nucleus chat` CLI registration; module dormant; no migration cost for existing assets since Copilot is orthogonal to data layer. Beta-tier (ADR-005 §3) permits surface removal at v0.5 cutoff with 6-month deprecation.
- **NO-rollback bedrock** (mirrors ADR-011): once opt-in privacy default ships, future minor cannot silently flip to opt-out. Cloud-only opt-out reserved for v0.5+ Cloud ToS.

## Trigger · Downstream

**Trigger** (PROPOSED → ACCEPTED when all four hold): (1) founder resolves Open Questions #1-#8; (2) ADR-006 §NV co-accepts `NE4xxx` range; (3) v0.1 ship gate per AGENTS.md §1 (`[ ] v0.1 implementation` flipped to `[x]`); (4) re-verification of LLM SDK versions + pricing + model IDs at ratification time per research §15 NEEDS VERIFICATION (LLM SDK landscape moves fast).

**Downstream**: `src/nucleus/intelligence/copilot.py` (~150 LOC), `src/nucleus/intelligence/context.py` (~100 LOC), `src/nucleus/intelligence/prompts/system.j2` (~60 LOC), `src/nucleus/cli/commands/chat.py` (~80 LOC), `tests/intelligence/test_copilot*.py`, `tests/upgrade_smoke/test_litellm.py`, `scripts/dagster_leak_check.py` extension, `pyproject.toml` `litellm==1.83.14` line, `nucleus_cli_spec.md` chat-command amendment, `docs/swap/litellm.md`, `docs/errors/copilot.md`. Compatibility matrix update in `docs/compatibility.md`. ADR-012 pin matrix update.

## Docs URLs

External (verified 2026-05-13 — re-verify at ratification per research §15):

- LiteLLM Getting Started: <https://docs.litellm.ai/docs/>
- LiteLLM exception mapping: <https://docs.litellm.ai/docs/exception_mapping>
- LiteLLM providers list: <https://docs.litellm.ai/docs/providers>
- LiteLLM PyPI: <https://pypi.org/project/litellm/>
- Anthropic Messages API: <https://docs.anthropic.com/docs/en/api/messages>
- Anthropic API errors: <https://docs.anthropic.com/docs/en/api/errors>
- OpenAI API reference: <https://platform.openai.com/docs/api-reference>
- OpenAI error codes: <https://platform.openai.com/docs/guides/error-codes>
- Ollama Python client: <https://github.com/ollama/ollama-python>
- Ollama REST API: <https://github.com/ollama/ollama/blob/main/docs/api.md>

Internal: `docs/research/ai_copilot.md` (substrate); `nucleus_architecture_v4.1.md` §7.2 + §7.7 + §8.1 + §20.1 + §11.5; ADR-002 / ADR-005 / ADR-006 / ADR-007 / ADR-011 / ADR-012 / ADR-013.

---

*Substrate: `docs/research/ai_copilot.md` (2026-05-13). PROPOSED until founder ratification + LLM-SDK re-verification at implementation time.*
