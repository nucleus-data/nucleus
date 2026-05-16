# Recipe: Slack bot answers questions on your data (v0.5+ preview)

> ## ⚠️ v0.5+ preview, **not runnable today**
>
> None of the agent-runtime APIs (`ctx.agent`, `nucleus-mcp-server`) ship yet. The MCP server (~500 LOC) lands at v0.5 per [v4.1 §18.4](../specs/nucleus_architecture_v4.1.md) + [ADR-002 §4.2](../decisions/ADR-002-positioning-decision-2026-05.md). North-star reference, not a step-by-step. Every step carries `NEEDS VERIFICATION`.

> **Target time (v0.5+)**: ~30 min on a working v0.1 stack · **Difficulty**: Senior · **Prereqs**: working v0.1 pipeline (see [`postgres_to_iceberg.md`](./postgres_to_iceberg.md)); Nucleus v0.5+ (Mo 20-28 best-case per [v4.1 §17.2](../specs/nucleus_architecture_v4.1.md), gated on the Mo 24 founder decision per [ADR-002 §8.3](../decisions/ADR-002-positioning-decision-2026-05.md)); Slack bot token; LLM API key
> **Refs**: [v4.1 §7.3](../specs/nucleus_architecture_v4.1.md) · [v4.1 §18.4](../specs/nucleus_architecture_v4.1.md) · [ADR-002 §4.2](../decisions/ADR-002-positioning-decision-2026-05.md)

---

## What you'll build (when this works)

A Slack bot that answers data questions from the asset graph. Teammate asks `how many orders this week?` in `#data`; bot calls the MCP server's tool for `analytics.orders_daily`; replies with the number plus lineage. Every answer emits an OpenLineage event — provenance, snapshot ID, LLM provider, asking user, all reproducible.

## Why this matters

[ADR-002 §4.2](../decisions/ADR-002-positioning-decision-2026-05.md) treats the agent-substrate scenario as a hedged future, not Nucleus's wedge: we are **not** an "agent data substrate" or "AI-native data CLI" (Angles C, D — retired per ADR-002 §4); but if MCP becomes the default way agents talk to data, the ~500 LOC `nucleus-mcp-server` keeps users on Nucleus. <!-- banned-term: AI-native --> The headline "Ship data products from a laptop" already implies "consumable by BI tools, applications, **or AI agents**" via `ctx` or MCP ([AGENTS.md §0](../../AGENTS.md)).

---

## Step 1: Confirm v0.5+ prereqs (NEEDS VERIFICATION — none of this exists yet)

```bash
nucleus version    # <!-- pre-v0.5; NEEDS VERIFICATION --> expected (future): 0.5.0+
```

Also: `analytics.orders_daily` materialized (see [`postgres_to_iceberg.md`](./postgres_to_iceberg.md)), Slack bot token `<PLACEHOLDER>`, LLM API key `<PLACEHOLDER>`.

## Step 2: Annotate the asset for MCP exposure (~5 min, NEEDS VERIFICATION)

```python
import nucleus

@nucleus.asset(
    description="Daily order rollup. One row per UTC day.",
    expose_to_agents=True,                          # NEEDS VERIFICATION: spec'd in v4.1 §18.4 narrative only
    contract="analytics.orders_daily.contract",
)
def orders_daily(ctx):
    raw = ctx.read("raw.orders", as_="polars")
    ...  # same body as the postgres recipe
```

`expose_to_agents=True` registers the asset with `nucleus-mcp-server`; the contract + description become the MCP tool's documented schema, so the LLM picks it confidently rather than hallucinating columns.

## Step 3: Boot the MCP server (~3 min, NEEDS VERIFICATION)

```bash
nucleus mcp serve --port 7331                     # <!-- pre-v0.5; no `mcp` subcommand in docs/specs/nucleus_cli_spec.md §1 -->
mcp-inspector http://localhost:7331               # any MCP-compatible inspector lists analytics.orders_daily
```

## Step 4: Wire up the Slack bot (~10 min, NEEDS VERIFICATION)

**Option A — Stock MCP client.** Any MCP-compatible agent runtime (Claude Desktop, `mcp-agent`, `n8n` MCP node) attaches to the URL from Step 3. Likely the v0.5+ default; Nucleus does not host the agent loop itself.

**Option B — `ctx.agent` runtime (Nucleus-native, v0.5+).**

```python
import nucleus
from nucleus import agent                          # NEEDS VERIFICATION: ctx.agent per v4.1 §7.3

agent.serve_slack(
    token="<PLACEHOLDER>",
    channels=["#data"],
    expose_assets=["analytics.orders_daily"],
    llm="anthropic:claude-3-5-sonnet",            # NEEDS VERIFICATION: ctx.llm provider DSL not locked
)
```

