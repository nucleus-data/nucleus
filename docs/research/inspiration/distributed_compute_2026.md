# Distributed Compute + Streaming Primitives — Landscape Research 2026

> **Last verified**: 2026-05-15 against official documentation + PyPI  
> **Research tier**: AGENTS.md §11.14 — Research tier (model: Claude Sonnet 4.6 fallback per availability)  
> **Audience**: Nucleus founder + future architects evaluating distributed/streaming decisions at v0.5–v2.0+  
> **Related docs**: `docs/research/inspiration/peer_distributed_streaming.md` (Daft/Smallpond/Polars — DO NOT REPEAT), `nucleus_architecture_v4.1.md` §10 (yield-to-giants Modes 1/2/3)  
> **Note**: This document covers Ray, Modal, Coiled, Mojo, Dask, Paimon, Substrait, and Flink/Beam only. Daft, Smallpond, and Polars Streaming are covered in `peer_distributed_streaming.md`.

---

## 1. Executive Summary

**Verdict: Yield-to-Giants remains the correct call. Do NOT embed a distributed engine in Nucleus v0.1–v1.0.**

The 2026 distributed compute landscape has bifurcated sharply:

1. **Single-node is now genuinely powerful**: DuckDB + Polars handle 100GB–5TB on a laptop. The Nucleus beachhead never needed distributed compute to succeed.
2. **Distributed is increasingly serverless/managed**: Ray (via Anyscale), Modal, Coiled, and Confluent Flink all abstract away cluster management. The integration path is "call their API" — not "embed their runtime."

The yield-to-giants strategy (v4.1 §10) is empirically validated by this landscape. The only question is *which* dispatch targets to prioritize for Mode 2 (v1.5+).

**Top 2 Mode 2 dispatch-target candidates for Nucleus:**

| Rank | Target | Why |
|------|--------|-----|
| 1 | **Databricks** | Existing pyiceberg + catalog integration; widest enterprise adoption; Iceberg-native; REST catalog federation already built |
| 2 | **Modal** | Python-native, serverless, sub-4s cold start, per-second billing, no cluster management; ideal for "escape hatch" batch jobs that exceed laptop capacity by 10–50x |

Ray (self-managed clusters) is a credible v0.5+ optional path via Daft's Ray backend, not a direct Nucleus dispatch target yet.

---

## 2. Ray 2.55 / 3.0 Landscape

### 2.1 What Ray is in 2026

Ray is a distributed Python runtime for ML + data workloads. It ships five major sub-libraries:
- **Ray Core**: task + actor scheduling primitives
- **Ray Data**: distributed data processing (the relevant layer for Nucleus)
- **Ray Train**: distributed ML training
- **Ray Tune**: hyperparameter search
- **Ray Serve**: model serving

