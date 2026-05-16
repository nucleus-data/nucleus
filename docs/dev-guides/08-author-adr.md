# 08 — Author an Architecture Decision Record (ADR)

> **What you're doing**: Creating a permanent record of an architectural decision so future contributors understand WHY the code is the way it is.
> **Why it matters**: Code can be read. Intent cannot. ADRs prevent "why did we do it this way?" from being answered with "no one remembers."
> **Time**: 30-60 minutes per ADR (longer for complex decisions)

---

## When to Write an ADR

Write an ADR when you're making a decision that:
1. Adds a new external dependency.
2. Chooses to BUILD instead of WRAP (always requires an ADR).
3. Makes a major version upgrade (X.y.z → X+1.0.0).
4. Changes the public `ctx.*` API surface.
5. Changes the CLI command surface.
6. Deviates from the architecture in `docs/specs/nucleus_architecture_v4.1.md`.
7. Affects the 30K LOC budget significantly.
8. Any architectural question where "future developers need to understand why."

When in doubt: write an ADR. A short ADR is always better than no ADR.

---

## Step 1: Check if an ADR Already Exists

```bash
ls docs/decisions/ADR-*.md | sort
```

If an existing ADR covers the same decision (even if it's in PROPOSED status), amend it rather than creating a duplicate.

---

## Step 2: Allocate the Next ADR Number

```bash
# Find the highest existing number
ls docs/decisions/ADR-*.md | grep -oP 'ADR-\K\d+' | sort -n | tail -1
# Add 1 to get the next number
```

Current highest as of 2026-05-15: ADR-018. Next: ADR-019.

---

## Step 3: Create the ADR File

File path format: `docs/decisions/ADR-NNN-<kebab-title>.md`

Example: `docs/decisions/ADR-019-redis-cache-for-lineage.md`

---

## Step 4: Fill the Template

```markdown
# ADR-NNN: <Title>

**Status**: PROPOSED
**Date**: YYYY-MM-DD
**Authors**: @<github-username>
**Reviewers**: (founder + 1 external reviewer for major decisions)

---

## Context

<2-4 paragraphs explaining the situation. What problem are we solving?
Why is this decision needed now? What constraints exist?
Reference the relevant architecture section.>

Per `docs/specs/nucleus_architecture_v4.1.md` §X.Y: ...

## Options Considered

### Option A: <Name>
<Description>

**Pros**:
- <Pro 1>
- <Pro 2>

**Cons**:
- <Con 1>

**OSS Candidates** (for wrap decisions):
- `<library>` (<license>): rejected because <reason>
- `<library>` (<license>): accepted — see Decision below

### Option B: <Name>
<Description, pros, cons>

### Option C: Defer
<Why this could wait, and what trigger would make it urgent>

## Decision

**Chosen: Option <X>**

<3-5 sentences explaining why this option over the others. Be specific.
Reference the Five Pillars and beachhead metric if relevant.>

## Consequences

**Positive**:
- <Benefit 1>
- <Benefit 2>

**Negative / Trade-offs**:
- <Trade-off 1>: <how we mitigate it>

**LOC budget impact**: ~<N> lines added to `src/nucleus/` (currently at X of 30K ceiling)

**New dependencies**:
| Package | Version | License | Tier |
|---|---|---|---|
| `<package>` | `X.Y.Z` | MIT | GREEN |

**Swap target** (for Tier 1/2 dependencies): `docs/internal/swap/<component>.md`

**Rollback**: `pip install <old-package>==<old-version>` (or: no rollback path after vX.Y merge)

## Architecture Sections Affected

- `docs/specs/nucleus_architecture_v4.1.md` §X.Y — <what changes>
- `docs/specs/nucleus_ctx_sdk_spec.md` §X.Y — <what changes> (if applicable)

## Open Questions (NV = Needs Verification)

| # | Question | Default | Resolution |
|---|---|---|---|
| NV1 | <Question> | <recommended default> | Resolve in follow-up PR |
| NV2 | <Question> | <recommended default> | Block on acceptance |

## Implementation Notes

- Implementation starts only after Status = ACCEPTED
- All new code lands in `src/nucleus/<layer>/`
- Tests: `tests/<layer>/test_<component>.py` (minimum 5 tests)
- Upgrade smoke: `tests/upgrade_smoke/test_<package>.py` (one test per pinned dep)
```

---

## Step 5: Status Flow

```
PROPOSED → ACCEPTED (after founder review + open questions resolved)
         → REJECTED (with reason; kept for historical reference)
         → SUPERSEDED by ADR-NNN (when a better decision replaces it)
```

Rules:
- PROPOSED: drafted; under review.
- ACCEPTED: decision is binding; implementation can start.
- REJECTED: decision was evaluated and rejected. Keep the doc! Future reviewers need to know why.
- SUPERSEDED: a later ADR changed the decision. Add "Superseded by ADR-NNN" to the header.

---

## Step 6: Cross-Link When Accepted

When an ADR moves to ACCEPTED, update:
1. `docs/decisions/README.md` — add a row to the ADR table.
2. `docs/specs/nucleus_architecture_v4.1.md` — add a citation in the relevant section (e.g., §6.3 "See ADR-014 for dlt integration").
3. `docs/compatibility.md` — if the ADR adds a new dependency.
4. `CHANGELOG.md` — in the next release's entry.

---

## Examples

### Example: Wrap Decision (ADR-014 pattern)

```markdown
# ADR-014: dlt as Postgres → Iceberg Connector

Status: ACCEPTED
Date: 2026-05-13

## Context
nucleus ingest postgres://... requires reading Postgres tables and writing to Iceberg.
Per v4.1 §5.6.1, ctx.copy_from is the ~200 LOC helper pattern.
We evaluated dlt (Apache 2.0, 100+ verified sources) vs. building with SQLAlchemy directly.

## Options Considered
### Option A: Wrap dlt sql_database verified source
Pros: battle-tested, incremental loading built-in, 100+ sources as future bonus.
Cons: dlt as dependency adds ~2 MB to install.

### Option B: Build with SQLAlchemy + pyarrow directly
Pros: no new dependency; full control.
Cons: ~500 LOC vs. ~200 LOC; schema reflection, chunking, error handling all custom.

## Decision
Option A: wrap dlt. JVM-free (dlt's pyiceberg-core is Rust). Apache 2.0.
```

### Example: Build Decision (rare — with ADR required)

```markdown
# ADR-002 (excerpt): ctx.sql Jinja Resolver — Build, not Wrap dbt-duckdb

Status: ACCEPTED

## Decision
Build ~1000 LOC native Jinja+sqlglot resolver (PoC #2).
dbt-duckdb is community-maintained with fragile internals.
PoC #2 validated the 1000 LOC budget before committing.
```

---

## Common Pitfalls

- **Writing the ADR AFTER the code**: ADRs must come before implementation (per `AGENTS.md §11.4` step 1). "I already wrote it, just formalizing" is not acceptable for new build decisions.
- **Vague "pros" and "cons"**: "better" or "worse" without specifics doesn't help future readers. Cite benchmarks, LOC counts, or concrete examples.
- **Missing the rollback command**: every new-dependency ADR must document the `pip install <old>==<version>` rollback.
- **Leaving open questions unresolved**: NV items that are "resolve before acceptance" must be answered before Status → ACCEPTED.

---

## Verification

```
[ ] ADR file exists at docs/decisions/ADR-NNN-<title>.md
[ ] Number is unique (no conflicts with existing ADRs)
[ ] Status is PROPOSED (not ACCEPTED — founder must review)
[ ] Open questions listed with defaults
[ ] docs/decisions/README.md updated with new row
[ ] Cross-links added to architecture doc (when ACCEPTED)
```

---

## References

- ADR template file: `docs/decisions/_template.md`
- All accepted ADRs: `docs/decisions/README.md`
- Reference ADR for wrap decision: ADR-014
- Reference ADR for major version upgrade: ADR-003
- Reference ADR for build decision: ADR-002 §3 (ctx.sql resolver)
