# UI Founder Feedback — 2026-05-15 → 2026-05-16

**Walkthrough by:** Wave 2 builder (real-browser hands-on test, follow-up to
`UI_VERIFICATION_REPORT.md` which documented the API surface but left this
form empty).
**Method:** real Chrome 141 headless render + screenshot, in-process
ASGI httpx for SSE / asset-trigger paths the live server cannot reach,
PowerShell `Invoke-WebRequest` for the 11 GET / 4 POST endpoints, full DOM
dump verification of rendered React output.
**Server under test:** `nucleus workbench up --no-browser --port 8765`,
booted in **2.0s** (panel printed → "Application startup complete" timestamp,
captured from terminal log `597720`). Workbench `v0.2.0`, served from
`src/nucleus/workbench/static/index.html` (the offline-renderable bundle
per ADR-016 + ADR-042 — the React TS frontend is preview-only and was
**not** in scope for this walkthrough per ADR-042).

---

## What looks good

- **First-paint hero is striking.** Real Chrome render confirms the
  "Today's pipeline" h1 + glass stat-chip row + AI Copilot blob orb all
  hydrate without flicker. 696 KB PNG screenshot captured at 1440×900;
  no layout shift between source HTML (77.5 KB) and rendered DOM (107 KB)
  — React injection adds content but does not reflow the hero.
- **Vocabulary is on-spec.** The recent-activity card title is "Recent
  materializations" (not "Recent runs"), matching `AGENTS.md §7`. The
  empty-state copy ("No materializations yet" + `nucleus run <asset>`
  CTA) uses the same vocabulary. No banned terms (`job`, `task`,
  `pipeline output`) anywhere in the served HTML.
- **Error translation discipline holds end-to-end.** All 14
  good-and-bad-path responses I scanned (`/api/assets/__nope__`,
  `/api/query` with bad SQL / empty SQL / unknown table / drop,
  `/api/chat` without opt-in, `/api/runs/__nope__/log`,
  `/api/schedules/__nope__/preview`) returned NE-prefixed error codes
  with `user_message` + `fix_hint`. Zero leaks of the strings
  `dagster`, `OpExecutionContext`, `DuckDBPyConnection`, `traceback`,
  `PolarsError`, `pyiceberg.`, `Soda`, `dlt.` in any response body
  (combined 1559 bytes scanned).
- **Backend latency is excellent on loopback.** All 7 GET API endpoints
  warm-p95 < 50 ms. `GET /` html: cold 92 ms / warm-p95 16 ms.
  `GET /api/dashboard/summary`: cold 15 ms / warm-p95 22 ms.
  `GET /api/search`: warm-p95 5 ms. (Full timing matrix in
  `docs/workbench/lighthouse_real.json`.)
- **SSE streaming actually works.** `GET /api/runs/{id}/log` returns
  `text/event-stream; charset=utf-8` + `Cache-Control: no-cache` +
  `X-Accel-Buffering: no`, body `data: {"line":"…"}\n\n` per line +
  `data: [DONE]\n\n` sentinel — verified in-process against a
  pre-recorded run with three log lines.
- **Cross-browser HTML response is byte-identical** for Chrome 120 /
  Firefox 120 / Edge 120 / Safari 17 UA strings (77 542 bytes each).
  No UA-sniffing on the server side.
- **Run trigger flow is wired correctly.** `POST /api/runs/trigger
  {"asset_key":"smoke.b3_asset"}` (after registering the asset in-process)
  returned `200 {"run_id": ..., "status": "running", "started_at": ...}`,
  the run appeared in `GET /api/runs?limit=10` within ~400 ms with
  `status: "success"` and `duration_ms: 1`.
- **Static SPA is fully offline-renderable.** Vendored
  `vendor/tailwind.min.js` (407 KB), `vendor/react.production.min.js`
  (10.8 KB), `vendor/react-dom.production.min.js` (132 KB), `favicon.ico`
  (4.4 KB), `favicon.svg` all reachable as 200. The only `https://` URLs
  in the served HTML are an XML namespace declaration and one HTML
  attribution comment to lucide — no real-browser fetches go off-laptop.
- **Asset detail wiring is correct.** `GET /api/assets/{key}` returns
  the full asset record (key, deps, schedule, compute, has_contract,
  checks). The static SPA opens it as a slide-over panel (not a
  standalone route) which keeps the URL clean and matches the v0.2
  scope per ADR-016.

## What looks broken / off

