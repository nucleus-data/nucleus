# PoC #1 — Dagster Error Translation Layer

> **Status**: Spec only — not yet implemented.
> **Priority**: **HIGHEST** — release blocker for all subsequent v0.1 work.
> **Trigger**: Begin after dev environment setup (`SETUP.md`) + `M2.1 Dagster` from `docs/onboarding/learning_path.md` are complete.
> **Time budget**: 2-3 weeks of solo + AI pair work.
> **Companion**: [`../../docs/architecture/sequence_error_translation.md`](../../docs/architecture/sequence_error_translation.md), [`../../nucleus_poc_plan.md`](../../nucleus_poc_plan.md) PoC #1

This is **the first real implementation task** for Nucleus. Everything else depends on the error translation contract working. Hence the priority.

---

## §1. Goal

Build a working prototype of the Error Translation Layer (ETL) that:

1. Catches a Dagster exception thrown during asset materialization.
2. Translates it to a `NucleusError` subclass with proper `user_message` / `fix_hint` / `docs_url`.
3. Surfaces only the `NucleusError` to the user — **zero Dagster types in the rendered output**.
4. Preserves the original exception via `__cause__` for `--debug` mode.
5. Passes the 50-case fixture (see §5).

The prototype lives in this directory. The promotion path:

```
poc/p1_error_translation/         ← exploratory, not LOC-counted
        ↓ (passes acceptance)
src/nucleus/coordination/error_translation.py   ← production, ~300 LOC
src/nucleus/coordination/asset_materialization.py ← uses the translator, ~500 LOC
```

---

## §2. Acceptance criteria (gate for promotion)

Per [`sequence_error_translation.md`](../../docs/architecture/sequence_error_translation.md) §7:

| # | Criterion | How verified |
|---|-----------|--------------|
| 1 | Every Dagster exception type in §4 of sequence doc has a translator | `tests/test_translator_coverage.py` enumerates |
| 2 | Round-trip test: real failing asset → NucleusError visible, no Dagster path in CLI output | `tests/test_round_trip.py` + `capsys` |
| 3 | Unknown exceptions fall back to `NucleusInternalError` with bug-report URL | `tests/test_unknown_exception.py` |
| 4 | The 50-case fixture (§5) produces good messages for ≥45/50 | `tests/test_50_fixtures.py` |
| 5 | `scripts/dagster_leak_check.py` returns 0 violations on all PoC output | run in CI |
| 6 | Translator is thread-safe (multiple assets failing in parallel) | `tests/test_concurrent.py` |
| 7 | The translation operation takes <1ms per exception (not a hot path but should be fast) | `tests/test_benchmark.py` |

---

## §3. Suggested implementation steps

These are guidance, not rigid steps. Adapt as you learn.

### Step 1: Hello-world Dagster (½ day)

Before translating, **understand** what we're translating.

- `pip install dagster==1.9.5` in your dev env.
- Write `step1_dagster_basics.py` in this directory:
  - Define 3 assets (`raw`, `staging`, `marts`) with dependencies.
  - Materialize them via `materialize_to_memory`.
  - Verify all green.
- Add one **deliberately failing** asset and capture the exception.
  - What's its type? (e.g. `DagsterExecutionStepExecutionError`)
  - What does its `str()` look like?
  - What's its `__cause__`?
  - Write down each one.

### Step 2: First translator, hand-written (1 day)

- Write `step2_one_translator.py`:
  - Define `translate(exc: Exception) -> NucleusError` for ONE exception type only (e.g. `dagster.DagsterAssetNotFoundError`).
  - Wrap the failing materialization in a try/except, call `translate()`, print the rendered NucleusError.
  - Confirm: no `dagster.` string in the output.

### Step 3: Build the registry (2-3 days)

- Write `step3_translator_registry.py`:
  - Implement `ErrorTranslator` as the registry described in [`sequence_error_translation.md`](../../docs/architecture/sequence_error_translation.md) §5.
  - Register handlers for the ~10 most common Dagster exception types.
  - Add MRO-walking for unknown types (so subclasses pick up parent handlers).
  - Add inner-cause unwrapping for `DagsterExecutionStepExecutionError`.

### Step 4: Cover wrapped libraries (3-5 days)

- Write `step4_duckdb_translators.py`, `step4_polars_translators.py`, `step4_pyiceberg_translators.py`:
  - One file per source library.
  - Each registers handlers for the exception types listed in [`sequence_error_translation.md`](../../docs/architecture/sequence_error_translation.md) §4.2/4.3/4.4.
  - Drive each handler with a real failing input — not a mock.

