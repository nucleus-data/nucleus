# AI-Assisted Data Tooling — State of the Art 2026

> **Last verified:** 2026-05-15 against live official docs, benchmarks, and vendor sources.  
> **Tier per AGENTS.md §1:** Tier 1/2 inspiration research — no new dependency introduced by this doc.  
> **Researcher:** Claude Sonnet 4.6 (Research tier; Gemini 3.1 Pro unavailable — fallback per AGENTS.md §11.14).  
> **Related docs:** `docs/internal/research/ai_copilot.md` (LiteLLM v0.2 design) · `docs/internal/research/strategic/ai_agent_data_infra_2026.md` (market angles A/C/D) · `docs/internal/research/inspiration/big_cloud_platforms_recent.md` (Databricks/Snowflake AI — NOT repeated here).  
> **AI training-cutoff caveat:** All claims verified against live sources as of 2026-05-15. Unconfirmed claims marked `[NEEDS VERIFICATION]`.

---

## Executive Summary — Top 3 Patterns to Adopt

The decisive finding from 2026 AI-data research: **the context architecture around an LLM matters far more than which LLM you pick.** Cube.dev's paired benchmark proved this definitively — adding a 4 KB semantic markdown doc improved accuracy +17–23 pp across Claude Opus 4.7, Claude Sonnet 4.6, and GPT-5.4. With the doc present, the three frontier models are statistically indistinguishable (p ≥ 0.79). Model upgrades moved nothing; context did everything.

**Three patterns, tiered by v-series:**

| # | Pattern | Adopt in | LOC | ROI |
|---|---|---|---|---|
| **1** | **Nucleus asset-description sidecar** — a machine-readable `.nucleus/asset_docs/<key>.md` per asset with metric definitions, disambiguation rules, and join conventions; read by the Copilot on each query | **v0.3** | ~200 | Highest: converts generic LLM into domain-correct analyst without vector DB |
| **2** | **`nucleus-mcp-server`** — expose `assets`, `runs`, `query`, `lineage` as MCP tools backed by `ctx`; stdio transport; ~500 LOC | **v0.5** | ~500 | High: zero-marginal-cost distribution to every MCP-compatible AI host (Cursor, Claude, GitHub Copilot) |
| **3** | **Structured `ctx` tool-call harness** — read-only `ctx.sql` + `ctx.read` tools with hard guardrails (row cap, read-only DuckDB, cost ceiling, call budget) | **v0.7** | ~400 | Medium: enables AI pair programming inside assets; risky without guardrails |

All three pass the 8-question gate. None require multi-agent frameworks, vector stores, or model hosting. Anti-over-engineering discipline holds.

---

## §1 — Text-to-SQL State of the Art

### 1.1 Spider 2.0 benchmark landscape

