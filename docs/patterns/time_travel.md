# Pattern: Iceberg Time Travel

> **Tier 1+** per [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) §6.2. User surface (`ctx.read(..., snapshot_id=...)`, `ctx.snapshot(...)`) lands in v0.3+ ([`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md) §10). Full Replay & Time-Travel Debugger in v0.8+ (`nucleus_architecture_v4.1.md` §7.6). See also [`pyiceberg.md`](../research/pyiceberg.md) §4, §5; [`snapshot_retention.md`](./snapshot_retention.md) §3, §4; [`schema_evolution.md`](./schema_evolution.md) §5. Last reviewed 2026-05-12 against `pyiceberg==0.8.1`.

---

## §1. What this pattern is

Every commit creates a new **snapshot** — an immutable point-in-time view of the whole asset (per [Iceberg spec — snapshots](https://iceberg.apache.org/spec/#snapshots)). Time travel points a scan at a non-current snapshot, by **snapshot ID** (exact) or **timestamp** (resolves to the latest snapshot ≤ requested time). Metadata-driven: a time-travel read costs the same as a regular read — **as long as the snapshot still exists** (retention can expire it, per [`snapshot_retention.md`](./snapshot_retention.md)).

---

## §2. When to apply

- **Debugging anomalies / audit trails / backfill verification**: reproduce a downstream metric or "what was the customer balance on Jan 1?" against the exact input state; diff `snapshot_id_before` vs `_after`.
- **Reproducible analytics**: pin a notebook / report so re-runs are bit-identical (v0.5+ Marimo + `ctx.snapshot(...)`).
- **Replay debugging** (v0.8+, per `nucleus_architecture_v4.1.md` §7.6) and **DR rollback** (v0.5+ `nucleus snapshot revert`, per §14.5).

---

## §3. How (Nucleus wrap)

User code never imports `pyiceberg`. The SDK (per [`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md) §10) exposes a `snapshot_id=` / `snapshot_at=` keyword on `ctx.read` plus a `ctx.snapshot(asset)` inspection helper (`.history()`, `.at_time(...)`, `.at_snapshot(...)`, `.diff(...)`).

```python
import nucleus

@nucleus.asset
def daily_audit(ctx):
    current = ctx.read("sales.orders")
    yesterday = ctx.read("sales.orders", snapshot_id=ctx.params.yesterday_snapshot_id)
    return current.join(yesterday, on="order_id", how="left_anti")
```

| Release | Surface |
|---|---|
| v0.1 | **Not user-exposed.** AMA pins a snapshot ID per run for OpenLineage only. PoC scripts may call §4 directly with `# NEEDS VERIFICATION`. |
| v0.3 | `ctx.read(asset, snapshot_id=...)`, `snapshot_at=...`; `ctx.snapshot(asset)` helper. |
| v0.5+ | `.diff(...)`; `nucleus snapshot revert` CLI; Marimo + Workbench integration. |
| v0.8+ | Full Replay & Time-Travel Debugger; cost-aware planner gates expensive replays (per `nucleus_architecture_v4.1.md` §7.5). |

Vocabulary (per [AGENTS.md](../../AGENTS.md) §7): **snapshot**, never "version". SDK spec's legacy `at_version(...)` is open drift; resolves to `at_snapshot(...)` before v0.3.

---

## §4. How (underlying library — pyiceberg 0.8.1)

```python
from pyiceberg.catalog import load_catalog
# Docs: https://py.iceberg.apache.org/api/#scans  (Pinned: 0.8.1)

table = load_catalog("default").load_table("warehouse.orders")
arrow_table = table.scan(snapshot_id=8723195120384571234).to_arrow()
for snap in table.history():
    print(snap.snapshot_id, snap.timestamp_ms, snap.summary)
# Docs: https://py.iceberg.apache.org/api/#snapshots
```

