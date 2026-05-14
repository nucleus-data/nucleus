# [PoC promotion] PoC #2 ctx.sql Jinja resolver → src/nucleus/coordination/sql_resolver.py

## Summary

Promotes the native `ctx.sql` Jinja resolver from `poc/p2_ctx_sql/resolver.py` to `src/nucleus/coordination/sql_resolver.py`, landing the wrap-not-build implementation mandated by `nucleus_architecture_v4.1.md` §5.6.0 (≤ 2 500 LOC; no macros, no semantic layer, no adapter framework). Ships **16/16 green tests** (`test_resolver.py:43-222`) covering `{{ ref('schema.name') }}` rendering, argument arity rejection (T1-T3), empty / non-string / malformed / injection-shaped asset-name detection (T8, T10, C5), caller-supplied circular-reference detection (T9, `resolver.py:116-121`), `difflib.get_close_matches` hints for unknown assets (T4, `:127-140`), whitespace + block-comment tolerance (T5, T7), and a §6.4 leak gate (C7) asserting no `"jinja2"` substring escapes any user-facing surface. All Jinja boundary branches translate to typed `NucleusError` subclasses (`NucleusSQLSyntaxError`, `NucleusAssetNotFound`, `NucleusInvalidAssetDefinition`) from `nucleus.errors`. Unblocks `ctx.sql` Beta per ADR-005 §2 row 2 and the `nucleus query` CLI per `nucleus_cli_spec.md` §3.6.

---

## Pre-merge gate checklist

Cites `poc/p2_ctx_sql/PROMOTION_CHECKLIST.md` §1–§4. Re-run at PR-open time.

- [x] `pytest poc/p2_ctx_sql/ -v` → **16/16 green** (C1-C7 + T1-T5, T7-T10).
- [x] `python scripts/dagster_leak_check.py` → exit 0; resolver does not `import dagster`; C7 (`test_resolver.py:101-110`) asserts no `"jinja2"` substring leaks (`v4.1` §6.4).
- [x] `python scripts/check_vocabulary.py --paths poc/p2_ctx_sql/` → exit 0 (`AGENTS.md` §7).
- [ ] `python scripts/check_error_codes.py` → **gated on ADR-006 + T9 decision** (§Architectural changes); Option B claims a new `NE3xxx` per ADR-006 §"Layer prefix mapping".
- [x] `python scripts/check_api_stability.py` → exit 0; lands Internal under `src/nucleus/coordination/` with `# Stability: Beta` per ADR-005 §1 + §2 row 2.
- [x] `python scripts/check_licenses.py` → exit 0; only new runtime dep is `jinja2==3.1.5` (BSD-3-Clause; already pinned).
- [x] `python scripts/loc_budget.py --report` → 169 LOC + 222 LOC tests; under v4.1 §5.6.0's 2 500-LOC ceiling and v0.1's 8 000-LOC `src/nucleus/` ceiling (`AGENTS.md` §11.6).
- [ ] `REVIEW_NOTES.md` Approver Checklist (9 items) — **PENDING founder review**: C4 / C5 / T4 / T10 wording + T9 decision.
- [ ] T9 circular-ref class decision — **PENDING founder review**; THE gating item.
- [x] PoC #1 promotion-order independence — `src/nucleus/coordination/__init__.py` already in tree as an empty package marker; resolver imports from `nucleus.errors` directly (`PROMOTION_CHECKLIST.md` §7).

**Total**: 10 items · **7 met today** · **2 pending founder review** · **1 pending ADR-006 + T9 outcome**.

---

## Architectural changes requiring founder ratification

Two open decisions surface in `REVIEW_NOTES.md` + the `# NEEDS VERIFICATION` marker at `resolver.py:40-41`. Both must be resolved before squash-merge.

1. **T9 — circular-reference error class** (`resolver.py:40-41`, `:116-121`). The resolver raises `NucleusInvalidAssetDefinition` on a `{{ ref() }}` cycle, but that class's docstring (`errors.py:185-191`) describes single-asset definition errors — reuse stretches it to a graph-level invariant.
   - **Option A** — keep `NucleusInvalidAssetDefinition` + tighten its docstring. Zero new classes, no ADR-006 amendment, ships fastest. Conflates single-asset vs graph-level semantics.
   - **Option B** — add `NucleusAssetGraphError` + ADR-006 amendment row claiming a new `NE3xxx` code (L2 Coordination per §"Layer prefix mapping"). Cleaner semantics; precedent for future orphan-ref / partition-graph errors. ~30 LOC + ADR amendment; blocks merge until ADR-006 ratified.
   - **Reviewer task**: pick A or B; record in this PR description + the `T9: Option [A/B]` slot in the commit message. Option B requires the ADR-006 amendment first (`PROMOTION_CHECKLIST.md` §3).

2. **T4 — `difflib.get_close_matches` for unknown-asset hints** (`resolver.py:127-140`). First user-facing use of `difflib`; precedent for every future "X not found" hint.
   - **Cutoff**: `difflib.get_close_matches(name, _available_list, n=5, cutoff=0.0)` (`:132`) — most-permissive; suggests `staging.orders` for typo `marts.zzz`. Python default `cutoff=0.6` is similarity-gated. v0.1 registries cap at ≤ 100 assets (`AGENTS.md` §11.8), so noise is bounded — but the threshold ships permanently with the Beta surface.
   - **Phrasing**: prefix `"Available assets include: …"` reads naturally for ≤ 5 known assets but misleads for the `difflib` branch (`"Closest matches:"` is more honest). Reviewer must confirm the pair conforms to v4.1 §6.4's 3-field contract.

