# Type Mapping — Postgres ↔ Iceberg ↔ Arrow ↔ Polars ↔ DuckDB

> **Pattern**: Big Data — Type System Bridging
> **Audience**: Anyone writing or reviewing `ctx.copy_from`, `ctx.sql`, engine adapters, or schema contracts
> **Status**: Reference document. Property tests in `tests/patterns/test_type_mapping.py` enforce.
> **Last reviewed**: Month 0 (Pre-Heartbeat) — versions targets per `docs/internal/compatibility.md`

Cross-system data movement looks simple ("just copy the rows") but **subtle type corruption** is the #1 silent killer in real-world data engineering. This document is the authoritative mapping table. PRs that change any type handling **must** update this file.

---

## §1. Why this matters

When data flows:

```
Postgres → (extract) → Arrow → Polars/DuckDB (transform) → Arrow → Iceberg → Arrow → BI tool
```

…every arrow is a **type conversion**. Mistakes here are insidious:

- A Postgres `TIMESTAMP` (UTC implicit?) → Arrow `timestamp[ns, UTC]` (explicit) → Iceberg `timestamptz` (always UTC) → BI tool reads as "wrong time zone".
- A Postgres `NUMERIC(10,4)` → Arrow `decimal128(10,4)` → Polars cast incorrectly to `f64` → silently lossy.
- A Postgres `UUID` → Arrow `binary` (not native UUID) → Iceberg writes as `binary` → readers can't roundtrip.

Property-based tests with `hypothesis` enforce that **every round-trip is identity** for supported types.

---

## §2. The canonical pivot — Arrow

**Arrow is the lingua franca.** All conversions go via Arrow.

```
   Source                    Arrow                   Target
┌──────────┐               ┌──────────┐           ┌──────────┐
│ Postgres │ ── extract ──▶│  PyArrow │── write ─▶│ Iceberg  │
│  type    │               │   type   │           │   type   │
└──────────┘               └──────────┘           └──────────┘
                                 │
                                 │ zero-copy
                                 ▼
                          ┌──────────────┐
                          │ Polars / DuckDB│  (in-memory ops)
                          └──────────────┘
```

**Why Arrow as pivot**:
1. PyArrow has well-defined mappings to/from every other system we use.
2. Zero-copy between Arrow and Polars/DuckDB (the Physics layer point).
3. Iceberg internally uses Arrow for writes (PyIceberg).
4. **Single hop per direction** — N×M conversion problem becomes N + M.

---

## §3. The master mapping table (v0.1)

Read as: "if you see column type X in source, it becomes Y in Arrow, Z in Iceberg, W in Polars, V in DuckDB".

### §3.1 Integers

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `SMALLINT` (int2) | `int16` | `int` (32-bit, widened) | `Int16` | `SMALLINT` | Iceberg has no `int16`; widen to `int` |
| `INTEGER` (int4) | `int32` | `int` | `Int32` | `INTEGER` | Direct |
| `BIGINT` (int8) | `int64` | `long` | `Int64` | `BIGINT` | Direct |
| `SERIAL` | `int32` | `int` | `Int32` | `INTEGER` | Serial = int4 with default; type ID is int4 |
| `BIGSERIAL` | `int64` | `long` | `Int64` | `BIGINT` | Same |

### §3.2 Decimals & floats

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `REAL` (float4) | `float32` | `float` | `Float32` | `REAL` | Direct |
| `DOUBLE PRECISION` (float8) | `float64` | `double` | `Float64` | `DOUBLE` | Direct |
| `NUMERIC(p,s)` / `DECIMAL(p,s)` | `decimal128(p,s)` | `decimal(p,s)` | `Decimal(p,s)` | `DECIMAL(p,s)` | **Preserve precision/scale**. Never cast to float silently. |
| `NUMERIC` (no p/s) | `decimal128(38,9)` | `decimal(38,9)` | `Decimal(38,9)` | `DECIMAL(38,9)` | Postgres allows unbounded; we default to (38,9). **Configurable per source** in `nucleus.toml`. |

