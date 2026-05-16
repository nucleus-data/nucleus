# Nucleus `ctx` SDK — Specification

> The frozen public API surface of Nucleus. **This is the product.**
>
> Companion to `nucleus_architecture_v3.md` §9. Locked for v1.0; semver-stable.

---

## 0. Principles

1. **`ctx` is the only thing users import.** No `dagster`, no `iceberg`, no `duckdb`, no `dlt`, no `s3://`.
2. **The API is minimal.** Every method must justify itself against §3 of the architecture (the four-line decomposition).
3. **Pythonic, not framework-y.** Familiar to dbt + Pandas + Dagster users; surprising to nobody.
4. **Frozen on v1.0.** Adding new methods is fine. Changing/removing is a breaking change requiring v2.0.
5. **Leaks are bugs.** If a user must touch Dagster, Iceberg, or DuckDB directly, the SDK has failed.

---

## 1. Package & Imports

```python
import nucleus                   # decorators, asset definitions
import nucleus.types as nt       # type hints, dataclasses
import polars as pl              # users still use Polars directly for DataFrames
```

That's it. Three imports for 95% of work.

`ctx` is **not** imported — it is **passed** to every asset function by the runtime.

---

## 2. Decorators (Asset Definition)

### 2.1 `@nucleus.asset`

The primary primitive. Defines a materialized asset.

```python
@nucleus.asset(
    table="sales.orders",                  # required: 3-level Iceberg name
    schedule="@daily",                     # optional: cron or preset
    partitions=nucleus.daily("2024-01-01"),# optional: partition definition
    deps=["raw.orders", "dim.customers"],  # optional: explicit (usually auto-derived)
    owner="data-team@example.com",         # optional but recommended
    description="Cleaned and joined orders",
    tags=["pii", "finance"],
    freshness=nucleus.freshness(hours=24), # SLA target
    retries=nucleus.retries(count=3, delay="exponential"),
)
def orders(ctx) -> pl.DataFrame:
    ...
```

**Return type contract**: must return `pl.DataFrame` | `pl.LazyFrame` | `pyarrow.Table` | `duckdb.DuckDBPyRelation` | `None` (if writing via `ctx.write` explicitly).

**v0.1.1 `schedule=` kwarg (ADR-017)**: `schedule=` is now wired in `src/nucleus/sdk/decorators.py`. Accepts a 5-field cron string (`"0 2 * * *"`) or a shorthand alias (`"@daily"`, `"@hourly"`, `"@weekly"`, `"@monthly"`, `"@yearly"`). Aliases are normalised to canonical 5-field form at decoration time. Validation uses `croniter==3.0.4` (`is_valid()`) — errors raise `NucleusScheduleParseError` (NE5005) immediately on import. `schedule=None` (default) means no declared schedule.

Active scheduling (automatic execution) is deferred to v0.2 — declaring `schedule=` stores the expression and exposes it via `nucleus schedule list` and `nucleus schedule preview`. Stability: **Beta** per ADR-005 §2, same ladder as the rest of `@nucleus.asset`.

### 2.2 `@nucleus.sql_asset`

For pure SQL transformations. Equivalent to dbt models.

```python
@nucleus.sql_asset(
    table="sales.daily_revenue",
    schedule="@daily",
    materialized="table",   # "table" | "view" | "incremental"
)
def daily_revenue(ctx) -> str:
    return """
        SELECT date, SUM(amount) AS revenue
        FROM {{ ref('sales.orders') }}
        GROUP BY 1
    """
```

`{{ ref('...') }}` is the dbt-compatible asset reference syntax. Resolves to the underlying Iceberg table at runtime.

### 2.3 `@nucleus.source`

Declares an external data source (not produced inside Nucleus).

```python
@nucleus.source(
    name="raw.orders",
    connector="postgres",
    connection="prod-db",
    schedule="@hourly",
    incremental_key="updated_at",
)
def raw_orders(ctx):
    return ctx.connector.postgres(table="public.orders")
```

Sources are leaves in the asset graph. Powered by `dlt` underneath.

