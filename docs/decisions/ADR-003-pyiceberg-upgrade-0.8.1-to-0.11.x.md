# ADR-003: Upgrade PyIceberg from 0.8.1 to 0.11.x (skip 0.9.x and 0.10.x)

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0; PoC #1 promoted 2026-05-13 satisfies the auto-fire trigger)
> **Date**: 2026-05-12 (last touched 2026-05-13) · **Decider**: Solo founder (queued by ADR-002 §4.2)
> **Tags**: dependencies, upgrade, hard-constraint-11, iceberg, dlt-prerequisite
> **Related**: ADR-001, ADR-002 §4.2, AGENTS.md §11.13, `docs/internal/research/pyiceberg.md` §2 + §6 + §9, `docs/internal/research/dlt.md` §6

## Context

Per **ADR-002 §4.2** (PyIceberg upgrade scheduled "as the first dependency-upgrade ADR immediately after PoC #1 passes (Mo 2-3)") and **AGENTS.md §11.13** (one-component-per-PR, 24 h cool-down, mandatory smoke test): current pin `pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1` (`pyproject.toml:47`, Nov 2024) is ~15 months and 3 minor releases behind 0.11.1 (Feb 2026).

**Second forcing function (added 2026-05-13)**: the v0.3 connector framework (`dlt`) requires `pyiceberg>=0.9.1` for its Iceberg destination — `dlt[pyiceberg]==1.26.0` will fail `pip install` resolution against our current `0.8.1` pin (see `docs/internal/research/dlt.md` §6, KEY FINDING). This ADR is therefore a hard prerequisite for **two** downstream workstreams now, not one:

1. **Immediate** (Mo 2-3): PoC #1 promotion to `src/nucleus/coordination/error_translation.py` (validates 0.11's `CommitFailedException` constructor against the 14 wrapped-library handlers in the promotion-ready translator).
2. **Mid-roadmap** (Mo 14-20): v0.3 dlt integration ADR — cannot land until this upgrade clears.

This does NOT change the trigger condition (still: PoC #1 passes). It tightens the consequence-of-delay: slipping this upgrade slips v0.3 connector breadth, not just PoC #1 promotion.

## Decision

> **Skip 0.9.x and 0.10.x. Jump directly to the latest 0.11.x release** (currently 0.11.1; re-confirm at PR time per AGENTS.md §11.12).

What 0.11.x buys, per `docs/internal/research/pyiceberg.md` §B.3: `ExpireSnapshots` API, the O(N²) manifest cache fix, generator-based writes, full ORC read, sort-order evolution, REST scan planning, Python 3.13. Skipping 0.9/0.10 is supported and explicitly endorsed by §B.3.

Single dedicated PR: (1) bump `pyproject.toml` to `==0.11.1` (no other dep changes); (2) read all 3 minor changelogs and summarize behavioral changes in the PR description (§11.13); (3) add `tests/upgrade_smoke/test_iceberg_upgrade.py` per Verification below; (4) re-validate PoC #3 (`poc/p3_ingest/`) **unchanged** — most exposed PoC; (5) update `docs/internal/compatibility.md`; (6) **24 h cool-down** before the next dep upgrade.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **API surface drift across 3 minor versions** — `Schema`, `UpdateSchema`, `SqlCatalog` URI parsing all churned (§9). | Read all 3 changelogs before the PR; rewrite `_build_schemas()` and `_open_catalog()` against 0.11; smoke-test on a real filesystem catalog (§11.13). |
| **`CommitFailedException` / `CommitStateUnknownException` constructor signatures may have shifted**, breaking PoC #1 translators. | PoC #1 must pass on 0.8.1 first; then re-run all 8 translator cases against 0.11. |
| **PyArrow envelope** — 0.8 needs `pyarrow<19`; 0.11 may widen. Do **not** unilaterally bump pyarrow (separate ADR). | Re-check upper bound in 0.11 changelog. |
| **Filesystem-catalog atomicity on Windows** (`os.rename`, §7). | Smoke test runs the kill-9 stress on Win + macOS + Linux per ADR-001. |

## Verification plan

`tests/upgrade_smoke/test_iceberg_upgrade.py` — minimum cases (all pass on Win + macOS + Linux):

1. **5-record write + read + `ExpireSnapshots` round-trip on filesystem catalog** (mandatory minimum, headline test; uses 0.11.x's new `ExpireSnapshots` per §B.3).
2. `Catalog.create_namespace` + `create_table` + `Table.append` + `scan().to_arrow()` round-trip.
3. `Table.update_schema()` adds a nullable column; append + read still works.
4. `CommitFailedException` still importable from `pyiceberg.exceptions` and raised on optimistic-concurrency conflict — PoC #1 contract.
5. `Table.scan().to_duckdb("name")` zero-copy registration still works — PoC #3 contract.
6. **PoC #3 test suite (7 cases) runs unmodified** — must stay 7/7 green.

Acceptance: all six pass on three OSes; benchmark within ±10% of 0.8.1 baseline (§11.13).

## Rollback

```bash
pip install "pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1"
```

Then `git revert` the PR. No data migration: Iceberg table format is read-stable across 0.8 → 0.11.

## Docs URL

- API root (mandatory cite, AGENTS.md §11.12): https://py.iceberg.apache.org/api/
- 0.11.0 release notes: https://github.com/apache/iceberg-python/releases/tag/pyiceberg-0.11.0
- All 0.11.x release notes (verify latest patch at PR time): https://github.com/apache/iceberg-python/releases

Every 0.11.x feature claim above is sourced from `docs/internal/research/pyiceberg.md` §B.3; upgrade considerations from §9.

## Trigger

Status flips **PROPOSED → ACCEPTED** when **PoC #1 (Dagster Error Translation Layer) passes 17/17 green pytest** on the validation set in `docs/specs/nucleus_architecture_v4.1.md` §6.4 / Appendix C and `docs/specs/nucleus_poc_plan.md` §1. **Not a calendar date.** If PoC #1 fails, paused and re-evaluated alongside the mini-scheduler escalation per v4.1 §6.7.

## Downstream consumers (sequencing matters)

| Consumer | Mo | Blocks how? |
|---|---|---|
| PoC #1 promotion (`src/nucleus/coordination/error_translation.py`) | 2-3 | Validates 14 wrapped-library handlers against 0.11's `CommitFailedException` / `CommitStateUnknownException` constructors. |
| v0.3 connector framework (dlt) | 14-20 | `dlt[pyiceberg]==1.26.0` requires `pyiceberg>=0.9.1`; the v0.3 dlt ADR cannot land until this upgrade clears (`docs/internal/research/dlt.md` §6). |
| ADR-001 atomic-commit revisit | TBD | 0.11's REST scan planning + manifest-cache fix may change the "no custom commit service" risk calculus; revisit after upgrade. |

**Adjacent v0.3 sequencing note (not in scope of this ADR; logged for foresight):** `docs/internal/research/dbt-duckdb.md` §6 identified a SEPARATE blocker for the v0.3 dbt-duckdb adapter — `dbt-duckdb==1.10.1` transitively requires `click>=8.3.0,<9.0`, but `pyproject.toml` pins `click==8.1.8` as of 2026-05-14 (raised from `8.1.7` for `litellm` alignment). Full `8.3.x` remains its own future ADR. Logging here so the founder sees BOTH v0.3 pre-cursor upgrades (pyiceberg + click) when sequencing the v0.3 implementation window.

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
