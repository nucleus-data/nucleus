# Research: dbt-duckdb (+ dbt-core)

> **Component status in Nucleus**: **v0.3+ OPTIONAL adapter. NOT a v0.1 dependency.**
> v0.1 ships **native `ctx.sql` + Jinja resolver** (≤2500 LOC ceiling, owned in-house) per `nucleus_architecture_v4.1.md` §5.6 / §5.6.0 / D13. dbt-duckdb is the *fallback* if PoC #2 (native resolver) fails (`nucleus_poc_plan.md` §2) and the *forward-leverage* path for the v0.3 "drop your existing dbt project in" promise (§18.3).
> **Pin candidates (when v0.3 lands)**: `dbt-duckdb==1.10.1` (uploaded 2026-02-17, PyPI verified 2026-05-13) + `dbt-core==1.10.x` (verify minor-pairing). **Not pinned in `pyproject.toml` today and MUST NOT be added during v0.1.**
> **License**: `dbt-duckdb` = **Apache-2.0** (PyPI field `Apache-2`). `dbt-core` PyPI `license` field is **blank** — NEEDS VERIFICATION before pin (historically Apache-2.0).
> **JVM-free**: **YES** — pure-Python on both sides. Hard Constraint #1 satisfied.
> **Research date**: 2026-05-13  •  **Used in**: nowhere. Forward-leverage anchor for the v0.3 ADR.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before any v0.3 dbt-adapter ADR — and **do not import dbt-duckdb in v0.1 work**.