**Rule**: When `NUMERIC` has no explicit precision/scale in the source, log a warning at extraction and use the default. Surface this in the `ctx.copy_from` output.

### §3.3 Booleans

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `BOOLEAN` | `bool` | `boolean` | `Boolean` | `BOOLEAN` | Direct |

### §3.4 Strings

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `TEXT` | `large_string` | `string` | `String` | `VARCHAR` | Use `large_string` for safety on >2GB columns |
| `VARCHAR(n)` | `string` | `string` | `String` | `VARCHAR` | Length not enforced on Arrow side; documented in schema |
| `CHAR(n)` | `string` | `string` | `String` | `VARCHAR` | Trailing whitespace **stripped** on extract (Postgres pads). Surfaced in warning. |
| `JSON` | `string` | `string` | `String` | `JSON`/`VARCHAR` | We store as **string** to preserve fidelity. DuckDB's JSON type used only at query time. |
| `JSONB` | `string` | `string` | `String` | `JSON`/`VARCHAR` | Same. We don't reorder keys. |

**Rule for JSON**: We treat JSON as string at storage. Per-asset opt-in to `ctx.json` lazy-decoded views in v0.3+.

### §3.5 Dates & times — the danger zone

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `DATE` | `date32` | `date` | `Date` | `DATE` | Direct |
| `TIME` (no tz) | `time64[us]` | `time` | `Time` | `TIME` | Microsecond precision; **second-precision lost if source is sub-µs** |
| `TIMESTAMP` (no tz) | `timestamp[us]` (no tz) | `timestamp` | `Datetime("us")` | `TIMESTAMP` | **Never assume tz**. Stays naive end-to-end. |
| `TIMESTAMPTZ` | `timestamp[us, UTC]` | `timestamptz` | `Datetime("us", "UTC")` | `TIMESTAMP WITH TIME ZONE` | **Always stored as UTC** post-extraction. |
| `INTERVAL` | `interval_month_day_nano` | _no support_ | `Duration` (lossy) | `INTERVAL` | **v0.1 limitation**: Iceberg has no native interval. We **store as ISO 8601 string** and surface a warning. Future: structured logical type. |

**Critical rules for timestamps**:
1. **`TIMESTAMP` ≠ `TIMESTAMPTZ`** — never silently convert. They have **different semantics**.
2. Read connection-level `TimeZone` setting from Postgres; if not `UTC`, log loud warning.
3. PyIceberg requires explicit UTC for `timestamptz`. We convert *before* writing.
4. Microsecond precision is the canonical resolution. Nanoseconds are **truncated**; warning emitted.

### §3.6 Binary

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `BYTEA` | `large_binary` | `binary` | `Binary` | `BLOB` | Direct. Use `large_binary` to handle >2GB rows. |

### §3.7 UUID

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `UUID` | `fixed_size_binary(16)` | `uuid` (native!) | `String` (hex repr) | `UUID` | **PyIceberg supports `uuid` natively (v0.6+)**. We use it. Polars currently lacks native UUID; presented as hex string. |

**Watch**: PyArrow doesn't have a `uuid` logical type. We use `fixed_size_binary(16)` with the `uuid_metadata` extension. PyIceberg understands this.

### §3.8 Arrays

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `INTEGER[]` | `list[int32]` | `list<int>` | `List(Int32)` | `INTEGER[]` | Direct |
| `TEXT[]` | `list[large_string]` | `list<string>` | `List(String)` | `VARCHAR[]` | Direct |
| **Multi-dim arrays** | _not supported_ | _not supported_ | _not supported_ | _not supported_ | **v0.1 limitation**: 2D+ Postgres arrays raise `NucleusUnsupportedTypeError`. Workaround: flatten in source view. |

**Note on null in arrays**: Postgres arrays can contain NULL. Arrow `list` allows null elements. We preserve.

### §3.9 Composite / structured types

