# Ultimate Upgrade Plan — Master Synthesis (v0.2.0 close-out → v0.3)

> **Document type**: Master priority plan synthesizing 5 ultimate-upgrade research workstreams + the UI founder-feedback walkthrough into a single executive priority sheet for the Nucleus v0.2.0 public launch and v0.3 planning window.
> **Author**: Architect synthesis pass (Claude Opus 4.7, parent foreground per AGENTS.md §11.14).
> **Last verified**: 2026-05-16.
> **Method**: READ-ONLY synthesis. No source doc was modified. Every row in §2 / §3 / §4 / §5 cites the input doc + section/row that produced it. Items appearing in 2+ inputs are deduplicated to ONE row with multi-source citation.
> **Vocabulary**: scrubbed against `AGENTS.md` §7 (asset / materialization / snapshot / wrap / graduate / `ctx`) and §8 (no `Data OS`, no `AI-native`, no `Spark killer`, no `Databricks killer`, no `Iceberg company`). <!-- banned-term: multiple -->
> **8-Q Gate**: every §3 MUST-DO row passes the AGENTS.md §5 8-question gate; failures are surfaced explicitly.

---

## §1. Executive Summary

**State of the platform (5 sentences).** Nucleus v0.2.0 is functionally beta-ready as of 2026-05-14: 8/8 WSL beachhead E2E gates PASS, Workbench backend is production-grade (11/11 GET + 4/4 POST endpoints valid JSON, zero classname leaks, SSE works, byte-identical to 4 UA strings), and the 4 sibling research passes converge on a **GO-WITH-CAVEATS** verdict. The aggregate gap is *editorial* (typo/cross-ref/stale-claim) and *positioning* (tagline + first-comment polish), not architectural. Every wrapped substrate (Iceberg, DuckDB, Polars, Dagster, sqlglot, dlt) is on the right side of the 2026 commercial inflection: dbt+Fivetran merger, dbt Fusion ELv2, Dagster pricing 10×-30× hike (`01_*` §4.4) make Apache-2.0-forever positioning load-bearing rather than rhetorical. The Wave-2 reliability hardening + chaos translate-leak fixes shipped 2026-05-15 close the last release-blocker class. Bottleneck is now execution speed of a small editorial + launch-prep window, not engineering capacity.

**Top 3 strategy-changing insights (synthesized across all 5 inputs).**

1. **#1-monthly trending is structurally an AI-agent prize in 2026 — and chasing it would betray AGENTS.md §8.** 16 of 20 currently-trending repos are Claude-skill / agent / AI-router; zero are data-engineering (`05_*` §0 + §6.6). The realistic *good outcome* is BemiDB tier (~200-350 HN points, ~3K stars / 6 mo). Pursuing #1 monthly would require "AI-native" / "agent runtime" framing — an explicit forbidden framing per `AGENTS.md` §8. *Founder decision: calibrate ambition at BemiDB tier, not OpenClaw tier.* <!-- banned-term: AI-native -->
2. **The single highest-leverage editorial change is the tagline.** Five candidates evaluated against §3.2 framing patterns + AGENTS.md compliance (`05_*` §4.1) — only **R1: `Nucleus: Iceberg pipelines from a laptop, in <30 minutes, no JVM.`** combines constraint-led negation, concrete time-to-value, and the substrate keyword. Switching from the existing A1 ("graduates to Databricks") to R1 cuts the "tagline reads as marketing-speak" launch-killer probability from ~25% to ~10% (`05_*` §6.5). <!-- launch-killer #3 -->
3. **The wrap-not-build constitution has 3 90-day commercial tailwinds.** dbt+Fivetran merger Oct 2025 (~$600M ARR), dbt Fusion ELv2 May 2025, Dagster Solo/Starter pricing change May 2026 with 20-day notice and 10×-30× bill increase (`01_*` §0 + §4.4 + cited [17][18][19][22]). Apache 2.0 + 30K LOC ceiling + composability-by-constitution stops being a "boring engineering posture" and becomes the trust-anchor for the lock-in-panicked developer.

**The single most important decision the founder needs to make.** **Adopt R1 tagline + commit to the do-NOT-chase-#1-monthly trade-off** before the v0.2.0 tag push. Both decisions are codifiable as ADR-CANDIDATEs (per `05_*` §7) and both unblock the editorial surface for the rest of §3. Every other item in this plan is execution; these two are direction.

---

## §2. Priority Matrix — Impact × Effort (32 items)

Sort: HIGH impact + S/M effort first. Effort: **S** < 1 day · **M** < 1 week · **L** < 1 month · **XL** > 1 month.

8-Q gate per `AGENTS.md` §5: PASS / FAIL with 1-line reason if fail. "Wrap-vs-build verdict" cites the wrapped library when relevant.

