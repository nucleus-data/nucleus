# Nucleus Red Team Review

> Adversarial analysis of the entire Nucleus design. The job here is **not validation** — it is to find every weakness, bad pattern, fragile assumption, and risky decision that could undermine the product.
>
> Every finding has: severity, evidence, proposed fix, and which doc(s) to update.
>
> Companion to all `nucleus_*.md` specs. **Treat as authoritative for pre-v0.1 changes.**

---

## Legend

| Severity | Meaning |
|---|---|
| 🔴 **CRITICAL** | Must resolve before v0.1 commit. Could break the product strategy. |
| 🟠 **HIGH** | Resolve during v0.1–v0.3. Significant cost if deferred. |
| 🟡 **MEDIUM** | Resolve by v1.0. Manageable but accumulating risk. |
| 🟢 **LOW** | Worth tracking. Address opportunistically. |

---

# Part A — Anti-Patterns (Architectural Smells)

---

## 🔴 A1. The "Hidden Dagster" Leaky Abstraction

### What

Architecture v3 §6 commits to embedding Dagster but hiding it completely. The CLI, SDK, and Portal pretend Dagster doesn't exist.

### Why this is bad

This is the **single biggest architectural risk**. Astronomer faces this with Airflow — they wrap it, but every advanced user eventually opens Airflow UI directly.

Specific failure modes:

1. **Error messages leak.** When a Dagster materialization fails, the stack trace contains Dagster internals. Users will see "RuntimeError in `dagster._core.execution.plan.compute.execute_step`" — even if we wrap nicely.
2. **Advanced features unreachable.** Power users will want: Dagster sensors with custom Python conditions, asset-condition triggers, multi-asset partition logic, custom IO managers. We either re-expose these (defeating the hiding), or block users (losing power users).
3. **Debugging is doubled.** When something breaks, is it Dagster's bug, our wrapper's bug, or the user's code? Stack trace has 3 layers.
4. **Astronomer trap.** If our value-add is "Dagster, but easier," users eventually graduate to Dagster directly. Vercel survives Next.js because Vercel owns deployment infrastructure they can't replicate. What's our equivalent? Iceberg coordination + asset graph + UI integration. Is that enough? Unclear.

### Evidence

- `nucleus_ctx_sdk_spec.md` §14 lists "import dagster" as forbidden
- `nucleus_architecture_v3.md` §12 says Dagster is "embedded, hidden"
- No mention of how Dagster errors propagate to users
- No mention of how power users access Dagster features beyond `ctx`

### Proposed fix

**Adopt the "Progressive Disclosure" model**, three tiers:

```
Tier 1 (default 95%): ctx SDK only. Dagster fully hidden.
Tier 2 (escape hatch): `ctx.dagster_context` for advanced patterns. 
                       Documented as "you're stepping outside abstraction."
Tier 3 (full power): `nucleus enable compat-dagster` exposes Dagster UI/CLI 
                       directly for migration or power users.
```

Also: **own the error formatting**. All Dagster exceptions get rewritten into Nucleus-shaped errors with Dagster trace as `nested_cause`. No raw Dagster tracebacks reach the user.

### Docs to update

- `nucleus_architecture_v3.md` §6 — clarify the tier model
- `nucleus_ctx_sdk_spec.md` §14 — add `ctx.dagster_context` escape hatch
- New section in `nucleus_ctx_sdk_spec.md`: "Error Translation Contract"

---

## 🟠 A2. The "Single Engine, Two Languages" Confusion

### What

We have Polars (DataFrame) and DuckDB (SQL) both as "core compute." Users have to decide which to use for any given operation.

### Why this is bad

For "familiar UX," this creates cognitive load:

- A user writing transformations has to decide: "Should this be `@nucleus.asset` (Polars) or `@nucleus.sql_asset` (DuckDB)?"
- Conversion between Polars `DataFrame` and DuckDB `Relation` is Arrow-cheap but **mental load is real**.
- Two debug paths: query optimizer issues differ between engines.
- Two performance characteristics: a join optimized in DuckDB may not be in Polars and vice versa.

dbt avoided this by picking SQL only. Polars itself now has decent SQL support. DuckDB has decent Python relation API.

### Evidence

- `nucleus_ctx_sdk_spec.md` §4.1: `ctx.read()` defaults to Polars LazyFrame
- §6: `ctx.sql()` returns DuckDB relation
- No guidance on when to use which
- Examples mix both freely

### Proposed fix

**Pick one as primary execution engine; the other is a convenience.**

Recommendation: **DuckDB as primary execution engine**, Polars as developer ergonomic frontend.

```
USER writes Polars DataFrame transforms
  → translated to DuckDB Substrait plan via Polars' DuckDB output
  → executed in DuckDB
  → returned as Polars/Arrow

OR

USER writes SQL
  → executed directly in DuckDB
```

