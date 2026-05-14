# Research: Daft (multimodal / distributed dataframe engine)

> **Component status in Nucleus**: **v0.5+ optional engine.** Not in v0.1–v0.3. Per `nucleus_architecture_v4.1.md` §5.3, §3.2 layer L1, §18.4. Default workloads stay on DuckDB + Polars; Daft opts in for multimodal columns (images / audio / video / embeddings / tensors) and distributed execution via Ray.
> **Pin candidate (provisional)**: `daft==0.7.11` (released **2026-05-12**, verified PyPI 2026-05-13). **Not pinned in `pyproject.toml` today.** Daft is **pre-1.0** with monthly minor releases — actual v0.5 pin = whatever ships at v0.5 ADR time (Mo 20-28; expect 0.10+ or 1.0+).
> **License**: **Apache-2.0** ([PyPI](https://pypi.org/project/daft/0.7.11/), README §License). **JVM-free**: **YES** — Python frontend, Rust core (Tokio, Arrow). Hard Constraint #1 satisfied.
> **Research date**: 2026-05-13  •  **Used in**: nowhere yet — pre-research artifact for the v0.5 ADR.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening the v0.5 multimodal ADR. Daft is the canonical **wrap-not-build** case (Pillar #2) for multimodal column types we will never implement ourselves.

---

## §1. At a glance

- **License**: Apache-2.0  •  **Maintainer**: Eventual Inc. (Sammy Sidhu, Jay Chia)  •  **GitHub**: https://github.com/Eventual-Inc/Daft (~5.5k stars, 2026-05-13)
- **Position**: L1 Engines (v4.1 §3.2) — **optional**, surfaces as `@nucleus.asset(engine="daft")` (proposed) in v0.5. Hidden behind `ctx`; users never `import daft` outside the engine boundary.
- **Latest stable**: 0.7.11 (2026-05-12). **Pre-1.0** — `Development Status :: 5 - Production/Stable` not set on PyPI. Treat as Beta.
- **What it is**: a **Python dataframe engine** with first-class multimodal column types (`Image`, `Tensor`, `Binary`, embeddings) and a Rust engine ("Swordfish") plus optional distributed runner ("Flotilla") on Ray. `daft.set_runner_ray(...)` flips local → distributed. Reads/writes Iceberg natively via PyIceberg.

---

## §2. What Daft is, in Nucleus terms

Daft sits where Polars does (**L1 DataFrame engine**) but covers two workloads Polars doesn't: **multimodal columns** as native Arrow-extension types (with `download` / `decode_image` / `image_to_tensor` / `resize` expressions); and **distributed execution** via Ray. Per v4.1 §5.3, neither is needed for the v0.1 beachhead — both become live at v0.5 when Lance + multimodal lands (§18.4).

| Daft surface | Nucleus surface |
|---|---|
| `daft.DataFrame` | **asset** payload; returned from `@nucleus.asset(engine="daft")` |
| `daft.read_iceberg` / `df.write_iceberg` | **asset read** / **materialization**; AMA calls |
| `daft.read_lance` | **vector asset read** (v0.5+); `ctx.read_vector(...)` (proposed) |
| Native runner ("Swordfish") / Ray runner ("Flotilla") | local **engine** / **yield-to-giants Mode 2** target (§4.4) |
| `@daft.func` / `@daft.func.batch` | UDF surface — **never** public; adapter-internal |

Polars stays the v0.5+ default for tabular; Daft is per-asset opt-in via `engine="daft"`. v0.5 ADR central decision: per-asset (preferred) or per-project selector. **Deferred to v0.5 ADR.**

---

## §3. Official documentation URLs

Verified by `WebFetch` 2026-05-13. Docs root: **`https://docs.getdaft.io/en/stable/`** — substitute paths from this root.

- Project: [daft.ai](https://www.daft.ai/) • [GitHub](https://github.com/Eventual-Inc/Daft) • [PyPI](https://pypi.org/project/daft/) • [Releases](https://github.com/Eventual-Inc/Daft/releases)
- Docs leaves: `quickstart/` • `architecture/` • `api/` (+ `api/io/`, `api/datatypes/all_datatypes/`, `api/udf/`, `api/config/`) • `distributed/` (+ `distributed/ray/`) • `roadmap/`
- Connectors: `connectors/iceberg/` • `connectors/lance/` • `connectors/unity_catalog/`
- Modalities (leaf only — index 404s): `modalities/images/` (audio / video / text under sibling paths)

**404 gaps on 2026-05-13** (flag for AI agents): legacy `getdaft.io/projects/docs/...` 404s — canonical is `docs.getdaft.io`; marketing `getdaft.io` redirects to `daft.ai`. `modalities/` index 404s — cite per-modality leaves only. `api/exceptions/` does not exist (see §8).

---

## §4. APIs Nucleus will wrap

Symbols the v0.5 adapter (`engines/daft_engine.py`, target ≤500 LOC) calls. **NEEDS VERIFICATION** on first wire-up against the version pinned at v0.5 time, since pre-1.0 churn is high.

### §4.1 When to pick Daft over Polars

Router in `engines/router.py` (proposed). Per v4.1 §5.3 + §5.9:

| Workload | Engine |
|---|---|
| Tabular transform <100 GB single-node | **Polars** (cold-start, RAM, DX; no multimodal needed) |
| Tabular SQL single-node | **DuckDB** (v4.1 §5.1 default) |
| Asset has `Image` / `Audio` / `Video` / `Tensor` / `Embedding` column | **Daft** (Polars is `Multimodal: Python object` per Daft README) |
| Asset reads/writes Lance dataset | **Daft** (`daft.read_lance` is the integrated path; Polars has no Lance reader) |
| GPU UDF batched alongside CPU work | **Daft** (managed UDF runtime — `@daft.func.batch` with automatic batching) |
| Single dataframe distributed across machines | **Daft + Ray** (`daft.set_runner_ray()` — §4.4) |
| Cross-asset atomicity | neither (catalog is the boundary, v4.1 §6.2) |

**Default stays Polars.** Daft is opt-in, not the new floor. Per v4.1 §5.3: "Default workloads stay on DuckDB + Polars."

### §4.2 Daft's Iceberg integration (read + write paths)

Per `connectors/iceberg/`. Daft uses **PyIceberg under the hood** for catalog discovery + atomic commits — same `pyiceberg.catalog.load_catalog` path the rest of Nucleus uses. Entry points: `daft.read_iceberg(table)` and `df.write_iceberg(table, mode=...)` take a PyIceberg `Table` loaded by us, not a catalog config (verified `connectors/iceberg/` FAQ §1-§14, 2026-05-13):

**Supported**: read by snapshot id; hidden partition pruning + all Iceberg partition transforms (identity / bucket / truncate / year-month-day-hour) on read+write; all PyIceberg catalogs (filesystem / Lakekeeper / Polaris / R2 / Unity) — transparent across v0.1 → v0.5 catalog evolution (FAQ §4).

**Not supported in 0.7.11** (adapter routes around):

- Snapshot slices between two ids — roadmap (FAQ §7); incremental-since-snapshot stays on PyIceberg.
- Write modes other than `append` / `overwrite` — **NO** `upsert` / `MERGE INTO` (FAQ §14); merge workloads stay on PyIceberg.
- Equality deletes (read) — positional only; v2 equality on roadmap (FAQ §5); adapter rejects with `NucleusEngineError`.
- Schema evolution from DataFrame — only `create_table` exposed (FAQ §9); migration through PyIceberg, never Daft.
- Snapshot metadata read — docs recommend PyIceberg (FAQ §10).

**Atomicity per `df.write_iceberg(...)`**: one snapshot per call. Same constraint as PyIceberg directly (ADR-001). Cross-call atomicity = catalog responsibility.

### §4.3 Daft for vector workloads (alongside Lance)

Per `connectors/lance/`. Daft is the **canonical Python read/write path for Lance datasets** (v4.1 §4.1, §5.4 vector-storage Tier 0). Installed via `daft[lance]` extra (pulls `pylance<0.40.0`). Entry points: `daft.read_lance(uri, version=..., default_scan_options=...)` and `df.write_lance(uri, mode="create|append|overwrite")`.

Capabilities used by the v0.5 adapter: versioned reads + asof time-slice (`version=` / `asof=`); **vector search push-down at scan time** via `default_scan_options={"nearest": {"column": "vector", "q": ..., "k": 5}}` — native Lance scanner, **no second vector DB needed** for the common embedding-search case; compaction via `daft.io.lance.compact_files(uri, ..., partition_num=...)` — distributed across Ray workers; in-place column evolution via `daft.io.lance.merge_columns(...)`; REST namespace (LanceDB Cloud, Apache Gravitino) via `LanceRestConfig` — v0.5 swap path if Lance file-format becomes single-tenant.

This answers v4.1 §5.4 — Daft and Lance are the **integrated default pair** for v0.5; LanceDB SDK is opt-in for users wanting search-only access without a dataframe.

### §4.4 Distributed Daft via Ray as a Mode 2 graduation path

Per `architecture/` + `distributed/ray/`. Daft has two runners: **Native ("Swordfish")** — Rust + Tokio, single-machine, streaming, default; and **Distributed ("Flotilla")** — head node + worker actors each running embedded Swordfish, locality-aware. Switch via `daft.set_runner_ray("ray://host:10001")` — single line, **no code rewrite**.

This is the **only** path in our wrapped stack that distributes a single dataframe computation across machines without leaving the Iceberg substrate. Daft + Ray is **additive** to v4.1 §10.2 Databricks/Snowflake dispatch (Mode 2) — covers the OSS-stack case where the user owns the cluster; Databricks/Snowflake covers SaaS. Surfaces as `@nucleus.asset(engine="daft", compute="ray://…")` (proposed). Mode 1 + Mode 3 unaffected. **Deferred to v0.5 ADR.**

Caveats: (a) Ray client requires the **same Python minor + Daft version** between client and server (`distributed/ray/` warning box) — couples our pin to user's cluster; (b) `daft[ray]` extra pulls hundreds of MB; (c) `ray job submit` requires `pip install "ray[default]"` separately.

---

## §5. Integration points with Nucleus

- **PyArrow (L0)** — Arrow-backed end-to-end; record batches flow through both runners.
- **PyIceberg (L0)** — `daft.read_iceberg` / `df.write_iceberg` via our `pyiceberg.Catalog`.
- **Lance (L0, v0.5+)** — `daft.read_lance` / `df.write_lance` via `daft[lance]`.
- **Polars / DuckDB (L1, peer engines)** — co-resident; router selects per asset (§4.1). Direct DuckDB interop **NEEDS VERIFICATION** — Arrow is the pivot.
- **Dagster (L2)** — Daft frames never escape `coordination/`; errors translated by `error_translation.py` **before** the AMA → CTX boundary.
- **Ray (L1 distributed)** — `daft.set_runner_ray(...)` opt-in per project/asset; never default.
- **`ctx` SDK (L4)** — users return a Daft frame from `@nucleus.asset(engine="daft")`; AMA coerces to Arrow before PyIceberg writes.

Per `engineering.md` §11.4, we never materialize to pandas as an interop hop. Arrow is the pivot.

---

## §6. Performance characteristics

Numbers from docs only; **no Nucleus benchmark yet** — repeat under v0.5 ADR conditions.

- **Cold start**: `daft==0.7.11` core wheel ~61 MB vs `polars==1.18.0` ~30 MB; `daft[ray]+[lance]+[iceberg]` together >250 MB. Relevant to PoC #4 (`nucleus up <10s`) — **never auto-import daft in CLI startup**; lazy-import inside the engine adapter. Daft's "20x faster start times" claim ([docs](https://docs.getdaft.io/en/stable/)) is vs Spark, not vs Polars.
- **Memory** (marketing): "5x less memory than alternatives" ([daft.ai](https://www.daft.ai/)). **NEEDS VERIFICATION**. Streaming execution is real (`architecture/` "Native Runner" — async-channel + back-pressure).
- **Multimodal pipelining** is the differentiator vs Polars: Daft isolates "expensive projections such as Python UDFs, model inference, URL downloads, image decoding … executed as late as correctness permits" (`architecture/` "Optimization §3"). Polars has no opinion about scheduling expensive UDFs.
- **Distributed**: per `architecture/` "Ray Runner (Flotilla)" — head scheduler, worker actors running Swordfish, partitioning ≈ input file count. **NEEDS VERIFICATION** vs single-node + good partitioning before recommending Ray over a bigger laptop.

---

## §7. Compatibility with Nucleus pins (2026-05-13) + swap-target analysis

Daft 0.7.11 dependency constraints (verified `pypi.org/project/daft/0.7.11/`):

| Nucleus dep | Our pin | Daft 0.7.11 requires | Notes |
|---|---|---|---|
| `pyarrow` | `18.1.0` | `>=8.0.0,<24.0.0` | OK |
| `pyiceberg` | `0.8.1` today; `0.11.x` per ADR-003 | `>=0.7.0,<=0.11.0,!=0.9.1,!=0.10.0` (`daft[iceberg]`) | **OK with caveat** — 0.8.1 and 0.11.0 work; **0.9.1 and 0.10.0 excluded** — any interim upgrade landing on those breaks install |
| `polars` / `duckdb` | pinned | not required | OK |
| Python | `>=3.11,<3.13` | `>=3.10` | OK |
| `dagster` | `1.9.5` | no first-party `dagster-daft` shipped | Adapter writes Dagster wrapper ourselves (~200 LOC) |
| `pylance` | unpinned | `<0.40.0` (`daft[lance]`) | Pin alongside Daft at v0.5 ADR |
| `ray[client,data]` | unpinned | `>=2.0.0,<2.56.0` (`>=2.10.0` for client) (`daft[ray]`) | Pin Ray for users opting into Mode 2 |
| Windows wheels | required | published for 0.7.11 | OK |

**ADR sequencing**: (1) ADR-003 PyIceberg `0.8.1 → 0.11.x` ships first (already on roadmap); (2) Lance integration ADR (v0.5 prep); (3) Daft integration ADR after Lance lands AND multimodal use is empirically demanded — Pillar #5.

### §7.1 Swap-target analysis (v4.1 §9.3)

If Daft becomes unviable (license pivot, vendor death, perf regression >2x, deprecation):

- **Polars** (MIT, in stack) — covers the tabular subset only; Polars is `Multimodal: Python object` per Daft's PyPI README — users with images/audio/video lose native types.
- **Apache Spark** (Apache 2.0) — JVM violates Hard Constraint #1; already a Mode 2 graduation target (v4.1 §10.2). Disqualified as in-stack default.
- **Ray Data** (Apache 2.0) — `Dataset` API; covers multimodal + distributed + Arrow but **lacks query optimizer + vectorized execution engine** (per Daft's PyPI comparison). Worse DX, viable fallback.
- **DataFusion + custom multimodal layer** — would mean **building** the multimodal layer = Pillar #2 violation. Reject.

**Verdict**: **no single swap target covers Daft's combined (multimodal + distributed + JVM-free + Apache 2.0) niche.** Daft is **Tier 1 with conditional swap** — the v0.5 ADR must confirm Daft's vendor health before adoption. Smoke-test interface in `engines/Engine` Protocol (v4.1 §9.3) is mandatory; full swap adapter on-demand.

---

## §8. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge)

- `daft.write_iceberg(..., mode="merge"|"upsert")` — does not exist; only `append`, `overwrite` (FAQ §14).
- `daft.read_iceberg(..., snapshot_range=...)` — does not exist; only `snapshot_id` (FAQ §7).
- `df.evolve_schema(...)` / `df.alter_table(...)` — does not exist; only `create_table` (FAQ §9).
- `daft.from_polars(lf)` — **NEEDS VERIFICATION**. Documented constructors are `daft.from_pydict` / `daft.from_arrow`; Polars interop is via Arrow bridge.
- `df.collect(streaming=True)` — does not exist (Polars syntax). Daft's native runner is unconditionally streaming.
- `daft.set_runner_dask(...)` / `set_runner_modin(...)` — only `set_runner_ray()` and `set_runner_native()` exist (`api/config/`).
- `from daft.exceptions import DaftError` — **NEEDS VERIFICATION**; no `api/exceptions/` page on 0.7.11. Reject fabricated class names; read source.
- Citing `getdaft.io/projects/docs/...` — dead. Cite `docs.getdaft.io/en/stable/...` only.

### Real gotchas from official docs

- **Pre-1.0 = Beta** — `Development Status :: 5 - Production/Stable` not set on 0.7.11. ~1 minor/month (0.5.0 → 0.7.11 = 22 minors in 12 months); today's candidate is ~24 minors stale at v0.5 (Mo 20-28). Constraint #11 every-minor changelog read = real cost for Daft.
- **Equality-delete Iceberg tables can't be read** (FAQ §5) — reject in adapter.
- **Schema evolution one-way through PyIceberg** (FAQ §9). AMA routes around Daft.
- **Telemetry on by default** — Scarf-based per PyPI README §Telemetry. Disable via `DO_NOT_TRACK=true` in `nucleus up` startup.
- **Ray client requires version match** (Daft + Python minor) — couples our pin to user's cluster.
- **`daft.col()` ≠ `pl.col()`** despite identical names. Different expression dispatch, null semantics, cast rules. Cross-engine code review must check both.
- **`@daft.func` is per-row by default**; `@daft.func.batch` recommended for perf (`modalities/images/` §4) — wrong choice silently causes per-row overhead.

---

## §9. Decision log — why Daft enters at v0.5, not earlier, not later

- **v0.1 / v0.2 / v0.3 (Mo 2-20)**: beachhead is a tabular Postgres → Iceberg pipeline. Daft's value (multimodal, distributed) doesn't move the <30 min metric. 60-250 MB deps + 200-500 ms boot for zero v0.1 gain = Pillar #1 violation. v4.1 §18.1 explicit OUT list: "Lance / multimodal / Daft (v0.5)". **Defer.**
- **v0.5 (Mo 20-28)**: Lance + multimodal + `ctx.agent` lands per v4.1 §18.4. Two empirical triggers fire together: (a) users want `Image` / `Audio` / `Video` columns alongside structured assets — Polars can't serve natively; (b) lineage-aware AI Copilot + agent runtime want embedding columns + Lance — Daft is the canonical Lance reader. **Now.** Both triggers must show empirical demand (telemetry from v0.3 beta) before the v0.5 ADR opens — Pillar #5.
- **v1.0+ (Mo 28-36+)**: if multimodal demand is broad, Daft becomes Tier 1 production-supported. If narrow, Daft stays optional with quarterly maintenance.
- **Never**: build our own multimodal/distributed engine. Constraint #4 violation; v4.1 §20.1 non-goal "Our own DataFrame engine."

Integration ADR (when v0.5 work starts): `docs/decisions/ADR-NNN-daft-v05-multimodal.md`.

---

## §10. Next reads when v0.5 work starts

- [ ] **Daft + Dagster** — no first-party `dagster-daft` as of 2026-05-13; we likely write a thin wrapper. Check `https://docs.dagster.io/integrations` first. **NEEDS VERIFICATION.**
- [ ] **Exceptions inventory** — read `Eventual-Inc/Daft` source under `daft/exceptions.py`; mirror PoC #1's harness against Daft failure modes.
- [ ] **Daft ↔ DuckDB Arrow interop** — verify zero-copy via Arrow C Stream; benchmark vs Parquet round-trip.
- [ ] **Multimodal type round-trip** — Iceberg has no native image/audio types; they land as `binary` + metadata. Document fidelity.
- [ ] **Pre-1.0 stability survey** — read every release note from pin to v0.5 target; if breaking-density >1/minor, escalate ADR.
- [ ] **Benchmark Daft + Ray vs single-node Polars + bigger laptop** — at what size does Mode 2 dispatch beat vertical scaling? If "rarely under 1 TB", Daft + Ray is v1.0+, not v0.5.

---

*Last verified: 2026-05-13 against `daft==0.7.11`. Re-verify when opening the v0.5 ADR (~Mo 20+), before pinning, or on any minor bump while pre-1.0. Log any AI-fabricated Daft APIs caught in PR review to [`docs/research/ai_hallucinations.md`](./ai_hallucinations.md).*
