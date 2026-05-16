# Research: dlt (data load tool)

> **Component status in Nucleus**: **IMPLEMENTED — Stage 1 (per ADR-014, 2026-05-13).** `dlt[sql_database,pyiceberg]==1.26.0` is pinned in `pyproject.toml`. Stage 1 wraps the `sql_database` verified source for Postgres → Iceberg. dlt extends the v0.3 connector surface when 100+ source breadth becomes the bottleneck (§5.5.2, §18.3).
> **Pin**: `dlt[sql_database,pyiceberg]==1.26.0` (released **2026-04-28**, verified on PyPI 2026-05-13). **Pinned in `pyproject.toml` (Stage 1, 2026-05-13).**
> **License**: **Apache-2.0**  •  **JVM-free**: **YES** — pure Python; Iceberg extra adds Rust (`pyiceberg-core`), not Java. Hard Constraint #1 satisfied.
> **Research date**: 2026-05-13
> **Used in**: nowhere (yet). Pre-research artifact for the v0.3 ADR.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening the v0.3 integration ADR. dlt is the canonical **wrap-not-build** case (Pillar #2) — we will never write 100+ extractors ourselves.

---

## §1. At a glance

- **License**: Apache-2.0  •  **Maintainer**: dltHub Inc. (Marcin Rudolf, Adrian Brudaru et al.)  •  **GitHub**: https://github.com/dlt-hub/dlt
- **Position**: L2 Coordination — **optional**, surfaces as `@nucleus.source(engine="dlt")` in v0.3. Hidden behind `ctx`; users never `import dlt`.
- **Latest stable**: 1.26.0 (2026-04-28). `Development Status :: 5 - Production/Stable`. 8000+ source catalogue in their workspace.

**What it is**: a **pure-Python ELT library** — `dlt.source` / `dlt.resource` / `dlt.pipeline.run(...)` — that handles extract → normalize → load against pluggable destinations. Infers schemas, normalizes nested data, supports incremental loading + schema evolution + merge strategies (delete-insert / upsert / SCD2 / insert-only), and ships an **Iceberg destination** that calls `pyiceberg` under the hood. No daemon, no JVM, no scheduler — composable inside Dagster (`@dlt_assets`).

---

## §2. What dlt is, in Nucleus terms

A dlt `@dlt.source` maps to our **source asset** (the grouping). A `@dlt.resource` is the per-table unit. A `pipeline.run(...)` is the materialization action — in Nucleus, owned by the Asset Materialization Adapter, not user code.

| dlt term | Nucleus term | Surface |
|---|---|---|
| `@dlt.source` | **source asset** (grouping) | `@nucleus.source(engine="dlt")` |
| `@dlt.resource` | **source asset** (per-table unit) | yielded from the source fn |
| `dlt.pipeline` | runner config — **never** public | internal to the adapter |
| `pipeline.run` | **materialization** | called by AMA |
| destination | **catalog + FileIO** | already configured by Nucleus |
| pipeline state | adapter responsibility | see §4.3 ADR decision |

The hard question is **state location**: dlt writes a `_dlt_pipeline_state` table at the destination *and* keeps a working dir at `~/.dlt/pipelines/<name>/`. Reconciling that with Nucleus's single-source-of-truth principle is the v0.3 ADR's central decision (§4.3).

---

## §3. Official documentation URLs

Every fact cites this set. Verified by `WebFetch` 2026-05-13.

- Main / Pipeline / Source / Resource: https://dlthub.com/docs/intro • https://dlthub.com/docs/general-usage/pipeline • https://dlthub.com/docs/general-usage/source • https://dlthub.com/docs/general-usage/resource
- Destinations (general) + **Iceberg**: https://dlthub.com/docs/general-usage/destination • https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
- Incremental + cursor: https://dlthub.com/docs/general-usage/incremental-loading • https://dlthub.com/docs/general-usage/incremental/cursor
- State: https://dlthub.com/docs/general-usage/state
- Schema contracts + merge: https://dlthub.com/docs/general-usage/schema-contracts • https://dlthub.com/docs/general-usage/merge-loading
- Dagster (dlt-side / Dagster-side, authoritative): https://dlthub.com/docs/walkthroughs/deploy-a-pipeline/deploy-with-dagster • https://docs.dagster.io/integrations/libraries/dlt
- GitHub / Releases / PyPI: https://github.com/dlt-hub/dlt • https://github.com/dlt-hub/dlt/releases • https://pypi.org/project/dlt/

**404 gaps on 2026-05-13** (flag for AI agents):

- `https://dlthub.com/docs/api_reference/dlt` — dlt has **no auto-generated API reference**. Cite tutorial URLs only.
- `https://dlthub.com/docs/reference/exceptions` — no central exceptions reference. Read `dlt/extract/exceptions.py` + `dlt/pipeline/exceptions.py` in source.

---

## §4. APIs Nucleus will wrap

Symbols the v0.3 adapter (`coordination/dlt_source_adapter.py`, target ≤500 LOC) calls.

| Symbol | Signature (1.26.0) | Use |
|---|---|---|
| `dlt.pipeline` | `pipeline(pipeline_name, destination, dataset_name=None, pipelines_dir=None, dev_mode=False, refresh=None, progress=None)` | One pipeline per source asset; `pipeline_name=f"{project_id}__{source_asset_name}"`, `pipelines_dir=.nucleus/state/dlt/`. |
| `@dlt.source` | `source(name=None, section=None, max_table_nesting=None, schema_contract=None)` | What `@nucleus.source(engine="dlt")` expands to. **`@dlt_assets` requires a source**; bare resources don't work in Dagster. |
| `@dlt.resource` | `resource(name=None, table_name=None, write_disposition="append", primary_key=None, merge_key=None, columns=None, schema_contract=None, table_format=None)` | Per-table unit. `write_disposition` accepts `str` or `{"disposition":"merge","strategy":"upsert"}` dict. |
| `pipeline.run` | `run(data, *, destination=None, dataset_name=None, table_name=None, write_disposition=None, schema_contract=None, table_format=None, refresh=None) -> LoadInfo` | One call per source-asset materialization. `LoadInfo` → `AssetMaterialization` metadata. |
| `dlt.sources.incremental` | `incremental(cursor_path, initial_value=None, last_value_func=max, primary_key=None, allow_external_schedulers=False)` | Maps to `@nucleus.asset(materialization="incremental", incremental_key=...)`. |
| `dlt.current.*` | `resource_state()`, `source_state()`, `pipeline()`, `interval()` (new 1.26.0) | State + active-pipeline access **inside** a source/resource fn. |
| `iceberg_adapter` | `iceberg_adapter(resource, partition=[...], table_properties={...})` from `dlt.destinations.adapters` | Partition spec + per-table Iceberg properties. |
| `iceberg_partition.{identity,year,month,day,hour,bucket,truncate}` | per Iceberg spec | Partition transforms. |
| `get_iceberg_tables(pipeline)` | `from dlt.common.libs.pyiceberg import get_iceberg_tables` → `dict[str, pyiceberg.table.Table]` | **Hand-off boundary**: dlt commits, Nucleus reads post-commit `Table` here to record snapshot metadata. |

**Iceberg activation**: not a standalone destination. Set `destination="filesystem"` + `table_format="iceberg"`. dlt calls `pyiceberg.catalog.load_catalog(...)` with our catalog config — we do not double-construct a catalog.

---

## §5. Integration points with Nucleus

### §5.1 dlt sources as Nucleus source assets (v0.3 design)

Per `docs/specs/nucleus_architecture_v4.1.md` §5.5.2 + §6.3:

1. User writes `@nucleus.source(engine="dlt")` returning a dlt-style source fn (yielding resources).
2. Adapter constructs `dlt.pipeline(...)` keyed by `(project_id, source_asset_name)`; `pipelines_dir = .nucleus/state/dlt/` (project-local, not `~/.dlt`).
3. Adapter wraps the source in `@dlt_assets(dlt_source=..., dlt_pipeline=...)` (from `dagster-dlt`); registers in Nucleus's `Definitions`.
4. Decorated fn does `yield from dlt.run(context=context)` — Dagster receives one `AssetMaterialization` per resource; we layer snapshot id + doc URL on top.
5. Lineage: dlt source → Iceberg table(s) → downstream `@nucleus.asset`. Asset-level in v0.3; column-level v0.5+.

```python
from dagster_dlt import DagsterDltResource, dlt_assets   # NEEDS VERIFICATION at v0.3 time:
                                                          # was previously dagster-embedded-elt; packages have churned
```

Dagster's docs supersede dlt's on the integration: https://docs.dagster.io/integrations/libraries/dlt. Pin `dagster-dlt` alongside `dagster` in the v0.3 PR; major bump of either = fresh ADR.

### §5.2 Iceberg destination

- Writer is **PyIceberg**. Same catalog backends as us — REST, SQL, SQLite-ephemeral. No Lakekeeper / Polaris-specific gaps documented.
- **Filesystem-only host**: Iceberg sits on the `filesystem` destination; `bucket_url` is our MinIO / S3 / local path.
- **Atomicity per `pipeline.run()`**: one snapshot per table-write. Cross-resource atomicity is **not** provided — same constraint as raw PyIceberg (ADR-001). Sequence + document the inconsistency window. <!-- banned-term: none -->
- **Azure `az://` scheme NOT supported** on the Iceberg path (PyIceberg limitation); use `abfss://`.
- **Partition evolution NOT supported** on existing tables — falls back to drop + recreate.
- **Schema evolution + `upsert` merge incompatible at `pyiceberg==0.10.0`** (documented dlt limitation).
- **Upsert chunked at 1000 rows** until `pyiceberg > 0.9.1`.

### §5.3 Incremental loading + state — THE CRITICAL DESIGN QUESTION

dlt defaults:

- Local: `~/.dlt/pipelines/<pipeline_name>/state.json` (load packages, schemas, traces).
- Destination: `_dlt_pipeline_state` table written alongside the data, keyed by `(pipeline_name, destination, dataset_name)`.
- Sync at start of `pipeline.run()`. Disable with `restore_from_destination=false`.

Three options for Nucleus (the v0.3 ADR picks one):

| Option | Pros | Cons |
|---|---|---|
| **A. dlt owns state** | Simplest; matches dlt design; full feature coverage | Two stores; `nucleus state` CLI must shell out |
| **B. Nucleus catalog owns state** | Single source of truth | Requires injecting `dlt.common.state` — unsupported; fragile across upgrades |
| **C. Hybrid mirror** | Catalog records last-cursor for `ctx` API | Drift risk; reconciliation cost |

**Provisional v0.3 stance**: **A**, with `pipelines_dir=.nucleus/state/dlt/` (project-local) and `restore_from_destination=true`. Surface the per-resource cursor via `nucleus runs <id> --verbose` by reading `dlt.current.resource_state()` post-run and storing as Asset Materialization metadata. **Decision deferred to ADR.**

### §5.4 Error translation contract (PoC #1 implications)

dlt has no central exceptions reference. From source + tutorial docs:

| dlt exception | Raised when | Likely `NucleusError` target |
|---|---|---|
| `PipelineStepFailed` | Any step fails (`extract`/`normalize`/`load`/`sync`); step in `.step`, inner cause in `__context__` | **Unwrap `__context__`, re-translate**; fallback `NucleusIngestionError` |
| `DataValidationError` | Schema contract violation in `freeze` mode | `NucleusSchemaError` (preserve `schema_name`/`table_name`/`column_name`/`contract_mode`) |
| `CannotRestorePipelineException` | `dlt.attach()` fails | `NucleusInternalError` (we don't expose `dlt.attach` to users) |
| `ConfigFieldMissingException` | Required config/secret missing | `NucleusConfigError` |
| `DatabaseUndefinedRelation` | Source DB table missing | `NucleusAssetNotFound` |
| `JoinSchedulerError` (1.26.0+) | Incremental cursor coercion fails | `NucleusSchemaError` |
| `ExternalSchedulerNotAvailable` (1.26.0+) | Missing interval | `NucleusConfigError` |

**Verification mandatory at v0.3**: trigger each in a fixture (mirror PoC #1's 50-scenario harness). Some entries above are **unverified**. Log drift to `docs/internal/research/ai_hallucinations.md`.

Documented pattern (verified at https://dlthub.com/docs/general-usage/schema-contracts) — note the **two-level** `__context__` walk for normalize-step errors:

```python
try:
    pipeline.run()
except PipelineStepFailed as pip_ex:
    if pip_ex.step == "normalize":
        if isinstance(pip_ex.__context__.__context__, DataValidationError): ...
    if pip_ex.step == "extract":
        if isinstance(pip_ex.__context__, DataValidationError): ...
```

AI agents will fabricate a one-level walk — catch in review.

---

## §6. Performance characteristics

Numbers from docs only; **no Nucleus benchmark yet** — repeat under PoC v0.3 conditions before quoting to users.

- **Cold start**: `import dlt` ≈ 200-400 ms vs `import psycopg` <50 ms. Relevant to PoC #4 (`nucleus up <10s`) — **never auto-import dlt in CLI startup**; lazy-import inside the adapter.
- **Memory**: normalize step writes per-load-package Parquet to `pipelines_dir`. 1M-row Postgres table ≈ 100-500 MB temp footprint. Tune via `recommended_file_size` capability override.
- **Throughput**: SQL source uses SQLAlchemy + PyArrow batch path. dltHub blog cites 50-200k rows/sec on a single laptop core for Postgres → DuckDB (**NEEDS VERIFICATION** — re-fetch at v0.3 time). Iceberg destination adds 10-50% Parquet-write + commit overhead vs that baseline.
- **Parallelism**: extracts parallelize within a source (resource decomposition) and across sources via Dagster's executor. Accept Dagster's model; don't surface dlt's own concurrency knobs.

---

## §7. Compatibility with Nucleus pins (2026-05-13)

The critical section. dlt's `pyiceberg` extra has a **hard floor that conflicts with our current pin**.

| Nucleus dep | Our pin | dlt 1.26.0 (Iceberg path) requires | Conflict? | Resolution |
|---|---|---|---|---|
| `pyiceberg` | `0.8.1` | **`>=0.9.1`** (`dlt[pyiceberg]`) | **YES — BLOCKING** | Land queued PyIceberg `0.8.1 → 0.9.x` upgrade **before** v0.3 (ADR already on roadmap — `pyiceberg.md` §2). |
| `pyarrow` | `18.1.0` | `>=16.0.0` | No | OK |
| `polars` | `1.18.0` | not required | No | Polars wraps dlt outputs, not the reverse. |
| `duckdb` | `1.1.3` | `>=0.9` (`dlt[duckdb]`) | No | OK. `dlt[ducklake]` (out of v0.3 scope) needs `>=1.2.0`. |
| `sqlalchemy` | `2.0.36` | `>=1.4` (Iceberg docs recommend `>=2.0.18`) | No | OK |
| `psycopg[binary]` | `3.2.3` | dlt's `postgres` destination uses `psycopg2-binary` | No | **Skip `dlt[postgres]`** — we never load *into* Postgres. |
| `sqlglot` | `26.0.0` | `>=25.4.0` | No | OK |
| Python | `>=3.11,<3.13` | `<3.15,>=3.9.2` | No | OK |
| `dagster` | `1.9.5` | `dagster-dlt` (separate package) | No | Pin `dagster-dlt` alongside `dagster` in v0.3 PR. |
| Windows wheels | required | published | No | OK |

**ADR sequencing**: (1) PyIceberg upgrade `0.8.1 → 0.9.x` ADR ships first (already required for Iceberg spec v3 readiness regardless); (2) then dlt integration ADR opens. Without step 1, `pip install dlt[pyiceberg]` fails resolution. This is the single biggest concrete dependency on the roadmap that v0.3 reveals.

---

## §8. Swap-target analysis (v4.1 §9.3)

If dlt becomes unviable (license pivot, dltHub fold, perf regression >2x, deprecation):

| Candidate | License | Cost to swap | Notes |
|---|---|---|---|
| **Singer** (tap/target) | per-tap, mixed (some AGPL-3.0) | High — ~2k LOC adapter; different protocol | Older ecosystem; alive via Meltano. License risk on proprietary forks. |
| **Sling** (`sling-cli`) | MIT | Medium — Go subprocess; 500-1k LOC | Single-binary, fast, JVM-free. Smaller connector breadth. |
| **Custom Python** (top-10) | — | Low for 10 sources (~3-5k LOC); rises super-linearly | Already our v0.1 default via `ctx.copy_from`. Cap at 10-15; not 100+. |
| **Meltano** | MIT | High — embeds tap-discovery in its own scheduler | **Reject** — conflicts with Dagster ownership (Constraint #3). |

**Verdict**: dlt is the only candidate giving 100+ connectors + native Iceberg + no JVM + permissive license + active maintenance. Risk = low. Keep `ctx.copy_from` alive in CI via `nucleus.connectors.SourceEngine` Protocol (CI implementations: `DltSourceEngine` default, `CopyFromSourceEngine` baseline).

---

## §9. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge)

- ❌ `dlt.write_to_iceberg(...)` — does not exist. Correct: `pipeline.run(source, table_format="iceberg")` on `filesystem` destination.
- ❌ `pipeline.commit_atomic([resource_a, resource_b])` — does not exist. No cross-resource atomic commit.
- ❌ `@dlt.iceberg_resource(...)` — fabricated. Use `@dlt.resource(table_format="iceberg")`.
- ❌ `from dlt.exceptions import IcebergCommitError` — fabricated. Iceberg commit errors propagate as `pyiceberg.exceptions.CommitFailedException` wrapped in `PipelineStepFailed`; translate at PyIceberg level (`pyiceberg.md` §6).
- ❌ `pipeline.state["resource_x"]["last_value"]` — wrong shape. **Inside the resource fn**: `dlt.current.resource_state().setdefault("last_value", ...)`. Outside, the `pipeline.state` dict has internal/unstable key schema.
- ❌ `from dagster_embedded_elt.dlt import dlt_assets` — legacy path. Current per dlt walkthrough: `from dagster_dlt import dlt_assets, DagsterDltResource`. **Verify at v0.3 ADR** — packages have churned.
- ❌ Citing `/docs/api_reference/dlt` or `/docs/reference/exceptions` — both 404 (2026-05-13). Cite tutorial URLs.
- ❌ `destination="iceberg"` — string does not resolve. Iceberg = `destination="filesystem"` + `table_format="iceberg"`.

### Real gotchas from official docs

- **dlt state is JSON-only.** Standard types + `DateTime` / `Decimal` / `bytes` / `UUID`. Polars frames / Arrow tables in state fail at serialization — surface as `NucleusInternalError`.
- **`pipeline_name` is the state key.** Two source assets sharing one overwrite each other. Adapter MUST namespace `pipeline_name = f"{project_id}__{source_asset_name}"` and assert uniqueness.
- **`loader_file_format` ignored when `table_format="iceberg"`** — always Parquet.
- **`@dlt_assets` requires a source.** Adapter wraps single resources in a synthetic source.
- **State sync at `pipeline.run()` start** reads `_dlt_pipeline_state` — adds 100-500 ms per materialization. Disable in tests with `restore_from_destination=false`.
- **`pipeline.run()` is multi-snapshot** — each table commits independently; no atomic group.
- **1.26.0 breaking**: `allow_external_schedulers=True` raises `JoinSchedulerError` on un-coercible cursor values (previously silent warn). Wrapper catches + translates.
- **Two-level `PipelineStepFailed.__context__` walk** for normalize errors (§5.4). One-level loses the cause.

---

## §10. Decision log

**Why dlt enters at v0.3, not earlier, not later:**

- **v0.1**: `ctx.copy_from` (~200 LOC, Postgres/MySQL/SQLite/CSV/Parquet/JSON) covers the 30-min beachhead (`docs/specs/nucleus_architecture_v4.1.md` §1.5, §5.5.1). Adding dlt early = +30 MB deps + 200-400 ms boot for zero beachhead-metric improvement. **Defer.**
- **v0.3**: bottleneck shifts from "first table in 30 min" to "connect to the 50 SaaS tools we already pay for." dlt's 8000+ source catalogue + REST API auto-paginator is the lowest-LOC path. **Now.**
- **v0.5+**: AI-assisted source authoring becomes feasible — dlt's source model is small, declarative, explicitly LLM-native (`llm-native-workflow` doc). **Capitalize.**
- **Never**: build our own 100-connector framework. Constraint #4 / Pillar #2 violation.

Integration ADR: `docs/decisions/ADR-NNN-dlt-v03-connectors.md`.

---

## §11. Next reads when v0.3 work starts

- [ ] **dlt + Dagster deep dive** — confirm `dagster-dlt` package name + `@dlt_assets` API. Authoritative: https://docs.dagster.io/integrations/libraries/dlt. Production examples: https://github.com/dagster-io/dagster-open-platform.
- [ ] **dlt schema contracts vs `@nucleus.check`** — overlap matrix; decide which is user-facing.
- [ ] **dlt destination retries + idempotency** — partial Iceberg commit + network drop behaviour.
- [ ] **dlt deployment patterns** — Airflow / GCF / Lambda envelopes for v0.5 Cloud tier.
- [ ] **Verified-sources licensing** — community sources are mixed-license; audit each we ship by default. https://dlthub.com/workspace.
- [ ] **Verify exceptions in source** — `dlt/extract/exceptions.py` + `dlt/pipeline/exceptions.py`; confirm §5.4 table; trigger each in a fixture; update `ai_hallucinations.md`.
- [ ] **`dlt.current.interval()` (1.26.0+)** — interaction with Nucleus run-id / time-window model.
- [ ] **Benchmark Postgres → Iceberg**: dlt vs `ctx.copy_from` on 1M rows. If dlt overhead >20% with no functional gain, default `ctx.copy_from` for SQL DBs even in v0.3; use dlt only for REST/SaaS long tail.

---

## §12. Useful links

- https://dlthub.com/docs/intro — start here.
- https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg — our integration surface. **Bookmark.**
- https://dlthub.com/docs/general-usage/state — read before the ADR.
- https://dlthub.com/docs/general-usage/schema-contracts — `DataValidationError`.
- https://dlthub.com/docs/walkthroughs/deploy-a-pipeline/deploy-with-dagster — dlt-side Dagster walkthrough.
- https://docs.dagster.io/integrations/libraries/dlt — Dagster-side dlt integration (authoritative for `dagster-dlt`).
- https://github.com/dlt-hub/dlt • https://github.com/dlt-hub/dlt/releases • https://pypi.org/project/dlt/
- https://dlthub.com/community — Slack (team responsive).

---

*Last verified: 2026-05-13 against dlt 1.26.0. Re-verify when opening the v0.3 ADR, before pinning, or on any major bump (1.x → 2.x). Log any AI-fabricated dlt APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*

---

## §13. Postgres-source integration notes — Stage 1 wave (2026-05-13)

> **Supplement** to §1-§12 above. Trigger: founder greenlit a parallel 4-6 month
> ladder to v1.0 (target: enterprise-ready). Stage 1's most v1.0-impactful
> deliverable is **Postgres → Iceberg** — the first DE complaint on any beachhead
> field test will be *"my data is in Postgres, not SQLite."* This section
> documents the Postgres-specific subset of dlt that ADR-014 wraps.
>
> Re-verified against [dlt 1.26.0 on PyPI](https://pypi.org/project/dlt/) on
> 2026-05-13. Apache-2.0; `requires-python = <3.15,>=3.9.2` covers our
> `>=3.11,<3.13` pin. PoC #4 cold-start budget verified: lazy-import dlt inside
> the wrap, never at CLI startup (per §6 above).

### §13.1 What changes vs §10

§10 placed dlt at v0.3+ on a 100+-connector unlock argument. Stage 1 narrows
the trigger: **one production-grade SQL source** (Postgres) lights up the
beachhead for Postgres-shop customers (the dominant pattern in our 5-20-engineer
target). Connector-breadth-at-100+ remains a v0.3+ amplifier, not the Stage 1
justification. ADR-014 is the ratification of this re-prioritization.

### §13.2 The Postgres source flow — `sql_database` verified source

Postgres is read through dlt's [`sql_database`](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database)
verified source — a SQLAlchemy reflection on top of any dialect dlt supports
(documented dialects include Postgres, MySQL, MSSQL, Oracle, MariaDB —
see the [supported-databases table](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database)).
Two callables are relevant:

- [`sql_database(credentials, ..., table_names=[...])`](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration) —
  reflects multiple tables. The Stage 1 wrap calls it with a single-element
  `table_names=[table]` so reflection is bounded (the docs explicitly call out
  that bare `with_resources(...)` reflects the entire schema first — wasteful
  for our one-table CLI).
- [`sql_table(credentials, table=..., schema=..., chunk_size=..., backend=...)`](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration) —
  single-table convenience; equivalent surface for the CLI one-liner.

Both yield a `dlt.Resource`; the wrap binds it to a `dlt.pipeline(destination="filesystem", dataset_name=...)`
with [`table_format="iceberg"`](https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg)
on `pipeline.run()`. Catalog config is delegated to PyIceberg via dlt's
`iceberg_catalog.iceberg_catalog_config` block (per the Iceberg destination
[catalog support](https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg) section).

### §13.3 Backend choice for Stage 1

The [SQL-database configuration page](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration)
documents three backends; Stage 1 picks one and freezes the rest:

| Backend | Stage 1? | Why |
|---|---|---|
| **SQLAlchemy** (default) | **Yes** | Pure Python; runs against our pinned `sqlalchemy==2.0.36`; handles all column types correctly; slower but acceptable for the Stage 1 row-count band. No new runtime dep. |
| `pyarrow` | No (Stage 2) | 20-30× faster on large tables but adds `numpy` + `pandas` to the runtime closure. Defer until row-counts justify the bloat. |
| `connectorx` | No (Stage 3+) | Rust-fast on Postgres specifically; introduces a Rust toolchain + [`connectorx`](https://sfu-db.github.io/connector-x/) wheel that is platform-fragile (PoC #4 boot-time risk). |

Stage 1 sets `backend="sqlalchemy"` explicitly (do NOT rely on default — the
default has flipped twice in dlt's history; pin behavior). `reflection_level="full_with_precision"`
is the contract the wrap freezes so `Decimal` / `numeric` / `time` / `timestamptz`
round-trip cleanly into Iceberg types.

### §13.4 Wrap point in Nucleus

Per `docs/specs/nucleus_architecture_v4.1.md` §5.5 + §6.3 + Anti-Over-Engineering: ONE
new module, mirroring the existing SQLite branch. ADR-014 proposes
`src/nucleus/ctx/copy_from_postgres.py` paralleling `src/nucleus/ctx/copy_from.py`.

Naming is deliberate: `ingest_postgres_to_iceberg(...)` matches the existing
`ingest_sqlite_to_iceberg(...)` shape, NOT a class hierarchy. No
`SourceEngineFactory`, no `BackendRegistry`, no `PostgresIngester` class —
the swap interface lives in `docs/swap/dlt.md` and only formalizes if a
second wrapped engine appears (Anti-Over-Engineering §2: one caller = inline).

### §13.5 Connection string + auth scope (Stage 1 minimum)

dlt accepts `credentials=` in three forms per the
[setup page](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/setup)
+ [credentials guide](https://dlthub.com/docs/general-usage/credentials/setup):

1. **SQLAlchemy URL string** — `postgresql://user:pass@host:5432/db?sslmode=require`. **Stage 1 default.**
2. `ConnectionStringCredentials("...")` Python object — unchanged surface.
3. SQLAlchemy `Engine` instance — useful for SSH-tunnel scenarios per the
   [SSH section](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration);
   **Stage 1 OUT** (architectural escape hatch for v0.5).

Stage 1 carries TLS via the standard libpq query params (`sslmode=`, `sslrootcert=`)
documented at <https://www.postgresql.org/docs/current/libpq-ssl.html>. **No IAM,
no Vault, no AssumeRole, no OIDC token broker** — those land alongside ADR-010
(OIDC delegation) at v0.5+. The Stage 1 wrap REJECTS the temptation to invent
a `nucleus.secrets.postgres` shim; users supply a literal connection string or
set `NUCLEUS_POSTGRES_DSN` env var, full stop.

### §13.6 Schema inference + Iceberg type mapping

`sql_database` reflects Postgres types via SQLAlchemy and dlt translates them
to its own type system before the Iceberg destination (PyIceberg) writes.
Per the [Iceberg destination](https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg)
docs the writer is `pyiceberg`; once ADR-003 lands (`pyiceberg==0.11.x`) we
inherit that release's type-mapping fixes. Postgres-specific edge cases the
Stage 1 wrap MUST round-trip correctly (regression-test fixtures):

- `BIGINT`, `INTEGER`, `SMALLINT` → Iceberg `LongType` / `IntegerType`
- `NUMERIC(p, s)` / `DECIMAL` → Iceberg `DecimalType(p, s)` (requires
  `reflection_level="full_with_precision"` per §13.3)
- `TIMESTAMPTZ` → Iceberg `TimestamptzType`; **`TIMESTAMP` (naive) → `TimestampType`**.
  AI commonly conflates these (logged §13.10).
- `JSONB` → Iceberg `StringType` for Stage 1 (lossless; no nested-table flattening
  on the Postgres branch — pre-empts dlt's [`max_table_nesting`](https://dlthub.com/docs/general-usage/source)
  expansion which is a Stage 3+ concern).
- `BYTEA` → Iceberg `BinaryType`.
- Postgres `ARRAY` types → **Stage 1 OUT.** Raise `NucleusUnsupportedTypeError`
  with a fix hint suggesting a SQL view that unnests / casts.

### §13.7 Stage 1 scope (what `pipeline.run()` is asked to do)

| Capability | Stage 1 | Stage 2 | Stage 3+ |
|---|---|---|---|
| Full-table append (`write_disposition="append"`) | **Yes** | — | — |
| Full-table replace (`write_disposition="replace"`) | Yes (single flag) | — | — |
| [Incremental cursor loading](https://dlthub.com/docs/general-usage/incremental/cursor) | **No** (deferred) | Yes | — |
| [Merge / upsert / SCD2](https://dlthub.com/docs/general-usage/merge-loading) | No | — | Yes |
| Multi-table from one CLI call | No (one table per call) | Yes | — |
| Source-side column filter (`included_columns`) | No | — | Yes |
| MySQL / MSSQL same code path | No (different ADR) | Yes (MySQL) | Yes (rest) |

Stage 1 deliberately ships ONE write disposition flag and ONE table per CLI
invocation. Per Anti-Over-Engineering §4, no speculative scaffolding for
incremental until Stage 2's first real caller appears.

### §13.8 Error translation surface (Postgres-specific)

Builds on §5.4 above. Postgres-source-specific exceptions the Stage 1 wrap MUST
translate at the dlt boundary:

| Trigger | dlt outer | Inner cause | NucleusError | NE-code |
|---|---|---|---|---|
| Wrong host / port / DNS fail | `PipelineStepFailed(step="extract")` | `sqlalchemy.exc.OperationalError` wrapping `psycopg.OperationalError` "could not connect" | `NucleusSourceConnectionError` | `NE1001` |
| Bad password | same | `psycopg.errors.InvalidPassword` | `NucleusSourceAuthError` | `NE1009` |
| Database does not exist | same | `psycopg.errors.InvalidCatalogName` | `NucleusSourceConnectionError` | `NE1001` |
| Table missing | `PipelineStepFailed(step="extract")` | `sqlalchemy.exc.NoSuchTableError` | `NucleusSourceNotFound` | `NE1008` |
| SSL handshake fail | same | `psycopg.OperationalError` "SSL" | `NucleusNetworkError` | `NE1010` |
| Unsupported column type (e.g. `geometry`, ARRAY) | extract-time `TypeError` | — | `NucleusUnsupportedTypeError` | `NE2004` |
| Iceberg commit conflict (downstream of `pipeline.run`) | per §5.4 + ADR-001 | `pyiceberg.CommitFailedException` | `NucleusCommitConflictError` | `NE1002` |
| Catch-all dlt step failure | `PipelineStepFailed` | unknown | `NucleusInternalError` | `NE3001` |

All NE-codes already exist in `src/nucleus/errors.py` per ADR-006. **No new
NE-code allocations required for Stage 1** — verify in PR review.

The two-level `__context__` walk documented at §5.4 (citing the
[schema-contracts page](https://dlthub.com/docs/general-usage/schema-contracts))
applies unchanged for normalize-step errors. SQLAlchemy wraps psycopg, dlt
wraps SQLAlchemy — the wrap MUST unwrap both before pattern-matching the
inner cause; pure type-tests on the outer `PipelineStepFailed` will all
collapse to `NE3001` (information loss).

### §13.9 Performance — empirical placeholder

No Nucleus benchmark exists. dltHub blog claims (cited in §6 above) for
Postgres → DuckDB on `backend="sqlalchemy"` are not directly applicable —
Iceberg destination adds Parquet-write + commit overhead. **Stage 1 PR
must produce a measured baseline** on a 1M-row reference table (founder picks
the dataset) and store it in `tests/upgrade_smoke/` so future dlt minor
upgrades regression against it (per AGENTS.md §11.13). Acceptable Stage 1
floor: 10k rows/sec sustained on a M1 MacBook with default backend; below
that, escalate (the SQLAlchemy backend may be insufficient and Stage 2
PyArrow-backend acceleration moves up the queue).

### §13.10 Stage 1 hallucination watch (Postgres-specific)

Add to §9 hallucinations on PR review. AI agents will:

- ❌ Suggest `pip install dlt[postgres]`. **Wrong** — that pulls
  [`psycopg2-binary`](https://pypi.org/project/psycopg2-binary/) for the
  destination path; we want `dlt[sql_database,pyiceberg]` (source-only).
  Our pinned `psycopg[binary]==3.2.3` is psycopg3, used by SQLAlchemy 2.0;
  installing psycopg2-binary alongside is a transitive footgun.
- ❌ Suggest `from dlt.sources.postgres import postgres_source` — does not
  exist. The source is `dlt.sources.sql_database.{sql_database, sql_table}`.
- ❌ Suggest `pipeline.run(table_name="orders", source="postgresql://...")`
  — wrong shape; `data` is the first positional arg and must be a Resource
  / Source, not a connection string.
- ❌ Suggest `sql_table(uri="postgresql://...")` — the kwarg is
  `credentials=`, not `uri`; verify against [setup](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/setup).
- ❌ Conflate `TIMESTAMP` and `TIMESTAMPTZ` — see §13.6.
- ❌ Suggest `ssl_mode="require"` as a Python kwarg. **Wrong** — TLS rides
  on the URL query string (`?sslmode=require`), per
  <https://www.postgresql.org/docs/current/libpq-ssl.html> + SQLAlchemy's
  [Postgres dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
- ❌ Suggest `psycopg3` as a Python package name. **Wrong** — package is
  `psycopg` (psycopg3 is the marketing/major-version label); see
  <https://www.psycopg.org/psycopg3/docs/>.

### §13.11 Open questions for ADR-014

Surfaced in the ADR §"Open questions"; logged here for cross-reference:

1. **Wrap dlt vs extend native `ctx.copy_from`?** Native Postgres branch
   would be ~150 LOC SQLAlchemy + PyIceberg, mirroring §5.5.1 of v4.1. dlt
   wrap is ~80 LOC + the dlt dependency. ADR-014 picks dlt; this NEEDS
   founder confirmation given the architecture sized §5.5.1 for a native helper.
2. **Stage 1 row-count ceiling.** Below what cap does Stage 1 promise
   correctness? PoC #5 candidate value: 10M rows (covers 5-20-engineer
   beachhead for ~6 months without Stage 2 PyArrow upgrade).
3. **dlt pipelines_dir location.** `~/.dlt/pipelines/` (default) vs project-local
   `.nucleus/state/dlt/`. §5.3 picks project-local; ADR-014 must lock.
4. **`restore_from_destination` flag.** Default `True` re-reads `_dlt_pipeline_state`
   on every run (~100-500 ms penalty per §6). Stage 1 has no incremental
   state to restore, so `False` is the simplification. ADR-014 must lock.
5. **Concurrent ingest of the same target.** Two `nucleus ingest postgres://... --as raw.orders`
   calls in parallel — Iceberg commit conflict is the well-tested path
   (`NE1002`); confirm the wrap surfaces a clean retry-or-fail message.

*Last verified: 2026-05-13 against dlt 1.26.0. Re-verify on Stage 1 PR open;
cross-link to ADR-014 once it ratifies.*
