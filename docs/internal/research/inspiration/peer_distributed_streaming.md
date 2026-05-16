# Peer Research: Distributed + Streaming Compute — Tier A.5

> **Scope**: Daft · Smallpond (DeepSeek) · Polars Streaming + Polars Cloud
> **Last verified**: 2026-05-15 against official documentation + PyPI
> **Research tier**: AGENTS.md §11.14 — Research tier (fallback: Claude Sonnet 4.6)
> **Audience**: Nucleus founder + future architects evaluating distributed/streaming decisions at v0.5–v0.7+
> **Related docs**: `docs/internal/research/daft.md` (deep-dive), `docs/internal/research/polars.md`, `docs/specs/nucleus_architecture_v4.1.md` §5.3, §10.2, §18.4

---

## 1. Executive Summary

| Project | Verdict | Nucleus milestone |
|---|---|---|
| **Daft** (Eventual-Inc) | **WRAP — v0.5+, optional, multimodal trigger** | Gate: empirical ML-team demand after v0.3 beta (per v4.1 §18.4) |
| **Smallpond** (DeepSeek) | **DEFER — v0.7+ watch list, NOT wrap today** | Gate: production maturity + dependency conflict resolution |
| **Polars Streaming** | **USE NOW (already in stack) — `engine="streaming"` is the v0.3 out-of-core path** | Gate: none — already available in `polars==1.18.0` |
| **Polars Cloud** | **OBSERVE — do NOT integrate** | Gate: AWS-only, closed distributed engine, lock-in conflict with Pillar #5 |

**Distributed strategy in one sentence**: Nucleus stays single-node DuckDB + Polars for the v0.1–v0.3 beachhead; adds Polars streaming for out-of-core at v0.3; wraps Daft + Ray for multimodal + moderate-distributed at v0.5; defers true distributed tabular to "yield to giants" (Databricks/Snowflake) Mode 2/3 via `compute=` dispatch — always.

---

## 2. Project 1: Daft (Eventual-Inc)

> Note: A deep-dive research doc already exists at `docs/internal/research/daft.md` (last verified 2026-05-13 against `daft==0.7.11`). This section adds the Nucleus distributed-tier framing, benchmarks, and March 2026 roadmap updates.

### 2.1 What Daft is

Daft is a Python DataFrame engine with:
- **Multimodal column types** as first-class Arrow extension types: `Image`, `Audio`, `Video`, `Tensor`, `Embedding` — not `pl.Object`, not raw `bytes`
- **Rust engine ("Swordfish")** — Tokio async, vectorized, streaming execution; single-machine default
- **Distributed engine ("Flotilla")** — Ray actors each running embedded Swordfish; activated by one line: `daft.set_runner_ray("ray://host:10001")`
- **Native Iceberg + Lance read/write** via PyIceberg (same catalog Nucleus already uses)
- **JVM-free** — Python frontend, Rust core; Hard Constraint #1 satisfied