### 2.4 `@nucleus.check`

Runtime data quality check. Runs after asset materialization.

```python
@nucleus.check(asset="sales.orders")
def check_no_negative_amounts(ctx):
    df = ctx.read("sales.orders")
    bad = df.filter(pl.col("amount") < 0)
    return nucleus.CheckResult(
        passed=len(bad) == 0,
        metric=len(bad),
        message=f"{len(bad)} negative amounts found",
    )
```

### 2.5 `@nucleus.contract`

Declarative data contract (Soda-backed).

```python
@nucleus.contract("sales.orders")
def orders_contract():
    return [
        nucleus.expect("order_id").is_unique(),
        nucleus.expect("order_id").not_null(),
        nucleus.expect("amount").gt(0),
        nucleus.expect("date").freshness("1 day"),
        nucleus.expect("customer_id").references("dim.customers", "id"),
    ]
```

### 2.6 `@nucleus.sensor`

Event-driven trigger (file arrival, external signal).

```python
@nucleus.sensor(
    triggers=["raw.orders"],
    interval="5m",
)
def new_files_sensor(ctx):
    if ctx.s3_path("incoming/").has_new_files():
        return nucleus.trigger("raw.orders")
```

### 2.7 `@nucleus.schedule`

Standalone schedule (not tied to a single asset).

```python
@nucleus.schedule(cron="0 2 * * *", targets=["sales.*"])
def nightly_sales(ctx):
    pass
```

---

## 3. The `ctx` Object — Lifecycle

`ctx` is **constructed per asset execution** by the runtime. It is scoped to:

- one asset
- one run
- one partition (if partitioned)

It is **never** instantiated by user code.

### 3.1 What `ctx` carries

| Attribute | Type | Always available? |
|---|---|---|
| `ctx.asset` | `AssetRef` | Yes |
| `ctx.run_id` | `str` | Yes |
| `ctx.partition` | `Partition \| None` | If asset is partitioned |
| `ctx.params` | `Params` (typed) | Yes |
| `ctx.log` | `Logger` | Yes |
| `ctx.metrics` | `MetricsSink` | Yes |
| `ctx.secrets` | `SecretStore` | Yes |
| `ctx.env` | `str` (`"dev"`, `"staging"`, `"prod"`) | Yes |
| `ctx.connector` | `ConnectorNamespace` | If asset is `@source` |

---

## 4. Read API

### 4.1 `ctx.read(name, *, as_=...)`

Read another asset's materialization.

```python
df = ctx.read("sales.orders")                          # default: pl.LazyFrame
df = ctx.read("sales.orders", as_="polars")            # pl.LazyFrame
df = ctx.read("sales.orders", as_="arrow")             # pa.Table
df = ctx.read("sales.orders", as_="duckdb")            # duckdb.DuckDBPyRelation
df = ctx.read("sales.orders", as_="pandas")            # pd.DataFrame (last resort)
```

**Default**: `pl.LazyFrame` — encourages lazy + push-down optimization.

**Snapshot reading**:

```python
df = ctx.read("sales.orders", snapshot="2024-01-15")   # time travel
df = ctx.read("sales.orders", version=42)              # specific snapshot version
```

**Partition filtering** (push-down):

```python
df = ctx.read("sales.orders", partitions=["2024-01-15", "2024-01-16"])
```

### 4.2 `ctx.read()` dependency tracking

Every `ctx.read("X")` call automatically adds X as a dependency of the current asset. This is how Nucleus derives the DAG without `depends_on=`.

---

## 5. Write API

### 5.1 Implicit write (return value)

Returning from a `@nucleus.asset` writes to the declared table atomically.

```python
@nucleus.asset(table="sales.orders")
def orders(ctx) -> pl.DataFrame:
    return some_df  # auto-written to sales.orders Iceberg table
```

### 5.2 Explicit write

For multi-write or custom patterns.

```python
@nucleus.asset(table="sales.orders")
def orders(ctx):
    df = ...
    ctx.write("sales.orders", df, mode="overwrite")
```

