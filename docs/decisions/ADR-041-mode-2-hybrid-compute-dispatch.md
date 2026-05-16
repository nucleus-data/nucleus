# ADR-041: Mode 2 hybrid compute dispatch -- `compute=` decorator spec

> **Status**: PROPOSED -- 2026-05-15
> **Date**: 2026-05-15
> **Decider(s)**: Solo founder (graduation-pathways workstream, v0.2.0 close-out polish).
> **Tags**: yield-to-giants, layer-2-coordination, layer-4-experience, mode-2, hybrid-compute, sdk-surface, deferred-implementation
> **Supersedes**: (none -- first ADR scoping a Mode 2 dispatch surface)
> **Related**: `nucleus_architecture_v4.1.md` section 10 (Yield-to-Giants Strategy) - section 10.2 (Mode 2: Hybrid Compute) - section 6 (Coordination layer) - section 6.4 (Error Translation Discipline) - section 13 (`ctx` SDK Contract); `AGENTS.md` section 4 (Do-Not-Build list -- distributed compute) - section 3 #6 (No custom auth -- always delegate to OIDC); ADR-006 (NE-prefixed error codes); ADR-015 (AI Copilot single-turn chat); ADR-040 (Layer-4 peer imports); `docs/internal/research/parity_vs_databricks_snowflake.md` section 1, section 6 (gap-closure plan); `docs/cookbook/graduate-to-databricks.md`, `graduate-to-snowflake.md`, `graduate-to-bigquery.md` (the manual hybrid recipes ADR-041 automates).

---

## 1. Context

### 1.1 The current state

Nucleus v0.2.0 runs **all** asset compute in-process via DuckDB and Polars (`nucleus_architecture_v4.1.md` section 5.1, section 5.2). This is exactly right for the beachhead persona -- a 5-20-engineer startup team, 100 GB to 5 TB total, greenfield (`v4.1` section 1.5). Cold boot ~ 6 s; idle RAM ~ 117 MB; queries on 100M-row Parquet finish in seconds (per `docs/benchmarks/2026-05-15_baseline.md`).

The **honest evaluation pinned in `docs/internal/research/parity_vs_databricks_snowflake.md` section 1** flagged a documentation gap and an implementation gap:

> *Iceberg portability has not been tested on Databricks / Snowflake / BigQuery -- graduation claim is documented but not validated. Mode 2 hybrid compute dispatch is documented but not implemented.*

The graduation cookbooks added in the same workstream (`docs/cookbook/graduate-to-{databricks,snowflake,bigquery}.md`) close the *documentation* half of that gap. This ADR closes the *spec* half: it defines the user-visible API and the platform-side mechanics for the future implementation, **without committing to ship the implementation in v0.2 or v0.3**.

### 1.2 The user pain that justifies a Mode 2 surface

A concrete pattern emerging from beachhead user conversations and from the parity research:

- A team's daily Postgres-to-Iceberg ELT pipeline runs in 8 minutes on a laptop. Fine.
- Once a quarter, they need to backfill three years of history into a single 5 TB asset. That single materialization would take ~4 hours on the laptop and saturate it.
- They already have a Databricks workspace (or Snowflake account, or BigQuery project) that the data team uses for ad-hoc analytics.
- The Anti-Over-Engineering default per `.cursor/rules/nucleus.mdc` says: *do not own multi-cloud orchestration, do not host compute*. We yield (`v4.1` section 10).
- But the manual recipe (open Databricks console, paste SQL, point at the same S3 bucket, run, come back, validate) is friction-heavy -- it breaks the "Nucleus is the single tool" promise of the Felt Moat (`v4.1` section 2.1).

The minimum-viable Nucleus answer is a **thin dispatch decorator** that issues the SQL or Python statement on the remote engine and writes the resulting Iceberg snapshot back to the **same catalog**. The asset graph, the Workbench, the Asset Materialization Adapter (AMA), the contract enforcement, the error-translation layer -- all stay local. Only the heavy *one* step yields.

