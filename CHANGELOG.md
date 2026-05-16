# Changelog

All notable changes to **Nucleus** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Per v4.1 §13.3, AI-related APIs (`ctx.agent`, `ctx.copilot`) may have breaking
changes within minor releases with `NucleusAIBreakingChange` warnings instead of
the full deprecation cycle that core data APIs receive.

---

## [Unreleased]

> Post-v0.2.0 GA work in flight. Move new bullets here as PRs land.

### Fixed
- **CI workflows now run on `nucleus-data/nucleus`** — three-fix bundle: (1)
  `setup-uv@v3` `cache-dependency-glob` points at `pyproject.toml` (we don't
  ship `uv.lock`; the default `**/uv.lock` glob was zero-matching and failing
  all 5 jobs), (2) `pip-audit` bumped 2.7.3 → 2.10.0 so cyclonedx-bom 5.1.1's
  `cyclonedx-python-lib>=8` requirement resolves (2.7.3 capped at `<8`), and
  (3) `.gitignore` `site/` entries anchored to `/site/` so `docs/site/` source
  (90 mkdocs pages from Wave 1C docs-site builder) is tracked instead of
  silently excluded. Unblocks 13 of 14 failing checks; CodeQL still requires
  founder repo-settings change (enable Code scanning).

---

## [0.2.0] — 2026-05-15

> Wave 1 (11 autonomous builders, 2026-05-14 → 2026-05-15) + Wave 2 P0-1/P0-2/P0-3 reliability hardening + Workbench v0.3 interactive polish + uv/ruff toolchain + `nucleus.db` BI handshake + Iceberg branch/tag CLI + **v0.2 close-out batch** (chaos translate-leak fixes, UX polish, ADR-039, governance bumps) + **ultimate-sprint close-out** (cross-test flake fix, layering ADR-040, `nucleus list` subapp registration, README hero polish, vocab + ADR-012 gcsfs governance bake-in). Beachhead validated (8/8 WSL E2E gates); PoC #5 external-tester kit ready.

### Ultimate-sprint close-out (2026-05-16, post-Wave-2 + post-close-out-batch)

#### Fixed
- **Cross-directory test_expire_wraps_pyiceberg_exception flake resolved** — M5 mock snapshots now use a 0.1-day timestamp spread (matching M4) so multiple `_make_snapshot` calls on fast hardware never land in the same millisecond. The strict `s.timestamp_ms < expire_before_ms` candidate filter in `coordination/snapshot_maintenance.expire_old_snapshots` now always finds candidates → `commit()` always runs → `DID NOT RAISE NucleusMaintenanceError` stops firing in the full pytest sweep. Verified PASS on Windows 2026-05-16 across the 891-test full sweep.
- **CLI ↔ Workbench peer-import layering FAIL cleared** — `scripts/check_layering.py` refactored from `LAYERS.index(...)` order comparison to a `LAYER_DEPTH: dict[str, int]` keyed by architectural depth. `ctx`, `cli`, and `workbench` all share depth `4` as Layer 4 (Experience) surfaces per `docs/specs/nucleus_architecture_v4.1.md` §8.1; peer-imports between same-depth surfaces are explicitly allowed. Downward enforcement and cross-engine rule unchanged. ADR-040 (ACCEPTED 2026-05-15) documents the decision; verification §re-verified 2026-05-16. `cli/main.py:1334` (`from nucleus.workbench.cli import app`) now PASSes governance.
- **`nucleus list` registered as Typer subapp** — main.py's inline `@app.command(name="list") def list_assets` scaffold (text/json only) replaced by `app.add_typer(_list_app, name="list", help="...")` mounting the richer `cli/commands/list.py` subapp. `nucleus list` now surfaces `--namespace` filter, `--format jsonl` alias, and Iceberg-catalog-backed materialization status (PoC #5 Checkpoint 7 closer). `tests/cli/commands/test_list.py` 12/12 PASS through both the standalone subapp and the main-app integration.
- **Vocabulary banned-term hits cleared** — Two intentional negations of "AI-first" (the `AGENTS.md` §8 forbidden framing being explicitly rejected) in `docs/HANDOVER.md` line 14 and `docs/release/launch_kit/WOW_MOMENTS.md` line 120 now carry inline `<!-- banned-term: AI-first -->` self-suppressions, matching the existing pattern at WOW_MOMENTS.md line 148 and HANDOVER.md lines 16/466/616. `scripts/check_vocabulary.py` SKIP_PATTERNS gains `.scratch/` so transient agent-worker commit-message drafts (already git-ignored) no longer pollute the gate.
- **Stale orphaned site docs deleted** — `docs/site/cli-reference/list.md` (107 lines, never wired into `mkdocs.yml`) removed. The live, more detailed reference lives at `docs/cli/list.md` (141 lines).

#### Added
- **README.md hero rewrite** — Lines 10-80 replaced with the launch-day hero per `docs/release/launch_kit/README_HERO_PATCH.md` (synthesised with `WOW_MOMENTS.md` §"Five proposed README improvements"). Front-loads the 60-second demo, surfaces a 3-command quickstart, replaces the 5-row vendor matrix with a 1-row persona matrix, adds the PyPI version + Docs badges, demotes the "v0.1 beta" badge to "v0.2 beta", deletes the `git clone ... pip install -e .[dev]` developer-only install path (now in CONTRIBUTING.md), keeps Five Pillars / Architecture / ctx SDK / CLI / Yield-to-giants / Repository / Acknowledgments blocks unchanged.
- **`docs/decisions/ADR-040-cli-workbench-peer-import.md`** — ACCEPTED 2026-05-15. Documents the cli ↔ workbench peer-import allowance with rationale (Path B — peer-import allow), forces analysed (strict directional rule vs architecture intent vs anti-over-engineering vs dbt/Cursor/Vercel UX), and alternatives rejected (workbench-side register hook; setuptools entry-points). Verification re-confirmed 2026-05-16.
- **`docs/release/v0.2.0_FINAL_STATE.md`** — Pre-launch summary the founder reads before working `FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`. Lists the close-out commits, governance scores, pytest status, LOC budget, pre-existing failures still red (with rationale), founder-gated remaining items, and a one-line confidence verdict.

