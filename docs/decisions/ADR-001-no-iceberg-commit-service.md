# ADR-001: Use catalog-delegated commits; do not build a custom Iceberg commit service

> **Status**: Accepted
> **Date**: 2026-05-12 (Month 0, Pre-Heartbeat)
> **Decider(s)**: Solo founder (informed by F1/F2/F3 senior-review feedback)
> **Tags**: architecture, dependencies, storage, hard-constraint
> **Supersedes**: v4.0 architecture's "Iceberg Commit Service" component (deleted)
> **Related**: AGENTS.md Hard Constraint #5, `nucleus_architecture_v4.1.md` §6, `docs/architecture/C4_container.md` §2.0

---

## Context

The earlier v4.0 architecture (now superseded) included a custom **"Iceberg Commit Service"** as a Nucleus-owned component. Its job was to coordinate atomic commits to Iceberg tables, retry conflicts, and provide a single audit point.

Three senior reviewers (F1 product, F2 senior staff, F3 architect) independently flagged this as **the most over-built component in the design**. F3's exact words: *"This conflicts with what the Iceberg catalog is already responsible for. You'd be re-implementing atomicity primitives on top of primitives that already provide them. Worst case: subtle correctness bugs no one notices for months."*

### Problem

Atomic commits to Iceberg tables (snapshot creation, metadata file pointer swap) are already a responsibility of **Iceberg catalogs**:

