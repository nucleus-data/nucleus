---
title: nucleus run
description: Materialize one or more assets in dependency order.
---

# `nucleus run`

Materialize assets.

## Synopsis

```
nucleus run [--all] [--changed-only] [--dry-run] [--param KEY=VAL...] [ASSET_KEY...]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `ASSET_KEY...` | One or more asset keys to materialize |

## Options

| Option | Description |
|--------|-------------|
| `--all` | Materialize all assets in dependency order |
| `--changed-only` | Only materialize assets with changed deps (v0.2+) |
| `--dry-run` | Print which assets would run without materializing |
| `--param KEY=VAL` | Pass runtime parameters to assets (repeatable) |

## Output

```
┌────────────────────────┬────────┬──────────┬──────────┐
│ asset                  │ status │ duration │ rows     │
├────────────────────────┼────────┼──────────┼──────────┤
│ raw.orders             │ ✓ done │    1.2s  │  10,000  │
│ staging.orders         │ ✓ done │    0.4s  │   9,850  │
│ mart.daily_revenue     │ ✓ done │    0.2s  │     365  │
└────────────────────────┴────────┴──────────┴──────────┘
3 assets materialized in 1.8s. Iceberg snapshots committed.
```

## Dry run

```bash
nucleus run --all --dry-run
```

```
[dry-run] Would materialize:
  raw.orders          (no snapshot — will run)
  staging.orders      (deps changed — will run)
  mart.daily_revenue  (up-to-date — skip)
```

## Runtime parameters

```bash
nucleus run analytics.daily_revenue --param start_date=2026-01-01
```

Access in your asset:

```python
@nucleus.asset(table="analytics.daily_revenue")
def daily_revenue(ctx) -> pl.DataFrame:
    start_date = ctx.param("start_date", default=None)
    ...
```

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusInternalError` | NE3001 | Unhandled exception in asset body |
| `NucleusSchemaError` | NE2001 | Contract validation failed |
| `NucleusCommitConflictError` | NE1002 | Concurrent write conflict |
| `NucleusAssetNotFound` | NE3002 | Unknown asset key |

## Examples

```bash
# Single asset
nucleus run mart.daily_revenue

# Multiple assets (in order given)
nucleus run raw.orders staging.orders mart.daily_revenue

# Full graph
nucleus run --all

# Full graph with dry run
nucleus run --all --dry-run
```
