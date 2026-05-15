# Nucleus v0.2.0 — Launch Day FAQ

*25 questions covering install, getting started, security, scale-out, graduation, pricing, roadmap, "why not X", contributing, support, AI Copilot privacy, and error code reference. Updated 2026-05-15.*

---

## Install & getting started

### Q1. How do I install Nucleus?

```bash
# Lean core (~30 deps, <60 s install on warm cache)
pip install nucleus

# Or with optional extras:
pip install "nucleus[postgres]"     # + psycopg
pip install "nucleus[mysql]"        # + pymysql
pip install "nucleus[snowflake]"    # + dlt[snowflake]
pip install "nucleus[gcs]"          # + gcsfs
pip install "nucleus[ai]"           # + litellm + anthropic + openai
pip install "nucleus[workbench]"    # + fastapi + uvicorn extras
pip install "nucleus[all]"          # all of the above
```

Before the release workflow publishes to PyPI, use the editable git checkout per the README:

```bash
git clone https://github.com/nucleus-data/nucleus.git
cd nucleus
python3.11 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

**Python 3.11 is the primary supported interpreter.** 3.12 may work; follow `pyproject.toml`. Per ADR-039 the install-size split is enforced by `scripts/check_install_size.py` and `scripts/check_lazy_imports.py` in CI.

### Q2. What's the 30-second demo?

Per the README:

```bash
nucleus init beachhead-demo && cd beachhead-demo
nucleus up
nucleus run example.greeting
nucleus query "SELECT * FROM {{ ref('example.greeting') }} LIMIT 5"
nucleus down
```

That's it. You just materialized an Iceberg snapshot, queried it via DuckDB, and tore down the local stack. Every step has a typed exit code; any error has an `NE####` code with a `docs_url`.

### Q3. What's the realistic 30-minute path?

Per `nucleus_architecture_v4.1.md` §1.5 the headline beachhead metric:

> A 5-engineer startup team, on MacBooks, with Postgres source + S3 destination, builds their first BI-ready Iceberg table from `git clone` to live data in **<30 minutes**.

The walkthrough lives in `docs/onboarding/quickstart.md` and `examples/01-ecommerce-elt/`. Validated 2026-05-14 via WSL E2E (8/8 gates PASS, ~7 min boot, real Iceberg snapshot ID 7070059669214185406, zero forbidden classnames in CLI output). External-tester confirmation in flight via PoC #5 kit.

### Q4. What does `nucleus init` create?

A scaffolded project with:

- `nucleus_project.yaml` — project config (warehouse path, copilot opt-in, memory_limit, etc.)
- `assets/` — your asset definitions (Python + SQL)
- `tests/` — your `@nucleus.check` tests
- `data/warehouse/` — the local Iceberg warehouse (filesystem catalog v0.1; Lakekeeper v0.3+)
- `.nucleus/` — runtime state (run ledger, daemon pidfile, copilot opt-in marker)
- `docker-compose.yaml` — local stack (SeaweedFS + Nucleus services)

Templates live in `src/nucleus/templates/v01/`.

### Q5. What's actually shipping in v0.2 that wasn't in v0.1?

- **Workbench v0.3** — full editorial dashboard + 7 interactive routes
- **4 new connectors** — Snowflake, S3, GCS, local filesystem (in addition to Postgres/MySQL/SQLite)
- **Active scheduling daemon** — `@nucleus.asset(schedule="@daily")` actually runs on schedule
- **Durable run ledger** — NDJSON at `<project>/.nucleus/runs/runs.ndjson`
- **Iceberg branch + tag CLI** — `nucleus snapshot branch / tag` for WAP and compliance archiving
- **`nucleus.db` BI handshake** — single-file DuckDB connection for Superset/Evidence/Rill/Streamlit
- **AI Copilot v0.2** — single-turn chat via litellm
- **Reliability hardening (Wave 2 P0)** — DuckDB memory_limit guard, advisory filesystem lock, `expire_old_snapshots` maintenance, Windows `os.replace` audit, error-budget SLOs
- **Install-size split (ADR-039)** — lean core + optional extras
- **uv + ruff 0.15.13 toolchain** — 8 s CI install vs ~2m 15s with pip
- **Public docs site** — ~55 pages, MkDocs Material
- **11-script governance suite** enforced in CI

Full list: `CHANGELOG.md` `[0.2.0]` block.

---

## Security & privacy

### Q6. Does Nucleus phone home / send telemetry?

**No.** Nucleus has no servers. There is no telemetry, no analytics, no usage pings. The only outbound calls are:

- Calls to your **AI provider** when you run `nucleus chat` (and only after you opt in via `.nucleus/copilot_opt_in`). Routed through litellm to your chosen provider (anthropic / openai / ollama / etc.). Your API keys come from your shell environment and are never logged by Nucleus.
- Calls to your **catalog / object store** (filesystem in v0.1; Lakekeeper / S3 / GCS / Snowflake when you wire them up).

That's it.

### Q7. How does Nucleus handle authentication?

Per Hard Constraint #6 in `AGENTS.md`: **Nucleus never owns identity.** Always delegate to OIDC.

- **v0.1 / v0.2 single-user local**: no auth (you own your laptop)
- **v0.3+ team mode**: OIDC integration (Authentik / Keycloak self-hosted, or Auth0 hosted)
- **v1.0+ enterprise**: customer's OIDC provider (Okta, Azure AD, Google Workspace)

For production self-hosted v0.2, the Workbench has no native OIDC yet — front it with Caddy `basic_auth` or an IdP wedge (Authelia / Authentik / OAuth2-proxy). Recipe: `docs/cookbook/production-deployment.md` §"Authentication".

### Q8. How does Copilot privacy work?

Per `docs/cookbook/ai-copilot-setup.md` and `docs/decisions/ADR-015-ai-chat-mvp.md`:

- **Opt-in**: the first successful `nucleus chat` invocation prompts you to consent to sending project metadata to your chosen LLM provider. Consent is stored at `.nucleus/copilot_opt_in` (or `copilot.opt_in: true` in `nucleus_project.yaml`).
- **API keys**: read from your shell environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) — Nucleus never reads `.env`/`.env.local` automatically and never logs key values.
- **Cost ceiling**: pre-flight estimate cap, default $0.10/call (`copilot.cost_ceiling_usd`).
- **No Nucleus-side logging**: Nucleus has no servers. The conversation lives between you and your provider.

### Q9. What about secrets management?

- **Local dev**: `.env.local` files (gitignored). Nucleus does NOT auto-load these — export variables in your shell or use `direnv`.
- **Production self-hosted**: inject secrets at process start from your vault (Vault / Infisical / cloud KMS). See `docs/patterns/secret_management.md` and `docs/cookbook/cloud-credentials.md`.
- **Cloud tier (v0.2+)**: `ctx.secrets.get("name")` reads from the managed secret store.

Secrets never appear in logs, run metadata, or AI Copilot context.

---

## Scale-out & graduation

### Q10. Can Nucleus scale to 100+ engineers / 100 TB warehouse?

**Honestly, no — and that's by design.** Per `docs/research/scale_out_audit.md`, the documented data envelope is 100 GB–5 TB and the documented engineer envelope is 5–20 (per `nucleus_architecture_v4.1.md` §1.5). Above that, three real gaps surface:

1. **Cross-machine concurrency** — `coordination/locks.py` is filesystem-local only; multi-host coordination is the catalog's job. Closure path: Lakekeeper REST catalog (v0.3+).
2. **Workbench at 50+ concurrent users** — single uvicorn worker by default. Closure path: `uvicorn --workers=N` or k8s replicas. Documentation, not code.
3. **Scheduling daemon HA** — single-process polling loop; no leader election. Closure path: yield to Dagster daemon on Kubernetes with Postgres event log + k8s leases.

The architecturally-correct answer at large-team scale is **graduation via Iceberg portability**, not "make Nucleus distributed." See Q11.

### Q11. How do I graduate to Databricks / Snowflake?

Per `nucleus_architecture_v4.1.md` §10 yield-to-giants strategy:

- **Mode 1 — Graduation (today, zero effort)**: Your Nucleus-managed Iceberg snapshots are vendor-neutral. Point Databricks (Iceberg-compat via UniForm or native Iceberg tables), Snowflake (Iceberg tables GA 2024), or any Iceberg REST catalog (Polaris, Lakekeeper, Unity, R2) at the same S3 bucket. **No re-migration. No format translation.** Done.
- **Mode 2 — Hybrid compute (v1.5+)**: `@nucleus.sql_asset(compute="databricks")` — Nucleus orchestrates, Databricks executes, result committed back to Iceberg. The 30-min ergonomics stay; the 100-TB heavy lifting yields.
- **Mode 3 — Federation (v2.0+)**: Each domain runs its own Nucleus; cross-domain queries via Trino/Databricks/Snowflake against a federated Iceberg catalog. Data Mesh full.

Detailed comparison: `docs/release/launch_kit/comparison_vs_databricks_snowflake.md`.

