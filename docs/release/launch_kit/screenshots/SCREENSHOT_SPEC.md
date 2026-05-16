# Workbench Launch Screenshots -- Reproduction Spec

> **Status**: 6 placeholder PNGs (1x1 transparent, 68 bytes each) committed
> alongside this spec. **The founder must replace each placeholder with a
> real capture before the v0.2 launch announcement** -- see "Capture
> instructions" below.
>
> **Rationale**: the build environment that produced this spec has no
> headless browser available (Windows agent without Chrome / Chromium /
> Playwright). Per the workstream brief: "DO NOT fake them -- instead
> produce a SCREENSHOT_SPEC.md with placeholder PNGs."
>
> **Output target**: 6 PNG files at **1440 x 900** resolution (15 inch
> retina-ish), saved into `docs/release/launch_kit/screenshots/`.
>
> **Toolchain (founder's laptop)**:
> - Chrome / Edge / Firefox dev-tools "Capture Node Screenshot" or
>   "Capture Full-Size Screenshot" -- both render at the device pixel
>   ratio so a 1440x900 viewport on a 2x display gives a 2880x1800
>   PNG (downscale to 1440x900 before commit).
> - **OR** Playwright one-shot: `npx playwright screenshot --viewport-size=1440,900 http://localhost:8765 NN_xxx.png`
> - **OR** macOS `screencapture -R0,0,1440,900 -x out.png` after positioning the window.

---

## Common setup (do once before any capture)

1. **Clone or activate the demo project** (provides realistic dogfood data,
   not an empty registry):

   ```bash
   cd examples/nucleus-demo-app/
   ../../.venv/bin/python scripts/generate_seed.py
   docker compose up -d postgres
   ../../.venv/bin/python scripts/seed_postgres.py
   ../../.venv/bin/python -m nucleus.cli.main run bronze.orders silver.daily_revenue gold.revenue_dashboard
   ```

   This populates the in-process run ledger with 3 successful runs and
   registers 8 demo assets (3 bronze, 4 silver, 1 gold).

2. **Start the Workbench in a clean browser profile**:

   ```bash
   ../../.venv/bin/python -m nucleus.cli.main workbench up --no-browser
   # then in browser: http://localhost:8765
   ```

   Use **Chrome incognito** (or `--user-data-dir=/tmp/wb-shot`) so no
   personal extensions / themes pollute the capture.

3. **Set viewport to 1440 x 900**: DevTools -> toggle Device Toolbar ->
   Responsive -> set 1440x900 + 1x DPR. Reload.

4. **Verify the brand palette renders correctly**:
   - Charcoal `#0A0E1A` for body text
   - Off-white `#fff` page background, `#FAFAFA` for inputs
   - Accent blue `#2A5BFA` for CTAs and links
   - Error red `#DC2626` for error states
   - Success green `#10B981` for success badges
   - Muted gray `#5A6273` for secondary text

   System font stack only (no Google Fonts) -- the page should render in
   Inter / SF Pro / Segoe UI / system-ui.

---

## Screenshot 1 -- `01_asset_graph.png` (Asset DAG)

**File**: `docs/release/launch_kit/screenshots/01_asset_graph.png`

**Capture target**: the full Assets page with 5-8 assets visible as cards.

**Reproduction**:

```bash
# Demo data should be loaded per "Common setup" above.
# Browser navigation:
#   http://localhost:8765/  -> click "Assets" in top nav
```

**Expected visible content**:

- Top hero strip with charcoal-on-blue navigation: `nucleus / my_warehouse`,
  nav links (Dashboard / Assets active / Runs / Query / Schedules), search
  pill `CmdK`, bell icon, terminal avatar.
- Page H2 "Assets" + subtitle "8 registered".
- Search filter pill on the right: "Filter assets..." with magnifying icon.
- Card grid (3 columns at 1440 width) showing 8 asset cards:
  - `bronze.customers`, `bronze.orders`, `bronze.products` (each with
    "Contract" green badge if contract is set)
  - `silver.customer_ltv`, `silver.daily_revenue`, `silver.top_products`
    (each with "1 dep" or "2 deps" muted badge)
  - `gold.customer_segments`, `gold.revenue_dashboard` (with "Scheduled"
    blue badge if `schedule="@daily"` is set)
- Each card shows the monospace asset key in bold, badges in a row,
  and a `>` chevron on the right.

**Color expectations**: charcoal text on white cards, blue chevrons on
hover, muted gray subtitle text. Header hero is the deep blue gradient
(`#3A6FF8` -> `#0F1E6E`) with the metallic noise overlay.

---

## Screenshot 2 -- `02_query_editor.png` (SQL Query)

**File**: `docs/release/launch_kit/screenshots/02_query_editor.png`

**Capture target**: the Query page with a sample SQL query just executed
against the demo Iceberg warehouse, results pane showing 10 rows.

**Reproduction**:

```bash
# Browser:
#   http://localhost:8765/  -> click "Query" in top nav
# In the SQL editor textarea, paste:
SELECT
  order_date,
  channel,
  total_revenue,
  order_count
FROM silver.daily_revenue
ORDER BY order_date DESC
LIMIT 10;
# Click "Run query" (or press Ctrl+Enter)
# Wait ~200 ms for the result table to populate
```

**Expected visible content**:

- Page H2 "Query" + subtitle "Run SQL against your warehouse. Ctrl+Enter
  to execute."
- "Examples" row at top of editor card -- 3 monospace example pills.
- SQL editor textarea (gray background `#FAFAFA`, dashed-blue focus border)
  containing the SELECT above.
- "Run query" button (blue `#2A5BFA`, white text, play-arrow icon) +
  "Ctrl+Enter" hint + "10 rows" counter on the right.
- Result table: 4 columns (`order_date`, `channel`, `total_revenue`,
  `order_count`), 10 rows, each row showing realistic values:
  - dates: `2026-05-12`, `2026-05-11`, ... (ISO format)
  - channels: `web`, `mobile`, `partner` (mix)
  - revenue: numeric values (e.g. `42135.50`, `38901.25`)
  - order_count: integers (e.g. `1247`, `1101`)

**Color expectations**: white card background, charcoal text, blue button.
The result table header has gray `#FAFAFA` background, hover rows tint
slightly blue.

---

## Screenshot 3 -- `03_ai_chat.png` (AI Copilot)

**File**: `docs/release/launch_kit/screenshots/03_ai_chat.png`

**Capture target**: the dashboard view showing the AI Copilot card on the
right with an active conversation about the asset graph.

**Reproduction** (mock mode if no API key):

```bash
# To capture without real LLM cost, set:
export NUCLEUS_COPILOT_MOCK=1   # if mock-mode env var exists, or:

# Otherwise: real mode with API key
export ANTHROPIC_API_KEY=sk-ant-...

# Browser:
#   http://localhost:8765/   (dashboard)
# In the right "AI Copilot" card, click on the suggestion chip
#   "Why did revenue_daily run longer today?"
# Wait ~2-3 s for the assistant reply.
# Or, to keep the canned chip text visible in chat, type:
#   "Explain this DAG"
# Press Enter.
```

**Expected visible content**:

- The full dashboard: hero with "Today's pipeline" H1 + 4 stat chips
  (`8 ASSETS . -- ROWS . 8/8 GREEN . 2m ago`).
- 3-column grid below: Recent materializations (left), Asset graph
  (middle), AI Copilot (right with active conversation).
- AI Copilot card on the right shows:
  - Pulsing blob-orb avatar at top + "AI Copilot" heading.
  - User message bubble (blue, right-aligned): "Explain this DAG"
  - Assistant message bubble (gray, left-aligned): a 3-4 line answer
    in the Nucleus vocabulary, e.g.:
    > "Your warehouse has 8 registered assets across 3 layers. Bronze
    > assets ingest from Postgres; silver assets aggregate them; gold
    > assets produce BI-ready outputs. The DAG depth is 3, with
    > `gold.revenue_dashboard` as the deepest sink."
  - Composer input at bottom: "Ask anything..." + send button.

**Color expectations**: blue user bubbles, gray assistant bubbles, the
blob-orb cycles through brand gradient (blue -> purple -> cyan -> green).

---

## Screenshot 4 -- `04_run_monitor.png` (Run List)

**File**: `docs/release/launch_kit/screenshots/04_run_monitor.png`

**Capture target**: the Runs page showing the recent run table with
multiple statuses (success / failure / running) and timing data.

**Reproduction**:

```bash
# Demo data + a deliberate failure for variety:
../../.venv/bin/python -m nucleus.cli.main run bronze.orders        # success
../../.venv/bin/python -m nucleus.cli.main run silver.daily_revenue # success
../../.venv/bin/python -m nucleus.cli.main run gold.customer_segments  # success
# A deliberate failure (e.g. bad SQL ref):
NUCLEUS_DEMO_FORCE_FAIL=1 ../../.venv/bin/python -m nucleus.cli.main run silver.top_products   # failure (NE2006)
# Trigger a run that's still running:
../../.venv/bin/python -m nucleus.cli.main run gold.revenue_dashboard --async &

# Browser:
#   http://localhost:8765/  -> click "Runs"
```

**Expected visible content**:

- Page H2 "Runs" + subtitle "12 recorded".
- 4 filter chips at top: `All (12)`, `Success (10)`, `Failure (1)`,
  `Running (1)` -- one chip filled charcoal as the active filter.
- Search filter on the right.
- Result table: 5 columns (Status / Asset / Duration / Started / Rows):
  - 1 row: yellow "running" badge, `gold.revenue_dashboard`, no duration
    yet, "5s ago", `--` rows.
  - 8 rows: green "success" badges with monospace asset keys, durations
    like `1.2s`, `847ms`, `3.4s`, started timestamps `1m ago` / `2m ago`,
    rows written like `8.4K`, `12.1K`.
  - 1 row: red "failure" badge for `silver.top_products`, duration
    `412ms`, "30s ago", `--` rows.

**Color expectations**: green badges for success, red for failure, yellow
for running. Hover row tints blue.

---

## Screenshot 5 -- `05_error_display.png` (NucleusError Display)

**File**: `docs/release/launch_kit/screenshots/05_error_display.png`

**Capture target**: a NucleusError surfaced in the Query page showing
NE-code + user-friendly message + fix hint + Retry button.

**Reproduction**:

```bash
# Browser:
#   http://localhost:8765/  -> click "Query"
# In the SQL editor textarea, paste a query that violates a contract,
# e.g. a missing column reference that triggers NE2006:
SELECT non_existent_column FROM silver.daily_revenue;
# Click "Run query"
# The error banner appears below the editor.
```

**Expected visible content**:

- The Query page top half (page H2 + editor card with the SQL above).
- Below the editor, the **error banner** in the brand error palette:
  - Red-on-pink background (`rgba(239,68,68,0.06)` / border
    `rgba(239,68,68,0.20)`)
  - Alert-circle icon at left
  - Bold red message: "Column `non_existent_column` not found in
    asset `silver.daily_revenue`."
  - Muted gray hint below: "Check the column name against the contract
    in `assets/silver_daily_revenue.py`. Run
    `nucleus assets describe silver.daily_revenue` to see the schema."
  - **"Re-run query" retry button** on the right of the banner: white
    background, red border, refresh icon + label.
- Below the banner (still visible), the empty result panel.

**Critical contract** (verified by `tests/workbench/test_no_dagster_leaks.py`):
the error message **must not** contain "dagster", "OpExecutionContext",
"DuckDBPyConnection", "polars.exceptions", "pyiceberg.exceptions", or any
external classname. Only the NE-code (e.g. `NE2006`), user-friendly
message, and fix hint should appear. **If you see a stack trace or a
foreign classname in the screenshot, the error translation has
regressed -- STOP and file a bug.**

---

## Screenshot 6 -- `06_init_flow.png` (Terminal CLI)

**File**: `docs/release/launch_kit/screenshots/06_init_flow.png`

**Capture target**: a terminal screenshot of `nucleus init my-project`
showing the scaffolded files.

**Reproduction**:

```bash
# In a fresh empty directory:
cd /tmp
rm -rf my-project
nucleus init my-project
# Terminal output should show:
#   Creating project 'my-project' in /tmp/my-project ...
#   [x] Created nucleus_project.yaml
#   [x] Created assets/__init__.py
#   [x] Created assets/example.py
#   [x] Created checks/__init__.py
#   [x] Created README.md
#   [x] Created .gitignore
#
#   Project ready! Next steps:
#     cd my-project
#     nucleus up
#     nucleus run example
#
#   Workbench: nucleus workbench up
```

**Capture instructions**:

- Use a **dark-theme terminal** (e.g. Windows Terminal "One Half Dark",
  iTerm2 "Solarized Dark", or default Cursor/VS Code integrated
  terminal). Background should be near-black, text near-white.
- Set window to ~120 columns x ~32 rows so the entire output is visible
  with comfortable margins.
- Capture window only (not full screen). Crop to roughly 1440x900 with
  the terminal content centered.
- Optional: run `tree my-project/` after the init to show the directory
  structure in a second terminal pane / line:
  ```
  my-project/
  +-- .gitignore
  +-- README.md
  +-- assets/
  |   +-- __init__.py
  |   +-- example.py
  +-- checks/
  |   +-- __init__.py
  +-- nucleus_project.yaml
  ```

**Color expectations**: dark terminal background, monospace font (e.g.
Cascadia Code, JetBrains Mono, Fira Code), green checkmarks `[x]`, white
file paths, blue or cyan "Next steps" CTA.

---

## Verification checklist (founder, before commit)

After replacing each placeholder PNG:

- [ ] Each PNG is exactly **1440 x 900** (use `file 01_asset_graph.png`
      to verify).
- [ ] Each PNG is < **500 KB** (PNG-8 / `optipng -o3` if needed).
- [ ] No personal info visible: no API keys, no `~/Users/<your-name>`
      paths, no email addresses, no laptop hostname in the terminal.
- [ ] No "dagster" / "duckdb" / "polars" / "pyiceberg" classnames
      visible anywhere in any screenshot -- re-test by reading the image.
- [ ] Brand palette respected (charcoal / off-white / accent blue /
      error red / success green / muted gray).
- [ ] No emojis used in the UI text shown (per AGENTS.md tone -- only
      use emojis if user explicitly requests them).
- [ ] No banned vocabulary visible: no "table" (use "asset"), no
      "job" / "task" (use "asset" / "materialization"),
      no "metastore" (use "catalog"), no "AI helper" (use "Copilot"). <!-- banned-term: metastore -->

When all 6 PNGs pass, replace this spec entry with `## Captured` and
commit alongside the launch announcement.

---

## Why placeholders, not faked screenshots

Per AGENTS.md sec.10 (10) discipline: AI agents must not fabricate output
that purports to be real. A "fake" screenshot rendered by an AI image
generator would (a) misrepresent the actual Workbench appearance, (b)
embed AI-typical artifacts (warped text, inconsistent fonts, bad
shadows) that any reviewer would spot, (c) potentially leak banned
vocabulary or non-Nucleus framings via the generator's training data.

The honest path is: produce a precise reproduction spec + 1x1
placeholder PNGs that fail any "is this a real screenshot?" check, and
hand off to the human who can capture in the real environment. The
brief explicitly endorsed this fallback.

---

*Last updated: 2026-05-15 by the Workbench UX Final Polish workstream.*
*Architecture refs: `docs/specs/nucleus_architecture_v4.1.md` sec.6.5, ADR-016 sec.3.*
