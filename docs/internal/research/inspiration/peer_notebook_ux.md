# Peer Notebook UX: Marimo, Hex, Ploomber — Inspiration Research

> **Last verified**: 2026-05-15
> **Scope**: Notebook UX + reactive Python inspiration research for Nucleus Workbench v0.3+
> **Authored by**: Nucleus Researcher (Sonnet 4.6, fallback from Gemini 3.1 Pro — recorded per AGENTS.md §11.14)
> **Primary reference**: `docs/internal/research/marimo.md` (component-level deep-dive, 2026-05-13) — read that first for Marimo integration spec. This document synthesizes cross-cutting UX patterns and adoption verdict.
> **Tier context**: Marimo is a v0.3+ Tier 1 wrap candidate (AGENTS.md §4). Hex is closed-source; UX patterns only. Ploomber is **DEFUNCT** (archived 2025-07-12; platform shut down 2025-10-31).

---

## 1. Executive Summary

**WRAP MARIMO at v0.3. Steal UX patterns from Hex for Workbench today. Ploomber is dead — ignore for adoption.**

Three-line verdict:
- **Marimo**: WRAP at v0.3. Apache-2.0, JVM-free, reactive `.py` notebooks, native DuckDB/Polars, AI-ready. The only credible Jupyter replacement in the Nucleus stack.
- **Hex**: STUDY for UX patterns. Closed-source SaaS; do not attempt to replicate the platform, but adopt 5+ UX ideas immediately in Workbench v0.2/v0.3.
- **Ploomber**: DISCARD. OSS archived 2025-07-12; Cloud platform shut down 2025-10-31. Zero adoption path.

---

## 2. Project A: Marimo

### 2.1 What Marimo Is

Marimo is a reactive Python notebook where **cells form a static DAG** via variable reference analysis. Unlike Jupyter's mutable global state, marimo cells re-execute deterministically when their inputs change. Notebooks are stored as pure `.py` files — not JSON — and can run as editors (`marimo edit`), apps (`marimo run`), scripts (`python notebook.py`), or in-browser WASM notebooks.

