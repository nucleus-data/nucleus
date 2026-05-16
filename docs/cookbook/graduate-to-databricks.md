---
title: Graduate to Databricks
description: Step-by-step recipe for moving a Nucleus-managed Iceberg lakehouse to Databricks Unity Catalog without re-platforming the data.
---

# Graduate to Databricks

> Architectural intent: `docs/specs/nucleus_architecture_v4.1.md` section 10 (Yield-to-Giants Strategy) and `AGENTS.md` section 4 (Do-Not-Build list). Graduation is by design, not a retreat. Iceberg is a portable open standard, so the data you wrote with Nucleus is the same data Databricks will read.

This cookbook is the practical answer to the question:

> "I have a Nucleus-managed Iceberg lakehouse on S3 and I want my pipelines to run on Databricks. What do I actually do?"

It is a path, not a battle-tested runbook. Section 9 (Honest caveats) lists exactly what is and is not validated.

---

## 1. When you should graduate

Nucleus is designed for the beachhead persona in `docs/specs/nucleus_architecture_v4.1.md` section 1.5: a startup data team of 5-20 engineers, 100 GB to 5 TB of total data, a greenfield project, MacBook or Linux laptops as the daily drivers. If you outgrow any of the following thresholds, graduating to Databricks (or another cloud-scale Iceberg-aware engine) is the right move:

| Trigger | Why it fires graduation |
|---|---|
| A single Iceberg asset crosses 10 TB | Single-node DuckDB and Polars become I/O-bound; a distributed engine wins. |
| The data team grows past 50 engineers | Nucleus has no native multi-tenant control plane (out-of-scope per `docs/specs/nucleus_architecture_v4.1.md` section 20.3). |
| Regulated workload requires SOC 2 / HIPAA / column masking GA today | Nucleus row and column policies arrive in v1.5+ (see `docs/specs/nucleus_vs_databricks.md` section 7). |
| GPU-backed ML training pipelines need to live next to the warehouse | Nucleus is deliberately not an ML platform (`docs/specs/nucleus_architecture_v4.1.md` section 20.1). |
| 24x7 streaming ingest at multi-million events per second | Nucleus streaming arrives in v1.5+ via Benthos / Redpanda; Databricks Structured Streaming is GA today. |

If none of those apply, stay on Nucleus. The 30-minute-from-clone beachhead promise (`docs/specs/nucleus_architecture_v4.1.md` section 1.5) only holds while the workload fits the beachhead.

---

## 2. What graduates with you, and what does not

Graduation moves the data and the contract; it does not move the Nucleus build-time machinery, because Databricks already has its own equivalents.

| Travels to Databricks | Stays behind (rebuild on the other side) |
|---|---|
| Apache Iceberg snapshots and Parquet files in your S3 bucket | The Nucleus CLI (`nucleus up`, `nucleus run`) - replaced by Databricks Workspace and Lakeflow Jobs |
| Iceberg snapshot lineage, schema evolution, partition spec | The Asset Materialization Adapter (`src/nucleus/coordination/`) - replaced by Lakeflow Spark Declarative Pipelines |
| `@nucleus.contract` schema definitions (translatable to Delta Live Tables Expectations) | The Workbench web IDE - use Databricks Notebooks |
| The 24 stable error codes (NE1xxx-NE5xxx, ADR-006) - keep for any code you keep on Nucleus side | The Nucleus error translation layer - Databricks errors surface natively |
| Asset-level OpenLineage events you have already emitted (Tier 0 immortal per `docs/specs/nucleus_architecture_v4.1.md` section 4.1) | The Nucleus filesystem catalog - you switch to Unity Catalog or a Unity-federated Iceberg REST endpoint |

The contract surface that survives is the open-format substrate: Iceberg + Parquet + S3 + OpenLineage. Everything Nucleus-proprietary is by design under 30K LOC and is replaceable on the Databricks side.

---

## 3. Step 1 - Register your Iceberg lakehouse with Unity Catalog

Databricks Unity Catalog supports reading externally-managed Iceberg tables. As of 2026, the supported integration paths are:

1. **Foreign catalog (Lakehouse Federation)** - Unity Catalog points at an external Iceberg REST catalog (Lakekeeper, Polaris, AWS Glue, Snowflake Open Catalog) and surfaces those tables read-only inside Unity Catalog.
2. **Managed Iceberg tables** - Unity Catalog itself becomes the Iceberg catalog of record; Databricks can read and write.
3. **Foreign tables (per-table registration)** - register individual external Iceberg tables one by one.

