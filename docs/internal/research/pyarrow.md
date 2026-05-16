# PyArrow — In-Memory Tier-0 Substrate

> **Pinned**: `pyarrow==18.1.0` (released 2024-11-26, verified on PyPI 2026-05-13)  •  **License**: Apache-2.0  •  **Docs**: <https://arrow.apache.org/docs/python/>
> **Status in Nucleus**: **Tier 0 (immortal)** per `docs/specs/nucleus_architecture_v4.1.md` §3.1 / §4.1 — one of seven bedrock substrates alongside Apache Iceberg, Apache Parquet, Lance, S3 API, OpenLineage, OpenTelemetry. **No swap target ever.**
> **Wrapping mode**: **Zero wrapping behind an interface.** Apache Arrow IS the in-memory interface; wrapping it defeats the contract. Nucleus calls `pyarrow` directly in 3-4 narrow places (§3); the rest is inherited transitively via polars / duckdb / pyiceberg / dlt.

Official-docs anchor per [AGENTS.md Hard Constraint #10](../../../AGENTS.md). Read before touching any L0 ↔ L1 conversion path, or whenever a downstream pin (polars, duckdb, pyiceberg, dlt) is upgraded — the highest pyarrow floor across our pinned deps is what `pip install -e .[dev]` resolves to, and `pyiceberg==0.8.1`'s `pyarrow<19.0.0` is the binding ceiling. PyArrow is the **one dependency every other Tier 1/2 component already pulls transitively**; a poor pin here propagates everywhere.

---

## §1. What pyarrow is, in Nucleus terms

**Apache Arrow** is a language-independent **columnar in-memory format** plus a multi-language toolbox (C++, Rust, Java, Go, JS, R, Python, …) of zero-copy primitives — per [the docs](https://arrow.apache.org/docs/python/index.html), *"a universal columnar format and multi-language toolbox for fast data interchange and in-memory analytics."* **`pyarrow`** is the Python binding — a Cython layer over the C++ Arrow libraries, distributed as platform-specific binary wheels. The wheel ships the C++ runtime; **no JVM**, no daemon, no network hop (Hard Constraint #1).

**Why Tier 0 per v4.1 §3.1 + §4.1**: Arrow's columnar memory layout is the **interop contract** that lets pyiceberg, polars, duckdb, dlt, and OpenLineage's batch consumers share data **without copies**. Every engine boundary in Nucleus — `DuckDB → Polars`, `Polars → pyiceberg`, `pyiceberg → DuckDB`, `dlt → pyiceberg` — is an Arrow handoff at the buffer level. Without Arrow as the shared format, every boundary becomes a Python-object round-trip: 10-100× slowdown, GC pressure, schema drift. v4.1 §4.1 lists Arrow alongside Iceberg, Parquet, Lance, S3 API, OpenLineage, OpenTelemetry as the "immortal layer ... open standards backed by multi-vendor consortiums, zero death risk." Same status; **no swap target ever** per v4.1 §9.2.

**Why Arrow specifically**: Wes McKinney's 2017 essay [*Apache Arrow and the '10 Things I Hate About pandas'*](https://wesmckinney.com/blog/apache-arrow-pandas-internals/) is the historical North Star — pandas's NumPy-backed `BlockManager` creates 5-10× RAM amplification ("my 10 GB dataset needs 64-128 GB of RAM"). Arrow was designed to replace that representation across the Python data ecosystem with zero-copy columnar buffers. **Governance**: ASF Top-Level Project, Apache-2.0, committers from Snowflake, Databricks, Google, Meta, NVIDIA, Voltron Data, AWS — the multi-vendor pattern v4.1 §4.1 requires for Tier 0.

---

## §2. Version verification (PyPI, 2026-05-13)

Source: `https://pypi.org/pypi/pyarrow/18.1.0/json` + `https://pypi.org/simple/pyarrow/`.

| Check | Result |
|---|---|
| `18.1.0` real release? | ✓ Uploaded **2024-11-26 02:01:48 UTC**; sdist + wheels per CPython × platform. |
| Yanked? | ✗ No. PyPI `vulnerabilities` array empty. |
| License (PyPI classifier) | `License :: OSI Approved :: Apache Software License`. **Apache-2.0** (ASF TLP). |
| Maintainer | `"Apache Arrow Developers"` (Apache Software Foundation; not single-vendor). |
| `requires_python` | `>=3.9` — our `>=3.11,<3.13` pin is well inside. ✓ |
| `requires_dist` (runtime) | **None.** Only `extra == "test"` deps. PyArrow ships the C++ runtime in the wheel. |
| Wheel coverage | `cp39/310/311/312/313` × `manylinux_2_17/2_28_{x86_64,aarch64}` + `macosx_12_0_{arm64,x86_64}` + `win_amd64`. **Windows + macOS-arm64 wheels present** — no source build on beachhead platforms. |
| Wheel sizes | Win cp311 ≈ 25.1 MB ; macOS arm64 ≈ 29.6 MB ; Linux manylinux_2_28 x86_64 ≈ 40.1 MB. |
| JVM-free | ✓ C++ extensions, not Java. Hard Constraint #1 satisfied. |
| Latest stable on PyPI 2026-05-13 | **`24.0.0`**. We are ~6 major versions behind — **deliberate** (see below). |

**Why we pin at 18.1.0 specifically**: `pyiceberg==0.8.1` declares `pyarrow<19.0.0,>=14.0.0` (per [`pyiceberg.md`](./pyiceberg.md) §2) — that upper bound is the binding ceiling. `polars==1.18.0` (pyarrow extra) requires `>=7.0.0`; `dlt==1.26.0` requires `>=16.0.0` (per [`dlt.md`](./dlt.md) §6); `duckdb==1.1.3` declares no pyarrow dep at all (zero-copy via Arrow C-data interface, version-independent at the wheel boundary). Highest floor: 16.0.0 (dlt); only ceiling: `<19.0.0` (pyiceberg). **18.1.0 sits inside that band** and matches what polars 1.18.0 was tested against at release time.

**The gap to 24.0.0 is deliberate.** PyArrow majors ship with C++ ABI changes that affect every zero-copy boundary (polars's Arrow Stream / Capsule import, duckdb's `.arrow()`, pyiceberg's writer). The 18.1.0 → 19.x bump is **gated by ADR-003** (pyiceberg 0.8.1 → 0.11.x — see `docs/decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md`). Once pyiceberg ≥ 0.9 lifts the `<19.0.0` cap, pyarrow moves forward in **one-component-per-PR** steps per Hard Constraint #11, with smoke tests against polars + duckdb + pyiceberg in lockstep.

---

## §3. Nucleus integration surface (the only APIs we actually call)

**Scope discipline.** PyArrow's public surface is enormous (1000+ classes across `pa`, `pa.compute`, `pa.dataset`, `pa.parquet`, `pa.csv`, `pa.json`, `pa.fs`, `pa.flight`, `pa.feather`, `pa.orc`, `pa.cuda`, `pa.acero`). **Nucleus calls a tiny slice.** Document only that slice; flag the rest as out-of-scope (§3.7) so future AI agents can't bloat the integration without an ADR. URLs use `arrow.apache.org/docs/python/...` which serves latest stable (24.0.0); **NEEDS VERIFICATION** each signature is unchanged in 18.1.0 — spot-check against the version-pinned docs build (`/docs/18.1/python/...`) before merging.

### §3.1 In PoC #1 (Dagster Error Translation Layer)

**Zero direct pyarrow calls expected.** PoC #1 translates exceptions; it never touches in-memory data. The only indirect contact: a caught exception may carry an Arrow-level cause whose `__cause__` chain includes `pyarrow.lib.ArrowInvalid` or `ArrowIOError`. The translator walks `__cause__` defensively without importing pyarrow. **NEEDS VERIFICATION** (PoC #1 Week 1): confirm both classes inherit from `Exception` (not `BaseException`) — verify with `pa.lib.ArrowInvalid.__mro__`. Don't import from `pyarrow.lib` in production — public re-exports live at the module root.

### §3.2 In PoC #2 (`ctx.sql` + Jinja resolver)

The resolver returns a rendered SQL string; DuckDB executes; the result crosses back into Polars via Arrow. Two zero-copy boundaries:

- `DuckDBPyRelation.arrow() → pyarrow.Table` (per [`duckdb.md`](./duckdb.md) §5) — returns by reference, no copy.
- `polars.from_arrow(table) → polars.DataFrame | LazyFrame` (per [`polars.md`](./polars.md) §5) — zero-copy when the Arrow buffer is caller-owned.

Neither site imports `pyarrow` for its own sake; the `pyarrow.Table` is the in-flight payload, not a thing we construct. **NEEDS VERIFICATION** (PoC #2): benchmark-confirm the `polars → arrow → duckdb → arrow → polars` round-trip allocates zero new buffers via `pa.default_memory_pool().bytes_allocated()` deltas (see [Memory Pools](https://arrow.apache.org/docs/python/api/memory.html#memory-pools)).

### §3.3 In PoC #3 (SQLite → Iceberg ingest)

The **only PoC where Nucleus constructs a `pyarrow.Table` itself**, because SQLite (via stdlib `sqlite3`) returns Python tuples and pyiceberg's `Table.append()` requires a `pyarrow.Table` (per [`docs/internal/research/pyiceberg.md`](./pyiceberg.md) §5).

```python
import pyarrow as pa
# Docs: https://arrow.apache.org/docs/python/generated/pyarrow.Table.html
# Pinned version: 18.1.0
table = pa.Table.from_pylist(rows, schema=pa_schema)
# or:
table = pa.Table.from_pydict(columns_dict, schema=pa_schema)
```

Both methods verified against the 24.0.0 docs: `from_pylist(cls, mapping, schema=None, metadata=None)`, `from_pydict(cls, mapping, schema=None, metadata=None)`. **Always pass an explicit `schema=`** — without it, pyarrow type-infers and may pick a wider type than the Iceberg target column (e.g. `large_string` for short strings via the pandas path). See §5 hallucinations.

### §3.4 In the Asset Materialization Adapter (v0.1)

After pyiceberg commits a snapshot, the AMA reads back the schema to emit an OL `SchemaDatasetFacet` (per [`docs/internal/research/openlineage.md`](./openlineage.md) §5.1):

- `pyiceberg.Table.scan().to_arrow() → pyarrow.Table` — already pyarrow, no copy.
- `pa_table.schema → pyarrow.Schema` — read-only attribute; iterate for `pyarrow.Field` objects to build the OL facet.

No pyarrow construction; the AMA only **reads** the schema.

### §3.5 Asset schema contracts (`@nucleus.contract`, v0.1)

A Nucleus asset's declared schema is a `pyarrow.Schema`; the materialized snapshot's schema (from pyiceberg) is also a `pyarrow.Schema`. Drift detection uses:

```python
declared.equals(materialized, check_metadata=False)
# Docs: https://arrow.apache.org/docs/python/generated/pyarrow.Schema.html
```

Verified signature: `equals(self, Schema other, bool check_metadata=False)`. The `False` default compares fields + types + nullability + field IDs, ignoring schema-level `KeyValueMetadata` — what we want, because pyiceberg roundtrips field IDs through schema metadata in some configurations.

### §3.6 Schema construction (shared across PoC #2 / #3 / contracts)

`pa.schema(fields)`, `pa.field(name, type, nullable=True, metadata=None)`, plus primitive factories (`pa.int64`, `pa.string`, `pa.timestamp(unit, tz=None)`, `pa.decimal128(precision, scale)`, `pa.list_(value_type)`, `pa.struct(fields)`, `pa.map_(key, value)`) are the only constructors Nucleus uses. All verified in the [Data Types and Schemas reference](https://arrow.apache.org/docs/python/api/datatypes.html).

**Timestamp unit discipline** (per [`type_mapping.md`](../../patterns/type_mapping.md) §6.4 + `duckdb.md` §7): Iceberg v2 caps `timestamp`/`timestamptz` at **microseconds** — use `pa.timestamp("us", tz="UTC")`. Never `pa.timestamp("ns", ...)` against Iceberg v2 — pyiceberg rejects the write. Spec v3 adds `timestamp_ns`; revisit post-v0.5.

### §3.7 NOT called by Nucleus (transitive only — DO NOT bloat)

These pyarrow surfaces are present transitively (polars / duckdb / pyiceberg / dlt pull them). **Nucleus code never imports or calls them.** Adding any of them as a first-class dep requires an ADR.

| Surface | Why we don't use it | Transitive user |
|---|---|---|
| `pyarrow.parquet.read_table` / `write_table` | Parquet I/O is pyiceberg's responsibility | pyiceberg, dlt |
| `pyarrow.fs.{S3,Local,Gcs}FileSystem` | We use `s3fs` via `pyiceberg[s3fs]` extras | pyiceberg via fsspec |
| `pyarrow.compute.*` (~250 kernels) | Aggregations / casts / predicates → DuckDB SQL or Polars expressions | polars, duckdb |
| `pyarrow.dataset.*` | pyiceberg uses internally for scans | pyiceberg, polars parquet readers |
| `pyarrow.flight.*` | Deferred to v0.5+ (yield-to-giants distributed compute) | — |
| `pyarrow.csv` / `pyarrow.json` / `pyarrow.feather` / `pyarrow.orc` | Ingest via Polars (`scan_csv`, `scan_ndjson`) or `ctx.copy_from` / dlt | dlt sources |
| `pyarrow.acero` | pyarrow's own query engine; we use DuckDB / Polars | — |
| `pyarrow.cuda` | No GPU path in Nucleus | — |
| `pyarrow.ipc` | v0.1 stays in-process | — |
| `pyarrow.Table.from_pandas` / `to_pandas` | Pandas forbidden as interop hop (`engineering.md` §11.4 + `type_mapping.md` §2 — Arrow is the pivot, never pandas) | — |

This list is **load-bearing**: future "wouldn't it be easier to use `pyarrow.compute.cast(...)` here?" suggestions get rejected against it. Compute lives in engines (DuckDB / Polars). I/O lives in pyiceberg / Polars / dlt. PyArrow is the buffer format, not an engine.

---

## §4. Zero-copy contracts (what we actually rely on)

PyArrow's value to Nucleus is **not its API surface**; it's the **C-data interface** ([Arrow C Data Interface spec](https://arrow.apache.org/docs/format/CDataInterface.html)) and the **PyCapsule protocol** ([extending types](https://arrow.apache.org/docs/python/extending_types.html#controlling-conversion-to-py-arrow-with-the-pycapsule-interface)) — the ABI-stable C-level handoff that lets polars (Rust), duckdb (C++), and pyiceberg (Python) all read each other's `pyarrow.Table` buffers without serialization.

Three production zero-copy boundaries Nucleus depends on:

| Boundary | Mechanism | Where it's documented |
|---|---|---|
| `duckdb.DuckDBPyRelation.arrow() → polars.from_arrow()` | Arrow C Stream interface; DuckDB writes result vectors into Arrow buffers; polars wraps them as a DataFrame without copy. | `duckdb.md` §5 + `polars.md` §8 |
| `polars.DataFrame.to_arrow() → pyiceberg.Table.append(arrow_table)` | `to_arrow()` exposes polars's internal Arrow buffers; pyiceberg's writer reads them column-by-column and emits Parquet. | `polars.md` §5 + `pyiceberg.md` §5 |
| `pyiceberg.Table.scan().to_arrow() → duckdb.from_arrow(t)` *(or `.to_duckdb("name", connection=conn)` which registers under the hood)* | pyiceberg materializes the snapshot's Parquet files into an Arrow Table; DuckDB registers it as a SQL view. | `pyiceberg.md` §5 + `duckdb.md` §5 |

**Cost when zero-copy breaks**: the boundary falls back to a Python-object round-trip (a stray `.to_pylist()`, a `pa.Table.from_pandas(df.to_pandas())` detour, or a pyarrow-extension-type polars/duckdb can't decode at C level). Symptoms: `nucleus run` fast on 100 MB and 100× slower on 1 GB; high GC time in `cProfile`; `RSS` ballooning from a tight columnar 1 GB to a sprawling 10 GB+. Detection: every PoC #4 benchmark records `pool.bytes_allocated()` deltas across each boundary; large allocations on a no-op handoff are the smoking gun.

**ABI coordination**: polars / duckdb / pyiceberg each compile against a specific pyarrow C++ ABI revision. A mismatched pyarrow upgrade silently breaks zero-copy — the data still moves, but as a Python-object copy. Per Hard Constraint #11, upgrade smoke tests must assert **buffer-pointer equality** across the boundary, not just "the test passes". v0.1 does not use Arrow IPC / Flight / Plasma (cross-process handoff is a v0.5+ concern when Nucleus may dispatch heavy assets to a sidecar process or to Databricks via Mode 2). All v0.1 Arrow handoffs are **in-process** and rely on C-data-interface pointer sharing inside one Python process.

---

## §5. Known AI hallucinations (verify before merge — log catches to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md))

These come from the standard pyarrow-confusion failure modes: AI mixes pandas APIs with pyarrow, invents convenience methods that "should exist", or splits a real method's behaviour across two fabricated ones. Verified against the [pyarrow.Table reference](https://arrow.apache.org/docs/python/generated/pyarrow.Table.html) and [datatypes API](https://arrow.apache.org/docs/python/api/datatypes.html) 2026-05-13.

1. ❌ **`pyarrow.Table.to_iceberg()`** — does not exist. Iceberg writes go through `pyiceberg.Table.append(arrow_table)` / `.overwrite(...)`. PyArrow has no Iceberg writer. (Often paired with the equally wrong `pa.parquet.write_table` suggestion — pyiceberg owns the writer.)
2. ❌ **`pyarrow.Schema.from_polars(...)`** / **`Schema.from_duckdb(...)`** — neither exists. Real path: `polars_df.to_arrow().schema` and `duckdb_conn.execute(sql).arrow().schema`. Always go through the Table.
3. ❌ **`pyarrow.Table.from_iceberg(...)`** — does not exist. Use `pyiceberg.Table.scan().to_arrow()`. The asymmetry is real: pyarrow is unaware of Iceberg; pyiceberg knows how to emit `pyarrow.Table`.
4. ❌ **`Field.metadata` / `Schema.metadata` as `dict[str, str]`** — wrong. Per the [Schema reference](https://arrow.apache.org/docs/python/generated/pyarrow.Schema.html), `metadata` returns `{b'key': b'value'}` — **`bytes` keys and values**, not `str`. AI commonly assumes `dict[str, str]` because the constructor accepts string-coercible keys; the **read-back** is bytes. Always encode/decode UTF-8 at the boundary.
5. ❌ **`pyarrow.dataset.write_dataset(...)` for Iceberg output** — wrong path. `pa.dataset.write_dataset` writes a pyarrow-native partitioned dataset (Hive-style directory layout); **no Iceberg manifest awareness** — readers won't see snapshots, time travel, schema evolution, or commit atomicity. Always route Iceberg writes through pyiceberg's `Table.append()` / `Transaction`.
6. ❌ **`pyarrow.Table.from_pandas(df)` as the polars-to-Arrow path** — works (polars exports a pandas-compatible interchange) but pulls pandas as a runtime dep and adds a copy. Real path: `polars_df.to_arrow()` — zero-copy (per `polars.md` §8).
7. ❌ **`pa.compute.cast(table, new_schema)`** as a cheap "schema-align" — exists (real function) but invokes Arrow's compute kernels per column; **not** the no-op some AI suggestions imply. To rename without changing types use `Table.rename_columns(names)`; cast only when types actually differ.
8. ❌ **Capitalised class constructors** — `Schema.__init__`, `Array.__init__`, `Table.__init__`, `Field.__init__` are **private**; the docs explicitly say *"Do not call this class's constructor directly. Instead use the [`pyarrow.schema()` / `array()` / `table()` / `field()`] factory function"*. AI suggestions of `pa.Schema([...])` or `pa.Array(list, type)` are calling private constructors. Always lowercase factory: `pa.schema([...])`, `pa.array(...)`, `pa.field(...)`, `pa.table(...)`.
9. ❌ **`pa.array([1, "a", None])` with mixed types** — coerces to a Python-object array (`pa.null()` or an extension type), losing the columnar fast path. Always pass `type=`: `pa.array([1, 2, 3], type=pa.int64())`, or attach a schema via `pa.Table.from_pylist(rows, schema=...)`.

When any of these is caught in a PR, log it to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md) with date, PR, and detection method.

---

## §6. Compatibility matrix (2026-05-13)

Verified against each component's PyPI metadata. The resolved pyarrow in `pip install -e .[dev]` is **18.1.0** (explicit top-level pin in `pyproject.toml` line 44), above every floor and below the binding ceiling.

| Caller | Declared pyarrow constraint | Source | Notes |
|---|---|---|---|
| `pyiceberg==0.8.1` | `pyarrow>=14.0.0,<19.0.0` | `pyiceberg.md` §2 | **Binding upper bound.** 18.1.0 is the latest in the band; 19.x blocked until pyiceberg upgrades (ADR-003). |
| `polars==1.18.0` *(pyarrow extra)* | `pyarrow>=7.0.0` | `polars.md` §2 | Core polars uses Arrow ABI directly (no pyarrow runtime requirement). |
| `duckdb==1.1.3` | (none) | `duckdb.md` §2 | Arrow C-data interface at the ABI level; our `.arrow()` boundary requires pyarrow installed. |
| `dlt==1.26.0` *(v0.3+)* | `pyarrow>=16.0.0` | `dlt.md` §6 | Not in v0.1; floor is informational. |
| `openlineage-python==1.47.1` | (none) | `openlineage.md` §2 | OL emits JSONL/HTTP from native dicts; no Arrow path. |
| Python | `>=3.11,<3.13` (ours) ↔ `>=3.9` (pyarrow 18.1.0) | `pyproject.toml` L19 | OK. pyarrow 24.0.0 still supports 3.11/3.12. |
| Windows 11 + WSL2 / macOS arm64 / Linux x86_64 | wheels ship for all | PyPI 2026-05-13 | ✓ No source build on beachhead platforms. |

**Coupled-upgrade implication**: Hard Constraint #11 mandates one-component-per-PR. The pyarrow / pyiceberg cluster is the one place that rule bends — pyiceberg's `<19.0.0` cap means `pyiceberg 0.8.1 → 0.11.x` (ADR-003) must precede `pyarrow 18.1.0 → 19+.x`. Upgrade sequence at v0.3: **ADR-003 (pyiceberg) → pyarrow bump → polars / duckdb minor catch-up**, each a separate PR with 24 h soak between.

---

## §7. Tier-0 immortal status (per Hard Constraint #9 + v4.1 §4.1 / §9.2)

Per v4.1 §3.1 (L0 Physics block lists Apache Arrow first), §4.1 (Tier-0 immortal table), and §9.2 (Composability Constitution Tier-0 list, Apache Arrow first entry), pyarrow is **immortal** — never swapped, never wrapped behind an `Engine`-style Protocol, because **Arrow IS the interface**. Same logic as Apache Iceberg, Apache Parquet, Lance, S3 API, OpenLineage, OpenTelemetry.

**Concrete implications for the codebase:**

- **No `docs/internal/swap/pyarrow.md` will ever be written.** Tier-0 components are not swappable by design. Introducing a "pyarrow swap target" is a v4.1 §4.1 violation requiring a constitutional amendment.
- **No `nucleus.physics.ArrowEngine`-style wrapper class.** Nucleus code calls `import pyarrow as pa` and uses `pa.Table`, `pa.Schema`, `pa.field`, `pa.schema` directly in the four narrow places listed in §3. Wrapping them behind a Protocol would (a) defeat the zero-copy contract by adding per-call indirection, and (b) imply a swap v4.1 §4.1 forbids.
- **PyArrow type names are allowed in user-facing output.** Unlike `dagster.`, `duckdb.`, `pyiceberg.` class names (which the Error Translation Layer per v4.1 §6.4 scrubs), Arrow type strings (`int64`, `timestamp[us, tz=UTC]`, `decimal128(18, 4)`, `list<element: string>`) are **part of the Nucleus user contract** — the schema vocabulary users see in `nucleus describe`, `@nucleus.contract(schema=...)` errors, and lineage facets. The `scripts/dagster_leak_check.py` CI lint must whitelist Arrow type strings while still rejecting wrapped-library class names.

If Apache Arrow ever died or pivoted hostile (a vanishingly small probability given Linux Foundation + ASF governance and committers from Snowflake / Databricks / NVIDIA / Voltron Data / Google / Meta / AWS), the replacement would not be a "swap target" — it would be a **new Tier-0 substrate** the entire Python data ecosystem migrates to in lockstep. There is no in-Nucleus engineering response to that event; we follow polars / duckdb / pyiceberg wherever they go.

---

## §8. Performance traps + operational risks

1. **`pyarrow.Table.to_pylist()`** — converts the entire Table into a Python list of dicts. **Never call in a hot path.** The canonical "I broke zero-copy" symptom. Real use cases: tiny previews (≤ 10 rows) for CLI output, JSON-serializing small test fixtures. Beyond that, 10-100× perf cliff. v0.5+ CI lint should flag `.to_pylist()` outside `cli/` preview helpers.
2. **GIL behaviour** — pyarrow 18.1.0 still holds the GIL across most compute and I/O calls (the C++ implementation releases it for the largest kernels, not uniformly). Free-threading wheels ship from 3.13t onwards; pyarrow 24.0.0's classifier `"Free Threading :: 2 - Beta"` indicates active progress. **NEEDS VERIFICATION** when we upgrade past 3.13; until then, treat pyarrow calls as GIL-holding.
3. **Schema metadata bloat** — `bytes`-keyed/`bytes`-valued metadata is allowed at field- and schema-level. 1 KB of metadata × 100 columns × 10 000 snapshots = ~1 GB of manifest bloat. Use sparingly; prefer Nucleus-owned `nucleus.toml` over field-level metadata for non-essential annotations.
4. **`Schema.equals(check_metadata=True)`** in contract checks — over-strict; fails spuriously when pyiceberg roundtrips field IDs through schema metadata. Always use `check_metadata=False` (the default) for asset-contract diffing.
5. **Wheel install size** — 25 MB on Windows, 40 MB on Linux, ~30 MB on macOS. Largest dep after Dagster. Affects CI cache and `pip install` time on cold containers; mitigate with a uv-shared cache.
6. **`pa.timestamp("ns", ...)` against Iceberg v2** — valid pyarrow but **invalid** as an Iceberg-v2 column type. The error surfaces inside pyiceberg's writer, not pyarrow; the user-facing message must guide users to `pa.timestamp("us", tz="UTC")`. See `duckdb.md` §7, `pyiceberg.md` §7, `type_mapping.md` §6.4.

---

## §9. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-13 | pyarrow confirmed Tier-0 immortal substrate | v4.1 §3.1 / §4.1 / §9.2 — Arrow IS the in-memory contract. |
| 2026-05-13 | No direct wrapping; call pyarrow APIs directly in the four narrow places in §3 | Wrapping a Tier-0 substrate defeats zero-copy and implies a swap that v4.1 §4.1 forbids. |
| 2026-05-13 | No `docs/internal/swap/pyarrow.md` will be written | Tier-0 components have no swap targets (v4.1 §9.2). |
| 2026-05-13 | Pin remains `pyarrow==18.1.0`; upgrade gated by ADR-003 | pyiceberg 0.8.1 caps at `<19.0.0`; coupled upgrade per Constraint #11. |
| 2026-05-13 | Arrow type strings allowed in user-facing output | Schema vocabulary contract — update `scripts/dagster_leak_check.py` to whitelist them while still rejecting Dagster / DuckDB / pyiceberg class names (v4.1 §6.4). |
| TBD | Confirm `ArrowInvalid` / `ArrowIOError` are `Exception`-based | PoC #1 Week 1 fixture work. |
| TBD | Benchmark-confirm zero-copy across polars ↔ duckdb ↔ pyiceberg via `pool.bytes_allocated()` deltas | PoC #2 / #4. |

---

## §10. NEEDS VERIFICATION (open ends)

Residual items this doc cannot resolve without running real code against the pinned versions. Each is tagged to its resolving PoC; none block the doc.

- **PoC #1**: `pyarrow.lib.ArrowInvalid` / `ArrowIOError` hierarchy — confirm both subclass `Exception` (not `BaseException`). Verify with `pa.lib.ArrowInvalid.__mro__`.
- **PoC #2**: zero-copy verified across `duckdb.execute(sql).arrow() → polars.from_arrow()` and `polars_df.to_arrow() → pyiceberg.append()` via `pa.default_memory_pool().bytes_allocated()` deltas.
- **PoC #3**: `pa.Table.from_pylist(rows, schema=...)` on real SQLite rows — confirm `None` → `pa.null` semantics propagate into Iceberg, including for `pa.timestamp("us", tz="UTC")` columns where SQLite returns naive strings.
- **Contract checks**: `pa.Schema.equals(other, check_metadata=False)` in 18.1.0 — confirm the `False` default ignores schema-level `KeyValueMetadata` but still compares field-level metadata (24.0.0 docstring is ambiguous on field-level metadata).
- **Upgrade ADR (post-ADR-003)**: re-verify §3 surface against `pyarrow==19.x`+. Risk: `pa.compute` kernels and Arrow C-data ABI revision changed between 18 / 19 / 20.
- **Free-threading**: pyarrow 24.0.0 ships a `cp313t` wheel and carries `"Free Threading :: 2 - Beta"`. When Nucleus moves to Python ≥ 3.13 baseline (post-v0.5), benchmark whether Arrow-handoff paths benefit from GIL-free execution.

---

## §11. Useful links (verified 2026-05-13)

- **Docs landing**: <https://arrow.apache.org/docs/python/index.html> — start here.
- **API reference**: <https://arrow.apache.org/docs/python/api.html>  •  **Data types / schemas**: <https://arrow.apache.org/docs/python/data.html> + <https://arrow.apache.org/docs/python/api/datatypes.html>
- **`pyarrow.Table` class**: <https://arrow.apache.org/docs/python/generated/pyarrow.Table.html>  •  **`pyarrow.Schema` class**: <https://arrow.apache.org/docs/python/generated/pyarrow.Schema.html>
- **Arrow C Data Interface** (the ABI Nucleus relies on for zero-copy): <https://arrow.apache.org/docs/format/CDataInterface.html>
- **PyCapsule protocol** (zero-copy boundary contract): <https://arrow.apache.org/docs/python/extending_types.html#controlling-conversion-to-py-arrow-with-the-pycapsule-interface>
- **Memory and IO**: <https://arrow.apache.org/docs/python/memory.html> + <https://arrow.apache.org/docs/python/api/memory.html>
- **Project home**: <https://arrow.apache.org/>  •  **GitHub source**: <https://github.com/apache/arrow>  •  **Releases**: <https://github.com/apache/arrow/releases>
- **PyPI**: <https://pypi.org/project/pyarrow/>  •  Version JSON for 18.1.0: <https://pypi.org/pypi/pyarrow/18.1.0/json>
- **Wes McKinney's 2017 essay** *"Apache Arrow and the '10 Things I Hate About pandas'"* (the historical North Star): <https://wesmckinney.com/blog/apache-arrow-pandas-internals/>
- **License**: Apache-2.0 (ASF TLP policy + PyPI classifier). `https://github.com/apache/arrow/blob/main/LICENSE.txt` returns empty body via `WebFetch` (same GitHub blob-viewer quirk as Polaris / Lakekeeper repos); the license file does exist in the repo.
- **Companion Nucleus research docs**: [`pyiceberg.md`](./pyiceberg.md) §2 (upper bound)  •  [`polars.md`](./polars.md) §8 (zero-copy boundary)  •  [`duckdb.md`](./duckdb.md) §5 (`.arrow()`)  •  [`dlt.md`](./dlt.md) §6 (floor)  •  [`openlineage.md`](./openlineage.md) §5.1 (schema facet path)  •  [`ai_hallucinations.md`](./ai_hallucinations.md).
- **Architecture references**: `docs/specs/nucleus_architecture_v4.1.md` §3.1 (L0 Physics; Arrow first); §4.1 (Tier-0 immortal table); §9.2 (Composability Constitution Tier-0 list).

---

*Last verified against `pyarrow==18.1.0` on 2026-05-13 against PyPI + arrow.apache.org/docs/python (which currently serves v24.0.0; spot-check critical signatures against the version-pinned docs build before merging). Re-verify when the ADR-003 pyiceberg upgrade lands (it lifts the `pyarrow<19.0.0` cap), on any pyarrow minor / major bump, and before any new direct-pyarrow integration site beyond the four listed in §3. Log AI-fabricated pyarrow APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
