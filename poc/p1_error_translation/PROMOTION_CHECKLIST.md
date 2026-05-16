# PoC #1 Promotion Checklist

**Source**: `poc/p1_error_translation/translator.py` (17 cases: 3 baseline + 14 new + `_iter_causes` refactor + `NucleusInternalError` catch-all).
**Target**: `src/nucleus/coordination/error_translation.py`.
**Triggers**: ADR-003 (pyiceberg 0.8.1→0.11.x) PR opens automatically on completion.
**Discipline**: mechanical rails only; wording sign-off lives in `REVIEW_NOTES.md`. Both green before the promotion PR opens.

## §1 Verification gates (all GREEN)

- [ ] `pytest poc/p1_error_translation/ -v` → 17/17 pass.
- [ ] `python scripts/dagster_leak_check.py` → exit 0; no `dagster.*` outside `coordination/`/`tests/coordination/`/`poc/`; no leaked classnames in any captured CLI output.
- [ ] `python scripts/check_vocabulary.py` → exit 0 across all touched files (`AGENTS.md` §7).
- [ ] `mypy --strict poc/p1_error_translation/translator.py` → 0 errors. **Risk**: `cause: BaseException | None` defaults in `errors.py:75–96` must keep their explicit annotations or strict-mode trips on `__cause__` reassignment — run early.
- [ ] `ruff check poc/p1_error_translation/` → 0 errors.
- [ ] LOC budget: target ≤ 500 LOC for the promoted file. Current source = **343 LOC**, well under. Re-verify with `python scripts/loc_budget.py` after move.

## §2 Wording review (block until founder signs)

- [ ] `REVIEW_NOTES.md` Approver Checklist all 7 items ticked.
- [ ] H14 routing decision recorded inline: ☐ Option A (keep + soften msg) ☐ Option B (ship as-is + follow-up issue tracking the `NucleusTimeoutError` split).
- [ ] If any of H3 / H4 / H7 / H9 rewrites accepted, applied to `translator.py` **before** the `cp` step in §3.

## §3 Promotion mechanics

- [ ] `cp poc/p1_error_translation/translator.py src/nucleus/coordination/error_translation.py`.
- [ ] Update test imports: `from poc.p1_error_translation.translator import` → `from nucleus.coordination.error_translation import` (currently zero callers since v0.1 not implemented).
- [ ] Add `error_translation` to `src/nucleus/coordination/__init__.py` exports (file does not yet exist — create with single re-export of `translate`).
- [ ] Move tests: `poc/p1_error_translation/test_translator.py` → `tests/coordination/test_error_translation.py` (per `dagster_leak_check.py:54` allowed-imports policy).
- [ ] Update `docs/specs/nucleus_architecture_v4.1.md` §6.4 — drop "PoC #1 validates feasibility" caveat; promote draft → shipping.
- [ ] Append row to `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.6 apply log.
- [ ] Mark PoC #1 COMPLETE in `docs/specs/nucleus_poc_plan.md` §1 + flip `[ ] PoC #1` checkbox in `AGENTS.md` §1 to `[✓]`.
- [ ] Open ADR-003 PR (separate PR, not bundled).

## §4 Post-promotion verification

- [ ] CI green on the promotion PR (pytest, mypy, ruff, vocab, leak-check, LOC budget).
- [ ] Beachhead E2E passes — or log "deferred until PoC #5 lands" in PR description if `docs/specs/nucleus_poc_plan.md` §5 not yet implemented.
- [ ] `python scripts/loc_budget.py` confirms proprietary LOC under v0.1 ceiling (8,000 LOC per `pyproject.toml:291`).

## §5 Rollback plan

`git revert <promotion_commit_sha>` (promotion PR uses *Squash and merge* so this is atomic). The translator stays in `poc/p1_error_translation/` for one minor version (v0.1.0 → v0.1.1) as a dual-source. Remove `poc/` copy only after **30 consecutive days** of zero `NucleusInternalError` fallbacks attributable to translator gaps.
