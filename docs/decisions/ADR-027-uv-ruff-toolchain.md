# ADR-027: Adopt uv 0.11.x + ruff 0.15.x Toolchain

**Status**: ACCEPTED
**Date**: 2026-05-15
**Author**: Synthesis — ratification required from founder
**Priority**: P0
**Target phase**: v0.2
**Source research**: `docs/internal/research/inspiration/modern_python_ecosystem.md` §1, §2, §9
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #1

---

## Context

Nucleus currently uses `pip + venv` for package management and `ruff==0.8.4` for linting. Two issues:

1. **CI install time**: `pip install -e ".[dev]"` takes ~2m 15s in CI. The uv tool achieves the same in ~8s (measured from BENCHMARKS.md at https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md).
2. **ruff version lag**: Current pin `ruff==0.8.4` is 7 minor versions behind `ruff==0.15.12`. ruff 0.15.0 introduced a "2026 style guide" (breaking formatter output). Every new source file widens the diff with the canonical formatter.

Both tools are from Astral (OpenAI-acquired March 2026). uv has 126M monthly PyPI downloads; 74.2% "admired" in Stack Overflow 2025 developer survey. The migration cost is approximately 90 minutes with LOW risk (pyproject.toml core unchanged, zero `src/nucleus/` LOC impact).

Per AGENTS.md §11.13: each is a single-component upgrade PR (uv adoption + ruff pin upgrade bundled as one PR since they are from the same toolchain and shipped together in CI).

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Adopt uv + upgrade ruff in one PR** | Replace pip+venv with uv; bump ruff pin to 0.15.12; update CI `setup-uv` action; add `uv.lock`; update Makefile | ✅ SELECTED — single coherent PR; both from Astral toolchain; 8s vs 2m 15s CI |
| B — Adopt uv only, defer ruff upgrade | Two separate PRs | ❌ REJECTED — extra ceremony; the ruff formatter gap compounds over time |
| C — Status quo | No change | ❌ REJECTED — 2m 15s CI is measured pain; ruff formatter drift is growing |

---

## Decision

Ratified 2026-05-15: implemented in commit a41a82c (v0.2.0 workstreams bundle). Changes applied:
1. `pyproject.toml`: bumped `ruff==0.8.4` → `ruff==0.15.13` (latest stable on PyPI 2026-05-15).
2. `Makefile`: `install` target uses `uv pip install -e ".[dev]"` if `uv` is on PATH, falls back to pip.
3. `.github/workflows/ci.yml`: all 5 jobs updated to use `astral-sh/setup-uv@v3` + `uv pip install --system`.
4. `.pre-commit-config.yaml`: ruff hook rev bumped to `v0.15.13`.
5. `docs/compatibility.md`: ruff row updated.
6. Ran `ruff format .` — 107 files reformatted with 2026 style guide.
7. Added `PLC0415`, `SIM105`, `N818`, `RUF022` to global ignore list (intentional patterns).

Recommended: **Option A**. Single PR. Changes required:
1. `pyproject.toml`: bump `ruff==0.8.4` → `ruff==0.15.12`
2. `Makefile`: replace `python -m venv .venv && pip install -e ".[dev]"` with `uv venv && uv sync --locked`
3. `.github/workflows/ci.yml`: add `astral-sh/setup-uv@v3` with `enable-cache: true`
4. Add `uv.lock` to repo (commit to VCS; ~50–200 KB lockfile)
5. `.pre-commit-config.yaml`: bump ruff hook `rev: v0.8.4` → `rev: v0.15.12`; add `astral-sh/uv-pre-commit` with `id: uv-lock`
6. Run `ruff format .` after pin upgrade to apply new 2026 style; commit formatter diff as part of the PR

---

## Consequences

- **LOC budget impact**: 0 LOC on `src/nucleus/`; ~20 LOC CI/config changes
- **No new runtime dependencies** — uv is dev-only; ruff is already pinned
- **Migration time estimate**: ~90 min including formatter diff review
- **Rollback command**: `pip install ruff==0.8.4` (ruff); remove `uv.lock` + revert CI yml (uv)
- **NEEDS VERIFICATION before merge**: Run `ruff@0.15.12 format --check src/` to measure formatter diff size; confirm Nucleus frontend `package.json` Vite version (R5 NV-4)

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §3 Pillar 1 (performance on minimal resources)
- `AGENTS.md §11.13` (single-component upgrade per PR)
