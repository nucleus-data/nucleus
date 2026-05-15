# ADR-036: Modal as Mode 2 Python Function Dispatch Target

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P2 (watch-list)  
**Target phase**: v1.5+  
**Source research**: `docs/research/inspiration/distributed_compute_2026.md` §3, §10  
**Synthesis reference**: `docs/research/inspiration/ADOPTION_SHORTLIST.md` §2.9, §4

---

## Context

Modal is a serverless Python compute platform. You decorate Python functions with `@app.function(...)` and call them from anywhere — locally, in CI, or from another cloud function. Modal provisions containers, manages images, and bills per second.

**Why Modal is the P2 Mode 2 target** (over Coiled, Ray/Anyscale) for Nucleus:
- **Cold start**: 1–4 seconds for standard Python data workloads (vs Coiled's 30–90s cluster spinup, R6 §4)
- **Python-native**: The `@app.function()` decorator maps directly to Nucleus's asset model — a `@nucleus.asset` body is already a Python function
- **Per-second billing**: $0.047/core-hr base (R6 §3.3 from modal.com/pricing); no cluster management overhead
- **OIDC compliance**: Modal emits short-lived JWT tokens satisfying Hard Constraint #6 (no custom auth) for downstream AWS S3 access (R6 §3.4)

**Distinction from MotherDuck (ADR-035)**: Modal = Python function dispatch (heavy batch assets exceeding laptop CPU/RAM, Python-centric workloads). MotherDuck = DuckDB-native continuous SQL scale-out (transparent query overflow).

**Gate requirements** (from R6 §3.5): Requires Iceberg REST catalog (Lakekeeper v0.3+) so that Modal containers can read/write the same Iceberg tables as the laptop. Without a REST catalog, the container has no way to discover table snapshots.

**License concern**: Modal is proprietary SaaS (no self-hosted option). Acceptable for a Mode 2 optional compute target (user opt-in; not in the critical path); document in ADR body per ADR-007 license tier policy.

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Watch-list; plan at v0.3; integrate at v1.5+** | Document Modal as Mode 2 escape-hatch pattern; implement `compute="modal"` as optional hint at v1.5+ gated on user demand | ✅ SELECTED — correct sequence; no empirical demand yet; Lakekeeper required first |
| B — Integrate at v0.3 | Add Modal as optional `compute=` target at v0.3 | ❌ REJECTED — Lakekeeper required (not yet deployed at v0.3); proprietary SaaS ADR not yet written |
| C — Use Ray/Anyscale instead | Modal → Daft → Ray dispatch | ❌ REJECTED — Daft→Ray is the v0.5+ Daft integration path; Modal is a simpler Python-function dispatch for the laptop-overflow use case |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A**. No implementation work until v1.5+.

At v0.3:
1. Document Modal as "Mode 2 Python function escape hatch" in `docs/yield-to-giants/mode2.md`
2. Add to watch list with price monitor note (R6 §11 NV-7: pricing can change)

At v1.5+, implementation pattern:
```python
# Nucleus dispatch pattern (conceptual — not v0.1 code)
ctx.run("my_heavy_asset", compute="modal")
# → serialise asset + Iceberg snapshot refs → Modal container
# → container reads/writes same Iceberg tables via Lakekeeper REST
# → Nucleus commits metadata
```

Token management: user provides `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` in `nucleus_project.yaml` env block (user-provisioned, never stored in repo).

**GATE**: Lakekeeper REST catalog (v0.3) is a hard prerequisite. Without it, Modal containers cannot discover Iceberg table snapshots.

---

## Consequences

- **LOC budget impact**: 0 LOC for watch phase; ~150 LOC for v1.5+ integration (if triggered)
- **Dependency**: Modal is proprietary SaaS — no self-hosted fallback; document per ADR-007 license tier policy
- **Depends on**: Lakekeeper ADR (v0.3 catalog); ADR-035 (MotherDuck) for Mode 2 architecture framing
- **Cost risk**: 3.75× multiplier for production non-preemptible workloads; verify current pricing at https://modal.com/pricing at integration time (R6 NV-7)

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §10.2 (Mode 2 hybrid compute)
- `nucleus_architecture_v4.1.md` §14 (yield-to-giants strategy)
- `AGENTS.md §3` Hard Constraint #6 (OIDC delegation — Modal OIDC emission satisfies for downstream S3)
