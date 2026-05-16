# REVIEW_NOTES — PoC #1 Error Translation, wording critique

**Status**: DRAFT — Risky-tier per `AGENTS.md` §11.3 (human writes, AI suggests). Promotion gated on §11.7 (no library classnames in user strings; `error.cause` preserved). Suggestions, not authorship.

**Scope**: 14 new handlers in `translator.py:109–247` + `_iter_causes` refactor at `:39–71`. Baseline 3 branches in `_dagster_step_handler` shipped earlier; not re-litigated.

**Uniform cross-checks across all 14**: vocab per `AGENTS.md` §7 (asset/materialization/snapshot/contract/catalog; avoid *table/job/task/version* as primitives — v4.1 §6.4 example says *"Asset 'sales.fct_orders'..."*, never *"Table..."*); cause preserved (every handler returns `cause=exc`; `NucleusError.__init__` at `errors.py:96` sets `__cause__`); no `dagster.*`/`duckdb.*`/`polars.*`/`pyiceberg.*` classname leak (only `str(exc)` flows through `{msg}`).

---

## 9 handlers — looks good as-shipped (no rewrite)

Verbatim wording matches `errors.py` + `docs/internal/research/<lib>.md`. All preserve `cause`, leak-check clean, approved vocab.

| # | Handler (`:line`) | Catches → Maps to | Why it works |
|---|---|---|---|
| H1 | `_polars_schema_handler` (`:109`) | `polars.SchemaError` → `NucleusSchemaError` | `asset transform` vocab; `dtypes` standard. |
| H2 | `_polars_column_not_found_handler` (`:119`) | `polars.ColumnNotFoundError` → `NucleusSchemaError` | `upstream asset` vocab; concrete action. |
| H5 | `_duckdb_parser_handler` (`:149`) | `duckdb.ParserException` → `NucleusSQLSyntaxError` | *"dialect is not Postgres"* = #1 `duckdb.md` §7 gotcha. |
| H6 | `_pyiceberg_no_such_table_handler` (`:159`) | `pyiceberg.NoSuchTableError` → `NucleusAssetNotMaterialized` | `materialized` matches primitive; `{msg}` "Table 'X'..." is PyIceberg content, passes leak check. |
| H8 | `_file_not_found_handler` (`:179`) | `FileNotFoundError` → `NucleusIOError` | Two-clause hint covers local + source-glob. |
| H10 | `_duckdb_transaction_handler` (`:199`) | `duckdb.TransactionException` → `NucleusCommitConflictError` | *"two materializations target the same asset"* = right vocab. |
| H11 | `_pyiceberg_commit_state_unknown_handler` (`:209`) | `pyiceberg.CommitStateUnknownException` → `NucleusCommitUnknownError` | Safety-critical; honors `pyiceberg.md` §6 *"DO NOT retry blindly"*. |
| H12 | `_pyiceberg_validation_handler` (`:219`) | `pyiceberg.ValidationError` → `NucleusSchemaEvolutionError` | Naming **Iceberg** is intentional spec-disclosure. |
| H13 | `_permission_error_handler` (`:229`) | `PermissionError` → `NucleusPermissionError` | `catalog / warehouse path` vocab; actionable. |

---

## 5 handlers needing founder review

### H3 — `_duckdb_binder_handler` (`:129`)

`duckdb.BinderException` → `NucleusSchemaError`.
- msg: `"SQL binding failed: {msg}"` · hint: `"Check column and table names referenced in the SQL against the upstream asset's schema."`
- Critique: *"binding"* = SQL-planner internal jargon. *"column and table names"* mixes vocab — ctx exposes assets, not tables.
- Rewrite A: msg → `"Could not resolve a column or asset reference: {msg}"`; hint unchanged.
- Rewrite B: keep msg; hint → `"Check column and asset names referenced in the SQL against the upstream asset's schema."`

### H4 — `_duckdb_catalog_handler` (`:139`)

`duckdb.CatalogException` → `NucleusAssetNotFound`.
- msg: `"SQL referenced an unknown object: {msg}"` · hint: ``"Verify the asset / table / view name is registered. List available assets with `nucleus list`."``
- Critique: *"unknown object"* vague. *"asset / table / view name"* mixes our primitive with implementation terms. ``nucleus list`` — verify against `nucleus_cli_spec.md`; may be `nucleus assets list`.
- Rewrite A: msg → `"SQL referenced an unknown asset: {msg}"`; hint → ``"Verify the asset name is registered. List available assets with `nucleus list`."``

### H7 — `_pyiceberg_commit_failed_handler` (`:169`)

