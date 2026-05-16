# Research: SQLGlot

> **Component status in Nucleus**: pinned today, **active in v0.1 only via PoC #2** — `ctx.sql` Jinja resolver walks `exp.Table` to extract `{{ ref() }}` table references and feeds the asset-level dependency graph (`nucleus_poc_plan.md` §3). Column-level lineage lands **v0.5+** per `nucleus_architecture_v4.1.md` §12.4. Cost-Aware Planner lands **v0.7+** per arch §7.5 (brief said v0.5; arch wins per AGENTS.md §2).
> **Pin candidate**: `sqlglot==26.0.0` (released **2024-12-10**, verified on PyPI 2026-05-13). **Already pinned in `pyproject.toml`.**
> **License**: **MIT**  •  **JVM-free**: **YES** — pure Python, zero required runtime deps. Optional `[rs]` adds Rust tokenizer; `[c]` (v30.0+) adds mypyc compile. Hard Constraint #1 satisfied.
> **Research date**: 2026-05-13
> **Used in**: nowhere on disk yet. PoC #2 (Week 3-4) is the first integration target.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening PoC #2, the v0.5 column-lineage ADR, or any sqlglot bump PR.

---

## §1. What SQLGlot is, in Nucleus terms

A **pure-Python SQL parser, transpiler, and optimizer** producing a typed `exp.Expr` AST. **31 dialects**; DuckDB at **Official** tier — first-class, core-team maintained.

- **License**: MIT  •  **Maintainer**: Toby Mao + George Sittas, commercially backed by **Tobiko Data** (the SQLMesh company)  •  **GitHub**: https://github.com/tobymao/sqlglot
- **Position**: L2 Coordination — wrapped behind `ctx.sql` (v0.1) and the future Lineage Engine (v0.5+). Users never `import sqlglot`.
- **Latest stable**: 30.7.0 (2026-05-04). Our pin (26.0.0) is **four majors behind**; tolerable for v0.1 (most stable surface only). Upgrade path: §6.

| SQLGlot concept | Nucleus mapping | Surface |
|---|---|---|
| `parse_one(sql, dialect="duckdb")` | AST behind `ctx.sql` | PoC #2 + v0.5 lineage |
| `exp.Table` walk | **asset-level** dep extraction | feeds `@nucleus.asset(deps=…)` |
| `lineage.lineage(column, sql)` | **column-level** Node graph | OpenLineage `ColumnLineage` facet (v0.5+) |
| `optimizer.optimize(ast, schema=…)` | normalized AST | Cost-Aware Planner (v0.7+) |
| `transpile(read, write)` | — | reserved (v0.7+ portability) |
| `executor.execute(...)` | — | **never**; DuckDB owns execution |

Hard commitment: SQLGlot **reads** our SQL. It does not execute it, mutate Iceberg, or validate schemas — upstream FAQ is explicit ("not a SQL validator").

---

## §2. Official documentation URLs

Verified by `WebFetch` 2026-05-13.

- API root: https://sqlglot.com/sqlglot.html
- **Lineage (THE v0.5+ surface)**: https://sqlglot.com/sqlglot/lineage.html
- Optimizer: https://sqlglot.com/sqlglot/optimizer.html  •  rules: https://sqlglot.com/sqlglot/optimizer/optimizer.html
- Dialects + DuckDB confirmation: https://sqlglot.com/sqlglot/dialects.html  •  https://sqlglot.com/sqlglot/dialects/duckdb.html
- Expressions: https://sqlglot.com/sqlglot/expressions.html  •  Errors: https://sqlglot.com/sqlglot/errors.html  •  Scope: https://sqlglot.com/sqlglot/optimizer/scope.html
- AST primer (mandatory before authoring walkers): https://github.com/tobymao/sqlglot/blob/main/posts/ast_primer.md
- GitHub / tags / PyPI: https://github.com/tobymao/sqlglot • https://github.com/tobymao/sqlglot/tags • https://pypi.org/project/sqlglot/

**404 gaps on 2026-05-13** (flag for AI agents): `github.com/tobymao/sqlglot/releases` is empty (project ships tags, not "Releases" — use `/tags`); `sqlglot.com/sqlglot/lineage` (no `.html`) — pdoc URLs always end `.html`.

---

## §3. APIs Nucleus will wrap

Signatures verified against 26.0.0 docs + lineage.py source.

