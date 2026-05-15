---
title: Catalog
description: The metadata store that tracks all assets, their Iceberg tables, and schema evolution history.
---

# Catalog

The **catalog** is the metadata store that tracks all Iceberg tables — their schemas, partition specs, snapshot history, and properties. In Nucleus, the catalog is the bridge between your asset definitions and the underlying Parquet files in the object store.

## v0.1: Filesystem catalog

In v0.1, Nucleus uses pyiceberg's `SqlCatalog` backed by SQLite. This runs entirely on disk — no external service, no network dependency.

```
data/
├── catalog.db         # SQLite database: table metadata
└── warehouse/         # Iceberg table data (Parquet + manifests)
    ├── raw.orders/
    │   ├── metadata/
    │   └── data/
    └── analytics.daily_revenue/
        ├── metadata/
        └── data/
```

The filesystem catalog is:
- **Local-first** — works on a laptop with no network
- **Portable** — Iceberg metadata format is open standard
- **Sufficient** — handles single-node workloads indefinitely

## v0.3+: REST catalogs

At v0.3, Nucleus supports REST-based catalogs via `pyiceberg.RestCatalog`:

| Catalog | Language | When to use |
|---------|----------|-------------|
| **Lakekeeper** (default) | Rust | Low memory (~100-300 MB idle), fast cold start, OIDC-validation-only |
| **Apache Polaris** (alternate) | JVM | ASF TLP governance, native federation to Databricks/Snowflake/Glue |

Both expose identical `RestCatalog` API via pyiceberg. Your asset code doesn't change. See [Catalog Migration (ADR-004)](../governance/architecture-decisions.md).

```bash
# Migrate filesystem catalog to Lakekeeper
nucleus catalog migrate --to lakekeeper

# Enable Apache Polaris (requires JVM)
nucleus enable polaris
nucleus catalog migrate --to polaris
```

## Catalog migration

The v0.1 filesystem catalog migrates to REST cleanly:

1. The Parquet data in `data/warehouse/` is untouched
2. Nucleus re-registers each table's metadata in the new catalog
3. Existing Iceberg snapshots are immediately readable from the new catalog

Your BI tools and downstream consumers don't need to change their connection strings — Iceberg portability handles it.

## Multiple catalogs (v0.3+)

In multi-team setups, different catalogs can serve different asset namespaces:

```yaml
# nucleus_project.yaml
catalogs:
  default:
    type: lakekeeper
    endpoint: http://catalog:8181
  legacy:
    type: filesystem
    warehouse: ./data/warehouse_legacy
```

## Querying catalog metadata

```python
# List all registered tables
tables = ctx.catalog.list_tables()

# Get schema for an asset
schema = ctx.catalog.get_schema("analytics.daily_revenue")

# List snapshots
snapshots = ctx.catalog.list_snapshots("analytics.daily_revenue")
```
