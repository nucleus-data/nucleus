# Nucleus Project Anatomy — Specification

> **STATUS — 2026-05-14**: SUPERSEDED by `nucleus_architecture_v4.1.md §3.1` and `nucleus_cli_spec.md §3.1` for the v0.1 layout that `nucleus init` actually emits. The shipped template lives at `src/nucleus/templates/v01/` and produces `nucleus_project.yaml` (not `nucleus.yaml`) plus a flat `assets/`, `data/`, `.gitignore`, `README.md` layout. This doc is retained as historical v3-era reference per `AGENTS.md §2`; do not treat its `nucleus.yaml` + `.nucleus/warehouse/` references as authoritative. The v1.0 rewrite is queued.
>
> What a Nucleus project looks like on disk. The single canonical layout that `nucleus init` produces and every project follows.
>
> Companion to `nucleus_architecture_v3.md` and `nucleus_ctx_sdk_spec.md`. Locked for v1.0.

---

## 0. Why Standardize

If every project is structured differently, the platform stops being a platform. Same reason `next.js` enforces a layout, `rails` enforces conventions, `cargo` enforces a structure. **Convention is composability**.

---

## 1. The Canonical Layout

```
my-project/
├── nucleus.yaml                  # project config (single source of truth)
├── pyproject.toml                # Python dependencies (uv-managed)
├── .python-version               # Python version (3.11+)
├── .gitignore                    # standard nucleus gitignore
├── .env.example                  # template for local secrets (never committed)
├── README.md                     # project description
│
├── assets/                       # all @nucleus.asset definitions
│   ├── __init__.py
│   ├── raw/                      # source assets (ingestion)
│   │   ├── __init__.py
│   │   ├── postgres.py
│   │   └── stripe.py
│   ├── staging/                  # light cleaning
│   │   └── orders.py
│   ├── dim/                      # dimensions
│   │   ├── customers.py
│   │   └── products.py
│   ├── fact/                     # facts
│   │   └── orders.py
│   └── analytics/                # business aggregates
│       └── daily_revenue.py
│
├── sql/                          # SQL-only models (@nucleus.sql_asset)
│   ├── analytics/
│   │   └── daily_revenue.sql
│   └── macros/                   # reusable Jinja macros (dbt-compatible)
│       └── date_dim.sql
│
├── contracts/                    # data contracts
│   ├── orders.py
│   └── customers.py
│
├── checks/                       # imperative quality checks
│   └── balance_check.py
│
├── tests/                        # pytest tests for asset logic
│   ├── test_orders.py
│   └── conftest.py
│
├── connections/                  # connection definitions (no secrets)
│   ├── postgres.yaml
│   └── stripe.yaml
│
├── environments/                 # per-env overrides
│   ├── dev.yaml
│   ├── staging.yaml
│   └── prod.yaml
│
└── .nucleus/                     # local state (gitignored)
    ├── warehouse/                # local MinIO data (dev only)
    ├── catalog.db                # SQLite catalog (dev only)
    ├── runs/                     # local run history
    └── cache/                    # query/result cache
```

This is the layout `nucleus init` produces. **No deviations without justification.**

---

## 2. `nucleus.yaml` — The Project Manifest

The single source of truth for project config. All platform behavior derives from here.

```yaml
# nucleus.yaml
version: 1
project:
  name: acme-data-platform
  description: Acme's data engineering project
  owner: data-team@acme.com

# Core platform configuration
catalog:
  type: lakekeeper                          # iceberg REST catalog
  endpoint: ${CATALOG_ENDPOINT}
  warehouse: ${WAREHOUSE_NAME}

# Storage (per environment, see environments/)
storage:
  type: s3                                  # s3 | minio | local | gcs | r2
  
# Compute defaults
compute:
  default_engine: duckdb                    # duckdb | polars
  memory_limit: 16GB
  threads: auto

# Parameters (user-facing)
params:
  start_date:
    type: date
    default: "2024-01-01"
  region:
    type: enum
    values: [us, eu, apac]
    default: us

# Schedules (cron expressions for asset triggers)
schedules:
  nightly:
    cron: "0 2 * * *"
    timezone: UTC

# Modules (optional, enabled via `nucleus enable`)
modules:
  obs: false                                # observability stack
  auth: false                               # authentication
  streaming: false                          # CDC/streaming
  vector: false                             # vector retrieval
  scale: false                              # distributed (Daft+Ray)
  governance: false                         # column lineage, PII scanner
  bi-metabase: false                        # bundled Metabase

# Default environment
default_environment: dev
```