| Postgres | Arrow | Iceberg | Polars | DuckDB | Notes |
|----------|-------|---------|--------|--------|-------|
| `ROW(...)` (composite) | `struct<...>` | `struct<...>` | `Struct(...)` | `STRUCT(...)` | v0.2 support; v0.1 raises NucleusUnsupportedTypeError |
| `HSTORE` | `map<string,string>` | `map<string,string>` | `Struct` (best effort) | `MAP(VARCHAR, VARCHAR)` | v0.2+ |
| `ENUM` | `string` (with metadata) | `string` | `Categorical` | `ENUM` | Postgres enum value list captured in Arrow metadata. |

### §3.10 Geographic (PostGIS)

| Postgres | Arrow | Iceberg | Notes |
|----------|-------|---------|-------|
| `GEOMETRY`, `GEOGRAPHY` | _v0.1: not supported_ | _v0.1: not supported_ | **Out of scope** for v0.1-v0.5. Treat as string (WKB) if absolutely needed; user opt-in. |

### §3.11 Special / unsupported

| Postgres | Status | Reason |
|----------|--------|--------|
| `XML` | v0.1: store as `TEXT`, surface as `string` | XML transformation is a different problem space |
| `MONEY` | v0.1: store as `DECIMAL(19,4)` | Reliable currency math needs scale; users should pick their own currency precision |
| `CITEXT` | Treated as `TEXT` | Case-insensitivity is collation, not a separate Arrow type |
| `pg_lsn`, `tsvector`, `tsquery`, OID types | _Not supported_ | Postgres-internal; not data |

---

## §4. Iceberg-specific type rules

PyIceberg's writes have specific requirements. Even valid Arrow doesn't always roundtrip cleanly to Iceberg.

### §4.1 Required: explicit nullability
- Arrow allows null on all types by default.
- Iceberg requires explicit nullability per column.
- **Our rule**: `ctx.asset` accepts `nullable: bool = True` per column. Default permissive. Schema contracts can tighten this.

### §4.2 Integer widening to 32-bit
- Iceberg has only `int` (32-bit) and `long` (64-bit). No int8/int16.
- Postgres `SMALLINT` (int16) is widened to Iceberg `int`. Round-trip back to Polars: `Int32`, not `Int16`.
- **Impact**: One-time widening on first materialization. Documented; not an error.

### §4.3 Iceberg supports `timestamp_ns` (v3 spec)
- The Iceberg spec v3 adds `timestamp_ns` and `timestamptz_ns` (nanosecond precision).
- PyIceberg 0.8.x writes spec v2 by default (microsecond max).
- **v0.1 decision**: Stay on Iceberg spec v2 (microsecond timestamps). Spec v3 in v0.5+ after PyIceberg stabilizes.

### §4.4 Partition columns must be primitive types
- Cannot partition by `struct`, `list`, `map`.
- Most users partition by date/timestamp + low-cardinality string — supported.
- Documented in `docs/patterns/partitioning.md` (TODO).

### §4.5 Schema evolution rules
- Adding a column: **allowed** (default null or explicit).
- Removing a column: **allowed** (soft; reads still work via projection).
- Renaming a column: **allowed** (by field ID).
- Changing a column's type: **allowed only for compatible widenings** (int→long, decimal narrow→wide).
- Changing nullable→not-nullable: **not allowed** (data may have nulls).
- See: https://iceberg.apache.org/spec/#schema-evolution

---

## §5. Polars-specific quirks

### §5.1 String vs Utf8
- Polars 1.x renamed `Utf8` → `String`. We use `String`.

### §5.2 Categorical
- Polars `Categorical` is a runtime optimization, not a storage type. **Never persisted to Iceberg.**
- We materialize as `string` to Iceberg. On re-read, user can apply `.cast(pl.Categorical)` if needed.

### §5.3 Object / Python objects
- Polars allows `pl.Object` for arbitrary Python objects.
- **Forbidden in `ctx.asset` return values.** Raise `NucleusSchemaError` if detected.
- Reason: cannot be roundtripped to Iceberg.

### §5.4 List vs Array
- Polars distinguishes `List(T)` (variable length) from `Array(T, n)` (fixed length).
- Iceberg only has `list<T>`. We always use `List(T)`.
- Fixed-length arrays become variable-length on write.

---

## §6. DuckDB-specific quirks

