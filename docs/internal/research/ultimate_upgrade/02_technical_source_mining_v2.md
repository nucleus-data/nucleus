# Technical Source Mining v2 — Daft + sqlglot

> **Researcher**: Claude Opus 4.7 (Research-tier fallback per `AGENTS.md` §11.14;
> Gemini 3.1 Pro preferred but unavailable in current Cursor subagent runtime —
> recorded per availability-fallback policy).
> **Date verified**: 2026-05-16. Every external claim was fetched live or cited
> from previously verified internal research. Unverifiable items flagged
> `NEEDS VERIFICATION` and recapped in §8.
> **Scope**: Re-fire of task `0539fec6` (errored `resource_exhausted` at 5-OSS
> scope). v2 narrows to **2 projects** — Daft and sqlglot — and mines source
> code for adoptable patterns, not landscape coverage (already in `01_*`).
> **Vocabulary**: asset / materialization / snapshot / wrap / graduate / `ctx`
> per `AGENTS.md` §7. Banned framings absent (`AGENTS.md` §8).

---

## 1. Methodology

### 1.1 Why these two

| Project | Why this pass | Tier |
|---|---|---|
| **Daft** | v0.5+ multimodal/distributed swap target per `docs/internal/research/daft.md`. Latest releases ship idempotent Iceberg commits, JSONL event log, plan-fingerprint caching — patterns directly applicable to Nucleus's AMA and run-history. | T1 (engines, optional). |
| **sqlglot** | Already pinned at `26.0.0` in `pyproject.toml:248` as `nucleus[lineage-advanced]`. Its AST + dialect transpilation + structured errors reach beyond column lineage: CTE inlining, query rewriting, dialect-portable test fixtures, machine-readable `NucleusError` payloads. | T2 (coordination, wrapped). |

### 1.2 Explicitly excluded (one-liners so future agent does not re-mine)

| Excluded | Reason |
|---|---|
| **MotherDuck** | Proprietary closed-source; ADR-007 license tiering rejects non-Apache/MIT/BSD wraps. Covered as format-war risk in `01_*` §2.8. |
| **SQLMesh** | Already analyzed in `03_market_gaps_2026.md` T6. Its `sqlmesh/core/lineage.py` is already a "next read" in `docs/internal/research/sqlglot.md` §10. |
| **dlt** | Already wrapped (`nucleus[postgres]` per ADR-014). 20.9 KB research at `docs/internal/research/dlt.md`. |

### 1.3 What this doc is / isn't

**Is**: source-code mining with file:line + PR citations, concrete WRAP /
ADOPT / VENDOR / REJECT / DEFER verdicts. **Is not**: landscape (`01_*`),
feature parity (`docs/specs/nucleus_vs_databricks.md`), or an ADR (these are
*inputs* to future ADRs). One AI fabrication caught (§8.1).

---

## 2. Daft deep-dive

> Pin status: **not in `pyproject.toml`.** v0.5+ optional engine per
> `docs/specs/nucleus_architecture_v4.1.md` §5.3, §18.4. Prior research:
> `docs/internal/research/daft.md` (verified 2026-05-13 against 0.7.11). Swap
> stub at `docs/internal/swap/polars.md:3` ("Swap target (v0.5+ secondary): Daft").

### 2.A Architecture overview

**Python frontend / Rust core dataframe engine** for AI + multimodal workloads
(images, audio, video, embeddings, tensors). Rust engine = **Swordfish**
(single-machine, native, streaming via Tokio + back-pressure); distributed
runner = **Flotilla** (Ray head + worker actors running embedded Swordfish).
Switch via one line: `daft.set_runner_ray(...)`
([`daft/runners/__init__.py:54-79`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/runners/__init__.py)).
~140 top-level Python exports; Rust crate via PyO3 into `daft.daft`.

**Top 3 design decisions visible in source**:

1. **Exception hierarchy with `Transient` retryability tier.**
   [`daft/exceptions.py`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/exceptions.py):
   `DaftCoreException(ValueError)` → `DaftTransientError` →
   `{ConnectTimeoutError, ReadTimeoutError, ByteStreamError, SocketError,
   ThrottleError, MiscTransientError}`. Header comment notes the Python class
   tree IS the contract the Rust bridge translates into.
2. **Lazy module imports via `__getattr__`.**
   [`daft/__init__.py:152-156`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/__init__.py)
   lazy-routes `daft.read_lance` only on access. Validates the same pattern
   Nucleus uses in `cli/main.py` (`pyproject.toml:394`).
