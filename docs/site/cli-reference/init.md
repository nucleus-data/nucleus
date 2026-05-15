---
title: nucleus init
description: Scaffold a new Nucleus project directory.
---

# `nucleus init`

Scaffold a new Nucleus project.

## Synopsis

```
nucleus init [--template default] [--no-git] PROJECT_NAME
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `PROJECT_NAME` | Required | Name of the new project directory |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--template` | `default` | Project template (only `default` in v0.1) |
| `--no-git` | false | Skip the git init suggestion |

## Output

```
Created Nucleus project at ./beachhead-demo (6 files).
Next steps: cd beachhead-demo && nucleus up
```

## Files created

```
beachhead-demo/
├── nucleus_project.yaml     # Project configuration
├── assets/
│   └── example.py           # Starter @nucleus.asset
├── checks/
│   └── __init__.py
├── data/
│   └── .gitkeep
├── .gitignore
└── README.md
```

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusIOError` | NE1005 | Target directory already exists and is not empty |
| `NucleusInvalidAssetDefinition` | NE3004 | Invalid project name or unknown template |

## Examples

```bash
# Basic
nucleus init my-analytics

# No git suggestion
nucleus init my-analytics --no-git
```

!!! note "v0.3+ templates"
    The `--template` flag will support `minimal`, `postgres`, and `csv` presets in v0.3+. In v0.1, only `default` is available.
