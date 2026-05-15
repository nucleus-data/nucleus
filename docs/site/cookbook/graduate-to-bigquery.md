---
title: Graduate to BigQuery
description: Step-by-step recipe for moving a Nucleus-managed Iceberg lakehouse to Google BigQuery via BigLake, without re-platforming the data.
---

# Graduate to BigQuery

> Architectural intent: `nucleus_architecture_v4.1.md` section 10 (Yield-to-Giants Strategy) and `AGENTS.md` section 4 (Do-Not-Build list). Iceberg is a portable open standard, so the snapshots Nucleus committed are the same snapshots BigQuery will read - via **BigLake**, Google's open-format-on-cloud-storage feature.

This cookbook is the practical answer to:

> "I have a Nucleus-managed Iceberg lakehouse on S3 (or GCS) and I want my analytics to run on BigQuery. What do I actually do?"

It is a path, not a battle-tested runbook. Section 6 (Honest caveats) lists exactly what is and is not validated. The BigQuery-side documentation has more open questions than the Databricks or Snowflake docs - per `docs/research/parity_vs_databricks_snowflake.md` section 3.3 and section 7, several BigQuery surface claims were marked NEEDS VERIFICATION at research time and remain so here.

The BigQuery side leans on **BigLake** for cross-cloud or BigQuery-native Iceberg tables. Reference: <https://cloud.google.com/bigquery/docs/iceberg-tables>.

---

## 1. When you should graduate

Graduate to BigQuery when one or more of:

| Trigger | Why it fires graduation |
|---|---|
| Single asset crosses 10 TB and queries take > 30 s on a beefy laptop | BigQuery's serverless slot architecture scales without cluster sizing; DuckDB on one node does not. |
| Data team grows past 50 engineers | BigQuery + IAM provides project-level governance Nucleus does not have in v0.2. |
| Compliance program requires SOC 2 / HIPAA / FedRAMP today | BigQuery ships these certifications; Nucleus targets them only at v1.5+. |
| You want BigQuery ML (BQML) for in-warehouse ML, or Gemini in BigQuery | Nucleus is not an ML or AI platform (`nucleus_architecture_v4.1.md` section 20.1). |
| The org is GCP-native and the rest of the stack is Cloud Composer / Dataform / Looker | Tight integration outweighs the Iceberg-portability advantage of staying on Nucleus. |
| Data must live in GCS for residency or transfer-cost reasons | BigQuery reads GCS natively; an S3-only Nucleus deployment would have to move the bytes. |

If none of these apply, stay on Nucleus.

---

## 2. What graduates with you, and what does not

| Travels to BigQuery | Stays behind (rebuild on the other side) |
|---|---|
| Apache Iceberg snapshots and Parquet files (in S3 or GCS - more on cross-cloud below) | The Nucleus CLI - replaced by `bq` CLI and the BigQuery console |
| Iceberg snapshot lineage, schema evolution, partition spec | The Asset Materialization Adapter - replaced by Dataform or Cloud Composer |
| `@nucleus.contract` schema definitions (translatable to Dataform assertions) | Nucleus Workbench (`localhost:8765`) - use the BigQuery console or Colab Enterprise |
| OpenLineage events (Tier 0 immortal per `nucleus_architecture_v4.1.md` section 4.1) - emit to Google Dataplex if you want them reflected there | Nucleus filesystem catalog - swap for BigLake Metastore or BigQuery's native Iceberg catalog | <!-- banned-term: metastore -->
| Stable error codes (NE1xxx-NE5xxx, ADR-006) - keep for whatever Nucleus you keep | The Nucleus error translation layer - BigQuery surfaces native errors |

The contract surface that survives is the open-format substrate: Iceberg + Parquet + object storage + OpenLineage. Everything Nucleus-proprietary is replaceable on the BigQuery side.

---

## 3. Step 1 - Register your Iceberg lakehouse with BigQuery

BigQuery exposes Iceberg through three integration paths as of 2026:

1. **BigQuery tables for Apache Iceberg** (BigQuery-managed): BigQuery owns the catalog and writes the Iceberg metadata; storage stays in your GCS bucket.
2. **BigQuery tables for Apache Iceberg in BigLake Metastore** (externally-managed-by-BigLake): BigLake Metastore is the Iceberg REST catalog; BigQuery reads through it. <!-- banned-term: metastore -->
3. **External Iceberg tables** (one-table-at-a-time pointer): you point BigQuery at a metadata.json on object storage, BigQuery reads only.

For graduation from Nucleus, path 3 is the lightest landing; path 2 is the natural follow-up if you adopt BigLake Metastore as the shared catalog. <!-- banned-term: metastore -->

