<!--
Thank you for contributing to Nucleus!

Before you submit, please fill out every section below. Sections you don't
fill out tell us you haven't thought about them — that's not a green light.

If this is your first Nucleus PR, please skim:
  - AGENTS.md                          (the 11 hard constraints)
  - docs/conventions/engineering.md    (the 18 conventions)
  - docs/decisions/_template.md        (the ADR pattern)

If you're using AI to generate code (Cursor, Copilot, etc.), see
AGENTS.md §11 "Implementation Workflow Discipline" — there are extra rules.
-->

## Summary

<!-- One paragraph. What does this PR do, and why? -->

**Related issue / ADR**: <!-- #123 or ADR-007. Use "n/a" only for trivial PRs. -->
**Provenance**: <!-- one of: provenance:human / provenance:ai-assisted / provenance:ai-bulk -->
**Tier / version target**: <!-- e.g. Tier 0 Heartbeat, Tier 1 v0.1, etc. -->

---

## What changed

<!-- Concrete list. "Added X", "Changed Y to do Z", "Fixed W". -->

-
-

---

## Why this approach

<!-- What alternatives did you consider? Why this one? Keep it short. -->

---

## How I tested

<!-- Concrete steps. "Ran pytest -m smoke", "ran nucleus up locally", etc. -->

- [ ] Unit tests added / updated: `tests/...`
- [ ] Integration tests added / updated (if applicable): `tests/integration/...`
- [ ] Property tests added / updated (if applicable): `tests/patterns/...`
- [ ] Manual smoke test on Linux / macOS / Windows: <!-- which? -->
- [ ] Doctest examples (if applicable) verified

**Test output excerpt** (paste a few key lines, not the whole log):

```
<!-- paste here -->
```

---

## Hard Constraint check

Tick the box if the constraint is **NOT** violated by this PR. If a constraint is violated, explain in **why** below. Numbering mirrors `AGENTS.md` §3 verbatim.

- [ ] **#1 No JVM in core path** — no Java/Kotlin/Scala deps added; no JVM startup in any code path
- [ ] **#2 No public plugin SDK in v1** — internal interfaces only; no new plugin entry-points exposed
- [ ] **#3 No custom scheduler** — Dagster wrapped, not replaced or sidestepped
- [ ] **#4 No custom compute engine** — DuckDB / Polars / Daft wrapped; no engine built
- [ ] **#5 No custom Iceberg commit service / transaction coordinator** — atomic commits delegated to the Iceberg catalog (ADR-001)
- [ ] **#6 No custom auth system** — identity delegated to OIDC; no password / session storage
- [ ] **#7 No ML platform / training / agent hosting** — we use AI; we are not an AI/ML platform
- [ ] **#8 ≤ 30K LOC proprietary budget by v1.0** — `python scripts/loc_budget.py --report` is green after this change
- [ ] **#9 Composability by Constitution** — every Tier 1/2 dep keeps a clean swap interface + smoke tests
- [ ] **#10 Read official docs before integration** — docs URL cited for every wrapped library touched; no AI-memory APIs
- [ ] **#11 Upgrade-safe stack design** — runtime deps pinned exactly; one-component-per-PR; rollback documented

**Why** (only for items unchecked):
<!-- -->

---

## Dependency & API Governance (per ADR-005 / ADR-006 / ADR-007)

Tick each box that applies. If a box does NOT apply to this PR (e.g., no new deps), tick it anyway and note "n/a" below.

- [ ] **License tier (ADR-007)** — if adding a new runtime dependency, classified GREEN / YELLOW / RED per `docs/decisions/ADR-007-dependency-license-tier-policy.md`; RED rejected; YELLOW requires a Cloud-impact note (see ADR-007 §Tier 2). `python scripts/check_licenses.py` is green after this PR.
- [ ] **Error code (ADR-006)** — if adding a new `NucleusError` subclass, includes `error_code: ClassVar[str]` matching `^NE[1-5]\d{3}$` per `docs/decisions/ADR-006-nucleus-error-code-numbering.md`. `python scripts/check_error_codes.py` is green after this PR.
- [ ] **API stability tag (ADR-005)** — if touching `src/nucleus/__init__.py` `__all__` (adding / removing / renaming a public symbol), every new public symbol carries a `# Stability: <Frozen|Stable|Beta|Internal>` tag in its docstring per `docs/decisions/ADR-005-ctx-sdk-api-freeze-policy.md`. `python scripts/check_api_stability.py` is green after this PR.

**Governance notes** (only for items unchecked or `n/a`):
<!-- -->

---

## LOC budget

Run `python scripts/loc_budget.py --report` and paste the cumulative line:

```
<!-- Cumulative LOC: ____ / 8000 (v0.1 ceiling) -->
```

---

## Docs / ADR

<!-- For non-trivial PRs. -->

- [ ] User-facing change → updated `docs/` and `CHANGELOG.md`
- [ ] Architectural change → ADR added in `docs/decisions/`
- [ ] Public API change → updated `docs/specs/nucleus_ctx_sdk_spec.md` (or noted as intentional)
- [ ] Type-mapping change → updated `docs/patterns/type_mapping.md` + property tests
- [ ] Error type added / changed → updated `docs/architecture/sequence_error_translation.md`
- [ ] Dep change → updated `docs/internal/compatibility.md`

---

## AI-assisted PR checklist (skip if `provenance:human`)

<!-- Required if you used Cursor Composer, Copilot, or similar to generate
     more than ~30 lines of substantive code. -->

- [ ] Verified no invented APIs (every function/class/parameter actually exists in current docs)
- [ ] Every wrapped library has a current docs URL referenced
- [ ] All exceptions are NucleusError subclasses (not raw `Exception`)
- [ ] Layer direction respected (`scripts/check_layering.py` passes)
- [ ] No `from dagster import` outside `src/nucleus/coordination/`
- [ ] Diff size ≤ 600 lines (excluding tests + generated). If larger, justify here:

---

## Reviewer hints

<!-- Optional. Point reviewers at the trickiest part. -->

- The interesting bit is in `<file>:<lines>`.
- Watch out for `<concern>`.

---

## Definition of Done

This PR is mergeable when:

- [ ] CI is green
- [ ] All checkboxes above are ticked (or have written justification)
- [ ] Self-reviewed the diff line-by-line
- [ ] Tests pass locally on at least one OS
- [ ] No `TODO(name)` comments without a follow-up issue link

---

<!--
Quick reminders:
  - Prefer small PRs (target ≤300 LOC). Split big work.
  - Title format:  type(scope): subject     (e.g. feat(ctx): add copy_from)
  - Squash-merge only; the squash commit becomes the canonical message.
-->
