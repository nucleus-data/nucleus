---
title: Multi-Tenant Projects
description: Isolate data by tenant within a single Nucleus project using namespace conventions.
---

# Multi-Tenant Projects

For SaaS products where each customer's data must be isolated, Nucleus supports tenant namespacing via asset key conventions and optional catalog separation.

## Pattern 1 — Namespace per tenant

Use tenant IDs as the namespace in asset keys:

```python
import nucleus
import polars as pl


def make_tenant_asset(tenant_id: str):
    @nucleus.asset(
        table=f"tenant_{tenant_id}.orders",
        tags=["tenant", tenant_id],
    )
    def tenant_orders(ctx) -> pl.DataFrame:
        return ctx.copy_from(
            f"postgres://user:pass@host/tenant_{tenant_id}",
            table="public.orders",
            target=f"tenant_{tenant_id}.orders",
        )
    tenant_orders.__name__ = f"orders_{tenant_id}"
    return tenant_orders


# Register for each tenant
tenant_ids = ["acme", "globex", "initech"]
assets = [make_tenant_asset(tid) for tid in tenant_ids]
```

## Pattern 2 — Row-level tenant partitioning

Single Iceberg table with a `tenant_id` column:

```python
@nucleus.asset(
    table="raw.all_orders",
    partitions=nucleus.identity("tenant_id"),
    schedule="@hourly",
)
def all_orders(ctx) -> pl.DataFrame:
    # Merge all tenants into one partitioned table
    frames = []
    for tenant_id in ["acme", "globex", "initech"]:
        df = ctx.copy_from(
            f"postgres://user:pass@host/tenant_{tenant_id}",
            table="public.orders",
            target=f"raw.all_orders",
        )
        frames.append(df.with_columns(pl.lit(tenant_id).alias("tenant_id")))
    return pl.concat(frames)
```

Query for a specific tenant:

```bash
nucleus query "SELECT * FROM {{ ref('raw.all_orders') }} WHERE tenant_id = 'acme' LIMIT 100"
```

## Pattern 3 — Catalog per tenant (v0.3+)

Separate catalogs provide the strongest isolation:

```yaml
# nucleus_project.yaml
catalogs:
  acme:
    type: lakekeeper
    endpoint: http://catalog-acme:8181
  globex:
    type: lakekeeper
    endpoint: http://catalog-globex:8181
```

```python
@nucleus.asset(table="orders", catalog="acme")
def acme_orders(ctx) -> pl.DataFrame:
    ...
```

## Access control (v0.3+)

OIDC-backed RBAC at the catalog level controls which users can see which tenant's data. See [ADR-010: OIDC delegation policy](../governance/architecture-decisions.md).
