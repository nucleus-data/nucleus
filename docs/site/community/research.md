---
title: Research Notes
description: Official-docs research, ecosystem comparisons, and benchmark baselines.
---

# Research Notes

Per [Constraint #10 in AGENTS.md](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md#3-eleven-hard-constraints-non-negotiable), every wrapped component requires reading official docs **before first integration AND before any version upgrade**. Notes from each reading land in [`docs/research/` on GitHub](https://github.com/nucleus-data/nucleus/tree/main/docs/research) (39 files total at v0.2.0 ship).

## Wrapped libraries (Tier 1 / 2)

| Component | Research note |
|-----------|---------------|
| DuckDB | [duckdb.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/duckdb.md) |
| Polars | [polars.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/polars.md) |
| pyiceberg | [pyiceberg.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/pyiceberg.md) |
| PyArrow | [pyarrow.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/pyarrow.md) |
| Dagster (embedded) | [dagster.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/dagster.md) |
| dlt (verified sources) | [dlt.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/dlt.md) |
| sqlglot | [sqlglot.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/sqlglot.md) |
| OpenLineage | [openlineage.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/openlineage.md) |
| OpenTelemetry | [opentelemetry.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/opentelemetry.md) |
| Marimo (notebooks) | [marimo.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/marimo.md) |
| Soda Core | [soda.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/soda.md) |
| Lance / LanceDB | [lance.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/lance.md) |
| Daft | [daft.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/daft.md) |
| dbt-duckdb | [dbt-duckdb.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/dbt-duckdb.md) |
| MinIO | [minio.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/minio.md) |
| SeaweedFS | [seaweedfs.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/seaweedfs.md) |
| Lakekeeper | [lakekeeper.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/lakekeeper.md) |
| Apache Polaris | [polaris.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/polaris.md) |

## Ecosystem comparisons

| Document | Purpose |
|----------|---------|
| [parity_vs_databricks_snowflake.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/parity_vs_databricks_snowflake.md) | Capability matrix vs the giants |
| [parity_vs_dbt_dagster_airflow.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/parity_vs_dbt_dagster_airflow.md) | Capability matrix vs the OSS contemporaries |
| [parity_vs_bosch_ely_adb_batch.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/parity_vs_bosch_ely_adb_batch.md) | Enterprise-batch comparison (Bosch case) |
| [snowflake.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/snowflake.md) | Snowflake-as-target (yield-to-giants Mode 1) |

## Benchmarks + targets

| Document | Purpose |
|----------|---------|
| [`docs/benchmarks/2026-05-15_baseline.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/benchmarks/2026-05-15_baseline.md) | Empirical v0.2.0 baseline — boot, materialize, concurrent-run, TPC-H |
| [performance_reliability_targets.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/performance_reliability_targets.md) | Aspirational targets (v0.2 baseline diverges — see release notes) |
| [scale_out_audit.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/scale_out_audit.md) | What we yield to giants on, with citations |
| [free_tier_deploy_evaluation.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/free_tier_deploy_evaluation.md) | Cloud free-tier viability for demo deploys |

## Discipline + governance

| Document | Purpose |
|----------|---------|
| [README.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/README.md) | Research-notes index + format |
| [ai_hallucinations.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/ai_hallucinations.md) | **Mandatory log** — every AI-fabricated API caught in review |
| [windows_atomicity.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/windows_atomicity.md) | Cross-platform atomic write discipline (informs ADR-024 P0) |
| [otel_day1_decision.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/otel_day1_decision.md) | Why we shipped OTel SDK day-1, exporters opt-in |
| [ux_familiarity_audit.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/ux_familiarity_audit.md) | Pillar #4 ("Familiar UX from proven giants") audit |

## Connector + storage research

| Document | Purpose |
|----------|---------|
| [s3_duckdb.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/s3_duckdb.md) | S3 via DuckDB |
| [gcs_duckdb.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/gcs_duckdb.md) | GCS via DuckDB |
| [filesystem_duckdb.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/filesystem_duckdb.md) | Local filesystem via DuckDB |
| [ducklake.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/ducklake.md) | DuckLake evaluation (not chosen) |
| [workbench.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/workbench.md) | Workbench tech-stack research (Vite/React confirmation) |
| [observability_backends.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/observability_backends.md) | VictoriaMetrics + VictoriaLogs choice |
| [oidc_providers.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/oidc_providers.md) | Auth delegation targets (v0.3+) |
| [ai_copilot.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/ai_copilot.md) | LiteLLM routing + provider abstraction |
| [wave3_connectors_design.md](https://github.com/nucleus-data/nucleus/blob/main/docs/research/wave3_connectors_design.md) | Connector batch 2 design (v0.3+) |

---

*Last updated: 2026-05-15.*