> **Founder reading note**: this doc is forward-leverage. v0.1 implementation **does not** require it. The only v0.1-relevant section is §4.4 (PoC #2 fallback trigger). Stop there unless v0.3 work is actively starting.

---

## §1. At a glance

- **Adapter (`dbt-duckdb==1.10.1`, 2026-02-17)**: maintainer **DuckDB Foundation** (recent transition from `jwills/dbt-duckdb` — PyPI `home_page` URL is stale; see §8). License Apache-2.0.
- **Engine (`dbt-core==1.11.9`, 2026-05-06)**: maintainer **dbt Labs**. License presumed Apache-2.0 (PyPI metadata blank; verify before pin). Adapter tracks core minors with a 1-minor lag — pin matching minors (`1.10.x` both sides is safest).
- **Position**: L2 Coordination — **optional**. v0.3+ via `dbt_project.yml` discovery; **never** a v0.1 dependency.

**What it is**: a **dbt-core adapter plugin**. Together they form a **Jinja-templated SQL transformation framework** (`{{ ref(...) }}`, `{{ source(...) }}`, `{{ config(...) }}`, macros, tests, docs) bound to DuckDB. No daemon, no JVM. **dbt is not an engine; it is a SQL-compilation + scheduling layer over an engine** — the #1 framing error in Nucleus context.

**What it is NOT**: not an ingestion framework (dlt / `ctx.copy_from`), not an orchestrator (Dagster), not an Iceberg writer (no first-class `materialized='iceberg'`; §4.3), **not a v0.1 dependency**.

---

## §2. dbt-duckdb in Nucleus terms

| dbt term | Nucleus term | v0.3 surface |
|---|---|---|
| `model` (.sql file) | **asset** | imported into asset graph; never edited |
| `source` (yml) | **source asset** | mapped to existing `@nucleus.source` |
| `test` | **check** | Nucleus-facing surface is `@nucleus.check` |
| `snapshot` | (no equivalent) | parked; SCD2 is v0.5+ per §5.6.0 |
| `manifest.json` | (slice of) asset graph | dbt's resolver output; Nucleus reads, never writes |
| `profiles.yml` | (none — Nucleus owns config) | auto-generated under `.nucleus/dbt/`; user never edits |
| `dbt_project.yml` | (project-level config) | discovered, not generated; preserved for portability |

Hard architectural question for v0.3: **graph ownership**. Provisional stance (§9): Nucleus owns the outer graph; dbt's manifest is parsed, not delegated. Likely path = consume `dagster-dbt` (§5).

---

## §3. Official documentation URLs

Verified by `WebFetch` 2026-05-13.

**dbt-duckdb**: setup https://docs.getdbt.com/docs/core/connect-data-platform/duckdb-setup • configurations https://docs.getdbt.com/reference/resource-configs/duckdb-configs • repo https://github.com/duckdb/dbt-duckdb • releases https://github.com/duckdb/dbt-duckdb/releases • PyPI https://pypi.org/project/dbt-duckdb/

**dbt-core**: programmatic API https://docs.getdbt.com/reference/programmatic-invocations • `dbt_project.yml` https://docs.getdbt.com/reference/dbt_project.yml • `manifest.json` schema (versioned) https://docs.getdbt.com/reference/artifacts/manifest-json • repo https://github.com/dbt-labs/dbt-core • PyPI https://pypi.org/project/dbt-core/

**DuckDB Iceberg extension** (for §4.3): overview https://duckdb.org/docs/current/core_extensions/iceberg/overview.html • REST catalogs https://duckdb.org/docs/current/core_extensions/iceberg/iceberg_rest_catalogs.html

**The v0.1 alternative we ship instead**: `nucleus_architecture_v4.1.md` §5.6 + §5.6.0 + D13 • `nucleus_poc_plan.md` §2 • `docs/research/duckdb.md` • `docs/research/ducklake.md`.

---

## §4. Roles, status, and non-status in Nucleus

The answer is **NOT v0.1**. The rest of this section explains why.

### §4.1 Why NOT in v0.1 — Amendment 6 / D13

Per `nucleus_architecture_v4.1.md` §5.6: *"v0.1 ships native SQL transformation, NOT dbt-duckdb."* Reasons:

1. **LOC ownership > vendored complexity.** ~1000 LOC under our roof beats 22 direct `requires_dist` entries on `dbt-core` (PyPI 2026-05-13) plus ~20-30 more transitive — **2-3× the current Nucleus runtime surface**.
2. **Adapter ecosystem release lag.** dbt-duckdb 1.10.1 vs dbt-core 1.11.9. Bisection on every minor bump is a tax for a one-person team.
3. **Vocabulary collision.** dbt's *model* is our *asset*; *source* overloads *source asset*; *test* overloads *check* — forces a vocabulary translator at the user-facing layer, exactly the leak v4.1 §6.4 forbids for Dagster.
4. **Telemetry by default.** `dbt-core` ships `snowplow-tracker` enabled. The v0.1 "local-first" promise (§1.5) cannot be quietly broken — must mute + CI smoke-test zero outbound calls.
5. **Beachhead irrelevant.** Adds zero minutes to the <30-min `git clone` → BI-ready Iceberg target. Fails the 8-question gate's beachhead question (AGENTS.md §5) = defer.

**Conclusion**: native `ctx.sql` for v0.1. Defer dbt-duckdb to v0.3+ ADR.

### §4.2 v0.3+ "drop your existing dbt project in" — the migration adapter

Per `nucleus_architecture_v4.1.md` §18.3 (Tier 3 Connectors, Mo 14-20). The **single** v0.3 user story:

> A team with an existing `dbt-duckdb` project graduates to Nucleus without rewriting SQL. They drop their `models/`, `macros/`, `seeds/`, and `dbt_project.yml` in. `nucleus build` runs the dbt graph alongside native Nucleus assets, with unified lineage and unified error translation.

This is **forward-leverage**: lowers activation energy for existing dbt-duckdb projects. It is **NOT** "Nucleus uses dbt internally" — native resolver remains default; dbt-duckdb is opt-in via `dbt_project.yml` discovery.

What the v0.3 adapter (`coordination/dbt_duckdb_adapter.py`, ≤500 LOC per AGENTS.md §11.4) does:

1. Discover `dbt_project.yml`.
2. Auto-generate project-local `profiles.yml` pointing at our DuckDB engine.
3. `dbtRunner().invoke(["parse"])` → `target/manifest.json`. **NEEDS VERIFICATION** at v0.3 time.
4. Translate manifest nodes → Dagster assets via `dagster-dbt` (or thin wrapper). Nucleus's `Definitions` owns the merged graph.
5. On run, `dbtRunner().invoke(["build", "--select", ...])`. Errors translate through v4.1 §6.4 — no `dbt.exceptions.CompilationError` classname surfaces.

Authoritative `dagster-dbt` integration: https://docs.dagster.io/integrations/libraries/dbt/dbt. Consuming it may be cheaper than hand-rolled glue — decide at ADR time.

### §4.3 Iceberg destination via dbt-duckdb — verify carefully

Status 2026-05-13 per https://docs.getdbt.com/reference/resource-configs/duckdb-configs:

- **Built-in dbt-duckdb materializations**: `table`, `view`, `incremental` (`append` / `delete+insert` / `merge` / `microbatch`), `external` (Parquet/CSV/JSON), `table_function`. **No `materialized='iceberg'`.**
- **DuckLake is the only first-class lakehouse format dbt-duckdb supports natively** (`is_ducklake: true`, `partitioned_by=[...]`). DuckLake is the DuckDB Foundation's own format — **not** Iceberg. See `docs/research/ducklake.md`.
- **Iceberg via DuckDB extension**: reads via `iceberg_scan(...)`; writes only via a **REST-catalog attach** (`iceberg_rest_catalogs.html`). v3-spec writes and geometry are unsupported.
- **Python models**: receive a raw `DuckDBPyConnection`. A user *could* call `pyiceberg.Table.append(...)` inside one — but this is not a documented dbt-duckdb materialization, just user code in dbt's process.

**Implication**: there is **no clean "drop in your dbt project, get Iceberg out" path today**. Realistic v0.3 patterns:

1. **dbt → external Parquet → Nucleus commits to Iceberg** (two-step; `materialized='external'` + AMA pyiceberg commit). **Safest today.**
2. **dbt → DuckDB-attached Iceberg REST catalog** (single-step). Needs DuckDB at a version where REST-catalog writes are stable + Lakekeeper or Polaris in the loop — v0.3 timeline anyway per v4.1 §5.7.
3. **dbt Python models invoking `pyiceberg`** — user-authored, unsanctioned. Reject for v0.3.

Provisional stance: **(1) for safety + composability today; switch to (2)** once the DuckDB Iceberg write path matures.

### §4.4 Fallback trigger from PoC #2 (the only v0.1-relevant section here)

Per `nucleus_poc_plan.md` §2: *"If LOC blows past 2500 OR DAG resolution slow OR multi-CTE breaks → fall back to dbt-duckdb as v0.1 default."*

| Trigger | Action |
|---|---|
| Native resolver exceeds 2500 LOC | Open ADR to swap-in dbt-duckdb as v0.1 default |
| `{{ ref(...) }}` DAG resolution slow (>500 ms / 100 nodes) | Open ADR to swap-in dbt-duckdb |
| Multi-CTE / nested-ref resolution fails on fixtures | Open ADR to swap-in dbt-duckdb |
| Jinja sandbox security holes appear | Open ADR; may also re-scope native resolver |

If ANY fires, this doc graduates from "forward-leverage" to "v0.1 critical-path". Re-verify §3–§8 before that ADR.

---

## §5. APIs Nucleus would wrap (if/when v0.3 lands)

Symbols a v0.3 adapter would call. **All `NEEDS VERIFICATION` at v0.3 time** — dbt-core's Python API has churned 1.5 → 1.11.

- `dbtRunner` from `dbt.cli.main` — programmatic entry per `/reference/programmatic-invocations`. **NEEDS VERIFICATION** on 1.11.x.
- `dbtRunner().invoke([...])` — `["parse"]` / `["compile"]` / `["build", "--select", ...]`.
- `target/manifest.json` — parse for node graph. Schema versioned per `/reference/artifacts/manifest-json`.
- Always invoke with `--profiles-dir .nucleus/dbt/` to avoid stomping on user's `~/.dbt/profiles.yml`.
- **Do NOT import `dbt.adapters.duckdb` directly** — call through `dbtRunner`.
- Alternative: `from dagster_dbt import DbtCliResource, dbt_assets` (Dagster owns graph, dbt is worker; https://docs.dagster.io/integrations/libraries/dbt/dbt). Pin `dagster-dbt` alongside `dagster`; major bump of either = ADR.

**Materialization mapping** (per `/duckdb-configs`): `table`/`view` → `@nucleus.asset(materialization=...)`; `incremental` (`append`/`delete+insert`) OK on DuckDB 1.1.3; **`merge` needs DuckDB ≥ 1.4.0** (blocked); `microbatch` needs dbt-duckdb ≥ 1.9 (OK on 1.10.1); `external` (Parquet) → **the realistic Iceberg bridge** (§4.3); `table_function` unmapped; **Python models rejected for v0.3** (leaks raw `DuckDBPyConnection` — §8).

---

## §6. Compatibility with Nucleus pins (2026-05-13)

dbt-core 1.11.9's transitive deps **conflict with our `click` pin** and require pre-cursor upgrades.

| Nucleus dep | Our pin | dbt-core 1.11.9 / dbt-duckdb 1.10.1 require | Conflict? | Resolution |
|---|---|---|---|---|
| `click` | `8.1.7` | `<9.0,>=8.3.0` (via dbt-core) | **YES — BLOCKING** | Pre-cursor ADR: bump to `8.3.x`, one-component-per-PR per §11.13. |
| `jinja2` | `3.1.5` | `<4,>=3.1.3` | No | OK |
| `duckdb` | `1.1.3` | dbt-duckdb `>=1.0.0` | No (basic) | **`merge` strategy needs DuckDB ≥ 1.4.0** — defer until DuckDB upgrade |
| `pyarrow` | `18.1.0` | (transitive via `dbt-common`) | NEEDS VERIFICATION | Re-resolve at v0.3 time |
| Python | `>=3.11,<3.13` | `>=3.10` (both) | No | OK; dbt-duckdb 1.10.x dropped 3.8/3.9 |
| `dagster` | `1.9.5` | (no direct) | (n/a) | If `dagster-dbt`: pin alongside `dagster`; major bump = ADR |
| `pyiceberg` | `0.8.1` | (no direct) | No | dbt-duckdb does **not** depend on `pyiceberg`; Iceberg writes go through DuckDB ext or our AMA (§4.3) |
| Windows wheels | required | pure-Python | No | OK |

**Dependency surface + telemetry**: dbt-core 1.11.9 has 22 direct `requires_dist` (PyPI 2026-05-13); transitive closure ~40-50 packages, **2-3× current Nucleus runtime surface**. `snowplow-tracker` is a runtime dep — the v0.3 adapter MUST set `DBT_SEND_ANONYMOUS_USAGE_STATS=false` (or `send_anonymous_usage_stats: False` in `dbt_project.yml`) before any invocation, plus a CI smoke test asserting zero outbound calls to `*.snowplowanalytics.com` during `nucleus build`. **Non-negotiable for the "local-first" promise** (§1.5).

---

## §7. Swap-target analysis (v4.1 §9.3)

v4.1 §17.1 lists `dbt-duckdb / SQLMesh` as the swap pair. Native `ctx.sql` is the v0.1 default.

| Candidate | License | Cost | Notes |
|---|---|---|---|
| **dbt-duckdb + dbt-core** | Apache-2.0 / (presumed) | Medium (~500 LOC adapter; ~40-50 transitive deps; vocab translator; telemetry mute; `click` pre-cursor) | Largest ecosystem; existing-project migration is the real value. Vocabulary collision is the real cost. |
| **SQLMesh** | Apache-2.0 (verify) | Medium (~500 LOC adapter; semantic-layer overlap) | True incremental, virtual data envs. **Better fit for AI-assisted v0.5+** (cleaner state model). Smaller ecosystem. |
| **Native `ctx.sql` + Jinja + sqlglot** | (in-house) | Already v0.1 default | ~1000 LOC owned outright. Bound by §5.6.0 ceiling (no macros, no semantic layer, no adapter framework). |
| **Pure SQL (no templating)** | (in-house) | Trivial | Loses `{{ ref() }}`. Rejected — dep-graph resolution is the point. |

**Verdict**: keep both swap interfaces (dbt-duckdb *and* SQLMesh) at the `nucleus.transformations.TransformationEngine` Protocol level — interface + smoke tests, full adapter on-demand per v4.1 §9.3. **Build dbt-duckdb first when v0.3 lands** (migration ecosystem). **Build SQLMesh second** if AI-assisted v0.5+ proves it the better fit. Native `ctx.sql` remains the protocol's default.

---

## §8. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge)

- ❌ `dbt.run()` as a Python entry — older API; current is `dbtRunner().invoke([...])`. **NEEDS VERIFICATION at v0.3 ADR time.**
- ❌ `@dbt.model` decorator — does not exist. dbt models are `.sql` files + `{{ config(...) }}`.
- ❌ `materialized='iceberg'` — does not exist in dbt-duckdb today (§4.3).
- ❌ `dbt_duckdb.write_iceberg(...)` — fabricated.
- ❌ `from dbt_duckdb import DBTDuckDBAdapter` — internal; do not import. Use `dbtRunner` or `dagster-dbt`.
- ❌ `pyproject.toml` with `"dbt-duckdb==1.10.1"` alone — must also pin `dbt-core==1.10.x` AND resolve the `click` upgrade first.
- ❌ "dbt-duckdb is MIT licensed" — Apache-2.0 per PyPI 2026-05-13.
- ❌ "dbt-core is Apache-2.0" — **likely true but PyPI metadata is blank**; verify against `LICENSE` on `dbt-labs/dbt-core` before pinning.
- ❌ Citing `jwills/dbt-duckdb` — that's the original author's personal fork. Current maintained location is `duckdb/dbt-duckdb`.

### Real gotchas from official docs (2026-05-13)

- **Maintainer transition lag.** dbt-duckdb's PyPI `home_page` still points to `jwills/dbt-duckdb`. Actively-maintained repo is `duckdb/dbt-duckdb` (DuckDB Foundation), per dbt-labs docs + release GPG signatures (key `B5690EEEBB952194`). **Cite the `duckdb` org repo.**
- **dbt-core multi-package split (1.8+).** Now `dbt-core` + `dbt-adapters` + `dbt-common` + `dbt-protos` + `dbt-semantic-interfaces`. Five-way pin coordination — one PR per sub-package per AGENTS.md §11.13.
- **Snowplow telemetry by default** (§6). Release-blocker smoke test required.
- **`merge` incremental needs DuckDB ≥ 1.4.0** — our `1.1.3` blocks it; `delete+insert` / `append` work.
- **Python models leak `DuckDBPyConnection` to user code** — per `/duckdb-configs#python-models`. Violates L1 wrap discipline. v0.3 ADR must reject Python models, wrap as `ctx.engine.duckdb`, or document the leak. **Recommend reject for v0.3.**
- **Treat `manifest.json` as read-only.** Manifest drift breaks runs.
- **Interactive shell launches DuckDB UI** (browser-based, dbt-duckdb ≥ 1.9.3). Disable in CI / non-interactive paths.
- **`profiles.yml` location collision.** Always invoke with `--profiles-dir .nucleus/dbt/`.
- **DuckLake ≠ Iceberg.** Correct user expectations (§4.3).
- **`dbt-fusion`** (Rust rewrite) in development. Quarterly check on whether the Python adapter remains primary.

---

## §9. Decision log

Per v4.1 D13 + §5.6.0:

- **v0.1 (Mo 0-4)**: Native `ctx.sql` + Jinja (~1000 LOC target, ≤2500 LOC ceiling). dbt-duckdb explicitly excluded — reasons stacked in §4.1. **Not on the beachhead path.**
- **v0.3 (Mo 14-20)**: optional adapter for **the migration story**. Opt-in `coordination/dbt_duckdb_adapter.py` (≤500 LOC) per §18.3. Trigger: external user demand from existing dbt-duckdb teams. ADR + smoke tests + telemetry mute mandatory; `click` upgrade is a pre-cursor PR.
- **PoC #2 fallback (Week 3-4)**: per `nucleus_poc_plan.md` §2 (§4.4 above), dbt-duckdb becomes v0.1 default if native resolver trips its triggers.
- **v0.5+**: re-evaluate vs SQLMesh for AI-assisted authoring fit (§17.1).
- **Never**: build our own dbt-core competitor. Constraint #4 / Pillar #2 violation.

**The "support existing dbt projects" promise — clarified**: we promise *if you have a `dbt-duckdb` project, you can run it inside Nucleus without rewriting SQL.* We do **NOT** promise *Nucleus is dbt-compatible* (no dbt-cloud APIs, no dbt-docs UI, no full dbt-tests as user-facing surface). The adapter compiles + runs the user's models inside Nucleus's asset graph; lineage, docs, observability, error messages remain Nucleus-native.

Integration ADR (when v0.3 starts): `docs/decisions/ADR-NNN-dbt-duckdb-v03-adapter.md`.

---

## §10. Next reads when v0.3 work starts

- [ ] Verify `from dbt.cli.main import dbtRunner` at target dbt-core version.
- [ ] Decide `dagster-dbt` vs hand-rolled `dbtRunner` glue. Pinning ADR required.
- [ ] Re-fetch `iceberg_rest_catalogs.html`; pick Iceberg-write path (§4.3 (1) vs (2)).
- [ ] License audit: verify both `LICENSE` files match Apache-2.0 PyPI claim.
- [ ] **Telemetry mute smoke test** (zero `*.snowplowanalytics.com` calls during `nucleus build`). Release blocker.
- [ ] Pin fixed `manifest.json` schema version to parse against.
- [ ] **`click` upgrade ADR** as pre-cursor (`8.1.7` → `8.3.x`); one-component-per-PR.
- [ ] SQLMesh 1-week comparison spike on same fixtures.
- [ ] `dbt-fusion` quarterly status check.

---

## §11. Bookmarks

- `/duckdb-setup` and `/duckdb-configs` (§3) — the two pages you re-read at every v0.3 PR.
- https://docs.dagster.io/integrations/libraries/dbt/dbt — authoritative for `dagster-dbt`.
- `nucleus_architecture_v4.1.md` §5.6 / §5.6.0 / D13 / §18.3 / §17.1 • `nucleus_poc_plan.md` §2 • `docs/research/{duckdb,ducklake,dlt}.md`.

---

*Last verified: 2026-05-13 against `dbt-duckdb==1.10.1` and `dbt-core==1.11.9`. Re-verify when opening the v0.3 ADR, before pinning either package, on any major bump (1.x → 2.x), or if PoC #2 triggers the fallback per `nucleus_poc_plan.md` §2. Log any AI-fabricated dbt or dbt-duckdb APIs caught in PR review to [`docs/research/ai_hallucinations.md`](./ai_hallucinations.md).*
