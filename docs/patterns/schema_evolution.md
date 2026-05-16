# Pattern: Iceberg Schema Evolution

> **Tier 1+** per [`docs/specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) §6.2, §14.3. Add-column auto-applied in v0.1 `ctx.write`; drop / rename / widen lands with `nucleus migrate` in v0.3+. See also [`pyiceberg.md`](../research/pyiceberg.md) §5, §7; [`partitioning.md`](./partitioning.md) §5; [`type_mapping.md`](./type_mapping.md) §4; [`time_travel.md`](./time_travel.md) §5. Last reviewed 2026-05-12 against `pyiceberg==0.8.1`.

---

## §1. What this pattern is

Iceberg can `add`, `drop`, `rename`, `reorder`, and `widen` columns **without rewriting data files** — every change is a metadata commit (per [Iceberg spec — schema evolution](https://iceberg.apache.org/spec/#schema-evolution)). Powered by **immutable integer field IDs**: data files identify columns by ID, not name (per [`pyiceberg.md`](../research/pyiceberg.md) §7). Old snapshots stay readable because they reference their original IDs and files.

---

## §2. When to apply

- Add (new business field); drop (decommission — see §5); rename (preserves field ID); widen (`int32 → int64`, `decimal(10,2) → decimal(18,4)`, `float → double`).
- **Stop** for "narrow a type", "drop an active partition column", or "promote nullable → required on a non-empty asset" — forbidden by the validator.

---

## §3. How (Nucleus wrap)

User code never imports `pyiceberg`. The AMA (~500 LOC, per `docs/specs/nucleus_architecture_v4.1.md` §6.2) diffs incoming Arrow schemas against the asset's Iceberg schema on `ctx.write` and bundles deltas into the same transaction.

```python
import nucleus
import polars as pl

@nucleus.asset(partition_by="day(event_ts)")
def orders(ctx):
    df = ctx.read("raw.orders")
    return df.with_columns(event_country=pl.col("event").struct.field("country"))
```

| Release | Surface |
|---|---|
| v0.1 | **Add-column auto-applied** (nullable, end of schema). Drops / renames / type changes rejected → `NucleusSchemaEvolutionError`. |
| v0.3 | `nucleus migrate <asset>` — diffs `@nucleus.contract` vs Iceberg, prompts, runs one `update_schema()` transaction. |
| v0.5+ | Schema-contracts engine pre-validates at planning time; column-level lineage emits field-ID stability events (per `docs/specs/nucleus_architecture_v4.1.md` §6.3). |

Vocabulary (per [AGENTS.md](../../AGENTS.md) §7): **asset** (logical), Iceberg **table** (physical). Only the AMA crosses.

---

## §4. How (underlying library — pyiceberg 0.8.1)

`UpdateSchema` is a fluent builder used inside `Table.transaction()` so the schema change commits atomically with the data write.

```python
from pyiceberg.types import LongType, StringType
# Docs: https://py.iceberg.apache.org/api/#schema-evolution  (Pinned: 0.8.1)

with table.transaction() as txn:
    with txn.update_schema() as update:
        update.add_column("event_country", StringType(), doc="ISO-3166-1 alpha-2")
        update.rename_column("amount_cents", "amount_minor_units")
        update.update_column("user_id", field_type=LongType())  # int → long widen
        update.delete_column("legacy_flag")
```

- `add_column(path, field_type, doc=None, required=False)` — nullable on non-empty assets; `required=True` rejected.
- `rename_column(old, new)` — preserves field ID; the **only** safe rename path.
- `update_column(name, field_type=..., required=..., doc=...)` — legal widenings; `required: True → False` only.
- `delete_column(name)` — cannot drop a column still in an active partition spec (per [`partitioning.md`](./partitioning.md) §5).
- `move_first` / `move_after` / `move_before` — reorder.

Inside `Transaction`, the schema commit bundles with appends as **one snapshot**. Illegal moves raise `pyiceberg.exceptions.ValidationError` → `NucleusSchemaEvolutionError` (per [`pyiceberg.md`](../research/pyiceberg.md) §5, §6).

---

## §5. Anti-patterns

- **Silent drop via `df.drop(...)`.** Does NOT evolve the schema — AMA auto-fills `null` or rejects. Use `nucleus migrate` explicitly.
- **Type narrowing.** Forbidden. Workaround: add a column with the narrower type, backfill via `overwrite`, drop the old.
- **Rename loops.** `delete_column` + `add_column` of the same name allocates a **new** field ID; the new column reads `null` for old rows. Always prefer `rename_column`.
- **Cross-API confusion.** `update_schema` and `update_spec` are separate; drop the partition field before dropping the column.
- **Mid-traffic migration.** Schema commits race in-flight writers → `CommitFailedException` → `NucleusCommitConflictError`. Run during quiet windows.
- **Zombie columns under time travel.** A dropped column's field ID is retired in the **current** schema, but old snapshots still reference it and their data files still physically contain it — time-travel reads (per [`time_travel.md`](./time_travel.md) §5) **return the dropped column**. GDPR consequence: drop does NOT purge; combine with `overwrite` + snapshot expiration + orphan-file cleanup (per [`snapshot_retention.md`](./snapshot_retention.md) §6).

---

## §6. Trade-offs

- **Cheap commits, eventual data debt.** Adding columns is free at commit time but inflates per-row footprint forever. Audit nullable columns quarterly.
- **No type narrowing, ever.** Overly-wide initial types are forever — unless you copy-and-cycle.
- **Names aren't stable identifiers.** Rename preserves field ID but breaks every downstream SQL query referring to the name; v0.3 has no compile-time guard.
- **Atomic only per asset.** Cross-asset migrations are sequenced; multi-table atomicity deferred to v1.0+ (per `docs/specs/nucleus_architecture_v4.1.md` §6.2).

---

## §7. Cross-refs

- [`docs/specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) §6.2 (AMA), §14.3 (allowed-change policy).
- [`pyiceberg.md`](../research/pyiceberg.md) §5, §6, §7, §9.
- Related: [`partitioning.md`](./partitioning.md) §5; [`type_mapping.md`](./type_mapping.md) §4; [`snapshot_retention.md`](./snapshot_retention.md) §6; [`time_travel.md`](./time_travel.md) §5.
- Spec: [iceberg.apache.org/spec/#schema-evolution](https://iceberg.apache.org/spec/#schema-evolution).

---

## §8. NEEDS VERIFICATION

Confirm via PoC #1 against `pyiceberg==0.8.1`; log results to [`ai_hallucinations.md`](../research/ai_hallucinations.md).

- [ ] `Table.update_schema()` returns a context manager in 0.8.1 (docs landed post-0.8; release notes silent).
- [ ] Dotted-path syntax (`"user.address.city"`) for nested add/drop works at depth ≥ 2.
- [ ] `update_column(..., field_type=...)` is the correct widening method in 0.8.1 (spec calls it `promote`).
- [ ] Exact import path of `ValidationError`: `pyiceberg.exceptions.ValidationError` vs `pyiceberg.ValidationError`.
- [ ] Whether `delete_column` + `add_column` of the same name in one block allocates the same or a new field ID.

*Normative. When code disagrees, the doc wins — update the code.*