### 2.1 Required fields

| Field | Why required |
|---|---|
| `version` | Schema version of `nucleus.yaml` itself |
| `project.name` | Asset namespace prefix; logging identity |
| `catalog.*` | Where Iceberg tables are registered |
| `storage.type` | Where Parquet files actually live |

### 2.2 Forbidden in `nucleus.yaml`

- ❌ Secrets, API keys, passwords (use `${VAR}` substitution + `.env` or secrets module)
- ❌ Per-developer settings (use `environments/dev.yaml`)
- ❌ Hardcoded paths (use `${}` substitution)

---

## 3. `pyproject.toml`

Standard Python project file. Managed by `uv`.

```toml
[project]
name = "acme-data-platform"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    "nucleus-sdk>=1.0,<2.0",
    "polars>=1.0",
    # user-added dependencies
]

[tool.nucleus]
project_root = "."
asset_dirs = ["assets", "sql", "contracts", "checks"]
```

`nucleus init` generates this. `uv sync` installs everything. `uv run nucleus ...` is the canonical invocation pattern.

---

## 4. Environment Overrides

`environments/<env>.yaml` overrides any field in `nucleus.yaml`.

### 4.1 `environments/dev.yaml`

```yaml
catalog:
  type: file                                # SQLite-backed local catalog
  endpoint: ./.nucleus/catalog.db
storage:
  type: local
  path: ./.nucleus/warehouse
compute:
  memory_limit: 4GB
params:
  start_date: "2024-12-01"                  # narrower window for dev
```

### 4.2 `environments/prod.yaml`

```yaml
catalog:
  type: lakekeeper
  endpoint: https://catalog.acme.internal
  warehouse: prod-warehouse
storage:
  type: s3
  bucket: acme-warehouse-prod
  region: us-east-1
compute:
  memory_limit: 32GB
modules:
  obs: true
  auth: true
```

### 4.3 Selection

```bash
nucleus run --env prod         # use environments/prod.yaml
NUCLEUS_ENV=prod nucleus run   # same, via env var
```

Code is **byte-identical** across environments. Only config differs.

---

## 5. Asset File Conventions

### 5.1 One concept per file

Good:
```
assets/dim/customers.py        # all customer dimension assets
assets/fact/orders.py          # all order fact assets
```

Avoid:
```
assets/everything.py           # 3000-line god file
```

### 5.2 Naming

- File name matches the primary asset's table name (last segment): `dim/customers.py` → `dim.customers`
- Function name matches table name: `def customers(ctx)`
- One module can contain multiple related assets

### 5.3 Imports at top

```python
# assets/fact/orders.py
import nucleus
import polars as pl
from contracts.orders import orders_contract  # cross-reference if needed
```

### 5.4 Structure of an asset file

```python
"""Fact table: sales orders, cleaned and customer-joined."""

import nucleus
import polars as pl


@nucleus.asset(
    table="fact.orders",
    schedule="@daily",
    owner="data-team@acme.com",
    tags=["finance"],
)
def orders(ctx) -> pl.DataFrame:
    """One row per order. Joined with customer dimension."""
    raw = ctx.read("raw.orders")
    customers = ctx.read("dim.customers")
    return (
        raw.filter(pl.col("status") == "completed")
           .join(customers, on="customer_id", how="left")
           .select(["order_id", "customer_id", "amount", "date", "country"])
    )


@nucleus.check(asset="fact.orders")
def check_no_orphan_orders(ctx):
    orders = ctx.read("fact.orders")
    orphans = orders.filter(pl.col("country").is_null()).height
    return nucleus.CheckResult(passed=orphans == 0, metric=orphans)
```

Docstrings are not optional. Asset docstring becomes the asset description in the catalog.

---

## 6. SQL Asset Conventions

### 6.1 Pure SQL files

```sql
-- sql/analytics/daily_revenue.sql
-- @asset(table="analytics.daily_revenue", schedule="@daily")
-- @description: Daily revenue aggregated from completed orders

SELECT
    date,
    country,
    SUM(amount) AS revenue,
    COUNT(*) AS order_count
FROM {{ ref('fact.orders') }}
GROUP BY 1, 2
```

Asset metadata declared via SQL comments with `-- @key: value` syntax.

### 6.2 Macros (dbt-compatible)

```sql
-- sql/macros/date_dim.sql
{% macro date_range(start, end) %}
    SELECT date_value::DATE AS date
    FROM range('{{ start }}'::DATE, '{{ end }}'::DATE, INTERVAL '1 day') t(date_value)
{% endmacro %}
```

