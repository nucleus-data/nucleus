---
name: nucleus-error-translation
description: >-
  Enforce Nucleus error-translation discipline. Use when editing any code path
  that catches an external library exception (Dagster, DuckDB, Polars,
  pyiceberg, dlt, SQLAlchemy, pyarrow, openlineage, soda), wrapping a library
  call in try/except, or implementing handlers in
  `src/nucleus/coordination/error_translation.py` or
  `poc/p1_error_translation/translator.py`.
---

# Nucleus Error Translation Discipline

Every external exception caught at the `coordination/` boundary MUST be
translated to a `NucleusError` subclass before reaching users. Mandatory
release blocker per `@AGENTS.md §11.7` and `@nucleus_architecture_v4.1.md §6.4`
(library classnames in user-facing output = release blocked).

## Reference implementation

`@poc/p1_error_translation/translator.py` is the current green reference
(21/22 pytest; 14 wrapped-library handlers + 3 baseline + `_iter_causes`).
Promotion target: `src/nucleus/coordination/error_translation.py` per
`@poc/p1_error_translation/PROMOTION_CHECKLIST.md`.

`@src/nucleus/errors.py` is the subclass catalog. If no fit, ADD a subclass
(override `DEFAULT_DOCS_URL`, docstring the trigger, append to `__all__`).
Never raise bare `NucleusError`.

## Three-field contract (all required)

- `user_message` — plain-language, user vocabulary per `@AGENTS.md §7`
  (asset / materialization / snapshot / contract / catalog). No library jargon.
- `fix_hint` — concrete next step. Empty only when no action exists.
- `docs_url` — `https://nucleus.dev/errors/<slug>`; default from
  `DEFAULT_DOCS_URL` on the subclass.

Plus `cause=exc` (preserved on `__cause__`) and `asset=<name>` if known.

## Forbidden in user-facing strings

`user_message` and `fix_hint` MUST NOT mention external classnames. Banned:
`OpExecutionContext`, `DagsterUserCodeExecutionError`, `DuckDBPyConnection`,
`BinderException`, `CommitFailedException`, `CommitStateUnknownException`,
any `dagster.*` / `duckdb.*` / `polars.exceptions.*` /
`pyiceberg.exceptions.*` / `<module>.<ClassName>` from a Tier 0/1/2
dependency.

Library-supplied `str(exc)` is acceptable inside `{msg}` substitution (it's
user-facing detail, not Nucleus wording) — see H6/H10 precedents in
`@poc/p1_error_translation/REVIEW_NOTES.md`.

## Authoring loop

1. Identify the exception class to catch. Cite the official docs URL inline:
   `# Docs: https://...` per `@AGENTS.md §11.12`.
2. Pick or add the matching subclass in `@src/nucleus/errors.py`.
3. Write the handler returning the `NucleusError` with all three fields and
   `cause=exc`. Pattern: `poc/p1_error_translation/translator.py:109` onward.
4. Add a test asserting (a) correct subclass, (b) no banned classname in
   `str(exc)` or `exc.rendered()`, (c) `__cause__` is the original.
5. Run, in order:
   - `pytest poc/p1_error_translation/ -v` (or
     `tests/coordination/test_error_translation.py` post-promotion)
   - `python scripts/dagster_leak_check.py` — must exit 0
   - `python scripts/check_error_codes.py` — per ADR-006

## Two-pass shape (Dagster carry-forward)

`dagster.materialize()` (1.9.5) re-raises the user's original exception — NOT
a Dagster wrapper — with a synthetic `__cause__` cycle through
`DagsterExecutionStepExecutionError` (see 2026-05-13 entry in
`@docs/research/ai_hallucinations.md`). Translators MUST iterate candidates
outer→inner, prefer specific (non-Dagster) handlers, and fall back to the
Dagster handler only when no specific match exists. Re-verify on every
Dagster minor upgrade per `@AGENTS.md §11.13`.

## Hallucination log

If the catch revealed a library API that differed from initial assumption
(wrong exception class, moved namespace, dead package, changed `__cause__`
chain), append an entry to `@docs/research/ai_hallucinations.md` using the
established date / AI suggestion / reality / detection / fix format. The
PoC #1 two-pass discovery and the `openlineage-dagster` dead-package catch
are model entries.