This way:
- One optimizer to tune
- One memory model
- Polars is "the writing experience"
- DuckDB is "the running engine"

Alternative: opposite direction — Polars primary, DuckDB as SQL frontend. Less clean because DuckDB SQL is more mature.

### Docs to update

- `nucleus_architecture_v3.md` §7 — clarify single execution engine
- `nucleus_ctx_sdk_spec.md` §4 — explicit conversion semantics

---

## 🟠 A3. Jinja Strings Inside Python Functions

### What

```python
@nucleus.sql_asset(table="x")
def x(ctx):
    return "SELECT * FROM {{ ref('y') }}"
```

A Python function returning a Jinja-templated SQL string.

### Why this is bad

Worst of three worlds:
- **No SQL syntax highlighting** in editors (it's a Python string)
- **No Jinja syntax highlighting** either
- **No autocomplete** for `ref()` targets
- **No static analysis** — typos in `{{ ref('typo') }}` discovered at runtime
- **Mixed templating**: Python f-strings + Jinja + SQL is three languages in one expression
- **Errors are confusing**: is it Python syntax error? Jinja parse error? SQL semantic error?

This is dbt's *worst* pattern, which they had to mitigate with dbt-jinja IDE plugins.

### Evidence

- `nucleus_ctx_sdk_spec.md` §2.2 and §6.1 show this pattern
- Multiple examples throughout specs

### Proposed fix

**Prefer `.sql` files** for SQL assets. Already partially supported in `nucleus_project_anatomy.md` §6, but downplayed.

Make this the **primary** pattern:

```sql
-- sql/analytics/daily_revenue.sql
{# @asset(table="analytics.daily_revenue", schedule="@daily") #}

SELECT date, SUM(amount) AS revenue
FROM {{ ref('fact.orders') }}
GROUP BY 1
```

`@nucleus.sql_asset` decorator usage becomes secondary, for dynamic SQL only.

Editors get proper SQL + Jinja syntax highlighting via standard dbt extensions.

### Docs to update

- `nucleus_ctx_sdk_spec.md` §2.2 — make `.sql` file pattern primary
- `nucleus_project_anatomy.md` §6 — promote `.sql` file conventions
- Examples in all docs — switch to file-based pattern

---

## 🟡 A4. `ctx.read()` Returns LazyFrame by Default

### What

`ctx.read("X")` returns `pl.LazyFrame` by default.

### Why this is bad

For "familiar UX" claim (architecture goal), LazyFrame is unfamiliar:
- SQL/dbt users expect eager results
- pandas users expect eager
- Lazy execution surprises beginners: `df.height` triggers compute, `df.collect()` requires explicit call
- Debugging is harder — error happens at `.collect()`, not at `.read()`

### Evidence

- `nucleus_ctx_sdk_spec.md` §4.1

### Proposed fix

**Default eager, opt-in lazy:**

```python
df = ctx.read("orders")               # eager pl.DataFrame
df = ctx.read("orders", lazy=True)    # pl.LazyFrame for power users
df = ctx.read("orders", as_="arrow")  # pa.Table (explicit)
```

Or:

```python
df = ctx.read("orders").collect()     # explicit collect when lazy
df = ctx.read_lazy("orders")          # separate method
```

Pick one and stick.

### Docs to update

- `nucleus_ctx_sdk_spec.md` §4.1

---

## 🟡 A5. Inconsistent 2-Part vs 3-Part Asset Naming

### What

Docs mix `sales.orders` (2-part) and `catalog.schema.table` (3-part).

### Why this is bad

- Iceberg's native naming is 3-part: `catalog.namespace.table`
- Unity Catalog uses 3-part
- BigQuery uses 3-part: `project.dataset.table`
- Snowflake uses 3-part
- Postgres uses 3-part: `database.schema.table`

If we use 2-part user-facing but 3-part underneath, we have hidden catalog routing. Multi-project setups will collide.

### Evidence

- `nucleus_asset_model_spec.md` §2.1 says "catalog.schema.table" (3-part)
- All examples use `sales.orders` (2-part)
- No explanation of how 2-part maps to 3-part

### Proposed fix

**Pick one explicitly:**

Option A (simpler): always 2-part. Catalog implicit per-project. Multi-project deploys use namespace prefixes.

Option B (more powerful): always 3-part. `default_catalog` setting auto-prepends in dev.

Recommendation: **3-part throughout**, with project-level `default_catalog: "main"` setting that lets users write 2-part in casual contexts but underlying storage is always 3-part.

### Docs to update

- `nucleus_asset_model_spec.md` §2 — settle naming
- All other docs — fix examples to be consistent

---

## 🟡 A6. The "Familiar UX" Half-Truth

### What

We claim "familiar UX from Snowflake, Databricks, dbt" but actual user experience differs significantly.

### Why this is bad

| Claim | Reality |
|---|---|
| "Snowflake-like worksheet" | Monaco editor without role switcher, warehouse picker, share-link, schedule-this-query |
| "Databricks notebook" | Marimo (reactive, no kernel) — actually quite different mental model |
| "dbt models" | First-class but no `dbt deps`, `dbt seed`, `dbt source freshness` separately |
| "Familiar git ergonomics" | True, but most data team workflows aren't git-native (vs Databricks UI-native) |

When users discover the gaps, they feel deceived. Better to under-promise.

### Evidence

- `nucleus_architecture_v3.md` §11 portal table
- `nucleus_vs_databricks.md` multiple "🎯 Better" claims

### Proposed fix

**Honest messaging:**

- "Modern, familiar **concepts**" (true)
- NOT "1:1 replacement for Databricks UI" (false)

Update marketing-adjacent docs to use "concept parity" not "experience parity." Set realistic expectations.

### Docs to update

- `nucleus_architecture_v3.md` §11
- `nucleus_vs_databricks.md` summary section

---

# Part B — Tech Stack Re-Evaluations

---

## 🔴 B1. Lakekeeper vs Polaris — Reconsider the Bet

### What

We rejected Polaris (JVM) for Lakekeeper (Rust) on ideological grounds (no-JVM design law).

### Why this is risky

Lakekeeper:
- Pre-1.0 (as of 2026)
- Single major maintainer (Vakamo)
- Tiny community vs Polaris (Apache Foundation incubator)
- Implements Iceberg REST spec but **lags on advanced features** (view spec v3, snapshot tagging, partition stats)
- If main maintainer disappears, fork costs are real

Polaris:
- Apache Foundation backing
- Snowflake + Microsoft committed
- Production-grade at Fortune 500 scale (Snowflake's open-catalog future)
- JVM is fine for **catalog services** (not compute hot-path)

**The "no JVM" law was meant to eliminate JVM in compute path** (Spark replacement). It was over-applied to ancillary services.

### Evidence

- `nucleus_architecture_v3.md` §7 lists Lakekeeper as default
- Appendix A: "rejected Polaris (JVM)"
- `nucleus_poc_plan.md` PoC #2 has fallback to Polaris

### Proposed fix

**Re-classify the JVM constraint:**

> "No JVM in compute path. Ancillary services (catalog, observability sinks) may use JVM if they are best-in-class and run as separate processes."

Make Polaris the **default catalog**. Lakekeeper becomes an option for true single-binary deploys.

This is a deliberate change to design law #1. Worth the deliberation.

### Docs to update

- `nucleus_architecture_v3.md` §3 (goals) — clarify JVM scope
- `nucleus_architecture_v3.md` §4 (design law 1) — refine no-JVM
- `nucleus_architecture_v3.md` §7 — Polaris as default
- `nucleus_poc_plan.md` PoC #2 — adjust hypothesis

---

## 🟠 B2. CDC Stack is Undefined

### What

The `streaming` module is "Bento + Iceberg streaming writes." But Bento is a stream routing tool, **not a CDC capture tool**.

### Why this is bad

Real CDC requires:
1. **Source capture** (Debezium for Postgres/MySQL, native Kafka, etc.)
2. **Stream transport** (Kafka or Redpanda)
3. **Stream processing** (transform CDC events)
4. **Iceberg sink** (write merge into Iceberg)

Bento handles step 3 (routing/transformation), but **not capture**. If we promise CDC, we need to spec all four steps.

### Evidence

- `nucleus_architecture_v3.md` §8 mentions Bento for CDC but no full pipeline
- `nucleus_vs_databricks.md` Section 8 claims streaming parity
- No spec for capture layer

### Proposed fix

**Define the full CDC stack:**

```
Capture:    Debezium-server (lightweight, no Kafka Connect needed)
Transport:  Redpanda (Kafka-compatible, no ZK, no JVM)
Routing:    Bento (existing choice)
Sink:       Iceberg streaming writes (via iceberg-rust or Bento sink)
```

Note: Debezium-server has a JVM dependency. Same trade-off as Polaris — either accept JVM in optional module OR pick a different CDC tool (e.g., **DBLog** or **PgStream**).

### Docs to update

- `nucleus_architecture_v3.md` §8 — full CDC stack spec
- `nucleus_vs_databricks.md` §8 — honest about streaming gap
- New section in architecture: "Optional Module Specifications"

---

## 🟠 B3. iceberg-rust Maturity Gap

### What

We pick iceberg-rust as primary Iceberg lib for "no JVM."

### Why this is risky

iceberg-rust (as of 2026):
- Pre-1.0, active development
- **Write path is less mature than read path**
- Limited support for: snapshot management, compaction, partition evolution, view spec v3
- May require pyiceberg fallback for write-heavy operations

If we hit gaps, we end up with **dual code paths** (read with iceberg-rust, write with pyiceberg), which is operational hell.

### Evidence

- `nucleus_poc_plan.md` PoC #2 has acknowledged this with fallback
- `nucleus_architecture_v3.md` Appendix A picks iceberg-rust without caveat

### Proposed fix

**Use pyiceberg as the primary write path, iceberg-rust as the read path.** Be explicit:

- Writes: Python (pyiceberg)
- Reads: Rust + Python (iceberg-rust + pyiceberg) via DuckDB Iceberg extension

This is acceptable because:
- Writes are not in the latency-critical path (batch oriented)
- Reads dominate query workload
- pyiceberg is production-grade

When iceberg-rust matures (post-2026), swap write path.

### Docs to update

- `nucleus_architecture_v3.md` §7 — split read/write engines for Iceberg
- `nucleus_poc_plan.md` PoC #2 — adjust criteria

---

## 🟡 B4. Marimo Bet vs Jupyter Familiarity

### What

We chose Marimo over Jupyter for "modern reactive notebooks."

### Why this is risky

Marimo:
- Smaller ecosystem
- Some libraries assume Jupyter (kernel-based widgets, certain visualization libs)
- Analyst muscle memory is Jupyter
- Hiring "data scientists" defaults to Jupyter experience
- Smaller community means smaller bug-fix bandwidth

The "modern" appeal is real, but the "familiar" goal is undermined.

### Proposed fix

**Support both, default to Jupyter for analyst-heavy teams:**

```yaml
# nucleus.yaml
notebook:
  backend: marimo  # or "jupyter" or "both"
```

In Portal, expose both as tabs. Power users pick Marimo; familiarity users get Jupyter.

Cost: +5K LOC for dual backend support. Worth it for adoption.

### Docs to update

- `nucleus_architecture_v3.md` §7, §11
- `nucleus_project_anatomy.md` add notebook backend config

---

## 🟡 B5. The Postgres Dependency in "Local-First"

### What

Local mode uses SQLite, production uses Postgres. Architecture claims "single binary local-first."

### Why this is a problem

"Single binary" plus Postgres dependency in production is contradictory. Real single-binary deploys (`fly.io`-style) need self-contained storage.

### Proposed fix

**Three options:**

1. **Embed Postgres via [pglite-rs](https://github.com/electric-sql/pglite)** — runs Postgres as embedded WASM. Niche but interesting.
2. **Use [LiteFS](https://github.com/superfly/litefs) + SQLite everywhere** — distributed SQLite. Production-grade at Fly.io.
3. **Accept Postgres dep** — drop "single binary" claim, embrace 2-binary deploy (Nucleus + Postgres).

Recommendation: **Option 2 (SQLite + LiteFS for HA)** for true local-first promise. Postgres becomes optional for enterprises that already operate Postgres.

### Docs to update

- `nucleus_architecture_v3.md` §7 — metadata DB strategy
- `nucleus_project_anatomy.md` — defaults

---

## 🟡 B6. The dlt Coverage Question

### What

We claim "100+ connectors via dlt." Reality check needed.

### Why

dlt has 50+ verified sources as of 2026. Many are community-contributed, with varying quality. For enterprise Salesforce/SAP/Oracle/Workday connectors, dlt is weaker than Airbyte (200+ commercial sources).

### Evidence

- `nucleus_vs_databricks.md` claims "dlt > Partner Connect"
- Reality: dlt is broader for open sources, narrower for enterprise SaaS

### Proposed fix

**Hybrid connector strategy:**

- dlt for open-source sources (Postgres, REST, Kafka, S3, CSV, Stripe, GitHub, etc.)
- **Airbyte (Helm-installable open source)** as optional addon for enterprise SaaS
- Sling for high-volume Postgres→S3 sync

Connector breadth is a real differentiator. Don't underinvest.

### Docs to update

- `nucleus_architecture_v3.md` §7 — connector strategy nuance
- `nucleus_vs_databricks.md` §13 — honest connector parity

---

# Part C — Process & Execution Risks

---

## 🔴 C1. PoC Time Budget is Optimistic

### What

`nucleus_poc_plan.md` budgets 1 week per PoC. Realistic time for each is 1.5–3 weeks.

### Why

- PoC #1 (Dagster embed): Dagster is complex. Mapping decorators, schedules, sensors, partitions cleanly takes time. Likely **2–3 weeks**.
- PoC #2 (Iceberg-rust + Lakekeeper): Lakekeeper setup + iceberg-rust testing + concurrent write tests. **1.5–2 weeks**.
- PoC #3 (DuckDB concurrency): Building Flight server pool + benchmark suite + measuring isolation. **2 weeks**.
- PoC #4 (Portal Dagster embed): If iframe works, fast. If not, building reactflow alternative is **2–4 weeks**.
- PoC #5 (dlt + dbt under ctx): 3 systems integration is genuinely tricky. **2 weeks**.

Total realistic: **8–11 weeks**, not 5.

### Proposed fix

**Update `nucleus_poc_plan.md` §6 with realistic estimates.** Don't deceive ourselves on timeline. If we need 10 weeks for PoCs, that's fine — better than 5-week plan that slips to 12.

### Docs to update

- `nucleus_poc_plan.md` §6, §8

---

## 🔴 C2. LOC Budget is Wildly Optimistic

### What

Architecture v3 commits to "< 25K LOC proprietary code by v1.0."

### Why this is wrong

Realistic estimates for what we build:

| Component | Optimistic | Realistic |
|---|---|---|
| `ctx` SDK (Python) | 5K | 8–10K (decorators + runtime + types + error handling + tests) |
| `nucleus` CLI (Rust) | 3K | 5–7K (~30 commands × 150 LOC + shared infra + tests) |
| Portal (TypeScript) | 10K | 25–40K (8 tabs + auth + state + lineage viz + SQL editor integration + tests) |
| Asset Registry (Rust) | 2K | 5K (migrations + queries + indexing + search + tests) |
| Iceberg commit broker | 2K | 4K |
| Installer / packaging | 2K | 5K (multi-platform, multi-target) |
| Connector marketplace UX | 5K | 10K |
| Glue + docs + tooling | 10K | 15–20K |
| **Total** | **40K** | **75–100K** |

Real estimate: **75–100K LOC by v1.0**, not 25K.

For comparison: Dagster is 200K+ LOC. Astronomer's UI alone is 50K+. Vercel CLI is 30K+.

### Why this matters

- Team sizing was based on 25K LOC
- Hiring plan assumed 2 engineers + 1 designer
- Realistic team: **4–6 engineers + 1 designer + 1 DevRel** through v1.0

### Proposed fix

**Update `nucleus_architecture_v3.md` to realistic LOC budget: ~75K.**

Update team plan in `nucleus_implementation_readiness.md` §7 — minimum viable is 4 engineers, not 2.

### Docs to update

- `nucleus_architecture_v3.md` §3 goals
- `nucleus_architecture_v3.md` §6 build table (revise LOC estimates)
- `nucleus_architecture_v3.md` §17 metrics
- `nucleus_implementation_readiness.md` §3, §7

---

## 🟠 C3. Test Strategy is Undefined

### What

`nucleus_project_anatomy.md` mentions `tests/` and `nucleus.testing.TestContext`. That's it.

### Why this is bad

For a coordination platform integrating 14 OSS components, test strategy needs:

- **Unit tests** for `ctx` SDK
- **Integration tests** for: Dagster wrap, Iceberg commit, dlt source, dbt run, Soda check
- **End-to-end tests** for: `nucleus init → up → run → query` (the v0.1 DoD)
- **Compatibility tests** across upstream versions (Dagster 1.8.x, Polars 1.x, DuckDB 1.x)
- **Performance regression suite**: queries that shouldn't get slower
- **Multi-tenant isolation tests** (PoC #3 needs this)
- **Upgrade tests**: metadata migration between versions

This is missing.

### Proposed fix

**Add `nucleus_test_strategy.md` as a new supporting doc.** Defines:

- Test pyramid for our codebase
- Mock vs real-component decisions
- Test data fixtures
- CI gate criteria
- Performance regression thresholds

### Docs to update

- New: `nucleus_test_strategy.md`
- `nucleus_implementation_readiness.md` §2.3 — add test infrastructure checklist

---

## 🟠 C4. Upstream OSS Churn is Unbudgeted

### What

We wrap 14 OSS dependencies. Each has its own release cycle, breaking changes, security advisories.

### Why this is risky

- Dagster ships breaking changes every minor (1.8, 1.9, ...)
- DuckDB ships breaking changes between 1.x minors
- Polars deprecates APIs every minor
- iceberg-rust pre-1.0 changes weekly
- Lakekeeper pre-1.0 changes monthly

Conservative estimate: **2 breaking changes per dep per year × 14 deps = 28 disruption events/year.**

Each requires: detect, evaluate, update integration tests, ship update.

**Cost: ~0.5 FTE engineer-year** for upstream churn alone, by year 2.

### Proposed fix

1. **Pin upstream versions explicitly.** Don't track `latest`.
2. **Upgrade cadence on schedule:** quarterly review of all deps.
3. **Integration test coverage per dep** so churn is detected early.
4. **Allocate 10% engineering capacity** to upstream maintenance, explicitly.

### Docs to update

- `nucleus_implementation_readiness.md` §2.4 (currently lists "verify versions" — strengthen)
- New: dependency policy doc or section

---

## 🟡 C5. Documentation Drift Risk

### What

8 architecture docs is a lot. Maintaining cross-references is real work.

### Why this is a risk

Without doc-as-code (CI checking references), docs drift:
- Spec says X, but architecture says Y
- New engineers read one but not the other
- Two-month-old decisions are forgotten

### Proposed fix

- Add CI check: every cross-reference between docs is valid
- Designate **one doc as canonical per topic** (already true with `nucleus_architecture_v3.md`)
- Quarterly doc review per `nucleus_implementation_readiness.md` §12

### Docs to update

- `nucleus_implementation_readiness.md` §12 — strengthen quarterly review

---

# Part D — Strategic & Positioning Risks

---

## 🔴 D1. The OSS Distribution Question is Unanswered

### What

Is Nucleus open source? Open-core? Commercial? Self-hosted-only? No doc addresses this.

### Why this is critical before v0.1

The license decision drives:
- Code architecture (open-core needs clear OSS/commercial split)
- Repository structure
- Contribution model
- Pricing model
- Investor pitch

Once code is committed under license X, switching is painful.

### Proposed fix

**Make this decision now, in a new doc.**

Options:

1. **Pure Apache 2.0**: like Iceberg, Polars. Compete on cloud-hosted version.
2. **AGPL + commercial license**: like MongoDB, Grafana. Self-hosted free, embed paid.
3. **BSL (Business Source License)**: like Sentry, dbt Cloud. Source-available, time-delayed OSS.
4. **Open-core**: core OSS, enterprise features (auth, governance, multi-tenant) commercial. Like GitLab.

**Recommendation: Open-core with Apache 2.0 core + commercial enterprise modules.**

- Core (Apache 2.0): ctx SDK, CLI, Portal shell, all OSS wraps
- Commercial: `auth`, `governance`, `compliance`, `multi-tenant`, cloud SaaS

This matches Vercel (Next.js OSS, hosting commercial), Supabase, etc.

### Docs to update

- New: `nucleus_distribution_model.md`
- `nucleus_architecture_v3.md` §8 — note which modules are commercial

---

## 🟠 D2. The "<10TB" Buyer Mismatch

### What

We target sub-10TB workloads. But:
- Companies with <10TB often don't have data engineers (no buyer)
- Companies with data engineers usually scope for >10TB future growth
- "We support up to 10TB" sounds limiting to buyers

### Why this is bad

Sales motion friction. CTOs hear "10TB" and think "we'll grow past this."

### Proposed fix

**Reframe the positioning:**

NOT: "Best for sub-10TB workloads"
INSTEAD: "Optimal up to 10TB single-node; transparent scaling beyond"

The scale story exists (dormant `scale` module activating Daft+Ray). We just need to be clear it's there, not removed.

### Docs to update

- `nucleus_architecture_v3.md` §3 goals — phrasing
- `nucleus_vs_databricks.md` summary

---

## 🟠 D3. Buyer Persona is Undefined

### What

All specs target the engineer-user. No spec for the buyer (CTO, VP Data, procurement).

### Why this matters

Vercel sells to developers, but procurement reads enterprise-feature lists. Same for Snowflake, Databricks.

We need:
- Compliance positioning (SOC2 roadmap, HIPAA story)
- TCO calculator showing vs Databricks
- Security & governance story
- Support & SLA tiers
- Reference customers / case studies (eventually)

### Proposed fix

**Add `nucleus_buyer_positioning.md`** covering enterprise concerns.

This doesn't change tech — it ensures we don't ship a great product nobody can buy.

### Docs to update

- New: `nucleus_buyer_positioning.md`

---

## 🟡 D4. The dbt Labs Relationship

### What

We promote dbt-duckdb as first-class. dbt Labs is a $4B company with strong opinions about how their tool integrates.

### Why this could be a problem

- dbt Labs may release "dbt Cloud Local" that competes with our Portal
- dbt-duckdb adapter is community-maintained (not dbt Labs)
- If we differentiate too much from dbt conventions, we lose the dbt-familiar UX
- If we don't differentiate, why use Nucleus over dbt + Dagster + DuckDB directly?

### Proposed fix

- **Stay close to dbt conventions.** Don't fork the Jinja templating or `ref()` syntax.
- **Contribute to dbt-duckdb.** Don't fork.
- **Plan for dbt → SQLMesh migration support** (since SQLMesh is dbt's open-source alternative gaining traction).
- **Anticipate dbt Labs competitive moves.** Have a "what if dbt Cloud Local launches" contingency.

### Docs to update

- `nucleus_architecture_v3.md` Appendix A — add SQLMesh as supported alternative
- New section: "Upstream Ecosystem Relationships"

---

## 🟡 D5. The "Local-Identical-to-Prod" Half-Promise

### What

Architecture promises "byte-identical code across dev/prod."

### Why this is hard to deliver

Subtle differences will leak:
- Local: SQLite catalog vs prod: Lakekeeper → different concurrent-write semantics
- Local: MinIO vs prod: S3 → different consistency models for some operations
- Local: in-process Dagster vs prod: distributed Dagster → different sensor evaluation timing
- Local: file-based secrets vs prod: secrets module → different retrieval latency

Code is identical. Behavior isn't. This will burn users.

### Proposed fix

**Refine the promise:**

> "Code is byte-identical across environments. Behavior is functionally equivalent for 95% of operations; edge cases (concurrent writes, eventual consistency, network failures) may differ subtly between local SQLite and production Lakekeeper. We document these explicitly."

Honest > absolute.

### Docs to update

- `nucleus_architecture_v3.md` §3 goals
- New section: "Environment Parity Caveats"

---

# Part E — Specific Bad Patterns in Specs

---

## 🟡 E1. `ctx` is Over-Loaded

### What

`ctx` carries: asset ref, run_id, partition, params, log, metrics, secrets, env, connector, read, write, sql, snapshot, trigger.

13 responsibilities on one object.

### Why this is a smell

Single-Responsibility Principle violation. Hard to mock for testing. Hard to evolve.

### Proposed fix

**Group by namespace:**

```python
ctx.io.read()           # data access
ctx.io.write()
ctx.io.sql()
ctx.io.snapshot()

ctx.run.id              # run context
ctx.run.partition
ctx.run.env

ctx.config.params       # config
ctx.config.secrets

ctx.observe.log         # observability
ctx.observe.metrics

ctx.connector           # source data
```

More verbose but clearer mental model. Easier to test specific facets.

Counter-argument: shorter ctx is more pleasant to type. Trade-off.

### Docs to update

- `nucleus_ctx_sdk_spec.md` §3, §4–§10

---

## 🟢 E2. CLI Verb Inconsistency

### What

CLI has `nucleus run` (single asset), `nucleus build` (multiple), `nucleus backfill` (range). Three verbs for similar concepts.

### Why this is a smell

Cognitive load. Why not:
- `nucleus materialize <selector>` (handles all three cases)
- `nucleus materialize fact.orders --range ...` (backfill case)

Verbs proliferate; clarity decreases.

### Proposed fix

**Consolidate:**

```
nucleus materialize <selector>           # all cases
  --partition <key>
  --range <start>..<end>
  --upstream
  --downstream
```

`run`, `build`, `backfill` become aliases to `materialize` for ergonomics.

### Docs to update

- `nucleus_cli_spec.md` §4

---

## 🟢 E3. Asset Registry as a Separate Service

### What

Architecture has "Asset Registry" as a separate Rust+Postgres component.

### Why this is unnecessary

The asset registry IS the metadata DB. Why is it a separate service?

In Dagster, asset metadata lives in the same Postgres as run metadata. Splitting them creates two systems to sync.

### Proposed fix

**Asset Registry is a logical concern, not a separate service.** It's a set of tables in the metadata DB (Postgres/SQLite), accessed by the same coordination plane code.

Simplifies architecture.

### Docs to update

- `nucleus_architecture_v3.md` §3 (build table) — remove "Asset Registry" as separate component
- `nucleus_implementation_readiness.md` §3 — adjust LOC accounting

---

# Part F — Summary & Prioritized Action Plan

---

## All Findings Summary

| # | Severity | Finding | Doc(s) affected |
|---|---|---|---|
| A1 | 🔴 | Hidden Dagster leaky abstraction | architecture, ctx_sdk |
| A2 | 🟠 | Polars/DuckDB dual-engine confusion | architecture, ctx_sdk |
| A3 | 🟠 | Jinja in Python strings | ctx_sdk, project_anatomy |
| A4 | 🟡 | LazyFrame default in ctx.read | ctx_sdk |
| A5 | 🟡 | 2-part vs 3-part naming inconsistency | asset_model, all |
| A6 | 🟡 | "Familiar UX" half-truth | architecture, vs_databricks |
| B1 | 🔴 | Lakekeeper vs Polaris reconsider | architecture, poc_plan |
| B2 | 🟠 | CDC stack undefined | architecture, vs_databricks |
| B3 | 🟠 | iceberg-rust write maturity | architecture, poc_plan |
| B4 | 🟡 | Marimo vs Jupyter notebook bet | architecture |
| B5 | 🟡 | Postgres dep in "local-first" | architecture, anatomy |
| B6 | 🟡 | dlt connector coverage | architecture, vs_databricks |
| C1 | 🔴 | PoC time budget optimistic | poc_plan |
| C2 | 🔴 | LOC budget wildly optimistic | architecture, readiness |
| C3 | 🟠 | Test strategy undefined | new doc needed |
| C4 | 🟠 | Upstream OSS churn unbudgeted | readiness |
| C5 | 🟡 | Doc drift risk | readiness |
| D1 | 🔴 | OSS distribution model unanswered | new doc needed |
| D2 | 🟠 | "<10TB" buyer mismatch | architecture, vs_databricks |
| D3 | 🟠 | Buyer persona undefined | new doc needed |
| D4 | 🟡 | dbt Labs relationship unplanned | architecture |
| D5 | 🟡 | Local-identical-to-prod promise too absolute | architecture |
| E1 | 🟡 | ctx is over-loaded | ctx_sdk |
| E2 | 🟢 | CLI verb inconsistency | cli_spec |
| E3 | 🟢 | Asset Registry as separate service | architecture, readiness |

**Total: 25 findings.** 6 critical, 8 high, 9 medium, 2 low.

---

## Critical Path Before v0.1 Commit

The 6 🔴 findings **must** be resolved or explicitly accepted before any code:

1. **A1 — Hidden Dagster strategy.** Adopt three-tier disclosure model.
2. **B1 — Catalog choice.** Default Polaris, allow Lakekeeper.
3. **C1 — PoC timeline.** Revise to 8–11 weeks.
4. **C2 — LOC budget.** Revise to ~75K. Team plan to 4–6 engineers.
5. **D1 — Distribution model.** Decide open-core (recommended) vs alternatives.
6. **A2 — Engine consolidation.** Pick DuckDB as primary execution; Polars as developer ergonomic frontend (or vice versa, but pick).

These six together represent **the actual readiness gate.** Without resolving them, we're committing to an architecture with known structural risks.

---

## Recommended Sequence

| Week | Action |
|---|---|
| 1 | Decision meeting: resolve 6 🔴 findings; update architecture v3 |
| 2 | Resolve 🟠 findings A2, A3, B2, B3, C3, C4, D2, D3 |
| 3 | Create missing docs: distribution_model, test_strategy, buyer_positioning |
| 4 | Revise PoC plan with realistic timelines (8–11 weeks total) |
| 5–13 | Run PoCs against revised plan |
| 14 | Go/No-Go gate |
| 15+ | v0.1 implementation |

Total time **to v0.1 build start: ~14 weeks**, not 5–8 as originally implied.

This is the honest timeline.

---

## What I'd Change If I Were the Founder

Top 5 changes in order of leverage:

1. **Realistic team & timeline.** Budget for 4–6 engineers + 14 weeks pre-build. Anything less ships v1.0 late.

2. **Decide OSS distribution model now.** Open-core with Apache 2.0 core. Plan commercial modules early.

3. **Default to Polaris for catalog.** JVM in catalog is a non-issue. Lakekeeper is too immature for v1.0 commitment.

4. **Pick one execution engine: DuckDB primary, Polars ergonomic.** Stop pretending both are core.

5. **Adopt three-tier Dagster disclosure.** Don't pretend it doesn't exist; provide escape hatches.

The other 20 findings are real but not foundational. The 5 above are foundation-shaking.

---

## What This Review Did NOT Find

For balance:

- **Asset-centric data model** is sound. Dagster's mental model translates well.
- **Iceberg + Arrow + Parquet** as physics is uncontroversial.
- **Wrap-not-build philosophy** is correct (with caveats above).
- **The Robinhood thesis** is genuinely strong.
- **The 7-question decision framework** is well-designed.
- **Familiar concepts (asset, snapshot, contract, check, source)** are right.
- **The single-binary local boot promise** is achievable.
- **Local-first as differentiation** is real and unfilled in market.

The bones are right. The skeleton needs adjustments before flesh.

---

## Final Verdict

The Nucleus design is **architecturally sound but has six structural risks** that would damage execution if uncorrected. The proposed fixes are well-bounded: 14 weeks of additional planning resolves them all.

**Recommendation: do not start v0.1 implementation yet.** Resolve the 6 🔴 findings; revise the architecture; then proceed.

Yes, this delays the build. **Yes, it's the right call.** Architectural debt incurred at v0.1 compounds for years.

The whole point of this review is to spend 2 weeks now to save 2 quarters later.

---

*Honesty before commitment. Brutality before bonding. Red team before green light.*
