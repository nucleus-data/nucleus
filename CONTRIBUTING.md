# Contributing to Nucleus

> **Status**: pre-Heartbeat — only `src/nucleus/errors.py` + thin layer stubs exist. Solo founder + AI workflow today; external contributors at v0.5+.
> **Authority**: this doc operationalizes [`AGENTS.md`](AGENTS.md) §11. If it conflicts with [`AGENTS.md`](AGENTS.md) or [`docs/conventions/engineering.md`](docs/conventions/engineering.md), **the source docs win** — fix this one via PR.
> **Read first**: [`AGENTS.md`](AGENTS.md), [`docs/conventions/engineering.md`](docs/conventions/engineering.md), [`SETUP.md`](SETUP.md), [`.cursor/rules/nucleus.mdc`](.cursor/rules/nucleus.mdc).

## §1. Who this is for

- **Now**: founder + AI assistants (Cursor / Claude Code / Codex).
- **v0.5+**: external contributors after the public `ctx` SDK surface stabilizes.
- The workflow is identical regardless of who opens the PR — only the provenance label differs (`provenance:human` / `provenance:ai-assisted` / `provenance:ai-bulk`, per `engineering.md §13.2`).
- AI agents reading this autonomously: also read `AGENTS.md §10` and `§11` end-to-end first.

## §2. The "is this PR ready?" 9-question gate

Each "no" = stop and fix.