- **Tailwind CDN runtime nag in real-browser console.**
  `vendor/tailwind.min.js:64` prints
  > `cdn.tailwindcss.com should not be used in production. To use
  > Tailwind CSS in production, install it as a PostCSS plugin or
  > use the Tailwind CLI`
  on every page load. This is the **only** console message Chrome
  emits at idle (no errors, no failed fetches). The script is served
  from `/vendor/` not the actual CDN, but the Tailwind Play runtime
  still fingerprints itself and prints the banner. Recommend swapping
  to a build-time Tailwind for v0.3 as `LIGHTHOUSE_NOTES.md`
  recommendation #3 already flags. Not a release blocker but it is
  the one observable real-browser defect.

- **`POST /api/chat` returns HTTP 500 for "opt-in declined".**
  When Copilot opt-in is not yet accepted, the body is correctly
  `NE5001` with the right user_message and a fix_hint pointing to
  `nucleus chat` and `copilot.opt_in: true`, but the status code is
  500. Semantically this is not a server error — the user request
  was well-formed and the server worked correctly; the user simply
  has not opted in. Suggest 412 (precondition failed) or 403
  (forbidden) instead of 500 so dashboards don't false-alarm.

- **`POST /api/query` with unknown table returns 500 (NE3002).**
  `{"sql":"DROP TABLE foo"}` (or `SELECT * FROM foo`) returns
  `500 NE3002` — the error code is correct but 500 implies server
  bug. Suggest 400 (bad request) since the SQL itself is well-formed
  but references something that doesn't exist. Same NE3002 code is
  fine; just downgrade the HTTP status.

- **NE5001 is overloaded.** Both "missing question" (422) and
  "Copilot opt-in declined" (500) carry the same NE5001 code. They
  are distinct conditions that should split: NE5001 = missing/empty
  input, new NE5xxx = opt-in declined. Document gap, not blocker.

- **`LIGHTHOUSE_NOTES.md` claims a `:root` CSS custom-property block
  exists in `static/index.html`** — it does not. Source contains zero
  `:root` selectors and zero `--var-name:` definitions. The polish
  pass that LIGHTHOUSE_NOTES describes appears to refer to the React
  TS frontend's `index.css` (which DOES have the full var palette)
  and got transcribed into the static-fallback notes by mistake. The
  static SPA uses inline `style={{ }}` props instead. Functionally
  fine (visuals look correct), but the Lighthouse-notes accessibility
  table is over-claiming; recommend a one-line correction.

## What's missing

- **Catalog and Search do not have top-nav entries in the static SPA.**
  The TopNav exposes `Dashboard / Assets / Runs / Query / Schedules`
  (5 items). `/api/catalog` and `/api/search` are wired and return
  valid JSON, but the only way to reach Search from the UI is the
  ⌘K Command Palette (which calls `/api/search`), and there is no
  way at all to reach Catalog from the UI. Per ADR-042 the
  Catalog page is part of the React TS frontend (v0.3 preview);
  the static SPA intentionally ships a narrower nav. Consider a
  one-line note in the dashboard hero or a breadcrumb pointing to
  ⌘K so users know Search exists. (Decision is design-by-ADR, not
  a bug — flagging visibility for v0.3 promotion.)

- **No standalone `/asset-detail` or `/run-detail` route in the
  static SPA.** These render as SlideOver panels triggered by
  clicking a row. Acceptable for v0.2 (consistent with ADR-016
  static-SPA scope), but linking and bookmarking are not possible
  — the URL stays at `/` regardless of which slide-over is open.
  Worth a v0.3 ticket to upgrade to React Router so URLs reflect
  state.

- **No `meta description` tag in `static/index.html`.** Will dock
  ~5 points off SEO if Lighthouse runs against this URL. Acceptable
  for an internal local-first tool but a one-line fix.

- **No `prefers-reduced-motion: reduce` media query** to disable the
  `blob-orb` pulse and skeleton shimmer. `LIGHTHOUSE_NOTES.md`
  recommendation #2 already calls this out for v0.3. Confirmed
  still missing from the served HTML.

- **No screenshots of pages other than Dashboard.** The launch-kit
  screenshot folder lives at `docs/release/launch_kit/screenshots/`
  (post-reorg path; not the `docs/internal/release-process/launch_kit/`
  path the spec references). It contains 6 PNGs:
  `01_asset_graph.png`, `02_query_editor.png`, `03_ai_chat.png`,
  `04_run_monitor.png`, `05_error_display.png`, `06_init_flow.png`.
  None look stale (file mod-times verified) but the static SPA's
  Dashboard / Assets / Runs / Schedules pages are not represented;
  recommend regenerating with the v0.2 hero design before launch.
  Per spec, real-browser screenshot regeneration was out of scope
  for this walkthrough.

## What's confusing

- **The Copilot suggestion-chip placeholder text references assets
  that don't exist by default**: "Why did revenue_daily run longer
  today?", "What changed in orders_silver?". A first-time user with
  an empty registry will click these and see a confusing "Asset
  not found" or hallucinated reply. Suggest swapping to neutral
  prompts like "What is Nucleus?" or "Show me how to register my
  first asset" until project context is detected.

