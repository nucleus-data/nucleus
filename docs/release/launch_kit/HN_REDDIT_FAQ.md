# HN + Reddit Critical-Question FAQ — Nucleus v0.2.0

*Twenty questions a skeptical Hacker News or r/dataengineering commenter is most likely to ask in the first 24 hours. Each answer is 80–150 words, honest, and cites architecture sections, ADRs, or other docs. Companion to `faq_launch.md` (which covers install / security / pricing / roadmap basics in 27 questions). This file is the **adversarial** FAQ — every answer assumes the asker is hostile-but-substantive and wants to find a flaw. Last updated 2026-05-15.*

---

## Q1. Why not just use Spark / Databricks / Snowflake?

Three reasons, none of them "Spark / Databricks / Snowflake is bad" (all three are excellent for what they're designed for).

1. **JVM constraint** (`AGENTS.md` Hard Constraint #1). Cold boot for `nucleus up` is 5.82 s in PoC #4 measurements; idle RSS is 117 MB. A Spark session boots in tens of seconds and idles in gigabytes. Incompatible with the 30-min beachhead metric for a 5-engineer team on laptops.
2. **Single-node optimization is the v0.1–v1.0 envelope.** DuckDB beats Spark for <100 GB workloads on most benchmarks (TPC-H 10 GB on DuckDB ~2.5 s per published numbers at <https://duckdb.org/2023/02/13/announcing-duckdb-070.html>). Above ~5 TB, the architecturally-correct answer is **yield to giants** (Mode 2 dispatch in v1.5+), not "make Nucleus Spark-flavored."
3. **Local-identical-to-prod.** Same engine code locally and in production is the felt moat (v4.1 §2.1).

If your problem is 100+ TB multi-team writes, Spark + Databricks is right. The scale-out audit (`docs/internal/research/scale_out_audit.md`) is explicit about that.

---

## Q2. How is this different from dbt?

dbt is what we'd integrate via `dbt-duckdb` in v0.3+ as an **optional adapter** (per `docs/specs/nucleus_architecture_v4.1.md` §5.6). The reason we don't make dbt the v0.1 default is integration burden: `dbt-duckdb` is community-maintained, its release lag behind core dbt has burned similar projects, and we can't ship reliability-grade error translation through someone else's adapter without owning the boundary.

What we ship instead: ~180 LOC of native `ctx.sql` Jinja resolver with `{{ ref() }}` and `{{ source() }}` resolution. Hard scope ceiling **2,500 LOC** per v4.1 §5.6.0 — if we drift past, the policy is to STOP and integrate `dbt-duckdb` instead.

What you give up vs dbt: macro ecosystem, snapshots (SCD Type 2), doc generation, full hooks. What you get: one error namespace, one CLI, one auth model, native Iceberg writes.

---

## Q3. Why DuckDB and not DataFusion?

DuckDB is the **default**; DataFusion is the **swap target** (`docs/specs/nucleus_architecture_v4.1.md` §5.1 + `docs/internal/swap/duckdb.md`).

Why DuckDB as the default for v0.1: (1) more mature SQL surface in 2026, especially for window functions and complex `JOIN` planning (DuckDB published TPC-H 10 GB at ~2.5 s; DataFusion is competitive but newer); (2) richer Python ecosystem integration via `duckdb-engine` for BI tools; (3) battle-tested on small-to-mid datasets which is exactly the v0.1 envelope (100 GB–5 TB).

Why DataFusion as a clean swap interface: pure-Rust, embeddable, Apache 2.0, Arrow-native, growing fast. The swap interface (5–10 smoke tests in CI per v4.1 §9.3) means the day a perf regression >2x or vendor death triggers swap, the full adapter is built on demand. We do NOT maintain both engines preemptively (that's "Composability Tax" — explicitly avoided per v4.1).

---

## Q4. What happens at >5 TB?

You graduate. That is the documented answer, not a marketing line.

Per `docs/internal/research/scale_out_audit.md` and `docs/specs/nucleus_architecture_v4.1.md` §1.5, the documented data envelope is 100 GB–5 TB and the documented engineer envelope is 5–20. Above that envelope three real gaps surface:

1. **Cross-machine concurrency** — the advisory file lock in `coordination/locks.py` is filesystem-local; multi-host coordination is the catalog's job. Closure path: Lakekeeper REST catalog (v0.3+).
2. **Workbench at 50+ concurrent users** — single uvicorn worker by default. Closure path: `--workers=N` or k8s replicas.
3. **Distributed compute** — out of scope by design. Yield to Databricks/Snowflake via Mode 2 dispatch (v1.5+).

The 8-question gate (`AGENTS.md` §5) rejected seven candidate Rust rewrites for the same reason: ~95% of execution time at any meaningful workload is already in C++/Rust/wire-bound I/O, so optimizing the Python glue is the wrong target.

---

## Q5. Why Iceberg and not Delta Lake?

Iceberg is the ecosystem bet because every catalog outside Databricks is converging on it: Apache Polaris (TLP since Feb 2026 per <https://blogs.apache.org/foundation/entry/the-apache-software-foundation-announces37>), Lakekeeper (Rust), Cloudflare R2 Data Catalog, Unity-Iceberg-compat, Snowflake Iceberg-compat tables (GA 2024 per <https://docs.snowflake.com/en/user-guide/tables-iceberg>).

Delta is excellent for Databricks shops; less universal across the catalog ecosystem. The **yield-to-giants** story works at zero effort because the bytes Nucleus writes to S3 are valid Iceberg snapshots that anything Iceberg-aware can read.

If your destination is Databricks specifically and you want Delta, Nucleus is not for you (use Databricks Free Edition for local dev). If your destination is "any catalog, ever, no matter where we end up," Iceberg is the call. Delta would have constrained graduation to Databricks-flavored destinations only, which contradicts pillar #5 ("friendly to giants, hostile to no-one").

---

## Q6. Is the AI Copilot just a ChatGPT wrapper?

Yes, in v0.2 it intentionally is — and we say so in the docs.

`nucleus chat "..."` is one CLI command that routes through `litellm==1.83.14` to your provider of choice (anthropic / openai / ollama / etc.). API keys come from your shell environment, never logged, never sent to Nucleus servers (we don't have any). Opt-in consent stored at `.nucleus/copilot_opt_in`. Cost ceiling defaults to $0.10/call. Setup recipe: `docs/cookbook/ai-copilot-setup.md`.

v0.2 is intentionally thin per `docs/specs/nucleus_architecture_v4.1.md` §7.2. Schema-aware completion arrives in v0.3; lineage-aware refactoring + `ctx.agent` runtime arrive in v0.5. The differentiation is integration depth (asset graph context, lineage navigation, contract awareness), not "we have a chat command." Per v4.1 §2.1 the **Felt Moat is friction elimination**, not AI; AI is the **Technical Edge** that compounds over years.

We do not lead with AI marketing per `AGENTS.md` §8.

---

## Q7. How does this compare to Dagster?

Dagster is what we wrap, not what we replace. The reasons we put `ctx` on top:

1. **Boot time.** A full Dagster project boot (daemon + gRPC server + asset definitions module) measured against the 5-engineer 30-min beachhead is too slow. The wrapped path runs Dagster in-process per `nucleus run` invocation.
2. **Error translation discipline.** Per v4.1 §6.4, every external exception MUST be intercepted and re-emitted as a `NucleusError` with `docs_url`. User-facing strings MUST NOT contain external classnames. `scripts/dagster_leak_check.py` enforces this in CI; release blocked if any leak.
3. **Replaceability mandate** (v4.1 §6.5). Dagster MUST be replaceable internally by v1.0 without ANY user code change. `nucleus-mini-scheduler` is the documented fallback (~3-5K LOC).

If you want Dagster's web UI directly, `nucleus enable compat-dagster` (Tier 3 escape hatch per v4.1 §6.6) exposes it. For most teams, the wrapped path is what you want.

---

## Q8. What's the license?

**Apache 2.0 forever.** No BSL/SSPL pivot.

A license pivot is explicitly forbidden by `AGENTS.md` Hard Constraint trajectory and `docs/specs/nucleus_architecture_v4.1.md` §17.3. If we ever pivoted, it would auto-trigger the "vendor went hostile" composability fork condition documented in `docs/internal/swap/dagster.md`, which would be a darkly self-referential outcome.

What this means concretely:

- You can use Nucleus commercially (build a paid product on top, deploy as part of internal platform, sell consulting around it, fork it).
- The only obligations are the standard Apache 2.0 attribution + license-include-on-redistribute clauses.
- The OSS core is **complete enough to use forever without paying us** (`docs/specs/nucleus_architecture_v4.1.md` §17.3 explicit non-goal: no feature lock that breaks composability, no different SDK in "enterprise edition").
- License audit is enforced by `scripts/check_licenses.py` in CI: only Apache 2.0 / MIT / BSD / MPL-2.0 / LGPLv3 (Tier 2 exception) dependencies allowed.

---

## Q9. Why Python and not Rust / Go?

Three reasons:

1. **Beachhead persona reach.** Per `docs/specs/nucleus_architecture_v4.1.md` §1.5, the persona is a 5–20 engineer startup data team. Data engineers in 2026 are overwhelmingly Python-fluent; mandating Rust/Go would gate adoption on a language the persona doesn't already use daily.
2. **Wrap-not-build.** The hot path is already in fast languages: DuckDB (C++), Polars (Rust), pyarrow (C++), pyiceberg (Python+Rust). Per `docs/internal/research/scale_out_audit.md`, ~95% of execution time at any meaningful workload runs in those wrapped engines, not in Nucleus's Python glue. Rewriting the glue in Rust would optimize the wrong 5%.
3. **AI Copilot ergonomics.** Python is what LLMs write fluently in 2026; the platform's own `ctx` API needs to be in the language the AI is best at producing.

If a perf regression appears in the Python glue, the response is to `cargo build` the offending hot path as a `pyo3` extension — not rewrite the platform.

---

## Q10. How do you handle ACID without a real transaction coordinator?

We don't build one. **Hard Constraint #5** (`AGENTS.md` §3) forbids a custom Iceberg commit service or distributed transaction coordinator. The catalog handles atomic commits; we route writes through it.

Concretely: Iceberg metadata commits are atomic at the catalog level (filesystem catalog in v0.1; Lakekeeper REST in v0.3+). `pyiceberg.catalog.commit_table()` provides snapshot atomicity per the Iceberg spec (<https://iceberg.apache.org/spec/#table-metadata-and-snapshots>). For multi-table writes, application-level coordination (sequence the commits, accept partial-progress recovery) is the documented pattern — same as Databricks / Snowflake do for non-managed tables.

What we add on top: an advisory file lock for **single-machine** concurrent-run safety (`coordination/locks.py`, NE3008) so two `nucleus run` invocations don't trample each other. That's NOT a distributed lock; multi-host coordination remains the catalog's job. Honest caveat: B4 concurrent-run safety FAILs on Windows in our 2026-05-15 baseline due to NTFS `msvcrt.locking` byte-range semantics; Linux/WSL passes. Fix tracked for v0.2.1.

---

## Q11. Can I use this in production?

**No, it's beta.** v0.2.0 is the first publicly available release; v0.1.0 was an internal beta two days ago. Treat anything labeled "stability tier: Beta" as subject to small breaking changes within 0.x.

That said: the WSL beachhead E2E (8/8 gates PASS, ~7 min boot) does pass, real Iceberg snapshots are written (snapshot ID `7070059669214185406` validated 2026-05-14), error translation discipline is enforced in CI, and 873+ tests pass. Empirical baseline at `docs/internal/benchmarks/2026-05-15_baseline.md` documents what's verified and what's still in flight.

The honest position is **"stable enough to evaluate seriously; not stable enough to bet your job on yet."** Recommended for greenfield analytics on 100 GB–5 TB; not recommended for mission-critical production today. If you do deploy, follow `docs/cookbook/production-deployment.md` and pin every dependency exactly per Hard Constraint #11.

---

## Q12. What's your business model?

Open core, eventually. **None of the paid tiers ship in v0.2.** OSS Core is and will remain free forever (Apache 2.0).

Per `docs/specs/nucleus_architecture_v4.1.md` §17:

| Tier | Price target | Includes | Ships |
|---|---|---|---|
| **OSS Core** | Free (Apache 2.0) | Full platform, self-hosted Workbench | Today |
| Nucleus Cloud | ~$20/seat/mo + usage | Managed catalog, S3, secrets, deploy | v1.0+ |
| Copilot Pro | +$50/seat/mo | Premium AI: agent runtime, advanced models | v1.0+ |
| Enterprise | $50K-500K/yr | SSO/SAML, audit, multi-tenant, SLA | v1.0+ |
| Marketplace | 15-25% rev share | Data product templates | v2.0+ |

The Mo 24 decision gate (per ADR-002 §8.3) forces an explicit founder choice — raise / hand off / accept indie — so the business-model bet is honest, not vague.

---

## Q13. Why not just embed DuckDB in Jupyter?

That's a great solution for ad-hoc analysis, and we encourage it. DuckDB-in-Jupyter doesn't solve the same problem Nucleus solves.

What DuckDB-in-Jupyter gives you: a great query engine, attached to whatever notebook state you have. What it doesn't give you:

- An **asset graph** with stable IDs, contracts, lineage, and materialization history
- A **scheduler** that runs `@nucleus.asset(schedule="@daily")` overnight without you holding the laptop open
- **Iceberg snapshots** that survive notebook kernel restarts and graduate to other catalogs
- **Error translation** so a `psycopg.OperationalError` at 3 a.m. becomes a `NucleusSourceConnectionError` (NE1001) with a `docs_url`
- A **CLI** that gives you `init / up / ingest / run / query / down` outside a notebook
- A **production-shape** path beyond a single notebook session

If your problem is "I want to explore some data right now," DuckDB-in-Jupyter wins. If your problem is "I need to build a production-shaped pipeline a junior engineer can reproduce on their laptop next month," that's where Nucleus is built for. Marimo notebook integration arrives in v0.3+ for the best of both.

---

## Q14. How does this scale?

Honestly: single-node, until you graduate. The documented envelope is **100 GB–5 TB and 5–20 engineers** (`docs/specs/nucleus_architecture_v4.1.md` §1.5). Above that, three answers:

1. **Mode 1 graduation (today, zero effort).** Point Databricks/Snowflake/any Iceberg catalog at the same S3 bucket. No re-migration. The yield-to-giants strategy makes this work because there is no Nucleus byte format to migrate off — just Iceberg.
2. **Mode 2 hybrid dispatch (v1.5+).** `@nucleus.sql_asset(compute="databricks")` — Nucleus orchestrates, Databricks executes, result committed back to Iceberg.
3. **Mode 3 federation (v2.0+).** Each domain runs its own Nucleus; cross-domain queries via Trino/Databricks/Snowflake against a federated Iceberg catalog. Data Mesh full.

Per `docs/internal/research/scale_out_audit.md`, NONE of these modes require rewriting Nucleus internals. The eight-question gate rejected every candidate Rust rewrite for the same reason — optimizing the wrong 5%.

---

## Q15. What's the Cloud tier?

Not shipping today. **v0.2 is OSS only.** The Cloud tier is documented as a v1.0+ target per `docs/specs/nucleus_architecture_v4.1.md` §17:

- **What it would do**: managed catalog (Lakekeeper hosted), managed S3 (warehouse storage), managed secrets, one-command deploy from local Nucleus → cloud Nucleus.
- **What it would cost**: target ~$20/seat/mo + usage (the OSS core stays free; you pay for managed infra you'd otherwise run yourself).
- **What it would NOT do**: no proprietary SDK changes; no feature lock that breaks composability; no different `ctx` API in "enterprise edition" (explicit non-goal §17.3).

Architecturally, it's a thin layer over the same `ctx` API + an OIDC delegation (Authentik / Keycloak / Auth0) per Hard Constraint #6 ("never own identity"). If we ship it in v1.0, the entire `nucleus_project.yaml` you developed locally remains valid against the Cloud tier — that's the felt-moat upgrade path.

---

## Q16. Why no Kubernetes operator?

Two reasons:

1. **It's the wrong audience for v0.1–v1.0.** The beachhead persona (5–20 engineer startup, 100 GB–5 TB) does not run a k8s cluster for their data platform. They run a laptop. Building a k8s operator would optimize for a persona we explicitly defer to v1.5+ (`docs/specs/nucleus_architecture_v4.1.md` §1.4).
2. **It would gate adoption on platform engineering.** A k8s operator implies "you need a platform team to deploy this," which is exactly the friction we're eliminating.

For self-hosted production single-node deployments today, the documented path is `docs/cookbook/production-deployment.md` (uvicorn `--workers=N`, Caddy reverse proxy with OIDC wedge, systemd service file). For multi-host, the documented path is "yield to giants via Mode 1 graduation" — Databricks / Snowflake handle the k8s for you. If demand surfaces (>10 enterprise customers asking) we revisit per the trigger-event composability rule (v4.1 §9.3).

---

## Q17. What's the AI Chat MVP — what providers?

`nucleus chat "..."` ships as a **single-turn chat** (no conversation memory) routed through `litellm==1.83.14`. Per `docs/decisions/ADR-015-ai-chat-mvp.md`:

**Built-in providers:**
- `anthropic` (Claude) — `ANTHROPIC_API_KEY`
- `openai` (GPT) — `OPENAI_API_KEY`
- `ollama` (local LLMs, no key needed) — runs against `http://localhost:11434`

**Adding others:** litellm supports 100+ providers (Cohere, Mistral, Bedrock, Vertex, Azure, etc.); the `nucleus_project.yaml` `copilot.provider` field accepts any litellm-supported provider name.

**Privacy:**
- Opt-in via `.nucleus/copilot_opt_in` consent file
- API keys read from shell env only; never logged
- No Nucleus servers — conversation is between you and your provider
- Cost ceiling defaults to `$0.10/call` (configurable in `nucleus_project.yaml`)

Schema-aware completion arrives in v0.3; lineage-aware refactoring arrives in v0.5. v0.2 is intentionally just chat.

---

## Q18. How does error translation work?

Every code path that catches an external library exception MUST translate it to a `NucleusError` subclass before it reaches the user. Per `docs/specs/nucleus_architecture_v4.1.md` §6.4:

```python
try:
    catalog.commit_table(table, updates)
except pyiceberg.exceptions.CommitFailedException as e:
    raise NucleusCommitConflictError(
        user_message="Your write conflicted with a concurrent commit.",
        fix_hint="Retry, or use 'nucleus snapshot tag' to pin the snapshot you want.",
        docs_url="https://nucleus.dev/errors/NE1002",
        cause=e,  # original exception preserved for debugging
    ) from e
```

Three guarantees:

1. **Original exception preserved** as `error.cause` for debugging.
2. **User-facing strings MUST NOT contain external classnames** (`pyiceberg.exceptions.CommitFailedException`, `psycopg.OperationalError`, `dagster.DagsterStepFailureException`, etc.). `scripts/dagster_leak_check.py` enforces this in CI; release blocked if any leak.
3. **Every error has an `NE####` code** with a `docs_url` pointing to a fix recipe (`docs/errors/`).

This discipline is the **#1 release blocker** and lives at the `ctx` boundary. ADR-006 documents the numbering scheme; v0.2 covers ~30 error codes across 5 layers.

---

## Q19. Will the API break in v0.3?

Maybe — but bounded. Per `docs/specs/nucleus_architecture_v4.1.md` §13.3 (the "softened" API stability policy from v4.1 amendment #8):

- **Core data APIs** (`ctx.read`, `ctx.sql`, `ctx.copy_from`, `ctx.params`, `@nucleus.asset`, `@nucleus.check`): stable from v0.1, frozen from v1.0. We will only break these via deprecation warnings + 1-version overlap. Enforced by `scripts/check_api_stability.py` in CI.
- **AI-related APIs** (`ctx.copilot`, `ctx.agent` v0.5+): may evolve faster than core because AI paradigms evolve quickly. We can't freeze for 5+ years.
- **Internal interfaces** (Dagster wrapping, AMA internals, scheduling daemon impl): may change without notice. Direct usage is at your own risk; use the `ctx` boundary instead.

The core promise: code written against the v0.1 `ctx` SDK runs unchanged on v0.2 and will run unchanged on v0.3. If we have to break, we deprecate first.

---

## Q20. What if you abandon this in 6 months?

Your data stays. That is the entire point of the yield-to-giants strategy.

- **Apache Iceberg snapshots in your S3 bucket** are vendor-neutral by definition. Anything Iceberg-aware (Databricks, Snowflake, Trino, Spark, DuckDB, Polars, pyiceberg) can read them. **There is no Nucleus-proprietary format**, ever (explicit non-goal §20.1).
- **Your asset definitions** are plain Python files in your own git repo. Worst case, you write a small migration script to extract the schema and re-run the SQL elsewhere.
- **Your run history** is plain NDJSON at `<project>/.nucleus/runs/runs.ndjson`. Greppable, archivable, portable.
- **Apache 2.0 means anyone can fork.** If the founder vanishes, the project can be picked up by anyone — including, per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.3, the Bosch internal data-platform team is the documented off-ramp.

Your bet is on **Iceberg + open standards**, not on Nucleus the company. The Mo 24 decision gate forces an explicit founder choice (raise / hand off / accept indie) so the bet is honest. Reaching Mo 24 without a choice = automatic option (c) accept indie.

---

## What this FAQ does NOT cover

- Install / quickstart / 30-second demo → see `docs/release/launch_kit/faq_launch.md` Q1–Q5
- Security / Copilot privacy / secrets → see `faq_launch.md` Q6–Q9
- Pricing / commercial use → see `faq_launch.md` Q13–Q15 + Q12 here
- Roadmap details / Mo 24 gate → see `faq_launch.md` Q16–Q18
- Contributing → see `faq_launch.md` Q23
- Error code reference → see `faq_launch.md` Q25 + `src/nucleus/errors.py`

Companion files:
- `docs/release/launch_kit/comparison_vs_databricks_snowflake.md` — full capability matrix
- `docs/internal/research/scale_out_audit.md` — honest scale-out assessment
- `docs/internal/swap/dagster.md` — composability swap rationale
- `docs/specs/nucleus_architecture_v4.1.md` — ~50 min read, source of truth

---

*If a question is missing or an answer feels evasive, file an issue at <https://github.com/nucleus-data/nucleus/issues> and we'll fix it. Last updated 2026-05-15.*
