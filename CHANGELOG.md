# Changelog

All notable changes to **Nucleus** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Per v4.1 §13.3, AI-related APIs (`ctx.agent`, `ctx.copilot`) may have breaking
changes within minor releases with `NucleusAIBreakingChange` warnings instead of
the full deprecation cycle that core data APIs receive.

---

## [Unreleased]

### Added
- _placeholder — features land here as they're merged toward Heartbeat (v0.0.1)_

### Changed
- _placeholder_

### Deprecated
- _placeholder_

### Removed
- _placeholder_

### Fixed
- _placeholder_

### Security
- _placeholder_

---

## [0.0.0] — 2026-05-12 (Pre-Heartbeat — scaffolding only, no runtime code)

This is not a real release. The project is in the **planning + scaffolding** phase.
No code is installable. This entry exists so the changelog has a starting point.

### Added (pre-code scaffolding)
- Full architecture document (`nucleus_architecture_v4.1.md`, 1678 lines)
  incorporating 13 senior-review amendments and 4 follow-up patches.
- Universal AI-agent rules (`AGENTS.md`) with **11 Hard Constraints**.
- Cursor-specific rules (`.cursor/rules/nucleus.mdc`).
- Proof-of-Concept plan (`nucleus_poc_plan.md`) — 5 PoCs gating v0.1.
- Project scaffolding: `pyproject.toml`, `LICENSE` (Apache 2.0), `.gitignore`, `README.md`.
- Engineering conventions (`docs/conventions/engineering.md`) — 18 sections.
- C4 architecture diagrams (`docs/architecture/C4_context.md`, `C4_container.md`).
- Critical sequence: error translation flow (`docs/architecture/sequence_error_translation.md`).
- ADR template (`docs/decisions/_template.md`) + first ADR (`ADR-001-no-iceberg-commit-service.md`).
- Component compatibility matrix (`docs/compatibility.md`).
- Type-mapping pattern doc (`docs/patterns/type_mapping.md`).
- CI workflows (`.github/workflows/ci.yml`, `upgrade-deps.yml`).
- Issue & PR templates (`.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md`).
- Pre-commit hooks (`.pre-commit-config.yaml`).
- Constraint-enforcement scripts (`scripts/`).
- Junior-DE onboarding & learning path (`docs/onboarding/learning_path.md`).

### Notes
- **No package is published to PyPI.** Versions begin with `0.0.1` when Tier 0
  "Heartbeat" produces a first end-to-end runnable slice.
- Project status: **pre-Heartbeat**, solo founder + AI pair.

---

## Versioning policy

| Version range | Meaning |
|---------------|---------|
| `0.0.x` | Pre-Heartbeat / Heartbeat — pre-alpha, may break anything. |
| `0.1.x` | Tier 1 "Foundation" — beachhead-ready. Beta. **`ctx` SDK signatures stabilizing.** |
| `0.2.x` | Tier 2 "Workbench" — adds web IDE + simple Copilot. |
| `0.3.x` | Tier 3 "Connectors" — Lakekeeper, more sources/sinks, dbt-duckdb adapter. |
| `0.5.x` | Tier 4 "Intelligence" — lineage-aware Copilot + `ctx.agent` runtime. (Semantic Knowledge Graph lands v0.7+.) |
| `1.0.0` | **GA.** `ctx` SDK & error types are **stable** per semver. |
| `2.0.0+` | Future major versions. |

Within `0.y.z`:
- `y` bump = significant new functionality OR documented breaking change.
- `z` bump = bug fixes, minor improvements, doc updates.

After `1.0.0`:
- Standard semver. Breaking changes only in major versions.

### Per v4.1 §13.3
AI-namespace APIs (`ctx.agent`, `ctx.copilot`) may have breaking changes in
**minor** versions with a `NucleusAIBreakingChange` warning, NOT the full
deprecation cycle. Core data APIs (`ctx.read`, `ctx.sql`, `ctx.copy_from`,
`ctx.run`, `ctx.asset`) follow strict semver.

---

## Categories explained

- **Added** — for new features.
- **Changed** — for changes in existing functionality (non-breaking unless noted).
- **Deprecated** — for soon-to-be removed features. Lists the version of removal.
- **Removed** — for now removed features.
- **Fixed** — for bug fixes.
- **Security** — in case of vulnerabilities.

---

## How to update this changelog

1. **Every PR** that affects user-visible behavior adds a bullet under `[Unreleased]`.
2. The bullet links to the PR: `- Added `ctx.copy_from` for Postgres (#42)`.
3. Use **past tense**, **imperative-ish**: "Added X", "Fixed Y".
4. Group by category (Added / Changed / etc.).
5. When releasing:
   - Move `[Unreleased]` content under a new dated version section.
   - Recreate empty `[Unreleased]` template at the top.
   - Tag the release in git: `git tag v0.0.1 && git push --tags`.
   - GitHub Releases page is generated from these entries.

When in doubt, see the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) spec.
