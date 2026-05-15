# ADR-022: CI/CD, release automation, and community scaffolding

Status: ACCEPTED
Date: 2026-05-15

## Context

Shipping Nucleus on a repeatable cadence needs automated checks that mirror founder intent (constraints in `AGENTS.md` implementation workflow and upgrade-safe design), predictable release choreography, and a minimal community onboarding pack that does not bloat proprietary code paths.

Operating constraints cited: `AGENTS.md` §11 (implementation workflow) and §11.13 (pins, rollback, governance scripts, one-component upgrade PR discipline).

Ratified 2026-05-15: code shipped in commit a41a82c (v0.2.0 handover bundle).

## Decision

Proceed with GitHub-hosted automation and repository hygiene layered **outside** `src/nucleus/`:

- CI matrix spanning Python **3.11 / 3.12** × **Ubuntu / macOS / Windows**.
- Trusted **PyPI publishing via OIDC** (no long-lived passwords in repos).
- **Seven** GitHub Actions workflows already merged for CI, changelog, governance, docs, stale, security posture, releases.
- **Community pack**: `SECURITY.md`, `CODE_OF_CONDUCT.md`, support/governance docs, Dependabot weekly caps, Funding placeholders, CODEOWNERS, issue forms (including wrap-vs-build intake), Makefile helpers, lint hooks, Dockerfile + compose demo scaffold.
- **Pre-commit**: pinned revisions for generic hygiene + **Ruff**, plus repo-local pinning + vocabulary scripts.
- **Release helper script** validating semver alignment, unreleased changelog content, governance suite, pytest; prints tagging commands rather than invoking git directly.

Alternatives deferred: external CI SaaS duplication (would split signal), bespoke release bots without OIDC gates, or heavyweight policy engines inside the codebase.

Alternatives evaluated and rejected:

- **GitLab CI / Drone** — weaker default integration with repo-native OIDC publishers and issue templates chosen for OSS hosting on GitHub; would duplicate workflows already exercised by contributors cloning from GitHub.
- Single-platform CI-only matrix — rejects cross-environment regressions surfaced by Windows shells and macOS file paths encountered in PoC bake-offs.

## Consequences

Positive:

- Faster feedback on contributor PRs; fewer “works on my laptop” regressions across OS/Python pairs.
- PyPI attestations aligned with pinned wheels already produced in CI artifacts.
- Community expectations (conduct, disclosure, sponsorship placeholders) centralized without coupling runtime behavior.

Neutral / upkeep:

- Pin churn on `pre-commit` hook repos and Dependabot PR volume capped via `open-pull-requests-limit: 3`.
- Docker/demo assets are illustrative; upstream MinIO image remains the supported object-store recipe.

Negative / limits:

- OIDC + workflow behavior is GitHub-specific until a future ADR documents a multi-forge port.
- Release script cannot replace human judgment on semantic version bumps or marketing notes.

## Architecture / policy touchpoints

- `AGENTS.md` §11.4 (per-feature workflow), §11.6 (LOC budget script), §11.7 (leak + translation discipline via CI), §11.13 (pins + compatibility matrix expectations).
- Architecture v4.1 experience + coordination layers — automation reflects enforcement, not new product primitives.
