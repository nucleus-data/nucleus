# PoC #5 — End-to-End 30-Minute Beachhead Validation

> Validates: 5 external engineers can `git clone` → BI-ready Iceberg asset
> in ≤ 30 minutes on fresh laptops (per `docs/specs/nucleus_poc_plan.md` §5 and
> `docs/specs/nucleus_architecture_v4.1.md` §1.5).

## North Star

The single most important metric in the product. Per `AGENTS.md` §11.8:
*"Every commit, every PR, every architectural decision must serve"* this
metric. PoC #5 is its empirical validation, and the v0.1 ship gate per
`docs/specs/nucleus_poc_plan.md` §13.

## What "BI-ready Iceberg asset" means

A tester is considered successful when **all five** conditions hold,
captured by the harness as named milestones (see `harness.py`):

1. An Iceberg table snapshot exists in the local catalog
   (`pyiceberg.Catalog.list_tables(...)` lists it).
2. The asset has ≥ 1 row of **real** (not mock) data ingested from a real
   source (Postgres / SQLite seeded with `orders`).
3. A DuckDB query against the asset returns the expected row shape
   (e.g. `SELECT count(*), sum(amount) FROM analytics.orders_daily`).
4. The asset appears in the asset graph with a green materialization status.
5. The Iceberg snapshot is committed — visible via the catalog after a
   process restart, not just held in-memory.

Wording in user-facing surfaces (CLI output, README, scenario script)
follows `AGENTS.md` §7 vocabulary — *asset / materialization / snapshot /
contract*, never *job / task / version*.

## Acceptance criteria (mirror `docs/specs/nucleus_poc_plan.md` §5)

| # | Criterion | Target | Stop-the-line? |
|---|---|---|---|
| 1 | Median time across 5 testers | ≤ 30 min | YES |
| 2 | P90 time | ≤ 45 min | NO (warn — fold into v0.2 backlog) |
| 3 | Each tester completes end-to-end without founder intervention | 5/5 | YES |
| 4 | Testers external to founding team | 5/5 | YES (`AGENTS.md` §11.9 hard rule) |
| 5 | Stuck-point logging — every blocker captured by the harness | every event | YES |
| 6 | "Would you use this for a real project?" rating | ≥ 3/5 from ≥ 3 testers | YES |

Failure on any "YES" row → v0.1 ship blocked; trigger the fallback plan
below.

## Embedded ADR-002 §8.4 — Tagline Field Test

Per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8.4, before
**locking** the marketing tagline *"Ship data products from a laptop"*,
field-test it with the same 5 external testers. The methodology is folded
in here rather than running a separate PoC:

1. Before the hands-on session, show each tester the README L1 headline +
   L2 sub-headline only (no architecture pages, no docs).
2. Ask: **"What does this tool do, in your own words?"**
3. Record the answer verbatim in the harness
   (`milestone tagline_recall` followed by `log "<verbatim>"`).
4. Acceptance: ≥ 3/5 testers answer with concepts matching *laptop* OR
   *local-first* OR *Iceberg* OR *Python SDK / CLI* OR *pipelines* OR
   *data products*.
5. If < 3/5 match → tagline needs a rewrite before v0.1 ship; open an
   ADR-002 amendment PR and re-run §8.4 with a fresh tester pool.

Per ADR-002 §8.1, until this gate passes the headline is a **working
default**, not the locked tagline.

## Recruitment plan

See [`RECRUITMENT.md`](RECRUITMENT.md). Hard rule: testers external to
founding team (`AGENTS.md` §11.9). Mid-level data engineers (2-5 yrs),
zero prior Nucleus exposure, recruited paid ($200-500 per 2-hour session).

## Scenario script

See [`SCENARIO.md`](SCENARIO.md). Verbatim instructions handed to each
tester at session start. Written in generic data-engineering vocabulary
(*table*, *query*, *ingest*, *aggregate*) so the test measures Nucleus's
clarity, not the tester's pre-loaded vocabulary.

## Observation harness

See [`harness.py`](harness.py). stdlib only — testers should not need
`pip install` before running the harness itself. Captures: session start,
free-text events, named milestones, and the post-session rating + 3
open-text fields.

## Time budget + schedule

Per `docs/specs/nucleus_poc_plan.md` §5: **2 weeks** (planning + recruitment +
execution + analysis). Sessions block in a 5-day window
(`RECRUITMENT.md` §scheduling) to minimize cross-session contamination.
Runs in Mo 6-7 of the v0.1 timeline (after v0.1 Tier 1 ships per
`docs/specs/nucleus_architecture_v4.1.md` §17.2 / `README.md` Status table). Founder
schedules via Calendly + Zoom; founder is **not** present in the call.

## Status gate — preconditions

PoC #5 cannot run until ALL of these hold:

- [ ] PoC #1 promoted (`src/nucleus/coordination/error_translation.py`)
      per `poc/p1_error_translation/PROMOTION_CHECKLIST.md`
- [ ] PoC #3 promoted (`src/nucleus/ctx/copy_from.py`) per
      `poc/p3_ingest/STATUS.md` §4
- [ ] `nucleus init` command works            <!-- pre-v0.1; CLI surface TBD per docs/specs/nucleus_cli_spec.md -->
- [ ] `nucleus ingest` command works (PoC #3) <!-- pre-v0.1; CLI surface TBD per docs/specs/nucleus_cli_spec.md -->
- [ ] `nucleus up` boots < 10s (PoC #4 validated)
- [ ] `nucleus query "..."` returns BI-ready row count <!-- pre-v0.1; CLI surface TBD per docs/specs/nucleus_cli_spec.md -->
- [ ] `SETUP.md` instructions verified on the host OS the tester uses
      (macOS primary; Windows + Linux as stretch — see
      `RECRUITMENT.md` §scheduling)

## Fallback plan

Per `docs/specs/nucleus_poc_plan.md` §5 + §13:

| Outcome | Action |
|---|---|
| 1-2 stuck points fixable in < 2 weeks | Fix and retest with a fresh tester pool (do not re-run with the same testers — they learned). |
| 3+ stuck points OR architectural issue | Return to v4.1 amendment cycle. Delay v0.1 ship; open an ADR. |
| Tagline field test < 3/5 | Open ADR-002 amendment PR; rewrite headline; re-run §8.4 gate (not the hands-on portion). |

The beachhead metric is non-negotiable per `docs/specs/nucleus_poc_plan.md` §13 —
v0.1 ship date moves before the metric does.

## Promotion target

**None.** PoC #5 is a methodology, not a code artifact. Outcomes land in:

- `docs/audits/poc5_beachhead_<YYYY-MM-DD>.md` — per-tester transcripts,
  timings, stuck-points, tagline recall, ratings.
- `docs/specs/nucleus_poc_plan.md` §5 acceptance checkboxes flipped to ✓ on PASS.
- `AGENTS.md` §1 phase checklist line "PoCs #2-5 validated" flipped.
- ADR-002 §8.4 gate marked CLEARED (or AMENDED on rewrite).

The harness in this directory stays as the regression-test entry point
for future quarterly UX validations (per `AGENTS.md` §11.9 cadence).
