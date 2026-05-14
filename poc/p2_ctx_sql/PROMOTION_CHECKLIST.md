# PoC #2 Promotion Checklist

**Source**: `poc/p2_ctx_sql/resolver.py` (169 LOC) + `test_resolver.py` (222 LOC, 16 cases). **Target**: `src/nucleus/coordination/sql_resolver.py` — named in `sequence_query.md` §1; consistent with the `coordination/` discipline `dagster_leak_check.py:53-58` allow-lists. Not `src/nucleus/sql/jinja_resolver.py` (no precedent; allow-list would need amending). Founder may override at PR time.
**Trigger**: none at the resolver level. If Option B at T9 (new `NucleusAssetGraphError`), ADR-006 must land **before** this promotion. **Discipline**: mechanical rails only; wording sign-off lives in `REVIEW_NOTES.md`. Both green before the PR opens.

## §1 Verification gates (all GREEN)

- [ ] `pytest poc/p2_ctx_sql/ -v` → 16/16 pass.
- [ ] `python scripts/dagster_leak_check.py` → exit 0. Resolver does NOT import Dagster; jinja/duckdb/polars/pyiceberg substring guards covered by C7 + a one-line extension of `dagster_leak_check.py:62` (per `sequence_query.md` §5 acceptance #6).
- [ ] `python scripts/check_vocabulary.py --paths poc/p2_ctx_sql/` → exit 0 (`AGENTS.md` §7).
- [ ] `mypy --strict poc/p2_ctx_sql/resolver.py` → 0 errors. **Risk**: `Callable[[str], str]` is positional-only — capture signature snapshot per ADR-005 Verification plan #2.
- [ ] `ruff check poc/p2_ctx_sql/` → 0 errors.
- [ ] LOC budget: 169 LOC, well under v4.1 §5.6.0's hard ceiling of **2500 LOC** for resolver + Jinja + ref/source. Re-verify with `python scripts/loc_budget.py --warn`.

## §2 Wording review (block until founder signs)

- [ ] `REVIEW_NOTES.md` Approver Checklist all 9 items ticked.
- [ ] **T9 decision** recorded (THE blocker): ☐ Option A (reuse + fix `sorted()` bug; independent of ADR-006) · ☐ Option B (new `NucleusAssetGraphError`; **ADR-006 must land first**) · ☐ Option C (drop cycle from resolver; remove T9; update `sequence_query.md` §3.1).
- [ ] If T4 / C4 / C5 / T10 rewrites accepted, applied to `resolver.py` **before** the `cp` step in §3.

## §3 Promotion mechanics

- [ ] `cp poc/p2_ctx_sql/resolver.py src/nucleus/coordination/sql_resolver.py`; add `# Stability: Beta` to module docstring (ADR-005 §1; tiers Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0 per §2 row 2).
- [ ] Add `resolve_sql` to `src/nucleus/coordination/__init__.py` (create the file if PoC #1 has not promoted; package `__all__` stays Internal until `ctx.sql` wraps it).
- [ ] Move tests: `test_resolver.py` → `tests/coordination/test_sql_resolver.py` (matches PoC #1 convention; `dagster_leak_check.py:54` allow-list covers it). Update test imports `poc.p2_ctx_sql.resolver` → `nucleus.coordination.sql_resolver`. *(Zero callers in v0.1.)*
- [ ] Update `nucleus_architecture_v4.1.md` §5.6 / §5.6.0 — flip "PoC #2 validates feasibility" hedge to "shipping in v0.1".
- [ ] Update `docs/architecture/sequence_query.md` §1 Status; retarget the `poc/p2_ctx_sql/resolver.py` line refs in §2 / §3.1 to the new path.
- [ ] Mark PoC #2 PASS in `nucleus_poc_plan.md` §2 (use §12 PoC Report Template). The `[ ] PoC #2-5` checkbox in `AGENTS.md` §1 stays unchecked until PoC #5 also completes.
- [ ] **If Option B at T9**: open ADR-006 PR (separate; NOT bundled).
- [ ] `CHANGELOG.md` "Unreleased": `sql_resolver: Internal → Beta, see ADR-005 §2 row 2`. If Option B, also `errors: NucleusAssetGraphError added, Stable, see ADR-006`. Bump LOC row in `docs/budget_history.md`.

## §4 Post-promotion verification

- [ ] CI green (pytest, mypy --strict, ruff, vocab, leak-check, LOC budget).
- [ ] `python scripts/loc_budget.py` confirms `src/nucleus/` under v0.1 ceiling (8,000 per `pyproject.toml`).
- [ ] `python scripts/dagster_leak_check.py` exit 0 across the new `sql_resolver.py` (Layer-2 sibling to `error_translation.py`, not a Dagster consumer).
- [ ] Beachhead E2E (`scripts/beachhead_e2e.py`) — log "deferred until PoC #5 lands; placeholder contract preserved" in PR description (mirrors PoC #1).

## §5 Rollback plan

`git revert <promotion_commit_sha>` (PR uses *Squash and merge* → atomic). Resolver stays in `poc/p2_ctx_sql/` for one minor version as dual-source; remove the `poc/` copy only after **30 consecutive days** of zero `NucleusInternalError` fallbacks attributable to resolver gaps AND zero open `NEEDS VERIFICATION` markers in the promoted module. If post-promotion CI fails: document the failure in `poc/p2_ctx_sql/PROMOTION_FAILURES.md` (new file) and re-iterate inside `/poc/` before the next attempt.

## §6 Downstream consumers (sequencing matters)

| Consumer | Tier / contract | When affected |
|---|---|---|
| `ctx.sql` public API (`C4_component.md` §2.2) | Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0 (ADR-005 §2 row 2) | At promotion — `ctx.sql` wraps the resolver |
| `@nucleus.sql_asset` materialization path | inherits Beta | v0.1 |
| `nucleus query` CLI (per `nucleus_cli_spec.md` — NEEDS VERIFICATION) | inherits Beta | When CLI lands |
| Workbench SQL editor (v0.2+) | depends on `refs` list signature | v0.2 |
| Cloud Copilot / `nucleus-mcp-server` (v0.5+) | reads `fix_hint` + `refs` | v0.5 (ADR-002 §8.2) |

## §7 Dependency on PoC #1 promotion

PoC #2 **MAY land before, after, or in the same PR as** PoC #1. Resolver imports `NucleusAssetNotFound`, `NucleusInvalidAssetDefinition`, `NucleusSQLSyntaxError` directly from `nucleus.errors` (already in `__all__` at `:395`, `:397`, `:408`); no `coordination/error_translation.py` import; `resolve_sql` raises `NucleusError` subclasses directly. **Sequencing constraint**: Option B at T9 forces **ADR-005 → ADR-006 → PoC #1 → PoC #2** (per `AGENTS.md` §11.7). Options A or C → either PoC order works.
