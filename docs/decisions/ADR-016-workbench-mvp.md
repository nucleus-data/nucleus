# ADR-016: Workbench MVP — Custom React SPA + FastAPI (Fork B)

> **Status**: ACCEPTED — 2026-05-13 (founder ratified Fork B + all 6 Open Questions per recommendations; see `docs/internal/FOUNDER_ACTION_QUEUE.md §0 2026-05-13` ratification record)
> **Date**: 2026-05-13 · **Decider(s)**: Solo founder (this ADR DRAFTS the recommendation; founder ratifies)

> **Founder ratification (2026-05-13)** — Fork choice + all 6 Open Questions resolved per ADR recommendations:
> 1. **FastAPI** for v0.2 confirmed; Litestar swap reconsidered at v0.3 only on real Pydantic-vs-msgspec friction evidence.
> 2. **AI chat sidebar**: ship Workbench v0.2 without sidebar if ADR-015 not ratified by Week 10; chat deferred to v0.3 or v0.2.1 patch.
> 3. **Branding**: deferred to Week 6 once 2-3 screens exist for visual review (no brand book in v0.2 — Anti-Over-Engineering).
> 4. **Accessibility**: WCAG 2.1 AA best-effort + Week 14 audit for v0.2; hard-AA target at v1.0.
> 5. **Frontend LOC budget**: 8K TypeScript LOC ceiling for v0.2 (separate from 30K Python ceiling); tracked in `docs/internal/budget_history.md`.
> 6. **Tauri**: deferred to v0.5+ packaging ADR; v0.2 ships SPA + FastAPI architecture (Tauri-compatible).
> **Tags**: workbench, frontend, fastapi, react, v0.2, layer-4-experience
> **Supersedes**: (none — first Workbench architecture ADR)
> **Related**: `docs/specs/nucleus_architecture_v4.1.md` §6.4 (Error Translation Discipline) · §6.5 (Dagster Replaceability Mandate) · §8.1 (Layer 4 Experience surface matrix) · §11.2 (perf targets) · §16.3 (Workbench RAM ≤1 GB) · §18.2 (v0.2 roadmap) · §20 (non-goals); ADR-002 §4.2 (`nucleus-mcp-server` shares OpenAPI surface); ADR-005 §2 (Internal-tier API stability); ADR-006 (NE-codes); ADR-013 (`ctx.materialize` API consumed by Workbench); `docs/internal/research/workbench.md` (companion research, this ADR's evidence base); `docs/internal/research/marimo.md` §5.5 (Workbench vs Marimo boundary); `docs/specs/nucleus_vs_databricks.md` §1-§4 (workspace paradigm difference); `AGENTS.md §3 #1` (No JVM) · §3 #2 (No public plugin SDK) · §11.12 (docs-before-integration); `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND.

---

## Context

`docs/specs/nucleus_architecture_v4.1.md` §18.2 ("v0.2 — 'Developer Experience' (Month 8-14): Workbench (web IDE): Monaco editor + asset list + run history + simple AI chat") and §8.1 (Surfaces by Release matrix: Workbench `❌` v0.1 → `✅` v0.2) commit Nucleus to ship a Workbench in v0.2. The v4.1 spec stops at "web IDE + asset list + chat" — it does not pick a framework, a backend, or a delivery model. v4.1 Appendix B Question 3 ("Workbench technology — Tauri vs pure web") is the documented blocker for v0.2 design.

Two architectural forks are real:

- **Fork A**: wrap Dagster's webserver UI ([docs.dagster.io/guides/operate/webserver](https://docs.dagster.io/guides/operate/webserver)) + Marquez ([marquezproject.github.io/marquez](https://marquezproject.github.io/marquez/)) behind a Nucleus-branded shell.
- **Fork B**: build a thin custom React SPA with FastAPI backend.

Forces in tension:

- **Velocity vs brand-coherence** — Fork A ships in 4-6 weeks; Fork B in 10-14 weeks (per `docs/internal/research/workbench.md` §12).
- **Wrap-not-build (`AGENTS.md §4` default) vs Layer 4 Experience ownership (`AGENTS.md §0` "we own three things, forever: ... unified developer-first experience")** — Layer 4 is on the explicit BUILD list per `.cursor/rules/nucleus.mdc` ("Build only the experience and intelligence layers: ... Workbench (v0.2+)").
- **Hard Constraint #1 (No JVM in core path) vs Marquez** — Marquez's API server is Java Spring Boot per the [MarquezProject GitHub](https://github.com/MarquezProject/marquez); the React frontend cannot ship standalone.
- **v4.1 §6.5 Dagster Replaceability Mandate (D21) vs Dagster UI exposure** — exposing Dagster's UI directly leaks Dagster vocabulary ("Op", "Code Location", "Definitions") and breaks the by-v1.0 zero-Dagster-grep mandate.

Companion research at `docs/internal/research/workbench.md` (155 LOC, 25 distinct docs URLs cited) is this ADR's evidence base; founder is expected to read both before ratification.

---

## Decision

> **We will build the Workbench v0.2 MVP as a custom React 18 + TypeScript SPA (built with Vite) served by a FastAPI backend (Fork B), distributed inside the `nucleus` Python wheel as a pre-built static bundle and launched via `nucleus workbench`. We will reject Fork A.**
>
> Specifically:
> - **Frontend stack**: [Vite 5](https://vitejs.dev/guide/) + React 18 + TypeScript + [Tailwind CSS](https://tailwindcss.com/docs) + [shadcn/ui](https://ui.shadcn.com/docs) (open-code components — own the source, no black-box library) + [Zustand](https://github.com/pmndrs/zustand) state + [TanStack Query / Router](https://tanstack.com/query/latest).
> - **Asset graph viz**: [`@xyflow/react`](https://reactflow.dev/learn) (formerly React Flow). Cytoscape.js is the v0.5+ swap target if we exceed 5000-asset graphs.
> - **SQL editor**: [Monaco Editor v0.55.1](https://microsoft.github.io/monaco-editor/), lazy-loaded on the SQL editor route only (~1 MB ungzipped — bundle-budget critical).
> - **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python). REST + auto-generated OpenAPI at `/openapi.json` (which doubles as the `nucleus-mcp-server` v0.5+ contract per ADR-002 §4.2).
> - **Process model**: single Python process; FastAPI serves both API and pre-built static bundle. No Node.js at runtime. No Docker required for v0.2. Bound to `localhost:8765` by default.
> - **Stability tier**: Workbench REST API is **Internal** per ADR-005 §2 — subject to change pre-v1.0; `ctx` SDK remains the only Stable surface.

---

## Rationale

1. **Fork A is architecturally blocked, not slow.** Marquez requires JVM (`AGENTS.md §3 #1` violation). Embedding Dagster's UI exposes Dagster vocabulary directly (v4.1 §6.4 + §6.5 + Decision D21 violation — the entire reason PoC #1's Error Translation Layer exists). The 4-6-week estimate is irrelevant when the ship is forbidden.
2. **Fork B fits the documented v0.2 calendar** (Mo 8-14 = 24 weeks of calendar; 10-14 weeks of build leaves margin for Marimo v0.3 prep).
3. **Layer 4 Experience is on the explicit BUILD list** per `.cursor/rules/nucleus.mdc` — the wrap-not-build default does not apply to UX. Per v4.1 §2.1, the **Felt Moat** is "one coherent UX vs 15 disjoint tools"; outsourcing the UX to two upstream UIs (Dagster + Marquez) defeats the entire layer.
4. **Vite over Next.js** — Workbench is a local dev tool. SSR / RSC / Edge runtime are negative value; SPA is smaller and avoids requiring Node at runtime per [vitejs.dev/guide](https://vitejs.dev/guide/) ("Vite is opinionated and comes with sensible defaults out of the box"). Astro 6 ([docs.astro.build](https://docs.astro.build/en/getting-started/)) is content-island-focused — wrong fit for an interactive dashboard.
5. **FastAPI over Litestar** — both work; FastAPI's ecosystem dominates and the OpenAPI tooling is mature. [Litestar 2.21.1](https://litestar.dev/) is msgspec-native (cultural fit with our `msgspec==0.18.6` pin) but the ecosystem-size delta makes FastAPI the right v0.2 default; Litestar swap is a v0.3 reconsider if Pydantic-vs-msgspec friction emerges (open question §1 below).
6. **`@xyflow/react` over Cytoscape.js** — DAG-native, MIT, ~80 KB gzipped per the [Quick Start docs](https://reactflow.dev/learn). Cytoscape ([js.cytoscape.org](https://js.cytoscape.org/)) is overkill for ≤1000-asset DAGs at v0.2 scale.
7. **shadcn/ui + Tailwind** — Anti-Over-Engineering BIND. Per [ui.shadcn.com/docs](https://ui.shadcn.com/docs) ("hands you the actual component code") we own each component file, no opaque dependency. No custom design system in v0.2 — Tailwind defaults + shadcn defaults only. AI-comprehensible surface (Pillar #3).

---

## Alternatives considered

### Alternative A: Wrap Dagster UI + Marquez

**Pros**: ~0 frontend dev work; ships in 4-6 weeks; massive feature surface immediately.

**Cons**: Marquez backend is JVM (Hard Constraint #1 violation); Dagster UI exposes Dagster vocabulary (v4.1 §6.4 + §6.5 + D21 violation, kills replaceability mandate); brand dilution at v1.0 perception.

**Why rejected**: The JVM violation alone forbids ship. The Dagster vocabulary leak independently forbids ship. Both must be true simultaneously to ship Fork A; both are false.

### Alternative B: Custom React SPA + FastAPI (Fork B)

**Why selected**: see Decision + Rationale above.

#### External reviewer note — "Fork A" label disambiguation (2026-05-14 amendment)

An external reviewer-feedback round used the label **"Fork A"** to mean *"embed an OSS notebook UI (Marimo / Jupyter) instead of building a React SPA"*, which maps to **Alternative D** in this ADR (Marimo as the Workbench), not the **Alternative A** above (Dagster UI + Marquez). Both routes were rejected, but for different reasons:

- **Alternative A (Dagster UI + Marquez)** — rejected because Marquez is JVM (Constraint #1) and Dagster UI leaks Dagster vocabulary (v4.1 §6.4).
- **Alternative D (Marimo / Jupyter embed)** — rejected because Marimo is a notebook runtime (right primitive: cell), not a control surface (right primitive: asset graph + materialization status + lineage). Coupling the Workbench to a notebook iframe forces every Workbench feature to ship as a Marimo extension; gives up the asset-graph-native UX advantage the platform's vocabulary is built on; and ships a notebook surface in v0.2 when notebooks themselves are deferred to v0.3 per `docs/specs/nucleus_architecture_v4.1.md` §18 roadmap.

If a future external reviewer cites "Fork A," confirm which alternative they mean before responding.

### Alternative C: Tauri desktop app (cross-platform native)

**Pros**: native OS integration; offline-first identical-to-prod; native menu bar / system tray.

**Cons**: adds a Rust toolchain to founder's build pipeline; cross-platform packaging adds ~2-3 weeks per platform target; user installation friction (vs `pip install nucleus-data` then `nucleus workbench`).

**Why rejected (for v0.2 — reconsider for v0.5+)**: Tauri wraps SPAs. Building Fork B as a Vite SPA keeps the Tauri-packaging path open without committing to it now. Per v4.1 Appendix B Q3: "retrofit between them is significant rework" — but only if the SPA assumes a server. Our SPA + FastAPI architecture is Tauri-compatible because Tauri can either bundle FastAPI as a sidecar or replace it with a Tauri-native command surface. Defer Tauri to a v0.5 packaging swap, not a v0.2 architecture choice.

### Alternative D: Marimo as the Workbench

**Pros**: Marimo IS our notebook substrate per `AGENTS.md §4`; reusing it as the Workbench saves a stack.

**Cons**: per `docs/internal/research/marimo.md` §5.5, Marimo and Workbench serve different purposes — Marimo = ephemeral reactive exploration; Workbench = always-on dashboard for prod-bound asset work. Marimo lacks the asset-graph + run-history + lineage-panel surfaces. Marimo also adds 38.8 MB wheel weight per `marimo.md` §6.

**Why rejected**: different problems; both ship (Workbench v0.2, Marimo v0.3). Documented composability in `docs/internal/research/workbench.md` §10.

---

## Consequences

### Positive
- Brand-coherent UX, owned end-to-end (per Felt Moat thesis, v4.1 §2.1).
- Zero JVM (Hard Constraint #1 preserved).
- Zero Dagster vocabulary leaks at the Workbench surface (v4.1 §6.4 + §6.5 + D21 honored).
- OpenAPI surface doubles as `nucleus-mcp-server` v0.5+ contract (ADR-002 §4.2 hedge).
- Tauri-compatible architecture (v0.5+ packaging swap stays open).
- Stack is conventional (React + Vite + FastAPI), AI-agent-buildable (Pillar #3).

### Negative / costs
- 10-14 weeks of build at solo-founder + AI-swarm velocity (4-8 weeks slower than Fork A's blocked option).
- Two language stacks to maintain (Python backend + TypeScript frontend) — onboarding burden for any future contributor.
- LOC budget impact: Workbench v0.2 estimated ~3-4K LOC of Python (FastAPI + adapters) + ~5-7K LOC of TypeScript (React + components). The TypeScript LOC is **not counted in the 30K proprietary Python budget** per `pyproject.toml [tool.nucleus] loc_exclude` — but we should track it separately in `docs/internal/budget_history.md` to avoid silent expansion.
- Bundle-size discipline must hold. Monaco lazy-load is mandatory; CI gate at < 500 KB initial JS gzipped.

### Risks introduced
- **Risk**: Founder is Python-leaning; React build velocity is the highest single risk to v0.2 calendar. **Mitigation**: lean on AI-swarm for boilerplate (per AGENTS.md §11.14); use shadcn/ui for "open code" components (no learning a 3rd-party API surface); defer all custom design work to v1.0.
- **Risk**: Pydantic vs msgspec friction (FastAPI uses Pydantic; Nucleus core uses msgspec). **Mitigation**: thin adapter at the FastAPI boundary; reconsider Litestar at v0.3 if friction is real, not theoretical.
- **Risk**: Bundle-size creep (Monaco alone is ~1 MB ungzipped). **Mitigation**: route-based code splitting; CI bundle-budget gate; Monaco only loads when SQL editor route opens.
- **Risk**: AI chat sidebar dependency on ADR-015 (sibling worker). **Mitigation**: ship Workbench without the sidebar if ADR-015 stalls; the other 4 wow-factor features carry the v0.2 demo.
- **Risk**: `@xyflow/react` cannot scale past ~5000 asset nodes (anecdotal from upstream issue tracker; not yet measured). **Mitigation**: v0.2 ships at the ≤1000-asset scale per `docs/internal/research/workbench.md` §7; Cytoscape.js swap is interface-only at v0.2, full at v0.5+ if scale demands.
- **Risk**: We accidentally rebuild Tableau / Looker / Metabase. **Mitigation**: Forbidden Mental Models check in `docs/internal/research/workbench.md` §11; Drift Detection Pass (`AGENTS.md §11.11`) every 4 weeks during v0.2 build.

---

## Implementation notes

Sequencing (10-14 weeks; full breakdown in `docs/internal/research/workbench.md` §12):

1. **Weeks 1-2**: Scaffold (Vite + React + TS + Tailwind + shadcn + FastAPI app shell + CI bundle-budget script).
2. **Weeks 3-4**: Backend API surface + tests (asset list / detail, run list / detail, query). Per `docs/internal/research/workbench.md` §8.
3. **Weeks 5-7**: Asset graph page + xyflow integration + asset detail page.
4. **Weeks 8-9**: SQL editor page + Monaco lazy-load + DuckDB connection sharing with `coordination/`.
5. **Weeks 10-11**: Run history + run detail + log tailing.
6. **Weeks 12-13**: AI chat sidebar (gated on ADR-015 ratification) + polish.
7. **Week 14**: Bundle-budget audit + perf measurement + accessibility audit + PoC #5 prep.

**Affected files / modules** (forecasted; created during v0.2 build, not by this ADR):
- `src/nucleus/workbench/` (new module — FastAPI app, route handlers, adapter to `coordination/`)
- `frontend/` (new top-level dir — Vite project; built artifact copied into `src/nucleus/workbench/static/` during `hatch build`)
- `src/nucleus/cli/commands/workbench.py` (new — `nucleus workbench` command)
- `tests/workbench/` (new — backend API tests)
- `frontend/src/__tests__/` (new — Vitest unit + Playwright E2E)
- `scripts/check_bundle_size.py` (new — CI gate, < 500 KB initial JS gzipped)
- `scripts/dagster_leak_check.py` (extend — scan `src/nucleus/workbench/`)
- `docs/internal/budget_history.md` (extend — track frontend LOC separately)
- `docs/internal/swap/workbench.md` (new — document Tauri / Cytoscape / CodeMirror / Litestar swap targets)

**Migration**: none — Workbench is greenfield at v0.2. Users who never run `nucleus workbench` are unaffected.

---

## Compliance / verification

- [ ] Test added: `tests/workbench/test_api_surface.py` (every endpoint per `docs/internal/research/workbench.md` §8 returns 200 / NucleusError-shaped errors).
- [ ] Test added: `tests/workbench/test_no_dagster_leaks.py` (scan API responses + frontend strings — zero "dagster", "Op", "Code Location", "Definitions").
- [ ] CI check added: `scripts/check_bundle_size.py` (fail if initial JS gzipped > 500 KB).
- [ ] CI check extended: `scripts/dagster_leak_check.py` to scan `src/nucleus/workbench/` + `frontend/src/`.
- [ ] CI check extended: `scripts/check_vocabulary.py` (already runs; verify Workbench docs add no banned terms).
- [ ] Documented in: `docs/internal/research/workbench.md` (this ADR's evidence base); `docs/internal/swap/workbench.md` (NEW at v0.2 build start).
- [ ] Architecture sections updated on acceptance: v4.1 §8.1 row "Workbench v0.2" annotated with "(Vite + React + FastAPI per ADR-016)"; v4.1 Appendix B Question 3 marked RESOLVED-by-ADR-016.

---

## Open questions

1. **FastAPI vs Litestar tiebreak threshold.** If Pydantic-vs-msgspec friction surfaces in Weeks 3-4, do we swap to Litestar (msgspec-native) or stay on FastAPI? Recommend stay on FastAPI for v0.2; Litestar swap reconsidered at v0.3 only on real evidence.
2. **AI chat sidebar gating window.** ADR-015 ratification deadline. If ADR-015 not ratified by Week 10, ship Workbench v0.2 without sidebar; defer chat to v0.3 or to a v0.2.1 patch.
3. **Branding direction.** Color palette / typography / logo lockup. Recommend: defer to Week 6 once 2-3 screens exist for visual review. Anti-Over-Engineering: no brand book in v0.2.
4. **Accessibility commitment.** WCAG 2.1 AA target for v0.2 ship vs "best-effort, audit at Week 14". Recommend best-effort + Week 14 audit; hard-AA at v1.0.
5. **Frontend LOC budget.** TypeScript LOC is excluded from the 30K Python ceiling per `pyproject.toml [tool.nucleus] loc_exclude`, but we should set a parallel ceiling in `docs/internal/budget_history.md`. Recommend: **8K TypeScript LOC ceiling for v0.2**; reconsider at v1.0.
6. **Tauri future commitment.** v4.1 Appendix B Q3 was deferred. This ADR resolves the v0.2 web-vs-desktop question (web). Tauri-as-packaging at v0.5+ remains open; recommend a v0.5 ADR (not v0.2 work).

---

## References

- `docs/internal/research/workbench.md` — companion research (this ADR's evidence base; 25 docs URLs cited).
- `docs/specs/nucleus_architecture_v4.1.md` §6.4 (Error Translation Discipline) · §6.5 (Dagster Replaceability Mandate) · §8.1 (Layer 4 Experience surfaces) · §16.3 (RAM target) · §18.2 (v0.2 roadmap) · §20 (non-goals) · Appendix B Q3 (Workbench technology question — this ADR resolves the web/desktop fork).
- ADR-005 §2 (Internal-tier API stability) · ADR-006 (NE-codes) · ADR-013 (`ctx.materialize` consumed by Workbench).
- `AGENTS.md §3 #1` (No JVM in core path) · `§3 #2` (No public plugin SDK in v1) · `§4` (do-not-build list) · `§11.12` (docs-before-integration discipline).
- `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND + Velocity Discipline.
- `docs/specs/nucleus_vs_databricks.md` §1-§4 (workspace paradigm) · §11 (we are NOT a BI tool).
- External docs (full list cited in `docs/internal/research/workbench.md` §1-§14): [Vite](https://vitejs.dev/guide/), [React Flow / xyflow](https://reactflow.dev/learn), [Monaco](https://microsoft.github.io/monaco-editor/), [FastAPI](https://fastapi.tiangolo.com/), [shadcn/ui](https://ui.shadcn.com/docs), [Dagster webserver](https://docs.dagster.io/guides/operate/webserver), [Marquez](https://marquezproject.github.io/marquez/).

---

*This ADR DRAFTS the recommendation; founder ratifies the fork choice + framework picks before any implementation. Per ADR conventions in `docs/decisions/README.md`: PROPOSED → ACCEPTED gate is founder review only; AI agents may draft, never accept.*
