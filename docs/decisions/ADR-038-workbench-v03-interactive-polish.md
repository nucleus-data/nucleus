# ADR-038: Workbench v0.3 Interactive Polish

**Status**: ACCEPTED  
**Date**: 2026-05-15  
**Author**: Builder Agent  
**Area**: Layer 4 — Experience (Workbench)

---

## Context

Workbench v0.2 shipped an offline-renderable editorial hero static SPA (ADR-016 Fork B) but all pages except Dashboard + Copilot were stubs showing "Coming soon." Seven backend API endpoints had no UI consumers. The founder requested:

1. Stronger "metallic noise" visual (duotone gradient + dense film grain overlay)
2. Meaningful interactivity — "chuẩn chỉ" polish equivalent to real OSS data platforms (Dagster, Superset, Mage)

---

## Decision

### Visual: Metallic film-grain hero

| Parameter | v0.2 | v0.3 |
|---|---|---|
| SVG `feTurbulence baseFrequency` | 0.75 | 0.65 |
| SVG `<rect>` opacity | 0.03 | 1.0 (full) |
| `::before` CSS `opacity` | 0.18 | **0.40** |
| `mix-blend-mode` | none | **overlay** |
| `feColorMatrix` | none | `saturate: 0` (desaturate for clean blend) |
| Card grain | none | `::after` multiply 0.06 opacity |

Combined effect: effective noise opacity jumps from 0.005 to 0.40 with `overlay` blending that creates metallic depth on the blue gradient. Cards carry a 6% grain for texture consistency.

### Interactive features (7, all in single `index.html` file)

1. **Assets page** — card grid with filter; click → asset detail slide-over
2. **Asset detail slide-over** — metadata + Materialize CTA + SSE log stream
3. **Runs page** — full table with status filter chips + search; auto-polls every 6s
4. **Run detail slide-over** — log stream via `EventSource`
5. **Query page** — SQL textarea + Ctrl+Enter + result table + error banner with `fix_hint`
6. **Schedules page** — 7-day dot-matrix timeline + per-schedule next-run cards
7. **⌘K Command Palette** — keyboard-navigable `/api/search` consumer

### No new dependencies

All features use only the existing vendor files (React UMD, Tailwind Play CDN). No npm, no new CDN. Fully offline-renderable.

### No new backend endpoints

All 7 features consume existing API endpoints. No new Python code was added.

---

## Consequences

- LOC delta: +434 lines HTML (619 → 1053 lines)
- Zero new backend LOC (0 Python lines added)
- All 7 previously orphaned API endpoints now have UI consumers
- 35/35 existing tests pass; governance scripts all exit 0
- CDN-absence verified: all 6 CDN patterns absent from served HTML
- `mix-blend-mode: overlay` has negligible effect on pure white backgrounds; card grain uses `multiply` instead to ensure visibility
- The `feColorMatrix saturate=0` desaturates the turbulence noise to grayscale, ensuring neutral grain that doesn't add unwanted color casts on the blue gradient

---

## Alternatives considered

- **Full D3 pan/zoom DAG**: requires new CDN dep (D3 UMD ~240KB) or offline bundle. Deferred to v0.4.
- **Monaco SQL editor**: requires UMD build (~2MB) + offline serving. Deferred to v0.4.
- **Catalog page as separate tab**: redundant with Assets page (same backend data). Collapsed into Assets page.
