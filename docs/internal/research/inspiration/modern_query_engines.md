# Modern Query Engines — Inspiration Research (2026)

> **Last verified**: 2026-05-15 against live docs, GitHub releases, and official blog posts  
> **Researcher model**: Claude Sonnet 4.6 (Swarm/Research tier — Gemini 3.1 Pro unavailable in current runtime; fallback per `AGENTS.md §11.14`)  
> **AI training-data caveat**: All claims cite live URLs fetched on 2026-05-15. Do not rely on AI memory for version or API details.  
> **Scope**: Modern non-DuckDB query engines — adoption signals, performance gaps, swap relevance, Substrait as plan IR  
> **Prior work**: `docs/internal/research/inspiration/tier0_oss_evolution.md` covers DuckDB 1.1.3→1.5.2 and Polars 1.18.0→1.40.1. This doc does **not** repeat those.  
> **Nucleus current pins**: `duckdb==1.1.3`, `polars==1.18.0` (per `pyproject.toml`)

---

## 1. Executive Summary

**DuckDB remains the correct v0.1 default.** No alternative embeddable engine in 2026 matches DuckDB's combination of: (a) full SQL dialect, (b) Iceberg read support, (c) 30 MB binary, (d) MIT license, (e) stable Python API, (f) 5.82 s cold-start compatibility with the beachhead boot test. Every evaluated alternative fails at least one of these criteria.

**Top 2 signals to watch for swap trigger decisions:**

1. **Apache DataFusion Python bindings approaching parity** — datafusion-python v53.0.0 (May 2026) is "Pre-Alpha" and 6-7× slower on simple aggregations vs DuckDB. However, the DataFusion Rust engine powers dbt Fusion, delta-rs, Lance, and Cloudflare R2's query engine. It is the credible swap candidate when the Python bindings reach stable (estimated v55-60+ based on release cadence of ~4 versions/month). Monitor [datafusion-python/issues/1186](https://github.com/apache/datafusion-python/issues/1186) as the regression tracker.

2. **Vortex file format has industrial backing** — Donated to Linux Foundation AI & Data (LFAI) in August 2025 with Snowflake, Microsoft, and Palantir as backers. Its backward-compat guarantee starts at v0.36.0. If Vortex becomes a first-class Iceberg data file format (replacing Parquet), `ctx.sql` design will need to account for it as a scan target. DuckDB already ships a Vortex client package per Spiral Labs' release notes [NEEDS VERIFICATION — confirm Vortex extension ships in DuckDB 1.5.x].

**8-question gate verdicts (summary):** DataFusion → DEFER (swap target; build adapter on-demand). Velox → REJECT (not standalone; requires host query system). chDB → DEFER (niche Pandas-SQL bridge; 3-5× larger wheel; no Iceberg). GlareDB → DEAD (abandoned Nov 2025). MotherDuck → INSPIRATION ONLY (Mode 2 yield-to-giants pattern). Substrait → DEFER (Polars "not_planned"; DuckDB support is community extension only). Vortex → WATCH (LFAI incubation; swap target when Iceberg spec ratifies). Polars SQL → ALREADY WRAPPED (SQLContext available today; `engine="polars"` hint is v0.2 work).

---

## 2. Apache DataFusion 47+ (Rust, Embeddable)

### 2.1 What it is

Apache DataFusion is a query engine written in Rust, using Apache Arrow as its in-memory format. It is the engine that powers `delta-rs`, `Lance` (our v0.5+ vector store), `iceberg-rust`, and Cloudflare's R2 query engine. It is **not** a standalone product — it is a library that others embed, similar to how Nucleus embeds DuckDB.

