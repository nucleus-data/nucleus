# ADR-009: OpenLineage Event Schema Policy

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: openlineage, lineage, events, schema-stability, tier-0, ama
> **Related**: ADR-001 (snapshot id), ADR-002 §8.2 (AI/MCP consume lineage), ADR-005 (tiers — OL facets Stable @ v0.5 → Frozen @ v1.0), ADR-006 (NE-codes → `errorMessage`), ADR-007 (OL = GREEN Apache-2.0), AGENTS.md §11.7 + §11.12, v4.1 §6.2 step 4 + §6.4 + §12.4, `docs/research/openlineage.md` (Worker J), `docs/research/ai_hallucinations.md` (2026-05-13 `openlineage-dagster` trap), `docs/architecture/sequence_asset_materialization.md` §2 row "3, 17" + §5 row 3 (Worker L)

## Context

Per v4.1 §6.2 step 4, OpenLineage is the only lineage-emission path: every `@nucleus.asset` materialization fires `RunEvent(START)` + one terminal `RunEvent(COMPLETE|FAIL|ABORT)` from inside the Asset Materialization Adapter (AMA, ~500 LOC). OL is **Tier 0 (immortal)** per v4.1 §3.2 + §4.1 — no swap target, Apache-2.0, LF AI & Data Graduate (Worker J §1 + §8). Once an event escapes a release the facet shape is a public contract: consumers `grep` JSONL; AI Copilot maps facets to fix steps; Marquez / Workbench / MCP bind to field paths.

Worker J's research locked four shape choices that must resolve before the first AMA event escapes: (1) `openlineage-dagster` is **DEAD** at `dagster==1.9.5` — removed from the OL main repo Oct 2025; logged in `ai_hallucinations.md` 2026-05-13 — AMA emits directly (Worker J §9); (2) `openlineage.client.run` (v1; `DeprecationWarning` at import per Worker J §4 + §10) vs `openlineage.client.event_v2` (v2 active); (3) `FileTransport` JSONL vs `HttpTransport` Marquez vs silent default `ConsoleTransport` swallowing events into structlog (Worker J §10); (4) which facets are *mandatory*.

## Decision

> **`openlineage.client.event_v2` only (NEVER v1). `FileTransport` JSONL at `.nucleus/lineage/events.jsonl` for v0.1. `HttpTransport` opt-in for v0.3+ via `nucleus enable marquez`. Ten mandatory facets per event (eleventh `errorMessage` on FAIL). Emit ALWAYS from the AMA — never via the dead `openlineage-dagster` bridge.**

### 1. Module choice

Use **`openlineage.client.event_v2`** only. NEVER import from `openlineage.client.run` (v1; `DeprecationWarning` at import per Worker J §4 + §10). Facet classes import from `openlineage.client.facet_v2`.

```python
# Docs: https://openlineage.io/docs/client/python/usage · Pinned: openlineage-python==1.47.1
from openlineage.client.event_v2 import RunEvent, Run, Job, Dataset, InputDataset, OutputDataset
from openlineage.client.uuid import generate_new_uuid
```

### 2. Transport tier per Nucleus release

| Release | Default | Alternate |
|---|---|---|
| **v0.1** | `FileTransport` JSONL at `.nucleus/lineage/events.jsonl` (`append=True` for local `file://`) | none |
| **v0.3** | `FileTransport` default; `nucleus enable marquez` switches to `HttpTransport` → `http://localhost:5000` | `FileTransport` remains as fallback |
| **v0.5+ / Cloud** | `HttpTransport` to Cloud collector; `AsyncHttpTransport` once OL drops `experimental` (Worker J §6) | `FileTransport` for air-gapped |

**Why `FileTransport` v0.1**: Marquez is a 4-container service (API + Postgres + UI + nginx) — violates the 30-min beachhead per v4.1 §1.5 (Worker J §11); JSONL is `jq`-greppable, zero infra cost. **Why never the default**: with no transport configured the library defaults to `ConsoleTransport`, routing events to `structlog` INFO logs and **silently swallowing them** (Worker J §10) — AMA MUST pass an explicit `transport=`.

### 3. Mandatory facets per `RunEvent`

Every Nucleus-emitted `RunEvent` MUST carry these. Missing field = AMA bug; caught by `scripts/check_openlineage_facets.py`. Tier column maps to ADR-005 §2 row "OpenLineage facets from `ctx`" (Stable @ v0.5 → Frozen @ v1.0).