### 5.3 Write modes

| Mode | Semantics |
|---|---|
| `"overwrite"` | Replace table (creates new Iceberg snapshot) |
| `"append"` | Add rows (creates new snapshot) |
| `"merge"` | UPSERT on key columns: `ctx.write(..., mode="merge", on=["id"])` |
| `"overwrite_partitions"` | Replace only matching partitions |

All writes are **atomic** via Iceberg commits. Failed writes do not leave partial state.

### 5.4 Materialize API

Per [ADR-013](./docs/decisions/ADR-013-ctx-materialize-api.md) (ACCEPTED 2026-05-13). Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0 per ADR-005 §2. Wraps `dagster.materialize` under `coordination/asset_materialization.py` per `nucleus_architecture_v4.1.md` §6.2; users never see Dagster types.

```python
# Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)
# Docs: nucleus.dev/api/ctx.materialize
def materialize(
    asset: str | nucleus.AssetRef,
    *,
    partition: str | None = None,
    upstream: Literal["skip", "materialize", "validate"] = "skip",
    timeout_seconds: int | None = None,
) -> MaterializationResult:
    """Materialize a Nucleus asset to its declared destination.

    Per `nucleus_architecture_v4.1.md` §6.2 (Asset Materialization Adapter).
    """
```

Argument semantics:

- `asset` — 2-level v0.1 key (e.g. `"marts.orders_clean"`) or `AssetRef`. Unknown → `NucleusAssetNotFound` / `NE3002`.
- `partition` — single-string (`"2026-05-13"`); `None` = all eligible partitions; tuple form deferred to v0.3+.
- `upstream` — `"skip"` (default; fail loud via `NE3003` when an upstream asset is unmaterialized), `"materialize"`, `"validate"`.
- `timeout_seconds` — wall-clock; `None` = no timeout; exceeded → `NucleusTimeoutError` / `NE3005`.

Return type `MaterializationResult` (placed in `nucleus.sdk.types`, re-exported from `nucleus`):

```python
# Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0
@dataclass(frozen=True)
class MaterializationResult:
    asset_key: str            # e.g. "marts.orders_clean"
    snapshot_id: str          # Iceberg snapshot ID (v0.1); Lance version (v0.5+)
    partition: str | None
    row_count: int
    duration_ms: int
    lineage_event_id: str     # OpenLineage RunEvent UUID per v4.1 §6.2 step 4
    materialized_at: datetime # UTC
```

Errors raised (per ADR-006 §Decision + ADR-013 §4):

| Raised when | Subclass | NE-code |
|---|---|---|
| `asset` unresolvable | `NucleusAssetNotFound` | `NE3002` |
| `upstream="skip"` + unmaterialized | `NucleusAssetNotMaterialized` | `NE3003` |
| Pre-write contract violation | `NucleusSchemaError` | `NE2001` |
| Step-3 commit conflict | `NucleusCommitConflictError` | `NE1002` |
| Top-level exception in `@nucleus.asset` body | `NucleusInternalError` | `NE3001` |
| `timeout_seconds` exceeded | `NucleusTimeoutError` | `NE3005` |
| AMA cannot route via §6.4 — outer fallback | `NucleusMaterializationError` | `NE3004` |

`MaterializationResult` is `frozen=True`; fields are additive-only after Stable per ADR-005 §3. The CLI iterates `ctx.materialize(key)` once per `ASSET_KEY` argument — there is no list-variant in v0.1.

---

## 6. SQL API

### 6.1 `ctx.sql(query, **bindings)`

Execute SQL via DuckDB with `{{ ref() }}` resolution.

```python
result = ctx.sql("""
    SELECT date, SUM(amount) AS revenue
    FROM {{ ref('sales.orders') }}
    WHERE date >= {{ start_date }}
    GROUP BY 1
""", start_date="2024-01-01")
```

Returns `duckdb.DuckDBPyRelation` (lazy). Materialize with `.pl()`, `.arrow()`, `.df()`.

