# ADR-033: Marquez v0.54 Rust as v0.3+ Lineage Viewer

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P1  
**Target phase**: v0.3  
**Source research**: `docs/internal/research/inspiration/observability_lineage_2026.md` §1, §2, §7, §10  
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #6

---

## Context

Nucleus emits OpenLineage events for every asset materialisation. At v0.1, these are stored as NDJSON files in `.nucleus/lineage/`. The v0.3 Workbench lineage view needs a queryable backend that serves the standard Marquez REST API (`GET /api/v1/lineage?nodeId=...&depth=3`).

**The upstream Marquez project is stalled** (v0.50.0, October 2024 — 18 months without a release as of May 2026, per R4 §2). **The ilum-cloud fork shipped a complete Rust backend rewrite in March 2026** (v0.54.0: Axum + SQLx + tokio). Key facts (R4 §2):
- 100% API-compatible with upstream Marquez (same REST endpoints)
- Default Docker image has zero JVM — resolves Hard Constraint #1 for the sidecar
- Rust path is the default; Java path available via `./docker/up.sh --java` (unsupported in Nucleus docs)
- Only infrastructure dependency: PostgreSQL 16 (vs DataHub's Kafka + Elasticsearch + MySQL + JVM = ~8 GB)
- `lineageStatistics` facet in v0.54.0: upstream/downstream dependency counts computed at write time

**Recommended ADR wording** from R4 §2: *"Default lineage viewer for `nucleus enable marquez` is `ilum/marquez:0.54.0`, NOT `marquezproject/marquez:latest`."*

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — ilum-cloud Marquez v0.54 Rust** | Pin `ilum/marquez:0.54.0` as the default; document Java fallback as unsupported | ✅ SELECTED — no JVM; ~1 GB RAM vs 8 GB; 100% API-compatible; actively maintained |
| B — Upstream Marquez latest | `marquezproject/marquez:latest` | ❌ REJECTED — upstream stalled 18 months; Java backend; HC#1 violation |
| C — DataHub | Full catalog + governance platform | ❌ REJECTED — ~8 GB stack (Kafka + ES + JVM); too heavy for startup persona |
| D — NDJSON scan only | Keep v0.1 NDJSON-only lineage, no viewer | ❌ REJECTED — v0.3 Workbench needs a queryable lineage API; NDJSON scan doesn't scale past ~100 assets |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A**.

Implementation:
1. Add `nucleus enable marquez` CLI command (wraps `docker compose up ilum/marquez:0.54.0 + postgres:16`)
2. Update `docs/swap/marquez.md` with the pin and Rust/Java clarification
3. Configure AMA `HttpTransport` to emit events to Marquez when `--marquez-url` is configured in `nucleus_project.yaml`
4. Workbench lineage view: replace NDJSON scan with `GET /api/v1/lineage` call when Marquez is configured; fall back to NDJSON if not

**NEEDS VERIFICATION before writing code** (R4 NV #2): Confirm `ilum/marquez:0.54.0` default Docker image has zero JVM — check Dockerfile base image at https://github.com/ilum-cloud/marquez/blob/0.54.0/docker/Dockerfile-api.

---

## Consequences

- **LOC budget impact**: ~50 LOC (`nucleus enable marquez` command + Docker Compose template); ~100 LOC Workbench API client for Marquez REST
- **Infrastructure dependency**: PostgreSQL 16 (existing in our Docker Compose stack)
- **No new Python runtime dependencies** (openlineage-python already pinned; `HttpTransport` already documented)
- **Maintenance ownership**: Coordination layer (AMA emission) + Experience layer (Workbench client)
- **Swap target**: Documented at `docs/swap/marquez.md` — DataHub as swap target (OL HttpTransport is the interface; zero code change to switch)

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §6.5 (lineage layer)
- `AGENTS.md §3` Hard Constraint #1 (no JVM — ilum Rust path satisfies)
