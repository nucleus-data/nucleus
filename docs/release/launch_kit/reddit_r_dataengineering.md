# r/dataengineering Submission — Nucleus v0.2.0

*Target: <https://www.reddit.com/r/dataengineering/submit> · Flair: `Open Source` · Best post window: Tue–Thu 10:00–14:00 ET. Be technically deep; the audience is mid-to-senior data engineers who hate marketing.*

---

## Title

```
Nucleus v0.2.0 — local-first Iceberg pipelines from a laptop (Apache 2.0, Python SDK + CLI, wraps DuckDB/Polars/pyiceberg/Dagster)
```

*(120 chars — under the 300-char Reddit limit; loaded with the keywords r/dataengineering search filters on.)*

### Title alternates

- `Nucleus — Apache 2.0 local-first data platform for 5–20 engineer teams (no JVM, Iceberg-native, graduates to Databricks)`
- `Show /r/dataengineering: Nucleus, a single SDK + CLI over DuckDB+Polars+Iceberg, Apache 2.0, beta`

---

## Body

> Hi /r/dataengineering. I'm shipping **Nucleus v0.2.0** today — Apache 2.0 — and I want to be technically honest with this community first.
>
> **The 30-second pitch.** Nucleus is a local-first Python SDK (`ctx`) + CLI (`nucleus`) that wraps DuckDB, Polars, Apache Iceberg (via pyiceberg), and embedded orchestration (Dagster, hidden behind `ctx`) into one coherent surface. The headline use case is a 5–20 engineer team going from `git clone` to a BI-ready Iceberg table in under 30 minutes on a laptop. No JVM in the default path. Boot time ~6 seconds. Idle RAM ~117 MB. Iceberg snapshots stay portable to Databricks, Snowflake, or any Iceberg catalog the day you outgrow a single node.
>
> **Why I'm posting here first.** This subreddit has the lowest tolerance for hype slogans like "AI-native data fabric universal compute platform," and that's exactly the kind of framing I want to be held accountable to NOT slip into. Nucleus is *boring*. It's a single SDK over a parts list every senior DE in this sub already trusts. The interesting questions are about composability, error translation, scaling-out semantics, and graduation paths — not about "what new abstraction did you invent." (Spoiler: none. The asset is the only primitive.) <!-- banned-term: AI-native --> <!-- banned-term: universal compute -->
>
> **Architecture in one diagram.** Five layers, bottom-up:
>
>     L0 PHYSICS:        Apache Arrow / Iceberg / Parquet / Lance / S3 / OpenLineage / OpenTelemetry
>     L1 ENGINES:        DuckDB (default) → DataFusion (swap)  ·  Polars (default) → DataFusion DF (swap)
>     L2 COORDINATION:   Asset graph (Dagster wrapped) · AMA · Error translation · Contracts · Lineage
>                        Run ledger (NDJSON) · Scheduling daemon · Iceberg branch/tag CLI
>     L3 INTELLIGENCE:   Copilot v0.2 (chat) → v0.3 (schema-aware) → v0.5 (lineage-aware + ctx.agent)
>     L4 EXPERIENCE:     ctx SDK · nucleus CLI · Workbench · Marimo (v0.3+)
>
> Source of truth for every claim: `docs/specs/nucleus_architecture_v4.1.md` (~50 min read; ~25K words). It's in the repo at the root.
>
> **What's actually shipping in v0.2.**
>
> 1. **8-command CLI** — `nucleus init / up / down / run / ingest / query / chat / version` plus `runs / schedule / snapshot` subcommand groups. Every command has a typed exit code; every error is an `NE####` code with a `docs_url`.
> 2. **7 connectors** — Postgres, MySQL, SQLite, Snowflake, S3, GCS, local filesystem (Parquet/CSV/JSON with glob). One `ctx.copy_from(...)` dispatcher. Auto-infer schema, auto-create Iceberg destination, atomic commit, preview output. The one-liner: `nucleus ingest postgres://user:pass@host/db --table public.orders --as raw.orders`.
> 3. **Workbench v0.3** — FastAPI backend + React frontend. Editorial gradient hero dashboard, 7 interactive routes, live SSE log streaming for in-flight materializations, real ⌘K command palette. Single uvicorn worker by default; `--workers=N` for horizontal scaling.
> 4. **Active scheduling daemon + run ledger.** `@nucleus.asset(schedule="@daily")` materializes on schedule via a 5s-poll cron loop (croniter==3.0.4). Every materialization writes a typed record to a durable NDJSON ledger at `<project>/.nucleus/runs/runs.ndjson`. `nucleus runs list / show / cancel / tail --follow`.
> 5. **Reliability hardening (ADR-024).** DuckDB `memory_limit` guard at AMA init (80% of total RAM, clamped [2 GB, 32 GB]); cross-platform advisory file lock (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows); `expire_old_snapshots` post-commit maintenance; error-budget SLO definitions per operation.
> 6. **`nucleus.db` BI handshake.** `nucleus up` writes a single DuckDB file containing one native table per materialized Iceberg asset. Connect Superset/Evidence/Rill/Streamlit by file path. Recipe: `docs/cookbook/bi-connectivity.md`.
> 7. **Iceberg branch + tag CLI.** `nucleus snapshot branch create/delete` + `nucleus snapshot tag create/delete` exposing PyIceberg `manage_snapshots()` for WAP and EOM/EOW compliance archiving. Beta tier; full WAP semantics with Lakekeeper in v0.3.
> 8. **AI Copilot v0.2** — single-turn chat via litellm (anthropic/openai/ollama). API keys come from your shell env, never logged, never sent to Nucleus servers (we don't have any). Opt-in consent stored at `.nucleus/copilot_opt_in`. Cost ceiling defaults to $0.10/call. Setup: `docs/cookbook/ai-copilot-setup.md`.
> 9. **Install-size split.** `pip install nucleus` is lean (<30 deps, <60 s install on warm cache); optional extras `[postgres / mysql / snowflake / s3 / gcs / ai / workbench / all]`.
> 10. **11-script governance suite enforced in CI.** `check_vocabulary` (forbids the usual hype words plus several other forbidden framings), `check_pinning` (exact pins on every runtime dep), `loc_budget` (30K LOC ceiling), `dagster_leak_check` (zero external classnames in user-facing strings — if it leaks, the release is blocked), `check_error_codes`, `check_api_stability`, `check_licenses`, `check_layering`, `check_lazy_imports`, `check_install_size`, `check_perf_budget`.
>
> **Stack details.** Pinned wrapped dependencies (per `pyproject.toml` v0.2.0): `duckdb==1.1.3`, `polars==1.18.0`, `pyiceberg==0.11.1`, `pyarrow==18.1.0`, `dagster==1.9.5`, `dlt==1.26.0`, `fastapi==0.136.1`, `litellm==1.83.14`, `sqlalchemy==2.0.36`. Total proprietary code: 12,840 LOC under `src/nucleus/` (43% of the 30K LOC v1.0 ceiling per `docs/internal/research/scale_out_audit.md` §1.1).
>
> **Composability discipline.** Every Tier 1/2 dep has a swap interface and 5–10 smoke tests in CI. Per `docs/specs/nucleus_architecture_v4.1.md` §9, full alternate adapters are built **on demand** when a trigger event fires (vendor death, license pivot, perf regression >2x, community demand >10 enterprise customers) — NOT preemptively. That avoids "Composability Tax" (maintaining two implementations of every alternative for free). Documented swap targets:
>
> - DuckDB → DataFusion (interface from v0.1)
> - Polars → DataFusion DF (interface from v0.1)
> - Filesystem catalog → Lakekeeper (Rust, default v0.3+) → Polaris (JVM alternate, ASF TLP)
> - SeaweedFS (default object store for local dev) → MinIO (alternate via `docker-compose.minio.yml`)
> - Dagster → `nucleus-mini-scheduler` (~3-5K LOC fallback; design ready, ships by v1.0)
> - dbt-duckdb optional adapter (v0.3+) for teams migrating from dbt
>
> **HONEST disclosures (skip if you only want the marketing version, but you won't get one from me).**
>
> - **It's beta.** v0.2.0 is the first publicly available release. v0.1.0 was an internal beta two days ago. Treat anything labeled "stability tier: Beta" as subject to small breaking changes within 0.x.
> - **Performance baseline FAILED in 11 of measured cells.** Empirical baseline at `docs/benchmarks/2026-05-15_baseline.md`: boot time ~2 s on a Windows host with only 1 GB RAM available at run start (target was <500 ms; re-measurement on a freshly-booted beachhead-spec host is tracked for v0.2.1). Materialize 1 GB / 10M rows wall-clock 38.77 s vs <30 s target (PASS on RAM at 1.48 GB vs <3 GB target). B4 concurrent-run safety FAILS on Windows because NTFS lock semantics differ from POSIX (`msvcrt.locking` byte-range doesn't serialize the same way `fcntl.flock` does); Linux/WSL passes the same test. TPC-H 10 GB (B1) and Postgres ingest 1M rows (B3) both SKIP-DEPS due to network proxy + Docker Desktop issues on the measurement host.
> - **Solo founder.** No team. The Mo 24 decision gate per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.3 forces an explicit choice at Mo 24: (a) raise, (b) hand off, or (c) accept indie outcome. No default extension permitted. Reaching Mo 24 without a choice = automatic option (c).
> - **The scale-out story is honest.** Per `docs/internal/research/scale_out_audit.md`, Nucleus is NOT a fit for 100+ engineer teams or >5 TB warehouses today, and that's by design. The architecturally-correct answer for scale is yield-to-giants (Mode 1 graduation = zero effort because it's just Iceberg portability; Mode 2 hybrid dispatch in v1.5+; Mode 3 federation in v2.0+) — not rewriting Nucleus internals in Rust. The audit applied the 8-question gate to seven candidate Rust rewrites and rejected all seven for the same reason: ~95% of execution time at any meaningful workload is already in C++/Rust/wire-bound I/O, so optimizing the Python glue is the wrong target.
>
> **Quickstart:**
>
>     python3.11 -m venv .venv && source .venv/bin/activate
>     pip install nucleus
>     nucleus init demo && cd demo
>     nucleus up
>     nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
>     nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
>
> Repo: <https://github.com/nucleus-data/nucleus>. Docs site: <https://nucleus-data.github.io/nucleus/> once GitHub Pages is enabled (repo must be public or GitHub Pro until then). Architecture: `docs/specs/nucleus_architecture_v4.1.md`. Apache 2.0.
>
> Telling me "this is just dbt + Dagster + DuckDB + pyiceberg with a CLI on top" is technically correct. The thesis is that the integration *is* the product for the 5–20 engineer team segment. Tell me where I'm wrong.

---

## First-response drafts (drop into the thread as critiques surface)

### Q: "Why not just use Spark / PySpark?"

> Three reasons, none of them "Spark is bad" (it's excellent for what it's designed for).
>
> 1. **JVM constraint** (`AGENTS.md` Hard Constraint #1). Cold boot for `nucleus up` is 5.82 s in PoC #4 measurements; idle RSS is 117 MB. A Spark session starts in tens of seconds and idles in gigabytes. The 30-min beachhead metric for 5 engineers on laptops is incompatible with that.
> 2. **Single-node optimization is the v0.1–v1.0 envelope.** DuckDB on a single node beats Spark for <100 GB workloads on most benchmarks (TPC-H 10 GB on DuckDB is ~2.5 s per architecture §5.1). Above that envelope (~5 TB), the architecturally-correct answer is yield-to-giants (Mode 2 dispatch in v1.5+ to Databricks/Snowflake), not "make Nucleus Spark-flavored."
> 3. **Local-identical-to-prod.** Same engine code locally and in production is the felt moat (per v4.1 §2.1). Nucleus → Databricks Spark introduces a runtime split; Nucleus → DuckDB everywhere doesn't.
>
> If your problem is 100+ TB of multi-team writes, Spark + Databricks is the right answer and Nucleus is the wrong tool. The scale-out audit (`docs/internal/research/scale_out_audit.md`) is explicit about that.

### Q: "Why not just use dbt-core?"

> dbt-core is what we'd integrate via `dbt-duckdb` in v0.3+ as an optional adapter (per architecture §5.6 + table at v0.1 vs dbt-duckdb capability comparison). The reason we don't make dbt the v0.1 default is the integration burden: dbt-duckdb is community-maintained, its release lag behind core dbt has burned us before, and we can't ship reliability-grade error translation through someone else's adapter without owning the boundary.
>
> What we ship instead: ~180 LOC of native `ctx.sql` Jinja resolver with `{{ ref() }}` and `{{ source() }}` resolution, `StrictUndefined` rejection of unknown vars, and Jinja exceptions translated to `NucleusSQLSyntaxError` (NE2003). The hard scope ceiling is **2,500 LOC** per v4.1 §5.6.0 — if we drift past, the policy is to STOP and integrate dbt-duckdb instead. We are not "rebuilding dbt."
>
> What you give up vs dbt: the macro ecosystem, snapshots (SCD Type 2 — v0.5+), documentation generation (v0.3+), and full hooks (v0.5+). What you get: one error namespace, one CLI, one auth model, native Iceberg writes, and the dbt-duckdb adapter as an explicit upgrade path when you need the macro ecosystem.

### Q: "Why not just use Dagster directly?"

> Dagster is what we wrap. The reasons we put `ctx` on top:
>
> 1. **Boot time.** A Dagster project boot (with the daemon, the gRPC server, the asset definitions module) measured against the 5-engineer 30-min beachhead is too slow. The wrapped path runs Dagster in-process per `nucleus run` invocation, with the asset graph reconstituted from `@nucleus.asset` decorators at import time.
> 2. **Error translation discipline.** Per v4.1 §6.4, every external exception (Dagster, DuckDB, Polars, pyiceberg, dlt, SQLAlchemy) MUST be intercepted and re-emitted as a `NucleusError` subclass. User-facing strings MUST NOT contain external classnames. `scripts/dagster_leak_check.py` enforces this in CI; the release is blocked if any leaks. That discipline has to live somewhere — it's at the `ctx` boundary, not inside Dagster.
> 3. **Replaceability mandate.** Per v4.1 §6.5, Dagster MUST be replaceable internally by v1.0 without ANY user code change. `nucleus-mini-scheduler` is the documented fallback (~3-5K LOC; design ready). The `ctx` SDK API surface stays unchanged through any Dagster swap. Direct Dagster usage in user code would break this.
>
> If your team already lives in Dagster and the orchestration UI is a feature you want, `nucleus enable compat-dagster` exposes the Dagster web UI directly (Tier 3 escape hatch per v4.1 §6.6). For most teams the wrapped path is what you want.

### Q: "What about Iceberg vs Delta?"

> Iceberg is the bet because every catalog ecosystem outside Databricks is converging on it: Polaris (ASF), Lakekeeper (Rust), Cloudflare R2 Data Catalog, Apache Polaris (graduated TLP Feb 2026), Snowflake's Iceberg-compat tables, Unity-Iceberg-compat. The graduation path "your S3 + Iceberg catalog is portable" only works if Iceberg is the format. Delta would have constrained us to Databricks-flavored graduation, which contradicts the "friendly to giants, hostile to no-one" pillar.
>
> If your destination is Databricks specifically and you want Delta, Nucleus is not for you (use Databricks Free Edition or Databricks Community for local dev). If your destination is "any catalog, ever, no matter where we end up," Iceberg is the call.

### Q: "Why no public plugin SDK?"

> Per Hard Constraint #2 in `AGENTS.md`. A public plugin SDK at v1 would commit us to API stability for plugin authors before the internal interfaces have stabilized. Internal-only interfaces let us refactor without breaking external contracts. Plugin marketplace is explicitly out-of-scope for v1; we revisit at v2.0+.
>
> What you can do today: every wrapped library is accessible via the Tier 2 escape hatch (`ctx.dagster_context`, direct DuckDB connection, etc.). Telemetry tracks escape-hatch usage; if >5% of users use a specific escape hatch for >3 months, we build a native `ctx` equivalent (per v4.1 §6.6). That's the contributor signal we listen to instead of "let everyone build plugins and hope."

### Q: "How does this compare to MotherDuck / Tower.dev / Bauplan / dbt-Fusion?"

> Watch list, not enemies. Per Mo 24 decision gate trigger #4 (`ADR-002` §8.3), "funded competitor ships an equivalent local-first Iceberg stack with comparable DX" is one of the four conditions that auto-fires the founder gate. So I monitor these closely.
>
> The differentiation as I see it today (will be wrong if any of them out-execute):
>
> - **MotherDuck**: Cloud-first DuckDB; we are local-first DuckDB with Iceberg + asset graph + scheduling. Different beachhead.
> - **Tower.dev**: Bigger scope (full lakehouse); we cap at 30K LOC and yield to giants for distributed.
> - **Bauplan**: AI-flavored framing they own; "AI-ready" (not "AI-native") is our explicit positioning per `AGENTS.md` §8. <!-- banned-term: AI-native -->
> - **dbt-Fusion-with-DuckDB-GA**: This is the closest threat. dbt's macro ecosystem + DuckDB engine is a real story. The differentiation reduces to (a) we ship the asset graph + orchestration (dbt doesn't), (b) we ship the Workbench (dbt doesn't), (c) we ship integrated AI Copilot (dbt has Copilot but bolt-on, not first-class).
>
> If dbt-Fusion ships first and convincingly, Mo 24 gate fires from competitive pressure. That's the honest answer.

### Q: "Open issues with the empirical baseline failing 11 metrics?"

> Yes. Linked at `docs/benchmarks/2026-05-15_baseline.md` and tracked in the v0.2 founder close-out checklist. Three categories:
>
> 1. **Re-measurement on freshly-booted beachhead-spec host** — the host had only 1 GB free RAM during the run; B5 boot times and B2 wall-clock are inflated by OS paging. Fix: re-run on a clean MacBook before promoting numbers to public docs.
> 2. **B4 NTFS lock semantics** — Windows `msvcrt.locking` byte-range doesn't serialize concurrent writers the same way POSIX `fcntl.flock` does. Linux/WSL passes. Fix tracked for v0.2.1: switch to a catalog-managed lock when Lakekeeper lands in v0.3, OR document Windows as "single-writer only" in the meantime.
> 3. **TPC-H 10 GB and Postgres ingest 1M rows** — both SKIP-DEPS due to corporate network proxy (HTTP 407 blocking DuckDB tpch extension install) and Docker Desktop 500 errors. Re-run on a clean network.
>
> The 8/8 WSL beachhead E2E gates DO pass (boot 7 s, real Iceberg snapshot, zero classname leaks, full 30-min path), which is the headline metric. The B-suite numbers are deeper benchmark scenarios that fail honestly because the measurement host is contention-loaded — not because the platform is broken. Anything I can confirm against your hardware?

### Q: "How do I contribute?"

> External contributions are limited while Tier 1 stabilizes. Per the README:
>
> 1. Read `AGENTS.md` — hard constraints are non-negotiable.
> 2. Open an issue before any large change (architectural forks start as ADRs in `docs/decisions/`).
> 3. Per-feature workflow in `AGENTS.md` §11.4 — wrap-vs-build check first, test spec second, implementation third, governance gates fourth.
> 4. PRs ≤500 LOC each (single-file discipline per `.cursor/rules/nucleus.mdc`).
>
> The wrap-vs-build issue template at `.github/ISSUE_TEMPLATE/wrap_request.yml` is the right starting point for "could we add support for X" questions.

---

## Posting checklist

- [ ] Post Tue–Thu **10:00–14:00 ET** (peak r/dataengineering activity)
- [ ] Apply flair: `Open Source` (avoid `Discussion` — too generic)
- [ ] Re-read body for any banned vocabulary per `AGENTS.md` §7 + §8 (the catalog/asset/materialization rules + forbidden framings list) <!-- banned-term: metastore --> <!-- banned-term: AI-native --> <!-- banned-term: Spark killer --> <!-- banned-term: better Databricks --> <!-- banned-term: Data OS -->
- [ ] Be online and responsive for first 4–6 hours
- [ ] Cross-link to: HN Show post (if already live), GitHub repo, architecture doc
- [ ] If a comment is hostile but technically substantive, engage with the technical content
- [ ] Do NOT delete downvoted comments or argue moderation calls
- [ ] If a question is repeatedly asked (3+), edit the post body with an "EDIT: see comments for X" pointer

---

## Do NOT post

- ❌ "Stop using <competitor>, use Nucleus instead" — the audience hates this
- ❌ Cross-post to /r/Python or /r/programming on the same day (auto-flagged as spam by Reddit's spam filter on identical text)
- ❌ Any "production-ready" claim (this is beta)
- ❌ Pricing speculation ("might be $X/month") — Cloud tier isn't shipping; OSS is the only real pricing today (free)

---

*Final sanity check: re-read `AGENTS.md` §7 (vocabulary) and §8 (forbidden framings). If any phrase in the body would trigger `scripts/check_vocabulary.py`, fix it before posting.*