### Q12. What happens to my data if Nucleus dies?

Your data stays. Here's why:

- **Apache Iceberg snapshots in your S3 bucket** are vendor-neutral by definition. Anything Iceberg-aware (Databricks, Snowflake, Trino, Spark, DuckDB, Polars, pyiceberg) can read them.
- **Your asset definitions** are plain Python files. Worst case, you write a migration script to extract the schema and re-run the SQL elsewhere.
- **Your run history** is plain NDJSON at `<project>/.nucleus/runs/runs.ndjson`. Greppable, archivable, portable.
- **No Nucleus-proprietary format exists.** That is the explicit non-goal #20.1.

The whole point of the yield-to-giants strategy is that **your bet is on Iceberg + open standards, not on Nucleus the company.**

---

## Pricing & licensing

### Q13. How much does Nucleus cost?

**The OSS core is $0 forever.** Apache 2.0. Self-hosted, no seat licenses, no consumption pricing.

Future tiers per `nucleus_architecture_v4.1.md` §17 (NOT shipping in v0.2):

| Tier | Price target | Includes |
|---|---|---|
| **OSS Core** | Free (Apache 2.0) | Full platform, self-hosted Workbench |
| Nucleus Cloud (v1.0+) | ~$20/seat/mo + usage | Managed catalog, S3, secrets, deploy, basic Copilot |
| Nucleus Copilot Pro (v1.0+) | +$50/seat/mo | Premium AI: agent runtime, advanced models |
| Nucleus Enterprise (v1.0+) | $50K-500K/yr | SSO/SAML, audit, multi-tenant, RBAC, vertical packs, SLA |
| Marketplace (v2.0+) | 15-25% rev share | Data product templates, vertical accelerators |

**The OSS core is complete enough to use forever without paying us.** That's not a marketing line; it's an explicit non-goal (§17.3): no license pivot, no feature lock that breaks composability, no different SDK in "enterprise edition."

### Q14. Is the license going to change?

**No.** Per `AGENTS.md` §3 + Hard Constraint #11 trajectory: **Apache 2.0 forever. No BSL/SSPL pivot.** A license pivot is explicitly forbidden. If we ever did pivot, it would auto-trigger the "vendor went hostile" composability fork condition documented in `docs/swap/dagster.md` (which would be a darkly self-referential outcome).

### Q15. Can I use Nucleus commercially?

**Yes.** Apache 2.0 permits commercial use. You can build a paid product on top of Nucleus, deploy Nucleus as part of your internal platform, sell consulting services around Nucleus, fork Nucleus, etc. The only obligations are the standard Apache 2.0 attribution + license-include-on-redistribute clauses.

---

## Roadmap

### Q16. What's next after v0.2?

Per `nucleus_architecture_v4.1.md` §18.3:

**v0.3 — Tier 3 Connectors (Mo 14–20)**
- Lakekeeper REST catalog (default) + Polaris alternate (per ADR-004)
- dlt v0.3+ integration (100+ connectors: Stripe, Salesforce, Hubspot, etc.)
- dbt-duckdb optional adapter (for teams migrating from dbt-core)
- Marimo notebook integration
- Schema-aware Copilot completion
- `ctx.snapshot()`, incremental materialization
- Sensors

**v0.5 — Tier 4 Intelligence (Mo 20–28)**
- `ctx.agent` runtime (sandboxed AI code generation)
- Lineage-aware refactoring + AI test generation
- `nucleus-mcp-server` (~500 LOC) — expose assets/contracts/lineage to MCP-compatible agents
- Lance + multimodal optional engine
- Daft optional engine
- Cost meter v1
- Column-level lineage for SQL

**v1.0 GA (Mo 28–36, best-case, contingent on Mo 24 gate)**
- Hardened SDK (core data APIs stable per §13.3)
- Cloud offering managed (catalog, S3, secrets)
- Enterprise OIDC/SAML
- SLA-grade reliability
- First paying customers
- Dagster replaceability proven (mini-scheduler runs same project unchanged)

We do NOT promise dates. We DO promise that every commit will pass the 11 governance gates.

### Q17. When is v0.3 expected?

Per `nucleus_architecture_v4.1.md` §17.2 + §18.0 tier-version map: **Mo 14–20** in the project timeline, which translates roughly to **late 2026 / early 2027**. Solo-founder pacing per the v4.1.2 timeline patch. Mo 24 decision gate (raise / hand off / accept indie) per ADR-002 §8.3 may shift this.

### Q18. What's the Mo 24 decision gate?