### Step 5: Build the 50-case fixture (3-5 days)

- Write `step5_fixtures.py`:
  - 50 realistic failure scenarios. Categorize them: missing table, type mismatch, network failure, etc.
  - For each fixture, define: `(name, setup_fn, expected_error_class, expected_phrase_in_message, expected_docs_url)`.
  - Use `pytest.mark.parametrize` to run all 50.

### Step 6: Stress + concurrency (1-2 days)

- Write `step6_concurrent_failures.py`:
  - Parallelize 3-5 failing materializations (Dagster supports concurrent asset execution).
  - Verify each surfaces its own NucleusError without interleaving.

### Step 7: Leak check + benchmarks (1 day)

- Capture CLI output of all PoC scripts to a file.
- Run `python scripts/dagster_leak_check.py --scan-output <file>` — must return 0 leaks.
- Microbenchmark: 10K calls to translate(); must average <1ms each.

### Step 8: Production promotion (1-2 days)

- Move the registry + handlers to `src/nucleus/coordination/error_translation.py`.
- Move tests from `poc/` to `tests/coordination/test_error_translation.py`.
- Open an ADR (ADR-002): record the design choices made during the PoC.
- Update [`docs/architecture/sequence_error_translation.md`](../../docs/architecture/sequence_error_translation.md) §10 with the answers to open questions.

---

## §4. What to keep, what to discard

When promoting to `src/nucleus/coordination/`:

**Keep**:
- The registry + handlers (production-quality).
- The 50-case fixture (becomes part of `tests/`).
- The leak-check integration (already part of CI).

**Discard / rewrite**:
- Throw-away `print()` debug code.
- Inline `pytest.skip()` for skipped exploration paths.
- Any quick hacks where you wrote "TODO: revisit".

---

## §5. The 50-case fixture (yet to build)

These represent the **realistic** error scenarios a user will hit. We invent them by recalling common data-engineering bugs.

**Skeleton categories** (target 50 across these):

- **Asset reference errors** (8 cases) — typos, deletes, case mismatches, wildcard misuse, …
- **Schema errors** (12) — column missing, type mismatch, nullable→not-null violation, unknown timezone, decimal precision overflow, …
- **Connection errors** (6) — host unreachable, auth failure, TLS error, port closed, DNS failure, time-out
- **SQL syntax errors** (6) — typo, missing FROM, unclosed quote, dialect mismatch (DuckDB ≠ Postgres), undefined function, …
- **Commit conflicts** (4) — same table written twice, snapshot ID stale, catalog out-of-sync, manifest write conflict
- **Resource errors** (5) — OOM, disk full, file descriptor limit, query timeout, transaction too long
- **User code errors** (5) — Python exception inside the user's `@nucleus.asset` body (should pass through with sanitized info)
- **Catalog errors** (4) — namespace missing, permission denied, schema mismatch on registration, catalog backend down

You'll add specifics as you go. **It's fine to start with 15-20 and grow to 50 over the PoC.**

---

## §6. Done definition

PoC #1 is "done" when:

1. All 7 acceptance criteria (§2) pass.
2. The production code is merged at `src/nucleus/coordination/error_translation.py`.
3. ADR-002 is merged.
4. The sequence_error_translation.md §10 open questions all have answers.
5. The PoC directory is deleted (or kept only as a learning artifact, marked archived).
6. CI is green.

---

## §7. Anti-goals (out of scope for PoC #1)

- Performance optimization beyond the <1ms target.
- A "soft" mode that downgrades errors to warnings — errors are errors.
- Localization (i18n) — English-only for v0.1-v1.0.
- Retry logic — that's the Asset Materialization Adapter's job, separate PoC.
- A REST API for error rendering — CLI / SDK only for now.

---

## §8. References

- [`../../docs/architecture/sequence_error_translation.md`](../../docs/architecture/sequence_error_translation.md) — the spec
- [`../../docs/decisions/ADR-001-no-iceberg-commit-service.md`](../../docs/decisions/ADR-001-no-iceberg-commit-service.md) — ADR format example
- [`../../nucleus_poc_plan.md`](../../nucleus_poc_plan.md) — broader PoC plan
- [Dagster exception types](https://docs.dagster.io/_apidocs/errors) — official source for what we translate
- Python exception chaining: https://docs.python.org/3/tutorial/errors.html#exception-chaining

---

*Build this carefully. Everything else depends on it.*