1. **Docs read?** Official docs for every wrapped library this PR touches? (Hard Constraint #10, `AGENTS.md §11.12`)
2. **One feature?** ONE feature, ≤ 500 LOC, ≤ 5 files? (`AGENTS.md §11.10`, `engineering.md §10.3`)
3. **All 6 steps?** Per-feature workflow finished steps 1-6? ([§4](#4-the-per-feature-workflow))
4. **Tests first?** Tests added *before* implementation? (`AGENTS.md §11.4` step 2)
5. **Pinned?** All runtime deps still `package==X.Y.Z`? (Hard Constraint #11)
6. **Beachhead?** Serves (or doesn't hurt) the **<30-min** target? (architecture v4.1 §1.5)
7. **Errors translated?** Every external exception caught at a layer boundary becomes a `NucleusError`? (v4.1 §6.4)
8. **LOC budget?** If `src/` LOC grew, is `docs/budget_history.md` updated and the tier ceiling respected? (`AGENTS.md §11.6`)
9. **New library?** If wrapping a new lib, is `docs/internal/research/<library>.md` written from official docs? (`AGENTS.md §11.12`)

## §3. Branching and commits

**Branch**: `<type>/<short-desc>`, lowercase, hyphenated — e.g. `feat/copy-from-postgres`, `fix/iceberg-commit-retry`, `chore/upgrade-ruff`, `docs/contributing-guide`, `poc/1-dagster-error-translation` (in `/poc/`, NOT `/nucleus/`), `adr/002-engine-protocol`.

**Commits**: Conventional Commits (`engineering.md §10.1`) — `<type>(<scope>): <subject ≤72 chars>`. Body explains WHY (not WHAT). Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`, `style`, `revert`. Scopes: `ctx`, `cli`, `engines`, `coordination`, `physics`, `intelligence`, `errors`, `scripts`, `docs`, `ci`, `adr`, `poc`. DCO sign-off (`git commit -s`) required when external contributors arrive (v0.5+); build the habit now. `main` is protected; **squash-merge only** — the squash subject becomes canonical history.

## §4. The per-feature workflow

Six steps from `AGENTS.md §11.4`. PowerShell shown for the primary (Windows) developer.

**Step 1 — Wrap-vs-build check** (~5 min, human). Ask: "Is there production-grade OSS that already does this?" (`.cursor/rules/nucleus.mdc` table). Wrap path = note in PR body. Build path = ADR via `docs/decisions/_template.md` → `docs/decisions/ADR-NNN-<title>.md` (next is **ADR-002**; status starts `Proposed`, transitions to `Accepted` in the same PR). Wrapping a new dep = `docs/internal/research/<library>.md` is **mandatory** before merge.

**Step 2 — Spec the tests** (~15 min, human). Tests come *before* implementation. Mirror `src/` per `engineering.md §6.2`:

```powershell
New-Item -ItemType File tests\coordination\test_asset_materialization.py
pytest tests\coordination\test_asset_materialization.py -v --no-cov  # MUST fail
```

Each test cites the architecture section + the failure mode it guards (`# Guards v4.1 §6.4 — NucleusCommitConflictError translation`).

**Step 3 — AI scaffolds the implementation** (~10 min, AI). Use the **Composer Prompt Template** from `.cursor/rules/nucleus.mdc`. Required `@`-references: `@AGENTS.md`, `@docs/specs/nucleus_architecture_v4.1.md`, the `@<spec_file>.md`, an `@<existing_pattern>.py`, the `@<test_file>.py`. Constraints: ≤ 500 LOC; **single file** unless an exception in `.cursor/rules/nucleus.mdc` "Single-File Discipline" applies.

**Step 4 — AI expands tests** (~15 min, AI). Edge cases + regressions; each test cites the failure mode it guards in a comment.

**Step 5 — Human review** (~30 min, human). Run the §2 nine-question gate + the **AI Output Verification Checklist** from `.cursor/rules/nucleus.mdc` (imports actually exist, method calls match pinned-version docs, no `dagster.*` / `duckdb.*` / `polars.*` classnames in user-facing strings, returns `NucleusError`, vocabulary clean, docstring cites architecture). Read the diff line by line.

**Step 6 — Integration run** (~10 min, automated). PowerShell, `.venv` active — easiest: `make ci` (after `winget install GnuWin32.Make`). Manual equivalent: `ruff check . ; ruff format --check . ; mypy ; pytest -m "not integration and not slow"` followed by `python scripts\loc_budget.py --report` and the four guard scripts (`check_pinning`, `check_layering`, `dagster_leak_check`, `check_vocabulary`). All must pass. Pre-commit hooks (`pre-commit install`) run most of this on `git commit`.

## §5. Pull request etiquette

- Use [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md); fill EVERY section.
- Title matches the conventional-commit prefix: `feat(coordination): wrap Dagster materialize() in Asset Materialization Adapter`.
- Body must include LOC budget delta (`Cumulative LOC: 3,142 / 8,000 (v0.1 ceiling)`), Hard Constraints touched, provenance label.
- One PR = one feature. Refactors get their own PR. Drafts: open as Draft (or prefix title `[WIP]`).
- Size: target ≤ 300 LOC, hard limit 600 LOC excluding tests + generated (`engineering.md §10.3`).

## §6. ADR workflow

Triggers: wrap-vs-build "build" choice; swap-target choice (Constraint #9); public API change (`ctx.*` / `nucleus.cli.*`); abstraction boundary shift; major dep version upgrade (`X.y.z → X+1.y.z`, per `AGENTS.md §11.13`). Copy [`docs/decisions/_template.md`](docs/decisions/_template.md) → `docs/decisions/ADR-NNN-<title>.md` (sequential — model after [`ADR-001-no-iceberg-commit-service.md`](docs/decisions/ADR-001-no-iceberg-commit-service.md)). Status starts `Proposed`, transitions to `Accepted` or `Rejected` in the same PR. Cite the architecture section it touches; if the ADR refines architecture, link from `docs/specs/nucleus_architecture_v4.1.md` back to the ADR.

## §7. Working with AI (rules for the human)

These apply to YOU, not the AI. The AI does what you tell it; the discipline is yours.

- **Author the boundaries; let AI fill the inside** (`AGENTS.md §11.2`).
- **Verify against official docs** (Hard Constraint #10). Cite the docs URL in the import comment. Never accept AI-suggested wrapped-lib calls without confirming the API exists.
- **Log hallucinations** in `docs/internal/research/ai_hallucinations.md`.
- **Risky/Bad categories** (`AGENTS.md §11.3`) — do NOT accept AI authorship for: Error Translation Layer, `ctx.sql` Jinja resolver core, concurrency / atomicity decisions, performance-critical paths, schema evolution edge cases, direct Dagster internals.
- **New dep proposed by AI?** Write `docs/internal/research/<library>.md` BEFORE merging; confirm version exists on PyPI; update [`docs/compatibility.md`](docs/compatibility.md).
- **No bulk upgrades.** One component per PR (`AGENTS.md §11.13`).

## §8. Issue triage

Templates: [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) (`bug_report.yml`, `feature_request.yml`, `adr_proposal.yml`). Labels: `bug`, `feature`, `adr`, `docs`, `poc`, `chore`, `security`; tier (`tier-0`/`tier-1`/`tier-2`); severity (`blocker`/`major`/`minor`/`cosmetic`); auto (`weekly-audit` from `.github/workflows/upgrade-deps.yml`). All bugs need a **minimal reproduction** (without one, label `needs-repro` and ask). All feature requests pass the **8-question gate** in `AGENTS.md §5` before being labeled `accepted` — "Defer to v0.X" is a valid answer.

## §9. Code review checklist (paste into PR comments)

```markdown
- [ ] All 11 Hard Constraints satisfied (or violation justified in body)
- [ ] No hallucinated APIs (every external call exists in pinned-version docs)
- [ ] All exceptions translated to NucleusError (no raw external exceptions past coordination/)
- [ ] Vocabulary clean (engineering.md §15)
- [ ] Tests passing locally + in CI (lint + type + unit; integration if relevant)
- [ ] LOC under tier ceiling (`scripts/loc_budget.py --report`)
- [ ] Docs updated as needed: docs/internal/research/, docs/compatibility.md, ADR, CHANGELOG
- [ ] PR template filled completely; no empty sections
```

## §10. What we don't accept

Rejected on sight:

- PRs that **break the <30-min beachhead** (architecture v4.1 §1.5).
- PRs that add a **non-swappable Tier 1/2 dependency** (Hard Constraint #9).
- PRs that **introduce vocabulary outside `engineering.md §15`**.
- PRs that **bulk-upgrade dependencies** (`AGENTS.md §11.13`).
- PRs that **mix architectural change with implementation**. Split: ADR PR first, implementation PR second.
- PRs that **disable a constraint script "temporarily"**. Fix the violation; don't silence the guard.
- PRs that **delete tests to make a build pass**.
- PRs that use **`git commit --no-verify`** without an emergency justification in the body.

## §11. Getting unstuck

| Stuck on… | Where to look |
|---|---|
| Architecture | `docs/specs/nucleus_architecture_v4.1.md §1.5` (beachhead) + `AGENTS.md §12`. Apply the 8-question gate (`AGENTS.md §5`). |
| Vocabulary | `engineering.md §15`, `AGENTS.md §7`. `python scripts\check_vocabulary.py` lists banned terms. |
| Tooling / install | [`SETUP.md`](SETUP.md) §7 — common fixes for first-run issues. |
| Pinning mismatch | `python scripts\check_pinning.py` + `SETUP.md §7`. Single-component upgrade workflow in `AGENTS.md §11.13`. |
| AI gave me garbage | Log it in `docs/internal/research/ai_hallucinations.md`. Re-prompt with a stricter Composer template. |
| Junior DE overwhelm | [`docs/onboarding/learning_path.md`](docs/onboarding/learning_path.md). |

## §12. Useful links

[`AGENTS.md`](AGENTS.md) · [`docs/conventions/engineering.md`](docs/conventions/engineering.md) · [`docs/onboarding/learning_path.md`](docs/onboarding/learning_path.md) · [`.cursor/rules/nucleus.mdc`](.cursor/rules/nucleus.mdc) · [`docs/compatibility.md`](docs/compatibility.md) · [`docs/decisions/`](docs/decisions/) · [`docs/security/threat_model_v0.md`](docs/security/threat_model_v0.md) · [`docs/specs/nucleus_architecture_v4.1.md`](docs/specs/nucleus_architecture_v4.1.md) · [`SETUP.md`](SETUP.md) · [`Makefile`](Makefile) (`make help`)

---

*This file is operational, not aspirational. If a workflow described here doesn't match how the repo actually works, the doc is wrong — fix it via PR.*
