# ADR-040: `cli` and `workbench` are peers at Layer 4 — same-depth imports allowed

> **Status**: ACCEPTED — 2026-05-15
> **Date**: 2026-05-15
> **Decider(s)**: Solo founder (close-out batch builder, v0.2.0).
> **Tags**: layering, governance, ci, layer-4-experience, v0.2-close-out
> **Supersedes**: (none — first ADR scoping intra-Experience-layer imports)
> **Related**: `docs/specs/nucleus_architecture_v4.1.md` §8.1 (Layer 4 Experience surface matrix) · §6 (layered model); ADR-016 (Workbench MVP — Fork B); ADR-018 (`nucleus dagit` escape hatch); ADR-039 (install-size split — `[workbench]` extras carve-out); `docs/conventions/engineering.md` §3.1 (layers depend down, never up); `scripts/check_layering.py` (CI enforcement); `AGENTS.md` §11.5 (Wrap-vs-build ADR template) · `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND.

---

## Context

`scripts/check_layering.py` enforces `docs/conventions/engineering.md` §3.1: a module in layer N may import from layer N or below, never higher. The script's `LAYERS` list ordered the surfaces sequentially:

```python
LAYERS = ["_internal", "physics", "engines", "coordination", "intelligence", "ctx", "cli", "workbench"]
```

`workbench` sat at index 7 and `cli` at index 6. The check used `LAYERS.index(...)` for the comparison, so an import like `from nucleus.workbench.cli import app` inside `src/nucleus/cli/main.py` was flagged as an upward import:

```
src/nucleus/cli/main.py:1334
              cli imports nucleus.workbench.cli (workbench)
    reason: upward import: cli -> workbench
```

This violation was a pre-existing FAIL in the v0.2.0 mega-batch builder report. The import itself is intentional and correct: `nucleus.cli.main` registers the Workbench Typer sub-app via `app.add_typer(_workbench_app, name="workbench", ...)` per ADR-016. Removing it would break `nucleus workbench up`, the primary v0.2 GUI entrypoint.

Per `docs/specs/nucleus_architecture_v4.1.md` §8.1 ("Layer 4: Experience — Surfaces by Release"), the architecture explicitly classifies **all of `ctx`, `cli`, and `workbench` as Layer 4 (Experience) surfaces** — not stacked sub-layers. They are siblings, like `dbt` CLI and `dbt` IDE, or `git` CLI and `gitk` GUI. Composing one Experience surface from another (CLI registering the GUI sub-command) is normal and architecturally healthy.

### Forces

- **Force A — Strict directional rule.** The original `LAYERS.index(...)` comparison gave one canonical order, easy to read and easy to enforce. Adding peer-layer semantics complicates the model.
- **Force B — Architecture intent.** v4.1 §8.1 explicitly lists multiple L4 surfaces. Imports between same-depth surfaces are not "upward" in the architectural sense; they are composition of peers.
- **Force C — Anti-over-engineering.** The minimal correct fix is preferred (`.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND). A heavier "plugin entrypoint" pattern (Path C in the close-out brief) was considered but rejected as speculative.
- **Force D — Reproduction of `dbt`/`Cursor`/`Vercel` UX.** Per `docs/specs/nucleus_architecture_v4.1.md` §8.3, we deliberately copy UX patterns where one tool exposes both CLI and GUI surfaces under one binary. The CLI must be allowed to register the GUI sub-command directly.

---

## OSS / alternatives considered

This ADR is a governance / CI rule change, not a wrap-vs-build call, but for completeness:

- **Path A — Move registration into a workbench-side `register(app)` hook called from `cli/main.py`.** Rejected: the import inversion still produces an upward dotted reference (`from nucleus.workbench import register`), and adds a new layer-2 callable surface for no architectural benefit. Higher LOC, same outcome.
- **Path B — Permit `cli ↔ workbench` cross-import as Layer-4 peers.** **Selected.** Smallest change; matches v4.1 §8.1 architectural intent; ~5 lines of script delta; no runtime code change.
- **Path C — Late-bind the workbench Typer app via setuptools entry-points.** Rejected: violates Hard Constraint #2 ("No public plugin SDK in v1") in spirit, adds packaging complexity, and would require users to reinstall to register sub-commands. Disproportionate to the problem.

---

## Decision

> **Layer membership is now keyed by `LAYER_DEPTH: dict[str, int]` rather than `LAYERS.index(...)`. Layers at the same depth are peers and may import freely from each other. `ctx`, `cli`, and `workbench` all have depth `4` — Layer 4 (Experience) per `docs/specs/nucleus_architecture_v4.1.md` §8.1. Any import between two Layer-4 surfaces is therefore allowed.**

Concretely, in `scripts/check_layering.py`:

```python
LAYER_DEPTH: dict[str, int] = {
    "_internal": -1,    # shared toolbox; sits below all real layers
    "physics": 0,       # L0
    "engines": 1,       # L1
    "coordination": 2,  # L2
    "intelligence": 3,  # L3
    "ctx": 4,           # L4 — SDK surface
    "cli": 4,           # L4 — operator surface (peer of ctx + workbench)
    "workbench": 4,     # L4 — GUI surface (peer of ctx + cli; ADR-016 + ADR-040)
}
```

