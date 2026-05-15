---
title: nucleus version
description: Print the installed Nucleus version and all pinned dependency versions.
---

# `nucleus version`

Print version information.

## Synopsis

```
nucleus version [--check-updates]
```

## Options

| Option | Description |
|--------|-------------|
| `--check-updates` | Query PyPI for newer versions (never auto-installs) |

## Output

```
nucleus          0.1.0
duckdb           1.1.3
polars           1.18.0
pyarrow          18.1.0
pyiceberg        0.11.1
dagster          1.9.5
```

## With `--check-updates`

```
nucleus          0.1.0  (latest: 0.1.0 ✓)
duckdb           1.1.3  (latest: 1.2.0 — update available)
polars           1.18.0 (latest: 1.18.0 ✓)
...
```

`--check-updates` requires network access. It only queries PyPI and never installs anything automatically. Per [Constraint #11](../governance/upgrade-policy.md), upgrades are always manual and one-component-per-PR.

## Machine-readable output

```bash
nucleus version --format json
```

```json
{"_schema_version": 1, "nucleus": "0.1.0", "duckdb": "1.1.3", "polars": "1.18.0", "pyarrow": "18.1.0", "pyiceberg": "0.11.1", "dagster": "1.9.5"}
```

## Why all deps are shown

Per [AGENTS.md §11.13](../governance/upgrade-policy.md), every wrapped library has an exact pin. The `nucleus version` output is the single-source-of-truth for what is actually running — useful for bug reports and upgrade audits.
