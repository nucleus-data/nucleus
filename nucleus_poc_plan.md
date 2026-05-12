# Nucleus PoC Validation Plan

> Technical hypotheses that must be validated **before** committing to v0.1 implementation. If any fails, the architecture changes — not the timeline.
>
> Companion to `nucleus_architecture_v4.1.md` (risk register §19; PoC priorities Appendix C).
>
> **Updated for v4.1**: PoC priority reordered after senior engineer review. **PoC #1 is now Dagster Error Translation Layer** — the most architecturally critical bet.

---

## 0. Why PoCs Before Code

The Nucleus architecture rests on non-obvious technical bets. Each one, if wrong, requires significant rework. The cost of validating each is **~1-2 weeks**. The cost of building on a wrong assumption is **3+ months**.

**Rule**: every PoC has a *hypothesis*, a *validation criterion*, a *time budget*, and a *fallback plan*. If the PoC misses its criterion, we adopt the fallback — not extend the budget.

**Critical PoC ordering (v4.1):**

| Week | PoC | Why this order |
|---|---|---|
| 1-2 | **PoC #1: Dagster Error Translation Layer** | Asymmetric risk — if leaky, entire "wrap Dagster" thesis fails. Discover NOW. |
| 3-4 | PoC #2: Native ctx.sql Jinja resolver | Lower risk (fallback: dbt-duckdb). Validates ~1000 LOC budget assumption. |
| 5 | PoC #3: nucleus ingest one-liner | Validates ~200 LOC ctx.copy_from helper. Beachhead-critical. |
| 6 | PoC #4: nucleus up <10s | Validates boot time target with MinIO + filesystem catalog + Dagster. |
| 7-8 | PoC #5: End-to-end 30-minute beachhead validation | Live test with real 5-engineer team. |
| 9-10 | (Legacy) Iceberg-rust + filesystem catalog E2E | Lower priority now that Lakekeeper is deferred to v0.3. |

---

## 1. PoC #1 — Dagster Error Translation Layer (NEW IN v4.1, HIGHEST PRIORITY)

### Hypothesis

> Every Dagster error type can be intercepted at the `ctx` SDK boundary and re-emitted as a clean `NucleusError` with: plain-language explanation in user vocabulary, suggested fix, doc reference, and original cause preserved.

### Why this matters MOST

If error translation fails:
- "Wrap Dagster" thesis collapses (Tier 1 promise: 95% users never see Dagster)
- Forces a choice: expose Dagster directly (philosophy violation) OR build `nucleus-mini-scheduler` early (3-5K LOC scope explosion)
- Both alternatives break v4.1's architectural integrity

This is the single biggest abstraction bet in the architecture. **Discover failure here in Week 1-2, not Month 6.**

### Validation criteria (ALL 8 errors must translate cleanly)