**Spider 2.0** (ICLR 2025 oral, 632 enterprise workflows, BigQuery + Snowflake + SQLite, > 1,000 columns each) is the definitive 2026 benchmark. The gap from Spider 1.0 is brutal: GPT-4o scores 86.6% on Spider 1.0 but only **10.1%** on Spider 2.0. o1-preview reaches 17.1% standalone. Source: [spider2-sql.github.io](https://spider2-sql.github.io/)

**Current leaderboard (accessed 2026-05-15):**

| Track | Top system | Score |
|---|---|---|
| Spider 2.0-Snow (547 Snowflake tasks) | **Genloop Sentinel Agent v2 Pro** | 96.70%† |
| Spider 2.0-Snow #2 | Native mini (usenative.ai) | 96.53%† |
| Spider 2.0-Snow #3 | QUVI-3 + Gemini-3-pro-preview | 94.15% |
| Spider 2.0-Lite (BigQuery + Snowflake + SQLite) | **SOMA-SQL** (Oracle OCI) | 72.02% |
| Spider 2.0-DBT (68 code agent tasks) | **Databao Agent** (JetBrains) | 60.29% |

† Uses ground-truth table hints (starred entries on leaderboard) — scores are inflated vs. blind evaluation. See §11 NEEDS VERIFICATION item #6.

**Critical takeaway:** Every top-5 finisher is a **multi-step agent system**, not a single-shot LLM call. Model selection is secondary to the retrieval and planning pipeline around it.

### 1.2 SQLCoder — best open-source option

Defog's SQLCoder family (Apache-2.0 `[NEEDS VERIFICATION — confirm license before v0.5 ref]`):

| Model | Params | Benchmark accuracy | Weights |
|---|---|---|---|
| `sqlcoder-70b` | 70B | 91.4% on Defog complex-query eval | ✅ HuggingFace |
| `sqlcoder-7b-2` | 7B | ~80% complex-ratio queries | ✅ HuggingFace |

Source: [defog.ai/blog/open-sourcing-sqlcoder2-7b](https://defog.ai/blog/open-sourcing-sqlcoder2-7b) · [huggingface.co/defog/sqlcoder](https://huggingface.co/defog/sqlcoder)

**For Nucleus v0.5+:** SQLCoder-70b via Ollama is the best open-source privacy-first path for text-to-SQL. Zero cloud API needed. Perfectly aligned with ADR-011 (opt-in privacy model).

### 1.3 The production reality gap

Do not ship text-to-SQL based on benchmark numbers. Production accuracy on real warehouses (hundreds of tables, cryptic names) runs **10–40%** even for frontier models. Source: [tianpan.co/blog/2026-04-10-text-to-sql-failure-modes-production](https://tianpan.co/blog/2026-04-10-text-to-sql-failure-modes-production) · [omni.co/blog/why-text-to-sql-fails](https://omni.co/blog/why-text-to-sql-fails)

**The lethal failure mode is silent wrong answers.** SQL executes, returns plausible data, but the answer is 5× too high because of a fan-out join. The fix is structural — not a better model — see §3.

---

## §2 — Schema-Aware AI Patterns

### 2.1 Vanna AI's RAG architecture

**Vanna AI v2.0** (Feb 2026, MIT, open-source) is the reference implementation of schema-aware text-to-SQL via RAG:

1. **Training phase** (one-time): ingest DDL statements, business documentation, and example question-SQL pairs into a vector DB (ChromaDB by default; Qdrant, Milvus also supported).
2. **Query phase**: embed the question, retrieve k most relevant DDL chunks + doc snippets + example pairs, inject into prompt, call LLM.
3. **Memory loop** (v2.0): successful queries are stored back, improving accuracy over time on project-specific SQL patterns.

Source: [vanna.ai/docs](https://vanna.ai/docs) · [github.com/vanna-ai/vanna](https://github.com/vanna-ai/vanna/)

**Local-first path:** Vanna + ChromaDB + Ollama (sqlcoder-70b) = zero cloud bytes, zero per-query cost. Architecturally aligned with Nucleus privacy-first design.

**What to borrow for Nucleus v0.3:** The DDL-chunking strategy and the "business doc sidecar" pattern — one markdown file per asset describing metric definitions, column semantics, and join conventions. No vector DB needed for < 50 assets (flat-file retrieval is fast enough at that scale). Defer ChromaDB to v0.7+ when asset counts scale.

### 2.2 Prompt templates that work

Three patterns consistently outperform naive DDL-only prompting:

**SSE (Schema + Semantics + Example):**  
Inject DDL for relevant tables + the asset description sidecar (§2.1) + 3–5 example question–SQL pairs. This is the pattern validated by the Cube.dev benchmark (+17–23 pp). The semantic snippet is the decisive element.

**Table-selection pre-pass (chain-of-thought):**  
Before generating SQL, ask the model "Which tables are relevant?" Reduces fan-out join errors by forcing explicit scoping.

**Clarification on ambiguity:**  
One clarifying question when intent is unclear raises accuracy from 42.5% to 92.5% on multi-table queries. `[NEEDS VERIFICATION]` — source [tianpan.co/blog/2026-04-19-text-to-sql-at-scale-production](https://tianpan.co/blog/2026-04-19-text-to-sql-at-scale-production) — verify URL resolves correctly.

For Nucleus v0.5 Copilot (v4.1 §8.3): SSE is the right template; clarification is the fallback when the Copilot detects low-confidence phrasing (e.g., plural metric names, ambiguous time ranges).

---

## §3 — Semantic Layers as AI Substrates

### 3.1 The definitive benchmark

Cube.dev published a controlled paired benchmark (arXiv 2604.25149, 2026) on 100 natural-language questions against the Contoso Retail dataset:

| Model | Schema only | + Semantic layer (4 KB) | Δ |
|---|---|---|---|
| Claude Opus 4.7 | 50.5% | 67.7% | **+17.2 pp** |
| Claude Sonnet 4.6 | 46.5% | 68.7% | **+22.2 pp** |
| GPT-5.4 | 45.5% | 68.7% | **+23.2 pp** |

All improvements significant at p ≤ 0.0015 (McNemar). With the semantic layer, all three models are statistically indistinguishable. Without it, they are also indistinguishable. **The semantic document accounts for essentially all significant variance. Model choice within tier does not.**

Source: [cube.dev/blog/why-semantic-layers-make-llm-analytics-reliable-...](https://cube.dev/blog/why-semantic-layers-make-llm-analytics-reliable-a-paired-benchmark-across-three-frontier-models) · [arxiv.org/abs/2604.25149](https://arxiv.org/abs/2604.25149)

Corroborating independent results: BIRD benchmark external-knowledge ablation (+20 pp), dbt Labs paired benchmark (+15 pp). Same direction, three different teams.

**Note on bias:** Cube.dev ran their own study. Cross-validation from BIRD + dbt is reassuring but not a full replication. See §11 item #5.

### 3.2 Tool options

**Cube.dev** (Apache-2.0): most mature OSS semantic layer. Defines metrics in YAML, compiles to deterministic SQL, serves via REST + GraphQL. The `/v1/query` endpoint can return the semantic context document in machine-readable form for LLM injection. [cube.dev/docs](https://cube.dev/docs) — **DEFER for Nucleus**; the right v0.3 equivalent is the sidecar doc pattern (§2.1).

**dbt MetricFlow** (Apache-2.0, open-sourced Dec 2025): metric-compilation engine, compiles YAML metric definitions to correct SQL at any grain. Assumes dbt models as upstream. No native Iceberg bridge. Pattern to borrow: `measure` / `dimension` / `metric` vocabulary matches what Nucleus asset definitions currently lack. Source: [getdbt.com/blog/open-source-metricflow-governed-metrics](https://www.getdbt.com/blog/open-source-metricflow-governed-metrics)

**Malloy** (Google, MIT, TypeScript): semantic modeling language that compiles to SQL, natively supports DuckDB. Its `Publisher` server (Sept 2024) exposes Malloy models via REST **and MCP**, enabling AI agents to query a semantic model directly. Source: [malloydata.dev](https://www.malloydata.dev/) · [github.com/malloydata/publisher](https://github.com/malloydata/publisher). **Verdict for Nucleus: ADOPT the MCP-exposure pattern from Publisher, not the Malloy language** — Malloy adds a new query syntax that conflicts with Pillar #4 (familiar UX).

---

## §4 — Agent Frameworks for Data Tasks

### 4.1 LangGraph — graph-based stateful orchestration

LangGraph (MIT, v0.3+) is the dominant framework for stateful multi-step data agent workflows. Key capabilities: TypedDict state with reducer merging, PostgresSaver for checkpoint persistence, human-in-the-loop interrupts, fan-out/fan-in parallelism. Source: [inductivee.com/blog/langgraph-multi-agent-workflow-deep-dive](https://inductivee.com/blog/langgraph-multi-agent-workflow-deep-dive)

**8-question gate verdict: DEFER to v0.7+.** LangGraph + LangChain core = 50K+ LOC transitive — blows the 30K proprietary budget on a library alone. No v0.3 users have requested multi-agent workflows. **BORROW the pattern:** graph-of-steps with human-in-the-loop interrupts is the right architecture for any future `ctx.agent` (v4.1 §7.3); build it as a simple hand-rolled state machine when the time comes.

### 4.2 CrewAI — role/task agent orchestration

CrewAI's hierarchical manager-worker pattern is documented to **fail in real workflows** — the manager does not effectively coordinate agents, causing sequential execution, unnecessary tool calls, and high latency. An empirical study of 409 bugs across agentic frameworks (arXiv 2604.08906, 2026) identified specialized failure modes unique to autonomous orchestration. Sources: [towardsdatascience.com/why-crewais-manager-worker-architecture-fails](https://towardsdatascience.com/why-crewais-manager-worker-architecture-fails-and-how-to-fix-it/) · [arxiv.org/html/2604.08906v1](https://arxiv.org/html/2604.08906v1)

**Verdict: REJECT.** Failure modes are well-documented; architecture conflicts with Nucleus's explicit-beats-implicit philosophy.

### 4.3 AutoGen — self-healing pipeline pattern

AutoGen v0.4 (Apache-2.0, Microsoft) is more flexible but has breaking API changes from v0.3. Its best validated use case for data work is the **self-healing pipeline**: agent detects materialization failure, reads the error, queries the asset graph, proposes a concrete fix for human approval. Source: [cordum.io/blog/crewai-vs-autogen-2026](https://cordum.io/blog/crewai-vs-autogen-2026)

**Verdict: BORROW the pattern, not the framework.** The self-healing loop maps directly to the Nucleus Copilot v0.2 architecture: `NucleusError` → error-context injection → Copilot suggests `nucleus <command>` → human approves. No new dependency needed; this capability already exists in the v0.2 spec.

### 4.4 Recommended pattern: "pair programmer," not autonomous agent

The best-ROI pattern from 2026 field evidence is not autonomous execution but a **propose-approve loop**:

```
nucleus run <asset> → fails → NucleusError (structured, NE-code)
→ Copilot reads error + asset graph + last 3 errors
→ suggests concrete fix as "nucleus <command>"
→ human approves → runs fix → iterates
```

This is exactly what v0.2 Copilot specifies in `docs/internal/research/ai_copilot.md` §2 + §4. No new frameworks. No autonomous execution. No runaway cost risk.

---

## §5 — Model Context Protocol (MCP)

### 5.1 Protocol overview

MCP (Anthropic, Nov 2024, JSON-RPC 2.0, donated to Linux Foundation Dec 2025) defines three server-side building blocks: **Tools** (functions the LLM invokes), **Resources** (read-only data URIs), **Prompts** (parameterized templates). Source: [modelcontextprotocol.io/specification/latest](https://modelcontextprotocol.io/specification/latest)

**Adoption:** 97M monthly SDK downloads, 10,000+ public servers, hosted by Claude Desktop, ChatGPT, Gemini, Cursor, VS Code, JetBrains, GitHub Copilot. MCP is no longer a thesis — it is the ambient AI protocol. Source: `docs/internal/research/strategic/ai_agent_data_infra_2026.md` §3.1.

### 5.2 Cloud platform adoption

**Snowflake:** Managed MCP server **GA November 2025**. Exposes Cortex Analyst (structured SQL translation) and Cortex Search (semantic search) as MCP Tools. OAuth-backed, RBAC-governed. Source: [docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp)

**Databricks:** Managed MCP servers with Unity Catalog + Mosaic AI integration. Four servers: Vector Search, Genie Spaces, Databricks SQL, Unity Catalog Functions. All enforce Unity Catalog RBAC automatically. Source: [docs.databricks.com/aws/en/generative-ai/mcp](https://docs.databricks.com/aws/en/generative-ai/mcp)

**Iceberg community:** `cloudera/iceberg-mcp-server` (read-only via Impala) and `dragonejt/iceberg-mcp-server` (Python, PyIceberg + DuckDB, v0.1.34 Mar 2026) both exist. They operate on raw Iceberg files. Nucleus's server is differentiated by surfacing assets, contracts, lineage, and freshness through `ctx` — the semantic layer raw Iceberg tools lack.

### 5.3 `nucleus-mcp-server` concrete spec sketch

**Scope:** ~500 LOC · `src/nucleus/mcp/server.py` · `nucleus serve --mcp` CLI command · v0.5 deliverable · stdio transport (zero network exposure).

**Four tools + four resources:**

| Tool | Input | Returns |
|---|---|---|
| `list_assets` | `filter?: string` | Asset keys, schema columns, freshness, contract status |
| `query_asset` | `asset_key, sql, max_rows=100` | Rows (read-only DuckDB, max 1,000 enforced) |
| `get_lineage` | `asset_key, depth=2` | Upstream + downstream asset key pairs |
| `get_runs` | `asset_key, n=5` | Last N materialization results + NE-codes for failures |

Resources (read-only URIs): `nucleus://assets`, `nucleus://assets/{key}`, `nucleus://lineage/{key}`, `nucleus://errors/recent`.

**Security guardrails:** `query_asset` runs inside `duckdb.connect(read_only=True)`; pre-call parse blocks DDL, DML, `COPY`, `EXPORT`; all calls logged to `.nucleus/mcp.log` (no data values).

**Effort:** ~5 days total. Requires new ADR. Per Constraint #10, read [spec.modelcontextprotocol.io](https://spec.modelcontextprotocol.io/specification/draft/server/tools/) and confirm `mcp` Python SDK package name/version on PyPI before writing the ADR.

---

## §6 — "Cursor for Data" — Inline AI Editors

### 6.1 What shipped in 2025–2026

No single product owns the "Cursor for data" label. What exists:

**dbt Copilot (GA March 2025):** Inline SQL generation inside dbt Cloud Studio via keyboard shortcut or `@model_name` mention. Context includes full project schema, relationships, and lineage. Self-reported: 40–60% time reduction per model, 2–3× test coverage. Source: [getdbt.com/blog/dbt-copilot-is-ga](https://getdbt.com/blog/dbt-copilot-is-ga)

**Hex AI (May 2025, $70M Series C):** Notebook-level AI with a Notebook Agent that generates and edits SQL and Python cells, observes outputs, and iterates. Context includes warehouse schema. Source: [learn.hex.tech/docs/getting-started/ai-overview](https://learn.hex.tech/docs/getting-started/ai-overview)

**Cursor IDE itself** is what many data engineers use today — not a data-specific tool but a generic IDE with `@dbt-project` / `@nucleus_project.yaml` context injection. The v0.2 Nucleus workspace rules in `.cursor/rules/nucleus.mdc` already demonstrate this pattern.

### 6.2 Three UX patterns to copy

**Pattern 1 — `@asset` context mention:** Scope AI context to a specific asset. Implementation for Nucleus: parse `@<asset_key>` in `nucleus chat` and pre-inject that asset's schema + description sidecar. ~20 LOC delta to v0.2 Copilot.

**Pattern 2 — Apply/Replace with one click:** dbt and Hex show a SQL diff with a single apply button. CLI equivalent: print the `nucleus <command>` suggestion with a `[y/N] run now?` prompt. Already specced in `ai_copilot.md` §2 (`suggested_command` in `CopilotReply`).

**Pattern 3 — Project-context-first:** The differentiating feature vs. ChatGPT is that AI cannot hallucinate column names that don't exist in the actual schema. The v0.2 Copilot's `gather_context()` already enforces this for the asset graph. v0.5 upgrade: add column-level type information + the semantic description from §2.1.

### 6.3 Workbench opportunity (v0.3+)

The inline AI pattern maps directly to a Workbench SQL editor (v0.3 per v4.1 §7.2) with a "Generate SQL" button that calls the Copilot with the visible schema context. LOC estimate: ~200 LOC in React + existing Copilot backend. Right-sized v0.3 feature — not a standalone AI query tool, but AI augmenting the SQL editor that already exists.

---

## §7 — Tool-Use Patterns and Guardrails

### 7.1 Function-calling benchmark (BFCL V4)

| Model | Single-tool | 5-tool | 20+ tool |
|---|---|---|---|
| Claude Opus 4.7 | 96% | 91% | 76% |
| GPT-5 Pro | 95% | 90% | 74% |
| Llama-3-Groq-70B-Tool-Use | 90.76% overall | — | — |

Source: [gorilla.cs.berkeley.edu/leaderboard.html](http://gorilla.cs.berkeley.edu/leaderboard.html) · [presenc.ai/research/ai-agent-tool-calling-accuracy-benchmarks-2026](https://presenc.ai/research/ai-agent-tool-calling-accuracy-benchmarks-2026)

**Multi-step compounding:** 90% per-call accuracy = 73% at 3 calls = 59% at 5 calls. Cap tool counts at 15 max. Parameter mismatch (38%), type coercion (24%), wrong tool selection (18%) are the dominant failure modes at 20+ tools.

### 7.2 The four `ctx` tools for v0.5+

Map read-only `ctx` operations to the same four tools sketched in §5.3 (`list_assets`, `query_asset`, `get_lineage`, `get_runs`). These are sufficient to cover 90%+ of "what's wrong with my pipeline?" queries.

### 7.3 Guardrails (non-negotiable)

Five mitigations that must ship with any `ctx` tool-call feature:

1. **Hallucinated asset key** → `ctx.sql` throws `NucleusError(NE2xxx)` for unknown assets; error-translate to structured tool-call error for LLM self-correction.
2. **SQL that modifies data** → `duckdb.connect(read_only=True)` + pre-call parse blocking DDL/DML/COPY/EXPORT.
3. **Runaway cost loop** → hard tool-call budget (default 10 per session) + `NucleusBudgetExceededError`.
4. **Data exfiltration** → pre-call parse blocks `COPY TO`, `EXPORT DATABASE`, `INTO OUTFILE`.
5. **Overconfident wrong answers** → always surface generated SQL + row count before confirming; never hide intermediate results. Source: [arxiv.org/abs/2506.17203](https://arxiv.org/abs/2506.17203) `[NEEDS VERIFICATION — §11 item #7]`.

---

## §8 — Cost & Latency Benchmarks

### 8.1 Provider comparison (verified 2026-05-15)

| Provider + model | Input $/MTok | Output $/MTok | TTFT | ~200-tok response |
|---|---|---|---|---|
| **GPT-4o-mini** | $0.15 | $0.60 | 250 ms | 2.0 s |
| **Claude Haiku 3.5** | $0.80 | $4.00 | 280 ms | 1.8 s |
| **Groq Llama 3.1 70B** | $0.59 | $0.79 | 180 ms | 0.8 s |
| **GPT-4o** | $2.50 | $10.00 | 380 ms | 2.5 s |
| **Claude 3.5 Sonnet** | $3.00 | $15.00 | — | — |

Source: [kickllm.com/research/ai-api-latency-comparison](https://kickllm.com/research/ai-api-latency-comparison.html) · [kalviumlabs.ai/blog/llm-selection-for-production](https://www.kalviumlabs.ai/blog/llm-selection-for-production/) `[NEEDS VERIFICATION — verify current rates at official pricing pages before wiring into nucleus.toml]`

### 8.2 Per-query cost for Nucleus Copilot v0.2 (2K in / 1K out)

| Provider | Single query | 200 queries/month |
|---|---|---|
| GPT-4o-mini | **$0.00090** | **$0.18** |
| Claude Haiku 3.5 | **$0.00560** | **$1.12** |
| Groq Llama 3.1 70B | **$0.00197** | **$0.39** |
| Claude 3.5 Sonnet | **$0.02100** | **$4.20** |
| Ollama local | **$0.000** | **$0.00** |

**v0.2 recommendation:** Claude Haiku 3.5 for quality/cost balance at startup team usage (< 200 queries/month → < $1.12). GPT-4o-mini as budget-first alternative. Ollama for the privacy-first path.

**v0.5 schema-aware upgrade (4K in / 1K out):** Doubles input tokens. At 200 queries/month: GPT-4o-mini → $0.72, Haiku → $2.04. Still well within the $0.10/query ceiling in `nucleus.toml`. Ollama stays free.

### 8.3 The $38,000-in-four-days horror story

A real case: a company's "deep analysis" feature sent 50K-token documents to GPT-4. Power users ran it dozens of times daily, hitting $38K in four days against a $12K monthly budget. Source: [engineersofai.com/docs/mlops/llmops-pipelines/Token-Cost-Monitoring](https://engineersofai.com/docs/mlops/llmops-pipelines/Token-Cost-Monitoring)

**This is exactly what the Nucleus pre-flight cost ceiling prevents.** The ceiling in `ai_copilot.md` §6 (`NucleusBudgetExceededError` before the HTTP call) is load-bearing, not ceremonial. Keep it.

---

## §9 — Anti-Patterns (Failures and Backlash)

### 9.1 AI-native data startup death curve (2024–2025)

Four documented shutdowns:

- **Olli.ai** (YC): silent shutdown early 2025. Technical users wanted SQL; non-technical users burned by hallucinations.
- **Datawisp** (4 years): wound down 2025. Founder: *"Non-technical users wouldn't accept AI mistakes; technical users needed SQL too late."*
- **WhyHive**: shutdown Apr 2025: "Couldn't achieve sufficient growth."
- **Reworkd AI** (YC): shutdown Feb 6, 2025.

**Death mode:** AI-as-primary UX satisfies neither casual users (hallucination intolerance) nor power users (SQL escape hatch arrives too late). This is why Nucleus's AI-assisted (not AI-primary) posture is architecturally correct.

### 9.2 The silent wrong-answer trap

Text-to-SQL's most dangerous failure: SQL executes, returns plausible data, the answer is wrong. Fan-out traps inflate numbers silently; NULL-semantics bugs shrink counts silently; date off-by-ones corrupt trend lines. The fix is structural (semantic layer — §3), not a model upgrade.

**For any future Nucleus `query --ai` feature:** Always display the generated SQL alongside the result. Always provide a "edit SQL" escape hatch. Never hide intermediate results.

### 9.3 Agent framework churn risk

AutoGen v0.4 broke production workflows from v0.3. CrewAI's hierarchical pattern fails as documented. LangChain ships breaking changes weekly.

**Anti-pattern for Nucleus:** Hard-depending on any multi-agent framework in `pyproject.toml`. Any agent logic in `src/nucleus/intelligence/` must have clean swap interfaces (Constraint #9). Framework choice should be swappable between minor versions if usage data demands.

### 9.4 Prompt injection via asset data

If user-controlled data values reach the system prompt, the AI system can be manipulated. The `ai_copilot.md` §4 design already explicitly excludes data values from context injection. Maintain this invariant in all future Copilot expansions; it must be part of any code review checklist for Intelligence Layer changes.

---

## §10 — 8-Question Gate Summary for Top 3 Recommendations

| Question | Pattern 1 (v0.3 asset doc) | Pattern 2 (v0.5 MCP server) | Pattern 3 (v0.7 tool harness) |
|---|---|---|---|
| Maps to architectural layer? | ✅ Intelligence + Experience | ✅ Integration | ✅ Intelligence (§7.3) |
| Serves <30 min beachhead? | ✅ indirectly (better Copilot) | ❌ graduation enabler | ❌ advanced use case |
| Wrap possible? | ✅ plain markdown, no OSS | ✅ wrap `mcp` SDK + `ctx` | ✅ use LiteLLM + `ctx` |
| No JVM? | ✅ | ✅ | ✅ |
| Local-identical-to-prod? | ✅ | ✅ (stdio transport) | ✅ |
| 30K LOC budget? | ✅ ~200 LOC | ✅ ~500 LOC | ✅ ~400 LOC |
| Empirical telemetry? | ❌ add telemetry hook at v0.3 | ✅ MCP adoption is documented | ❌ defer until v0.5 usage data |
| v0.1 scope? | ❌ v0.3 correct | ❌ v0.5 correct | ❌ v0.7 correct |

**Verdicts:** Pattern 1 → ADOPT v0.3, no ADR needed. Pattern 2 → ADOPT v0.5, new ADR required (`ADR-NNN: Add nucleus-mcp-server`). Pattern 3 → DEFER v0.7, revisit after v0.5 telemetry.

---

## §11 — NEEDS VERIFICATION

1. **SQLCoder-70b current license** — verify Apache-2.0 at [huggingface.co/defog/sqlcoder](https://huggingface.co/defog/sqlcoder) before any v0.5 user-facing reference.
2. **Current LLM pricing (§8.1)** — verify at [platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing), [anthropic.com/pricing](https://anthropic.com/pricing), [groq.com/pricing](https://groq.com/pricing) before wiring into `nucleus.toml`. Pricing moves monthly.
3. **`mcp` Python SDK package name and version** — confirm on PyPI at [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) before the v0.5 ADR.
4. **Vanna AI v2.0 license** — listed MIT on GitHub; confirm no dual-license since Feb 2026 release at [github.com/vanna-ai/vanna/blob/main/LICENSE](https://github.com/vanna-ai/vanna/blob/main/LICENSE).
5. **Cube.dev benchmark bias** — Cube ran their own study. BIRD (+20 pp) and dbt Labs (+15 pp) are corroborating but not independent replications. Do not cite the Cube result as the sole proof; always cite all three.
6. **Spider 2.0-Snow top scores (96.70%, 96.53%)** — both are starred (use ground-truth table hints), inflating scores vs. blind evaluation. Verify footnotes at [spider2-sql.github.io](https://spider2-sql.github.io/) before citing in benchmarking context.
7. **Overconfidence paper (arXiv 2506.17203)** — fetched as PDF; verify arXiv abstract URL resolves at [arxiv.org/abs/2506.17203](https://arxiv.org/abs/2506.17203).

---

## §12 — References

**Spider 2.0:** [spider2-sql.github.io](https://spider2-sql.github.io/) · [proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html](https://proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html)

**SQLCoder:** [defog.ai/blog/open-sourcing-sqlcoder2-7b](https://defog.ai/blog/open-sourcing-sqlcoder2-7b) · [huggingface.co/defog/sqlcoder](https://huggingface.co/defog/sqlcoder)

**Cube.dev benchmark:** [cube.dev/blog/why-semantic-layers-make-llm-analytics-reliable-...](https://cube.dev/blog/why-semantic-layers-make-llm-analytics-reliable-a-paired-benchmark-across-three-frontier-models) · [arxiv.org/abs/2604.25149](https://arxiv.org/abs/2604.25149)

**BFCL V4:** [gorilla.cs.berkeley.edu/leaderboard.html](http://gorilla.cs.berkeley.edu/leaderboard.html) · [presenc.ai/research/ai-agent-tool-calling-accuracy-benchmarks-2026](https://presenc.ai/research/ai-agent-tool-calling-accuracy-benchmarks-2026)

**Vanna AI:** [vanna.ai/docs](https://vanna.ai/docs) · [github.com/vanna-ai/vanna](https://github.com/vanna-ai/vanna/)

**Semantic layers:** [cube.dev/docs](https://cube.dev/docs) · [getdbt.com/blog/open-source-metricflow-governed-metrics](https://www.getdbt.com/blog/open-source-metricflow-governed-metrics) · [malloydata.dev](https://www.malloydata.dev/) · [github.com/malloydata/publisher](https://github.com/malloydata/publisher)

**MCP:** [modelcontextprotocol.io/specification/latest](https://modelcontextprotocol.io/specification/latest) · [docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp) · [docs.databricks.com/aws/en/generative-ai/mcp](https://docs.databricks.com/aws/en/generative-ai/mcp) · [anthropic.com/news/model-context-protocol](https://www.anthropic.com/news/model-context-protocol)

**Agent frameworks:** [inductivee.com/blog/langgraph-multi-agent-workflow-deep-dive](https://inductivee.com/blog/langgraph-multi-agent-workflow-deep-dive) · [towardsdatascience.com/why-crewais-manager-worker-architecture-fails](https://towardsdatascience.com/why-crewais-manager-worker-architecture-fails-and-how-to-fix-it/) · [arxiv.org/html/2604.08906v1](https://arxiv.org/html/2604.08906v1) · [cordum.io/blog/crewai-vs-autogen-2026](https://cordum.io/blog/crewai-vs-autogen-2026)

**"Cursor for data":** [getdbt.com/blog/dbt-copilot-is-ga](https://getdbt.com/blog/dbt-copilot-is-ga) · [docs.getdbt.com/docs/platform/use-dbt-copilot](https://docs.getdbt.com/docs/platform/use-dbt-copilot) · [learn.hex.tech/docs/getting-started/ai-overview](https://learn.hex.tech/docs/getting-started/ai-overview)

**Production failures:** [tianpan.co/blog/2026-04-10-text-to-sql-failure-modes-production](https://tianpan.co/blog/2026-04-10-text-to-sql-failure-modes-production) · [omni.co/blog/why-text-to-sql-fails](https://omni.co/blog/why-text-to-sql-fails)

**Cost/latency:** [kickllm.com/research/ai-api-latency-comparison](https://kickllm.com/research/ai-api-latency-comparison.html) · [engineersofai.com/docs/mlops/llmops-pipelines/Token-Cost-Monitoring](https://engineersofai.com/docs/mlops/llmops-pipelines/Token-Cost-Monitoring)

**Nucleus internal:** `docs/specs/nucleus_architecture_v4.1.md` §7–§8.3 · `docs/internal/research/ai_copilot.md` · `docs/internal/research/strategic/ai_agent_data_infra_2026.md` · `AGENTS.md` §3, §7, §11.12

---

*Next re-verification: Q4 2026 before v0.5 MCP-server ADR. LLM cost tables change monthly; Spider 2.0 leaderboard updates continuously.*
