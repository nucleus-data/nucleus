---
title: Lineage
description: How Nucleus tracks asset dependencies and emits OpenLineage events.
---

# Lineage

**Lineage** in Nucleus is the dependency graph between assets — what data flows from where, through which transforms, to which outputs. It is powered by [OpenLineage](https://openlineage.io/) at the event-transport level.

## Asset-level lineage (v0.1)

Every materialization emits an OpenLineage `RunEvent` to the local file transport:

```json
{
  "eventType": "COMPLETE",
  "run": { "runId": "..." },
  "job": { "namespace": "nucleus", "name": "analytics.daily_revenue" },
  "inputs": [
    { "namespace": "nucleus", "name": "staging.orders" }
  ],
  "outputs": [
    { "namespace": "nucleus", "name": "analytics.daily_revenue" }
  ]
}
```

This is **asset-level lineage** — what assets produced which other assets. Column-level lineage (which SQL columns map to which output columns) requires `nucleus[lineage-advanced]` and is deferred to v0.5+.

## How dependencies are detected

Dependencies can be:

1. **Explicit** — `deps=["staging.orders"]` in the decorator
2. **Auto-derived** — Nucleus detects `ctx.read("staging.orders")` calls

For SQL assets, sqlglot (v0.5+) parses `{{ ref('staging.orders') }}` references to extract column-level lineage.

## Viewing lineage

```bash
# v0.3+
nucleus lineage show analytics.daily_revenue
nucleus lineage upstream analytics.daily_revenue
nucleus lineage downstream raw.orders
```

The Workbench (v0.2+) renders the full asset graph as an interactive DAG.

## OpenLineage transport

Events go to:

| v0.1 | File transport — `.nucleus/lineage/` directory |
| v0.3+ | HTTP transport to Marquez or any OpenLineage-compatible backend |

Enable HTTP transport:

```bash
nucleus enable marquez
```

Or configure directly in `nucleus_project.yaml`:

```yaml
lineage:
  transport: http
  endpoint: http://localhost:5000/api/v1/lineage
```

## Column-level lineage (v0.5+)

Column-level lineage traces how individual columns flow through SQL transforms. Requires sqlglot for SQL parsing and Python source analysis.

```python
# v0.5+ example — auto-derived from SQL
@nucleus.sql_asset(table="analytics.revenue_summary")
def revenue_summary(ctx) -> str:
    return """
        SELECT
            order_date,
            SUM(amount) AS total_revenue    -- lineage: raw.orders.amount
        FROM {{ ref('staging.orders') }}
        GROUP BY 1
    """
```

## Related

- [OpenLineage spec](https://openlineage.io/spec/1-0-5/OpenLineage.json)
- [ADR-009: OpenLineage event schema policy](../governance/architecture-decisions.md)
