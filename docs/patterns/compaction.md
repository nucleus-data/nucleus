# Pattern: Iceberg Compaction

> **Pattern**: Big Data — Iceberg Lifecycle / Maintenance
> **Status**: Pre-implementation reference. Not exposed in v0.1. CLI surface (`nucleus optimize`) lands in v0.3+; automatic triggers in v0.5+.
> **Audience**: Anyone reviewing the Asset Materialization Adapter; anyone diagnosing "my reads got slow after N commits".
> **References**: [`docs/internal/research/pyiceberg.md`](../research/pyiceberg.md) §4, §7; [`docs/internal/research/duckdb.md`](../research/duckdb.md) §5, §7; [`docs/patterns/partitioning.md`](./partitioning.md) §4; [`docs/patterns/snapshot_retention.md`](./snapshot_retention.md); [`docs/decisions/ADR-001-no-iceberg-commit-service.md`](../decisions/ADR-001-no-iceberg-commit-service.md)
> **Last reviewed**: 2026-05-12 — versions per [`docs/compatibility.md`](../compatibility.md) (`pyiceberg==0.8.1`, `duckdb==1.1.3`)

Read this **before** writing PoC #1 or any code that touches `Table.append` / `Table.overwrite` in a loop. Skipping compaction is how warehouses silently become 100× slower.

---

## §1. Why compaction matters

