# UX Familiarity Audit — Databricks + Snowflake Parity

> Last verified: 2026-05-15 against Nucleus v0.2.0 source tree (Wave 1 staged) + live fetches of Databricks docs (CLI 0.205+, Snowsight, Unity Catalog, Lakeflow Jobs, error-message format) and Snowflake docs (Snowsight, Snowflake CLI, Worksheets, Tasks, name resolution).
> Researcher: Claude Opus 4.7 (Architect-tier acting as Researcher; Gemini 3.1 Pro unavailable in current Cursor surface — fallback per AGENTS.md §11.14).
> Scope: how Nucleus v0.2-v1.0 should *feel* familiar to incoming Databricks / Snowflake users **without borrowing forbidden vocabulary** (AGENTS.md §3, §7, §8). Read-only research; this doc proposes — it does not edit.

---

## TL;DR

1. **The biggest gap is consistency, not coverage.** Nucleus already mirrors most giant-stack patterns at a structural level (catalog browser, command palette, runs view, schedule view, query editor, AI chat). The pain is wording drift: `Catalog` page exists but the row label says `assets` while Snowflake users expect `database.schema.object`; `nucleus runs list` shows `[green]●[/green]` dots but Databricks ships `Succeeded / Failed / Running / Pending / Skipped / Cancelled` words next to them; `nucleus query --format json` is NDJSON while `databricks --output json` is JSON-array. Closing these costs <600 LOC across the v0.2 polish bundle.
2. **CLI verb structure already rhymes.** `nucleus init / up / down / run / ingest / query / version` plus `nucleus runs / schedule / snapshot / workbench` matches the noun-verb pattern Databricks bundle (`bundle init/deploy/run`) and Snowflake CLI (`snow connection add`, `snow sql -q`) users have memorised. Two missing verbs hurt: `nucleus auth env / profiles` (Databricks rhyme — Rec #10) and `nucleus profile add / list / test` (Snowflake rhyme — Rec #2). Both are vocabulary-clean.
3. **Error-format gap is the top risk.** Databricks ships `[ERROR_CONDITION] message ... SQLSTATE: 42P01`. Snowflake ships `000936 (42000): SQL compilation error: line 1 at position 5, ...`. Nucleus ships a 3-line block (Error / Fix / Docs) with `NE3002` only in the docs URL, never in the headline. Adding `[NE3002]` as a leading bracket-tag (Rec #3) gives users one pattern they already grep for, costs ~40 LOC, and is 100% vocabulary-clean.
4. **AI chat panel is the single biggest UX leverage point for v0.3+.** Databricks Genie + Snowflake Cortex Code both put the assistant ALWAYS in the right rail (always-visible chat) so users stop context-switching. Nucleus has the right plumbing (`/api/chat`, `CopilotPanel.tsx`, opt-in privacy gate) — what's missing is making it persistent and routing query results / error messages into it (Rec #11, defer to v0.3).
5. **What we should NOT mirror.** Snowflake's "warehouse" compute primitive (we have no compute primitive — `ctx` runs in-process), Databricks' "cluster" picker (same reason), Snowflake's role-switcher dropdown (we delegate auth to OIDC per Constraint #6, never own roles), Databricks' notebook-first UX (we are SDK + CLI first; Marimo is v0.3+ optional), and any "Marketplace / plugin store" surface (Constraint #2). See §5 for full list.

**v0.2 polish bundle (6 quick wins, total ≈ 600 LOC):** Recs #1, #3, #5, #6, #7, #8 — status word + error-tag prefix + 3-level chip + last-materialised + Cmd-Enter shortcuts + `--format jsonl` alias. Ship before v0.2 tag if Wave 2 timing allows; otherwise v0.2.1.

**Phase distribution:** v0.2 polish = 6 items (~600 LOC) · v0.3 = 6 items (~1.5K LOC) · v0.5 = 3 items (~1.2K LOC) · v1.0+ = explicit defer/reject for 4 items per §5.

---

## Section 1 — Five Pillars vocabulary check

Pillar 4 (AGENTS.md §6) test: *"Are we inventing new vocabulary that doesn't exist in dbt/Dagster/Cursor?"* The current AGENTS.md §7 table holds — every Nucleus term has a dbt/Dagster/Cursor anchor. Spot checks:

| Nucleus term | Databricks equivalent | Snowflake equivalent | Verdict |
|---|---|---|---|
| **asset** | `table` (Unity Catalog) / `pipeline target` (Lakeflow) | `table` / `view` / `dynamic table` | KEEP. Dagster ships `asset` as first-class — we inherit familiarity from Dagster, not from giants. |
| **materialization** | `run` / `pipeline update` | `task run` / `dynamic table refresh` | KEEP. dbt-core ships `materialization` as a core concept. |
| **snapshot** | `version` (Delta time travel) / `clone` | `time travel version` / `clone` | KEEP. Iceberg-native — exactly matches `pyiceberg.Table.snapshots()`. Bonus: avoids Delta's `version` (banned per §7). |
| **contract / check** | `expectation` (DLT) / `constraint` | `constraint` / Data Metric Function | KEEP. dbt + Great Expectations + Dagster all ship these terms. |
| **catalog** | `catalog` (Unity Catalog) | `database` (top of 3-level) | KEEP. Unity Catalog uses the exact word. Snowflake users need a translation tooltip (see Appendix A). |
| **engine** | `Photon` / `Spark` | `virtual warehouse` | KEEP. We deliberately avoid the giants' compute-cluster vocabulary because we have no compute cluster. |
| **ctx** | `dbutils` / `spark` (notebook globals) | `session` | KEEP. Cursor / dbt / Dagster all have a single-letter or short-name session object. |
| **Copilot** | `Genie` / `Databricks Assistant` | `Cortex Code` / `Cortex Analyst` | KEEP. GitHub Copilot is the universal anchor. |
| **graduate** | n/a | n/a | KEEP. Our coined term but maps cleanly to dbt's `dbt build` → warehouse mental model. |

### Terms to add to the watch-list

| Term | Why ban | Replacement |
|---|---|---|
| **warehouse** as compute (`our warehouse`) | Snowflake's `virtual warehouse` is a compute SKU. We use `warehouse_dir` for storage path; Snowflake users will confuse it. | KEEP for Iceberg storage (pyiceberg uses `iceberg.warehouse` too). Add tooltip on `warehouse` in CLI/Workbench: "Iceberg warehouse — local storage path. Not the same as a Snowflake virtual warehouse (compute)." |
| **cluster** | Both Databricks `cluster` and Snowflake `multi-cluster warehouse` mean compute pool. We have zero clusters by design. | Use `engine` (Polars/DuckDB) or `runtime`. |
| **workspace** | Databricks `workspace` = tenant-isolation; Snowflake `account` = same. We have neither. | Use `project` (already canonical — `nucleus_project.yaml`). |
| **dbutils** | Databricks-specific magic global. If a Workbench developer types `dbutils.fs.ls(...)` it should NOT autocomplete. | Use `ctx` exclusively. |
| **dashboard** as primitive (decorator/YAML key) | Both giants ship a Dashboard object. Workbench has a `Dashboard` *page* but no dashboard-as-data-product. | `Dashboard` as page-name OK; defer `@nucleus.dashboard` decorator to v1.0+. |

**Recommendation (no code edit — propose for ADR):** add `warehouse (when used as compute)`, `cluster`, `workspace`, `dbutils` to `scripts/check_vocabulary.py` ban-list with the existing inline-exemption marker support (`<!-- banned-term: warehouse-compute -->`). Zero scan-time impact (regex per-term is O(1)).

---

## Section 2 — Surface-by-surface map

**Gap rating**: 0 = fully familiar to a DB/SF user · 5 = nothing in common.
**Phase**: v0.2 (polish before tag) · v0.3 / v0.5 / v1.0+ (defer) · REJECT (would violate a pillar).
**8-Q**: PASS / PASS-with-caveats / FAIL — applied per AGENTS.md §5.

### 2.1 Top-level navigation

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Sidebar / topnav order | Workspace → Catalog → Compute → SQL Editor → Workflows → ML | Worksheets → Dashboards → Notebooks → Catalog → Data → Marketplace | Dashboard / Assets / Runs / Query / Schedules / Catalog (`TopNav.tsx` line 25-32) | 1 | KEEP order. Add "Sources" between Catalog and Schedules once `nucleus.source` lands. | v0.5 | PASS |
| App identity | "Databricks" wordmark + workspace name | "Snowflake" wordmark + account locator | `nucleus / project_name` with `/` separator | 0 | KEEP — dead-on familiar. | shipped | PASS |
| Project selector | Workspace dropdown | Account-role-warehouse triad | Project dropdown chevron (no list yet) | 2 | Wire to `~/.nucleus/profiles.yaml` once profiles ship (Rec #2). v0.2 stub: list current profile only. | v0.3 | PASS |

### 2.2 Onboarding / first-5-min

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| First screen after up | Workspace homepage + sample notebook + tour | Worksheet with `SELECT 1;` + tour | Workbench Dashboard with hero gradient; user runs `nucleus run example.greeting` | 2 | Dashboard ships a 3-step "Getting started" card when zero runs (Rec #4). | v0.3 | PASS |
| Sample data | `samples.tpch` catalog | `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` | Single `example.greeting` asset | 3 | Ship `assets/tpch/` template variant (`nucleus init --template tpch`) — Rec #13. | v0.3 | PASS |
| Quickstart docs entry | "Get Started" tile | "Quickstart" right-rail | `README.md` 30-second demo + `docs/onboarding/quickstart.md` | 1 | KEEP; surface as a Workbench card on `/` (Rec #4). | v0.3 | PASS |

### 2.3 Catalog browser (3-level namespace)

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Namespace cardinality | 3-level: `catalog.schema.table` | 3-level: `database.schema.object` | 2-level: `<namespace>.<name>` (cli_spec §3.4) | 3 | KEEP 2-level for v0.1/v0.2; light up 3-level when Lakekeeper/Polaris lands (v0.3 per cli_spec NV #6). When 3-level lands, default catalog name should be `default` (rhymes with Snowflake `PUBLIC` and Databricks `main`). | v0.3 | PASS |
| Catalog page columns | Name / Type / Owner / Updated / Tags / Lineage | Name / Created / Owner / Type / Comment / Tags | `key / namespace / has_schedule / has_contract / check_count / dep_count / compute` (`api/catalog.py` line 39-47) | 2 | Re-order to `key / namespace / type / contract / checks / last materialized / dep_count`. Add Last materialized (Rec #6). | v0.2 | PASS |
| Three-level path display | `catalog.schema.table` chip with copy-button | `DATABASE.SCHEMA.TABLE` chip with copy-button | Just `key` rendered (e.g. `raw.users`) — no chip | 3 | v0.2 polish: render as `<chip>{namespace}</chip> · <chip-bold>{name}</chip-bold>` with copy-on-click (Rec #5). | v0.2 | PASS |
| Pin / favourite | Bookmark star | Pin icon | None | 4 | DEFER. v0.5+ when projects routinely have >50 assets. | v0.5 | PASS-with-caveats (Q7: not telemetry-driven yet) |
| Search box | Top-of-page filter input | Top-of-page search | Top-right "Filter assets..." input | 0 | KEEP. | shipped | PASS |
| Tag column | Tags (Unity Catalog) | Tags / classification | None | 4 | DEFER `@nucleus.asset(tags=[...])` to v0.5+. | v0.5 | PASS |

### 2.4 Asset graph / DAG view

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Graph rendering | Lakeflow LR DAG, status-coloured nodes | Tasks graph (vertical/horizontal DAG) | React Flow DAG with topological columns (`AssetDAG.tsx`) | 1 | KEEP layout. Add status colouring on each node (Rec #9). | v0.3 | PASS |
| Click-through to detail | Right-rail panel (keeps DAG visible) | Inspector panel (zoom + sidebar) | Navigate to `/assets/:key` (loses DAG context) | 1 | Switch to right-rail slide-over (Lakeflow pattern) v0.3. | v0.3 | PASS |
| Status legend | Color legend in DAG header | Status icons in worksheet bar | None on DAG | 3 | When status overlay added (Rec #9), include 4-color legend top-right. | v0.3 | PASS |

### 2.5 Run / materialization monitoring

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Status vocabulary | `Queued / Pending / Running / Skipped / Succeeded / Failed / Timed Out / Canceling / Cancelled` | `Running / Succeeded / Failed / Cancelled / Queued` | `success / failed / running / cancelled` (lowercase, dot only — no word) (`runs.py` line 76-82) | 2 | Add the WORD next to the dot — Title Case matches both giants (Rec #1). | v0.2 | PASS |
| Filter chips | Status filter dropdown + tag chips | Status / warehouse / time-range filters | API supports `--status`; no chips UI in `RunsPage.tsx` yet | 3 | Add 5-chip filter row above RunsTable: `All / Succeeded / Failed / Running / Cancelled`. | v0.3 | PASS |
| Tail logs / live updates | "Auto-refresh" toggle; SSE on serverless | Live status updates in Task Run History | `RunLogDrawer.tsx` exists; `nucleus runs tail --follow` polls every 1s | 1 | KEEP. Add Auto-refresh toggle to RunsPage.tsx (~30 LOC). | v0.3 | PASS |
| Time-range picker | "Last 7d / 30d / Custom" dropdown | "Last 14d" + custom range | `--since` ISO flag in CLI; no Workbench picker | 3 | DEFER to v0.5 — full picker. | v0.5 | PASS |
| Trigger column | "Trigger" col: `Manual / Schedule / API / File arrival` | "Run as" + trigger type | `trigger` field in run ledger; surfaced in `runs list` | 0 | KEEP. | shipped | PASS |
| Run ID display | Full UUID + copy button | Snowflake query ID | 8-char prefix + full ID on detail page | 1 | KEEP; add copy-full-ID button on detail page (~10 LOC). | v0.3 | PASS |

### 2.6 Query editor

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Editor pane | Monaco SQL editor with autocomplete | Monaco + autocomplete + Cortex Code | `<textarea>` (`QueryEditor.tsx`); CodeMirror in static SPA | 4 | DEFER Monaco to v0.3 (~400 KB bundle delta hits offline-bundle promise). v0.2 cheaper: keyword highlighter (~100 LOC). | v0.3 | PASS-with-caveats |
| Run / Run All | Run + Run All buttons | Run (at cursor) + Run All | Single Run; multi-statement rejected by CLI v0.1 | 2 | KEEP single-statement v0.2. Add `;`-split + Run All in v0.3. | v0.3 | PASS |
| Result table | Sortable, JSON-expandable, contextual stats | Same | Plain HTML table with sticky header | 3 | v0.3: column-sort + Arrow virtualisation for >1k rows (Rec #14). Skip contextual-stats panel (heavy build, low payoff). | v0.3 | PASS |
| Export results | Download CSV / Open in dashboard | Download CSV/TSV | None in Workbench; CLI has `--format csv` | 2 | v0.3 polish: "Download CSV" link below result (~20 LOC). | v0.3 | PASS |
| Query history | Re-run + filter (24h default) | Same (14d) | None — `nucleus query` runs not in run ledger | 4 | DEFER v0.5; needs query-ledger schema. | v0.5 | PASS |
| Save worksheet | Save / share / fork | Save / share / fork | None — query is ephemeral | 4 | DEFER v0.5+; Marimo (v0.3+) covers Python-notebook save. | v0.5 | PASS |

### 2.7 Schedule view

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Cron + human readable | Cron + "Every day at 12:00" tooltip | CRON shown with `USING CRON` syntax | `nucleus schedule list` shows cron + next-run UTC | 0 | KEEP. | shipped | PASS |
| Next-run preview | "Next run: 2h from now" tooltip | Task run history with "next scheduled" | `nucleus schedule preview <key> --count N` (default 3) | 0 | KEEP. | shipped | PASS |
| On / Off toggle | Pause/resume button | `ALTER TASK ... RESUME / SUSPEND` | Deferred to v0.2 active-scheduling daemon (NE5008 in v0.1.1) | 2 | Wave 2 P0-1 closes this. Mirror Databricks pause-icon when shipping Workbench Schedules page. | v0.3 | PASS |
| Schedule timeline | "Next 7 runs" timeline strip | Task run history bar chart | `.sched-day` strip styling exists in static SPA but unwired | 2 | v0.3: wire 7-day calendar with dots from `nucleus schedule preview` (~100 LOC). | v0.3 | PASS |

### 2.8 Copilot / AI chat

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Chat panel position | Genie: persistent right rail with toggle | Cortex Code: persistent right rail | `CopilotCard.tsx` in Dashboard right column only; `CopilotPanel.tsx` not globally reachable | 2 | v0.3: persistent right-rail with `Cmd-J` toggle (Rec #11). | v0.3 | PASS |
| Chat persistence | Chats saved per workspace | History per Cortex Code session | Single-turn only (cli_spec §3.8 out-of-scope) | 4 | DEFER multi-turn to v0.3, history to v0.5. | v0.5 | PASS |
| Provider selector | Genie uses Databricks-hosted models only | Cortex Code uses Snowflake-managed models only | `--provider anthropic\|openai\|ollama` flag (cli_spec §3.8) | 0 (we WIN) | KEEP and surface Ollama-default story prominently — giants can't bring own model. | shipped | PASS |
| Chat → query pipeline | "Insert SQL into editor" button | "Insert into worksheet" | None | 4 | v0.3: when on `/query`, Copilot SQL responses get an "Insert" button (~50 LOC). | v0.3 | PASS |
| Cost meter | Tokens consumed per message | Credits consumed | Pre-flight cost ceiling (NE4005) | 1 | KEEP. After reply, surface `Used $0.0034` chip (~20 LOC). | v0.3 | PASS |

### 2.9 CLI command tree + flag naming

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Verb structure | `databricks <noun> <verb> [args]` (e.g. `bundle deploy`, `jobs run-now`) | `snow <noun> <verb> [args]` (e.g. `connection add`, `sql -q`) | Hybrid: `nucleus <verb>` (v0.1: init/up/down/run/ingest/query/version/list/chat) + `nucleus <noun> <verb>` (v0.2+: runs list, schedule preview, snapshot list, workbench start) | 1 | KEEP hybrid. The 7 frozen v0.1 verbs are familiar (`init` like git, `up`/`down` like docker compose); v0.2 noun-verb groups rhyme with both giants. | shipped | PASS |
| `--profile` flag | `--profile <name>` / `-p` | `--connection <name>` / `-c` | `--profile <name>` / `-p` (cli_spec §6) | 0 | KEEP — exact Databricks match. Tooltip for Snowflake users: "Like `--connection`". | shipped | PASS |
| `--format` flag | `--output json\|text` | `--format json\|table\|csv\|plain` | `--format text\|json\|csv` / `-f` | 1 | KEEP. Text and json overlap perfectly. NDJSON divergence flagged in Rec #8. | shipped | PASS |
| `--quiet` / `-q` | `--no-banner` (uncommon) | `--silent` (some) | `--quiet` / `-q` | 1 | KEEP. Industry-standard. | shipped | PASS |
| `--verbose` / `-v` | `--debug` | `--verbose` (some) | `--verbose` / `-v` (prints `cause` class + stack) | 1 | KEEP. | shipped | PASS |
| `auth` subcommand | `databricks auth env / profiles / login / logout / token` | `snow connection add / list / test / set-default` | None — v0.1/v0.2 has no auth surface | 4 | When OIDC + Lakekeeper land (v0.3): ship `nucleus auth env / profiles` matching Databricks names exactly (Rec #10). | v0.3 | PASS |
| `bundle` / `deploy` | `databricks bundle init / deploy / run / destroy` | n/a | None | n/a | REJECT — we have no remote workspace. v1.0+ Cloud may add `nucleus deploy` (out of OSS scope). | reject | FAIL Q2 |
| `-h` / `--help` | Yes | Yes | Yes (Typer default) | 0 | KEEP. | shipped | PASS |
| Tab completion | `databricks completion <shell>` | `snow completion install` | Disabled (`add_completion=False` in `cli/main.py` line 80) | 3 | v0.3: enable Typer's bundled completion (Rec #12). | v0.3 | PASS |

### 2.10 Output formatting

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Table renderer | Plain bordered table | Plain table; auto-width | Rich tables (`rich==13.9.4`) | 0 | KEEP. Rich gives terminal beauty both giants lack. | shipped | PASS |
| JSON output | `--output json` returns ARRAY | `--format json` returns ARRAY | NDJSON (one JSON per line) (cli_spec §5.2) | 3 | KEEP NDJSON — pipe-friendly for `jq` + MCP. Add `--format jsonl` alias (Rec #8). | v0.2 | PASS |
| Progress bars | Rich CLI bars | Plain `█` chars | Rich `Progress` bars >2s; `--no-progress` for CI | 0 | KEEP. | shipped | PASS |
| Color | Auto-disable in non-TTY + `NO_COLOR` env | Same | Same | 0 | KEEP. Add auto-disable in `CI=true` (~5 LOC). | v0.2 | PASS |

### 2.11 Error message format

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Error tag in headline | `[ERROR_CONDITION]` prefix (e.g. `[TABLE_OR_VIEW_NOT_FOUND]`) | `nnnnnn (sqlstate): message` (e.g. `000936 (42000): SQL compilation error`) | `Error: <user_message>` (NE-code only in URL) | 3 | v0.2 polish: prefix headline with `[NE3002]` so the code is greppable + searchable (Rec #3). | v0.2 | PASS |
| SQLSTATE field | Yes — 5-char SQLSTATE per ANSI | Yes — same | None | 4 | REJECT for v0.2-v1.0 — adds zero user value when user-message + fix-hint already do the job. | reject | FAIL Q2 |
| Fix hint | "Verify spelling..." inline | Inline hints in some errors | Dedicated `Fix:` line | 0 (we WIN) | KEEP. Three-block format BETTER than both giants. | shipped | PASS |
| Docs URL | Some errors link `docs.databricks.com/error-messages/` | None | Always `Docs: <url>` to `nucleus.dev/errors/<slug>` | 0 (we WIN) | KEEP. Massive UX advantage. | shipped | PASS |
| Stack-trace in `--verbose` | `--debug` shows | `--verbose` shows | `--verbose` prints `cause` class + stack | 0 | KEEP. | shipped | PASS |

### 2.12 Snapshot history / time-travel / lineage / cost / RBAC / connections / notebooks / palette

Compressed for size; details in `nucleus_cli_spec.md`, `nucleus_architecture_v4.1.md` §12.

| Surface | Databricks | Snowflake | Nucleus current | Gap | Rec | Phase | 8-Q |
|---|---|---|---|---|---|---|---|
| Snapshot list | `DESCRIBE HISTORY <table>` | `SHOW VERSIONS / TIME TRAVEL` | `nucleus snapshot list / restore` deferred to v0.5 (cli_spec §4.1) | 4 | KEEP. Workbench AssetDetailPage v0.3 shows snapshot list from run ledger. | v0.5 | PASS |
| Branch / tag | Delta CLONE | Zero-copy CLONE | `nucleus snapshot branch / tag create / delete` exists v0.2 (ADR-028) | 0 (we WIN) | KEEP. Iceberg-native branch + tag is a Nucleus-only local capability. | shipped | PASS |
| Asset upstream/downstream | Unity Catalog lineage panel | Access History query lineage | `AssetDetailsPanel.tsx` has deps; AssetDAG renders graph | 1 | Add upstream/downstream chips to AssetDetailPage v0.3 (~50 LOC) — Rec #15. | v0.3 | PASS |
| Column-level lineage | Unity Catalog column lineage GA | Snowflake Horizon column lineage | Deferred v0.5+ (sqlglot per v4.1 §12.4) | 4 | KEEP planned. v0.5+ via OpenLineage column-lineage facet. | v0.5 | PASS |
| Per-asset cost meter | DBU usage per pipeline | Credit usage per task / warehouse | Deferred v0.5+ | 4 | DEFER alongside OTel telemetry rollup. | v0.5 | PASS |
| Role switcher | Role + workspace dropdown | Role + warehouse dropdown | None — Constraint #6 delegates to OIDC | 5 | REJECT mirroring at our layer. v0.3+: "Signed in as: <user@org>" only. | reject | FAIL Q3 |
| Grants UI | Unity Catalog Grants tab | "Privileges" panel | None | 5 | REJECT same reasoning. v1.0+ may add read-only "Effective access" panel. | reject | FAIL Q3 |
| Add connection | `databricks configure` (interactive) | `snow connection add` | None — `nucleus_project.yaml` has `profiles.<name>` blocks but no command | 3 | v0.3: `nucleus profile add / list / use / test` (Rec #2). Vocabulary clean. | v0.3 | PASS |
| Notebook UX | Native Databricks notebooks | Snowflake Notebooks (Python + SQL) | None — Marimo deferred v0.3+ | 5 | KEEP DEFER. Marimo at v0.3+ via `nucleus enable marimo` opt-in. | v0.3 | PASS |
| Magic commands | `%sql / %md / %fs / %pip` | `!sql / !notebook` | None | 5 | REJECT. Magic commands are notebook-only artefact; we are SDK-first. Marimo uses Python-native cells. | reject | FAIL Q3 |
| Cmd-K palette | None (DB lacks one) | None native (browser only) | `Cmd-K` / `Ctrl-K` / `/` opens CommandPalette | 0 (we WIN) | KEEP — Cursor-style touch DB/SF lack. Surface louder in onboarding. | v0.2 | PASS |
| `Cmd-Enter` to run query | Yes | Yes | None in Workbench `/query` | 3 | v0.2 polish: wire `Cmd-Enter` / `Ctrl-Enter` (~15 LOC) — Rec #7. | v0.2 | PASS |
| `?` for shortcut help | Built-in cheatsheet | Cheatsheet in worksheet menu | None | 2 | v0.2 polish: `?` opens 4-row modal (~30 LOC) — Rec #7. | v0.2 | PASS |
| Hover help / docs deep-link | Tooltips with docs link | `?` icon top-right with deep-links | Sparse — `Docs: <url>` in errors only | 3 | v0.3: `<Tooltip>` component on column headers; TopNav `?` icon → docs (~80 LOC). | v0.3 | PASS |

---

## Section 3 — Top 15 actionable recommendations

Sorted by phase + impact. Each gated against AGENTS.md §5 8 questions; only PASS items get a v0.2/v0.3 phase. All 15 pass vocabulary check (no forbidden term introduced).

### Rec 1 — Status word next to dot in `nucleus runs list`

- **Surface**: CLI + Workbench `RunsTable.tsx`. **Current**: coloured dot only (no word) per `runs.py` line 76-82 + 196.
- **Familiar equivalent**: Like Databricks Lakeflow Jobs status column (`Succeeded / Failed / Running`) and Snowflake Task Run History.
- **Change**: In `runs.py` line 196 render `f"{_dot(r.status)} {r.status.title():<10}"` instead of bare dot. Add Status column to RunsTable.tsx with same Title-Case word.
- **Impact**: Users tail logs in CI / Slack and read status without ANSI colour interpretation. Big accessibility win.
- **Effort**: S (~30 LOC). **Phase**: v0.2 polish. **8-Q**: PASS (Q2 beachhead, Q4-Q6 trivial, Q7 PoC #5 sketch already requested).
- **Files**: `src/nucleus/cli/commands/runs.py` (3 lines), `src/nucleus/workbench/frontend/src/components/RunsTable.tsx` (1 column).
- **Acceptance**: A Databricks user runs `nucleus runs list` and identifies success/failure without checking a legend.

### Rec 2 — `nucleus profile` command group

- **Surface**: CLI. **Current**: `--profile <name>` flag exists (cli_spec §6) but no command to add/list/test profiles. v0.1 raises `NucleusInternalError` for `--profile other` (`cli/main.py` line 670-675).
- **Familiar equivalent**: Like `databricks auth profiles`, `databricks auth env --profile`, `snow connection list / add / test`.
- **Change**: New `src/nucleus/cli/commands/profile.py` with `add / list / show / test / use` subcommands. Storage: `nucleus_project.yaml` `profiles.<name>` blocks (already in cli_spec §7). `add` is interactive (prompt for catalog / storage URL / credentials env-var).
- **Impact**: Closes the #1 missing surface for Snowflake CLI converts. Lights up dev/staging/prod toggling without YAML editing by hand.
- **Effort**: M (~250 LOC + tests). **Phase**: v0.3 (gated on Lakekeeper/Polaris REST catalog — without it, profile diffs only swap `warehouse_dir`). **8-Q**: PASS (Q3 wraps Typer prompts, Q5 local-prod identical, Q6 GREEN).
- **Files**: `src/nucleus/cli/commands/profile.py` (new), `src/nucleus/cli/main.py` (~5 lines), `nucleus_cli_spec.md` (new section).
- **Acceptance**: A Snowflake user runs `nucleus profile add staging`, answers prompts; `nucleus profile list` shows it; `nucleus run --profile staging asset.x` works.

### Rec 3 — `[NE3002]` error-code prefix in headline

- **Surface**: Error format (CLI + Workbench). **Current**: NE-code only in `Docs:` URL slug per cli_spec §5.4. `_exit_nucleus_error` in `cli/main.py` line 98-114 emits `Error: <user_message>` with no NE-code visible.
- **Familiar equivalent**: Like Databricks `[TABLE_OR_VIEW_NOT_FOUND] ...` and Snowflake `000936 (42000): SQL compilation error`. Both giants put the machine-readable identifier FIRST.
- **Change**: In `_exit_nucleus_error` change line 110 to `typer.echo(f"Error [{err.error_code}]: {err.user_message}", err=True)` (`error_code` is the ClassVar in `errors.py`). Mirror in `runs.py` line 50-56 + `schedule.py` + `snapshot.py` + `chat.py`. Update `cli_spec §5.4` example block.
- **Impact**: Users grep `NE3002` in chat / docs / Stack Overflow without parsing the URL. Closes the "user-friendly" (we win) vs "machine-greppable" (giants win) gap.
- **Effort**: S (~40 LOC across 5 files + spec doc + 1 snapshot test). **Phase**: v0.2 polish. **8-Q**: PASS (Q4 unaffected, Q6 negligible, Q7 founder anti-over-engineering "no black-box surfaces").
- **Files**: `src/nucleus/cli/main.py`, `src/nucleus/cli/commands/{runs,schedule,snapshot,chat}.py`, `nucleus_cli_spec.md` §5.4, `tests/cli/test_exit_codes.py`.
- **Acceptance**: A Databricks user runs `nucleus run nonexistent.asset`, sees `Error [NE3002]: Asset 'nonexistent.asset' not found` and recognises the bracket pattern.

### Rec 4 — Workbench Dashboard "Getting started" 3-step card

- **Surface**: Workbench `/`. **Current**: Hero gradient + 3-column grid; no onboarding hint when project has zero runs (`DashboardPage.tsx`).
- **Familiar equivalent**: Like Snowsight "Try a sample query" tour, Databricks "Get started with sample data" tile.
- **Change**: When `RecentRunsCard` returns 0 records, swap for `GettingStartedCard` listing: 1) `nucleus run example.greeting`, 2) `nucleus query "SELECT * FROM example.greeting"`, 3) `Open the Catalog →`. Each line copy-clickable.
- **Impact**: New users land on Dashboard, see exactly what to do — no need to leave for docs.
- **Effort**: M (~120 LOC). **Phase**: v0.3 (after Rec #2 so `nucleus profile add` is also reachable). **8-Q**: PASS (Q2 directly serves the 30-min metric).
- **Files**: `src/nucleus/workbench/frontend/src/components/GettingStartedCard.tsx` (new), `src/nucleus/workbench/frontend/src/pages/DashboardPage.tsx` (conditional swap).
- **Acceptance**: A fresh `nucleus init demo && nucleus up && nucleus workbench start` — first thing visible is the 3-step card.

### Rec 5 — Catalog page namespace column + 3-level path display

- **Surface**: Workbench `/catalog`. **Current**: CatalogPage shows `key / namespace / has_schedule / ...` — namespace is a column but `key` cell shows the dotted form.
- **Familiar equivalent**: Snowsight Databases explorer 3-level tree (`db > schema > object`); Unity Catalog Catalog Explorer 3-level tree.
- **Change**: Render `key` as `<chip muted>{namespace}</chip><chip>·</chip><chip bold>{name}</chip>` with copy-on-click full key. Add a "Type" column (`asset / source asset` per AGENTS.md §7).
- **Impact**: Snowflake users immediately recognise the 3-level pattern even though we're 2-level (chip layout signals "hierarchy here").
- **Effort**: S (~80 LOC). **Phase**: v0.2 polish. **8-Q**: PASS.
- **Files**: `src/nucleus/workbench/frontend/src/pages/CatalogPage.tsx`, `src/nucleus/workbench/frontend/src/components/NamespacePath.tsx` (new).
- **Acceptance**: A Snowflake user opens Catalog, scans rows, identifies which assets belong to `raw` vs `staging` namespaces in <5 seconds.

### Rec 6 — Last-materialised timestamp in Catalog table

- **Surface**: Workbench `/catalog` + `/api/catalog`. **Current**: No timestamp visible per `api/catalog.py` line 39-47. Data exists via run ledger.
- **Familiar equivalent**: Unity Catalog "Updated" column; Snowsight "Last Modified" column.
- **Change**: Add `last_materialized` field to `_catalog_row()` (lookup latest run from `RunLedger.list(asset_key=key, limit=1)`). Render as relative time ("3h ago") with absolute on hover.
- **Impact**: Closes the "is this asset stale?" question that both giants make answerable in one glance.
- **Effort**: M (~60 LOC API + 30 LOC frontend; relative-time helper bundled). **Phase**: v0.2 polish (depends on RunLedger being read-stable). **8-Q**: PASS.
- **Files**: `src/nucleus/workbench/api/catalog.py`, `src/nucleus/workbench/frontend/src/pages/CatalogPage.tsx`, `src/nucleus/workbench/frontend/src/lib/relativeTime.ts` (new).
- **Acceptance**: A Databricks user opens Catalog after running 3 assets, sees the staleness column, identifies the most-recently-updated asset.

### Rec 7 — `Cmd-Enter` to run query + `?` shortcut help modal

- **Surface**: Workbench `/query` + global. **Current**: `Cmd-K`/`Ctrl-K`/`/` open command palette (`App.tsx` line 82-92); no query-specific shortcuts; no help cheatsheet.
- **Familiar equivalent**: Snowsight `Cmd-Enter` runs query at cursor; Databricks SQL Editor same; both surface a `?` cheatsheet.
- **Change**: In `QueryPage.tsx` capture `(Cmd|Ctrl)+Enter` and trigger Run. Add `?` global handler that opens `<KeyboardHelpModal>` listing `Cmd-K · open palette / · open palette Cmd-Enter · run query Esc · close ? · this help`.
- **Impact**: SQL writers from both giants reflexively press Cmd-Enter; meeting them halfway closes the "feels native" gap.
- **Effort**: S (~50 LOC). **Phase**: v0.2 polish. **8-Q**: PASS.
- **Files**: `src/nucleus/workbench/frontend/src/App.tsx`, `src/nucleus/workbench/frontend/src/pages/QueryPage.tsx`, `src/nucleus/workbench/frontend/src/components/KeyboardHelpModal.tsx` (new).
- **Acceptance**: A Snowflake user in QueryPage types SQL, presses Cmd-Enter, the query runs.

### Rec 8 — `--format jsonl` alias + clearer JSON output docs

- **Surface**: CLI. **Current**: `--format json` returns NDJSON per cli_spec §5.2; both giants ship JSON-array as default for their `--format json`.
- **Familiar equivalent**: jq's ecosystem standardised on `.jsonl` extension; Snowflake CLI distinguishes `json` (array) vs streaming.
- **Change**: Add `--format jsonl` as a synonym of `--format json` (NDJSON behaviour preserved). Update `--help`: `text | json (NDJSON, one record per line) | jsonl (alias) | csv`. Document divergence in cli_spec §5.2.
- **Impact**: A DB/SF user piping `nucleus runs list --format json | jq .` won't be confused — `jsonl` alias signals format up front.
- **Effort**: S (~15 LOC + 1 spec sentence). **Phase**: v0.2 polish. **8-Q**: PASS.
- **Files**: `src/nucleus/cli/main.py` (run + query + version commands' `format_` validation), `src/nucleus/cli/commands/runs.py`, `nucleus_cli_spec.md` §5.2.
- **Acceptance**: `nucleus runs list --format jsonl | jq .` works identically to `--format json`.

### Rec 9 — Status overlay on AssetDAG nodes

- **Surface**: Workbench `/assets` (DAG view). **Current**: AssetDAG nodes are uncoloured (`AssetDAG.tsx`); selected node gets glow only.
- **Familiar equivalent**: Lakeflow Jobs Graph View (status-coloured task nodes — green/red/grey/yellow); Snowflake Tasks graph similar.
- **Change**: Pass `status` field to each node (read latest run for asset key from RunLedger). Apply status-coloured 2px border (green=Succeeded, red=Failed, yellow=Running, grey=never run). Add a 4-row legend above the DAG.
- **Impact**: At-a-glance pipeline health — same pattern as both giants. Massive UX win for first-time DAG view.
- **Effort**: M (~150 LOC). **Phase**: v0.3. **8-Q**: PASS.
- **Files**: `src/nucleus/workbench/frontend/src/components/AssetDAG.tsx`, `src/nucleus/workbench/api/assets.py` (add `last_run_status` to AssetDTO).
- **Acceptance**: A Lakeflow user opens AssetsPage, glances at DAG, identifies which assets are healthy.

### Rec 10 — `nucleus auth env / profiles` (when OIDC lands v0.3)

- **Surface**: CLI. **Current**: No `auth` subcommand. Per cli_spec §12: "No `nucleus auth <subcommand>` — no custom auth per Constraint #6". The spec forbids _owning_ auth, not _surfacing_ delegation.
- **Familiar equivalent**: `databricks auth env --profile <name>`, `databricks auth profiles`, `databricks auth login` (OIDC flow).
- **Change**: When OIDC delegation lands in v0.3 (Lakekeeper / Polaris REST catalog), add `nucleus auth env / profiles / login / logout / token` subcommands that delegate to the configured OIDC provider — never owning credentials, only proxying. Mirrors Databricks naming exactly.
- **Impact**: Closes "where do I configure my Lakekeeper token?" question. Familiar verb tree.
- **Effort**: M (~200 LOC for subcommand surface + tests; OIDC flow itself separate scope). **Phase**: v0.3 (gated on REST catalog). **8-Q**: PASS (Q3 we wrap an OIDC client, Q5 delegation identical local + cloud).
- **Files**: `src/nucleus/cli/commands/auth.py` (new), `src/nucleus/cli/main.py` (~5 lines), `nucleus_cli_spec.md` §12 (clarify "owning identity" vs "surfacing OIDC delegation").
- **Acceptance**: A Databricks user runs `nucleus auth profiles` and gets the same shape of output as `databricks auth profiles`.

### Rec 11 — Persistent CopilotPanel right-rail with Cmd-J toggle

- **Surface**: Workbench (global). **Current**: `CopilotCard.tsx` is in Dashboard right column only; `CopilotPanel.tsx` exists but isn't globally reachable.
- **Familiar equivalent**: Genie persistent right rail in Databricks; Cortex Code persistent right rail in Snowsight. Both giants treat AI as always-on.
- **Change**: Make CopilotPanel a global slide-over (300-400px right-rail) with `Cmd-J`/`Ctrl-J` toggle. When user is in `/query`, route Copilot SQL responses to an "Insert" button that fills the editor. When user is on `/assets/:key`, auto-inject the asset key into chat context.
- **Impact**: AI chat goes from "feature" to "ambient assistant" — closes the perceptual gap with both giants.
- **Effort**: L (~400 LOC — global state in `useUIStore`, slide-over component, context injection per route). **Phase**: v0.3. **8-Q**: PASS-with-caveats (Q3 wraps LiteLLM, Q4-Q6 OK; caveat on Q7: no telemetry yet — poll PoC #5 testers).
- **Files**: `src/nucleus/workbench/frontend/src/components/CopilotPanel.tsx` (rewrite), `src/nucleus/workbench/frontend/src/App.tsx` (mount globally), `src/nucleus/workbench/frontend/src/pages/QueryPage.tsx` (Insert hook).
- **Acceptance**: A Snowflake user presses Cmd-J on any page, panel slides in; they ask "select all from raw.users", receive SQL, click Insert, QueryPage editor populates.

### Rec 12 — Tab completion (`nucleus completion bash|zsh|fish`)

- **Surface**: CLI. **Current**: Disabled (`add_completion=False` in `cli/main.py` line 80).
- **Familiar equivalent**: `databricks completion bash`, `snow completion install`. *(NEEDS VERIFICATION: Databricks completion command name — see §NV item 1.)*
- **Change**: Flip `add_completion=True` and document in onboarding. Typer's bundled completion handles most heavy lifting; we add a custom completer for `nucleus run <key>` that lists registered asset keys.
- **Impact**: Zero-friction tab-complete for `nucleus run <Tab>` → list of asset keys, `nucleus runs <Tab>` → `list show cancel tail`. DB/SF muscle memory works.
- **Effort**: S (~10 LOC for the flip + ~50 LOC for asset-key completer). **Phase**: v0.3. **8-Q**: PASS.
- **Files**: `src/nucleus/cli/main.py` (one boolean flip + completer), `docs/onboarding/quickstart.md` (one section).
- **Acceptance**: After install, a fresh shell user types `nucleus runs <Tab>` and sees `list show cancel tail`.

### Rec 13 — `nucleus init --template tpch` sample-data variant

- **Surface**: CLI + onboarding. **Current**: Only `--template default` ships, with single `example.greeting` asset (`cli/main.py` line 132).
- **Familiar equivalent**: `samples.tpch` in Databricks Unity Catalog; `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` shared by default in every Snowflake account.
- **Change**: Bundle a `tpch_sf001` template with `customer.csv` (1500 rows), `orders.csv` (15k rows), `lineitem.csv` (60k rows) totalling ≈ 5 MB. Three `@nucleus.asset` definitions in `assets/tpch.py`. CLI: `nucleus init --template tpch demo`.
- **Impact**: Demo data immediately runnable. Critical for "first impressions" — both giants do this. PoC #5 testers asked for sample data per `poc/p5_beachhead/RECRUITMENT.md`.
- **Effort**: M (~300 LOC — template files + cli/main.py edits + 1 test). **Phase**: v0.3. **8-Q**: PASS (Q2 directly serves beachhead).
- **Files**: `src/nucleus/templates/tpch_sf001/*` (new tree ~10 files), `src/nucleus/cli/main.py` (extend `_TEMPLATE_KEYS`), test.
- **Acceptance**: `nucleus init --template tpch demo && cd demo && nucleus up && nucleus run tpch.lineitem` — completes <60 s.

### Rec 14 — Workbench column-sort + Arrow-table virtualization

- **Surface**: Workbench `/query` result table. **Current**: Plain HTML table (`static/index.html` line 196-208).
- **Familiar equivalent**: Snowsight result table sortable + virtualized (1M rows scrollable); Databricks SQL Editor same.
- **Change**: In QueryPage.tsx swap result table for `react-table` v8 (TanStack — already a transitive dep through Workbench frontend). Wire column-sort + row virtualization for >1k results.
- **Impact**: First-time SQL users with even 10k rows get a smooth scroll experience; matches giant-stack feel.
- **Effort**: M (~300 LOC + bundle delta ~28 KB gzipped). **Phase**: v0.3. **8-Q**: PASS-with-caveats (Q5 offline-bundle promise per ADR-016 §3 Fork B; ~28 KB gzipped acceptable).
- **Files**: `src/nucleus/workbench/frontend/src/pages/QueryPage.tsx`, `package.json` (add `@tanstack/react-table`).
- **Acceptance**: A Snowflake user runs a 10k-row query, scrolls smoothly, sorts a column.

### Rec 15 — Workbench AssetDetailPage upstream/downstream chips + snapshot list

- **Surface**: Workbench `/assets/:key`. **Current**: `AssetDetailsPanel.tsx` exists but `AssetDetailPage.tsx` is sparse; deps in data via `defn.deps` but not visualised.
- **Familiar equivalent**: Unity Catalog asset detail (Lineage tab + History tab); Snowsight table detail with "Used by" + "Depends on" + Time Travel tabs.
- **Change**: AssetDetailPage gets two new sections — (a) Lineage chips: `Upstream → ` clickable / `Downstream → ` clickable; (b) Snapshot history table (read RunLedger entries with `snapshot_id` non-null) with snapshot ID + timestamp + row count.
- **Impact**: Closes the "where does this data come from / who uses it" loop that both giants make a 1-click answer.
- **Effort**: M (~250 LOC). **Phase**: v0.5 (after Rec #9 status overlay so chips colour-match). **8-Q**: PASS.
- **Files**: `src/nucleus/workbench/frontend/src/pages/AssetDetailPage.tsx`, `src/nucleus/workbench/api/assets.py` (extend with snapshot-list endpoint).
- **Acceptance**: A Unity Catalog user opens any asset, sees upstream chips, clicks one, navigates to the upstream's detail page.

---

## Section 4 — Phase distribution

| Phase | Count | LOC | Items |
|---|---|---|---|
| **v0.2 polish** (ship before / with v0.2 tag) | 6 | ~600 | Rec 1 (status word), Rec 3 ([NE-code] prefix), Rec 5 (catalog 3-level chip), Rec 6 (last-materialised), Rec 7 (Cmd-Enter + ? help), Rec 8 (`--format jsonl` alias) |
| **v0.3** (Wave 2-4 candidates) | 6 | ~1500 | Rec 2 (`nucleus profile`), Rec 4 (Getting Started card), Rec 9 (DAG status overlay), Rec 10 (`nucleus auth`), Rec 12 (tab completion), Rec 13 (TPC-H template) |
| **v0.5** (later) | 3 | ~1100 | Rec 11 (persistent Copilot panel), Rec 14 (sortable virtualised table), Rec 15 (lineage chips + snapshot history) |
| **v1.0+ defer** (mentioned in §2; not in top-15) | — | — | Pin/favourite (§2.3), tags column, save worksheet, contextual stats panel, time-range picker |
| **REJECT** (would violate a pillar) | — | 0 | SQLSTATE field (§2.11), `nucleus deploy` (§2.9), role-switcher (§2.12), notebook magic commands (§2.12) |

**LOC budget impact**: v0.2 polish bundle adds ~600 LOC, well within the v0.2 ceiling. Per `docs/budget_history.md`, Wave 1 closed at <80% of phase ceiling; this bundle stays GREEN.

---

## Section 5 — What we should NOT mirror

These patterns exist in Databricks/Snowflake and would be tempting to copy. Per the 8-Question Gate (AGENTS.md §5) each FAILS at least one question.

### 5.1 Notebook-first UX

**Pattern**: Databricks Workspace built around notebooks; Snowflake Snowsight pushes Worksheets first.
**Why we reject**: Pillar 5 (graduates users out, not in). Notebooks encode no graduation path — code lives in a remote runtime, not Git. We are SDK + CLI + Workbench in that order. Marimo (v0.3+) gives users who want notebook UX the option, but it's a `nucleus enable marimo` opt-in, not a default surface. **Pillar violated**: 4 (we'd invent notebook vocabulary like `cell` / `magic` that Cursor/dbt/Dagster don't ship).

### 5.2 Cluster / virtual-warehouse picker

**Pattern**: Both giants front-load a compute-pool picker — Databricks "Cluster" dropdown, Snowflake "Warehouse" dropdown.
**Why we reject**: We have zero compute pools. `ctx` runs in-process. Adding a fake picker would lie to the user. **Pillar violated**: 1 (introducing an unused UI element hurts UX), 5 (cluster-management is what Databricks DOES — yielding to giants means deferring this entirely).

### 5.3 Role / persona switcher

**Pattern**: Snowflake's "current role" dropdown (`SYSADMIN / ANALYST / ACCOUNTADMIN`); Databricks workspace personas.
**Why we reject**: AGENTS.md Constraint #6 (no custom auth — always delegate to OIDC). The IdP owns role-switching. Adding our own re-implements what Authentik/Keycloak/Okta already do. **Pillar violated**: would force us to BUILD what we promised to wrap.

### 5.4 Plugin / connector marketplace

**Pattern**: Databricks Marketplace; Snowflake Marketplace.
**Why we reject**: AGENTS.md Constraint #2 (no public plugin SDK in v1). `nucleus enable <feature>` per cli_spec §4.4 is the bounded opt-in mechanism — not a marketplace. **Pillar violated**: would invite community-maintained plugins we cannot govern, breaking Constraint #2 and the 30K LOC ceiling.

### 5.5 Dashboard-as-data-product

**Pattern**: Databricks Dashboards / SQL Dashboards; Snowsight Dashboards.
**Why we reject**: We're not a BI vendor. The Workbench Dashboard *page* is fine; a `@nucleus.dashboard` decorator is not. BI lives in Tableau / Power BI / Streamlit / Marimo. **Pillar violated**: Pillar 5 (we yield this to the BI ecosystem).

### 5.6 Job branching / looping / dynamic task graph

**Pattern**: Databricks Lakeflow Jobs supports "If/else" task type, "For each" task type, dynamic task lists.
**Why we reject**: The asset model is declarative. If users need imperative control flow they reach for Dagster's escape-hatch (`nucleus dagit` — see ADR-018) or write Python. Adding Nucleus-native branching primitives re-invents Dagster's `Definitions`. **Pillar violated**: 3 (no custom scheduler — Constraint #3).

---

## Section 6 — Risks

### Risk 1 — "Databricks Lite" framing trap

**Risk**: As we mirror more giant-stack UX patterns, copy-writing drift could land us in marketing language like "Databricks for laptops" or "Snowflake without the cloud". Both are forbidden per AGENTS.md §8. The vocabulary checker catches obvious cases (`Databricks killer`, `Spark killer`) but more subtle drift like "...feels like Snowsight" in onboarding copy would pass the regex.
**Mitigation**: Add a soft watch-list to `scripts/check_vocabulary.py` (warn-only, not fail) for phrases like `like Databricks`, `like Snowflake`, `lite version of`, `mini-Snowflake`. Reviewer judges intent. Reference: AGENTS.md §8.

### Risk 2 — Trademark / look-alike

**Risk**: Mirroring icon palettes (e.g. Databricks' red flame logo or Snowflake's snowflake) or color schemes could trigger trademark concerns. Mirroring KEYBOARD shortcuts and command structures is fair use (functional, not creative).
**Mitigation**: Stay clear of competitor logos / branding / proprietary icon sets. Use Lucide icons (MIT) which we already do. Color scheme: keep the Editorial Hero blue gradient — distinctly ours per `docs/brand/`.

### Risk 3 — Expectation creep

**Risk**: A Snowflake user who sees our Catalog page might expect a "Sharing" tab, a "Tasks" tab, a "Streams" tab — features we deliberately don't have.
**Mitigation**: When a tab/feature isn't there, NOT having it is better than a stub. Don't ship `<TabsContainer>` with disabled tabs. The README "What works vs. what waits" is the correct pattern — be loud about scope. PoC #5 testers should be asked: "What did you expect to find that wasn't there?" — feeds v0.3 decisions.

### Risk 4 — JSON output divergence (NDJSON vs JSON-array)

**Risk**: A Databricks user pipes `nucleus runs list --format json | jq '.[] | .status'` expecting a JSON array; gets an error because our output is NDJSON. They blame Nucleus.
**Mitigation**: Rec #8 (`--format jsonl` alias + `--help` doc) flags it explicitly. Don't change to array — NDJSON wins for `jq` streams + MCP/agent consumption per cli_spec §5.2. Document loudly.

### Risk 5 — AI chat sets unrealistic expectations

**Risk**: A Genie/Cortex user expects multi-turn, lineage-aware, cost-traced chat. We ship single-turn (v0.2 per ADR-015) → they perceive Nucleus as "AI-lite".
**Mitigation**: Be explicit on the chat input placeholder text ("Single-turn chat — multi-turn coming v0.3"). Founder ratification on chat scope already locked at ADR-015 §"Out-of-scope for v0.2" — surface that to the user, not just the docs reader.

---

## Section 7 — Sources cited

All URLs verified live 2026-05-15. Where a primary docs URL returned 404 the related sub-page was used.

### Databricks (Unity Catalog, CLI, Lakeflow, error format)

- Databricks CLI commands: <https://docs.databricks.com/aws/en/dev-tools/cli/commands>
- Bundle command group (Declarative Automation Bundles): <https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands>
- Configuration profiles: <https://docs.databricks.com/aws/en/dev-tools/cli/profiles>
- Unity Catalog overview (3-level namespace, Catalog Explorer): <https://docs.databricks.com/aws/en/data-governance/unity-catalog/>
- Data lineage in Unity Catalog: <https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage>
- Lakeflow Jobs monitoring (status vocabulary, graph view, timeline view): <https://docs.databricks.com/aws/en/jobs/monitor>
- Error handling (ERROR_CONDITION + SQLSTATE format): <https://docs.databricks.com/aws/en/error-messages/index>

### Snowflake (Snowsight, CLI, name resolution, Tasks)

- Snowsight overview: <https://docs.snowflake.com/en/user-guide/ui-snowsight>
- Worksheets / query editor / contextual stats / query history: <https://docs.snowflake.com/en/user-guide/ui-snowsight-query>
- Snowflake CLI command reference: <https://docs.snowflake.com/en/developer-guide/snowflake-cli/command-reference/overview>
- Object name resolution (3-level + search-path): <https://docs.snowflake.com/en/sql-reference/name-resolution>
- Tasks (scheduled SQL primitive — analog of `@nucleus.asset(schedule=...)`): <https://docs.snowflake.com/en/user-guide/tasks-intro>
- Account identifier (location structure): <https://docs.snowflake.com/en/user-guide/admin-account-identifier>

### Industry conventions

- NDJSON spec: <https://github.com/ndjson/ndjson-spec>
- NO_COLOR convention: <https://no-color.org/>
- dbt model contracts (vocabulary alignment): <https://docs.getdbt.com/docs/collaborate/govern/model-contracts>
- dbt materializations (vocabulary alignment): <https://docs.getdbt.com/docs/build/materializations>
- Dagster software-defined assets (vocabulary alignment): <https://docs.dagster.io/concepts/assets/software-defined-assets>

### Internal references

- AGENTS.md §3 (Eleven Hard Constraints), §5 (8-Question Gate), §6 (Five Pillars), §7 (Vocabulary), §8 (Forbidden Mental Models), §11.12 (Official Documentation Discipline), §11.14 (Subagent Model Orchestration)
- nucleus_architecture_v4.1.md §1.5 (Beachhead), §6.4 (Error Translation), §8 L4 (CLI), §8.1 (Workbench), §10 (yield-to-giants)
- nucleus_cli_spec.md §3 (command surface), §5 (output format), §6 (flag conventions), §7 (config), §10 (NEEDS VERIFICATION), §12 (forbidden patterns)
- docs/decisions/ADR-015 (Copilot scope), ADR-016 (Workbench fork B), ADR-017 (Schedule), ADR-018 (Dagit escape-hatch), ADR-025 (Active scheduling daemon), ADR-028 (Iceberg branch + tag CLI)
- docs/internal/research/parity_vs_databricks_snowflake.md (capability parity — different from this doc which is UX parity)

---

## Appendix A — Vocabulary translation table

For tooltip / hover-help / docs-team copy. Use to help DB/SF users — NEVER substitute the right-hand-column terms in our own surfaces.

### Asset model

| Nucleus term | "In Databricks…" | "In Snowflake…" |
|---|---|---|
| asset | managed table (Unity Catalog) / pipeline target (Lakeflow) | table or dynamic table |
| source asset | Lakeflow connector source / Auto Loader source | `COPY INTO` source / external stage |
| materialization | job run / pipeline update | task run / dynamic table refresh |
| snapshot | Delta version (`DESCRIBE HISTORY`) | Time Travel version |
| contract / check | DLT expectation / table constraint / DMF | constraint / Data Metric Function |
| catalog | metastore (legacy) / Unity Catalog metastore | account → database (top of 3-level) |
| namespace | schema (UC 2nd level) | schema (SF 2nd level) |
| ctx | spark / dbutils (in notebooks) | session / Snowpark Session |
| Copilot | Genie / Databricks Assistant | Cortex Code / Cortex Analyst |
| graduate | "migrate to Databricks" (loosely) | "migrate to Snowflake" (loosely) |
| engine | Photon / Spark | virtual warehouse |

### CLI verbs (most-asked)

| Nucleus | Databricks | Snowflake |
|---|---|---|
| `nucleus init` | `databricks bundle init` | n/a |
| `nucleus up` / `down` | n/a (no local boot) | n/a |
| `nucleus run <key>` | `databricks bundle run` / `databricks jobs run-now` | `snow object task execute` |
| `nucleus ingest <uri>` | `COPY INTO` / Auto Loader / `databricks fs cp` | `COPY INTO` / `snow stage cp` |
| `nucleus query "..."` | `databricks sql` / SQL Editor | `snow sql -q "..."` |
| `nucleus runs list / show / tail` | `databricks jobs list-runs / get-run <id>` (no tail) | Tasks → Run History (no tail) |
| `nucleus schedule list / preview / on / off` (v0.2+) | `databricks jobs list` (filter) / pause-resume Job | `SHOW TASKS` / `ALTER TASK ... SUSPEND/RESUME` |
| `nucleus snapshot list / restore` (v0.5) | `DESCRIBE HISTORY <table>` | `SHOW VERSIONS` |
| `nucleus snapshot branch / tag` | n/a (Delta CLONE, no branch/tag) | n/a (Snowflake CLONE) |
| `nucleus chat "..."` (v0.2 Beta) | Genie chat in workspace | Cortex Code / Cortex Analyst chat |
| `nucleus profile add / list / test` (v0.3 — Rec #2) | `databricks configure` / `databricks auth profiles / env` | `snow connection add / list / test` |
| `nucleus auth env / login` (v0.3 — Rec #10) | `databricks auth env / login` | `snow connection list / set-default` |
| `nucleus version` | `databricks --version` | `snow --version` |

### Error codes (selected — full registry in `errors.py`)

| Nucleus code | "Like Databricks…" | "Like Snowflake…" |
|---|---|---|
| **NE1001** SourceConnection | `[CONNECT_ERROR]` (loose) | `08001 (08001): connection failed` |
| **NE1002** CommitConflict | `[DELTA_CONCURRENT_APPEND]` | n/a (server-side serialised) |
| **NE1004** SchemaEvolution | `[DELTA_SCHEMA_CHANGE_NOT_ALLOWED]` | `000932 (42000): incompatible column type change` |
| **NE2001** Schema | `[DATATYPE_MISMATCH]` | `000936 (42000): SQL compilation error` |
| **NE2002** SQLSyntax | `[PARSE_SYNTAX_ERROR]` | `000900 (42000): syntax error at position N` |
| **NE3002** AssetNotFound | `[TABLE_OR_VIEW_NOT_FOUND]` | `002003 (42S02): object does not exist` |
| **NE3005** Timeout | `[QUERY_TIMEOUT]` | `000604 (57014): statement timeout` |
| **NE3008** ConcurrentRun | `[ANOTHER_RUN_IN_PROGRESS]` | n/a (server-side queueing) |
| **NE4001** CopilotAuth | `[AUTH_FAILED]` | `390101 (08004): JWT validation failed` |
| **NE5001** Config | `[INVALID_CONFIG_VALUE]` | `000901 (42000): invalid config value` |

---

## NEEDS VERIFICATION

Items not fully confirmed against live docs (5 total). Founder should spot-check before acting on the linked Recs.

1. **Databricks `completion` command exists**: I asserted `databricks completion bash` exists by analogy to `snow completion install`. Could not find a primary doc page. Verify at <https://docs.databricks.com/aws/en/dev-tools/cli/install> before promoting Rec #12 wording.
2. **Snowflake CLI `--format jsonl` flag**: I asserted parity with NDJSON. The `snow` CLI ships `--format json | table | csv | plain` per overview page; `jsonl` may be `json` + a stream-mode flag. Verify at <https://docs.snowflake.com/en/developer-guide/snowflake-cli/command-reference/snow> before publishing Rec #8 verbatim.
3. **Genie persistent right-rail vs modal**: My memory says right-rail; could not screenshot-verify in this session. Read <https://docs.databricks.com/aws/en/genie/index.html> if exact UX details matter for Rec #11 spec.
4. **Databricks SQLSTATE coverage in CLI errors**: I asserted CLI errors include SQLSTATE; the docs page covered SQL errors only. CLI-tool errors (e.g. `databricks bundle deploy` failure) may not. Verify before citing in §2.11 row text.
5. **Snowflake `samples.tpch` exact path**: I cited `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`; the actual path may be `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM` etc. Confirm at <https://docs.snowflake.com/en/user-guide/sample-data> before publishing Rec #13 docs.

None of these blockers stop the Rec #1, #3, #5, #6, #7 v0.2 polish bundle from landing — they only affect the wording of v0.3+ items.

---

## Logged hallucinations

None caught in this session. All API surface references for Nucleus internals were cross-checked against the source files cited inline (`errors.py`, `cli/main.py`, `cli/commands/runs.py`, `workbench/api/catalog.py`, `App.tsx`, `TopNav.tsx`, `Sidebar.tsx`, `AssetDAG.tsx`, `CatalogPage.tsx`). Databricks/Snowflake claims that I could not pin to a specific URL are flagged as `NEEDS VERIFICATION` above.

---

*Generated 2026-05-15 by background researcher (Claude Opus 4.7, Architect-tier acting as Researcher per AGENTS.md §11.14 fallback policy). Read-only analysis. No code edits made; this doc proposes 15 changes spanning v0.2 polish through v0.5 — founder ratifies which to land in which Wave.*