Used:
```sql
SELECT * FROM ({{ date_range('2024-01-01', '2024-12-31') }})
```

Jinja engine is identical to dbt's. Existing dbt projects can be dropped in nearly unchanged.

---

## 7. Connection Definitions

`connections/<name>.yaml` — definition without secrets.

```yaml
# connections/postgres.yaml
name: prod-db
type: postgres
host: ${POSTGRES_HOST}
port: 5432
database: app
user: nucleus_reader
password: ${POSTGRES_PASSWORD}
schema_filter: ["public", "analytics"]
```

Secrets via `${VAR}` substitution from:
1. `.env` file (dev only, gitignored)
2. OS keychain / env vars (CI/CD)
3. `secrets` module (production, when enabled)

Never inline secrets. Ever.

---

## 8. Testing Strategy

### 8.1 Unit tests for asset logic

```python
# tests/test_orders.py
import polars as pl
from nucleus.testing import TestContext
from assets.fact.orders import orders


def test_orders_filters_to_completed():
    ctx = TestContext(
        reads={
            "raw.orders": pl.DataFrame({
                "order_id": [1, 2, 3],
                "status": ["completed", "pending", "completed"],
                "customer_id": [10, 20, 30],
                "amount": [100, 50, 75],
                "date": ["2024-01-01"] * 3,
            }),
            "dim.customers": pl.DataFrame({
                "customer_id": [10, 20, 30],
                "country": ["US", "EU", "VN"],
            }),
        }
    )
    result = orders(ctx)
    assert result.height == 2
    assert set(result["order_id"]) == {1, 3}
```

`nucleus.testing.TestContext` is provided by the SDK. No Iceberg/Dagster/DB needed for unit tests.

### 8.2 Integration tests

```bash
nucleus test                        # run all asset checks against dev env
nucleus test fact.orders            # one asset
nucleus test --contract-only        # contracts only
```

---

## 9. The `.gitignore`

Standard for every Nucleus project:

```gitignore
# Local state
.nucleus/
*.duckdb
*.db-journal

# Secrets
.env
.env.local
*.pem
*.key

# Python
__pycache__/
*.pyc
.venv/
.uv-cache/

# IDE
.vscode/settings.json
.idea/

# OS
.DS_Store
Thumbs.db
```

---

## 10. Git Conventions

### 10.1 Branching

| Branch | Purpose |
|---|---|
| `main` | Production deployable |
| `dev/<feature>` | Active development |
| `hotfix/<issue>` | Production fix |

### 10.2 Commits

Asset changes should be **atomic per asset** when possible. Mixing 20 asset changes in one commit makes lineage diffs impossible.

### 10.3 PR conventions

Every PR touching `assets/` must include:
- Asset name in title: `[fact.orders] Add country filter`
- Description of business reason
- Updated tests if logic changed
- Updated contract if schema changed

---

## 11. `nucleus init` — Project Scaffolding

```bash
nucleus init my-project --template=basic
```

Templates:

| Template | Contents |
|---|---|
| `basic` | Minimal: one source, one transform, one analytic |
| `medallion` | Bronze/Silver/Gold structure |
| `dbt-migrate` | Includes dbt → nucleus migration helpers |
| `enterprise` | Full setup with auth + obs modules pre-enabled |

Generated files include filled-in examples, not empty stubs.

---

## 12. Anti-Patterns (Forbidden)

| Pattern | Why bad |
|---|---|
| Mixing notebook code (`*.ipynb`) into `assets/` | Asset definitions must be `.py` |
| Reading from raw `s3://...` in user code | Bypasses lineage |
| Defining same asset twice | Ambiguous truth |
| Hardcoding env-specific values in code | Breaks env portability |
| Circular cross-file imports between asset files | Refactor; assets should be flat |
| `from assets.foo import bar` and calling `bar(ctx)` directly | Use `ctx.read("foo.bar")` instead |
| Editing `.nucleus/` directly | Internal state; touch via CLI only |

---

## 13. The Project Promise

If a user follows this layout, the platform promises:

1. **`nucleus up`** boots their project in <30s
2. **`nucleus build`** materializes every asset
3. **`nucleus deploy --env prod`** ships byte-identical code to production
4. **Portal automatically discovers** every asset, contract, check, schedule
5. **CI works out of the box** via standard pytest + `nucleus test`
6. **Migrations between Nucleus versions** require zero code changes (only `nucleus.yaml` version bump)

These six are the user-facing return on the convention tax.

---

*Convention is composability. Standardize ruthlessly.*
