# ADR-037: Reorganise Root-Level Markdown Spec Files into `docs/`

| Field | Value |
|---|---|
| **Status** | PROPOSED |
| **Date** | 2026-05-15 |
| **Author** | swarm-implementer (root-cleanup wave) |
| **Reviewers** | Founder |
| **Supersedes** | — |
| **Execution plan** | [docs/reorg/2026-05-15_root_md_reorg.md](../reorg/2026-05-15_root_md_reorg.md) |

---

## Context

As of 2026-05-15, the repository root contains 19 markdown files. 10 of them are large technical specifications (`docs/specs/nucleus_architecture_v4.1.md`, `docs/specs/nucleus_cli_spec.md`, etc.) and one user-setup guide (`SETUP.md`) that are better served from a structured `docs/` hierarchy. Founder explicitly requested cleanup to reduce root-level noise. The issue was surfaced during the PoC #5 external-tester run: new engineers cloning the repo face an overwhelming list of files before finding `README.md`.

Phase 1 of the cleanup (cruft files, stale archive) was executed on 2026-05-15. Phase 2 (this ADR) is the spec-file reorg — deferred until parallel builders (ratification + UI v0.3) complete their waves, to avoid collision on locked files.

---

## Decision

Move 10 root-level spec and plan files to organised subdirectories under `docs/`:

| Current path | New path |
|---|---|
| `SETUP.md` | `docs/onboarding/setup.md` |
| `docs/specs/nucleus_architecture_v4.1.md` | `docs/architecture/architecture-v4.1.md` |
| `docs/specs/nucleus_asset_model_spec.md` | `docs/architecture/asset-model.md` |
| `docs/specs/nucleus_cli_spec.md` | `docs/architecture/cli-spec.md` |
| `docs/specs/nucleus_ctx_sdk_spec.md` | `docs/architecture/ctx-sdk-spec.md` |
| `docs/specs/nucleus_project_anatomy.md` | `docs/architecture/project-anatomy.md` |
| `docs/specs/nucleus_vs_databricks.md` | `docs/architecture/vs-databricks.md` |
| `docs/specs/nucleus_poc_plan.md` | `docs/poc/poc-plan.md` |
| `docs/specs/nucleus_implementation_readiness.md` | `docs/architecture/implementation-readiness.md` |
| `docs/specs/nucleus_red_team_review.md` | `docs/architecture/red-team-review.md` |

Use `git mv` to preserve git history. Update all cross-references in `.md`, `.mdc`, `.yml` files. Rename to kebab-case on move (pending founder confirmation — see Open Questions).

Files that remain at root: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `GOVERNANCE.md`, `MAINTAINERS.md` (standard community files), plus all non-markdown config files.

---

## Consequences

- **LOC delta**: 0 (no code changes)
- **Cross-reference update scope**: ~350+ source files contain filename mentions; of these, ~170 non-Python files contain literal path strings that need updating. Python docstring section-citations (`# Per v4.1 §6.3`) do NOT require updating.
- **Commit strategy**: single atomic commit (`chore: reorg root .md spec files -> docs/architecture/`) — enables clean `git revert <SHA>` rollback.
- **MkDocs nav**: `mkdocs.yml` `nav:` section will need updating in the same commit.
- **`AGENTS.md` §2 Required Reading table**: 9 path references must be updated (currently LOCKED; Phase 2 gate).
- **`.cursor/rules/nucleus.mdc`**: multiple `@`-reference hints must be updated (currently LOCKED; Phase 2 gate).
- **Risk level**: LOW — pure file moves + text substitution, zero runtime impact.

---

## Options Considered

| Option | Verdict |
|---|---|
| Keep all spec files at root | REJECTED — root is already at 19 .md files; external testers found it confusing |
| Move spec files to `docs/` (this ADR) | ACCEPTED — conventional for OSS repos; improves discoverability |
| Delete spec files, rely on MkDocs site only | REJECTED — docs must remain version-controlled alongside code |

---

## Open Questions

1. **Rename convention**: Move as kebab-case (e.g., `architecture-v4.1.md`) or preserve snake_case? — see [§E.2 of execution plan](../reorg/2026-05-15_root_md_reorg.md#e2--file-naming-convention-on-move).
2. **Docker Compose consolidation**: Consolidate 3 root `docker-compose*.yml` files, or keep at root? — see [§E.1](../reorg/2026-05-15_root_md_reorg.md#e1--docker-compose-consolidation).
3. **MkDocs nav assignment**: Assign nav update to Phase 2 executor or handle separately? — see [§E.3](../reorg/2026-05-15_root_md_reorg.md#e3--mkdocs-nav-section).

---

## Architecture Sections Touched

- v4.1 §1.5 (beachhead metric — DX improvement)
- v4.1 §2 (documentation standards — spec files are primary refs)

## Ratification Gate

Execute Phase 2 only after:
1. Founder ACCEPTS this ADR
2. Ratification builder wave completes
3. UI v0.3 builder wave completes

See [execution plan](../reorg/2026-05-15_root_md_reorg.md) Steps 1–8 for the full sequenced procedure.