| Symbol | Signature | Use |
|---|---|---|
| `sqlglot.parse_one` | `parse_one(sql, dialect=None, into=None, **opts) -> exp.Expr` | PoC #2. Always pass `dialect="duckdb"` (default is permissive superset; §8). |
| `sqlglot.exp` | typed AST module (`Select`, `Table`, `Column`, `Window`, `CTE`, `SetOperation`, `Lateral`, `Subquery`, …) | `expr.find_all(exp.Table)` for dep extraction. |
| `sqlglot.lineage.lineage` | `lineage(column, sql, schema=None, sources=None, dialect=None, scope=None, trim_selects=True, copy=True, on_node=None, **kwargs) -> Node \| dict[str, Node]` | v0.5+. `column=None` returns all output cols. **Import: `from sqlglot.lineage import lineage` — §8.** |
| `sqlglot.lineage.Node` | frozen `@dataclass(name, expression, source, downstream: list[Node], source_name, reference_node_name, payload: dict)` | `Node.walk()` depth-first; `payload` is the caller-owned hook for OpenLineage facet inputs. |
| `lineage(on_node=cb)` | callback fired per Node after `downstream` populated | **Integration seam** — stamp `payload["openlineage_input"]` here. |
| `sqlglot.optimizer.optimize` | `optimize(expr, schema=None, dialect=None, rules=RULES, **kwargs) -> exp.Expr` | v0.7+ only. Lineage invokes `qualify` internally (§4.1). |
| `sqlglot.errors.ParseError` | `.errors: list[{description, line, col, start_context, highlight, end_context, …}]` | translates to `NucleusSQLSyntaxError`. |
| `sqlglot.errors.SqlglotError` | base; raised by `lineage()` on non-SELECT, unknown col, unnamed projection | translates to `NucleusLineageError` (v0.5+). |
| `sqlglot.transpile` | `transpile(sql, read, write, identify=False, **opts) -> list[str]` | reserved. Returns a **list** even for single statements (§8). |

**Never used**: `sqlglot.executor.execute` (toy), `sqlglot.diff`, `sqlglot.dataframe` (removed upstream in v24).

---

## §4. Integration points with Nucleus

### §4.1 v0.5+ — column-level lineage from `ctx.sql`

Per arch §12.4. Surface: `nucleus lineage fact.orders --column total` (`nucleus_cli_spec.md`). Adapter target: ≤300 LOC in `intelligence/sql_lineage_adapter.py`.

```python
from sqlglot.lineage import lineage
nodes: dict[str, Node] = lineage(
    column=None, sql=rendered_sql,
    schema=registry_schema,        # dict[table, dict[col, dtype]]
    dialect="duckdb",
    on_node=stamp_openlineage_payload,
)
```

Flow: (1) AMA resolves post-Jinja SQL + asset-registry schema; (2) for each output column traverse `node.walk()`, map each `exp.Table` leaf to its Iceberg-qualified name, collect `(input_table, input_col) → output_col`; (3) emit `OpenLineage RunEvent` with `outputs[*].facets.columnLineage = ColumnLineageDatasetFacet` (cross-cite `docs/internal/research/openlineage.md` §ColumnLineage — parallel research in flight); (4) `SqlglotError` → `NucleusLineageError` at the boundary; never leak `sqlglot.` strings to user CLI (v4.1 §6.4).

Why `lineage()` and not a hand-rolled walker: it already handles CTE expansion (via `qualify`), `SELECT *` expansion when schema is supplied, SetOperation merging, and subquery scope-chasing. Reimplementing is ~800 LOC we cannot afford (§11.6).

### §4.2 v0.7+ — Cost-Aware Planner consumes `optimizer.optimize`

Per arch §7.5. Pre-run estimates need a normalized AST: `optimize(ast, schema=...)` runs predicate pushdown, common-subexpression elimination, type annotation, and `qualify`. **Cost heuristics live in our planner, not sqlglot.** Caveat: `sqlglot.optimizer` uses a PEP-562 lazy `__getattr__` to dodge a `sqlglot[c]` circular import — benign for pure-Python use and with our mypy config (`pyproject.toml` L224-232).

### §4.3 v0.1 — not used for lineage; used in PoC #2 only

| Subsystem | sqlglot in v0.1? | Why |
|---|---|---|
| Asset graph topology + Python-asset lineage | No | Built from `@nucleus.asset(deps=…)` + Dagster materialization events. |
| **SQL-asset lineage (asset-level only)** | **Yes — PoC #2** | Post-Jinja, parse SQL and walk `exp.Table` to discover upstreams. ~50-100 LOC. |
| Column-level lineage | No | Deferred to v0.5+ (§4.1). |
| Cost estimation, transpilation, query optimization | No | Deferred to v0.7+ (§4.2); DuckDB's optimizer is authoritative. |
| Schema validation | **Never** | Not a validator; contracts via `@nucleus.contract` (v4.1 §12.5). |

