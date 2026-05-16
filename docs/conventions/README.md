# Engineering Conventions

Project-wide engineering rules: language, type system, imports, formatting, testing, dependency hygiene, secret handling, commit and PR discipline. Per [`AGENTS.md`](../../AGENTS.md) §10, every AI agent and human contributor follows these — they make 1,000 small decisions once so they're never re-debated. PRs that violate engineering conventions are rejected without further review (per `engineering.md` §0).

This file is a navigation index. Read the linked convention before opening any PR; per [`AGENTS.md`](../../AGENTS.md) Hard Constraints #10 + #11, conventions co-evolve with the wrapped-library pin matrix in [`../internal/compatibility.md`](../internal/compatibility.md) and the official-docs anchors in [`../research/`](../research/).

---

## Files

| File | Purpose | Size |
|---|---|---|
| [engineering.md](./engineering.md) | Master convention doc — Python version, mypy strictness, imports, formatting, ruff, pytest, secrets, commits, PR labels | ~23 KB |

---

## Authority

- **This folder overrides personal preference.** PRs that violate a convention are rejected without further discussion.
- **To change a convention, raise an ADR** in [`../decisions/`](../decisions/) — never bend a rule by precedent. Conventions are amended by ADR, not in PR comments.
- **Cursor + AI agents inherit these.** [`.cursor/rules/nucleus.mdc`](../../.cursor/rules/nucleus.mdc) cites this folder; AI scaffolds that violate `engineering.md` are rejected in review per [`AGENTS.md`](../../AGENTS.md) §11.3.
- **Vocabulary discipline** lives upstream in [`AGENTS.md`](../../AGENTS.md) §7 and [`.cursor/rules/nucleus.mdc`](../../.cursor/rules/nucleus.mdc); `scripts/check_vocabulary.py` enforces in CI.

---

## Cross-cutting touch points

- [`../internal/compatibility.md`](../internal/compatibility.md) — runtime dependency pin matrix (per Hard Constraint #11)
- [`../research/`](../research/) — official-docs anchors per Hard Constraint #10
- [`../decisions/`](../decisions/) — ADRs that amend a convention (e.g., ADR-005 SDK API freeze, ADR-006 error code numbering, ADR-007 license tier policy)
- [`../patterns/secret_management.md`](../patterns/secret_management.md) — `pydantic.SecretStr` + `ctx.secrets` discipline (cross-cutting pattern)
- [`../internal/security/threat_model_v0.md`](../internal/security/threat_model_v0.md) — security implications of convention drift

---

[← `AGENTS.md` §10](../../AGENTS.md) · [`AGENTS.md` Hard Constraints #10 + #11](../../AGENTS.md) · [Sibling — decisions/](../decisions/README.md) · [Sibling — onboarding/](../onboarding/README.md) · [Sibling — research/](../research/README.md)

*Last updated 2026-05-13. Add new convention files only when a topic exceeds ~5 KB inside `engineering.md`; otherwise expand the existing master doc.*
