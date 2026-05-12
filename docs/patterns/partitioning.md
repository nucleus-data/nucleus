# Pattern: Iceberg Partitioning

> **Pattern**: Big Data — Iceberg Lifecycle / Layout
> **Status**: Pre-implementation reference. Used by: Tier 1+ asset declarations (`partition_by=...`).
> **Audience**: Anyone writing or reviewing assets that materialize to Iceberg, especially before touching `ctx.asset` partition arguments.
> **References**: [`docs/research/pyiceberg.md`](../research/pyiceberg.md) §4, §7; [`docs/patterns/type_mapping.md`](./type_mapping.md) §4.4; [`docs/decisions/ADR-001-no-iceberg-commit-service.md`](../decisions/ADR-001-no-iceberg-commit-service.md)
> **Last reviewed**: 2026-05-12 — versions per [`docs/compatibility.md`](../compatibility.md) (`pyiceberg==0.8.1`, `pyarrow==18.1.0`)

Read this **before** writing Tier 0 Heartbeat code that calls `Table.append` or `create_table(... partition_spec=...)`. Picking the wrong partition transform is the #1 silent performance killer in Iceberg warehouses.

---

## §1. Why partitioning matters for Nucleus

- Tier 1+ assets declare partitioning via `@nucleus.asset(partition_by="day(event_ts)")`. The decorator translates that to a PyIceberg `PartitionSpec` (per [`pyiceberg.md`](../research/pyiceberg.md) §4).
- **Wrong spec, two symptoms**:
  1. Too coarse → readers full-scan multi-GB files for a 1-day query.
  2. Too fine → millions of tiny files; manifest reads dominate; commit latency balloons.
- The **default if you do nothing** = no partition spec = one big file per write, no pruning. Acceptable for tables <1 GB; catastrophic past that.
- The 30-minute beachhead metric in [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) §1.5 relies on the default being safe: `ctx.copy_from` will set a sensible time-column partition if the source has one.

---

## §2. Iceberg's "hidden partitioning" mental model

Iceberg's partitioning model is the **single biggest mental shift** from Hive-style warehouses. Get this right and the rest of the doc is mechanical.