### 6.2 `{{ ref('...') }}` resolution

- Resolves to underlying Iceberg table location
- Tracks dependency automatically (same as `ctx.read()`)
- Compatible with dbt syntax intentionally

### 6.3 `{{ source('...') }}` for raw sources

```python
ctx.sql("SELECT * FROM {{ source('raw.orders') }}")
```

---

## 7. Parameters

### 7.1 Defining params (per project)

In `nucleus.yaml`:

```yaml
params:
  start_date:
    type: date
    default: "2024-01-01"
  region:
    type: enum
    values: [us, eu, apac]
    default: us
```

### 7.2 Accessing params

```python
ctx.params.start_date    # typed: date
ctx.params.region        # typed: Literal["us", "eu", "apac"]
```

### 7.3 Runtime override

```bash
nucleus run sales.orders --param start_date=2024-06-01
```

---

## 8. Logging, Metrics, Secrets

### 8.1 `ctx.log`

Structured logging. Always goes to OpenTelemetry + stdout.

```python
ctx.log.info("Processing batch", batch_size=len(df), region=ctx.params.region)
ctx.log.warning("Slow query detected", duration_ms=2300)
ctx.log.error("Validation failed", count=42)
```

### 8.2 `ctx.metrics`

Custom metric emission.

```python
ctx.metrics.gauge("row_count", len(df))
ctx.metrics.counter("rejected_rows", count=42)
ctx.metrics.histogram("processing_seconds", elapsed)
```

Built-in metrics (auto-emitted): `asset.duration`, `asset.rows_written`, `asset.bytes_written`, `asset.success`.

### 8.3 `ctx.secrets`

Retrieve secrets without exposing them to logs.

```python
api_key = ctx.secrets["stripe_api_key"]
```

Source: env vars → OS keychain → `nucleus.config` → `secrets` module (Infisical/Vault) if enabled. **Never** logged. Auto-redacted in error messages.

---

## 9. Connectors (Source assets only)

### 9.1 `ctx.connector.<provider>(**kwargs)`

```python
@nucleus.source(name="raw.orders", connection="prod-db")
def raw_orders(ctx):
    return ctx.connector.postgres(table="public.orders", incremental="updated_at")

@nucleus.source(name="raw.stripe_charges", connection="stripe-prod")
def stripe_charges(ctx):
    return ctx.connector.stripe(resource="charges")
```

All connectors are dlt-backed. Connection definitions live in `nucleus.yaml`:

```yaml
connections:
  prod-db:
    type: postgres
    host: $POSTGRES_HOST
    credentials: $POSTGRES_DSN
  stripe-prod:
    type: stripe
    credentials: $STRIPE_API_KEY
```

---

## 10. Snapshot & Time Travel

```python
ctx.snapshot("sales.orders").versions()                  # list snapshots
ctx.snapshot("sales.orders").at_version(42).read()       # read at version
ctx.snapshot("sales.orders").at_time("2024-01-15").read()
ctx.snapshot("sales.orders").diff(v1=41, v2=42)          # row-level diff
ctx.snapshot("sales.orders").revert_to(version=41)       # admin-only
```

All powered by Iceberg snapshots. No new mechanism.

---

## 11. Configuration

Project-level config in `nucleus.yaml`. Code-level config via `nucleus.config()` at top of project module.

```python
# nucleus_project.py
import nucleus

nucleus.config(
    project_name="acme",
    catalog="lakekeeper://localhost:8181/main",
    warehouse="s3://acme-warehouse/",
    default_engine="duckdb",
)
```

Environment-specific overrides via `nucleus.yaml`:

```yaml
environments:
  dev:
    warehouse: ./.nucleus/warehouse
  prod:
    warehouse: s3://acme-warehouse/
```

Selected via `nucleus run --env prod`.

---

## 12. Frozen Surface (v1.0)

These are **locked**. Removing or changing semantics is a v2.0 breaking change.