### §6.1 Implicit casts
- DuckDB is liberal with implicit casts (`SELECT 1 + '2'` works).
- For our SQL execution via `ctx.sql`, we run with `set timezone='UTC'; set decimal_separator='.';` to make execution deterministic.

### §6.2 Decimal arithmetic
- DuckDB decimal arithmetic preserves scale up to 38 digits.
- Operations exceeding 38 digits silently switch to `DOUBLE`. **Surface as a warning** if detected at write time.

### §6.3 STRUCT and LIST
- DuckDB has `STRUCT(...)` and `LIST(...)` types matching Iceberg's.
- Composite types via DuckDB → Iceberg roundtrip cleanly (v0.2+).

### §6.4 TIMESTAMP precision
- DuckDB stores timestamps at microsecond precision. Matches our canonical.
- DuckDB has `TIMESTAMP_NS` (nanosecond) — **not used by Nucleus** (incompatible with Iceberg v2).

---

## §7. NULL handling

### §7.1 Three-valued logic preservation
- Postgres NULL is distinct from empty string `''`, zero `0`, and false.
- All systems in our chain preserve NULL.
- **Rule**: never substitute defaults for NULL in transit. Substitution must be explicit user code.

### §7.2 NULL ordering
- Postgres: `NULLS FIRST` for ASC by default in 9.6+.
- DuckDB: `NULLS LAST` by default.
- Polars: `NULLS LAST` by default.
- Iceberg: ordering implementation-defined; downstream readers may differ.
- **Documented gotcha**: If your assets depend on null ordering, **explicit `NULLS FIRST/LAST` is required**. Schema contracts can warn.

### §7.3 NaN vs NULL
- Postgres distinguishes NaN (in `float`) from NULL.
- Arrow / Iceberg / Polars / DuckDB all preserve this distinction.
- **However**: comparisons differ. Postgres: `NaN > NULL` is unknown. Polars: NaN sorts to one end. **Document downstream**.

---

## §8. Property test coverage (acceptance criteria)

`tests/patterns/test_type_mapping.py` uses `hypothesis` to verify:

For each row in §3:
1. **Round-trip identity**: Postgres → Arrow → Iceberg → Arrow → Polars/DuckDB → expected reconstruction.
2. **No silent precision loss** beyond documented widenings (§4.2).
3. **NULL preservation** through every hop.
4. **Schema contract**: declared schema must match actual schema on materialization.

Coverage requirement: **every row in this document has at least one property test.**

---

## §9. When you encounter an unsupported type

The contract:

1. **Extraction**: `ctx.copy_from` raises `NucleusUnsupportedTypeError` with the offending column name, source type, and link to this document (`docs_url=/docs/patterns/type_mapping#section-X`).
2. **Workaround**: User can transform the column in their source view (`CREATE VIEW v AS SELECT ..., col::TEXT FROM tbl`) before extraction.
3. **Roadmap**: File an issue. Type support is incremental.

---

## §10. Adding a new type

When a new type needs support (e.g., adding PostGIS Geometry in v0.5):

1. **ADR**: explain why and the storage approach.
2. **Update this doc**: add row(s) to §3.
3. **Adapter**: extend `src/nucleus/physics/arrow_postgres.py` (or relevant).
4. **Property test**: extend `tests/patterns/test_type_mapping.py`.
5. **Schema contract**: extend `coordination/contracts.py` to recognize.
6. **CHANGELOG**: under `Added`.

---

## §11. References

- [Apache Arrow data types](https://arrow.apache.org/docs/python/api/datatypes.html)
- [Iceberg type system](https://iceberg.apache.org/spec/#primitive-types)
- [PyIceberg schema](https://py.iceberg.apache.org/api/#schemas)
- [Polars data types](https://docs.pola.rs/api/python/stable/reference/datatypes.html)
- [DuckDB data types](https://duckdb.org/docs/sql/data_types/overview.html)
- [Postgres data types](https://www.postgresql.org/docs/current/datatype.html)
- [`docs/architecture/C4_container.md`](../architecture/C4_container.md) §2.0 (Physics layer)

---

*This document is normative. When code disagrees with this doc, the doc is the source of truth — update the code.*
