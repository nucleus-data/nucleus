# PoC #5 Beachhead E2E Evidence

**Captured**: 2026-05-13 17:15 UTC+7 (approximate — run completed same calendar day as kit finalize)
**Run by**: swarm-implementer (foreground-supervised, autopilot mode)
**Script**: `scripts/beachhead_e2e.py`
**Environment**: Windows 10, repo root `Mordern Data Platform`, Python via `.venv\Scripts\python.exe`
**Target metric**: Under 30 minutes end-to-end per AGENTS.md §11.8 (script compares wall time to 1800 s)

## Result

- Exit code: `0`
- Wall-clock (outer shell, Stopwatch): ~17.1 s (includes interpreter startup and teardown)
- Wall-clock (script-reported chain total): **16.26 s** (`TOTAL elapsed` in summary)
- Status: **PASS** (all steps `PASS`; no `SKIPPED`, no `FAIL`)

## Phase timing

Script steps map to the automated walker phases (not the full human quickstart with Docker). Targets below mirror the 30-minute beachhead budget for **human** sessions; the walker only asserts the chain completes and sums step durations.

| Phase | Human-session target (design intent) | Actual (automated run) | Status |
|-------|--------------------------------------|-------------------------|--------|
| 1. setup | — | 0.00 s | PASS |
| 2. `nucleus version` | \< 2 min | 0.93 s | PASS |
| 3. `nucleus init` | \< 5 min | 0.70 s | PASS |
| 4. SQLite source seed | \< 5 min | 0.13 s | PASS |
| 5. `nucleus ingest` | \< 15 min | 4.36 s | PASS |
| 6. `nucleus query` | \< 5 min | 3.99 s | PASS |
| 7. `nucleus run` | \< 5 min | 6.16 s | PASS |
| **Total** | **\< 30 min (1800 s)** | **16.26 s** | **PASS** |

## Stdout/stderr (full capture — script output fits below 200-line truncation threshold)

```
Working directory: C:\Users\GOT4HC\AppData\Local\Temp\nucleus_beachhead_8o8ycbp6
Nucleus invocation: C:\Users\GOT4HC\Mordern Data Platform\.venv\Scripts\python.exe -m nucleus.cli.main

  [step 1] setup                        PASS          0.00s  (tmp dir registered)
  [step 2] nucleus version              PASS          0.93s
  [step 3] nucleus init                 PASS          0.70s
  [step 4] SQLite source seed           PASS          0.13s  (3 rows)
  [step 5] nucleus ingest               PASS          4.36s
  [step 6] nucleus query                PASS          3.99s
  [step 7] nucleus run                  PASS          6.16s

============================================================
Nucleus v0.1 Beachhead E2E - Result Summary
============================================================
Step                           Status           Elapsed
------------------------------------------------------------
1. setup                       PASS               0.00s
2. nucleus version             PASS               0.93s
3. nucleus init                PASS               0.70s
4. SQLite source seed          PASS               0.13s
5. nucleus ingest              PASS               4.36s
6. nucleus query               PASS               3.99s
7. nucleus run                 PASS               6.16s
------------------------------------------------------------
TOTAL elapsed: 16.26s    Target: 30 minutes (1800s)
Headroom: 1783.74s
============================================================
Status: PASS
```

Stderr: empty for this run.

## Outstanding gaps

- **MINOR**: Walker uses SQLite and a temp project only — it does **not** exercise Postgres + S3-API storage, Docker compose, or the full [`docs/onboarding/quickstart.md`](../../onboarding/quickstart.md) path. Human PoC #5 still validates the real beachhead narrative.
- **MINOR**: Single OS datapoint (Windows). macOS remains the stated beachhead laptop; schedule at least one external tester on Apple silicon before drawing conclusions.
- **MINOR**: Align [`SCENARIO.md`](./SCENARIO.md) screening wording with [`RECRUITMENT.md`](./RECRUITMENT.md) (experience band differs today — founder should reconcile in one pass).
