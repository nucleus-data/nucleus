# Follow-Up Items — Gaps Surfaced During Roadmap Authoring

> **Purpose**: Items discovered during roadmap + dev-guides authoring that require source code changes, architectural decisions, or research output before the relevant roadmap section can be finalized. Surfaced per task instructions: "write findings to FOLLOW_UPS.md and continue."

---

## Research-Dependent Sections (Refine Post-Wave-1F/G/H)

These sections use `[REFINE WITH RESEARCH FINDINGS]` placeholders. Update them when the corresponding research docs are available.

| Section | Research file needed | Placeholder location |
|---|---|---|
| v0.3 connector priority order | `docs/internal/research/parity_vs_databricks_snowflake.md` | `v0.3-hardening.md` §dlt connectors |
| v0.3 Lakekeeper config parity | `docs/internal/research/lakekeeper.md` | `v0.3-hardening.md` §Lakekeeper |
| v0.3 Marimo version compat | `docs/internal/research/marimo.md` | `v0.3-hardening.md` §Marimo |
| v0.5 Daft integration API | `docs/internal/research/daft.md` | `v0.5-multimodal.md` §Daft |
| v0.5 Lance API for Nucleus | `docs/internal/research/lance.md` | `v0.5-multimodal.md` §Lance |
| v0.5 perf targets | `docs/internal/research/performance_reliability_targets.md` | `v0.5-multimodal.md` §Cost meter |
| v1.0 Python column-level lineage approach | TBD (needs architecture research) | `v1.0-production-ready.md` §Column-level lineage |
| v1.5 differential privacy library | TBD at v1.5 design time | `v1.5-enterprise-gateway.md` §Privacy |

---

## Architectural Decisions Still Pending

These affect the roadmap but are founder-gated:

| Decision | Current status | Affected doc |
|---|---|---|
| Workbench tech stack: Tauri vs pure web | Open (ADR-016 records choice as Vite/React; revisit if desktop app desired) | `v0.2-public-launch.md` |
| v0.7 cloud: self-hosted option (users run their own control plane) | Open — not built in v0.7; reconsidered at v1.5 | `v0.7-cloud-tier-mvp.md` |
| Phase codenames (Public Launch, Hardening, etc.) | Working titles — founder may want to lock final names | `overview.md` version table |
| Mo 24 decision gate monitoring cadence | ADR-002 §8.3 says quarterly; FOUNDER_ACTION_QUEUE §D4.1 says extract at first trigger | `risks-and-mitigations.md` v1.0 |

---

## Naming Conventions Assumed (Confirm with Founder)

- Phase codenames: "Public Launch", "Hardening", "Multimodal", "Cloud Tier MVP", "Production-Ready", "Enterprise Gateway", "Federation + Mesh" — these are working names. Founder may want to finalize before v0.2 announcement.
- Version numbers in the timeline match `docs/specs/nucleus_architecture_v4.1.md` §18 exactly. If the roadmap shifts, both docs must be updated together.

---

## Items That Would Benefit from Source Code Changes

These are not code changes made by the roadmap docs (they're read-only here), but gaps in the codebase that would improve the dev-guide accuracy:

| Item | Current gap | Suggested fix |
|---|---|---|
| `scripts/upgrade_smoke.py` test narrowing | Some pre-existing test failures exist (test_up_down.py, test_v01_template.py) that cause upgrade_smoke gate to fail | Fix the pre-existing tests or narrow upgrade_smoke scope |
| `nucleus ingest` CLI bypasses `ctx.copy_from` dispatcher | `cli/main.py:1091, 1113` imports directly; verified by FOUNDER_ACTION_QUEUE | Spawn dedicated builder per FOUNDER_ACTION_QUEUE §MEDIUM finding |
| `docs/specs/nucleus_project_anatomy.md` is stale (v3-era) | References `nucleus.yaml`, old layout | Add "Superseded by v4.1 §3.1" header; full rewrite in v0.2 docs sprint |

---

*Created: 2026-05-15 during roadmap + dev-guides authoring.*
