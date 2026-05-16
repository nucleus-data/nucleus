# 02 — Wrap vs. Build Decisions

> **What you're doing**: Deciding whether to wrap an existing OSS library or build something from scratch.
> **Why it matters**: The #1 cause of scope creep and LOC budget overruns in Nucleus is building what should be wrapped. Getting this right from the start prevents months of wasted work.
> **Time**: 5-30 minutes (depending on research needed)

---

## The Core Rule

> **Default decision: WRAP, not BUILD.**
>
> For every proposed component, ask: "Which production-grade OSS handles this already?" — `AGENTS.md §0`

If an OSS solution exists:
1. Read its official docs.
2. Write a thin wrapper.
3. Add error translation.
4. Add a swap interface + smoke tests.
5. Done.

Build ONLY when no viable OSS exists or when wrapping costs more than building. And even then: write an ADR first.

---

## The Decision Algorithm

```
START: I want to add feature X.

Step 1: Is X on the Do-Not-Build list?
  → See AGENTS.md §4 and docs/roadmap/non-goals.md
  → YES: STOP. Feature is rejected. Explain why to the requestor.

Step 2: Does OSS Y handle X?
  → YES: Does Y have permissive license (Apache 2.0 / MIT / BSD)?
      → YES: WRAP Y. (Write thin wrapper + error translation + swap interface)
      → NO (BSL, SSPL, AGPL): YELLOW flag → check ADR-007 license tier policy
  → NO OSS exists: Build? Apply the 8-question gate (Step 3).

Step 3: 8-Question Gate
  (All 8 must be YES to proceed with BUILD)
  [ ] Maps to one of the 5 architectural layers?
  [ ] Serves the <30-min beachhead metric?
  [ ] No viable wrap target exists?
  [ ] Preserves no-JVM constraint?
  [ ] Preserves local-identical-to-prod?
  [ ] Stays within 30K LOC budget?
  [ ] Triggered by empirical telemetry, not anxiety?
  [ ] Required for v0.1 Hello World, or can it defer?
  → Any NO: DEFER. Document in docs/roadmap/FOLLOW_UPS.md.
  → All YES: BUILD. Write ADR first.
```

---

## Worked Examples

### Example 1: Postgres Connector

**Want**: `nucleus ingest postgres://...`

**Step 1**: Not on the Do-Not-Build list. Continue.

**Step 2**: dlt has a verified Postgres source. Apache 2.0 license. ✅ WRAP.

**Result**: `src/nucleus/ctx/copy_from_postgres.py` wraps `dlt.sources.sql_database.sql_table`. See ADR-014.

### Example 2: SQL Jinja Resolver

**Want**: `ctx.sql("SELECT * FROM {{ ref('my_asset') }}")` with asset reference resolution.

**Step 1**: Not on Do-Not-Build list. But custom SQL transformation frameworks ARE (dbt-duckdb was the wrap target).

**Step 2**: dbt-duckdb is community-maintained, fragile for our use case. Alternative: build ~1000 LOC Jinja+sqlglot resolver.

**Step 3**: 8-question gate:
- Maps to Coordination layer (L2)? YES
- Serves beachhead metric? YES (required for `nucleus run` to work)
- Wrap possible? dbt-duckdb is fragile; ~1000 LOC beats the integration burden. BORDERLINE — but the tradeoff was evaluated.
- No JVM? YES (pure Python)
- Local=prod? YES
- LOC budget? ~1000 LOC is within v0.1 ceiling. YES
- Empirical? PoC #2 validated the hypothesis first. YES
- v0.1 Hello World? YES (required for `nucleus run`)

**Result**: BUILD. ADR documented. PoC #2 validated before commit. See `docs/swap/dlt.md` (dbt-duckdb as swap target for v0.3).

### Example 3: Custom Auth System

**Want**: Built-in username/password system for Nucleus Cloud.

**Step 1**: On Do-Not-Build list. Constraint #6. STOP.

**Result**: REJECT. Delegate to OIDC. ADR-010 ratified. No further discussion needed.

### Example 4: Vector Search Engine

**Want**: `ctx.vector_search(query, top_k=10)` backed by custom HNSW index.

**Step 1**: Not explicitly on Do-Not-Build list. But "custom vector database" is.