- **GitHub**: https://github.com/marimo-team/marimo
- **PyPI**: https://pypi.org/project/marimo/
- **Docs**: https://docs.marimo.io/
- **License**: Apache-2.0
- **Version verified**: 0.23.6 (2026-05-11) — not pinned in Nucleus yet
- **JVM-free**: YES — pure Python kernel + bundled React/TypeScript frontend
- **Affiliation**: NumFOCUS affiliated; founded at Stanford's SLAC
- **Community signal**: 2.2M+ monthly PyPI downloads; HN posts show mass Jupyter → Marimo migration (https://news.ycombinator.com/item?id=39552882)

### 2.2 Reactive Dataflow Engine

**Core mechanic**: marimo performs static reference analysis on cell code. If cell B references variable `df` defined in cell A, cell B re-executes whenever cell A runs. This is deterministic — no hidden state, no out-of-order surprises.

Key properties (per https://docs.marimo.io/guides/reactivity/):
- Execution order is determined by **data dependencies, not cell order on page**. Cells can be physically arranged out of order.
- **Multi-column layout** is possible precisely because execution order comes from the DAG, not visual position.
- **Limitation**: mutation is not tracked. `df["new_col"] = value` does not trigger downstream cells. Side effects are invisible to the reactive engine.
- Cycle detection is static; circular dependencies are an error at parse time (exact exception class `NEEDS VERIFICATION` — see §8).

**Nucleus implication**: marimo's reactive DAG is per-notebook, in-process, dev-time only. Nucleus's asset graph is global, persistent, Iceberg-backed, Dagster-orchestrated. **These must never be merged.** The `@nucleus.asset` decorator is the boundary. See `docs/internal/research/marimo.md` §2 + §5.3.

### 2.3 Git-Friendly Format

Marimo notebooks are stored as `.py` files, not `.ipynb` JSON blobs:

```python
import marimo
app = marimo.App()

@app.cell
def _():
    import polars as pl
    df = pl.read_csv("data.csv")
    return (df,)

@app.cell
def _(df):
    return (df.head(),)
```

Benefits vs Jupyter (per https://marimo.io/features/vs-jupyter-alternative):
- Standard `git diff` works — no JSON diffs of output arrays
- No cell output stored in version control (clean commits)
- `python notebook.py` runs the notebook as a script without any notebook runtime
- Works with standard Python tooling: ruff, mypy, pytest

**Nucleus adoption**: notebooks in a `notebooks/` directory (per `nucleus_project_anatomy.md`) are plain `.py`, importable, ruff-formatted. No `.ipynb` noise in version control.

### 2.4 UI Elements and Interactive Widgets

`mo.ui.*` namespace (per https://docs.marimo.io/api/inputs/ — requires verification for exact signatures at 0.23.6):

| Widget | Class | Notes |
|---|---|---|
| Slider | `mo.ui.slider(start, stop, value, step)` | `mo.ui.slider.from_series(series)` for Polars/Pandas series |
| Dropdown | `mo.ui.dropdown(options, value)` | `from_series` variant |
| Text input | `mo.ui.text(value, label)` | |
| Button | `mo.ui.button(label, on_click)` | |
| Interactive table | `mo.ui.table(df, selection="multi")` | Returns selection as `df` in `.value` |
| DataFrame transformer | `mo.ui.dataframe(df)` | No-code filter/groupby/agg GUI → emits code |
| File upload | `mo.ui.file(filetypes, multiple)` | |
| Array of inputs | `mo.ui.array([...])` | Compose multiple inputs |
| Altair chart (selectable) | `mo.ui.altair_chart(chart)` | Selection feeds back to Python as DataFrame |
| Plotly chart (selectable) | `mo.ui.plotly(fig)` | Same pattern |

**Widget reactivity model**: every `mo.ui.*` widget exposes a `.value` property. When a user interacts with the widget, `.value` updates and all cells referencing it re-execute. This makes parameterized apps trivially buildable without callbacks.

**Nucleus adoption boundary**: `mo.ui.*` is dev-time only. At `marimo run` (app mode), widgets become interactive inputs. Do not expose through `ctx` SDK at v0.3 — they are presentation-layer concerns.

### 2.5 `marimo edit` vs `marimo run` Modes

| Mode | Invocation | Runtime semantics | Who uses it |
|---|---|---|---|
| **Edit** | `marimo edit notebook.py` | Full IDE; reactive re-execution on every change; all panels visible | Developer iterating |
| **Run** | `marimo run notebook.py` | App mode; code hidden; only outputs + widgets visible; no edit | Stakeholder viewing result |
| **Script** | `python notebook.py` | Sequential execution, no UI; `mo.app_meta().mode == "script"` | CI, cron, `nucleus run` |
| **WASM** | `marimo export html-wasm` / molab | Browser-only; Pyodide; no server | Sharing/demos |

`nucleus notebook run <name>` wraps `python notebook.py`. `nucleus notebook edit <name>` wraps `marimo edit`. `nucleus notebook export <name> --as-app` is the v0.3+ CLI surface — not yet implemented.

Docs: https://docs.marimo.io/guides/apps/ · https://docs.marimo.io/guides/scripts/

### 2.6 WASM Mode

WASM notebooks execute entirely in browser via [Pyodide](https://pyodide.org/). No server required.

Key facts (per https://docs.marimo.io/guides/wasm/):
- DuckDB, Polars, NumPy, scikit-learn all supported in Pyodide
- 2 GB memory limit
- No threading/multiprocessing (Pyodide limitation — may improve: https://github.com/pyodide/pyodide/issues/237)
- No PDB debugger
- `molab` (https://molab.marimo.io) is Marimo's free hosted WASM service; appending `/wasm` to a GitHub URL creates a live preview
- `marimo export html-wasm notebook.py` produces a static HTML with embedded WASM

**Nucleus position**: WASM is **out of scope for v0.3**. No Dagster, no Iceberg writes, no MinIO inside WASM. Potential v0.5+ "share a data product preview as a link" UX bet — but zero LOC spent on it today.

### 2.7 AI Integration

Marimo self-describes as "an AI-native editor" (per https://docs.marimo.io/guides/editor_features/ai_completion/) — **note: we use "AI-ready" per ADR-002; Marimo uses "AI-native" internally; do not copy that framing**.

Capabilities verified at docs.marimo.io 2026-05-15:

| Feature | How | Scope |
|---|---|---|
| **AI cell generation** | Prompt box at bottom; generates new cells | All LLM providers |
| **Cell refactoring** | `Ctrl/Cmd-Shift-E` on existing cell | All providers |
| **Notebook generation** | `marimo new "PROMPT"` CLI | All providers |
| **Variable context injection** | `@df` in prompt = schema injected into context | Critical — AI knows column names |
| **Chat panel** | Left sidebar; Manual / Ask / Agent modes | Agent mode (beta): can edit + run cells |
| **GitHub Copilot** | Tab completion (inline) | Via Node.js + Copilot auth |
| **Windsurf Copilot** | Tab completion alternative | Via Codeium API |
| **Custom copilot** | Any OpenAI-compatible endpoint | Local Ollama, etc. |
| **External agents** | Claude Code, Codex, Gemini CLI (experimental) | Via `agents` guide |

Supported LLM providers: OpenAI, Anthropic, AWS Bedrock, Google AI, GitHub, Ollama, any OpenAI-compatible (https://docs.marimo.io/guides/configuration/llm_providers/).

**Nucleus Copilot integration (v0.5+)**: When Nucleus AI Copilot lands (v0.5, per architecture §8.2), the `@df` variable injection pattern is the reference UX. Nucleus context = asset catalog schema + run history + lineage graph → inject all into AI context the same way Marimo injects `@df`. This is the "AI-ready by design" differentiation bet.

### 2.8 Dependency Conflicts (Pre-existing; see marimo.md §7)

Two blocking conflicts before `pip install marimo[sql]` can resolve:

| Package | Nucleus pin | Marimo 0.23.6 requires | Action |
|---|---|---|---|
| `msgspec` | `0.18.6` | `>=0.20.0` | Upgrade PR before v0.3 |
| `sqlglot` | `26.0.0` | `>=26.8.0[c]` (sql extra) | Upgrade PR before v0.3 |
| `opentelemetry-api` | `1.29.0` | `~=1.28.0` (otel extra only) | Avoid `marimo[otel]` — we own OTel |

Full conflict table in `docs/internal/research/marimo.md` §7. ADR sequencing: (1) msgspec upgrade, (2) sqlglot upgrade, (3) Marimo integration ADR + adapter.

### 2.9 How to Wrap into Nucleus Workbench (v0.3 Design)

**Option A (recommended)**: Shell-out model — `nucleus notebook edit <name>` starts `marimo edit` as a subprocess, opening in separate browser tab. Workbench remains the primary IDE; Marimo is launched as a satellite.

**Option B**: Iframe embed — Workbench hosts an `<iframe src="http://localhost:2718/...">` pointing at a locally running `marimo edit` server. Complex CORS handling; Marimo's WebSocket transport would need cross-origin support. **NOT recommended at v0.3** — over-engineered, brittle.

**Option C**: WASM embed — `marimo export html-wasm notebook.py` → static HTML served from Workbench. Loses server-side Dagster/DuckDB/MinIO access. Only viable for "preview" mode at v0.5+.

**Verdict**: Option A at v0.3. Zero iframe complexity. Nucleus Workbench launches Marimo; user switches tab. The adapter (`experience/marimo_adapter.py`, ≤300 LOC) wraps the `marimo` CLI subprocess. The Workbench shows a "Open in Notebook" button on any asset, launching `nucleus notebook edit <name>`.

---

## 3. Project B: Hex

> **Status**: Closed-source SaaS. All findings from public docs and pricing page only. Claims marked `[NEEDS VERIFICATION]` where blog/docs are the only source.
> **Why analyze it**: Hex is the gold-standard for "what great collaborative data notebook UX looks like." We steal UX patterns; we do not replicate the platform.
> **Official docs**: https://learn.hex.tech/docs/ · **Pricing**: https://hex.tech/pricing

### 3.1 What Hex Is

Hex is a hosted collaborative data notebook product. The core unit is a **Project** — a mix of SQL, Python, visualization, and no-code cells that can be published as an **App**. Think "Jupyter for teams, with a built-in app builder and real-time collaboration."

- **Model**: Closed-source SaaS (multi-tenant). No self-hosted option on standard plans.
- **Pricing (2026)**: Community (free, 5 projects, trial Notebook Agent), Professional ($36/editor/month), Team ($75/editor/month, collaborative features), Enterprise (custom, OIDC SSO).
- **Underlying compute**: Hex runs Python/SQL on managed kernels (not disclosed internally). Python uses standard CPython environment. SQL uses direct warehouse connections (Snowflake, BigQuery, Redshift, etc.) or in-process DuckDB for dataframe SQL.
- **Community tier**: Free, 5 projects, up to 5 published apps, Small compute (4 GB / 0.5 CPU). [Source: https://hex.tech/pricing]

### 3.2 Cell Types: The Mix-and-Match Model

Hex extends the Jupyter model with first-class non-code cells:

| Cell type | What it does | Nucleus analogue |
|---|---|---|
| **Python cell** | Standard Python with pandas/polars | `@nucleus.asset` (with `@app.cell` decoration in Marimo) |
| **SQL cell** | Warehouse SQL or DuckDB dataframe SQL | `ctx.sql(...)` |
| **Chart cell** | No-code drag-drop chart builder (bar, line, scatter, map, table) | Not in Workbench yet |
| **Transform cell** | UI-driven reshape/filter/pivot — no code | `mo.ui.dataframe(df)` equivalent |
| **Input parameter cell** | Dropdowns, sliders, date pickers → feed into SQL/Python via Jinja | `mo.ui.*` equivalent |
| **Single value cell** | KPI / metric display with Jinja-dynamic text | Not in Workbench yet |
| **Markdown/Text cell** | Docs + Jinja variable interpolation | Markdown in Marimo cells |
| **Writeback cell** | Write dataframe rows back to warehouse table | Out of scope |

All cells are wired into a reactive DAG (per https://learn.hex.tech/docs/explore-data/projects/project-execution/execution-model). Hex infers cell linkages automatically from variable references — no user definition needed.

### 3.3 "Magic" SQL → DataFrame Transition

This is Hex's most imitated pattern. In Hex:

1. User writes a SQL cell against a data warehouse or uploaded CSV.
2. Result is **automatically assigned to a named variable** (e.g., `df_1`).
3. Next Python cell references `df_1` as a **pandas DataFrame**.
4. Next SQL cell references `df_1` as a **table name in DuckDB**.

The result type (`dataframe` = green pill, `query` = purple pill) controls how data flows:
- **Dataframe mode**: full results streamed to Hex; accessible in Python as pandas.
- **Query mode**: only 1k-row preview fetched; downstream warehouse SQL cells use it as a CTE. Hex auto-compiles chained warehouse SQL into a single query. [Source: https://learn.hex.tech/docs/explore-data/cells/sql-cells/sql-cells-introduction]

**Nucleus Workbench steal**: The `ctx.sql(...)` return already is a Polars DataFrame. What's missing is the **visual "pill" that shows the result variable name** beneath the SQL cell and tracks where it flows. This is a pure frontend concern — zero new API surface. Add to Workbench SQL editor in v0.2 or v0.3.

**Jinja in SQL**: Hex uses `{{ variable }}` in SQL cells to inject Python/input values as prepared statements (https://learn.hex.tech/docs/explore-data/cells/using-jinja). This is **identical syntax** to Nucleus's `ctx.sql` Jinja `{{ ref('asset') }}`. The critical difference: Hex's Jinja variables are Python runtime values; Nucleus's `{{ ref(...) }}` is a catalog lookup. Workbench must clearly label the two modes to avoid user confusion.

### 3.4 "Logic vs Display" Split — The App Builder Pattern

Hex separates authoring from publishing:

- **Notebook view** = authoring mode (all cells visible, code editable, reactive execution on change)
- **App builder** = layout mode (drag-and-drop cells into rows/columns/tabs, choose Source/Output/Both display)
- **Published App** = viewer mode (Can View App permission; no code visible by default)

Key App builder facts (per https://learn.hex.tech/docs/build-apps/app-builder):
- First navigate to App builder → Hex **auto-generates** a default layout from all cells
- Drag from the Outline panel to place cells in any row/column
- Multiple **App tabs** for dashboard-like experience
- **Theme**: Light / Dark / User preference (inherited from system settings)
- Custom themes on Team/Enterprise plans
- Auto-generated Table of Contents from markdown headers
- Element display options: Source-only, Output-only, Source+Output

**Nucleus Workbench steal**: The "auto-generate default app layout" pattern is directly stealable. When a user runs `marimo run notebook.py`, Marimo does exactly this — outputs concatenated, code hidden. We can surface this as `nucleus notebook preview <name>` in the CLI and a "App Preview" button in Workbench v0.3.

### 3.5 Real-Time Collaboration Model

Hex is multi-user simultaneous editing (the docs mention "Can Edit or higher permissions" for simultaneous users — https://learn.hex.tech/docs/collaborate/sharing-and-permissions/project-sharing). Specific multiplayer engine not disclosed publicly. The permission tiers are:

| Role | Access |
|---|---|
| Full Access | Edit, rename, delete, manage sharing |
| Can Edit | Edit notebook + app; share with others |
| Can Explore | View notebook + app; explore published app |
| Can View App | Published app only (no notebook) |

**Nucleus position**: Real-time collaboration is v2.0+ (out of scope for v0.3 startup beachhead). However, the **permission model** is worth studying for the Workbench v0.3 sharing design. Nucleus v0.3 will have OIDC roles — the Can Edit / Can View App dichotomy maps well to "author" vs "stakeholder" roles.

### 3.6 Underlying Compute

Hex uses DuckDB for **dataframe SQL** (in-process) and direct warehouse connections for warehouse SQL (Snowflake, BigQuery, Redshift, Postgres, etc.) (per https://learn.hex.tech/docs/explore-data/cells/sql-cells/sql-cells-introduction §Dataframe).

Compute profiles (per https://hex.tech/pricing): XS (2GB/0.25CPU) → 4XL (128GB/16CPU) → GPU (A10G, L4). Free includes up to Medium (8GB/1CPU).

**Nucleus comparison**: Nucleus uses DuckDB embedded (no network round-trip) + MinIO/S3 for storage. For the 100GB-5TB startup beachhead, this is actually *more* performant than Hex's hosted compute for local iteration. This is a differentiation claim worth surfacing in positioning.

### 3.7 Notebook Agent (AI, 2025)

Hex launched Notebook Agent (August 2025) and expanded it in Act II (December 2025) (per https://learn.hex.tech/changelog/2025-08-27 · https://learn.hex.tech/changelog/2025-12-16). Capabilities:

- Plans analyses, creates SQL/Python cells, visualizes data, generates summaries
- Creates input parameters and single value cells
- Auto-organizes cells into sections
- Deletes cells, cleans up logic
- Graph-aware context (understands DAG when generating)
- Available on Professional+ plans (trial on Community)
- Used by Figma, Ramp, Notion per their changelog [NEEDS VERIFICATION — changelog claim, not independently confirmed]

**Nucleus Copilot parallel**: The Hex Notebook Agent is the closed-source proof-of-concept for what Nucleus AI Copilot (v0.5+) should do. Key insight: **graph-aware context** is the differentiator. A generic LLM generates plausible cells; a graph-aware agent generates cells that correctly reference upstream outputs. For Nucleus this means: Copilot must inject the asset catalog + lineage graph into context, not just the current cell text.

---

## 4. Project C: Ploomber

> **Status**: DEFUNCT. OSS archived 2025-07-12. Ploomber Cloud shut down 2025-10-31. **No adoption path.** Analysis retained for historical context only.

### 4.1 What Ploomber Was

Ploomber was a Python pipeline framework using a declarative `pipeline.yaml` file. Pipelines were DAGs of tasks — `NotebookRunner`, `ScriptRunner`, `SQLDumpTask`, etc. — with upstream/downstream dependencies inferred from a shared `product` object.

- **GitHub**: https://github.com/ploomber/ploomber (ARCHIVED — read-only since 2025-07-12)
- **PyPI**: ploomber 0.23.3 (last stable, still installable but unmaintained)
- **License**: Apache-2.0
- **Monthly downloads**: ~6,000 (niche; never achieved mass adoption)
- **Last push**: 2025-05-29

### 4.2 Pipeline YAML Approach

```yaml
# pipeline.yaml
meta:
  extract_upstream: True
  extract_product: False

tasks:
  - source: notebooks/clean.ipynb
    name: clean
    product:
      nb: output/clean.html
      data: output/clean.parquet

  - source: notebooks/analyze.ipynb
    name: analyze
    params:
      some_param: '{{some_param}}'
    product:
      nb: output/analyze.html
```

```yaml
# env.yaml
some_param: default_value
```

**Parametrization**: `{{placeholder}}` syntax (double curly braces, like Jinja) + `env.yaml` overrides. Parameters can be overridden at CLI: `ploomber build --env--some_param override_value`. (https://docs.ploomber.io/en/stable/user-guide/parametrized.html)

**NotebookRunner** wraps papermill under the hood: injects a tagged `parameters` cell, executes notebook, produces HTML/IPYNB output. (https://docs.ploomber.io/en/latest/api/_modules/tasks/ploomber.tasks.NotebookRunner.html)

**ScriptRunner** is similar but runs `.py` scripts without generating notebook outputs.

### 4.3 Why Ploomber Failed (Lessons for Nucleus)

The archival note and shutdown confirm a pattern visible in retrospect:
1. **Poor notebook DX**: `pipeline.yaml` + `upstream` cell injection was unfamiliar to most Jupyter users. The cognitive model of "inject upstream as a special cell" was confusing.
2. **Papermill dependency** for `NotebookRunner` added a heavyweight dep for a questionable UX.
3. **Split between OSS and Cloud** was never resolved — OSS users didn't convert; Cloud never reached critical mass.
4. **No reactivity**: pipeline.yaml DAG re-ran entire notebooks (via papermill), not individual cells. For iteration, this was slower than just running cells manually.

**Nucleus lesson**: The "parametrize notebooks and run as pipelines" use case is real, but the solution is NOT a separate YAML file. Nucleus's answer is `@nucleus.asset` in a `.py` Marimo notebook — same file, same language, zero YAML, cells that re-execute reactively during dev and full materializations during prod runs.

### 4.4 Ploomber Cloud Shutdown — Lessons for Nucleus

Ploomber Cloud's shutdown blog post (https://ploomber.io/blog/platform-shut-down/) confirms:
- Effective October 31, 2025: all running apps shut down
- Community users lost deploy/redeploy as of announcement
- Subscriptions not auto-cancelled (user must manually cancel)
- Dockerfiles open-sourced for migration

**Nucleus lesson**: Never gate v0.3+ features on a Cloud component without a local-first fallback. Ploomber's Cloud-only deployment path left users stranded on shutdown. Nucleus's architecture — local-first by design, graduating to Cloud — avoids this failure mode entirely.

### 4.5 Ploomber Marimo Integration (Historical)

A [marimo pull request](https://github.com/marimo-team/marimo/pull/8249) titled "docs: removes ploomber deployment" confirms Marimo itself removed its Ploomber integration as the platform shut down. This is the definitive signal: **Ploomber is not a reference architecture for Nucleus, and adopting any part of it would require maintaining a dead dependency.**

---

## 5. Cross-Cutting Analysis

### 5.1 Pattern Comparison Matrix

| Pattern | Marimo | Hex | Ploomber |
|---|---|---|---|
| Reactive DAG execution | ✅ (cell-level) | ✅ (cell-level) | ❌ (file-level via papermill) |
| Git-friendly storage | ✅ `.py` | ❌ (hosted, git export optional) | ❌ `.ipynb` |
| Notebook → App in one click | ✅ `marimo run` | ✅ App builder | ❌ |
| SQL → DataFrame "magic" | ✅ `mo.sql` → Polars | ✅ SQL cell → pandas | ❌ |
| Jinja in SQL | ⚠️ (f-string collision — see marimo.md §5.2) | ✅ (prepared statements) | ❌ |
| Interactive widgets | ✅ `mo.ui.*` | ✅ Input parameter cells | ❌ |
| Interactive DataFrame explorer | ✅ `mo.ui.dataframe` + panels | ✅ Transform cells | ❌ |
| AI code generation | ✅ (variable context, chat panel) | ✅ Notebook Agent (2025) | ❌ |
| Self-hosted / local | ✅ | ❌ (SaaS only) | ✅ (archived) |
| Open-source | ✅ Apache-2.0 | ❌ | ✅ Apache-2.0 (unmaintained) |
| DuckDB native | ✅ | ✅ (dataframe SQL) | ❌ |
| Polars support | ✅ first-class | ⚠️ (pandas-default) | ❌ |
| WASM / browser execution | ✅ | ❌ | ❌ |
| Command palette (⌘K) | ✅ | ✅ | ❌ |
| Dependency graph visualization | ✅ minimap + graph view | ✅ Graph view | ❌ |
| Real-time collaboration | ❌ | ✅ | ❌ |
| Current maintenance status | ✅ Active | ✅ Active (SaaS) | ❌ DEAD |

### 5.2 Notebook → Production Mapping

All three projects attempt the "notebooks in production" promise. The quality of the answer varies dramatically:

| Project | Notebook → Prod mechanism | Quality |
|---|---|---|
| **Marimo** | `python notebook.py` runs sequentially; `@nucleus.asset` decorator promotes cell to Dagster job | ✅ Clean, composable |
| **Hex** | Scheduled runs (Team plan+); triggered via Airflow/Dagster/dbt integration | ✅ Works well for warehouse-centric teams |
| **Ploomber** | `ploomber build` via papermill + `pipeline.yaml` DAG | ❌ Confusing UX, now dead |

Nucleus's answer is superior to Ploomber and peer to Hex: a Marimo `.py` notebook with `@nucleus.asset` cells is a first-class Dagster materialization target with no extra YAML, no papermill, and full reactivity during dev.

---

## 6. Adoption Shortlist for Workbench v0.3+

### 6.1 Priority 1: Add Notebook Tab — WRAP MARIMO

**Decision: WRAP MARIMO at v0.3. Apply the 8-question gate:**

| Gate | Answer |
|---|---|
| 1. Maps to architectural layer? | ✅ L4 Experience — `nucleus notebook` CLI + `experience/marimo_adapter.py` |
| 2. Serves <30-minute beachhead? | ⚠️ NEUTRAL — notebook is exploratory, not part of `git clone` → first Iceberg table. Does not *help* the metric but does not *harm* it if correctly scoped. |
| 3. Wrap possible? | ✅ YES — `nucleus notebook edit <name>` shells out to `marimo edit`. ~300 LOC adapter. |
| 4. Preserves no-JVM? | ✅ YES — Marimo is pure Python + React/TypeScript. |
| 5. Preserves local-identical-to-prod? | ✅ YES — `marimo edit` and `python notebook.py` use same Python env. |
| 6. Stays within 30K LOC budget? | ✅ ~300 LOC adapter is well within budget. |
| 7. Triggered by empirical telemetry? | ✅ YES — 2.2M+ monthly downloads; HN thread shows active Jupyter migration; Stanford SLAC origin gives scientific credibility; community asks for notebooks alongside CLI. |
| 8. Required for v0.1/v0.2, or can defer? | ✅ DEFER to v0.3. v0.1 is CLI Hello World; v0.2 is Workbench Monaco editor + asset graph. Marimo at v0.3 is correctly sequenced. |

**Verdict: WRAP at v0.3, starting with the 300-LOC shell-out adapter. Do NOT build a custom notebook runtime (AGENTS.md §4). Do NOT embed via iframe at v0.3 (over-engineered). Do NOT add reactive engine semantics to Nucleus's asset graph.**

**LOC budget impact**: `experience/marimo_adapter.py` ≤ 300 LOC. Dependency conflicts (msgspec, sqlglot upgrades) are prerequisite PRs with minimal Nucleus LOC delta.

### 6.2 Priority 2: Reactive Dataflow in Workbench

**Decision: DEFER to v0.3 with Marimo wrapping. Do NOT build reactive DAG in Workbench.**

Hex's reactive execution model (cells re-execute on dependency change) is one of the most compelling DX features. However:
- Building a custom reactive engine = ~2,000+ LOC + ongoing maintenance = violates AGENTS.md §4 + LOC budget
- Marimo wrapping gives us this for free in the notebook surface
- For the Workbench Monaco editor (assets, not notebooks), reactive re-execution would mean re-materializing Iceberg snapshots on every save — wrong semantics

**Acceptable scope**: Workbench v0.3 can show a visual dependency graph of assets (already planned per architecture §8) with stale-cell highlighting. This is read-only lineage visualization, not reactive re-execution. ~200 LOC frontend, zero backend.

### 6.3 Priority 3: "Notebook as App" Export

**Decision: DEFER to v0.3+ via `nucleus notebook preview <name>` CLI.**

`marimo run notebook.py` already provides this. Nucleus wrapper: `nucleus notebook preview <name>` launches `marimo run <path>`. The Workbench "App Preview" button (v0.3) calls this. Total CLI wiring: ~50 LOC.

**Future consideration (v0.5+)**: `nucleus workbench export notebook_name --as-app` producing a WASM HTML for sharing without a server. This is the "share a data product preview as a link" UX bet. Zero LOC today.

### 6.4 Priority 4: No-Code Transform Cells

**Decision: DEFER to v0.3+ via `mo.ui.dataframe`.**

Hex's Transform cells (no-code pivot/filter/groupby) are excellent for stakeholders who don't write Python. Marimo's `mo.ui.dataframe(df)` provides the same capability — interactive GUI that emits code. Nucleus gets this for free by wrapping Marimo; no Workbench-specific implementation required.

### 6.5 Priority 5: Graph-Aware AI Copilot Context

**Decision: ARCHITECT for v0.5+, zero code today.**

Both Hex (Notebook Agent, 2025) and Marimo (variable context injection via `@df`) demonstrate that AI code generation quality dramatically improves when the AI has access to schema + runtime values. Nucleus's differentiator: inject the **asset catalog + lineage graph + last snapshot schema** into AI context, not just in-memory variables. Document this design intent in the v0.5 ADR placeholder but write zero code today.

---

## 7. Notebook Adoption Verdict: Decision Matrix

| Option | WRAP MARIMO | BUILD CUSTOM | DEFER (no notebook) |
|---|---|---|---|
| **LOC cost** | ~300 (adapter) + 2 upgrade PRs | 2,000-5,000+ | 0 |
| **JVM-free** | ✅ | ✅ | ✅ |
| **30K LOC budget** | ✅ | ❌ RISK | ✅ |
| **30-min beachhead impact** | NEUTRAL (scoped to v0.3) | NEGATIVE (slows v0.1) | NEUTRAL |
| **Reactivity** | ✅ Free via Marimo | ✅ But expensive | ❌ |
| **Git-friendly `.py`** | ✅ Free | Could achieve | ❌ |
| **AI integration** | ✅ Marimo provides | Must build | ❌ |
| **Swap cost (if Marimo dies)** | ~500 LOC → Jupyter | N/A | 0 (nothing to swap) |
| **Composability** | ✅ `experience/notebook_adapter.py` Protocol | ❌ No swap | ✅ |
| **Risk** | LOW | HIGH | MEDIUM (deferred demand) |

**Verdict: WRAP MARIMO at v0.3.** There is no case for building a custom notebook runtime under any interpretation of AGENTS.md §4, the LOC budget, or the 8-question gate. The only real choice is WRAP vs DEFER. WRAP wins because Marimo satisfies demand at 300 LOC; DEFER accumulates user demand and technical debt while offering nothing.

**ADR required**: `docs/decisions/ADR-NNN-marimo-v03-notebooks.md`. Prerequisites: msgspec upgrade ADR, sqlglot upgrade ADR.

---

## 8. UX Patterns to Adopt in Workbench Today (v0.2/v0.3)

These UX patterns are **pure frontend concerns** that do not require adding Marimo as a dependency or wrapping any new OSS. They can be adopted in the Workbench React frontend.

### Pattern 1: Command Palette (⌘K / Ctrl+K)

**Source**: Both Marimo (https://docs.marimo.io/guides/editor_features/overview/#command-palette) and Hex use `⌘K` for command palette. This is also Cursor's shortcut — **our users already know it.**

**Adopt**: Workbench needs `⌘K` command palette that surfaces: Run asset, Open notebook, Query asset, View lineage, Show run history, Open settings. No server API required for most commands — pure frontend routing.

**Nucleus value**: Familiar UX from proven giants (Pillar #4). Every Cursor user already has this muscle memory.

**Effort**: ~200 LOC React; use `cmdk` library (https://cmdk.paco.me/) or similar.

### Pattern 2: Interactive DataFrame Explorer as First-Class Citizen

**Source**: Marimo's `mo.ui.dataframe` — no-code GUI for filter/groupby/sort/agg that emits Python code (https://docs.marimo.io/guides/working_with_data/dataframes/). Hex's Transform cells. Both show that data exploration should require zero Python for basic operations.

**Adopt in Workbench**: When a user views an asset's last snapshot in Workbench (already planned), render it in an interactive table with:
- Column sort
- Column filter (type-ahead)
- Row count in header
- "Copy as Polars filter" button (generates `df.filter(pl.col("x") == "y")` — users can paste into notebook)
- Export as CSV

**Nucleus value**: This is the single highest-ROI DX improvement for non-technical stakeholders. Asset owner runs materialization; stakeholder explores in Workbench without opening a notebook or writing Python.

**Effort**: ~300 LOC React + existing API (query endpoint already returns Arrow/JSON); use AG Grid or TanStack Table.

### Pattern 3: SQL Result Variable "Pill" + Dataflow Visibility

**Source**: Hex's result variable pills (green = DataFrame, purple = Query object) beneath each SQL cell; clicking shows where the variable is used downstream. Marimo's Variables panel + Dependency minimap.

**Adopt in Workbench SQL editor (v0.3)**: Below each `ctx.sql(...)` result block, show:
- The Polars DataFrame shape (N rows × M cols)
- The variable name the result was assigned to (from Python code AST)
- A small lineage indicator: which asset(s) reference this query result

**Nucleus value**: Matches Hex's proven UX pattern; reinforces Nucleus's "lineage by default" positioning. Pure frontend with existing Workbench lineage data.

**Effort**: ~150 LOC React + existing lineage API.

### Pattern 4: Schema Browser in SQL Editor Sidebar

**Source**: Hex's Data sources tab shows connected warehouse schemas; clicking a table auto-generates a `SELECT * FROM table LIMIT 100` query. Marimo shows connected catalogs in its data sources panel.

**Adopt in Workbench SQL editor**: Left sidebar "Assets" panel shows:
- All materialized assets in the Nucleus catalog
- For each: schema (column names + types from last snapshot metadata)
- Click column name → inserts `asset_name.column_name` at cursor
- Double-click asset → inserts `SELECT * FROM {{ ref('asset_name') }} LIMIT 100`

**Nucleus value**: This is the `ctx.sql` DX unlock — users discover the catalog through the UI instead of memorizing asset names. Directly serves the <30-min beachhead metric (user doesn't need to know catalog API).

**Effort**: ~400 LOC React + existing catalog API (already available in Workbench).

### Pattern 5: "Notebook Mode" Keyboard Shortcuts (Command Mode)

**Source**: Marimo's Command Mode (Esc to enter, then `a`/`b` for cells above/below, `c`/`v` for copy/paste, `dd` for delete). (https://docs.marimo.io/guides/editor_features/overview/#command-mode). Jupyter's same conventions.

**Adopt in Workbench SQL editor**: When users are authoring SQL assets in the Monaco editor, support:
- `Esc` → command mode for the asset editor
- `⌘+Enter` / `Ctrl+Enter` → Run query (already exists)
- `Shift+Enter` → Run query + move to next cell
- `⌘+Shift+H` → Show keyboard shortcut help modal

**Nucleus value**: Users already have this muscle memory from Jupyter + Hex. Zero learning curve (Pillar #4).

---

## 9. Open Questions for Founder

1. **v0.3 sequencing**: Should Marimo integration land in v0.3 alongside dlt (v0.3 connectors) and Lakekeeper (v0.3 catalog), or should it be a separate v0.3+ patch once Workbench is validated? The msgspec + sqlglot upgrade PRs are prerequisites either way.

2. **"Notebook as App" positioning**: Marimo `run` mode turns a notebook into an app. This overlaps with Workbench's Workbench tab. Should we position Marimo notebooks as "exploration layer" (separate from Workbench apps), or eventually unify them (notebook IS a Workbench app)? The Hex model (one product, two views) suggests unification. The Nucleus model suggests separation (Workbench = asset authoring; Marimo = ad-hoc exploration). Which direction?

3. **`⌘K` command palette priority**: Given the "work faster" directive, is implementing the Workbench command palette (Pattern 1 above) a v0.2 quick win before the Marimo v0.3 work begins? Estimated 3-day frontend task.

4. **Schema browser scope**: Should the Workbench schema browser (Pattern 4) show **all catalog assets** or **only materialized snapshots**? The distinction matters for users who have defined assets that have never been run.

5. **Hex collaboration model reference**: When Nucleus Workbench adds sharing (v0.3+ with OIDC), should we adopt Hex's 4-tier model (Full Access / Can Edit / Can Explore / Can View App) or a simpler 2-tier (Editor / Viewer)? OIDC delegation (per v4.1 §6.6) handles authentication; Nucleus needs to define the authorization model.

---

## 10. NEEDS VERIFICATION Items

1. **Marimo reactive-cycle exception class**: `docs/internal/research/marimo.md` §5.4 flags `NucleusInvalidNotebookDefinition` as unverified. Must read `marimo/_runtime/runtime.py` at v0.3 development time and confirm before writing error translation handler. [Docs URL: https://github.com/marimo-team/marimo/blob/main/marimo/_runtime/runtime.py]

2. **`mo.sql` engine kwarg signature**: Whether `mo.sql(query, engine=conn)` is a supported kwarg or if engine discovery is cell-scope only at v0.23.6. See marimo.md §4 — `# NEEDS VERIFICATION` note on `mo.sql`. [URL: https://docs.marimo.io/guides/working_with_data/sql/]

3. **Marimo 0.23.x breaking changes since 2026-05-13**: The existing research is 2 days old. Marimo ships frequently (0.23.5 and 0.23.6 both had breaking changes per release notes). Re-verify `msgspec` and `sqlglot` conflict table before opening upgrade PRs. [URL: https://github.com/marimo-team/marimo/releases]

4. **Hex Notebook Agent team adoption claims**: The December 2025 changelog claims "used by thousands of teams including Figma, Ramp, and Notion" — stated in Hex's own changelog, not independently confirmed. Useful as signal only. [NEEDS VERIFICATION — independent source not found]

5. **Ploomber Cloud subscription billing after shutdown**: Blog says subscriptions are NOT auto-cancelled. Any Nucleus users currently paying for Ploomber Cloud should be warned to cancel manually. [Source: https://ploomber.io/blog/platform-shut-down/]

---

## 11. References

All official URLs cited in this report:

**Marimo**
- Main docs: https://docs.marimo.io/
- Getting started: https://docs.marimo.io/getting_started/
- Reactivity: https://docs.marimo.io/guides/reactivity/
- Editor overview: https://docs.marimo.io/guides/editor_features/overview/
- AI completion: https://docs.marimo.io/guides/editor_features/ai_completion/
- Dataflow: https://docs.marimo.io/guides/editor_features/dataflow/
- Apps / marimo run: https://docs.marimo.io/guides/apps/
- WASM: https://docs.marimo.io/guides/wasm/
- Dataframes: https://docs.marimo.io/guides/working_with_data/dataframes/
- SQL: https://docs.marimo.io/guides/working_with_data/sql/
- Scripts: https://docs.marimo.io/guides/scripts/
- LLM providers: https://docs.marimo.io/guides/configuration/llm_providers/
- App API: https://docs.marimo.io/api/app/
- Control flow: https://docs.marimo.io/api/control_flow/
- vs Jupyter: https://marimo.io/features/vs-jupyter-alternative
- GitHub: https://github.com/marimo-team/marimo
- Releases: https://github.com/marimo-team/marimo/releases
- PyPI: https://pypi.org/project/marimo/
- molab: https://molab.marimo.io
- HN thread: https://news.ycombinator.com/item?id=39552882
- Marimo SLAC → HN: https://news.ycombinator.com/item?id=44332796
- Marimo Polars example: https://github.com/marimo-team/marimo/blob/main/examples/third_party/polars/polars_example.py

**Hex**
- Docs home: https://learn.hex.tech/docs/
- Pricing: https://hex.tech/pricing
- Develop notebook: https://learn.hex.tech/docs/explore-data/notebook-view/develop-your-notebook
- Execution model: https://learn.hex.tech/docs/explore-data/projects/project-execution/execution-model
- SQL cells intro: https://learn.hex.tech/docs/explore-data/cells/sql-cells/sql-cells-introduction
- Jinja in cells: https://learn.hex.tech/docs/explore-data/cells/using-jinja
- App builder: https://learn.hex.tech/docs/build-apps/app-builder
- Project sharing: https://learn.hex.tech/docs/collaborate/sharing-and-permissions/project-sharing
- Notebook Agent launch: https://learn.hex.tech/changelog/2025-08-27
- Notebook Agent Act II: https://learn.hex.tech/changelog/2025-12-16
- Product page (notebooks): https://hex.tech/product/notebooks/

**Ploomber (historical)**
- GitHub (ARCHIVED): https://github.com/ploomber/ploomber
- PyPI: https://pypi.org/project/ploomber/
- Stable docs: https://docs.ploomber.io/en/stable/
- pipeline.yaml spec: https://docs.ploomber.io/en/stable/api/spec.html
- Parametrized pipelines: https://docs.ploomber.io/en/stable/user-guide/parametrized.html
- Cloud shutdown blog: https://ploomber.io/blog/platform-shut-down/
- Marimo removes Ploomber deployment: https://github.com/marimo-team/marimo/pull/8249

**Supporting**
- Pyodide (WASM packages): https://pyodide.org/en/stable/usage/packages-in-pyodide.html
- Jinja2 (templating): https://jinja.palletsprojects.com/templates/

---

*Research model: Claude Sonnet 4.6 (Gemini 3.1 Pro unavailable in current Cursor runtime; recorded per AGENTS.md §11.14 fallback policy). AI training cutoff may be stale on library details; all claims above verified against live official docs as of 2026-05-15.*
