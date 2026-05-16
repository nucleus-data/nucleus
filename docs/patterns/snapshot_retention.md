# Pattern: Iceberg Snapshot Retention

> **Pattern**: Big Data — Iceberg Lifecycle / Maintenance
> **Status**: Pre-implementation reference. Not exposed in v0.1. CLI surface (`nucleus expire-snapshots`) lands in v0.3+.
> **Audience**: Anyone reviewing the Asset Materialization Adapter; anyone debugging "we delete daily but storage keeps growing".
> **References**: [`docs/internal/research/pyiceberg.md`](../research/pyiceberg.md) §4, §5; [`docs/patterns/compaction.md`](./compaction.md); [`docs/patterns/partitioning.md`](./partitioning.md); [`docs/decisions/ADR-001-no-iceberg-commit-service.md`](../decisions/ADR-001-no-iceberg-commit-service.md)
> **Last reviewed**: 2026-05-12 — versions per [`docs/internal/compatibility.md`](../internal/compatibility.md) (`pyiceberg==0.8.1`)

Read this **before** any code path that calls `Table.append`, `Table.overwrite`, or the compaction recipe in [`compaction.md`](./compaction.md). Every one of those creates a snapshot. Without retention, snapshots accumulate forever.

---

## §1. Why snapshot retention matters