#### Changed
- **ADR-012 Runtime pin matrix** — `gcsfs==2026.5.0` promoted from amendment-paragraph fallback (where `scripts/upgrade_smoke.py adr_012_cross_check` was already picking it up) into a canonical matrix row. BSD-3-Clause · GREEN · pairs with `s3fs==2026.4.0` cadence (both fsspec-family). Origin: ADR-020 (object-storage connectors via DuckDB httpfs). The 2026-05-15 amendment paragraph is retained as audit trail per the ADR-012 §Trigger rule ("amendments are additive only").
- **`.github/workflows/release.yml`** — Adds `python scripts/check_install_size.py` to the governance gate step, restoring parity with `docs/release/PACKAGING_COMPLETENESS_AUDIT.md` §8 (11/11 governance scripts in CI).

#### Verification
- 11/11 governance scripts EXIT 0 locally (vocabulary / pinning / loc_budget / dagster_leak / error_codes / api_stability / layering / licenses / install_size / lazy_imports / changelog).
- `python scripts/upgrade_smoke.py`: all gates PASS except the pytest --cov-fail-under=70 + 4 pre-existing test failures documented in `docs/release/v0.2.0_FINAL_STATE.md` §"Pre-existing failures still red".
- LOC budget: `src/nucleus/=8506 LOC / 18000 ceiling (GREEN)` — 47.3 % of v0.2 phase ceiling.
- `tests/cli/commands/test_list.py`: 12/12 PASS.
- `tests/coordination/test_snapshot_maintenance.py`: 9/9 PASS (in isolation, per-directory, and full sweep).

### v0.2 close-out batch (2026-05-15, post-Wave-2)

#### Fixed
- **Chaos J3 / CF-1 closed (FileExistsError leak)** — `coordination/asset_materialization.py:_commit_to_iceberg` wraps `warehouse_dir.mkdir(parents=True, exist_ok=True)` in `translate()`. `exist_ok=True` does NOT suppress FileExistsError when the target is a non-directory entry (per Python pathlib docs), so the raw stdlib classname was leaking through. Per `docs/release/chaos_test_results.md` §J3.
- **Chaos J8 / CF-2 + CF-3 closed (pydantic.ValidationError leak)** — `cli/main.py:_execute_sql` widens the existing `try/except` to wrap `_open_iceberg_catalog` + `_register_catalog_in_duckdb` calls. New `_pydantic_validation_handler` in `coordination/error_translation.py` routes `pydantic.ValidationError` → `NucleusCatalogError` (NE1007). Registered BEFORE `ValueError` in the registry because pydantic v2 `ValidationError` subclasses `ValueError`. Per chaos_test_results.md §J8.
- **`NucleusRaceConditionDuringWrite` (NE5018)** — new error class + `_file_exists_handler` routing builtin `FileExistsError` → NE5018. Stub docs at `docs/errors/race-condition-during-write.md`. L4 Experience layer per ADR-006.

#### Added
- **ADR-039 install-size split (ratified retroactively)** — `docs/decisions/ADR-039-install-size-split-extras.md` documents the layered-extras pattern (core / postgres / mysql / snowflake / s3 / gcs / ai / workbench / observability / lineage-advanced / all). The code shipped in pyproject.toml lines 41-49 + 105-107; ADR-039 was a phantom citation until now. Status: ACCEPTED.

#### v0.2 UX polish (6 wins from `docs/internal/research/ux_familiarity_audit.md`)
- **Rec #1 — Status word next to dot in `nucleus runs list`** — Title-Case "Succeeded / Failed / Running / Cancelled" labels in CLI table + tail; matches Databricks Lakeflow + Snowflake Task Run History vocabulary. (~30 LOC)
- **Rec #3 — `[NE3002]:` bracket-prefix in error headlines** — `_exit_nucleus_error` + 4 mirrored helpers in `cli/commands/{runs,schedule,snapshot,chat}.py` now emit `Error [NEXXXX]: <message>` so users can grep the NE-code directly. Matches Databricks `[ERROR_CONDITION]` and Snowflake `nnnnnn (sqlstate):` conventions. (~40 LOC across 5 files + 24 test substring updates)
- **Rec #5 — Catalog 3-level namespace chip** — new `frontend/src/components/NamespacePath.tsx` renders the key as `<chip muted>{namespace}</chip> · <chip bold>{name}</chip>` with copy-on-click button. Visual hierarchy signal that 3-level DB/SF users recognise; gracefully extends to true 3-level when Lakekeeper lands at v0.3. (~120 LOC)
- **Rec #6 — Last-materialized timestamp in Workbench Catalog** — `workbench/api/catalog.py` adds `last_materialized` field via RunLedger lookup (resolved ONCE per page request). New `frontend/src/lib/relativeTime.ts` hand-rolled "Xm ago / Yh ago / Zd ago" helper (no date-fns dep — offline bundle promise per ADR-016 §3 Fork B). CatalogPage shows new "Last materialized" column. (~90 LOC backend + 90 LOC frontend)
- **Rec #7 — Cmd-Enter + `?` shortcut help modal** — `App.tsx` adds global `?` hotkey + `UIStore.keyboardHelpOpen` state. New `components/KeyboardHelpModal.tsx` cheatsheet (⌘K / Ctrl-K / `/` / ⌘-Enter / Ctrl-Enter / `?` / `Esc`). `QueryEditor.tsx` wires Monaco `addCommand(KeyMod.CtrlCmd | KeyCode.Enter, run)` via a `useRef` so the keybinding reads the freshest closure. Previous `handleKeyDown` was dead code. (~170 LOC)
- **Rec #8 — `--format jsonl` alias for `--format json`** — `run`, `query`, `list`, `runs list`, `runs show` accept `jsonl` as an NDJSON-explicit synonym. Behaviour identical; signals NDJSON-ness up front for `jq` ecosystem users coming from Databricks / Snowflake JSON-array conventions. (~30 LOC)

