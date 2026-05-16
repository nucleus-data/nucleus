---
title: Composability by Constitution
description: How Nucleus guarantees that every dependency can be swapped without breaking user code.
---

# Composability by Constitution

Per [architecture v4.1 §9](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md), every Tier 1/2 dependency must have:

1. **A clean swap interface** — types compile, API surface matches — ALWAYS maintained
2. **Basic smoke tests** (5-10 tests) — ALWAYS run in CI
3. **A documented migration path** in `/docs/internal/swap/<component>.md`

Full swap implementations are built **on-demand** when a trigger fires, not speculatively.

## Tier 0 — Immortal (never swapped)

| Component | Reason |
|-----------|--------|
| Apache Iceberg | Open standard; the whole portability promise depends on it |
| Apache Arrow | Zero-copy in-memory format; too fundamental |
| Apache Parquet | On-disk format; immortal with Iceberg |
| Lance | Multimodal format for v0.5+ |
| S3 API | Object store interface; immortal |
| OpenLineage | Lineage event spec; immortal |
| OpenTelemetry | Observability spec; immortal |

## Tier 1 — Primary wrapped engines (swap interfaces required)

| Component | Default | Swap target | Trigger |
|-----------|---------|-------------|---------|
| SQL engine | DuckDB | Apache DataFusion | Performance regression >2x |
| DataFrame engine | Polars | DataFusion DF | Same as SQL engine |
| Orchestration | Dagster | `nucleus-mini-scheduler` | Dagster license pivot or death |
| Catalog (v0.3+) | Lakekeeper | Apache Polaris | Mo 24 gate or customer demand |

## Trigger conditions for building full swap

A full swap implementation is built when **any** of these fire:

1. Vendor death or abandonment
2. License pivot (OSS → commercial, non-Apache)
3. Performance regression > 2x vs baseline
4. Community demand (empirical, not perceived)

## Swap docs

Swap migration paths are documented in `/docs/internal/swap/`:

| File | Component |
|------|-----------|
| `docs/internal/swap/duckdb.md` | DataFusion as DuckDB swap |
| `docs/internal/swap/polars.md` | DataFusion DF as Polars swap |
| `docs/internal/swap/dagster.md` | nucleus-mini-scheduler fallback |
| `docs/internal/swap/lakekeeper.md` | Apache Polaris as Lakekeeper swap |
| `docs/internal/swap/pyiceberg.md` | pyiceberg version upgrade notes |
| `docs/internal/swap/dlt.md` | Sling/Singer as dlt swap |

## CI enforcement

Swap interface smoke tests run in CI:

```yaml
# .github/workflows/ci.yml
- name: Swap interface smoke tests
  run: pytest -m smoke
```