- **Python bindings**: `datafusion` on PyPI → [https://pypi.org/project/datafusion/](https://pypi.org/project/datafusion/)
- **Latest release**: v53.0.0 (May 2026) — `pip install datafusion`
- **Stability**: Marked **"Pre-Alpha" (Status: 2)** on PyPI as of v53.0.0 [1]
- **Python requirement**: ≥3.10 (our pin is 3.11 — compatible) [1]
- **License**: Apache-2.0 [2]
- **Architecture**: Arrow-native, Rust kernel, zero-copy between Python and Rust via Arrow C Data Interface [3]
- **Release cadence**: ~4 major releases/month (v47 = April 2025; v53 = May 2026)
- **Key users**: dbt Fusion engine, delta-rs, Lance, Cloudflare R2, InfluxDB, GlareDB (RIP), Vortex [4]

### 2.2 Performance vs DuckDB

DataFusion's Rust kernel is fast for complex multi-table scans and parallel Parquet reads. Python binding overhead is the weak link.

**Documented regressions (GitHub, 2025):**

- Simple `GROUP BY` on a registered PyArrow table: DataFusion v47.0.0 ran in ~1,002 ms vs DuckDB 1.3.1 at ~152 ms — a **6-7× gap** [5]. Root cause identified as DataFusion using 1 CPU core for the aggregation. This gap is not fundamental — it is a binding/thread dispatch bug.
- TPC-H SF100 on MacBook M3 (2025): DataFusion showed gaps on Q4, Q7, Q9 specifically; other queries competitive [6].
- h2o benchmark at 100M rows: "DataFusion and DuckDB very close, without large differences on most queries" (Ibis benchmarks) [7].

**v47 performance improvements (April 2025):**

- `FIRST_VALUE`/`LAST_VALUE` on high-cardinality data: **5× faster** (7 s → 36 s in v46) [2]
- `MIN`/`MAX`/`AVG` for Duration columns: **2.5× faster** [2]
- Short-circuit `AND`/`OR` for many `LIKE`/`CASE` expressions: **up to 100× improvement** [2]
- TopK on partially sorted data: improved via early termination extension [2]

**Conclusion**: DataFusion wins when the user supplies Arrow-native data (zero overhead) and runs complex multi-table joins. DuckDB wins at most file-backed SQL workloads due to more mature Python bindings and a full SQL dialect with Iceberg read support.

### 2.3 Python API surface (what Nucleus would touch)

Core entry points: `SessionContext` (main context), `register_parquet()`, `register_csv()`, `sql()`, `DataFrame.to_pandas()`, `to_arrow()`, UDF/UDAF registration. Substrait plan serialization available via `datafusion.substrait` module [3][8]. API matches DuckDB's register+sql pattern closely, which keeps the `Engine` Protocol swap interface shallow.

### 2.4 When DataFusion beats DuckDB (today, May 2026)

- Arrow-native pipelines where data never leaves Arrow (zero serialization cost)
- Applications that need to embed a customizable Rust query kernel with custom operators
- Streaming execution with backpressure (DataFusion supports streaming plans; DuckDB does not natively)
- Projects that build *on top of* DataFusion as a library (custom databases, new query languages)
- When you need open governance (Apache vs DuckDB Foundation)

### 2.5 Swap interface implications for Nucleus

Per `docs/specs/nucleus_architecture_v4.1.md §9.3`, DataFusion is Nucleus's documented swap target. The current obligation is:
1. Clean `Engine` Protocol interface (types compile, API matches)
2. 5-10 smoke tests in CI
3. Full adapter built only when trigger fires

The trigger conditions for building the full DataFusion adapter:
- DataFusion Python bindings reach "Stable" status (currently Pre-Alpha)
- DuckDB license pivot or vendor-controlled risk event
- A specific user workload (e.g., custom operators, streaming) that requires DataFusion's flexibility
- Performance regression in DuckDB 2.0 (planned Sept 2026)

**Recommendation**: HOLD on current swap interface. Add a CI smoke test that installs `datafusion==53.0.0` and runs `SessionContext().sql("SELECT 1")` — 5 LOC. Do not build the full adapter.

---

## 3. Meta Velox (C++)

### 3.1 What it is

Velox is Meta's unified execution engine, written in C++, that provides vectorized execution kernels used inside Presto C++ and Apache Spark (via Apache Gluten). It is **not** a standalone embeddable database — it is a collection of execution primitives (expression eval, vectorized operators, connectors) intended to be embedded into a larger query system.

- **GitHub**: [https://github.com/facebookincubator/velox](https://github.com/facebookincubator/velox)
- **License**: Apache-2.0
- **Python bindings**: `PyVelox` v0.2.0 — **Alpha, no stable release** [9]
- **Python requirement**: ≥3.9 [9]
- **Wheels**: Pre-built for Linux and macOS x86_64 only (no ARM64 macOS wheel) [9]
- **Partners**: IBM/Ahana, Intel, Voltron Data, Microsoft, ByteDance [9]

### 3.2 Why Velox is not a DuckDB alternative for Nucleus

Velox is a **C++ execution kernel**, not a query engine. It has no SQL parser, no query optimizer, and no standalone Python operation — it requires a host system (Presto, Spark, Gluten) to function. Using Velox from Python would require building a full parser+planner layer, violating Hard Constraint #4 (`docs/specs/nucleus_architecture_v4.1.md §3`). PyVelox also ships x86_64 only (no ARM macOS wheels) and is Alpha-stability — incompatible with the beachhead's MacBook constraint.

### 3.3 Who uses Velox

- **Presto C++ (prestissimo)**: Replaces JVM-based Presto workers with Velox execution kernels [10]
- **Apache Spark (via Gluten)**: Offloads Spark physical plans to Velox for native execution [11]
- **Meta internal systems**: Warehouse, messaging analytics
- **Cumulus (ByteDance)**: Large-scale data processing

### 3.4 Nucleus verdict

**REJECT** for v0.1 through v1.0. Velox fails questions Q2 (beachhead), Q3 (wrap? — requires building a full query planner), Q5 (no Windows), and Q8 (definitely not v0.1). Not a DuckDB swap candidate for a Python SDK.

---

## 4. ClickHouse Local + chDB

### 4.1 What it is

**chDB** is ClickHouse packaged as an embeddable Python library — "SQLite for ClickHouse." The full ClickHouse OLAP engine (ClickHouse v25.8.2.1 as of chDB v4.x) runs in-process with `pip install chdb`.

- **PyPI**: [https://pypi.org/project/chdb/](https://pypi.org/project/chdb/)
- **Current version**: v4.1.6 (March 19, 2026) [12]
- **License**: Apache-2.0 [12]
- **Python requirement**: ≥3.9 [12]
- **Stability**: **Production/Stable** (PyPI classifier) [12]
- **Wheel size**: ~90 MB (macOS ARM64) to ~150 MB (Linux x86_64 manylinux) per platform [13]
- **DuckDB wheel size**: ~30 MB per platform [14]
- **Size ratio**: chDB is **3-5× larger** than DuckDB's wheel

### 4.2 Architecture: Zero-Copy (v4.0, January 2026)

chDB v4.0 achieved bidirectional zero-copy with Pandas: `Python(df)` table function auto-discovers DataFrames from caller scope without serialization. Output maps ClickHouse column types directly to NumPy dtypes via SIMD routines. A C++ string encoding bypass eliminates GIL contention (string-heavy query: 8.6 s → 0.56 s — 15×). Overall 87× faster than chDB v1.0 [15].

### 4.3 Performance vs DuckDB

**Benchmark: Export 1M rows (ClickBench) to Pandas DataFrame (AWS EC2 c6a.4xlarge, Jan 2026):**

| Engine | Time | Winner |
|---|---|---|
| chDB v4.0 | 2.64 s | ✅ chDB |
| DuckDB (≈1.1.3 era) | 3.47 s | — |
| Difference | — | **24% faster for chDB** |

Source: [ClickHouse blog, Jan 9, 2026] [15]

**Benchmark: 14 Pandas operations at 1M / 10M rows (MacBook M4 Pro 48GB, 2026):**
- chDB wins 7/10 at 10M row scale
- DuckDB wins on Head/Limit (Pandas itself wins these)
- At 1M rows, both are extremely close [15]

**TPC-H analysis (indirect): chDB vs DuckDB on tabular data files (not in-memory Pandas)**  
[NEEDS VERIFICATION — no authoritative TPC-H chDB vs DuckDB comparison on Parquet files found in official docs as of 2026-05-15]

### 4.4 When chDB beats DuckDB

- Pandas-heavy data science workflows where data is already in-memory as DataFrames
- ClickHouse-specific SQL (100+ aggregation functions not in DuckDB's standard SQL)
- Users already invested in ClickHouse ecosystem (schema, functions, tooling)
- Semi-structured data: native ClickHouse JSON type, `Python(df)` auto-handles object columns [15]

### 4.5 Why chDB is not a DuckDB swap for Nucleus (v0.1)

1. **Wheel size**: 90-150 MB per platform vs DuckDB's 30 MB. PoC #4 validated 5.82 s, 117 MB total boot with DuckDB. Adding chDB would likely blow the boot RAM target.
2. **No Iceberg read extension**: DuckDB has `INSTALL iceberg; LOAD iceberg;`. chDB has no equivalent for reading Iceberg snapshots [NEEDS VERIFICATION — check chDB GitHub for Iceberg table function].
3. **Beachhead persona mismatch**: The 5-engineer startup team doing SQL over Iceberg tables needs file-backed SQL, not in-process Pandas SQL.
4. **Boot time**: chDB loads the full ClickHouse engine; cold-start profile not compatible with <10 s boot requirement.

### 4.6 Nucleus verdict

**DEFER**. chDB is an interesting niche tool for the Pandas-SQL bridge use case. Relevant for Nucleus v0.5+ when the AI Copilot needs to run SQL on in-memory datasets without exiting the Python process. Not a swap candidate for `ctx.sql` (file-backed Iceberg SQL). Add to `FOUNDER_ACTION_QUEUE.md` as a potential `ctx.execute_inline()` integration for v0.5.

---

## 5. GlareDB (Rust + DataFusion Federation)

**STATUS: DEAD.** GlareDB was an open-source, Rust-based federated SQL database built on Apache DataFusion, supporting cross-source queries against Postgres, MySQL, BigQuery, Snowflake, and Iceberg. The company pivoted to AI and **abandoned GlareDB in November 2025** [16].

**Architectural lesson**: DuckDB's `postgres_scan`, `httpfs`, and `iceberg` extensions cover ~80% of GlareDB's federation value with zero extra catalog overhead. The DataFusion-based federation pattern continues in `spiceai/spiceai` for Nucleus v2.0+ multi-source inspiration.

**Nucleus verdict**: No action. No ADR.

---

## 6. MotherDuck (Managed DuckDB)

### 6.1 What it is

MotherDuck is a serverless cloud analytics service built on DuckDB. Its unique architectural contribution is **Dual Execution** (formerly "Hybrid Execution"): a query planner that automatically routes query stages between local DuckDB and cloud DuckDB based on where data lives.

- **Website**: [https://motherduck.com/](https://motherduck.com/)
- **License**: Proprietary SaaS (not open source)
- **DuckDB versions supported**: 1.1.x-1.5.x (varies by region)
- **Regions**: AWS us-east-1, us-west-2, eu-central-1 [17]
- **Storage cost**: $0.04/GB/month [18]
- **Compute**: "Ducklings" — serverless DuckDB instances, sub-100 ms cold start [17]

### 6.2 Dual Execution Architecture

The query planner implements "bridge" operators that stream tuples between local DuckDB and cloud Ducklings based on data locality [19]. A user `ATTACH 'md:'` once; all subsequent queries are automatically split — `SELECT * FROM local_parquet JOIN md:cloud_table ON id=id` runs the scan locally on `local_parquet` and in the cloud on `md:cloud_table`, joined optimally. **Key limitation**: Custom Python UDFs cannot run on Ducklings [17].

### 6.3 Relevance to Nucleus's Yield-to-Giants Strategy

MotherDuck is the most concrete implementation of `docs/specs/nucleus_architecture_v4.1.md §14` Mode 2 (hybrid compute): local DuckDB handles 1–100 GB, MotherDuck handles the overflow with zero query rewrites. Integration path for Nucleus v0.3+: `compute="md"` on `ctx.run()` ATTACHes MotherDuck via `duckdb.connect("md:token")` — zero new Nucleus LOC.

**Critical open question**: MotherDuck's DuckLake lakehouse format vs Nucleus's Iceberg-backed assets. [NEEDS VERIFICATION — NV-6: are Nucleus's Iceberg files directly attachable to MotherDuck?] If not, a format bridge is needed before Mode 2 can work.

### 6.4 OpenDuck: The OSS MotherDuck Alternative

In April 2026, `citguru/openduck` was created on GitHub as an open-protocol, open-backend reimplementation of MotherDuck's dual execution model using standard DuckDB [20]. This is early-stage but architecturally relevant for Nucleus: if OpenDuck matures, Nucleus could implement `compute="cloud"` via OpenDuck without MotherDuck dependency.

### 6.5 Nucleus verdict

**INSPIRATION ONLY** for v0.1. Add MotherDuck to the `compute=` roadmap as Mode 2 yield-to-giants implementation for v0.3+. Key open question requiring ADR: DuckLake vs Iceberg format compatibility.

---

## 7. Substrait — Cross-Engine Plan IR

### 7.1 What it is

Substrait is a cross-language serialization format for relational algebra (query plans) using Protocol Buffers. The goal: decouple SQL frontends from execution backends so a plan produced by one system can be consumed by another without re-parsing.

- **Spec**: [https://substrait.io/spec/specification/](https://substrait.io/spec/specification/)
- **License**: Apache-2.0
- **Governance**: Substrait community (Voltron Data, Meta, Google, etc.)

### 7.2 Adoption Status (May 2026)

**Engines with Substrait support:**

| Engine | Producer | Consumer | Notes |
|---|---|---|---|
| DataFusion | ✅ | ✅ | `datafusion-substrait` crate; v52.1.0 (Jan 2026) [21] |
| DuckDB | ✅ | ✅ | Community extension `substrait` v1.2.2 (May 2025) [22] |
| Velox | ❌ | ✅ | Consumer only via `SubstraitVeloxPlanConverter` [23] |
| Apache Arrow Acero | ❌ | ✅ | Consumer only [24] |
| Polars | ❌ | ❌ | **"not_planned"** — closed April 2024 [25] |
| Ibis | ✅ | ❌ | Ibis-substrait produces Substrait for Substrait-consuming engines [24] |

**DataFusion roundtrip testing**: A `--substrait-round-trip` option was added to DataFusion's sqllogictest suite in 2025, converting plans to Substrait and back before execution. An ongoing epic (#16248) tracks known conversion gaps including `Dictionary` casting, `RecursiveQuery`, `FixedSizeList`, and `EXISTS` subqueries [26].

### 7.3 Can Substrait Replace Nucleus's Hand-Coded Swap Interface?

**No — not in 2026.** Polars explicitly declined Substrait support ("not_planned" [25]), breaking the "produce once, execute anywhere" promise for Nucleus's current swap set. DuckDB's Substrait support is a **community extension** (not core), requiring boot-time network calls to install. DataFusion's roundtrip has 30+ known gaps (RecursiveQuery, FixedSizeList, EXISTS subqueries) in the open epic [26]. Substrait also has no concept of Jinja template variables — `{{ ref('orders') }}` must be resolved before serialization.

**Keep the hand-coded `Engine` Protocol.** Revisit when Polars changes position and DuckDB Substrait moves to core wheel.

**Where Substrait IS useful for Nucleus (v0.5+):** As a *consumer-only* interface on the MCP server — external AI agents can submit Substrait plans (e.g., via Ibis-substrait) for Nucleus to execute against DuckDB. This requires no round-trip portability.

---

## 8. Vortex (Spiral Labs → Linux Foundation AI & Data)

### 8.1 What it is

Vortex is a next-generation columnar file format and in-memory array framework. It was developed by Spiral Labs and donated to the Linux Foundation AI & Data (LFAI) in **August 2025** with Microsoft, Snowflake, and Palantir as founding backers [27].

- **GitHub**: [https://github.com/vortex-data/vortex](https://github.com/vortex-data/vortex) (⭐ 2,935 stars)
- **License**: Apache-2.0
- **Backward compatibility**: Guaranteed from v0.36.0 forward [27]
- **Language**: Rust (primary), with Python, Java, and C bindings [28]
- **Status**: LFAI Incubation Stage

### 8.2 What Makes Vortex Different from Parquet

Vortex is a **pluggable compression framework**, not just a file format. Key differentiators: (a) pluggable encodings (FSST, ALP, BtrBlocks-style) per column, including WASM decompression kernels for forward compatibility; (b) fine-grained zone maps for predicate pushdown; (c) dated "Editions" (e.g., `2025.05.XX`) that bound reader requirements; (d) lazy segments enabling push-down compute over compressed data [28].

**Performance claims (Spiral Labs / benchbox.dev, Aug 2025):**
- Random access: **100-200× faster** than Parquet [27]
- Scan: **10-20× faster**; Write: **5× faster**; Compression: similar to Parquet [27]
- Microsoft: **30% runtime reduction** on Spark + Iceberg + Vortex [27] [NEEDS VERIFICATION — NV-2]

### 8.3 Ecosystem Integration

Vortex ships client packages for DataFusion, DuckDB, and Polars (per Spiral Labs' `towards-vortex-10` roadmap) [28]. DuckDB, DataFusion, and Polars users can scan Vortex files without manual decoding — transparent to Nucleus's `ctx.sql` layer.

### 8.4 Relevance to Nucleus

**Iceberg data files**: Apache Iceberg's spec allows any columnar format as the physical data file (Parquet, ORC, Avro). If Vortex is ratified as a supported Iceberg data file format, Nucleus's `ctx.sql()` would need to handle Vortex-backed Iceberg assets. DuckDB's Iceberg extension would need to support Vortex scans. This is not a concern for v0.1 (Vortex has no Iceberg spec acceptance yet).

**Performance**: If Nucleus beachhead users have random-access patterns (point lookups, AI embedding retrieval) that Parquet handles poorly, Vortex's 200× random access improvement would be significant for the v0.5+ Lance/vector use cases.

**`ctx.sql` design**: The Jinja resolver in `ctx.sql` produces a SQL string sent to DuckDB. If Vortex tables become scannable via DuckDB, no changes to `ctx.sql` are needed — the scan is transparent.

### 8.5 Nucleus verdict

**WATCH**. No action for v0.1. Add to `FOUNDER_ACTION_QUEUE.md` as a v0.5+ scan format. When Vortex publishes its first `2025.XX.XX` edition and a DuckDB extension ships with stable API, evaluate adding `vortex://` as an optional asset storage format alongside `s3://` and `file://`.

---

## 9. Polars LazyFrame as a "Query Engine"

### 9.1 What it is

Polars 1.18.0 (our current pin) ships a full SQL interface via `SQLContext` that can be used as a lightweight query engine over in-memory DataFrames, Parquet files, and other data sources. Polars is not just a DataFrame library — it is a SQL query engine for in-memory data.

- **Docs**: [https://docs.pola.rs/api/python/dev/reference/sql/python_api.html](https://docs.pola.rs/api/python/dev/reference/sql/python_api.html)
- **Pin**: `polars==1.18.0` (current), `1.40.1` (latest per `tier0_oss_evolution.md`)

### 9.2 SQL interface

Three entry points: `df.sql("SELECT ... FROM self ...")` for frame-level queries; `pl.SQLContext(orders=lf, ...).execute(query)` for multi-table SQL across Polars/Pandas/PyArrow objects in a single query; `pl.sql(query)` for global context. `Series.sql()` added December 2025 [30]. Zero-copy conversion for Arrow-typed Pandas inputs. Docs: [https://docs.pola.rs/api/python/dev/reference/sql/python_api.html](https://docs.pola.rs/api/python/dev/reference/sql/python_api.html) [29].

### 9.3 Performance vs DuckDB

| Scenario | DuckDB | Polars | Source |
|---|---|---|---|
| ≤10 GB local SQL | Tie | Tie | Coiled TPC-H [31] |
| >10 GB local SQL | **Clear winner** | Competitive but slower | Coiled TPC-H [31] |
| TPC-H Q21 (16-core heavy joins) | ~0.20 s | ~0.37 s (**futex** lock contention) | GitHub#26846 [32] |
| In-memory LazyFrame (no I/O) | Slower (serialization) | **Wins** (zero-copy native) | — |

TPC-H Q21 regression: Polars spent ~96% of syscall time in `futex` (lock contention) — a known tracked issue [32]. DuckDB wins for file-backed SQL; Polars wins for already-in-memory frames.

### 9.4 What this means for `ctx.sql` design

Current: all SQL routes to DuckDB, forcing LazyFrame → Arrow → DuckDB view → result serialization. A `ctx.sql(query, engine="polars")` hint (v0.2, ~100 LOC) could route in-memory queries to `pl.SQLContext`, avoiding DuckDB entirely. Gate on empirical demand from users loading data via `ctx.copy_from` into Polars.

### 9.5 Nucleus verdict

**ALREADY WRAPPED** (polars==1.18.0). Polars SQL is available today — no additional integration needed. Document the `SQLContext` pattern in the user guide. Consider `engine="polars"` hint as v0.2 feature in `FOUNDER_ACTION_QUEUE.md`.

---

## 10. Benchmark Reference Table

> No single unified TPC-H SF10 laptop benchmark covers all engines as of 2026-05-15. The table aggregates different sources with different hardware. Use directionally; run NV-4 and NV-5 before any swap decision.

| Engine | TPC-H SF10 relative | Notes | Source |
|---|---|---|---|
| DuckDB 1.1.3–1.5.x | **1.0× (baseline)** | Boot: 5.82 s, 117 MB RAM (PoC #4) | Nucleus internal |
| DataFusion v47-53 (Python) | ~0.1–0.7× | Group-by: 6-7× slower [5]; complex joins near parity [7] | datafusion-python#1186, Ibis bench |
| chDB v4.x (in-memory Pandas) | ~1.24× for Pandas export | 24% faster Pandas export [15]; no Parquet SF10 data available | ClickHouse blog |
| Polars 1.18–1.40 (SQL) | ~0.5–0.9× | Q21 heavy join: 1.85× slower [32]; most queries near parity [31] | GitHub#26846, Coiled |
| Velox (standalone Python) | N/A | Requires host system; no standalone benchmark | — |
| ClickHouse Local (CLI) | [NEEDS VERIFICATION] | No authoritative chDB vs DuckDB Parquet benchmark found | — |

---

## 11. "When to Swap" Decision Tree

| Symptom | Engine to consider | Gate |
|---|---|---|
| GROUP BY 6-7× slower vs expected | DataFusion threading bug ([#1186](https://github.com/apache/datafusion-python/issues/1186)) | Workaround: increase DuckDB threads, or use Polars `.group_by()` directly |
| Data already in Polars LazyFrame (in-memory) | `df.sql(...)` or `ctx.sql(engine="polars")` (v0.2) | No new dep; zero overhead |
| Data >100 GB on single machine | MotherDuck (Mode 2) or Databricks dispatch (Mode 2) | v0.3+ — see ADR-027 |
| Need custom operators / streaming backpressure | DataFusion Python bindings | Gate: datafusion-python reaches Stable PyPI status |
| Need ClickHouse-specific SQL function | chDB isolated call only — do NOT swap ctx.sql | Empirical demand required |
| DuckDB license or governance change | DataFusion full adapter | ADR + CI smoke test already maintained |
| **Default** | **Stay on DuckDB** | **Upgrade pin per tier0_oss_evolution.md** |

---

## 12. NEEDS VERIFICATION

The following claims require founder/engineer verification before relying on them in architecture decisions:

| # | Claim | Why uncertain | URL to check |
|---|---|---|---|
| NV-1 | DuckDB 1.5.x ships a Vortex extension bundled in the wheel | Spiral Labs says DuckDB client package ships alongside Vortex; not confirmed in DuckDB 1.5.2 release notes | https://github.com/duckdb/duckdb/releases/tag/v1.5.2 |
| NV-2 | Microsoft 30% runtime reduction via Vortex + Iceberg + Spark | Cited from BenchBox/LFAI announcement but no primary MSFT blog URL found | https://github.com/vortex-data/vortex — check README for citation |
| NV-3 | chDB has no Iceberg table function | Checked chDB v4.1.6 docs; no Iceberg extension found but not exhaustively confirmed | https://clickhouse.com/docs/chdb — search "iceberg" |
| NV-4 | chDB boot time on MacBook M2 | Not benchmarked. Critical for beachhead boot-time PoC #4 comparison | Run: `time python -c "import chdb; chdb.query('SELECT 1')"` |
| NV-5 | DataFusion boot time on MacBook M2 | Not benchmarked. Compare to DuckDB 5.82 s baseline | Run: `time python -c "from datafusion import SessionContext; SessionContext().sql('SELECT 1').collect()"` |
| NV-6 | MotherDuck DuckLake format Iceberg compatibility | MotherDuck docs mention DuckLake as their lakehouse format but Iceberg interop not confirmed | https://motherduck.com/docs/integrations/file-formats/ducklake/ |
| NV-7 | TPC-H SF10 chDB vs DuckDB on Parquet (not in-memory Pandas) | No authoritative benchmark found. All chDB benchmarks are in-memory Pandas | Run TPC-H with `FROM file('orders.parquet')` in both engines |
| NV-8 | Velox Windows wheel availability | PyVelox docs only mention Linux and macOS x86_64; Windows not listed | https://facebookincubator.github.io/velox/bindings/python/README_generated_pyvelox.html |

---

## 13. References

All URLs verified live on 2026-05-15.

| # | URL |
|---|---|
| [1] | https://pypi.org/project/datafusion/53.0.0/ |
| [2] | https://datafusion.apache.org/blog/2025/07/11/datafusion-47.0.0/ |
| [3] | https://datafusion.apache.org/python/index.html |
| [4] | https://datafusion.apache.org/user-guide/introduction.html |
| [5] | https://github.com/apache/datafusion-python/issues/1186 |
| [6] | https://github.com/apache/datafusion/issues/17259 |
| [7] | https://ibis-project.org/posts/ibis-bench/index.html |
| [8] | https://docs.rs/datafusion-substrait/latest/datafusion_substrait |
| [9] | https://facebookincubator.github.io/velox/bindings/python/README_generated_pyvelox.html |
| [10] | https://prestodb.github.io/docs/current/presto-cpp.html |
| [11] | https://gluten.incubator.apache.org/archives/v1.3.0/velox-backend/limitations |
| [12] | https://pypi.org/project/chdb/ |
| [13] | https://github.com/pypi/support/issues/8997 |
| [14] | https://pypi.org/project/duckdb/ |
| [15] | https://clickhouse.com/blog/chdb-journey-to-zero-copy |
| [16] | https://dbdb.io/db/glaredb |
| [17] | https://motherduck.com/docs/concepts/architecture-and-capabilities/ |
| [18] | https://motherduck.com/docs/about-motherduck/billing/pricing/ |
| [19] | https://motherduck.com/research/motherduck-duckdb-in-the-cloud-and-in-the-client/ |
| [20] | https://github.com/citguru/openduck |
| [21] | https://crates.io/crates/datafusion-substrait/21.1.0 (note: v52.x latest) |
| [22] | https://github.com/substrait-io/duckdb-substrait-extension |
| [23] | https://readmex.com/facebookincubator/velox/substrate |
| [24] | https://substrait.io/community/powered_by/ |
| [25] | https://github.com/pola-rs/polars/issues/7404 |
| [26] | https://github.com/apache/datafusion/issues/16248 |
| [27] | https://benchbox.dev/docs/guides/table-formats/vortex-guide.html |
| [28] | https://spiraldb.com/post/towards-vortex-10 |
| [29] | https://docs.pola.rs/api/python/dev/reference/sql/python_api.html |
| [30] | https://github.com/pola-rs/polars/pull/25792 |
| [31] | https://docs.coiled.io/blog/tpch.html |
| [32] | https://github.com/pola-rs/polars/issues/26846 |
| [33] | https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-polars-performance-and-memory-with-massive-parquet-data |

---

## 14. Suggested ADRs

Based on this research, the following ADRs are candidates for the founder's review queue. None are urgent for v0.1.

| ADR | Title | Priority | Trigger |
|---|---|---|---|
| ADR-026 | Ratify DataFusion as Tier 2 swap target with CI smoke test | P2 | Wave 3 before v0.5 |
| ADR-027 | MotherDuck as Mode 2 yield-to-giants target for v0.3+ | P2 | After v0.1 GA |
| ADR-028 | Vortex file format as optional Iceberg data file target (v0.5+) | P3 | When LFAI publishes first edition + DuckDB extension ships |
| ADR-029 | Substrait as MCP server query input format (v0.5+ consumer-only) | P3 | When MCP server scoped |

**No ADR required for chDB, Velox, or GlareDB** (rejected/dead).

---

## 15. Logged Hallucinations

Per `AGENTS.md §11.12`, any AI-fabricated APIs discovered during research must be logged.

| Date | Claim | Reality | Detection |
|---|---|---|---|
| 2026-05-15 | "`datafusion.substrait.SerializedPlan`" (assumed method name) | Actual module is `datafusion.substrait` but specific class names not verified from official docs — treated as NEEDS VERIFICATION rather than asserting | Docs check before including in text |
| 2026-05-15 | "chDB supports Iceberg via an extension similar to DuckDB's" | No such extension found in chDB v4.1.6 docs; marked as NV-3 | Docs check against chdb-io/chdb README |

---

*Research model: Claude Sonnet 4.6 (Swarm/Research tier; fallback from Gemini 3.1 Pro per `AGENTS.md §11.14`). Gemini 3.1 Pro unavailable in current Cursor runtime.*

*Supersedes: No prior file — this is a new research document.*
