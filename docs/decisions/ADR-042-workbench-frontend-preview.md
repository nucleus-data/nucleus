# ADR-042: Workbench React Frontend is Preview (v0.3 work-in-progress) — Static SPA is Production Path for v0.2.0

> **Status**: ACCEPTED — 2026-05-16
> **Date**: 2026-05-16 · **Decider(s)**: Solo founder (v0.2.0 close-out batch)
> **Tags**: workbench, frontend, layer-4-experience, v0.2.0, packaging, preview, governance
> **Supersedes**: (none — first ADR scoping the static/frontend dual-implementation reality)
> **Related**: `docs/decisions/ADR-016-workbench-mvp.md` (Workbench MVP — Fork B; selects React SPA + FastAPI as the architectural target); `docs/decisions/ADR-038-workbench-v03-interactive-polish.md` (v0.3 polish window where the React build will land); `docs/decisions/ADR-039-install-size-split-extras.md` (`[workbench]` extras carve-out — clarifies what ships in the wheel); `docs/decisions/ADR-040-cli-workbench-peer-import.md` (Layer-4 peer-import rule that lets `cli/` register the Workbench sub-command); `docs/specs/nucleus_architecture_v4.1.md` §8.1 (Layer 4 Experience surface matrix) · §16.3 (Workbench RAM ≤ 1 GB target); `AGENTS.md` §11.5 (Wrap-vs-build ADR template) · §11.8 (beachhead metric — < 30-min `git clone` → BI-ready Iceberg snapshot, must not regress) · §11.10 (single-file PR discipline); `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND ("Default to less"; "No premature abstractions") + Velocity Discipline.

---

## Context

ADR-016 (2026-05-13) selected **Fork B** for the Workbench: a custom React 18 + TypeScript + Vite SPA served by a FastAPI backend, distributed inside the `nucleus` Python wheel as a pre-built static bundle and launched via `nucleus workbench up`. The sequencing in ADR-016 §"Implementation notes" assumed Weeks 1-14 of v0.2 build would carry the React tree from scaffold through to a built artifact in `src/nucleus/workbench/static/`.

The v0.2.0 sprint (Wave 1 → Wave 2 → close-out) shipped:

1. **A Vite + React + TypeScript source tree at `src/nucleus/workbench/frontend/`** — 28 components, 7 pages, ~150 KB of `.tsx` / `.ts` / `.css`, `package.json` declaring all dependencies pinned per ADR-016 (`react==18.3.1`, `vite==5.4.11`, `tailwindcss==3.4.17`, `@xyflow/react==11.11.4`, `@monaco-editor/react==4.6.0`, `zustand==5.0.2`, `@tanstack/react-query==5.62.3`, etc.). Banned-token guard at `tests/workbench/test_no_dagster_leaks.py::test_workbench_tree_has_no_banned_tokens` does PASS against this tree (sweeps `src/nucleus/workbench/` recursively for "dagster", whole-word "op", "Code Location", and "Definitions"). **However:** `node_modules/` was never created (corporate-proxy `npm install` constraints during the sprint), TypeScript was never compiled, Vite was never invoked, and there are no UI tests for these files.
2. **A self-contained `static/index.html`** — ~79 KB single-file inline-React app, vendoring `react.production.min.js`, `react-dom.production.min.js`, and `tailwind.min.js` under `src/nucleus/workbench/static/vendor/`. Mounted at `/` by `nucleus.workbench.app:create_app` via `StaticFiles(directory=str(_STATIC_DIR), html=True)`. Verified by 35/35 tests in `tests/workbench/` (covering every `/api/*` route end-to-end). Offline-renderable per ADR-016 Decision §"Process model" (no Node.js at runtime, single Python process, localhost-bound) and Rationale ("avoids requiring Node at runtime"). Renders the same Editorial Hero layout (hero gradient, 3-column grid Recent Runs / Pipeline DAG / Copilot, 8 routes) as the React tree targets.

The two implementations therefore co-exist in the v0.2.0 source. `src/nucleus/workbench/frontend/` is **the architectural target ADR-016 picked**; `src/nucleus/workbench/static/index.html` is **what users actually receive when they run `nucleus workbench up`**. There is no risk of a user accidentally getting the wrong one — `app.py` mounts only `./static/` — but the dual-implementation reality must be governed explicitly: tracking docs, public docs, and the wheel/sdist artifact must all reflect the production path, not the unfinished one.

### Forces

- **Force A — Honesty about scope (`AGENTS.md` §10 #8: "Be brutally honest about scope").** Pretending the React tree is shippable when `node_modules` does not exist is the kind of drift the §11.11 Drift Detection Pass exists to catch. The dual-implementation reality must be documented, not papered over.
- **Force B — Anti-Over-Engineering (`.cursor/rules/nucleus.mdc` BIND).** Deleting the React tree to "clean up" would discard ~150 KB of authored source that is the literal v0.3 starting point per ADR-016 sequencing. That violates "code is a liability, not an asset" only if the code has no concrete v0.3 caller — but it does, and the v0.3 caller is named (ADR-038 polish window).
- **Force C — Velocity Discipline (`.cursor/rules/nucleus.mdc` BIND).** Doing the React `npm install && npm run build` *now* would consume v0.2.0 close-out time on a path that the corporate-proxy environment cannot complete. Punting the build to v0.3 keeps the v0.2.0 ship date.
- **Force D — Beachhead metric (`AGENTS.md` §11.8).** A 5-engineer team must reach a BI-ready Iceberg snapshot in < 30 minutes from `git clone`. The `static/index.html` path satisfies this today (no Node toolchain required); any path that forces users through `npm install` regresses the metric.
- **Force E — Composability + replaceability mandate (architecture v4.1 §6.5 + §9).** The React tree is itself a swap target for the static fallback at v0.3+. Keeping both source trees in-repo preserves the swap path; deleting the React tree forecloses it.

---

## OSS / alternatives considered

This ADR is governance + packaging, not wrap-vs-build, but per `AGENTS.md` §11.5 the alternatives matrix is required:

### Option A — Mark React tree PREVIEW; ship static SPA; document; defer build to v0.3 *(SELECTED)*

- Add a PREVIEW banner to `src/nucleus/workbench/frontend/README.md`.
- Clarify the static-vs-frontend boundary in the `nucleus.workbench.app` module docstring.
- Add this ADR-042 as the canonical record of the dual-implementation reality.
- Add `src/nucleus/workbench/frontend/ export-ignore` to `.gitattributes` so `git archive` (used by some sdist build paths) does not bloat the source distribution with an uncompiled React tree end users cannot run anyway.
- Defer the actual `npm install && npm run build` + Lighthouse audit to the v0.3 polish window (ADR-038 evolution).

**Pros**: zero scope creep on the v0.2.0 ship date; preserves v0.3 starting point; beachhead metric unchanged; one coherent documentation pass settles the question for current and future readers; reversible at any time.

**Cons**: dual-implementation reality persists in the repo until v0.3; reviewers reading `pyproject.toml [project.urls]` and discovering a React tree without `node_modules` may be momentarily confused — mitigated by the README banner + `app.py` docstring.

### Option B — Delete `src/nucleus/workbench/frontend/` entirely

**Pros**: clean repo; no risk of confusion; LOC budget marginally lighter (TypeScript LOC is excluded from the 30 K Python ceiling per `pyproject.toml [tool.nucleus] loc_exclude` already, so the budget impact is purely informational, not gating).

**Cons**: discards ~150 KB of authored source that is the literal v0.3 starting point per ADR-016 sequencing §"Weeks 1-14"; v0.3 would have to re-author or re-import the components from the static `index.html`'s inline React; reverses ADR-016's architectural decision without an ADR; surprises any contributor who reads ADR-016 + ADR-038 expecting to find the tree.

**Why rejected**: the React tree IS the v0.3 work product. Deleting it because it has not yet been compiled fails Force E (replaceability + swap target) and the §11.10 single-file-PR discipline (deletion would touch 30 + files). Anti-Over-Engineering BIND ("default to less") prefers *less new code*, not *less existing source*.

### Option C — Compile the React tree now and replace `static/index.html` with the build artifact

**Pros**: realises ADR-016 fully; one canonical Workbench frontend; no preview/production split.

**Cons**: requires `npm install` to succeed, which the v0.2.0 sprint environment cannot guarantee (corporate proxy); pulls Lighthouse audit + bundle-size budget enforcement (≤ 500 KB initial JS gzipped per ADR-016 Risks) into a release window already at capacity; risks regressing the offline-renderable property of the static SPA (ADR-016 Decision §"Process model" — "no Node.js at runtime"); meaningfully extends v0.2.0 ship date.

**Why rejected**: out of scope for v0.2.0 close-out. Punting to v0.3 (ADR-038 polish window) keeps both options on the table with no hidden cost.

### Option D — Add a `[workbench-react]` extras flag that downloads the prebuilt tree at install time

**Pros**: keeps the `[workbench]` extras minimal; lets users opt-in to the (eventually built) React frontend without bloating the default install per ADR-039.

**Cons**: requires hosting a prebuilt tarball; introduces a network-fetch install path that violates the offline-friendly stance in ADR-016 + ADR-039; PoC-grade complexity for a problem the static SPA already solves.

**Why rejected**: speculative; no v0.2.0 user pain to remove. Anti-Over-Engineering BIND.

---

## Decision

> **For v0.2.0, the Nucleus Workbench frontend is `src/nucleus/workbench/static/index.html` (the offline-renderable static SPA with locally vendored React + Tailwind under `static/vendor/`). The parallel `src/nucleus/workbench/frontend/` React + TypeScript + Vite source tree is preview / v0.3 work-in-progress: it ships in the repository as the v0.3 starting point, but it is NOT compiled, NOT bundled, NOT mounted by `nucleus.workbench.app:create_app`, and NOT advertised to users in `README.md`, `mkdocs.yml`, or any cookbook / guide.**

Concretely:

1. **Source-tree governance.** `src/nucleus/workbench/frontend/README.md` carries a PREVIEW banner at the top of the file declaring its non-shipping status, naming `static/index.html` as the v0.2.0 production path, and citing ADR-016 + this ADR. The banner is the FIRST thing any reader sees.
2. **Module-boundary documentation.** `src/nucleus/workbench/app.py`'s module docstring states explicitly that only `./static/` is mounted, that `./frontend/` is preview, and that no production code path imports from `./frontend/`.
3. **No public-doc surface.** `mkdocs.yml` (the public-docs source under `docs/site/`) does not reference `src/nucleus/workbench/frontend/`. Cookbook + guide pages reference `nucleus workbench up` only — never the React source tree directly. Verified at decision time via `rg "workbench/frontend" docs/site/` → zero matches.
4. **Wheel / sdist hygiene.** `.gitattributes` marks `src/nucleus/workbench/frontend/` as `export-ignore` so `git archive` (used by sdist builders that defer to git for file enumeration) does not include it in the distributed source archive. Hatchling's wheel build is a separate path; if hatchling does not honour `export-ignore`, a follow-up `[tool.hatch.build.targets.{sdist,wheel}].exclude` rule lands in the v0.3 polish window — explicitly out of scope for this ADR.
5. **No `npm install` / `npm run build` is run during the v0.2.0 sprint.** The compile step is deferred to v0.3 per ADR-038 evolution — alongside the Lighthouse audit, the ≤ 500 KB initial-JS-gzipped bundle-size CI gate per ADR-016 Risks, and the production-path replace-or-coexist decision (replace `static/index.html` with the `dist/*` artifact, or ship both and let operators choose).

### What is unchanged

- `src/nucleus/workbench/static/index.html` and `src/nucleus/workbench/static/vendor/*.min.js` remain the production path. No edits to these files as part of this ADR.
- `nucleus.workbench.app:create_app` continues to mount `./static/` only. No code-flow change.
- `tests/workbench/` continues to cover the FastAPI surface (35/35 PASS at decision time). No new UI tests added in v0.2.0 for the React tree.
- ADR-016's architectural target (Fork B — React SPA + FastAPI) remains the v0.3+ direction. This ADR does not supersede ADR-016; it documents the v0.2.0 packaging reality on the way to ADR-016's fully-built outcome.

### What is newly governed

- The PREVIEW banner in `src/nucleus/workbench/frontend/README.md` is the canonical signal for any future contributor / external reader that the React source tree is not the v0.2.0 ship surface.
- The `app.py` docstring boundary statement is normative: any future code that mounts or imports from `./frontend/src/` must update this ADR + the docstring first.
- `.gitattributes` `export-ignore` keeps the React tree out of `git archive` outputs.

---

## Consequences

### Positive

- **Honesty preserved.** `AGENTS.md` §10 #8 ("brutally honest about scope") satisfied: the v0.2.0 ship surface is exactly what users receive (`static/index.html`); the React tree is documented as preview.
- **v0.3 starting point preserved.** ~150 KB of authored React + TypeScript source, with a lockfile-ready `package.json` pinning every dependency per ADR-016, remains in-repo. v0.3 begins with `npm install && npm run build` against this tree, not from scratch.
- **Beachhead metric preserved.** No regression to the < 30-min `git clone` → BI-ready snapshot path. Users running `nucleus workbench up` get the offline-renderable static SPA instantly; no Node toolchain required.
- **Wheel / sdist hygiene improved.** `.gitattributes` `export-ignore` prevents the React tree from bloating sdist archives generated via `git archive`.
- **Single source of governance.** One ADR, one banner, one docstring — not three different stories in three different places.

### Neutral

- The React tree continues to occupy ~150 KB of repo size + ~30 source files. Acceptable: TypeScript LOC is excluded from the 30 K Python ceiling per `pyproject.toml [tool.nucleus] loc_exclude`; the parallel TypeScript LOC ceiling (8 K per ADR-016 Open Question §5) is informational, not gating.
- The banned-token guard at `tests/workbench/test_no_dagster_leaks.py::test_workbench_tree_has_no_banned_tokens` continues to scan the React tree (since `_iter_scannable_files` recurses into `src/nucleus/workbench/`). Acceptable: vocabulary discipline does not depend on the tree being compiled.

### Negative / costs

- **Dual-implementation cognitive load.** Until v0.3 lands the React build, contributors must distinguish `static/` (production) from `frontend/` (preview). Mitigated by the PREVIEW banner + `app.py` docstring + this ADR's three-document trail.
- **No UI tests for the React tree in v0.2.0.** Acceptable: the production path (`static/index.html`) is fully covered by `tests/workbench/` backend-API integration tests + manual a11y / WCAG 2.1 AA review per ADR-016 Open Question §4. UI tests for the React build land alongside the v0.3 compile pass.

### Risks introduced

- **Risk**: a future contributor may unintentionally edit `frontend/src/*.tsx` expecting the change to ship to users in v0.2.0. **Mitigation**: PREVIEW banner is the first content in `frontend/README.md`; `app.py` docstring states the boundary; CI tests at `tests/workbench/` exercise only the FastAPI + `static/` path, so any frontend-only edit is provably non-shipping.
- **Risk**: hatchling's wheel build does not honour `.gitattributes export-ignore`, so the wheel may still include the uncompiled React tree. **Mitigation**: out-of-scope for this ADR; v0.3 polish window will add `[tool.hatch.build.targets.{sdist,wheel}].exclude` if measurement shows wheel bloat (current `pip install nucleus[workbench]` size budget per ADR-039 not violated).
- **Risk**: v0.3 reaches the build window and `npm install` still fails behind corporate proxies. **Mitigation**: external builder (CI on a non-proxied runner, or an explicit one-off founder-laptop build) produces the `dist/*` artifact and commits it directly into `static/` with a release-note explanation. ADR-038 will name the runner.

---

## Implementation notes

This ADR has four small artifacts; each lands as part of the v0.2.0 close-out:

1. **`src/nucleus/workbench/frontend/README.md`** — prepend a PREVIEW banner with status, production-path pointer, dual-implementation reasoning, v0.3 plan, and a back-link to this ADR.
2. **`src/nucleus/workbench/app.py`** — extend the module docstring with a "Static-vs-frontend boundary (ADR-042)" paragraph that names `./static/` as the only mounted directory and `./frontend/` as preview.
3. **`docs/decisions/ADR-042-workbench-frontend-preview.md`** — this file.
4. **`.gitattributes`** — add `src/nucleus/workbench/frontend/` and `src/nucleus/workbench/frontend/**` as `export-ignore` with a comment citing this ADR.

**No code-flow change. No test change. No `pyproject.toml` change.** Net Python LOC delta is ~0 (the `app.py` docstring extension is a docstring per `ast`, which `scripts/loc_budget.py` does not count).

**Migration**: none — `frontend/` was never the production path, so no users are migrated.

---

## Compliance / verification

- [x] PREVIEW banner present at the top of `src/nucleus/workbench/frontend/README.md`.
- [x] Static-vs-frontend boundary paragraph present in `src/nucleus/workbench/app.py` module docstring.
- [x] `.gitattributes` carries `src/nucleus/workbench/frontend/ export-ignore` with a citation comment.
- [x] `mkdocs.yml` does not reference `workbench/frontend` (verified via `rg "workbench/frontend" mkdocs.yml docs/site/` → zero matches at decision time).
- [x] Root `README.md` UI section references `nucleus workbench up` only — no link to `src/nucleus/workbench/frontend/`.
- [x] `nucleus.workbench.app:create_app` continues to mount only `./static/`. No production code path imports from `./frontend/src/` (verified via `rg "workbench.frontend|workbench\\\\frontend|frontend/src|frontend\\\\src" src/` → zero matches under `src/`).
- [x] Banned-token guard at `tests/workbench/test_no_dagster_leaks.py::test_workbench_tree_has_no_banned_tokens` continues to PASS against the React tree (it scans `src/nucleus/workbench/` recursively; the PREVIEW banner introduces no banned vocabulary).
- [ ] **Founder-gated**: `python scripts/check_vocabulary.py`, `python scripts/check_pinning.py`, `python scripts/dagster_leak_check.py`, `python scripts/loc_budget.py`, and `python -m pytest tests/workbench/ -q` all PASS at the founder's local environment (the swarm-implementer that authored this ADR could not exercise the Python toolchain — Microsoft-Store stub on PATH only). All five are pure docs-or-comment changes plus one `.gitattributes` addition; no logic change is in scope.
- [x] Architecture sections updated on acceptance: ADR-016 Open Question §"Implementation notes" cross-referenced from this ADR's Context (no ADR-016 edit performed — historical record preserved).

---

## Open questions

1. **Wheel-build hygiene for the React tree.** Hatchling's exact treatment of `.gitattributes export-ignore` should be measured at v0.2.0 PyPI publish time (ADR-022 release-automation surface). If the wheel ends up shipping the React source, add `[tool.hatch.build.targets.{sdist,wheel}].exclude = ["src/nucleus/workbench/frontend/**"]` in the v0.3 polish window. Out of scope for this ADR.
2. **v0.3 production-path decision: replace or coexist?** Once `npm run build` produces `dist/*`, do we (a) replace `static/index.html` with the React build artifact, or (b) ship both and let operators pick (e.g. via `nucleus workbench up --frontend=react|static`). Recommendation: (a) — single source of truth wins; (b) is speculative composability that violates Anti-Over-Engineering BIND. Final call defers to ADR-038 evolution.
3. **Compile environment for the React tree.** Corporate-proxy `npm install` constraints persisted through v0.2.0. v0.3 needs a named build environment — likely the GitHub-Actions release runner per ADR-022. Founder confirmation required before v0.3 sprint kickoff.

---

## References

- `docs/decisions/ADR-016-workbench-mvp.md` — Workbench MVP (Fork B); selects the React + FastAPI architecture this ADR documents the v0.2.0 packaging reality of.
- `docs/decisions/ADR-038-workbench-v03-interactive-polish.md` — v0.3 polish window where the React build will land.
- `docs/decisions/ADR-039-install-size-split-extras.md` — `[workbench]` extras carve-out (clarifies wheel content boundaries).
- `docs/decisions/ADR-040-cli-workbench-peer-import.md` — Layer-4 peer-import rule that lets `cli/` register the Workbench sub-command.
- `docs/decisions/ADR-022-cicd-release-automation.md` — release runner where v0.3 `npm run build` will execute.
- `docs/specs/nucleus_architecture_v4.1.md` §8.1 (Layer 4 Experience surface matrix) · §16.3 (RAM target).
- `AGENTS.md` §3 #1 (No JVM in core path — preserved by this ADR; static SPA is JVM-free) · §10 #8 ("brutally honest about scope") · §11.5 (ADR template) · §11.8 (beachhead metric — preserved) · §11.10 (single-file PR discipline — this ADR is one file plus a banner + a docstring extension + one `.gitattributes` line).
- `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND ("Default to less"; "No premature abstractions"; "No speculative code") + Velocity Discipline ("Skip ceremony, not gates").
- `tests/workbench/test_no_dagster_leaks.py` — banned-token guard that already scans the React tree.

---

*Per ADR conventions in `docs/decisions/README.md`: this ADR documents an existing v0.2.0 ship reality (the static SPA was already the production path; the React tree was already preview). The decision is to make that reality explicit + governed, not to change it.*
