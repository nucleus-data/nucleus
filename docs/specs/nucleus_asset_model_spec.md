# Nucleus Asset Model — Specification

> The fundamental data primitive of Nucleus. Everything else maps to this.
>
> Companion to `nucleus_architecture_v3.md` §0. Locked for v1.0.

---

## 0. Why "Asset" (not "Table", "Pipeline", "Job")

We borrow Dagster's terminology because it is the cleanest abstraction for modern data engineering. An **asset** is a *named, persistent unit of data* that the platform produces, tracks, and serves.

| If you think in… | An asset is… |
|---|---|
| Spark / Databricks | A managed table + the code that produces it |
| dbt | A model |
| Airflow | A task's output, tracked as a first-class object |
| Filesystem | A file with versioned, queryable metadata |

The unification is the point: **one mental model for sources, transformations, materializations, and contracts.**

---

## 1. Anatomy of an Asset

Every asset has these properties:

```yaml
asset:
  # Identity (immutable once created)
  name: "sales.orders"           # 3-part: catalog.schema.table
  id: "asset:01HZ..."            # ULID, internal

  # Code provenance
  code_location: "pipelines/sales/orders.py:orders"
  code_version: "sha256:abc..."  # hash of decorated function source
  
  # Materialization target
  iceberg_table: "lakekeeper://main/sales/orders"
  storage_uri: "s3://acme-warehouse/sales/orders/"
  
  # Metadata
  owner: "data-team@acme.com"
  description: "Cleaned orders joined with customers"
  tags: ["pii", "finance"]
  
  # Schedule & partitioning
  schedule: "@daily"
  partitions: {type: "daily", start: "2024-01-01"}
  
  # Dependencies (auto-derived from ctx.read())
  upstream: ["raw.orders", "dim.customers"]
  
  # SLAs
  freshness_sla: "24h"
  
  # Contracts
  contract_id: "contract:01HZ..."
  
  # Runtime
  retries: {count: 3, delay: "exponential"}
  timeout: "1h"
```

---

## 2. Asset Identity

### 2.1 Logical name (the human-facing identity)

Format: `catalog.schema.table` — 3 parts, lowercase, snake_case.

```
sales.orders
sales.daily_revenue
raw.stripe_charges
analytics.dau
```

### 2.2 Reserved namespaces

| Namespace | Purpose |
|---|---|
| `raw.*` | Ingested data, untransformed |
| `staging.*` | Light cleaning, intermediate |
| `dim.*` | Dimensions |
| `fact.*` | Fact tables |
| `analytics.*` | Business-facing aggregates |
| `dev.*` | Development scratch (auto-cleaned) |
| `_internal.*` | Platform-managed (never user-writable) |

These are conventions, not enforced — but `nucleus init` scaffolds them.

### 2.3 Internal ID

ULID (`01HZ...`) is generated on first registration. Used internally for:
- Lineage edges
- Run history references
- Audit logs

Name is mutable (rename allowed); ID is forever.

---

## 3. Asset Types

| Type | Decorator | Materialization | Use case |
|---|---|---|---|
| **Table asset** | `@nucleus.asset` | Iceberg table | DataFrame transforms |
| **SQL asset** | `@nucleus.sql_asset` | Iceberg table or view | Pure SQL transforms |
| **Source asset** | `@nucleus.source` | Iceberg table (via dlt) | External ingestion |
| **Multi asset** | `@nucleus.multi_asset` | Multiple Iceberg tables | One function produces N tables |
| **Check asset** | `@nucleus.check` | None (run record) | Quality validation |
| **Sensor asset** | `@nucleus.sensor` | None (trigger emitter) | Event detection |

---

## 4. Materialization Modes

### 4.1 `materialized = "table"` (default)

Full overwrite on every run. New Iceberg snapshot per run.

### 4.2 `materialized = "view"`

No data written. Iceberg view definition stored in catalog. Queried virtually.

### 4.3 `materialized = "incremental"`

Append/merge new rows only. Requires `incremental_key` or partition logic.

```python
@nucleus.asset(
    table="events.clicks",
    materialized="incremental",
    incremental_key="event_time",
)
def clicks(ctx):
    last = ctx.last_materialization.max_event_time or "1970-01-01"
    return ctx.read("raw.clicks").filter(pl.col("event_time") > last)
```

