# ADR-029: MetricFlow-Compatible `nucleus_semantic.yaml` Contract

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P0  
**Target phase**: v0.3 (decorator design at v0.1/v0.2)  
**Source research**: `docs/internal/research/inspiration/embedded_analytics_bi.md` §9 + §4; `docs/internal/research/inspiration/ai_data_tooling_2026.md` §3  
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #7, §2.1

---

## Context

Two independent research lanes converge on the same requirement:

1. **BI integration** (R7 §9): MetricFlow (Apache-2.0, dbt Core v1.12 May 2026) is the closest open standard for semantic layer definitions. Lightdash, dbt Semantic Layer, and Cube (for self-hosted installations) all consume MetricFlow-compatible YAML. Emitting `nucleus_semantic.yaml` alongside materialised assets enables downstream tools with zero transformation.

2. **AI text-to-SQL accuracy** (R3 §3.1): The Cube.dev paired benchmark (arXiv 2604.25149) proves that a 4 KB semantic document raises LLM text-to-SQL accuracy by +17–23 pp across all frontier models — a larger gain than any model upgrade. The semantic document is the decisive variable; the `nucleus_semantic.yaml` per asset is exactly this document.

The MetricFlow spec defines five metric types: `simple`, `cumulative`, `ratio`, `derived`, `conversion`. YAML structure (per R7 §9 dbt Core v1.12):

```yaml
metrics:
  - name: total_revenue
    type: simple
    label: "Total Revenue"
    measure:
      name: revenue
      agg: sum
    time_spine_required_granularity: day
```

Cube.dev uses Elastic License 2.0 — **cannot be embedded or wrapped** (per AGENTS.md §3 Hard Constraint #2 and R3 §3.2). MetricFlow is Apache-2.0. The correct path is to adopt MetricFlow YAML as the Nucleus semantic schema.

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — MetricFlow-compatible YAML** | `@nucleus.asset(measures=..., dimensions=...)` → emit `nucleus_semantic.yaml` on `nucleus run`. Design kwargs at v0.2; YAML output at v0.3. | ✅ SELECTED — Apache-2.0; converging open standard; dbt v1.12 convergence; AI Copilot multiplier |
| B — Cube.dev native schema | Emit Cube.dev YAML format directly | ❌ REJECTED — BSL license prohibits integration; documentation guide only |
| C — Custom Nucleus semantic format | Invent a Nucleus-native metric YAML | ❌ REJECTED — violates Pillar 4 (familiar UX); fragments the ecosystem |
| D — Defer to v0.5 entirely | No semantic layer until full Copilot | ❌ REJECTED — the decorator kwargs can be designed in at v0.2 at zero cost; delaying forces a breaking API change later |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A**. Implementation sequence:
1. **v0.2 (decorator design)**: Add `measures: list[dict]` and `dimensions: list[str]` optional kwargs to `@nucleus.asset`. No YAML output yet. Forward-compatible parameter.
2. **v0.3 (YAML output)**: Emit `nucleus_semantic.yaml` alongside each materialised asset in the asset output directory. ~200 LOC.
3. **v0.3+ (Copilot integration)**: The `gather_context()` function in `src/nucleus/intelligence/context.py` reads `nucleus_semantic.yaml` and injects into the Copilot prompt alongside schema.

**NEEDS VERIFICATION**: dbt Core v1.12 release date (R7 NV-5: verify at https://docs.getdbt.com/docs/dbt-versions/core-upgrade).

---

## Consequences

- **LOC budget impact**: ~10 LOC (decorator kwargs at v0.2) + ~200 LOC (YAML emitter at v0.3) + ~50 LOC (Copilot context reader at v0.3)
- **No new runtime dependencies**
- **Depends on**: ADR-026 (nucleus.db BI handshake) for the overall asset output bundle pattern; ADR-028 (branch+tag) for snapshot-level semantic versioning context
- **Swap target**: MetricFlow YAML is itself an open standard with multiple consumers; the YAML format is stable as of dbt v1.12

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §7.3 (AI Copilot architecture)
- `nucleus_architecture_v4.1.md` §8.3 (Intelligence layer)
- `nucleus_ctx_sdk_spec.md` §3 (`@nucleus.asset` decorator parameters)
