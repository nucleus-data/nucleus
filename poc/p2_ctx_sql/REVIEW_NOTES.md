# REVIEW_NOTES — PoC #2 native ctx.sql Jinja resolver, wording critique

**Status**: DRAFT — Risky-tier per `AGENTS.md` §11.3 (founder writes core, AI suggests). Promotion gated on §11.7 + v4.1 §5.6.0 LOC ceiling. Suggestions, not authorship.

**Scope**: 16 cases in `resolver.py:51–169` + `test_resolver.py:43–222`. Worker B's hardening pass expanded 7 → 16 (T1-T5, T7-T10; T6 skipped per the test-module docstring) for parity with PoC #1's leak discipline + arity + cycle + difflib hint.

**Uniform cross-checks across all 16**: vocab per `AGENTS.md` §7 ("asset name" / "asset graph" / "asset chain", never "table" as primitive); no `jinja2.` / `duckdb.` / `polars.` / `pyiceberg.` substring in user-facing prose (verified by C7 §6.4-mirror leak check); `cause` set on the two boundary branches that wrap a non-`NucleusError` (`:140`, `:167`), intentionally NOT set on validation paths (`:94`, `:103`, `:108`, `:118`) — those are raised by us, not translated; no CLI commands in any `fix_hint` (PoC #2 stays purely descriptive until `docs/specs/nucleus_cli_spec.md` finalizes).

---

## 11 cases — looks good as-shipped

| # | Case (`test_resolver.py`) | Why it works |
|---|---|---|
| C1 | `test_simple_ref_renders_to_resolved_string` (`:43`) | Happy path; `refs` preserves encounter order. |
| C2 | `test_multiple_refs_in_one_template` (`:50`) | Encounter-order matches `sequence_query.md` §5 acceptance #2. |
| C3 | `test_duplicate_refs_deduplicated_in_returned_list` (`:64`) | Dedup in the list (`seen` at `:88`, `:122`), NOT in rendered SQL. Correct. |
| C6 | `test_no_refs_returns_empty_list` (`:93`) | "Do no harm" base case. |
| C7 | `test_renderer_does_not_leak_jinja_classnames_in_error_message` (`:101`) | §6.4 leak check, mirrors PoC #1 §2.5. Wording critiqued under C4. |
| T1 | `test_unquoted_ref_argument_raises...` (`:120`) | Test accepts either StrictUndefined or non-string `isinstance` branch — robust to Jinja upgrades. |
| T2 | `test_ref_with_no_arguments_raises...` (`:131`) | Arity branch; awkward `"got {N} positional and {M} keyword"` count format — lower-priority polish. |
| T3 | `test_ref_with_extra_arguments_raises...` (`:140`) | Same branch as T2. |
| T5 | `test_whitespace_in_ref_call_resolves_identically` (`:168`) | Free from Jinja's tokenizer. |
| T7 | `test_jinja_block_comments_are_stripped` (`:177`) | Free from Jinja's parser. |
| T8 | `test_sql_injection_shape_rejected_at_validation` (`:187`) | Security gate — `called_with == []` (`:199`) proves `ref_resolver` never runs for malformed names. Fix_hint reveals zero detail about the mechanism. |

---

## 5 cases needing founder review

### C4 — generic Jinja translation (resolver.py:155–167)

Catches `jinja2.UndefinedError` + `jinja2.TemplateSyntaxError`; same branch C7 leak-tests.
- msg: `"SQL template rendering failed: {exc}"` — interpolates `str(exc)`; for `UndefinedError` reads `"'undefined_var' is undefined"`. No `"jinja2"` (C7).
- hint: long multi-clause ending *"v0 supports only `{{ ref('schema.name') }}` — source(), config(), and user macros are deferred."*
- Critique: interpolating `{exc}` carries the same upgrade risk as PoC #1's `{msg}` handlers — a future Jinja exception whose `__str__` references its class path would leak. Trailing scope-reminder reads slightly internal (compare PoC #1 H9's `engine 'memory_limit'`).
- Rewrite A: hint → *"Check the template for unknown variables, mismatched braces, or unsupported expressions. Only ref('schema.name') is supported in v0.1; source(), config(), and user macros come later."*

### C5 — malformed-name fix_hint (resolver.py:107–115)

`test_malformed_ref_name_raises_nucleus_sql_syntax_error` (`:83`) + T8 (`:187`) both hit this. Most common error a new user sees.
- msg: `"ref({name!r}) is not a valid asset name."` — `!r` quotes injection chars (security-friendly).
- hint: *"Asset names must match '<schema>.<name>' where each part starts with a lowercase letter and contains only lowercase letters, digits, or underscores. Example: ref('staging.orders')."*
- Critique: 4-clause rule. "Starts with a lowercase letter" is implicit-only in `_REF_NAME_RE` (`:48`) — `ref('_internal.tmp')` hits this without obvious cause. `<schema>.<name>` placeholders read as code metasyntax.
- Rewrite A: *"Asset names look like 'schema.name' — lowercase letters, digits, underscores; each part must start with a letter. Example: ref('staging.orders')."*

### T4 — unknown-asset difflib hint (resolver.py:125–140) ⚠️ NEW PATTERN

**First time `difflib` enters Nucleus's user-facing surface** — pattern will be copied for other "X not found" hints.
- msg: `"Asset {name!r} is not defined."`
- hint: no `available` → *"Check the asset name spelling, or register the asset first."*; ≤5 → list all, prefixed *"Available assets include: …"*; >5 → `difflib.get_close_matches(name, available, n=5, cutoff=0.0)` then same prefix.
- Critique 1 (`cutoff=0.0`): most-liberal cutoff — will suggest `staging.orders` for typo `marts.zzz` (no shared prefix). Tradeoff vs Python default `cutoff=0.6` (similarity-gated, 0–5 hints). v0.1 registries ≤100 assets so noise is bounded, but worth a documented call. Also: *"Available assets include:"* reads naturally for ≤5 but is misleading for the difflib output — *"Closest matches:"* is more honest there.
- Critique 2 (CLI clause): *"register the asset first"* is right for v0.1 (no `nucleus list` CLI yet — parallels PoC #1 H4's NEEDS VERIFICATION). Swap to *"… run 'nucleus list' …"* once `docs/specs/nucleus_cli_spec.md` finalizes. v0.5 polish, not a v0.1 blocker.
- Decision: (a) `cutoff=0.0` vs `cutoff=0.6`; (b) unified vs split hint wording; (c) cleared to defer CLI swap.

### T9 — circular ref (resolver.py:40–41, :116–121) ⚠️ HIGHEST PRIORITY — open architectural decision

**THE blocker for PoC #2 promotion.** Currently emits `NucleusInvalidAssetDefinition`. Explicit marker at `resolver.py:40-41`:

```
# NEEDS VERIFICATION (AGENTS.md §11.12): NucleusInvalidAssetDefinition reused
# for cycles; founder may prefer a dedicated NucleusAssetGraphError later.
```

- msg: `"Circular asset reference detected: {cycle}."` where `cycle = " -> ".join([*sorted(_resolving), name])`.
- hint: *"Break the cycle in the asset chain — asset graphs must be acyclic."*
- Critique 1 (class reuse vs new class): `NucleusInvalidAssetDefinition` docstring at `errors.py:185-191` reads *"`@nucleus.asset` was used with invalid configuration. Examples: wrong name pattern, schema/return-type mismatch, missing deps."* A cycle is NOT an invalid *definition* — each asset is well-defined; the **graph-level invariant** fails.
  - **Option A (reuse)**: zero new error classes; ADR-006 does NOT block PoC #2; promotion sooner. Cost: stretch the existing "Examples" docstring.
  - **Option B (new `NucleusAssetGraphError`)**: cleaner separation — cycles, orphan refs, partition-graph violations all fit one bucket. Cost: (i) new class in `errors.py` + `__all__`; (ii) **ADR-006 must assign its code BEFORE the first release** per `AGENTS.md` §11.7; (iii) docstring tightening on the existing class. ~30 LOC + ADR row; ~1 week added.
- Critique 2 (cycle-string bug, not wording): `" -> ".join([*sorted(_resolving), name])` sorts the in-flight set **lexically**, destroying encounter order. `marts.a -> marts.b -> marts.c -> marts.a` tells the user nothing about the traversal that found the cycle. Single-template case accidentally works; multi-asset chains will mislead. **Fix before promotion regardless of A/B/C**: pass `_resolving` as tuple/list, skip the sort.
- Critique 3 (private API smell): `_resolving` is underscore-prefixed but `test_circular_ref...` passes it directly. The test exercises an interface **no caller in v0.1 uses** — `ctx.sql` always passes the default empty frozenset. On promotion either document the future multi-asset orchestrator caller in the docstring, or move cycle detection out of `resolve_sql` entirely (Option C).
- Decision (THE blocker):
  - ☐ **Option A** — keep `NucleusInvalidAssetDefinition`, fix `sorted()` bug, document multi-asset caller. Independent of ADR-006.
  - ☐ **Option B** — add `NucleusAssetGraphError`; ADR-006 must land first.
  - ☐ **Option C** — drop cycle detection from resolver; defer to asset-graph walker PoC. Remove T9; update `sequence_query.md` §3.1.

### T10 — empty-name + non-string overlap (resolver.py:102–106)

`ref('')` and `ref(some_non_string)` share one branch.
- msg: *"ref() requires a non-empty quoted asset name."* · hint: *"Did you forget the quotes? Example: ref('staging.orders')."*
- Critique: branch handles both `not isinstance(name, str)` AND `not name`. *"Did you forget the quotes?"* is right for the non-string case but confuses `ref('')` users — the quotes ARE there.
- Rewrite A (split): empty-string gets *"Asset names cannot be empty. Example: ref('staging.orders')."*; non-string keeps current. Rewrite B (generalize): single hint *"Provide a non-empty asset name in quotes. Example: ref('staging.orders')."*

---

## Approver Checklist (founder ticks before signing)

- [ ] **T9 cycle decision** (THE blocker): ☐ Option A · ☐ Option B · ☐ Option C.
- [ ] T9 cycle-string `sorted()` fix landed (encounter-order list) — regardless of A/B/C.
- [ ] T4 difflib: ☐ `cutoff=0.0` or ☐ `cutoff=0.6`; ☐ unified or ☐ split hint wording.
- [ ] C4 generic-Jinja fix_hint: ☐ keep or ☐ Rewrite A.
- [ ] C5 malformed-name fix_hint: ☐ keep or ☐ Rewrite A.
- [ ] T10 empty-name fix_hint: ☐ split or ☐ generalize.
- [ ] All referenced subclasses (`NucleusAssetNotFound`, `NucleusInvalidAssetDefinition`, `NucleusSQLSyntaxError`, plus optional new `NucleusAssetGraphError`) exist in `errors.py` `__all__`. *(Audited: first three at `:395`, `:397`, `:408`; new class needs adding under Option B.)*
- [ ] Architecture cite (`v4.1 §5.6.0` + `v4.1 §6.4`) preserved in the promoted module docstring.
- [ ] `# Stability: Beta` annotation added per ADR-005 §1 + Verification plan item #1 (resolver tiers Beta @ v0.1 → Stable @ v0.5 per ADR-005 §2 row 2).