1. **Asset materialization failure** (Python exception in `@nucleus.asset` body)
2. **SQL execution error** (DuckDB throws during `ctx.sql()`)
3. **Out-of-memory crash** (DuckDB or Polars exceeds RAM)
4. **Iceberg commit conflict** (concurrent write detected by pyiceberg/catalog)
5. **Dependency asset not yet materialized** (upstream missing)
6. **Schema mismatch / contract violation** (output doesn't match declared schema)
7. **Timeout / cancellation** (run killed by signal or timeout)
8. **Concurrent write conflict** (two runs of same asset overlap)

For each error type:
- ✅ Translates to a `NucleusError` subclass with structured fields
- ✅ Zero Dagster class names leak to user-facing output (`stdout`, `stderr`, logs, exception message)
- ✅ Original cause accessible via `--verbose` flag (preserved on `__cause__`)
- ✅ `fix_hint` is concrete and actionable
- ✅ `docs_url` follows convention `https://nucleus.dev/errors/<slug>` (numeric NUC-XXX codes deferred post-v0.5; see v4.1 §6.4)

### Time budget

**2 weeks (1 engineer).**

### Validation script (skeleton)

```python
# poc1_error_translation.py
import nucleus
import pytest

def test_asset_failure_translation():
    @nucleus.asset(table="test.broken")
    def broken(ctx):
        raise ValueError("intentional failure")

    with pytest.raises(nucleus.NucleusError) as exc:
        nucleus.materialize("test.broken")

    assert "test.broken" in exc.value.user_message
    assert "dagster" not in str(exc.value).lower()
    # Until per-scenario translators land, the fallback uses a known slug.
    assert exc.value.docs_url.endswith("/errors/translation-not-implemented")
    assert exc.value.fix_hint  # non-empty string
    assert exc.value.asset == "test.broken"
    assert exc.value.__cause__ is not None  # original ValueError preserved

# Similar tests for all 8 error scenarios...
```

### Fallback plan if it fails

| Scenario | Response |
|---|---|
| 1-2 error types cannot translate cleanly | Document as known leaks; ship Tier 2 escape hatch warning. Acceptable. |
| 3-4 error types cannot translate | Escalate. Consider building `nucleus-mini-scheduler` POC by v0.5 to reduce Dagster dependency. |
| 5+ error types cannot translate | **Architectural reset.** Dagster abstraction has failed. Build `nucleus-mini-scheduler` from start (adds ~3-5K LOC to v0.1; 2-3 months added to timeline). |

### Definition of done

PR review by all founding engineers. Test suite passes. `/docs/swap/dagster.md` updated with findings. Decision recorded in architecture log.

---

## 2. PoC #2 — Native `ctx.sql` Jinja Resolver (NEW IN v4.1)

### Hypothesis

> ~1000 LOC of native code (Jinja templating + sqlglot for SQL parsing) can replace 80% of `dbt-duckdb` functionality for v0.1 needs.

### Why this matters

Per v4.1 D13, native ctx.sql is the v0.1 default (not dbt-duckdb). If implementation cost blows past ~2500 LOC or DAG resolution is slow, we'd be better off integrating dbt-duckdb despite its fragility.

### Validation criteria

1. **`{{ ref('schema.table') }}` resolves** to actual Iceberg table reference at query time
2. **`{{ source('schema.table') }}` resolves** for external sources
3. **Basic macros work**: `date_trunc`, `dateadd`, `current_timestamp`, custom user macros
4. **Multi-CTE SQL** with refs works correctly
5. **Incremental config** (`{{ config(materialized='incremental', unique_key='id') }}`) honored
6. **DAG resolution** for 100-asset project: <500ms
7. **Total native code**: <2500 LOC (target ~1000)

### Time budget

**2 weeks (1 engineer).**

### Fallback plan

If LOC blows past 2500 OR DAG resolution slow OR multi-CTE breaks: **fall back to dbt-duckdb as v0.1 default**. Accept fragility risk; document migration path.

---

## 3. PoC #3 — `nucleus ingest` One-Liner (NEW IN v4.1)

### Hypothesis

> ~200 LOC of SQLAlchemy + pyiceberg gives auto-infer + auto-create + atomic-commit for Postgres/MySQL/SQLite + CSV/Parquet/JSON, satisfying the beachhead 30-minute metric.

### Why this matters

Per v4.1 §1.5, the 30-minute beachhead promise breaks if first-table requires Python code or external tools. `nucleus ingest postgres://...` is non-negotiable.

### Validation criteria

1. `nucleus ingest postgres://user:pass@host/db --table public.orders --as raw.orders` runs successfully
2. Schema auto-inferred (column names + types correct)
3. Iceberg destination table auto-created
4. Atomic commit (no partial writes)
5. Preview shows 10 rows after completion
6. Works for: PostgreSQL, MySQL, SQLite, CSV, Parquet, JSON (6 sources)
7. Total ingestion LOC: <500

### Time budget

**1 week (1 engineer).**

### Fallback plan

If a source family fails, reduce v0.1 supported sources to 3 (PostgreSQL + CSV + Parquet). Defer others to v0.3 with dlt.

---

## 4. PoC #4 — `nucleus up` <10s Boot

### Hypothesis

> MinIO + filesystem catalog (pyiceberg) + Dagster in-process boots in <10s on an M1 MacBook Pro 16GB.

### Validation criteria

1. Cold boot (fresh `git clone`): <10s
2. Warm boot (subsequent): <3s
3. Idle RAM: <500MB
4. All components reachable (MinIO API, catalog read/write, Dagster sensor running)

### Time budget

**1 week (1 engineer).**

### Fallback plan

If >10s but <15s: optimize startup order, lazy-init non-critical components. If >15s: investigate Dagster startup overhead specifically — may need to lazy-init Dagster on first asset run.

---

## 5. PoC #5 — End-to-End 30-Minute Beachhead Validation

### Hypothesis

> A 5-engineer team, given laptops + Postgres source + S3 destination, can `git clone` a Nucleus template project, modify it, and have a BI-ready Iceberg table within 30 minutes.

### CRITICAL METHODOLOGICAL RULE: External Testers Mandatory

**Participants MUST be external to the founding team.**

Why this is non-negotiable:
- Founding team engineers subconsciously work around every rough edge
- They know which docs to read, which commands have typos, which error messages mean what
- "Works for the team" tells us nothing; "works for strangers" tells us everything
- Internal validation = optimism bias inflated by 50%+

**How to recruit:**
- 3-5 engineers from professional network who have NEVER seen Nucleus
- Mid-level data engineers (2-5 years experience) preferred — they're the beachhead
- Each given fresh MacBook (no Nucleus pre-installed)
- Compensated $200-500 for 2-hour session
- Recorded screen + think-aloud protocol

**Where they get stuck = where Nucleus is actually broken.**

### Validation criteria

1. Live test with 3-5 **external** data engineers (recruited from outside founding team)
2. Each completes the task end-to-end without founder intervention
3. Median time: <30 min
4. P90 time: <45 min
5. Every stuck point documented (must be addressable in v0.1)
6. Subjective rating: "Would you use this for a real project?" → >3/5 from at least 3/5 testers

### Time budget

**2 weeks** (planning + recruitment + execution + analysis).

### Fallback plan

If median >45 min or stuck-points reveal architectural issues, **delay v0.1 ship date** and fix root causes. Beachhead metric is non-negotiable.

Specifically:
- 1-2 stuck points fixable in <2 weeks → fix and retest with new testers
- 3+ stuck points OR architectural issue → return to v4.1 architecture amendment cycle

---

## 6. (Legacy) Dagster Library Embedding Validation

> **Note (v4.1):** This validation was originally PoC #1 in v3/v4.0. Its core concerns (library embedding, zero leakage, embedded scheduler) are now distributed across new PoCs #1 (Error Translation), #4 (boot time), and the v1.0 Dagster Replaceability Mandate (§6.5 of v4.1 architecture). Kept here for technical reference.

### Original Hypothesis

> Dagster can be embedded as a Python library (not a separate service) and fully hidden behind the `ctx` SDK. Users never need to know Dagster exists.

### Validation criteria (still relevant, covered across new PoCs)

1. **Library embedding**: Dagster's `Definitions`, `materialize`, and sensor APIs work from inside a Python library without spawning `dagster-daemon`. → **Covered by new PoC #4**
2. **API mapping**: `@nucleus.asset` decorator translates 1:1 to `@dagster.asset` semantics. → **Covered by v0.1 implementation phase**
3. **Zero leakage**: User code completes full lifecycle without importing `dagster.*`. → **Covered by new PoC #1 (Error Translation) + Replaceability Mandate**
4. **Embedded scheduler**: Schedules tick correctly from our process; no daemon. → **Covered by new PoC #4**
5. **UI bypass**: Run history retrievable via GraphQL/DB. → **Deferred to v0.2 Workbench implementation**
6. **Asset graph extraction**: Read at runtime for our UI. → **Deferred to v0.2 Workbench implementation**

### Original validation script (retained for reference)

```python
import nucleus
import polars as pl

@nucleus.asset(table="test.orders", schedule="@daily")
def orders(ctx):
    return pl.DataFrame({"id": [1, 2, 3], "amount": [100, 200, 300]})

@nucleus.asset(table="test.totals")
def totals(ctx):
    df = ctx.read("test.orders")
    return df.select(pl.col("amount").sum().alias("total"))

nucleus.materialize_all()
nucleus.runs()
nucleus.backfill("test.orders", range="...")
nucleus.start_scheduler()
```

---

## 7. (Legacy) Iceberg-rust + Lakekeeper E2E

> **Note (v4.1):** Lakekeeper is **deferred to v0.3** per Amendment 4. v0.1 uses filesystem catalog via pyiceberg. This PoC is rescheduled to before v0.3 implementation, not before v0.1.

### Hypothesis

> `iceberg-rust` + `pyiceberg` (Python bindings) + Lakekeeper (Rust REST catalog) can handle our full v0.3+ workload: create tables, write Parquet, commit snapshots, read back, time-travel, schema-evolve. Without any JVM component.

### Why this matters

We have a "zero JVM" design law. If iceberg-rust has spec gaps that force us to fall back to PyIceberg-with-Java or even JVM Iceberg, the whole "no JVM" promise breaks.

### Validation criteria

1. **Table creation** via Lakekeeper REST API with Iceberg schema.
2. **Atomic writes** of 100K and 10M row Parquet datasets, committed as Iceberg snapshots.
3. **DuckDB reads** the resulting Iceberg table directly (via the iceberg extension).
4. **Polars reads** the resulting Iceberg table via PyIceberg.
5. **Schema evolution**: add column, drop column, rename column — all without rewriting data.
6. **Time travel**: read at `version=N`, `version=N-1`.
7. **Partition evolution**: change partition spec on an existing table.
8. **Concurrent writes**: two writers committing simultaneously, optimistic concurrency works.
9. **Compaction**: run Iceberg compaction action, file count reduces, data unchanged.
10. **No JVM**: `ps aux | grep -i java` returns nothing throughout.

### Time budget

**1 week.**

### Fallback plan if it fails

- **If iceberg-rust has spec gaps**: use PyIceberg (Python) as the primary writer. Adds a Python dep but no JVM. PyIceberg is mature.
- **If Lakekeeper is unstable**: use file-based catalog (SQLite + Iceberg manifests on disk) for v0–v0.5. Add Lakekeeper later when stable.
- **If both fail**: defer to JVM-based Polaris with explicit acknowledgement that "zero JVM" is aspirational for v1. Update architecture §3.

---

## 8. (Legacy) DuckDB Arrow Flight Concurrency

> **Note (v4.1):** Multi-user Workbench concurrency is **deferred to v0.5+** (Workbench itself arrives in v0.2 with single-user focus). This PoC rescheduled accordingly.

### Hypothesis

> A pool of DuckDB processes exposed via Arrow Flight can serve concurrent SQL queries from multiple users (notebook, Portal, BI tool) with acceptable performance and isolation.

### Why this matters

DuckDB is embedded by design. To serve a multi-user team, we need a strategy. If concurrent users cause DuckDB to bottleneck, OOM, or corrupt state, we have a fundamental problem.

### Validation criteria

1. **10 concurrent users** running 100GB-scale queries simultaneously without crashes.
2. **Per-user isolation**: one user's heavy query doesn't kill another user's session.
3. **Latency p99 < 5s** for simple aggregation queries on 10GB Iceberg tables.
4. **Resource isolation**: memory limit per session is honored.
5. **Connection reuse**: clients reconnecting don't trigger full Iceberg metadata refetch.
6. **Graceful degradation**: when pool is saturated, queries queue rather than fail.
7. **Cache coherence**: when an asset is re-materialized, all sessions see new data on next query.

### Architecture being validated

```
Portal / Notebook / BI tool
        │ Arrow Flight (gRPC)
        ▼
   [Flight server]
    ├─ DuckDB proc 1
    ├─ DuckDB proc 2
    └─ DuckDB proc N    (process pool, per-tenant or per-session)
        │
        ▼
   Iceberg tables on MinIO
```

### Time budget

**1 week.**

### Fallback plan if it fails

- **If pool is slow**: investigate DuckDB's native HTTP/Flight integration in 2026 (their roadmap).
- **If isolation is poor**: spawn DuckDB-per-session (heavier but isolated).
- **If concurrency is fundamentally bad**: swap to **chDB** (ClickHouse embedded) as the SQL engine. Same Arrow contract; ClickHouse is multi-tenant by design. Update architecture Appendix A.

---

## 9. (Legacy) Portal Embed of Dagster UI

> **Note (v4.1):** Portal is **deferred to v0.5+**. v0.2 Workbench is built from scratch (Monaco + custom asset list, no Dagster UI embed). This PoC removed; may be replaced by a Workbench design PoC closer to v0.2.

### Hypothesis

> We can embed Dagster's existing asset-graph UI cleanly inside our Portal (as one panel/tab) while wrapping it with our own navigation, theming, and asset metadata overlay — well enough that users perceive it as "Nucleus".

### Why this matters

Architecture §15 v0.3 says "Phase 1 embeds Dagster UI in iframe; native panels replace later." If this embedding feels jarring or impossible to integrate, our v0.3 timeline blows up because we'd have to build a Dagster-equivalent UI from scratch.

### Validation criteria

1. **Iframe or component embed**: Dagster UI loads inside our Portal shell.
2. **Auth pass-through**: a user logged into Nucleus is auto-authenticated to Dagster UI.
3. **Theme alignment**: at minimum, dark/light mode follows Portal setting; ideally CSS overrides work.
4. **Navigation feels unified**: clicking from Nucleus "Assets" tab to "Runs" tab doesn't feel like leaving the app.
5. **Asset name resolution**: user clicks an asset in Dagster UI → Portal can intercept and overlay Nucleus metadata (contract status, owner, tags).
6. **Data freshness**: Dagster UI reflects materialization status within 5 seconds of completion.

### Time budget

**3–5 days.**

### Fallback plan if it fails

- **Tier 1**: Use Dagster's GraphQL API and render asset graph + runs in our own React components using `reactflow`. More work (~4 weeks), but cleaner.
- **Tier 2**: Use Dagster UI as a separate page accessed via "Advanced view" button. Less polish but works.

---

## 10. (Legacy) dlt + dbt-duckdb Under `ctx`

> **Note (v4.1):** Per Amendment 6, native `ctx.sql` replaces dbt-duckdb in v0.1. Per Amendment 13, `ctx.copy_from` replaces dlt in v0.1. dlt and dbt-duckdb become optional adapters in v0.3+. This PoC re-targets to v0.3 implementation gate, not v0.1.

### Hypothesis

> Both dlt (connectors) and dbt-duckdb (SQL transformations) can be wrapped behind `ctx` such that:
> - dlt source assets and dbt models appear in the same asset graph
> - lineage flows continuously (source → dbt model → downstream Python asset)
> - users don't need to write `dlt.pipeline(...)` or `dbt run` separately

### Why this matters

These are two of our biggest "rented" components. If they don't integrate cleanly into our asset graph, we either lose them (huge feature regression) or expose them directly (lose coherence).

### Validation criteria

1. **dlt as `@nucleus.source`**: a Postgres source defined via `ctx.connector.postgres(...)` works end-to-end — fetch, schema infer, incremental load, write to Iceberg.
2. **dbt model as `@nucleus.sql_asset`**: a `.sql` file with `{{ ref() }}` syntax is registered as a Nucleus asset and materialized via dbt-duckdb internally.
3. **Cross-system lineage**: dlt source → dbt model → Python asset all appear as connected nodes in the asset graph.
4. **Schedule unification**: a dbt model's schedule is set via `@nucleus.sql_asset(schedule=...)`, not via dbt's `schedule` configs.
5. **Failure handling**: dbt model failure shows up in Nucleus runs view with proper error context.
6. **Existing dbt project migration**: an existing `dbt-duckdb` project can be dropped into `sql/` directory and runs with minimal changes.

### Time budget

**1 week.**

### Fallback plan if it fails

- **dlt fails**: fall back to writing custom Polars-based source assets for the top 10 sources (Postgres, MySQL, Stripe, REST, S3, GCS, CSV, Parquet, Kafka, JSON). Defer the long tail.
- **dbt-duckdb fails**: support pure `@nucleus.sql_asset` (our own SQL execution) and accept that users can't drop in existing dbt projects in v0.5; promote that feature to v1.0.

---

## 11. Combined PoC Schedule (v4.1)

| Week | PoC | Output | Priority |
|---|---|---|---|
| 1-2 | **#1 Dagster Error Translation Layer** | All 8 error types translate cleanly; zero Dagster classnames leak | 🔴 CRITICAL |
| 3-4 | #2 Native `ctx.sql` Jinja resolver | <1000 LOC handles ref/source/macros/CTE/incremental | 🟠 HIGH |
| 5 | #3 `nucleus ingest` one-liner | Auto-infer + atomic commit for 6 source types | 🟠 HIGH |
| 6 | #4 `nucleus up` <10s boot | Cold boot under 10s on M1 16GB | 🟡 MEDIUM |
| 7-8 | #5 30-min beachhead validation | Live 5-engineer team test | 🟡 MEDIUM |

**Total time: 8 weeks.** Run by 1-2 engineers in parallel where possible.

**Compressed schedule**: PoCs #2-4 are independent of #1; can run in parallel if 2 engineers available, reducing total to 4-5 weeks.

**Pre-v0.3 PoCs (later schedule):**
- Iceberg-rust + Lakekeeper E2E → before v0.3 implementation
- DuckDB Arrow Flight Concurrency → before v0.5 multi-user
- dlt + dbt-duckdb integration → before v0.3 connectors

---

## 12. PoC Report Template

Each PoC produces a report:

```markdown
# PoC #X: <title>

## Result: ✅ PASS | ⚠️ PASS WITH CAVEATS | ❌ FAIL

## Criteria Met
- [x] Criterion 1
- [x] Criterion 2
- [ ] Criterion 3 (failed because…)

## Findings
<what we learned, surprising things>

## Recommendation
- [ ] Proceed with planned architecture
- [ ] Proceed with modification: <describe>
- [ ] Trigger fallback plan: <which tier>

## Artifacts
- Repo: <link>
- Benchmark data: <link>
- Notes: <link>
```

---

## 13. Decision Gates

After PoCs complete, hold a single explicit go/no-go review:

| Outcome | Action |
|---|---|
| All 5 ✅ | Lock architecture, start v0.1 implementation |
| PoC #1 ❌ | **STOP.** Architectural reset. Build `nucleus-mini-scheduler` from start (adds 2-3 months to v0.1). Update `nucleus_architecture_v4.1.md` §6.4 accordingly. |
| PoC #2 ❌ | Use dbt-duckdb as v0.1 default. Update v0.1 scope to include dbt-duckdb integration. |
| PoC #3 ❌ | Reduce supported sources to 3 (Postgres + CSV + Parquet). Document gap. |
| PoC #4 ❌ | Investigate boot bottleneck; if Dagster is culprit, lazy-init it on first asset run. |
| PoC #5 ❌ | **STOP.** Beachhead metric is non-negotiable. Fix root causes, retest. Delay v0.1 ship. |
| 1-2 ⚠️ | Implement fallback plans; proceed with caveats. |
| 3+ ⚠️ | Stop. Revisit architecture. Update `nucleus_architecture_v4.1.md`. |

**Do not start v0.1 implementation until this gate is cleared.** This is the single most important discipline in the entire plan.

---

## 14. What These PoCs Deliberately Do NOT Cover

These are out of scope for v0.1 PoCs. They're either obvious (won't fail), or deferred until later phase:

- ❌ Multi-tenancy authentication (v1.0+ — OIDC delegation)
- ❌ Observability stack integration (v0.5+ `obs` module)
- ❌ Streaming/CDC (v1.5+)
- ❌ Distributed Daft/Ray execution (Yield-to-Giants Mode 2 covers this)
- ❌ Vector retrieval / Lance integration (v0.5+ PoC then)
- ❌ Compliance audit (separate workstream, v1.0+)
- ❌ BI tool integration (assume standard ODBC/JDBC works in v0.5+)
- ❌ Performance against Databricks (separate benchmark project, post v1.0)
- ❌ Workbench UI feasibility (v0.2 design PoC closer to ship)
- ❌ Lakekeeper integration (v0.3 PoC before ship)
- ❌ dlt/dbt-duckdb integration (v0.3 PoC before ship)

The 5 v0.1 PoCs above target *only* the assumptions that, if wrong, change the v0.1 architecture itself.

---

## 15. The Bet

We are betting the v0.1 build plan on five hypotheses. Each is independently testable in 1-2 weeks. The cost of being wrong about any one of them, *discovered after* shipping v0.1, is **3-6 months of rework**.

The cost of validating now: **8 weeks, 1-2 engineers**.

**The single biggest bet is PoC #1 (Dagster Error Translation Layer).** If it fails, v0.1 architecture changes fundamentally. Discover that in Week 2, not Month 6.

This is the highest-leverage 8 weeks we will spend on this project.

---

*Validate, then commit. Never the other way around.*