This is exactly Mode 2 as described in `nucleus_architecture_v4.1.md` section 10.2:

> *Nucleus orchestrates; Databricks executes; result committed back to Iceberg.*

### 1.3 Why the API is undocumented today

`v4.1` section 10.2 sketches the syntax (`@nucleus.sql_asset(compute="databricks")`) and `nucleus_architecture_v4.1.md` section 18.6 lists "Hybrid compute Mode 2 (Databricks/Snowflake dispatch)" as a **v1.5+** deliverable. The existing `docs/site/guides/graduate-to-databricks.md` says "v0.5+ planned syntax". `docs/roadmap/overview.md` says "v0.5+ (Hybrid dispatch ADR)". The README says "v1.5+".

That is **drift between documents**. The spec was never written. This ADR locks the spec; the founder decides separately whether to pull implementation into v0.3, v0.5, or v1.5.

### 1.4 Forces

- **Force A -- User pain is real today, even at v0.2.** Beachhead teams already hit the "occasional 5 TB workload" pattern. A documented manual recipe (the cookbooks) is the correct v0.2 answer. A decorator is the correct v0.3+ answer.
- **Force B -- Anti-Over-Engineering BIND** (per `.cursor/rules/nucleus.mdc`). No premature abstraction. If we ship a decorator without a real second backend wired, we will over-design it. Therefore: spec now, build behind a feature flag with **Databricks first**, add Snowflake and BigQuery only after one backend ships.
- **Force C -- No-orchestrator constraint.** `AGENTS.md` section 3 #3: "No custom scheduler". `AGENTS.md` section 4: "Distributed compute -> yield to giants via Mode 1/2/3 (Iceberg portability + dispatch)". We MUST NOT become a Dagster-Cloud competitor or a "multi-cloud platform" -- both are explicit non-goals (`v4.1` section 20.1).
- **Force D -- Error translation.** Per `v4.1` section 6.4 (release-blocker discipline): every external exception MUST translate to `NucleusError`. Remote-engine errors are external exceptions just like local DuckDB / pyiceberg errors and MUST be re-emitted as `NE2xxx` / `NE3xxx` per ADR-006.
- **Force E -- Auth must delegate to OIDC.** `AGENTS.md` section 3 #6: "No custom auth system. Always delegate to OIDC." Mode 2 cannot ship its own credential management surface. It MUST consume credentials from the existing OIDC / vault layers (or `.env` for v0.1-v0.2 dev).
- **Force F -- Composability constitution.** `v4.1` section 9: every Tier 1/2 dependency needs a clean swap interface + smoke tests. The `compute=` dispatch is conceptually a swap dimension; the chosen design MUST support per-provider plugins behind one stable interface.

---

## 2. Proposed API

### 2.1 The user-visible surface

```python
import nucleus
import polars as pl

# Local default -- runs on this laptop, unchanged from v0.2.
@nucleus.asset(table="silver.daily_orders")
def daily_orders(ctx) -> pl.DataFrame:
    return ctx.read("raw.orders").group_by("day").agg(pl.col("amount").sum())


# Mode 2 dispatch -- the SAME asset, but materialization happens on Databricks.
# The asset graph, deps, Workbench, AMA, OpenLineage emission, contracts -- all
# stay LOCAL. Only the SQL/Python execution + the Iceberg write yield.
@nucleus.asset(
    table="gold.three_year_revenue_rollup",
    compute="databricks://my-workspace/sql-warehouse-prod",
)
def three_year_revenue_rollup(ctx) -> Asset:
    return ctx.sql(
        """
        SELECT year, region, SUM(amount) AS total
          FROM {{ ref('silver.daily_orders') }}
         WHERE year >= 2023
         GROUP BY 1, 2
        """
    )
```

### 2.2 Surface explained

