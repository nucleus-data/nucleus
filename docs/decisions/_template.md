# ADR-XXX: <Short imperative title — one line>

> **Status**: Proposed | Accepted | Deprecated | Superseded by ADR-YYY
> **Date**: YYYY-MM-DD
> **Decider(s)**: <name> (currently: solo founder)
> **Tags**: <e.g. architecture, dependencies, security, performance>
> **Supersedes**: (none) | ADR-NNN
> **Related**: ADR-MMM, doc paths

---

## Context

What's the situation that prompts this decision? Be brief but complete.

- What problem are we solving?
- What constraints apply? (List relevant Hard Constraints from AGENTS.md if applicable.)
- What's at stake if we choose wrong?

**Forces in tension** (what makes this hard):
- Force A vs Force B
- Force C vs Force D

---

## Decision

State the decision **clearly**, in one paragraph. Use imperative voice: "We will use X" not "X is being used".

> **We will <do the thing>.**
>
> Specifically:
> - First concrete action
> - Second concrete action
> - …

---

## Rationale

Why this option over the others? Cover:

1. **How this addresses the forces above.**
2. **Why we reject the alternatives.** (See Alternatives section below.)
3. **What evidence/research supports this?** (Link to spikes, benchmarks, docs.)
4. **Which Hard Constraint(s) does this satisfy / enforce?**

---

## Alternatives considered

### Alternative A: <option>

**Pros**:
- ...

**Cons**:
- ...

**Why rejected**: One sentence.

### Alternative B: <option>

**Pros**:
- ...

**Cons**:
- ...

**Why rejected**: One sentence.

### Alternative C: <option (often "do nothing")>

**Why rejected**: ...

---

## Consequences

### Positive
- ...
- ...

### Negative / costs
- ...
- ...

### Neutral / observed
- ...

### Risks introduced
- **Risk**: ...
- **Mitigation**: ...

---

## Implementation notes

(Optional) High-level steps to enact this decision. Use ordered list when sequence matters.

1. ...
2. ...

**Affected files / modules** (if known):
- `src/nucleus/...`
- `docs/...`

**Migration** (if changing existing behavior):
- What breaks?
- What's the upgrade path?
- Deprecation timeline?

---

## Compliance / verification

How will we know this decision is being followed?

- [ ] Test added: `tests/...`
- [ ] CI check added: `scripts/...`
- [ ] Documented in: `docs/...`
- [ ] Linter rule: `pyproject.toml` `[tool.ruff]` ...

---

## Open questions

(Optional) Things this ADR does NOT resolve, captured for future work:

- ...

---

## References

- Link to GitHub issue (if any)
- Link to relevant external docs (per Constraint #10)
- Link to senior-review feedback (if applicable)
- Link to PoC results (if applicable)

---

## Notes on filling out this template

- **Be concrete.** "We will use DuckDB version 1.1.x" is better than "we will pick a SQL engine".
- **Cite versions and dates.** Software changes; the "current" we knew yesterday is not today.
- **State alternatives even when obvious.** Future-you will wonder why.
- **Don't pad.** A 1-page ADR is better than a 5-page one. Keep it terse.
- **Update Status** when this decision evolves. If superseded, link forward.
- **Number sequentially.** Look at the highest existing ADR number and add 1.

When in doubt, model after [`ADR-001-no-iceberg-commit-service.md`](ADR-001-no-iceberg-commit-service.md).