- **Hive**: partition column stored physically; user writes `WHERE event_day = '2026-05-12'`; if they forget the partition column, full scan.
- **Iceberg**: a **transform** is applied to a source column (`day(event_ts)`); the partition value is **derived**, not stored separately. Users write `WHERE event_ts BETWEEN ... AND ...` (the regular column); Iceberg's scan planner automatically translates that to partition pruning.
- **Consequence**: SQL is portable. The same query works whether you partition by `day(event_ts)` or `month(event_ts)` or not at all — only speed changes.
- Spec: [iceberg.apache.org/spec/#partitioning](https://iceberg.apache.org/spec/#partitioning)

```
┌────────────────────┐        ┌────────────────────┐
│  source column     │── day()──▶│  partition value   │
│  event_ts          │           │  2026-05-12        │
│  (timestamp[us])   │           │  (int days from 1970) │
└────────────────────┘        └────────────────────┘
       ▲                                │
       │                                ▼
   user SQL                       partition-prune
   (transparent)                  during planning
```

---

## §3. The transform menu

The seven [partition transforms](https://iceberg.apache.org/spec/#partition-transforms) defined by spec v2:

| Transform | What it does | When to use | Source types accepted |
|---|---|---|---|
| `identity(col)` | Use the column value as-is | Low-cardinality column (region, country, env) | Any except struct/list/map |
| `year(col)` | Years since 1970 | Time-series, low write volume, archival queries | date, timestamp, timestamptz |
| `month(col)` | Months since 1970-01 | Time-series, monthly query patterns | date, timestamp, timestamptz |
| `day(col)` | Days since 1970-01-01 | **The safe default for most time-series** | date, timestamp, timestamptz |
| `hour(col)` | Hours since 1970-01-01 00:00 | Hourly dashboards, high write rate (>1 GB/day) | timestamp, timestamptz |
| `bucket(N, col)` | `hash(value) mod N` | High-cardinality joins/dedup keys (customer_id, order_id) | int, long, decimal, date, string, uuid, fixed, binary |
| `truncate(W, col)` | Value truncated to width `W` | String prefix grouping; integer ranges | int, long, decimal, string, binary |
| `void(col)` | Drops a partition field on evolution | Advanced — only used inside `update_spec` to remove a field cleanly | Any |

### §3.1 PyIceberg API (0.8.1)

```python
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import DayTransform, BucketTransform, IdentityTransform

spec = PartitionSpec(
    PartitionField(source_id=3, field_id=1000, transform=DayTransform(), name="event_day"),
    PartitionField(source_id=5, field_id=1001, transform=BucketTransform(16), name="customer_bucket"),
)
```

- `source_id` = the integer field ID of the source column in the table schema (NOT the column name; field IDs are the source of truth per [`pyiceberg.md`](../research/pyiceberg.md) §4).
- `field_id` = the partition field's own ID. Start at 1000+ to avoid collision with schema field IDs.
- `name` = the human-readable partition name visible in manifests and SQL projections.
- Pass `spec` into `Catalog.create_table(..., partition_spec=spec)`.

Docs: [py.iceberg.apache.org/api/#partitioning](https://py.iceberg.apache.org/api/) (search "PartitionSpec").

---

## §4. Sizing rules of thumb

These are the rules junior DEs most often miss. Iceberg's manifest layer makes "many small files" expensive in a way that traditional Parquet warehouses don't punish as harshly.

- **Target partition size**: 100 MB – 1 GB compressed Parquet, total across all files in that partition.
- **If average partition < 10 MB** → over-partitioned. Coarsen the transform (`hour` → `day`, `day` → `month`) or compact (see [`compaction.md`](./compaction.md)).
- **If average partition > 5 GB** → under-partitioned. Add a finer time transform OR add a `bucket(N, col)` on a secondary high-cardinality key.
- **Files per partition**: target 1–4. More than ~10 files in a single partition usually means compaction is overdue.
- **Time-series rule**: choose the partition unit equal to or one step coarser than the **smallest** query range. Daily dashboards → `day()`. Hourly alerting → `hour()`. Monthly board reports → `month()`. Never finer than the query granularity (`hour()` for a daily query is pure overhead).
- **`bucket(N, col)`**: pick N so that **average bucket size** lands in 100 MB – 1 GB. For 100 GB of data on a join key, N ≈ 128 to 256 is a reasonable start.

---

## §5. Partition evolution (the PyIceberg 0.8.1 part is fragile)

Iceberg supports **evolving** the partition spec without rewriting old data.

- Old snapshots keep their original spec; new data is written under the new spec. Reads transparently union both.
- Spec: [iceberg.apache.org/spec/#partition-evolution](https://iceberg.apache.org/spec/#partition-evolution).
- PyIceberg API: `Table.update_spec()` returns a builder used inside a transaction (see [`pyiceberg.md`](../research/pyiceberg.md) §5).

```python
from pyiceberg.transforms import HourTransform

with table.update_spec() as update:
    update.add_field("event_ts", HourTransform(), "event_hour")
    update.remove_field("event_day")
```

- `add_field(source_col, transform, name)` — add a partition field on an existing column. `name` is optional; auto-generated if omitted.
- `remove_field(name)` — drop a partition field (uses the `void` transform under the hood).
- Works inside `Table.transaction()` alongside `update_schema` and writes (per the PyIceberg API page).

**Gotchas specific to 0.8.1**:

- Partition-evolution **read support** is in 0.8.1, but coverage of newer transforms (multi-arg transforms in spec v3) is **partial**. We stay on spec v2 anyway (per [`type_mapping.md`](./type_mapping.md) §4.3), so this is mostly fine.
- TODO: verify on 2026-08-01 (next quarterly upgrade audit) whether 0.8.1 supports `update.rename_field` cleanly; current docs example uses it but the patch-release notes don't mention it. If you need rename, smoke-test against your catalog first.
- **Never evolve inside the hot path of a production run.** Treat partition evolution like a schema migration: separate maintenance PR, separate run, observed under low traffic.

---

## §6. Nucleus conventions

- Asset decorators expose `partition_by` (v0.2+). Examples:
  - `partition_by="day(event_ts)"` → single time transform.
  - `partition_by=["day(event_ts)", "bucket(16, customer_id)"]` → multi-column spec (v0.5+).
- v0.1 Heartbeat: **ONE partition transform per asset, maximum**. No multi-field specs in the first write. Multi-field is fine, but it lands in v0.5+ once the Asset Materialization Adapter (per ADR-001) has been exercised on real workloads.
- The `@nucleus.asset` decorator translates the string DSL to a real PyIceberg `PartitionSpec` under the hood; users **never import `pyiceberg.partitioning` themselves** (per `nucleus_architecture_v4.1.md` §13.1 — the `ctx` SDK is the only stable public surface; wrapped library names do not appear in user code).
- Lineage emits the partition spec at materialization time (asset-level metadata only in v0.1; column-level lineage including partition columns lands in v0.5+).
- Schema contracts (`@nucleus.check`) can assert "this column has a partition transform applied"; useful for catching accidental partition-spec drops on schema updates.

---

## §7. Known pitfalls

Each pitfall below explains **why**, not just **what**. The "why" is what saves you 3 hours of debugging.

- **Bare `identity()` on a high-cardinality column** (e.g., `identity(customer_id)`) — classic anti-pattern. You get one partition per distinct value; with 5M customers, that's 5M partitions, each holding a few rows. Manifest list grows past gigabytes; planning becomes slower than scanning. Use `bucket(N, customer_id)` instead.
- **`bucket(N, col)` is hash-based, so the bucket count is essentially fixed at write time.** Changing N later requires reading and rewriting the data; the cheap "ALTER TABLE" change of a Hive-style warehouse does not exist. Pick N once, with sizing math (§4).
- **Time transforms assume UTC.** Per [`engineering.md`](../conventions/engineering.md) §6.1 we set `timezone='UTC'` on every DuckDB connection. Source data in local time must be converted before write or you'll partition by the wrong day. PyIceberg writes `timestamptz` correctly only if the Arrow tz metadata is `UTC` (per [`type_mapping.md`](./type_mapping.md) §3.5).
- **Don't partition on a nullable column unless you understand the null partition behavior.** Iceberg places nulls in a dedicated partition; queries that filter the column will skip that null partition unless you explicitly write `OR col IS NULL`.
- **Don't partition on a column you'll later try to drop.** The schema-evolution rules in [iceberg.apache.org/spec/#schema-evolution](https://iceberg.apache.org/spec/#schema-evolution) forbid dropping a column used by an active partition field. You'd need to evolve the spec first (drop the partition field), commit, then drop the column. Two-step.
- **Avoid `hour()` unless you actually query at hour granularity.** Daily ingestion + `hour()` partitioning = 24 files per ingestion × 365 days = 8,760 files/year per source. Daily queries pay manifest cost for partitions they never prune to.
- **Partition columns must be primitive.** No `struct`, `list`, or `map` (per [`type_mapping.md`](./type_mapping.md) §4.4). Apply a transform on a primitive child field instead.
- **Two partition specs are considered "compatible" only if all fields match exactly** (per spec §"Partitioning"). Slightly different `field_id` or `name` = a different spec, causes a forced spec evolution on commit. Always use the canonical IDs from the Nucleus decorator.

---

## §8. Inspecting partitions

When something looks wrong, these are the diagnostics — in order of cost.

```python
table = catalog.load_table("warehouse.orders")
table.spec()
table.scan(row_filter="event_ts >= '2026-05-01'").plan_files()
```

- `table.spec()` returns the **current** `PartitionSpec`. Cheap (metadata only).
- `table.specs()` returns the dict of **all historical specs** (one per spec evolution). Useful for "why are these files in a different layout?"
- `table.scan(row_filter=...).plan_files()` returns the list of files that would be read for that filter. If you see thousands of files for a daily query, partitioning is broken or compaction is overdue (see [`compaction.md`](./compaction.md) §5).
- **DuckDB iceberg extension** (read-only in 1.1.3, per [`duckdb.md`](../research/duckdb.md) §4): `SELECT *` transparently shows the source columns; partition columns are derived metadata and aren't returned unless you explicitly add them as columns.

---

## §9. Decision tree

When in doubt, walk this tree top to bottom. It's the fastest path to a sensible default.

```
Is the column time-typed (date / timestamp / timestamptz)?
├─ YES
│   ├─ Query range: hourly  →  hour()
│   ├─ Query range: daily   →  day()   ← safe default for time-series
│   ├─ Query range: monthly →  month()
│   └─ Query range: yearly  →  year()  (low-volume archives only)
│
└─ NO
    └─ Cardinality of the column?
        ├─ Low (< 1000 distinct values)            →  identity(col)
        ├─ Medium (1k – 100k distinct)             →  truncate(W, col)  (prefix grouping)
        └─ High (> 100k distinct, e.g. IDs)        →  bucket(N, col)    (target ~1 GB / bucket)
```

If you can't classify the column, the answer is "don't partition yet — write the table flat, observe query patterns for 2 weeks, then partition based on real telemetry." This is the empirical-trigger discipline of [AGENTS.md](../../AGENTS.md) §5 question #7.

---

## §10. Useful links

- [Iceberg spec — Partitioning](https://iceberg.apache.org/spec/#partitioning) — the canonical reference.
- [Iceberg spec — Partition Transforms](https://iceberg.apache.org/spec/#partition-transforms) — table of all 7 transforms with input/output types.
- [Iceberg spec — Partition Evolution](https://iceberg.apache.org/spec/#partition-evolution) — semantics of changing the spec.
- [PyIceberg API — Partitioning](https://py.iceberg.apache.org/api/) (search "PartitionSpec") — Python API surface.
- [Schema evolution](https://iceberg.apache.org/spec/#schema-evolution) — referenced because partition fields constrain what you can drop.
- Related Nucleus docs: [`type_mapping.md`](./type_mapping.md) §4.4 (primitive constraint), [`compaction.md`](./compaction.md) (what to do when partitions get small), [`snapshot_retention.md`](./snapshot_retention.md) (every commit creates a snapshot regardless of partition spec).

---

*This document is normative. When code disagrees with this doc, the doc is the source of truth — update the code.*