- `Table.scan(..., snapshot_id=None, ...) -> DataScan` — `None` reads current; pass an ID for exact-point read.
- `Table.history()` — chronological `(timestamp_ms, snapshot_id)` log. Post-0.8 docs document an `as_of(timestamp=...)` convenience; verify in 0.8.1 (§8).
- `Table.snapshots()` — full snapshot objects (already-expired ones do NOT appear).
- `Table.manage_snapshots().create_tag(name, snapshot_id)` — pin a snapshot so retention cannot expire it (per [`snapshot_retention.md`](./snapshot_retention.md) §4). The v0.5+ `nucleus snapshot tag` CLI wraps this.

---

## §5. Anti-patterns

- **Querying an expired snapshot.** Retention prunes it (per [`snapshot_retention.md`](./snapshot_retention.md) §3) → `NoSuchSnapshotException` → `NucleusSnapshotExpiredError`. No recovery after orphan-file cleanup. Mitigation: **tag** any snapshot you plan to query >7 days later. Same gotcha for the v0.8+ Replay Debugger pinning expired upstreams (per [`snapshot_retention.md`](./snapshot_retention.md) §7).
- **Cross-asset time travel by wall-clock timestamp.** Each asset has its own timeline — no global clock. `snapshot_at` on two assets can resolve to snapshots hours apart. For consistency, run a pinning materialization that records upstream snapshot IDs into an `ops.snapshot_pin` asset.
- **Snapshot ID as row version.** A snapshot covers the **whole asset**. Per-row CDC requires a separate engine; spec v2 has no row-level versioning.
- **Time travel across schema evolution without aliases.** Dropped or renamed columns still exist physically in older snapshots (per [`schema_evolution.md`](./schema_evolution.md) §5 — zombie columns). SQL against current names may NULL out or fail at planning.

---

## §6. Trade-offs

- **Storage cost.** 7-day retention + daily writes ≈ 7× steady-state storage for heavily-overwritten assets. Quantify with the v0.5+ Cost Meter.
- **Retention vs deep time travel** — incompatible. Use tags for long-lived points; expire the rest.
- **Schema drift surprises** — time travel returns the historical schema (per [`schema_evolution.md`](./schema_evolution.md) §5); cross-asset consistency requires explicit pinning (see §5).

---

## §7. Cross-refs

- [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) §6.2 (AMA emits OpenLineage with snapshot IDs), §7.6 (Replay Debugger), §14.5 (DR rollback).
- [`pyiceberg.md`](../research/pyiceberg.md) §4, §5, §6 (`NoSuchSnapshotException` → `NucleusSnapshotExpiredError`); SDK: [`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md) §4, §10.
- Related: [`snapshot_retention.md`](./snapshot_retention.md) §3, §4; [`schema_evolution.md`](./schema_evolution.md) §5; [`compaction.md`](./compaction.md) §6. Spec: [iceberg.apache.org/spec/#snapshots](https://iceberg.apache.org/spec/#snapshots).

---

## §8. NEEDS VERIFICATION

Confirm via PoC #1 against `pyiceberg==0.8.1`; log results to [`ai_hallucinations.md`](../research/ai_hallucinations.md).

- [ ] Exact `Table.scan()` parameter name for pinning: docs show `snapshot_id=`; older mentions used `snapshot=`.
- [ ] Whether 0.8.1's `Table.scan()` accepts `as_of(timestamp=...)` or requires `Table.history()` + manual lookup.
- [ ] Whether `Table.manage_snapshots().create_tag(...)` exists in 0.8.1 (same TODO as `snapshot_retention.md` §4).
- [ ] Exception type / import path on `Table.scan(snapshot_id=<expired>)`: `NoSuchSnapshotException` vs generic `ValidationError`.
- [ ] Old-snapshot projection after a rename: Arrow schema returns the **old** or **new** name? Hypothesis: old.

*Normative. When code disagrees, the doc wins — update the code.*
