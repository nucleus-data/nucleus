# Research: Polars

> **Pinned**: `polars==1.18.0` (released 2024-12-24)
> **Verified**: 2026-05-12 against [PyPI](https://pypi.org/project/polars/1.18.0/) and [docs.pola.rs](https://docs.pola.rs/)
> **Used in**: `src/nucleus/engines/polars_engine.py` (L1, Tier 0+). Default DataFrame engine.
> **Repo**: https://github.com/pola-rs/polars  •  **License**: MIT

This file is the official-docs anchor for Polars per [AGENTS.md Hard Constraint #10](../../AGENTS.md). Audience: junior data engineer or AI agent integrating against Polars. Read before touching any Polars-wrapping code.

---

## §1. At a glance

- **License**: MIT
- **Author / maintainer**: Ritchie Vink + Polars team (Python bindings in `py-polars/`)
- **What it is**: Rust-implemented columnar query engine with a Python DataFrame surface, built on Apache Arrow Columnar Format. **NOT pandas**: lazy by default, Arrow-first, strict typing, no Python-object columns.
- **Why we wrap it**: pure Rust (Constraint #1: no JVM); zero-copy Arrow interop with Physics (L0) and DuckDB; lazy execution = free query planner.

---

## §2. Version verification (PyPI, 2026-05-12)

Verified at `https://pypi.org/pypi/polars/1.18.0/json`:

- `polars==1.18.0` is **real**, not yanked. Uploaded 2024-12-24 by `c-peters` / `ritchie46`.
- Python compatibility per 1.18.0 wheel classifiers: 3.9, 3.10, 3.11, 3.12. ✓ Matches our `requires-python = ">=3.11,<3.13"`.
- PyArrow extra requires `pyarrow>=7.0.0` — our `pyarrow==18.1.0` pin sits comfortably above the floor.
- PyIceberg extra requires `pyiceberg>=0.5.0` — our `pyiceberg==0.8.1` pin sits above the floor.
- Wheels published: macOS x86_64 / arm64, manylinux x86_64 / aarch64, win_amd64, win_arm64. Universal — no install blocker on any beachhead platform.
- **Latest stable as of 2026-05-12: ≥ 1.40.1**. The `docs.pola.rs/api/python/stable` source link resolves to `py-1.40.1`. Our 1.18.0 is ~16 months / ~22 minor releases behind. An upgrade ADR will eventually be needed (per Constraint #11 — major / stale-version moves are not casual).

---

## §3. Why Nucleus uses Polars

- **L1 Engines** — default DataFrame engine. Co-resides with DuckDB (SQL engine) at the same layer.
- **v4.1 §6.4** — every Polars exception is translated at `coordination/error_translation.py` (see §6).
- **Zero-copy interop** — Polars ↔ Arrow ↔ DuckDB ↔ PyIceberg share the Arrow memory model. No pandas hops (`engineering.md` §11.4).
- **Lazy execution** — `LazyFrame` is planned and optimized before execution. Compose lazily, collect once.

**Swap target**: Apache DataFusion Python DataFrame API. Interface at `nucleus.engines.Engine` (Protocol). Smoke tests only in v0.1 per Constraint #9 — full adapter built on-demand.

**Explicitly NOT chosen**: pandas. Single-threaded, eager-only, weak typing, no Arrow-native, no lazy planner. Pandas appears only as a user **import**; never an engine.

---

## §4. Core concepts (memorize these)

| Concept | Type | When to use |
|---|---|---|
| **DataFrame** | Eager, materialized | Small frames, REPL, final hop before write |
| **LazyFrame** | Lazy, planned | **Default** for asset transforms |
| **Expression** (`pl.Expr`) | Composable column expression | Inside `select` / `filter` / `with_columns` / `group_by().agg` |
| **`scan_*`** | Lazy reader (`scan_parquet`, `scan_iceberg`, `scan_csv`, `scan_ndjson`) | **Default ingress** — defers I/O until `collect` |
| **`read_*`** | Eager reader | Small frames, final hop only |
| **`collect()`** | Materialize a LazyFrame | One terminal call per asset |
| **`collect(streaming=True)`** | Streaming materialization | Larger-than-RAM datasets (see §7.6) |
| **`sink_*`** | Stream to disk (`sink_parquet`, `sink_csv`, `sink_ipc`, `sink_ndjson`) | Bypass memory on write |
| **Arrow interop** | `from_arrow`, `to_arrow` | Zero-copy bridge to/from L0 and DuckDB |

**Rule of thumb in `polars_engine.py`**: read with `scan_*`, transform on `LazyFrame`, terminate with `collect()` or `sink_*`. Never `read_*` for a frame the user might produce.

---

## §5. Critical API surface

Methods we wrap or expose in `polars_engine.py`. URLs point to `docs.pola.rs/api/python/stable`; for version-exact behavior, swap `stable` for `version/1.18`.

```python
import polars as pl
# Docs: https://docs.pola.rs/api/python/stable/reference/

# Construction
pl.DataFrame(data, schema=...)
pl.LazyFrame(data, schema=...)
pl.from_arrow(arrow_table_or_recordbatch)   # zero-copy

# Lazy readers (preferred)
pl.scan_parquet(source, ...)
pl.scan_iceberg(source, *, snapshot_id=None, storage_options=None)
# Docs: https://docs.pola.rs/api/python/stable/reference/api/polars.scan_iceberg.html
pl.scan_csv(source, ...)
pl.scan_ndjson(source, ...)

# Eager readers (small only)
pl.read_parquet(source, ...)

# Frame ops (work on DataFrame and LazyFrame)
df.select(*exprs)
df.filter(expr)
df.with_columns(*exprs)
df.group_by(*by).agg(*exprs)
df.join(other, on=..., how="inner" | "left" | "outer" | "anti" | "semi" | "cross")
df.sort(*by, descending=False, nulls_last=False)

# Materialization
lf.collect()                  # default engine
lf.collect(streaming=True)    # streaming engine; see §7.6
lf.sink_parquet(path)         # never materializes in memory
lf.explain(streaming=False)   # show optimized plan

# Arrow exit (zero-copy → PyIceberg writer)
df.to_arrow()                 # returns pyarrow.Table

# Expressions
pl.col("name"); pl.lit(value); pl.when(cond).then(a).otherwise(b)
pl.struct([...]); expr.over(partition_by)   # window; see §7.7
```

`scan_iceberg` is verified to exist. Our 1.18.0 supports the core `(source, snapshot_id, storage_options)` signature. Newer stable-docs params (`reader_override`, `use_metadata_statistics`, `fast_deletion_count`, `use_pyiceberg_filter`) post-date 1.18.0. **NEEDS VERIFICATION** on first wire-up: pin the call against the 1.18.x docs build, not stable.

---

## §6. Exception types we translate (PoC #1)

Per `docs/architecture/sequence_error_translation.md` §4.3. Source classes live at `polars.exceptions.*` (re-exported at the `polars` top level in 1.x).

| Polars exception | Raised when | Nucleus translation |
|---|---|---|
| `polars.SchemaError` | Schema mismatch (wrong-typed column in expression) | `NucleusSchemaError` |
| `polars.ColumnNotFoundError` | Expression refers to a missing column | `NucleusSchemaError` |
| `polars.ComputeError` | Arithmetic / cast / kernel failure in an expression | `NucleusEngineError` |
| `polars.ShapeError` | Frame shapes don't align (join keys missing, bad broadcast) | `NucleusSchemaError` |
| `polars.NoDataError` | Source produced zero rows where rows required | `NucleusEmptyAssetError` |

Each registers a handler in `coordination/error_translation.py`. PoC #1 fixtures construct **real** instances — raised by real Polars calls, no mocks (`sequence_error_translation.md` §7).

Canonical reference: `https://docs.pola.rs/api/python/stable/reference/exceptions.html` (verify exact path against pinned version on first integration).

---

## §7. Known gotchas / pitfalls

These have bitten real teams. Read once, remember forever.

### §7.1 `Utf8` → `String` rename (`type_mapping.md` §5.1)
Polars 1.x renamed `Utf8` → `String`. **Use `pl.String` only**. Any `pl.Utf8` is a 0.x carryover — rejected in PR review.

### §7.2 `Categorical` is never persisted (`type_mapping.md` §5.2)
`pl.Categorical` is a runtime optimization, not a storage type. Iceberg has no categorical. We cast to `String` on materialization.

### §7.3 `pl.Object` is forbidden in asset returns (`type_mapping.md` §5.3)
`pl.Object` allows arbitrary Python objects — uncoercible to Arrow / Iceberg. `ctx.asset` raises `NucleusSchemaError` if detected.

### §7.4 `List(T)` vs `Array(T, n)` (`type_mapping.md` §5.4)
Polars distinguishes variable-length `List(T)` from fixed-length `Array(T, n)`. **Iceberg only has `list<T>`** — always use `List(T)`. Fixed-length arrays become variable-length on write.

### §7.5 Premature `.collect()`
`.collect()` mid-pipeline forces materialization and disables downstream optimization. Pattern: collect **exactly once**, at the AMA hand-off boundary.

### §7.6 The streaming engine is incomplete
`collect(streaming=True)` is fast and memory-bounded, but **not all operations are supported**. Unsupported ops silently fall back or fail. Always run `lf.explain(streaming=True)` first to confirm the plan, then benchmark before relying on it for >RAM datasets. Streaming coverage churns per minor release.

### §7.7 Window functions: `.over(...)` ≠ SQL window
`expr.over(partition_by)` is Polars' window syntax. It does **not** match SQL `OVER (PARTITION BY … ORDER BY …)` semantics in all cases — Polars chooses a strategy (`group_to_rows`, `explode`, `join`) per call. When porting from SQL, regression-check against DuckDB. `mapping_strategy` is your friend.

### §7.8 NaN ≠ NULL
Float NaN and NULL are **distinct** in Polars by design. Preserved through Arrow / Iceberg / DuckDB, but comparison semantics differ across systems (`type_mapping.md` §7.3). Asset code depending on null / NaN ordering needs explicit `nulls_last=`.

### §7.9 Plan inspection is cheap
`.explain()` and `.explain(streaming=True)` print the optimized plan. Use them when an asset is unexpectedly slow, **before** reaching for `pyspy`. Almost always reveals the issue.

---

## §8. Interaction with other Nucleus components

| Boundary | Mechanism | Tier |
|---|---|---|
| ↔ PyArrow (L0 Physics) | `pl.from_arrow(t)` / `df.to_arrow()` — **zero-copy** | 0 |
| ↔ DuckDB (L1 SQL engine) | DuckDB's `register("name", df)` accepts a Polars frame via the Arrow C Stream interface — zero-copy | 1 |
| → PyIceberg writer (L0 Physics) | `df.to_arrow()` → PyIceberg `table.append(arrow_table)` | 0 |
| ← PyIceberg reader (L0 Physics) | `pl.scan_iceberg(source, ...)` → `LazyFrame` | 0 |
| ↔ Dagster (L2 Coordination) | Polars frames never escape `coordination/`. Errors translated by `error_translation.py` **before** the AMA → CTX boundary | 2 |
| ↔ `ctx` SDK (L4) | Users may return a Polars frame from a `@nucleus.asset` function. We coerce to Arrow before persisting | 4 |

Critical: per `engineering.md` §11.4, we never materialize to pandas as an interop hop. Arrow is the pivot (`type_mapping.md` §2).

---

## §9. Upgrade considerations

Per Constraint #11, upgrading Polars is a single-component PR with smoke tests + rollback. Things to watch:

- **Expression API**: 1.x stable for `pl.col`, `pl.lit`, expression chaining. 2.x (if/when) **may** rework dispatch — full ADR required.
- **Streaming engine churn**: each minor adds / removes ops from the streaming engine. Re-run benchmarks on every upgrade; `collect(streaming=True)` is the most volatile surface.
- **Scan readers evolve fast**: `scan_iceberg`, `scan_parquet`, `scan_delta` gain parameters often (stable docs already has params not in 1.18.0). Diff the signature on every upgrade.
- **PyArrow envelope**: Polars depends on Arrow Stream / Capsule. Coordinate Polars + PyArrow upgrades; upgrade together when release notes mention Arrow-side changes.
- **Python floor**: Polars periodically drops old Python minors. Confirm target version still supports `>=3.11,<3.13`.
- **Releases ship weekly**. We do **not** chase head — quarterly review per `compatibility.md`. Changelog: https://github.com/pola-rs/polars/releases.

Rollback command (record in the upgrade PR description):

```
pip install polars==1.18.0
```

---

## §10. Useful links

Verified against `docs.pola.rs` and PyPI on 2026-05-12. Substitute `version/1.18` for `stable` in URLs when chasing version-exact behavior.

- Project home: https://www.pola.rs/
- GitHub: https://github.com/pola-rs/polars
- PyPI: https://pypi.org/project/polars/
- Python API reference: https://docs.pola.rs/api/python/stable/reference/index.html
- Data types: https://docs.pola.rs/api/python/stable/reference/datatypes.html
- LazyFrame reference: https://docs.pola.rs/api/python/stable/reference/lazyframe/index.html
- Expressions reference: https://docs.pola.rs/api/python/stable/reference/expressions/index.html
- Exceptions reference: https://docs.pola.rs/api/python/stable/reference/exceptions.html
- `scan_iceberg` (verified): https://docs.pola.rs/api/python/stable/reference/api/polars.scan_iceberg.html
- User guide (lazy / eager / streaming / expressions): https://docs.pola.rs/user-guide/
- Release notes / changelog: https://github.com/pola-rs/polars/releases

---

*Last verified against `polars==1.18.0` on 2026-05-12. When this doc disagrees with code, update the code. When this doc disagrees with the upstream pinned API, update this doc.*
