# OSS Data Platform UI Research — 2026-05-15

Research for Nucleus Workbench v0.3 interactive polish.

---

## 1. Dagster Webserver (gold standard)

**Source**: https://github.com/dagster-io/dagster / https://docs.dagster.io/concepts/webserver

### UI patterns Nucleus should adopt:
- **Asset catalog with namespace grouping**: Assets listed in collapsible namespace groups (raw.*, silver.*, gold.*). Click any asset → right-side detail panel with: dependencies graph mini-preview, materialization history timeline, partition matrix, checks status, lineage upstream/downstream.
- **Run monitor panel**: Click any run row → full-screen slide-over with live SSE log streaming. Log lines color-coded: `[INFO]` gray, `[WARNING]` amber, `[ERROR]` red. Real-time scroll-to-bottom with auto-scroll toggle.
- **Materialize button in asset detail**: Prominent blue "Materialize" CTA; on click shows progress overlay with stage dots (Launching → Running → Storing snapshot). On completion: green badge + duration.
- **Partition health grid**: For partitioned assets, a calendar-style heatmap (green/yellow/red cells per partition). Not needed in v0.3 (no partitioned assets in v0.1 scope).
- **Status filter chips**: Above runs table, chips: All | Success | Failure | Running — single-click filter.

**Adopted for v0.3**: Asset detail panel, run log slide-over, Materialize progress, status filter chips.

---

## 2. Apache Airflow 3.0 UI

**Source**: https://airflow.apache.org/docs/apache-airflow/stable/ui.html

### UI patterns to note:
- **DAG Grid view**: Rows = tasks, columns = DAG runs (most recent right). Color cells: green=success, red=failed, yellow=running. This is Airflow-specific (per-task per-run matrix); not directly applicable to Nucleus asset model.
- **Gantt chart on run**: Shows task duration blocks on a time axis. Useful for multi-step pipelines. Defer to v0.5 (multi-step assets).
- **Calendar view for schedule**: Monthly calendar showing days when the DAG ran, colored by success/failure ratio. **Adopted**: Simplified to 7-day timeline in v0.3.
- **Log streaming**: Same SSE approach as Dagster. Click task instance → side panel with streamed log.
- **Trigger DAG button**: Red/green "Play" button with confirmation dialog (optional). Nucleus adopts without confirmation dialog (v0.1 simplicity).

**Adopted for v0.3**: Schedule 7-day timeline, trigger button (no modal).

---

## 3. Mage AI

**Source**: https://github.com/mage-ai/mage-ai

### UI patterns:
- **Split-pane pipeline builder**: Left=block list, right=code editor. Out of scope (Nucleus is Python SDK, not block-based).
- **Pipeline run list**: Clean table with status dot, pipeline name, duration, started/ended timestamps. Same approach Nucleus already uses.
- **Error block display**: When a block fails, error message shown inline in red card with full traceback. **Adopted**: Nucleus renders `fix_hint` banners instead of raw tracebacks (consistent with error-translation discipline).
- **Dark terminal output panel**: Log lines in dark monospace panel at bottom of run view. **Adopted** for run detail log view.
- **Quick execute SQL block**: Inline SQL with run button and result table. Very similar to our Query page concept. **Adopted**.

**Adopted for v0.3**: Error banner with fix_hint, dark log panel, SQL execute + result table.

---

## 4. Apache Superset — SQL Lab

**Source**: https://superset.apache.org/docs/using-superset/exploring-data/

### UI patterns:
- **SQL Lab**: Textarea editor + "Run" button (Ctrl+Enter shortcut) + result table below. Tab strip for saved queries.
- **Result table**: Fixed-height scrollable table with column headers. Truncation banner when results exceed limit.
- **Schema browser**: Left sidebar showing table names + column names. Nucleus defers schema browser to v0.4.
- **Query history**: Previous queries listed below SQL editor. Nucleus defers to v0.4 (session storage).

**Adopted for v0.3**: Ctrl+Enter shortcut, result table with truncation banner. Schema browser deferred.

---

## 5. Rill Data

**Source**: https://docs.rilldata.com/

### UI patterns:
- **Measure/dimension sidebar**: Left panel with checkboxes for metrics. Not applicable (Nucleus is pipeline-first, not dashboard-first).
- **Time grain picker**: Buttons for Day/Week/Month. Not applicable.
- **Filter chips**: Horizontal row of active filter chips (dismissible). **Adopted**: filter chips on runs + assets pages.
- **DuckDB-backed fast preview**: "Instant" feel — query results appear in <500ms with no loading spinner if fast enough. Nucleus aims for same via `/api/query` DuckDB backend.

**Adopted for v0.3**: Filter chips pattern.

---

## 6. Marquez

**Source**: https://marquezproject.github.io/marquez/

### UI patterns:
- **Lineage DAG with pan/zoom**: Force-directed graph of datasets + jobs. Nodes styled as circles (datasets) vs squares (jobs). Pan by drag, zoom by scroll. **Partially adopted**: Nucleus v0.3 makes DAG nodes clickable; full force-directed layout deferred to v0.4.
- **Dataset detail panel**: Click dataset → right panel with fields list (name, type, nullable), tags, run history, upstream/downstream links. **Adopted**: Asset detail panel in v0.3.
- **Run event timeline**: Horizontal timeline of START → COMPLETE events per job. **Defer to v0.4**.

**Adopted for v0.3**: Asset detail panel (dataset detail analog), clickable DAG nodes.

---

## 7. Marimo

**Source**: https://marimo.io/

### UI patterns:
- **Reactive cell execution**: Cells re-run automatically when upstreams change. Not applicable for pipeline UI.
- **Clean white UI with editorial typography**: Very similar to Nucleus's editorial hero approach. Validates direction.
- **File system browser**: Left sidebar with workspace files. Nucleus Workbench doesn't need this in v0.3.

---

## Summary: 10 Patterns Adopted for v0.3

| # | Pattern | Source | Implementation |
|---|---|---|---|
| 1 | **Clickable asset cards → detail slide-over** | Dagster, Marquez | `AssetDetailPanel` slide-over |
| 2 | **Materialize button with live progress** | Dagster | `handleMaterialize` in asset panel; SSE log stream |
| 3 | **Run detail slide-over with dark log panel** | Dagster, Mage | `RunDetailPanel` with SSE EventSource |
| 4 | **Status filter chips on runs table** | Dagster, Rill | Run status filter (All/Success/Failure/Running) |
| 5 | **SQL editor with Ctrl+Enter + result table** | Superset, Mage | `QueryPage` |
| 6 | **Truncation banner on query results** | Superset | "Showing first N rows" banner when `truncated: true` |
| 7 | **Error banners with actionable fix hints** | Mage, Dagster | `ErrorBanner` component consuming `fix_hint` |
| 8 | **Schedule 7-day timeline** | Airflow | `SchedulesPage` with next-runs dots |
| 9 | **⌘K command palette** | Dagster, Linear | `CommandPalette` using `/api/search` |
| 10 | **Dismissible filter input on asset list** | Rill, Dagster | Client-side filter on assets + runs pages |