| Element | Role |
|---|---|
| `compute="databricks://..."` | URI naming the remote engine. **Scheme** = provider plugin (`databricks`, `snowflake`, `bigquery`). **Authority + path** = workspace / warehouse / dataset selector. **No query string** in v1; reserved for future tuning. |
| Default value | `compute="local"` (implicit, identical to today's behaviour). When omitted, Nucleus runs DuckDB / Polars in-process. |
| Asset return type | Unchanged. `pl.DataFrame`, `Asset`, or SQL string -- the AMA validates against the contract regardless of where compute happened. |
| `ctx.read(upstream)` | Resolves the upstream Iceberg snapshot **on the remote side** when `compute=` is non-local. Requires the same Iceberg catalog endpoint to be reachable from the remote engine (this is the precondition the graduation cookbooks document). |
| `ctx.sql(...)` | Sent to the remote SQL engine verbatim (after Jinja `{{ ref() }}` resolution against the same catalog). For Python assets, the body is serialized and executed remotely (Databricks Notebook task or equivalent). |
| Errors | Remote-engine errors are translated to `NucleusComputeDispatchError` (proposed new code under NE3xxx, see section 3.5) with the original exception preserved per `v4.1` section 6.4. |

### 2.3 URI scheme -- full grammar (v1)

```
compute       = "local" | provider-uri
provider-uri  = scheme "://" authority [ "/" path ]
scheme        = "databricks" | "snowflake" | "bigquery"
authority     = workspace-or-account-host    ; e.g. "my-workspace.cloud.databricks.com"
                                             ;       "my-account.snowflakecomputing.com"
                                             ;       "my-project"
path          = warehouse-or-dataset         ; e.g. "/sql-warehouse-prod"
                                             ;       "/compute_wh"
                                             ;       "/us"
```

The URI is parsed at decoration time. Invalid URIs raise `NucleusEnvironmentError` (NE5001) immediately, before the asset graph is built.

### 2.4 What `compute=` does NOT do

- Does NOT pick a different *table format*. The asset is still Iceberg, written to the same catalog. (No Delta, no Hive.)
- Does NOT change the *asset key*. `gold.three_year_revenue_rollup` is the same asset whether materialized locally or remotely; the next run can flip back to local without re-keying.
- Does NOT change the *contract enforcement*. `@nucleus.contract(...)` still runs locally on the result that comes back (or on the post-write Iceberg metadata, if the result is too large to bring back).
- Does NOT change the *lineage*. OpenLineage events are emitted from the AMA (local), not the remote engine.
- Does NOT introduce a *new orchestrator*. Dagster (wrapped per `v4.1` section 6) still owns the asset graph, dependencies, retries, schedules. The dispatch is a single in-process call from inside the asset materialization step.

---

## 3. Mechanics

### 3.1 Per-provider plugin interface

Each provider implements one interface, defined in `src/nucleus/coordination/dispatch/__init__.py` (the path proposed for the v0.3+ implementation; the file does not exist today).

```python
# Proposed shape -- NOT in src/ yet. Implementation tracked by
# the wave-3-mode2-implementation milestone. See section 6.
from typing import Protocol
from nucleus.errors import NucleusError

class ComputeProvider(Protocol):
    """One implementation per backend (databricks, snowflake, bigquery)."""

    scheme: str  # e.g. "databricks"

    def parse_uri(self, uri: str) -> "ComputeTarget": ...

    def materialize_sql(
        self,
        target: "ComputeTarget",
        rendered_sql: str,
        write_target: "IcebergWriteTarget",
        ctx: "NucleusCtx",
    ) -> "MaterializationResult":
        """Execute SQL on the remote engine; commit Iceberg snapshot to write_target."""
        ...

    def materialize_python(
        self,
        target: "ComputeTarget",
        callable_ref: "SerializedCallable",
        write_target: "IcebergWriteTarget",
        ctx: "NucleusCtx",
    ) -> "MaterializationResult":
        """Send Python body to the remote engine; commit Iceberg snapshot to write_target."""
        ...

    def health_check(self, target: "ComputeTarget") -> "HealthStatus":
        """Pre-flight: credentials valid? endpoint reachable? warehouse running?"""
        ...
```

The Coordination layer never imports a specific provider; providers register via an internal entry-point (`nucleus.coordination.dispatch._registry`). This is **not** a public plugin SDK (forbidden in v1 by `AGENTS.md` section 3 #2). Internal-only.

### 3.2 Materialization flow

The seven-step path the AMA follows when `compute != "local"`:

```
1. Pre-write contract validation             (LOCAL -- unchanged from v0.2)
2. Resolve upstream {{ ref() }} to current
   Iceberg metadata pointers                 (LOCAL)
3. Pre-flight health_check on provider       (LOCAL -> REMOTE one round-trip)
4. Render SQL or serialize Python body       (LOCAL)
5. Issue ONE materialize_sql / materialize_
   python call to the provider               (REMOTE -- owns the heavy work)
6. Provider commits Iceberg snapshot to the
   SAME catalog endpoint                     (REMOTE write to shared catalog)
7. Post-write OpenLineage emit + contract
   re-check on the resulting snapshot
   metadata + asset registry update          (LOCAL -- unchanged from v0.2)
```

The Coordination layer issues exactly **one** SQL or PySpark statement per asset materialization. This is the boundary that prevents Nucleus from drifting into "multi-cloud orchestrator" territory: we do not loop, we do not chain, we do not retry on the remote side beyond the provider's native retry. One asset, one statement.

### 3.3 Iceberg-catalog precondition

For step 6 to work, the remote engine MUST be configured to write to the same Iceberg catalog endpoint that Nucleus uses. The graduation cookbooks (`docs/cookbook/graduate-to-{databricks,snowflake,bigquery}.md`) document this precondition. In practice this means:

- For Mode 2 with Databricks: Unity Catalog Lakehouse Federation pointed at Lakekeeper (or the Nucleus filesystem catalog if Databricks supports the `metadata.json` pointer pattern).
- For Mode 2 with Snowflake: a CATALOG INTEGRATION (REST or OBJECT_STORE) pointed at the same Iceberg catalog.
- For Mode 2 with BigQuery: BigLake Metastore or external Iceberg pointers.

If the precondition is not met, `health_check` fails fast with `NucleusComputeDispatchError` and a `fix_hint` pointing at the appropriate cookbook.

### 3.4 Auth model

Per Force E above and `AGENTS.md` section 3 #6: **Nucleus does NOT own credentials for remote engines.** Credentials are supplied via:

- **Local dev**: `.env` file with provider-specific keys (e.g. `DATABRICKS_TOKEN`, `SNOWFLAKE_PASSWORD`, `GOOGLE_APPLICATION_CREDENTIALS`). The provider plugin reads these via `os.environ` only.
- **Production**: existing OIDC / vault delegation per `nucleus_architecture_v4.1.md` section 15.1 (Lakekeeper / Authentik / Keycloak / Okta / Azure AD). The provider plugin asks `ctx.secrets.get(...)` (v0.2+ surface per `v4.1` section 13.2).
- **Service-account / workload-identity** patterns: documented per provider; Nucleus does not enforce a specific pattern.

Open question: per-user OAuth flows (Databricks personal access tokens via OIDC, Snowflake key-pair, GCP application-default-credentials). See section 5.

### 3.5 Error translation

Remote-engine failures translate per `v4.1` section 6.4. Proposed new code (paired class name + URL slug per ADR-006):

```python
# Proposed addition to src/nucleus/errors.py at v0.3+ implementation time.
class NucleusComputeDispatchError(NucleusError):
    """NE3008 -- dispatch to remote compute provider failed.

    Subtypes:
      - NE3008.health: pre-flight health_check failed (auth, network, warehouse stopped)
      - NE3008.execute: remote engine raised during execution
      - NE3008.commit: remote engine succeeded but failed to commit Iceberg snapshot
      - NE3008.translate: result returned but contract validation failed
    """
    code = "NE3008"
    docs_slug = "/errors/compute-dispatch"
```

The Asset Materialization Adapter wraps every step 3-6 call site in a try/except per the existing pattern in `src/nucleus/coordination/error_translation.py`. Original exceptions preserved as `error.cause`; user-facing strings carry asset names not provider classnames (e.g. "Asset 'gold.three_year_revenue_rollup' failed to materialize on Databricks SQL Warehouse 'sql-warehouse-prod'." NOT "DatabricksJobsApi.runs_submit() returned 400."). Validated by `scripts/dagster_leak_check.py` extended for the new providers.

### 3.6 Cost-meter integration

Per `v4.1` section 7.5 (v0.5+ Cost Meter): the per-asset cost meter cannot directly observe remote runs. Mitigation in v0.3+ implementation:

- Provider plugin returns a `RemoteRunReceipt` (run-id, start, end, billable units, currency) from each dispatch.
- The receipt is stored alongside the local `MaterializationResult` in the run ledger.
- The cost meter UI (v0.5+) surfaces remote spend per asset using these receipts.
- For providers without billable-unit attribution at run-time (BigQuery on-demand), the receipt carries the bytes-scanned metric instead.

This is **not** a billing system. We surface what the provider tells us and link out to the provider's billing console for the source of truth.

### 3.7 Lineage emission for remote runs

Asset-level OpenLineage events are emitted by the AMA **locally** in step 7, exactly as they are today. The `outputFacets` carry the new Iceberg snapshot ID returned by the remote commit. Open question: whether to bridge to the remote engine's native lineage (Unity Catalog lineage, Snowflake ACCESS_HISTORY, Dataplex lineage). See section 5.

---

## 4. Why this preserves "yield to giants" without becoming a multi-cloud orchestrator

Three structural guarantees, in order of importance:

1. **One SQL/PySpark statement per asset materialization.** No looping, no chaining, no remote-side scheduling. The Coordination layer issues a single dispatch per asset; the asset graph stays in Dagster (local).
2. **The Iceberg lakehouse is the contract surface, not the engine.** The remote engine is asked to "produce a snapshot at this Iceberg metadata path"; how it computes the snapshot is its concern. We do not ship Spark configs, we do not tune Snowflake warehouse sizes, we do not pick BigQuery slot reservations.
3. **No remote-side state owned by Nucleus.** No long-running Nucleus daemons inside Databricks workspaces. No remote-side queues. No remote-side metadata DB. The provider plugin is stateless: it parses the URI, dispatches, waits for the receipt, returns.

Cross-check against `AGENTS.md` section 4 do-not-build list: [x] no scheduler, [x] no orchestration, [x] no compute engine, [x] no auth system, [x] no multi-tenant control plane, [x] no LLM hosting. Cross-check against `v4.1` section 20 non-goals: [x] no Spark replacement, [x] no Databricks competitor, [x] no Iceberg commit service. Cross-check against the 8-question gate (`AGENTS.md` section 5): [x] all eight pass for the *spec*; the implementation will re-run the gate per-provider.

---

## 5. Open questions

In priority order. Each must be answered before the implementation milestone closes.

1. **Auth -- OIDC delegation vs per-user secrets vs both?** The architecture says always-OIDC (`AGENTS.md` section 3 #6). Real Mode 2 users will have a mix: cloud-managed service principals for production, personal-access-tokens for development. Decision needed: does v0.3+ ship with OIDC-only and force users to set up Authentik/Keycloak first, or does it permit `.env`-based PATs as a development on-ramp? **Recommended**: both, with `.env` as the dev fast-path and OIDC as the production path; document the trade-off explicitly.
2. **Per-user vs project-wide credentials.** A single Nucleus project may want to dispatch to multiple workspaces (one per environment). The `compute=` URI carries the workspace; the credential lookup must follow the URI. Decision needed: a `[compute.databricks.<workspace-slug>]` block in `nucleus_project.yaml`, or a flat `DATABRICKS_TOKEN_<slug>` env-var convention?
3. **Lineage bridging.** Whether to emit OpenLineage events from inside the remote engine (Databricks supports OpenLineage natively; Snowflake and BigQuery do not at v1.5 cadence). Decision deferred to per-provider implementation.
4. **Cost meter receipt schema.** Provider plugins must return a comparable cost receipt. Decision: define `RemoteRunReceipt` as a Pydantic dataclass with optional fields per provider, NOT a strict union; let consumers handle missing fields.
5. **Sync vs async dispatch.** Today's AMA is synchronous. A remote 4-hour materialization blocks the Dagster asset run for 4 hours. Decision: ship v0.3+ as synchronous-only (matches the rest of Nucleus); revisit async dispatch in v0.5+ if telemetry shows >5% of Mode-2 runs exceed 30 minutes.
6. **Error message localisation.** `NucleusComputeDispatchError` carries provider context. Decision needed: do we expose the raw provider error message to the user (helpful, but may leak credentials in URLs) or always sanitise? **Recommended**: always sanitise the user-facing string; preserve the raw error in `error.cause` for `--verbose` mode.
7. **Health-check caching.** Step 3 (pre-flight) round-trips to the remote per asset. For a DAG of 50 assets all dispatched to the same warehouse, that is 50 wasted round-trips. Decision: cache per (provider, target, run-id) with a 60 s TTL.
8. **Schema evolution synchronisation.** If the remote engine adds a column to a shared table, Nucleus's local AMA must see it on the next read. Decision: rely on the Iceberg metadata pointer being authoritative (it is, by definition); document that schema-evolution races can cause `NucleusContractViolationError` until the next pointer refresh.

---

## 6. Out of scope for ADR-041

This ADR is a **specification**. The following are explicitly NOT decided here:

- **Implementation timeline.** Recommended pull-forward target: **v0.3+** (per founder direction in the graduation-pathways workstream brief). The original architecture target is v1.5+ (`v4.1` section 10.2, section 18.6). Implementation tracked by the milestone tag `wave-3-mode2-implementation`. Pulling implementation forward from v1.5 to v0.3 requires a follow-up amendment to `nucleus_architecture_v4.1.md` section 18.6 per `AGENTS.md` section 10.7.
- **Provider plugin code.** Each provider (Databricks first, then Snowflake, then BigQuery) will arrive as its own ADR + PR per `AGENTS.md` section 11.10 single-file discipline.
- **Performance targets.** Per `v4.1` section 16, local performance targets are documented; remote performance is the remote engine's responsibility.
- **Exact `nucleus_project.yaml` schema.** Specifics of the `[compute.databricks.<slug>]` block or its alternatives wait until the first provider implementation.
- **Workbench UI for Mode 2.** Whether the Workbench shows remote-run status differently is a v0.5+ question after at least one provider ships.

---

## 7. Alternatives considered

Three high-level shapes were on the table.

### 7a. Mode A -- Full remote orchestration (REJECTED)

Build a Nucleus-side compute scheduler that owns multi-cloud dispatch end-to-end: queue, retry, fan-out, consolidate, cost-cap, multi-tenant routing.

- **Why rejected**: directly violates `AGENTS.md` section 3 #3 ("No custom scheduler") and section 4 ("Distributed compute -> yield to giants"). Also drifts toward the explicit non-goal in `v4.1` section 20 ("Multi-cloud control plane -- out of scope for OSS"). This is the Dagster-Cloud / Prefect Cloud business; Nucleus is not entering it.

### 7b. Mode B -- Just write a how-to guide (REJECTED)

The graduation cookbooks (which we DID write) tell users to manually paste SQL into Databricks consoles and re-emit Iceberg pointers. No platform code at all.

- **Why rejected as the END state**: this is the right *v0.2* answer (and exactly what we shipped in `docs/cookbook/graduate-to-{databricks,snowflake,bigquery}.md`). It is NOT the right v0.3+ answer because it breaks the Felt Moat (`v4.1` section 2.1) -- users have to context-switch to a different tool for their occasional heavy job. The friction kills the "Nucleus is the single tool" promise. We need at least the thin decorator at v0.3+.

### 7c. Mode C -- Thin `compute=` decorator + per-provider plugin (CHOSEN)

Spec'd in this document. ~100-300 LOC for the dispatch interface + ~200-500 LOC per provider plugin. Total proprietary LOC budget impact: ~1,000-2,000 LOC for the full three-provider build. Within the 30K LOC ceiling (`AGENTS.md` section 3 #8).

- **Why chosen**: smallest surface that closes the user-visible friction; preserves all existing constraints; honours composability (one interface, three implementations); ships in waves (Databricks first); naturally extends to a fourth provider later.

---

## 8. Decision criteria for accepting this ADR

The founder accepts this ADR (status PROPOSED -> ACCEPTED) if at least **4 of these 6** hold at review time:

1. **Clear API.** A reader of `section 2 Proposed API` understands what `compute="databricks://..."` does in under 90 seconds.
2. **No scope creep into orchestration.** section 4 cleanly demonstrates that Mode C does NOT become a multi-cloud orchestrator. Cross-checked against `AGENTS.md` section 4 do-not-build list with no violations.
3. **Preserves local-prod parity.** Asset code is byte-identical between `compute="local"` and `compute="databricks://..."` runs (same `@nucleus.asset`, same `ctx.sql`, same contract). The only delta is the URI string.
4. **Error translation maps remote errors to NucleusError.** section 3.5 defines `NucleusComputeDispatchError` (NE3008) with subtypes covering the four failure modes (health, execute, commit, translate) per ADR-006 numbering convention.
5. **Founder can prototype the Databricks plugin in <100 LOC.** A spike implementation of `materialize_sql` for Databricks (using the Databricks SQL Statement Execution API, <https://docs.databricks.com/api/workspace/statementexecution>) fits in the budget. NEEDS VERIFICATION at prototype time.
6. **Cookbooks remain valid.** `docs/cookbook/graduate-to-{databricks,snowflake,bigquery}.md` continue to describe a meaningful manual fallback even after the decorator ships -- useful for users who have hard "no extra deps" policies.

If <4 hold, the ADR returns to PROPOSED with the gaps named in the founder's review note.

---

## 9. Consequences

### Positive

- Closes the documentation gap flagged in `docs/internal/research/parity_vs_databricks_snowflake.md` section 1.
- Gives the founder a concrete spec to prototype against, without committing implementation effort in v0.2.
- Locks the user-visible API early so the cookbooks (`graduate-to-{databricks,snowflake,bigquery}.md`) can reference a stable name (`compute=`) without a syntax-drift risk.
- Provides a forward-compatible plug interface that future providers (Trino, ClickHouse, Tinybird, R2 Data Catalog) can implement without re-spec.

### Neutral

- Introduces a new error code (NE3008) into the ADR-006 numbering plan. Adjacent codes (NE3009+) reserved for future Mode 2 / Mode 3 expansion.
- Creates an expectation that the implementation follows in v0.3+. If founder velocity requires deferring to v0.5 or v1.5, this ADR remains valid; only the milestone tag moves.

### Negative

- A new internal interface (`ComputeProvider`) increases the swap surface that the composability constitution (`v4.1` section 9) must keep healthy. Mitigation: Tier 2 classification (replaceable per `v4.1` section 9.2), interface-only smoke tests in CI per provider.
- Documentation drift risk: the `compute=` syntax is now mentioned in 4 documents (this ADR, the 3 graduation cookbooks). If the spec changes, all 4 must update together. Mitigation: this ADR is the source of truth; cookbooks reference it by section, not by inline syntax restatement.

---

## 10. Compliance / verification (for the future implementation, not for the ADR itself)

Pre-acceptance (this ADR):

- [x] Follows `AGENTS.md` section 11.5 ADR template (Status, Date, Decider, Tags, Context, OSS Options, Decision, Consequences, References).
- [x] Cites architecture sections explicitly per `AGENTS.md` section 10.1.
- [x] Honours all 11 hard constraints in `AGENTS.md` section 3 (no JVM in core path, no custom scheduler, no custom auth, no compute engine, no Iceberg commit service, no multi-tenant control plane, etc.).
- [x] No fabricated APIs -- every cited URL is reachable and every code snippet is marked as PROPOSED, not as shipped code.

Pre-implementation (when v0.3+ wave starts):

- [ ] `scripts/dagster_leak_check.py` extended to scan provider plugins for classname leaks.
- [ ] `scripts/check_pinning.py` covers any new SDK dep (e.g. `databricks-sdk`, `snowflake-connector-python`, `google-cloud-bigquery`) per `AGENTS.md` section 11.13.
- [ ] LOC budget delta tracked per provider PR (~200-500 LOC per provider).
- [ ] Smoke test per provider lives in `tests/smoke/dispatch/test_<provider>.py`.
- [ ] Beachhead E2E (`scripts/beachhead_e2e.py`) extended to verify `compute=` round-trip when a credential is provided; otherwise skipped.
- [ ] Per-provider `docs/swap/<provider>.md` documents the swap-out path off that provider per `v4.1` section 9.3.

---

## 11. References

### Internal

- `nucleus_architecture_v4.1.md` section 10 (Yield-to-Giants Strategy), section 10.2 (Mode 2: Hybrid Compute), section 6 (Coordination layer), section 6.4 (Error Translation), section 9 (Composability by Constitution), section 13 (`ctx` SDK Contract), section 15.1 (Authentication -- OIDC delegation), section 18.6 (v1.5 Hybrid Compute Mode 2 line).
- `AGENTS.md` section 3 (Eleven Hard Constraints), section 4 (Do-Not-Build list), section 5 (8-Question Gate), section 6 (Five Pillars), section 10 (AI agent disciplines), section 11.5 (ADR template), section 11.7 (Error Translation Enforcement), section 11.10 (single-file discipline).
- `.cursor/rules/nucleus.mdc` (Anti-Over-Engineering BIND, Velocity Discipline, Subagent Model Orchestration).
- ADR-006 (NE-prefixed error codes -- defines the NE3xxx Coordination range that NE3008 lands in).
- ADR-015 (AI Copilot single-turn chat MVP -- precedent for "spec the surface, build later").
- ADR-040 (Layer-4 peer imports -- precedent for ADRs that crystallise architectural intent without runtime code change).
- `docs/internal/research/parity_vs_databricks_snowflake.md` section 1 (the scope statement that motivated this ADR), section 6 #1-#5 (Top 5 must-close items -- Mode 2 is the umbrella for these).
- `docs/cookbook/graduate-to-databricks.md` section 8 (Hybrid mode), `graduate-to-snowflake.md` section 6, `graduate-to-bigquery.md` section 6 -- the manual recipes ADR-041 will eventually automate.

### External (cited URL form, content verifiable at implementation time)

- Databricks SQL Statement Execution API: <https://docs.databricks.com/api/workspace/statementexecution>
- Databricks Lakehouse Federation: <https://docs.databricks.com/aws/en/query-federation/index.html>
- Snowflake Iceberg Tables: <https://docs.snowflake.com/en/user-guide/tables-iceberg>
- Snowflake catalog integration: <https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration>
- BigQuery Iceberg overview: <https://cloud.google.com/bigquery/docs/iceberg-tables>
- BigLake Metastore: <https://cloud.google.com/bigquery/docs/biglake-metastore>
- Apache Iceberg spec: <https://iceberg.apache.org/spec/>
- OpenLineage: <https://openlineage.io>

---

*This ADR is the design source of truth for the `compute=` decorator surface. The first implementation (Databricks provider) gets its own ADR (ADR-04x, TBD) with concrete LOC numbers, dependency pins, and smoke-test acceptance criteria. The cookbooks remain the v0.2 answer for users who need Mode 2 today.*
