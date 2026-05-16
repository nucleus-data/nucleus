# Workbench — research notes (v0.2 MVP design)

> **Component status in Nucleus**: **v0.2 web viewer + light editor** per `nucleus_architecture_v4.1.md` §8.1 (Surfaces by Release: "Workbench: ❌ v0.1 / ✅ v0.2 Monaco + asset list + chat") + §18.2 ("v0.2 — 'Developer Experience' (Month 8-14): Workbench (web IDE): Monaco editor + asset list + run history + simple AI chat").
> **Pin candidate**: nothing pinned in `pyproject.toml` today. v0.2 wave will pin one Python package (FastAPI) + a `package.json` lockfile for the frontend.
> **Tier per AGENTS.md §4**: BUILD (Layer 4 Experience — one of the three things we own forever per AGENTS.md §0). Frontend stack itself wraps OSS libraries; no custom rendering / state / SQL-editor engines.
> **Research date**: 2026-05-13. AI training cutoff may be stale; this doc reflects upstream docs verified as of today.

Required reading (all consulted before drafting): `.cursor/rules/nucleus.mdc` (Anti-Over-Engineering BIND, Velocity Discipline, wrap table); `AGENTS.md` §3 #1 (No JVM), §3 #2 (No public plugin SDK in v1), §4 (Marimo for notebooks), §11.12 (docs-before-integration), §6 Pillars; `nucleus_architecture_v4.1.md` §6.4 (Error Translation Discipline), §6.5 (Dagster Replaceability Mandate), §8.1 (surface matrix), §11.2 (perf targets), §18.2 (v0.2 scope), §20 (non-goals); `docs/internal/research/marimo.md` (notebook substrate, v0.3+); `nucleus_vs_databricks.md` (90% of analyst polish deliberately deferred).

---

## §1. What "Workbench" is for Nucleus (vs Databricks Workspace)

The Workbench is a **viewer + light editor**, not a full IDE replacement. Engineers already use Cursor / VS Code for asset *authoring*; the Workbench answers the questions that Cursor cannot — "what does my asset graph look like?", "what's in this Iceberg table right now?", "did the last run succeed?". One mental model per v4.1 §8.2: everything is an asset.

Per `nucleus_vs_databricks.md` §1 verdict: *"Different paradigm. Databricks = cloud workspace database. Nucleus = git-native project."* The Workbench is the **always-on dashboard for a git-native project**, not a cloud workspace clone.

**IS** (v0.2 minimum-viable): asset graph viewer · per-asset detail page · SQL editor against the local DuckDB warehouse · run history · simple AI chat sidebar (gated by ADR-015). **IS NOT** (deferred or out-of-scope forever): dataset-preview-at-scale (DuckDB is fine for that; we don't paginate billions of rows in-browser); dashboard builder (per v4.1 §1.6 "we are NOT a BI tool"); alerting routes (v0.5+ via the OTel-backed observability path); scheduling UI (Dagster's own UI does this — exposed via `nucleus enable compat-dagster` per v4.1 §6.1, never branded as Nucleus); collaboration / threaded comments / co-editing (per `nucleus_vs_databricks.md` §2 "Real gap — defer to v1.0+ if demanded").

The boundary with Marimo (v0.3+, per `docs/internal/research/marimo.md` §5.5): **Workbench = always-on dashboard for prod-bound asset work; Marimo = ephemeral reactive exploration before committing**. They coexist; founders pick per situation. Workbench is **NOT** a notebook IDE replacement.

---

## §2. Wow factor inventory (5 features that earn the "wow" slot)

