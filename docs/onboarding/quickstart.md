# Quickstart (about 5 minutes)

This path is for **small product engineering teams** (on the order of five people) with **roughly 100GB–5TB** of greenfield data who want a **BI-ready Iceberg-backed asset** quickly.

## What you need

- **Python 3.11** (primary tested interpreter)
- **Docker Desktop** (optional for MinIO; filesystem catalog still works for many SQLite paths)
- **About five minutes** for this slice — the full **under 30 minutes** target assumes real sources, credentials, and reading once

## What you will have afterward

- A **generated project** from `nucleus init`
- A running **local stack** from `nucleus up` (when Docker + compose are available)
- At least one **materialized asset** and a **query** result against the warehouse

## 1. Install

Public release path, after the `v0.2.0` PyPI workflow is green:

```bash
pip install nucleus
nucleus version
```

Pre-PyPI or contributor path:

```bash
git clone https://github.com/nucleus-data/nucleus.git
cd nucleus
python3.11 -m venv .venv
```

Activate the venv (Windows PowerShell: `.\.venv\Scripts\Activate.ps1`), then:

```bash
pip install -e ".[dev]"
```

**Expected:** `nucleus version` prints Nucleus plus pinned dependency versions without errors.

## 2. Scaffold and boot

```bash
nucleus init beachhead-demo
cd beachhead-demo
nucleus up
```

**Expected (shape, not exact wording):** readiness lines for optional MinIO, filesystem catalog, and definitions discovery, then a line like `Nucleus up in …s`.

`nucleus up` uses the `docker-compose.yaml` in the project directory (not `docker-compose.minio.yml`).

## 3. Materialize the starter asset

```bash
nucleus run example.greeting
```

**Expected:** a success summary with `example.greeting` and a non-zero row count once Iceberg commits.

## 4. Query through Jinja `ref`

```bash
nucleus query "SELECT * FROM {{ ref('example.greeting') }} LIMIT 5"
```

**Expected:** a small table with columns `name` and `value` (or JSON lines if stdout is not a TTY and JSON mode is selected).

## 5. Optional: ingest SQLite into a `raw.*` asset

Create any SQLite file (or reuse one you already trust), then:

```bash
nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
nucleus query "SELECT count(*) AS n FROM {{ ref('raw.orders') }}"
```

**Expected:** row count echoed after ingest; `nucleus query` prints `n` matching that count.

URI spelling matters on Windows — prefer absolute paths if relative URLs confuse the shell.

## 6. Tear down

```bash
nucleus down
cd ..
```

**Expected:** confirmation that local containers stopped and volumes were preserved unless you passed `--volumes` (run `nucleus down` from the project directory that contains `nucleus_project.yaml`).

## Python API (same building blocks)

```python
from pathlib import Path

import nucleus.ctx as ctx

warehouse_dir = str(Path("./data/warehouse").resolve())
rows = ctx.copy_from(
    "sqlite:///./data/orders.db",
    table="orders",
    target="raw.orders",
    warehouse_dir=warehouse_dir,
)
df = ctx.sql(
    "SELECT * FROM {{ ref('raw.orders') }} LIMIT 10",
    warehouse_dir=warehouse_dir,
).collect()
```

Use `nucleus --help` and the Markdown specs at the repo root when you need flag-level detail.

## Contracts (`@nucleus.check`)

Checks are **zero-argument** functions registered with `@nucleus.check("schema.asset")` that return `CheckResult`. They run **after** the asset materializes. See any file under `examples/01-ecommerce-elt/checks/` for ready-made patterns.

## Deferred (not in v0.1)

- `ctx.write`, `ctx.log`, `ctx.params` — use asset return values, stdlib `logging`, and project config instead.
- **Workbench**, **Copilot chat**, **column-level lineage**, hosted Iceberg REST catalogs — later milestones on the public roadmap.

## Next step

Work through **`examples/01-ecommerce-elt/`** for Postgres + SQLite + Iceberg layers you can adapt quickly — see that directory’s `README.md`.

---

[← Onboarding index](./README.md) · [Recipes →](../recipes/)