Per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.3: by Month 24 (mid-v0.5), the founder MUST commit to exactly one of:

- **(a) Raise seed / pre-seed** → build a team to ship v1.0 GA
- **(b) Hand off** → downstream consumer / acqui-hire (Bosch internal data-platform team is the documented off-ramp)
- **(c) Accept indie outcome** → cap scope, charge from v1.0 OSS-friendly tier, retire fundraise ambitions

Auto-fires from weakness (0 paying after 3 months beta, <10 active teams after 6 months OSS, founder velocity <3 features/month for 60 consecutive days, funded competitor ships equivalent) AND from strength (>50 active teams + ≥2 design partners paying). **No default extension permitted.** Reaching Mo 24 without an explicit choice = automatic option (c).

This is documented in public so the bet is honest.

---

## "Why not X?"

### Q19. Why not Spark / PySpark?

Three reasons:

1. **JVM constraint** (`AGENTS.md` Hard Constraint #1). Cold boot for `nucleus up` is 5.82 s in PoC #4 measurements; idle RSS is 117 MB. A Spark session boots in tens of seconds and idles in gigabytes. Incompatible with the 30-min beachhead metric for 5 engineers on laptops.
2. **Single-node optimization is the v0.1–v1.0 envelope.** DuckDB beats Spark for <100 GB workloads (TPC-H 10 GB on DuckDB ≈ 2.5 s per architecture §5.1). Above that envelope (~5 TB), the architecturally-correct answer is yield to giants (Mode 2 dispatch in v1.5+), not "make Nucleus Spark-flavored."
3. **Local-identical-to-prod** is the felt moat. Nucleus → Databricks Spark introduces a runtime split; Nucleus → DuckDB everywhere doesn't.

If your problem is 100 TB of multi-team writes, Spark is the right answer.

### Q20. Why not dbt-core?

dbt-core is what we'd integrate via `dbt-duckdb` in v0.3+ as an **optional adapter** (per architecture §5.6). The reason we don't make dbt the v0.1 default: integration burden, community-maintained adapter release lag, and we can't ship reliability-grade error translation through someone else's adapter without owning the boundary.

What we ship instead: ~180 LOC of native `ctx.sql` Jinja resolver with `{{ ref() }}` resolution. Hard scope ceiling **2,500 LOC** per v4.1 §5.6.0 — if we drift past, the policy is to STOP and integrate dbt-duckdb.

What you give up vs dbt: macro ecosystem, snapshots (SCD Type 2 — v0.5+), doc generation (v0.3+), full hooks (v0.5+).
What you get: one error namespace, one CLI, one auth model, native Iceberg writes, dbt-duckdb explicit upgrade path.

### Q21. Why not just use Dagster directly?

Dagster is what we wrap. Three reasons for the `ctx` layer on top:

1. **Boot time** — full Dagster project boot is too slow for the 30-min beachhead. Wrapped path runs Dagster in-process per `nucleus run` invocation.
2. **Error translation discipline** — every external exception MUST be intercepted at the `ctx` boundary and re-emitted as a `NucleusError` with `docs_url`. User-facing strings MUST NOT contain external classnames. `scripts/dagster_leak_check.py` enforces this in CI; release blocked if any leak. That discipline lives at the `ctx` boundary.
3. **Replaceability mandate** — per v4.1 §6.5, Dagster MUST be replaceable internally by v1.0 without ANY user code change. `nucleus-mini-scheduler` is the documented fallback (~3-5K LOC; design ready). Direct Dagster usage in user code would break this guarantee.

If you want Dagster's web UI directly, `nucleus enable compat-dagster` (Tier 3 escape hatch per v4.1 §6.6) exposes it.

### Q22. Why Iceberg, not Delta?

Iceberg is the ecosystem bet because every catalog outside Databricks is converging on it: Apache Polaris (TLP since Feb 2026), Lakekeeper (Rust), Cloudflare R2 Data Catalog, Unity-Iceberg-compat, Snowflake Iceberg-compat tables (GA 2024). Delta is excellent for Databricks shops; less universal across the catalog ecosystem.

The yield-to-giants story works at zero effort because the bytes Nucleus writes to S3 are valid Iceberg snapshots that anything Iceberg-aware can read. Delta would constrain graduation to Databricks-flavored destinations only, which contradicts pillar #5 ("friendly to giants, hostile to no-one").

---

## Contributing & support

### Q23. How do I contribute?

External contributions are limited while Tier 1 stabilizes. Per the README contributing section:

1. **Read `AGENTS.md`** — hard constraints are non-negotiable
2. **Open an issue first** for anything large; architectural forks start as ADRs in `docs/decisions/`
3. **Follow the per-feature workflow** in `AGENTS.md` §11.4 (wrap-vs-build → spec tests → implement → governance gates)
4. **Single-file PRs ≤500 LOC** per `.cursor/rules/nucleus.mdc`
5. **Wrap-vs-build issue template** at `.github/ISSUE_TEMPLATE/wrap_request.yml`

Code of Conduct: Contributor Covenant. Governance: `GOVERNANCE.md`. Maintainers: `MAINTAINERS.md`.

### Q24. Where do I get support?

- **Bug reports + feature requests**: <https://github.com/nucleus-data/nucleus/issues>
- **Q&A and discussion**: <https://github.com/nucleus-data/nucleus/discussions>
- **Security disclosure**: per `SECURITY.md` (90-day responsible disclosure window)
- **Commercial / paid support**: not available in v0.2 (OSS only). Cloud tier (v1.0+) will include first-line support.

This is **OSS support**, not enterprise SLA. Response time depends on founder availability; community help is welcome and encouraged in Discussions.

---

## Error code reference

### Q25. What are the `NE####` error codes I see?

Every Nucleus error is typed and numbered per ADR-006. The numbering scheme:

| Band | Layer | Examples |
|---|---|---|
| **NE1xxx** | L0 Physics | `NE1001 NucleusSourceConnectionError`, `NE1002 NucleusCommitConflictError`, `NE1009 NucleusSourceAuthError` |
| **NE2xxx** | L1 Engines | `NE2003 NucleusSQLSyntaxError`, `NE2007 NucleusMemoryLimitExceeded` |
| **NE3xxx** | L2 Coordination | `NE3007 NucleusContractViolation`, `NE3008 NucleusConcurrentRunError`, `NE3009 NucleusMaintenanceError`, `NE3011 NucleusRunNotFoundError` |
| **NE4xxx** | L3 Intelligence | `NE4001 NucleusCopilotAuthError`, `NE4002 NucleusCopilotRateLimitError` |
| **NE5xxx** | L4 Experience | `NE5001 NucleusInternalError`, `NE5005 NucleusScheduleParseError`, `NE5012 NucleusDaemonStartError`, `NE5015 NucleusSnapshotNotFoundError`, `NE5018 NucleusRaceConditionDuringWrite` |

Every error has a `user_message`, `fix_hint`, `docs_url`, and `cause` (the original exception). The `docs_url` points to a fix recipe at `nucleus.dev/errors/<slug>` (currently `docs/errors/` in the repo until DNS lands).

When you see a leaked external classname (`dagster.*`, `pyiceberg.*`, `duckdb.*`, `polars.*`, `pydantic.*`, `psycopg.*`) in CLI output — **that's a release-blocking bug**, not expected behavior. File an issue at <https://github.com/nucleus-data/nucleus/issues> with the exact stack trace; it's covered by `scripts/dagster_leak_check.py` enforcement and we want to know.

Full error registry: `src/nucleus/errors.py`. Per-error fix docs: `docs/errors/`.

---

## Bonus: things people will ask that aren't in the 25

### Q26. (bonus) Is Nucleus production-ready?

**No, it's beta.** v0.2.0 is the first publicly available release. The empirical baseline at `docs/benchmarks/2026-05-15_baseline.md` documents what's verified and what's still in flight. Recommended for greenfield analytics on 100 GB–5 TB; **not recommended for mission-critical production today.**

That said: the WSL beachhead E2E (8/8 gates) does pass, real Iceberg snapshots are written, error translation discipline is enforced in CI, and 873+ tests pass. The honest position is "stable enough to evaluate seriously; not stable enough to bet your job on yet."

### Q27. (bonus) What does the project's name mean?

A nucleus is the dense, central core of an atom — the part that holds everything else together. We picked the name because:

1. The asset graph is the **dense central core** of any data platform — everything orbits it.
2. Nucleus is small (~13K LOC) but **holds together** a much larger surface area of wrapped open-source engines (DuckDB, Polars, Iceberg, Dagster, …).
3. The name doesn't claim category leadership ("the platform", "the lakehouse", "the X") — it claims **a coherent center**.

Related: per ADR-002 §8.1, "Iceberg company" is on the forbidden framings list. Iceberg is our substrate; the asset graph is our core. Nucleus is the latter.

---

*This FAQ is honest and lives in the public repo. If a question is missing or an answer is wrong, file an issue at <https://github.com/nucleus-data/nucleus/issues> and we'll fix it. Last updated 2026-05-15.*
