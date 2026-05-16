# ADR-013: `ctx.materialize()` API Surface for Asset Materialization

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: ctx-sdk, materialize, api-surface, error-translation
> **Related**: ADR-001 (catalog owns commits); ADR-005 §1+§2 (tier ladder); ADR-006 §Decision+§Initial+§NV (NE-codes); ADR-012 (`dagster==1.9.5` underwrites the wrap); AGENTS.md §0+§7+§11.5; v4.1 §6.2+§6.4+§6.5+§13.2; `docs/specs/nucleus_ctx_sdk_spec.md` §0+§3.1+§12; `cli_spec` §3.4+§8; `sequence_asset_materialization.md` §1+§5; `v01_skeleton_plan.md` §6 Q2+§7 NV #1+§3.1.

## Context

`v01_skeleton_plan.md` §6 Q2 + §7 NV #1 surfaced a citation gap: **`ctx.materialize(...)` is consumed by two locked specs but absent from the frozen `ctx` surface.** Consumers: `cli_spec` §3.4 (*"`nucleus run [ASSET_KEY...]` … equivalent to `ctx.materialize(...)`"*; same paragraph drifts to plural `ctx.materialize_assets([...])` — NV #1) + `sequence_asset_materialization.md` §1 step 2 (canonical happy-path; §5 r1 flags spelling open). Producers: v4.1 §13.2 (lines 1079-1092) + `docs/specs/nucleus_ctx_sdk_spec.md` §12 (lines 422-439) — neither lists it.

`cli/commands/run.py` (skeleton plan §3.2 r6, 300 LOC) cannot land until this resolves. Per AGENTS.md §0 `ctx` is one of three things Nucleus owns forever; an undeclared public name is the worst form of premature freezing.

API-definition decision (wrap-vs-build already answered by v4.1 §6.2 + ADR-001). ADR-013 answers *what `ctx`-shape exposes that wrap*.

## OSS / Surface Options Considered

| Option | Shape | Verdict |
|---|---|---|
| **A** — Re-export `dagster.materialize` directly | `dagster.materialize([asset_def_or_key], ...)` | REJECT — leaks `AssetSelection`/`Definitions`/`DagsterInstance` across `ctx`; violates v4.1 §6.4+§6.5. |
| **B** — Wrap `Definitions.execute_asset` (lazy) | Lazy graph + run-config | REJECT — same leak + job/run-config objects (AGENTS.md §7). |
| **C** — Thin Nucleus-vocabulary wrapper over `dagster.materialize`; Nucleus dataclass return; zero Dagster types cross | `ctx.materialize(asset, *, partition, upstream, timeout_seconds) -> MaterializationResult` | **ACCEPT** — matches v4.1 §6.2 AMA (~500 LOC) + §6.4 translation + §6.5 replaceability (signature must survive `nucleus-mini-scheduler` swap per v4.1 §6.7). |

## Decision

> **Add `ctx.materialize(asset, *, partition, upstream, timeout_seconds) -> MaterializationResult` to the `ctx` surface (Option C). Tier per ADR-005 §2. NE-codes per ADR-006 §Decision. Implementation hides behind `coordination/asset_materialization.py` (skeleton plan §3.1 r3) which ultimately calls `dagster.materialize(...)` per `sequence_asset_materialization.md` §1 step 4.**

### 1. Public signature

```python
# Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)
# Docs: nucleus.dev/api/ctx.materialize
def materialize(
    asset: str | nucleus.AssetRef,
    *,
    partition: str | None = None,
    upstream: Literal["skip", "materialize", "validate"] = "skip",
    timeout_seconds: int | None = None,
) -> MaterializationResult:
    """Materialize a Nucleus asset to its declared destination.

    Per `docs/specs/nucleus_architecture_v4.1.md` §6.2 (Asset Materialization Adapter).
    """
```

Argument semantics:

- `asset` — 2-level v0.1 key (cli_spec §10 NV #6) or `AssetRef` (`docs/specs/nucleus_ctx_sdk_spec.md` §3.1+§12; **not** `NucleusAsset` from skeleton plan §6 Q2 — NV #5). Unknown → `NucleusAssetNotFound`/`NE3002`.
- `partition` — single-string (`"2026-05-13"`); `None` = all eligible partitions; tuple form deferred (Q2).
- `upstream` — `"skip"` (default; fail loud via `NE3003`), `"materialize"`, `"validate"`. No `recursive=` (AGENTS.md §7).
- `timeout_seconds` — wall-clock; `None` = no timeout; exceeded → `NucleusTimeoutError` (NE-code per NV #2).

### 2. Return type — `MaterializationResult`

```python
# Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0
@dataclass(frozen=True)
class MaterializationResult:
    asset_key: str            # e.g. "marts.orders_clean"
    snapshot_id: str          # Iceberg snapshot ID (v0.1); Lance version (v0.5+)
    partition: str | None
    row_count: int
    duration_ms: int
    lineage_event_id: str     # OpenLineage RunEvent UUID per v4.1 §6.2 step 4
    materialized_at: datetime # UTC
```

Placement: `src/nucleus/sdk/types.py` (new module per skeleton plan §2). Re-exported from `nucleus/__init__.py`. `frozen=True`; fields additive-only post-Stable per ADR-005 §3. Name `MaterializationResult` (not `RunResult`) per AGENTS.md §7 — `RunResult` is reserved for the coordination-layer return type (skeleton plan §3.1 r3); **internal `RunResult` transforms into public `MaterializationResult` at the `ctx` boundary** (v4.1 §6.5 replaceability). Transform-owner: Q5.

### 3. Stability tier (per ADR-005 §2)

Added alongside `ctx.read`/`write`/`sql`/`copy_from`: **Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0**. User-prompt "Frozen at v1.0" *is* this row; no new ladder. Beta @ v0.1 keeps kwarg-shape NVs movable until v0.5 lock. `MaterializationResult` inherits.

### 4. NE-code allocations (per ADR-006 §Decision)

Per "one code per subclass" + **semantic-over-source**:

| Raised when | Subclass | NE-code |
|---|---|---|
| `asset` unresolvable | `NucleusAssetNotFound` (errors.py:164) | `NE3002` reused (ADR-006 H7) |
| `upstream="skip"` + unmaterialized | `NucleusAssetNotMaterialized` | `NE3003` reused (H11) |
| Pre-write contract violation | `NucleusSchemaError` | `NE2001` reused (H2/4/5/6) |
| Step-3 commit conflict | `NucleusCommitConflictError` | `NE1002` reused (H12) |
| Top-level exception in `@nucleus.asset` body | `NucleusInternalError` | `NE3001` reused (H3) |
| `timeout_seconds` exceeded | `NucleusTimeoutError` (errors.py:355) | **`NE3005` proposed** (resolves ADR-006 §NV #2; see NV #2) |
| AMA cannot route via §6.4 — outer fallback | **`NucleusMaterializationError` (NEW)** | **`NE3004` proposed** (distinct from `NE3001`; per ADR-006 §Decision r3) |

ADR-006 §Initial has 12 codes; this ADR adds **2 new** (`NE3004`, `NE3005`) → 14 total per "monotonic / no-gaps-reserved" rule. **Co-acceptance required** (§Trigger).

### 5. Implementation contract (informative)

`ctx.materialize` delegates to `coordination/asset_materialization.py:materialize(asset_key, *, params=None) -> RunResult` (skeleton plan §3.1 r3) — runs v4.1 §6.2 five-step: validate → partition-enforce → catalog atomic commit (ADR-001) → OpenLineage emit → registry update.

## Consequences

- **LOC impact**: ~150-200 LOC across `sdk/types.py` (~30 LOC new module per skeleton plan §2), `ctx/_decorators.py` or new `ctx/sdk/materialize.py` (~100 LOC; Q5), `errors.py` (~15 LOC for `NucleusMaterializationError`/`NE3004`).
- **Maintenance ownership**: @founder (AGENTS.md §0).
- **Swap**: `docs/internal/swap/dagster.md` (existing). `nucleus-mini-scheduler` (v4.1 §6.7, ~3-5K LOC) MUST honour signature unchanged.
- **Tests**: `tests/sdk/test_materialize.py` (~10-15 cases: happy, each `upstream=` mode, timeout, partition forms, both `asset` forms, unknown-key); `tests/api_stability/test_signatures.py` snapshot; `scripts/dagster_leak_check.py` asserts zero Dagster strings in `MaterializationResult` + `NucleusMaterializationError.user_message`.
- **Sections to update on acceptance** (AGENTS.md §10 r7): v4.1 §13.2 — add `ctx.materialize` row (✅ v0.1+); `docs/specs/nucleus_ctx_sdk_spec.md` §12 + new §5.4 "Materialize API" (NV #4); `cli_spec` §3.4 — reconcile plural drift (NV #1); `sequence_asset_materialization.md` §5 r1 — close; `v01_skeleton_plan.md` §6 Q2 + §7 NV #1 — mark resolved.
- **Downstream**: unblocks `cli/commands/run.py` (§3.2 r6); unblocks `coordination/asset_materialization.py` public-surface tests (§4 step 7); locks `nucleus-mini-scheduler` input contract.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Dagster `materialize()` drifts in 1.10+ (pin `dagster==1.9.5` per ADR-012) | Option C decouples; v4.1 §6.5 test r3 catches; ADR-012 upgrade-PR template. |
| Three-state `upstream=` footgun | `Literal[...]` + mypy `--strict`; Q1 considers `bool` collapse at v0.5. |
| `MaterializationResult` shape locks too early | Beta @ v0.1 — field-add free until Stable; `frozen=True` blocks mutation. |
| `NE3004` ↔ `NE3001` semantic overlap | Docstrings split: 3001 = "invariant violated, bug"; 3004 = "materialize failed, not yet enumerated." Drift Detection (AGENTS.md §11.11). |
| ADR-006 not yet ACCEPTED — adds 2 codes into not-yet-ratified scheme | §Trigger requires ADR-006 acceptance OR co-acceptance — pauses with PoC #1 / ADR-006. |
| `ctx.materialize_assets([...])` plural implies undesigned list variant | NV #1: drop plural from v0.1; CLI iterates singular. |

## Rollback

Argument-shape regret: ADR-013a demotes the kwarg per ADR-005 §3 (6-month deprecation). Return-type regret: field-add free in Beta; removal in Stable per ADR-005 §3. Code regret: per ADR-006 §Rollback **renumbering forbidden** — subclass relabel only. **No emergency rollback for the name** — `ctx.materialize` anchors CLI (cli_spec §3.4); rename = ADR-005 §3 Frozen-tier post-v1.0; structural per AGENTS.md §9.

## Architecture Sections Touched

v4.1 **§6.2** (AMA runtime — primary; user prompt cited §6.3 which is off-by-one, NV #3) · **§6.4** (error translation — wraps every external exception per H1-H17 table) · **§6.5** (Replaceability — signature must survive Dagster → mini-scheduler swap) · **§13.2** (Surface Summary — table this ADR amends) · **§18.1** (v0.1 must-ship — `ctx.materialize` is implicit in *"`nucleus` CLI: `init`,`up`,`down`,`run`,`ingest`"*; this ADR makes it explicit on the SDK side).

## Trigger · Downstream

**Trigger** (PROPOSED → ACCEPTED when all four hold): (1) Founder resolves NV #1–#6 + Q1–Q5; (2) ADR-005 ACCEPTED (tier); (3) ADR-006 ACCEPTED with §NV #2 resolved (`NE3004`+`NE3005`) — OR co-acceptance with ADR-006a; (4) PoC #1 promotion PR co-lands `errors.py +1` subclass + new `sdk/types.py` + v4.1 §13.2 + `docs/specs/nucleus_ctx_sdk_spec.md` §12 amendments. Not calendar-gated — pauses with PoC #1 / ADR-005 / ADR-006.

**Downstream**: `cli/commands/run.py` (skeleton plan §3.2 r6, Mo 4-6) delegates `ASSET_KEY...` → `ctx.materialize(key)`, emits NE3001/NE2001/NE1002/NE3004/NE3005 per cli_spec §3.4+§8. `coordination/asset_materialization.py` (§3.1 r3, Mo 2-3) owns `RunResult → MaterializationResult` transform. `nucleus-mini-scheduler` (v4.1 §6.7, by v1.0) MUST honour signature unchanged. `nucleus-mcp-server` (ADR-002 §4.2, v0.5+) maps `materialize_asset` tool 1:1. `ctx.agent.*` (v0.5+, ADR-005 §4 carve-out) Beta-tier callers per v4.1 §7.3 sandbox.

## NEEDS VERIFICATION (founder, before promotion)

1. **`ctx.materialize` vs `ctx.materialize_assets` plural drift in cli_spec §3.4** (both in one paragraph). Recommend: drop `_assets` from v0.1; multi-asset is the CLI's job (`nucleus run a b c` iterates singular); list-variant → v0.3+. cli_spec §3.4 patched same acceptance PR.
2. **NE-code for `NucleusTimeoutError`.** Provisional `NE3005`; ADR-006 §NV #2 candidates were `NE2004`/`NE3004`. This ADR's `NE3004` for `NucleusMaterializationError` forces `NE3005` for timeout. **Resolve in tandem with ADR-006 §NV #2.** Founder may swap labels — purely cosmetic.
3. **v4.1 §6.2 vs §6.3 citation.** User prompt cited *"§6.3 asset materialization runtime"* — **§6.3 is "What We Add on Top of Dagster"** (capability list); AMA five-step lives in **§6.2 "Asset Materialization Adapter (Amendment 1)"**. This ADR cites §6.2 throughout.
4. **Placement of signature in `docs/specs/nucleus_ctx_sdk_spec.md`** (§4=Read, §5=Write, §6=SQL, §10=Snapshot). Recommend new **§5.4 "Materialize API"** (materialization is the verb that writes).
5. **`AssetRef` vs `NucleusAsset`.** Skeleton plan §6 Q2 prose used `NucleusAsset`; this ADR uses **`AssetRef`** per `docs/specs/nucleus_ctx_sdk_spec.md` §12 line 432 + §3.1. Rename = separate ADR.
6. **`upstream="materialize"` recursion-depth ceiling.** Recursive materialization fans out unboundedly; v4.1 §14.4 covers concurrency, not recursion. Recommend: v0.1 accepts `upstream="skip"` **only**; `"materialize"`/`"validate"` deferred to v0.3+ once telemetry sets safe-depth threshold. If accepted, `Literal[...]` narrows to `Literal["skip"]` for v0.1; additive widening at v0.3+ is Beta-tier-free per ADR-005 §3.

## Open Questions (founder review)

1. **Three-state `upstream` vs `bool`.** Explicit clarity vs API-surface area (`materialize_upstream: bool` loses "validate-only"). Recommend three-state for Beta; collapse iff PoC #5 proves `"validate"` unused.
2. **Multi-key partitions.** Spec §15.3 shows single-string `daily("2024-01-01")`; some assets want tuples `("2026-05-13","us-east-1")`. Recommend single-string only at v0.1; tuple lights up v0.3 with 3-level keys (cli_spec §10 NV #6).
3. **`timeout_seconds` default.** `None` vs `3600`. CI risk: runaway materialization hangs test process. Recommend `None` for SDK; `nucleus run` surfaces `--timeout` defaulting `3600s` (aligns with v4.1 §16.5 99.9% materialization success target).
4. **`MaterializationResult` vs `Materialization` name.** AGENTS.md §7 lists `materialization` as the canonical noun for the *act*; `Result` suffix disambiguates the *outcome record*. Recommend keep.
5. **`RunResult → MaterializationResult` transform owner.** (a) `ctx/_decorators.py` (+30-50 LOC); (b) new `ctx/sdk/materialize.py` (off skeleton-plan tree; cleaner boundary); (c) `coordination/asset_materialization.py` returns `MaterializationResult` directly (couples L2 to SDK types — violates skeleton plan §3.1 r3 Internal-tier intent). Recommend (b), ~80 LOC.

---

*Closes the citation gap surfaced by `v01_skeleton_plan.md` §6 Q2 + §7 NV #1. Binds no code yet; binds every code-shaping decision for `cli/commands/run.py`, `coordination/asset_materialization.py`'s public surface, and the `nucleus-mini-scheduler` fallback signature after acceptance. Co-dependencies: ADR-005 (tier) · ADR-006 (codes) · PoC #1 promotion.*

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
