# Onboarding Docs

Internal-facing learning material for the solo founder and future contributors. Per [`AGENTS.md`](../../AGENTS.md) §2 (Required Reading), every new contributor — human or AI agent — reads the nine architecture / spec docs in order before any non-trivial contribution. Onboarding docs here are the **scaffolding** that makes that reading productive, not a substitute for it.

This file is a navigation index. Onboarding files are *project-specific* — generic Python / SQL / Iceberg tutorials live elsewhere on the open web and are linked from the learning path, not duplicated here.

---

## Files

| File | Audience | Purpose | Size |
|---|---|---|---|
| [quickstart.md](./quickstart.md) | Junior DE / new contributors | 30-minute hands-on guide from `git clone` to first materialized Iceberg asset — honest about v0.1 stubs (2026-05-13) | ~3 KB |
| [learning_path.md](./learning_path.md) | Solo founder | Sequential, project-specific learning plan — ~6-10 hrs/wk alongside coding; each module ends in a concrete exercise that becomes useful Nucleus code | ~20 KB |

---

## Conventions

- **Internal, not public.** Onboarding is for contributors. End-user walkthroughs live in [`../recipes/`](../recipes/) and the (future) public site.
- **Build to learn.** Every module ends in a concrete exercise that becomes shipped Nucleus code — no theory-only lessons.
- **Honest about gaps.** Where the founder doesn't know something yet, the doc says so. False expertise produces worse code than admitted gaps.
- **Linked, not duplicated.** Generic Python / SQL / Docker references are linked to their canonical sources, not re-explained here.
- **Engineering rules win.** When `learning_path.md` and [`../conventions/engineering.md`](../conventions/engineering.md) disagree, conventions are authoritative — file an issue against the learning path.

---

## Required reading order (per [`AGENTS.md`](../../AGENTS.md) §2)

The learning path is the **prerequisite**; the architecture docs below are the **substance**:

1. [`../specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) — single source of truth
2. [`../specs/nucleus_vs_databricks.md`](../specs/nucleus_vs_databricks.md) — what we are and aren't
3. [`../specs/nucleus_ctx_sdk_spec.md`](../specs/nucleus_ctx_sdk_spec.md) — the developer contract (the product)
4. [`../specs/nucleus_asset_model_spec.md`](../specs/nucleus_asset_model_spec.md) — fundamental data primitive
5. [`../specs/nucleus_project_anatomy.md`](../specs/nucleus_project_anatomy.md) — user project layout
6. [`../specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) — CLI surface
7. [`../specs/nucleus_poc_plan.md`](../specs/nucleus_poc_plan.md) — PoCs gating v0.1
8. [`../specs/nucleus_implementation_readiness.md`](../specs/nucleus_implementation_readiness.md) — go/no-go checklist
9. [`../specs/nucleus_red_team_review.md`](../specs/nucleus_red_team_review.md) — adversarial review

Total reading time: ~3 hours.

---

[← `AGENTS.md` §2 (Required Reading)](../../AGENTS.md) · [Sibling — conventions/](../conventions/README.md) · [Sibling — decisions/](../decisions/README.md) · [Sibling — recipes/](../recipes/README.md)

*Last updated 2026-05-13. Add new onboarding modules by appending to `learning_path.md` first; only spawn a new file when a module exceeds ~5 KB on its own.*
