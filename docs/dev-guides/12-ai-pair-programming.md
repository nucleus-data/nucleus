# 12 — AI Pair Programming with Cursor

> **What you're doing**: Working effectively with Cursor and AI agents on Nucleus code without introducing hallucinations, vocabulary drift, or error-translation gaps.
> **Why it matters**: AI assistance is powerful but dangerous without discipline. This project has caught multiple AI hallucinations that would have shipped if not for structured verification. Per `AGENTS.md §11`, `docs/internal/research/ai_hallucinations.md`.
> **Time**: 5 min to read; ongoing practice

---

## The AI Boundary Map

Not all tasks are equally safe for AI. Know where to lean on AI and where to stay in the driver's seat:

| Task | AI quality | Human discipline required |
|---|---|---|
| Decorator scaffolds (`@nucleus.asset`, etc.) | Excellent | Light review |
| Type definitions, dataclasses | Excellent | Light review |
| Basic test cases from spec | Excellent | Light review |
| Documentation generation | Excellent | Light review |
| Refactoring (rename, extract, inline) | Excellent | Review for correctness |
| Wrapping a stable OSS library | Good | Verify API actually exists in docs |
| SQL parsing logic | Good | Verify edge cases |
| Standard CRUD logic | Good | Light review |
| **Error Translation Layer (the 8 cases)** | **Risky** | **Human writes; AI suggests** |
| **`ctx.sql` Jinja resolver** | **Risky** | **Human writes core; AI assists** |
| **Concurrency/atomicity decisions** | **Risky** | **Human authority** |
| **Performance-critical paths** | **Risky** | **Human authority + benchmarks** |
| **Schema evolution edge cases** | **Risky** | **Human authority** |
| **Dagster internals interaction** | **Bad** | **Human writes; AI cannot deeply reason** |

---

## @-Reference Hygiene

When asking Cursor for help on v0.1 code, include these `@-references`:

```
# Required for any v0.1 code task:
@AGENTS.md
@docs/specs/nucleus_architecture_v4.1.md
@<spec file> (e.g., @docs/specs/nucleus_ctx_sdk_spec.md)
@<test file> (the test file that defines what passes)

# For PoC/promotion work:
@docs/specs/nucleus_poc_plan.md

# For connector work:
@src/nucleus/ctx/copy_from_postgres.py  (gold standard template)
```

**Missing the spec file = AI invents APIs that don't exist.** Always reference the spec.

---

## Single-File vs. Multi-File Edits

Per `.cursor/rules/nucleus.mdc` (Single-File Discipline):

**Multi-file edits (Composer) are acceptable only for**:
- Pure renames across files (mechanical refactor)
- Adding a new decorator to `ctx` SDK — touches `__init__.py` + one new file only
- Generating test fixtures across `tests/fixtures/`

**Composer is NOT acceptable for**:
- Implementing a new feature across multiple layers
- Error handling logic spanning multiple files
- Wrapping a new OSS dependency
- Any change touching Layer 2 (Coordination) — too high-stakes for batch edits

**Why**: A 12-file diff hides leaks. Architectural review requires reading each diff individually.

---

## Composer Prompt Template (When Justified)

```
Read these files for context:
@docs/specs/nucleus_architecture_v4.1.md §<section>
@<spec_file>.md
@<existing_file>.py (the pattern to follow)
@<test_file>.py (the spec to satisfy)

Implement ONLY what the test file requires. Constraints:
- Total LOC ≤ <budget>
- Use <wrapped OSS lib> for <responsibility>
- All errors translate to NucleusError per v4.1 §6.4
- No new dependencies without ADR

Do NOT add features beyond what tests require.
Do NOT modify files outside the target directory unless required.
Do NOT invent APIs that don't exist in the wrapped library.
```

---

## Post-AI-Generation Verification Checklist

After every AI code generation, verify before accepting:

```
[ ] All imports actually exist (no hallucinated modules)
     → pip show <package>; python -c "from <module> import <symbol>"

[ ] All method calls actually exist in wrapped library docs
     → Check the pinned version's official docs, not memory

[ ] No "dagster", "duckdb", "polars" classnames in user-facing strings
     → python scripts/dagster_leak_check.py

[ ] Returns NucleusError, not raw external exceptions
     → Every except block wraps with translate()

[ ] LOC count under per-feature ceiling (500 per PR)
     → python scripts/loc_budget.py

[ ] Matches vocabulary in AGENTS.md §7
     → python scripts/check_vocabulary.py

[ ] Cites architecture section in docstring
     → Per docs/specs/nucleus_architecture_v4.1.md §X.Y

[ ] No drift from spec file API surface
     → Compare against docs/specs/nucleus_ctx_sdk_spec.md or docs/specs/nucleus_cli_spec.md
```