---

## Known issues

None blocking. Two soft items carry from `REVIEW_NOTES.md`; the 16-test suite passes against either disposition:

- **T9 cycle-string `sorted()` bug** (`resolver.py:117`). `" -> ".join([*sorted(_resolving), name])` sorts lexically, destroying encounter order on multi-asset chains. `REVIEW_NOTES.md` T9 Critique 2 recommends switching `_resolving` from `frozenset` to ordered tuple — safe regardless of Option A vs B.
- **T10 split vs generalize** (`resolver.py:102-106`). `ref('')` and `ref(non_string)` share a branch hinting `"Did you forget the quotes?"` — accurate for non-string, confusing for empty-string. `REVIEW_NOTES.md` T10 offers Rewrite A (split) or B (generalize); test (`:217-222`) accepts either.

---

## Files to be created

- `src/nucleus/coordination/sql_resolver.py` — `cp` of `resolver.py`; docstring rewritten to cite v4.1 §5.6.0 + §6.4 as canonical (dropping the PoC framing); `# Stability: Beta` added per ADR-005 §1.
- `tests/coordination/test_sql_resolver.py` — `mv` of `test_resolver.py`; imports rewritten to `nucleus.coordination.sql_resolver` (`PROMOTION_CHECKLIST.md` §3).

## Files to be updated

- `nucleus_poc_plan.md` §2 — PoC #2 status `PROPOSED` → `PROMOTED 2026-05-NN`; `AGENTS.md` §1 `[ ] PoC #2-5` row stays unchecked until PoC #5 lands.
- `nucleus_architecture_v4.1.md` §5.6 / §5.6.0 — flip "PoC #2 validates feasibility" → "shipping in v0.1".
- `docs/architecture/sequence_query.md` §1 — Status → "shipped"; retarget `resolver.py` line refs in §2 / §3.1.
- `nucleus_cli_spec.md` §3.6 + §10 NV #2 — drop "Confirm at PoC #2 promotion" caveat.
- `CHANGELOG.md` "Unreleased" — `sql_resolver: Internal → Beta, see ADR-005 §2 row 2`.
- `docs/budget_history.md` — append post-promotion `src/nucleus/` LOC snapshot (`AGENTS.md` §11.6).
- **IF Option B at T9**: `src/nucleus/errors.py` adds `NucleusAssetGraphError` + `__all__`; ADR-006 §"Initial code assignment" gains the new `NE3xxx` row.

`poc/p2_ctx_sql/` stays in tree **30 days** dual-source per `PROMOTION_CHECKLIST.md` §5 — removable after 30 days of zero `NucleusInternalError` fallbacks AND zero open `# NEEDS VERIFICATION` markers.

---

## Downstream chain unlocked by this merge

Per `PROMOTION_CHECKLIST.md` §6 + ADR-005 §"Downstream consumers":

1. **`ctx.sql(...)` public API** usable under `src/nucleus/`; inherits Beta tier from ADR-005 §2 row 2 until v0.5 spec lock.
2. **`@nucleus.sql_asset` materialization path** inherits Beta; unblocks Layer-2 wiring (v4.1 §6.3 — Coordination is the only layer permitted to `import dagster` per `scripts/dagster_leak_check.py`).
3. **`nucleus query` CLI command** unblocks per `nucleus_cli_spec.md` §3.6 (wraps `ctx.sql(query)` per SDK §6; flags "Confirm at PoC #2 promotion" for the `pyarrow.Table` return shape).
4. **PoC #1 promotion** is independent (`PROMOTION_CHECKLIST.md` §7) — both may ship in either order or stacked.

---

## Rollback plan

Squash-merge so rollback is atomic per `PROMOTION_CHECKLIST.md` §5:

```bash
git revert <merge-commit-sha>
git push origin main
```

`poc/p2_ctx_sql/` is unchanged by this PR (purely additive `cp` into `src/nucleus/coordination/` and `tests/coordination/`); rollback leaves the PoC source intact. On CI failure, document in `poc/p2_ctx_sql/PROMOTION_FAILURES.md` and re-iterate inside `/poc/`.

---

## Commit message body (founder uses verbatim with `git commit -m "$(cat <<'EOF' ... EOF)"`)

```
[PoC promotion] PoC #2 ctx.sql Jinja resolver

Promotes 16-test green resolver from poc/p2_ctx_sql/ to
src/nucleus/coordination/sql_resolver.py.

Provides {{ ref('schema.name') }} resolution with argument arity
checks, empty / non-string / malformed / injection-shaped asset-name
detection, caller-supplied circular-reference detection, and
difflib-based hints for unknown asset names. All Jinja boundary
branches translate to typed NucleusError subclasses; no jinja2
substring leaks into user_message or rendered() (verified by C7).

Tests: 16/16 green.

T9 circular-ref class decision: Option [A/B] (founder choice).
- A: keep NucleusInvalidAssetDefinition.
- B: add NucleusAssetGraphError (requires ADR-006 amendment).

Refs: AGENTS.md §11.1, §11.7; nucleus_architecture_v4.1.md §5.6.0,
§6.3, §6.4; ADR-005 §2 row 2; ADR-006 (error code scheme).
```
