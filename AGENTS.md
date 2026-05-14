# AGENTS.md — Nucleus Project

> **Read this first.** Universal instruction file for any AI coding agent
> (Cursor, Claude Code, Codex, Aider, Continue, Cline, etc.) working on this repo.

---

## 0. Project Identity

**Nucleus ships data products from a laptop.** A local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks — built on open Apache foundations, AI-ready by design. Grows with the team. Graduates cleanly to cloud giants (Databricks/Snowflake) — or any Iceberg catalog (Polaris, Lakekeeper, Unity, R2) — when users outgrow it.

A *data product* in Nucleus terms = an Iceberg-backed asset with transformations, contracts, and lineage, consumable by BI tools, applications, or AI agents via the `ctx` SDK or the MCP server (v0.5+). See `nucleus_architecture_v4.1.md` §12.1 for the canonical *asset* definition the marketing term wraps. *(Positioning hierarchy and trade-offs documented in `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.)*

It is **not** a database, a SQL engine, a DataFrame engine, an orchestrator, a Spark replacement, a Databricks competitor, a "Data OS", an ML platform, an "AI-native data CLI", an "agent data substrate", or a vector database. Treat any drift toward those framings as a bug. <!-- banned-term: multiple -->

We own three things, forever:

1. The **asset graph** (logical model of data products)
2. The **`ctx` SDK** (the developer contract)
3. The **unified developer-first experience** (CLI + Workbench + SDK as one product, with AI assistance as a feature, not as the headline)

Everything else is rented from open source.

---

## 1. Current Phase

**v0.1.0 Foundation — released (beta) 2026-05-14.** Beachhead empirically validated; PoC #5 external-tester kit ready.

**v0.2.0 Public Launch — bundled 2026-05-15.** Wave 1 (11 builders) complete; handover commit staged; founder pushes tag.

```
[✓] Architecture v4.1 locked (supersedes v4.0 and v3)
[✓] Feature parity vs Databricks mapped
[✓] ctx SDK API specified
[✓] Asset model specified
[✓] Project layout specified
[✓] CLI surface specified
[✓] PoC plan defined (Dagster Error Translation = PoC #1)
[✓] Composability constitution formalized (interface + smoke tests)
[✓] Yield-to-giants strategy locked
[✓] Beachhead persona picked (startup data team 5-20)
[✓] v0.1 split: Hello World (Mo 0-4 CLI only) + DX (Mo 4-8 + Workbench)
[x] PoC #1: Dagster Error Translation Layer  ← PROMOTED 2026-05-13
[x] PoC #2: Native ctx.sql Jinja resolver    ← PROMOTED 2026-05-13
[x] PoC #3: ctx.copy_from SQLite → Iceberg   ← PROMOTED 2026-05-13
[x] PoC #4: nucleus up <10s boot              ← VALIDATED 2026-05-12 (5.82s, 117.3 MB)
[x] PoC #5: 30-minute beachhead validation   ← EXECUTED 2026-05-14 (WSL E2E kit run; external testers to confirm)
[✓] v0.1 Hello World CLI: all 8 commands wired (init/up/down/run/ingest/query/chat/version)
[✓] WSL beachhead E2E: 8/8 gates PASS 2026-05-14 (7s boot, real Iceberg snapshot, zero classname leaks)
[✓] v0.1.0 tag bundle: `pyproject.toml` version → 0.1.0; CHANGELOG flipped; ADRs 001–016 ACCEPTED
[✓] Wave 1 (11 builders): Workbench + 4 connectors + docs site + CI/CD + mass audit + research + release plan + roadmap + Bosch parity
[✓] v0.2.0 tag bundle: `pyproject.toml` version → 0.2.0; CHANGELOG flipped; ADRs 018–025 PROPOSED
[~] ADR-018 through ADR-025 ratification ← founder-gated
[ ] Wave 2 launch: active scheduling daemon (ADR-025 P0-1) ← gated on ADR-023/024/025 ratification
```

v0.2.0 source under `src/nucleus/` ships Workbench v0.2, 4 new connectors, 11-script governance suite, and the public docs site. Next milestone: Wave 2 implementer wave gated on ADR-023/024/025 founder ratification.

---

## 2. Required Reading (in order)

| # | Document | Purpose |
|---|---|---|
| 1 | `nucleus_architecture_v4.1.md` | **THE single source of truth** (supersedes v4.0 and v3) |
| 2 | `nucleus_vs_databricks.md` | What we are and aren't (feature parity) |
| 3 | `nucleus_ctx_sdk_spec.md` | The stable API surface — **THE product** |
| 4 | `nucleus_asset_model_spec.md` | Fundamental data primitive |
| 5 | `nucleus_project_anatomy.md` | User project layout standard |
| 6 | `nucleus_cli_spec.md` | CLI command surface |
| 7 | `nucleus_poc_plan.md` | PoCs to run before v0.1 (PoC #1 = Dagster Error Translation) |
| 8 | `nucleus_implementation_readiness.md` | Master go/no-go checklist |
| 9 | `nucleus_red_team_review.md` | Adversarial review with mitigations |

Total reading time: ~3 hours. **Required** before any non-trivial contribution.

If any doc conflicts with `nucleus_architecture_v4.1.md`, **architecture v4.1 wins.**

`docs/archive/architecture-v4.md` and `docs/archive/architecture-v3.md` are **deprecated** (archived 2026-05-15). Use only as historical reference; do not cite in new code or docs.

---

## 3. Eleven Hard Constraints (Non-Negotiable)

### Architectural Constraints

1. **No JVM in core path.** Every always-on component is Rust/Go/C++/Python.
2. **No public plugin SDK in v1.** Internal interfaces only.
3. **No custom scheduler.** Dagster is wrapped and hidden behind `ctx`.
4. **No custom compute engine.** DuckDB/Polars/Daft are wrapped, never built.
5. **No custom Iceberg commit service / transaction coordinator.** Catalog handles atomic commits.
6. **No custom auth system.** Always delegate to OIDC.
7. **No ML platform / AI training / agent hosting platform.** We assist with AI; we are not an AI/ML platform.
8. **Proprietary code budget ≤ 30K LOC by v1.0.** Tracked monthly.
9. **Composability by Constitution.** Every Tier 1/2 dependency MUST have a documented swap **interface** + smoke tests in CI. Full swap implementation built on-demand only. See v4.1 §9.

### Operating Constraints

10. **Read official documentation before integration.** Never rely on AI memory or assumed API behavior. Every wrapped component (Dagster, DuckDB, Polars, dlt, pyiceberg, SQLAlchemy, etc.) requires reading official docs before first integration AND before any version upgrade. See §11.12.
11. **Upgrade-safe stack design.** Every wrapped component MUST have: exact version pin in `pyproject.toml`, upgrade smoke tests in CI, single-component upgrade PRs (no bulk upgrades), documented rollback command, and major-version-upgrade ADR requirement. See §11.13.

Violating any of these requires explicit amendment to `nucleus_architecture_v4.1.md`.

---

## 4. The "Do NOT Build" List

These are wrapped, never built. See `nucleus_architecture_v4.1.md` §20 for full list.

- ❌ Custom scheduler → use **Dagster** (embedded, hidden); mini-scheduler as fallback only
- ❌ Custom orchestration → use **Dagster**
- ❌ Custom lineage parser → use **OpenLineage + sqlglot** (column-level v0.5+)
- ❌ Custom connectors → use **`ctx.copy_from` helper (v0.1)** / **dlt (v0.3+)** / **Sling** / **Singer**
- ❌ Custom SQL engine → use **DuckDB** (default) / **DataFusion** (swap interface)
- ❌ Custom DataFrame engine → use **Polars** (default) / **DataFusion DF** (swap interface)
- ❌ Custom multimodal engine → use **Daft** (optional, v0.5+)
- ❌ Custom vector storage → use **Lance / LanceDB** (v0.5+)
- ❌ Custom table format → use **Apache Iceberg** + **Lance**
- ❌ **Custom Iceberg commit service / distributed transaction coordinator** — catalog handles this
- ❌ Custom catalog → **filesystem (v0.1)** / **Lakekeeper (v0.3+)** / **Apache Polaris** (swap interface)
- ❌ Custom notebook runtime → use **Marimo** (v0.3+)
- ❌ Custom data quality framework → native `@nucleus.check` (v0.1) / Soda Core (v0.5+ optional)
- ❌ **Custom auth/RBAC system → always delegate to OIDC** (Authentik / Keycloak / Okta / Azure AD)
- ❌ Custom observability backend → use **OpenTelemetry + VictoriaMetrics + VictoriaLogs**
- ❌ Distributed compute → **yield to giants** via Mode 1/2/3 (Iceberg portability + dispatch)
- ❌ Multi-tenant cloud control plane → out of scope for OSS; Cloud tier only
- ❌ LLM training / model serving → out of scope (we use models, don't host)
- ❌ Column-level lineage in v0.1 (deferred to v0.5+ for SQL, v1.0 for Python)
- ❌ Full AI Copilot (schema/lineage-aware) in v0.1 (v0.2 chat only; v0.5 lineage-aware)

**Default decision is WRAP.** Build only when no viable OSS exists or wrapping costs more than building.

---

## 5. The 7-Question Decision Framework

Before proposing **any** feature, component, or abstraction:

1. Does it map to one of the five architectural layers in v4.1 §3?
2. Does it serve the **<30 minute** time-to-first-Iceberg-table beachhead metric (§1.5)?
3. Can we **wrap** it instead of building it?
4. Does it preserve the **no-JVM** constraint?
5. Does it preserve **local-identical-to-prod**?
6. Does it remain inside the **< 30K LOC** proprietary budget?
7. Is it triggered by **empirical user telemetry**, or by anxiety?
8. Is it required for v0.1 "Hello World" (Mo 0-4), or can it defer to v0.2/0.3/0.5?

**A "no" or "unclear" on any question = feature is rejected or deferred.**

---

## 6. The Five Pillars (Frame All Decisions Against)

Every architectural decision must serve at least one of these pillars without harming another:

| # | Pillar | Test |
|---|---|---|
| 1 | High performance on minimal resources | Does this hurt boot time, idle RAM, or query latency? |
| 2 | Composable by constitution | Does this introduce a non-swappable dependency? |
| 3 | AI-assisted by design | Does this make the platform easier or harder for LLMs to operate? |
| 4 | Familiar UX from proven giants | Are we inventing new vocabulary that doesn't exist in dbt/Dagster/Cursor? |
| 5 | Friendly to giants, hostile to no-one | Does this make Databricks/Snowflake graduation harder? |

---

## 7. Vocabulary (Use These Terms)

Consistency in language prevents architecture drift.

| Use | Not |
|---|---|
| **asset** | "table", "job", "task", "pipeline output" |
| **materialization** | "run output", "result" |
| **snapshot** | "version", "checkpoint" |
| **partition** | "shard" |
| **contract** | "expectation", "constraint" |
| **check** | "test", "assertion" (in asset context) |
| **source asset** | "ingestion job" |
| **wrap** | "integrate", "use" |
| **engine** | "backend" (in coordination context) |
| **module** (optional) | "plugin", "extension" |
| **catalog** | "metastore" <!-- banned-term: metastore --> |
| **`ctx`** | "context", "session" |
| **Copilot** | "AI helper", "assistant" |
| **agent runtime** | "AI runner" |
| **yield to giants** | "scale out", "go big" |
| **graduate** | "migrate" (in the context of outgrowing Nucleus) |

If you find yourself reaching for any "Not" term, **stop**. The platform's vocabulary is a contract with users; drift here equals drift everywhere.

---

## 8. Forbidden Mental Models

If you catch yourself or another agent framing the product this way, push back hard.

- ❌ "Data OS" <!-- banned-term: Data OS -->
- ❌ "Spark killer" <!-- banned-term: Spark killer -->
- ❌ "Databricks killer / replacement" <!-- banned-term: Databricks killer -->
- ❌ "Universal compute platform"
- ❌ "Own every layer"
- ❌ "AI-first platform" / "AI-native platform" (we are AI-assisted, not AI-native) <!-- banned-term: multiple -->
- ❌ "Distributed-first" (we yield to giants for distributed)
- ❌ "Plugin marketplace" (in v1)
- ❌ "Better Databricks" (we are *different*, not *better-of-the-same*)
- ❌ "ML platform" / "Feature store" / "Model registry"
- ❌ "AI-native data CLI" (Angle C — retired per `docs/decisions/ADR-002-positioning-decision-2026-05.md`) <!-- banned-term: AI-native -->
- ❌ "Agent data substrate" / "Workbench for agents" (Angle D — retired per ADR-002)
- ❌ "Iceberg company" (we use Iceberg as durable-truth substrate; we are not an Iceberg vendor or catalog — see ADR-002 §8.1)

Correct framing: **"Ship data products from a laptop — a local-first Python SDK + CLI for building Iceberg-native pipelines and analytics stacks, AI-ready by design, graduating cleanly to any Iceberg catalog when users outgrow their laptop."** (Per ADR-002 §8.1 hierarchy. Final tagline locks after PoC #5 external-tester field test per ADR-002 §8.4.)

---

## 9. Stop Conditions — Pause and Escalate

Trigger an explicit human review if any of these happen:

- More than 2 PoCs require fallback plans
- v0.1 ships > 3 months late
- Proprietary LOC exceeds 30K before v1.0
- Internal interfaces become a maintenance burden
- "We should also build X" appears in any planning doc where X is in §4 above
- A major upstream OSS we wrap breaks compatibility, hostile licenses, or dies
- Composability swap drill fails for any Tier 1 component
- AI Copilot economics break (token cost > 30% of Cloud margin)
- A pillar in §6 is violated to serve another pillar

These are not failures — they are signals to revisit `nucleus_architecture_v4.1.md`.

---

## 10. Disciplines for AI Agents Specifically

When you (an AI agent) propose changes:

1. **Cite sources.** Reference the exact doc + section (e.g., "per architecture v4.1 §6.3").
2. **Apply the 8 questions** before suggesting any new component.
3. **Default to deferring.** "Defer to vX.Y" is a valid answer; over-eagerness is a bug.
4. **Resist scope creep.** If a user request implies building something on the "do not build" list, surface the conflict before complying.
5. **Use the vocabulary.** Never silently translate to other terms.
6. **Match the philosophy.** Friction elimination > feature accumulation.
7. **Keep docs in sync.** Any architectural change requires updating `nucleus_architecture_v4.1.md` and a note in `nucleus_implementation_readiness.md`.
8. **Be brutally honest about scope.** Overpromising scope is the #1 killer of OSS projects.
9. **Respect the composability constitution.** Never introduce a non-swappable Tier 1/2 dependency.
10. **Cite official documentation URLs** when suggesting any code that uses a wrapped library. If you cannot cite, write `# NEEDS VERIFICATION` and ask the user to confirm. **Never fabricate APIs that "should exist".** See §11.12.
11. **Check current pinned version** before suggesting library usage. AI training cutoff may be stale; the API you remember may have changed. When uncertain, default to "check `/docs/compatibility.md` for current version, then verify against that version's official docs."
12. **Flag bulk upgrade requests.** If user asks to "upgrade dependencies", split into one-component-per-PR per §11.13. Never bulk-upgrade.

---

## 11. Implementation Workflow Discipline

This section governs **how** AI agents and humans collaborate during PoCs and v0.1 implementation. Read carefully before touching any code.

### 11.1 Phase Gate: No Architectural Code Before PoC #1 Passes

Until PoC #1 (Dagster Error Translation Layer) is validated:

- ✅ Allowed: PoC stubs in `/poc/` directory
- ✅ Allowed: test fixtures, validation scripts, benchmark harnesses
- ✅ Allowed: documentation, ADRs (Architecture Decision Records)
- ❌ Forbidden: Production code in `/nucleus/` (the main package)
- ❌ Forbidden: Implementing v0.1 features speculatively
- ❌ Forbidden: "Just refactoring" production code

If PoC #1 fails, large amounts of code built on top of it would need to be rewritten. Discover failure cheap.

### 11.2 Author vs Reviewer Discipline

**Default mode for Nucleus v0.1:**

- **Human authors:** test specs, abstraction boundaries, error translation logic, architectural decisions
- **AI authors:** boilerplate, type stubs, basic implementations within humman-spec'd boundaries, test expansions
- **Both review:** every PR

Do NOT invert this. The plan "AI authors everything, human reviews" produces:
- Subtle hallucinations (AI invents APIs that don't exist)
- Drift from architecture (AI optimizes for plausibility, not correctness)
- Tests that match code instead of requirements

### 11.3 The AI Boundary Map

| Task | AI quality | Human discipline |
|---|---|---|
| Decorator scaffolds (`@nucleus.asset`, etc.) | Excellent | Light review |
| Type definitions, dataclasses | Excellent | Light review |
| Basic test cases from spec | Excellent | Light review |
| Documentation generation | Excellent | Light review |
| Refactoring (rename, extract, inline) | Excellent | Review for correctness |
| Wrapping a stable OSS library | Good | Verify API actually exists |
| SQL parsing logic | Good | Verify edge cases |
| Standard CRUD logic | Good | Light review |
| Error Translation Layer (the critical 8 cases) | **Risky** | **Human writes; AI suggests** |
| `ctx.sql` Jinja resolver | **Risky** | **Human writes core; AI assists** |
| Concurrency/atomicity decisions | **Risky** | **Human authority** |
| Performance-critical paths | **Risky** | **Human authority + benchmarks** |
| Schema evolution edge cases | **Risky** | **Human authority** |
| Dagster internals interaction | **Bad** | **Human writes; AI cannot deeply reason** |

When in the "Risky" or "Bad" categories, AI's role is suggestion, not authorship.

### 11.4 The Per-Feature Workflow

Every v0.1 feature follows these 6 steps:

```
Step 1: WRAP-vs-BUILD CHECK (5 min, human)
  - Is there OSS we wrap? → wrap path, document in /docs/decisions/
  - Otherwise: justify build, log ADR

Step 2: SPEC THE TESTS (15 min, human)
  - What assertions must pass for this feature to be correct?
  - Reference architecture section + beachhead metric
  - Save tests to /tests/ with comments referencing architecture

Step 3: AI SCAFFOLDS THE IMPLEMENTATION (10 min, AI)
  - Single file or small directory only
  - Implements the typed surface
  - Wraps the OSS dependency
  - Total LOC ≤ 500 per PR

Step 4: AI EXPANDS TESTS (15 min, AI)
  - Edge cases beyond human-spec'd ones
  - Regression cases for known pitfalls

Step 5: HUMAN REVIEW (30 min, human)
  - Architecture spec match?
  - Error translation discipline (no Dagster classnames in user output)?
  - LOC budget check?
  - AI hallucinations (made-up APIs)?

Step 6: INTEGRATION RUN (10 min, automated)
  - pytest passes
  - mypy --strict passes
  - ruff check passes
  - LOC budget script confirms under ceiling
  - Beachhead E2E still passes
```

Each feature is ONE PR ≤ 500 LOC. No mega-PRs.

### 11.5 Wrap-vs-Build Decision Record

Every "build" decision (vs wrapping OSS) is logged in `/docs/decisions/` as an ADR:

```markdown
# ADR-NNN: Build [component] (not wrap)

Status: ACCEPTED | REJECTED | SUPERSEDED
Date: YYYY-MM-DD
Author: @username
Reviewers: @username1, @username2

## Context
What forced this decision? Reference architecture section.

## OSS Options Considered
- Option A: <name>, <license>, <reason rejected>
- Option B: <name>, <license>, <reason rejected>

## Decision
Build custom because: <specific reason>

## Consequences
- LOC budget impact: ~X lines
- Maintenance ownership: @owner
- Swap target documented in: <path>
- Tests verifying: <test files>

## Architecture Sections Touched
- §X.Y
- §X.Z
```

If you cannot fill out the OSS Options section honestly, the answer is "wrap, don't build."

### 11.6 LOC Budget Enforcement

Hard ceiling: **30,000 LOC** by v1.0.

Tracked monthly via `scripts/loc_budget.py`. Output committed to `/docs/budget_history.md`.

| Phase | Expected LOC |
|---|---|
| PoCs complete | ~1,000 |
| v0.1 ship | ~8,000 |
| v0.5 ship | ~18,000 |
| v1.0 ship | ~30,000 (ceiling) |

If a feature would push us past these phase-specific targets, defer it or reduce scope. Do NOT silently exceed.

### 11.7 Error Translation Enforcement

Per v4.1 §6.4:

- Every code path that catches an external exception (Dagster, DuckDB, Polars, dlt, pyiceberg, SQLAlchemy) MUST translate to a `NucleusError` subclass
- Original exception preserved as `error.cause`
- User-facing strings MUST NOT contain external class names (e.g., "OpExecutionContext", "DuckDBPyConnection")
- Validated by `scripts/dagster_leak_check.py` in CI

This is the #1 release blocker discipline.

### 11.8 Beachhead Metric as North Star

Every commit, every PR, every architectural decision must serve:

> A 5-engineer startup team, on MacBooks, with Postgres source + S3 destination, builds their first BI-ready Iceberg table from `git clone` in **<30 minutes**.

When evaluating "is this feature worth it?", ask: does this make the 30-min metric better, worse, or unchanged? Unchanged or worse = defer.

### 11.9 External Validation Cadence

PoC #5 and subsequent quarterly UX validations MUST use external engineers, not the founding team. Founding team workarounds are invisible to themselves; only strangers expose real friction.

### 11.10 Composer / Multi-File Edit Discipline

For v0.1 implementation:

- Multi-file edits (Cursor Composer, Aider whole-project edits, etc.) are **discouraged**
- Reason: architectural reviews become impossible with 10+ file diffs
- Preferred: single-file PRs with clear architectural intent
- Exception: pure renames or `ctx` SDK API surface additions (still ≤ 5 files)

Multi-file edits become safe after v1.0 when abstractions are battle-tested.

### 11.11 Architecture Drift Detection

Every 4 weeks, run a Drift Detection Pass:

```
Prompt to AI:
"Read nucleus_architecture_v4.1.md and AGENTS.md.
Then review the last 4 weeks of commits.

For each commit, flag any drift:
- Wrap-not-build violations
- Scope creep beyond current version
- Composability violations
- Error translation gaps
- Vocabulary drift
- LOC budget overruns
- Hallucinated API usage (methods that don't exist in official docs)
- Unpinned dependency versions

Be brutally honest. Cite specific files/lines."
```

Human reviews the AI's review. Don't trust AI to police AI alone.

### 11.12 Official Documentation Discipline (Hard Constraint #10)

**Rule**: Before integrating any wrapped component OR upgrading to a new version, READ the official documentation. Never rely on AI memory.

**Why this matters (especially for solo + AI workflow):**

AI hallucinations are MOST dangerous when they sound plausible. A made-up `pyiceberg.commit_atomic()` looks reasonable; it doesn't exist; it ships; it fails in prod weeks later. For a one-person team, this is catastrophic.

**Concrete requirements:**

| Situation | Required reading | Required artifact |
|---|---|---|
| First integration of an OSS component | Full Getting Started + relevant API reference sections | Notes in `/docs/research/<component>.md` |
| Adding new functionality from existing OSS component | Specific API page on official docs | Docs URL in code comment |
| Upgrading minor version (1.2.0 → 1.3.0) | Release notes + changelog | Changelog summary in upgrade PR description |
| Upgrading major version (1.x → 2.x) | Migration guide + breaking changes | ADR + migration test |
| AI suggests a method/API you don't recognize | Look it up in official docs BEFORE using | Verify or reject |

**Mandatory code conventions:**

```python
# Every external library import must be accompanied by docs reference

from pyiceberg.catalog import load_catalog
# Docs: https://py.iceberg.apache.org/api/catalog/

from polars import LazyFrame
# Docs: https://docs.pola.rs/api/python/stable/reference/lazyframe/

import duckdb
# Docs: https://duckdb.org/docs/api/python/overview
```

**For AI agents (mandatory behavior):**

- When suggesting code using a wrapped library, ALWAYS include a docs URL comment
- If uncertain a method exists, write `# NEEDS VERIFICATION` comment and flag to user
- Never fabricate API names that "should exist"
- When asked about library behavior, cite docs section, not memory

**Anti-pattern logs**: When AI hallucinates an API, log it in `/docs/research/ai_hallucinations.md` for future awareness:

```markdown
## 2026-05-15: pyiceberg.commit_atomic()

AI suggested `pyiceberg.commit_atomic()` for multi-table writes.
Reality: method doesn't exist. Actual API is `Catalog.commit_table()` 
plus app-level coordination. Caught by docs check before merge.
```

This catalog becomes priceless over time.

### 11.13 Upgrade Safety Discipline (Hard Constraint #11)

**Rule**: Wrapped components must be upgradable without breaking the stack. Design for upgrade safety from day 1.

**Why this matters (especially for solo + AI workflow):**

- Compounding upgrade debt is a slow killer (you stop upgrading → security debt → eventually forced to do a massive migration that breaks everything)
- One-person teams cannot afford 3-day debugging sessions from bad upgrades
- Wrapped components evolve faster than we expect (DuckDB ships monthly; Polars ships frequently)

**Concrete requirements:**

#### Version pinning policy

```toml
# pyproject.toml — runtime deps use EXACT pins, not ranges

[project]
dependencies = [
    "duckdb==1.1.3",          # ✅ exact pin
    "polars==1.18.0",         # ✅ exact pin
    "pyiceberg==0.8.1",       # ✅ exact pin
    "dagster==1.9.5",         # ✅ exact pin
    # NOT: "duckdb>=1.0"      # ❌ unpinned — different installs = different behavior
    # NOT: "polars~=1.18"     # ❌ minor-flex — invisible drift
]
```

Dev deps (linters, formatters) can use loose pins. Runtime deps cannot.

#### Compatibility matrix (mandatory artifact)

Maintain `/docs/compatibility.md`:

```markdown
# Compatibility Matrix (last updated: YYYY-MM-DD)

| Component | Current pin | Tested versions | Last upgrade | Next planned |
|---|---|---|---|---|
| DuckDB | 1.1.3 | 1.1.0, 1.1.1, 1.1.2, 1.1.3 | 2026-04-15 | 1.2.0 (when stable) |
| Polars | 1.18.0 | 1.16.x, 1.17.x, 1.18.0 | 2026-04-20 | Quarterly review |
| Dagster | 1.9.5 | 1.9.0 - 1.9.5 | 2026-04-01 | 1.10.x in 30 days |
| pyiceberg | 0.8.1 | 0.8.x | 2026-03-15 | 0.9.x — needs migration test |
```

#### Upgrade workflow (mandatory for every dependency upgrade)

```
1. ONE component per PR. NEVER bulk upgrade.

2. Read changelog from current_version to target_version
   (every minor release, not just target)
   Save summary in PR description.

3. Run upgrade smoke test:
   - All existing tests pass
   - Beachhead E2E passes
   - Benchmarks within 10% of pre-upgrade

4. PR description MUST include:
   - Changelog summary
   - "Rollback command" — exact `pip install` to revert
   - Behavioral changes observed
   
5. Wait 24h between merge and next dependency upgrade.
   Catch regressions before stacking changes.

6. Major version (X.y.z → X+1.y.z) ALWAYS requires:
   - ADR documenting decision + breaking changes
   - Full benchmark suite re-run
   - Optional: feature flag to gate the upgrade for canary
```

#### CI enforcement

```yaml
# .github/workflows/upgrade_check.yml

# Triggers on dependency changes only
- name: Verify exact pins
  run: python scripts/check_pinning.py

- name: Upgrade smoke test
  run: |
    pytest tests/upgrade_smoke/ -v
    python scripts/beachhead_e2e.py
    python scripts/benchmark_regression.py
```

#### Quarterly upgrade audit (mandatory cadence)

Every 3 months, dedicated 1-2 day session:
- Review compatibility matrix
- Plan upgrades for next quarter
- Identify "stale" deps (>6 months behind)
- Identify security advisories
- Update `/docs/compatibility.md`

**For one-person reality:** This sounds like a lot of overhead. It's actually *less* than the alternative (debugging mysterious failures from upgrade drift). Pay 1 day per quarter to save 1 week per year.

---

### 11.14 Subagent Model Orchestration (cost-unconstrained mode)

**Rule**: When the workflow involves multi-agent execution, many spawned subagents, long-running autonomous loops, large refactors, or architecture + implementation running in parallel, route work by **role** — not by "strongest model wins."

**Why this matters (especially for solo + multi-agent workflow):**

The naive default — "use the strongest model for everything" — burns tokens on workloads where a cheaper model is equal or better, starves the architect role of attention because it's competing with implementation tasks, and produces verbose over-engineered outputs on tasks where a swarm-tier model would be cleaner. Heterogeneous orchestration is cheaper AND faster AND more accurate.

**Core principle:**

> There is no single "best model."
> There is only the best orchestration of models.

#### Role-based model stack

| Layer | Primary role | Preferred model |
|---|---|---|
| **Architect** | Design authority, ADR owner, final reviewer, invariant keeper, subtle debugging | Claude Opus 4.7 |
| **Builder** | Autonomous implementation, terminal loops, build/test/fix iteration, CI fixing | GPT-5.5 |
| **Swarm** | Parallel file-level implementation, tests, docs, API wiring, connectors | Claude Sonnet 4.6 (4.5 fallback) |
| **Research** | Large-context repo/docs ingestion, RFC/spec analysis, ecosystem comparison | Gemini 3.1 Pro |

**Tier-B specialist:**

- **Codex 5.3** — useful for terminal-heavy code editing and CLI-centric loops; overlaps with GPT-5.5.

**Not recommended as core in unlimited-budget mode:**

- GPT-5.4 / GPT-5.2 (superseded by GPT-5.5)
- GPT mini/nano classes (use only for cheap background micro-tasks like autocomplete)
- Haiku (insufficient depth for architecture-scale platform engineering)
- Grok 4.3 (interesting for systems/infra reasoning but ecosystem/tooling not on par with OpenAI/Anthropic; do not use as primary)

#### Spawn pattern (Nucleus reference)

1. Spawn **one Architect** agent (Opus 4.7) — design authority, never burned on boilerplate.
2. Spawn **one Builder** agent (GPT-5.5) — implementation engine for long autonomous loops.
3. Spawn **3-10 Swarm** agents (Sonnet 4.6) — bounded parallel tasks (file-level changes, tests, docs).
4. Spawn **one Research** agent (Gemini 3.1 Pro) — upstream/spec/ecosystem tracking.
5. Route all integration, merge review, and invariant checks back through the Architect agent.

**Anti-pattern**: Using the strongest model for every subagent. This wastes compute, starves the architect role, and consistently produces over-engineered outputs on simple tasks.

#### Reduced-model fallback ranking

If forced to pick fewer models:

- **One model only**: Claude Opus 4.7 (best overall for serious platform engineering)
- **Two models**: Opus 4.7 + GPT-5.5 (architect + autonomous builder — sweet spot)
- **Three models**: + Sonnet 4.6 (add the swarm tier)
- **Four models**: + Gemini 3.1 Pro (add research tier — recommended for serious multi-agent in Cursor)

#### Availability fallback policy

If a preferred model is unavailable in the current tool/runtime:

1. Select the closest available model for that role (e.g., if Codex 5.3 unavailable, fall back to Sonnet 4.6 for the swarm tier).
2. **Record the fallback choice explicitly in the subagent prompt** so the human can audit.
3. Continue execution unless the user explicitly requires waiting.

**Cross-reference**: Cursor-specific subagent dispatch rules mirror this section in `.cursor/rules/nucleus.mdc`. This `AGENTS.md` version is canonical for all agent tools.

#### Concrete subagent registry (Cursor 2.4+)

The role-based model stack above is operationalized in `.cursor/agents/` as four custom subagents:

| Agent file | Tier | Use when |
|---|---|---|
| `.cursor/agents/swarm-implementer.md` | Swarm | Bounded file-level work (PoC promotions, test scaffolds, governance fixes); 25-40 min |
| `.cursor/agents/builder.md` | Builder | Multi-step iteration with build/test/fix loops (features, dep upgrades, CI fixes); 1-3 hr |
| `.cursor/agents/researcher.md` | Research | Read official docs → produce research/swap doc per §11.12 |
| `.cursor/agents/verifier.md` | Cross-tier (read-only) | Skeptical validation of any claimed completion; canonical per Cursor docs |

The Architect tier stays in foreground on the parent (Opus 4.7); we deliberately do not define a separate `architect.md` to avoid split authority. See `.cursor/agents/README.md` for routing table + escalation rules + when NOT to delegate.

Anti-pattern: defining a generic `dispatcher.md` or `orchestrator.md` — the Cursor parent agent IS the dispatcher per [Cursor docs §Subagents](https://cursor.com/docs/context/subagents).

---

## 12. When in Doubt

1. Re-read `nucleus_architecture_v4.1.md` (the locked architecture).
2. Re-read v4.1 §1.5 (beachhead persona + 30-min metric).
3. Re-read v4.1 §18 (roadmap — is the feature even in v0.1?).
4. Apply §11.4 per-feature workflow (don't skip the wrap-vs-build check).
5. Check the AI Boundary Map in §11.3 (am I in a "Risky" or "Bad" category?).
6. Re-read `nucleus_implementation_readiness.md` §4 (the 7 questions).
7. Ask: "Is this in §20 of architecture v4.1?" (Non-Goals)
8. Ask: "Does this serve one of the 5 pillars without harming another?"
9. If still unclear: stop and ask the human.

Honest preparation is the only path to perfect execution.

---

*This file is universal. Cursor-specific rules live in `.cursor/rules/`. Other agent tools (Claude Code, Codex, Aider, etc.) read this file as their primary source.*
