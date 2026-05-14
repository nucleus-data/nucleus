# OpenLineage — Research Notes

> **Pinned**: not yet — candidate `openlineage-python==1.47.1` (released 2026-05-12, verified on PyPI 2026-05-13)  •  **License**: Apache-2.0  •  **Docs**: <https://openlineage.io/docs/>
> **Status in Nucleus**: **Tier 0 (immortal)** per `nucleus_architecture_v4.1.md` §3.2 + §4.1. Asset-level lineage in v0.1 (per §6.2 step 4 + §12.4); column-level via sqlglot in v0.5+ (§12.4 + §18.4).
> **Used in (planned)**: `src/nucleus/coordination/asset_materialization.py` — the AMA is the *only* module that constructs `OpenLineageClient` or calls `client.emit(...)`.

Official-docs anchor per [AGENTS.md Hard Constraint #10](../../AGENTS.md). Read before wiring the OL emitter into the AMA (post PoC #1), or before any column-lineage work in v0.5+. OpenLineage is one of seven immortal substrates in `nucleus_architecture_v4.1.md` §4.1; it has **no swap target** and cannot be re-architected away (see §8 here).

---

## §1. What OpenLineage is, in Nucleus terms

OpenLineage is an **open spec** for emitting data-lineage events. Four core nouns — `Run`, `Job`, `Dataset`, `Facet` — and three event types: `RunEvent`, `JobEvent`, `DatasetEvent`. A `Run` is one instance of a `Job` (UUID-keyed) with input/output Datasets; `Facet`s attach typed, schema-versioned metadata (schema, statistics, ownership, error messages, **column lineage**). Wire format is JSON; OpenAPI spec at **2-0-2**.

Every `@nucleus.asset` materialization **is** an OL `Run`. `ctx.read(...)` calls become Input Datasets; the committed Iceberg snapshot becomes the Output Dataset (snapshot ID lives in the `version` dataset facet). Per v4.1 §6.2, the AMA step 4 — *"emit OpenLineage event"* — is the *only* call site. Users never `import openlineage`. The asset graph (one of the three things Nucleus owns forever) IS derivable from the OL event log: catalog answers *"what exists now?"*; OL answers *"how did it come to be?"*. Workbench (v0.2+) and AI Copilot (v0.5+) consume this stream as the source of truth for lineage queries.

**Governance**: [LF AI & Data Foundation Graduate project](https://lfaidata.foundation/projects/openlineage). Backed by Astronomer, Microsoft, Databricks, Confluent, dbt Labs, Snowflake, Google. Consumed by Airflow (native), dbt (`dbt-ol`), Spark, Flink, Feast, Great Expectations, Marquez, Unity Catalog, Atlan, Datadog, AWS Glue, GCP Data Catalog. This is *the* protocol.

---

## §2. Version verification (PyPI, 2026-05-13)

Source: `https://pypi.org/pypi/openlineage-python/json`.

| Check | Result |
|---|---|
| `1.47.1` real release? | ✓ `openlineage_python-1.47.1-py3-none-any.whl` (113 KB), uploaded 2026-05-12 14:51 UTC |
| Yanked? | ✗ No |
| `license_expression` | **Apache-2.0** |
| `requires_python` | `>=3.10` — our `>=3.11,<3.13` pin is inside ✓ |
| `requires_dist` (runtime) | `attrs>=20.0`, `python-dateutil>=2.8.2`, `pyyaml>=5.4`, `requests>=2.32.4`, `httpx>=0.27.0`, `packaging>=21.0` |
| Wheel | universal `py3-none-any` — Win + macOS + Linux all served |
| Cadence | Monthly minors. 1.40.0 → 1.47.1 over 6 months. Active. |
| JVM-free | ✓ Pure Python. The OL Spark agent is a separate JVM artifact, not relevant. |

Adding OL introduces **two new top-level runtime pins** per Constraint #11: `httpx>=0.27.0`, `requests>=2.32.4`.

---

## §3. Official documentation URLs

Every fact below cites this set. Verified by `WebFetch` 2026-05-13.

- Spec: <https://openlineage.io/docs/spec/object-model> • <https://openlineage.io/docs/spec/run-cycle> • <https://openlineage.io/docs/spec/facets/> • <https://openlineage.io/docs/spec/naming>
- OpenAPI (2-0-2): <https://openlineage.io/apidocs/openapi/>
- Python client: <https://openlineage.io/docs/client/python> • <https://openlineage.io/docs/client/python/usage> • <https://openlineage.io/docs/client/python/configuration>
- Spec source: <https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md>
- ColumnLineage facet schema (v1-2-0): <https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/spec/facets/ColumnLineageDatasetFacet.json>
- Integrations: <https://openlineage.io/docs/integrations/spark> • <https://openlineage.io/docs/integrations/dbt> • <https://openlineage.io/docs/integrations/about>
- Source / releases / PyPI: <https://github.com/OpenLineage/OpenLineage> • <https://github.com/OpenLineage/OpenLineage/releases> • <https://pypi.org/project/openlineage-python/>

**404s observed 2026-05-13 — do not cite**: `/docs/integrations/` (index), `/docs/integrations/dagster` (removed — see §9), `/docs/spec/facets/dataset-facets/column-lineage-facet` (schemas in GitHub spec tree only), `/docs/development/developing/python/setup` (replaced by `/docs/client/python` family).

---

## §4. APIs Nucleus will wrap

Verified against `openlineage-python==1.47.1` source (`client/python/src/openlineage/client/`) + the 1.47.0 docs build.

| Symbol | Signature / import (1.47.1) | Use in Nucleus |
|---|---|---|
| `OpenLineageClient` | `OpenLineageClient(url=None, options=None, session=None, transport=None, factory=None, *, config=None)` — `url` deprecated | One per process, lazy-constructed in AMA. |
| `client.emit(event)` | `(event: RunEvent | DatasetEvent | JobEvent) -> None` | Per state transition (START + one of COMPLETE / FAIL / ABORT). |
| `client.close(timeout=-1.0)` | `(timeout: float = -1.0) -> bool` | Flush on `nucleus down` / process exit. |
| `RunState` | enum: `START`, `RUNNING`, `COMPLETE`, `ABORT`, `FAIL`, `OTHER` (six, exact) | START + (COMPLETE \| FAIL \| ABORT) per asset materialization. |
| `RunEvent` (v2) | `RunEvent(eventType, eventTime, run, job, producer, inputs=[], outputs=[], schemaURL=...)` | The event Nucleus emits. |
| `Run`, `Job`, `Dataset`, `InputDataset`, `OutputDataset` | `from openlineage.client.event_v2 import …` | Event payload construction. |
| `generate_new_uuid` | `from openlineage.client.uuid import generate_new_uuid` → UUIDv7 | `Run.runId`; **not** `uuid.uuid4()`. |
| `FileTransport` / `FileConfig` | `from openlineage.client.transport.file import …` — `log_file_path`, `append=False`, optional `storage_options` / `filesystem` / `fs_kwargs` (fsspec) | **v0.1 default.** JSONL to `.nucleus/lineage/`. |
| `HttpTransport` / `HttpConfig` | `from openlineage.client.transport.http import …` — `auth.type ∈ {api_key, jwt}`, `compression=gzip`, `retry` dict (since 1.33) | v0.3+ Marquez and v0.5+ Cloud. Uses `httpx`. |
| `ConsoleTransport` / `ConsoleConfig` | `from openlineage.client.transport.console import …` | Library default when no config — INFO log to `openlineage.client.transport.console`. |
| `NoopTransport` | activated by `OPENLINEAGE_DISABLED=true` | Backs `--no-lineage` escape hatch. |
| Facet v2 imports | `from openlineage.client.facet_v2 import schema_dataset, sql_job, error_message_run, source_code_location_job, nominal_time_run, parent_run, column_lineage_dataset` | Schema, SQL text, error info, column-lineage. |

**Two event modules exist**: `openlineage.client.run` (v1, deprecation-warns at import) and `openlineage.client.event_v2` (v2). **Always use v2.** The library itself imports v1 under `warnings.catch_warnings` in `client.py` because the public types must stay backwards-compatible.

**Producer string**: a stable URI identifying the emitter (spec recommends git URL with tag/sha). Pin a single value in Nucleus config — e.g., `f"https://github.com/<org>/nucleus/tree/v{__version__}"`. Do not regenerate per-event.

---

## §5. Integration points with Nucleus

### §5.1 Asset materialization → OL Run event (v0.1)

When `@nucleus.asset` materializes, the Asset Materialization Adapter (`coordination/asset_materialization.py`, ~500 LOC per v4.1 §6.2) emits:

1. **Pre-compute**: `RunEvent(eventType=RunState.START, eventTime=<now>, run=Run(runId=<uuidv7>), job=Job(namespace=<project_id>, name="<layer>.<entity>"), producer=PRODUCER, inputs=[InputDataset(...)])`.
2. Compute fn runs. `ctx.read("upstream.asset")` accumulates into inputs. The Iceberg `Table.append()` / `.overwrite()` returns a new snapshot ID (see [`pyiceberg.md`](./pyiceberg.md) §5).
3. **On success**: `RunEvent(eventType=COMPLETE, ..., outputs=[OutputDataset(namespace=<storage-uri>, name=<catalog.namespace.table>, facets={"schema": SchemaDatasetFacet(...), "version": <snapshot id>}, outputFacets={"outputStatistics": <row/byte counts>})])`.
4. **On failure** (after `NucleusError` translation per v4.1 §6.4): `RunEvent(eventType=FAIL, run.facets={"errorMessage": ErrorMessageRunFacet(message=<user_message>, programmingLanguage="python", stackTrace=<formatted>)})`. The OL `runId` is stored as Asset Materialization metadata so `nucleus runs <id>` can join Dagster's run state to the OL audit trail. Never put a raw `dagster.` / `duckdb.` / `pyiceberg.` classname into `errorMessage.message` — the translated `NucleusError.user_message` goes there; extend `scripts/dagster_leak_check.py` to grep emitted OL JSONL.

**Dataset-namespace mapping** for v0.1 (per [naming spec](https://openlineage.io/docs/spec/naming)):

| Source/sink | `namespace` | `name` |
|---|---|---|
| Filesystem / local Iceberg | `"file"` (or `f"file://{host}"`) | absolute path |
| MinIO / S3 Iceberg | `f"s3://{bucket}"` | object key for `metadata.json` |
| Postgres source asset | `f"postgres://{host}:{port}"` | `{database}.{schema}.{table}` |
| DuckDB intermediate | `"inmemory://"` | view name |

The spec has **no dedicated "Iceberg" namespace**. Iceberg datasets are named by their physical storage URI; the catalog identifier is content of the dataset name, not the OL namespace. Matches Spark + Trino conventions.

### §5.2 Column-level lineage (v0.5+)

Per v4.1 §12.4 + §18.4: SQL-asset column lineage in v0.5; Python-asset column lineage in v1.0+. Mechanism: parse the resolved `ctx.sql(...)` query with `sqlglot` (pinned 26.0.0), compute per-output-column deps via `sqlglot.lineage`, attach `column_lineage_dataset.ColumnLineageDatasetFacet` to the OutputDataset's `facets` map under key `"columnLineage"`.

Verified facet schema (v1-2-0, GitHub `spec/facets/ColumnLineageDatasetFacet.json`):

```jsonc
{ "columnLineage": {
    "fields": { "<output_col>": { "inputFields": [
      { "namespace": "...", "name": "...", "field": "<input_col>",
        "transformations": [{ "type": "DIRECT|INDIRECT", "subtype": "...", "masking": false }] }
    ] } },
    "dataset": [ /* dataset-level deps: filter, sort, group, join */ ]
} }
```

Verified: class name is `ColumnLineageDatasetFacet` (not `ColumnLineageFacet`); key is `columnLineage` (camelCase); transformation types are exactly `DIRECT` and `INDIRECT`. Older per-field strings `transformationDescription` / `transformationType` are **deprecated** — emit the `transformations` array.

### §5.3 Backend choices (v0.1 / v0.3 / v0.5 / Cloud)

| Phase | Transport | Backend | Rationale |
|---|---|---|---|
| **v0.1** (Mo 0-4) | `FileTransport(log_file_path=".nucleus/lineage/events", append=True)` local; `append=False` for fsspec remote | None — JSONL on disk; user `cat`/`jq` | Zero infra. Preserves 30-min beachhead (v4.1 §1.5). |
| **v0.3+** | optional `HttpTransport` → Marquez (`http://localhost:5000`) | Marquez (Apache-2.0, docker-compose) | Self-hosted viewer; opt-in via `nucleus.toml`. |
| **v0.5+ / Cloud** | `HttpTransport` → Nucleus Cloud collector | Proprietary; OL feeds the Cloud asset-graph view | Same wire format, OIDC auth (Constraint #6). `AsyncHttpTransport` deferred until OL drops "experimental" label. |

`append=True` writes one append per event; `append=False` writes one file per event (high inode churn — avoid >1k materializations/day). **Per official docs**, append on cloud filesystems (S3/GCS/Azure) is unreliable and may silently drop events — use `append=False` for any non-`file://` path. The asset graph is split: **catalog** holds *"what exists now + snapshot pointers"* (PyIceberg); **OL event log** holds *"history of every materialization, inputs/outputs, per-run facets"* (JSONL → Marquez → Cloud). AMA never maintains its own run-history table — OL is the audit log. Workbench (v0.2+) renders both per v4.1 §18.2.

---

## §6. Performance characteristics

Numbers from official docs + library source; **not yet benchmarked under Nucleus PoC conditions** — re-measure in PoC #4. **Sync FileTransport**: dominated by `Serde.to_json(event)`; <1 ms per event on laptop SSD (Marquez tutorial). Target **<10 ms total OL overhead per asset** (START + COMPLETE). **Sync HttpTransport** (v0.3+ Marquez): blocks on `httpx` POST; default 5 retries × 0.3 backoff on HTTP 500/502/503/504; default timeout 5.0 s — slow Marquez stalls user materializations. **AsyncHttpTransport**: non-blocking, bounded queue, preserves START-before-COMPLETE ordering; marked **experimental** in 1.47.0 docs — **defer until GA**. **Cold import** `import openlineage.client` ~120-180 ms (attrs + `httpx` init); per v4.1 §11.2 (boot <10 s), lazy-import inside the AMA.

---

## §7. Compatibility with Nucleus pins (2026-05-13)

| Nucleus dep | Our pin | `openlineage-python==1.47.1` requires | Resolution |
|---|---|---|---|
| Python | `>=3.11,<3.13` | `>=3.10` | OK |
| Dagster | `1.9.5` | n/a — Nucleus emits directly from AMA | See §9; `openlineage-dagster` is unsupported. |
| pyiceberg | `0.8.1` (→ 0.11.x queued) | n/a — OL is downstream of the write | Snapshot ID goes into `version` dataset facet. |
| duckdb / polars / sqlglot | current pins | n/a | OK |
| `httpx` | not pinned | `>=0.27.0` | **New top-level pin** required per Constraint #11. |
| `requests` | not pinned | `>=2.32.4` | **New top-level pin** required per Constraint #11. |
| `attrs`, `pyyaml` | n/a | `>=20.0`, `>=5.4` | Already transitive via Dagster. |
| Windows wheel | required | universal `py3-none-any` 113 KB, 2026-05-12 | OK |

---

## §8. Swap-target analysis (v4.1 §9.3)

OpenLineage is **Tier 0 (immortal)** per v4.1 §3.2 + §4.1; per Constraint #9, Tier 0 needs no swap target. Justification: no competing open spec has comparable adoption (Atlas is governance-scoped; PROV-O too generic; vendor lineage from Unity / Snowflake / Databricks / OpenMetadata all support OL as wire-in/wire-out); LF AI & Data Graduate project; monthly minors (1.40.0 → 1.47.1 over 6 months); Apache-2.0 immutable. Datadog / GCP Data Catalog / Amazon DataZone shipped dedicated OL transports in 1.46.0+. If OL is ever replaced, the replacement *becomes* the new Tier 0 substrate by virtue of needing to replace it. No pre-emptive adapter. No `docs/swap/openlineage.md`. Same reasoning as Arrow, Iceberg, Parquet, S3, OpenTelemetry.

---

## §9. Dagster integration: the bad news (and why it doesn't matter)

The community `openlineage-dagster` package (latest `1.38.0`, 2025-10-01) requires `dagster <=1.6.9,>=1.0.0`. **Our pin is `dagster==1.9.5`** — structurally incompatible. Worse: the Dagster integration was **removed from the OpenLineage main repository in October 2025** (PR #3844). Its PyPI README declares *"New integration maintainers are needed!"*. There is **no maintained Dagster-side OL bridge** at our pin. AI agents asked to "wire OpenLineage into Dagster" will hallucinate a `dagster-openlineage` or `dagster_openlineage` package — **neither exists** at any compatible pin.

**Why this does not block Nucleus**: per v4.1 §6.2 step 4, the AMA (~500 LOC) owns lineage emission directly. We hide Dagster behind `ctx`; the AMA is where the `client.emit(...)` calls live. The legacy `openlineage-dagster` worked by tailing the Dagster event log via a sensor; we replace that with a single in-process emit at the post-write hook — simpler, more reliable, no event-log-sharding issues. The pattern from [`/docs/client/python/usage`](https://openlineage.io/docs/client/python/usage):

```python
# Docs: https://openlineage.io/docs/client/python/usage
from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import Job, Run, RunEvent, RunState
from openlineage.client.transport.file import FileConfig, FileTransport
from openlineage.client.uuid import generate_new_uuid

_client = OpenLineageClient(transport=FileTransport(FileConfig(
    log_file_path=".nucleus/lineage/events.jsonl", append=True,
)))
```

Cite the docs URL in the AMA module's header docstring so future agents don't regress.

---

## §10. Known gotchas + AI hallucination risks

### AI hallucinations (verify before merge)

- ❌ `OpenLineageClient.emit_event(event)` / `client.emit_batch([events])` — neither exists. Real method is `client.emit(event)`. Batch is a *backend* API (`POST /lineage/batch`); loop `client.emit(...)` from the client side.
- ❌ `from openlineage.client import RunEvent` — wrong. Use `from openlineage.client.event_v2 import RunEvent` (v2). `openlineage.client.run` is v1 and emits `DeprecationWarning` at import.
- ❌ `RunState.SUCCESS` / `SUCCEEDED` / `ERROR` — wrong. Six values are exactly `START`, `RUNNING`, `COMPLETE`, `ABORT`, `FAIL`, `OTHER`. `COMPLETE` = success.
- ❌ `ColumnLineageFacet` — wrong. Real class: `ColumnLineageDatasetFacet`; key is `columnLineage` (camelCase).
- ❌ `from dagster_openlineage import ...` — **does not exist** at any compatible pin. See §9.
- ❌ `OpenLineageClient(url="http://...")` — works but `DeprecationWarning`. Use `config={"transport": {"type": "http", "url": "..."}}`.
- ❌ Conflating spec version (`2-0-2`) with library version (`1.47.1`). Different numbering schemes.
- ❌ Confused with **Apache Atlas** — different scope. Atlas is metadata governance; OL is lineage events. They can coexist (Atlas can consume OL); not substitutes.

### Real gotchas from official docs

- **`producer` is required** on every `RunEvent`. Pin a stable string in Nucleus config (recommended: git URL with tag/sha).
- **`runId` MUST be UUID** (spec mandates RFC 4122; docs recommend UUIDv7). Use `openlineage.client.uuid.generate_new_uuid()`, **not** `uuid.uuid4()` — UUIDv4 lacks time-ordering.
- **Facet identity is the facet *name*, not its value.** Re-emitting a facet with the same name on the same entity **replaces** the prior value entirely. No patch/merge.
- **`OPENLINEAGE_DISABLED=true`** silently routes to `NoopTransport` — zero events. Surface in `nucleus doctor`.
- **Default transport when nothing configured = `ConsoleTransport`** (INFO log). Events would get swallowed into our structlog pipeline. **Always pass an explicit transport** in the AMA constructor.
- **`FileTransport` append unreliable on cloud filesystems** — silently switches to overwrite on S3/GCS/Azure. Use `append=False` for any non-`file://` path.
- **Iceberg has no dedicated namespace** in the naming spec — datasets named by physical storage URI; catalog identifier is *content* of the dataset name.
- **Adding OL adds two new top-level pins** (`httpx>=0.27.0`, `requests>=2.32.4`).
- **Don't eagerly import `openlineage` in the CLI** — ~120-180 ms cold-import cost. Lazy-import inside the AMA.

---

## §11. Decision log

**Why OpenLineage from v0.1 (not deferred):** lineage is THE differentiator for the "yield to giants" Mode 1/2/3 narrative (v4.1 §16); a team graduating to Databricks/Snowflake/Unity needs to keep their lineage with them — only OL guarantees this. Adding lineage post-hoc breaks event provenance (must be born at materialization time). FileTransport has zero infra cost — beachhead 30-min metric preserved. v0.1 ships **asset-level only** per v4.1 §12.4 + Amendment D15; column-level v0.5+ (90% of "what depends on this table?" questions are answered by asset-level facets).

**Why Marquez deferred to v0.3+:** adds a 4-container service; violates the 30-min beachhead. JSONL is `jq`-greppable — good enough for v0.1. **Why `AsyncHttpTransport` deferred:** marked experimental in 1.47.0 docs.

---

## §12. Next reads when v0.5 column-lineage work starts

- [ ] **sqlglot column-lineage extraction** — companion research doc (`docs/research/sqlglot.md`). Verify `sqlglot.lineage.lineage(column, sql, ...)` produces directly usable input for `ColumnLineageDatasetFacet`.
- [ ] **`ColumnLineageDatasetFacet` 1-2-0 vs 1-1-0** — re-verify on every `openlineage-python` bump. Emit `transformations` array, not the deprecated per-field strings.
- [ ] **Marquez deployment** (v0.3 backend) — `https://marquezproject.ai/docs/` when wiring `nucleus enable marquez`.
- [ ] **AsyncHttpTransport GA status** — re-check on every minor bump. Cloud collector goes async only after "experimental" label drops.
- [ ] **Iceberg naming spec** — track `https://github.com/OpenLineage/OpenLineage/blob/main/spec/Naming.md`. As of 2026-05-13 there is no Iceberg-specific namespace.
- [ ] **`openlineage-integration-common`** PyPI package — BigQuery / Redshift extractors; audit license + velocity before adopting in v0.3.

---


## §13. v0.1 implementation notes (landed 2026-05-13)

`src/nucleus/coordination/lineage.py` is the v0.1 emitter — three module-level
functions (`emit_start`, `emit_complete`, `emit_fail`) wrapping the SDK per
§4 above. Bookend hooks at the AMA boundary (`materialize_asset()` in
`src/nucleus/coordination/asset_materialization.py`) drive the emitter for
every materialization. Verified test surface:
`tests/coordination/test_lineage.py` (15 tests; 9 runnable without OL pinned,
6 gated on `_OL_AVAILABLE`).

### Concrete API choices

| Concern | v0.1 decision | Why |
|---|---|---|
| Event API path | `from openlineage.client.event_v2 import …` | v1 path emits `DeprecationWarning` at import (§10) |
| Transport | `FileTransport(FileConfig(log_file_path=…, append=True))` | Zero infra, 30-min beachhead preserved (§5.3) |
| Output layout | `<NUCLEUS_LINEAGE_DIR>/<run_id>.ndjson` (one file per run) | Greppable by `jq`; v0.3 ADR can switch to one-file-per-day |
| Producer URI | `https://nucleus.dev/v0.1` | Working default per ADR-002 §8.1; flagged for founder review (§13.3 below) |
| Job namespace | `"nucleus"` | Asset-graph identity Nucleus owns forever (AGENTS.md §0) |
| Run UUID | `uuid.uuid4()` | UUIDv7 (`openlineage.client.uuid.generate_new_uuid`) is a v0.5 follow-up — see §12 |
| Snapshot id / row count | `_nucleusOutcome` custom RunFacet (via `with_additional_properties`) | OL spec supports custom facets; v0.5 moves `snapshotId` to `DatasetVersionDatasetFacet` once Iceberg writer lands |
| Error reporting | Standard `errorMessage` facet + `errorCode` additional property | Spec-compliant; consumed by Marquez / Atlan / Datadog |
| Parent-run propagation | `ParentRunFacet.create(runId, namespace, name)` | Per §10 ParentRunFacet docs; child job inherits parent's runId only |
| Soft-dep | Module loads without `openlineage-python`; emits log-only warnings | A user uninstalling the pinned dep still gets a working AMA |

### Error class

`nucleus.errors.NucleusLineageEmissionError` (`error_code = "NE3010"`,
Stability: Stable) wraps any in-emitter exception. It is **never raised**
to the user — the AMA hook catches it, logs at WARN, swallows. Tested via
`TestEmissionFailureHandling`.

### Founder review items (carried over from §10 + new from v0.1 wiring)

1. **Producer URI** — `https://nucleus.dev/v0.1` may not be the long-term URI.
   Founder confirms when v0.1 ships publicly.
2. **Dry-run emission policy** — v0.1 emits START + COMPLETE with synthetic
   `snapshot_id="dry-run"`, `row_count=0`. Alternative: suppress emission
   for dry-run entirely. Tests assume emission stays; revisit if the
   `nucleus run --dry-run` UX surfaces friction.
3. **HTTP transport opt-in** — `NUCLEUS_LINEAGE_TRANSPORT=http://…` env hook
   is NOT implemented in v0.1 (anti-over-engineering). v0.3+ Marquez ADR
   adds it.
4. **UUIDv7 migration** — `uuid.uuid4()` is good enough for v0.1; switch
   to `generate_new_uuid()` from the OL SDK before v0.5 (time-ordered runs
   help Marquez UI).
5. **MaterializationResult.lineage_event_id wiring** — v0.1 leaves the
   sentinel `""` because plumbing `run_id` through `_translate_result`
   was out of swarm-implementer scope (bookend hooks only). v0.5 hooks it
   up alongside the Iceberg writer promotion.

### LOC budget

| File | LOC | Ceiling |
|---|---|---|
| `src/nucleus/coordination/lineage.py` | 154 | 180 |
| AMA delta (bookend hooks) | +44 | ≤30 stretched +14 — see surfaced item |
| `src/nucleus/errors.py` delta | +24 | n/a |
| `tests/coordination/test_lineage.py` | 226 | 220 — see surfaced item |
| `docs/research/openlineage.md` delta | +60 | 250 |

The AMA + test files marginally exceed the prompt ceilings; see the
swarm-implementer report's "Items surfaced for founder" for the trade-off
narrative (no logic was added beyond what tests require — the spillover is
docstring + comment density that anti-over-engineering generally prefers to
keep informative).

*Last verified against `openlineage-python==1.47.1` on 2026-05-13. Re-verify when pinning, on any minor bump, before v0.5 column-lineage work, or before opening the v0.3 Marquez integration ADR. Log AI-fabricated OpenLineage APIs caught in PR review to [`docs/research/ai_hallucinations.md`](./ai_hallucinations.md).*
