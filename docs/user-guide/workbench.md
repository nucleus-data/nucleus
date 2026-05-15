# Nucleus Workbench — User Guide (v0.3)

Start the Workbench with:

```bash
nucleus workbench up
```

Opens at `http://127.0.0.1:8765/` by default. Use `--port` to change, `--no-browser` to suppress auto-open.

---

## Visual design

The Workbench uses an **Editorial Hero** light theme with a **metallic film-grain** aesthetic. The hero gradient uses SVG `feTurbulence` (`fractalNoise`, `baseFrequency=0.65`, `numOctaves=4`) overlaid at 40% opacity with `mix-blend-mode: overlay` — producing dense, visible grain similar to analog film stock. Cards carry a 6% multiply-mode grain for consistent texture. The underlying gradient is the locked blue palette (`#3A6FF8` → `#0F1E6E`).

---

## Dashboard

The landing page shows:

- **Hero stat chips** — total assets, estimated rows, checks green/total, time since last materialization
- **Recent materializations** — last 8 runs; click any row → **Run detail slide-over** with log stream
- **Asset graph mini-preview** — static DAG; click a node → **Asset detail slide-over**; "Explore all" → Assets page
- **AI Copilot** — ask natural-language questions about your pipeline; responds via `/api/chat`

---

## Assets page

Navigate via the top nav "Assets" link.

- Shows all `@nucleus.asset`-decorated assets as cards
- Each card shows: asset key, schedule badge, contract badge, checks count, deps count
- **Filter** the list by typing in the search box (client-side, instant)
- **Click any card** → opens the Asset detail slide-over

### Asset detail slide-over

- **Metadata**: deps, schedule cron, contract status, checks list with severities
- **Materialize button**: triggers `POST /api/runs/trigger`, then opens a live SSE log stream showing progress in a dark terminal panel
- On completion: "Materialization queued — check Runs for status" confirmation

---

## Runs page

Navigate via "Runs" in the top nav.

- Full table of materialization runs (most recent first)
- **Filter chips**: All | Success | Failure | Running — single-click filter
- **Search**: type an asset name to filter the table in real time
- Auto-refreshes every 6 seconds to pick up in-flight materializations
- **Click any row** → Run detail slide-over

### Run detail slide-over

- Run ID, asset key, status, start time, duration, rows written, snapshot ID
- **Log output panel**: streams all recorded log lines via `EventSource` to `/api/runs/{run_id}/log`; lines color-coded (green = completed, amber = warning, red = error)

---

## Query page

Navigate via "Query" in the top nav.

- **SQL textarea** — write any DuckDB-compatible SQL; `{{ ref('asset_key') }}` Jinja notation supported
- **Ctrl+Enter** (or click "Run query") → executes via `POST /api/query`
- **Example presets** — click to pre-fill the editor
- **Result table** — scrollable table with sticky headers; up to 200 rows
- **Truncation banner** — shown when `truncated: true` in response (more rows exist)
- **Error banner** — displays `user_message` + `fix_hint` from NucleusError responses (never raw stacktraces)

---

## Schedules page

Navigate via "Schedules" in the top nav.

- **7-day timeline** — matrix table: rows = scheduled assets, columns = next 7 days
  - Blue circle = at least one run scheduled that day (hover for time)
  - Small gray dot = no run that day
- **Per-schedule cards** — shows asset key, cron expression, and all computed next-run timestamps
- Consumes `GET /api/schedules` (returns cron + next 5 runs per schedule)

---

## ⌘K Command Palette

Press **⌘K** (macOS) or **Ctrl+K** (Windows/Linux) anywhere to open the command palette:

- Type at least 2 characters → live search via `GET /api/search?q=...`
- Results include assets, recent runs, and scheduled assets
- **Arrow keys** to navigate, **Enter** to jump to the matching page
- **Esc** to close

---

## Offline-first

The Workbench is fully offline-renderable — no CDN requests. All dependencies (React 18 UMD, Tailwind Play CDN, icons as inline SVG paths) are served from `static/vendor/`. This means it works on air-gapped machines and corporate networks with proxy restrictions.

---

## API surface (consumed by Workbench v0.3)

| Endpoint | Page |
|---|---|
| `GET /api/dashboard/summary` | Dashboard hero chips + recent runs |
| `GET /api/assets` | Assets page card grid + Dashboard DAG |
| `GET /api/assets/{key}` | Asset detail slide-over |
| `POST /api/runs/trigger` | Materialize button |
| `GET /api/runs?limit=100` | Runs page table |
| `GET /api/runs/{id}/log` | Run log slide-over (SSE stream) |
| `POST /api/query` | Query page result table |
| `GET /api/schedules` | Schedules page timeline + cards |
| `POST /api/chat` | AI Copilot card |
| `GET /api/search?q=...` | ⌘K command palette |