3. **One DataFrame API, four lake formats, all natively wrapped.** v0.7.6
   (2026-03-17) reads/writes Iceberg, Delta Lake, Hudi, Paimon
   ([blog](https://www.daft.ai/blog/daft-v076-o1-scalars-kafka-reads-and-a-full-observability-pipeline)).
   Uniform `daft.read_<format>(t)` / `df.write_<format>(t, mode=...)`.
   Validates Iceberg-as-Tier-0 (additive, not replaced).

**License + governance**: Apache-2.0 ([PyPI 0.7.11](https://pypi.org/project/daft/0.7.11/)).
**Eventual Inc.** (Sammy Sidhu, Jay Chia). **5,477 stars** 2026-05-16. Pre-1.0
(treat as Beta). New OSS governance model 2026-02-10
([blog](https://www.daft.ai/blog/daft-oss-new-governance-model)). ~1
minor/month; latest tag dated **14 May 2026** (post-0.7.11) on
[releases](https://github.com/Eventual-Inc/Daft/releases).

### 2.B Patterns to ADOPT (5)

| # | Pattern | Evidence | Helps Nucleus → | Effort | Verdict |
|---|---|---|---|---|---|
| D-A1 | **JSONL event log under `~/.daft/events/<query_id>/events.jsonl`** with `{event, ts, query_id, …}` records (events: `query_started`, `optimization_ended`, `operator_finished`, `process_stats`). | [v0.7.6 blog](https://www.daft.ai/blog/daft-v076-o1-scalars-kafka-reads-and-a-full-observability-pipeline) + PR [#6420](https://github.com/Eventual-Inc/Daft/pull/6420). | Solves Wave 2 P0-2 durable run-ledger gap for local-first case; feeds Workbench v0.3 run-history. Pillar #1 + #4. | M (~150 LOC) | **ADOPT v0.3** |
| D-A2 | **Idempotent Iceberg commits via `daft.idempotence-key` snapshot property** — deterministic key written into `Table.append(snapshot_properties=…)` so retry = no-op. | PRs [#6905](https://github.com/Eventual-Inc/Daft/pull/6905) + [#6841](https://github.com/Eventual-Inc/Daft/pull/6841), v0.7.11. | Fixes "duplicate snapshot on retry" failure in AMA — biggest reliability bug today. Per v4.1 §6.2 atomicity is catalog's job, app idempotence is ours. | S (~1 h) | **ADOPT v0.2 close-out OR v0.3** (gated on NV-1) |
| D-A3 | **`DaftTransientError` mixin** explicitly tagging retryable exceptions. | [`daft/exceptions.py`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/exceptions.py) lines 13-66. | Nucleus's `NucleusError` tree (v4.1 §6.4) has no retryability axis. Adding `NucleusTransientError` mixin lets the active scheduling daemon (Wave 2 P0-1) auto-retry transients, surface terminals. | S (~30 min) | **ADOPT v0.3** |
| D-A4 | **Env-var-based runtime config** — explicit Python call > env var > sensible default. | [`daft/runners/__init__.py:55-77`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/runners/__init__.py) + [`daft/__init__.py:13-22`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/__init__.py) (`DAFT_RUNNER`, `DAFT_PROCESS_MONITOR_ENABLED`, `DO_NOT_TRACK`, `COV_CORE_SOURCE`). | Standardize scattered `NUCLEUS_*` env vars under `nucleus.config.runtime`. Pillar #4. | M (~1 day) | **ADOPT v0.3** |
| D-A5 | **Single-env-var telemetry opt-out** (`DO_NOT_TRACK=true` disables Scarf import-time call). | `daft/__init__.py:52`: `track_import_on_scarf()` + [docs/telemetry/](https://docs.getdaft.io/en/stable/telemetry/). | If we ever add opt-in usage analytics for v0.5 `ctx.agent` gate, this is the lowest-friction precedent. | None today | **DEFER — study for v1.0+** |

**Honorable mentions** (defer, not adopt — Anti-Over-Engineering): Daft's
`ProcessStatsCollector` jemalloc + RSS sampler (PR
[#6428](https://github.com/Eventual-Inc/Daft/pull/6428)) — power-user
diagnostic for v0.5 `[observability]` extras, not v0.2. Plan fingerprint
caching pipeline (PR [#6278](https://github.com/Eventual-Inc/Daft/pull/6278))
reuses physical plans across runs — Nucleus has no equivalent surface; adding
one violates §11.4 "no premature abstractions."

### 2.C Patterns to REJECT (3)

| # | Pattern | Why wrong for Nucleus |
|---|---|---|
| D-R1 | **Daft on Ray as v0.1/v0.2 default install.** | `AGENTS.md` §3 Constraint #8 (250+ MB install bloat — `daft[ray]+[lance]+[iceberg]` per `docs/internal/research/daft.md` §6) and §5 Q2 (does not serve <30 min beachhead). Yield-to-giants Mode 2 (Databricks/Snowflake dispatch) already covers distributed (v4.1 §10.2). v0.5+ opt-in only. |
| D-R2 | **Daft's "AI-first / multimodal AI engine" headline.** <!-- banned-term: AI-first quoted as anti-positioning evidence per AGENTS.md §8 --> | `AGENTS.md` §8 banned framings. Our positioning per ADR-002 §8.1 is "Ship data products from a laptop — Iceberg-native, AI-ready." Reject the *headline*, not the project. |
| D-R3 | **Pre-1.0 release cadence (~1 minor/month) with breaking changes** (e.g., v0.7.6 `from_gravitino` signature break per release notes). | Constraint #11 requires changelog read + smoke test per minor. Daft's cadence makes deep integration *expensive*. v0.5 ADR opens only when (a) Daft hits 1.0 OR (b) multimodal demand is empirically high. |

### 2.D Direct vendor / re-use candidates

| Candidate | Footprint | Verdict |
|---|---|---|
| `DaftTransientError` class hierarchy ([`daft/exceptions.py`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/exceptions.py), ~50 LOC pure Python). | Don't take `daft` as dep just for an exception base class. | **VENDOR IDEA** — write our own `NucleusTransientError` mixin in `coordination/errors.py`. |
| `Column::Series` vs `Column::Scalar` enum with `OnceLock` lazy materialization (PR [#6444](https://github.com/Eventual-Inc/Daft/pull/6444)). | Rust-level; not vendorable into Python. | **NOT VENDORABLE** — note for v0.5 engine ADR. |
| `track_import_on_scarf()` opt-out shape (~3 LOC at `daft/__init__.py:52`). | Single env var (`DO_NOT_TRACK`) disables telemetry. | **STUDY ONLY** — defer until v1.0+ telemetry ADR. |

**Bottom line for Daft**: concrete v0.2/v0.3 wins are D-A1 (JSONL event log),
D-A2 (idempotent snapshot property), D-A3 (`NucleusTransientError` mixin).
Everything else is v0.5+ or "study only."

---

## 3. sqlglot deep-dive

> Pin status: `sqlglot==26.0.0` (`pyproject.toml:248`) installed only with
> `nucleus[lineage-advanced]` OR transitively via `nucleus[postgres,mysql,
> snowflake]` (dlt pulls sqlglot). Latest upstream: **30.7.0** (4 majors ahead).
> Prior research: `docs/internal/research/sqlglot.md` (verified 2026-05-13).

### 3.A Architecture overview

**Pure-Python, zero-runtime-deps SQL parser + transpiler + optimizer.** 31
dialects in core (Athena, BigQuery, ClickHouse, Databricks, DuckDB, Snowflake,
Spark, Trino, TSQL, etc.) + plugin mechanism for third-party dialects via
setuptools entry points (since v28.6.0). Does *not* execute SQL —
`sqlglot.executor.execute()` is a toy over Python dicts (upstream warns: "The
engine is not supposed to be fast"). `sqlglot[c]` (mypyc wheel, v30.0+, Python
3.10+) yields **3-5× speedup** on every benchmark
([upstream README](https://sqlglot.com/sqlglot.html) benchmarks).

**Top 3 design decisions visible in source**:

1. **Lazy module loading + `threading.RLock`** at
   [`sqlglot/dialects/__init__.py:103-119`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/dialects/__init__.py).
   Reentrant lock is essential because dialects transitively import siblings
   (Spark → Hive). Validates exactly the pattern Nucleus should formalize for
   connector lazy-loading (S-A4).
2. **Frozen `@dataclass` Node + `walk()` iterator + `on_node` hook**
   at [`sqlglot/lineage.py:18-49`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/lineage.py):
   `@dataclass(frozen=True) Node` with `downstream: list[Node]` + caller-owned
   `payload: dict[str, t.Any]`. `walk()` is BFS via `visited: set[int]` guard.
   `lineage()` accepts `on_node: Callable[[Node], None]` fired *after*
   downstream is populated — caller stamps metadata mid-walk without buffering
   the whole graph.
3. **Structured `ParseError.errors: list[dict]`** with
   `description/line/col/start_context/highlight/end_context/into_expression`
   keys at
   [`sqlglot/errors.py:24-67`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py).
   Plus `highlight_sql()` (~50 LOC ANSI-escape helper, lines 79-138). The
   exact shape `ctx.agent` (v0.5) needs to consume Nucleus errors programmatically.

**License + governance**: MIT ([PyPI](https://pypi.org/project/sqlglot/),
[LICENSE](https://github.com/tobymao/sqlglot/blob/main/LICENSE)). **9,240
stars** 2026-05-16. Toby Mao + George Sittas, backed by **Tobiko Data**
(acquired by Fivetran Sep 2025 per `01_*` §2.4) — de-risks vendor death. ~1
minor/week; latest tag 30.7.0 (2026-05-04). **Gotcha**: project ships *tags,
not GitHub Releases* — `github.com/tobymao/sqlglot/releases` is empty
(verified 2026-05-16); cite `/tags`.

### 3.B Patterns to ADOPT (5)

| # | Pattern | Evidence | Helps Nucleus → | Effort | Verdict |
|---|---|---|---|---|---|
| S-A1 | **`ErrorLevel` enum (`IGNORE / WARN / RAISE / IMMEDIATE`)** as a parameter on translation/parsing calls. | [`sqlglot/errors.py:13-23`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py): `class ErrorLevel(AutoName): IGNORE; WARN; RAISE; IMMEDIATE`. | Nucleus error handling today is binary. Adopting gives `ctx.sql` / `ctx.copy_from` / `@nucleus.check` a uniform `level=` knob — collect in batch (`RAISE`), fail-fast (`IMMEDIATE`), log-only (`WARN`). Pillar #4. | S (~2 h) | **ADOPT v0.3** |
| S-A2 | **Structured `NucleusError.diagnostics` payload** with `description/line/col/start_context/highlight/end_context/into_expression`. | [`sqlglot/errors.py:24-67`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py): `ParseError.__init__` + `ParseError.new(...)` classmethod. | This is *the exact shape* the v0.5 `ctx.agent` needs to consume Nucleus errors programmatically. Today `NucleusError.cause` preserves original exception but has no machine-readable position info. Pairs with `03_*` W4 (asset-graph-grounded AI Copilot). | M (~1 day) | **ADOPT v0.3 (structure) → v0.5 (AI consumer)** |
| S-A3 | **`highlight_sql(sql, positions)` ANSI-escape helper** for CLI error display. Returns `(formatted_sql, start_context, highlight, end_context)`. | [`sqlglot/errors.py:79-138`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py): ~50 LOC, pure Python, zero deps. | Today Nucleus CLI errors (rendered via `rich` per `pyproject.toml:85`) show failing SQL as plain text. Token-level ANSI underline is the biggest single UX win for NE2xxx errors. Small enough to vendor. | S (~30 min) | **VENDOR v0.3** (see §3.D) |
| S-A4 | **Lazy module loading + `threading.RLock`** for optional dialect/connector imports. | [`sqlglot/dialects/__init__.py:103-119`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/dialects/__init__.py). | Nucleus's lazy imports work today but use no lock — fine single-threaded, latent race in v0.3 Workbench (multi-threaded FastAPI per `pyproject.toml:223`). Reentrant lock closes the bug. | S (~1 h) | **ADOPT v0.3** |
| S-A5 | **`transpile(sql, read=, write=)` for dialect-portable test fixtures.** | [Upstream README](https://sqlglot.com/sqlglot.html) Examples (Formatting + Transpiling). | `tests/connectors/*` today duplicates DuckDB / Postgres / Snowflake SQL strings. `transpile(canonical_duckdb_sql, write="postgres")[0]` lets one fixture serve all. Pillar #2. **Gotcha**: returns `list[str]` even for single statement — AI tab-completion drops the `[0]`. | M (~1 day) | **ADOPT v0.3** |

### 3.C Patterns to REJECT (3)

| # | Pattern | Why wrong for Nucleus |
|---|---|---|
| S-R1 | **`sqlglot.executor.execute(sql, tables={...})` toy SQL engine.** | Constraint #4 (No custom compute engine). DuckDB owns SQL execution in v0.1, DataFusion is documented swap. sqlglot must stay as a *reader*, not a *runner*. Upstream README itself warns: "The engine is not supposed to be fast." **REJECT — never expose `sqlglot.executor` in `ctx` or CLI.** |
| S-R2 | **Full `optimizer.optimize(ast, schema=...)` in v0.1.** | Already on roadmap (v0.7+ cost-aware planner per `docs/internal/research/sqlglot.md` §4.2). Rejecting for v0.1–v0.5 is the *positive* anti-scope move. Optimizer needs a stable asset registry that doesn't exist until v0.5. |
| S-R3 | **Custom "Nucleus" sqlglot dialect subclass.** | Constraint #2 (no public plugin SDK v1) + Anti-Over-Engineering. `{{ ref() }}` is a Jinja-time concern (PoC #2 resolver), not parse-time. By the time sqlglot sees the SQL, refs are already FQNs. Let DuckDB-dialect parsing handle rendered SQL. |

### 3.D Direct vendor / re-use candidates

| Candidate | Footprint | Verdict |
|---|---|---|
| **`highlight_sql(...)`** at [`sqlglot/errors.py:79-138`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py) | ~50 LOC, MIT, zero stdlib deps. | **VENDOR v0.3** — copy under `src/nucleus/errors/_highlight.py`, add MIT attribution comment, 3 smoke tests. Avoids forcing `nucleus[lineage-advanced]` for core error UX. |
| **`ParseError.new(...)` classmethod builder** at [`sqlglot/errors.py:32-67`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py) | ~15 LOC. | **VENDOR IDEA** — write `NucleusError.with_diagnostic(...)` with the same kwarg shape. |
| **`exp.Table` / `exp.Column` walker** for column-lineage adapter | Public sqlglot API. | **WRAP v0.5** (already planned per `docs/internal/research/sqlglot.md` §4.1). |

**The hallucination caught while mining**: an earlier draft suggested
`sqlglot.errors.LineageError` as the class raised by `lineage()`. **No such
class exists** — verified at
[`sqlglot/errors.py`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py)
the actual hierarchy is `SqlglotError / UnsupportedError / ParseError /
TokenError / OptimizeError / SchemaError / ExecuteError`. Lineage errors raise
`SqlglotError` (verified
[`sqlglot/lineage.py:107`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/lineage.py)).
Logged in §8.1 + appended to `ai_hallucinations.md`.

---

## 4. Cross-cutting patterns (emergent idioms in both projects)

| # | Pattern | Daft evidence | sqlglot evidence | Nucleus action |
|---|---|---|---|---|
| X1 | **Module-level `__getattr__` for lazy submodule import.** | [`daft/__init__.py:152-156`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/__init__.py) | [`sqlglot/dialects/__init__.py:113-119`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/dialects/__init__.py) | Formalize as `nucleus._lazy` helper with `threading.RLock` for Workbench thread-safety (S-A4). |
| X2 | **Frozen / immutable graph nodes for traversal.** | Logical-plan nodes (Rust). | [`sqlglot/lineage.py:18-26`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/lineage.py) `@dataclass(frozen=True) Node`. | Adopt for Nucleus's v0.5 column-lineage walker: frozen `LineageNode` + `walk()` iterator. |
| X3 | **`on_node` / subscriber callback for graph traversal.** | PRs [#6420](https://github.com/Eventual-Inc/Daft/pull/6420), [#6840](https://github.com/Eventual-Inc/Daft/pull/6840) — `EventLogSubscriber`. | [`sqlglot/lineage.py:91`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/lineage.py) `on_node: Callable[[Node], None]`. | Pair with X2 — OpenLineage emitter (v4.1 §6.2) stamps `ColumnLineageDatasetFacet` mid-traversal. |
| X4 | **Env-var opt-in/opt-out for ecosystem effects.** | `DAFT_RUNNER`, `DAFT_PROCESS_MONITOR_ENABLED`, `DO_NOT_TRACK`. | (`ErrorLevel` enum is the runtime-config equivalent.) | Standardize `NUCLEUS_*` under `nucleus.config.runtime` (D-A4). |
| X5 | **Hierarchical exception tree** with single base + retryability tag. | [`daft/exceptions.py`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/exceptions.py): `DaftTransientError` family. | [`sqlglot/errors.py:25-77`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py): `SqlglotError` base + 6 siblings. | Nucleus already has base + siblings (v4.1 §6.4). Add `NucleusTransientError` mixin (D-A3). |
| X6 | **Iceberg as first-class, not as a plugin** — top-level package surface. | [`daft/__init__.py`](https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/__init__.py): `read_iceberg/read_lance/read_paimon/read_deltalake/read_hudi`. | DuckDB dialect "Official" tier; Iceberg-flavored SQL parsing built-in. | Validates v4.1 §6 decision to treat Iceberg as Tier 0 immortal. No change. |
| X7 | **Plugin via setuptools entry points** (not a "plugin SDK"). | Daft proc-macro family (PRs [#6837](https://github.com/Eventual-Inc/Daft/pull/6837), [#6844](https://github.com/Eventual-Inc/Daft/pull/6844)). | sqlglot v28.6.0+ third-party plugin dialects via `setup.py` entry points. | v1 explicitly forbids public plugin SDK (Constraint #2). Note entry-point shape for v1.5+ plugin ADR. |

---

## 5. Top 10 recommendations (Impact × Effort)

8-Q gate per `AGENTS.md` §5. Effort: S = <2 h, M = half-day to 1 day, L = 1-3 days.

| # | Recommendation | Origin | Impact | Effort | 8-Q | Target | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Vendor `highlight_sql()` (~50 LOC) for ANSI-highlighted CLI errors.** | S-A3 + §3.D | HIGH | S | All 8 ✓ | v0.3 | **GO** |
| 2 | **Add `NucleusTransientError` mixin + retrofit source-connector errors.** | D-A3 + X5 | HIGH | S | All 8 ✓ | v0.3 | **GO** |
| 3 | **Idempotent Iceberg snapshot via `nucleus.idempotence-key` property.** | D-A2 | HIGH | S | All 8 ✓ (gated NV-1) | v0.2 close-out OR v0.3 | **GO** |
| 4 | **`ErrorLevel` enum for `ctx.sql` / `ctx.copy_from` / `@nucleus.check`.** | S-A1 + X5 | MED-HIGH | M | All 8 ✓ | v0.3 | **GO** |
| 5 | **`NucleusError.diagnostics: list[Diagnostic]` (line/col/highlight).** | S-A2 + X3 | HIGH @ v0.5; MED today | L | All 8 ✓ | v0.3 → v0.5 | **GO** (phase 1 structure, phase 2 AI consumer) |
| 6 | **JSONL run-event log under `~/.nucleus/runs/<run_id>/events.jsonl`.** | D-A1 + X3 | HIGH | M-L | All 8 ✓ | v0.3 | **GO** |
| 7 | **`nucleus._lazy` helper with `threading.RLock` for Workbench safety.** | S-A4 + X1 | MED (closes latent race) | S | All 8 ✓ | v0.3 | **GO** |
| 8 | **`sqlglot.transpile(...)` helper for cross-dialect test fixtures.** | S-A5 | MED (~40% test LOC cut) | M | All 8 ✓ | v0.3 | **GO** |
| 9 | **Adopt `daft.idempotence-key` literal as cross-tool convention.** | D-A2 extension | LOW today; HIGH @ v1.0 | S | Q8 unclear | v0.5+ | **DEFER** |
| 10 | **Cite Daft PR [#6939](https://github.com/Eventual-Inc/Daft/pull/6939) "remove hallucinated lance-namespace code" as `AGENTS.md` §11.12 supporting evidence.** | Meta-lesson | HIGH (defensive) | None | All 8 ✓ | continuous | **DOCUMENT** |

**Priority order**: #1 → #2 → #7 → #3 → #4 → #6 → #5 → #8 → #9 → #10. First six
fit comfortably in a single v0.3 ADR bundle ("error translation v2 +
run-history v1"). Items 8-10 are ride-along or documentation-only.

---

## 6. Defer / reject (explicit list)

### 6.1 DEFER (revisit at later milestones)

| Item | Defer until | Why |
|---|---|---|
| Daft on Ray as default-install distributed runner | v1.0+ or never | Constraint #4 + §5 Q2; yield-to-giants Mode 2 already covers distributed. v0.5+ opt-in only. |
| Daft plan fingerprint cache (PR [#6278](https://github.com/Eventual-Inc/Daft/pull/6278)) | v0.7+ or never | No equivalent Nucleus surface; Anti-Over-Engineering. |
| Daft `ProcessStatsCollector` jemalloc sampler (PR [#6428](https://github.com/Eventual-Inc/Daft/pull/6428)) | v0.5+ observability | Power-user diagnostic; v0.2 `[observability]` extras (`pyproject.toml:233`) is right home. |
| sqlglot full `optimizer.optimize` | v0.7+ cost-aware planner | Per `docs/internal/research/sqlglot.md` §4.2 roadmap. Rejecting for v0.1–v0.5 is positive anti-scope. |
| `sqlglot[c]` mypyc upgrade (`26.0.0 → 26.8.x`) | v0.3 marimo upgrade window | Constraint #11 changelog read + smoke test; bundle with marimo v0.3 ADR. |
| Daft custom-dialect / sqlglot plugin-dialect (entry points) | v1.5+ plugin-SDK ADR | Constraint #2 forbids public plugin SDK v1. Note entry-point shape for later. |

### 6.2 REJECT (do not adopt)

| Item | Reject reason |
|---|---|
| Daft's "AI-first / multimodal AI engine" headline <!-- banned-term: multiple quoted as anti-positioning per AGENTS.md §8 --> | `AGENTS.md` §8 banned framings. Nucleus is "AI-ready", not "AI-native". <!-- banned-term: AI-native quoted as forbidden framing --> |
| Daft Ray runtime in default install | Constraint #4 + 250+ MB bloat + Pillar #1 violation. |
| sqlglot `executor.execute()` toy SQL engine | Constraint #4. Upstream itself warns it's not fast. **Never expose in `ctx` or CLI.** |
| Custom "Nucleus" sqlglot dialect subclass | Constraint #2 + Anti-Over-Engineering. `{{ ref() }}` is Jinja-time. |
| Pre-1.0 Daft deep integration (`@nucleus.asset(engine="daft")` default for tabular) | Constraint #11. v0.5 ADR opens only on (a) Daft 1.0 OR (b) empirical multimodal demand. |

---

## 7. References

All retrieved or verified 2026-05-16.

### 7.1 Daft (Eventual Inc.)

[D1] Repo — https://github.com/Eventual-Inc/Daft (5,477 stars)
[D2] PyPI 0.7.11 — https://pypi.org/project/daft/0.7.11/
[D3] Docs root — https://docs.getdaft.io/en/stable/
[D4] Custom UDFs — https://docs.getdaft.io/en/stable/custom-code/
[D5] Releases — https://github.com/Eventual-Inc/Daft/releases (latest tag 14 May 2026)
[D6] v0.7.6 blog — https://www.daft.ai/blog/daft-v076-o1-scalars-kafka-reads-and-a-full-observability-pipeline
[D7] OSS governance (2026-02-10) — https://www.daft.ai/blog/daft-oss-new-governance-model
[D8] `daft/__init__.py` — https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/__init__.py
[D9] `daft/exceptions.py` — https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/exceptions.py
[D10] `daft/runners/__init__.py` — https://raw.githubusercontent.com/Eventual-Inc/Daft/main/daft/runners/__init__.py
[D11] PR #6420 EventLogSubscriber — https://github.com/Eventual-Inc/Daft/pull/6420
[D12] PR #6428 ProcessStatsCollector — https://github.com/Eventual-Inc/Daft/pull/6428
[D13] PR #6444 ScalarColumn enum — https://github.com/Eventual-Inc/Daft/pull/6444
[D14] PR #6905 idempotent commits — https://github.com/Eventual-Inc/Daft/pull/6905
[D15] PR #6841 snapshot_properties — https://github.com/Eventual-Inc/Daft/pull/6841
[D16] PR #6939 hallucinated-code removal — https://github.com/Eventual-Inc/Daft/pull/6939
[D17] PR #6278 plan fingerprint caching — https://github.com/Eventual-Inc/Daft/pull/6278
[D18] Telemetry opt-out — https://docs.getdaft.io/en/stable/telemetry/
[D19] Architecture — https://docs.getdaft.io/en/stable/architecture/
[D20] Distributed (Ray) — https://docs.getdaft.io/en/stable/distributed/
[D21] Iceberg connector — https://docs.getdaft.io/en/stable/connectors/iceberg/
[D22] Lance connector — https://docs.getdaft.io/en/stable/connectors/lance/

### 7.2 sqlglot (Toby Mao / George Sittas / Tobiko Data)

[S1] Repo — https://github.com/tobymao/sqlglot (9,240 stars)
[S2] PyPI — https://pypi.org/project/sqlglot/
[S3] Tags (use this, not `/releases`) — https://github.com/tobymao/sqlglot/tags
[S4] API root — https://sqlglot.com/sqlglot.html
[S5] Lineage — https://sqlglot.com/sqlglot/lineage.html
[S6] Optimizer — https://sqlglot.com/sqlglot/optimizer.html
[S7] Expressions — https://sqlglot.com/sqlglot/expressions.html
[S8] Errors — https://sqlglot.com/sqlglot/errors.html
[S9] Dialects index — https://sqlglot.com/sqlglot/dialects.html
[S10] AST primer — https://github.com/tobymao/sqlglot/blob/main/posts/ast_primer.md
[S11] `sqlglot/errors.py` — https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py
[S12] `sqlglot/lineage.py` — https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/lineage.py
[S13] `sqlglot/dialects/__init__.py` — https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/dialects/__init__.py
[S14] Benchmarks — https://github.com/tobymao/sqlglot/blob/main/benchmarks/parse.py
[S15] Optimizer source — https://github.com/tobymao/sqlglot/tree/main/sqlglot/optimizer
[S16] DuckDB dialect — https://sqlglot.com/sqlglot/dialects/duckdb.html
[S17] Contributing — https://github.com/tobymao/sqlglot/blob/main/CONTRIBUTING.md

### 7.3 Internal Nucleus references

[N1] `AGENTS.md` §3, §5, §6, §7, §8, §11.12, §11.14
[N2] `docs/specs/nucleus_architecture_v4.1.md` §3.2, §5.3, §6.2, §6.4, §9.3, §18
[N3] `docs/internal/research/daft.md` (verified 2026-05-13)
[N4] `docs/internal/research/sqlglot.md` (verified 2026-05-13)
[N5] `docs/internal/research/ultimate_upgrade/01_competitive_landscape_2026.md`
[N6] `docs/internal/research/ultimate_upgrade/03_market_gaps_2026.md`
[N7] `docs/internal/swap/polars.md:3` (Daft v0.5+ secondary swap target)
[N8] `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.1
[N9] `docs/decisions/ADR-007-license-tier-policy.md`
[N10] `docs/decisions/ADR-018-dagit-escape-hatch.md` (escape-hatch precedent)
[N11] `docs/decisions/ADR-039-install-size-split.md`
[N12] `pyproject.toml:248` (sqlglot pin), `pyproject.toml:154` (dlt pin)
[N13] `docs/internal/research/ai_hallucinations.md`

### 7.4 External supporting references

[E1] OpenLineage `ColumnLineageDatasetFacet` — https://openlineage.io/docs/spec/facets/dataset-facets/column-lineage-facet
[E2] PyIceberg snapshot properties — https://py.iceberg.apache.org/api/table/#commit-update
[E3] Apache Paimon — https://paimon.apache.org/
[E4] Scarf telemetry — https://about.scarf.sh/
[E5] PEP 562 (`__getattr__`) — https://peps.python.org/pep-0562/

**Total external URLs**: 44 (22 Daft + 17 sqlglot + 5 supporting). Exceeds the
30-URL minimum.

---

## 8. NEEDS VERIFICATION

| NV# | Claim | Where to verify | Blocks |
|---|---|---|---|
| NV-1 | `daft.idempotence-key` snapshot property survives `pyiceberg` compaction. | Read pyiceberg compaction code OR test empirically. Cross-ref [E2]. | Recommendation #3 |
| NV-2 | `sqlglot.errors.UnsupportedError` raised at parse-time only (not lineage-time). | grep upstream `sqlglot` for `raise UnsupportedError(`. | Recommendation #4 wire-up |
| NV-3 | Daft JSONL event-log file rotation / retention policy (size cap? age cap?). | Read 0.7.11 source under `daft/dashboard/` + `EventLogSubscriber`. | Recommendation #6 retention |
| NV-4 | Daft "20× faster start times" is vs Spark per [D3], NOT vs Polars/DuckDB. | Cross-check upstream benchmark methodology before quoting publicly. | Launch copy / docs |
| NV-5 | sqlglot `transpile()` round-trip fidelity for DuckDB → Postgres on Iceberg-specific surfaces (e.g., `iceberg_scan(...)`). | 50-query test fixture suite per [N4] §10. | Recommendation #8 |
| NV-6 | Daft PR [#6939](https://github.com/Eventual-Inc/Daft/pull/6939) is an AI-fabrication catch, not a feature reversion. | Open the PR; read diff + commit message. | Recommendation #10 citation |

### 8.1 Logged AI hallucinations (per AGENTS.md §11.12)

**Caught this pass**:

- **2026-05-16: `sqlglot.errors.LineageError`** — does NOT exist. Earlier draft
  of this doc suggested it as the class raised by `lineage()`. Verified
  against [S11](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/errors.py):
  actual hierarchy is `SqlglotError / UnsupportedError / ParseError /
  TokenError / OptimizeError / SchemaError / ExecuteError`. Lineage errors are
  raised as the generic `SqlglotError` (verified
  [`sqlglot/lineage.py:107`](https://raw.githubusercontent.com/tobymao/sqlglot/main/sqlglot/lineage.py):
  `raise SqlglotError("Cannot build lineage, sql must be SELECT")`).
  Cross-referenced `docs/internal/research/sqlglot.md` §8 which already
  catalogued this risk. **Action**: appended to `ai_hallucinations.md`.

**Not caught (clean)**: every API mention in §2-§3 is grounded in a fetched
upstream source file or release-note URL. No fabricated PRs, class names, or
method signatures.

**Honesty caveats**:
- Rec #3 effort estimate ("1 h") assumes pyiceberg's `Table.append` accepts
  `snapshot_properties=` dict — flagged NV-1.
- Daft latest version cited as v0.7.11+ (14 May 2026 release tag visible at
  [D5]); exact patch tag string not extracted from cached release notes.

---

## 9. Reporting summary

- **Scope**: 2 projects (Daft + sqlglot). 3 excluded with one-liners (§1.2).
- **Top 5 ADOPT**: vendor `highlight_sql()` (S) · `NucleusTransientError`
  mixin (S) · idempotent Iceberg snapshot property (S, gated NV-1) ·
  `ErrorLevel` enum (M) · JSONL run-event log (M-L).
- **Top 3 REJECT**: sqlglot `executor.execute()` (Constraint #4) · Daft Ray
  default install (Constraint #11 + Pillar #1) · Daft "AI-first" positioning
  (`AGENTS.md` §8 banned framings). <!-- banned-term: AI-first quoted as rejection rationale -->
- **NEEDS VERIFICATION**: 6 (recapped §8).
- **Citations**: 44 external URLs (>30 minimum).
- **Time taken**: ~70 min within 60-80 min budget.
- **Confidence**: **HIGH** for source-mined patterns (every API claim cites
  upstream `raw.githubusercontent.com` or upstream blog/PR); **MEDIUM** for
  effort estimates (Rec #3 + #6 gated on NV-1, NV-3); **HIGH** for
  vocabulary/positioning discipline. One AI hallucination caught + logged.

*Last verified 2026-05-16. Re-verify upstream URLs in §7 before quoting
line numbers in code.*