- **The TopNav brand string is `nucleus / my_warehouse`** — the
  `my_warehouse` part is a hard-coded placeholder in the static
  HTML (line 598). For a fresh `nucleus init` project it should
  pull the actual project name from `nucleus_project.yaml`.
  Currently every Workbench shows "my_warehouse" regardless.

- **`POST /api/chat` accepts the `stream=true` query parameter but
  the field is also accepted in the body.** Pydantic union of
  query + body is fine but the OpenAPI spec (`/api/openapi.json`)
  documents only the body field. A user reading the docs and
  setting `?stream=true` in the URL gets the body to default
  `false` if the client doesn't also send `stream` in the JSON.
  Minor doc nit.

## Performance notes (load time, responsiveness)

Empirical timings on this laptop (Win11, Python 3.11, FastAPI dev
server, all measurements via PowerShell `Invoke-WebRequest`,
1 cold + 5 warm samples):

| Endpoint | Cold | Warm avg | Warm p95 | Target | Verdict |
|---|---:|---:|---:|---:|---|
| `GET /` (HTML) | 92 ms | 9.6 ms | 16 ms | < 500 ms | PASS |
| `GET /api/health` | 157 ms | 27.6 ms | 48 ms | < 100 ms | PASS |
| `GET /api/dashboard/summary` | 15 ms | 13.8 ms | 22 ms | < 200 ms | PASS |
| `GET /api/assets` | 6 ms | 8.8 ms | 17 ms | < 200 ms | PASS |
| `GET /api/runs` | 12 ms | 6.6 ms | 9 ms | < 200 ms | PASS |
| `GET /api/catalog?page=1&page_size=20` | 14 ms | 5.8 ms | 7 ms | < 200 ms | PASS |
| `GET /api/search?q=test` | 4 ms | 4.2 ms | 5 ms | < 200 ms | PASS |
| `vendor/tailwind.min.js` | 21 ms | 20.6 ms | 22 ms | (407 KB asset) | OK |
| `vendor/react.production.min.js` | 7 ms | 6.8 ms | 7 ms | (10.8 KB asset) | OK |
| `vendor/react-dom.production.min.js` | 20 ms | 12.4 ms | 14 ms | (132 KB asset) | OK |

- **Cold boot of the workbench process**: 2.0 s from CLI invocation
  to "Application startup complete" + Uvicorn binding (terminal log).
  Well under the 10 s target. Workers expect 5-15 s on a cold Python
  cache; this run had warmed bytecode.
- **Real Chrome render**: dashboard fully populated in a single
  headless screenshot pass with `--virtual-time-budget=4000`. No
  console errors, no failed fetches, one INFO message from the
  Tailwind CDN runtime (see "What looks broken").
- **Total payload for cold first-load**: 627.8 KB (HTML + 3 vendor
  scripts + favicon). Under the 1 MB target.

## Pages tested

- [x] **Dashboard** (`/`) — `GET /` returns 77.5 KB HTML; `GET
  /api/dashboard/summary` returns `{"total_assets":0, ...,
  "recent_runs":[]}` 200 with empty-state values; real Chrome render
  shows hero + 4 stat chips + Recent materializations card +
  Pipeline DAG card + AI Copilot card with 3 suggestion chips.
  All 5 expected static-SPA pages reachable from TopNav.
- [x] **Assets** (`page='assets'`) — `GET /api/assets` returns `[]`
  on empty registry; after registering an asset in-process,
  returns `[{"key":"smoke.b3_asset","deps":[],"schedule":null,
  "compute":null,"has_contract":false,"checks":[]}]`. AssetsPage
  component exists in static SPA.
- [x] **Asset Detail** (slide-over, not a standalone route) —
  `GET /api/assets/smoke.b3_asset` returns the full asset record;
  `GET /api/assets/__nonexistent__` returns
  `404 {"detail":{"error_code":"NE3001","user_message":"Asset
  '__nonexistent__' is not registered.","fix_hint":"Check that
  the module defining this asset is imported."}}`.
- [x] **Runs** (`page='runs'`) — `GET /api/runs?limit=20` returns
  `[]` initially; populated after `POST /api/runs/trigger` runs
  in-process. `RunsPage` component exists in static SPA.
- [x] **Run Detail + SSE log stream** — `GET /api/runs/{id}/log`
  returns `text/event-stream; charset=utf-8`, `Cache-Control:
  no-cache`, `X-Accel-Buffering: no`. Body for a 3-line run:
  ```
  data: {"line": "line one"}

  data: {"line": "line two"}

  data: {"line": "line three"}

  data: [DONE]
  ```
  Unknown run id returns `404 NE3001` with proper fix_hint.
