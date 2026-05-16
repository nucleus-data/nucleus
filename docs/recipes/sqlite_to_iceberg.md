# Recipe: SQLite → Iceberg in 10 minutes

> **Time**: ~10 min (no Docker, no source DB to install) · **Difficulty**: Junior DE · **Prereqs**: Python 3.11 / 3.12, ~200 MB disk
> **Status**: pre-v0.1 — depends on PoCs #1 + #3 + #4 passing first; CLI lines marked `<!-- pre-v0.1 -->`. PoC #3's Python entry point is 7/7 pytest green ([`poc/p3_ingest/test_ingest.py`](../../poc/p3_ingest/test_ingest.py)).
> **Refs**: [`postgres_to_iceberg.md`](./postgres_to_iceberg.md) · [`csv_to_iceberg.md`](./csv_to_iceberg.md) · [`docs/patterns/partitioning.md`](../patterns/partitioning.md) · [`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) §3.5

A junior DE's first taste of Iceberg. You have a local SQLite DB (Django dev DB, Excel export, Airtable archive) and you want it queryable as an Iceberg asset for BI / future graduation to a real catalog. SQLite is the only source PoC #3 has validated end-to-end ([`poc/p3_ingest/STATUS.md`](../../poc/p3_ingest/STATUS.md)) — this recipe traces the shortest verified path through `nucleus ingest`.

---

## What you'll build

A 5-row `customers` SQLite source → Iceberg `raw.customers` source asset (auto-inferred schema) → optional `staging.customers_partitioned` re-bucketed by signup month for fast BI scans.

```mermaid
graph LR
    A[sales.db<br/>SQLite] -->|nucleus ingest| B[raw.customers<br/>Iceberg snapshot]
    B -->|@nucleus.sql_asset| C[staging.customers_partitioned<br/>month signup_ts]
    C -->|DuckDB iceberg_scan| D[BI / nucleus sql / agent]
```

Smallest working end-to-end of the v0.1 beachhead promise ([v4.1 §1.5](../specs/nucleus_architecture_v4.1.md)). The `ctx.copy_from` path ([v4.1 §5.5.1](../specs/nucleus_architecture_v4.1.md)) is the same one Postgres / MySQL / CSV will use once PoC #3 graduates.

---

## Step 1: Confirm prerequisites (~1 min)

```bash
python --version    # 3.11.x or 3.12.x
```

That's it — `sqlite3` is stdlib, no Docker needed. v0.1 catalog is filesystem-backed ([v4.1 §5.7](../specs/nucleus_architecture_v4.1.md)); writes land in `.nucleus/warehouse/`. Missing Python? [`SETUP.md`](../../SETUP.md) §1-§3.

## Step 2: Prepare a SQLite source (~2 min)

Skip if you already have a `.db` file. Otherwise:

```bash
sqlite3 sales.db <<'SQL'
CREATE TABLE customers (
  id          INTEGER PRIMARY KEY,
  email       TEXT NOT NULL,
  signup_ts   TEXT NOT NULL,                 -- ISO-8601; see Common gotchas
  ltv         REAL NOT NULL DEFAULT 0
);
INSERT INTO customers VALUES
  (1, 'a@example.com', '2026-01-05T08:23:00Z',   49.99),
  (2, 'b@example.com', '2026-01-12T11:09:00Z',  120.00),
  (3, 'c@example.com', '2026-02-03T16:42:00Z',    0.00),
  (4, 'd@example.com', '2026-02-19T09:55:00Z',   12.50),
  (5, 'e@example.com', '2026-03-08T14:30:00Z', 1234.56);
SQL
```

5 rows is enough to eyeball the partition effect in Step 6; real `sales.db` files have thousands.

## Step 3: Initialize and boot Nucleus (~2 min)

```bash
nucleus init customers-demo                       # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.1 -->
cd customers-demo
mv ../sales.db .
nucleus up                                        # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.2 -->
```

Same `<10 s` boot as the Postgres recipe ([v4.1 §11.1](../specs/nucleus_architecture_v4.1.md)) — MinIO + filesystem catalog + Dagster substrate.

## Step 4: Ingest the SQLite asset (~2 min)

```bash
nucleus ingest sqlite:///./sales.db \
    --table customers --as raw.customers          # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.5 -->
```

Auto-infers the Iceberg schema from `PRAGMA table_info(...)` ([`poc/p3_ingest/ingest.py:55-60`](../../poc/p3_ingest/ingest.py)) and atomically commits via `Catalog.create_table` + `Table.append` ([`poc/p3_ingest/ingest.py:219-222`](../../poc/p3_ingest/ingest.py)). Destination: `.nucleus/warehouse/raw/customers/`. No Python, no schema declaration.

## Step 5: Verify (~1 min)

```bash
nucleus sql "SELECT count(*), min(signup_ts), max(signup_ts) FROM raw.customers"
                                                  # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.6 -->
# Expected: 5 | 2026-01-05T08:23:00Z | 2026-03-08T14:30:00Z
```

`nucleus sql` runs DuckDB zero-copy against the Iceberg asset via `Table.scan().to_duckdb(...)` ([`docs/internal/research/pyiceberg.md`](../research/pyiceberg.md) §5).

## Step 6: Add a monthly partition for BI (~3 min, optional)

`assets/staging/customers_partitioned.py`:

```python
import nucleus

@nucleus.sql_asset(partition_by="month(signup_ts)")
def customers_partitioned(ctx):
    """Re-bucket customers by signup month — fast time-range scans."""
    return ctx.sql("""
        SELECT id, email, signup_ts, ltv
        FROM {{ ref('raw.customers') }}
    """)
```

```bash
nucleus run staging.customers_partitioned         # <!-- pre-v0.1; docs/specs/nucleus_cli_spec.md §3.4 -->
```

`month(signup_ts)` is one of seven Iceberg partition transforms ([`partitioning.md`](../patterns/partitioning.md) §3). With 5 rows across 3 months you get one Parquet file per month.

Done. Total: **<10 min** if nothing went sideways.

---

## What you've achieved

- **Iceberg-native asset** — schema preserved, `Table.append` atomic, snapshot committed.
- **Auto-inferred schema** — `INTEGER → LongType`, `REAL → DoubleType`, `TEXT → StringType`, `BLOB → BinaryType` ([`poc/p3_ingest/ingest.py:55-60`](../../poc/p3_ingest/ingest.py)); `NOT NULL` preserved as Iceberg `required=True` ([`poc/p3_ingest/ingest.py:91-94`](../../poc/p3_ingest/ingest.py)).
- **Partition strategy applied** — `month(signup_ts)` prunes BI queries at planning time.
- **BI-ready, graduation-clean** — Parquet + Iceberg metadata, portable to Polaris / Lakekeeper / Databricks / Snowflake (Mode 1, [v4.1 §17](../specs/nucleus_architecture_v4.1.md)).

## Common gotchas

- **Type map is narrow** — only `INTEGER`, `REAL`, `TEXT`, `BLOB` (the four SQLite storage classes) work in v0. `NUMERIC`, `DECIMAL`, `BOOLEAN`, `DATE`, `DATETIME` raise `NucleusUnsupportedTypeError` ([`poc/p3_ingest/ingest.py:80-89`](../../poc/p3_ingest/ingest.py)). Workaround: `CREATE VIEW v AS SELECT CAST(weird AS TEXT) ...` and ingest the view. User-supplied schema is v0.5+ ([`schema_evolution.md`](../patterns/schema_evolution.md) §3); auto-infer is the only v0 path ([`poc/p3_ingest/ingest.py:176`](../../poc/p3_ingest/ingest.py)).
- **Windows `file:///` URI quirk** — pyiceberg 0.8.1 mis-parses the RFC 8089 `file:///C:/...` form on Windows; PoC #3 emits the two-slash `file://C:/...` workaround ([`poc/p3_ingest/ingest.py:112-125`](../../poc/p3_ingest/ingest.py)). `nucleus ingest` handles this — flag it only if you call pyiceberg directly. Tracker: [iceberg-python#1005](https://github.com/apache/iceberg-python/issues/1005).
- **WAL-mode source DB** — if `sales.db` is being written by another process, ingest reads a snapshot at file-open time per stdlib [`sqlite3.connect`](https://docs.python.org/3/library/sqlite3.html). Quiesce the writer for fully-consistent reads.

## What's next

- **Add a `@nucleus.check`** for row-count drift or column nullability — fails the materialization on violation ([v4.1 §6.2](../specs/nucleus_architecture_v4.1.md)).
- **Schedule** via the wrapped Dagster substrate ([v4.1 §6.1](../specs/nucleus_architecture_v4.1.md)); cron lands at v0.3.
- **Real DB?** [`postgres_to_iceberg.md`](./postgres_to_iceberg.md) once PoC #3 graduates. **No DB at all?** [`csv_to_iceberg.md`](./csv_to_iceberg.md).
- **Patterns** — [`partitioning.md`](../patterns/partitioning.md) · [`schema_evolution.md`](../patterns/schema_evolution.md) · [`snapshot_retention.md`](../patterns/snapshot_retention.md).

---

## NEEDS VERIFICATION

Per [AGENTS.md §11.12](../../AGENTS.md):

1. **`nucleus ingest` CLI** — spec §3.5 lists `sqlite://` + `--table` / `--as`, but PoC #3 ships only the Python entry point `ingest_sqlite_to_iceberg(...)` ([`poc/p3_ingest/ingest.py:176`](../../poc/p3_ingest/ingest.py)). The CLI shim lands when PoC #3 graduates to `src/nucleus/ctx/copy_from.py` (~200 LOC, [v4.1 §5.5.1](../specs/nucleus_architecture_v4.1.md)). The original prompt's `--source-table` / `--target` / `--partition-by` flags are *not* spec form — partitioning runs through the asset decorator, not an ingest flag.
2. **`nucleus sql "..."` vs `nucleus query "..."`** — sibling recipes use `nucleus sql`; spec §3.6 calls it `nucleus query`. Recipe mirrors the existing recipes pending sibling reconciliation.
3. **`@nucleus.sql_asset(partition_by="month(signup_ts)")` string DSL** — described in [`docs/patterns/partitioning.md`](../patterns/partitioning.md) §3 + §6 but the parser inside `@nucleus.asset` / `@nucleus.sql_asset` is not implemented; lands alongside PoC #2.
4. **`nucleus snapshot list / restore`** — deferred to v0.5 per spec §4.1. Use `nucleus sql` against the asset until the snapshot subcommand ships.
5. **`docs/recipes/README.md` index does not yet list this file** — the v0.1 beachhead table contains only `postgres_to_iceberg.md` + `csv_to_iceberg.md`. Adding a row is a follow-up PR (out of scope per the no-modify constraint).

Hit any of these? Log to [`docs/internal/research/ai_hallucinations.md`](../research/ai_hallucinations.md).

---

[← `docs/recipes/README.md`](./README.md) · [Sibling — `docs/patterns/README.md`](../patterns/README.md) · [Source — `poc/p3_ingest/`](../../poc/p3_ingest/)