- **Filesystem catalog** (PyIceberg's default for v0.1): atomic file rename for `vN.metadata.json` pointer
- **SQL catalog** (SQLite/Postgres via PyIceberg): SQL transaction for the metadata pointer update
- **REST catalog** (Lakekeeper v0.3+): CAS (compare-and-swap) operations
- **AWS Glue, Polaris, Tabular** (v1.0+): each implements atomic update guarantees per Iceberg's catalog interface

If we add **our own service** on top, we either:
1. **Duplicate** their atomicity logic (wasteful, error-prone), or
2. **Bypass** them (and lose the atomicity they provide).

### Forces in tension

- **Force A**: Want strong control + audit over write operations (built-in observability, retry policies).
- **Force B**: Constraint #3 — never build what OSS already provides well.
- **Force C**: Solo founder LOC budget (~8000 LOC for v0.1, Constraint #8). A commit service is ~1500-2000 LOC of subtle code.
- **Force D**: Correctness — atomic commits are the **most safety-critical** behavior. Bugs here = silent data corruption. Iceberg catalog implementations have been hardened over years; ours haven't.

---

## Decision

> **We will delegate ALL atomic commit operations to the Iceberg catalog. We will NOT build a custom commit service.**
>
> Specifically:
>
> 1. **Removed** the "Iceberg Commit Service" component from the architecture (deleted from v4.1).
> 2. **Replaced** with a thin **Asset Materialization Adapter** (`coordination/asset_materialization.py`, ~500 LOC) whose sole responsibility is:
>    - Translate `ctx.asset` definitions to Dagster materialization requests.
>    - Call `pyiceberg.Table.append(...)` / `.overwrite(...)` for the actual commit.
>    - Translate `pyiceberg.exceptions.CommitFailedException` / `CommitStateUnknownException` to NucleusError types (via Error Translation Layer).
> 3. **Observability** for commits is achieved by:
>    - Emitting `commit.attempted` / `commit.succeeded` / `commit.failed` structured log events around each `pyiceberg.Table.commit_transaction()` call.
>    - OpenTelemetry spans wrap the same calls (Constraint #7).
> 4. **Retry policy** is implemented as a simple `tenacity`-based retry loop in the Adapter (max 3 attempts on `CommitFailedException`, exponential backoff). **Not a separate service** — just a decorator on the commit call.
> 5. This is codified as **Hard Constraint #5** in `AGENTS.md`: *"No custom Iceberg commit service / distributed transaction coordinator. Catalog handles atomic commits."*

---

## Rationale

### How this addresses the forces

| Force | How addressed |
|-------|---------------|
| **A (control + audit)** | Achieved via structured logging + OTel spans around catalog calls. We get all the audit benefits without re-implementing atomicity. |
| **B (don't reinvent)** | We delegate to PyIceberg, which delegates to the configured catalog. Both are battle-tested OSS. |
| **C (LOC budget)** | Saves ~1500-2000 LOC. The Adapter is ~500 LOC instead. **75% reduction** in surface area. |
| **D (correctness)** | The Iceberg spec and reference implementations have been audited by Netflix, AWS, Snowflake, Databricks, Apple. **Far more robust** than anything we'd write. |

### Hard Constraints satisfied

- ✓ **#5** — No custom Iceberg commit service. (This ADR is the source of #5.)
- ✓ **#4** — Iceberg is the only table format we materialize to; using its catalog directly reinforces this.
- ✓ **#8** — LOC budget protected.
- ✓ **#9** — Composability: catalog swap (filesystem → SQL → Lakekeeper → Glue) becomes a config change, not a code change.

### Evidence

1. **Iceberg spec § "Commit Concurrency"**: defines exactly the atomicity contract catalogs must satisfy. Reference: https://iceberg.apache.org/spec/#commit-concurrency
2. **PyIceberg implementation** of `Transaction.commit_transaction`: implements optimistic concurrency control on top of catalog operations. Reference: https://py.iceberg.apache.org/api/#transactions
3. **Senior-review F3 verdict**: "Trust the catalog. Build a thin adapter, not a service."

---

## Alternatives considered

### Alternative A: Build a full Iceberg Commit Service (the v4.0 design)

**Pros**:
- Centralized retry policy
- Custom telemetry shape
- Could in theory add features (priority queuing, multi-table transactions)

**Cons**:
- Duplicates Iceberg catalog's atomicity contract
- High correctness risk (we'd own a safety-critical primitive)
- 1500-2000 LOC of dense code we have to maintain forever
- Doesn't help us; catalogs already provide what we need
- Would block on Constraint #3 (which we'd have to weaken)

**Why rejected**: Pure over-engineering. The pros are negligible vs the costs and risks.

### Alternative B: Wrap PyIceberg's Transaction API in a thicker layer with custom retry, batching, deduplication

**Pros**:
- More flexibility than pure delegation
- Could batch multiple small commits into one (perf)

**Cons**:
- Still ~1000+ LOC of subtle logic
- Batching introduces visibility issues (when does a commit appear?)
- Most users don't write enough small commits to need batching
- Premature optimization

**Why rejected**: YAGNI. If batching becomes a real need (post v0.3), we'll add it as a tactical optimization, with an ADR-driven re-think. Not at v0.1.

### Alternative C: Don't use Iceberg's catalog at all — write metadata files directly

**Pros**:
- Lowest dependency footprint

**Cons**:
- We'd be re-implementing the catalog interface ourselves
- Loses portability (Iceberg-aware tools expect a real catalog)
- Trivially worse than Alternative B

**Why rejected**: Hilariously bad idea. Listed for completeness.

### Alternative D: Use Iceberg catalog directly, no Adapter at all

**Pros**:
- Minimum code

**Cons**:
- Then `ctx.asset` decorator can't talk to Dagster cleanly
- We need *some* layer to translate `ctx` semantics to Dagster + Iceberg
- That's exactly what the Adapter does, in 500 LOC

**Why rejected**: Conflates "thin adapter" with "no adapter". A thin adapter is necessary; a fat service is not.

---

## Consequences

### Positive
- **LOC saved**: ~1500-2000 LOC not written. ~75% reduction in this component.
- **Correctness gained**: Atomic commit safety inherits from upstream OSS (battle-tested at scale).
- **Catalog portability**: Swapping filesystem → Lakekeeper → Glue is a config change, not a code change.
- **Maintenance bandwidth freed**: Solo founder doesn't own a safety-critical primitive.
- **Constraint #3 born**: This ADR formalizes the principle as a project-wide rule.

### Negative / costs
- **Less custom telemetry shape** — we get what PyIceberg + catalog emit, plus our own wrap. No fine-grained per-manifest hooks.
- **Retry policy is simpler** — `tenacity` decorator on the commit call, not a stateful queue. (Sufficient for v0.1.)
- **Future "advanced commit features"** (multi-table transactions, idempotency tokens) would need to come from upstream Iceberg, not from us. We can't unilaterally add them.

### Neutral / observed
- This is consistent with how every other Iceberg consumer in the ecosystem operates (Spark, Trino, Flink, Athena, Snowflake all delegate to the catalog).

### Risks introduced
- **Risk**: PyIceberg's filesystem catalog could have bugs in atomicity (especially on Windows filesystems, where `os.rename` semantics differ).
  - **Mitigation**: PoC #1 + integration tests include atomic-commit stress tests on Windows + macOS + Linux. If a bug is found, we file upstream and pin a fixed version.
- **Risk**: For pre-v0.3 users on filesystem catalog, concurrent writes from multiple processes could conflict more often than with a real catalog.
  - **Mitigation**: v0.1 is single-process anyway. Documented in `docs/conventions/engineering.md` §4.1. Multi-process becomes a Lakekeeper (v0.3) use case.
- **Risk**: If PyIceberg becomes unmaintained, our atomic-commit story breaks.
  - **Mitigation**: PyIceberg is an Apache Software Foundation project with broad industry investment (AWS, Tabular, Dremio contribute). Acceptable risk; track as a Tier 0 dependency per Constraint #9.

---

## Implementation notes

### Files affected
- ✓ **Created**: This ADR.
- ✓ **Updated**: `AGENTS.md` (Hard Constraint #5 codified).
- ✓ **Updated**: `nucleus_architecture_v4.1.md` (removed Iceberg Commit Service component, replaced with Asset Materialization Adapter).
- ⏳ **Will create** (PoC #1 phase): `src/nucleus/coordination/asset_materialization.py` (~500 LOC).
- ⏳ **Will create** (PoC #1 phase): `tests/coordination/test_asset_materialization.py`.
- ⏳ **Will create** (PoC #1 phase): `tests/integration/test_atomic_commit_stress.py` (Windows/Mac/Linux matrix).

### Migration

N/A — this is a Month 0 decision, no prior code exists to migrate.

For the documentation: v4.0 architecture mentions the Iceberg Commit Service. v4.1 has the deprecation banner at the top of v4.0 with a pointer to this ADR for explanation.

---

## Compliance / verification

How we know this decision is being followed:

- [x] **Hard Constraint #5** codified in `AGENTS.md` §3 and `.cursor/rules/nucleus.mdc`.
- [ ] **CI grep**: `scripts/check_no_commit_service.py` searches `src/nucleus/` for class definitions like `class *CommitService` or `class *CommitCoordinator`. Fails build if found.
- [ ] **Test**: Integration test asserts that under failure mid-commit (kill -9 simulation), the catalog state is consistent.
- [x] **Documentation**: This ADR. `C4_container.md` §2.0 references it. `engineering.md` §3 references Constraint #3.

---

## Open questions

1. **Pluggable retry policies?** If we get user feedback that 3 retries is too few/many, do we expose a knob? — *Defer to v0.3, when real-world data exists.*
2. **Per-catalog tuning?** Lakekeeper might want different retry behavior than filesystem catalog. — *Yes, but as a single `retry_policy_for_catalog(cat: CatalogType)` helper, not a service.*

---

## References

- [Iceberg Spec — Commit Concurrency](https://iceberg.apache.org/spec/#commit-concurrency)
- [PyIceberg — Transactions](https://py.iceberg.apache.org/api/#transactions)
- [PyIceberg — Catalog implementations](https://py.iceberg.apache.org/configuration/#catalogs)
- F3 senior-review verdict (internal, captured in conversation history)
- `nucleus_architecture_v4.1.md` §6 (the corrected architecture)
- `docs/architecture/C4_container.md` §2.0 (current container diagram)

---

*This is ADR-001. It is the template-by-example for all future ADRs. When you write ADR-002, model after this format.*