### 3a. Create an external Iceberg table (path 3, simplest)

```sql
-- Reference: https://cloud.google.com/bigquery/docs/iceberg-external-tables
-- NEEDS VERIFICATION: the WITH CONNECTION ... USING ICEBERG syntax for
-- an external Iceberg pointer evolves between BigQuery releases; verify
-- against the live page above.
CREATE EXTERNAL TABLE my_dataset.sales_daily_revenue
  WITH CONNECTION `my-project.us.my-biglake-connection`
  OPTIONS (
    format = 'ICEBERG',
    uris = ['gs://my-prod-bucket/warehouse/sales.daily_revenue/metadata/v0042.metadata.json']
  );
```

Repeat per table. The `metadata/v*.json` pointer must be the **current** snapshot's metadata - BigQuery will not auto-discover newer Nucleus commits, you re-issue the `CREATE OR REPLACE` to point at a newer file. Tools like Apache Iceberg's `metadata-version-hint.text` help; reference: <https://iceberg.apache.org/spec/#table-metadata>.

### 3b. Use BigLake Metastore as the shared catalog (path 2) <!-- banned-term: metastore -->

If your Nucleus side already runs Lakekeeper or any Iceberg REST endpoint (`nucleus enable lakekeeper`, ADR-004, available v0.3+), point BigLake Metastore at that endpoint, then have BigQuery query through BigLake. <!-- banned-term: metastore -->

```sql
-- Reference: https://cloud.google.com/bigquery/docs/biglake-metastore <!-- banned-term: metastore -->
-- NEEDS VERIFICATION: BigLake Metastore is fast-evolving; the exact <!-- banned-term: metastore -->
-- federation-from-external-Iceberg-REST surface may not be GA in your
-- region. Check the live page before relying on it.
-- Conceptual flow (verify exact API in your release):
--   1. Create a BigLake Metastore catalog backed by your Iceberg REST endpoint. <!-- banned-term: metastore -->
--   2. Create a BigQuery dataset linked to that catalog.
--   3. Each Iceberg table appears as a queryable table in the dataset.
```

If your Nucleus side is on the v0.1 filesystem catalog (no REST endpoint), path 3 (per-table external pointer) is the right starting point; switch to path 2 after you graduate to Lakekeeper.

### 3c. Cross-cloud note (S3 vs GCS)

BigQuery is GCS-native. If your Iceberg lakehouse lives on S3, you have two choices:

- **Cross-cloud read** via BigQuery Omni (<https://cloud.google.com/bigquery/docs/omni-introduction>) - BigQuery Omni runs in AWS regions and can read S3 directly. Verify region availability.
- **Move bytes to GCS** via `gsutil rsync s3://my-prod-bucket gs://my-bigquery-bucket` - simplest, but a one-time data transfer cost and an ongoing sync if Nucleus keeps writing to S3.

For Mode 1 (full graduation), most teams move bytes to GCS once and stop writing on the S3 side. For Mode 2 (hybrid), BigQuery Omni keeps the data in place.

---

## 4. Step 2 - Verify read access, then move scheduling and compute

### Verify

```sql
SELECT COUNT(*) AS row_count
  FROM my_dataset.sales_daily_revenue;

SELECT *
  FROM my_dataset.INFORMATION_SCHEMA.TABLES
  WHERE table_name = 'sales_daily_revenue';
```

Diff against Nucleus side:

```bash
nucleus query "SELECT COUNT(*) FROM {{ ref('sales.daily_revenue') }}"
```

If counts diverge, the BigLake connection is not seeing the current Iceberg snapshot. Common causes: stale `metadata.json` pointer, GCS / S3 bucket policy missing the BigLake connection's service account, BigQuery Omni region mismatch.

### Move scheduling

Nucleus uses an embedded Dagster scheduler. On Google Cloud the equivalent surfaces are **Cloud Composer** (managed Apache Airflow), **Dataform** (SQLX-based transformation orchestration; reference: <https://cloud.google.com/dataform/docs/overview>), or **Cloud Workflows** (lightweight orchestration; reference: <https://cloud.google.com/workflows/docs/overview>).

| Nucleus declaration | GCP equivalent |
|---|---|
| `@nucleus.asset(schedule="@daily")` | Cloud Composer DAG with `schedule_interval="0 0 * * *"`, OR Dataform release config with cron, OR a BigQuery scheduled query |
| `@nucleus.asset(deps=["bronze.x"])` | Airflow `>>` operator, OR Dataform `ref("bronze_x")` |
| `@nucleus.sql_asset` returning SQL | Dataform `.sqlx` file with `config { type: "table" }` |
| `@nucleus.check(...)` | Dataform `assertion {}` block - assertions are GA in Dataform |
| `nucleus run my.asset` | `dataform run --tag=my_tag` or a manual Cloud Composer trigger |

Dataform is the closest one-to-one match for the Nucleus asset model and it is **free to use** with BigQuery (you only pay for the BigQuery compute it triggers). Recommended landing for SQL-heavy projects.

### Move compute

Three porting strategies:

1. **BigQuery SQL only**: most `@nucleus.sql_asset` queries run unchanged on BigQuery. BigQuery SQL is GoogleSQL, ANSI-leaning. Watch for: differences in struct/array access, `QUALIFY` semantics, and `EXCEPT DISTINCT` vs `EXCEPT`.
2. **BigQuery DataFrames** (`bigframes`): a pandas-like Python API that compiles to BigQuery SQL. Reference: <https://cloud.google.com/bigquery/docs/bigquery-dataframes-introduction> (NEEDS VERIFICATION - the `bigframes` API is being extended; pin to the current version's docs).
3. **Dataflow / Apache Beam**: for streaming or beyond-warehouse compute, Cloud Dataflow runs Apache Beam. Reference: <https://cloud.google.com/dataflow/docs>.

For most graduation cases, option 1 (raw BigQuery SQL via Dataform) is the cleanest.

---

## 5. Step 3 - Decommission Nucleus

When you have run a quarter of parallel materializations and verified row counts and checksums match, retire the Nucleus side.

| Keep | Discard |
|---|---|
| Iceberg snapshots and Parquet files in GCS (or S3 for Omni) - they ARE the data | The local `.nucleus/` directory (filesystem catalog, run ledger) |
| Your `nucleus_project.yaml` (kept for audit / historical reproducibility) | The MinIO and Lakekeeper containers - Google now serves storage and catalog |
| `@nucleus.contract` schemas - port them to Dataform assertions | The Nucleus virtualenv on engineer laptops |
| Asset-level OpenLineage events already emitted to your collector | The Nucleus Workbench (`localhost:8765`) |

Do NOT delete GCS buckets, do NOT touch Iceberg `metadata/` directories, do NOT run BigQuery `OPTIMIZE_TABLE` against external pointers - those are read-only references to the Iceberg metadata Nucleus owns. Snapshot lineage is the only history you carry forward until BigQuery (BigLake-managed) accumulates its own.

If the goal is to move write ownership to BigQuery (so BigQuery commits new snapshots into BigLake-managed tables), perform a **catalog hand-off**: stop all Nucleus writes, do a one-time copy `CREATE TABLE ... AS SELECT * FROM external_iceberg_table` into a BigQuery-managed Iceberg table, and from that point on BigQuery owns the snapshots. Iceberg history before the hand-off remains visible only on the external pointer; once cut over, archive it but stop relying on it.

---

## 6. Hybrid mode (Mode 2 territory)

The same hybrid story applies as for Databricks and Snowflake. Mode 2 of the yield-to-giants strategy will eventually expose:

```python
# Implementation arrives v0.3+ per ADR-041 (currently PROPOSED).
@nucleus.asset(compute="bigquery://my-project/us")
def heavy_aggregation(ctx) -> Asset:
    return ctx.sql("SELECT ... 100M rows ...")
```

Until the dispatch decorator ships, the manual hybrid recipe is:

1. Develop and test locally with Polars / DuckDB.
2. When ready, paste the SQL into a Dataform `.sqlx` file or a BigQuery scheduled query.
3. Point both runtimes at the same physical lakehouse - Nucleus writes Iceberg into GCS (or S3 + BigQuery Omni); BigQuery reads via BigLake.

The full design lives in `docs/decisions/ADR-041-mode-2-hybrid-compute-dispatch.md` (PROPOSED).

---

## 7. Honest caveats - what this cookbook does NOT yet validate

Per `docs/research/parity_vs_databricks_snowflake.md` section 3.3 and section 7, BigQuery has **the highest open-question count of the three graduation targets** because several Google Cloud doc pages timed out during research. Treat the following as known unknowns:

1. **No end-to-end test in CI today.** No Nucleus CI job spins up a BigQuery dataset and asserts that a Nucleus-written Iceberg snapshot reads cleanly through BigLake. PoC #5 external testers are the first verification path.
2. **BigLake Metastore is fast-moving.** Several BigLake surfaces (Iceberg integration depth, federation from external Iceberg REST, cross-region availability) were GA at different times during 2025-2026. Pin to the live docs at <https://cloud.google.com/bigquery/docs/biglake-metastore> at integration time. <!-- banned-term: metastore -->
3. **External Iceberg pointers do NOT auto-discover new snapshots.** Each `CREATE OR REPLACE EXTERNAL TABLE ... uris = [...]` references one specific `metadata.json`. If your Nucleus side commits a new snapshot, BigQuery will not see it until you re-issue the DDL. Workaround: emit a Dataform release on every Nucleus materialization, or graduate to BigLake Metastore (path 2). <!-- banned-term: metastore -->
4. **Cross-cloud read via BigQuery Omni has region constraints.** Omni regions are limited; your S3 region may not have an Omni equivalent. Check <https://cloud.google.com/bigquery/docs/omni-introduction> before assuming cross-cloud reads will work.
5. **Iceberg spec version mismatch is possible.** Nucleus pins `pyiceberg`. BigLake supports a documented Iceberg spec range (currently v1, v2; v3 features arrive gradually). Verify against <https://cloud.google.com/bigquery/docs/iceberg-tables> before relying on advanced spec features.
6. **`bigframes` (BigQuery DataFrames) API surface evolves.** Marked NEEDS VERIFICATION in `docs/research/parity_vs_databricks_snowflake.md` section 7 item 2. Use the current version's docs, not memory.
7. **OpenLineage events into Dataplex.** Nucleus emits OpenLineage to NDJSON FileTransport by default. Bridging to Dataplex lineage requires a separate ingestion step, not yet documented end-to-end (NEEDS VERIFICATION against <https://cloud.google.com/dataplex/docs> at integration time).
8. **IAM permission propagation.** Nucleus has no RBAC layer in v0.2. Once BigQuery owns the tables, all access is governed by GCP IAM. Do NOT assume any Nucleus-side ACL semantics carry over.
9. **Cost attribution.** The Nucleus per-asset cost meter (v0.7+) does not see BigQuery on-demand or slot costs. Use BigQuery's INFORMATION_SCHEMA.JOBS_BY_PROJECT and Cloud Billing.
10. **Permissions for cross-cloud (S3 read).** BigQuery Omni requires a specific IAM-to-S3 role binding pattern; the precise IAM policy varies by region. NEEDS VERIFICATION at <https://cloud.google.com/bigquery/docs/omni-aws-create-connection>.

If you hit any of the above, file an issue on <https://github.com/nucleus-data/nucleus/issues> with the prefix `[graduation]`.

---

## Related documents

- `docs/cookbook/graduate-to-databricks.md` - sibling recipe for Databricks.
- `docs/cookbook/graduate-to-snowflake.md` - sibling recipe for Snowflake.
- `docs/decisions/ADR-041-mode-2-hybrid-compute-dispatch.md` - design spec for the `compute=` decorator that automates Mode 2.
- `docs/research/parity_vs_databricks_snowflake.md` - the honest capability matrix that motivated this cookbook (BigQuery section is the most NEEDS VERIFICATION-heavy of the three).
- `nucleus_architecture_v4.1.md` section 10 - canonical Yield-to-Giants Strategy.

## External references (verified URL form, content NEEDS VERIFICATION at integration time)

- BigQuery Iceberg overview: <https://cloud.google.com/bigquery/docs/iceberg-tables>
- BigQuery external Iceberg tables: <https://cloud.google.com/bigquery/docs/iceberg-external-tables>
- BigLake Metastore: <https://cloud.google.com/bigquery/docs/biglake-metastore> <!-- banned-term: metastore -->
- BigQuery Omni cross-cloud: <https://cloud.google.com/bigquery/docs/omni-introduction>
- BigQuery Omni AWS connection: <https://cloud.google.com/bigquery/docs/omni-aws-create-connection>
- Dataform: <https://cloud.google.com/dataform/docs/overview>
- Cloud Composer (managed Airflow): <https://cloud.google.com/composer/docs>
- Cloud Workflows: <https://cloud.google.com/workflows/docs/overview>
- Cloud Dataflow (Apache Beam): <https://cloud.google.com/dataflow/docs>
- BigQuery DataFrames (`bigframes`): <https://cloud.google.com/bigquery/docs/bigquery-dataframes-introduction>
- BigQuery scheduled queries: <https://cloud.google.com/bigquery/docs/scheduling-queries>
- Dataplex: <https://cloud.google.com/dataplex/docs>
- Apache Iceberg spec: <https://iceberg.apache.org/spec/>

*Last revised 2026-05-15. The BigQuery side has the highest documentation drift of the three graduation cookbooks; always pin to the live docs for production use. PoC #5 external-tester field test is the first systematic validation path.*
