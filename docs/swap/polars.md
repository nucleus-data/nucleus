# Swap Target: Polars → Apache DataFusion DataFrame API

**Tier**: 1 (engines, default DataFrame engine, per `docs/specs/nucleus_architecture_v4.1.md` §5.1, §9.2) · **Default**: `polars==1.18.0` (`pyproject.toml:43`) · **Swap target (v0.1)**: Apache DataFusion DataFrame API (Python — candidate `datafusion>=43.0`; co-versioned with DuckDB → DataFusion in `docs/swap/duckdb.md`) · **Swap target (v0.5+ secondary)**: Daft (multimodal-only — out of scope for this doc; see `docs/internal/research/daft.md`) · **Status (2026-05-13)**: Interface documented + smoke tests in CI; full swap on-demand only per v4.1 §9.3.

## What we use Polars for

In v0.1 (post-PoC #1 promotion), Polars usage is narrow:

- **Exception-class registration**: `coordination/error_translation.py` lazy-imports `polars.exceptions` to register handlers for `SchemaError` and `ColumnNotFoundError` (lines 311-319). Three deferred classes (`NoDataError`, `ComputeError`, `ShapeError`) are documented as "next iteration" in the same module's tail comment.
- **User-facing return type for assets**: `templates/v01/assets/example.py:13` returns `pl.DataFrame`; the AMA's `IcebergIOManager` (pending promotion) will `df.to_arrow()` before handing to PyIceberg (zero-copy via Arrow C-data — `docs/internal/research/polars.md` §8).
- **Decorator docstrings**: `sdk/decorators.py` references `pl.col(...)` in `@nucleus.asset` and `@nucleus.check` examples; the SDK never imports `polars` itself.
- **No engine-side Polars execution wired in v0.1**: `engines/polars_engine.py` is not yet promoted. `ctx.read(...)` returning a `LazyFrame` lights up alongside the engine.

If our wrap surface stays this narrow, the swap is mostly an exception-registry rewrite + asset-return-type translation. As `engines/polars_engine.py` grows, this section grows with it; review on every promotion PR.

## API surface we depend on

Today (v0.1, exception registry + return-type only — `coordination/error_translation.py:314-317`):

| Symbol | Use site | DataFusion equivalent |
|---|---|---|
| `polars.exceptions.SchemaError` | `error_translation.py:316` | `datafusion.errors.SchemaError` (NEEDS VERIFICATION — single decomposed class or umbrella?) |
| `polars.exceptions.ColumnNotFoundError` | `error_translation.py:317` | likely surfaces as `SchemaError` in DataFusion (NEEDS VERIFICATION) |
| `pl.DataFrame` (asset return) | `templates/v01/assets/example.py:13` | DataFusion has no eager DataFrame primitive; users return `pyarrow.Table` instead (breaks user code) |
| `pl.col(...)` (in docstrings) | `sdk/decorators.py:304, 385` | `datafusion.col(...)` (NEEDS VERIFICATION) |

Future (when `engines/polars_engine.py` lights up — `docs/internal/research/polars.md` §5):

| Symbol | Wrap responsibility | DataFusion equivalent |
|---|---|---|
| `pl.scan_iceberg(source, ...)` | lazy Iceberg read | `datafusion-iceberg` Python surface (NEEDS VERIFICATION — Python-callable or SQL-only?) |
| `pl.scan_parquet(source)` | lazy Parquet read | `ctx.read_parquet(source)` |
| `pl.from_arrow(table)` | zero-copy in | `ctx.from_arrow(table)` |
| `LazyFrame.collect() -> pl.DataFrame` | terminal materialization | `df.to_arrow_table()` (returns `pyarrow.Table`, not a DF type) |
| `df.to_arrow()` | zero-copy out for IcebergIOManager | already `pyarrow.Table` natively |
| `LazyFrame.sink_parquet(path)` | streaming write | `ctx.write_parquet(...)` (NEEDS VERIFICATION) |

## Swap target sketch

```python
# Pseudocode — engines/polars_engine.py refactored to engines/datafusion_df_engine.py
# Docs: https://datafusion.apache.org/python/  (NEEDS VERIFICATION on first wire-up)
from datafusion import SessionContext


class DataFusionDataFrameEngine:
    def __init__(self) -> None:
        self._ctx = SessionContext()

    def from_arrow(self, t: "pyarrow.Table") -> "datafusion.DataFrame":
        # Polars: pl.from_arrow(t)
        return self._ctx.from_arrow(t)

    def scan_parquet(self, source: str) -> "datafusion.DataFrame":
        # Polars: pl.scan_parquet(source)
        return self._ctx.read_parquet(source)

    def scan_iceberg(self, source: str) -> "datafusion.DataFrame":
        # Polars: pl.scan_iceberg(source)
        # DataFusion: needs datafusion-iceberg Python wrapper
        # NEEDS VERIFICATION — alpha as of 2026-05.
        raise NotImplementedError("datafusion-iceberg Python wrapper pending")

    def collect_to_arrow(self, df: "datafusion.DataFrame") -> "pyarrow.Table":
        # Polars: lf.collect().to_arrow()
        return df.to_arrow_table()
```

Caveats: Polars's expression API (`.over()` window strategies, `pl.struct`, `.list.eval`, `.str.json_path_match`) is wider than DataFusion's Python DF facade — many transforms live in DataFusion SQL only, so user `@nucleus.asset` bodies that chain Polars-specific expressions break and need rewrites or a SQL fallback. Type system: `pl.Categorical` (runtime-only — `docs/internal/research/polars.md` §7.2) and `pl.List(T)` vs `pl.Array(T,n)` distinctions don't exist in DataFusion (it works at PyArrow level); user code dropping `Categorical` is required. Streaming: `lf.collect(streaming=True)` is incomplete-but-useful in Polars (§7.6); DataFusion streams natively with different trigger semantics. NaN ≠ NULL is preserved by both via Arrow.

## Smoke tests

Located at `tests/swap/test_polars_swap.py`. Verifies the **default (Polars) wrap behaves as documented** AND that **DataFusion is reachable as a swap target** via `importlib.util.find_spec` — without installing DataFusion in CI, per v4.1 §9.3 (full swap on-demand only).

- 3 live tests: `pl.DataFrame` constructs + `to_arrow()` round-trip; `pl.from_arrow` zero-copy; `pl.col("x") > 0` lazy filter
- 3 interface assertions: `polars.exceptions.SchemaError` + `ColumnNotFoundError` present; `pl.DataFrame.to_arrow` and `pl.LazyFrame.collect` callable; `datafusion` discoverable via `find_spec`
- 2 skip-marked placeholders: full DataFusion-DF smoke suite (built when trigger fires)

## Trigger events for full swap implementation

Per v4.1 §9.3, swap fires only on:

- Pola.rs abandons OSS `main` >12 months OR pivots license (current: MIT — `docs/internal/research/polars.md` §1)
- v4.1 §11.2 "100M-row aggregation <2s on laptop" regresses >2× on a 1.18.0+ minor
- `pl.from_arrow()` zero-copy guarantee breaks (Arrow C-data interop is the substrate — `docs/internal/research/polars.md` §8)
- Polars adds JVM dep (Hard Constraint #1) or drops Windows / macOS-arm64 wheels
- Community demand: ≥30% of telemetry requests DataFusion DF (likely co-fires with DuckDB → DataFusion)

The biggest open question if a trigger fires is **exception decomposition** — whether DataFusion's Python errors arrive as distinct classes (translatable 1:1 to Polars's `SchemaError` / `ComputeError` / `ColumnNotFoundError`) or collapse into one `DataFusionError`. Translator design diverges sharply on the answer; that's the first thing the swap PR re-verifies.

Until one fires, we maintain interface + smoke tests only, never a full second implementation. That is "Composability Tax" per v4.1 §9.3 + the Anti-Over-Engineering directive in `.cursor/rules/nucleus.mdc`.

## References

- Polars Python API: https://docs.pola.rs/api/python/stable/reference/index.html
- Polars exceptions: https://docs.pola.rs/api/python/stable/reference/exceptions.html
- Polars `scan_iceberg`: https://docs.pola.rs/api/python/stable/reference/api/polars.scan_iceberg.html
- Polars LazyFrame: https://docs.pola.rs/api/python/stable/reference/lazyframe/index.html
- DataFusion home: https://datafusion.apache.org/
- DataFusion Python: https://datafusion.apache.org/python/  (re-verify on PyPI at trigger time per `AGENTS.md` §11.12)
- `datafusion-iceberg`: https://github.com/apache/datafusion-iceberg
- Architecture: `docs/specs/nucleus_architecture_v4.1.md` §5.1 (Engines), §9.2 (composability tier table), §9.3 (swap discipline)
- Research notes: `docs/internal/research/polars.md` · `docs/internal/research/daft.md` (v0.5+ secondary swap target)
- Related: `docs/swap/duckdb.md` (natural co-swap if both DuckDB and Polars retire together)
