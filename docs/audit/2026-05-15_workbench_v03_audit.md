# Workbench v0.3 Audit — 2026-05-15

## 1. Component Classification

### `src/nucleus/workbench/static/index.html` (619 lines)

| Component | Classification | Notes |
|---|---|---|
| `TopNav` | **Interactive** | Nav page switching works; Search bar, Bell, Avatar are display-only clickable elements with zero functionality |
| Hero stat chips (total assets, rows, checks, last run) | **Display-only** | Fetches real data from `/api/dashboard/summary`, but renders as static text — no drill-down |
| `RecentRunsCard` run rows | **Display-only** | Renders from summary runs; each row has `cursor:pointer` class but `onClick` is undefined → click does nothing |
| `PipelineDAGCard` | **Display-only** | SVG shows real assets but nodes are un-clickable rectangles; "Fit view" button navigates to Assets page which is a stub |
| `CopilotCard` | **Interactive** | Full send/receive; input + submit + suggestion chips all functional; calls `/api/chat` |
| Search bar (⌘K) | **Display-only** | Styled as a button, no handler, never opens a palette |
| Bell icon | **Display-only** | No handler, no notification model |
| Avatar | **Display-only** | No handler |
| Assets page | **Stub** | `PlaceholderPage` — icon + "Coming soon" text + npm build hint |
| Runs page | **Stub** | `PlaceholderPage` — same |
| Query page | **Stub** | `PlaceholderPage` — same |
| Schedules page | **Stub** | `PlaceholderPage` — same |
| Catalog page | **Stub** | `PlaceholderPage` — same |

**Summary**: 1 fully interactive component (CopilotCard), 3 partially interactive (TopNav navigation, stat chips with real data), 2 display-only with click affordance but no action, 5 full stubs.

---

## 2. Backend API Consumer Map

| Endpoint | Has UI consumer? | Notes |
|---|---|---|
| `GET /api/dashboard/summary` | ✅ Yes | Powers hero chips + recent runs list |
| `GET /api/assets` | ⚠ Partial | Used in `PipelineDAGCard` for node labels only (display-only SVG) |
| `GET /api/assets/{key}` | ❌ No | Endpoint exists, no UI consumer |
| `GET /api/catalog` | ❌ No | Catalog page is a stub |
| `POST /api/chat` | ✅ Yes | CopilotCard |
| `POST /api/query` | ❌ No | Query page is a stub |
| `GET /api/runs` | ❌ No | Dashboard uses summary which embeds recent runs; `/api/runs` itself never called |
| `GET /api/runs/{id}/log` | ❌ No | SSE log stream exists; no EventSource consumer in UI |
| `POST /api/runs/trigger` | ❌ No | Trigger endpoint exists; no button in UI |
| `GET /api/schedules` | ❌ No | Schedules page is a stub |
| `GET /api/schedules/{key}/preview` | ❌ No | No UI consumer |
| `GET /api/search` | ❌ No | ⌘K bar renders but has no handler |

**Orphan endpoints** (7 of 12): `/api/assets/{key}`, `/api/catalog`, `/api/query`, `/api/runs`, `/api/runs/{id}/log`, `/api/runs/trigger`, `/api/schedules`, `/api/schedules/{key}/preview`, `/api/search`.

---

## 3. Visual Audit

### Hero noise (current)
- SVG `feTurbulence` `baseFrequency='0.75'` with `numOctaves='4'`
- SVG `<rect>` has `opacity='0.03'` → effectively invisible
- Outer `::before` has `opacity: 0.18`
- **Combined opacity: 0.03 × 0.18 ≈ 0.005 — essentially invisible**
- No `mix-blend-mode` — even if visible, no metallic depth
- Reference images show grain at ~0.40 opacity with `overlay` blend mode for metallic depth

### Card noise
- Cards have zero grain/texture
- Plain `background: #ffffff` with `box-shadow`
- Reference images show grain on solid surfaces

---

## 4. Phase 3 Feature Selection (8-question gate)

### Passed gate (implement in v0.3):

1. **Full Assets page** — asset cards, filter, click-to-detail  
   - Layer 4 ✅ | Beachhead ✅ | Wrap existing API ✅ | No JVM ✅ | LOC OK ✅ | v0.1 ✅

2. **Asset detail slide-over** — schema, deps, checks, Materialize button  
   - Layer 4 ✅ | Beachhead ✅ | Uses `/api/assets/{key}` + `/api/runs/trigger` ✅ | LOC OK ✅

3. **Runs page** with filter/sort + Run detail slide-over (log stream)  
   - Layer 4 ✅ | Beachhead ✅ | Uses `/api/runs` + `/api/runs/{id}/log` ✅ | LOC OK ✅

4. **Live Materialize button** — trigger run + SSE log tail + toast  
   - Layer 4 ✅ | Beachhead (first-run experience) ✅ | Uses existing endpoints ✅ | LOC OK ✅

5. **SQL Query page** — textarea + run + tabular result  
   - Layer 4 ✅ | Beachhead (explore data immediately) ✅ | Uses `/api/query` ✅ | LOC OK ✅

6. **Schedules page** — cron list + next 7 days timeline  
   - Layer 4 ✅ | Beachhead ✅ | Uses `/api/schedules` ✅ | LOC OK ✅

7. **⌘K Command Palette** — connects search bar to `/api/search`  
   - Layer 4 ✅ | Beachhead ✅ | Uses existing `/api/search` endpoint ✅ | LOC OK ✅

### Deferred (fail gate):
- Full DAG pan/zoom with D3: D3 is a new CDN dep. Defer to v0.4 (offline bundle). Client 8: No CDN ❌
- Catalog page (separate tab): Covered by Assets page with filter. Deferred to reduce LOC.
- Partition matrix: No backend endpoint yet. v0.3+ needed. Question 3 ❌