**License**: Apache-2.0 ([GitHub](https://github.com/Eventual-Inc/Daft), README §License)
**Latest stable (verified PyPI 2026-05-15)**: `daft==0.7.11` (released 2026-05-12); `daft-lts==0.7.10` exists as a long-term-support track
**GitHub**: ~5.5k stars, active (monthly minor releases since 0.5.0)
**Docs root**: `https://docs.getdaft.io/en/stable/` (NOT `getdaft.io/projects/docs/` — that URL is dead as of 2026-05-13)

### 2.2 Daft's architecture

Daft has three layers per official docs at `https://docs.getdaft.io/en/stable/architecture/`:

1. **API layer** — Python DataFrame API + SQL interface → `LogicalPlan` (tree of `Source`, `Project`, `Filter`, `GroupBy`, `Join` operators plus expression trees)

2. **Optimization layer** — two passes before any `collect()`:
   - **Rule-based**: filter/projection/limit/aggregation pushdowns, projection folding, subquery unnesting
   - **Cost-based**: join reordering using a brute-force enumerator with source statistics
   - **Multimodal awareness**: expensive projections (Python UDFs, model inference, URL downloads, image decoding) are isolated into dedicated logical nodes and deliberately NOT pushed into scans, so batching/backpressure applies independently

3. **Execution layer** — two runtime options:
   - **Native Runner (Swordfish)**: Rust + Tokio, async channels between operators, single-machine, unconditionally streaming (no opt-in flag needed)
   - **Ray Runner (Flotilla)**: head node runs Flotilla scheduler; each worker node runs a single Ray actor embedding Swordfish; partitioning ≈ input file count; outputs go to Ray's object store; locality-aware task assignment

The planner is **custom** — not Substrait-based as of 0.7.11. No Substrait query interchange as of March 2026 roadmap. NEEDS VERIFICATION for future versions.

### 2.3 When Daft beats DuckDB + Polars

Per official docs `architecture/` §Optimization and Nucleus `docs/internal/research/daft.md` §4.1:

| Workload | Right engine | Reason |
|---|---|---|
| Tabular SQL, single-node < ~500 GB | **DuckDB** | Lower startup, full SQL optimizer, already in stack |
| Tabular DataFrame, single-node < ~500 GB | **Polars** | Lower overhead, lower cold-start (~30 MB vs ~61 MB), already in stack |
| Asset has `Image`, `Audio`, `Video`, `Tensor`, `Embedding` column | **Daft** | Native Arrow-extension types; Polars reduces these to `pl.Object` (unoptimized, unindexed) |
| Asset reads/writes a Lance dataset | **Daft** | `daft.read_lance` + `df.write_lance` is the canonical Lance read/write path; Polars has no Lance reader |
| GPU UDF batched in a pipeline | **Daft** | `@daft.func.batch` with automatic batching + backpressure; Polars has no GPU UDF scheduler |
| Single-machine tabular > ~500 GB | **Polars streaming** (`engine="streaming"`) | Out-of-core without distributed complexity; Daft adds value only when streaming can't keep up or multimodal is needed |
| Multi-machine tabular | **Daft + Ray** OR **yield to giants** | Daft is the OSS-stack option; Databricks/Snowflake is the SaaS option via `compute=` |

**Size threshold for Daft + Ray vs vertical scaling**: NEEDS VERIFICATION — no official threshold published. Daft's own docs demonstrate single-node processing of 1 TB+ (`benchmarks/#1000-scale-factor`). Vertical scaling (bigger laptop/EC2) is often competitive with Ray at < 1 TB depending on I/O bandwidth. Do NOT recommend Ray over bigger machine for < 1 TB without empirical measurement.

### 2.4 Daft's benchmarks (official, self-reported)

Source: `https://docs.getdaft.io/en/stable/benchmarks/` (verified 2026-05-15).

**AI/multimodal benchmarks** (Flotilla on 8x AWS g6.xlarge, benchmark date 2025-09-22, Daft 0.6.2):

| Workload | Daft | Ray Data | EMR Spark | Daft advantage |
|---|---|---|---|---|
| Audio transcription (113,800 files, Whisper-tiny) | **6m 22s** | 29m 20s | 25m 46s | 4.0–4.6x faster |
| Document embedding (10,000 PDFs, sentence-transformers) | **1m 54s** | 14m 32s | 8m 4s | 4.2–7.6x faster |
| Image classification (803,580 images, ResNet18) | **4m 23s** | 23m 30s | 45m 7s | 5.4–10.3x faster |
| Video object detection (1,000 videos, YOLO11n) | **11m 46s** | 25m 54s | 3h 36m | 2.2–18.4x faster |

**TPC-H tabular benchmarks** (Flotilla on AWS i3.2xlarge, multiple node counts):

| Scale | Daft | Spark | Dask | Modin | Notes |
|---|---|---|---|---|---|
| 100 SF (100 GB) | **785s** | 2,648s (3.3x) | 6,010s (7.7x) | partial | 4 workers |
| 1000 SF (1 TB) | **7,774s** | 27,161s (3.5x) | partial | failed | 4 workers |
| 1000 SF, 1 node | completes | — | — | — | Daft processes 16x-memory data single-node |

**Important caveats**:
- All benchmarks are self-reported by Eventual-Inc; independent replication encouraged
- AI benchmarks used 0.6.2 (we're on 0.7.11 candidate); results may differ
- TPC-H benchmarks compare distributed Daft to distributed Spark — not relevant to Nucleus single-node beachhead
- Relevant comparison for Nucleus v0.3: **Polars streaming vs single-node Daft native runner** — no official head-to-head; run under v0.5 ADR conditions

### 2.5 Daft's Iceberg integration surface

Source: `https://docs.getdaft.io/en/stable/connectors/iceberg/` (verified 2026-05-15, content written to agent-tools file).

Key API points Nucleus wraps:
- `daft.read_iceberg(table: pyiceberg.Table)` — reads by snapshot; supports all Iceberg partition transforms
- `df.write_iceberg(table: pyiceberg.Table, mode="append"|"overwrite")` — writes one snapshot per call; no `upsert`/`merge`
- Equality deletes (read): **NOT supported** in 0.7.11 — adapter must reject with `NucleusEngineError`
- Schema evolution: only `create_table` exposed — migration through PyIceberg only
- PyIceberg version constraint: `>=0.7.0,<=0.11.0` excluding `!=0.9.1,!=0.10.0` — **skip those interim pins**

### 2.6 Daft's Ray integration surface

Source: `https://docs.getdaft.io/en/stable/distributed/` and `https://docs.getdaft.io/en/stable/architecture/` (verified 2026-05-15).

- `daft.set_runner_ray("ray://host:10001")` — single line to switch local → distributed; no code rewrite
- Flotilla scheduler on head node; one Ray actor per worker node running Swordfish
- Partitioning ≈ input file count (manual control via `repartition()`)
- `daft[ray]` extra requires `ray>=2.0.0,<2.56.0` (and `>=2.10.0` for client mode)
- **Kubernetes support on 2026 roadmap** (not yet shipped as of March 2026)
- **Critical caveat**: Ray client requires same Python minor + Daft version between client and server — couples our pin to user's cluster

### 2.7 Daft dependency conflicts with Nucleus

| Nucleus dep | Our pin | Daft 0.7.11 requires | Conflict? |
|---|---|---|---|
| `pyarrow` | `18.1.0` | `>=8.0.0,<24.0.0` | **No** |
| `pyiceberg` | `0.8.1` | `>=0.7.0,<=0.11.0,!=0.9.1,!=0.10.0` | **No** (but watch ADR-003 upgrade path) |
| `polars` | `1.18.0` | not required | **No** |
| `duckdb` | current | not required | **No** |
| Python | `>=3.11,<3.13` | `>=3.10` | **No** |
| `pylance` | none | `<0.40.0` (daft[lance]) | Pin at v0.5 ADR |
| `ray[client,data]` | none | `>=2.0.0,<2.56.0` | Pin at v0.5 ADR |

**Smallpond conflict** (covered in §3.7): Smallpond pins `polars~=0.20.9` — incompatible with our `1.18.0`. Cannot co-install Daft + Smallpond without isolation.

### 2.8 Known risks and gotchas

1. **Pre-1.0 churn**: `daft==0.7.11` ships `Development Status :: 4 - Beta` on PyPI (not Production/Stable). ~1 minor release/month historically. At v0.5 (Mo 20-28), we're ~12+ months stale — ~12 changelog reads required under Constraint #11. **HIGH risk, HIGH cost.**
2. **Telemetry on by default**: Scarf-based telemetry per PyPI README. Must disable with `DO_NOT_TRACK=true` at startup.
3. **Ray version coupling**: Ray client + Daft version must match across client/worker — pins become user-visible, complicating multi-user setups.
4. **`@daft.func` vs `@daft.func.batch`**: per-row UDF is the default; batch UDF (`@daft.func.batch`) is required for GPU efficiency. Wrong choice = silent per-row overhead.
5. **No equality-delete support**: Iceberg v2 tables with equality deletes throw errors — adapter must reject with `NucleusEngineError`.

### 2.9 Daft v0.5 decision (8-question gate)

1. **Maps to architectural layer?** Yes — L1 Engines (v4.1 §3.2) ✓
2. **Serves <30 min beachhead?** No — v0.1 beachhead is tabular Postgres → Iceberg; no multimodal needed. **Not for v0.1.** ✓ (deferred)
3. **Wrap possible?** Yes — pure wrap behind `ctx` SDK engine adapter. ✓
4. **No JVM?** Yes — Rust/Python. ✓
5. **Local-identical-to-prod?** Yes — `daft.set_runner_native()` locally, `daft.set_runner_ray()` on cluster. ✓
6. **Within 30K LOC?** Engine adapter ≤500 LOC. ✓
7. **Empirical telemetry trigger?** **Not yet** — await v0.3 beta telemetry showing ML-team multimodal demand. ⚠️
8. **Required for v0.1?** No. Defer to v0.5. ✓

**Verdict**: Question 7 is pending. Wrap at v0.5 gated on empirical demand. Do NOT add today.

---

## 3. Project 2: Smallpond (DeepSeek)

### 3.1 What Smallpond is and why it exists

Smallpond was released by DeepSeek AI in **February 2025** as an OSS framework for large-scale distributed data processing. It was built to solve DeepSeek's internal pain: pre-training dataset preparation at petabyte scale required distributed shuffles and transformations that single-node DuckDB couldn't handle, but Spark was too heavy and too slow to iterate.

**Core idea**: shard your data across a distributed file system; run per-shard DuckDB instances in parallel via Ray Core; collect and write results back via the same FS. No long-running services, no JVM, no catalog.

**Architecture** (per official docs at `https://deepseek-ai.github.io/smallpond/`):
- **Compute engine**: DuckDB (per shard, in-process, no inter-shard SQL joins across the network)
- **Scheduling**: Ray Core as task scheduler (`ray.remote` per partition)
- **Storage**: Parquet on a distributed/shared filesystem; designed around DeepSeek's in-house 3FS (Fire-and-Forget Filesystem), but also works with S3 + fsspec
- **Data model**: explicit partitions — users call `df.repartition(n)` / `df.repartition(n, hash_by="col")` manually

**License**: MIT ([GitHub](https://github.com/deepseek-ai/smallpond), README)
**Latest version (verified PyPI 2026-05-15)**: `smallpond==0.15.0` (released 2025-02-28) — **only two releases ever: 0.0.1 and 0.15.0**
**GitHub stars**: ~4,952 (as of 2026-05-15) — grew rapidly in Feb-Mar 2025 hype cycle; slowed since
**PyPI downloads (last month)**: 157 — extremely low, suggesting it's mostly a research/internal tool

### 3.2 How the DuckDB + Ray wiring works

Source: `https://deepseek-ai.github.io/smallpond/getstarted.html` and `https://pypi.org/project/smallpond/0.15.0/` (verified 2026-05-15).

```python
import smallpond

sp = smallpond.init()              # starts Ray locally or connects to cluster
df = sp.read_parquet("path/*.parquet")  # DataFrame = partition manifest
df = df.repartition(3, hash_by="host") # explicit partition assignment
df = df.map('a + b as c')          # SQL string → per-shard DuckDB query
df.write_parquet("path/to/output") # materialization per partition
```

Key architectural notes:
- **No distributed joins** across shards at the DuckDB level — SQL runs per partition independently. Cross-shard aggregations (e.g., global `GROUP BY`) require a repartition step followed by per-shard aggregation.
- **No Iceberg write support** — output is always Parquet; no catalog integration
- **No schema contracts** — Parquet files are the only agreement surface
- **Ray Dashboard** is the only observability tool

### 3.3 Performance claim

Source: `https://deepseek-ai.github.io/smallpond/` (verified 2026-05-15):

> "In the GraySort test, smallpond sorted 110.5 TiB of data in 30 minutes and 14 seconds on a 75-node cluster (50 compute + 25 storage nodes), achieving 3.66 TiB/min throughput."

**Important context for Nucleus**: This benchmark used DeepSeek's proprietary 3FS cluster — not a general S3/fsspec setup. Reproducing at this throughput on MinIO or S3 would require benchmarking under realistic Nucleus conditions. Do NOT cite this number for customer-facing material.

### 3.4 Production-readiness signals

| Signal | Value | Assessment |
|---|---|---|
| PyPI downloads/month | 157 | Extremely low — not widely adopted |
| Releases | 2 total (0.0.1 + 0.15.0) | Only one real release; no patch cadence |
| Last activity on PyPI | 2025-02-28 | ~15 months stale |
| GitHub stars | ~4,952 | High hype, low sustained community |
| Issues/PRs | Not accessible from docs | Unknown velocity |
| DeepSeek prod use | Yes — GraySort claim | Internal tool only; may diverge from public repo |
| Dependency freshness | `polars~=0.20.9` | **22+ minor versions behind current Polars 1.40.x** |

**Assessment**: The PyPI package is effectively abandoned. The public repo may still have internal development, but the external-facing release cadence suggests DeepSeek uses an internal fork. **Do NOT wrap this for production use today.**

### 3.5 Dependency conflicts with Nucleus

This is the critical blocker:

| Dep | Smallpond 0.15.0 requires | Nucleus requires | Conflict? |
|---|---|---|---|
| `polars` | `~=0.20.9` (pre-1.0!) | `==1.18.0` | **FATAL — cannot co-install** |
| `pyarrow` | `~=16.1.0` | `==18.1.0` | **FATAL — cannot co-install** |
| `duckdb` | `>=1.2.0` | current pin | Likely compatible |
| `pandas` | `>=1.3.4` | Nucleus excludes pandas | Transitive pull-in |
| `ray` | `>=2.10.0` | unpinned | OK |
| `GPUtil` | `>=1.4.0` | none | Linux GPU monitoring lib; Windows may fail |
| `py-libnuma` | `>=1.2` | none | **Linux-only NUMA binding — fails on Windows/macOS** |

`py-libnuma` is a Linux-only C extension for NUMA-aware memory allocation. **Nucleus runs on Windows (user's OS) and macOS. Smallpond 0.15.0 cannot be installed on this machine.**

### 3.6 Smallpond 8-question gate

1. **Maps to architectural layer?** Marginally — would be L1 Engine. ✓ (barely)
2. **Serves <30 min beachhead?** No. ✗
3. **Wrap possible?** Technically yes, but requires heavy isolation.
4. **No JVM?** Yes. ✓
5. **Local-identical-to-prod?** **No** — `py-libnuma` breaks on Windows/macOS. ✗
6. **Within 30K LOC?** Adapter only is fine. ✓
7. **Empirical telemetry trigger?** No. ✗
8. **Required for v0.1?** No. ✗

**Score**: 3 questions fail (2, 5, 7). **DEFER — do not wrap. Watch list only.**

### 3.7 When Smallpond might become relevant

If by v0.7+ (Mo 32+):
- Smallpond releases a version with modern `polars>=1.x` + `pyarrow>=18.x` deps
- Cross-platform support (macOS/Windows wheels) ships
- Sustained community uptake beyond 157 downloads/month
- Public performance benchmarks on S3/MinIO (not 3FS) are available
- No competing wrap target (Daft + Ray) has already proven itself at v0.5

Under those conditions, Smallpond's DuckDB-native compute model (single SQL engine throughout) is architecturally elegant for users who don't need multimodal and want minimal overhead. Re-evaluate with a fresh research pass at v0.7 planning time.

### 3.8 Smallpond vs Daft — which is the better "moderate distributed" tier?

| Criterion | Daft + Ray | Smallpond + Ray |
|---|---|---|
| SQL engine | Custom optimizer + DuckDB (for SQL API) | Per-shard DuckDB |
| Cross-shard joins | Yes (Flotilla ships data via Ray object store) | No — requires explicit repartition |
| Multimodal | Yes — native Image/Audio/Video types | No |
| Iceberg read/write | Yes — `daft.read_iceberg`, `df.write_iceberg` | No |
| Lance read | Yes — `daft.read_lance` | No |
| Windows support | Yes | No (`py-libnuma` blocks) |
| Dependency freshness | Modern (monthly releases) | Stale (polars 0.20.x) |
| Community | ~5.5k stars, active | ~5k stars, stagnant |

**Decision**: Daft + Ray is the better wrap for Nucleus's v0.5 moderate distributed tier. Smallpond offers no advantage that Daft doesn't also provide, and has worse compatibility and adoption signals.

---

## 4. Project 3: Polars Streaming + Polars Cloud

### 4.1 Polars streaming engine — what it is

Nucleus already uses `polars==1.18.0`. The streaming engine is a **built-in feature** of Polars, not a separate install. It processes data in bounded batches, enabling out-of-core execution on datasets larger than RAM.

**Current API** (verified `https://docs.pola.rs/user-guide/concepts/streaming/`, 2026-05-15):

```python
import polars as pl

# Activating streaming — pass engine="streaming" to collect()
q = (
    pl.scan_csv("large_file.csv")
    .filter(pl.col("sepal_length") > 5)
    .group_by("species")
    .agg(pl.col("sepal_width").mean())
)
df = q.collect(engine="streaming")   # ← this is the streaming API in current stable Polars

# Inspect the streaming plan before executing
q.show_graph(plan_stage="physical", engine="streaming")
```

**Note on API drift**: In Polars 1.18.0 (our pin), the streaming API was `collect(streaming=True)`. As of 1.40.x (current latest), it migrated to `collect(engine="streaming")`. The `collect(streaming=True)` syntax may still work in recent versions but check the deprecation status when upgrading. **NEEDS VERIFICATION** against pin before use.

**Sink API** (avoids materializing in memory entirely):
```python
lf.sink_parquet("output.parquet")   # streams to Parquet without RAM materialization
lf.sink_csv("output.csv")
lf.sink_ndjson("output.ndjson")
```

**`sink_iceberg()` (NEW in Polars 1.39.0)** — see §4.4 below.

### 4.2 Streaming engine coverage and limitations

Source: `https://docs.pola.rs/user-guide/concepts/streaming/` (verified 2026-05-15) and `docs/internal/research/polars.md` §7.6.

- **Coverage**: Many operations run in streaming mode — `filter`, `group_by`, `agg`, joins (some), projections, scans, `scan_iceberg`
- **Non-streaming fallback**: Some operations fall back to in-memory engine silently. Polars doesn't throw an error — it just switches to the in-memory engine for those nodes
- **How to check**: `lf.explain(engine="streaming")` or `.show_graph(plan_stage="physical", engine="streaming")` reveals which nodes are streaming vs in-memory
- **Churn**: Each Polars minor release adds/removes streaming-supported ops. **Always re-run plan inspection after a Polars upgrade.**
- **Polars 1.40.0 added**: lock-free memory manager with spill-to-disk — significant enhancement to the out-of-core story (verify against exact pin when upgrading)
- **1 TB claim**: Users report processing hundreds of gigabytes single-node with `engine="streaming"`. Official FAQ: "Users already report utilizing Polars to process hundreds of gigabytes of data on single (large) compute instance."

### 4.3 `collect_async()` — async DataFrame collection

Source: `https://docs.pola.rs/api/python/dev/reference/lazyframe/api/polars.LazyFrame.collect_async.html` and GitHub issue #18718 (verified 2026-05-15).

```python
import asyncio, polars as pl

async def main():
    lf = pl.scan_parquet("s3://bucket/data/*.parquet")
    df = await lf.collect_async()   # schedules collection in a thread pool
    # or: lf.collect_async(gevent=True) for gevent event loops

asyncio.run(main())
```

**Status**: Marked **unstable** — may change without breaking-change notice.

**Known issue** (GitHub #18718): `collect_async` has been reported to block the event loop in some cases. The bottleneck is that `LazyFrame` expression trees are constructed eagerly from Python before the async collection even begins. Use with caution in async orchestration pipelines.

**Nucleus relevance**: Low for v0.1–v0.3 (Dagster handles scheduling); may become relevant for v0.5 async AI Copilot pipelines. **DEFER until async orchestration need is proven.**

### 4.4 Polars Iceberg read + write — current state

**Read** (`pl.scan_iceberg`):
Source: `https://docs.pola.rs/api/python/stable/reference/api/polars.scan_iceberg.html` (verified 2026-05-15).

```python
pl.scan_iceberg(
    source,                      # PyIceberg Table, namespace.table_name, or metadata.json path
    snapshot_id=None,            # specific snapshot
    storage_options=None,        # S3/Azure/GCS creds
    catalog=None,                # PyIceberg Catalog or IcebergCatalogConfig
    reader_override=None,        # 'native' | 'pyiceberg' | None (auto)
    use_metadata_statistics=True, # unstable — use partition stats for pushdown
    fast_deletion_count=None,    # unstable — count from metadata
    use_pyiceberg_filter=True,   # push filters to PyIceberg
)
```

Note: `reader_override`, `use_metadata_statistics`, `fast_deletion_count` are **marked unstable** in current docs. Available in stable Polars 1.40.x; **NEEDS VERIFICATION** for which params exist in `polars==1.18.0`.

**Write — `df.write_iceberg()` (added in 1.24.0)**:
- Requires a `pyiceberg.Table` — Nucleus provides this
- Modes: `append` | `overwrite`
- Marked **unstable**
- **Partitioned writes NOT supported** as of 1.40.x
- Source: GitHub PR #15018

**Write — `lf.sink_iceberg()` (NEW, added in 1.39.0)**:
- **NOT available in our pin `polars==1.18.0`** — requires upgrade ADR
- Two-stage: sink Parquet via streaming engine → commit to Iceberg via PyIceberg
- Performance: ~2 GiB/s vs ~500 MiB/s for `write_iceberg` on large datasets (benchmark in PR #26799)
- **Partitioned writes NOT supported** in 1.39.0 either
- Marked **unstable**

**Implications for Nucleus**:
1. `pl.scan_iceberg` in `polars==1.18.0` works for read — confirmed in `docs/internal/research/polars.md`
2. `df.write_iceberg` exists in 1.18.0 but is NOT the right path — AMA uses PyIceberg directly for writes; Polars exit point is `df.to_arrow()` → PyIceberg
3. `sink_iceberg()` is the v0.3 out-of-core write path candidate — requires Polars upgrade ADR (1.18.0 → 1.39.0+, 21 minor versions, Hard Constraint #11 — needs changelog review)

### 4.5 Polars Cloud — managed Polars as a service

Source: `https://docs.pola.rs/polars-cloud/` and `https://docs.pola.rs/polars-cloud/faq/` (verified 2026-05-15).

**What it is**: A managed service by the Polars organization that runs the same Polars API on distributed compute via a closed proprietary distributed engine. Users write standard Polars queries, call `.remote(context=ctx)` to dispatch to the cloud.

```python
import polars as pl
import polars_cloud as pc

ctx = pc.ComputeContext(workspace="your-workspace", cpus=16, memory=64)

query = (
    pl.scan_parquet("s3://my-dataset/")
    .group_by("l_returnflag", "l_linestatus")
    .agg(avg_price=pl.mean("l_extendedprice"))
)

query.remote(context=ctx).sink_parquet("s3://my-dst/")  # ← dispatch API
```

**Pricing**: `$0.05 per vCPU/hour` (verified AWS Marketplace listing, 2026-05-15). 30-day free trial.

**Infrastructure model**: Polars Cloud deploys raw EC2 instances in the **user's own AWS account**. Data never leaves user's environment. Managed via `pc setup` which creates VPC, subnets, security groups, and IAM roles.

**Key FAQ confirmation** (verified `docs.pola.rs/polars-cloud/faq/`):
> "The distributed engine is only available in Polars Cloud. There are no plans to make it available in the open source project."

**Polars Cloud availability**: AWS only — "Other cloud providers and on-premises solutions are on the roadmap."

### 4.6 Why Nucleus must NOT integrate Polars Cloud

1. **Closed distributed engine**: the distributed engine is proprietary and AWS-only — violates Pillar #2 (Composable by Constitution) and conflicts with Pillar #5 (Friendly to giants, hostile to no-one)
2. **AWS lock-in**: Nucleus's beachhead uses MinIO (local S3-compatible). Polars Cloud requires a real AWS account and VPC — incompatible with local-first philosophy
3. **On-prem not supported**: per FAQ, on-prem is roadmap only. Nucleus users with airgapped environments cannot use it
4. **Overlap with Mode 2**: Nucleus already has a "yield to giants" pattern (`compute="databricks://..."` dispatch). Polars Cloud would add a third compute tier with no swap interface
5. **Dependency**: `polars_cloud` is a separate package — adds a dependency Nucleus doesn't need when Daft + Ray covers the distributed case for OSS users

**Do NOT recommend or integrate Polars Cloud into any Nucleus component.**

### 4.7 Polars streaming as the v0.3 out-of-core path

This is the **immediate, practical recommendation** for Nucleus:

At v0.3, when Nucleus begins handling larger-than-laptop datasets within the beachhead window (100 GB–5 TB), the correct path is:

```python
# In polars_engine.py / AMA
lf = pl.scan_iceberg(source_table, snapshot_id=snapshot_id)
lf = apply_transforms(lf)

# v0.3 upgrade: use streaming for large assets
result = lf.collect(engine="streaming")   # or collect(streaming=True) for 1.18.0
```

For write path, `sink_iceberg()` requires a Polars upgrade ADR (1.18.0 → 1.39.0+). Until that ADR is accepted, the write path stays `df.to_arrow()` → PyIceberg directly.

**DuckDB streaming alternative**: DuckDB also supports out-of-core via `SET memory_limit='8GB'; SET spill_dir='/tmp/duckdb_spill'` — this is the recommended approach for SQL-centric assets at v0.3 before introducing Polars streaming complexity. Much lower friction.

---

## 5. Cross-Cutting Patterns

### 5.1 Zero-copy + lazy evaluation convergence

All three projects converge on the same performance model:

| Pattern | Daft | Smallpond | Polars |
|---|---|---|---|
| Arrow-native memory | Yes (Rust core) | Via PyArrow interop | Yes (Rust core) |
| Lazy evaluation / query planning | Yes (LogicalPlan) | Partial (DAG of Ray tasks) | Yes (LazyFrame) |
| Vectorized execution | Yes (Swordfish) | Via DuckDB per shard | Yes (SIMD Rust) |
| Out-of-core / spilling | Yes (streaming native runner) | Via distributed FS + Ray | Yes (`engine="streaming"`) |
| Zero-copy UDFs | Yes (Arrow C Data Interface) | No (pickle via cloudpickle) | Via Arrow exit (`to_arrow()`) |

### 5.2 Ray as the distributed substrate

Both Daft and Smallpond use **Ray Core** as their distributed task scheduler. This is significant for Nucleus:
- Ray is a large optional dependency (~200 MB+ for full Ray; `ray[default]` adds dashboard, dashboard-agent, etc.)
- Pin coordination: both `daft[ray]` and `smallpond` require `ray>=2.10.0` — pinning Ray independently of Daft creates a potential conflict
- If Nucleus adds Ray at v0.5 for Daft, Smallpond becomes trivially easy to support from a dependency standpoint — but production maturity remains the blocker

### 5.3 DuckDB streaming for free

Before investing in Polars streaming or Daft at all, note that DuckDB already handles out-of-core natively:

```python
import duckdb
# Docs: https://duckdb.org/docs/operations/memory_management.html
conn = duckdb.connect()
conn.execute("SET memory_limit='8GB'")
conn.execute("SET threads=4")
conn.execute("SET enable_progress_bar=true")
# DuckDB will automatically spill to disk when memory_limit is reached
```

This is the **lowest-friction path** for Nucleus v0.3 out-of-core on SQL-centric assets. No new dependencies, no streaming-engine compatibility matrix, no API changes. Try this first.

---

## 6. Adoption Shortlist — Top 5 Decisions for Nucleus

| # | Decision | When | Action |
|---|---|---|---|
| **1** | Enable DuckDB `SET memory_limit` + `SET threads` in `ctx.config` | **v0.2 / v0.3** | 2-line change in DuckDB init; free out-of-core for SQL assets |
| **2** | Enable Polars `engine="streaming"` on large `LazyFrame` collects | **v0.3** | Guarded by asset size; upgrade `polars==1.18.0` ADR gates `sink_iceberg()` path |
| **3** | Open Polars upgrade ADR (1.18.0 → 1.39.0+) for `sink_iceberg()` | **v0.3 planning** | 21 minor versions; changelog review required; performance win is ~4x on write |
| **4** | Wrap Daft as optional engine for multimodal assets | **v0.5** | Gate: empirical ML-team demand in v0.3 beta telemetry; `docs/internal/research/daft.md` has full spec |
| **5** | Add `compute="ray://..."` dispatch option for Daft + Ray | **v0.5** | Gate: same as #4; surfaces as `@nucleus.asset(engine="daft", compute="ray://…")` |

**Explicit non-adoptions** (record here to prevent re-evaluation churn):
- Smallpond: DEFER until dependency freshness + cross-platform support resolved (v0.7+ re-evaluation)
- Polars Cloud: DO NOT integrate — closed engine, AWS-only, lock-in
- `collect_async()`: DEFER until async orchestration need is proven
- Daft as default engine (replacing DuckDB/Polars): NEVER for tabular beachhead

---

## 7. Special Focus: Multimodal AI Workloads — Do We Need Daft Now?

**PoC #5 finding**: external fresh-eyes tester reported tabular-only use case. v0.1 beachhead users are startup data teams doing Postgres → Iceberg ETL. No multimodal demand observed in v0.1.

**Future persona signal**: ML teams (v1.5+ persona per v4.1 §1.6) need:
- Embedding columns in assets (vector search for AI Copilot v0.5+)
- Image/audio/video transforms in pipelines (Daft's native value-add)
- Lance dataset reads (Daft is the canonical reader)

**Decision framework**:

| Timeline | Trigger | Action |
|---|---|---|
| v0.1–v0.2 (now) | None | No action — Polars Object columns work for rare edge cases |
| v0.3 beta | Telemetry shows >10% of assets use `pl.Object` columns with "image" / "embedding" in schema | Open Daft v0.5 ADR early |
| v0.5 (Mo 20-28) | Lance + AI Copilot lands per v4.1 §18.4 | Daft integration ADR goes live; wrap behind `engine="daft"` |
| v1.0+ | Daft 1.0 ships (stable); multimodal demand confirmed broad | Promote Daft to Tier 1, production-supported |
| Defer-forever | Multimodal demand never materializes in empirical telemetry | Keep Daft on watch list; never commit adapter LOC |

**Answer**: We do NOT need Daft now. We need a telemetry gate at v0.3 that fires if multimodal demand appears. The cost of not having Daft at v0.1–v0.3 is zero — no beachhead user needs it.

---

## 8. Special Focus: Smallpond Evaluation — 8-Question Gate Full Pass

**Context**: Smallpond is the most-hyped project in this evaluation (~5k GitHub stars in 2 weeks). The founder should have a clear verdict rather than a soft deferral.

**Full 8-question gate result**:

| Question | Smallpond answer | Pass? |
|---|---|---|
| Maps to architectural layer? | L1 Engine (marginally) | ✓ |
| Serves <30 min beachhead? | No | ✗ |
| Wrap possible? | Technically yes, but requires isolation layer | ⚠️ |
| No JVM? | Correct | ✓ |
| Local-identical-to-prod? | **No** — `py-libnuma` is Linux-only; fails on Windows/macOS | ✗ |
| ≤30K LOC? | Adapter only is fine | ✓ |
| Empirical trigger? | No | ✗ |
| Required for v0.1? | No | ✗ |

**Dependency conflict**: `polars~=0.20.9` is 22+ minor versions behind Nucleus's `polars==1.18.0`. Cannot co-install without virtualenv isolation.

**PyPI activity**: 157 downloads/month. Only 2 releases in project history, last one 2025-02-28. Effectively unmaintained as a public package.

**Verdict**: **DEFER indefinitely.** Not because the idea is bad — per-shard DuckDB + Ray is architecturally sound for pure tabular distributed processing. But the public package is stale, cross-platform support is broken, and the dependency conflict is severe. If by v0.7+ the project is actively maintained with modern deps and cross-platform wheels, re-evaluate. Until then, Daft + Ray serves the moderate-distributed need better in every measurable way.

**One potential exception**: If a Nucleus enterprise user at v1.0+ comes in with an existing 3FS/Linux-only cluster and a DeepSeek-style pre-training data pipeline, Smallpond becomes a reasonable per-customer adapter. That is not an OSS core feature.

---

## 9. Distributed Strategy Verdict

For Nucleus's "yield to giants" architecture (v4.1 §10.2):

```
Single-node path (v0.1–v0.3):
  DuckDB + Polars (current stack)
  ↓ DuckDB memory_limit + threads (v0.2) — out-of-core SQL, zero new deps
  ↓ Polars engine="streaming" (v0.3) — out-of-core DataFrame, existing dep

Moderate-distributed path (v0.5):
  Daft + Ray (gated on multimodal/ML demand telemetry from v0.3 beta)
  → surfaces as @nucleus.asset(engine="daft", compute="ray://...")
  → Mode 2 parallel to Databricks/Snowflake dispatch

True distributed path (v1.0+):
  Yield to giants — Databricks / Snowflake / Spark via compute= dispatch
  Iceberg portability (Mode 1) — user's data is already portable
  Federation (Mode 3) — Iceberg REST catalog (v2.0+)

Permanent defers:
  Smallpond — stale deps, broken cross-platform, no Iceberg, low adoption
  Polars Cloud — closed engine, AWS-only, lock-in
```

---

## 10. Open Questions for Founder

1. **DuckDB memory_limit**: Should this be a `nucleus.toml` setting (`[engine] memory_limit = "8GB"`) or auto-detected from system RAM at runtime? The latter is simpler for v0.2; the former gives power users control.

2. **Polars upgrade ADR**: `sink_iceberg()` requires a 21-minor-version upgrade (1.18.0 → 1.39.0+). Is the ~4x write performance improvement a priority for v0.3, or is `df.to_arrow()` → PyIceberg fast enough for beachhead data volumes (100 GB–5 TB)?

3. **Daft telemetry gate**: Which v0.3 beta metric triggers the v0.5 Daft ADR? Suggested: >10% of assets have schema fields with `pl.Object` dtype AND user-reported "multimodal" intent in opt-in telemetry. Is this gate too high or too low?

4. **compute= dispatch API**: Should `compute="ray://host:10001"` be a top-level `@nucleus.asset` parameter or an env-level config in `nucleus.toml`? The former is per-asset; the latter is per-project. v4.1 §10.2 is ambiguous on the surface level.

5. **Smallpond re-evaluation trigger**: If DeepSeek releases `smallpond==0.16.0+` with modern deps and cross-platform support, should there be an automatic calendar trigger (quarterly) to re-check? Or should this require a founder directive?

---

## 11. NEEDS VERIFICATION

| # | Claim | URL to check | Priority |
|---|---|---|---|
| 1 | Daft `collect(streaming=True)` vs `collect(engine="streaming")` syntax for 0.7.11 | `https://docs.getdaft.io/en/stable/api/` | HIGH — Daft native runner is streaming by default; no flag needed |
| 2 | `polars==1.18.0` streaming API: `collect(streaming=True)` vs `collect(engine="streaming")` | `https://docs.pola.rs/api/python/version/1.18/reference/lazyframe/api/polars.LazyFrame.collect.html` | HIGH — pin-specific |
| 3 | Polars `write_iceberg` vs `sink_iceberg` availability in 1.18.0 | Same URL | MEDIUM |
| 4 | Daft query planner — is Substrait used for plan interchange? | `https://docs.getdaft.io/en/stable/architecture/` | LOW |
| 5 | Smallpond Linux-only `py-libnuma` — does 0.15.0 install on macOS? | Try `pip install smallpond` on macOS | HIGH — if macOS works, partially unblocks |
| 6 | Polars Cloud `.remote()` API — can it use our PyIceberg filesystem catalog (not just S3 URIs)? | `https://docs.pola.rs/polars-cloud/` | LOW — moot since we're not integrating |
| 7 | Daft 0.7.11 `@daft.func.batch` GPU memory management — does it respect `SET memory_limit`? | `https://docs.getdaft.io/en/stable/api/udf/` | LOW — v0.5 concern |
| 8 | Smallpond active internal development at DeepSeek — is a v0.16+ coming? | Monitor `https://github.com/deepseek-ai/smallpond/commits/main` | MEDIUM |

---

## 12. References

All URLs verified 2026-05-15 unless noted.

### Daft
- Docs root: `https://docs.getdaft.io/en/stable/`
- Architecture: `https://docs.getdaft.io/en/stable/architecture/`
- Distributed: `https://docs.getdaft.io/en/stable/distributed/`
- Benchmarks: `https://docs.getdaft.io/en/stable/benchmarks/`
- Iceberg connector: `https://docs.getdaft.io/en/stable/connectors/iceberg/`
- Roadmap (March 2026): `https://docs.getdaft.io/en/stable/roadmap/`
- PyPI: `https://pypi.org/project/daft/0.7.11/`
- GitHub: `https://github.com/Eventual-Inc/Daft`
- AI benchmarks blog: `https://www.daft.ai/blog/benchmarks-for-multimodal-ai-workloads`

### Smallpond
- Official docs: `https://deepseek-ai.github.io/smallpond/`
- Getting started: `https://deepseek-ai.github.io/smallpond/getstarted.html`
- PyPI: `https://pypi.org/project/smallpond/0.15.0/`
- GitHub: `https://github.com/deepseek-ai/smallpond`

### Polars
- Streaming user guide: `https://docs.pola.rs/user-guide/concepts/streaming/`
- `scan_iceberg` API: `https://docs.pola.rs/api/python/stable/reference/api/polars.scan_iceberg.html`
- `collect_async` API: `https://docs.pola.rs/api/python/dev/reference/lazyframe/api/polars.LazyFrame.collect_async.html`
- `collect_all_async`: `https://docs.pola.rs/api/python/stable/reference/api/polars.collect_all_async.html`
- Cloud storage: `https://docs.pola.rs/user-guide/io/cloud-storage/`
- Polars Cloud intro: `https://docs.pola.rs/polars-cloud/`
- Polars Cloud FAQ: `https://docs.pola.rs/polars-cloud/faq/`
- Polars Cloud billing: `https://docs.pola.rs/polars-cloud/organization/billing/`
- Polars Cloud AWS infra: `https://docs.pola.rs/polars-cloud/providers/aws/infra/`
- Polars Cloud AWS Marketplace: `https://aws.amazon.com/marketplace/pp/prodview-xrx4wmwctfrcc`
- `write_iceberg` PR: `https://github.com/pola-rs/polars/pull/15018`
- `sink_iceberg` PR: `https://github.com/pola-rs/polars/pull/26799`
- `collect_async` issue #18718: `https://github.com/pola-rs/polars/issues/18718`
- Latest release (1.40.1, 2026-04-22): `https://github.com/pola-rs/polars/releases/tag/py-1.40.1`

---

## 13. Hallucination Log

The following AI-memory claims were evaluated and corrected during this research pass. Appended to `docs/internal/research/ai_hallucinations.md` as well.

| Claim | Reality | Detection |
|---|---|---|
| Polars streaming enabled via `collect(streaming=True)` in all Polars 1.x | API changed to `collect(engine="streaming")` in 1.40.x stable docs; 1.18.0 may use old syntax | Docs check on streaming user guide |
| `daft.DataFrame.collect(num_partitions=...)` distributes semantics | No such parameter; `daft.set_runner_ray()` is the distribution mechanism | Not in official API |
| Smallpond uses Ray Data (not Ray Core) | Smallpond uses Ray Core only — `ray.remote` task scheduling; not Ray Data Datasets API | PyPI deps + official docs |
| `polars_cloud` distributed engine will be open-sourced | Official FAQ explicitly states "no plans to make it available in the open source project" | Docs verification |
| Polars `sink_iceberg` is available in 1.18.0 | Added in 1.39.0 — not in our pin | GitHub PR #26799 merged March 2026 |

---

*Research model: Claude Sonnet 4.6 (Researcher tier fallback per AGENTS.md §11.14; Gemini 3.1 Pro was unavailable in current runtime).
Last verified: 2026-05-15. Re-verify when opening v0.5 Daft ADR, v0.3 Polars streaming/sink_iceberg upgrade ADR, or when Smallpond releases v0.16+.*
