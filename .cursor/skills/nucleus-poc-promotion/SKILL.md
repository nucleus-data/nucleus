---
name: nucleus-poc-promotion
description: >-
  Run the full pre-merge gate before promoting a Proof of Concept to production
  code. Use when the user requests "promote PoC", "merge PoC #N", "graduate
  the PoC", "move poc/pN to src/nucleus/", or refers to a
  PROMOTION_CHECKLIST.md inside any `poc/` subdirectory.
---

# PoC Promotion Gate

Promotion is the moment a PoC stops being a discovery vehicle and starts
counting against the proprietary LOC budget. The phase gate at
`@AGENTS.md §11.1` (no `src/nucleus/` production code until PoC #1 promotes)
makes the first promotion architecturally critical. Subsequent PoCs follow
the same shape.

## Order of operations (do not skip)

1. **Read the per-PoC checklist first**:
   `@poc/<name>/PROMOTION_CHECKLIST.md`. That is the canonical gate; this
   skill is only the wrapper enforcement.
2. **Read the wording-review file**: `@poc/<name>/REVIEW_NOTES.md`. Confirm
   the founder has signed off on every subjective wording decision (per
   `@AGENTS.md §11.3` Risky-tier discipline).
3. **pytest GREEN**: `pytest poc/<name>/ -v` must report N/N pass. N/N skip
   or N/N error is NOT acceptable. PoC #1 reference: 21/22 green at
   `@poc/p1_error_translation/PROMOTION_CHECKLIST.md`.
4. **Governance scripts (zero violations on each)**:
   - `python scripts/dagster_leak_check.py` — no external classnames in
     user output (`@AGENTS.md §11.7`).
   - `python scripts/check_vocabulary.py` — no banned terms (`@AGENTS.md §7`).
   - `python scripts/check_licenses.py` — per ADR-007.
   - `python scripts/check_error_codes.py` — per ADR-006.
   - `python scripts/check_api_stability.py` — per ADR-005.
5. **LOC budget**: `python scripts/loc_budget.py`. Total proprietary LOC
   stays under the phase ceiling per `@AGENTS.md §11.6` (~8,000 at v0.1).
6. **Phase gate**: `@AGENTS.md §11.1` — PoC #1 must promote before any new
   `src/nucleus/` production code lands. Subsequent PoCs follow the same
   gate against their own checklists.
7. **Founder sign-off in the PR description**: explicit. Never auto-merge.
8. **Update the PoC plan**: flip the status field for that PoC in
   `@nucleus_poc_plan.md` from PROPOSED → PROMOTED with commit ref + date.
   Flip the matching `[ ] PoC #N` checkbox in `@AGENTS.md §1` to `[✓]`.
9. **Surface the downstream chain**: if promotion triggers a queued ADR
   (e.g., PoC #1 promotion fires ADR-003 PyIceberg upgrade), name the chain
   in the PR description before merging. Open the ADR as a separate PR —
   never bundle.

## Storage-substrate gate (when applicable)

If the PoC depends on the local S3 substrate (PoC #3, #4, #5), ADR-008
must be ACCEPTED before promotion. Verify dual-track docker-compose
templates work against both SeaweedFS and MinIO.

## Promotion mechanics

The per-PoC checklist (`§3 Promotion mechanics` in PoC #1's checklist) is
the source of truth for file moves, import rewrites, and architecture-doc
edits. Follow that exactly. Common pattern:

- `cp poc/<name>/<module>.py src/nucleus/<layer>/<module>.py`
- Move tests: `poc/<name>/test_<module>.py` →
  `tests/<layer>/test_<module>.py`.
- Update architecture references (drop "PoC validates feasibility"
  caveats; promote draft → shipping in `@nucleus_architecture_v4.1.md`).
- Open downstream ADR PRs separately, not bundled.

## Rollback plan (always state in PR description)

`git revert <promotion_commit_sha>` is atomic when the promotion PR uses
*Squash and merge*. The PoC stays in `poc/<name>/` for one minor version
as a dual-source. Remove the `poc/` copy only after the duration documented
in the per-PoC checklist (PoC #1: 30 consecutive days zero
`NucleusInternalError` fallbacks attributable to translator gaps).

## Cite when reviewing

`@AGENTS.md §11.1, §11.6, §11.7`; `@docs/decisions/` ADR-005, ADR-006,
ADR-007, ADR-008 (if storage-dependent); and the per-PoC
`@poc/<name>/PROMOTION_CHECKLIST.md`.