| # | Facet path | Source |
|---|---|---|
| 1 | `eventType` ∈ `{START, COMPLETE, FAIL, ABORT}` (Worker J §4: never `SUCCESS`/`SUCCEEDED`/`ERROR`) | AMA state machine |
| 2 | `eventTime` ISO 8601 UTC | `datetime.now(timezone.utc).isoformat()` |
| 3 | `producer` = `https://github.com/<org>/nucleus/tree/v<__version__>` | `nucleus.__version__` |
| 4 | `schemaURL` (pinned for `event_v2`) | OL library constant |
| 5 | `run.runId` — **UUIDv7** via `generate_new_uuid()` (NEVER `uuid.uuid4()` per Worker J §10) | AMA on START |
| 6 | `job.namespace` (project name from `nucleus.toml`) | coordination config |
| 7 | `job.name` (asset key, dotted) | `@nucleus.asset(name=...)` |
| 8 | `inputs[].facets.schema` `SchemaDatasetFacet` from upstream `Table.schema()` via pyarrow | `ctx.read` accumulator |
| 9 | `outputs[].facets.schema` from committed snapshot | post-`Table.append` |
| 10 | `outputs[].facets.dataSource` storage URI per Worker J §5.1 (no Iceberg namespace; catalog id is *content* of dataset name) | catalog config |
| 11 (FAIL) | `run.facets.errorMessage` `ErrorMessageRunFacet`; NE-code per ADR-006; NEVER a raw external classname (AGENTS.md §11.7) | error translator |

**Optional (v0.5+)**: `columnLineage` (Worker J §5.2 — sqlglot; class `ColumnLineageDatasetFacet`, key camelCase, transformations exactly `DIRECT`/`INDIRECT`); `dataQuality` from `@nucleus.check`; `parent`; `outputStatistics`; `nominal_time_run`.

**Total mandatory: 10 always-on + 1 conditional-on-FAIL = 11.**

### 4. Forbidden

- **NEVER** `pip install openlineage-dagster` — DEAD at our pin (Worker J §9 + `ai_hallucinations.md`); AI suggestions to install it = release-blocker bugs.
- **NEVER** import from `openlineage.client.run` (v1 deprecated; `DeprecationWarning` at import).
- **NEVER** rely on default `ConsoleTransport` — swallows into `structlog` (Worker J §10); AMA MUST pass explicit `transport=`.
- **NEVER** `FileTransport(append=False)` for local `file://` (one file per event + loses history). **MUST** `append=False` for remote fsspec paths (S3/GCS/Azure) — `append=True` silently switches to overwrite (Worker J §5.3 + §10).
- **NEVER** `uuid.uuid4()` for `runId` — UUIDv7 via `generate_new_uuid()` (Worker J §10).
- **NEVER** invent `RunState.SUCCESS`/`SUCCEEDED`/`ERROR` — `COMPLETE` = success.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **AI proposes `openlineage-dagster`** (top hallucination per `ai_hallucinations.md`) | This ADR cited in AMA docstring; CI script greps forbidden imports |
| **`event_v2` deprecated** when OL ships v3 | Constraint #11 single-component upgrade ADR fires; rollback below |
| **Mandatory facet missing** at runtime | AMA wraps `emit(...)` in `try/except` → `NucleusLineagePartial` (`NE3xxx` per ADR-006); asset still succeeds (lineage = observability, not correctness) |
| **`ConsoleTransport` activates by accident** | CI asserts every `OpenLineageClient(` constructor passes explicit `transport=` |
| **External classname leak into `errorMessage`** (release-blocker per AGENTS.md §11.7) | Extend `scripts/dagster_leak_check.py` to grep emitted JSONL for `dagster.`/`duckdb.`/`polars.`/`pyiceberg.` substrings |
| **`OPENLINEAGE_DISABLED=true` → `NoopTransport`** silently (Worker J §10) | `nucleus doctor` (v0.2+) surfaces the env var |
| **Iceberg dataset naming churns** v0.1 filesystem → v0.3+ Lakekeeper | Worker J §5.1: storage URI = namespace, catalog id = *content* of dataset name; same convention spans both backends |

## Verification plan

