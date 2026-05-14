# Positioning Drift Audit — v4.1.3 patches sweep

**Date**: 2026-05-12 · **Scope**: drift introduced by v4.1.3 patches per ADR-002 §8.6 apply log.
**Method**: `rg` workspace-wide for `"AI-assisted by design"`, `"modern composable data engineering platform"`, `"AI-native"`, `"agent data substrate"`, `"workbench for agent"`. Classified per audit-brief categories (a) §2 pillar #3 context, (b) ADR-002 / v4.1.3 retirement note, (c) deprecated v4.0/v3 doc, (d) research file.

## §1. DRIFT findings

| File:line | Match | Suggested fix |
|---|---|---|
| **`docs/architecture/C4_context.md:29`** | Mermaid label `Modern composable data\|engineering platform.\|Local-first, AI-assisted,\|built on Apache OSS.` — **DRIFT, patch-introduced**: ADR-002 §8.6 apply log did not include the C4 diagrams; the only drift the v4.1.3 patches missed. | Replace with v4.1 §1 + ADR-002 §8.1 hierarchy: `Ship data products from a laptop.\|Local-first Python SDK + CLI\|for Iceberg-native pipelines\|and analytics stacks.` |
| **`nucleus_architecture_v4.1.md:170`** | `\| 6 \| AI-native data contracts \| LLM-generated, human-reviewed (v0.5+) \|` — **DRIFT, pre-existing (NOT introduced by v4.1.3)**: trips `pyproject.toml:318` ban-list and `scripts/check_vocabulary.py`. | Rename to `LLM-generated data contracts` (preferred) OR add inline `<!-- banned-term: AI-native -->` exemption per `scripts/check_vocabulary.py:80-81`. v4.1 is on the critical-docs list — flagged not auto-fixed. |

## §2. LEGITIMATE matches (22 findings, grouped)

- **(a) §2 pillar #3 / engineering layer context** — `.cursor/rules/nucleus.mdc:100`; `AGENTS.md:152`; `nucleus_architecture_v4.1.md:7,34,255`; `docs/architecture/C4_container.md:144`; `docs/architecture/C4_context.md:75,96`. Per ADR-002 §8.5.
- **(b) ADR-002 / v4.1.3 retirement notes + forbidden-framings** — `nucleus_architecture_v4.1.md:7,34`; `docs/decisions/ADR-002-positioning-decision-2026-05.md` (5 hits); `README.md:79`; `AGENTS.md:14,194,199,200`; `.cursor/rules/nucleus.mdc:133-135`.
- **(c) Deprecated v4.0/v3 docs** — `nucleus_architecture_v4.md:31,128,185`; `nucleus_architecture_v3.md:8`.
- **(d) Strategic research files** — `docs/research/strategic/ai_agent_data_infra_2026.md` (multi); `docs/research/strategic/competitive_landscape_2026.md` (multi).
- **(e) Ban-enforcement infra itself** — `pyproject.toml:318`; `scripts/check_vocabulary.py:10,11,61`; `docs/conventions/engineering.md:449`; `.github/workflows/ci.yml:82`.
- **(f) PR-label convention** (`provenance:ai-assisted`, not the marketing tagline) — `docs/conventions/engineering.md:396,400`; `CONTRIBUTING.md:11`.

**No drift in the other audited files**: `threat_model_v0.md`, `nucleus_poc_plan.md`, `nucleus_ctx_sdk_spec.md`, `nucleus_asset_model_spec.md`, `nucleus_project_anatomy.md`, `nucleus_cli_spec.md`, `nucleus_implementation_readiness.md`, `nucleus_red_team_review.md`, `nucleus_vs_databricks.md`.

## §3. Verdict + auto-fix log + next-pass recs

**LEGITIMATE 22 · DRIFT 2 · auto-fixes 0.** Both DRIFT items fail the brief's auto-fix rule (*"trivially stale strings (e.g., a comment in scripts/)"*): `C4_context.md` is a primary architecture doc with a user-visible Mermaid diagram, and `nucleus_architecture_v4.1.md` is on the **DO NOT modify without flagging** critical-docs list. Both surfaced for next pass.

**Next-pass priority**: (1) update `C4_context.md:29` Mermaid label per §1; spot-check the rest of `C4_context.md` and `C4_container.md` for the same drift; append a v4.1.3 changelog row noting the C4 propagation. (2) Resolve `nucleus_architecture_v4.1.md:170` — rename (preferred) or add exemption; vocab check will currently FAIL on v4.1 itself if `scripts/check_vocabulary.py` is wired into CI per `.github/workflows/ci.yml:82`. (3) Re-run this sweep after the next ADR-002 §8.6 apply-log extension (e.g. when ADR-003 ships).

---

*Critical contradictions: 1 (C4_context Mermaid label vs v4.1.3 thesis).*
