---
name: nucleus-iceberg-write
description: >-
  Pull Iceberg-write knowledge into context. Use when writing or modifying any
  code that produces Iceberg snapshots — `catalog.create_table`, `table.append`,
  `table.overwrite`, `table.delete`, partition spec, or any function inside
  `coordination/asset_materialization_adapter.py`,
  `coordination/iceberg_writer.py`, or PoC #3 ingest paths.
---

# Iceberg Write Discipline

Snapshot-producing code is the highest-leverage failure surface in the
Coordination Layer. Catalog-side atomic commit is the only commit primitive
per `@docs/specs/nucleus_architecture_v4.1.md §6.3` and
`@docs/decisions/ADR-001-no-iceberg-commit-service.md`.

## Read these before writing snapshot code

Each pattern doc is normative — re-read on first edit and on any partition /
schema / lifecycle change. Do not re-derive their content here.

- `@docs/patterns/partitioning.md` — transform menu, sizing, decision tree
  (§9 is the fastest path to a sensible default).
- `@docs/patterns/compaction.md` — when small files become a problem.
- `@docs/patterns/snapshot_retention.md` — every commit makes a snapshot.
- `@docs/patterns/schema_evolution.md` — safe vs. reader-breaking changes.
- `@docs/patterns/time_travel.md` — querying historical snapshots.

## v0.1 Heartbeat defaults

The Nucleus-specific synthesis. These override anything in the pattern docs
that reads "v0.5+" or "default policy".

### Partitioning

- **Default: single time-bucket transform** (`day(<primary_ts>)` typical;
  `month(<primary_ts>)` for low-volume archives) on the primary timestamp
  column. NOT no-partition; NOT over-partition. Cite
  `@docs/patterns/partitioning.md` §4 + §9.
- One transform per asset, max. Multi-field specs land in v0.5+ once the
  AMA has been exercised on real workloads.
- `@nucleus.asset(partition_by="day(event_ts)")` translates the string DSL
  to a `PartitionSpec` — users never `import pyiceberg.partitioning`
  directly per `@docs/specs/nucleus_architecture_v4.1.md §13.1`.

### Compaction

- **PoC #3 and v0.1 do NOT auto-compact.** Document the surface but defer
  triggers to v0.3+ (`nucleus optimize`) and v0.5+ (default policy) per
  `@docs/specs/nucleus_architecture_v4.1.md §18.3`.
- Any compaction helper now is Tier 2 only — never fire from the hot
  materialization path.

### Snapshot retention

- **PoC #3 and v0.1 keep ALL snapshots.** No `ExpireSnapshots`. No default
  `history.expire.*` table properties.
- `table.maintenance.expire_snapshots()` requires `pyiceberg>=0.9.1`. Our
  pin is `0.8.1`. The upgrade is gated by
  `@docs/decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md`, which
  fires automatically on PoC #1 promotion. Do not call `expire_snapshots`
  in v0.1 code paths.
- v0.3+ exposes `nucleus expire-snapshots <asset>`; v0.5+ applies a default
  7-day policy per `@docs/patterns/snapshot_retention.md` §7.

### Schema evolution

- **Always additive in v0.1.** New column with default value is the only
  shape `ctx.write` applies automatically.
- Renames, drops, and widening require a contract version bump and an
  explicit `nucleus migrate` (v0.3+). Reject silent drops.
- Field IDs are immutable — never rewrite. See
  `@docs/patterns/schema_evolution.md` §1.

### Atomicity

- One catalog commit per snapshot. Multi-table atomicity is NOT a Nucleus
  primitive — the catalog owns the commit per
  `@docs/specs/nucleus_architecture_v4.1.md §6.3` and Hard Constraint #5
  (`@AGENTS.md §3`).
- On `CommitFailedException` (concurrent write): retry up to 3×, then
  surface `NucleusCommitConflictError`. On `CommitStateUnknownException`:
  do NOT retry; surface `NucleusCommitUnknownError` per
  `@docs/internal/research/pyiceberg.md` §6.

## Wrapped-library access

`import pyiceberg` is permitted inside `coordination/` only. User code
never imports it — the `ctx` SDK is the only stable public surface
(`@docs/specs/nucleus_architecture_v4.1.md §13.1`). Cite docs URLs on every wrapped
import per `@AGENTS.md §11.12`.
