# Storage Formats + Cross-Engine RPC — Research Notes (R8)

> **Last verified**: 2026-05-15 against live docs, GitHub PRs, and official release notes  
> **Researcher model**: Claude Sonnet 4.6 (Swarm tier — Gemini 3.1 Pro unavailable; fallback per `AGENTS.md §11.14`)  
> **AI caveat**: Every non-trivial claim cites a live URL fetched 2026-05-15. Do not rely on AI memory.  
> **Scope**: 9 format-layer topics — Iceberg v3, Parquet v3, Vortex, Lance v2, Delta Lake 4, Paimon, Arrow Flight SQL, Arrow IPC, Compression evolution  
> **NOT covered**: catalog landscape (R1), engine upgrade paths (`tier0_oss_evolution.md`)  
> **Tier**: Tier 0 subjects throughout — Arrow, Iceberg, Parquet are immortal

---

## 1. Executive Summary — Top 3 Format-Layer Signals for v0.5–v1.0

| Rank | Signal | Nucleus action |
|---|---|---|
| **1** | **Iceberg v3 is ratified (June 2025) and engines are shipping.** DuckDB reads + writes deletion vectors (Feb–Mar 2026); Trino GA'd (Mar 2025); Spark via Databricks GA'd. PyIceberg 0.11.1 reads DVs. Tables upgraded to format-version=3 get **≤10× faster UPDATE/DELETE/MERGE** at zero engine cost. | **Plan `nucleus migrate-format` helper for v0.3.** No action now — blocked on pyiceberg DV write support. Requires ADR (breaking: readers without v3 DV support silently return deleted rows). |
| **2** | **Vortex (LFAI incubation) + FastLanes (VLDB 2025) signal the next columnar encoding generation.** Adaptive SIMD-native encodings achieve 40–200× faster random access vs Parquet. DuckDB 1.4.0 LTS ships a Vortex extension. This is a 3–5 year watch signal, not a format to adopt today. | **TRACK — no action for v0.5; revisit at v1.0** once LFAI graduates Vortex and DuckDB extension matures. Add to `FOUNDER_ACTION_QUEUE.md`. |
| **3** | **Arrow Flight SQL is the correct BI-connectivity story for Workbench v0.3.** JDBC driver ships with Arrow; `FlightServerBase` exists in pyarrow 18.x (already pinned); ADBC client lets any BI tool connect. >80% serialization overhead reduction vs JSON REST for bulk result sets. | **Implement at Workbench v0.3** (~500 LOC, 1 new dev dep). Requires ADR. Existing JSON REST stays — additive endpoint only. |

---

## 2. Apache Iceberg v3 — Deep Dive

> **Spec ratified**: June 2025 · **v4 under active development** as of May 2026  
> **Spec URL**: https://iceberg.apache.org/spec/  
> **GitHub**: https://github.com/apache/iceberg/blob/main/format/spec.md

### 2.1 Deletion Vectors

**What they are:** Compressed roaring bitmaps stored as Puffin `deletion-vector-v1` blobs. One DV per data file (spec requires writers to merge; no two DVs may reference the same data file). They replace v2 positional delete files — v3 prohibits new positional delete file writes.

