# Swap Target: Dagster → `nucleus-mini-scheduler`

**Tier**: 2 (orchestration substrate, fully replaceable, per `docs/specs/nucleus_architecture_v4.1.md` §6.3, §6.7, §9.2) · **Default**: `dagster==1.9.5` (`pyproject.toml:51`) · **Swap target (primary)**: `nucleus-mini-scheduler` — in-house fallback per `AGENTS.md` §4 ("mini-scheduler as fallback only") and v4.1 §6.7. Triggered ADR-NNN at swap time (no dedicated ADR exists yet — latest is ADR-013) · **Swap target (fallback)**: Prefect 3.x — only if mini-scheduler would breach the 30K v1.0 LOC ceiling (Hard Constraint #8) · **Status (2026-05-13)**: Interface documented + smoke tests in CI; full swap on-demand only per v4.1 §9.3.

This swap is **categorically different** from DuckDB / Polars: the swap target is in-house, not OSS. The mini-scheduler is a **v1.0 commitment** under v4.1 §6.7, not a v0.1 commitment. v0.1 ships Dagster wrapped behind the AMA; the in-house fallback only materializes if a trigger fires.

## What we use Dagster for

The wrapped surface is deliberately tiny. Per v4.1 §6.4 + the Anti-Over-Engineering directive, Dagster lives behind the **Asset Materialization Adapter** (AMA) at `coordination/asset_materialization.py` and is invisible to users:

- **In-process materialization** of `@nucleus.asset` definitions: the AMA translates `_AssetDefinition` → `dagster.AssetsDefinition`, then routes to `dagster.materialize` (production) or `dagster.materialize_to_memory` (dry-run). Implemented across the four AMA helpers (lines 106-341).
- **Asset-key identity**: `dagster.AssetKey(["schema", "name"])` mirrors our 2-segment key (`asset_materialization.py:160-161`).
- **Exception translation**: `dagster.DagsterExecutionStepExecutionError` is registered as the generic Dagster-wrapper fallback in `coordination/error_translation.py:308`; `translate(exc)` walks `__cause__`/`__context__` to prefer specific library handlers (DuckDB / Polars / pyiceberg) over the wrapper.
- **NOT used in v0.1**: `@op`, `@job`, `@sensor`, `@schedule`, `ConfigurableResource`, the Dagster webserver / Dagit, `IOManager` (deferred until `coordination/iceberg_writer.py` lands), partitions, backfills, multi-process executors, code locations, code servers (`docs/internal/research/dagster.md` §5).

The swap boundary is **the four AMA helpers**: any swap target reimplements only these. Everything else stays unchanged.

## API surface we depend on

The four AMA helpers + the coordination/error_translation registry — each is one swap unit:

| Wrap site | Dagster call | Mini-scheduler equivalent (sketch) |
|---|---|---|
| `_resolve_asset_from_registry` (`asset_materialization.py:106`) | none — pure Nucleus registry lookup via `sdk.decorators.get_asset` | unchanged (registry is ours) |
| `_build_dagster_assets_definition` (`asset_materialization.py:129`) | `dagster.AssetKey(...)`, `dagster.asset(key=...)` decorator | `mini_scheduler.AssetNode(key=..., compute_fn=...)` (sketch) |
| `_run_dagster_in_process` (`asset_materialization.py:204`) | `dagster.materialize([assets_def], raise_on_error=True)` / `dagster.materialize_to_memory(...)` | `mini_scheduler.run_in_process([nodes], raise_on_error=True)` (sketch) |
| `_translate_result` (`asset_materialization.py:273`) | reads `execute_result.success` only in v0.1 | reads the same `success` flag from a `MiniRunResult` — shape-compatible by design |
| Error registry entry (`error_translation.py:308`) | `dagster.DagsterExecutionStepExecutionError` | drop entry; mini-scheduler raises user exception unwrapped, so library handlers (DuckDB / Polars / pyiceberg) match directly |

That's the full surface. Any function not in this list is internal to Dagster and not part of our wrap; if a future `coordination/` PR reaches deeper, the swap doc updates with it.

## Swap target sketch

```python
# Pseudocode — coordination/asset_materialization.py with Dagster swapped for
# nucleus-mini-scheduler. Interface preserved per v4.1 §6.5
# (replaceability mandate — public materialize_asset signature MUST survive).

# When triggered, this lands in src/nucleus/coordination/mini_scheduler/.
# Estimated 3000-5000 LOC + 5-week build per v4.1 §6.7.
from nucleus.coordination.mini_scheduler import AssetNode, run_in_process


def _build_mini_scheduler_node(entry: _AssetDefinition) -> AssetNode:
    schema_segment, name_segment = entry.key.split(".", 1)
    return AssetNode(
        key=(schema_segment, name_segment),
        compute_fn=entry.fn,  # no shim needed — mini-scheduler accepts arity 0/1 natively
    )


def _run_mini_scheduler_in_process(node: AssetNode, *, dry_run: bool) -> "MiniRunResult":
    # mirror dg.materialize / dg.materialize_to_memory split
    try:
        if dry_run:
            return run_in_process([node], persist_outputs=False, raise_on_error=True)
        return run_in_process([node], persist_outputs=True, raise_on_error=True)
    except NucleusError:
        raise  # already typed
    except BaseException as exc:
        raise translate(exc) from exc  # error_translation.translate unchanged
```

The mini-scheduler reuses the same `MaterializationResult` boundary (ADR-013 §2) — by design. Caveats: loss of Dagit / GraphQL (Workbench v0.2+ rebuilds the run-history view from `ctx` introspection); `@asset_sensor` + `FreshnessPolicy` are non-trivial (deferred to v1.0+); Tier 3 users running `nucleus enable compat-dagster` lose the GraphQL path (smallest user segment per v4.1 §6.6); `scripts/dagster_leak_check.py` is the safety net — must stay at 0 violations.

## Smoke tests

Located at `tests/swap/test_dagster_swap.py`. Tests through `nucleus.coordination.asset_materialization.materialize_asset` rather than importing `dagster` directly — `scripts/dagster_leak_check.py` forbids `import dagster` outside `src/nucleus/coordination/` and `tests/coordination/`, and `tests/swap/` is intentionally NOT in the allow-list (any leak there is an architecture-review trigger).

- 3 live tests: register an asset, materialize it via `materialize_asset(...)`, verify shape; dry-run path produces same shape; missing-key raises `NucleusAssetNotFound` with no `dagster.` leak in `rendered()`
- 3 interface assertions: the 4 AMA helpers exist as module attributes (the swap unit boundary); `dagster` is discoverable via `importlib.util.find_spec` (it's an installed runtime dep); Mini-scheduler swap target NOT yet importable (asserts `find_spec("nucleus.coordination.mini_scheduler")` returns None — by design pre-trigger)
- 2 skip-marked placeholders: mini-scheduler smoke suite (built when trigger fires)

## Trigger events for full swap implementation

Per v4.1 §6.7 + §9.3, swap fires only on:

- Dagster Labs abandons OSS `main` >12 months OR pivots license (current: Apache-2.0 — `docs/internal/research/dagster.md` §1)
- `nucleus up` boot regresses >2× vs PoC #4 baseline (5.82 s, 117.3 MB validated 2026-05-12)
- PoC #1 retroactively fails ≥6/8 error-translation scenarios on a Dagster minor bump (auto-escalates per v4.1 §6.7)
- Architectural-constraint violation: JVM dep, mandatory webserver for `materialize()`, `IOManager` extension contract breaks (Hard Constraints #1, #3)
- Community demand: ≥30% of telemetry requests mini-scheduler or Prefect

The first trigger should also produce **ADR-NNN: nucleus-mini-scheduler design** (no dedicated ADR exists today; the latest is ADR-013). Mini-scheduler is the v1.0 default per AGENTS.md §4 in any case ("mini-scheduler as fallback only by v1.0"), so the ADR is on the roadmap regardless of trigger.

Until one fires, we maintain interface + smoke tests only, never a full second implementation. That is "Composability Tax" per v4.1 §9.3 + the Anti-Over-Engineering directive in `.cursor/rules/nucleus.mdc`.

## References

- Dagster docs home: https://docs.dagster.io/
- Dagster Python API index: https://docs.dagster.io/api/python-api/
- `dagster.materialize`: https://docs.dagster.io/api/dagster/execution
- `dagster.materialize_to_memory`: https://docs.dagster.io/api/dagster/execution#dagster.materialize_to_memory
- `@dagster.asset`: https://docs.dagster.io/api/dagster/assets#dagster.asset
- `dagster._core.errors`: https://docs.dagster.io/api/python-api/errors
- Prefect 3.x (fallback): https://docs.prefect.io/3.0/
- Architecture: `docs/specs/nucleus_architecture_v4.1.md` §6.3 (what we take from Dagster), §6.4 (error translation discipline), §6.5 (replaceability mandate), §6.7 (mini-scheduler design intent), §9.2-§9.3
- Research notes: `docs/internal/research/dagster.md` (PoC #1 anchor)
- Related: `docs/decisions/ADR-013-ctx-materialize-api.md` (the public `materialize_asset` contract that survives any swap)
