# NE2003 — NucleusResourceError

**Code**: `NE2003`  ·  **Class**: `NucleusResourceError`  ·  **Layer**: L1 Engines  ·  **Stability**: Stable

## What happened

A materialization exceeded an engine resource limit and the engine aborted it. Most commonly this is memory — the working set did not fit and the engine could not spill it cleanly.

## Likely causes

- The asset materializes more rows / wider rows than the engine's `memory_limit` allows.
- Filters and projections are applied *after* a heavy join, instead of pushed down.
- A cross join or accidental Cartesian explosion blew up row count.
- The engine's `memory_limit` is set lower than the working set genuinely requires.

## Fix steps

1. Filter and project earlier in the asset body so less data is held in memory.
2. Add or fix join keys so the join does not become a cross join.
3. If the working set is genuinely required, raise the engine `memory_limit` in your project config.

## Related

- Source: `src/nucleus/errors.py` (`NucleusResourceError`)
- Default fix hint: "Reduce the working set (filter / project earlier) or raise the engine `memory_limit`."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