Either path satisfies the [v4.1 §7.3](../specs/nucleus_architecture_v4.1.md) sandbox: agent cannot modify Tier 0, cannot commit without human approval (production), cannot access secrets outside declared scope.

## Step 5: Ask a question, watch the audit trail (~5 min, NEEDS VERIFICATION)

In Slack: `@nucleus-bot how many orders this week?`

Expected (when v0.5 ships):

1. Bot calls the MCP `analytics.orders_daily` tool with a date filter for the current ISO week.
2. Nucleus runs the Iceberg scan (DuckDB, [v4.1 §5.1](../specs/nucleus_architecture_v4.1.md)).
3. Bot replies: `47 orders this week. Asset: analytics.orders_daily, snapshot v17, lineage: postgres://orders → raw.orders → analytics.orders_daily.`
4. OpenLineage `agent_query` event lands in `.nucleus/lineage/` with question, asset, snapshot ID, LLM provider, bot user ID.

The audit trail is the differentiator vs "ChatGPT with read access to a CSV": every AI-mediated query is reproducible and provenance-tagged.

---

## Verification (when v0.5 ships — not testable today)

| Signal | Pass criterion |
|---|---|
| MCP server starts | `nucleus mcp serve` exits 0 + serves a listing |
| Asset exposed | `mcp-inspector` lists `analytics.orders_daily` with a typed schema |
| Bot answers | Slack round-trip < 10 s for a single-asset query |
| Audit emitted | `.nucleus/lineage/` has `agent_query` event with LLM provider + snapshot ID |
| Sandbox holds | Bot cannot materialize or expire a snapshot from Slack |

## Troubleshooting (forecast — not from real runs)

- **Hallucinated columns** — `description=` / `contract=` not propagated to MCP schema. Fail closed (refuse exposure).
- **Stale answers** — snapshot is most-recent committed; daily schedule means "this week" is <24 h stale. Tighten schedule or document staleness in description.
- **Token leak in audit** — secrets MUST not appear in lineage events per [v4.1 §15.3](../specs/nucleus_architecture_v4.1.md). Release-blocker bug.

## What's next

- **Build the Postgres pipeline first**: [`postgres_to_iceberg.md`](./postgres_to_iceberg.md) — needed before any exposure.
- **Architecture**: [v4.1 §7.3](../specs/nucleus_architecture_v4.1.md) (`ctx.agent` sandbox) · [ADR-002 §4.2](../decisions/ADR-002-positioning-decision-2026-05.md) · [`docs/internal/research/strategic/ai_agent_data_infra_2026.md`](../internal/research/strategic/ai_agent_data_infra_2026.md).

---

## NEEDS VERIFICATION

Forward-looking; nothing here ships before v0.5 (Mo 20-28 best-case per [v4.1 §17.2](../specs/nucleus_architecture_v4.1.md); gated on the Mo 24 founder decision per [ADR-002 §8.3](../decisions/ADR-002-positioning-decision-2026-05.md)).

1. **`nucleus mcp serve` CLI subcommand** — not in [`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) §1.
2. **`expose_to_agents=True` decorator argument** — narrative-only in [v4.1 §18.4](../specs/nucleus_architecture_v4.1.md); not yet typed per [`docs/specs/nucleus_asset_model_spec.md`](../specs/nucleus_asset_model_spec.md).
3. **`agent.serve_slack(...)` API** — not in [`docs/specs/nucleus_ctx_sdk_spec.md`](../specs/nucleus_ctx_sdk_spec.md); `ctx.agent` is v0.5+ per [v4.1 §13.2](../specs/nucleus_architecture_v4.1.md), Slack-binding unspecified.
4. **`ctx.llm` provider DSL** (`"anthropic:claude-3-5-sonnet"`) — v0.5+, no naming convention locked; AI-related APIs flex more than core data APIs per [v4.1 §13.3](../specs/nucleus_architecture_v4.1.md).
5. **OpenLineage `agent_query` event type** — not in the [OpenLineage spec](https://openlineage.io/) as of 2026-05; would be a Nucleus extension.
6. **`nucleus-mcp-server` LOC budget** — spec'd ~500 LOC; actual scope reckoned at implementation start.
7. **Sandbox guarantees for production agents** — [v4.1 §7.3](../specs/nucleus_architecture_v4.1.md) lists guardrails as design intent; threat model deferred to v0.5.

If you must ship agent-facing **today**: stop. Use [`postgres_to_iceberg.md`](./postgres_to_iceberg.md) to materialize, then query assets from a vanilla Python Slack bot via DuckDB / Polars. Add MCP when `nucleus-mcp-server` lands (target v0.5, Mo 20-28).