1. **`scripts/check_openlineage_facets.py`** (~80 LOC, new) — reads emitted JSONL; asserts 10 mandatory facets (+ `errorMessage` on FAIL); greps forbidden imports (`openlineage.client.run`, `openlineage-dagster`); asserts every `OpenLineageClient(` passes `transport=`. Wired into CI alongside `check_error_codes.py` (ADR-006).
2. **`tests/lineage/test_event_v2_schema.py`** — snapshot tests; asserts pinned `schemaURL`, UUID-pattern `runId`, allowed `eventType`.
3. **PoC #1 promotion** wires `errorMessage` (`NucleusError.user_message` → `ErrorMessageRunFacet.message`; NE-code → `code` field).
4. Resolves `sequence_asset_materialization.md` §5 row 3 open Q ("pre-fn failures emit FAIL or nothing?") → **emit FAIL** once AMA reaches step 1; silent skip if not.

## Rollback

- **`event_v2` proves problematic** → **ADR-009a** allows `event_v1` for one minor cycle; both modules co-exist in `openlineage-python==1.47.1` (Worker J §4).
- **Mandatory facet un-emittable** → **ADR-009b** demotes to Optional via ADR-005 §3 Stable-tier protocol.
- **No rollback** for the dead `openlineage-dagster` bridge — AMA owns emission per v4.1 §6.2 step 4 forever.

## Docs URLs

- Spec: <https://openlineage.io/docs/spec/object-model> · <https://openlineage.io/docs/spec/run-cycle> · <https://openlineage.io/docs/spec/naming>
- Python client: <https://openlineage.io/docs/client/python/usage>
- ColumnLineage facet (v0.5+): <https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/spec/facets/ColumnLineageDatasetFacet.json>
- PyPI 2026-05-13: <https://pypi.org/project/openlineage-python/1.47.1/> · Primary: `docs/research/openlineage.md` (Worker J) · `docs/research/ai_hallucinations.md`

### NEEDS VERIFICATION

1. **`run.runId` ↔ Dagster `run_id` mapping**: Worker J §10 mandates UUIDv7 via `generate_new_uuid()`; v4.1 §6.2 sequence shows Dagster `run_id` flowing into the OL run. Default position: AMA generates a UUIDv7 as canonical OL `runId`; Dagster `run_id` stored as a custom run facet (`nucleus_dagster_run`) so `nucleus runs <id>` can join. Confirm against Dagster `1.9.5` `DagsterRun.run_id` format before AMA prototype.
2. **`schemaURL` exact value** for `event_v2`: pinned in `openlineage-python==1.47.1` source but not in user-facing docs index. Read from library constant at runtime; cross-check on every minor bump.

## Trigger

Status flips **PROPOSED → ACCEPTED** when all three hold: (1) founder signs off (or amends per ADR-002 §6); (2) `scripts/check_openlineage_facets.py` lands in CI; (3) AMA prototype emits one valid `event_v2` JSONL line verified by the script. **Not strictly gated on PoC #1 promotion** — governance can land before code. In practice AMA work fires *after* PoC #1 promotes because the translator output feeds `errorMessage` (§3 row 11).

## Downstream consumers

| Consumer | When | Affected how |
|---|---|---|
| AMA (`src/nucleus/coordination/asset_materialization.py`) | Post-PoC #1 (Mo 2-3) | Only call site for `client.emit(...)` per Worker J §1; emits per §3 |
| `scripts/dagster_leak_check.py` | PoC #1 promotion | Greps emitted JSONL for external classnames in `errorMessage.message` |
| PoC #4 boot-time | Mo 3-4 | Lazy-imports `openlineage.client` (~120-180 ms cold-import, Worker J §6) to fit <10 s budget |
| `nucleus enable marquez` (v0.3+) | Mo 8-14 | Switches to `HttpTransport`; same §3 schema |
| Cloud Copilot + `nucleus-mcp-server` (v0.5+) | Mo 14-20 | Reads JSONL or queries Marquez; AI APIs Beta per ADR-005 §2 |
| Founder debugging (v0.1) | Mo 0-4 | `jq '.eventType, .job.name' .nucleus/lineage/events.jsonl` |

## Open questions for founder

1. **`eventTime` timezone**: UTC always or respect user `TZ`? **Default: UTC always** — OL spec convention; Marquez stores UTC; local breaks multi-machine teams.
2. **`producer` content**: `v<__version__>` only or `+<commit-sha>`? **Default: `v<__version__>` for OSS; `+<commit-sha>` only in Cloud** — per-deployment forensics without leaking dev-branch shas publicly.
3. **`job.namespace` structure**: single string from `nucleus.toml` or hierarchical `org.team.project`? **Default: project name for v0.1**; revisit at v0.3 catalog migration (ADR-004) when Lakekeeper introduces real namespace boundaries.

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