1. **Asset graph visualization** — the #1 demo screen. Render the global asset DAG (`@nucleus.asset` defs from `coordination/asset_materialization.py`) interactively with pan / zoom / asset-type filter / freshness indicator. Reuses Dagster's GraphQL `assetNodes` query internally per the [Dagster GraphQL docs](https://docs.dagster.io/guides/operate/graphql) — we re-render in our brand, no Dagster vocabulary leaks (per v4.1 §6.4 / §6.5).
2. **Lineage panel** — per-asset upstreams + downstreams panel (asset-level only at v0.2; column-level deferred to v0.5 per v4.1 §12.4 + ADR-009). **Provisionally deferred to v0.3** to keep v0.2 surface minimal — see §6.
3. **SQL editor against the local warehouse** — Monaco editor + 1-click run against the same DuckDB process the assets use. Same query latency as `nucleus run` because we share the connection. Uses [Monaco Editor v0.55.1](https://microsoft.github.io/monaco-editor/) lazy-loaded.
4. **Snapshot history per asset** — table view showing Iceberg snapshots (snapshot ID, parent, summary, materialized-at). Reads via `pyiceberg.Table.history()` (per [PyIceberg API docs](https://py.iceberg.apache.org/api/)). Time-travel UX — click a snapshot, get the SQL `AT VERSION` clause to copy.
5. **AI Copilot chat sidebar** — depends on ADR-015 (sibling worker output). Plain inline chat per v4.1 §7.2 v0.2 stage ("Inline AI chat in Workbench — Claude API + project file context (no schema introspection)"). If ADR-015 stalls, ship Workbench without the sidebar — the other 4 carry the wow.

Anything else (custom dashboards, alerting UI, collaboration, dataset preview at >1M rows, multi-language editor, Tableau-style chart picker) is **deliberately not v0.2** — would either fail the 8-question gate or duplicate Dagster's own UI.

---

## §3. Fork A: Wrap Dagster UI + Marquez

**Concept**: ship `nucleus enable workbench` as a thin shell — embed [Dagster's webserver UI](https://docs.dagster.io/guides/operate/webserver) (asset catalog, asset graph, runs, schedules) and [Marquez](https://marquezproject.github.io/marquez/) (OpenLineage's reference UI) behind a Nucleus-branded reverse proxy with our color scheme.

**Pros**: massive feature surface for ~0 frontend dev work. Dagster's UI is genuinely excellent (asset catalog, global asset lineage, Run details, code-locations admin per the [webserver docs](https://docs.dagster.io/guides/operate/webserver)). Marquez ships an OpenLineage-compatible metadata server + React frontend already (per [marquezproject.github.io/marquez](https://marquezproject.github.io/marquez/) "real-time metadata server" + "unified visual graph"). Estimated 4-6 weeks to integrate (proxy plumbing + theme work + ADR documentation).

**Cons (terminal — these kill Fork A)**:

1. **Hard Constraint #1 violation (No JVM)**. Marquez's API server is a Java Spring Boot service per the [Marquez GitHub repo](https://github.com/MarquezProject/marquez) (`/api/` Java + `/web/` React). Embedding Marquez requires shipping a JVM in the local stack — direct conflict with `AGENTS.md §3 #1` and v4.1's "no JVM in core path" pillar. The React frontend cannot be embedded standalone; it talks Marquez's API contract.
2. **v4.1 §6.4 + §6.5 Error Translation / Replaceability violation**. Dagster's UI exposes Dagster-native vocabulary EVERYWHERE — "Op", "Code Location", "Run", "Definitions", "Schedule" (per the [webserver UI reference](https://docs.dagster.io/guides/operate/webserver)). Per v4.1 §6.5 "Dagster MUST be replaceable internally by v1.0 without ANY user code changes" + Decision D21 — exposing Dagster UI as the Workbench couples users to Dagster mental model and **kills the replaceability mandate**. This is Constraint #12 in the v4.1 §19 risk register made manifest.
3. **Brand dilution at v1.0**. Two upstream UIs (Dagster + Marquez) glued together with our header looks like exactly that. Per `nucleus_architecture_v4.1.md` §2.1 ("The Felt Moat ... one coherent UX vs 15 disjoint tools") — Fork A is 15-disjoint-tools-but-only-3, structurally identical to the Modern Data Stack we say we replace.
4. **Forbidden framing trap**. Per `AGENTS.md §8` we explicitly avoid framing as "Better Databricks". Wrapping someone else's UIs and rebranding is the canonical "Databricks-but-cheaper" move.

**Verdict**: Fork A **cannot ship** as documented in v4.1. Even if we accepted brand dilution, the JVM constraint alone makes Marquez non-embeddable. Could degrade to "Dagster UI only" — still violates §6.5 + bring back the leak risk that PoC #1 was built to eliminate. **Reject.**

---

## §4. Fork B: Custom React SPA + FastAPI backend

**Concept**: build a thin React 18 + TypeScript SPA, served by a FastAPI backend that talks to the existing `nucleus` Python core (`coordination/`, `ctx/`, `pyiceberg`, `duckdb`). Brand-coherent, hides Dagster fully, minimal footprint.

**Framework choice**: **[Vite 5+](https://vitejs.dev/guide/) + React 18 + TypeScript**. Why Vite over [Next.js 16.2.6](https://nextjs.org/docs): the Workbench is a local dev tool — no SSR / RSC / Edge runtime is needed; SPA-only ships smaller and avoids requiring Node at runtime (Python users don't want a Node server in their stack). Why not [Astro 6](https://docs.astro.build/en/getting-started/): Astro is content-island-focused, wrong fit for an interactive dashboard. Vite requires Node.js 20.19+ / 22.12+ at *build* time only — the built artifact is static files served by FastAPI's `StaticFiles` ([FastAPI docs](https://fastapi.tiangolo.com/tutorial/static-files/)), no Node at runtime. Founder builds locally; users `pip install` a wheel that contains the pre-built static bundle.

**Backend choice**: **[FastAPI](https://fastapi.tiangolo.com/)** (Python). MIT-licensed; battle-tested at Microsoft / Netflix / Uber per the front page; auto-generates OpenAPI for the Workbench REST surface (which doubles as the spec for `nucleus-mcp-server` v0.5+ per ADR-002 §4.2 hedge). Pydantic dependency conflicts with our `msgspec` preference — see §13 open question. Considered alternatives: **[Litestar 2.21.1](https://litestar.dev/)** is msgspec-native (DTO support per the front page) and the closer cultural fit, but FastAPI's ecosystem is ~10× larger and OpenAPI tooling is mature; **vanilla Flask** is rejected for missing async + missing OpenAPI generation.

**Asset graph viz**: **[React Flow / `@xyflow/react`](https://reactflow.dev/learn)**. React-native, MIT, designed for DAG visualization specifically. Quick-Start docs confirm React 18 compatibility, ~80 KB gzipped initial bundle (minus internal nodes/edges payload). Alternative considered: **[Cytoscape.js](https://js.cytoscape.org/)** — vanilla JS (needs `cytoscape-react` wrapper or manual integration), bigger (~200-300 KB depending on layout extensions), powerful but designed for general graphs incl bioinformatics. For a DAG-only use case at v0.2 scale (≤1000 assets), React Flow is the right scope. Cytoscape becomes a swap target if we ever need extreme-scale graph layout (5000+ nodes).

**SQL editor**: **[Monaco Editor v0.55.1](https://microsoft.github.io/monaco-editor/)**. Same engine as VS Code → familiar to engineers. SQL syntax highlighting built in. ~1 MB ungzipped — **mandatory lazy-load** (only when SQL editor route opens). Alternative considered: **[CodeMirror 6](https://codemirror.net/)** — smaller (~200 KB), modern API, but Monaco's VS Code parity is the bigger DX win and Cursor users already know its keybindings.

**Component library / styling**: **[shadcn/ui](https://ui.shadcn.com/docs) + [Tailwind CSS 4](https://tailwindcss.com/docs)**. shadcn is "Open Code" (per its docs intro: *"hands you the actual component code"*) — we own each component file, no black-box dependency. Tailwind defaults only; no custom design system in v0.2 (Anti-Over-Engineering BIND from `.cursor/rules/nucleus.mdc`). MIT licensed. 12-15 components total at v0.2 (Button, Card, Tabs, Dialog, Input, Select, Tooltip, Toast, Badge, Skeleton, Separator, ScrollArea).

**State management**: **[Zustand](https://github.com/pmndrs/zustand)** (~3 KB gzipped, MIT, demo at https://zustand-demo.pmnd.rs/). No boilerplate, no providers. Anti-Over-Engineering aligned. Rejected alternatives: Redux Toolkit (overkill for this surface area), Jotai (atoms add a mental model we don't need at v0.2).

**Data fetching**: **[TanStack Query v5](https://tanstack.com/query/latest)**. Standard for REST APIs; built-in caching, refetch, suspense.

**Routing**: **[TanStack Router v1](https://tanstack.com/router/latest)** (type-safe, file-based) or React Router v6.

**Testing**: [Vitest](https://vitest.dev/) (unit) + [Playwright](https://playwright.dev/) (E2E for the 30-min beachhead path).

**Pros**: brand-coherent · own the UX · zero JVM · zero Dagster vocabulary leak · OpenAPI surface doubles as MCP server spec (v0.5+) · matches `AGENTS.md §0` "we own three things, forever: ctx SDK, asset graph, unified DX" · stack is conventional → AI-assistance / agent-buildable per Pillar #3.

**Cons**: 10-14 weeks dev time at solo-founder + AI-swarm velocity (vs Fork A's 4-6 weeks) · founder is Python-leaning, so the React build velocity is the highest single risk · two language stacks to maintain (Python backend + TS frontend) · bundle-size discipline must hold (Monaco lazy-load mandatory) · we own all the bug surface we don't have today.

---

## §5. Recommendation: **Fork B (custom React SPA)**

Fork A is **not optional** — it fails Hard Constraint #1 (Marquez JVM) AND the v4.1 §6.5 Dagster Replaceability Mandate (D21). It cannot ship. The 4-6 week estimate is irrelevant when the ship is forbidden.

**Fork B at 10-14 weeks is the documented v4.1 §18.2 plan** (v0.2 spans Mo 8-14 = 24 weeks of calendar; 10-14 weeks of build leaves margin). The brand-coherence benefit is the v1.0 perception we're optimizing for; the felt-moat (per v4.1 §2.1 — "one coherent UX vs 15 disjoint tools") is the entire reason Workbench exists. Outsourcing the UX defeats the layer.

**However**: we can *internally* lean on Dagster's GraphQL API (per [Dagster GraphQL docs](https://docs.dagster.io/guides/operate/graphql)) as the read-side data source for the asset graph + run history pages. The user never sees Dagster vocabulary; we translate at the FastAPI boundary (per v4.1 §6.4 mandatory translation discipline). This collapses the v0.2 backend surface from "build asset registry from scratch" to "thin translation layer over `coordination/`'s already-Dagster-wrapped state". Effort estimate stays at the **10-14 week** band.

---

## §6. v0.2 MVP scope (minimum-viable)

**In-scope (v0.2 ship list)**:
- **Asset graph page** — full DAG, pan / zoom / filter by asset type, click a node → asset detail
- **Asset detail page** — schema (from contract), owners, last-N materializations table, link to source code (file path + line number; opens in user's editor via `vscode://` URL scheme)
- **SQL editor page** — Monaco + run-against-DuckDB + result table (paged, max 1000 rows displayed, full result downloadable as Parquet)
- **Run history page** — list view (filter by asset / status / time range), click a run → run detail (stdout/stderr tail, structured logs, NucleusError with `fix_hint` rendered)
- **AI chat sidebar** — fixed right panel, Claude API call with project file context (gated by ADR-015; ship without if ADR-015 not ratified)
- **`nucleus workbench` CLI command** — boots FastAPI on `localhost:8765`, opens browser, structured-logs to existing `~/.nucleus/logs/`

**Out of v0.2** (deferred or out-of-scope forever):
- **Lineage panel** → v0.3 (column-level needs sqlglot per v4.1 §12.4; asset-level UI needs an interaction model that's not obviously different from the asset graph view)
- **Snapshot history table** → v0.3 polish (initial v0.2 surfaces snapshot count + last snapshot only on the asset detail page; full history is one click away in the SQL editor via `SELECT * FROM <asset>.history`)
- **Collaboration / threaded comments / co-editing** → v1.5+ if customer demand (per `nucleus_vs_databricks.md` §2 "Real gap")
- **Custom dashboards / chart builder / alerting UI** → out of scope forever (per v4.1 §1.6 "we are NOT a BI tool")
- **Scheduling UI** → reuse Dagster's via `nucleus enable compat-dagster` (v4.1 §6.6 Tier 3); we don't rebuild
- **Multi-tenant UI (workspace switcher, RBAC editor)** → v0.3+ (v4.1 §15.2)
- **Plugin SDK** → forbidden in v1 per `AGENTS.md §3 #2`. No `WorkbenchPluginRegistry`. Ever.
- **i18n** → v1.0+. English-only at v0.2 per Anti-Over-Engineering BIND.

---

## §7. Performance target (DX gate)

Per v4.1 §16.3 ("Workbench server (single user) <1GB RAM"):

| Metric | Target | Source |
|---|---|---|
| Workbench cold load (browser DOMContentLoaded) | < 3 s on M1/M2 laptop | New, derived from v4.1 §11.2 "Time to first materialized asset <5 min" + UX heuristic |
| Asset graph render (≤100 assets) | < 1 s after data fetch | React Flow benchmark guidance |
| Asset graph render (≤1000 assets) | < 3 s | xyflow handles at this scale per docs |
| SQL query latency (cached DuckDB) | DuckDB-bound only — no Workbench overhead beyond network round-trip | v4.1 §16.2 "TPCH-10GB on DuckDB <3s" |
| FastAPI cold start (`nucleus workbench`) | < 2 s | Per FastAPI front page |
| Idle RAM (FastAPI + browser tab) | < 800 MB combined | v4.1 §16.3 |

These are DX gates, not SLAs. Beachhead E2E (PoC #5) verifies cold-load on real external machines.

---

## §8. Backend API surface (FastAPI)

**Stability tier**: **Internal** per ADR-005 §2 (subject to change pre-v1.0; the `ctx` SDK is the only Stable surface). REST + JSON; OpenAPI auto-generated at `/openapi.json` for future MCP server reuse.

| Endpoint | Method | Purpose | Notes |
|---|---|---|---|
| `/api/assets` | GET | List all assets w/ filter | Pagination via `?limit=N&cursor=...` |
| `/api/assets/{key}` | GET | Single asset detail | Schema, contract, owners, last-N materializations |
| `/api/assets/{key}/snapshots` | GET | Iceberg snapshot history | Reads `pyiceberg.Table.history()` |
| `/api/assets/{key}/materialize` | POST | Trigger materialization | SSE stream for progress; wraps `ctx.materialize` per ADR-013 |
| `/api/runs` | GET | List recent runs | Filter by asset/status/time |
| `/api/runs/{run_id}` | GET | Run detail + logs tail | Structured logs from `~/.nucleus/logs/` |
| `/api/query` | POST | Execute SQL via DuckDB | Returns JSON-serialized Arrow batch |
| `/api/lineage/{key}` | GET | Direct upstreams + downstreams | **v0.3+ only** — stub returns 501 in v0.2 |
| `/api/chat` | POST | AI Copilot proxy | Gated by ADR-015 |
| `/healthz` | GET | Liveness | For `nucleus workbench --check` |

**Error contract**: every endpoint returns `NucleusError` (per v4.1 §6.4) with NE-codes per ADR-006 — never raw `pyiceberg` / `duckdb` / `dagster` exceptions in the response body. The frontend renders `error.user_message` + `error.fix_hint` + `error.docs_url`.

---

## §9. Frontend bundle size budget

| Asset | Budget (gzipped) | Notes |
|---|---|---|
| Initial JS (route: `/`) | < 500 KB | React 18 (~45 KB) + Tailwind CSS (~10 KB after purge) + shadcn components used on home (~40 KB) + xyflow lazy-loaded |
| Initial CSS | < 50 KB | Tailwind purged + shadcn defaults |
| Asset graph page | adds ~80 KB | xyflow + adapter |
| SQL editor page | adds ~1 MB ungzipped (~300 KB gzipped) | **Lazy-load Monaco** — code-split by route |
| Total cold-load size for asset graph | < 600 KB gzipped | Honors §7 cold-load < 3 s |

Discipline gate: `vite build` + bundle-analyzer in CI (parallel to Python budget script in `scripts/loc_budget.py`). Fail the build if initial route exceeds 500 KB gzipped.

---

## §10. Composability with Marimo + Dagster

Per `docs/internal/research/marimo.md` §5.5 — Workbench (v0.2) and Marimo (v0.3+) coexist. Marimo IS the notebook substrate for ad-hoc reactive exploration; Workbench is the always-on dashboard. They share nothing in the frontend stack — Marimo bundles its own React frontend (38.8 MB wheel per `marimo.md` §6).

Per v4.1 §9.3 swap interface mandate — the FastAPI backend's REST surface is the swap point. If a future founder wants a different UI (e.g., a Tauri desktop app per Appendix B Question 3, or a TUI), they implement the same REST contract. The frontend SPA is one consumer of the API, not the only one.

For Dagster swap (per v4.1 §6.7 + Decision D21) — the Workbench's read paths read from `coordination/`'s abstract surface (asset registry, run registry), not Dagster directly. When `nucleus-mini-scheduler` replaces Dagster by v1.0, the Workbench is unchanged. Verified by `scripts/dagster_leak_check.py` extended to scan `src/nucleus/workbench/` (new module).

---

## §11. Forbidden mental models check

Per `.cursor/rules/nucleus.mdc` Forbidden Framings + `AGENTS.md §8`:

- ❌ NOT "the Nucleus dashboard tool" (we are not a BI tool — v4.1 §1.6)
- ❌ NOT "Databricks Workspace clone" (per `AGENTS.md §8` "Better Databricks" forbidden)
- ❌ NOT "BI replacement" (per `nucleus_vs_databricks.md` §11 verdict — connect Metabase / Superset; we are not Tableau)
- ❌ NOT framed with `AI-native` / `AI-first` vocabulary <!-- banned-term: AI-native --> <!-- banned-term: AI-first --> (per `pyproject.toml` `[tool.nucleus] forbidden_terms_in_docs` — Nucleus is AI-assisted, per ADR-002 §8)
- ❌ NOT "data warehouse UI" (the warehouse is DuckDB+Iceberg; the Workbench observes it, doesn't replace it)

✅ IS: **viewer + light editor for Iceberg-native asset graphs, AI-assisted, brand-coherent with the `ctx` SDK + `nucleus` CLI**.

---

## §12. Effort estimate

| Fork | Calendar weeks | Confidence | Block? |
|---|---|---|---|
| **A: Wrap Dagster UI + Marquez** | 4-6 | High on the integration; **architecturally blocked** | YES — Hard Constraint #1 (JVM) + v4.1 §6.5 |
| **B: Custom React SPA + FastAPI** | **10-14** | Medium-low (founder Python-leaning) | NO |

Fork B 10-14 week distribution (estimate; AI-swarm-assisted):
- Week 1-2: scaffold (Vite + React + TS + shadcn + Tailwind + FastAPI app shell + CI)
- Week 3-4: backend API surface + tests (asset list, detail, run list, run detail, query)
- Week 5-7: asset graph page + xyflow integration + asset detail page
- Week 8-9: SQL editor page + Monaco lazy-load + DuckDB connection sharing
- Week 10-11: run history + run detail + log tailing
- Week 12-13: AI chat sidebar (gated on ADR-015 ratification) + polish
- Week 14: bundle-budget + perf + accessibility audit + PoC #5 prep

Buffer: v0.2 calendar window is Mo 8-14 = 24 weeks, leaves ~10 weeks margin for unknown-unknowns + Marimo v0.3 prep work.

---

## §13. Open questions for founder

1. **Fork choice** — confirm Fork B (custom React SPA). Fork A is architecturally blocked but worth founder explicit ratification given the 6-8 week extra cost.
2. **Branding direction** — color palette + typography + logo lockup. Suggest: defer to v0.2 mid-build (Week 6) once 2-3 screens exist for visual review. Anti-Over-Engineering: don't build a brand book in v0.2.
3. **Asset graph library** — confirm React Flow / `@xyflow/react` over Cytoscape. Recommend yes; Cytoscape is a 5000+ node swap target only.
4. **SQL editor** — confirm Monaco over CodeMirror. Recommend Monaco for VS Code parity; CodeMirror is the swap target if the bundle-size gate fails repeatedly.
5. **FastAPI vs Litestar** — confirm FastAPI. Litestar is msgspec-native (cultural fit with `msgspec==0.18.6` pin in `pyproject.toml`) but FastAPI's ecosystem dominates. Recommend FastAPI for v0.2; Litestar swap if Pydantic-vs-msgspec friction emerges.
6. **AI chat sidebar at v0.2 vs v0.3** — depends on ADR-015. If ADR-015 ratifies, ship at v0.2; if not, defer to v0.3. Recommend "ship gated on ADR-015 ratification by Week 10".
7. **Accessibility commitment** — v0.2 target WCAG 2.1 AA on the 4 main pages? Recommend "best-effort AA, audit at Week 14, hard-AA at v1.0". Tailwind + shadcn defaults already give 80% of AA.
8. **Tauri (desktop) future** — Appendix B Question 3 in v4.1 (2026-05 status: undecided). Vite SPA is Tauri-compatible (Tauri wraps SPAs). Recommend SPA-first; Tauri is a v0.5+ packaging swap, not a v0.2 architecture choice.

---

## §14. AI hallucinations watch (verify before merge)

APIs I almost suggested then verified:

- ❌ `react-flow` (the npm package) — **renamed to `@xyflow/react`** in 2024; the `react-flow-renderer` legacy package is dead. Per [reactflow.dev/learn](https://reactflow.dev/learn) install command: `npm install @xyflow/react`. Logged to `ai_hallucinations.md`.
- ❌ `https://docs.dagster.io/concepts/webserver/ui-overview` — **404 as of 2026-05-13**. The URL was in the user-prompted reading list but Dagster restructured the docs. Correct URL is [docs.dagster.io/guides/operate/webserver](https://docs.dagster.io/guides/operate/webserver). Logged.
- ❌ `https://marquezproject.ai/docs/` — **404 as of 2026-05-13**. The Marquez project's official docs live at [marquezproject.github.io/marquez](https://marquezproject.github.io/marquez/), not marquezproject.ai. Logged.
- ❌ `marimo.workbench(...)` / `marimo.embed_in_react(...)` — **fabricated.** Marimo embeds via `marimo export html` for static HTML, not React iframes. Per `docs/internal/research/marimo.md` §4 + §9 known-gotchas list. Workbench and Marimo do not share frontend.
- ❌ `dagster_pipes.workbench(...)` / `dagster.materialize_via_workbench(...)` — **fabricated.** Workbench triggers materialization via `ctx.materialize` per ADR-013, not a Dagster-direct API.
- ❌ `# NEEDS VERIFICATION` — exact gzipped bundle size of React 18 + xyflow + shadcn at v0.2 cold-route. Numbers in §9 are derived from package READMEs + bundle-analyzer historical data; **measure on real build at Week 2 of v0.2 work** and update this doc.

---

*Last verified: 2026-05-13 against React 18 / Vite 5 / FastAPI 0.115+ / Monaco 0.55.1 / xyflow latest / Dagster 1.9.5 docs. Re-verify before opening the v0.2 implementation ADRs and on any Hard Constraint touching upgrade. Log any AI-fabricated framework APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