### 4.4 `materialized = "snapshot"`

SCD2 / slowly-changing dimension. Each run produces a new versioned snapshot row.

---

## 5. Partitioning

### 5.1 Partition types

| Type | Syntax | Behavior |
|---|---|---|
| Static | `nucleus.static(["us", "eu"])` | Fixed set of partition keys |
| Time-based | `nucleus.daily("2024-01-01")` | One partition per day |
| Hourly | `nucleus.hourly("2024-01-01T00")` | One per hour |
| Dynamic | `nucleus.dynamic(values_from="ctx.read('regions')")` | Computed at runtime |
| Multi | `nucleus.multi(date=nucleus.daily(...), region=nucleus.static(...))` | Cross-product |

### 5.2 Partition execution

Partitions can be materialized:
- One at a time (`nucleus run sales.orders --partition 2024-01-15`)
- In bulk (`nucleus backfill sales.orders --range 2024-01-01..2024-01-31`)
- On schedule (one partition per scheduled run)

### 5.3 Iceberg partitioning vs Nucleus partitioning

| Nucleus partition | Iceberg partition |
|---|---|
| Defines *execution unit* | Defines *physical storage layout* |
| User-facing | Engine-facing |
| Can match Iceberg partition (typical) | Set via `partition_by` in `@nucleus.asset` |

```python
@nucleus.asset(
    table="events.clicks",
    partitions=nucleus.daily("2024-01-01"),
    partition_by=["event_date", "region"],  # Iceberg storage
)
```

---

## 6. Dependencies & The Asset Graph

### 6.1 Auto-derivation

Every call to `ctx.read("X")` or `{{ ref('X') }}` adds X as upstream of the current asset.

```python
@nucleus.asset(table="sales.orders")
def orders(ctx):
    raw = ctx.read("raw.orders")        # adds raw.orders as upstream
    dim = ctx.read("dim.customers")     # adds dim.customers as upstream
    return raw.join(dim, on="customer_id")
```

Result: `orders` depends on `{raw.orders, dim.customers}` — registered automatically.

### 6.2 Explicit override

If auto-derivation isn't possible (dynamic reads):

```python
@nucleus.asset(table="aggregated", deps=["raw.a", "raw.b", "raw.c"])
def aggregated(ctx):
    for name in ["raw.a", "raw.b", "raw.c"]:
        ...
```

### 6.3 DAG rules

- **Cycles are forbidden.** Detected at registration; pipeline rejected.
- **Self-edges are forbidden.**
- **Cross-project dependencies require explicit declaration** (`deps=["other_project::asset"]`).

---

## 7. Lifecycle States

```
DEFINED → SCHEDULED → RUNNING → {SUCCEEDED, FAILED, SKIPPED, CANCELLED}
```

| State | Meaning |
|---|---|
| `DEFINED` | Code registered, never materialized |
| `SCHEDULED` | Triggered by schedule/sensor, queued |
| `RUNNING` | Executing |
| `SUCCEEDED` | Latest run wrote successfully; snapshot exists |
| `FAILED` | Last run errored; previous snapshot still queryable |
| `SKIPPED` | Skipped (e.g., upstream failed) |
| `CANCELLED` | User-aborted |

**Key invariant**: a `FAILED` asset is still readable — Iceberg snapshot from last success remains. Reads never fail because of a failed write.

---

## 8. Versioning

Three independent version axes per asset:

### 8.1 Code version

`sha256(decorated_function_source + imports + dependencies)`.
Changes when user edits code. Triggers re-materialization.

### 8.2 Data version

Iceberg snapshot ID. Auto-incremented on each successful materialization.

### 8.3 Schema version

Iceberg schema ID. Changes only on schema evolution (add/drop/rename column).

### 8.4 Version stamping

Every materialization records: `(code_version, data_version, schema_version, run_id, timestamp)`. Stored in the metadata DB and as Iceberg snapshot properties.

---

## 9. Contracts

### 9.1 What a contract is

A declarative set of *invariants* that must hold for an asset's data.