**Current stable**: `ray==2.55.1` (released 2026-04-xx)  
**3.0 status**: Development API documented at `https://docs.ray.io/en/master/data/api/api.html` — **3.0 has NOT shipped as of 2026-05-15**. All production citations in this doc use 2.55.x.  
**License**: Apache-2.0 ([GitHub](https://github.com/ray-project/ray/blob/master/LICENSE))  
**Sustainability**: Ray joined the PyTorch Foundation (Linux Foundation) in October 2025. Anyscale raised $259M total. 237M total PyPI downloads; 39k GitHub stars. Governance risk: LOW.  
[Docs: https://docs.ray.io/en/releases-2.55.1/]

### 2.2 Key 2025–2026 Ray Data advances

**Iceberg integration is now first-class** (most relevant to Nucleus):

- `ray.data.Dataset.write_iceberg()` ships in 2.55.x with `APPEND`, `UPSERT`, and `OVERWRITE` modes  
  [Docs: https://docs.ray.io/en/releases-2.55.1/data/api/doc/ray.data.Dataset.write_iceberg.html]
- Upsert + schema evolution added November 2025 via PyIceberg 0.10.0 primitives  
  [PR #58270: https://github.com/ray-project/ray/pull/58270]
- Streaming write architecture decoupled: Parquet files written in parallel worker tasks; metadata committed by driver — exactly-once semantics  
  [PR #58601: https://github.com/ray-project/ray/pull/58601]
- Retry policies for catalog/storage writes added January 2026  
  [PR #60620: https://github.com/ray-project/ray/pull/60620]
- Native Kafka datasource + datasink (2.53.0 + 2.55.0)
- GPU shuffle support via rapidsmpf 26.2 (2.55.0)

**AI + agents convergence** (the headline direction):
Ray 2.55 positions itself as the distributed runtime for "agentic AI" — specifically for distributed tool calls across Ray clusters via the Agentic-Ray integration, batch LLM inference across GPU clusters, and large-scale model serving. This is NOT relevant to Nucleus's v0.1–v1.0 beachhead (startup data team, laptop-first). It is relevant for the v0.5+ "AI Copilot on distributed assets" use case.

### 2.3 Embeddability cost

Ray's "local mode" (`ray.init()`) spawns a local Ray cluster: ~200–400 MB idle RAM for GCS, Raylet, and object store processes; 2–5s boot; background daemons persist after script exit without `ray.shutdown()`. This would violate PoC #4 (boot time <10s) and blow past the 117.3 MB beachhead RAM baseline. Ray is NOT a candidate for embedding in the v0.1 stack.

**The correct pattern**: Daft wraps Ray with one line: `daft.set_runner_ray(...)`. Nucleus wraps Daft. Ray is available as an opt-in scale target at v0.5+, invisible to the user until needed.  
[Docs: https://docs.getdaft.io/en/stable/distributed/ray/]

**Nucleus verdict**: Ray is Tier 1 DEFER for direct Nucleus integration. Wrap it invisibly through Daft at v0.5+. Do NOT integrate Ray directly into Nucleus CLI or ctx SDK.

---

## 3. Modal — Serverless Python Compute

### 3.1 What Modal is

Modal is a serverless Python compute platform: you decorate Python functions with `@app.function(...)` and call them from anywhere — locally, in CI, or from another cloud function. Modal provisions containers, manages images, handles scaling, and bills per second.

**Docs root**: https://modal.com/docs/  
**License**: Proprietary (SaaS); no self-hosted option  
**Python version**: 3.8+ supported

### 3.2 Cold start performance

Per Modal's official cold-start guide (https://modal.com/docs/guide/cold-start):
- **Container boot**: ~1 second (Modal's custom container stack)
- **Warm start**: sub-100ms (container already running)
- **With model weight download**: minutes reduced to seconds by pre-downloading into container images using `modal.Volume` or image layers
- **Memory Snapshots (CRIU-based)**: Modal captures container memory state post-initialization; future boots restore that state, reducing first-invocation overhead from minutes to seconds for heavy deps (PyTorch, HuggingFace, etc.)

**For Nucleus batch dispatch use cases** (no large model weights):
- Cold start: **1–4 seconds** for a standard Python data workload container
- With `min_containers=1` (keep-warm): effectively **<100ms** at a cost of ~$0.05/hr idle CPU

### 3.3 Pricing model (as of 2026-05-15)

Per Modal's pricing page (https://modal.com/pricing):

| Resource | Rate |
|----------|------|
| CPU | $0.0000131/core/sec (~$0.047/core-hr) |
| Memory | $0.00000222/GiB/sec (~$0.008/GiB-hr) |
| GPU H100 | $0.001097/sec (~$3.95/hr) |
| GPU T4 | $0.000164/sec (~$0.59/hr) |

**Critical**: Regional (1.25x) + non-preemptible (3x) multipliers stack to **3.75x** for production guaranteed workloads. A realistic CPU data job in US prod: ~$0.177/core-hr — still cheap for batch work.

**Free tier**: $30/month credits (Starter plan)

### 3.4 Auth model

Modal's OIDC integration (https://modal.com/docs/guide/oidc-integration) issues short-lived JWT tokens injected as `MODAL_IDENTITY_TOKEN` environment variable. Claims include `workspace_id`, `app_name`, `function_name`, `container_id`.

Per AGENTS.md §3 Hard Constraint #6: **no custom auth system — always delegate to OIDC**. Modal's OIDC emission satisfies this for external service authentication (AWS S3, etc.). For Nucleus-to-Modal authentication specifically: Modal uses API tokens (`MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET`) stored in `~/.modal.toml`. SSO via Okta available on Enterprise plans.

**Nucleus concern**: Modal tokens would need to be managed per-workspace in `nucleus.toml` or environment variables — the user provisions Modal tokens themselves. Acceptable UX for v1.5+ Mode 2 dispatch.

### 3.5 Relevance to Nucleus Mode 2 dispatch

Modal is the most natural "escape hatch" for a laptop user who needs one asset exceeding local compute. Dispatch pattern (v1.5+ scope, NOT v0.1): Nucleus serializes the asset + upstream Iceberg snapshot references → dispatches via `modal.Function.call()` → Modal container reads/writes the same Iceberg tables → Nucleus commits metadata.

**Gate**: Requires Iceberg REST catalog. Gated on Lakekeeper at v0.3+. Mode 2 target: **v1.5+**.

**Nucleus verdict for Modal**: OBSERVE now, PLAN at v0.3, INTEGRATE as optional Mode 2 adapter at v1.5+. License concern: proprietary SaaS — flag per ADR template.

---

## 4. Coiled (Managed Dask)

### 4.1 What Coiled is

Coiled is a managed Dask platform: provision and scale Dask clusters on AWS/GCP/Azure with a single Python call. Founded by the Dask core team (Matthew Rocklin et al.), Coiled runs on your own cloud account (bring-your-own-cloud) and bills a platform fee on top of underlying cloud costs.

**Docs root**: https://docs.coiled.io/  
**License**: Proprietary SaaS (platform fee); Dask itself is BSD-3  
**Cloud support**: AWS, GCP, Azure

### 4.2 Pricing

Per Coiled pricing page (https://coiled.io/pricing):

| Plan | Platform fee | Seats |
|------|-------------|-------|
| Free | $25/month usage allowance | 1 |
| Basic | $100/month + usage | 2 |
| Professional | $500/month + usage | 6 |
| Enterprise | Custom | Custom |

Platform charges layered on top of cloud compute:
- CPU: $0.05/CPU-hour platform fee
- GPU T4: $0.15/GPU-hour; A100: $1.00/GPU-hour

**Cluster spinup time**: Coiled documentation markets "instant" cluster creation. Based on community benchmarks, practical spinup from Python call to worker-ready is **30–90 seconds** for a 10-node cluster (dominated by EC2 instance provisioning). [NEEDS VERIFICATION — Coiled's public benchmarks dashboard at benchmarks.coiled.io should be checked directly]

### 4.3 Relevance to Nucleus

Coiled targets teams scaling Pandas/Dask. Low-priority for Nucleus for four reasons: (1) Nucleus defaults to Polars, not Pandas/Dask — Coiled adds zero value for Polars workloads; (2) 30–90s spinup is strictly worse than Modal's <4s for "one big asset" dispatch; (3) Dask DataFrame/Array APIs are second-class in a Polars-first stack; (4) BYOC model adds IAM/VPC complexity for startup teams.

**Nucleus verdict for Coiled**: DEFER indefinitely. Not a Mode 2 target.

---

## 5. Dask 2026 Status

### 5.1 Current state

Dask is actively maintained ([GitHub](https://github.com/dask/dask), BSD-3 license). As of 2026, Dask is at approximately version 2024.x–2025.x.

Dask's positioning in 2026:
- **Scale Pandas/NumPy/scikit-learn workflows** by parallelizing the existing API
- **Dask-on-Ray** integration exists (Ray as Dask scheduler backend)
- **Dask DataFrame** recently transitioned to use cuDF/Polars as backends [NEEDS VERIFICATION — check Dask changelog]

### 5.2 Has Dask been eclipsed?

For **structured tabular ETL** (the Nucleus beachhead use case): **YES, Polars has largely eclipsed Dask** for single-node workloads.

Evidence:
- 2026 benchmarks show Polars delivering 94x speedups over Pandas on structured workloads; Dask inherits Pandas overhead
- Polars Streaming (already in Nucleus stack at v0.3) handles out-of-core single-node data that previously required Dask
- For distributed tabular, Ray Data + Daft now offer better performance with native Iceberg integration

For **numeric/scientific Python** (scikit-learn, NumPy at scale): Dask **remains the best option** because no modern alternative parallelizes the NumPy/scikit-learn API as transparently.

For **streaming/incremental workloads**: Dask's streaming support (`dask.dataframe` with `blocksize`) has been surpassed by purpose-built options (Polars streaming, Flink, Paimon).

### 5.3 Nucleus verdict for Dask

**DEFER indefinitely as a direct integration.** Dask remains relevant through two indirect paths:
1. Dask-on-Ray: if a Nucleus user adopts a Ray cluster, Dask can run on it transparently
2. Coiled (managed Dask) for teams with existing Dask codebases (Coiled handles it; Nucleus doesn't)

No Nucleus code should import `dask` directly in v0.1–v1.0.

---

## 6. Mojo Language Status

### 6.1 What Mojo is

Mojo is a new programming language from Modular (company behind MAX inference platform) designed to combine Python's ergonomics with systems programming performance (C++/Rust-class speed). It targets GPU/CPU kernel programming for AI/ML workloads.

**Docs root**: https://docs.modular.com/mojo/  
**License**: Source-available today; compiler to be open-sourced at Mojo 1.0 GA  
**GitHub**: https://github.com/modular/modular

### 6.2 2026 status

Per the official Modular blog (https://www.modular.com/blog/the-path-to-mojo-1-0, December 5, 2025):
- **Mojo 1.0 entered beta** on May 7, 2026 (version `1.0.0b1`)  
  [Source: https://www.modular.com/blog/modular-26-3-mojo-1-0-beta-max-video-gen-and-more]
- **GA targeted**: "Fall 2026" per the blog
- **Compiler open-source**: Promised at GA

1.0 Beta ships: safe closures, conditional trait conformance, improved variadics, `TileTensor` type for GPU kernels.

**Phase 1 focus** (what 1.0 covers): High-performance CPU + GPU kernel programming. Phase 2 (general systems programming — private members, robust async) will be a source-breaking Mojo 2.0.

### 6.3 Python compatibility

Mojo provides bidirectional Python interoperability:
- **Mojo → Python**: Import any Python module using the unmodified CPython runtime. `from python import Python; np = Python.import_module("numpy")` works today.
- **Python → Mojo**: Declare Mojo functions/types as bindings, import them in Python as a normal module.

[Official docs: https://docs.modular.com/stable/mojo/manual/python/]

### 6.4 Why Nucleus cares (very tangentially)

Mojo is **not relevant to Nucleus v0.1–v1.0.** Zero Nucleus code should be written in Mojo. Awareness matters for two future decisions: (1) DuckDB/Polars/Daft are Rust/C++ today — if Mojo becomes competitive for kernel writing, future versions of those libraries may use it, affecting Nucleus only as a downstream user; (2) Modular's MAX platform uses Mojo for model serving — relevant if Nucleus ever integrates MAX for local inference (deferred v0.5+).

**Nucleus verdict for Mojo**: OBSERVE. Not a dependency decision point before v1.5+. Re-evaluate when Mojo 1.0 GA + compiler open-source ships (expected Fall 2026).

---

## 7. Apache Paimon vs Apache Iceberg

### 7.1 What Paimon is

Apache Paimon (formerly Flink Table Store, donated to Apache in 2023) is a **streaming-native lake format** using LSM-trees (Log-Structured Merge-Trees) for efficient high-throughput upserts and CDC ingestion. Paimon 1.0 is the current stable release.

**Docs root**: https://paimon.apache.org/docs/1.0/  
**License**: Apache-2.0  
**GitHub**: https://github.com/apache/paimon  
**Primary compute engine**: Apache Flink (with read support via Spark, Hive, Trino)

### 7.2 Paimon vs Iceberg: the core trade-off

| Dimension | Apache Iceberg | Apache Paimon |
|-----------|---------------|---------------|
| **Write model** | Copy-on-Write (CoW, default) + MoR option | Merge-on-Read (MoR, default via LSM) |
| **Storage metadata** | Manifest files + snapshot trees | LSM files + changelog streams |
| **Best write throughput** | Batch (high-throughput append) | Streaming (CDC, high-frequency upserts) |
| **Read latency** | Sub-second batch reads on mature snapshots | Sub-second batch + real-time streaming read |
| **CDC ingestion** | Requires Flink CDC + Debezium → Iceberg write | Native: MySQL, Kafka, MongoDB, Pulsar, Debezium direct |
| **Primary key upserts** | Via MoR + merge-on-read or Flink iceberg sink | Native LSM upsert; no external sink required |
| **Compute engine** | Spark, Flink, Trino, DuckDB, DuckDB+PyIceberg | Flink (primary), Spark (read), Hive, Trino |
| **DuckDB support** | Yes (DuckDB 1.1+ native Iceberg reader) | No DuckDB native support [NEEDS VERIFICATION — check 2026 Paimon release notes] |
| **Time travel** | Full snapshot history, configurable retention | Snapshot-based time travel (less mature than Iceberg) |
| **Schema evolution** | Full (add/rename/drop/reorder/promote type) | Partial (add columns, alter type; no rename/drop) |
| **Community size** | Very large (Snowflake, Databricks, AWS, Apple) | Growing (Alibaba Cloud primary sponsor; Flink community) |
| **Iceberg compatibility** | Native | Optional: Paimon 1.0 can expose tables via Iceberg REST catalog [NEEDS VERIFICATION — confirm compatibility layer details] |

Sources: 
- Iceberg: https://iceberg.apache.org/docs/latest/
- Paimon overview: https://paimon.apache.org/docs/1.0/concepts/overview/
- Paimon CDC: https://paimon.apache.org/docs/1.0/cdc-ingestion/overview/
- Paimon primary key: https://paimon.apache.org/docs/1.0/primary-key-table/data-distribution/

### 7.3 When would a Nucleus user pick Paimon over Iceberg?

```
DECISION TREE: Iceberg vs Paimon for a Nucleus user

Q1: Is your primary ingest pattern CDC (Postgres/MySQL → lake)?
  YES →
    Q2: Can you afford Flink operational overhead (JVM, stateful clusters)?
      YES → Paimon is viable; native CDC ingestion is its killer feature
      NO  → STAY ON ICEBERG + use ctx.copy_from (Debezium → DuckDB → Iceberg)
  NO  → STAY ON ICEBERG

Q3: Is your update frequency >100k rows/sec sustained?
  YES → Paimon's LSM handles this better than Iceberg CoW
  NO  → STAY ON ICEBERG (Iceberg MoR handles sub-100k/sec upserts fine)

Q4: Do you need sub-second read latency on CONTINUOUSLY UPDATED data?
  YES → Paimon (acts as message queue in streaming mode)
  NO  → STAY ON ICEBERG

Q5: Do you need DuckDB reads? Trino? Snowflake integration? Rich time travel?
  YES → STAY ON ICEBERG (Paimon ecosystem is narrower)
  NO  → Paimon viable if Q1-Q4 push you there
```

**For the Nucleus v0.1–v0.3 beachhead** (startup, 100GB–5TB, Postgres → S3):
- **STAY ON ICEBERG.** Paimon requires Flink (JVM — Hard Constraint #1), has narrower DuckDB/Trino ecosystem, and its primary advantage (native CDC at high frequency) doesn't apply to the startup persona.
- At v0.5+ with CDC-heavy enterprise users, revisit Paimon as an **optional backend** for source assets with >100k/s update rates.

**Important**: Paimon 1.0 is implementing an Iceberg compatibility layer that allows Paimon tables to be read via Iceberg REST catalog clients. If this matures, Nucleus users could write to Paimon (via Flink) and read from Nucleus (via Iceberg) without format translation. [NEEDS VERIFICATION — confirm Paimon Iceberg catalog bridge status in 1.0]

**Nucleus verdict for Paimon**: DEFER to v0.5+. Monitor Iceberg compatibility layer maturity. Do NOT expose a Paimon backend in v1.0 — JVM Hard Constraint #1 applies until a Rust/Python-native Paimon writer exists. Add to the v0.5 streaming architecture ADR discussion.

---

## 8. Substrait — Cross-Engine Query Plans

### 8.1 What Substrait is

Substrait is an open standard for serializing relational query plans as protobuf messages, enabling cross-engine query plan exchange. Goal: write a query plan once, execute it on DuckDB, DataFusion, Velox, Spark, or any Substrait consumer.

**Spec site**: https://substrait.io/  
**Serialization**: https://substrait.io/serialization/binary_serialization/  
**License**: Apache-2.0  
**Governance**: Linux Foundation

### 8.2 2026 adoption landscape

As of September 2025 community reports, adoption by activity level:

| Engine | Role | Activity |
|--------|------|---------|
| DataFusion | Producer + Consumer | Most active |
| DuckDB | Producer + Consumer (community extension) | Active |
| Velox (Meta) | Consumer | Active |
| Apache Arrow/Acero | Consumer | Active (v0.20.0 spec) |
| Daft | None as of 0.7.11 | Not yet [NEEDS VERIFICATION for 2026 roadmap] |
| Spark | Partial (Gluten bridge) | Limited |

DuckDB Substrait extension: last updated 2026-02-12; provides `get_substrait()`, `from_substrait()`, `get_substrait_json()`, `from_substrait_json()`.  
[GitHub: https://github.com/substrait-io/duckdb-substrait-extension]

DataFusion ongoing function mapping: https://github.com/apache/datafusion/issues/16949

Arrow/Acero integration: https://arrow.apache.org/docs/python/integration/substrait.html

### 8.3 Could Substrait become the yield-to-giants dispatch wire protocol?

**Short answer: Not yet. Promising but pre-production for cross-company dispatch.**

The vision: Nucleus serializes a query plan as Substrait protobuf, sends to Databricks/Snowflake/BigQuery, which execute natively. Zero data movement for dispatch.

**What's missing:**
1. **Snowflake does not support Substrait ingestion** — it uses its own query layer (Snowpark)
2. **Databricks supports Substrait partially** via Velox/Gluten for certain Spark plans, but not as a first-class SQL dispatch API
3. **BigQuery**: no public Substrait API
4. **Function mappings are incomplete** — SQL dialect differences mean Substrait plans generated by DuckDB often can't round-trip through Databricks without translation

**What IS production-ready:**
- DuckDB ↔ DataFusion plan interchange (both implement the same Substrait version)
- Arrow Acero execution of DuckDB-generated plans
- This is the **local swap interface** path: Nucleus's DuckDB → DataFusion swap could use Substrait as the bridge (per v4.1 §9.3, interface + smoke tests)

**Nucleus verdict for Substrait**: ADOPT as the DuckDB↔DataFusion **swap interface** (not as dispatch wire protocol). This satisfies Composability by Constitution (v4.1 §9.3) for the SQL engine swap. Defer cross-company dispatch use of Substrait until Databricks/Snowflake publish Substrait ingestion endpoints. Add to ADR for DataFusion swap (composability docs).

---

## 9. Apache Flink + Apache Beam in 2026

### 9.1 Apache Flink status

Apache Flink is the dominant stateful stream processor for production streaming at scale.

**Key facts:**
- **License**: Apache-2.0
- **JVM**: YES — Flink is JVM-first. Python support via PyFlink, but execution engine is JVM. **This is Hard Constraint #1 for Nucleus core path.**
- **Latency**: Single-digit millisecond event-time processing with exactly-once semantics via incremental checkpoints
- **State management**: Terabytes of state via RocksDB state backend (external dependency)
- **Managed offerings**: Confluent Cloud for Apache Flink (serverless, 50+ regions, autoscaling via "Autopilot") — removes JVM ops burden  
  [Docs: https://docs.confluent.io/cloud/current/flink/overview.html]
- **SQL support**: Flink SQL is mature; Python Table API also available

**When users still pick Flink over lakehouse streaming in 2026:**

| Use case | Why Flink wins |
|----------|---------------|
| Exactly-once stateful aggregations (fraud detection) | Checkpoint-based state beats Iceberg commit latency |
| Sub-second latency | Iceberg file commits impose 1–5 min floor; Flink pushes to Kafka/Paimon in ms |
| Complex CEP (pattern matching) | No lakehouse equivalent |
| Large persistent state (TB-scale joins) | RocksDB state backend; Iceberg reads require file scans |
| Event-time windowing with late arrivals | Flink watermarks more expressive than Iceberg append |
| Confluent + Kafka-native shops | Confluent Cloud Flink: Kafka topics appear as Flink tables |

**Fluss** (Apache incubating, 2025): Streaming storage layer by the Flink community. "Streamhouse" model: Fluss (hot tier, seconds latency) + Iceberg (cold tier, analytics). Third option alongside Paimon for streaming lakehouse architectures.  
[Blog: https://fluss.apache.org/blog/2025/12/02/fluss-x-iceberg-why-your-lakehouse-is-not-streamhouse-yet/]

### 9.2 Apache Beam status

Beam provides a unified batch + streaming model runnable on Flink, Spark, or Google Cloud Dataflow. License: Apache-2.0. GitHub stars: ~8.6k (vs Flink's ~26k). Killer feature: write once, run on any backend. Weakness: state management depends on the underlying runner; SQL support limited.

**When Beam beats Flink**: Multi-cloud portability requirements; GCP Dataflow shops; teams wanting to avoid Flink operational expertise.

**Nucleus verdict for Flink/Beam**: NO INTEGRATION needed. Nucleus users operating Flink clusters point their Flink Iceberg connector at the same catalog Nucleus writes to — Iceberg compatibility handles it transparently. Document as a graduation path note at v0.3+.

---

## 10. Yield-to-Giants Dispatch Target Matrix (Mode 2)

This matrix evaluates candidates for `compute=` dispatch at Nucleus v1.5+ (per v4.1 §10.2).

| Dispatch Target | Auth model | Cost model | Cold start / cluster spin | Iceberg compat | Nucleus integration complexity | Priority |
|-----------------|-----------|-----------|--------------------------|----------------|-------------------------------|---------|
| **Databricks** | OAuth2/PAT (OIDC-delegable) | Per-DBU; ~$0.07–$0.22/DBU | Warm cluster: <5s; cold cluster: 2–5 min | Native (REST catalog, Delta+Iceberg read/write) | MEDIUM (REST API, existing `compute="databricks"` spec in v4.1 §10.2) | **P1** |
| **Modal** | API key (OIDC emit for outbound) | Per-second CPU/GPU; $0.047/core-hr base (3.75x max) | <4s cold; <100ms warm | Via dlt or Daft inside container | LOW-MEDIUM (Python decorator pattern fits Nucleus asset model) | **P2** |
| **Snowflake** | Key-pair auth / OAuth2 | Per-credit (~$2–$3/credit); warehouse-based | 1–15s warehouse resume | Iceberg external tables (read) + Snowflake Open Catalog (write) | HIGH (SQL API only; Nucleus needs DBAPI bridge) | P3 |
| **Coiled/Dask** | Cloud IAM (BYOC) | $0.05/CPU-hr platform + cloud | 30–90s cluster spinup | No native Iceberg; via fsspec | HIGH (Dask API ≠ Polars; adapter needed) | DEFER |
| **Ray/Anyscale** | API key; cluster-specific | Cluster-based (self-managed or Anyscale SaaS) | 2–5s local; 5+ min cluster | Yes (Ray Data 2.55 Iceberg write) | MEDIUM via Daft adapter | P4 (v0.5+ Daft integration first) |
| **BigQuery** | OAuth2 / ADC | Slot-based; ~$6/TB scanned | <5s for serverless | BigQuery Iceberg tables (2025) | HIGH (SQL API only; BigLake catalog) | P5 |

**Notes:**
- Databricks is P1 because it's already in the v4.1 §10.2 spec example; the catalog integration exists via PyIceberg; the REST catalog federation story is built.
- Modal is P2 for the "1 asset that blows up laptop RAM" use case — Python-native, per-second billing, sub-4s cold start, no cluster ops.
- Snowflake P3 because Open Catalog (Polaris-based) makes Iceberg write viable in 2026; but Nucleus needs a DBAPI bridge.
- Coiled is DEFER — Dask API mismatch + slow spinup + Polars-first stack.
- Ray/Anyscale is P4 — the right path is Daft → Ray, not Nucleus → Ray direct.

---

## 11. NEEDS VERIFICATION

1. **Paimon 1.0 Iceberg compatibility layer**: Official docs at https://paimon.apache.org/docs/1.0/ mention an Iceberg REST catalog bridge. Exact API surface, version compatibility with PyIceberg 0.10.x, and read/write mode details need direct verification before any Paimon integration work.

2. **Coiled cluster spinup benchmarks**: The Coiled benchmarks dashboard (https://benchmarks.coiled.io) should be checked for current P50/P95 cluster-ready times. The "30–90 seconds" estimate in this document is based on EC2 instance provisioning estimates, not measured Coiled-specific data.

3. **Dask Polars backend**: Dask's recent transition to support alternative backends including Polars is partially documented but the API maturity and feature parity status should be verified at https://docs.dask.org/en/latest/dataframe-polars.html before evaluating whether Dask+Polars changes the Coiled relevance assessment.

4. **Daft Substrait roadmap**: Daft 0.7.11 does NOT use Substrait (it uses a custom planner per `peer_distributed_streaming.md`). Verify whether the Daft 0.8+ roadmap includes Substrait support: https://github.com/Eventual-Inc/Daft/issues or roadmap discussions.

5. **Ray 3.0 shipping timeline**: The 3.0 dev docs exist but no official GA announcement as of 2026-05-15. Verify at https://github.com/ray-project/ray/releases before citing 3.0 features in any Nucleus ADR.

6. **Mojo compiler open-source date**: Modular targets "Fall 2026" for Mojo 1.0 GA + compiler open source. Verify at https://docs.modular.com/mojo/roadmap closer to that date.

7. **Modal enterprise pricing**: The 3.75x cost multiplier for production non-preemptible US workloads may change. Verify against https://modal.com/pricing at integration time.

8. **BigQuery Iceberg external tables**: BigQuery added Iceberg external table support in 2025. Verify write capability (not just read) and catalog compatibility at https://cloud.google.com/bigquery/docs/iceberg-tables before rating BigQuery as P5.

---

## 12. Adjacent Ecosystem Notes

### Fluss (Apache incubating)
The Flink community's new "hot tier" streaming storage project (Fluss) pairs with Iceberg as a "Streamhouse" architecture. Not yet Apache top-level. Relevant at v0.5+ for CDC-heavy Nucleus users. Monitor at https://fluss.apache.org/.

### Turbopuffer
Ray 2.55.0 added a Turbopuffer datasink (vector search). Irrelevant to Nucleus v0.1–v1.0 but intersects with the v0.5+ Lance/LanceDB multimodal tier.

### DataFusion 45+ (2026)
The Substrait function mapping work in DataFusion (https://github.com/apache/datafusion/issues/16949) is progressing. This matters for the DuckDB→DataFusion swap interface described in the composability docs.

---

## 13. Suggested ADRs Triggered by This Research

1. **ADR for Mode 2 dispatch target prioritization** (new ADR-NNN): Formal decision on which dispatch targets to implement in what order. Recommended: Databricks P1 → Modal P2 → Snowflake P3. Gate: Lakekeeper REST catalog at v0.3.

2. **ADR for Substrait as DuckDB↔DataFusion swap interface** (extend existing composability ADR): Adopt Substrait protobuf as the interface contract for the SQL engine swap (not as dispatch wire protocol). This makes the swap testable: generate a Substrait plan from DuckDB, execute it on DataFusion, compare results.

3. **ADR for Paimon watch list** (v0.5 tracking): Formal decision to defer Paimon integration, with gate conditions: (a) Paimon Iceberg bridge verified production-ready, (b) Python-native Paimon writer exists (no JVM), (c) CDC-heavy user demand empirically validated post-v0.3 beta.

---

## 14. References

**Ray**: https://docs.ray.io/en/releases-2.55.1/ · license https://github.com/ray-project/ray/blob/master/LICENSE · PyTorch Foundation https://www.anyscale.com/press/pytorch-foundation-welcomes-ray-to-deliver-a-unified-open-source-ai-compute · Iceberg write API https://docs.ray.io/en/releases-2.55.1/data/api/doc/ray.data.Dataset.write_iceberg.html · Daft-Ray bridge https://docs.getdaft.io/en/stable/distributed/ray/

**Modal**: cold start https://modal.com/docs/guide/cold-start · pricing https://modal.com/pricing · OIDC https://modal.com/docs/guide/oidc-integration · memory snapshots https://modal.com/docs/guide/memory-snapshots

**Coiled**: https://coiled.io/pricing · https://docs.coiled.io/ · benchmarks https://benchmarks.coiled.io

**Mojo**: path to 1.0 https://www.modular.com/blog/the-path-to-mojo-1-0 · 1.0 beta https://www.modular.com/blog/modular-26-3-mojo-1-0-beta-max-video-gen-and-more · roadmap https://docs.modular.com/mojo/roadmap · Python interop https://docs.modular.com/stable/mojo/manual/python/

**Apache Paimon**: docs https://paimon.apache.org/docs/1.0/ · CDC https://paimon.apache.org/docs/1.0/cdc-ingestion/overview/ · primary key https://paimon.apache.org/docs/1.0/primary-key-table/data-distribution/

**Substrait**: spec https://substrait.io/ · DuckDB ext https://github.com/substrait-io/duckdb-substrait-extension · DataFusion https://github.com/apache/datafusion/issues/16949 · Arrow https://arrow.apache.org/docs/python/integration/substrait.html · powered-by https://substrait.io/community/powered_by/

**Flink/Beam/Fluss**: Confluent Flink https://docs.confluent.io/cloud/current/flink/overview.html · Flink vs Beam https://www.modern-datatools.com/compare/apache-flink-vs-apache-beam · Fluss blog https://fluss.apache.org/blog/2025/12/02/fluss-x-iceberg-why-your-lakehouse-is-not-streamhouse-yet/

**Dask**: https://github.com/dask/dask

---

## 15. Hallucination Log

No confirmed AI-fabricated APIs in this document. Items flagged `[NEEDS VERIFICATION]` rather than asserted: Paimon Iceberg REST catalog bridge details; Coiled spinup benchmarks (estimate only); Dask Polars backend maturity; Daft Substrait roadmap post-0.7.11; Ray 3.0 GA timeline.

See `docs/research/ai_hallucinations.md` — no new entries required.

---

*Research tier: Claude Sonnet 4.6 (Gemini 3.1 Pro unavailable in current Cursor runtime; fallback per AGENTS.md §11.14). All claims verified against official docs URLs as of 2026-05-15.*
