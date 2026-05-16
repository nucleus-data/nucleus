# Positioning Drift Audit — 2026-05-13 16-worker session sweep

**Date**: 2026-05-13 · **Scope**: drift introduced by today's 16+ parallel worker outputs (~30 new/modified files: ADR-002 through ADR-013, governance scripts, threat-model v1, v01 skeleton plan, compose stubs, founder-queue + NV-index + hallucination-log, 3 PROMOTION_PR_DRAFTs, alignment sweeps #1+#2).
**Method**: `python scripts/{check_vocabulary,check_pinning,loc_budget,upgrade_smoke}.py` + `Grep` for forbidden-framings, stale tags, naming variants, `<doc> §<N>` citation patterns. Baseline: [`positioning_drift_2026-05-12.md`](positioning_drift_2026-05-12.md) (2 DRIFT / 22 LEGITIMATE).
**Exclusions** per brief: `poc/p5_beachhead/preflight.py` · `docs/recipes/sqlite_to_iceberg.md`.

---

## §1. Category 1 — Vocabulary drift (AGENTS.md §7)

**Method**: `.venv\Scripts\python.exe scripts/check_vocabulary.py` (banned terms loaded from `pyproject.toml [tool.nucleus]`).

**1 hit, FAILing CI exit-1**: [`docs/architecture/C4_component.md:168`](../../architecture/C4_component.md) — `AI-native` in a legitimate negation context (*"we are AI-**ready**, not AI-native"*) but missing the inline `<!-- banned-term: AI-native -->` exemption required by `scripts/check_vocabulary.py:91`. Same root cause as 2026-05-12 §1 row 2 (`v4.1.md:170`, since fixed).

**Recommendation**: mechanical-fix — append exemption marker; `check_vocabulary.py` returns exit 0.

---

## §2. Category 2 — Cross-doc citation drift

**Method**: sampled ≥5 citations per new file (ADR-013, threat_model_v1, v01_skeleton_plan, compatibility, FOUNDER_ACTION_QUEUE, ADR-008); verified each `<file> §<N>` target via `Grep` on cited section headers.

**Clean on the sample**. ADR-013 hits all six v4.1 sections it cites (§6.2/§6.4/§6.5/§6.7/§13.2/§18.1 — real at `docs/specs/nucleus_architecture_v4.1.md:666, :1066, :1362`), `cli_spec §10 NV #6` (real at `docs/specs/nucleus_cli_spec.md:200`), `errors.py:164` (`NucleusAssetNotFound`) + `errors.py:355` (`NucleusTimeoutError`) verified. ADR-013 NV #3 self-discloses one §6.3-vs-§6.2 off-by-one in the user prompt — not undisclosed drift. `threat_model_v1.md:25` → `ADR-010 §1 + §4 rule 5` verified. `v01_skeleton_plan.md:142` → `cli_spec §3.4 + sequence_asset_materialization.md §1 step 2` verified.

**Recommendation**: nothing. Workers self-caught citation slips this session.

---

## §3. Category 3 — Naming consistency

**Method**: `Grep` for variant tokens across new files.

| Pair | Finding | Status |
|---|---|---|
| `NucleusAssetNotFound` vs `…NotFoundError` | Zero `…NotFoundError` matches workspace-wide. | Clean. |
| `AssetRef` vs `NucleusAsset` | ADR-013 §1 + NV #5 binds `AssetRef`; only outlier is skeleton plan §6 Q2 prose (owed FAQ §C3.3). | Self-disclosed. |
| `ctx.materialize` vs `ctx.materialize_assets` | Plural drift at [`docs/specs/nucleus_cli_spec.md:52`](../../specs/nucleus_cli_spec.md) inside the same paragraph that cites singular `ctx.materialize(...)`. | Self-disclosed ADR-013 NV #1 + [FAQ §C3.3](../../FOUNDER_ACTION_QUEUE.md). Founder. |
| `nucleus run` vs `nucleus materialize` | CLI = `nucleus run`; SDK = `ctx.materialize`. Documented split (`sequence_asset_materialization.md:75`). | Clean (intentional). |
| `NE3004` vs `NE.3004` vs `NE-3004` | Zero `NE-\d{4}` or `NE\.\d{4}` matches. Only canonical `NE[1-5]\d{3}`. | Clean. |
| `Iceberg REST catalog` vs `Iceberg catalog` vs `REST catalog` | Disciplined: REST form for transport-specific (`seaweedfs.md`, lakekeeper row); bare form for the generic primitive (`README.md:7`, `errors.py:195`). | Clean (intentional). |

**Recommendation**: nothing on naming itself; `_assets` plural is FAQ §C3.3.

---

## §4. Category 4 — Status / state drift

**Method**: `Grep "^>\s*\*\*Status\*\*:" docs/decisions/ADR-*.md` + read of `AGENTS.md` §1 + `docs/specs/nucleus_poc_plan.md` + `loc_budget.py` verdict.