Pick path 1 or 3 first; path 2 requires a fuller hand-off where Databricks owns commits.

### Path 1: Foreign catalog via Lakehouse Federation

When you ran `nucleus enable lakekeeper` (per ADR-004, available v0.3+), your Iceberg tables already sit behind a REST catalog endpoint. Register that endpoint as a foreign catalog in Unity Catalog. The exact SQL surface evolves; the canonical reference is the Databricks Lakehouse Federation documentation.

```sql
-- Reference: https://docs.databricks.com/aws/en/query-federation/index.html
-- NEEDS VERIFICATION against the connector list in Databricks 2026.x:
-- exact CONNECTION TYPE for an Iceberg REST endpoint may be `iceberg`,
-- `iceberg_rest`, or vendor-specific (lakekeeper / polaris / unity).
CREATE CONNECTION my_nucleus_lake
  TYPE iceberg
  OPTIONS (
    uri 'https://lakekeeper.my-company.com/v1',
    warehouse 'main',
    token secret('lakekeeper_creds', 'token')
  );

CREATE FOREIGN CATALOG nucleus_lake
  USING CONNECTION my_nucleus_lake;
```

The `CREATE CONNECTION` and `CREATE FOREIGN CATALOG` SQL is documented under Lakehouse Federation: <https://docs.databricks.com/aws/en/query-federation/index.html>.

### Path 3: Per-table foreign Iceberg registration

If you stayed on the Nucleus filesystem catalog (v0.1 default, supported indefinitely per ADR-004), each Iceberg table can still be registered one by one by pointing Unity Catalog at the table's metadata.json location.

```sql
-- Reference: https://docs.databricks.com/aws/en/external-data/iceberg/
-- NEEDS VERIFICATION: USING ICEBERG with explicit metadata_location is
-- supported on Databricks Runtime 14.3 LTS and later; verify your cluster.
CREATE TABLE nucleus_lake.sales.daily_revenue
  USING ICEBERG
  LOCATION 's3://my-prod-bucket/warehouse/sales.daily_revenue/'
  TBLPROPERTIES (
    'metadata_location' = 's3://my-prod-bucket/warehouse/sales.daily_revenue/metadata/v0042.metadata.json'
  );
```

Repeat per table, or script the loop using the Nucleus catalog inventory:

```bash
nucleus list --output json --field "table,storage.location,metadata.current_metadata_location" \
  | jq -r '.[] | "\(.table)\t\(.storage.location)\t\(.metadata.current_metadata_location)"'
```

---

## 4. Step 2 - Verify read access

Before you change anything else, prove that Databricks can read the data Nucleus wrote.

```sql
-- In Databricks SQL editor or a notebook attached to a Unity-enabled cluster.
SELECT COUNT(*) AS row_count, MAX(snapshot_id) AS latest_snapshot
  FROM nucleus_lake.sales.daily_revenue;

-- Sanity-check schema evolution survived the hand-off.
DESCRIBE EXTENDED nucleus_lake.sales.daily_revenue;
```

Then run the same query on Nucleus side and diff:

```bash
nucleus query "SELECT COUNT(*) AS row_count FROM {{ ref('sales.daily_revenue') }}"
```

The two row counts should match exactly. If they do not, do not proceed - your Lakehouse Federation connection is not seeing the same Iceberg snapshot. Common causes: stale metadata pointer, S3 bucket policy not granting Databricks read access, or the foreign catalog pointing at an older catalog snapshot.

---

## 5. Step 3 - Move scheduling

