---
title: nucleus up
description: Start the Nucleus local runtime — object store, catalog, and asset definitions.
---

# `nucleus up`

Start the local Nucleus runtime.

## Synopsis

```
nucleus up [--rebuild] [--catalog filesystem] [--profile NAME]
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--rebuild` | false | Force rebuild of docker images |
| `--catalog` | `filesystem` | Catalog type (`filesystem` in v0.1; `lakekeeper`, `polaris` in v0.3+) |
| `--profile` | `default` | Environment profile from `nucleus_project.yaml` |

## What it starts

1. **SeaweedFS** (default) or MinIO (opt-in via `docker-compose.minio.yml`) — local S3-compatible object store on port 9000
2. **Filesystem Iceberg catalog** — `pyiceberg.SqlCatalog` backed by SQLite at `data/catalog.db`
3. **Dagster Definitions** — in-process, auto-discovers all `@nucleus.asset` definitions

## Output

```
✓ Object store ready (SeaweedFS on :9000)
✓ Catalog ready (filesystem, 3 tables)
✓ Definitions loaded (8 assets)
Nucleus up in 6.1s.
```

## Boot time targets

- **Cold start (first run):** &lt;10 seconds
- **Warm start (Docker already running):** &lt;3 seconds

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusDockerUnavailable` | NE5002 | Docker Desktop is not running or not reachable |
| `NucleusPortBound` | NE5003 | Port 9000 or 9001 is already in use |

## Examples

```bash
# Standard boot
nucleus up

# Force rebuild (after a docker-compose update)
nucleus up --rebuild
```

## See also

- [`nucleus down`](down.md)
- [Architecture v4.1 §6.1](../philosophy/five-pillars.md)