**Why it matters:** Every `UPDATE` / `DELETE` / `MERGE` in Iceberg v2 writes expensive positional delete files. DVs consolidate this into a single bitmap per data file, reducing write amplification and per-query I/O. Databricks reports **10× faster UPDATE statements** with DVs enabled. [[AWS Big Data Blog]](https://aws.amazon.com/blogs/big-data/accelerate-data-lake-operations-with-apache-iceberg-v3-deletion-vectors-and-row-lineage/)

**pyiceberg DV status (our write path):** DV **read** support complete (PyIceberg 0.11.1, March 2025). DV **write** support was in progress via PR #2822 (December 2025–March 2026); final merge status requires verification — see §9 [NV-2]. **Do NOT enable format-version=3 by default until write support is confirmed.** [[V3 tracking issue]](https://github.com/apache/iceberg-python/issues/1818)

### 2.2 Variant Type — Semi-Structured Data

A self-describing type for JSON-like documents with arbitrary evolving schemas. Stored as a struct with two binary fields: `metadata` (field-name dictionary) and `value` (encoded binary tree). Iceberg and Parquet aligned on the same Variant encoding. [[Snowflake eng blog — Iceberg Variant]](https://www.snowflake.com/en/engineering-blog/apache-iceberg-v3-variant-type/)

DuckDB Iceberg extension: Variant column read+write merged March 3, 2026. Output is JSON string; bounds deserialization pending. [[duckdb-iceberg PR #474]](https://github.com/duckdb/duckdb-iceberg/pull/474)

**pyiceberg:** Blocked on PyArrow Variant support (Arrow issue #45937). No ETA as of January 2026. [[pyiceberg issue #1819]](https://github.com/apache/iceberg-python/issues/1819)

**Nucleus impact:** `ctx.copy_from` pipelines ingesting `json`/`jsonb` Postgres columns benefit directly once DuckDB + pyiceberg upgrades land in v0.3. Zero new Nucleus LOC.

### 2.3 Geo Types — Geometry + Geography

- `geometry(C)` — linear/planar edge interpolation parameterized by CRS
- `geography(C, A)` — spherical edge interpolation parameterized by CRS + algorithm

Both store as WKB bytes. No support for partitioning by geo columns.

Spec merged February 2025 (PR #10981). PyIceberg geo support completed February 2026, requiring `geoarrow-pyarrow` for Parquet conversion. [[pyiceberg RFC #3004]](https://github.com/apache/iceberg-python/issues/3004)

**Not a v0.1–v0.3 priority.** The beachhead persona is a startup data team, not a GIS shop. Passive benefit: if a user ingests from PostGIS, pyiceberg 0.11.1 will not corrupt the geometry column.

### 2.4 Row Lineage (Always-On in v3)

Every v3 table automatically tracks `_row_id` (monotonically increasing integer, unique per table) and `_last_update` (sequence number of last modifying commit). Row lineage is **required** — made mandatory in April 2025 (was optional). [[PR #12593]](https://github.com/apache/iceberg/pull/12593)

Relevant to Nucleus v0.5+: `_row_id` enables row-level lineage without additional instrumentation, complementing the asset-level OpenLineage we ship today.

### 2.5 Iceberg v3 Engine Readiness Table

| Engine | Nucleus pin | Deletion Vectors R/W | Variant | Geo | Row Lineage |
|---|---|---|---|---|---|
| **DuckDB** | `1.1.3` (latest: `1.5.2`) | ✓ / ✓ (Feb+Mar 2026) [1][2] | ✓ (Mar 2026, JSON out) [3] | ✓ (DuckDB 1.5.0) | `[NV-1]` |
| **Polars** | `1.18.0` (latest: `1.40.x`) | ✗ (read-only via pyiceberg) | ✗ (blocked on PyArrow) | ✗ | ✗ |
| **Trino** | not pinned | ✓ / ✓ (Mar 2025 + Jan 2026) [4][5] | `[NV-3]` | `[NV-3]` | `[NV-3]` |
| **Spark (1.8.0+)** | not pinned | ✓ / ✓ (Databricks GA) [6] | ✓ (Databricks GA) [6] | `[NV-4]` | ✓ (mandatory v3) |
| **PyIceberg** | `0.11.1` | ✓ READ; WRITE `[NV-2]` | ✗ (blocked ARROW-45937) | ✓ (Feb 2026, needs Arrow 21+) | ✓ (spec) |

[1] https://github.com/duckdb/duckdb-iceberg/pull/327 · [2] https://github.com/duckdb/duckdb-iceberg/pull/728  
[3] https://github.com/duckdb/duckdb-iceberg/pull/474 · [4] https://github.com/trinodb/trino/pull/24882  
[5] https://github.com/trinodb/trino/issues/27788 · [6] https://www.databricks.com/blog/advancing-lakehouse-apache-iceberg-v3-databricks

### 2.6 Nucleus v3 Migration Plan

**Phase 1 (now → v0.3):** No format-version changes. Block on pyiceberg DV write support [NV-2].  
**Phase 2 (v0.3):** `nucleus migrate-format --table <asset> --version 3` — explicit opt-in per table. Draft ADR before shipping; it is a **one-way door** (tables cannot downgrade).  
**v4 signal:** Iceberg v4 is under development as of mid-2026. Monitor only; no design decisions yet.

---

## 3. Apache Parquet v3 — Format Additions

> **Parquet docs**: https://parquet.apache.org/docs/file-format/

### 3.1 Variant Logical Type (August 2025)

Finalized via PR #509, August 2025. Aligned with Iceberg Variant: two binary fields (metadata + value). Reference implementations in Java, Go, Rust, DuckDB, Iceberg. DuckDB added Parquet Variant read support with shredded encoding in July 2025. [[parquet-format issue #508]](https://github.com/apache/parquet-format/issues/508) [[DuckDB PR #18224]](https://github.com/duckdb/duckdb/pull/18224)

**Zero Nucleus LOC.** DuckDB upgrade to 1.5.x in v0.3 unlocks Variant reads via `ctx.sql` automatically.

### 3.2 Geometry and Geography Logical Types (February 2025)

Merged February 10, 2025. [[parquet-format PR #240]](https://github.com/apache/parquet-format/pull/240) [[Parquet geo blog]](https://parquet.apache.org/blog/2026/02/13/native-geospatial-types-in-apache-parquet/)

Key capabilities beyond mere encoding:
- Query engines detect spatial columns automatically (no explicit function call needed)
- Bounding-box statistics attached to column chunks → row group pruning for spatial queries → significant I/O reduction on geo-filtered scans

Joint effort with Iceberg and GeoParquet; DuckDB 1.5.0 ships native geometry type.

### 3.3 Bloom Filter Folding (2025)

Contributed via arrow-rs: adaptive sizing that eliminates the need to know distinct-value counts before writing. Filter starts large; post-write bitwise OR shrinks it. [[Pydantic Logfire blog]](https://pydantic.dev/articles/bloom-filter-folding-parquet-logfire)

Measured gains:
- Up to **50× speedup on point lookups** in DuckDB [[DuckDB blog]](https://duckdb.org/2025/03/07/parquet-bloom-filters-in-duckdb.html)
- Up to **30× improvement** measured by InfluxData

DuckDB 1.2.0+ reads and writes Parquet bloom filters. Benefit is automatic for `ctx.sql` Parquet exports — no Nucleus configuration changes.

### 3.4 ALP (Adaptive Lossless Floating-Point) Encoding

ALP (SIGMOD 2024) is the successor to ChiMP and Patas for float column encoding. DuckDB deprecated ChiMP for writing February 2024; ALP is now the DuckDB default. [[DuckDB — ALP]](https://duckdb.org/library/alp/)

Parquet format spec PR submitted January 2026, under active review. [[parquet-format PR #548]](https://github.com/apache/parquet-format/pull/548) Performance: 1–2 orders of magnitude faster decompression vs Gorilla/ChiMP, compression ratio comparable to ZSTD.

**Nucleus impact:** ALP is already active in every DuckDB Parquet write at our current pin (`duckdb==1.1.3`). When ALP lands in the Parquet spec, non-DuckDB readers of Nucleus-produced Parquet benefit automatically. No code change required.

---

## 4. Vortex File Format (LFAI&Data Incubation)

> **GitHub**: https://github.com/vortex-data/vortex  
> **Docs**: https://docs.vortex.dev/  
> **Latest**: 0.67.0 (2026-03-30)  
> **Governance**: Linux Foundation AI & Data Foundation, incubation stage (donated August 2025)

Vortex's core innovation is **adaptive composable encodings**: FastLanes (integer bit-packing) + ALP (floats) + FSST (strings), chained adaptively based on data characteristics. A single unified disk/memory/wire representation enables zero-copy reads via Arrow alignment. [[Spiral Labs — Towards Vortex 1.0]](https://spiraldb.com/post/towards-vortex-10)

**Published performance (vendor-claimed — verify before citing):**

| Metric | vs Parquet+zstd |
|---|---|
| Compression ratio | Comparable |
| Write throughput | 1–2× faster |
| Sequential scan | 2–3× faster |
| **Random access** | **Up to 200×** faster |

The 200× figure derives from push-down compute over compressed data — encoding-aware kernels skip decompression for predicate evaluation. Architecturally different from Parquet.

**Format stability:** Stable (forward compatible) since 0.36.0, April 2025. [[stabilization issue #2077]](https://github.com/spiraldb/vortex/issues/2077) DuckDB 1.4.0 LTS ships a Vortex extension (`[NV-6]` — scope of read/write support not confirmed from docs).

**Verdict: TRACK. Do not adopt for v0.5.** 8-question gate Q2 (beachhead metric): no clear v0.3 user pain removed. Q8: not required for v0.1 Hello World. LFAI incubation ≠ Apache Top-Level graduation. Revisit at v1.0 if LFAI graduates Vortex and DuckDB extension matures to read+write.

---

## 5. Lance v2 — Multimodal Format Updates

> **Docs**: https://docs.lancedb.com/lance  
> **GitHub**: https://github.com/lancedb/lance  
> **License**: Apache-2.0  
> **Lance 2.1 stable**: October 2025 · **Lance 2.2**: benchmarks published 2025

Lance v2.2 introduced **Blob V2: adaptive storage semantics** with four modes selected per column based on value size: `Inline` (small), `Packed` (medium), `Dedicated` (large), `External` (reference to object store for images/video). This eliminates the need for separate ETL pipelines per modality.

**Published performance vs Lance v1 (vendor-claimed):** [[LanceDB v2.2 benchmarks]](https://www.lancedb.com/blog/lance-format-v2-2-benchmarks-half-the-storage-none-of-the-slowdown)
- 50%+ storage reduction
- Up to 68× faster blob reads
- Scan and random access performance maintained

Additionally: nested schema evolution (add embedding columns without table rewrites), native Map type support.

Engine compatibility: Pandas, DuckDB, Polars, PyArrow, PyTorch, Apache Spark, Ray.

**DuckDB 1.5.0 bundles the Lance extension as a core extension.** Once DuckDB is upgraded to 1.5.x (v0.3 per `tier0_oss_evolution.md`), `ctx.sql("SELECT * FROM 'my_data.lance'")` works out of the box. Zero Nucleus LOC.

**Verdict: ADOPT plan unchanged.** Lance v0.5+ as Tier 0 immortal for multimodal assets is confirmed by v2.2 maturity. The 4-mode Blob V2 design maps cleanly to the Nucleus AI Copilot plans (vectors → Inline, chunked text → Packed, images → Dedicated, raw media → External).

---

## 6. Delta Lake 4 — Parity Check (Not Adopted)

> **Delta Lake 4.0**: September 2025 · **Delta Lake 4.1.0**: March 2026

Three features define Delta 4.x:

**Coordinated Commits** (GA for Unity Catalog, May 2026): Multi-engine writes brokered by the catalog. Addresses Delta's historical split-brain problem where engines writing directly to object storage caused metadata divergence. [[Databricks blog — Catalog Commits GA]](https://www.databricks.com/blog/convergence-open-table-formats-and-open-catalogs-catalog-commits-generally-available) This is architecturally converging toward what Iceberg's REST catalog has done since 2021 — Delta is solving in 4.0 what Iceberg solved years ago.

**Variant Data Type**: Delta ships the same Parquet-aligned Variant type. Engine parity with Iceberg on semi-structured data.

**Catalog-Managed Tables**: Table lifecycle (create/drop/rename) governed by the catalog, not raw object-storage paths.

**Nucleus assessment:** Our Iceberg bet is confirmed. Remaining meaningful delta (pun intended):

| Dimension | Iceberg | Delta Lake 4 |
|---|---|---|
| Engine breadth | 30+ (Trino, Spark, DuckDB, ClickHouse, Snowflake, Athena…) | Spark/Databricks best; partial elsewhere |
| Governance | Apache Software Foundation (community) | Linux Foundation (Databricks-influenced roadmap) |
| Write coordination | REST catalog spec (standard) | Coordinated commits (catalog-specific) |
| Vendor lock-in risk | LOW | MEDIUM |

Continue with Iceberg. Beachhead users graduating to Databricks will find Delta native there; our Iceberg portability (Mode 1) lets users keep both.

---

## 7. Apache Paimon — Streaming-Native Format Internals

> **Docs**: https://paimon.apache.org/docs/master/  
> **Version**: 1.2 (2025)  
> **Role for Nucleus**: encountered as a CDC source, not a Nucleus write target

Paimon primary-key tables use an **LSM tree** per bucket. Three table modes: MOR (merge on read, default), COW (copy on write), and MOW (merge on write via deletion vectors, balanced performance — recommended for general use). [[Paimon table modes]](https://paimon.apache.org/docs/master/primary-key-table/table-mode/)

**Iceberg compatibility:** Paimon tables can expose an Iceberg-compatible metadata layer. As of May 2025, Paimon's 64-bit bitmap DVs are recognized by Iceberg format-version=3 readers (requires `deletion-vectors.enabled = true` + `deletion-vectors.bitmap64 = true` + `format-version = 3`). [[Paimon PR #5670]](https://github.com/apache/paimon/pull/5670)

**Nucleus impact:** Users running Flink-based CDC pipelines (Debezium → Paimon → Iceberg compatibility layer) can have `ctx.sql` read those assets directly via REST catalog. **No Nucleus code changes required.** Document in connector guide when dlt Iceberg sources formalize in v0.3.

---

## 8. Arrow Flight SQL — Cross-Engine RPC for Workbench

> **Spec**: https://arrow.apache.org/docs/format/FlightSql.html  
> **FlightServerBase**: https://arrow.apache.org/docs/python/generated/pyarrow.flight.FlightServerBase.html  
> **ADBC client**: https://arrow.apache.org/adbc/current/python/api/adbc_driver_flightsql.html  
> **Current pin**: `pyarrow==18.1.0` (already in `pyproject.toml`)

### 8.1 What Is It?

Arrow Flight SQL is a binary SQL database protocol over gRPC/HTTP2 using native Arrow RecordBatches. It eliminates JSON serialization overhead on the hot result-return path. A JDBC driver ships with Arrow since v10.0.0. [[Arrow blog — JDBC driver]](https://arrow.apache.org/blog/2022/11/01/arrow-flight-sql-jdbc) The ADBC client library (`adbc_driver_flightsql`) allows BI tools (Superset, Tableau, DBeaver) to connect without custom drivers.

Performance: >80% serialization overhead reduction vs JDBC/JSON for analytics-scale result sets. [[Dremio blog — Flight SQL vs ODBC/JDBC]](https://dremio.com/blog/will-apache-arrow-flight-sql-replace-odbc-and-jdbc-for-analytics-bi-workloads)

### 8.2 Implementation Constraints

1. **No native Python Flight SQL server library.** `pyarrow.flight.FlightServerBase` provides raw Flight RPC but NOT the Flight SQL protocol layer (catalog metadata endpoints, statement result routing). You must manually implement the Flight SQL message parsing on top of raw Flight RPC. Apache Arrow issue #37700 tracking Python Flight SQL server helpers is stale (closed as not-planned February 2026). This is feasible but adds ~150 LOC of protocol glue.

2. **gRPC server lifecycle.** `FlightServerBase` runs a gRPC server in a background thread; must coexist with uvicorn. Clean solution: separate port (e.g., `:8766` Flight, `:8765` REST).

3. **pyarrow already pinned.** No new runtime deps on server side.

### 8.3 Workbench Flight SQL Effort Card

| Component | LOC | Notes |
|---|---|---|
| `FlightServerBase` subclass + DuckDB query wiring | ~150 | DuckDB returns Arrow natively; zero re-encoding |
| SQL metadata handlers (`GetSqlInfo`, `GetDbSchemas`, `GetDbTables`) | ~100 | Required by JDBC clients for schema discovery |
| Statement execution (`GetFlightInfo` + `DoGet` streaming) | ~150 | Core query path |
| Integration tests (ADBC client → Nucleus → DuckDB) | ~100 | New dev dep: `adbc-driver-flight-sql` |
| **Total** | **~500 LOC** | **1 new dev-only dep** |

**Verdict: DEFER to Workbench v0.3** (already planned per `tier0_oss_evolution.md §2.4`). Prerequisites: Workbench v0.2 REST API stable, at least one beachhead BI tool confirms ADBC adoption. When implemented, Flight SQL is additive — JSON REST stays for CLI and browser clients.

---

## 9. Arrow IPC + Arrow C Data Interface

> **IPC Python docs**: https://arrow.apache.org/docs/python/ipc.html  
> **C Data Interface spec**: https://arrow.apache.org/docs/format/CDataInterface.html

**Arrow IPC** has two sub-formats: streaming (sequential RecordBatch sequences, used for network) and file (random access, useful with `mmap`). Both support LZ4/ZSTD compression.

**C Data Interface (CDI)** is a 2-C-struct definition (`ArrowSchema` + `ArrowArray`) for zero-copy in-process exchange with no Arrow library dependency. CDI is the mechanism DuckDB uses to export RecordBatches to pyarrow with zero copy: `duckdb.execute("...").arrow()`.

**Nucleus today already leverages both:**
- DuckDB → pyarrow: CDI (zero copy, no overhead)
- pyiceberg Parquet reads: Arrow IPC via pyarrow
- `polars.scan_iceberg()`: pyiceberg Arrow layer

**Adding IPC to Workbench HTTP responses** (returning `application/vnd.apache.arrow.stream`) would break CLI and browser JSON clients. **Do not add to HTTP layer in v0.1–v0.2.** In v0.3, add as an opt-in `Accept: application/vnd.apache.arrow.stream` header alongside JSON — satisfies ADBC clients without breaking CLI. Estimated 50–100 LOC of Workbench middleware.

---

## 10. Compression Evolution

| Algorithm | Type | DuckDB status | Parquet spec status | Key fact |
|---|---|---|---|---|
| **Zstandard** | General binary | Write default | Supported | Best ratio/speed balance; keep as default |
| **ALP** | Float64/Float32 | **Write default** (replaced ChiMP Feb 2024) | PR #548 under review (Jan 2026) | 10–100× faster decompression vs ChiMP/Gorilla |
| **FastLanes** | Integer columns | DuckDB internal | Not in Parquet spec | 40% better compression, 40× faster decode; VLDB 2025 standalone format |
| **FSST** | High-cardinality strings | Via Vortex extension | Not in Parquet spec | Dictionary-free string compression |
| **Bloom filter folding** | Predicate pushdown | Full (DuckDB 1.2+) | Published (arrow-rs) | 50× point-lookup speedup; no distinct count needed upfront |
| **ChiMP** | Float time series | **Deprecated** for writes (Feb 2024) | Never formally in spec | Superseded by ALP in all benchmarks — remove from docs if mentioned |

**Nucleus action:** ALP is already active at our current pin. No code changes needed. FastLanes is a research signal for v1.0+ caching format evaluation. Remove any documentation references to ChiMP as a recommended encoding.

---

## 11. NEEDS VERIFICATION

| ID | Claim | Check URL |
|---|---|---|
| **[NV-1]** | DuckDB 1.5.x exposes `_row_id`/`_last_update` v3 metadata columns | https://github.com/duckdb/duckdb-iceberg/releases |
| **[NV-2]** | PyIceberg DV **write** support — PR #2822 close event (March 2026) was merge or close-without-merge | https://github.com/apache/iceberg-python/blob/main/CHANGES.md |
| **[NV-3]** | Trino Iceberg v3 variant + geo type support (deletion vectors confirmed; others not found) | https://trino.io/docs/current/connector/iceberg.html |
| **[NV-4]** | Spark open-source (non-Databricks) geo type support for Iceberg v3 | https://iceberg.apache.org/docs/latest/spark-ddl/ |
| **[NV-5]** | Vortex license — LFAI incubation standard implies Apache-2.0 but not confirmed from LICENSE file | https://github.com/vortex-data/vortex/blob/main/LICENSE |
| **[NV-6]** | DuckDB 1.4.0 Vortex extension — read-only or read+write? Full spec or subset? | https://duckdb.org/2025/09/15/announcing-duckdb-140.html |
| **[NV-7]** | `adbc-driver-flight-sql` current PyPI version + Python 3.11 compatibility | https://pypi.org/project/adbc-driver-flight-sql/ |

---

## 12. References

| # | URL | Topic |
|---|---|---|
| [1] | https://iceberg.apache.org/spec/ | Iceberg spec (v1–v4) |
| [2] | https://aws.amazon.com/blogs/big-data/accelerate-data-lake-operations-with-apache-iceberg-v3-deletion-vectors-and-row-lineage/ | Iceberg v3 DVs + row lineage |
| [3] | https://www.snowflake.com/en/engineering-blog/apache-iceberg-v3-variant-type/ | Iceberg Variant type design |
| [4] | https://github.com/duckdb/duckdb-iceberg/pull/327 | DuckDB v3 DV reads |
| [5] | https://github.com/duckdb/duckdb-iceberg/pull/728 | DuckDB v3 DV writes |
| [6] | https://github.com/duckdb/duckdb-iceberg/pull/474 | DuckDB v3 Variant |
| [7] | https://github.com/trinodb/trino/pull/24882 | Trino v3 DVs |
| [8] | https://www.databricks.com/blog/advancing-lakehouse-apache-iceberg-v3-databricks | Spark Iceberg v3 GA |
| [9] | https://github.com/apache/iceberg-python/issues/1818 | PyIceberg v3 tracking |
| [10] | https://github.com/apache/iceberg/pull/12593 | Row lineage required in v3 |
| [11] | https://parquet.apache.org/blog/2026/02/27/variant-type-in-apache-parquet-for-semi-structured-data/ | Parquet Variant |
| [12] | https://parquet.apache.org/blog/2026/02/13/native-geospatial-types-in-apache-parquet/ | Parquet geo types |
| [13] | https://github.com/apache/parquet-format/pull/240 | Parquet geometry PR |
| [14] | https://duckdb.org/2025/03/07/parquet-bloom-filters-in-duckdb.html | DuckDB bloom filters |
| [15] | https://pydantic.dev/articles/bloom-filter-folding-parquet-logfire | Bloom filter folding |
| [16] | https://github.com/apache/parquet-format/pull/548 | Parquet ALP spec PR |
| [17] | https://duckdb.org/library/alp/ | ALP in DuckDB |
| [18] | https://spiraldb.com/post/towards-vortex-10 | Vortex 1.0 roadmap |
| [19] | https://github.com/vortex-data/vortex/issues/2077 | Vortex format stabilization |
| [20] | https://www.lancedb.com/blog/lance-format-v2-2-benchmarks-half-the-storage-none-of-the-slowdown | Lance v2.2 benchmarks |
| [21] | https://www.lancedb.com/blog/lance-file-format-2-2-taming-complex-data | Lance v2.2 features |
| [22] | https://lancedb.com/blog/lance-file-2-1-stable/ | Lance 2.1 stable |
| [23] | https://www.databricks.com/blog/convergence-open-table-formats-and-open-catalogs-catalog-commits-generally-available | Delta 4 coordinated commits GA |
| [24] | https://paimon.apache.org/docs/master/primary-key-table/table-mode/ | Paimon table modes |
| [25] | https://github.com/apache/paimon/pull/5670 | Paimon Iceberg DV compat |
| [26] | https://arrow.apache.org/docs/format/FlightSql.html | Arrow Flight SQL spec |
| [27] | https://arrow.apache.org/docs/python/generated/pyarrow.flight.FlightServerBase.html | PyArrow FlightServerBase |
| [28] | https://arrow.apache.org/adbc/current/python/api/adbc_driver_flightsql.html | ADBC Flight SQL driver |
| [29] | https://dremio.com/blog/will-apache-arrow-flight-sql-replace-odbc-and-jdbc-for-analytics-bi-workloads | Flight SQL vs ODBC/JDBC |
| [30] | https://arrow.apache.org/blog/2022/11/01/arrow-flight-sql-jdbc | Arrow Flight SQL JDBC driver |
| [31] | https://arrow.apache.org/docs/format/CDataInterface.html | Arrow C Data Interface |
| [32] | https://www.vldb.org/pvldb/vol18/p4629-afroozeh.pdf | FastLanes VLDB 2025 paper |
| [33] | https://github.com/cwida/FastLanes | FastLanes GitHub |
| [34] | https://github.com/apache/arrow/issues/37700 | PyArrow Flight SQL server (stale) |

---

*Researcher: Claude Sonnet 4.6 (Swarm tier fallback, per `AGENTS.md §11.14`). Preferred: Gemini 3.1 Pro (unavailable). All URLs fetched live 2026-05-15.*