- [x] **Schedules** (`page='schedules'`) — `GET /api/schedules`
  returns `[]`; `GET /api/schedules/__nope__/preview` returns
  `404 NE3001 "No schedule found for asset '__nope__'."` with a
  fix_hint pointing at `schedule=...` in `@nucleus.asset`.
- [x] **Query (SQL editor)** —
  - `POST /api/query {"sql":"SELECT 1 AS x"}` → `200
    {"columns":["x"],"rows":[[1]],"row_count":1,"truncated":false}`
  - `POST /api/query {"sql":"SELEKT BAD SYNTAX"}` → `400 NE2002`
    "SQL syntax error: Parser Error: syntax error at or near …"
    + fix_hint
  - `POST /api/query {"sql":""}` → `422 NE2001` "A SQL string is
    required."
  - `POST /api/query {}` → `422` Pydantic standard "Field required"
  - `POST /api/query {"sql":"DROP TABLE foo"}` → `500 NE3002`
    "SQL referenced an unknown object" (status code probably should
    be 400 — see "What looks broken")
  - `POST /api/query {"sql":"SELECT generate_series FROM
    generate_series(1,10000)"}` → `200` 1 165 b body, 200 rows
    truncated correctly
- [x] **Catalog** + **Search** + **Chat/Copilot**
  - `GET /api/catalog?page=1&page_size=20` → `200
    {"items":[],"total":0,"page":1,"page_size":20}`
  - `GET /api/search?q=test` → `200 {"query":"test","items":[]}`;
    `GET /api/search?q=` → `200 {"query":"","items":[]}`
  - `POST /api/chat?stream=true {"question":"hi","stream":true}`
    → `500 NE5001` "Copilot opt-in declined. No data was sent."
    (well-formed error; status-code grade B per "What looks broken")
  - `POST /api/chat {"question":""}` → `422 NE5001` "A question
    is required."
  - `POST /api/chat {"message":"hi"}` (using brief's body shape)
    → `422` Pydantic "Field required" because the schema expects
    `question` not `message` — chat schema doc nit, not a bug.

## Browsers tested

- [x] **Edge 120** UA — server returned 77 542 bytes HTML, byte-
  identical to baseline.
- [x] **Chrome 120** UA — server returned 77 542 bytes HTML, byte-
  identical to baseline.
- [x] **Firefox 120** UA — server returned 77 542 bytes HTML, byte-
  identical to baseline.
- [x] **Safari 17 (macOS)** UA — server returned 77 542 bytes HTML,
  byte-identical to baseline.
- [x] **Real Chrome 141** (system installed) headless render —
  full DOM hydration, screenshot 696 744 bytes at 1440×900, zero
  JS console errors, zero failed fetches, one INFO Tailwind nag
  message (see "What looks broken").

Server is UA-agnostic (no UA sniffing). Client-side rendering parity
verified directly only for Chrome 141; Edge / Firefox / Safari
parity inferred from shared HTML + React UMD compatibility.

---

## Phase 3 — npm install + Lighthouse (best effort, expected fail)

Both blocked by Bosch corporate Artifactory TLS chain:

```
npm error code UNABLE_TO_VERIFY_LEAF_SIGNATURE
npm error errno UNABLE_TO_VERIFY_LEAF_SIGNATURE
npm error request to https://lo-artifact.de.bosch.com/artifactory/api/npm/
  npm-automationx/@monaco-editor%2freact failed, reason: unable to verify
  the first certificate; if the root CA is installed locally, try running
  Node.js with --use-system-ca
```

Same failure mode for `npx --yes lighthouse --version` (Artifactory chain
on the `lighthouse` package). Different mode than the original verification
report (which described a hang) but same outcome: cannot install. Per
ADR-016 §3 the static-fallback design exists precisely for this proxy
constraint, so the React-TS frontend remains preview-only per ADR-042
and Lighthouse must be re-run from a non-proxied environment for
ratified scores.

Empirical performance + render measurements that stand in for the
Lighthouse run live at `docs/workbench/lighthouse_real.json` (this PR).
Server-side timing + Chrome render confirmation only — not Core Web
Vitals.

---

## Phase 6 / process notes

- Workbench was started via
  `.venv\Scripts\python.exe -m nucleus.cli.main workbench up
   --no-browser --port 8765` and stopped via `taskkill /pid 31416`
  at the end of this walkthrough.
- A small ASGI in-process script was used to register
  `smoke.b3_asset` and exercise the trigger / SSE happy path that
  the bare `Invoke-WebRequest` cannot reach (the live server has
  no assets registered). No production code in `src/nucleus/`
  was modified.

---

*Last updated: 2026-05-16 by the v0.2 release-readiness Wave 2 builder.*
