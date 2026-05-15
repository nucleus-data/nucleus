---
title: Architecture Decisions
description: Index of all Nucleus Architecture Decision Records (ADRs).
---

# Architecture Decisions

Nucleus uses ADRs to document significant architectural choices. Every "build" decision (vs wrapping OSS) requires an ADR.

## ADR index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-001-no-iceberg-commit-service.md) | No custom Iceberg commit service | ACCEPTED |
| [ADR-002](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-002-positioning-decision-2026-05.md) | Mid-2026 positioning refresh | ACCEPTED |
| [ADR-003](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md) | pyiceberg upgrade 0.8.1 → 0.11.x | ACCEPTED |
| [ADR-004](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-004-catalog-migration-v01-to-v03.md) | Catalog migration v0.1 → v0.3 | PROPOSED |
| [ADR-005](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-005-ctx-sdk-api-freeze-policy.md) | ctx SDK API freeze policy | ACCEPTED |
| [ADR-006](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-006-nucleus-error-code-numbering.md) | NucleusError code numbering scheme | ACCEPTED |
| [ADR-007](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-007-dependency-license-tier-policy.md) | Dependency license tier policy | ACCEPTED |
| [ADR-008](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-008-storage-substrate-v01.md) | Storage substrate v0.1 (SeaweedFS default) | PROPOSED |
| [ADR-009](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-009-openlineage-event-schema-policy.md) | OpenLineage event schema policy | ACCEPTED |
| [ADR-010](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-010-oidc-delegation-policy-v03.md) | OIDC delegation policy (v0.3) | ACCEPTED |
| [ADR-011](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-011-telemetry-and-observability-opt-in-policy.md) | Telemetry and observability opt-in | ACCEPTED |
| [ADR-012](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md) | Runtime dependency pin matrix v0.1 | ACCEPTED |
| [ADR-013](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-013-ctx-materialize-api.md) | ctx.materialize API design | ACCEPTED |
| [ADR-014](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-014-dlt-postgres-source.md) | dlt Postgres source integration | ACCEPTED |
| [ADR-015](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-015-ai-chat-mvp.md) | AI chat MVP (v0.2) | ACCEPTED |
| [ADR-016](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-016-workbench-mvp.md) | Workbench MVP (v0.2) | ACCEPTED |
| [ADR-017](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-017-schedule-exposure-v01.md) | Schedule exposure v0.1 | ACCEPTED |
| [ADR-018](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-018-dagit-escape-hatch.md) | Dagit escape hatch | ACCEPTED |
| [ADR-021](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/ADR-021-mkdocs-material-docs-stack.md) | MkDocs Material documentation stack | PROPOSED |

## ADR template

```markdown
# ADR-NNN: <title>

Status: PROPOSED | ACCEPTED | REJECTED | SUPERSEDED
Date: YYYY-MM-DD

## Context
What forced this decision?

## Options considered
- Option A: ...
- Option B: ...

## Decision
Chosen: ...

## Consequences
- LOC budget impact:
- Maintenance owner:
```

See [`docs/decisions/_template.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/decisions/_template.md) for the full template.
