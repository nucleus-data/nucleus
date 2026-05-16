# ADR-023: Performance budget enforcement

Status: ACCEPTED
Date: 2026-05-15
Author: builder (v0.2.0 reconciliation pass)
Source: `docs/internal/research/performance_reliability_targets.md` §2

## Context

Nucleus v0.1.0 ships with qualitative performance targets from `docs/specs/nucleus_architecture_v4.1.md` §16 (boot < 10 s, 100M-row aggregate < 2 s). These targets are validated empirically at PoC milestones (PoC #4: `nucleus up` = 5.82 s / 117.3 MB; WSL Beachhead E2E: 7 s boot) but there is no automated regression gate that catches new code slowing a critical path before it merges.

Wave-1H research (`docs/internal/research/performance_reliability_targets.md`) formalised nine per-operation budget sections from v4.1 §5/§16 and beachhead empirical data. Those budgets now need to be a first-class CI signal, not just a narrative in a research doc.

The anti-over-engineering directive (`.cursor/rules/nucleus.mdc`) explicitly prohibits building measurement infrastructure before the caller exists. A benchmark harness that nobody runs is speculative code. The minimal viable commitment is: (1) adopt the nine-section budget table as the authoritative v0.2 target; (2) stub a script for CI; (3) defer automation to v0.3 when a stable benchmark suite is available.

Ratified 2026-05-15: code shipped in commit a41a82c (v0.2.0 handover bundle).

## Decision

1. **Adopt the numeric budgets in `docs/internal/research/performance_reliability_targets.md` §2 as the authoritative v0.2 performance commitment.** The nine sections (Boot/Startup, Materialise, DuckDB query, Ingest, SQL resolver, Workbench, AI Copilot, Governance scripts, Memory) are the canonical reference.

2. **Establish `scripts/check_perf_budget.py` as a placeholder** that prints the budget table from a machine-readable `pyproject.toml` `[tool.nucleus.perf_budgets]` block and exits 0. The actual benchmark measurements are not automated in v0.2 (defer to v0.3 per §4 below).

3. **Report performance targets as "aspirational (nightly-unverified)"** in public docs until the nightly benchmark CI job exists.

4. **Defer nightly benchmark CI automation to v0.3** (gated on: stable benchmark harness for DuckDB + Polars warm/cold paths, GitHub Actions self-hosted runner or M-series macOS runner available, and `scripts/benchmark_regression.py` ≥ 3 months of baseline data).

## OSS Options Considered

| Option | Reason rejected |
|---|---|
| `pytest-benchmark` embedded in CI | Adds ~200 ms overhead per test; runner-dependent variance makes regression thresholds unreliable for cloud CI (Ubuntu runner ≠ MacBook M3) |
| Codspeed.io / Bencher.dev | External SaaS; ADR-011 operating constraint 11 prohibits external deps without founder ADR |
| Custom `time.perf_counter` microbenchmarks | "Build not wrap" violation; DuckDB already has native benchmark tooling |

## Consequences

**Positive:**

- Nine budget sections adopted as v0.2 standard; no ambiguity about what "fast enough" means.
- `scripts/check_perf_budget.py` stub added to the 11-script governance suite (exits 0; CI green; meaningful output added when measurements are wired in v0.3).
- Codifies the Anti-Over-Engineering directive: measurement infra ships when the benchmark runner is stable, not speculatively.

**Negative / Open:**

- v0.2 ships without automated regression detection. Manual benchmark runs required at release time (developer runs `python scripts/benchmark_regression.py` per AGENTS.md §11.13 upgrade workflow).
- NEEDS VERIFICATION 11.1 from research doc (Polars `engine="streaming"` group-by/sort out-of-core) remains open; do NOT publish the 10 GB materialise target as "guaranteed" until verified against `polars==1.18.0`.

## Architecture Sections Touched

- `docs/specs/nucleus_architecture_v4.1.md` §16 (performance targets)
- `docs/specs/nucleus_architecture_v4.1.md` §5.1 (DuckDB query engine)
- `docs/specs/nucleus_architecture_v4.1.md` §5.2 (Polars DataFrame engine)
- `AGENTS.md` §11.4 (per-feature workflow — step 6 integration run)
- `AGENTS.md` §11.13 (upgrade workflow — benchmark regression gate)

## Rollback

Remove `scripts/check_perf_budget.py` and the `[tool.nucleus.perf_budgets]` block from `pyproject.toml`. Zero production-code impact (stub only).