The violation rule changes from `imported_idx > importer_idx` to `imported_depth > importer_depth`. All four lower layers (physics, engines, coordination, intelligence) keep the strict directional rule; only same-depth peers gain the new freedom.

### What is unchanged

- `_internal/` is still depth `-1` and forbidden from importing any layer.
- Cross-engine imports (`engines/duckdb_engine.py` → `engines/polars_engine.py`) remain forbidden by the separate Rule 3 (engineering.md §3.2).
- All downward imports remain allowed (ctx → coordination, workbench → coordination, cli → ctx, etc.).
- Imports from non-Layer-4 surfaces UP into Layer 4 (e.g. `coordination` → `cli`) remain forbidden.

### What is newly allowed

- `cli` ↔ `workbench` (the immediate motivating case)
- `cli` ↔ `ctx`
- `workbench` ↔ `ctx`

In practice we expect `cli → workbench` and `workbench → ctx` to be the active edges; `ctx → cli` and `ctx → workbench` would be unusual (the SDK should not depend on UI surfaces) and would still be governance-reviewable in PR.

---

## Consequences

### Positive

- The pre-existing `cli/main.py:1334` layering FAIL is cleared. v0.2.0 governance suite returns to all-green per `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md` §3.
- Architecture intent (`v4.1 §8.1`) is now mirrored faithfully in the CI rule. Future Layer-4 surfaces (Marimo at v0.3, Portal at v0.5) can be added at depth `4` without reopening this discussion.
- The change is local to one script (~10 LOC delta). No runtime code change. No new module, no new test infrastructure.

### Neutral

- Reviewers must now read the depth dict, not the list-index comparison. Mitigated by inline comments (`# L4 — operator surface (peer of ctx + workbench)`) on every `LAYER_DEPTH` entry.

### Negative

- A new failure mode: someone could legitimately argue that `ctx → cli` is wrong (the SDK should not depend on the operator surface). The current rule change permits it because they are peers. Mitigation: the architecture review checklist (`AGENTS.md` §11.4) and PR review continue to catch this; a future ADR can introduce a directional matrix among peers if drift becomes real. Per Anti-Over-Engineering: not added today on speculation.

---

## Compliance / verification

- [x] `scripts/check_layering.py` PASS after change (verified locally, 2026-05-15).
- [x] No `_internal` regressions: depth `-1` keeps Rule 1 firing.
- [x] No cross-engine regression: Rule 3 unchanged.
- [x] Existing `cli → ctx`, `cli → coordination`, `workbench → coordination`, `workbench → ctx` imports continue to PASS (downward direction).
- [x] `cli/main.py:1334` (`from nucleus.workbench.cli import app`) now allowed.
- [x] No new dependencies; no `pyproject.toml` changes.
- [x] LOC budget unchanged (governance script delta ≈ +10 lines net, well within v0.2 ceiling).
- [x] Test added: not strictly required (rule is data-only), but `scripts/check_layering.py --json` is exercised by CI on every push (`.github/workflows/governance.yml`).
- [x] **Re-verified 2026-05-16** during the v0.2.0 ultimate-sprint close-out builder pass: `python scripts/check_layering.py` exits `0`; `tests/coordination/test_snapshot_maintenance.py::test_expire_wraps_pyiceberg_exception` PASSES in full pytest sweep (the cross-test flake the mega-batch builder flagged is no longer reproducible — the in-test 0.1-day timestamp spread on M5 snapshots eliminates the millisecond-collision race).

---

## Open questions

1. **Should `ctx → cli` ever be permitted in practice?** The current rule allows it. Recommendation: enforce by review only at v0.2; add a direction matrix among Layer-4 peers if drift surfaces. Defer to v0.3 if needed.
2. **Marimo at v0.3 + Portal at v0.5.** Both are Layer-4 surfaces per v4.1 §8.1. They will join `LAYER_DEPTH` at depth `4` when their `src/nucleus/<surface>/` modules land. This ADR sets the precedent.

---

## References

- `docs/specs/nucleus_architecture_v4.1.md` §8.1 (Layer 4 Experience — Surfaces by Release table) · §8.2 (Design Principles — "progressive disclosure") · §8.3 (UX patterns borrowed from dbt / Dagster / Cursor / Vercel / Supabase / Linear / Marimo).
- `docs/conventions/engineering.md` §3.1 (Layers depend down, never up) · §3.2 (No cross-engine imports) · §2.4 (Package boundaries).
- `scripts/check_layering.py` (the CI enforcement; this ADR's primary code change).
- ADR-016 (Workbench MVP — Fork B; defines `src/nucleus/cli/commands/workbench.py` and the `app.add_typer(...)` registration site).
- ADR-018 (`nucleus dagit` escape hatch — companion v0.1.1 cli/workbench surface decision).
- ADR-039 (install-size split — `[workbench]` extras carve-out).
- `AGENTS.md` §11.5 (Wrap-vs-build ADR template) · §11.10 (single-file PR discipline) · §3 #2 (No public plugin SDK in v1) · §3 #8 (LOC budget).
- `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND ("Default to less"; "No premature abstractions").