```python
@nucleus.contract("sales.orders")
def orders_contract():
    return [
        nucleus.expect("order_id").is_unique(),
        nucleus.expect("order_id").not_null(),
        nucleus.expect("amount").gt(0).lte(1_000_000),
        nucleus.expect("date").freshness("24h"),
        nucleus.expect("customer_id").references("dim.customers", "id"),
        nucleus.expect("currency").one_of(["USD", "EUR", "VND"]),
    ]
```

### 9.2 Enforcement levels

| Level | Behavior on violation |
|---|---|
| `strict` (default) | Materialization fails; previous snapshot retained |
| `warn` | Materialization succeeds; alert emitted |
| `block_consumers` | Materialization succeeds; downstream reads fail until fixed |

### 9.3 Backed by

Soda Core under the hood. `ctx.contract` translates to Soda checks.

---

## 10. Checks (Imperative Quality)

For checks too complex for declarative contracts.

```python
@nucleus.check(asset="sales.orders", severity="error")
def orders_balance_check(ctx):
    orders = ctx.read("sales.orders")
    payments = ctx.read("sales.payments")
    diff = abs(orders["amount"].sum() - payments["amount"].sum())
    return nucleus.CheckResult(
        passed=diff < 0.01,
        metric=diff,
        message=f"Orders/payments diff: ${diff:.2f}",
    )
```

Runs after materialization. Records pass/fail to metadata.

---

## 11. Metadata Storage

All asset metadata lives in Postgres (or SQLite in embedded mode). Schema:

```sql
assets (id, name, kind, code_location, code_version, ...)
asset_runs (id, asset_id, run_id, status, started_at, finished_at, ...)
asset_dependencies (upstream_id, downstream_id, derived_from)
asset_materializations (id, asset_id, snapshot_id, code_version, data_version, ...)
asset_contracts (id, asset_id, definition, enforcement_level)
asset_check_results (id, asset_id, run_id, passed, metric, message)
asset_lineage_edges (run_id, source_column, target_column, transformation)
```

This schema is **internal** but stable — exposing it as a read-only `_internal.*` schema for advanced users is allowed in v1.0.

---

## 12. Asset Discovery

### 12.1 Programmatic

```python
nucleus.assets()                          # all assets
nucleus.assets(tag="pii")                 # by tag
nucleus.assets(owner="data-team@...")     # by owner
nucleus.asset("sales.orders").info()      # full metadata
nucleus.asset("sales.orders").upstream()  # upstream graph
nucleus.asset("sales.orders").downstream()
```

### 12.2 Via Portal

Asset Catalog tab → search, filter, browse, lineage view.

### 12.3 Via CLI

```bash
nucleus list                      # all assets
nucleus describe sales.orders     # full info
nucleus lineage sales.orders      # graph
```

---

## 13. Asset Identity Across Environments

Same logical name (`sales.orders`) refers to *different physical tables* in dev vs prod:

```
env=dev:  ./.nucleus/warehouse/sales/orders/
env=prod: s3://acme-warehouse/sales/orders/
```

Resolution happens via `nucleus.yaml` → `environments.<env>.warehouse`.

**Critical invariant**: code is byte-identical across envs. Only config differs.

---

## 14. Forbidden Patterns

| Anti-pattern | Why |
|---|---|
| Two assets writing to the same `table=` | Ambiguous truth |
| Mutating `ctx.read()` result and re-writing as the same asset | Side-effect on input |
| Reading from raw `s3://` instead of `ctx.read()` | Breaks lineage |
| `nucleus.asset` without `table=` | Asset must have a name |
| Cross-project deps without explicit declaration | Hidden coupling |
| Decorating non-function (class, lambda) | Unsupported |

Registration validates these; bad pipelines never reach scheduling.

---

## 15. The Asset Model Contract

These properties are **promised** by the platform forever:

1. **Atomic materialization** — partial writes never visible
2. **Time-travel-able** — every materialization queryable via snapshot
3. **Auto-lineage** — `ctx.read()` always tracked
4. **Idempotent re-runs** — same code + same upstream = same output
5. **Failure-isolated** — failed asset never corrupts readers
6. **Environment-portable** — code unchanged across dev/staging/prod
7. **Schema-evolvable** — adding columns never breaks downstream
8. **Discoverable** — every asset queryable via catalog

These are the eight properties that justify Nucleus existing.

---

*The asset is the noun. Everything else is verbs operating on it.*