- **Every commit** to an Iceberg table — every `Table.append`, every `Table.overwrite`, every schema/spec update inside a `Transaction` — creates a new **snapshot**. Snapshots are immutable points-in-time (per the [Iceberg spec — Snapshots](https://iceberg.apache.org/spec/#snapshots)).
- **"Delete" in Iceberg is logical, not physical.** `Table.overwrite(...)` adds a new snapshot that excludes the deleted rows, but the old data files stay on disk because earlier snapshots still reference them.
- **Without retention**, a year of daily appends + small daily overwrites = ~700 snapshots × ~10 partitions per snapshot = thousands of retained data files, none of which can be deleted.
- Storage grows **monotonically forever**. New users see "delete should reclaim space" and find it doesn't. This is **the** support question of any Iceberg-based platform.
- Retention is the operation that converts logical deletes into physical reclamation.

---

## §2. What an Iceberg snapshot actually is

A snapshot is a small piece of metadata, not a copy of the data. Knowing its shape makes the retention rules below intuitive.

| Field | Meaning |
|---|---|
| `snapshot_id` | Unique long integer. Used in time-travel queries. |
| `timestamp_ms` | Wall-clock ms since epoch at commit time. |
| `parent_snapshot_id` | The snapshot this one was built on; `null` for the first. Forms a linear history per branch. |
| `manifest_list` | Path to a `*-snap-*.avro` file listing all manifests alive at this snapshot. |
| `summary` | Operation type (`append`, `overwrite`, `delete`, etc.) + counters (added-files, deleted-files, added-records). |

Inspecting via PyIceberg (per [`pyiceberg.md`](../research/pyiceberg.md) §5):

```python
table = catalog.load_table("warehouse.orders")
for snap in table.snapshots():
    print(snap.snapshot_id, snap.timestamp_ms, snap.summary.operation)
current = table.current_snapshot()
```

- `table.snapshots()` returns all live snapshots (already-expired ones don't appear; they're physically gone from metadata).
- `table.current_snapshot()` is just the latest on the main branch — used for `SELECT *` reads.
- `table.history()` returns the same list ordered by time. Reference: [py.iceberg.apache.org/api/](https://py.iceberg.apache.org/api/) ("Snapshots" section).

---

## §3. The retention dimensions

Iceberg's expiration policy is governed by **two orthogonal dimensions**. Use both; neither alone is sufficient.

| Dimension | Iceberg table property | Default we recommend |
|---|---|---|
| **Max age** | `history.expire.max-snapshot-age-ms` | 7 days (604,800,000 ms) |
| **Min count** | `history.expire.min-snapshots-to-keep` | 10 snapshots |

- Both are enforced **simultaneously**: a snapshot is kept if it's newer than max-age **OR** within the most-recent min-count. The intersection of "too old" AND "beyond min-count" is what gets expired.
- The min-count is a **safety floor**. If you commit 50 times in one hour, the 7-day max-age would expire none of them, but if you commit once a year for 5 years, min-count=10 keeps all 5 plus enforces no expiration on the most recent ones.
- Set on a table via the catalog:

```python
with table.transaction() as txn:
    txn.set_properties({
        "history.expire.max-snapshot-age-ms": str(7 * 24 * 60 * 60 * 1000),
        "history.expire.min-snapshots-to-keep": "10",
    })
```

Reference: [iceberg.apache.org/docs/latest/configuration/](https://iceberg.apache.org/docs/latest/configuration/) (write properties — table properties section). The properties exist on the table itself; the engine running the expiration reads them to decide what to expire.

---

## §4. Time-travel implications

Snapshot retention has a direct user-facing consequence: queries against expired snapshots fail.

- After expiration, any of these fail with `NoSuchSnapshotException` (or its NucleusError-translated form):
  - Time-travel SQL: `SELECT * FROM orders FOR SYSTEM_VERSION AS OF <expired_snapshot_id>`.
  - Replay debugging via the v0.5+ time-travel debugger (per `docs/specs/nucleus_architecture_v4.1.md` §6.3).
  - Audit trails that pinned a specific snapshot_id.
- This is **intentional and correct** — you cannot read data files that no longer exist.
- **Tagged snapshots are protected from expiration.** Iceberg v2 supports named tags (`table.manage_snapshots().create_tag(...)`) that pin a specific snapshot indefinitely, regardless of policy. Use these for: monthly board-report cuts, regulatory snapshots, release pins.
- TODO: verify on 2026-08-01 that PyIceberg 0.8.1's `Table.manage_snapshots()` supports `create_tag` cleanly. The newer PyIceberg docs document the API but 0.8.1 was a patch release; check release notes for `manage_snapshots` mentions.

---

## §5. PyIceberg 0.8.1 status (honest version)

This section is the **most fragile** in the doc — treat as the current best understanding, not gospel. The maintenance API surface evolved significantly across PyIceberg 0.8 → 0.11.

- **The PyIceberg docs at [py.iceberg.apache.org/api/](https://py.iceberg.apache.org/api/) currently document a `table.maintenance.expire_snapshots()` API** with `.older_than(datetime)`, `.by_id(snapshot_id)`, and context-manager forms. The 0.8.1 release notes ([github.com/apache/iceberg-python/releases/tag/pyiceberg-0.8.1](https://github.com/apache/iceberg-python/releases/tag/pyiceberg-0.8.1)) do NOT mention this maintenance namespace — it appears to have landed post-0.8.
- **For 0.8.1**: the documented expiration flow is **catalog-side** or **manual**. Concretely:
  1. Set the `history.expire.*` properties on the table (§3) — these are read by **engines** running expiration, including Spark's `expireSnapshots` action.
  2. Trigger expiration externally (e.g., a Spark or Trino maintenance job) using the catalog the table is registered in.
- TODO: verify on 2026-08-01. Smoke-test: in PoC #1 or its maintenance follow-up, attempt `table.maintenance.expire_snapshots()` against a 0.8.1 install. If it raises `AttributeError`, document the actual 0.8.1 path. If it works, log to `docs/internal/research/ai_hallucinations.md` that the API IS in 0.8.1 (this section was wrong).
- **For v0.1 Heartbeat**: snapshot expiration is **NOT exposed to users** regardless. Documented here for human/operator awareness.
- **Alternative path** (v0.3+): catalog-side cron. Lakekeeper supports scheduled maintenance per-table; this is the path we'll most likely use rather than driving expiration from the AMA.

---

## §6. The "orphan files" problem

Expiration is **two operations**, and missing the second is the most common cause of "I expired and storage didn't shrink".

1. **Snapshot expiration** — removes snapshot entries from table metadata. The expired snapshots' manifest lists are deleted.
2. **Orphan file removal** — actually deletes the data files that were referenced **only** by the now-expired snapshots.

These are separate because expiration only knows about snapshots, not files. A file might be:

- Referenced by an active snapshot → keep
- Referenced by an expired snapshot but ALSO by an active one → keep (still live)
- Referenced only by expired snapshots → **orphan, delete**

Iceberg's reference implementation calls this `removeOrphanFiles` (per [iceberg.apache.org/docs/latest/maintenance/#delete-orphan-files](https://iceberg.apache.org/docs/latest/maintenance/#delete-orphan-files)). It's:

- **Slow** — must list the table's data directory and cross-reference with all live manifests. For a multi-TB warehouse this is minutes-to-hours.
- **Dangerous** — if run with a too-short retention interval, it can delete files for in-progress writes. The Iceberg docs recommend at least 3 days.
- TODO: verify on 2026-08-01 whether PyIceberg 0.8.1 has a `remove_orphan_files` equivalent or whether we delegate this entirely to the catalog (likely the latter for v0.1 — filesystem catalogs typically don't, Lakekeeper does).

Until orphan-file cleanup runs, expired snapshots' files **still occupy storage**. This is the root cause of the support question in §1.

---

## §7. Nucleus conventions

| Tier / Version | Retention surface |
|---|---|
| v0.1 (Heartbeat) | Not exposed. No automatic expiration. Default Iceberg properties unset (= no expiration policy). Documented here for human awareness. |
| v0.3 | `nucleus expire-snapshots <asset>` CLI command + `nucleus maintenance --schedule daily` Dagster schedule. |
| v0.5+ | Default policy applied automatically to all Tier 2 assets (per `docs/specs/nucleus_architecture_v4.1.md` §6.3). Telemetry-driven exceptions. |

**Default policy (Tier 2 / v0.5+)**:

- 7-day rolling window (max-age = 7d).
- Min 10 snapshots retained.
- Tagged snapshots retained indefinitely (release tags, audit pins).
- Expire + orphan-file cleanup run as a single Dagster maintenance schedule, low-traffic window.
- All expirations logged as OpenLineage events with `op=expire_snapshots` + counts (per `docs/specs/nucleus_architecture_v4.1.md` §6.2 AMA responsibility 5).

**Asset-level overrides** (v0.3+ syntax):

```python
@nucleus.asset(retention="30d", min_snapshots=20)
def orders_audit():
    ...
```

- v0.1 syntax is **inheritance only** (uses platform defaults). Per-asset overrides ship with the CLI surface in v0.3.

---

## §8. Operational guidance

For the operator running the v0.3+ maintenance job manually, or for anyone PoC-ing expiration on a real warehouse.

- **Run during low-traffic windows.** Expiration commits one new metadata file; not heavy, but pairs with orphan-file cleanup which IS heavy.
- **Test on a non-prod table first.** Always. Expiration is destructive; the policy is recoverable but the data referenced by the wiped snapshots is not.
- **Per-asset overrides matter**: analytical assets (long retention for audits) vs operational assets (short retention, frequent overwrites). One global policy is rarely right.
- **Monitor metadata-file count.** Iceberg writes a new `vN.metadata.json` per commit; old ones accumulate too. The [Iceberg maintenance docs](https://iceberg.apache.org/docs/latest/maintenance/#remove-old-metadata-files) recommend `write.metadata.delete-after-commit.enabled=true` with `write.metadata.previous-versions-max=100` to bound this.
- **If metadata-file count > ~100 per table**, your expiration cadence is wrong (too infrequent) OR your write rate has spiked. Both are observability triggers, not silent failures.
- **Long-lived warehouses**: review retention quarterly. Data importance changes; an analytical asset may turn operational, or vice versa.

---

## §9. Pitfalls

Each pitfall has a "why" — the reason it's non-obvious for a junior DE.

- **Expiring a snapshot currently being queried = query failure.** Iceberg's read path holds a reference to a specific snapshot for the duration of a scan. If expiration commits between scan-plan and scan-execute, the query fails. Mitigation: low-traffic window + `min-snapshots-to-keep` floor.
- **Tagged snapshots always win over the expiration policy.** This is **correct behavior** — you tagged it for a reason. But: a forgotten tag on an old snapshot will pin tens of GB of data files forever. Audit tags quarterly.
- **`min-snapshots-to-keep` is a safety floor, not a target.** It ALWAYS wins over `max-snapshot-age-ms`. A table with 50 commits in the last hour will keep all 50 even if max-age is "1 minute". This is by design.
- **Forgetting orphan-file cleanup = expiration without storage savings.** This is the most common misconfiguration. Always pair §6 step 1 with step 2.
- **Replay/backfill assumes the snapshot still exists.** If your replay tool pins to a specific snapshot_id and you expired it, replay fails. Use **tags** for any snapshot you plan to replay.
- **Compaction creates extra snapshots** (per [`compaction.md`](./compaction.md) §8). If you compact 10 partitions ungrouped, that's 10 extra snapshots — and those 10 keep the old small files alive until they themselves expire. Group compactions in a single `Table.transaction()` to commit one snapshot for the batch.
- **The `metadata.json` files THEMSELVES accumulate.** They're tiny (KB each) but at high write rates they add up. Enable `write.metadata.delete-after-commit.enabled` (per §8).
- **Snapshot IDs are NOT row-versions.** A snapshot covers the whole table at a point in time. Don't use snapshots as a per-row "version" mechanism (that's what schema field IDs and row lineage in spec v3 are for).

---

## §10. Useful links

- [Iceberg docs — Maintenance: Expire Snapshots](https://iceberg.apache.org/docs/latest/maintenance/#expire-snapshots) — canonical reference for the operation.
- [Iceberg docs — Maintenance: Delete orphan files](https://iceberg.apache.org/docs/latest/maintenance/#delete-orphan-files) — the second half of expiration.
- [Iceberg docs — Maintenance: Remove old metadata files](https://iceberg.apache.org/docs/latest/maintenance/#remove-old-metadata-files) — the metadata-file cleanup we configure via table properties.
- [Iceberg spec — Snapshots](https://iceberg.apache.org/spec/#snapshots) — what a snapshot actually is.
- [PyIceberg API — Snapshots / Maintenance](https://py.iceberg.apache.org/api/) — current Python surface; verify against 0.8.1 per §5.
- [Iceberg table write properties](https://iceberg.apache.org/docs/latest/configuration/#write-properties) — `history.expire.*` and `write.metadata.*` reference.
- Related Nucleus docs: [`compaction.md`](./compaction.md) (creates snapshots; coordinated with retention), [`partitioning.md`](./partitioning.md) (each spec evolution = a snapshot), [ADR-001](../decisions/ADR-001-no-iceberg-commit-service.md) (atomicity model the maintenance ops rely on).

---

*This document is normative. When code disagrees with this doc, the doc is the source of truth — update the code.*
