# Marimo (Reactive Python Notebook) — Research Notes

> **Component status in Nucleus**: **v0.3+ optional notebook wrap.** Replaces Jupyter; coexists with the Workbench web IDE (v0.2). Per `AGENTS.md §4` (do-not-build list: "Custom notebook runtime → use Marimo") and `docs/specs/nucleus_architecture_v4.1.md` §3.1 (L4 Experience), §8.1 (component matrix), §18.3 (v0.3 roadmap: "Marimo notebook integration").
> **Pin candidate**: `marimo==0.23.6` (released **2026-05-11**, verified on PyPI 2026-05-13). **Not pinned in `pyproject.toml` today.**
> **License**: **Apache-2.0**  •  **JVM-free**: **YES** — pure Python kernel + bundled React/TypeScript frontend (no JVM). Hard Constraint #1 satisfied.
> **Research date**: 2026-05-13
> **Used in**: nowhere (yet). Pre-research artifact for the v0.3 ADR.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening the v0.3 integration ADR. Canonical **wrap-not-build** case (Pillar #2) — we will never write a reactive notebook runtime ourselves (AGENTS.md §4).

---

## §1. At a glance

- **License**: Apache-2.0  •  **Maintainer**: marimo team (Akshay Agrawal, Myles Scolnick et al.); **NumFOCUS affiliated**.  •  **GitHub**: https://github.com/marimo-team/marimo
- **Position**: L4 Experience — **optional**. Surfaces as `nucleus notebook` (wraps `marimo edit/run`) in v0.3. The `ctx` SDK is callable from inside Marimo cells; cells are **not** Nucleus assets unless explicitly decorated with `@nucleus.asset`.
- **Latest stable**: 0.23.6 (2026-05-11). Pre-1.0 (still 0.x). ~2.2M monthly PyPI downloads. `Development Status :: 4 - Beta`.

**What it is**: a **reactive Python notebook** stored as pure `.py`. Cells form a static DAG via reference analysis (no hidden state, no out-of-order surprises). Cells can be Python, markdown, or **SQL** (`mo.sql(...)`, DuckDB-powered). Runs as editor (`marimo edit`), app (`marimo run`), or script (`python notebook.py`). Optional in-browser execution via Pyodide. No daemon, no JVM, no scheduler.

---

## §2. What Marimo is, in Nucleus terms

A Marimo notebook is a **per-notebook reactive DAG**, in-process, dev-time. Nucleus's asset graph is a **global persistent DAG**, materializing to Iceberg, owned by Dagster. **Different objects; do not conflate** (see §5.3).

| Marimo concept | Nucleus mapping |
|---|---|
| Notebook file (`.py`) | **Source of exploration**, optionally promotes to one or more `@nucleus.asset` defs (`nucleus notebook` CLI) |
| `@app.cell` | **Ephemeral asset preview** (memory only) — not a Nucleus primitive |
| `mo.sql(...)` cell | **DuckDB query**, same engine as `ctx.sql` (see §5.2) |
| `mo.ui.*` widget | **Dev-time parameter** (slider/dropdown/text); maps to `ctx.params` only on promotion |
| `mo.state(...)` | Out of scope — never expose through `ctx`; docs warn against use |
| Reactive re-execution | Dev-time feedback loop only; Dagster owns prod re-derivation |
| `marimo export html-wasm` | Out of scope for v0.3; founder MAY use directly; we don't host |

The boundary is **the `@nucleus.asset` decorator**. Until applied to a cell function and `nucleus run` invoked, no Iceberg commit, no lineage, no contract runs. Marimo is the iteration loop; Nucleus is the commit ledger.

---

## §3. Official documentation URLs

Verified via `WebFetch` 2026-05-13.

- Main / API: https://docs.marimo.io/ • https://docs.marimo.io/api/
- Reactivity: https://docs.marimo.io/guides/reactivity/  •  SQL: https://docs.marimo.io/guides/working_with_data/sql/  •  Dataframes: https://docs.marimo.io/guides/working_with_data/dataframes/
- State: https://docs.marimo.io/guides/state/  •  Scripts: https://docs.marimo.io/guides/scripts/  •  Apps: https://docs.marimo.io/guides/apps/  •  WASM: https://docs.marimo.io/guides/wasm/
- Runtime config: https://docs.marimo.io/guides/configuration/runtime_configuration/  •  Exporting: https://docs.marimo.io/guides/exporting/
- `marimo.App`: https://docs.marimo.io/api/app/  •  Control flow: https://docs.marimo.io/api/control_flow/
- GitHub / Releases / PyPI: https://github.com/marimo-team/marimo • https://github.com/marimo-team/marimo/releases • https://pypi.org/project/marimo/

**Documented 404s on 2026-05-13** (flag for AI agents):

- `https://docs.marimo.io/guides/integrating_with_other_tools/` — **does not exist.** Integration content is scattered (scripts page, reusing-functions, VS Code extension on README). Cite the specific subpage; do not invent the umbrella URL.
- No central reference for marimo's exception classes. Only `MarimoStopError` documented on the control-flow page. Read `marimo/_runtime/` in source for the rest.

---

## §4. APIs Nucleus will wrap

Symbols the v0.3 wrap (`experience/marimo_adapter.py`, target ≤300 LOC) touches. Signatures at 0.23.6.

| Symbol | Signature | Use |
|---|---|---|
| `marimo.App` | `App(**kwargs)` (full kwargs not enumerated in public docs) | Produced by `marimo new`/`edit`. Never called directly. |
| `App.run` | `run(defs=None, **kwargs) -> tuple[Sequence[Any], Mapping[str,Any]]` | **Confirmed** — programmatic execution with optional def overrides. Path for `nucleus run notebook=...`. |
| `App.embed` | `async embed(defs=None) -> AppEmbedResult` | Embed notebook in notebook. Out of scope for v0.3. |
| `@app.cell` | Decorator on user fns **inside** a notebook | Reactive DAG built statically. Nucleus never calls. |
| `mo.sql` | `mo.sql(query: str, *, output=None, engine=None) -> DataFrame` — **`# NEEDS VERIFICATION`** (param names inferred; read `marimo/_sql/sql.py` at v0.3) | Integration point for `ctx.sql` (§5.2). |
| `mo.ui.*` | `slider`, `dropdown`, `table`, `text`, `button`, `dataframe`, `array`, etc. | Dev-time only; out of scope. |
| `mo.state` | `mo.state(value, *, allow_self_loops=False) -> (getter, setter)` | Docs: "in over 99% of cases ... shouldn't use." Not surfaced. |
| `mo.stop` | `mo.stop(predicate: bool, output=None) -> None` — raises `MarimoStopError` when `predicate is True` | Error translation (§5.4). |
| `mo.Thread` | `threading.Thread` subclass; `.should_exit` tied to spawning cell | Out of scope. |
| `mo.app_meta` | Returns `.mode` (`"edit"\|"run"\|"script"\|"test"\|None`), `.theme`, `.request` | Script-vs-edit context. |
| `mo.notebook_location` | Returns notebook's parent `Path`; works in WASM | Project-relative file resolution. |
| Marimo CLI | `marimo edit [file]`, `marimo run file`, `marimo export {html,pdf,ipynb,script,md,html-wasm,session}`, `marimo convert ipynb`, `marimo check` | `nucleus notebook` shells out. https://docs.marimo.io/guides/exporting/. |

**Not used in v0.3**: `mo.state`, `mo.Thread`, `App.embed`, GUI-transform back-translation, WASM HTML export, slides layout, `marimo pair` agent CLI.

---

## §5. Integration points with Nucleus

### §5.1 Marimo cell as Nucleus ephemeral asset preview

User adds `@nucleus.asset(...)` to a function inside a `@app.cell` (decorator-callable-inside-cell **`# NEEDS VERIFICATION`** at v0.3 PoC). In **`marimo edit` mode**, the cell runs reactively and `ctx.preview(asset_fn)` (new v0.3 SDK surface, ≤50 LOC) materializes **in memory only** — no Iceberg commit, no Dagster run record. In **`python notebook.py` (script) mode** (`mo.app_meta().mode == "script"`), the path runs `ctx.commit()` semantics — full Dagster materialization, Iceberg snapshot, lineage event. Preview lineage is **dev-only**; on commit, Nucleus's asset graph is source of truth.

Wrap surface: **`nucleus.marimo`** module exposing `preview(fn) -> DataFrame`, `commit(fn) -> RunResult`. Total budget ≤300 LOC. **Build only when v0.3 telemetry shows demand** (AGENTS.md §11.4).

### §5.2 SQL cell integration with `ctx.sql` — THE CRITICAL DESIGN QUESTION

Per `docs/specs/nucleus_architecture_v4.1.md` §5: native `ctx.sql` resolver handles `{{ ref('asset_x') }}` Jinja → catalog lookup → DuckDB-registered view.

Marimo's `mo.sql(...)` runs SQL in a Python **f-string** wrapper, against either the default in-memory DuckDB connection or a **user-supplied engine variable discovered from cell scope**. Custom DuckDB connections are explicitly supported (https://docs.marimo.io/guides/working_with_data/sql/ §"Connecting to a custom database"):

```python
import duckdb
duckdb_conn = duckdb.connect("file.db")  # marimo auto-discovers; listed in engine dropdown
```

**The original integration design question is resolved: YES, `mo.sql` accepts a custom DuckDB connection.** Registering `ctx.duckdb_connection` as a notebook global suffices. Output type (`native`/`polars`/`lazy-polars`/`pandas`/`auto`) is set via `[tool.marimo.runtime] default_sql_output`; `nucleus init` will default to `polars`.

**However: a syntactic collision the docs reveal.** Marimo SQL cells are f-strings, so `{...}` is Python interpolation. Per https://docs.marimo.io/guides/working_with_data/sql/ §"Escaping SQL brackets", literal `{`/`}` in SQL must be escaped as `{{...}}` — **exactly Nucleus's Jinja `{{ ref('asset_x') }}` syntax**. A naive `mo.sql("SELECT * FROM {{ ref('asset_a') }}")` is interpreted as **literal `{ ref('asset_a') }` in SQL**, not as Jinja. This is the v0.3 ADR's central design call:

| Option | User writes | Pros | Cons |
|---|---|---|---|
| **A. Python helper** | `df = ctx.ref('asset_a')` in Python cell; `SELECT * FROM df` in SQL cell | Pure DuckDB SQL; uses Marimo's df-as-table feature; data-sources panel autocomplete | Two-cell pattern |
| **B. Pre-resolve wrapper** | `nucleus.marimo.sql("SELECT * FROM {{ ref('asset_a') }}")` | One-line; matches `ctx.sql` exactly | Bypasses Marimo's SQL cell UX (no engine dropdown, no linter); duplicates `mo.sql` |
| **C. Global-injection pre-pass** | `mo.sql("SELECT * FROM {{ref_a}}")` after `App.run` defs inject `ref_a = ...` | Closest to Marimo idiom | Magic; brittle |

**Provisional v0.3 stance**: **Option A.** Composes with Marimo's data-sources panel, doesn't fight f-string syntax, matches the docs example pattern. **Decision deferred to ADR**, with an external-tester UX field test as the gate.

### §5.3 Reactivity vs Nucleus's asset graph

Per https://docs.marimo.io/guides/reactivity/, marimo builds a DAG of cells from static reference analysis. **Marimo's DAG**: per-notebook, in-process, dev-time, in-memory. **Nucleus's asset graph**: global, persistent in catalog, prod, with Iceberg snapshots. **Must not be merged**: don't display Nucleus's asset graph as if it were the reactive DAG (users will expect reactive re-materialization, which Dagster doesn't provide at notebook latency); don't import a Marimo `.py` as a catalog manifest (it is **source code**; users apply `@nucleus.asset` explicitly). Marimo's pure-`.py` storage helps: one file can be both a notebook and a normal Python module exporting `@nucleus.asset` defs (https://docs.marimo.io/guides/scripts/, https://docs.marimo.io/guides/reusing_functions/).

### §5.4 Error translation contract (PoC #1 implications)

Per v4.1 §6.4: every external exception crossing into `ctx/` MUST translate to `NucleusError` with original preserved as `error.cause`. Marimo surface is small (the wrap shells out), but SQL-cell and `mo.stop` paths touch our domain.

| Marimo exception / event | Raised when | `NucleusError` target |
|---|---|---|
| `MarimoStopError` | `mo.stop(predicate=True, ...)` | **Not an error** — `NucleusUserHalt` (info-level; mirrors Dagster run-cancel). https://docs.marimo.io/api/control_flow/. |
| DuckDB exception inside `mo.sql(...)` | SQL error in cell | **Already translated** by `ctx.sql` (`duckdb.md`). Marimo wrap MUST NOT re-wrap. |
| Reactive-loop / cycle errors | Static analyser detects cycle | `NucleusInvalidNotebookDefinition`. **Class name `# NEEDS VERIFICATION`** — read `marimo/_runtime/runtime.py`. |
| `marimo check` lint failures | Pre-run lint | Bubble up verbatim under `nucleus notebook check`; do **not** translate — dev-tool diagnostics. |
| Subprocess crash (kernel dies) | OOM, segfault | `NucleusInternalError` + subprocess exit code + stderr tail. |

**Verification mandatory at v0.3**: trigger each in a fixture. Reactive-loop entry is **unverified**; log to `docs/internal/research/ai_hallucinations.md` on any drift.

### §5.5 Workbench vs Marimo (v0.2 vs v0.3 boundary)

Per v4.1 §8.1 + §18: **Workbench (v0.2)** = Monaco web IDE (SQL editor + asset graph + run history + simple AI chat); authoritative for **production asset authoring**. **Marimo (v0.3+)** = full reactive notebook for **ad-hoc exploration** ("iterate on a transformation before committing"). They coexist; founder picks per situation — prod-bound assets → Workbench; exploration / one-off / debug → Marimo. Documented in `docs/specs/nucleus_project_anatomy.md` §"Notebooks vs Assets" at v0.3 time.

---

## §6. Performance characteristics

Numbers from docs only; **no Nucleus benchmark yet** — repeat under PoC v0.3 before quoting.

- **Cold start**: `marimo edit` = websocket + kernel subprocess + React frontend. **No official number.** Anecdotal 1-3 s kernel-ready. Relevant to PoC #4 (`nucleus up <10s`) but **not in that path** — `nucleus notebook` is separate. **Never auto-import `marimo` in core CLI startup**; lazy-import inside `experience/marimo_adapter.py`.
- **Memory**: per-notebook kernel process; no documented budget. `mo.sql` results in memory by default; use `output_type=native` (DuckDB lazy relation) for large datasets — https://docs.marimo.io/guides/working_with_data/sql/ §"SQL Output Types".
- **Reactive overhead**: static analysis on every edit (ms range; no published benchmark). Runtime re-executes "only those cells that need to be run" — no whole-notebook re-run.
- **WASM** (https://docs.marimo.io/guides/wasm/ §"Limitations"): 2 GB cap, no threading/multi-proc/PDB. DuckDB+Polars wheels work in Pyodide. Out of scope for v0.3; v0.5+ "share as link" UX bet.
- **Wheel size**: 38.8 MB at 0.23.6 (PyPI bdist_wheel) — bundled React frontend. Relevant to `pip install nucleus[notebook]` UX.

---

## §7. Compatibility with Nucleus pins (2026-05-13)

**The critical section.** Marimo 0.23.6's runtime deps **conflict** with two current Nucleus pins; SQL cells additionally conflict with a third.

| Nucleus dep | Our pin | marimo 0.23.6 requires | Conflict? | Resolution |
|---|---|---|---|---|
| Python | `>=3.11,<3.13` | `>=3.10` | No | OK |
| `msgspec` | `0.18.6` | **`>=0.20.0`** (runtime) | **YES — BLOCKING** | One-component upgrade PR `0.18.6 → 0.20.x` before v0.3. Small surface in Nucleus (`NucleusError`, configs); low-risk. |
| `sqlglot` | `26.0.0` | **`sqlglot[c]>=26.8.0`** (only with `marimo[sql]`) | **YES — BLOCKING for SQL cells** | Upgrade PR `26.0.0 → 26.8.x[c]` (Cython parser). Verify our resolver against 26.8 changelog. |
| `opentelemetry-api` | `1.29.0` | **`~=1.28.0`** (only in `marimo[otel]`) | **YES** for `marimo[otel]` only | **Avoid `marimo[otel]`.** We own OTel via `nucleus.observability/`; Marimo's OTel is for its own kernel-internal traces. |
| `duckdb` | `1.1.3` | `>=1.0.0` (only in `marimo[sql]`) | No | OK |
| `polars[pyarrow]` | `1.18.0` | `>=1.9.0` (only in `marimo[sql]`) | No | Our pin covers `pyarrow` extra. |
| `pyiceberg` | `0.8.1` (`0.9.x` queued per `dlt.md`) | not a runtime dep; supported via UI | No | Opt-in via Data Sources UI, not a runtime pin. |
| `click` | `8.1.7` | `<9,>=8.0` | No | OK |
| `dagster` | `1.9.5` | not required | No | Marimo and Dagster don't interact. |
| Windows wheels | required | published | No | OK |

**ADR sequencing** (v0.3 prerequisites):

1. `msgspec 0.18.6 → 0.20.x` one-component upgrade PR (1-2 days).
2. `sqlglot 26.0.0 → 26.8.x[c]` one-component upgrade PR + smoke test against `ctx.sql` Jinja resolver (1 day).
3. Optional: PyIceberg `0.8.1 → 0.9.x` (queued per `dlt.md` §7; not strictly required for Marimo but aligns v0.3 dep wave).
4. Marimo integration ADR + `nucleus notebook` CLI + `experience/marimo_adapter.py` (~300 LOC).

Without (1) and (2), `pip install marimo[sql]` fails resolution.

---

## §8. Swap-target analysis (v4.1 §9.3)

If Marimo becomes unviable (license pivot, vendor death, perf regression >2x, hostile fork):

| Candidate | License | Cost | Notes |
|---|---|---|---|
| **Jupyter (Lab / Notebook 7)** | BSD-3 | ~500 LOC adapter; loses reactivity | Universal; Workbench (v0.2) would need explicit-reactivity features to compensate. |
| **VS Code notebooks (.ipynb)** | MIT extension | Low — "open the file" | Loses pure-`.py` format; loses reproducibility guarantees. |
| **Hex / Deepnote / Mode** | Proprietary, hosted | N/A | **Reject** — conflicts with OSS-first (v4.1 §2 / §20). |
| **Port Pluto.jl model to Python** | MIT | **High** — multi-KLOC | **Reject** — violates LOC budget (Constraint #8) and "do not build a notebook runtime" (AGENTS.md §4). |
| **No notebook layer** | n/a | Zero | Lose v0.3 differentiation; users fall back to Jupyter outside Nucleus. Acceptable fallback if Marimo dies day-before-launch. |

**Verdict**: Marimo is the only candidate giving reactivity + pure-`.py` storage + native DuckDB/Polars/PyIceberg awareness + Apache-2.0 + active maintenance + NumFOCUS governance. Risk = **low**. v4.1 §8.2 Inspiration table already cites Marimo by name.

**Swap cost if needed**: ~500 LOC, ~3 engineering days for Marimo → Jupyter. Keep `experience/notebook_adapter.py` as a Protocol so swap is a class substitution.

---

## §9. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge; log to `docs/internal/research/ai_hallucinations.md`)

- ❌ `mo.cell(...)` — **fabricated.** Real API is `@app.cell` (on an `App` instance, not the `mo` module). https://docs.marimo.io/api/app/.
- ❌ `mo.iceberg(...)` — **fabricated.** Iceberg via PyIceberg directly: `RestCatalog(...).load_table((...)).to_polars()`. https://docs.marimo.io/guides/working_with_data/sql/ §"Catalogs".
- ❌ `mo.dagster_run(...)` / `marimo.materialize(...)` / `mo.asset(...)` — **fabricated.** No Marimo-Dagster integration. "Materialize"/"asset" are our vocabulary; Marimo's programmatic execution is `App.run()`.
- ❌ `mo.export.iceberg(...)` — **fabricated.** Export targets are `html, pdf, ipynb, script, md, html-wasm, session`. https://docs.marimo.io/guides/exporting/.
- ❌ `mo.sql(query, conn=...)` with explicit `conn` kwarg — **`# NEEDS VERIFICATION`.** Docs show custom connections via cell-scope discovery; kwarg signature inferred, not confirmed.
- ❌ `marimo.kernel(...)` / `marimo.runtime(...)` — **fabricated.** Internal; not public API.

### Real gotchas from official docs

- **No mutation tracking** (https://docs.marimo.io/guides/reactivity/ §"Variable mutations are not tracked"): `df["new_col"] = ...` and `my_list.append(...)` do **not** trigger reactive re-runs. Document in `docs/specs/nucleus_project_anatomy.md` notebook section.
- **Globals must be unique** — every global defined by exactly one cell. Two `@nucleus.asset` defs sharing a function name fail at Marimo's static-analysis stage before reaching Nucleus.
- **`mo.sql` is f-strings.** `{value}` interpolation collides with Jinja `{{ ref(...) }}` (§5.2).
- **`marimo run` vs `marimo edit`** have different runtime semantics; `run` ignores the "On startup"/"On cell change" config knobs (https://docs.marimo.io/guides/configuration/runtime_configuration/).
- **`marimo check` is a separate linter** from our `ruff`. Two linters now; document precedence.
- **`mo.state` is dangerous.** Docs: "In over 99% of cases ... shouldn't use." Do not surface through `ctx`.
- **WASM has no threading / no PDB** (https://docs.marimo.io/guides/wasm/ §"Limitations"). `mo.Thread` code fails in WASM exports.
- **`marimo[otel]` pins `opentelemetry-api ~= 1.28.0`**, conflicting with our `1.29.0`. Do not install (§7).
- **Pre-1.0 versioning (0.x).** API still mobile; 0.23.5 (2026-05-05) and 0.23.6 (2026-05-11) both shipped "🚨 Breaking changes" or correctness fixes per https://github.com/marimo-team/marimo/releases. Pin exact; read changelog on every upgrade.

---

## §10. Decision log

**Why Marimo enters at v0.3, not earlier, not later:**

- **v0.1 (Mo 0-4)**: CLI Hello World. A notebook layer = +38 MB install + extra UX to test + zero contribution to the <30-min beachhead metric (v4.1 §1.5). **Defer.**
- **v0.2 (Mo 4-8)**: Workbench ships (SQL editor + asset graph + AI chat). Covers "GUI to author assets." Marimo here splits attention before Workbench is validated. **Defer.**
- **v0.3 (Mo 14-20)**: Workbench validated; demand shifts to "ad-hoc exploration without committing to an asset definition." Marimo's reactive cells are exactly that. **Ship.**
- **v0.5+**: AI Copilot inside Marimo (reactivity + AI = the unique UX bet — v4.1 §8.2 / `ADR-002-positioning-decision-2026-05.md` §8). Marimo's `marimo pair` agent CLI is reference architecture.
- **Never**: build our own reactive notebook runtime (Constraint #4 / Pillar #2 / AGENTS.md §4).

Integration ADR: `docs/decisions/ADR-NNN-marimo-v03-notebooks.md`. Prerequisites: `msgspec` and `sqlglot` upgrade ADRs (§7).

---

## §11. Next reads when v0.3 work starts

- [ ] **Verify `mo.sql` signature** — read `marimo/_sql/sql.py`; confirm whether engine is kwarg or cell-scope-discovered, plus supported output types. Update §4; log drift in `ai_hallucinations.md`.
- [ ] **Verify reactive-cycle exception class** — read `marimo/_runtime/runtime.py`; confirm §5.4 row.
- [ ] **External-tester field test on §5.2 Option A/B/C** — picks the v0.3 ADR's central design.
- [ ] **Benchmark `marimo edit` kernel cold-start** on a clean MacBook — publish in `docs/compatibility.md`.
- [ ] **Marimo + Dagster reference patterns** — search `marimo/examples` + Discord. Document or note absence.
- [ ] **PyIceberg integration depth** — Marimo's data-sources panel supports `Catalog`. Decide whether `nucleus notebook` pre-registers the Nucleus catalog as default.
- [ ] **Inline-deps story (`marimo[sandbox]`)** — sandbox versions ≠ project pins. Interaction with our pinning policy?
- [ ] **State persistence across kernel restarts** — does `marimo edit` survive `Ctrl+C`? Check live.

---

## §12. Useful links

- https://docs.marimo.io/ — start here.
- https://docs.marimo.io/guides/reactivity/ — read **before** any asset-graph composition thinking.
- https://docs.marimo.io/guides/working_with_data/sql/ — the integration page. **Bookmark.**
- https://docs.marimo.io/api/app/ — `App.run` is the programmatic execution path.
- https://docs.marimo.io/guides/scripts/ — `python notebook.py` semantics.  •  https://docs.marimo.io/guides/wasm/ — for v0.5 "share as link" UX.
- https://github.com/marimo-team/marimo • https://github.com/marimo-team/marimo/releases • https://pypi.org/project/marimo/
- https://marimo.io/discord — community Discord (active; team responsive).  •  https://molab.marimo.io — first-party hosted free service (reference UX for v0.5 Cloud tier).

---

*Last verified: 2026-05-13 against marimo 0.23.6. Re-verify when opening the v0.3 ADR, before pinning, or on any minor bump (0.x → 0.x+1 is currently breaking-allowed pre-1.0). Log any AI-fabricated marimo APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
