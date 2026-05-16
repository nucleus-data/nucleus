# Workbench stack swaps (v0.2+)

This note records **on-demand** swap targets for the Workbench (Layer 4
Experience) per `docs/decisions/ADR-016-workbench-mvp.md` implementation notes
and rationale items 4–7. Full swap implementations are built only when a
trigger fires with **measured evidence** — not preemptive dual stacks.

## 1. `@xyflow/react` → Cytoscape.js (graph visualization)

**Default (v0.2):** `@xyflow/react` for asset graph views.

**Swap trigger**

- Real workloads exceed ~5000 graph nodes **and** profiling shows layout or
  interaction latency fails the Workbench RAM / interaction budget in
  `nucleus_architecture_v4.1.md` §16.3, not anecdotal issue links alone.

**Notes:** Keep the **asset graph** as a narrow interface (nodes/edges +
selection callbacks). Rewire rendering only; do not fork coordination or
`ctx` contracts.

## 2. Monaco Editor → CodeMirror (SQL editor)

**Default:** Monaco on the SQL editor route only (lazy-loaded per ADR-016).

**Swap trigger**

- `scripts/check_bundle_size.py` and real-network baselines show **initial**
  route load cannot meet the **< 500 KB gzipped initial JS** gate **after**
  code-splitting and lazy-load, **or** maintenance burden of the Monaco CDN /
  bundling path is higher than a CodeMirror integration for the same feature
  set.

## 3. FastAPI → Litestar (API process)

**Default:** FastAPI + Pydantic at the HTTP boundary.

**Swap trigger**

- **v0.3+ reconsideration only:** repeated, concrete friction between Pydantic
  models at the boundary and msgspec-first internal types (adapter noise,
  perf regression in hot paths, or serialization bugs), documented in an ADR.
  Not a preemptive swap for theoretical “ecosystem size” reasons alone.

## 4. Pure web → Tauri packaging (desktop distribution)

**Default (v0.2):** SPA built by Vite + FastAPI in one local process; bound to
`localhost:8765` by default.

**Swap trigger**

- v0.5+ packaging ADR: founder commits to **desktop install** UX and accepts
  Rust toolchain + platform packaging cost. Architecture stays “SPA + local
  API” so Tauri can host the same bundle or a documented sidecar.

## References

- ADR-016 Decision + Rationale §§4–7 and Risk mitigations (bundle size,
  xyflow scale, Pydantic vs msgspec, Tauri deferral).
- `docs/internal/research/workbench.md` — framework evidence base.