`pyiceberg.CommitFailedException` → `NucleusCommitConflictError`.
- msg: `"Concurrent write conflict on the asset's table: {msg}"` · hint: `"Another writer committed to the same table. Retry the run; if it persists, check for overlapping schedules."`
- Critique: *"the asset's table"* + *"the same table"* repeats the asset/table tension. v4.1 §6.4 example drops *"table"* in our framing.
- Rewrite A: msg → `"Concurrent write conflict on this asset: {msg}"`; hint → `"Another writer committed first. Retry the run; if it persists, check for overlapping schedules on the same asset."`

### H9 — `_duckdb_out_of_memory_handler` (`:189`)

`duckdb.OutOfMemoryException` → `NucleusResourceError`.
- msg: `"Query exceeded the memory budget: {msg}"` · hint: ``"Reduce the working set (filter / project earlier) or raise the engine `memory_limit`."``
- Critique: *"project"* = SQL jargon (column projection). ``engine `memory_limit` `` reveals the engine — not a classname leak but worth noting.
- Rewrite A: hint → `"Reduce the working set (filter rows or select fewer columns earlier) or raise the engine memory limit."`

### H14 — `_timeout_error_handler` (`:239`) ⚠️ HIGHEST PRIORITY

builtin `TimeoutError` → `NucleusSourceConnectionError`.
- msg: `"Connection to a data source timed out: {msg}"` · hint: `"Check network reachability and credentials; raise the source timeout if the source is genuinely slow."`
- **Only handler where the *type→category mapping* is contested, not just the wording.** Builtin `TimeoutError` can fire from non-source paths (asset compute, query budget, lock acquisition); handler's docstring (`:240–241`) acknowledges this and defers to telemetry. `NucleusTimeoutError` already exists at `errors.py:355` but no handler routes there. Risk: a future query-budget timeout surfaces as a misleading *"connection to a data source"* message.
- Rewrite A (preferred until telemetry): keep routing, soften msg → `"Operation timed out: {msg}"`; hint → `"If a source is involved, check network reachability and credentials. Otherwise raise the timeout for this run."`
- Rewrite B: ship as-is + file follow-up issue **before promotion** for the `TimeoutError` → `NucleusTimeoutError` split.

---

## `_iter_causes` refactor critique (`:39–71`)

**Contract**: yields `exc` first, walks `__cause__` outer→inner; falls back to `__context__` when `__cause__ is None` and `__suppress_context__` is `False`; depth-bounded by `_MAX_CAUSE_DEPTH = 8`; cycle-safe via `seen: set[int]` of `id(cur)`. Used by `_unwrap_cause` (back-compat) and by `translate()` for innermost-first matching. Cause-beats-context-unless-suppressed matches CPython's `traceback.TracebackException`. The `id()` guard is correct because exception identity is stable for the call's lifetime.

**Edge cases not yet covered** (add pre-promotion or open follow-up):

1. **Suppressed context** (`raise X from None` → `__suppress_context__=True`): walk should stop at `X`.
2. **Cycle**: `e1.__cause__ is e1` or `e1 ↔ e2`. The `seen` guard handles it; add a test so a refactor can't silently regress.
3. **Depth boundary**: chain of length 9+ — yields exactly 8 and stops. Parametrize at 7 / 8 / 9.
4. **Both `__cause__` and `__context__` set**: code path picks `__cause__`; no precedence test.

**Anti-patterns to watch**: registry is dict-insertion order, so **subclass-before-superclass matters**. Currently safe (no `OSError` registered above `FileNotFoundError`/`PermissionError`/`TimeoutError`), but a future `OSError` registration would shadow all three — add a docstring note in `_registry()` + a CI smoke test asserting most-specific match wins. `_MAX_CAUSE_DEPTH = 8` is a magic number with no escape hatch; acceptable for v0.1, revisit on real chain >8.

---

## Approver Checklist (founder ticks before signing)

- [ ] Per-handler rewrites accepted/rejected: **H3, H4, H7, H9, H14** (other 9 are "Looks good").
- [ ] H14 routing decision recorded in PROMOTION_CHECKLIST §2 (option A or B).
- [ ] All referenced `NucleusError` subclasses exist in `errors.py` `__all__`. *(Audited: all 12 + `NucleusInternalError` present.)*
- [ ] `_iter_causes` contract acceptable; 4 missing-test edge cases added pre-promotion or filed.
- [ ] `# NEEDS VERIFICATION` markers (`translator.py:251–253, 289–292`) resolved on first PoC run **or** tracked by issue.
- [ ] Architecture cite (`v4.1 §6.4`) preserved in the promoted file's module docstring.
- [ ] CLI commands in fix_hints (`nucleus list`, `nucleus run <asset>`, `nucleus catalog inspect`) verified against `nucleus_cli_spec.md`.
