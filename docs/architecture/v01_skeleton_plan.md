# v0.1 `src/nucleus/` Skeleton Plan

> **Status**: PROPOSED — blueprint for the post-PoC-#1-promotion code phase. **Date**: 2026-05-13.
> **Phase gate**: production code under `src/nucleus/` is **forbidden** until PoC #1 promotion lands (`AGENTS.md` §11.1; `.cursor/rules/nucleus.mdc` "Phase Gate"). Plans only.
> **Required reading**: `AGENTS.md` §0–§11 · v4.1 §3 + §6 + §13 + §18.1 + §20 · `docs/specs/nucleus_cli_spec.md` §3 + §10 · `docs/specs/nucleus_ctx_sdk_spec.md` §0–§13 · `docs/specs/nucleus_asset_model_spec.md` §1–§3 · `docs/specs/nucleus_project_anatomy.md` §1–§5 · `ADR-002` §8 · `ADR-005` §1–§2 · `ADR-006` §Decision + §Initial · `ADR-008` / `ADR-012` · `C4_component.md` §2 + `C4_container.md` §3.1 · `engineering.md` §2.4 + §3.1 + §6.2.

---

## §1. Existing state of `src/nucleus/`

- **`__init__.py`** ~50 LOC, READY — tagline + `__version__="0.0.0"` + re-exports `NucleusError`.
- **`errors.py`** ~426 LOC, READY — 22 `NucleusError` subclasses, three-field contract.
- **`_internal/logging.py`** ~110 LOC, READY — structlog `configure()` + `get_logger()`.
- **`cli/main.py`** ~60 LOC, PARTIAL — Typer shell with `--version`/`--help` only.
- **`ctx/__init__.py`** stub, PARTIAL — re-exports `NucleusError`; public surface intentionally empty.
- **`coordination/__init__.py` · `engines/__init__.py` · `physics/__init__.py`** — stubs, EMPTY (await PoC #1 / Heartbeat).
- **`intelligence/__init__.py`** stub, DEFERRED to v0.2+ (v4.1 §18.1 OUT).

`errors.py` is the only substantive production module today. Per `ADR-006` §Trigger r3, the PoC #1 promotion PR appends `error_code: ClassVar[str]` to the 12 subclasses in `ADR-006` §Initial; otherwise untouched. Layer mirroring matches `engineering.md` §2.4 (derives from v4.1 §3.1 — bottom-up L0..L4).

---

## §2. Target tree (post-PoC-#1 promotion → v0.1 GA)

```
src/nucleus/
├── __init__.py                                                 # + re-exports nucleus.asset, nucleus.check
├── errors.py                                                   # + error_code ClassVar (ADR-006 §Initial × 12)
├── _internal/{logging, config, asset_names, ids}.py
├── physics/{iceberg_io, type_mapping}.py                       # L0 (v4.1 §4)
├── engines/{_protocol, duckdb_engine, polars_engine}.py        # L1 (v4.1 §5)
├── coordination/                                               # L2 (v4.1 §6) — only layer allowed to import dagster
│   ├── error_translation.py    # PROMOTED ← poc/p1_error_translation/translator.py
│   ├── sql_resolver.py         # PROMOTED ← poc/p2_ctx_sql/resolver.py
│   ├── asset_materialization.py # NEW — AMA (v4.1 §6.2 5 steps)
│   ├── lineage.py              # NEW — asset-level OL emit (v4.1 §6.2 step 4)
│   └── contracts.py            # NEW — schema-only validation (v4.1 §6.3)
├── ctx/                                                        # L4 SDK (v4.1 §13.2; the public API)
│   ├── {_context, _decorators, read, write, sql}.py
│   └── copy_from.py            # PROMOTED ← poc/p3_ingest/ingest.py
└── cli/commands/{version, init, up, down, ingest, run, query}.py   # L4 (cli_spec §3)
```

`intelligence/` stays empty per v4.1 §18.1 OUT. Downward deps enforced by `scripts/check_layering.py` per `engineering.md` §3.1; `dagster_leak_check.py:53–58` enforces the dagster-import boundary.

---

## §3. File-by-file scope

Tier defaults: **Beta @ v0.1** for `ctx/*`, **Internal @ v0.1** for everything else, per `ADR-005` §2 (Frozen at v1.0 unless noted). LOC from `C4_component.md` §2 + `coordination/__init__.py:6–11`. Tests mirror under `tests/<layer>/test_<file>.py` per `engineering.md` §6.2; `ctx/sql.py` adds `syrupy` snapshots per §6.7.

### §3.1 Coordination (L2) + SDK (L4)

| File | Public API | LOC | Wraps |
|---|---|---:|---|
| `coordination/error_translation.py` | `translate(exc) -> NucleusError` | 350 | dagster · polars · duckdb · pyiceberg (`ADR-012`) |
| `coordination/sql_resolver.py` | `resolve_sql(template, ref_resolver, *, available)` | 200 | jinja2 3.1.5 (PROMOTED — `PoC #2 PROMOTION_CHECKLIST` §3) |
| `coordination/asset_materialization.py` | `materialize(asset_key, *, params=None) -> RunResult` | 500 | dagster 1.9.5 (only file allowed to import dagster) |
| `coordination/lineage.py` | `emit_run_event(state, asset, run_id, snapshot_id=None)` | 250 | openlineage-python 1.47.1 (not yet pinned — §7 NV #4) |
| `coordination/contracts.py` | `validate_schema(asset, arrow_table) -> None \| NucleusSchemaError` | 250 | pyarrow; Soda → v0.5 |
| `ctx/_context.py` | `Ctx` (log/params/env/run_id/asset) | 250 | `_internal.logging` + `_internal.config` |
| `ctx/read.py` | `ctx.read(name, *, as_=...)` | 250 | pyiceberg · polars · pyarrow |
| `ctx/write.py` | `ctx.write(df, *, mode=...)` — v0.1: `overwrite\|append` (§6 Q3) | 250 | pyiceberg (catalog owns commit; Hard Constraint #5) |
| `ctx/copy_from.py` | `ctx.copy_from(source, *, table, target, mode="full_refresh")` | 250 | sqlalchemy · psycopg · pymysql · stdlib sqlite3/csv/json |
| `ctx/sql.py` | `ctx.sql(query, **bindings)` | 800 | duckdb · jinja2; wraps `coordination.sql_resolver` |
| `ctx/_decorators.py` | `@nucleus.asset`, `@nucleus.check` | 400 | `coordination.asset_materialization` |
| `ctx/__init__.py` | re-exports per v4.1 §13.2 + `# Stability:` tags | 100 | enforced by `scripts/check_api_stability.py` (`ADR-005` Verification #1) |

### §3.2 CLI commands (L4 — one file per command, `cli/commands/`)

Each is a **thin** wrap over one `ctx.*` call per `docs/specs/nucleus_cli_spec.md` §1; `engineering.md` §10.3 PR-size limit drives per-file commands.

| File | Wraps | LOC | NE-codes raised + cite |
|---|---|---:|---|
| `version.py` | `__version__` + `importlib.metadata.version()` | 80 | — · cli_spec §3.7 |
| `init.py` | `importlib.resources` template + opt `git init` | 250 | (proposed) NE5001 · cli_spec §3.1 |
| `up.py` | `docker compose up -d` (SeaweedFS default per `ADR-008`) + `pyiceberg.load_catalog(type="sql")` | 250 | NE5002, NE5003 · cli_spec §3.2; cold-boot <10 s (v4.1 §11.2) |
| `down.py` | `docker compose down` | 150 | — · cli_spec §3.3 |
| `ingest.py` | `ctx.copy_from(...)` | 250 | NE1001, NE2001, NE1002 · cli_spec §3.5 — the 30-min beachhead |
| `run.py` | `coordination.asset_materialization.materialize(...)` (§6 Q2) | 300 | NE3001, NE2001, NE1002 · cli_spec §3.4 |
| `query.py` | `ctx.sql(query)` | 250 | NE2002, NE3002, NE2003 · cli_spec §3.6 — flagged §6 Q4 |

### §3.3 Layer 0/1/internal additions

| File | LOC | Notes |
|---|---:|---|
| `physics/iceberg_io.py` | 100 | `load_catalog_from_config`, `load_or_create_table` (minimal; `ctx.read/write` reach pyiceberg directly per `C4_component.md` §3) |
| `physics/type_mapping.py` | 150 | `sequence_ingestion.md` §1 step 2; hypothesis-tested per `engineering.md` §6.6 |
| `engines/_protocol.py` | 50 | `Engine` Protocol per `engineering.md` §7.2; smoke-test target only (Constraint #9 + `docs/internal/swap/{duckdb,polars}.md`; §7 NV #5) |
| `engines/duckdb_engine.py` | 300 | owns `iceberg_scan(...)` registration |
| `engines/polars_engine.py` | 250 | `LazyFrame` plumbing |
| `_internal/config.py` | 200 | Load + validate `nucleus.toml` via msgspec 0.18.6 (`engineering.md` §8.2); schema = `cli_spec` §7 |
| `_internal/asset_names.py` | 50 | regex `^(raw\|staging\|marts\|ops)\.[a-z][a-z0-9_]*$` (2-level v0.1; §7 NV #2) |
| `_internal/ids.py` | 50 | ULID per `docs/specs/nucleus_asset_model_spec.md` §2.3 |

---

## §4. Implementation order

Sequential within a layer; parallel where deps allow. One PR ≤500 LOC per `AGENTS.md` §11.4.

1. **`errors.py`** — append `error_code: ClassVar[str]` to 12 subclasses (`ADR-006` §Initial); rewrite `errors.py:23–28` "NUC-XXX deferred" docstring. Same PR as step 2 (`PoC #1 PROMOTION_CHECKLIST` §3).
2. **PoC #1 promotion** → `coordination/error_translation.py` (auto-opens ADR-003 PR per checklist §3 last bullet).
3. **PoC #2 promotion** → `coordination/sql_resolver.py` (independent of step 2 per `PoC #2 PROMOTION_CHECKLIST` §7).
4. **`_internal/`** additions (config, asset_names, ids) — no external deps.
5. **`physics/`** Iceberg I/O + type-mapping helpers.
6. **`engines/`** Protocol + DuckDB + Polars adapters (`engineering.md` §3.2 forbids cross-engine imports).
7. **`coordination/asset_materialization.py`** — the AMA; **Risky tier** per `AGENTS.md` §11.3 (human-authored, AI assists). Implements v4.1 §6.2 five steps.
8. **`coordination/lineage.py`** — AMA step-4 callee. Blocked on `openlineage-python==1.47.1` pin (§7 NV #4).
9. **`coordination/contracts.py`** — AMA step-1 callee.
10. **`ctx/_context.py`** → **PoC #3 promotion** (`ctx/copy_from.py`) → **`ctx/read.py` + `write.py`** → **`ctx/sql.py`** (wraps resolver + DuckDB) → **`ctx/_decorators.py`** (registers with AMA; v4.1 §6.5: zero Dagster types cross this boundary).
11. **`ctx/__init__.py`** + **`nucleus/__init__.py`** — public re-exports + tier tags per `ADR-005` §1.
12. **CLI commands** in dep order: `version → init → down → up → ingest → run → query`; register all in `cli/main.py`.
13. **`tests/`** mirrors per `engineering.md` §6.2 (partially scaffolded today).
14. **Beachhead E2E** (`scripts/beachhead_e2e.py`) — proves <30-min metric per v4.1 §1.5 + `docs/specs/nucleus_poc_plan.md` §5. Release-blocker for v0.1 GA.

---

## §5. LOC budget breakdown

Hard ceiling **8,000 LOC** for `src/nucleus/` at v0.1 per `pyproject.toml:291` + `AGENTS.md` §11.6. `tests/`, `poc/`, `scripts/` do not count.

| Subtree | Budget | Composition |
|---|---:|---|
| `errors.py` | 450 | 426 today + ~24 for `error_code` × 12 |
| `_internal/` | 400 | logging 110 + config 200 + asset_names 50 + ids 50 |
| `physics/` | 250 | iceberg_io 100 + type_mapping 150 |
| `engines/` | 600 | protocol 50 + duckdb 300 + polars 250 |
| `coordination/` | 1550 | error_translation 350 + sql_resolver 200 + AMA 500 + lineage 250 + contracts 250 |
| `ctx/` | 2400 | _context 250 + read/write 500 + copy_from 250 + sql 800 + _decorators 400 + shared 200 |
| `cli/` | 1800 | main 100 + commands ~1530 + helpers 170 |
| `intelligence/` | 0 | v0.1 OUT (v4.1 §18.1) |
| **Sum / Buffer / Ceiling** | **7450 / 550 / 8000** | tracked monthly via `scripts/loc_budget.py` → `docs/budget_history.md` |

---

## §6. Open questions for founder

Each = a concrete decision required before the corresponding PR can land.

1. **`nucleus.toml` vs `nucleus.yaml`** — `cli_spec` §7 + `engineering.md` §8.1 mandate TOML; `docs/specs/nucleus_project_anatomy.md` §2 still uses YAML. **Recommend** TOML (stdlib `tomllib`, parity with `pyproject.toml`); patch project_anatomy in same sweep.
2. **`ctx.materialize(...)` API spelling** — used by `cli_spec` §3.4 + `sequence_asset_materialization.md` §1 step 2 but **absent** from v4.1 §13.2 / `docs/specs/nucleus_ctx_sdk_spec.md` §12 frozen surface. **Recommend** expose as `ctx.materialize(asset_key)` Internal in v0.1; promote into v4.1 §13.2 same PR. *May warrant new ADR — §7 NV #1.*
3. **`ctx.copy_from` mode taxonomy** — `C4_component.md` §2.4 ships `mode="full_refresh"` only; `cli_spec` §3.5 advertises `--mode overwrite|append|merge` (`merge` flagged §10 NV #9). **Recommend** v0.1 accepts `overwrite|append`; defer `merge` to v0.3 (DuckDB pin upgrade).
4. **`nucleus query` in v0.1?** — `cli_spec` §10 NV #3 flags; v4.1 §18.1 lists only 5 commands. **Recommend** include (30-min metric implies verify-the-table step); upgrade v4.1 §18.1 to 7 commands.
5. **`ctx.dagster_context` escape hatch** — v4.1 §13.2 r12 lists v0.1+; `ADR-005` §4 says "provisionally Internal forever". **Recommend** keep Internal (`_internal/dagster_context.py`); revisit only if telemetry shows >5% usage (v4.1 §6.6 trigger). Saves ~200 LOC.
6. **`@nucleus.asset` import path** — Spec contract is `import nucleus; @nucleus.asset(...)` (`docs/specs/nucleus_ctx_sdk_spec.md` §1); implementation lives in `ctx/_decorators.py`. **Recommend** re-export from `nucleus/__init__.py`; validate via `scripts/check_public_api.py`.

---

## §7. NEEDS VERIFICATION inventory

Per `AGENTS.md` §11.12. Each = a citation gap; resolved or downgraded before v0.1 GA.

1. **`ctx.materialize` missing from v4.1 §13.2** but assumed by `cli_spec` §3.4 + `sequence_asset_materialization.md` §1 step 2. May warrant **new ADR-013** — see §6 Q2.
2. **Asset-name cardinality** — `docs/specs/nucleus_asset_model_spec.md` §2.1 says 3-level; `engineering.md` §15.3 + `cli_spec` §3 + `poc/p2_ctx_sql/resolver.py:48` use 2-level (`cli_spec` §10 NV #6). v0.1 ships 2-level; 3-level at v0.3 with REST catalog.
3. **`docs/specs/nucleus_project_anatomy.md` is v3-era stale** — references `nucleus.yaml`, `dlt`-by-default, modules YAML, `assets/raw|staging|dim|fact|analytics/` (v0.1 uses `raw|staging|marts|ops` per `engineering.md` §15.3). Needs a v4.1 patch sweep.
4. **`openlineage-python==1.47.1` not in `pyproject.toml`** — `ADR-012` recommended-but-unpinned; step 8 blocked until pin lands per Hard Constraint #11.
5. **`Engine` Protocol shape** — `engineering.md` §7.2 specifies `execute(plan: Plan, ctx: ExecContext) -> Arrow`; `Plan` + `ExecContext` undefined anywhere. `# NEEDS VERIFICATION` in `engines/_protocol.py` until smoke-tested vs DataFusion swap stub (v4.1 §9.3).
6. **`ctx.read(snapshot=...)` deferred** — `docs/specs/nucleus_ctx_sdk_spec.md` §4.1 advertises; v4.1 §13.2 / `ADR-005` NV #1 defer `ctx.snapshot` to v0.3+. Strip `snapshot=` / `version=` kwargs from v0.1 `ctx/read.py`.
7. **CLI per-file structure** — `engineering.md` §10.3 PR-size limit makes `cli/commands/<name>.py` the only viable layout, but no spec/ADR mandates it. Confirm at PoC #1 promo PR.
8. **Polaris JVM exclusion** — Constraint #1 forbids JVM in core path; v4.1 §5.7 lists Polaris co-default at v0.3+. `C4_container.md` §6 r1 reconciles (Polaris JVM lives in its own docker container, not always-on). Re-verify at v0.3 catalog ADR.
9. **`docker compose` vs `docker-compose`** — `cli/commands/up.py` shells out; v2 plugin vs v1 binary varies by host; `cli_spec` §3.2 doesn't specify. Probe at PoC #4.
10. **`scripts/check_api_stability.py` not yet created** — `ADR-005` Verification #1 requires it (~100 LOC) before any Frozen-tier code lands; must exist before step 11.

---

## §8. Non-goals for v0.1 (defer markers)

Per v4.1 §18.1 OUT + §20.1 + `ADR-002` §4.1 + `ADR-005` §2 schedule. **Anything below introduced into the v0.1 skeleton = release-blocker scope creep.**

**v0.2** (v4.1 §18.2): Workbench / Web IDE · AI Copilot / inline chat · `ctx.metrics` / `ctx.secrets` (v4.1 §13.2 r7–8). **v0.3** (v4.1 §18.3): `ctx.snapshot()` / time travel / incremental materialization (`ADR-005` NV #1) · dlt connectors (v4.1 §5.5.2) · Marimo (v4.1 §8.1) · Lakekeeper / Polaris catalogs (v4.1 §5.7 + `ADR-004`) · dbt-duckdb (v4.1 §5.6) · schema-aware AI completion. **v0.5** (v4.1 §18.4): `ctx.agent` runtime (v4.1 §7.3) · `nucleus-mcp-server` (`ADR-002` §4.2) · Lance / multimodal / Daft / LanceDB (v4.1 §3.1 L1) · Soda Core (`ADR-012`). **v0.7+**: cost meter · replay debugger · semantic graph (v4.1 §18.6). **v2.0**: federation / Marketplace (v4.1 §18.7). **v0.5 SQL / v1.0 Python**: column-level lineage (v4.1 §3.1 L2).

**Forbidden forever** (Hard Constraints): custom Iceberg commit service (#5; `ADR-001`) · custom auth (#6; OIDC delegation only @ v0.3+ per `ADR-010`) · custom scheduler as default (#3; `nucleus-mini-scheduler` is on-demand fallback only, v4.1 §6.7) · JVM in core path (#1; v4.1 §5.7).

Every bullet in §3 + §4 was re-checked against the **<30-min beachhead metric** (v4.1 §1.5; `AGENTS.md` §5 Q2): each serves (a) the `git clone → BI-ready Iceberg table` happy path, (b) a release-blocker discipline, or (c) the public-API contract. Anything failing this filter moved to §8.

---

*Blueprint locked at v4.1 + `ADR-005` + `ADR-006` + `ADR-008` + `ADR-012` + `docs/specs/nucleus_cli_spec.md`. No code lands under `src/nucleus/` until PoC #1 promotion (`AGENTS.md` §11.1). Founder reviews §6 → resolves → §3/§4/§5 implementation begins per §4.*
