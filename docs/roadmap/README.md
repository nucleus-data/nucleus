# Nucleus Roadmap — Reading Guide

> **Audience**: External developers joining the project + the founding team.
> **Purpose**: Authoritative, version-to-version plan for what Nucleus builds, when, and why — so contributors align effort with the product's actual trajectory before touching a line of code.

---

## Who this is for

| Reader | What to read first |
|---|---|
| New contributor | This file → [`HANDOVER.md`](HANDOVER.md) → [`overview.md`](overview.md) → current-phase doc → relevant [`../dev-guides/`](../dev-guides/) runbook |
| Founder / architect | [`overview.md`](overview.md) version timeline → current-phase doc → [`risks-and-mitigations.md`](risks-and-mitigations.md) |
| External evaluator / investor | [`overview.md`](overview.md) (§Mission, §Timeline) → [`non-goals.md`](non-goals.md) |
| Open-source contributor from the future | Read the phase doc for the version you want to contribute to; check `AGENTS.md §3` constraints first |

---

## How to read

1. **Start with [`overview.md`](overview.md)** — one page with the mission, the 8-question gate, and the full version timeline. Orients you in 10 minutes.
2. **Dive into the current phase doc** — each phase file has features, go/no-go gates, risks, and step-by-step contributor onboarding for that phase.
3. **Scan future phases for direction** — future docs are honest about what is and isn't decided yet. Sections that depend on external research say `[REFINE WITH RESEARCH FINDINGS]`.
4. **Use [`../dev-guides/`](../dev-guides/)** for "how to do X" — the roadmap says *what*; the guides say *how*.

---

## Document map

| File | Size | Purpose |
|---|---|---|
| `README.md` (this file) | 3 KB | Index + reading guide |
| [`overview.md`](overview.md) | 6 KB | Mission, pillars, 8-Q gate, version timeline |
| [`v0.2-public-launch.md`](v0.2-public-launch.md) | 10 KB | **Current phase** — Workbench + docs + CI + connectors |
| [`v0.3-hardening.md`](v0.3-hardening.md) | 9 KB | Post-launch reliability + chaos tests + dlt connectors |
| [`v0.5-multimodal.md`](v0.5-multimodal.md) | 8 KB | Daft + Lance + AI Copilot lineage-aware |
| [`v0.7-cloud-tier-mvp.md`](v0.7-cloud-tier-mvp.md) | 7 KB | OSS Cloud edition (single-tenant managed) |
| [`v1.0-production-ready.md`](v1.0-production-ready.md) | 8 KB | SLA + governance maturity + first paying customers |
| [`v1.5-enterprise-gateway.md`](v1.5-enterprise-gateway.md) | 6 KB | Auth federation + audit + multi-env |
| [`v2.0-federation-mesh.md`](v2.0-federation-mesh.md) | 5 KB | Iceberg REST federation + Data Mesh Mode 3 |
| [`non-goals.md`](non-goals.md) | 6 KB | What Nucleus will NEVER build — and why |
| [`risks-and-mitigations.md`](risks-and-mitigations.md) | 10 KB | Top risks per phase + mitigation playbooks |
| [`HANDOVER.md`](HANDOVER.md) | 4 KB | "Start here" doc for the next developer joining |

---

## Version naming convention

Nucleus uses [Semantic Versioning](https://semver.org/):

- **Major** versions (`v1.0`, `v2.0`) = milestone releases with stability commitments.
- **Minor** versions (`v0.2`, `v0.3`) = phase releases adding features. No breaking changes to `ctx.*` Frozen-tier APIs.
- **Patch** versions (`v0.1.1`) = bug fixes + urgent security. No new features.

Per [`ADR-005`](../decisions/ADR-005-ctx-sdk-api-freeze-policy.md), `ctx.*` Frozen-tier APIs get a 2-year deprecation cycle before removal (from `v1.0` onward). AI-tier APIs (`ctx.agent`, `ctx.copilot`) may break within minor versions with `NucleusAIBreakingChange` warnings.

### Release cadence

| Horizon | Cadence |
|---|---|
| v0.x phases | Every 3-6 months (founder pacing) |
| v1.x → v2.0 | Every 6-12 months |
| Patch releases | As needed; no waiting for phase trains |

---

## Living-document policy

These roadmap docs are **living documents** — they evolve with the project:

1. **Phase doc is authoritative for that phase.** Once a phase ships, its doc is updated to reflect what actually shipped vs what was planned.
2. **Future phase docs are intentional projections**, not commitments. Anything marked `[REFINE WITH RESEARCH FINDINGS]` must be updated before that phase starts.
3. **Updating rules**: only the founding team amends phase docs for future-phase content. Contributors may open a PR with `[PROPOSAL]` prefix in a new section to suggest changes.
4. **Cross-reference discipline**: when an ADR changes the roadmap, both the ADR and this roadmap are updated in the same PR.

---

## Cross-links to dev guides

The roadmap says *what* to build. For *how*, see:

- Adding a new connector → [`../dev-guides/03-add-connector.md`](../dev-guides/03-add-connector.md)
- Adding a CLI command → [`../dev-guides/04-add-cli-command.md`](../dev-guides/04-add-cli-command.md)
- Authoring an ADR → [`../dev-guides/08-author-adr.md`](../dev-guides/08-author-adr.md)
- Upgrading a wrapped library → [`../dev-guides/07-upgrade-wrapped-library.md`](../dev-guides/07-upgrade-wrapped-library.md)
- Release process → [`../dev-guides/11-release-process.md`](../dev-guides/11-release-process.md)

---

*Last updated: 2026-05-15. Source of truth: `docs/specs/nucleus_architecture_v4.1.md` §18.*
