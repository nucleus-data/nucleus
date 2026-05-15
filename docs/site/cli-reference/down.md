---
title: nucleus down
description: Stop the local Nucleus runtime and optionally remove volumes.
---

# `nucleus down`

Stop the local runtime. Iceberg data is always preserved by default.

## Synopsis

```
nucleus down [--volumes]
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--volumes` | false | Also remove Docker volumes (deletes `data/warehouse/`) |

## Output

```
Nucleus down. Volumes: preserved.
```

With `--volumes`:

```
Nucleus down. Volumes: removed.
```

## Behavior

- Without `--volumes`: stops docker-compose services; all Iceberg data in `data/warehouse/` remains on disk
- With `--volumes`: stops services AND removes docker volumes; data is deleted

!!! warning "Data loss"
    `--volumes` deletes your local warehouse. Only use this when you intend to start fresh.

## Idempotent

Calling `nucleus down` when the stack is already stopped exits with code 0.

## Examples

```bash
# Stop, preserve data
nucleus down

# Stop and wipe everything
nucleus down --volumes
```
