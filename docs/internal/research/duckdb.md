# Research: DuckDB

> **Pinned**: 1.1.3  •  **Verified**: 2026-05-12  •  **Docs**: https://duckdb.org/docs/stable/clients/python/overview
> **Used in**: `src/nucleus/engines/duckdb_engine.py` (Tier 0+). Default SQL engine.
> **Companion**: [`docs/architecture/sequence_error_translation.md`](../architecture/sequence_error_translation.md) §4.2, [`docs/patterns/type_mapping.md`](../patterns/type_mapping.md) §6.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before writing PoC #1 or any Tier 0 Heartbeat code.

---

## §1. At a glance

- **License**: MIT  •  **Maintainer**: DuckDB Foundation (Mark Raasveldt, Hannes Mühleisen et al., originated at CWI Amsterdam)  •  **GitHub**: https://github.com/duckdb/duckdb
- **Position**: L1 Engines — default SQL engine. Wrapped behind `ctx.sql`. Users never `import duckdb`.

**What it is**: An **embedded, in-process, columnar OLAP SQL engine** — "SQLite for analytics". Single C++ library; no daemon, no JVM, no network hop. Reads Parquet/CSV/JSON/Arrow/(via extension) Iceberg natively. PyPI wheels for Linux/macOS/Windows × Python 3.7–3.13.

---

## §2. Version verification

Verified via `https://pypi.org/pypi/duckdb/1.1.3/json` + `https://pypi.org/pypi/duckdb/json` (latest).

| Check | Result |
|---|---|
| 1.1.3 a real release? | **YES** — wheels + sdist, uploaded 2024-11-04T14:01:05Z |
| `requires_python` (1.1.3) | `>=3.7.0` — compatible with our `>=3.11,<3.13` pin |
| Yanked? | No |
| Vulnerabilities (PyPI) | None listed |
| `requires_dist` (1.1.3) | `null` — wheel is self-contained C++; PyArrow / Polars are optional integrations |
| Windows wheel for cp311/cp312 | Present (`duckdb-1.1.3-cp31{1,2}-cp31{1,2}-win_amd64.whl`) |
| Latest stable as of today | **1.5.2** (~4 minor releases ahead). Informational; we stabilize on 1.1.3 pre-Heartbeat. |

**PyArrow compatibility**: zero-copy via the Arrow C-data interface; no PyArrow version is required by the wheel. Our `pyarrow==18.1.0` pin works with 1.1.3.

**Repo split**: 1.1.3-era Python bindings live in `duckdb/duckdb` under `tools/pythonpkg/`; from ~1.4.x they moved to `duckdb/duckdb-python`. Pin docs against 1.1.3 sources.

---

## §3. Why Nucleus uses DuckDB

