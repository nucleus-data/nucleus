# Swap Target: DuckDB → Apache DataFusion

**Tier**: 1 (engines, default SQL engine, per `nucleus_architecture_v4.1.md` §5.1, §9.2) · **Default**: `duckdb==1.1.3` (`pyproject.toml:42`) · **Swap target**: Apache DataFusion (Python bindings — candidate `datafusion>=43.0`; **NEEDS VERIFICATION** at trigger time per `AGENTS.md` §11.12) · **Status (2026-05-13)**: Interface documented + smoke tests in CI; full swap on-demand only per v4.1 §9.3.

## What we use DuckDB for

In v0.1 (post-PoC #1 promotion), DuckDB usage is deliberately narrow:

- **Exception-class registration**: `coordination/error_translation.py` lazy-imports `duckdb` to register handlers for the five exception types we translate to `NucleusError` subclasses (lines 324-330, lazy inside `_registry()` to avoid a hard import at module load).
- **No SQL execution wired in v0.1**: `engines/duckdb_engine.py` is not yet promoted; the `nucleus query` and `nucleus run` CLI commands stub on `NucleusInternalError` per the v0.1 skeleton.
- **Future SQL surface**: `coordination/sql_resolver.py` (PoC #2 promoted) will hand a rendered SQL string to the engine; `ctx.read(...)` will scan Iceberg via DuckDB once `engines/duckdb_engine.py` lands. See `docs/research/duckdb.md` §4 + §8.
- **Iceberg writes are NOT a DuckDB concern**: PyIceberg owns atomic commits per ADR-001 + Hard Constraint #5. DuckDB is read-side only.

If our wrap surface stays this narrow, the swap is mostly an exception-registry rewrite. As `engines/duckdb_engine.py` grows, this section grows with it; review on every promotion PR.

## API surface we depend on

Today (v0.1, exception registry only — `coordination/error_translation.py:324-330`):

| Symbol | Use site | DataFusion equivalent |
|---|---|---|
| `duckdb.BinderException` | `error_translation.py:326` | `datafusion.errors.SchemaError` (NEEDS VERIFICATION) |
| `duckdb.CatalogException` | `error_translation.py:327` | `datafusion.errors.PlanError` for object-not-found (NEEDS VERIFICATION) |
| `duckdb.ParserException` | `error_translation.py:328` | `datafusion.errors.ParserError` (NEEDS VERIFICATION) |
| `duckdb.OutOfMemoryException` | `error_translation.py:329` | `datafusion.errors.ResourcesExhausted` (NEEDS VERIFICATION) |
| `duckdb.TransactionException` | `error_translation.py:330` | DataFusion is not a transactional store — concurrent-write conflicts surface at the catalog instead |

Future (when `engines/duckdb_engine.py` lights up — `docs/research/duckdb.md` §5):

| Symbol | Wrap responsibility | DataFusion equivalent |
|---|---|---|
| `duckdb.connect(":memory:")` | engine connection | `datafusion.SessionContext()` |
| `conn.sql(query).arrow()` | lazy execution + Arrow exit | `ctx.sql(query).to_arrow_table()` |
| `conn.from_arrow(table)` | zero-copy in | `ctx.from_arrow(table)` |
| `conn.register("v", obj)` | register Arrow as view | `ctx.register_table("v", arrow_table)` |
| `iceberg_scan('metadata.json')` | Iceberg snapshot read | `datafusion-iceberg` (alpha; see Trigger events) |

## Swap target sketch

```python
# Pseudocode — engines/duckdb_engine.py refactored to engines/datafusion_engine.py
# Docs: https://datafusion.apache.org/python/  (NEEDS VERIFICATION on first wire-up)
from datafusion import SessionContext


class DataFusionEngine:
    def __init__(self) -> None:
        self._ctx = SessionContext()  # equivalent of duckdb.connect(":memory:")

    def execute(self, sql: str) -> "pyarrow.Table":
        # DuckDB: conn.sql(sql).arrow()
        return self._ctx.sql(sql).to_arrow_table()

    def from_arrow(self, view: str, t: "pyarrow.Table") -> None:
        # DuckDB: conn.register(view, t)
        self._ctx.register_table(view, t)

    def scan_iceberg(self, view: str, metadata_uri: str) -> None:
        # DuckDB: f"INSTALL iceberg; LOAD iceberg; CREATE VIEW {view} AS "
        #        f"SELECT * FROM iceberg_scan('{metadata_uri}')"
        # DataFusion: requires `datafusion-iceberg` Python wrapper
        # NEEDS VERIFICATION — alpha as of 2026-05; see Trigger events.
        raise NotImplementedError("datafusion-iceberg Python wrapper pending")
```

Caveats: SQL dialect drift (DataFusion is stricter ANSI than DuckDB); DuckDB-specific constructs (`STRUCT(...)`, array literals, `strftime`, `SET memory_limit / threads / timezone`) need a translation table on swap; the Iceberg-extension story is the largest unknown; DuckDB's `DuckDBPyRelation` lazy semantics + `register()` ergonomics may need helper code that DataFusion gives us for free.

## Smoke tests

Located at `tests/swap/test_duckdb_swap.py`. Verifies the **default (DuckDB) wrap behaves as documented** AND that **DataFusion is reachable as a swap target** via `importlib.util.find_spec` — without installing DataFusion in CI, per v4.1 §9.3 (full swap on-demand only).

- 3 live tests: `:memory:` connect, `SELECT 1` literal, Arrow round-trip
- 3 interface assertions: 5 exception classes present; future API names (`execute`, `sql`, `from_arrow`, `register`, `close`) exist on `DuckDBPyConnection`; `datafusion` discoverable via `find_spec`
- 2 skip-marked placeholders: full DataFusion smoke suite (built when trigger fires)

## Trigger events for full swap implementation

Per v4.1 §9.3, swap fires only on:

- DuckDB Foundation pivots license unfavorably (current: MIT — `docs/research/duckdb.md` §1)
- DataFusion's Iceberg story reaches stable parity with DuckDB's `iceberg_scan` (currently DuckDB covers Iceberg v1 + v2 read; v3 partial)
- TPC-H 10 GB or `:memory:` startup regresses >2× vs the pinned 1.1.3 baseline (PoC #4 budget)
- DuckDB drops Windows or macOS-arm64 wheels (PoC #4 cross-platform requirement)
- Community demand: ≥30% of telemetry requests DataFusion

Until one fires, we maintain interface + smoke tests only, never a full second implementation. That is "Composability Tax" per v4.1 §9.3 + the Anti-Over-Engineering directive in `.cursor/rules/nucleus.mdc`.

## References

- DuckDB Python API: https://duckdb.org/docs/stable/clients/python/overview
- DuckDB DBAPI / exceptions: https://duckdb.org/docs/stable/clients/python/dbapi
- DuckDB Iceberg extension: https://duckdb.org/docs/stable/extensions/iceberg
- DataFusion home: https://datafusion.apache.org/
- DataFusion Python: https://datafusion.apache.org/python/  (re-verify on PyPI at trigger time per `AGENTS.md` §11.12)
- `datafusion-iceberg`: https://github.com/apache/datafusion-iceberg
- Architecture: `nucleus_architecture_v4.1.md` §5.1 (Engines), §9.2 (composability tier table), §9.3 (swap discipline)
- Research notes: `docs/research/duckdb.md`