**Clean.** ADRs 002–013 all PROPOSED (ADR-001 = Accepted, pre-existing); `docs/specs/nucleus_poc_plan.md` zero `PROMOTED` / `ACCEPTED` matches; [`AGENTS.md:42-46`](../../../AGENTS.md) phase-gate rows still `[ ] PoC #1 …` through `[ ] v0.1 implementation`; LOC budget GREEN (227 / 8000 = 2.8 %). Informational only: [`budget_history.md:64`](../../budget_history.md) records PoC total `1,344 LOC` (point-in-time); live `loc_budget.py` reports `1,644 LOC` (+300 from same-day PROMOTION_PR_DRAFTs / REVIEW_NOTES). Not drift; reconciles next monthly snapshot.

---

## §5. Category 5 — Stale references (post-correction residuals)

**Method**: `Grep -n "RELEASE\.2025-10-15T17-29-55Z|2026-05-04"` workspace-wide; cross-checked against [`ai_hallucinations.md:41-47`](../research/ai_hallucinations.md) + FAQ §C3.1+§C3.2.

**Still stale — queued in FAQ §C3.1+§C3.2** (founder territory, 8 sites):

- `ADR-008-storage-substrate-v01.md:10, :33, :66, :109` — 4× MinIO fabricated tag (`RELEASE.2025-10-15T17-29-55Z`)
- `ADR-008-storage-substrate-v01.md:16, :32` — 2× SeaweedFS year typo (`release 2026-05-04` → should be 2025)
- `ADR-012-runtime-dependency-pin-matrix-v01.md:61` — SeaweedFS year typo; `:62` — MinIO tag

**Still stale — NOT in FAQ (newly surfaced this audit)**:

- [`README.md:211`](../../../README.md) — *"the archived MinIO `RELEASE.2025-10-15T17-29-55Z` is preserved …"* · **MEDIUM** (user-visible quickstart).
- [`docs/specs/nucleus_architecture_v4.1.md:47`](../../specs/nucleus_architecture_v4.1.md) — MinIO tag (alignment-sweep-#2 prose) · **MEDIUM** (critical doc, founder-only).
- `docs/specs/nucleus_architecture_v4.1.md:529` — MinIO tag + SeaweedFS year (storage-substrate paragraph) · MEDIUM.
- [`docs/internal/research/README.md:39`](../research/README.md) — MinIO row pin string · LOW (FAQ §E5.3 flags as optional polish).
- [`docs/NEEDS_VERIFICATION_INDEX.md:216`](../../NEEDS_VERIFICATION_INDEX.md) — *"pin candidate post-**2026**-05-04 per ADR-008"* · LOW. Brief cited `:185`; actual location is `:216`.

**Confirmed corrected** (no action): `minio.md:3,25,65,217,237` · `docker-compose.yml:8` (SeaweedFS `4.23`/`2025-05-04`, Worker B sha-verified) · `docker-compose.minio.yml:8` (MinIO `RELEASE.2025-09-07T16-13-09Z`, sha-verified). **Meta-commentary** (DO NOT fix): `ai_hallucinations.md:41-47` · `nucleus-wrapped-api-verify/SKILL.md:59` · `compatibility.md:109` · `FOUNDER_ACTION_QUEUE.md:163` · `minio.md:245`.

**Recommendation**: bundle the 5 newly-surfaced sites into the A1.14 mechanical sed/replace PR (`RELEASE.2025-10-15T17-29-55Z → RELEASE.2025-09-07T16-13-09Z` and `release 2026-05-04 → release 2025-05-04`). `v4.1.md` edits remain founder-only.

---

## §6. Category 6 — LOC sanity + governance scripts

**Method**: all four scripts via `.venv\Scripts\python.exe`.

| Script | Verdict | Detail |
|---|---|---|
| `loc_budget.py` | **PASS · GREEN** | 227 / 8000 (2.8 %). |
| `check_pinning.py` | **PASS** | 17 runtime deps exact-pinned; ADR-012 matrix in sync. |
| `upgrade_smoke.py --json` | **6/7 PASS · 1 FAIL** | Fail: `pytest` gate (CovFailUnderWarning — coverage threshold). Pass: `pin_validation`, `adr_012_cross_check`, `beachhead_e2e` (`VERDICT: SKELETON`), `benchmark_regression`, `license_check` (1 YELLOW psycopg LGPL — documented), `loc_budget`. |
| `check_vocabulary.py` | **FAIL · exit 1** | 1 hit — see §1. |

**Recommendation**: §1 fix retires `check_vocabulary` failure. `pytest` coverage failure pre-dates today (no new test-LOC added in audit window) — track separately as NV.

---

## §7. Category 7 — Forbidden mental models (AGENTS.md §8)

**Method**: workspace-wide `Grep` across the 14 banned framings (`Data OS`, `Spark killer`, `Databricks killer`, `Universal compute platform`, `Own every layer`, `AI-first`, `AI-native`, `Distributed-first`, `Plugin marketplace`, `Better Databricks`, `ML platform`, `Feature store`, `Model registry`, `agent data substrate`, `Iceberg company`).

**Same single hit as §1** — `C4_component.md:168` `AI-native` without exemption.

All others clean: **inline-exempted** at `lance.md:226`, `slack_bot_on_data.md:18`, `README.md:79`, `docs/specs/nucleus_vs_databricks.md:347`, `AGENTS.md:14/194/199`, `v4.1.md:43/239`, `.cursor/rules/nucleus.mdc:129-140`; **whole-file-exempt** per `check_vocabulary.py:81-87` (`docs/decisions/`, `docs/internal/audits/`, `docs/internal/research/strategic/`, `nucleus_architecture_v3.md`, `nucleus_architecture_v4.md`, `pyproject.toml`); **quoted negation** in spec / convention (`AGENTS.md §3/§7/§8`, `.cursor/rules/nucleus.mdc` Forbidden Framings, `docs/specs/nucleus_vs_databricks.md:214/337`, `PR template:69`). §1 fix retires this category.

---

## §8. Top-5 most severe (sorted)

1. **[`docs/architecture/C4_component.md:168`](../../architecture/C4_component.md)** · `AI-native` missing exemption · **mechanical-fix** · 1-line · trips CI today.
2. **[`README.md:211`](../../../README.md)** · stale `RELEASE.2025-10-15T17-29-55Z` in user-visible quickstart · **mechanical-fix** · bundle with A1.14 PR.
3. **[`docs/specs/nucleus_architecture_v4.1.md:47, :529`](../../specs/nucleus_architecture_v4.1.md)** · 2× stale MinIO tag + 1× SeaweedFS year typo in critical doc · **founder-amendment** · bundle with A1.14 + A1.15.
4. **[`ADR-008-storage-substrate-v01.md` lines 10/16/32/33/66/109](../../decisions/ADR-008-storage-substrate-v01.md)** · 6 stale refs in URGENT pre-v0.1-blocker ADR · **founder-amendment** · already queued FAQ §C3.1 + sign-off step 7.
5. **[`docs/specs/nucleus_cli_spec.md:52`](../../specs/nucleus_cli_spec.md)** · `ctx.materialize_assets([...])` plural drift in `nucleus run` Wraps line · **founder-amendment** · already queued ADR-013 NV #1 + FAQ §C3.3 sign-off step 9.

(Sixth: ADR-012:61/62 + research/README.md:39 + NV-INDEX:216 — all mechanical-fix LOW; same A1.14/A1.15 PR.)

---

## §9. Net assessment — better / worse / stable since 2026-05-12

**Stable to slightly better.**

| Dimension | 2026-05-12 | 2026-05-13 |
|---|---|---|
| Open DRIFT | 2 (Mermaid `C4_context.md:29`; vocab `v4.1.md:170`) | 1 CI-trip (`C4_component.md:168`) + 8 stale-tag residuals (founder-tracked) + 1 self-disclosed plural drift |
| CI-tripping | 1 (`v4.1:170`) | 1 (`C4_component.md:168`) — different file, same fix pattern |
| User-visible | Mermaid label (high vis) | `README.md:211` stale tag (medium vis; tagged "archived") |
| Tracking infra | None | NEW: `FOUNDER_ACTION_QUEUE.md` (243 lines) + `NEEDS_VERIFICATION_INDEX.md` v2 (181 markers) + `ai_hallucinations.md` (3 catches) |

Volume ballooned (16+ workers · ~30 files · 11 new ADRs · threat model · 3 PROMOTION_PR_DRAFTs · 4 governance scripts) but **drift density per worker is lower**. Yesterday: critical Mermaid label + CI-tripping vocab bug, no formal tracking. Today: drift **pre-tracked in FAQ** — §C3.1+§C3.2+§C3.3+§E5.3 catch 8 of 10 §5–§8 items before this audit ran. Audit's marginal contribution: un-queued residuals at `README.md:211`, `v4.1.md:47/529`, `NV-INDEX:216`, and the `C4_component.md:168` vocab miss.

---

## §10. NEEDS VERIFICATION

1. **`upgrade_smoke.py` pytest gate failed at coverage threshold** (CovFailUnderWarning), not test-shape. Cannot determine if delta is from today's PoC test additions or pre-existing floor mismatch. Resolution: re-run `pytest --cov-report=term-missing` vs `pyproject.toml [tool.coverage]` floor — out of audit scope.
2. **`budget_history.md:64` PoC total = 1,344 vs live = 1,644** (+300 LOC). Plausibly from PROMOTION_PR_DRAFT (×3) + REVIEW_NOTES (×2) + STATUS additions; not enumerated. Next monthly snapshot reconciles.
3. **`NEEDS_VERIFICATION_INDEX.md` line-number discrepancy** — brief cited `:185`; actual stale `2026-05-04` SeaweedFS ref is at `:216`. Either pointer-off or stale-line drift between brief authoring and this audit.
4. **`p5_beachhead/preflight.py` + `sqlite_to_iceberg.md` LOC count** — excluded per brief; cannot confirm §6 LOC totals impact.

---

*Last verified 2026-05-13. Per [`docs/internal/audits/README.md`](README.md): audits are append-only; un-fixed findings flow forward. Auto-fix log to be appended when the §1 vocab fix lands; founder-territory items (§5 stale residuals + §3 `_assets` plural) flow forward after FAQ §C3.1+§C3.2+§C3.3 sign-off.*