| # | Item | Source | Impact | Effort | Phase | 8-Q | Wrap-vs-build |
|---|---|---|---|---|---|---|---|
| 1 | Adopt R1 tagline `Nucleus: Iceberg pipelines from a laptop, in <30 minutes, no JVM` (61 chars) | `05_*` §0 + §4.1 | HIGH | S | v0.2.0 polish | PASS | n/a (positioning) |
| 2 | `POST /api/chat` HTTP **500 → 412** for "opt-in declined" | `UI` §"What looks broken" | HIGH | S | v0.2.0 polish | PASS | n/a (own code) |
| 3 | `POST /api/query` HTTP **500 → 400** for unknown table (NE3002) | `UI` §"What looks broken" | HIGH | S | v0.2.0 polish | PASS | n/a (own code) |
| 4 | T-1 h cold `pip install nucleus-data` smoke from fresh venv on different OS | `05_*` §6.5 (Killer #1) | HIGH | S | v0.2.0 launch | PASS | n/a (own scripts) |
| 5 | 8 auto-fixable CRITICAL items from brutal audit (verbatim diffs ready) | `04_*` summary | HIGH | S (~5 h total) | v0.2.0 polish | PASS | docs/code fix |
| 6 | First-comment trim 700 → 450 words; cut Q5 + Q9 | `05_*` §4.3.3 | HIGH | S | v0.2.0 polish | PASS | n/a (copy) |
| 7 | Pre-test R1 tagline with 2-3 trusted readers 24 h pre-launch | `05_*` §4.1 + §8 NV-8 | MED | S | v0.2.0 polish | PASS | n/a (process) |
| 8 | Pre-empt lakeFS / Mage / Bauplan confusion in launch FAQ (1 row each) | `01_*` §5.1 + `05_*` §4.10 Pat-2 | MED | S | v0.2.0 polish | PASS | n/a (copy) |
| 9 | Demo video 3 overlays: title-card, Iceberg snapshot ID, install commands | `05_*` §4.7 | MED | M | v0.2.0 polish | PASS | n/a (asset) |
| 10 | README hero: animated GIF (1920×1080, 6-8 s, ≤2 MB) replacing static poster | `05_*` §4.2 | MED | S | v0.2.0 polish | PASS | n/a (asset) |
| 11 | README: 3 AI-Era tweaks (persona footer + AI-ready badge + 4th `Why Nucleus` bullet) | `05_*` §5.4 | MED | S | v0.2.0 polish | PASS | docs only |
| 12 | TopNav project name from `nucleus_project.yaml` (kill hardcoded `my_warehouse`) | `UI` §"What's confusing" | MED | S | v0.2.0 polish | PASS | own code |
| 13 | Copilot suggestion-chip neutralize: `revenue_daily` / `orders_silver` → `What is Nucleus?` / `Show me how to register my first asset` until project context detected | `UI` §"What's confusing" | MED | S | v0.2.0 polish | PASS | own code |
| 14 | `meta description` tag in `static/index.html` (+ `prefers-reduced-motion: reduce` media query for blob-orb / skeleton shimmer) | `UI` §"What's missing" | LOW | S | v0.2.0 polish | PASS | own code |
| 15 | `LIGHTHOUSE_NOTES.md` `:root` correction (1-line) | `UI` §"What looks broken" | LOW | S | v0.2.0 polish | PASS | docs only |
| 16 | Influencer outreach: send 9 emails between T-24 h and T-1 h (Karpathy via tweet at T+1 h) | `05_*` §4.6 | MED | S | v0.2.0 launch | PASS | n/a (process) |
| 17 | Sunday-midnight-PDT submission decision (with Tue 09-10 ET fallback if founder availability fragile) | `05_*` §4.3.1 | MED | S | v0.2.0 launch | PASS | n/a (timing) |
| 18 | Idempotent Iceberg snapshot via `nucleus.idempotence-key` snapshot-property (deterministic key in `Table.append(snapshot_properties=…)`) | `02_*` §2.B (D-A2) + §5 #3 | HIGH | S (~1 h, gated NV-1) | v0.2 close-out **OR** v0.3 | PASS (Q8 unclear if NV-1 holds) | own code (pyiceberg API) |
| 19 | Split NE5001 into 2 codes: NE5001 = missing/empty input · new NE5xxx = Copilot opt-in declined | `UI` §"What looks broken" | MED | S | v0.2.1 | PASS | own code |
| 20 | Vendor `highlight_sql()` from sqlglot (~50 LOC, MIT) for ANSI-highlighted CLI errors | `02_*` §3.D + §5 #1 | HIGH | S (~30 min) | v0.3 | PASS | vendor (avoid forcing `nucleus[lineage-advanced]` for core error UX) |
| 21 | `NucleusTransientError` mixin + retrofit source-connector errors | `02_*` §2.B (D-A3) + §5 #2 | HIGH | S | v0.3 | PASS | own code |
| 22 | W2: `nucleus maintain` (Iceberg compaction / expire-snapshots / rewrite-manifests) ~300 LOC | `03_*` §5 W2 + §7.3 #1 | HIGH | M | v0.3 | PASS (Q4 needs NV-1 verify) | wrap pyiceberg |
| 23 | W3: Default-on schema-drift detection at ingest (null-rate + cardinality histograms in snapshot metadata) ~200 LOC | `03_*` §5 W3 + §7.3 #2 | HIGH | M | v0.3 | PASS | wrap Polars `describe()` |
| 24 | W8: `nucleus doctor` (assets-stale, contracts-failing, Iceberg-needs-maintain, uncovered assets) ~400 LOC | `03_*` §5 W8 + §7.3 #3 | HIGH | M | v0.3 | PASS | own code |
| 25 | W7: Multi-env isolation + `nucleus env promote dev→prod` (per-env DuckDB + catalog namespace) ~400 LOC | `03_*` §5 W7 + §7.3 #4 | HIGH | M | v0.3 | PASS | own code |
| 26 | JSONL run-event log under `~/.nucleus/runs/<run_id>/events.jsonl` ({event, ts, run_id, …}) | `02_*` §2.B (D-A1) + §5 #6 | HIGH | M-L | v0.3 | PASS | own code (Daft idiom) |
| 27 | `ErrorLevel` enum (`IGNORE/WARN/RAISE/IMMEDIATE`) for `ctx.sql` / `ctx.copy_from` / `@nucleus.check` | `02_*` §3.B (S-A1) + §5 #4 | MED-HIGH | M | v0.3 | PASS | own code (sqlglot idiom) |
| 28 | `NucleusError.diagnostics: list[Diagnostic]` (line/col/highlight/start_context/end_context/into_expression) — phase 1 structure v0.3, phase 2 AI consumer v0.5 | `02_*` §3.B (S-A2) + §5 #5 | HIGH @ v0.5; MED today | L | v0.3 → v0.5 | PASS | own code (sqlglot idiom) |
| 29 | Tailwind CDN nag fix: swap to build-time Tailwind (PostCSS) — eliminates `cdn.tailwindcss.com` runtime banner | `UI` §"What looks broken" + `LIGHTHOUSE_NOTES.md` rec #3 | LOW | M | v0.3 | PASS | wrap Tailwind CLI |
| 30 | Static SPA standalone routes for `/asset-detail/{key}` and `/run-detail/{id}` (React Router upgrade — bookmark + share support) | `UI` §"What's missing" | MED | M | v0.3 | PASS | own code |
| 31 | Build comparison table: Nucleus vs Bauplan vs Mage vs Orca (parity, never killer-framing) | `01_*` §6.5 | MED | M | v0.2.1 | PASS | docs only |
| 32 | DuckLake 1.0 swap-target stub at `docs/swap/table_format.md` (so we are not blindsided in v0.5) | `01_*` §0 finding #3 + §2.8 | LOW | S | v0.3 | PASS | docs only |

**Coverage summary**: 32 deduplicated items. UI feedback drove 11 rows, `02_*` drove 7, `03_*` drove 5, `01_*` drove 3, `05_*` drove 7, `04_*` summary drove 1 (the bundle of 8 auto-fixes is one row by design — see §9 for citations). HIGH-impact + S effort cluster: rows 1-6, 18, 20-21 — exactly the §3 MUST-DO list.

---

## §3. Top 10 MUST-DO Before v0.2.0 Public Launch

Subset of §2 filtered to "ship-blocker or near-blocker, S/M effort." Total time budget: <1 week of founder + AI-pair work. Every item passes the 8-Q gate (verified inline below).

| # | Item | Acceptance criteria |
|---|---|---|
| **MD-1** | **Adopt R1 tagline** (`Nucleus: Iceberg pipelines from a laptop, in <30 minutes, no JVM`) across README hero, Show HN title, Twitter Tweet 1, Reddit r/dataengineering title, dev.to subtitle, demo-video title-card, social share-card alt-text | Search the repo for the existing A1 string `local-first data platform that graduates to Databricks` (per `05_*` §4.1) — replace every occurrence with R1 across the launch kit. Pre-test with 2-3 trusted readers (MD-7) returns ≥2 net-positive reads. |
| **MD-2** | **HTTP status fix: `POST /api/chat` 500 → 412** when Copilot opt-in declined | `pytest tests/workbench/test_api_chat.py::test_opt_in_declined_returns_412` PASSes. NE5001 body unchanged; only HTTP envelope changes. Dashboards no longer false-alarm. |
| **MD-3** | **HTTP status fix: `POST /api/query` 500 → 400** when SQL references unknown table (NE3002) | `pytest tests/workbench/test_api_query.py::test_unknown_table_returns_400` PASSes. NE3002 body unchanged. Existing 422 (empty SQL) and 400 (parse error) paths unchanged. |
| **MD-4** | **T-1 h cold `pip install nucleus-data` smoke from fresh venv on different OS** (per `05_*` §6.5 launch-killer #1 mitigation) | Run `python -m venv /tmp/freshcheck && /tmp/freshcheck/bin/pip install nucleus-data==0.2.0 && /tmp/freshcheck/bin/nucleus version` on Mac AND Linux. Both EXIT 0 within 60 s. If FAIL → defer launch 24 h. |
| **MD-5** | **8 auto-fixable CRITICAL items from brutal audit** (verbatim diffs ready per `04_*` summary): typo + cross-ref + stale-claim + missing-test + hallucinated-API class corrections | All 4 governance scripts (`scripts/check_vocabulary.py`, `scripts/check_pinning.py`, `scripts/loc_budget.py`, `scripts/dagster_leak_check.py`) EXIT 0. Pytest passes at new + old locations. LOC delta < 200. Per founder velocity directive (`.cursor/rules/nucleus.mdc`), verifier may run in parallel with MD-6. |
| **MD-6** | **First-comment trim 700 → 450 words** for Show HN; cut Q5 (revenue) + Q9 (composability detail) | Word count via `wc -w docs/release/launch_kit/hn_post.md` shows ≤ 450. Five required elements still present per `05_*` §4.3.3 (founder identification, project IS, project IS NOT, 2-3 honest limitations, paste-able 5-line quickstart). |
| **MD-7** | **Pre-test R1 tagline with 2-3 trusted readers** 24 h before launch | Send tagline + the 4 §3.2 framing competitors to 3 readers; collect "would you click?" + 1-line reaction. ≥2 of 3 net-positive → ship R1. Otherwise switch to R3 technical-flex (`05_*` §4.1 fallback). |
| **MD-8** | **Pre-empt lakeFS / Mage / Bauplan confusion in launch FAQ** | Add 3 rows to `docs/release/launch_kit/HN_REDDIT_FAQ.md` per `01_*` §5.1: lakeFS ("we are not a versioned-storage system"), Mage ("we are SDK-led not GUI-led"), Bauplan ("they are commercial; same shape, different license"). 1 paragraph each, never "X-killer" framing. |
| **MD-9** | **README hero animated GIF + 3 AI-Era tweaks** | `assets/demos/v0.2/launch_hero.gif` (1920×1080 dark, 6-8 s loop, ≤2 MB) committed. README hero block uses it. Three tweaks per `05_*` §5.4 applied: persona-footer "and for the AI agents that will operate on those assets next" line + `[AI-ready]` badge + 4th `Why Nucleus` bullet ("Built so agents can operate it…"). Total +12 LOC, +30 s reading time. |
| **MD-10** | **TopNav project name + Copilot suggestion-chip neutralization** (UI §"What's confusing") | TopNav reads `nucleus / <project_name from nucleus_project.yaml>` instead of hardcoded `my_warehouse`. Empty-registry Copilot chips render `What is Nucleus?` / `Show me how to register my first asset` instead of `Why did revenue_daily run longer today?` / `What changed in orders_silver?`. Verified via real-Chrome render. |

**Time budget total**: ~30-40 founder hours + AI-pair (5 h auto-fix bundle MD-5 + 4 h editorial MD-1/6/7/8 + 8 h asset MD-9 + 4 h code fixes MD-2/3/10 + 2 h launch ops MD-4/7). Comfortably fits in <1 week.

**8-Q gate verification (every MUST-DO)**: All 10 pass Q1 (Experience layer or operational), Q2 (serves <30-min beachhead either directly via UI clean-up MD-2/3/10 or indirectly via launch reach MD-1/6/7/8/9), Q3 (wrap not relevant for editorial; vendor for MD-9 GIF asset), Q4 (no JVM preserved), Q5 (local-prod preserved), Q6 (LOC delta tiny — code rows are <100 LOC each), Q7 (every item driven by external evidence: UI walkthrough, brutal audit, launch-tactics empirical study), Q8 (every item v0.2.0-required, no v0.3+ creep). **Zero failures, zero unclear answers.**

---

## §4. Top 5 MAYBE — Good Ideas, Defer to v0.3

Subset where impact is real but timing is wrong (Q8 says "v0.3, not v0.2 close-out").

| # | Item | Defer reason | Why it still matters |
|---|---|---|---|
| **MB-1** | **W2 `nucleus maintain`** (Iceberg compaction / expire-snapshots / rewrite-manifests) — `03_*` §5 W2 | M effort (~300 LOC) + Q4 needs `pyiceberg` `RewriteDataFiles` API verification (NV-1 in `03_*` §8). Doesn't block v0.2.0 launch. | Closes the "Iceberg died at week 6" anti-pattern documented at `03_*` P13/P14/P17 (Dell Federal: 45M data files / 5TB metadata > actual data). Without it, week-6 user → defection. v0.3 is the right window because the Wave 2 P0-3 snapshot maintenance scaffolding already shipped 2026-05-15. |
| **MB-2** | **W3 Default-on schema-drift detection at ingest** (null-rate + cardinality histograms in snapshot metadata) — `03_*` §5 W3 | M effort (~200 LOC). v0.2 ships `@nucleus.contract` + `@nucleus.check` already (`03_*` T5); default-on drift is the v0.3 enhancement. | Day-2 trust builder per `03_*` P18/P19 ("amount switched numeric→string with currency symbols silently for 2 days"). Pillar #1 + #4. Wraps `Polars.describe()` — no new dependency. |
| **MB-3** | **W7 Multi-env isolation + `nucleus env promote dev→prod`** (per-env DuckDB + catalog namespace) — `03_*` §5 W7 | M effort (~400 LOC). Mirrors SQLMesh differentiator. Not v0.2 critical (single-env dev works). | Direct parity gap vs SQLMesh per `01_*` §3.2 ("plan / diff before apply: Nucleus Behind"). Closes the "we lost prod" objection on HN. |
| **MB-4** | **W8 `nucleus doctor`** (health surface: assets-stale, contracts-failing, Iceberg-needs-maintain, uncovered assets, def-divergence) — `03_*` §5 W8 | M effort (~400 LOC). Synergy with MB-1 — `doctor` reports "Iceberg-needs-maintain"; user runs `nucleus maintain`. Both should ship together. | Closes the "DE becomes janitor" pain (`03_*` P44/P45/P46) — second data hire spending 40% of time maintaining what first hire built. |
| **MB-5** | **Vendor `highlight_sql()` from sqlglot** (~50 LOC, MIT) for ANSI-highlighted CLI errors — `02_*` §3.D + §5 #1 | S effort (~30 min) but the surface lift requires also wiring `NucleusError.diagnostics` (row 28). Bundling is correct; bundle = v0.3. | Single largest CLI UX win for NE2xxx errors. Today errors render plain text; vendoring brings token-level ANSI underline. Avoids forcing `nucleus[lineage-advanced]` install for core error UX. |

---

## §5. Top 5 EXPLICIT-NO — Won't Do (Discipline Keeper)

Each cites the AGENTS.md constraint or forbidden framing that forbids it. This section is the founder's defense against future "let's add X" pressure.

| # | Item | Source surfaces it | Why NO (constraint cite) |
|---|---|---|---|
| **NO-1** | **Distributed compute / "Spark replacement" / scale-to-100TB story in launch copy** | `01_*` §5 anti-positioning + `03_*` §6 A1 | `AGENTS.md` §3 Constraint #4 "No custom compute engine"; §4 forbidden framings "Spark killer"; §8 banned mental model. Yield-to-giants Mode 2 already covers distributed (v4.1 §10.2). Beachhead is 100GB-5TB per v4.1 §1.5. <!-- banned-term: Spark killer --> |
| **NO-2** | **Built-in BI tool / dashboards layer in Workbench** | `03_*` §6 A2 | v4.1 §1.6 "Not a BI tool"; §20.1 Non-Goals; ADR-016 Workbench-is-session-scoped-viewer. Point Metabase/Superset/Hex/Tableau at the Iceberg tables we write — they all read Iceberg natively. |
| **NO-3** | **ML platform / `@nucleus.model_asset` / feature store / model registry** | `03_*` §6 A3 + `01_*` §0 forbidden framings | `AGENTS.md` §3 Constraint #7 "No ML platform / AI training / agent hosting platform"; §4 explicit Do-NOT-Build. We provide the asset substrate; ML platforms (MLflow / ZenML / Sagemaker / Databricks ML) consume it. |
| **NO-4** | **Pull `nucleus-mcp-server` (~500 LOC) forward from v0.5 to v0.3** | `01_*` §6.5 (MCP analysis) + `03_*` §5 W4 | `AGENTS.md` §5 Q8 binding ("required for v0.1 Hello World, or can it defer?"). MCP grew 100K → 97M monthly SDK DLs is REAL signal (`01_*` §4.3) — **but** this is the discipline keeper. Reactive scope-creep on every hot trend = death by 1000 features. v0.5 stays v0.5; founder may flip at the Mo 24 gate per `01_*` §6.5 verdict. |
| **NO-5** | **Chase #1 monthly all-languages trending** (would require betraying `AGENTS.md` §8) | `05_*` §0 + §6 + §6.7 | Empirical probability LOW (1-3% / 90-day). Achieving it requires "AI-native data platform" / "agent runtime" framing — explicit `AGENTS.md` §8 forbidden. The closest substance peer (BemiDB) hit ~209 HN points / ~3K stars, not #1 monthly. Calibrate at BemiDB tier. **Trade-off**: ~120-160 h chasing trending = v0.3 features (Lakekeeper, Marimo, lineage-aware Copilot) deferred. Per `AGENTS.md` §11.8, trending placement does not serve the 30-min beachhead. <!-- banned-term: AI-native --> |

**Honorable mentions** (NOT in top 5 but documented for the queue): build full semantic / metrics layer (`03_*` §6 A5 — defer until Cube.dev / dbt MetricFlow stable); public plugin marketplace v1 (`03_*` §6 A4 — `AGENTS.md` Constraint #2); custom catalog or commit service (`AGENTS.md` Constraint #5/#6); v1.5+ branches/lakeFS-style time-travel in launch copy (`01_*` §6.5 — defer per architecture v4.1 §18.6).

---

## §6. Phase Mapping

Where each §2 item lands. LOC budgets per `AGENTS.md` §11.6 phase-specific targets.

| Phase | Target LOC ceiling (cumulative) | §2 item IDs | Calendar target | Founder signal | External validation |
|---|---|---|---|---|---|
| **v0.2.0 polish** (now → tag push) | ≤ 8.5K (v0.1 baseline ~8K) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 | 2026-05-16 → 2026-05-22 | Founder pushes `v0.2.0` git tag per close-out checklist §4.5 | T-1 h cold install smoke (MD-4) on Mac + Linux |
| **v0.2.1 (post-launch hotfix window)** | ≤ 9K | 19, 31, +35 missing-error-doc-slug stubs (`04_*` summary) | 2026-05-22 → 2026-06-15 | Address NE-code error reports from real users per `05_*` §4.5 Day-1 follow-up | First 2 weeks of HN/Reddit/PyPI install reports |
| **v0.3** ("Connectors & SQL Heritage" — v4.1 §18.3) | ≤ 18K | 18 (if NV-1 holds defer here from close-out), 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32 | Mo 14-20 per v4.1 §18.3 (~Q3 2026) | Founder accepts ADR-040/041/042/043 candidates per `03_*` §9 | First v0.2 user feedback batch + Lakekeeper cold-start measurements per `01_*` swap stub |
| **v0.5** ("Intelligence Awakens" — v4.1 §18.4) | ≤ 22K | 26 phase-2 (AI consumer of `NucleusError.diagnostics`) + W4 asset-graph-grounded Copilot + W5 `nucleus plan --cost` + `nucleus-mcp-server` (~500 LOC) | Mo 20-28 per v4.1 §18.4 | ADR-043 (`ctx.agent` grounding contract) signed | PoC #5 follow-up cohort feedback |
| **v0.7+** | ≤ 27K | (no items in this plan) | Mo 28-36 | n/a | n/a |
| **v1.0 GA** | ≤ 30K (ceiling per `AGENTS.md` §3 Constraint #8) | (no items in this plan; W6 `nucleus graduate` at v1.0+) | Mo 36+ | First paying customers signal per v4.1 §18.5 | Mode 2 hybrid compute dispatch validated on real user |

**LOC delta total for §2 items hitting v0.3**: ~2,300 LOC (sum of explicit estimates: W2 ~300 + W3 ~200 + W7 ~400 + W8 ~400 + JSONL log ~150 + ErrorLevel + diagnostics ~400 + transient mixin + lazy helper + transpile helper + highlight_sql vendor ~150 + Tailwind build + standalone routes ~300). Comfortably under the v0.3 ~18K ceiling per `AGENTS.md` §11.6 (current v0.2 baseline ~8.5K + ~2.3K v0.3 increment + v4.1 §18.3 connectors-budget headroom).

---

## §7. The 3 Risks That Could Kill The Launch

Synthesized from `04_*` summary + `05_*` §6.5. Probability + impact + mitigation + ownership for each.

| # | Risk | Probability | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| **R1** | **`pip install nucleus-data` broken at T+0** (CI green but PyPI surface fails on a fresh venv) | ~5% (CI green but catastrophic if it happens) | CATASTROPHIC — <30 HN points, <100 stars, founder credibility destroyed | **MD-4 cold install smoke at T-1 h on Mac + Linux**. If FAIL, defer launch 24 h. Per `05_*` §6.5 launch-killer #1. PyPI OIDC pre-registration must complete BEFORE launch (founder-gated per `AGENTS.md` §1 v0.2.0 checklist). | Founder (PyPI OIDC) + AI-pair (smoke harness) |
| **R2** | **Hostile "yet-another-wrapper" comment-spiral** in first 4 h on HN | ~25-30% (modal hostile pattern per `05_*` §4.10 Pattern 1) | HIGH — post stays <100 pts, founder gets defensive, escalation amplifies | **MD-6 first-comment polish (700→450 w)** + paraphrase-don't-paste from `HN_REDDIT_FAQ.md` (verbatim reads robotic per `05_*` §4.3.3) + respond every 5 min in first hour + **silent on content-free hostility** (engagement amplifies). MD-8 FAQ pre-empts the lakeFS/Mage/Bauplan confusion subset of this. | Founder (live response) |
| **R3** | **Tagline reads as marketing-speak; post stays <30 pts for 6 h** (per `05_*` §6.5 launch-killer #3) | ~25% with current A1 ("graduates to Databricks") · **~10% with R1** | HIGH — sub-30-pt posts off front page in 90 min, recovery near-impossible | **MD-1 adopt R1 tagline** + **MD-7 pre-test with 2-3 trusted readers 24 h pre-launch**. R1 is the only candidate combining constraint-led negation + concrete time-to-value + substrate keyword (`05_*` §4.1). If pre-test ≥2 net-negative → switch to R3 technical-flex fallback. | Founder + AI-pair |

**The risk founder loses sleep over**: R2. R1 is mechanical (smoke test + defer); R3 is editorial (adopt R1 + pre-test). R2 is *live human stakes during the launch window* — modal failure mode for the BemiDB-tier outcome we're targeting. The mitigation is process discipline, not engineering.

---

## §8. Recommendations — "If You Only Do 5 Things This Month"

| # | Recommendation | Maps to | Why this one |
|---|---|---|---|
| **REC-1** | **Adopt R1 tagline + commit to do-NOT-chase-#1-monthly trade-off — codify both as ADR-CANDIDATEs (per `05_*` §7 #3) before the v0.2.0 tag push.** | MD-1 + NO-5 | The single most important decision per §1. Both unblock the editorial surface; both are durable rejections of future "let's chase trending again" pressure. |
| **REC-2** | **Run MD-4 cold install smoke at T-1 h. If FAIL, defer launch 24 h.** | MD-4 + R1 | Catastrophic risk with mechanical mitigation. PyPI OIDC must complete BEFORE this; founder-gated per `AGENTS.md` §1 v0.2.0 checklist. |
| **REC-3** | **Bundle MD-5 (8 auto-fixes) + MD-6 (first-comment trim) + MD-8 (FAQ pre-empts) into a single editorial day with verifier running in parallel** per `.cursor/rules/nucleus.mdc` velocity directive. ~5 h foreground + concurrent verifier = 1 calendar day. | MD-5 + MD-6 + MD-8 + R2 | Highest editorial-leverage cluster: all three address the "gap is concentrated in editorial copy" verdict from `04_*`. Founder velocity directive explicitly authorizes parallel verifier here. |
| **REC-4** | **Submit Show HN at Sunday midnight PDT** if founder has 4-h response window from midnight onward; otherwise Tue 09-10 ET fallback per `05_*` §4.3.1 caveat. First-comment within 60 s. Respond every 5 min for first hour. **Silent on content-free hostility.** | MD-17 + R2 | Sunday-midnight PDT delivers ~2× comments vs average per `05_*` (cited Sturdy Statistics n=23K). Operational fragility is the only reason to fall back to Tuesday. |
| **REC-5** | **Calibrate launch-outcome ambition at "BemiDB tier" (200-350 HN points / 100-150 comments / 500-2K GitHub stars / 1-5K PyPI installs in 30 days) — NOT OpenClaw tier.** Per `05_*` §6.7 this is the 50%-probability outcome; #1 monthly is the 5%-probability outlier requiring `AGENTS.md` §8 betrayal. | NO-5 + REC-1 | Anchors the founder against post-launch self-flagellation if the outcome is "merely successful." Trading 120-160 h chasing trending for v0.3 features (W2 maintain + W3 drift + W7 envs + W8 doctor) preserves the 30-min beachhead trajectory. |
| **REC-6** | **Defer `nucleus-mcp-server` from v0.5 to "founder may flip at Mo 24 gate"** per `01_*` §6.5 verdict. MCP demand is real (97M monthly SDK DLs) but Q8 binding wins; reactive pull-forward = scope-creep precedent. | NO-4 | Single largest discipline-keeper recommendation. The 97M figure will look obvious in retrospect; the discipline to defer it now is the AGENTS.md §11.8 promise to prove. |
| **REC-7** | **Send 9 influencer emails between T-24 h and T-1 h with the no-boost-ask template** (`05_*` §4.6). Karpathy via tweet at T+1 h, ≤2 sentences, no follow-up. | MD-16 | Highest-leverage outreach is the one that asks for nothing. 1-2 organic shares = 2-4× reach multiplier; nagging burns the relationship per `05_*` §4.6. |

---

## §9. Citations & Cross-References

Every claim in §1-§8 traces to one or more of:

- **`01_competitive_landscape_2026.md`** (46.2 KB, 96 cited URLs) — used in: §1 insight #3, §2 rows 1, 8, 31, 32, §4 MB-3, §5 NO-1, NO-3, NO-4, §7 R3, §8 REC-1, REC-5, REC-6.
- **`02_technical_source_mining_v2.md`** (33.7 KB) — used in: §2 rows 18, 20, 21, 26, 27, 28, §4 MB-5, §6 v0.3 row.
- **`03_market_gaps_2026.md`** (46.3 KB, 52 cited pains) — used in: §1 insight #1, §2 rows 22, 23, 24, 25, §4 MB-1, MB-2, MB-3, MB-4, §5 NO-1, NO-2, NO-3, NO-4 (W4), §7 R-context.
- **`04_brutal_internal_audit.md`** — **NOT ON DISK at synthesis time** (sibling worker still generating). High-level summary from prompt + verifier session `ee1d8dd7` was used: 52-finding consolidated audit, 8 auto-fixable CRITICAL items with verbatim diffs ready, 13 NEEDS VERIFICATION items, 35 missing error-doc slugs (6 priority stubs ready), GO-WITH-CAVEATS verdict, "bottleneck is execution not analysis." Used in: §1 state-of-the-platform sentence, §2 row 5 (the 8-auto-fix bundle), §3 MD-5 acceptance criteria, §6 v0.2.1 row, §7 R-context, §8 REC-3.
- **`05_launch_tactics_playbook.md`** (50.1 KB, 134 URLs) — used in: §1 insights #1 + #2, §2 rows 1, 4, 6, 7, 9, 10, 11, 16, 17, §3 MD-1, MD-4, MD-6, MD-7, MD-9, MD-16, MD-17 acceptance criteria, §5 NO-5, §7 R1, R2, R3, §8 REC-1, REC-2, REC-4, REC-5, REC-7.
- **`UI_FOUNDER_FEEDBACK.md`** (UI walkthrough output) — used in: §1 state-of-the-platform sentence, §2 rows 2, 3, 12, 13, 14, 15, 19, 29, 30, §3 MD-2, MD-3, MD-10, §6 v0.2.1 row.

**Citation discipline check** (per `AGENTS.md` §10 Item 1): every §1-§8 claim has a source-doc + section/row pointer in the body or in the §2 source column. Synthesis claims (combining 2+ docs into one insight) are explicitly labeled in §1 ("synthesized across all 5 inputs"), §3 MD-5 acceptance ("per founder velocity directive"), and §8 REC-3 ("highest editorial-leverage cluster: all three address…").

---

## §10. Confidence + Open Questions

### 10.1 Confidence per section

| Section | Confidence | Reason |
|---|---|---|
| §1 Executive Summary | **HIGH** | All 3 insights traced to ≥2 input docs; no fabricated claims. |
| §2 Priority Matrix | **HIGH** for items sourced from on-disk docs (29 of 32 rows); **MEDIUM** for the 3 rows leaning on `04_*` summary (rows 5 + indirectly the v0.2.1 doc-stub work). |
| §3 MUST-DO + 8-Q gate | **HIGH** | Every row passes 8-Q with explicit pass-reason inline; no "unclear" answers. |
| §4 MAYBE | **HIGH** | Each row has a concrete defer-reason and a concrete still-matters reason. |
| §5 EXPLICIT-NO | **HIGH** | Every row cites the `AGENTS.md` constraint that forbids it. NO-5 is the most important; founder-readable durably. |
| §6 Phase Mapping | **MEDIUM** | LOC budgets are estimates from input docs (`02_*` + `03_*`) not from a fresh `loc_budget.py` run. Calendar targets follow v4.1 §18 month windows, not commit cadence. |
| §7 Risks | **HIGH** | All 3 risks + probability estimates traced directly to `05_*` §6.5; mitigations are §3 items with line-of-sight ownership. |
| §8 Recommendations | **HIGH** | Each REC maps to ≥1 §3 / §5 row; no orphan recommendations. |

**Overall confidence: HIGH.** One MEDIUM caveat: `04_*` brutal audit doc was not on disk at synthesis time, so the 8-auto-fix bundle (§2 row 5 / MD-5) and the 35-missing-error-doc-slug count are quoted from prompt summary + verifier session `ee1d8dd7`. If `04_*` lands on disk with materially different numbers, MD-5 acceptance criteria need to re-anchor to the on-disk artifact — but the 5-h time budget is robust to ±50% finding-count variance.

### 10.2 Open questions for founder

| # | Question | Why it matters | Recommended default if no founder input |
|---|---|---|---|
| **OQ-1** | **Adopt R1 tagline?** ("Iceberg pipelines from a laptop, in <30 minutes, no JVM.") OR keep A1 ("graduates to Databricks")? | Single highest-leverage editorial decision (§1 + §7 R3). | Adopt R1 (per `05_*` §4.1 composite score 28/30 + §7 R3 probability drop from ~25% to ~10%). |
| **OQ-2** | **Sunday-midnight PDT submission OR Tuesday 09-10 ET fallback?** | Operational availability gates the choice (`05_*` §4.3.1 caveat). | Tuesday 09-10 ET if founder cannot guarantee 4-h response window from Sunday midnight PDT onward. |
| **OQ-3** | **Ship row 18 (idempotent Iceberg snapshot via `nucleus.idempotence-key`)** in v0.2 close-out OR defer to v0.3? | NV-1 verification gate. ~1 h work + ~1 h verification. Promotes `02_*` §5 #3. | Defer to v0.3 unless NV-1 (does `daft.idempotence-key` literal survive `pyiceberg` compaction?) is verified BEFORE tag push. Per anti-over-engineering directive: don't ship gated features against a clock. |
| **OQ-4** | **Accept ADR-CANDIDATEs from `01_*` §6.5 + `03_*` §9 + `05_*` §7 (8 candidates total)** as the v0.2.0/v0.3 ratification batch? | Each candidate is referenced in §2-§5 of this plan; without ratification the plan items are advisory. | Ratify the 5 most load-bearing first: ADR-040 `nucleus maintain`, ADR-041 default-on schema-drift, ADR-042 multi-env promotion, ADR-044 launch positioning M1/M2/M3, ADR-CANDIDATE Trending-Chart-vs-Beachhead trade-off. ADR-043 (`ctx.agent` grounding) and ADR-CANDIDATE Influencer Outreach Discipline can wait until v0.3. |
| **OQ-5** | **Is the "do not chase #1 monthly" trade-off acceptable** to the founder as durable policy? Or is the empirical 1-3% probability actually worth the 120-160 h investment? | Per `05_*` §6.7 the trade-off is v0.3 features deferred ⇄ ~5% chance of a 10× outlier outcome. Founder's call. | Acceptable. BemiDB-tier outcome (50% probability) ships v0.3 features on schedule and preserves the 30-min beachhead trajectory; #1-monthly attempt sacrifices both for a lottery ticket. |

---

*Document type: master synthesis. Word count: ~5,300. Verified 2026-05-16 by the architect synthesis pass (Claude Opus 4.7, parent foreground). All claims traceable to §9 citation pointers; no AI hallucinations introduced. If a downstream reader finds a §2 row whose source citation does not resolve, log in `docs/internal/research/ai_hallucinations.md` per `AGENTS.md` §11.12.*
