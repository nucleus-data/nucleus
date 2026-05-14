# Nucleus Workbench — Frontend (Editorial Hero v0.2)

React 18 + Vite 5 + TypeScript 5 + Tailwind CSS 3 SPA.
Designed as an **Editorial Hero** layout: bold gradient hero dashboard +
3-column grid (Recent Runs | Pipeline DAG | AI Copilot).

## Dev (requires npm / Node 18+)

```bash
# Install deps
npm install

# Dev server (proxies /api/* to localhost:8765)
# First, start the FastAPI backend: nucleus workbench up
npm run dev
# → open http://localhost:5173
```

## Build for production

```bash
npm run build
# dist/ is created; copy to src/nucleus/workbench/static/ so FastAPI serves it.
cp -r dist/* ../static/
```

## Proxy-blocked environments (Bosch APAC etc.)

If `npm install` fails (corporate proxy), the static CDN fallback demo is available
at `../static/index.html` and is served by FastAPI automatically.
The CDN demo renders the full Editorial Hero layout using React 18 via esm.sh and
Tailwind via the Play CDN — no build step required.

Run `nucleus workbench up` and open http://localhost:8765 to see the demo.

## Routes

| Route             | Page                                        |
|-------------------|---------------------------------------------|
| `/`               | Dashboard — Editorial Hero + 3-column grid  |
| `/assets`         | Asset Explorer (tree + React Flow DAG)      |
| `/assets/:key`    | Asset Detail drilldown                      |
| `/runs`           | Run history table + SSE log drawer          |
| `/runs/:run_id`   | Run Detail — live SSE log stream            |
| `/query`          | SQL Query Editor (Monaco)                   |
| `/schedules`      | Schedule list + next-run preview            |
| `/catalog`        | Asset catalog browser (paginated table)     |

## API endpoints (backend)

| Endpoint                           | Purpose                                 |
|------------------------------------|-----------------------------------------|
| `GET  /api/dashboard/summary`      | Hero stat chips + recent runs           |
| `GET  /api/assets`                 | List registered assets                  |
| `GET  /api/assets/{key}`           | Single asset detail                     |
| `GET  /api/runs`                   | Recent run history                      |
| `GET  /api/runs/{id}/log`          | SSE log stream                          |
| `POST /api/runs/trigger`           | Trigger asset materialization           |
| `POST /api/query`                  | Execute SQL via ctx.sql                 |
| `POST /api/chat`                   | AI Copilot single-turn exchange         |
| `GET  /api/schedules`              | List scheduled assets                   |
| `GET  /api/schedules/{key}/preview`| Next N run times for a schedule         |
| `GET  /api/catalog`                | Paginated/filtered asset catalog        |
| `GET  /api/search?q=`              | Global search (assets + runs + schedules)|

## Design system

**Editorial Light theme** (dark mode descoped in v0.2 per founder directive):

| Token           | Value    | Usage                              |
|-----------------|----------|------------------------------------|
| Hero gradient   | `#3A6FF8 → #0F1E6E` | Hero background   |
| Body bg         | `#FFFFFF` | Page/card background              |
| Border          | `#EEF0F4` | Card borders, dividers            |
| Primary         | `#2A5BFA` | Buttons, links, selected states   |
| Accent purple   | `#7C3AED` | Selected DAG node, highlights     |
| Success         | `#10B981` | Run success status                |
| Warning         | `#F59E0B` | Run warning / in-progress         |
| Error           | `#EF4444` | Run failure / error states        |
| Skip            | `#94A3B8` | Skipped runs                      |
| Text primary    | `#0A0E1A` | Body text                         |
| Text secondary  | `#5A6273` | Captions, labels                  |
| Monospace font  | JetBrains Mono | Asset keys, SQL, log output  |
| Sans font       | Inter     | All UI text                       |

## Keyboard shortcuts

| Shortcut       | Action                          |
|----------------|---------------------------------|
| `⌘K` / `Ctrl+K` | Open command palette           |
| `/`            | Open command palette (search)   |
| `↑` / `↓`      | Navigate palette results        |
| `Enter`        | Navigate to selected result     |
| `Esc`          | Close palette / modal           |
| `⌘Enter`       | Run SQL query (Query page)      |

## Stack

| Library               | Version  | Purpose                          |
|-----------------------|----------|----------------------------------|
| react                 | 18.3.1   | UI framework                     |
| react-dom             | 18.3.1   | DOM renderer                     |
| react-router-dom      | 6.28.2   | Client-side routing (8 routes)   |
| @tanstack/react-query | 5.62.3   | Data fetching + cache            |
| @tanstack/react-table | 8.20.5   | Asset/runs table                 |
| reactflow             | 11.11.4  | Asset DAG visualization          |
| @monaco-editor/react  | 4.6.0    | SQL query editor                 |
| zustand               | 5.0.2    | Global UI state                  |
| lucide-react          | 0.469.0  | Icons                            |
| tailwindcss           | 3.4.17   | Utility-first CSS                |
| vite                  | 5.4.11   | Build tool + dev proxy           |
| typescript            | 5.7.2    | Type safety                      |

## Architecture

Workbench is Layer 4 (Experience) per `nucleus_architecture_v4.1.md §8.1`.
The frontend communicates exclusively with the backend via `/api/*` endpoints.
It never imports Python code directly.

Routes are code-split via `React.lazy` — each page chunk loads on demand,
keeping the initial dashboard bundle small.
