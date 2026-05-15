---
title: nucleus query
description: Run DuckDB SQL against your Iceberg warehouse.
---

# `nucleus query`

Run SQL against the warehouse.

## Synopsis

```
nucleus query [--file PATH] [--asset KEY] [--limit N] [--format text|json|csv] [--no-page] [SQL]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `SQL` | Inline SQL query (optional — use `--file` or `--asset` instead) |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--file PATH` | — | Read SQL from a file |
| `--asset KEY` | — | Run `SELECT * FROM <key> LIMIT N` |
| `--limit N` | 100 (with `--asset`) | Row limit |
| `--format text\|json\|csv` | text | Output format |
| `--no-page` | false | Disable `less` pagination for large results |

## Input modes

=== "Inline SQL"

    ```bash
    nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
    ```

=== "From file"

    ```bash
    nucleus query --file ./queries/daily_revenue.sql
    ```

=== "By asset key"

    ```bash
    nucleus query --asset analytics.daily_revenue --limit 20
    ```

## Jinja resolution

`{{ ref('asset.key') }}` resolves to the DuckDB Iceberg scan path. Use it everywhere:

```bash
nucleus query "
  SELECT a.order_date, SUM(a.amount) AS revenue, b.region
  FROM {{ ref('staging.orders') }} a
  JOIN {{ ref('dim.customers') }} b ON a.customer_id = b.id
  GROUP BY 1, 3
  ORDER BY 1 DESC
  LIMIT 30
"
```

## Output formats

=== "Text (default)"

    Rich table, truncated to terminal width. Auto-paginates via `less -R` for >50 rows.

=== "JSON"

    NDJSON (one object per row), pipe-friendly:

    ```bash
    nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }}" \
      --format json | jq '.revenue'
    ```

=== "CSV"

    ```bash
    nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }}" \
      --format csv > report.csv
    ```

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusSQLSyntaxError` | NE2002 | SQL parse error |
| `NucleusAssetNotFound` | NE3002 | Unknown asset key in `{{ ref() }}` |
| `NucleusAssetNotMaterialized` | NE3003 | Asset defined but never materialized |
| `NucleusResourceError` | NE2003 | DuckDB memory limit exceeded |
