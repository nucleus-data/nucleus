---
title: Graduate to Snowflake
description: Step-by-step recipe for moving a Nucleus-managed Iceberg lakehouse to Snowflake using the Iceberg Tables feature, without re-platforming the data.
---

# Graduate to Snowflake

> Architectural intent: `docs/specs/nucleus_architecture_v4.1.md` section 10 (Yield-to-Giants Strategy) and `AGENTS.md` section 4 (Do-Not-Build list). Iceberg is a portable open standard, so the snapshots Nucleus committed are the same snapshots Snowflake will read.

This cookbook is the practical answer to:

> "I have a Nucleus-managed Iceberg lakehouse on S3 and I want my analytics to run on Snowflake. What do I actually do?"

It is a path, not a battle-tested runbook. Section 6 (Honest caveats) lists exactly what is and is not validated.

The Snowflake side leans on **Iceberg Tables**, GA since 2024 and steadily extended through 2026 (per Snowflake's release notes). Reference: <https://docs.snowflake.com/en/user-guide/tables-iceberg>.

---

## 1. When you should graduate

Nucleus serves the beachhead persona in `docs/specs/nucleus_architecture_v4.1.md` section 1.5: a startup data team of 5-20 engineers, 100 GB to 5 TB of total data, greenfield, laptop-first. Graduate to Snowflake when one of the following fires:

| Trigger | Why it fires graduation |
|---|---|
| Single asset crosses 10 TB or query latency on it crosses 30 s on a beefy laptop | Snowflake Virtual Warehouses scale horizontally and elastically; DuckDB on one node does not. |
| Data team grows past 50 engineers | Snowflake roles, masking policies, and account-level governance become net-positive overhead; Nucleus has no native RBAC layer in v0.2. |
| Compliance program requires SOC 2 Type II / HIPAA / PCI today | Snowflake ships these certifications; Nucleus targets them only at v1.5+. |
| The org runs Cortex ML, Snowpark ML, or Streamlit-in-Snowflake apps | Nucleus is deliberately not an ML platform (`docs/specs/nucleus_architecture_v4.1.md` section 20.1). |
| You want zero-copy clones (`CLONE`) for cheap branch-style experimentation | Snowflake's metadata-only clone is GA today; Nucleus equivalents arrive v0.5+. |

If none of these apply, stay on Nucleus and keep the 30-minute beachhead promise (`docs/specs/nucleus_architecture_v4.1.md` section 1.5).

---

## 2. What graduates with you, and what does not

| Travels to Snowflake | Stays behind (rebuild on the other side) |
|---|---|
| Apache Iceberg snapshots and Parquet files in your S3 bucket | The Nucleus CLI - replaced by the Snowsight UI and SnowSQL |
| Iceberg snapshot lineage, schema evolution, partition spec | The Asset Materialization Adapter - replaced by Snowflake Tasks + Dynamic Tables |
| `@nucleus.contract` schema definitions (translatable to Snowflake `NOT NULL`, `CHECK`, masking policies) | Nucleus Workbench (`localhost:8765`) - use Snowsight worksheets |
| OpenLineage events already emitted (Tier 0 immortal per `docs/specs/nucleus_architecture_v4.1.md` section 4.1) | Nucleus filesystem catalog - swap for Snowflake's native Iceberg catalog or Snowflake Open Catalog (Apache Polaris) |
| Stable error codes (NE1xxx-NE5xxx, ADR-006) - keep for whatever Nucleus you keep | The Nucleus error translation layer - Snowflake errors surface natively |

The contract surface that survives is the open-format substrate: Iceberg + Parquet + S3 + OpenLineage. Everything Nucleus-proprietary is replaceable on the Snowflake side.

---

## 3. Step 1 - Register your Iceberg lakehouse with Snowflake

Snowflake supports two Iceberg integration modes (see <https://docs.snowflake.com/en/user-guide/tables-iceberg>):

- **Snowflake-managed Iceberg tables**: Snowflake owns the catalog and the metadata; the engine reads and writes.
- **Externally-managed Iceberg tables**: an external catalog (AWS Glue, Snowflake Open Catalog / Apache Polaris, Lakekeeper, an Iceberg REST endpoint, or a metadata.json on object storage) owns the catalog; Snowflake reads only.

For graduation from Nucleus, externally-managed is the natural starting point - your Iceberg metadata lives where Nucleus put it, and you avoid double-bookkeeping.

### 3a. Create an external volume (S3 access)

```sql
-- Reference: https://docs.snowflake.com/en/sql-reference/sql/create-external-volume
-- NEEDS VERIFICATION: STORAGE_AWS_ROLE_ARN policy must allow Snowflake's
-- account ARN (returned by DESCRIBE EXTERNAL VOLUME). The trust setup
-- changes occasionally; re-check the docs before pasting.
CREATE EXTERNAL VOLUME nucleus_lake_volume
  STORAGE_LOCATIONS = (
    (
      NAME = 'us-east-1'
      STORAGE_PROVIDER = 'S3'
      STORAGE_BASE_URL = 's3://my-prod-bucket/warehouse/'
      STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::111122223333:role/snowflake-iceberg-role'
    )
  )
  ALLOW_WRITES = FALSE;  -- Snowflake will read only; Nucleus stays the writer.

DESCRIBE EXTERNAL VOLUME nucleus_lake_volume;
-- Copy the STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID into your
-- IAM role's trust policy, per the Snowflake setup guide above.
```

### 3b. Create a catalog integration

If your Nucleus side runs Lakekeeper or any Iceberg REST endpoint (`nucleus enable lakekeeper`, ADR-004, available v0.3+), use a REST catalog integration. Otherwise use an "object store" catalog that points at the metadata.json files directly.

```sql
-- Reference: https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration
-- REST endpoint variant (Lakekeeper / Polaris / vendor-managed REST):
CREATE CATALOG INTEGRATION nucleus_lake_catalog
  CATALOG_SOURCE = ICEBERG_REST
  TABLE_FORMAT = ICEBERG
  CATALOG_NAMESPACE = 'main'
  REST_CONFIG = (
    CATALOG_URI = 'https://lakekeeper.my-company.com/v1'
    WAREHOUSE = 'main'
  )
  REST_AUTHENTICATION = (
    TYPE = OAUTH
    OAUTH_TOKEN_URI = 'https://lakekeeper.my-company.com/v1/oauth/tokens'
    OAUTH_CLIENT_ID = '<client-id>'
    OAUTH_CLIENT_SECRET = '<from snowflake secret>'
    OAUTH_ALLOWED_SCOPES = ('catalog')
  )
  ENABLED = TRUE;

-- Object-store variant (Nucleus filesystem catalog v0.1, no REST):
-- NEEDS VERIFICATION: parameter names for OBJECT_STORE source vary by
-- Snowflake release; verify against the live page before applying.
CREATE CATALOG INTEGRATION nucleus_lake_catalog_objstore
  CATALOG_SOURCE = OBJECT_STORE
  TABLE_FORMAT = ICEBERG
  ENABLED = TRUE;
```

### 3c. Create the Iceberg table on Snowflake side

```sql
-- REST-catalog path:
CREATE ICEBERG TABLE sales_daily_revenue
  CATALOG = 'nucleus_lake_catalog'
  EXTERNAL_VOLUME = 'nucleus_lake_volume'
  CATALOG_NAMESPACE = 'sales'
  CATALOG_TABLE_NAME = 'daily_revenue';

-- Object-store path (point at metadata.json directly):
CREATE ICEBERG TABLE sales_daily_revenue_objstore
  CATALOG = 'nucleus_lake_catalog_objstore'
  EXTERNAL_VOLUME = 'nucleus_lake_volume'
  METADATA_FILE_PATH = 'sales.daily_revenue/metadata/v0042.metadata.json';
```

Repeat per table, or script the loop with the Nucleus catalog inventory:

```bash
nucleus list --output json --field "table,storage.location,metadata.current_metadata_location" \
  | jq -r '.[] | "CREATE ICEBERG TABLE \(.table | gsub("\\."; "_")) ... METADATA_FILE_PATH = \"\(.metadata.current_metadata_location | sub("^s3://[^/]+/"; ""))\";"'
```

---

## 4. Step 2 - Verify read access, then move scheduling and compute

### Verify

```sql
SELECT COUNT(*) AS row_count, MAX(snapshot_id) AS latest_snapshot
  FROM sales_daily_revenue;

DESCRIBE TABLE sales_daily_revenue;
```

Diff against Nucleus side:

```bash
nucleus query "SELECT COUNT(*) FROM {{ ref('sales.daily_revenue') }}"
```

If the row counts diverge, do not proceed - your catalog integration is not seeing the same Iceberg snapshot. Common causes: stale metadata pointer, S3 IAM role missing read permission for Snowflake's external user ARN, REST catalog token expired.

### Move scheduling

Nucleus uses an embedded Dagster scheduler (hidden behind `@nucleus.asset(schedule=...)`). On Snowflake the equivalent surfaces are **Tasks** and **Dynamic Tables** (reference: <https://docs.snowflake.com/en/user-guide/tasks-intro> and <https://docs.snowflake.com/en/user-guide/dynamic-tables-intro>).

| Nucleus declaration | Snowflake equivalent |
|---|---|
| `@nucleus.asset(schedule="@daily")` | `CREATE TASK ... SCHEDULE = 'USING CRON 0 0 * * * UTC'` |
| `@nucleus.asset(deps=["bronze.x"])` | `CREATE TASK ... AFTER bronze_x_task` (DAG of Tasks) |
| `@nucleus.asset(materialize="incremental")` | `CREATE DYNAMIC TABLE ... TARGET_LAG = '1 hour'` (incremental refresh, GA April 2026) |
| `@nucleus.check(...)` | Scheduled task running `ASSERT` queries, or `CONSTRAINT` clauses |
| `nucleus run my.asset` | `EXECUTE TASK my_task;` |

If your team uses Airflow, the `apache-airflow-providers-snowflake` package provides `SnowflakeOperator` for SQL and `SnowflakeSqlApiOperator` for the SQL API; reference: <https://airflow.apache.org/docs/apache-airflow-providers-snowflake/stable/operators/snowflake.html>.

### Move compute

Three porting strategies, in order of effort:

1. **SQL-only**: most `@nucleus.sql_asset` queries run unchanged on Snowflake. Both DuckDB and Snowflake SQL are ANSI-leaning. Watch for: half-open windows, qualified column references in `QUALIFY`, and DuckDB's `EXCLUDE` syntax (Snowflake supports it as of 2024).
2. **Snowpark Python**: keep your asset bodies in Python. Snowpark DataFrames are Snowflake's native Python engine and execute server-side. Reference: <https://docs.snowflake.com/en/developer-guide/snowpark/python/index>. Mapping:

   | Nucleus / Polars | Snowpark equivalent |
   |---|---|
   | `pl.read_iceberg(table)` | `session.table(table)` |
   | `df.filter(pl.col("x") > 0)` | `df.filter(F.col("x") > 0)` |
   | `df.with_columns(pl.col("x").rank().over("y"))` | `df.with_column("rank", F.rank().over(Window.partition_by("y")))` |
   | `df.write_iceberg(table, mode="append")` | `df.write.mode("append").save_as_table(table)` |

3. **Streamlit-in-Snowflake / Snowflake Notebooks**: keep Python notebooks alongside the data; reference: <https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit> and <https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-about>.

---

## 5. Step 3 - Decommission Nucleus

When you have run a quarter of parallel materializations and verified row counts and checksums match, retire the Nucleus side.

| Keep | Discard |
|---|---|
| Iceberg snapshots and Parquet files in S3 - they ARE the data | The local `.nucleus/` directory (filesystem catalog, run ledger) |
| Your `nucleus_project.yaml` (kept for audit / historical reproducibility) | The MinIO and Lakekeeper containers - Snowflake now serves them |
| `@nucleus.contract` schemas - port them to Snowflake `NOT NULL` / `CHECK` / masking policies | The Nucleus virtualenv on engineer laptops |
| Asset-level OpenLineage events already emitted | The Nucleus Workbench (`localhost:8765`) |

Do NOT delete S3 buckets, do NOT touch Iceberg `metadata/` directories, do NOT run Snowflake's `OPTIMIZE` against externally-managed tables - Nucleus or your existing optimizer owns that responsibility. Snapshot lineage is the only history you carry forward until Snowflake accumulates its own.

If the goal is to move write ownership to Snowflake (so Snowflake creates new snapshots), perform a **catalog hand-off** at the cutover moment: stop all Nucleus writes, run `ALTER ICEBERG TABLE ... CONVERT TO MANAGED` (or the equivalent for your Snowflake release - NEEDS VERIFICATION against <https://docs.snowflake.com/en/user-guide/tables-iceberg-convert>), and from that point on Snowflake commits new snapshots into its own catalog. Iceberg history before the hand-off remains visible.

---

## 6. Hybrid mode (Mode 2 territory)

The same hybrid story applies as for Databricks. Many teams keep Nucleus as the development environment and use Snowflake only for production analytics. Mode 2 of the yield-to-giants strategy will eventually expose:

```python
# Implementation arrives v0.3+ per ADR-041 (currently PROPOSED).
@nucleus.asset(compute="snowflake://my-account/my-warehouse")
def heavy_aggregation(ctx) -> Asset:
    return ctx.sql("SELECT ... 100M rows ...")
```

Until the dispatch decorator ships, the manual hybrid recipe is:

1. Develop and test locally with Polars / DuckDB.
2. When ready, paste the SQL into a Snowflake worksheet and run it on a Virtual Warehouse.
3. Point both runtimes at the same S3 bucket and the same Iceberg catalog endpoint, so snapshots commit to the same physical lakehouse.

The full design lives in `docs/decisions/ADR-041-mode-2-hybrid-compute-dispatch.md` (PROPOSED).

---

## 7. Honest caveats - what this cookbook does NOT yet validate

Per `docs/internal/research/parity_vs_databricks_snowflake.md` section 1, Iceberg portability between Nucleus and Snowflake is documented but not yet field-tested. Treat as known unknowns:

1. **No end-to-end test in CI today.** No Nucleus CI job spins up a Snowflake account and asserts a Nucleus-written Iceberg snapshot reads cleanly. PoC #5 external testers are the first verification path.
2. **Iceberg spec version mismatch is possible.** Nucleus pins `pyiceberg` (see `pyproject.toml` and `docs/internal/compatibility.md`); Snowflake's reader supports a documented Iceberg spec range (currently v1, v2; v3 features such as deletion vectors and equality deletes are being rolled out gradually). Verify against <https://docs.snowflake.com/en/user-guide/tables-iceberg> before relying on advanced spec features.
3. **CREATE EXTERNAL VOLUME + IAM trust setup drift.** The IAM trust policy snippet above is illustrative and marked NEEDS VERIFICATION. Re-check against <https://docs.snowflake.com/en/sql-reference/sql/create-external-volume> before pasting into a production console.
4. **Catalog integration syntax drift.** OBJECT_STORE catalog integration parameters and the OAuth REST authentication block evolve. Always verify against <https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration>.
5. **Permission propagation.** Nucleus has no RBAC layer in v0.2 (per `AGENTS.md` section 4 do-not-build list). Once Snowflake owns the tables, all access is governed by Snowflake roles. Do NOT assume any Nucleus-side ACL semantics carry over.
6. **OpenLineage events.** Nucleus emits OpenLineage to NDJSON FileTransport by default. Snowflake has its own ACCESS_HISTORY view; bridging the two requires a separate ingestion step, not yet documented end-to-end.
7. **Cost attribution.** The Nucleus per-asset cost meter (v0.7+) does not see Snowflake credits. Use Snowflake's RESOURCE_MONITORS and ACCOUNT_USAGE views.
8. **Snowflake-managed conversion.** Converting an externally-managed Iceberg table to Snowflake-managed (so Snowflake takes write ownership) is supported but the API surface evolves. Pin to the docs at the time of cutover, not to this cookbook.

If you hit any of the above, file an issue on <https://github.com/nucleus-data/nucleus/issues> with the prefix `[graduation]`.

---

## Related documents

- `docs/cookbook/graduate-to-databricks.md` - sibling recipe for Databricks.
- `docs/cookbook/graduate-to-bigquery.md` - sibling recipe for BigQuery.
- `docs/decisions/ADR-041-mode-2-hybrid-compute-dispatch.md` - design spec for the `compute=` decorator that automates Mode 2.
- `docs/internal/research/parity_vs_databricks_snowflake.md` - the honest capability matrix that motivated this cookbook.
- `docs/specs/nucleus_architecture_v4.1.md` section 10 - canonical Yield-to-Giants Strategy.

## External references (verified URL form, content NEEDS VERIFICATION at integration time)

- Snowflake Iceberg Tables: <https://docs.snowflake.com/en/user-guide/tables-iceberg>
- Snowflake catalog integration setup: <https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration>
- Snowflake CREATE EXTERNAL VOLUME: <https://docs.snowflake.com/en/sql-reference/sql/create-external-volume>
- Snowflake Tasks: <https://docs.snowflake.com/en/user-guide/tasks-intro>
- Snowflake Dynamic Tables: <https://docs.snowflake.com/en/user-guide/dynamic-tables-intro>
- Snowflake Snowpark Python: <https://docs.snowflake.com/en/developer-guide/snowpark/python/index>
- Snowflake Notebooks: <https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-about>
- Snowflake Streamlit: <https://docs.snowflake.com/en/developer-guide/streamlit/about-streamlit>
- Snowflake Open Catalog (Polaris): <https://other-docs.snowflake.com/en/opencatalog/overview>
- Apache Iceberg spec: <https://iceberg.apache.org/spec/>
- Airflow Snowflake provider: <https://airflow.apache.org/docs/apache-airflow-providers-snowflake/stable/operators/snowflake.html>

*Last revised 2026-05-15. Iceberg substrate is stable; the Snowflake catalog-integration surface is the part most likely to drift between releases. Always pin to the live docs for production.*
