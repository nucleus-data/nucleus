# Architecture Diagrams & Skeleton Plans

Per [`docs/specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) §3 (Five Layers) and §6 (Coordination Layer), every structural artifact that visualizes the Nucleus runtime — C4 levels, sequence diagrams, the v0.1 `src/nucleus/` skeleton — lands here. These artifacts are the **derivative**; v4.1 is the **source of truth**. When v4.1 amends, this folder is the first dependent set updated; never the reverse.

This file is a navigation index. Read the linked artifact for the actual Mermaid diagrams, scope/audience callouts, and `NEEDS VERIFICATION` markers per [`AGENTS.md`](../../AGENTS.md) §11.12. Sequence diagrams sit alongside the modules they describe (e.g., `sequence_asset_materialization.md` ↔ `coordination/asset_materialization.py`).

---

## C4 levels (structural)

The C4 model has four levels (Context → Container → Component → Code). Read in order to orient — Code (L4) lives in the source tree, not here.

| File | Level / scope | Size |
|---|---|---|
| [C4_context.md](./C4_context.md) | L1 — Nucleus in its environment (users, external systems, giants) | ~12 KB |
| [C4_container.md](./C4_container.md) | L2 — Runtime containers on a single laptop at v0.1 scope | ~15 KB |
| [C4_component.md](./C4_component.md) | L3 — Components inside the `ctx` SDK (the developer contract) | ~14 KB |

## Sequence diagrams (behavioural)

UML sequence specs for every critical end-to-end path. Each cites its companion code module and the architecture section it serves.

| File | Path covered | Size |
|---|---|---|
| [sequence_error_translation.md](./sequence_error_translation.md) | Critical — Dagster failure → `NucleusError` (PoC #1 backbone, v4.1 §6.4) | ~24 KB |
| [sequence_asset_materialization.md](./sequence_asset_materialization.md) | Happy path — `nucleus run` → new Iceberg snapshot via the AMA (v4.1 §6.2) | ~10 KB |
| [sequence_ingestion.md](./sequence_ingestion.md) | `ctx.copy_from` — source URL → first Iceberg asset (PoC #3, v4.1 §5.5.1) | ~11 KB |
| [sequence_query.md](./sequence_query.md) | `ctx.sql` — Jinja `{{ ref() }}` → DuckDB → Arrow → Polars (PoC #2, v4.1 §5.6) | ~14 KB |
| [sequence_swap_drill.md](./sequence_swap_drill.md) | Quarterly composability swap drill process (v4.1 §9.3) | ~13 KB |

## Implementation skeleton

| File | Purpose | Size |
|---|---|---|
| [v01_skeleton_plan.md](./v01_skeleton_plan.md) | Target tree for `src/nucleus/` post-PoC-#1 promotion → v0.1 GA | ~16 KB |

---

## Conventions

- **Mermaid first.** Every diagram is fenced as ` ```mermaid ` so it renders inline on GitHub. ASCII fallbacks live next to the Mermaid block when the diagram is required reading.
- **Layers numbered bottom-up** per v4.1 §3.1: L0 = Physics, L4 = Experience. C4 component IDs match `src/nucleus/<layer>/`.
- **No invented APIs.** Every method/type cited in a sequence must exist in the wrapped library or be explicitly marked `NEEDS VERIFICATION` per [`AGENTS.md`](../../AGENTS.md) §11.12.
- **One sequence per critical path.** New paths (`nucleus optimize`, `ctx.snapshot`, etc.) get a new file; do not append to an existing sequence.
- **Diagram drift is caught quarterly** — see [`../internal/audits/`](../internal/audits/) and [`sequence_swap_drill.md`](./sequence_swap_drill.md).

---

[← `docs/specs/nucleus_architecture_v4.1.md` §3 + §6](../specs/nucleus_architecture_v4.1.md) · [Sibling — decisions/](../decisions/README.md) · [Sibling — swap/](../internal/swap/README.md) · [Sibling — research/](../research/README.md) · [Sibling — patterns/](../patterns/README.md)

*Last updated 2026-05-13. Add new diagrams by appending to the appropriate group; group is set by which architecture layer (L0..L4) or process the artifact serves. Keep entries to one line each.*