- Every `Table.append(df)` writes **≥1 data file** per affected partition. PyIceberg 0.8.1 defaults to the [fast-append](https://iceberg.apache.org/spec/#snapshots) strategy: minimal write cost, but more metadata than a merge commit.
- Frequent appends → tens of thousands of small files. Small files kill reads three ways:
  1. **S3 round trips**: each file = one HEAD + one GET, regardless of payload size. 10,000 files at 5 ms latency = 50 s of pure I/O setup before any bytes flow.
  2. **Parquet headers**: each file has a ~1–4 KB footer. Reading 10,000 footers ≈ 30 MB just to plan the query.
  3. **Manifest list growth**: Iceberg's metadata tree fans out. Reading the manifest list before any data dominates query planning.
- **Concrete example**: 100 appends/day × 10 partitions = 1,000 new files/day; one year = 365,000 files. Read latency for a single-day partition climbs from <1 s to tens of seconds.
- This is **the** maintenance operation. Without it, every other optimization is undermined.

---

## §2. What compaction actually does

Iceberg's term for compaction is **"rewrite data files"**. The semantics are precise:

- Read N small files from a partition → write 1 (or a few) larger files → commit a new snapshot that references the new files.
- **Old files are not deleted in the rewrite snapshot.** They remain referenced by earlier snapshots until those snapshots expire (see [`snapshot_retention.md`](./snapshot_retention.md) §6).
- The new snapshot is atomic via the catalog (per [ADR-001](../decisions/ADR-001-no-iceberg-commit-service.md)). Concurrent reads on the old snapshot see the old layout; new reads see the new layout. **No read corruption window.**
- The data itself is unchanged — same rows, same schema, same partition spec. Only the file layout differs.

Reference: [iceberg.apache.org/docs/latest/maintenance/#compact-data-files](https://iceberg.apache.org/docs/latest/maintenance/#compact-data-files) (Java-side reference for `rewriteDataFiles`).

---

## §3. PyIceberg 0.8.1 status (honest version)

This is the most uncertain corner of v0.1, so treat the statements below as the current best understanding, not gospel.

- **PyIceberg 0.8.1 does NOT have a Spark-equivalent `rewriteDataFiles` action.** The Java/Spark `SparkActions.rewriteDataFiles(table)` has no direct Python equivalent in 0.8.x; tracking issue in iceberg-python (see [github.com/apache/iceberg-python/issues/270](https://github.com/apache/iceberg-python/issues/270) — referenced from the PyIceberg docs).
- Three workable paths for v0.1 compaction-by-hand (none exposed to users in v0.1 — these are for the Asset Materialization Adapter author and PoC operators):

| Path | What it costs | When to use |
|---|---|---|
| **1. DuckDB-driven read + PyIceberg `Table.overwrite()`** | ~50 LOC, works today | Default v0.1/v0.3 strategy. Per-partition, atomic via the catalog. |
| **2. `Table.dynamic_partition_overwrite(df)`** | Documented in current PyIceberg docs; replaces matching partitions in one call. TODO: verify on 2026-08-01 it exists in 0.8.1 (release notes don't explicitly confirm). | Multi-partition rewrite when the dataframe is the full re-grouped data. PoC must smoke-test before relying on it. |
| **3. Wait for native `rewrite_data_files`** | Zero LOC, but no timeline | Post-v0.5+ when PyIceberg gets parity with the Spark action. |

- TODO: verify on 2026-08-01 that 0.8.1 still lacks a native rewrite. Check changelog entries on [github.com/apache/iceberg-python/releases](https://github.com/apache/iceberg-python/releases) for any commits to `pyiceberg/table/maintenance/` after 0.8.1.

---

## §4. The "read-compact-write" recipe

The default v0.1 strategy: read a partition into memory, write it back as a single larger file via `Table.overwrite()` with a filter. Atomic by definition (the overwrite is one commit).

```python
import duckdb
from pyiceberg.expressions import EqualTo

table = catalog.load_table("warehouse.orders")
con = duckdb.connect(":memory:")
table.scan(row_filter=EqualTo("event_day", "2026-04-01")).to_duckdb("partition_data", connection=con)
rewritten = con.sql("SELECT * FROM partition_data ORDER BY event_ts").arrow()
table.overwrite(rewritten, overwrite_filter=EqualTo("event_day", "2026-04-01"))
```

Key points:

- `Table.scan(row_filter=...).to_duckdb(name, connection=con)` registers the partition zero-copy into DuckDB (per [`duckdb.md`](../research/duckdb.md) §5). No Arrow→Pandas hop.
- `Table.overwrite(df, overwrite_filter=expr)` is the **atomic primitive** for partial overwrite. PyIceberg deletes the matching files and appends the new ones in **one snapshot** (per [PyIceberg overwrite docs](https://py.iceberg.apache.org/api/), "Partial overwrites" section).
- `overwrite_filter` must use `pyiceberg.expressions.*` (`EqualTo`, `GreaterThan`, `And`, etc.), not a DuckDB SQL string.
- The `ORDER BY` in the SQL is the cheap way to **also** improve compression and clustering during the rewrite — free with the read.
- **All of this lives behind `coordination/asset_materialization.py` (the AMA, per ADR-001). Users never see PyIceberg or DuckDB imports.**

---

## §5. When to compact (the trigger conditions)

In v0.5+ these become automatic Cost-Meter-driven triggers. For v0.1/v0.3 they're documented for the operator/CLI to act on manually.

- **File count per partition exceeds ~10** — the manifest cost starts to dominate per-partition reads.
- **Average file size in a partition < 50 MB** — too small to amortize parquet footer + S3 round trip.
- **`table.scan(row_filter=...).plan_files()` returns >1,000 files for a normal query** — planning is the bottleneck.
- **Manifest list size > 1 MB** — surfaced by the v0.5+ telemetry (per `nucleus_architecture_v4.1.md` §6.3 Asset Materialization Adapter responsibilities).
- **Daily ingestion job repeats the same partition** (e.g., late-arriving data appends to yesterday) — that partition accumulates files even when total volume is stable.

---

## §6. When NOT to compact

- **Right after a partition spec evolution** (see [`partitioning.md`](./partitioning.md) §5) — files written under different specs cannot be compacted into a single output file without explicit handling. Wait for the evolution to settle (one cycle of normal writes).
- **Concurrent writers active.** Two simultaneous compactions racing on the same partition will both succeed at the PyIceberg layer (atomic commits) but waste work; one will likely retry on `CommitFailedException` (per [`pyiceberg.md`](../research/pyiceberg.md) §6). Coordinate via Dagster.
- **Active time-travel readers** querying snapshots that reference the small files. The query won't break (snapshots are immutable), but storage savings from compaction won't materialize until those snapshots expire.
- **Storage is cheap and reads are fine.** Compaction is a cost optimization, not a correctness fix. If you're under-utilized, defer.

---

## §7. Nucleus conventions

| Version | Compaction surface |
|---|---|
| v0.1 (Heartbeat) | **NOT exposed.** Documented for human awareness only. Manual rewrite is for emergencies via direct PyIceberg calls (with a `# NEEDS VERIFICATION` comment per [AGENTS.md](../../AGENTS.md) §11.12). |
| v0.3 | `nucleus optimize <asset>` CLI command. Dispatches a Dagster maintenance job using the §4 recipe. |
| v0.5+ | Automatic compaction driven by Cost Meter telemetry (`nucleus_architecture_v4.1.md` §6.3). Triggers from §5 above. |

- Compaction operations log an OpenLineage event with `op=compact` plus before/after file counts and bytes (per `nucleus_architecture_v4.1.md` §6.2 Asset Materialization Adapter responsibility 5).
- Compaction is **always per-partition**. Cross-partition compaction is not a real operation — it would shuffle data across partitions, defeating the partition spec.
- Errors during compaction translate to `NucleusError` subclasses per [`pyiceberg.md`](../research/pyiceberg.md) §6 (e.g., `CommitFailedException` → `NucleusCommitConflictError` with retry).

---

## §8. Gotchas

Each gotcha below has a "why" — the reason this is non-obvious for a junior DE.

- **Memory ≈ partition size.** The §4 recipe reads the partition into DuckDB before writing. A 5 GB partition needs ~5 GB of headroom; on an 8 GB laptop (Nucleus default per [`engineering.md`](../conventions/engineering.md) §11.1) you'll OOM. **Chunk the rewrite** if a partition is >50% of available memory: use DuckDB's `LIMIT N OFFSET M` or `WHERE` on a secondary column.
- **Don't compact across partitions.** Tempting ("smaller manifest list!") but it would shuffle data across partition boundaries, violating the spec. Use `bucket()` partitioning instead if you actually want more inter-file mixing.
- **Always `Table.refresh()` in long-running readers** after a compaction commits. The in-memory `Table` handle is stale and will plan against the old snapshot (per [`pyiceberg.md`](../research/pyiceberg.md) §7).
- **Compaction creates a new snapshot — every time.** This counts against your snapshot retention policy. See [`snapshot_retention.md`](./snapshot_retention.md): if you compact 10 partitions, you've added 10 snapshots (or 1, if you batch them in a single `Transaction`).
- **TIMESTAMP precision can be lost in the roundtrip.** Iceberg v2 caps `timestamp` at microseconds (per [`type_mapping.md`](./type_mapping.md) §4.3). If your source had nanosecond precision and was already truncated at write, you're fine. If somehow ns precision reached the table, the rewrite will silently lose it. Verify with property tests.
- **For very large tables**: parallelize across partitions, not within. Dagster fan-out (v0.5+) materializes one compaction op per partition; they commit independently. Within a partition, a single writer is correct.
- **PyIceberg's `Table.overwrite()` without a filter overwrites the entire table.** This is a destructive operation guarded only by the snapshot history. Always pass an `overwrite_filter`. The PyIceberg API page shows `overwrite_filter=AlwaysTrue()` as the default; in our AMA this default is replaced with an exception (per ADR-001 thin-adapter responsibility 1 — pre-write validation).

---

## §9. Cost-aware notes

Compaction is not free. The Cost Meter (v0.5+) will surface the tradeoff explicitly.

- **Each compaction** ≈ one full read of the partition + one full write. Cloud egress + put cost.
- **Read-latency savings** scale with query frequency × users. A partition queried hourly by 50 users earns its compaction cost back in days. A partition queried once a month does not.
- **Rule of thumb**: compact when `daily_read_time × users > compaction_cost × frequency`. Without telemetry (pre-v0.5), use the §5 thresholds as proxies.
- **Storage savings** from compaction only materialize after snapshots referencing the old files **expire** (per [`snapshot_retention.md`](./snapshot_retention.md) §6) AND orphan-file cleanup runs. Compaction + retention are two halves of the same operation.

---

## §10. Useful links

- [Iceberg docs — Maintenance: Compact data files](https://iceberg.apache.org/docs/latest/maintenance/#compact-data-files) — the canonical Java/Spark reference.
- [PyIceberg API — Write to a table](https://py.iceberg.apache.org/api/) (sections "Append", "Overwrite", "Partial overwrites", "Dynamic Partition Overwrite") — the Python primitives we use.
- [iceberg-python issue #270](https://github.com/apache/iceberg-python/issues/270) — tracking issue for native rewrite (verify URL on 2026-08-01).
- [DuckDB Iceberg extension](https://duckdb.org/docs/stable/extensions/iceberg) — read-side companion (read-only in 1.1.3 per [`duckdb.md`](../research/duckdb.md) §4).
- [Iceberg spec — Snapshots](https://iceberg.apache.org/spec/#snapshots) — context for fast-append vs merge-commit tradeoffs.
- Related Nucleus docs: [`partitioning.md`](./partitioning.md) §4 (sizing — why small files happen), [`snapshot_retention.md`](./snapshot_retention.md) (why compaction storage savings depend on retention), [ADR-001](../decisions/ADR-001-no-iceberg-commit-service.md) (atomicity guarantees we rely on).

---

*This document is normative. When code disagrees with this doc, the doc is the source of truth — update the code.*