- **Layer / role**: L1 Engines — default SQL engine. Hidden behind `ctx.sql` (v4.1 §6.4); no `duckdb` import, type, exception, or stacktrace crosses `engines/` → `ctx/`.
- **Provides**: SQL execution, Parquet/CSV/JSON readers, Iceberg read via extension, vectorized columnar execution, larger-than-memory queries (spill-to-disk), Arrow zero-copy I/O.
- **Why DuckDB wins**: in-process (no JVM, no daemon — Constraint #1), MIT, Arrow-native, 1.x storage-format-stable, monthly releases, mature Windows wheel. Alternatives rejected: Postgres (heavy daemon, row-major), SQLite (row-major + weak analytics SQL), Polars-only (no full SQL), bespoke (Constraint #4).
- **Swap target**: Apache DataFusion. Per Constraint #9 we keep an `Engine` Protocol (`engineering.md` §7.2) + 5–10 smoke tests in CI; full DataFusion adapter on-demand only.

---

## §4. Core concepts we depend on

Paths below are under `https://duckdb.org/docs/stable/`.

- **`DuckDBPyConnection`** — Entry point; cheap to construct. Owns DB handle + session state (settings, transactions, registered views). → `/clients/python/overview`
- **In-memory vs file-backed** — `connect(":memory:")` ephemeral; `connect("warehouse.duckdb")` opens/creates single-file DB. **v0.1 mode = `:memory:`**; persistence is Iceberg, not the DuckDB file.
- **`DuckDBPyRelation`** — Lazy relation from `conn.sql(...)` / `conn.from_arrow(...)`. Materializes only on `.arrow()` / `.pl()` / `.fetchall()`. Useful for the `ctx.sql` Jinja resolver. → `/clients/python/relational_api`
- **Native readers** — `read_parquet`, `read_csv`, `read_json` as SQL functions. Globs + S3 URIs need the `httpfs` extension.
- **Iceberg extension** — `INSTALL iceberg; LOAD iceberg;` then `SELECT * FROM iceberg_scan('.../metadata.json')`. **Read-only** in 1.1.3; writes are via PyIceberg. → `/extensions/iceberg`
- **Memory + spill** — `SET memory_limit='4GB'` caps RAM; over-budget queries spill to `temp_directory`. Default ~80% of system RAM.
- **Threads** — Auto-parallelizes; defaults to one per CPU core. `SET threads=N`. Tests want `threads=1` for deterministic ordering.
- **Transactions / threading** — `BEGIN; ... COMMIT;` per connection; single-writer per file (MVCC). Connection (or `conn.cursor()`) per task; **never share across threads**.

---

## §5. Critical API surface

Symbols our `DuckDBEngine` adapter calls. Reference: [Python API](https://duckdb.org/docs/stable/clients/python/overview).

| Symbol | Signature (1.1.3) | Use |
|---|---|---|
| `duckdb.connect` | `connect(database=':memory:', read_only=False, config=None) -> DuckDBPyConnection` | Open engine connection. |
| `conn.execute` | `execute(query, parameters=None) -> DuckDBPyConnection` | Run statement; positional params (PEP 249). |
| `conn.sql` | `sql(query, alias='', params=None) -> DuckDBPyRelation` | Run **lazy** relational query. Preferred for `ctx.sql`. |
| `conn.from_arrow` | `from_arrow(arrow_object) -> DuckDBPyRelation` | **Zero-copy in** from PyArrow Table / RecordBatchReader. |
| `result.arrow()` / `result.fetch_arrow_table()` | `-> pyarrow.Table` | **Zero-copy out** to PyArrow. |
| `result.pl()` | `-> polars.DataFrame` | Convert to Polars (zero-copy via Arrow). |
| `conn.register` / `conn.unregister` | `register(view_name, obj)` / `unregister(view_name)` | Register PyArrow / Polars / Pandas as a SQL view. |
| `conn.execute("INSTALL iceberg; LOAD iceberg;")` | — | Load Iceberg extension once per connection. |
| `conn.execute("SELECT * FROM iceberg_scan(?)", [path])` | — | Read an Iceberg table snapshot. |
| `SET memory_limit / threads / timezone` | — | `SET timezone='UTC'` is **required for determinism** per `engineering.md` §6.1. |
| `conn.close()` | — | Release the handle. Prefer context manager. |

**Not used in v0.1**: `conn.create_function` (Python UDFs), `httpfs` cloud streaming (deferred to v0.3 + `dlt`), Iceberg writes (PyIceberg owns this — Constraint #5), MotherDuck, replacement scans.

---

## §6. Exception types we'll translate (PoC #1 target)

Module: `duckdb` (top-level). All inherit from `duckdb.Error` ⊂ `Exception`. Reference: https://duckdb.org/docs/stable/clients/python/dbapi. These match `sequence_error_translation.md` §4.2 (seven classes) plus `ConnectionException`. Each must be triggered against a real 1.1.3 connection in PoC #1 Week 1.

| Class | Raised when | Translates to |
|---|---|---|
| `duckdb.CatalogException` | Object (table/view/schema/function) doesn't exist | `NucleusAssetNotFound` |
| `duckdb.BinderException` | Unknown column / type mismatch / ambiguous reference | `NucleusSchemaError` |
| `duckdb.ParserException` | SQL syntax invalid; message carries position | `NucleusSQLSyntaxError` (preserve line/col) |
| `duckdb.IOException` | File / S3 read or write failed | `NucleusIOError` |
| `duckdb.ConversionException` | Implicit cast or `CAST(...)` failed | `NucleusSchemaError` |
| `duckdb.OutOfMemoryException` | Query exceeded `memory_limit`, could not spill | `NucleusResourceError` (suggest `--large` / higher limit) |
| `duckdb.TransactionException` | Concurrent write conflict on the DB file | `NucleusCommitConflictError` |
| `duckdb.ConnectionException` | DB file locked by another process / handle invalidated | `NucleusEngineError` |

**Flagged for PoC #1 to verify**: `ParserException` exposing parseable line/column; `OutOfMemoryException` firing reliably (vs. OS OOM-kill); `TransactionException` triggering with concurrent file connections. If any class name is missing or renamed in 1.1.3, log to `docs/internal/research/ai_hallucinations.md` per `.cursor/rules/nucleus.mdc`.

Translator contract: [`sequence_error_translation.md`](../architecture/sequence_error_translation.md) §5.

---

## §7. Known gotchas / pitfalls

- **SQL dialect ≠ Postgres.** Array literals `[1,2,3]`; no `::regclass`/`::oid`; date-style uses `strftime`/`strptime` not `to_char`; window-function defaults stricter. Read the [SQL reference](https://duckdb.org/docs/sql/introduction), do not translate by analogy.
- **Implicit casts are liberal.** `SELECT 1 + '2'` returns 3. Issue `SET timezone='UTC'` (and any future strictness pragmas) at connection start per `engineering.md` §6.1 / `type_mapping.md` §6.1.
- **Decimal silently widens, then becomes DOUBLE.** Precision/scale preserved up to **38 digits**; past that DuckDB silently switches to DOUBLE — surface a warning at write time (`type_mapping.md` §6.2).
- **`TIMESTAMP` = microseconds.** `TIMESTAMP_NS` exists but is **incompatible with Iceberg v2** (`type_mapping.md` §4.3 / §6.4). Never expose to assets.
- **Memory defaults to ~80% of RAM** — 12.8 GB on a 16 GB laptop, easily stealing from the user's IDE. Set `memory_limit` explicitly; align with `engineering.md` §11.1 (8 GB default, `--large` for more).
- **`STRUCT(...)` / `LIST(...)`** roundtrip cleanly to Iceberg from **v0.2+**; in v0.1 raise `NucleusUnsupportedTypeError` (`type_mapping.md` §3.9).
- **Threads + connections.** Defaults to all cores; tests use `SET threads=1` for deterministic ordering. `DuckDBPyConnection` is **not thread-safe** — use `conn.cursor()` (cheap) or separate connections.
- **Single-writer per file.** Two processes writing the same `.duckdb` → `TransactionException` / `ConnectionException`. v0.1 uses `:memory:` so this is informational, relevant when we add a query cache.
- **Windows extensions.** Parquet/JSON/ICU bundled; `iceberg` and `httpfs` are **autoloadable** — first use downloads to `~/.duckdb/extensions/`. Air-gapped CI needs pre-download.
- **Storage format stable across 1.x.** Files written by 1.0+ are readable by all 1.x; 2.x makes no such promise.

---

## §8. Interaction with other Nucleus components

- **Inputs**: SQL strings produced by `ctx.sql` Jinja resolver (Tier 1). Parameters positional — never f-string interpolation (`engineering.md` §12.2).
- **Arrow zero-copy**: PyArrow `Table` ↔ DuckDB ↔ Polars `DataFrame` without a Pandas hop (`engineering.md` §11.4).
- **Iceberg reads**: (a) DuckDB's `iceberg_scan(...)` for SQL-side reads; (b) PyIceberg's `Table.scan().to_duckdb(connection_name)` to expose an Iceberg table as a DuckDB view from Python. v0.1 prefers (b) — it composes with the Asset Materialization Adapter.
- **Iceberg writes**: **never via DuckDB**. PyIceberg `Table.append()` / `.overwrite()` only — Constraint #5.
- **Errors**: caught at the engine boundary → Error Translation Layer → `NucleusError`. `scripts/dagster_leak_check.py` extends naturally to detect `duckdb.` substrings in user-facing CLI output.
- **Type coercion**: governed by [`type_mapping.md`](../patterns/type_mapping.md) §6. Property tests in `tests/patterns/test_type_mapping.py`.

---

## §9. Upgrade considerations

When bumping the pin (one-component-per-PR per AGENTS.md §11.13), re-check:

- **Exception class names + module path** — verify each row in §6 still imports.
- **Default settings** — `memory_limit`, `threads`, `temp_directory` defaults occasionally change in minors.
- **SQL dialect drift** — minors tweak implicit casts + window-function defaults; re-run the Jinja-resolver snapshot suite (`engineering.md` §6.7).
- **Iceberg extension** — pinned alongside DuckDB; spec coverage (v1, v2 reads; v3 partial) evolves faster than DuckDB itself.
- **Storage format** — stable across 1.x; **2.x makes no guarantee** → ADR + Iceberg-snapshot replay test on major bump.
- **Wheel availability** — Windows + macOS arm64 must be present on PyPI before we move; Tier 0 ships on Windows.
- **Python support floor** — 1.5.2 raised `requires_python` to `>=3.10.0`; we hold at 3.11/3.12 (`engineering.md` §1.1).

Release notes: https://github.com/duckdb/duckdb/releases (pre-1.4) and https://github.com/duckdb/duckdb-python/releases (1.4+). Read **every** minor between current and target. Major bumps (1.x → 2.x) require ADR + re-run of type-mapping property tests + the 50-scenario error fixture (`sequence_error_translation.md` §7).

---

## §10. Useful links

- https://duckdb.org/docs/stable/clients/python/overview — Python client. **Bookmark.**
- https://duckdb.org/docs/stable/clients/python/dbapi — DBAPI + exception class reference. Re-read on every upgrade.
- https://duckdb.org/docs/stable/clients/python/relational_api — Lazy `DuckDBPyRelation` used by `conn.sql(...)`.
- https://duckdb.org/docs/stable/sql/introduction — SQL dialect reference. Use over memory.
- https://duckdb.org/docs/stable/sql/data_types/overview — Type system (paired with `type_mapping.md` §6).
- https://duckdb.org/docs/stable/extensions/iceberg — Iceberg extension (read-side only).
- https://duckdb.org/docs/stable/configuration/overview — Settings (`memory_limit`, `threads`, `timezone`, `temp_directory`).
- https://github.com/duckdb/duckdb — Engine source + issues.
- https://github.com/duckdb/duckdb/releases — Changelog (read full range during any upgrade PR).
- https://pypi.org/project/duckdb/ — Version history + vulnerability disclosures.

---

*Last verified: 2026-05-12. Re-verify when bumping the pin or before integrating any new DuckDB capability (UDFs, httpfs, Iceberg writes if/when they exit experimental).*
