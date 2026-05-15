---
title: Citations
description: All wrapped open-source libraries used in Nucleus with their licenses.
---

# Citations

Nucleus is built on the shoulders of excellent open-source projects. We wrap rather than build.

## Tier 0 — Immortal substrate

| Library | License | Use |
|---------|---------|-----|
| [Apache Iceberg](https://iceberg.apache.org/) | Apache-2.0 | Table format |
| [Apache Arrow](https://arrow.apache.org/) | Apache-2.0 | In-memory columnar format |
| [Apache Parquet](https://parquet.apache.org/) | Apache-2.0 | On-disk format |
| [Lance](https://lancedb.github.io/lance/) | Apache-2.0 | Multimodal format (v0.5+) |
| [OpenLineage](https://openlineage.io/) | Apache-2.0 | Lineage events |
| [OpenTelemetry](https://opentelemetry.io/) | Apache-2.0 | Observability |

## Tier 1 — Primary engines

| Library | Version | License | Docs |
|---------|---------|---------|------|
| [DuckDB](https://duckdb.org/) | 1.1.3 | MIT | https://duckdb.org/docs/ |
| [Polars](https://www.pola.rs/) | 1.18.0 | MIT | https://docs.pola.rs/ |
| [PyArrow](https://arrow.apache.org/docs/python/) | 18.1.0 | Apache-2.0 | https://arrow.apache.org/docs/python/ |
| [pyiceberg](https://py.iceberg.apache.org/) | 0.11.1 | Apache-2.0 | https://py.iceberg.apache.org/ |
| [Dagster](https://dagster.io/) | 1.9.5 | Apache-2.0 | https://docs.dagster.io/ |

## Tier 2 — Supporting libraries

| Library | Version | License | Use |
|---------|---------|---------|-----|
| [SQLAlchemy](https://www.sqlalchemy.org/) | 2.0.36 | MIT | Source connectors |
| [psycopg](https://www.psycopg.org/) | 3.2.3 | LGPL-3 | PostgreSQL driver |
| [PyMySQL](https://pymysql.readthedocs.io/) | 1.1.1 | MIT | MySQL driver |
| [dlt](https://dlthub.com/) | 1.26.0 | Apache-2.0 | Stage 1 Postgres source |
| [Jinja2](https://jinja.palletsprojects.com/) | 3.1.6 | BSD-3-Clause | SQL templating |
| [croniter](https://github.com/kiorky/croniter) | 3.0.4 | MIT | Schedule parsing |
| [s3fs](https://s3fs.readthedocs.io/) | 2026.4.0 | BSD-3-Clause | S3 filesystem |
| [rich](https://rich.readthedocs.io/) | 13.9.4 | MIT | Terminal output |
| [typer](https://typer.tiangolo.com/) | 0.15.1 | MIT | CLI framework |
| [click](https://click.palletsprojects.com/) | 8.1.8 | BSD-3-Clause | CLI core |
| [FastAPI](https://fastapi.tiangolo.com/) | 0.136.1 | MIT | Workbench API |
| [uvicorn](https://www.uvicorn.org/) | 0.46.0 | BSD-3-Clause | ASGI server |
| [litellm](https://docs.litellm.ai/) | 1.83.14 | MIT | AI Copilot provider abstraction |
| [structlog](https://www.structlog.org/) | 24.4.0 | Apache-2.0 | Structured logging |
| [openlineage-python](https://openlineage.io/) | 1.47.1 | Apache-2.0 | Lineage client |

## Documentation

| Library | Version | License |
|---------|---------|---------|
| [MkDocs](https://www.mkdocs.org/) | 1.6.1 | BSD-2-Clause |
| [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) | 9.5.49 | MIT |
| [mkdocstrings](https://mkdocstrings.github.io/) | 0.27.0 | ISC |
| [pymdown-extensions](https://facelessuser.github.io/pymdown-extensions/) | 10.21.3 | MIT |

All dependencies comply with [ADR-007: Dependency license tier policy](../governance/architecture-decisions.md).
