# Nucleus CLI Specification

> **Status**: SPEC v0.1 — locks the command surface for `git clone` → BI-ready Iceberg in <30 min.
> **Date**: 2026-05-13 · **Owner**: Solo founder · **Supersedes**: nothing (first CLI spec; resolves ADR-005 NV #2).
> **Related**: `nucleus_architecture_v4.1.md` (§8 L4, §5.5, §6.4, §11, §18.1) · `nucleus_ctx_sdk_spec.md` (every CLI command delegates to one `ctx.*` call) · `docs/architecture/C4_container.md` §3.1 · ADR-005 §4 (CLI carve-out — this doc is that governance) · ADR-006 (NE-codes in §5.4 + §8) · ADR-007 (`nucleus enable` gating).

---

## 1. Why this exists

The CLI is the first artefact a Nucleus user touches. Per v4.1 §1.5, a 5-engineer team must `git clone`, `nucleus up`, ingest, transform, and query in **<30 minutes**. If `nucleus init` is friction, the project is dead. If `nucleus run` leaks a Dagster stack trace, the wrap-not-build thesis (v4.1 §6.5) collapses. Per `AGENTS.md` §0 the CLI is one third of "the unified developer-first experience" Nucleus owns forever; every §3 command is a thin operator wrapper over one `ctx.*` call. ADR-005 §4 carves the CLI out of the SDK freeze schedule because operator ergonomics need a different cadence than the Python API contract — **this spec is that separate governance**.

Scope: defines the command surface, flag conventions, output contract (text + NDJSON), error contract (NucleusError → exit code per ADR-006), and stability tier of each command. Does **not** define implementation (lives in `src/nucleus/cli/`), output copy (iterates with PoC #5), or marketing strings (lock at v0.1 GA per ADR-002 §8.4).

---

## 2. Stability tiers (ADR-005 CLI carve-out)

ADR-005 §1 defines four SDK tiers (Frozen / Stable / Beta / Internal); §4 carves the CLI out and points here. CLI command **names** freeze at v1.0; **flag taxonomy** + **output wording** stay Beta through v1.5 to absorb PoC #5 + telemetry without ADR-005 §3 breaking-change overhead.

| Command | v0.1 | v0.5 | v1.0 | v2.0 |
|---|---|---|---|---|
| `nucleus init` / `up` / `down` / `run` / `ingest` / `query` / `version` | Beta | Stable | **Frozen** | Frozen |
| `nucleus chat` | (v0.2, **Beta**) | Stable | **Frozen** | Frozen |
| `nucleus schedule list / preview` | (v0.1.1, **Beta** — ADR-017) | Stable | **Frozen** | Frozen |
| `nucleus schedule on / off / trigger` | (v0.2, deferred stubs in v0.1.1 — NE5008) | Beta | Stable | **Frozen** |
| `nucleus snapshot list / restore` | (v0.3+) | Beta | Stable | **Frozen** at v1.5 |
| `nucleus catalog migrate` | (v0.3+) | Beta | Stable | **Frozen** at v1.5 |
| `nucleus enable <feature>` | Beta | Stable | **Frozen** | Frozen |
| `nucleus doctor` | (v0.3+) | Beta | Stable | **Frozen** at v1.5 |
| `nucleus agent` (AI runtime) | n/a | Beta | Beta | **Frozen** at v1.5 — AI carve-out per ADR-005 §4 + v4.1 §13.3 |

Flag-level stability is uniformly **Beta until v1.0** even where the parent command is Stable, mirroring SDK §13. Flag rename in Beta = `CHANGELOG.md` entry; flag rename in Frozen = ADR + deprecation per ADR-005 §3.

---

## 3. v0.1 command surface (Mo 2-8 Hello World)

Each entry gives: **Synopsis** · **Purpose** · **Wraps** (`ctx.*` API) · **Outputs** · **Error exits** (NucleusError → exit code + ADR-006 NE-code) · **Cite arch §**. Asset keys use v4.1 §12.1 form `<namespace>.<name>` (2-level for v0.1 single-catalog scope; 3-level lights up at v0.3 — §10 NV #6).

### 3.1 `nucleus init [PROJECT_NAME]`

`nucleus init [--template <default>] [--no-git] [PROJECT_NAME]` — scaffolds a new project (`nucleus_project.yaml`, `assets/`, `data/`, example asset, optional `git init` suggestion). **v0.1 ships only `--template default`**; `minimal | postgres | csv` preset variants defer to v0.3+ per Anti-Over-Engineering (no real v0.1 user-visible payoff). Omitting `PROJECT_NAME` is not supported in v0.1 (raises `NucleusInvalidAssetDefinition` for ambiguity reasons). **Wraps**: stdlib only (template copy via `importlib.resources`; `git init` is a printed suggestion, NOT a subprocess shell-out, since cross-platform git invocation is fragile). **Outputs**: `Created Nucleus project at <path> (6 files). Next steps: cd <name> && nucleus up`; JSON variant pending `--format json` v0.3+. **Error exits**: dir non-empty → 1 `NucleusIOError` (NE1005); invalid name / unknown template → 1 `NucleusInvalidAssetDefinition` (NE3004) — see §10 NV #4 for the L4 NE5xxx allocation that may supersede in v0.3+. **Cite**: v4.1 §8.2 (project anatomy), §18.1.

### 3.2 `nucleus up [--rebuild]`

`nucleus up [--rebuild] [--catalog filesystem] [--profile <name>]` — starts the local runtime (MinIO via docker-compose, filesystem-backed Iceberg catalog via `pyiceberg.SqlCatalog`, Dagster `Definitions` in-process). **Wraps**: `docker compose up -d minio`; `pyiceberg.catalog.load_catalog(type="sql", ...)`; `dagster.Definitions(assets=...)` per `C4_container.md` §4.1. **Target boot**: **<10s cold, <3s warm** per v4.1 §11.2 / §16.1 and `poc/p4_boot_time/DESIGN.md`. **Outputs**: per-component checkmarks (`✓ MinIO ready` / `✓ Catalog ready` / `✓ Definitions loaded (N assets)`) + final `Nucleus up in <duration>s.` **Error exits**: Docker unreachable → 3 `NucleusDockerUnavailable` (`NE5002`); port 9000 bound → 3 `NucleusPortBound` (`NE5003`); catalog locked → 1. **Cite**: v4.1 §6.1, §5.7, §5.8, §11.1.

### 3.3 `nucleus down`

`nucleus down [--volumes]` — stops the local runtime; **preserves** MinIO docker volumes by default (`warehouse/` data on disk always preserved). Pass `--volumes` (no `-v` short flag — reserved by Typer for global verbosity) to also remove docker volumes, matching `docker compose down --volumes` semantics. **Wraps**: `docker compose down [--volumes]`; no SDK call. **Outputs**: `Nucleus down. Volumes: preserved | removed.` **Error exits**: 0 (idempotent — already-down is success). **Cite**: v4.1 §6.1, §11.1. **Promoted from stub 2026-05-14**: `--keep-volumes`/`--no-keep-volumes` spec variant rejected in favour of `--volumes` (opt-in destroy, default preserve) per the §"Recommendations" entry #5 RESOLVED note.

### 3.4 `nucleus run [ASSET_KEY...]`

`nucleus run [--all] [--changed-only] [--dry-run] [--param KEY=VAL...] [ASSET_KEY...]` — materializes one or more assets (full graph with `--all`); equivalent to one or more `ctx.materialize(...)` calls from a script. **Windows (Beta Tier 2, v0.2.0)**: overlapping two `nucleus run` sessions for the **same asset** can both succeed and commit separate Iceberg snapshots; run serially, coordinate an external lock, or use Linux/macOS until the caveat in [`docs/site/troubleshooting/common-errors.md`](./docs/site/troubleshooting/common-errors.md#concurrent-runs-on-windows-beta-tier-2) is closed in v0.2.1. **Wraps**: iterates `ctx.materialize(asset_key)` once per `ASSET_KEY` (per [ADR-013](./docs/decisions/ADR-013-ctx-materialize-api.md) NV #1 — there is no list-variant; the CLI is the multi-asset surface) → `dagster.materialize(...)` against in-process `Definitions`. AMA handles the 5 steps per v4.1 §6.2 (validate → partition → atomic commit → OL event → registry update). **Outputs**: per-asset status table (key, status, duration, rows) + summary; OL events emit to `FileTransport` per `C4_container.md` §3.6. **Error exits**: any asset fails → 1 with the first error (most likely `NucleusInternalError` `NE3001` for Python body failures; `NucleusSchemaError` `NE2001` for contract mismatch; `NucleusCommitConflictError` `NE1002` for concurrent writes per ADR-006 §Initial). **Cite**: v4.1 §6.2 (AMA), §6.4 (Error Translation — release blocker), ADR-013 (`ctx.materialize` API).

### 3.5 `nucleus ingest <SOURCE_URI> --table <SRC> --as <DEST>`

`nucleus ingest <SOURCE_URI> --table <SRC_TABLE> --as <DEST_KEY> [--mode overwrite|append|merge] [--merge-on <COL>...]` — the **30-min beachhead one-liner** (v4.1 §1.5 mandate). Auto-infers schema, auto-creates the Iceberg destination, pulls rows, commits atomically, prints a 10-row preview. **Wraps**: `ctx.copy_from(source=<URI>, table=<SRC>, target=<DEST>, mode=...)` per SDK §5.3 + v4.1 §5.5.1; impl: SQLAlchemy → pyarrow → pyiceberg `Table.append`/`overwrite`; total path **≤500 LOC** per PoC #3 budget. **Sources (v0.1)**: `postgresql://`, `mysql://`, `sqlite://`, local CSV / Parquet / JSON (six families). **Outputs**: Rich progress bar (`--no-progress` for CI) + final count + 10-row preview; JSON mode: NDJSON status events + summary. **Error exits**: source unreachable → 1 `NucleusSourceConnectionError` (`NE1001` per ADR-006 H1+H17); schema mismatch → 1 `NucleusSchemaError` (`NE2001`); catalog conflict → 1 `NucleusCommitConflictError` (`NE1002`). **Examples**: `nucleus ingest postgres://u:p@host/db --table public.users --as raw.users --mode overwrite` · `nucleus ingest ./orders.csv --as raw.orders --mode append` · `nucleus ingest mysql://... --table orders --as raw.orders --mode merge --merge-on order_id`. **Cite**: v4.1 §5.5.1, §1.5.

### 3.6 `nucleus query <SQL> | --file <PATH> | --asset <KEY>`

`nucleus query [--file <PATH>] [--asset <KEY>] [--limit N] [--format text|json|csv] [SQL]` — one-off SQL against the warehouse via DuckDB. Three input modes: positional SQL, `--file`, or `--asset` (`SELECT * FROM <key>` with `--limit` default 100). **Wraps**: `ctx.sql(query)` per SDK §6 — Jinja `{{ ref() }}` / `{{ source() }}` resolution, DuckDB `iceberg_scan(...)`; collected to `pyarrow.Table` for rendering (§10 NV #2). **Outputs**: Rich table for TTY; NDJSON for `--format json`; CSV for `--format csv`; auto-pages through `less -R` for >50 rows on TTY (`--no-page` overrides — §10 NV #1). **Error exits**: SQL parse → 1 `NucleusSQLSyntaxError` (`NE2002` per ADR-006 H8); missing `ref()` target → 1 `NucleusAssetNotFound` (`NE3002`); OOM → 1 `NucleusResourceError` (`NE2003`). **Cite**: v4.1 §5.6 (native `ctx.sql` + Jinja, ≤2500 LOC ceiling), §6.4. v4.1 §18.1 must-ship list does **not** include `query` — §10 NV #3.

### 3.7 `nucleus version`

`nucleus version [--check-updates]` — reports installed Nucleus version + all pinned wrapped-OSS versions per `pyproject.toml` (Constraint #11 traceability); `--check-updates` queries PyPI, never auto-installs. **Wraps**: `nucleus.__version__` + `importlib.metadata.version()` per runtime dep; no network unless `--check-updates`. **Outputs**: two-column table — at minimum `nucleus` / `duckdb` / `polars` / `pyarrow` / `pyiceberg` / `dagster` (same set §11 enumerates). **Error exits**: 0 (informational; `--check-updates` network failure → warning, not error). **Cite**: `AGENTS.md` §3 Constraint #11; `docs/internal/compatibility.md`.

### 3.8 `nucleus chat "<question>"` ← v0.2, **Beta**

`nucleus chat "<question>" [--provider anthropic|openai|ollama] [--model <id>] [--json]` — single-turn AI Copilot chat against the current project context. Auto-injects asset graph summary + recent errors. Enforces opt-in privacy gate (ADR-015 §4 — mirrors ADR-011 §1) and a pre-flight cost ceiling before any bytes leave the laptop. **Stability**: Beta (ADR-005 §2 — promoted to Stable at v0.5). **Wraps**: `litellm==1.83.14` via `nucleus.intelligence.chat(...)`. **Providers (v0.2)**: Anthropic (default, `ANTHROPIC_API_KEY`), OpenAI (`OPENAI_API_KEY`), Ollama (local, `OLLAMA_HOST`). **Outputs**: Markdown-rendered text via Rich (default); JSON payload with `--json`. **Error exits**: opt-in declined → 1 `NucleusConfigError`; cost > ceiling → 1 `NucleusBudgetExceededError` (`NE4005`); auth failure → 1 `NucleusCopilotAuthError` (`NE4001`); rate limit → 1 `NucleusCopilotRateLimitError` (`NE4002`); provider 5xx → 1 `NucleusCopilotProviderError` (`NE4003`); content filter → 1 `NucleusCopilotContentFilterError` (`NE4004`); timeout → 1 `NucleusTimeoutError` (`NE3005`). **Cite**: ADR-015 + `nucleus_architecture_v4.1.md` §7.2 (v0.2 Copilot staging); `docs/errors/copilot.md`; `docs/internal/swap/litellm.md`. **Out-of-scope for v0.2**: multi-turn, streaming, tool-calls, lineage-aware context, Workbench integration (all v0.3+/v0.5+).

### 3.9 `nucleus schedule` ← v0.1.1, **Beta** (ADR-017)

`nucleus schedule list [--format text|json]` — lists every asset whose `@nucleus.asset` decorator carries a `schedule=` expression; shows asset key, cron expression, and next run time (UTC).

`nucleus schedule preview <key> [--count N] [--format text|json]` — shows the next N (default 3, max 20) scheduled run times for one asset. Calculated from the cron expression via `croniter==3.0.4`; no Dagster daemon required.

`nucleus schedule on <key>` / `off <key>` / `trigger <key>` — **deferred to v0.2**; in v0.1.1 these three sub-commands raise `NucleusFeatureDeferredError` (NE5008) with a clear "active scheduling ships in v0.2" message and `nucleus run <key>` as the manual workaround.

**Stability**: Beta (ADR-005 §2). **Wraps**: `nucleus.coordination.schedules.{list_schedules, preview_schedule}` → croniter (validation + preview) + Dagster `ScheduleDefinition` (v0.2 active-scheduling path; hidden behind coordination layer). **Error exits**: unknown / unscheduled asset → 1 `NucleusScheduleNotFoundError` (NE5006); invalid format → 1 `NucleusInvalidAssetDefinition` (NE3004); deferred sub-commands → 1 `NucleusFeatureDeferredError` (NE5008). **Cite**: ADR-017; `nucleus_ctx_sdk_spec.md` §5 (`schedule=` kwarg); `docs/internal/compatibility.md` (`croniter==3.0.4`). **Out-of-scope for v0.1.1**: daemon wiring, timezone support, partition-aware scheduling (all v0.2+).

---

## 4. v0.3+ commands (deferred)

Each lists earliest milestone per v4.1 §18.

- **4.1 `nucleus snapshot list / restore`** *(v0.5, Mo 20-28)* — Time-travel queries on Iceberg snapshots. Wraps `ctx.snapshot(<key>).versions()` / `.at_version(N).read()` / `.revert_to(version=N)` per SDK §10. `restore` appends a reverting snapshot (Iceberg never deletes). Cites `docs/patterns/time_travel.md`.
- **4.2 `nucleus catalog migrate`** *(v0.3, Mo 14-20)* — Migrates metadata from v0.1 filesystem `SqlCatalog` to **Lakekeeper** (Rust REST) or **Apache Polaris** (ASF TLP, co-default per v4.1 §5.7 P2 + ADR-002 §4.2). Warehouse Parquet untouched. Will be governed by ADR-004 (not yet authored).
- **4.3 `nucleus agent <subcommand>`** *(v0.5+, Mo 20-28)* — AI agent surface. Per ADR-005 §4 carve-out, stays **Beta through v1.0** and freezes at v1.5 — subcommands and flags may change minor-to-minor with 6-month deprecation per v4.1 §13.3. Provisional subcommands: `chat` / `explain` / `fix` (sandboxed per v4.1 §7.3). Exact surface NV per ADR-005 NV #3.
- **4.5 `nucleus doctor`** *(v0.3, Mo 14-20)* — Fixed-checklist diagnostic: Python `>=3.11,<3.13`, Docker reachable, ports 9000/9001 free, MinIO health, catalog valid, OL transport reachable, disk free >5 GB. Coloured pass/fail table; exit 0 all green, 1 any red. PoC #5 testers run this as "step 0" per `poc/p5_beachhead/RECRUITMENT.md`.

### 4.4 `nucleus enable <feature>` (v0.3 onward, Mo 14-20)

Opt-in to optional integrations. Adds a runtime dep via `pip install nucleus-data[<feature>]` and writes the toggle to `nucleus_project.yaml`. License-tier compliance per ADR-007 enforced at enable time: RED-tier features refuse to enable in Cloud and warn loudly in OSS. Initial features (all GREEN-tier per ADR-007 unless noted): `marquez` (OL HttpTransport → Marquez, v0.3), `dbt` (dbt-duckdb adapter, v0.3), `polaris` (Apache Polaris catalog, v0.3), `lakekeeper` (Lakekeeper catalog, v0.3), `mcp-server` (`nucleus-mcp-server` ~500 LOC, v0.5), `soda` (Soda Core v3.x, v0.5 — **GREEN only with `soda-core==3.x`**; v4+ is RED per ADR-007).

---

## 5. Output format contract

**5.1 Default (`--format text`, TTY default)** — Tabular via `rich==13.9.4` (pinned), trunc-to-width. Plain key-value for single values. Color when `sys.stdout.isatty()` and `NO_COLOR` unset. Rich `Progress` bars for ops >2s; `--no-progress` for CI.

**5.2 JSON (`--format json`)** — **NDJSON**: one self-contained JSON object per record, `\n`-terminated. Pipe-friendly for `jq`, AI agent / MCP consumption per ADR-002 §8.2. Schema versioned via top-level `_schema_version` (`1` at v0.1; bumps per ADR-005 §3). Field naming: **`snake_case`** (§13 q4 resolved here). Progress bars + color suppressed automatically.

**5.3 Quiet (`--quiet` / `-q`)** — Suppresses non-error output. Exit code is the sole signal; errors still print to stderr.

**5.4 Error format** — Errors print to **stderr** per the PoC #1 `NucleusError` three-field contract (v4.1 §6.4):

```
Error: <user_message>            ← NucleusError.user_message
Fix:   <fix_hint>                ← (block omitted if empty)
Docs:  <docs_url>
       [NE<L><CCC>]              ← error_code per ADR-006
```

In `--format json`, errors print to stderr as one NDJSON line: `{"_schema_version": 1, "level": "error", "error_code": "NE1002", "error_class": "NucleusCommitConflictError", "user_message": "...", "fix_hint": "...", "docs_url": "...", "asset": "raw.orders"}`.

**Forbidden in any error output**: `dagster.`, `duckdb.`, `polars.`, `pyiceberg.`, `OpExecutionContext`, `DagsterInstance`, `DuckDBPyConnection`. Enforced by `scripts/dagster_leak_check.py` per `AGENTS.md` §11.7 + ADR-006 §Verification row 4.

---

## 6. Flag conventions

Uniform across every command (Frozen at v1.0). Short flags `-p`, `-f`, `-q`, `-v` are **reserved globally**; no per-command alias may shadow them.

| Long form | Short | Env var | Default |
|---|---|---|---|
| `--profile <name>` | `-p` | `NUCLEUS_PROFILE` | `default` |
| `--format <text\|json\|csv>` | `-f` | `NUCLEUS_FORMAT` | `text` if TTY else `json` (CSV only in `nucleus query`) |
| `--quiet` | `-q` | `NUCLEUS_QUIET=1` | false (mutex with `--verbose`) |
| `--verbose` | `-v` | `NUCLEUS_VERBOSE=1` | false (prints `NucleusError.cause` class + stack on failure) |
| `--no-color` | — | `NO_COLOR=1` | TTY-detected (no `NUCLEUS_*` alias by design) |
| `--config <path>` | — | `NUCLEUS_CONFIG` | `./nucleus_project.yaml` |
| `--catalog <type>` | — | `NUCLEUS_CATALOG` | `filesystem` (v0.1 only; `lakekeeper` / `polaris` land in v0.3 per §4.2) |

---

## 7. Configuration file (`nucleus_project.yaml`)

**v0.1 file format: YAML** (revised 2026-05-13 per Anti-Over-Engineering reconciliation). Rationale: PyYAML is already transitively pinned via `dagster==1.9.5`, so no new runtime dep is added; YAML aligns with the dbt / Marquez / Lakekeeper ecosystem most users will graduate into; and the shipped `src/nucleus/templates/v01/nucleus_project.yaml` is the live source of truth. TOML remains a viable alternative for v0.3+ if the `nucleus enable` toggle table outgrows YAML expressiveness — track via separate ADR.

```yaml
project:
  name: "my-data-stack"
  version: "0.1.0"

catalog:
  type: "filesystem"                         # v0.1 only value; "lakekeeper" / "polaris" land v0.3
  path: "./.nucleus/catalog.db"              # SQLite-backed pyiceberg.SqlCatalog (§10 NV #5)

storage:
  endpoint: "http://localhost:9000"
  bucket: "nucleus-warehouse"
  credentials:
    from: "env:MINIO_ACCESS_KEY,env:MINIO_SECRET_KEY"

lineage:
  transport: "file"                          # v0.1 default; v0.3+: transport: "http" (Marquez)
  path: ".nucleus/lineage/events.jsonl"

telemetry:
  opt_in: false                              # OTEL emit defaults OFF in v0.1 (privacy)
```

`nucleus init` writes a minimal valid `nucleus_project.yaml`. `nucleus up` re-reads on every invocation (no daemon to invalidate). Per-environment overrides via `profiles.<name>` blocks selected by `--profile` / `NUCLEUS_PROFILE`.

---

## 8. Exit-code contract

| Code | Meaning | Source |
|---|---|---|
| **0** | Success | All commands |
| **1** | A `NucleusError` was raised — three-block error per §5.4, with `NE<L><CCC>` per ADR-006 | Any command body |
| **2** | CLI usage error (Typer-driven) — bad arg, missing required, unknown subcommand | Typer/Click layer |
| **3** | Docker / local runtime not reachable | `nucleus up`, `nucleus doctor` |
| **4** | Network error (S3, OL HttpTransport, PyPI for `--check-updates`) | Any network-touching command |
| **5** | Schema / contract violation on a write path | `nucleus run`, `nucleus ingest` |
| **130** | User interrupt (SIGINT / Ctrl-C) | Any command |

CI treats any non-zero exit as a check failure; `scripts/beachhead_e2e.py` and `.github/workflows/ci.yml` already follow this.

---

## 9. Environment variables (exhaustive)

Every `NUCLEUS_*` var below either backs a CLI flag (§6) or configures a sub-component. AI agents and CI configurators rely on this list — additions require a CHANGELOG entry and (post-v1.0) an ADR.

| Variable | Backs | Default |
|---|---|---|
| `NUCLEUS_PROFILE` | `--profile` | `default` |
| `NUCLEUS_FORMAT` | `--format` | TTY-detect (`text` / `json` / `csv`) |
| `NUCLEUS_QUIET` | `--quiet` | `0` |
| `NUCLEUS_VERBOSE` | `--verbose` | `0` |
| `NUCLEUS_CONFIG` | `--config` | `./nucleus_project.yaml` |
| `NUCLEUS_CATALOG` | `--catalog` | `filesystem` (v0.1 only value) |
| `NUCLEUS_HOME` | runtime dir | `./.nucleus` (holds `catalog.db`, `lineage/`, `runs/`) |
| `NUCLEUS_LOG_LEVEL` | logging level | `info` (`debug` / `info` / `warning` / `error`) |
| `NUCLEUS_NO_TELEMETRY` | telemetry opt-out | `1` (off in v0.1; flag exists for forward-compat) |
| `NO_COLOR` | color suppression | unset (industry convention; precedes flag absence) |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO auth | `minioadmin` (dev only — §10 NV #7) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | S3 prod | unset (used when `[storage].endpoint` points at AWS) |

v0.5+ deferred: `NUCLEUS_AGENT_LLM_PROVIDER`, `NUCLEUS_AGENT_MODEL`, `NUCLEUS_MCP_SERVER_URL` — out of scope (ADR-005 §4 AI carve-out).

---

## 10. NEEDS VERIFICATION

Per `AGENTS.md` §10 + §11.12. Resolved or downgraded before v0.1 spec lock at Mo 6.

1. **`nucleus query` pagination** — auto-page >50 rows through `less -R` on TTY vs always print? Telemetry post-PoC #5; `--no-page` preserves both.
2. **`nucleus query` return shape** — SDK §6.1 returns `DuckDBPyRelation`; §4.1 default is `pl.LazyFrame`. CLI must collect to something concrete. Provisionally `pyarrow.Table` (engine-neutral, NDJSON-friendly). Confirm at PoC #2 promotion.
3. **`nucleus query` in v0.1 scope** — v4.1 §18.1 must-ship enumerates only `init / up / down / run / ingest` (5 commands); `query` is in `C4_container.md` §3.1 + this spec but not §18.1. Defaulted to v0.1 (30-min metric implies user verifies the table). Confirm in next v4.1 patch.
4. **Layer-4 error codes** — ADR-006 §Initial allocates L1/L2/L3 only. `NE5001-5003` proposed here are **first L4 allocations**; need acceptance via PoC #1 promotion PR per ADR-006 §Trigger row 3.
5. **`filesystem` vs `sqlite` catalog naming** — v4.1 §5.7 says "filesystem"; `C4_container.md` §3.4 implements as `pyiceberg.SqlCatalog` over SQLite. Spec uses `filesystem` user-facing; reconcile with PoC #4 `catalog_type` (Worker C).
6. **Asset key cardinality** — v0.1 uses 2-level `<namespace>.<name>`; v4.1 §12.1 canonical is 3-level. 2-level is provisional for v0.1 single-catalog scope; 3-level lights up v0.3 with Lakekeeper / Polaris.
7. **MinIO dev credentials** — defaults `minioadmin` unconfirmed against the docker-compose image. `docs/internal/research/minio.md` (Worker BB) not yet landed. Confirm at PoC #4 promotion.
8. **`nucleus ingest` syntax drift** — three variants in repo: this spec's `<URI> --table <SRC> --as <DEST>` (v4.1 §5.5.1 canonical); `README.md` `--table=orders --target=raw.orders`; founder brief's `--from / --to`. Canonical wins per `AGENTS.md` §2; README + brief drift to be patched in a same-PR sweep.
9. **`--mode merge` engine floor** — `MERGE INTO` requires DuckDB ≥ 1.4.0 per Worker S; current pin `1.1.3`. Recommendation: implement via pyiceberg row-level delete + append for v0.1.
10. **macOS init paths** — PoC #5 testers may run macOS; current `SETUP.md` is Windows-focused. `nucleus init` must scaffold identically cross-platform — confirm `.nucleus/` path-separator on macOS per `poc/p5_beachhead/RECRUITMENT.md`.

---

## 11. Docs URLs

Pins confirmed against `pyproject.toml` 2026-05-13. Upgrade per Constraint #11 (one-component-per-PR, ADR for major bumps, smoke tests).

| Library | Docs | Pin |
|---|---|---|
| Typer | <https://typer.tiangolo.com/> | `typer==0.15.1` |
| Click | <https://click.palletsprojects.com/> | `click==8.1.8` |
| Rich | <https://rich.readthedocs.io/> | `rich==13.9.4` |
| pyiceberg | <https://py.iceberg.apache.org/api/catalog/> | `pyiceberg==0.8.1` |
| DuckDB | <https://duckdb.org/docs/api/python/overview> | `duckdb==1.1.3` |
| Polars | <https://docs.pola.rs/api/python/stable/> | `polars==1.18.0` |
| Dagster | <https://docs.dagster.io/api> | `dagster==1.9.5` |
| OpenLineage | <https://openlineage.io/docs/client/python> | `openlineage-python==1.47.1` |
| NDJSON · `NO_COLOR` | <https://github.com/ndjson/ndjson-spec> · <https://no-color.org> | — |

---

## 12. Forbidden CLI patterns

Per `AGENTS.md` §3 + §4 + §7. Any of these in a PR is a release blocker.

- **No `nucleus dagster ...`** — violates v4.1 §6 (wrapped + hidden) and §6.5 Replaceability Mandate; substrate must be invisible.
- **No `nucleus install <plugin>`** — no public plugin SDK in v1 per Constraint #2. `nucleus enable <feature>` per §4.4 is the bounded opt-in mechanism, not a marketplace.
- **No `nucleus auth <subcommand>`** — no custom auth per Constraint #6; always delegate to OIDC (v4.1 §15.1). CLI never owns credentials beyond reading `MINIO_*` / `AWS_*` env.
- **No `nucleus train ...` / `nucleus serve <model>`** — no ML platform per Constraint #7. We use models; we never host them.
- **No `nucleus migrate-from-<vendor>`** — yield-to-giants is Iceberg portability + dispatch (v4.1 §10), not migration tooling. The Iceberg lake IS the migration tool.
- **No `nucleus pipeline run` / `nucleus job submit` / `nucleus task ...`** — vocabulary violations per `AGENTS.md` §7. Everything is an *asset*; the verb is *materialize* (CLI surfaces as `run` for familiarity, internal vocab stays *asset*).

---

## 13. Open governance questions (founder review)

1. **`nucleus query` paging** — auto-page for >50 rows (current §3.6 + NV #1), or always table + user pipes manually? Feeds PoC #5 protocol.
2. **`nucleus run --retry <N>`** — CLI operator-level flag, or always declared at asset via `nucleus.retries(...)` per SDK §2.1? Recommendation: SDK-only; CLI exposes `--no-retry` for explicit override.
3. **`nucleus ingest --ssh-tunnel`** — support in v0.1 or defer to v0.3 when dlt (native tunnel) arrives? Recommendation: defer to v0.3.
4. **JSON output key casing** — `snake_case` (resolved §5.2) vs `camelCase` (MCP-tooling-familiar)? Revisit if MCP v0.5+ consumers push back.
5. **`nucleus down` volume default** — preserve (safer, opt-in destroy) vs destroy (cleaner CI)? **RESOLVED 2026-05-14**: preserve by default; opt-in destroy via `--volumes` flag (NOT `--keep-volumes`/`--no-keep-volumes` per AGENTS.md §7 vocabulary cleanliness + Typer reserved-short-flag avoidance). CI that wants a clean slate passes `--volumes` explicitly.

---

*Governs the CLI surface that `AGENTS.md` §2 Required Reading #6 calls out and ADR-005 §4 carves out from the SDK freeze schedule. Implementation lives in `src/nucleus/cli/`. CI enforcement via `scripts/check_vocabulary.py` (§12 patterns + §7 vocab), `scripts/dagster_leak_check.py` (output strings per §5.4), `tests/cli/test_exit_codes.py` (NucleusError → exit code + NE-code matrix), `tests/cli/test_help_snapshot.py` (--help diff = red without Beta CHANGELOG or post-v1.0 ADR), and `scripts/beachhead_e2e.py` (Worker G — full §3 sequence timed against the 30-min metric). Updates require: (a) ADR for any Frozen-tier change post-v1.0, (b) CHANGELOG for any Beta-tier change, (c) co-landing PR to `tests/cli/test_help_snapshot.py`.*
