# Research: Dagster

> **Pinned**: 1.9.5  •  **Verified**: 2026-05-12  •  **Docs**: https://docs.dagster.io/
> **Used in**: `src/nucleus/coordination/` (post PoC #1). Constraint #2 + #6.4.
> **Companion**: [`docs/architecture/sequence_error_translation.md`](../../architecture/sequence_error_translation.md).

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before touching `coordination/` or starting PoC #1.

---

## §1. At a glance

- **License**: Apache-2.0  •  **Maintainer**: Dagster Labs (VC-backed, OSS since 2018)  •  **GitHub**: https://github.com/dagster-io/dagster
- **Position**: L2 Coordination — wrapped and hidden behind `ctx`. Users never `import dagster`.

**What it is**: An **asset-centric orchestrator**. Decorated Python functions declare data assets; Dagster builds the dependency graph, runs materializations, records run/event state, and exposes asset lineage. The primitive is the **asset**, not the task — which matches our `@nucleus.asset` and is why we wrap it instead of building one.

---

## §2. Version verification

Verified via `https://pypi.org/pypi/dagster/1.9.5/json` + `https://github.com/dagster-io/dagster/releases/latest`.

| Check | Result |
|---|---|
| Is 1.9.5 a real release? | **YES** — sdist + wheel, uploaded 2024-12-12T21:08:28Z |
| `requires_python` | `<3.13,>=3.9` — compatible with our `>=3.11,<3.13` pin |
| Yanked? | No |
| Latest stable as of today | **1.13.3** (released 2026-04-30) |
| Gap | ~16 months / multiple minor releases. **Informational, not blocking.** |
| CVEs affecting 1.9.5 | None. CVE-2025-51481 (LFI in `dagster._grpc.impl.get_notebook_data`) is in 1.10.14, fixed in 1.10.16; does **not** affect 1.9.5. |

The gap is intentional pre-Heartbeat: stabilize the wrap against a known release before chasing minors. Upgrade workflow: [`docs/compatibility.md`](../../compatibility.md) §4.

---

## §3. Why Nucleus uses Dagster

- **Layer**: L2 Coordination.
- **Provides**: asset graph, materialization runs, in-process execution, asset lineage primitives, run/event log.
- **Hidden** behind `ctx` SDK (v4.1 §6.4). No `dagster` import, type, exception, or stacktrace crosses `coordination/` → `ctx/`.
- **Alternatives rejected**: Prefect (workflow-centric, not asset-first), Airflow (task-centric, heavy daemon, JVM-adjacent), Luigi (stagnant). Building our own = Hard Constraint #3 violation.
- **Why Dagster wins**: asset-first matches our primitive; ephemeral instance fits local-first; declarative model is LLM-authorable; Apache-2.0; no JVM.

---

## §4. Core concepts we depend on

Paths below are under `https://docs.dagster.io`.

- **Software-defined asset (`@asset`)** — Decorated Python fn; return value = stored data product. → `/guides/build/assets`
- **`AssetKey`** — Tuple identifier; we use `["layer", "name"]` mirroring `<layer>.<entity>`. → `/api/dagster/assets#dagster.AssetKey`
- **`IOManager`** — Per-asset "store output / load input" plumbing. Default writes pickles; we subclass for Iceberg. → `/guides/build/io-managers/`
- **`DagsterInstance.ephemeral()`** — In-memory, no SQL state, no daemon, no run-history persistence. **Our v0.1 mode** (PoC #4 boot < 10 s target). → `/api/dagster/internals#dagster.DagsterInstance`
- **`materialize(...)`** — Runs assets and calls IOManager `handle_output`, so writes happen. Production path. → `/api/dagster/execution#dagster.materialize`
- **`materialize_to_memory(...)`** — Runs but stores outputs in memory. Tests + dry runs. → `/api/dagster/execution#dagster.materialize_to_memory`
- **`Definitions`** — "Code location" grouping assets/resources/sensors/schedules. v0.1 = one in-process Definitions. → `/api/dagster/definitions#dagster.Definitions`
- **`AssetMaterialization` event** — Emitted on success; carries metadata (we record snapshot IDs through it). → `/api/dagster/assets#dagster.AssetMaterialization`
- **Asset graph / lineage** — Built statically from `deps=` / input arg names. Powers asset-level lineage in v0.1 (column-level → v0.5+).

---

## §5. Critical API surface

Symbols our Adapter calls. Signatures linked from the [Python API index](https://docs.dagster.io/api/python-api/).

| Symbol | Signature (1.9.5) | Use |
|---|---|---|
| `@dagster.asset` | `@asset(*, name=None, key=None, deps=None, ins=None, io_manager_key=None, ...)` | Applied internally when translating `@nucleus.asset`. |
| `dagster.materialize` | `materialize(assets, *, instance=None, resources=None, ...) -> ExecuteInProcessResult` | Production (`ctx.run`). |
| `dagster.materialize_to_memory` | `materialize_to_memory(assets, *, resources=None, ...) -> ExecuteInProcessResult` | Tests, `--dry-run`, PoC #1. |
| `DagsterInstance.ephemeral` | `classmethod ephemeral() -> DagsterInstance` | Single source of `instance` in v0.1. |
| `dagster.Definitions` | `Definitions(assets=..., resources=..., sensors=..., schedules=...)` | Built once from user's `assets/`. |
| `dagster.IOManager` | Override `handle_output(context, obj)` + `load_input(context)` | Base class for `IcebergIOManager`. |
| `dagster.OpExecutionContext` | Per-op runtime context | **Internal only**. Never crosses into `ctx/`. |
| `dagster.AssetMaterialization` | `AssetMaterialization(asset_key, metadata=None, ...)` | Internal event after a successful Iceberg commit. |

**Not used in v0.1**: `@op`, `@job`, `@sensor`, `@schedule`, `ConfigurableResource`, the Dagster webserver, partitions, backfills, multi-process executors.

---

## §6. Exception types we'll translate (PoC #1 target)

The reason PoC #1 exists. Module: `dagster._core.errors`. Reference: https://docs.dagster.io/api/python-api/errors

Initial set — must be re-verified against running 1.9.5 in PoC #1 Week 1:

| Class | Raised when | Translates to |
|---|---|---|
| `DagsterError` | Base of all framework errors | Catch-all fallback |
| `DagsterUserCodeExecutionError` | Wraps any exception in user compute fn | **Unwrap `__cause__`, re-translate** |
| `DagsterExecutionStepExecutionError` | A step (asset) crashed | **Unwrap inner cause (DuckDB/Polars/PyIceberg), re-translate** |
| `DagsterExecutionStepNotFoundError` | Step key doesn't exist | `NucleusAssetNotFound` (suggest typo check) |
| `DagsterStepOutputNotFoundError` | Required upstream output missing | `NucleusAssetNotMaterialized` |
| `DagsterInvalidDefinitionError` | Bad `@asset` def — cycles, dup names, bad deps | `NucleusInvalidAssetDefinition` |
| `DagsterInvariantViolationError` | Dagster's internal invariant broken | `NucleusInternalError` (bug report) |
| `DagsterTypeCheckDidNotPass` | Output type mismatch vs declared `DagsterType` | `NucleusSchemaError` |
| `DagsterResourceFunctionError` | Resource init fn raised | `NucleusConfigError` |
| `DagsterInvalidConfigError` | Provided config doesn't match schema | `NucleusConfigError` |

**Flagged for PoC #1 to verify** (names appear in `sequence_error_translation.md` §4.1 but I could not pin them to the 1.9.5 errors page — possible AI drift; log results to `docs/internal/research/ai_hallucinations.md`):

- `DagsterAssetNotFoundError` — *unconfirmed*. Asset-missing case may actually surface as `DagsterExecutionStepNotFoundError`.
- `DagsterExecutionInterruptedError` — *unconfirmed*. Ctrl+C may surface as bare `KeyboardInterrupt`.
- `DagsterUserCodeProcessError` — *unconfirmed* in-process (likely subprocess-only).

PoC #1 Week 1 = trigger each of the 8 scenarios in `sequence_error_translation.md` §4.1 and reconcile both docs with reality.

---

## §7. Known gotchas / pitfalls

- **Exception wrapping is multi-layer.** User exc → `DagsterUserCodeExecutionError` → `DagsterExecutionStepExecutionError`. Walk `__cause__` (fall back to `__context__`) until you reach a non-Dagster type before translating.
- **`materialize_to_memory()` does NOT persist anything**; `materialize()` with an ephemeral instance **does** write through the IOManager and may create a temp dir for compute logs. Tests = `_to_memory`; runs = `materialize`.
- **Asset vs Op.** Assets only; never surface Ops through `ctx` (leaks workflow vocabulary — `engineering.md` §15 forbids it).
- **Code locations.** v0.1 = one in-process Definitions. Multi-location / remote code servers force a daemon model — deferred to v0.3+.
- **Async assets** (`async def` compute fns) work but exception wrapping differs (inner cause may be wrapped in `asyncio` task machinery). **PoC #1 must investigate** and add an async case to the 50-scenario fixture set.
- **Eager `import dagster` installs a logging handler** that fights `structlog` (`engineering.md` §5.1). Import lazily inside `coordination/` functions, after `nucleus.logging.configure()` runs.
- **Platform notes**: `requires_python <3.13` blocks Python 3.13 in 1.9.5 (we're 3.11/3.12 — informational). Windows requires `psutil>=1.0` and `pywin32!=226`; both ship as wheels.

---

## §8. Interaction with the rest of Nucleus

- **Inputs**: `@nucleus.asset` user fns → Asset Materialization Adapter (`coordination/asset_materialization.py`, ≤500 LOC) translates each into a `@dagster.asset` and registers it in `Definitions`.
- **Outputs**: `IcebergIOManager` (`coordination/iceberg_io_manager.py`, ≤300 LOC) takes `pyarrow.Table` / `polars.DataFrame` and calls PyIceberg `Table.append()` / `.overwrite()`. PyIceberg + catalog handle atomic commits (ADR-001; no custom commit service — Hard Constraint #5).
- **Errors**: caught at the Adapter boundary → Error Translation Layer (`coordination/error_translation.py`, PoC #1) → re-raised as `NucleusError`. `scripts/dagster_leak_check.py` greps test output for `dagster.` — must be 0 in CI.
- **Lineage**: read from Dagster's static asset graph, emitted as OpenLineage events from the Adapter. Asset-level only in v0.1.

Container-level diagram: [`docs/architecture/C4_container.md`](../../architecture/C4_container.md) §2.2.

---

## §9. Upgrade considerations

When bumping the pin (one-component-per-PR per AGENTS.md §11.13), re-check:

- **Exception class names + module paths** — `dagster._core.errors` occasionally refactors; a rename silently breaks Error Translation.
- **`IOManager` interface** — `handle_output` / `load_input` signatures + any new required methods.
- **`Definitions` API** — kwarg shape and any newly-required fields.
- **`AssetKey` representation** — path-tuple stability; new metadata-required params.
- **`materialize` / `materialize_to_memory` signatures** — kwarg order/names; default changes.
- **`DagsterInstance.ephemeral()` semantics** — compute log capture, event-log retention.
- **CVEs**: grep https://github.com/advisories. **Release notes**: https://github.com/dagster-io/dagster/releases (read every minor between current and target).

Major bumps (when 2.x lands) require a full ADR + re-run of the 50-scenario error fixture (`sequence_error_translation.md` §7).

---

## §10. Useful links

- https://docs.dagster.io/ — Docs home. (The 2025 site rewrite changed URL shapes; do not trust pre-2025 cached deep links.)
- https://docs.dagster.io/api/python-api/ — Python API reference index. Bookmark.
- https://docs.dagster.io/api/python-api/errors — Errors module reference. **Our translator's target.** Re-read on every upgrade.
- https://docs.dagster.io/guides/build/assets — Asset concepts + rationale.
- https://docs.dagster.io/guides/build/io-managers/ — Required reading before touching `iceberg_io_manager.py`.
- https://github.com/dagster-io/dagster — Source + issues.
- https://github.com/dagster-io/dagster/releases — Changelog (read full range during any upgrade PR).
- https://pypi.org/project/dagster/ — Version history + vulnerability disclosures.
- https://dagster.io/slack — Community Slack; team responds.

---

*Last verified: 2026-05-12. Re-verify when bumping the pin or before integrating any new Dagster capability.*