---

## How to Verify an AI-Suggested API

AI training data is stale. An API that "should exist" may not exist in the pinned version.

**Protocol**:
1. AI suggests `pyiceberg.catalog.commit_atomic(...)`.
2. Check the pinned version: `grep pyiceberg pyproject.toml` → `pyiceberg==0.11.1`.
3. Go to: https://py.iceberg.apache.org/api/ (or `pip show pyiceberg` → Home URL).
4. Search for `commit_atomic` in the docs.
5. If found: use it with a `# Docs: <URL>` comment.
6. If NOT found: write `# NEEDS VERIFICATION: commit_atomic — not confirmed in docs` and flag.

**Never ship code with `# NEEDS VERIFICATION` without resolving it.**

---

## Hallucination Log

When you catch an AI hallucination (a fabricated API or behavior), log it:

```markdown
<!-- docs/internal/research/ai_hallucinations.md -->

## YYYY-MM-DD: <library>.<method>
AI suggested: `<fabricated API call>`
Reality: <actual API or "method does not exist">
Detection: <how it was caught — docs check, ImportError, etc.>
Impact: <was it caught before merge? after merge?>
```

This log becomes priceless over time. It prevents the same hallucination from recurring.

---

## Drift Detection Pass (Monthly)

Every 4 weeks, run a drift detection pass using this Cursor Chat prompt:

```
Drift Detection Pass.

Context:
@docs/specs/nucleus_architecture_v4.1.md
@AGENTS.md
@CHANGELOG.md (last 4 weeks of commits)
@src/nucleus (current state of code)

Task: Review the last 4 weeks of commits for drift. Flag:

1. Wrap-not-build violations
2. Scope creep (v0.3+ features that snuck into v0.1)
3. Composability violations
4. Error translation gaps
5. Vocabulary drift
6. LOC budget overruns

Be brutally honest. Cite file paths and line numbers.
```

**Human reviews AI's review.** Don't accept AI's "all clear" without spot-checking at least 3 flagged items.

---

## Model Selection for Different Tasks

Per `AGENTS.md §11.14` (Subagent Model Orchestration):

| Task | Model | Why |
|---|---|---|
| Architecture decisions, ADR review, final review | Claude Opus 4.7 | Deepest reasoning; best for subtle tradeoffs |
| Autonomous implementation loops, CI fixing | GPT-5.5 | Best autonomous operator |
| File-level implementation, tests, docs | Claude Sonnet 4.6 | Swarm-tier efficiency |
| Research docs, library comparisons | Gemini 3.1 Pro | Large context; good at reading specs |

In Cursor, the parent agent (responding to your message) is the Architect tier. Subagents spawned for bounded tasks are the Swarm tier.

---

## Tab Completion Discipline

Cursor Tab completion is generally safe for:
- Type annotations
- Import statements
- Common patterns (decorators, dataclass fields)
- Test boilerplate

**Not safe** for:
- Error handling blocks (might skip error translation)
- Wrapped OSS calls (might hallucinate APIs)
- Concurrency primitives (might miss atomicity)
- SQL string construction (might bypass `{{ ref() }}`)

When in doubt about tab completion: use Chat instead.

---

## Common AI Failure Modes in Nucleus

Based on `docs/internal/research/ai_hallucinations.md`:

1. **Inventing methods** that "should exist" (e.g., `dataframe.to_iceberg()` — doesn't exist in Polars).
2. **Mixing APIs** from similar libraries (pandas methods on Polars).
3. **Hallucinating parameter names** (e.g., `copy_from(url=...)` vs the actual `copy_from(uri=...)`).
4. **Inventing config options** in `nucleus_project.yaml`.
5. **Combining v1 and v2 API syntax** (e.g., pyiceberg 0.8 syntax in pyiceberg 0.11 code).
6. **Claiming file edits that didn't happen** — always verify with `git diff` before trusting.

---

## References

- `AGENTS.md §11.2` — Author vs Reviewer discipline
- `AGENTS.md §11.3` — AI Boundary Map
- `AGENTS.md §11.12` — Official documentation discipline
- `.cursor/rules/nucleus.mdc` — Cursor-specific rules (auto-applied)
- `.cursor/agents/` — Custom subagent definitions (swarm-implementer, builder, researcher, verifier)
- `docs/internal/research/ai_hallucinations.md` — living hallucination log
