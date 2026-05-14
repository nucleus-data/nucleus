# Governance

## Today (founder-led OSS)

Decision-making rests with the project founder / listed maintainers in `MAINTAINERS.md`. Day-to-day policy is grounded in architecture v4.1 and `AGENTS.md`: wrap-not-build defaults, Constraint #11 (pins and upgrades), error translation discipline, and the proprietary LOC ceiling.

Contribution paths are Issues and PRs; larger trade-offs belong in Architectural Decision Records (ADRs).

## ADR process

1. Draft `docs/decisions/ADR-NNN-short-slug.md` with **PROPOSED** status.
2. Reference the architecture section touched and summarize alternatives/consequences (see existing ADRs).
3. After review, flip status to **ACCEPTED** (or REJECTED / SUPERSEDED with cross-links).

The index (`docs/decisions/README.md`) summarizes the numbering line.

## Transition

If the founder adds co-maintainers, extend `MAINTAINERS.md` areas of ownership and revise `CODEOWNERS` accordingly. Consensus-based governance for contentious changes stays optional until documented in a superseding ADR; until then founder approval remains authoritative for merges that cross architecture or license boundaries.