Nucleus uses an embedded Dagster scheduler (hidden behind `@nucleus.asset(schedule=...)` per `docs/specs/nucleus_architecture_v4.1.md` section 6). On Databricks the equivalent surface is **Lakeflow Jobs** (the GA name for Databricks Workflows; reference: <https://docs.databricks.com/aws/en/workflows/index.html>).

The mapping is one-to-one:

| Nucleus declaration | Databricks equivalent |
|---|---|
| `@nucleus.asset(schedule="@daily")` | Lakeflow Job task with cron trigger `0 0 * * *` |
| `@nucleus.asset(deps=["bronze.x"])` | Task `depends_on: [bronze_x_task]` in the job spec |
| `@nucleus.check(...)` | Lakeflow Spark Declarative Pipelines `EXPECT` clause, or a separate quality task |
| `@nucleus.sensor(...)` (v0.3+) | File-arrival trigger or table-update trigger in Lakeflow Jobs |
| `nucleus run my.asset` | `databricks jobs run-now --job-id ...` |

Two practical patterns:

1. **Lift-and-shift**: rewrite each asset's Python body inside a Databricks Notebook task; one notebook per asset; wire dependencies with `depends_on`. Quickest to land, slowest to maintain long-term.
2. **Declarative pipelines**: rewrite SQL assets as Lakeflow Spark Declarative Pipelines (formerly DLT, see <https://docs.databricks.com/aws/en/dlt/index.html>). More idiomatic Databricks, more work upfront.

If your team uses Airflow already, point Cloud Composer or self-hosted Airflow at Databricks via the `DatabricksSubmitRunOperator` (reference: <https://airflow.apache.org/docs/apache-airflow-providers-databricks/stable/operators/submit_run.html>) and skip Lakeflow Jobs entirely.

---

## 6. Step 4 - Move compute

Nucleus runs Polars in-process (`docs/specs/nucleus_architecture_v4.1.md` section 5.2) and DuckDB in-process (section 5.1). Databricks runs PySpark on a JVM. The compute primitives differ.

Three porting strategies, in order of effort:

### 6a. Single-node compute (cheapest)

For workloads under roughly 100 GB you can keep using Polars and DuckDB on Databricks single-node clusters. Both are pure Python and both are pip-installable on Databricks runtimes 14.3 LTS and later. Reference: <https://docs.databricks.com/aws/en/compute/single-node.html>.

```python
# Inside a Databricks notebook attached to a single-node cluster.
import polars as pl
# Docs: https://docs.pola.rs/api/python/stable/reference/io.html
df = pl.scan_iceberg(
    "s3://my-prod-bucket/warehouse/sales.daily_revenue/metadata/v0042.metadata.json",
    storage_options={"region": "us-east-1"},
).collect()
```

This keeps your asset code byte-identical with the Nucleus version. You give up Spark's distribution but gain a smooth landing on Databricks.

### 6b. PySpark refactor (idiomatic)

For workloads above a few hundred GB, rewrite the hot Polars paths in PySpark. The mapping is mechanical:

| Polars | PySpark equivalent |
|---|---|
| `pl.scan_iceberg(path).filter(...).select(...)` | `spark.read.format("iceberg").load(path).filter(...).select(...)` |
| `df.with_columns(pl.col("x").rank().over("y"))` | `df.withColumn("rank", F.rank().over(Window.partitionBy("y")))` |
| `df.write_iceberg(table, mode="append")` | `df.writeTo(table).append()` (Spark 3.4+ DataFrameWriterV2) |

Reference: <https://docs.databricks.com/aws/en/dataframes/index.html>.

### 6c. SQL-only

If your assets are mostly `@nucleus.sql_asset`, the SQL itself often runs unchanged on Databricks SQL Warehouses, because both DuckDB and Spark SQL are ANSI-leaning. Validate with the smallest table first; watch for `STRUCT` column access syntax differences.

---

## 7. Step 5 - Decommission Nucleus

When you have run a quarter of parallel materializations (Nucleus and Databricks side by side, comparing row counts and checksums), retire the Nucleus side.

| Keep | Discard |
|---|---|
| The Iceberg snapshots and Parquet files in S3 - they ARE the data | The local `.nucleus/` directory (filesystem catalog, run ledger) |
| Your `nucleus_project.yaml` (kept for audit and historical reproducibility) | The `docker-compose.yml` for MinIO and Lakekeeper if Databricks now serves them |
| Any `@nucleus.contract` schemas - port them to Lakeflow Spark Declarative Pipelines `EXPECT` | The Nucleus virtualenv on engineer laptops |
| Asset-level OpenLineage events already emitted to your lineage backend | The Nucleus Workbench (`localhost:8765`) |

Do NOT delete S3 buckets, do NOT touch Iceberg `metadata/` directories, do NOT run `VACUUM` or `OPTIMIZE` on the Nucleus side after the cutover. Snapshot lineage is the only history you have until Databricks accumulates its own.

---

## 8. Hybrid mode (Mode 2 territory)

Many teams do not graduate fully; they keep Nucleus as the development environment and use Databricks only for the heavy production workloads. This is **Mode 2 of the yield-to-giants strategy** (`docs/specs/nucleus_architecture_v4.1.md` section 10.2). The user-visible API is intended to be:

```python
# Implementation arrives v0.3+ per ADR-041 (currently PROPOSED).
# The architecture's original v1.5+ target is being pulled forward by ADR-041.
@nucleus.asset(compute="databricks://my-workspace/my-warehouse")
def heavy_aggregation(ctx) -> Asset:
    return ctx.sql("SELECT ... 100M rows ...")
```

Until the dispatch decorator ships, the manual hybrid recipe is:

1. Develop and test the asset locally with Polars or DuckDB.
2. When ready for production, copy the SQL into a Databricks job and run it on a SQL Warehouse.
3. Point both runtimes at the same S3 bucket and same Iceberg catalog endpoint, so the snapshots commit to the same physical lake.

The full design is in `docs/decisions/ADR-041-mode-2-hybrid-compute-dispatch.md` (PROPOSED).

---

## 9. Honest caveats - what this cookbook does NOT yet validate

Per `docs/internal/research/parity_vs_databricks_snowflake.md` section 1, Iceberg portability between Nucleus and Databricks is documented but not yet field-tested. Treat the following as known unknowns:

1. **No end-to-end test in CI today.** No Nucleus CI job spins up a Databricks workspace and asserts that a Nucleus-written Iceberg snapshot reads cleanly through Lakehouse Federation. PoC #5 external testers are the first verification path. Tracked in `docs/release/public_demo_deploy_plan.md`.
2. **Iceberg spec version mismatch is possible.** Nucleus pins `pyiceberg` (see `pyproject.toml` and `docs/compatibility.md`). Databricks runtime ships its own Iceberg reader. If you are on Iceberg spec v3 features (deletion vectors, equality deletes), verify Databricks runtime support before relying on them.
3. **Foreign catalog SQL syntax drift.** The `CREATE CONNECTION` / `CREATE FOREIGN CATALOG` snippets above are illustrative and marked NEEDS VERIFICATION. Re-check against <https://docs.databricks.com/aws/en/query-federation/index.html> before pasting into a production console.
4. **Permission propagation.** Nucleus has no RBAC layer in v0.2 (per `AGENTS.md` section 4 do-not-build list). Once Unity Catalog owns the tables, all access is governed by Databricks. Do NOT assume any Nucleus-side ACL semantics carry over.
5. **OpenLineage events.** Nucleus emits OpenLineage events to a NDJSON FileTransport by default. Wiring those to Databricks' Unity Catalog lineage requires a separate ingestion step (an OpenLineage HTTP transport pointed at a collector). Not yet documented end-to-end.
6. **Cost estimation.** Once compute moves to Databricks, the per-asset cost meter (`docs/specs/nucleus_architecture_v4.1.md` section 7.5, v0.7+) does not see remote runs. Use Databricks System Tables for cost attribution.

If you hit any of the above, file an issue on <https://github.com/nucleus-data/nucleus/issues> with the prefix `[graduation]` so PoC #5 telemetry can pick it up.

---

## Related documents

- `docs/cookbook/graduate-to-snowflake.md` - sibling recipe for Snowflake.
- `docs/cookbook/graduate-to-bigquery.md` - sibling recipe for BigQuery.
- `docs/decisions/ADR-041-mode-2-hybrid-compute-dispatch.md` - the design spec for the `compute=` decorator that automates Mode 2.
- `docs/internal/research/parity_vs_databricks_snowflake.md` - the honest capability matrix that motivated this cookbook.
- `docs/specs/nucleus_architecture_v4.1.md` section 10 - the canonical Yield-to-Giants Strategy.
- `docs/specs/nucleus_vs_databricks.md` - the full Nucleus-vs-Databricks feature mapping.

## External references (verified URL form, content NEEDS VERIFICATION at integration time)

- Databricks Unity Catalog: <https://docs.databricks.com/aws/en/data-governance/unity-catalog/index.html>
- Databricks Lakehouse Federation: <https://docs.databricks.com/aws/en/query-federation/index.html>
- Databricks external Iceberg tables: <https://docs.databricks.com/aws/en/external-data/iceberg/>
- Databricks Lakeflow Jobs (Workflows): <https://docs.databricks.com/aws/en/workflows/index.html>
- Databricks Lakeflow Spark Declarative Pipelines (DLT): <https://docs.databricks.com/aws/en/dlt/index.html>
- Databricks DataFrames: <https://docs.databricks.com/aws/en/dataframes/index.html>
- Databricks single-node clusters: <https://docs.databricks.com/aws/en/compute/single-node.html>
- Polars Iceberg I/O: <https://docs.pola.rs/api/python/stable/reference/io.html>
- Apache Iceberg spec: <https://iceberg.apache.org/spec/>

*Last revised 2026-05-15. Re-verify the Databricks SQL syntax before any production cutover; the Iceberg substrate is stable but the Lakehouse Federation surface is the part most likely to drift.*
