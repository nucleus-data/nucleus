# Pattern Reference

Per [`docs/specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) §6.3 (Coordination Layer) — and the L0 type-mapping contract called out in §5.5 — Iceberg lifecycle and cross-cutting operational patterns live here. Each pattern is a **how-to + why** reference, not a runnable walkthrough — read the linked file before writing or reviewing code that touches `Table.append`, `Table.overwrite`, partition specs, schema diffs, or anything credential-shaped.

This file is a navigation index. Patterns are versioned to the pinned wrapped-library release in [`../compatibility.md`](../compatibility.md); when a pin moves, the affected pattern is re-reviewed before the upgrade lands per [`AGENTS.md`](../../AGENTS.md) Hard Constraint #11.

---

## Iceberg lifecycle & layout

| File | Purpose | Size |
|---|---|---|
| [partitioning.md](./partitioning.md) | Picking the right `PartitionSpec` transform — the #1 silent perf killer | ~15 KB |
| [compaction.md](./compaction.md) | Why small files kill reads + when to merge (v0.3+ `nucleus optimize`) | ~13 KB |
| [snapshot_retention.md](./snapshot_retention.md) | Snapshot lifecycle, expire-snapshots, physical reclamation (v0.3+ `nucleus expire-snapshots`) | ~15 KB |
| [time_travel.md](./time_travel.md) | `snapshot_id=` / `snapshot_at=` reads, replay debugging (v0.5+) | ~7 KB |
| [schema_evolution.md](./schema_evolution.md) | Add / drop / rename / widen via metadata-only commits + immortal field IDs | ~7 KB |

## Cross-cutting

| File | Purpose | Size |
|---|---|---|
| [type_mapping.md](./type_mapping.md) | Postgres ↔ Iceberg ↔ Arrow ↔ Polars ↔ DuckDB authoritative mapping table | ~16 KB |
| [secret_management.md](./secret_management.md) | `pydantic.SecretStr` + `ctx.secrets` discipline; OIDC delegation per Hard Constraint #6 | ~7 KB |

---

## Conventions

- **Pattern, not recipe.** Patterns explain the *why* and the *Nucleus wrap*. End-to-end runnable walkthroughs live in [`../recipes/`](../recipes/).
- **Cite the wrapped library.** Every pattern links to its [`../research/<lib>.md`](../research/) anchor and the pinned release per [`../compatibility.md`](../compatibility.md).
- **No bare `pyiceberg` in user-facing examples.** Code samples always wrap through `ctx` — patterns demonstrate the abstraction users actually see.
- **Vocabulary** per [`AGENTS.md`](../../AGENTS.md) §7: *asset*, *snapshot*, *contract*, *check*, *materialization*. Never *table* (as primitive), *version* (for snapshots), *test* (for asset checks).
- **Property tests enforce.** Where a pattern is mechanically verifiable (`type_mapping.md`), property tests in `tests/patterns/` are the contract; doc and tests evolve together.

---

[← `docs/specs/nucleus_architecture_v4.1.md` §6.3](../specs/nucleus_architecture_v4.1.md) · [Sibling — decisions/](../decisions/README.md) · [Sibling — research/](../research/README.md) · [Sibling — recipes/](../recipes/README.md) · [Sibling — security/](../security/README.md)

*Last updated 2026-05-13. Add new patterns by appending to the matching group; the group is set by which architecture section the pattern serves. One file per pattern — do not bundle.*