```
nucleus.asset          nucleus.sql_asset       nucleus.source
nucleus.check          nucleus.contract        nucleus.sensor
nucleus.schedule       nucleus.expect          nucleus.daily
nucleus.hourly         nucleus.static          nucleus.freshness
nucleus.retries        nucleus.config          nucleus.trigger
nucleus.CheckResult    nucleus.AssetRef        nucleus.Partition

ctx.asset              ctx.run_id              ctx.partition
ctx.params             ctx.log                 ctx.metrics
ctx.secrets            ctx.env                 ctx.connector
ctx.read               ctx.write               ctx.sql
ctx.copy_from          ctx.materialize         ctx.snapshot
ctx.trigger

nucleus.MaterializationResult
```

---

## 13. Evolvable Surface (additions allowed in minor versions)

- New connectors (`ctx.connector.X`)
- New write modes
- New decorators (must not duplicate existing semantics)
- New `ctx.metrics` types
- Engine swap hooks (internal — not user-facing)

---

## 14. Boundaries — What's NOT in `ctx`

If a user needs any of these, the SDK has failed:

| Should NOT be needed | Why |
|---|---|
| `import dagster` | Orchestrator is implementation detail |
| `import iceberg` | Table format is implementation detail |
| `import duckdb` | Engine is implementation detail (but `as_="duckdb"` returns a relation, which is fine) |
| `import dlt` | Connector lib is implementation detail |
| Raw `s3://...` paths | Asset name resolves automatically |
| Catalog client config | Project config handles it |
| Iceberg snapshot IDs | `ctx.snapshot(...)` abstracts them |

**Exception**: power users can drop down to `import polars` and `import duckdb` directly because these *are* part of the contract (DataFrame and SQL primitives). They are Layer 1 physics.

---

## 15. Canonical Examples (Reference)

### 15.1 Minimal asset

```python
@nucleus.asset(table="sales.orders")
def orders(ctx):
    return ctx.read("raw.orders").filter(pl.col("amount") > 0)
```

### 15.2 SQL asset with ref

```python
@nucleus.sql_asset(table="analytics.daily_revenue")
def daily_revenue(ctx):
    return "SELECT date, SUM(amount) FROM {{ ref('sales.orders') }} GROUP BY 1"
```

### 15.3 Partitioned incremental

```python
@nucleus.asset(
    table="events.clicks",
    partitions=nucleus.daily("2024-01-01"),
)
def clicks(ctx):
    day = ctx.partition.value
    return ctx.connector.kafka(topic="clicks", date=day)
```

### 15.4 Source → transform → SQL

```python
@nucleus.source(name="raw.users", connection="prod-db")
def raw_users(ctx):
    return ctx.connector.postgres(table="users")

@nucleus.asset(table="dim.users")
def users(ctx):
    return ctx.read("raw.users").drop("password_hash")

@nucleus.sql_asset(table="analytics.dau")
def dau(ctx):
    return """
        SELECT DATE(event_time), COUNT(DISTINCT user_id)
        FROM {{ ref('events.clicks') }} c
        JOIN {{ ref('dim.users') }} u USING (user_id)
        GROUP BY 1
    """
```

### 15.5 Contract + check

```python
@nucleus.contract("dim.users")
def users_contract():
    return [
        nucleus.expect("user_id").is_unique().not_null(),
        nucleus.expect("email").matches_regex(r".+@.+"),
    ]

@nucleus.check(asset="dim.users")
def check_active_users(ctx):
    n_active = ctx.read("dim.users").filter(pl.col("active")).height
    return nucleus.CheckResult(passed=n_active > 1000, metric=n_active)
```

---

## 16. Versioning Policy

| Change type | Semver bump |
|---|---|
| Add new decorator / method | Minor (1.x → 1.x+1) |
| Add optional parameter | Minor |
| Add new return type option | Minor |
| Remove/rename anything in §12 | Major (1.x → 2.0) |
| Change default behavior | Major |
| Change return semantics | Major |

Users on v1.x always get backward compatibility. v2.0 only if absolutely justified.

---

*This is the contract. Implementation may evolve underneath; the user-visible API does not.*
