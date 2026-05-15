---
title: nucleus workbench
description: Launch the Nucleus Workbench web IDE — v0.2 feature.
---

# `nucleus workbench`

Launch the Workbench web interface. <span class="badge badge-beta">Beta</span> <span class="badge badge-v05">v0.2+</span>

## Synopsis

```
nucleus workbench [--port PORT] [--host HOST] [--no-browser]
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `8080` | Port to bind |
| `--host` | `127.0.0.1` | Host to bind |
| `--no-browser` | false | Don't auto-open browser |

## What Workbench includes (v0.2)

- **Asset graph** — interactive DAG visualization
- **SQL Editor** — Monaco editor with `{{ ref() }}` autocomplete
- **Run history** — per-asset materialization log
- **Check results** — quality check pass/fail history
- **Lineage viewer** — upstream/downstream asset explorer

## v0.1 note

In v0.1, `nucleus workbench` raises `NucleusFeatureDeferredError` (NE5008):

```
Error: Workbench ships in v0.2.
Fix:   Use 'nucleus query' and 'nucleus run' in the CLI until v0.2.
Docs:  https://nucleus.dev/errors/ne5xxx/#ne5008
       [NE5008]
```

## Related

- [ADR-016: Workbench MVP](../governance/architecture-decisions.md)
- [Roadmap](../community/roadmap.md)