**Step 2**: Lance/LanceDB exists. Apache 2.0-inspired governance. ✅ WRAP.

**Result**: WRAP LanceDB. Defer to v0.5. Document in `docs/swap/` if a swap target is needed.

---

## The Swap Interface Requirement

Every wrapped Tier 1/2 component MUST have a clean swap interface + smoke tests, per the Composability Constitution (`docs/specs/nucleus_architecture_v4.1.md` §9):

```
Tier 1 / Tier 2 dependency → requires:
  1. Clean swap interface (types compile, API surface matches)  — ALWAYS maintained
  2. Basic smoke tests (5-10 tests)                            — ALWAYS run in CI
  3. Full swap implementation                                  — on-demand only (trigger event)
  4. Migration path in docs/swap/<component>.md                — ALWAYS maintained
```

"Full adapter built on-demand" means: don't pre-build two full implementations. Build the interface + smoke tests from day 1; build the full adapter only when the trigger fires (vendor death, license pivot, >2x perf regression).

---

## When to Escalate to Founder

Escalate (do NOT proceed autonomously) when:

1. The proposed wrap has a non-permissive license (BSL, SSPL, AGPL) that creates a compliance risk.
2. The OSS library is in poor health (no commits in 6+ months, no maintainers responding).
3. The wrapping would require >500 LOC of non-trivial adapter code (approaches "build" territory).
4. The decision contradicts a locked ADR.
5. The 8-question gate has any "unclear" answers.

Format for escalation:
```
PAUSE — <one-line reason>
Options:
  A) <recommended default>
  B) <alternative>
  C) <defer>
Recommended: A because <one-line justification>.
```

---

## ADR-as-Output (Required for BUILD Decisions)

Every "build" decision must produce an ADR before any code is written. Template:

```markdown
# ADR-NNN: Build [component] (not wrap)

Status: PROPOSED
Date: YYYY-MM-DD

## Context
What forced this decision?

## OSS Options Considered
- <Option A>: rejected because <reason>
- <Option B>: rejected because <reason>

## Decision
Build custom because: <specific reason>

## Consequences
- LOC budget impact: ~X lines
- Maintenance ownership: @owner
- Swap target: docs/swap/<component>.md
- Tests verifying: <test files>

## Architecture Sections Touched
- §X.Y (cite exact section)
```

See `docs/dev-guides/08-author-adr.md` for the full template and workflow.

---

## Common Wrap Patterns

### Pattern 1: Thin function wrapper with error translation

```python
# src/nucleus/ctx/copy_from_<source>.py

# Per docs/specs/nucleus_architecture_v4.1.md §6.4 (Error Translation Layer)
# Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/

from nucleus.coordination.error_translation import translate


def copy_from_<source>(uri: str, table: str, **kwargs):
    """
    Wraps <OSS library> for <source> → Iceberg ingestion.

    Per docs/specs/nucleus_architecture_v4.1.md §5.6.1.
    Docs: <official docs URL>
    Pinned version: <version from pyproject.toml>
    """
    try:
        # ... wrapping code ...
    except SourceSpecificError as exc:
        raise translate(exc) from exc
```

### Pattern 2: Dispatch entry in `_dispatch.py`

```python
# src/nucleus/ctx/_dispatch.py

def copy_from(uri: str, **kwargs):
    scheme = uri.split("://")[0]
    if scheme in ("postgres", "postgresql"):
        from nucleus.ctx.copy_from_postgres import copy_from_postgres
        return copy_from_postgres(uri, **kwargs)
    elif scheme == "<source>":
        from nucleus.ctx.copy_from_<source> import copy_from_<source>
        return copy_from_<source>(uri, **kwargs)
    else:
        raise NucleusSourceConnectionError(
            user_message=f"Unsupported source scheme: {scheme!r}. ...",
            fix_hint="Supported schemes: postgres://, mysql://, sqlite://. ...",
        )
```

---

## References

- `AGENTS.md §4` — Do-Not-Build list
- `AGENTS.md §5` — 7-question decision framework
- `docs/specs/nucleus_architecture_v4.1.md` §9 — Composability by Constitution
- `docs/roadmap/non-goals.md` — forbidden builds with rationale
- ADR-014 — example of a wrap decision (dlt Postgres)
- ADR-002 — wrap vs build for AI Copilot
