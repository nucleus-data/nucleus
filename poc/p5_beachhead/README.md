# PoC #5 — End-to-End 30-Minute Beachhead Validation

**Status**: Designed — runs after v0.1 ship (Mo 6-7).
**Priority**: 🔴 SHIP GATE (per `docs/specs/nucleus_poc_plan.md` §13).
**Time budget**: 2 weeks (planning + recruitment + execution + analysis).
**Companion**: [`DESIGN.md`](DESIGN.md), [`../specs/nucleus_poc_plan.md`](../specs/nucleus_poc_plan.md) §5.

## What this PoC validates

The single most important hypothesis: 5 external engineers can
`git clone` → BI-ready Iceberg asset in ≤ 30 min on fresh laptops. See
`AGENTS.md` §11.8 (Beachhead Metric as North Star) and
`docs/specs/nucleus_architecture_v4.1.md` §1.5 (5-engineer startup team success
metric).

## Files

- [`DESIGN.md`](DESIGN.md) — full design, acceptance criteria,
  ADR-002 §8.4 tagline gate embedded
- [`RECRUITMENT.md`](RECRUITMENT.md) — tester profile, channels,
  anti-bias rules
- [`SCENARIO.md`](SCENARIO.md) — verbatim instructions for testers
- [`harness.py`](harness.py) — local event-logging harness (stdlib only)

## Gates

- **v0.1 ship**: PoCs #1-4 promoted; `nucleus init` + `ingest` + `up` +
  `query` working; `SETUP.md` verified on the host OS (see
  [`DESIGN.md`](DESIGN.md) §Status gate).
- **ADR-002 §8.4 tagline gate**: tested with the same 5 external testers
  before locking the marketing tagline — see
  [`DESIGN.md`](DESIGN.md) §Embedded ADR-002 §8.4.

## Running (only after v0.1 ships)

```bash
# Founder schedules sessions via Calendly + Zoom
# Each tester runs the harness locally:
python poc/p5_beachhead/harness.py start --tester-id T1
# (tester goes through the SCENARIO.md flow)
python poc/p5_beachhead/harness.py log "ran nucleus init"
python poc/p5_beachhead/harness.py milestone first_query_returned
python poc/p5_beachhead/harness.py finish \
    --rating 4 --friction "..." --surprise "..." --missing "..."
```

Output: a JSON report at `./poc5_results/T<id>_<UTC-timestamp>.json`
containing the timeline + post-session ratings. stdlib only — no
`pip install` required for the harness itself.

## Promotion target

**None** — PoC #5 is methodology. Results land in
`docs/audits/poc5_beachhead_<YYYY-MM-DD>.md` and feed the v0.1
ship / no-ship decision at `docs/specs/nucleus_poc_plan.md` §13.