**v0.1 surface budget**: `parse_one(sql, dialect="duckdb")` + `expr.find_all(exp.Table)` + `expr.find_all(exp.CTE)`. PRs introducing `lineage()` / `optimize()` / `transpile()` before v0.5 → **block** (scope creep per §11.4).

---

## §5. Performance characteristics

Upstream benchmarks (sqlglot 30.x on Python 3.14.3 — https://github.com/tobymao/sqlglot/blob/main/benchmarks/parse.py). **No Nucleus benchmark yet** — replicate under PoC #2 against 26.0.0 before quoting.

| Workload | Pure Python | `sqlglot[c]` |
|---|---|---|
| Short query (~20 tokens) | ~0.23 ms | ~0.08 ms |
| TPC-H query | ~2.7 ms | ~0.74 ms |
| Long query (~500 lines, many CTEs) | ~8.9 ms | ~2.0 ms |
| Pathological 1000-elem `IN` | ~410 ms | ~102 ms |
| Pathological huge `VALUES` | ~467 ms | ~114 ms |

**Target**: parse-time **<10 ms** for typical user SQL (single `SELECT`, ≤5 CTEs, ≤20 joined tables). Validated by `tests/perf/test_parse_time.py` in PoC #2.

- **Pathological cases** trigger 100×+ regression and will hang Workbench. PoC #2 sets a 100 ms parse budget per query; on timeout, fall back to "could not auto-discover; please add `deps=[…]`". Full lineage walk is 5-10× parse time.
- **Boot**: `import sqlglot` ≈ 80-150 ms cold on M-class laptops (NEEDS VERIFICATION on v0.1 stack). Lazy-import inside `intelligence/sql_*` — never at CLI entry (PoC #4 budgets 10 s total).
- **Memory**: <1 MB per AST for ~1000-line query. **Do not cache 10k+ parsed ASTs**; `Expr` nodes are heavyweight.
- **`[c]` mypyc** (v30.0+, Python 3.10+): ~3-4× speedup, ~1 MB extra wheel. **`[rs]` Rust tokenizer**: less mature, separate `sqlglotrs` pin. **Reject both in v0.1**; revisit at v0.5.

---

## §6. Compatibility with Nucleus pins (2026-05-13)

| Nucleus dep | Our pin | sqlglot 26.0.0 requires | Conflict? | Resolution |
|---|---|---|---|---|
| Python | `>=3.11,<3.13` | `>=3.7` | No | OK. (30.x raises floor to `>=3.9`.) |
| Runtime deps | — | **none** | No | Zero-deps at runtime per PyPI. |
| `duckdb` | `1.1.3` | not required | No | DuckDB dialect built-in. |
| `dagster` | `1.9.5` | Dagster imports sqlglot internally | No | Coexist; verify on bumps. |
| `dlt` | v0.3 target | `sqlglot>=25.4.0` | No | Above floor. |
| `marimo[sql]` | v0.3 target | **`sqlglot[c]>=26.8.0`** | **YES — BLOCKING marimo SQL cells** | Upgrade `26.0.0 → 26.8.x[c]` already on v0.3 roadmap per `docs/internal/research/marimo.md` §7. |
| Latest sqlglot | 30.7.0 | — | — | Four majors ahead. Lineage API stable across 26→30 per source; each bump still ADR'd (§11.13). |

**DuckDB dialect coverage** (verified 2026-05-13):

- ✅ `SELECT`, `WITH`, `GROUP BY`, `WINDOW`, `QUALIFY`, `JOIN` (incl. ASOF / POSITIONAL); DuckDB extensions `LIST` / `STRUCT` / `MAP` / `[i:j]` slicing / `**` glob `FROM`.
- ✅ `WITH RECURSIVE` parses; lineage walks `union_scopes` once (L261-300) — **cycle behaviour: §8**.
- ✅ `LATERAL` / `UNNEST` parse to `exp.Lateral` — **scope-chasing non-trivial; verify v0.5 ADR (§8)**.
- ⚠ `iceberg_scan(...)` parses as a generic table function — lineage reports `iceberg_scan` not the underlying Iceberg table. Our Jinja resolver rewrites `{{ ref() }}` to FQNs first (moot for assets); raw user SQL with `iceberg_scan(...)` has weak lineage. Document in `nucleus_cli_spec.md`.

**Upgrade workflow** (AGENTS.md §11.13, one-component PRs): (1) v0.3 prerequisite — `26.0.0 → 26.8.x[c]` for marimo SQL cells (smoke test: PoC #2 fixture suite); (2) v0.5 launch — `26.8.x → 30.x`, **ADR mandatory** (4 majors) — read every minor tag changelog and exercise lineage on the 50-query fixture set; (3) future major bumps — full ADR + lineage golden test re-baseline + benchmark regression check.

---

## §7. Swap-target analysis (v4.1 §9.3)

If sqlglot becomes unviable (license pivot — unlikely given Tobiko's commercial stake; vendor death; perf regression >2×):

| Candidate | License | JVM? | Column-lineage in box? | Cost to swap |
|---|---|---|---|---|
| **SQLFluff** | MIT | No | No — linter/parser only | High (~1.5-2k LOC for lineage layer) |
| **JSQLParser** | LGPL-2.1 / Apache-2.0 | **YES — Java** | Partial | **Violates Constraint #1.** Off the table. |
| **ANTLR grammar** | grammar-dependent | No | No | Very high (~3-5k LOC + per-dialect maintenance) |
| **DuckDB `EXPLAIN (FORMAT JSON)`** | DuckDB MIT | No | Partial (execution-plan, not source-projection) | Medium (~500-800 LOC); use as cross-check, not replacement |
| **OpenMetadata `metadata-ingestion`** | Apache-2.0 | No | Yes — but wraps sqlglot internally | Pointless (re-imports sqlglot) |

**Verdict**: SQLGlot is the only candidate giving **pure Python + MIT + 31 dialects + first-class DuckDB + column-lineage in box + active commercial backing**. Risk: low. Swap interface: `intelligence/sql_parser.py` Protocol (`parse(sql, dialect) -> AST`, `extract_table_deps(ast) -> set[str]`, `extract_column_lineage(ast, schema) -> dict[str, list[(table, col)]]`) + 5-10 smoke tests; full swap on-demand only per Composability Constitution.

---

## §8. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge)

- ❌ `sqlglot.lineage(...)` as a top-level call. **Reality**: `sqlglot.lineage` is a **module**; use `from sqlglot.lineage import lineage`. **The canonical AI failure mode** — log every catch to `ai_hallucinations.md`.
- ❌ `sqlglot.transpile(sql, …)` returning `str`. **Reality**: returns `list[str]` — AI drops the `[0]`.
- ❌ `parse_one(sql).find_columns()` / `.columns` / `.column_lineage()`. **Reality**: no such methods. Use `expr.find_all(exp.Column)`.
- ❌ `lineage(...).columns` / `.to_dict()`. **Reality**: returns `Node` or `dict[str, Node]`; walk via `Node.walk()`; use `Node.payload`.
- ❌ `from sqlglot import lineage` returns the **module**, not the function.
- ❌ `optimizer.optimize(sql, …)`. **Reality**: takes `exp.Expr`. `parse_one()` first.
- ❌ `sqlglot.errors.LineageError`. No such class — lineage raises `SqlglotError`.
- ❌ `Node.upstream`. Lineage is downstream-linked (`Node.downstream`); reconstruct upstream by walking from root.
- ❌ `parse_one(sql)` without `dialect=`. Works, but uses sqlglot's generic superset — accepts queries DuckDB rejects. **Always pass `dialect="duckdb"`.**
- ❌ Case-sensitivity assumptions: `lineage()` normalizes identifiers per dialect (L156-158); DuckDB is case-insensitive, other dialects aren't.
- ❌ Citing `github.com/tobymao/sqlglot/releases` — empty 2026-05-13. Use `/tags`.

### Real gotchas from docs + source inspection

- **`trim_selects=True` (lineage default) rewrites `Node.source`** to only the asked-about column — lossy. Capture original SQL **before** `lineage()` if emitters need `SQLJobFacet`; or pass `trim_selects=False`.
- **Window functions** (`OVER (PARTITION BY a ORDER BY b)`): lineage walks via `find_all_in_scope` (L327-350), so partition/order cols **are** captured. **Verify with a `SUM(x) OVER (PARTITION BY y)` fixture** at v0.5 — sloppy walkers miss `y`.
- **Recursive CTEs (`WITH RECURSIVE`)**: parsed as `exp.SetOperation`; `to_node()` walks `union_scopes` once (L282-294); `_cache` prevents infinite descent, but **anchor + recursive arm collapse to the same column name**, potentially merging distinct sources. Emit `NucleusLineagePartial` when detected.
- **Lateral joins (`LATERAL` / `UNNEST`)**: scope-chasing through laterals **not** explicitly exercised in lineage.py main path. `exp.Lateral` parses as a regular `FROM` expression but its row-binding semantics aren't modeled. **Risk: lineage under-reports inputs.** Build `tests/lineage/test_lateral.py` golden suite at v0.5; file upstream if broken.
- **`qualify` runs inside `lineage()` by default** (L137-142) and **mutates the AST**. Re-using an AST is unsafe unless `copy=True` (default — keep it).
- **Not a SQL validator.** Accepts trailing commas, MySQL `#` comments, etc. Successful parse ≠ DuckDB will execute. Schema correctness lives in `@nucleus.contract`.
- **`Schema` arg accepts both `dict[str, dict[str, str]]` and `sqlglot.schema.MappingSchema`** — type-checkers miss mis-shaped dicts; smoke-test one canonical fixture per release.
- **AST is mutable**: `transform()` / `replace()` / `set()` mutate in place unless `copy=True`.

---

## §9. Decision log

**Why SQLGlot, not the alternatives:** custom AST walker (~3-5k LOC) violates Constraint #4 + §11.6 — reject; ANTLR-generated grammar adds per-dialect maintenance tar pit — reject; SQLFluff has no in-box lineage and lacks the SQLMesh/dlt/Dagster/Superset/Ibis composability dividend — reject for parsing, revisit only if formatting surfaces (v0.7+); JSQLParser is Java (Constraint #1) — reject; DuckDB `EXPLAIN (FORMAT JSON)` captures execution-plan, not source-projection — use as v0.7 cost-planner cross-check, not lineage source.

**Why SQLGlot enters at v0.1, not later or earlier:**

- **v0.1 (PoC #2)**: rendered SQL → `parse_one()` → `find_all(exp.Table)` extracts `{{ ref() }}` upstreams (~50-100 LOC). Without it, users hand-write `deps=[…]` for every SQL asset — torpedoes the 30-min beachhead (§1.5).
- **v0.5**: column-level lineage moves from "rabbit hole" (arch §12.4) to table-stakes for SQL-heavy users; `lineage()` is the API.
- **v0.7+**: cost-aware planner (arch §7.5) consumes `optimize()`-normalized ASTs.
- **Never**: build a SQL parser, execution engine, or formatter beyond what sqlglot's `generator` ships.

**Pin philosophy**: hold 26.0.0 through v0.1; `26.0.0 → 26.8.x[c]` at v0.3 marimo landing; `26.8.x → 30.x` at v0.5 column-lineage launch (full ADR + golden test re-baseline). Integration ADRs (when authored): `docs/decisions/ADR-NNN-poc2-ctx-sql-jinja-resolver.md`, `docs/decisions/ADR-NNN-v05-column-lineage-sqlglot.md`.

---

## §10. Next reads when v0.5 column-lineage work starts

- [ ] **Re-fetch lineage.py at upgrade-target** — verify `Node` shape + `lineage()` signature unchanged. https://github.com/tobymao/sqlglot/blob/main/sqlglot/lineage.py.
- [ ] **OpenLineage `ColumnLineageDatasetFacet` schema** — cross-cite `docs/internal/research/openlineage.md`. Confirm `inputFields: [{namespace, name, field, transformations: [...]}]`.
- [ ] **Window fixture**: `SUM(x) OVER (PARTITION BY y ORDER BY z)` must yield `output ← {x, y, z}`.
- [ ] **Recursive CTE fixture**: `WITH RECURSIVE` with cycle; verify `_cache` prevents infinite walk; surface partial-lineage warning.
- [ ] **Lateral fixture**: `SELECT a.id, t.v FROM a, LATERAL UNNEST(a.xs) AS t(v)` — verify `t.v` traces back to `a.xs`. If broken: file upstream or vendor; fall back to asset-level.
- [ ] **TPC-H 22-query suite** under pin — confirm <10 ms parse, <50 ms full lineage per query.
- [ ] **Schema-shape contract** — solidify `dict[str, dict[str, str]]` for `lineage(schema=…)`; property test.
- [ ] **`on_node` hook contract** — design `Node.payload` keyspace; document in `engineering.md`.
- [ ] **Dialect coverage vs DuckDB EXPLAIN** — for 50 most-common patterns, verify sqlglot plan ≈ DuckDB plan.
- [ ] **AST primer** (mandatory, ~30 min): https://github.com/tobymao/sqlglot/blob/main/posts/ast_primer.md.
- [ ] **SQLMesh `sqlmesh/core/lineage.py`** — most production-tested consumer of `sqlglot.lineage.lineage()`.

---

*Last verified: 2026-05-13 against sqlglot 26.0.0 (pin) and 30.7.0 (latest). Re-verify before opening PoC #2, the marimo `26.0.0 → 26.8.x[c]` upgrade PR, or the v0.5 column-lineage ADR. Log any AI-fabricated sqlglot APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