#### Docs
- **`docs/internal/research/performance_reliability_targets.md` demoted §2 to v0.3+ aspirational targets** — added status banner + §14 v0.2.0 empirical actuals per `docs/benchmarks/2026-05-15_baseline.md` (boot 2.1 s vs <500 ms claim, B4 Windows concurrent-run FAIL, B2 1 GB +29 %). §7.5 SLOs that DO hold empirically promoted as the v0.2.0 release contract. Anti-Over-Engineering default: "v0.2 actuals; v0.3 targets" honesty over aspirational claims that fail at first user validation. Per close-out checklist §1.9 Option A.
- **`docs/audit/2026-05-15_frozen_worker_audit.md`** — meta-audit document of the 2026-05-15 IDE-crash recovery session. 78 transcripts inspected; zero FROZEN workers; pure sequenced commit pass.
- **`docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md`** — 894-line forward-looking release runbook (founder one-stop document for tag-push, PyPI OIDC, GitHub Pro, PoC #5 outreach).
- **`docs/internal/research/ux_familiarity_audit.md`** — 56 KB Databricks + Snowflake parity research that drove the v0.2 polish bundle above.
- **`docs/errors/race-condition-during-write.md`** — new error reference stub for NE5018.

#### Changed
- **LOC budget phase v0.1 → v0.2** — `scripts/loc_budget.py` adds `"v0.2": 18000` to `PHASE_CEILINGS` and flips `--phase` default. v0.1 (8 K) was historical; v0.2 tracks the §11.6 18 K target. Default report now reads `46.2 % of v0.2 ceiling GREEN` instead of `104 % of v0.1 ceiling RED`.
- **`scripts/check_vocabulary.py` ignores `.venv-*/`** — sibling worker venvs (`.venv-adr039/` etc.) inherit licence / README / docs containing banned terms verbatim; substring exclusion drops 5 false positives per worker pass. Pre-fix: 7 hits; post-fix: 0 hits (the 2 close-out doc hits carry inline `<!-- banned-term: -->` exemptions).

#### Remote infrastructure
- **Origin remote switched** to `github.com/nucleus-data/nucleus` (founder created 2026-05-15). Legacy `github.com/mtoanng/nucleus` preserved as `mtoanng` remote for the mirror. Corrupt `v0.1.0` tag (pointed at orphaned cleanup commit `0a65da5f`) deleted from local + `mtoanng` remote per close-out §1.6 critical-finding recovery; `v0.2.0` local tag also deleted; per close-out §1.3 Option B recommendation v0.1.0 stays unpushed (internal beta, no PyPI artifact). The v0.2.0 tag itself remains FOUNDER-GATED.

### Wave 2 — reliability hardening (P0-1 / P0-2 / P0-3, ADR-024 / ADR-025)

#### Added
- **Active scheduling daemon (Wave 2 P0-1, ADR-017 §v0.2.1 mini-scheduler)** — `@nucleus.asset(schedule=...)` now EXECUTES on schedule. `coordination/daemon.py` implements a lightweight cron-poll loop (5s interval, croniter==3.0.4) that materializes due assets via the AMA. Daemon lifecycle: `nucleus schedule on` (background subprocess, pidfile at `.nucleus/.daemon.pid`), `nucleus schedule off`, `nucleus schedule trigger <key>` (one-shot bypass), `nucleus schedule status` (table). Cross-platform (Windows: psutil TerminateProcess; POSIX: SIGTERM). Zero Dagster classnames in user-facing output. New error codes: NE5012 (DaemonStartError), NE5013 (DaemonNotRunningError), NE5014 (DaemonAlreadyRunningError). ADR-017 amended to IMPLEMENTED.
- **Durable run ledger** (`coordination/run_ledger.py`) — append-only NDJSON persistence at `<project_root>/.nucleus/runs/runs.ndjson`. API: `RunLedger.record_start`, `record_finish`, `list`, `get`, `tail`, `cancel`. Thread-safe; in-memory LRU cache of last 1000 records; tolerates single-line corruption. ADR-025 §P0-2.
- **`nucleus runs` CLI** (`cli/commands/runs.py`) — 4 subcommands: `list` (Rich table with status-dot/run-id/asset/duration/started/trigger), `show` (Rich panel + fix-hint banner), `cancel` (ledger marker), `tail` (live `--follow` mode). `--format json` emits NDJSON per run. Beta tier. ADR-025 §P0-2.
- **`NucleusRunNotFoundError` (NE3011)** — raised by `runs show` / `runs cancel` when the requested run ID is absent from the ledger. fix_hint: "Use `nucleus runs list` to see available run IDs." ADR-006 §1 L2 Coordination.
- **DuckDB memory_limit guard at AMA init (Wave 2 P0-3, ADR-024 P0-1)** — `coordination/asset_materialization.py` now applies `SET memory_limit` (80% of total RAM, clamped [2 GB, 32 GB]) and `SET temp_directory` on every DuckDB connection before the asset body runs. Overridable via `nucleus_project.yaml` `memory_limit` key. OOM conditions surface as `NucleusMemoryLimitExceeded` (NE2007) instead of opaque `NE5001`. 8 tests in `tests/coordination/test_memory_limit.py`.
- **Advisory filesystem lock for concurrent runs (ADR-024 P0-2)** — `coordination/locks.py` cross-platform context manager (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows) prevents two `nucleus run` invocations from racing on the same asset's Iceberg commit (chaos scenario J6). Stale locks (dead PID) auto-reclaimed. `NucleusConcurrentRunError` (NE3008) raised after 30 s timeout. 11 tests in `tests/coordination/test_locks.py`; 4 integration tests in `tests/coordination/test_concurrent_runs.py`.
- **`expire_old_snapshots` post-commit maintenance (ADR-024 P0-3)** — `coordination/snapshot_maintenance.py` calls `table.maintenance.expire_snapshots().older_than(dt).commit()` (pyiceberg 0.11.1 verified API) after each successful commit when snapshot count exceeds 100. Keeps at least 10 recent snapshots regardless of age. Configurable `retain_days` / `min_snapshots`. Maintenance failures are non-fatal (logged; commit not rolled back). `NucleusMaintenanceError` (NE3009). 9 tests in `tests/coordination/test_snapshot_maintenance.py`.
- **Windows `os.rename` → `os.replace` audit** — confirmed zero `os.rename()` calls in `coordination/` source (all paths use `os.replace()` which is atomic on both POSIX and Windows since Python 3.3). 4 tests in `tests/coordination/test_windows_rename.py` enforce this going forward.
- **Error-budget SLO definitions (ADR-024 P0-5)** — `coordination/error_budget.py` defines per-operation `target_p95_ms` / `target_p95_s` and `max_failure_rate` thresholds for 6 operations: boot, materialize_empty, materialize_1gb, query_100mb, ingest_postgres_1m_rows, schedule_resolution. OTEL enforcement deferred to v0.3+. 11 tests in `tests/coordination/test_error_budget.py`.
- **Three new error codes (ADR-024 + ADR-006)** — `NucleusMemoryLimitExceeded` (NE2007, L1 Engines), `NucleusConcurrentRunError` (NE3008, L2 Coordination), `NucleusMaintenanceError` (NE3009, L2 Coordination). All have docs URLs and fix hints.

### Workbench v0.3 — Interactive Polish (post-Wave-1)

#### Added
- **`nucleus.db` BI handshake (`nucleus up`, ADR-026)** — `nucleus up` now generates `<project_root>/nucleus.db` containing one DuckDB table per materialised Iceberg asset (snapshot at boot time). Connect from any DuckDB-compatible BI tool (Superset, Evidence, Rill, Streamlit) via single file path. Superset: `duckdb:////<path>/nucleus.db`. Also writes `_nucleus_catalog_info` metadata table. Non-fatal: first boot with no assets produces valid empty metadata table. 7 tests in `tests/coordination/test_bi_handshake.py`. Cookbook: `docs/cookbook/bi-connectivity.md`. (ADR-026)
- **`nucleus snapshot` CLI — Iceberg branch + tag management (ADR-028, Beta)** — `nucleus snapshot branch create/delete` and `nucleus snapshot tag create/delete` + `nucleus snapshot list` expose PyIceberg's `table.manage_snapshots()` API for snapshot isolation workflows. Useful for compliance archiving (EOW/EOM tags) and pre-commit audit branches. Full WAP (branch-targeted writes) deferred to v0.3 pending Lakekeeper. New error codes `NucleusSnapshotNotFoundError` (NE5015), `NucleusBranchAlreadyExistsError` (NE5016). 10 tests in `tests/cli/commands/test_snapshot.py`. PyIceberg API docs: https://py.iceberg.apache.org/api/#snapshot-management (ADR-028)
- **`scripts/check_perf_budget.py` stub (ADR-023)** — placeholder script that prints the v0.2 performance budget table and exits 0. Full nightly benchmark automation deferred to v0.3.
- **Metallic-noise hero** — `feTurbulence` base frequency 0.75→0.65, rect opacity 0.03→1.0, `::before` CSS opacity 0.18→0.40 with `mix-blend-mode: overlay` and `feColorMatrix saturate=0`; cards gain 0.06-opacity multiply grain for consistent metallic texture across surfaces.
- **Assets page** — full grid of clickable asset cards (filter input, schedule/contract/checks badges) replacing the "Coming soon" stub.
- **Asset detail slide-over** — click any asset card → right-side panel showing deps, schedule, contract status, checks list, and a live **Materialize** button that triggers `/api/runs/trigger`, then streams SSE logs from `/api/runs/{run_id}/log` in a dark terminal panel.
- **Runs page** — full table of materialization runs (status badge, asset, duration, started, rows) with status filter chips (All / Success / Failure / Running) and client-side asset search. Auto-refreshes every 6 seconds.
- **Run detail slide-over** — click any run row → right-side panel with run metadata + SSE log stream via `EventSource`.
- **Query page** — SQL textarea with Ctrl+Enter shortcut, example presets, and a scrollable tabular result preview consuming `/api/query`. Shows truncation banner when `truncated: true`.
- **Schedules page** — 7-day visual timeline (dot matrix per asset × day) + per-schedule card listing next run times; consumes `/api/schedules`.
- **⌘K Command Palette** — search bar now opens a full command palette (keyboard-navigable) that queries `/api/search` for assets, runs, and schedules and navigates to the matching page.
- **Dashboard clickability** — Recent materializations rows → run detail slide-over; DAG asset nodes → asset detail slide-over; "View all" → Runs page.

#### Changed
- **ruff upgrade `0.8.4` → `0.15.13` (ADR-027)** — adopted ruff 2026 style guide; ran `ruff format .` (107 files reformatted). Added `astral-sh/setup-uv@v3` to all 5 CI jobs replacing `pip install` (~2m 15s → ~8s). Updated `.pre-commit-config.yaml` ruff hook. Added `PLC0415`/`SIM105`/`N818`/`RUF022` to ignore list (intentional patterns). Rollback: `pip install ruff==0.8.4`. Docs: https://docs.astral.sh/ruff/ (ADR-027)
- **Makefile `install` target** — uses `uv pip install -e ".[dev]"` if `uv` is on PATH, falls back to pip.

#### Docs
- **ADR-018..025 ratified** — all 8 Wave 1 ADRs flipped PROPOSED → ACCEPTED (ADR-018 was already ACCEPTED). Ratification date: 2026-05-15; shipped code: commit a41a82c (v0.2.0 handover bundle).
- **ADR-026, ADR-027, ADR-028** flipped PROPOSED → ACCEPTED (code shipped in this bundle).
- **`docs/cookbook/bi-connectivity.md`** — new cookbook page: "Connect Superset/Evidence/Rill/Streamlit to Nucleus via `nucleus.db`" with concrete connect-string examples for all 4 BI tools.
- **`docs/compatibility.md`** — ruff row updated to `0.15.13`.

#### Fixed
- **workbench:** Offline-first static index.html — embedded Tailwind/React via local `static/vendor/`, system font stack, inline SVG icons replacing `lucide-react`. Fixes blank page on corporate networks blocking `cdn.tailwindcss.com`/`fonts.googleapis.com`/`esm.sh`. (ADR-016 Fork B)

### Wave 1 bundle (initial v0.2.0 handover commit `a41a82c`, 2026-05-15)

> 11 autonomous builders (2026-05-14 → 2026-05-15). Beachhead validated (8/8 WSL E2E gates); PoC #5 external-tester kit ready.

### Added
- **Public documentation site** (`docs/site/`) — ~55-page MkDocs Material site covering installation, quickstart, concepts, guides, cookbook, CLI reference, API reference, errors, governance, and philosophy. Stack: `mkdocs==1.6.1`, `mkdocs-material==9.5.49`, `mkdocstrings[python]==0.27.0`, `mkdocs-include-markdown-plugin==7.2.2`, `mkdocs-glightbox==0.5.2`, `pymdown-extensions==10.21.3`. Serves at `mkdocs serve` locally; build CI in `.github/workflows/docs.yml`. ADR-021 PROPOSED.
- **Connector expansion — 4 new ingest sources (ADR-019 PROPOSED + ADR-020 PROPOSED, Beta-tier)** — `nucleus.ctx.copy_from()` dispatcher now routes `snowflake://`, `s3://`, `gs://`, `file://`, and relative paths in addition to existing SQL sources. Four new per-source helpers: `ingest_snowflake_to_iceberg()` (dlt[snowflake]==1.26.0, optional `nucleus[snowflake]`), `ingest_s3_to_iceberg()` (DuckDB httpfs, no new deps), `ingest_gcs_to_iceberg()` (gcsfs==2026.5.0, optional `nucleus[gcs]`), `ingest_filesystem_to_iceberg()` (DuckDB, no new deps). All support Parquet/CSV/JSON with format auto-detection and glob patterns. 40 new unit tests across `tests/ctx/`; 0 raw external classnames in user-facing error messages. New optional extras `nucleus[snowflake]`, `nucleus[gcs]`.
- **Workbench Editorial Hero v0.2 redesign** — complete frontend redesign replacing the Sidebar-centric layout with an editorial gradient hero dashboard (matching the founder-picked visual reference, 2026-05-15). Dashboard (`/`) renders a bold blue gradient hero with huge "Today's pipeline" H1, four glassmorphism stat chips (total assets / rows / checks green / last run ago), and a 3-column body grid (Recent Runs card | Pipeline DAG card | AI Copilot card — always-on, not a drawer). `TopNav` floats transparently over the hero gradient and turns solid on all other pages. Theme toggle descoped; editorial light theme only.
- **7 new frontend routes**: `/` (Dashboard), `/assets/:key` (Asset Detail), `/runs/:run_id` (Run Detail with live SSE log stream), `/schedules` (Schedule list + next-run preview), `/catalog` (paginated asset catalog browser). All routes code-split via `React.lazy`.
- **4 new backend API endpoints**: `GET /api/dashboard/summary` (hero stat chips + recent runs in one call), `GET /api/schedules` + `GET /api/schedules/{key}/preview` (wraps `nucleus.coordination.schedules`), `GET /api/catalog` (paginated/filterable asset list), `GET /api/search?q=` (global search across assets + runs + schedules for ⌘K palette).
- **`POST /api/runs/trigger`** — triggers an immediate asset materialization from the Workbench UI (fire-and-forget background thread in v0.2; v0.3 routes through the embedded orchestration layer).
- **Real ⌘K Command Palette** (`components/CommandPalette.tsx`) — replaces the static navigation stub. Full keyboard navigation (↑/↓/Enter), live search via `/api/search`, result categories (assets / runs / schedules), triggered by `⌘K`, `Ctrl+K`, or `/`.
- **Live SSE log streaming** in `RunDetailPage.tsx` — subscribes to `GET /api/runs/{id}/log` SSE stream via `EventSource`; log lines appear in real-time during active materializations.
- **New components**: `TopNav`, `StatChip`, `BlobAvatar` (animated iridescent orb), `SuggestionChip`, `CopilotCard`, `RecentRunsCard`, `PipelineDAGCard`. AssetDAG updated with `constrained` prop (card mode vs full mode).
- **CDN static fallback redesigned** (`static/index.html`) to render the full Editorial Hero layout (gradient hero, stat chips, 3-col grid, SVG mini-DAG, blob avatar Copilot card) without a build step. JetBrains Mono + Inter loaded from Google Fonts.
- **Asset Detail page** (`/assets/:key`) — deps, checks, recent materializations for that asset, "Run" trigger button.
- **Run Detail page** (`/runs/:run_id`) — metadata (asset key, status, duration, rows, snapshot) + dark terminal log viewer with live SSE stream.
- **Schedules page** (`/schedules`) — expandable cards showing cron expression, description, and next N run times.
- **Catalog page** (`/catalog`) — sortable/filterable table of all registered assets with namespace, schedule, contract, checks, dep count, compute columns; pagination.
- Loading skeletons, empty states, error states on all new pages and cards; page fade-in transitions; animated button presses; focus management; ARIA labels on icon-only buttons.
- Responsive breakpoints: ≥ 1280px ideal, ≥ 1024px 2-col, ≥ 768px 1-col.
- **Scheduling exposure (ADR-017 PROPOSED, Beta-tier)** — `@nucleus.asset(schedule="@daily")` / `@nucleus.asset(schedule="0 2 * * *")` accepts cron strings + shorthand aliases (`@hourly`/`@daily`/`@midnight`/`@weekly`/`@monthly`/`@yearly`/`@annually`). Validated at decoration time via the wrapped `croniter` library; preview the next N runs with `nucleus schedule preview <key>` and inspect the full registry with `nucleus schedule list`. The actual scheduling daemon is deferred to v0.2; `nucleus schedule on/off/trigger` raise `NucleusFeatureDeferredError` (NE5008) with a structured v0.2 message. New error codes `NucleusScheduleParseError` (NE5005), `NucleusScheduleNotFoundError` (NE5006), `NucleusScheduleAlreadyActiveError` (NE5007 — reserved), `NucleusFeatureDeferredError` (NE5008). New pin `croniter==3.0.4` (latest `<4` release compatible with `dagster==1.9.5`'s transitive constraint). 72 new tests across `tests/sdk/test_schedule_kwarg.py` + `tests/coordination/test_schedules.py` + `tests/cli/commands/test_schedule.py`. Stability tier: Beta @ v0.1.1, gated on founder ratification of ADR-017.
- examples/01-ecommerce-elt + examples/02-iot-sensor-rollup; README + quickstart polish for v0.1 beta launch.
- CI/CD + community scaffolding (ADR-022 PROPOSED): `.github/CODEOWNERS`, Dependabot caps, Funding placeholders; `SECURITY.md` disclosure policy; Contributor Covenant Code of Conduct; `SUPPORT.md`, `GOVERNANCE.md`, `MAINTAINERS.md`; streamlined `.pre-commit-config.yaml` subset; Makefile targets `release-check`, `pre-commit-install`, `docker-build`, `docker-demo`, `governance-all`; `scripts/release.py` release gate (optional `--no-pytest` governance-only shortcut) plus printable tag steps; hardened `scripts/check_changelog.py` (`[skip-changelog]` + shallow-repo skip); vocabulary scanner skips `docs/dev-guides/` until those guides pick up glossary markup; Docker multi-stage `docker/Dockerfile.nucleus` + `docker-compose.demo.yml` (MinIO + CLI image); upstream MinIO sidecar sketch `docker/Dockerfile.minio-sidecar`; issue form `wrap_request.yml` for wrap-vs-build proposals.

### Changed
- _placeholder._

### Fixed
- Postgres ingest (`copy_from_postgres`): one error-translation try block now wraps `sql_table(...)` and `pipeline.run(...)` so SQLAlchemy/psycopg failures during resource construction (reflection / connect) raise `NucleusSourceAuthError` / `NucleusSourceConnectionError` (NE1009 / NE1001) instead of raw `OperationalError` tracebacks.

---

## [0.1.0] — 2026-05-14 (Tier 1 Foundation — beachhead beta)

> Phase gate: **released (beta)**. `pyproject.toml` now declares `version = "0.1.0"`.
> Empirical proof-of-life: WSL beachhead E2E 8/8 PASS — boot 7 s (<10 s goal), real
> Iceberg snapshot `7070059669214185406` written through wrapped pyiceberg, zero
> forbidden-classname leaks. v4.1 §1.5 30-minute target met for the 5-engineer startup
> persona on Windows-with-WSL and Linux. PoC #5 external-tester recruitment is the gate
> for the public announcement; the code is shipping under the `0.1.0` semver line now.

### Added — v0.1 launch wave (2026-05-13 → 2026-05-14)
- `nucleus ingest mysql://...` — MySQL source via wrapped `dlt` (ADR-014 amended 2026-05-14; same `sql_database` verified source as Postgres; `pymysql==1.1.1` driver — already pinned). Parity with the existing Postgres + SQLite paths through `nucleus.ctx.copy_from`. New `src/nucleus/ctx/copy_from_mysql.py` plus `_translate_dlt_mysql_exception` in `coordination/error_translation.py`; `_dispatch.py` adds `mysql://` and `mysql+pymysql://` schemes; full mocked-unit + upgrade-smoke test coverage in `tests/ctx/test_copy_from_mysql.py` and `tests/upgrade_smoke/test_dlt_mysql.py`.
- ADR-007 **License Resolution (2026-05-14)** — verified SPDX / upstream citations for `openlineage-python==1.47.1`, `s3fs==2026.4.0`, `orjson==3.11.9`, `psycopg==3.2.3` + MPL / LGPL boundary notes; `scripts/check_licenses.py` baked-in fallbacks updated.

### Changed — v0.1 launch wave
- Promoted `nucleus up` and `nucleus down` from stub to real implementations. Wraps `docker compose` (v2 with v1 fallback) over a `docker-compose.yaml` shipped by `nucleus init`. MinIO health-check via `httpx`; clean error translation for missing docker, port conflicts, image-pull failures, and 30 s health-check timeout. Closes the last v4.1 beachhead-critical CLI gap. (See `tests/cli/test_up.py` + `tests/cli/test_down.py`.)
- Runtime dependency surface tightened per Option α-split (drift-detection verifier MEDIUM #3): `opentelemetry-sdk==1.29.0` and `sqlglot==26.0.0` moved to `[project.optional-dependencies]` (`observability` + `lineage-advanced`); `msgspec==0.18.6` removed entirely. Default `pip install nucleus` install size shrinks ~2 MB (OpenTelemetry SDK + `opentelemetry-semantic-conventions` ≈ 1.5 MB; msgspec ≈ 0.5 MB; sqlglot still arrives transitively via `dlt` per `pip show dlt` 2026-05-14). ADR-011 + ADR-012 amended in place; pin count revised 25 → 23 core + 2 optional. No source code changes (zero v0.1 callers under `src/`, `tests/`, `poc/`, `scripts/`). `scripts/check_pinning.py` extended (~50 LOC) to enforce exact-pin discipline on the new runtime-extras tier and to surface mandatory-vs-optional pin counts in its summary line. New regression-lock suite at `tests/upgrade_smoke/test_optional_extras.py` (9 tests) guards the install matrix. See `docs/internal/research/otel_day1_decision.md` §D1-D3 for the full rationale.
- `click==8.1.7` → `click==8.1.8` (Constraint #11 single-component bump) so the declared pin matches `litellm==1.83.14`’s `click==8.1.8` requirement. Changelog: https://github.com/pallets/click/blob/main/CHANGES.rst (`Version 8.1.8`). Companion updates: ADR-012, `docs/compatibility.md`, `.pre-commit-config.yaml`, `docs/specs/nucleus_cli_spec.md`. Rollback: `pip install click==8.1.7`.
- `scripts/upgrade_smoke.py` — ADR-012 cross-check now unions mandatory `[project.dependencies]` pins with optional-runtime extras (`observability`, `lineage-advanced`) so the matrix matches `pyproject.toml` after Option α-split (2026-05-14).

### Fixed — v0.1 launch wave
- `pyproject.toml`: `jinja2` 3.1.5 → 3.1.6 to align with `litellm==1.83.14` transitive exact pin (`litellm` hard-locks `jinja2==3.1.6` in wheel metadata; cold install was failing with `ERROR: Cannot install jinja2==3.1.5` on clean envs). 3.1.6 is also a security release (GHSA-cpwx-vrp4-4pq7). ADR-012 + `docs/compatibility.md` updated. Caught by WSL beachhead E2E 2026-05-14.
- ADR-005 §2 schedule amended 2026-05-14: `ctx.write`, `ctx.log`, and `ctx.params` are **DEFERRED (v0.2+)** — not exported in v0.1 per `src/nucleus/ctx/__init__.py` / `docs/specs/nucleus_architecture_v4.1.md` §13.1; substitutes remain asset returns, stdlib `logging`, and CLI/config.
- `nucleus ingest mysql://...` CLI scheme allow-list now matches the dispatcher (post-Worker-B cleanup) — previously rejected at the CLI pre-flight even though `ctx.copy_from` accepted MySQL.
- `_V01_COMMANDS` smoke matrix in `tests/cli/test_main.py` extended from 7 → 8 commands so `chat` is exercised by every per-command `--help` test (ADR-015 surface parity).
- `_copy_traversable` in `nucleus init` now silently skips `__pycache__/` and `*.pyc`/`*.pyo` artefacts — prevents a `UnicodeDecodeError` when the installed `templates/v01/` tree has been touched by `compileall` (caught in the 2026-05-14 polish wave).
- Asset Materialization Adapter rewired to **Option A** (direct invocation + `pyiceberg.append`/`overwrite`); Dagster is still wrapped for asset graph + run lifecycle, but the data path no longer routes through Dagster's `PickledObjectFilesystemIOManager`. Caught by WSL E2E Run #1 (`nucleus run example.greeting` failed to write to Iceberg + leaked Dagster log surface). Run #2 confirmed real snapshot IDs, real metadata.json, and zero classname leaks.

### Added — Architecture and core

- `docs/specs/nucleus_architecture_v4.1.md` — five-layer architecture (Physics / Engines / Coordination / Intelligence / Experience) and roadmap (§18) governing v0.1 scope.
- `src/nucleus/errors.py` — `NucleusError` base plus 32 concrete subclasses with `error_code` ClassVars (ADR-006).
- `docs/decisions/README.md` — ADR-001 through ADR-016 recorded ACCEPTED (strategy, pins, SDK freeze, errors, connectors, Workbench); see per-ADR files under `docs/decisions/`.

### Added — `ctx` package (Layer 4)

- `src/nucleus/ctx/__init__.py` — exports `copy_from`, `sql`, `read`, `ingest_sqlite_to_iceberg`, `ingest_postgres_to_iceberg`, `ingest_mysql_to_iceberg`, and `NucleusError` (stability tiers per ADR-005 in the module docstring).
- `src/nucleus/ctx/_dispatch.py` — unified `copy_from` entrypoint dispatching SQLite, Postgres, and MySQL paths (MySQL co-default landed 2026-05-14).
- `src/nucleus/ctx/copy_from.py` — SQLite source → Iceberg materialization helper (promoted from PoC #3).
- `src/nucleus/ctx/copy_from_postgres.py` — Postgres → Iceberg via wrapped dlt (ADR-014).
- `src/nucleus/ctx/copy_from_mysql.py` — MySQL → Iceberg via wrapped dlt + pymysql (ADR-014 §"MySQL parity (2026-05-14)").
- `src/nucleus/ctx/sql.py` — Jinja-aware SQL execution against the local warehouse (pairs with `coordination/sql_resolver.py`).
- `src/nucleus/ctx/read.py` — lazy reads of materialized assets for CLI `query` / SDK flows.

### Added — SDK surface

- `src/nucleus/sdk/decorators.py` — `@nucleus.asset` and `@nucleus.check` registration.
- `src/nucleus/sdk/materialize.py` — `materialize()` for asset runs (ADR-013).
- `src/nucleus/sdk/results.py` — `MaterializationResult`, `AssetRef`, and `CheckResult` value types.
- `src/nucleus/sdk/contracts.py` — runtime schema contracts (NE3007).

### Added — Coordination (Layer 3)

- `src/nucleus/coordination/error_translation.py` — Error Translation Layer at external boundaries (promoted from PoC #1).
- `src/nucleus/coordination/sql_resolver.py` — native Jinja + `ref` resolution for `ctx.sql` (promoted from PoC #2).
- `src/nucleus/coordination/asset_materialization.py` — Asset Materialization Adapter wrapping Dagster `materialize`.
- `src/nucleus/coordination/lineage.py` — asset-level OpenLineage NDJSON emission (FileTransport).

### Added — Engines and physics (wrappers)

- `src/nucleus/engines/__init__.py`, `src/nucleus/physics/__init__.py` — layer placeholders (1 LOC each); DuckDB, Polars, pyiceberg, and Dagster are consumed via ctx and coordination code with exact pins in `pyproject.toml` (ADR-012).

### Added — CLI (Layer 5)

- `src/nucleus/cli/main.py` — eight v0.1 commands wired: `init`, `up`, `down`, `run`, `ingest`, `query`, `chat`, `version`.
- `src/nucleus/cli/rendering.py` — shared CLI rendering helpers (Rich tables, endpoint formatting).
- `src/nucleus/cli/commands/` — command modules imported by `main.py`, including the `chat` subcommand introduced by ADR-015.
- `src/nucleus/cli/_compose.py` — Docker Compose wrapper powering real `nucleus up` / `nucleus down` with httpx health polling and clean error translation.

### Added — Intelligence (Layer 4) — AI Chat MVP (ADR-015)

- `src/nucleus/intelligence/copilot.py`, `intelligence/context.py`, `intelligence/translate.py`, `intelligence/__init__.py` — `nucleus chat` wraps `litellm==1.83.14` to expose a single CLI entry into a developer's chosen model (OpenAI / Anthropic / etc.). Five new `NE4xxx` error codes in `errors.py` cover missing API keys, transport errors, and provider-name leak prevention (regex-stripped, case-insensitive).
- `src/nucleus/cli/commands/chat.py` — CLI subcommand surface.

### Added — Workbench scaffold (ADR-016)

- `src/nucleus/workbench/app.py`, `src/nucleus/workbench/cli.py` — FastAPI entrypoints; ORJSON-oriented JSON responses per ADR-016 and current `fastapi` pin (see `pyproject.toml`).

### Added — Project templates

- `src/nucleus/templates/v01/` — files emitted by `nucleus init` (including example asset under `templates/v01/assets/`).

### Added — Internal utilities

- `src/nucleus/_internal/logging.py` — logging helpers for CLI and services.

### Added — Governance and CI

- `scripts/check_vocabulary.py` — AGENTS.md §7 vocabulary guard.
- `scripts/check_pinning.py` — exact runtime pins (Constraint #11 / ADR-012).
- `scripts/loc_budget.py` — proprietary LOC budget report (§11.6).
- `scripts/dagster_leak_check.py` — forbidden orchestrator surface leak scan (v4.1 §6.4).
- `scripts/check_error_codes.py` — ADR-006 `error_code` completeness.
- `scripts/check_api_stability.py` — ADR-005 public-symbol stability tags.
- `scripts/check_layering.py` — package import-direction rules.
- `scripts/check_licenses.py` — ADR-007 license tiers on runtime deps.
- `scripts/check_bundle_size.py` — optional bundle-size gate (scaffold stage).
- `.github/workflows/ci.yml` — Ubuntu, Python 3.11, `pip install -e ".[dev]"`, Ruff on `src/nucleus/ctx`, `scripts`, `poc`, `tests` with `--exclude tests/ctx`, required governance steps, then `pytest tests/ poc/`.

### Added — Documentation artifacts

- `docs/decisions/README.md` — ADR index (001–016 ACCEPTED at snapshot time).
- `docs/compatibility.md` — pin matrix companion to ADR-012.
- `docs/errors/` — error slug stubs referenced by `docs_url` conventions.
- `docs/specs/nucleus_poc_plan.md` — PoC #1–#5 status and criteria.

### Errors / error translation

- ADR-006 NE-code bands implemented across `src/nucleus/errors.py`; orchestration and engine exceptions are translated in `coordination/error_translation.py` with CI enforcement via `dagster_leak_check.py` and pytest suites under `tests/coordination/` and `poc/p1_error_translation/`.

### Known limitations (deferred)

- `ctx.write`, `ctx.log`, `ctx.params` — not surfaced yet; use asset return values, stdlib `logging`, and CLI/config respectively (per `ctx/__init__.py` docstring).
- Intelligence CLI chat paths (`src/nucleus/intelligence/`, `cli/commands/chat.py`) — in-repo but omitted from this UNRELEASED draft’s highlights until the founder tags the chat MVP.
- Workbench UI — FastAPI shell only in-repo; rich SPA remains v0.2+ (ADR-016).
- Column-level lineage — v0.5+ (`coordination/lineage.py` is asset-level only).
- Marimo, optional dbt-duckdb — v0.3+ per architecture roadmap.
- Lakekeeper / REST catalog parity — v0.3+; v0.1 stays on filesystem catalog (ADR-004).
- Daft + Ray — yield-to-giants v0.5+.

### Dependencies

- Exact runtime pins: `pyproject.toml`.
- Consolidated matrix and rationale: `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md`.

### Verification snapshot (2026-05-14)

- `pytest -q` — 519 passed / 27 skipped / 0 failed.
- `scripts/loc_budget.py` — 4,166 LOC under `src/nucleus/` (52.1% of v0.1 8 000 LOC ceiling).
- `scripts/check_vocabulary.py`, `check_pinning.py`, `check_layering.py`, `dagster_leak_check.py`, `check_error_codes.py`, `check_api_stability.py`, `check_licenses.py`, `check_bundle_size.py` — 8 / 8 PASS.
- `scripts/upgrade_smoke.py` — 7 / 7 PASS (ADR-012 cross-check + beachhead E2E + pytest sweep).
- WSL beachhead E2E — 8 / 8 gates PASS; boot 7 s; Iceberg snapshot `7070059669214185406`; format-version 2; 3 rows; zero forbidden classnames in CLI output.

[Unreleased]: https://github.com/nucleus-data/nucleus/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nucleus-data/nucleus/releases/tag/v0.1.0

---

## [0.0.0] — 2026-05-12 (Pre-Heartbeat — scaffolding only, no runtime code)

This is not a real release. The project is in the **planning + scaffolding** phase.
No code is installable. This entry exists so the changelog has a starting point.

### Added (pre-code scaffolding)
- Full architecture document (`docs/specs/nucleus_architecture_v4.1.md`, 1678 lines)
  incorporating 13 senior-review amendments and 4 follow-up patches.
- Universal AI-agent rules (`AGENTS.md`) with **11 Hard Constraints**.
- Cursor-specific rules (`.cursor/rules/nucleus.mdc`).
- Proof-of-Concept plan (`docs/specs/nucleus_poc_plan.md`) — 5 PoCs gating v0.1.
- Project scaffolding: `pyproject.toml`, `LICENSE` (Apache 2.0), `.gitignore`, `README.md`.
- Engineering conventions (`docs/conventions/engineering.md`) — 18 sections.
- C4 architecture diagrams (`docs/architecture/C4_context.md`, `C4_container.md`).
- Critical sequence: error translation flow (`docs/architecture/sequence_error_translation.md`).
- ADR template (`docs/decisions/_template.md`) + first ADR (`ADR-001-no-iceberg-commit-service.md`).
- Component compatibility matrix (`docs/compatibility.md`).
- Type-mapping pattern doc (`docs/patterns/type_mapping.md`).
- CI workflows (`.github/workflows/ci.yml`, `upgrade-deps.yml`).
- Issue & PR templates (`.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md`).
- Pre-commit hooks (`.pre-commit-config.yaml`).
- Constraint-enforcement scripts (`scripts/`).
- Junior-DE onboarding & learning path (`docs/onboarding/learning_path.md`).

### Notes
- **No package is published to PyPI.** Versions begin with `0.0.1` when Tier 0
  "Heartbeat" produces a first end-to-end runnable slice.
- Project status: **pre-Heartbeat**, solo founder + AI pair.

---

## Versioning policy

| Version range | Meaning |
|---------------|---------|
| `0.0.x` | Pre-Heartbeat / Heartbeat — pre-alpha, may break anything. |
| `0.1.x` | Tier 1 "Foundation" — beachhead-ready. Beta. **`ctx` SDK signatures stabilizing.** |
| `0.2.x` | Tier 2 "Workbench" — adds web IDE + simple Copilot. |
| `0.3.x` | Tier 3 "Connectors" — Lakekeeper, more sources/sinks, dbt-duckdb adapter. |
| `0.5.x` | Tier 4 "Intelligence" — lineage-aware Copilot + `ctx.agent` runtime. (Semantic Knowledge Graph lands v0.7+.) |
| `1.0.0` | **GA.** `ctx` SDK & error types are **stable** per semver. |
| `2.0.0+` | Future major versions. |

Within `0.y.z`:
- `y` bump = significant new functionality OR documented breaking change.
- `z` bump = bug fixes, minor improvements, doc updates.

After `1.0.0`:
- Standard semver. Breaking changes only in major versions.

### Per v4.1 §13.3
AI-namespace APIs (`ctx.agent`, `ctx.copilot`) may have breaking changes in
**minor** versions with a `NucleusAIBreakingChange` warning, NOT the full
deprecation cycle. Core data APIs (`ctx.read`, `ctx.sql`, `ctx.copy_from`,
`ctx.run`, `ctx.asset`) follow strict semver.

---

## Categories explained

- **Added** — for new features.
- **Changed** — for changes in existing functionality (non-breaking unless noted).
- **Deprecated** — for soon-to-be removed features. Lists the version of removal.
- **Removed** — for now removed features.
- **Fixed** — for bug fixes.
- **Security** — in case of vulnerabilities.

---

## How to update this changelog

1. **Every PR** that affects user-visible behavior adds a bullet under `[Unreleased]`.
2. The bullet links to the PR: `- Added `ctx.copy_from` for Postgres (#42)`.
3. Use **past tense**, **imperative-ish**: "Added X", "Fixed Y".
4. Group by category (Added / Changed / etc.).
5. When releasing:
   - Move `[Unreleased]` content under a new dated version section.
   - Recreate empty `[Unreleased]` template at the top.
   - Tag the release in git: `git tag v0.0.1 && git push --tags`.
   - GitHub Releases page is generated from these entries.

When in doubt, see the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) spec.
