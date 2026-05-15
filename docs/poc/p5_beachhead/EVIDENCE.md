# PoC #5 Beachhead E2E Evidence

**Internal automated run captured**: 2026-05-13 (Windows `.venv`, foreground-supervised)
**External human validation**: Simulated run 2026-05-14 on WSL2/Ubuntu-22.04 (see `FEEDBACK_FORM.md`)
**Human external-tester sessions**: Pending — requires GitHub remote live and compensation confirmed (see `RECRUITMENT.md`)

---

## Automated walker result (2026-05-13)

- **Script**: `scripts/beachhead_e2e.py`
- **Environment**: Windows 10, repo root, Python via `.venv\Scripts\python.exe`
- **Exit code**: `0`
- **Wall time**: **16.26 s** (target: 1800 s / 30 min) — headroom: 1783 s
- **Status**: PASS (all 7 steps)

> **Scope note**: The automated walker exercises `init → version → SQLite seed → ingest → query → run` in a temp directory. It does NOT exercise Docker compose, Postgres sources, S3-API storage, or the full human-interactive quickstart path. Human sessions are required to validate the real beachhead narrative.

---

## The 8 beachhead checkpoints

These are the gates every external tester session must traverse. Human-session targets differ from automated-walker times because human sessions include reading, decision-making, and environment variability.

| # | Checkpoint | CLI command(s) | Human target | Automated (2026-05-13) |
|---|---|---|---|---|
| 1 | **Discovery** — README read + quickstart understood | *(reading only)* | < 5 min | N/A |
| 2 | **Install** — dependencies pulled and CLI confirmed | `pip install -e ".[dev]"` then `nucleus version` | < 5 min | 0.93 s |
| 3 | **First project** — scaffold created | `nucleus init <name>` | < 5 min | 0.70 s |
| 4 | **Boot stack** — local runtime live | `nucleus up` | < 2 min | Not in walker |
| 5 | **Ingest** — source → Iceberg asset created | `nucleus ingest sqlite://...` | < 8 min | 4.36 s |
| 6 | **Query** — SQL returns expected result | `nucleus query "SELECT ..."` | < 3 min | 3.99 s |
| 7 | **First custom asset** — user-authored asset materializes | `nucleus run <asset-key>` | < 5 min | 6.16 s |
| 8 | **Shutdown** — stack stopped cleanly | `nucleus down` | < 1 min | Not in walker |
| | **Total wall** | | **< 30 min** | **16.26 s** |

---

## Artifacts collected per checkpoint

For each human tester session, the following evidence is collected and stored:

| Checkpoint | Artifacts collected | How collected |
|---|---|---|
| 1 — Discovery | Tester notes in friction log (Part 2 of `FEEDBACK_FORM_TEMPLATE.md`) | Self-reported |
| 2 — Install | `pip install` terminal output (copy-paste) + elapsed time | Self-reported + screen recording |
| 3 — First project | `nucleus init` terminal output + elapsed time | Self-reported + screen recording |
| 4 — Boot stack | `nucleus up` terminal output + elapsed time + Docker version | Self-reported + screen recording |
| 5 — Ingest | Full `nucleus ingest` output (rows ingested + snapshot ID) + elapsed time | Self-reported + screen recording |
| 6 — Query | Full `nucleus query` output (result rows) + elapsed time | Self-reported + screen recording |
| 7 — First custom asset | `nucleus run` output + elapsed time + any error text | Self-reported + screen recording |
| 8 — Shutdown | `nucleus down` output + total wall time | Self-reported + screen recording |
| All | Friction log (real-time entries during session) | `FEEDBACK_FORM_TEMPLATE.md` Part 2 |
| All | Quantitative scores (Likert 1–5 + NPS) | `FEEDBACK_FORM_TEMPLATE.md` Part 4 |
| All | Qualitative free-text (3 prompts) | `FEEDBACK_FORM_TEMPLATE.md` Part 5 |

**SHA-256 of warehouse directory**: Computed by tester after checkpoint 6 (`nucleus query` pass) using:

```bash
find data/warehouse -type f | sort | xargs sha256sum | sha256sum
```

This fingerprint lets us verify the tester's Iceberg snapshot matches the expected materialization output independent of recording.

---

## Automated walker phase timing (2026-05-13 run)

```
  [step 1] setup                        PASS          0.00s  (tmp dir registered)
  [step 2] nucleus version              PASS          0.93s
  [step 3] nucleus init                 PASS          0.70s
  [step 4] SQLite source seed           PASS          0.13s  (3 rows)
  [step 5] nucleus ingest               PASS          4.36s
  [step 6] nucleus query                PASS          3.99s
  [step 7] nucleus run                  PASS          6.16s
  ──────────────────────────────────────────────────────
  TOTAL elapsed: 16.26s    Target: 30 minutes (1800s)
  Headroom: 1783.74s
  Status: PASS
```

---

## Simulation run summary (2026-05-14, WSL2)

A Nucleus swarm-implementer simulated an external tester on WSL2/Ubuntu-22.04 (Windows 11), working from README and quickstart only. Key findings (full detail in `FEEDBACK_FORM.md`):

| Checkpoint | Actual | Status | Root cause (if failed) |
|---|---|---|---|
| 1. Discovery | ~10 min | PARTIAL | Insider doc links in README confuse external readers; dead GitHub URL |
| 2. Install | 381 s (6.3 min) | FAIL — over budget | ~100 transitive deps including full Dagster + LiteLLM stack |
| 3. First project | 1 s | PASS | |
| 4. Boot stack | 16 s | PASS (over 10s target) | Docker already warm; first-run would be longer |
| 5. Ingest | 9 s | PASS | |
| 6. Query | 4 s | PASS | |
| 7. First custom asset | 2 s (FAIL on discoverability) | FAIL | `nucleus list` command does not exist yet |
| 8. Shutdown | 2 s | PASS | |
| **Total wall** | ~35–40 min | **MISSED** | Install time + GitHub 404 + `nucleus list` gap |

**Critical blockers for external testers** (must be resolved before recruitment opens):
1. `github.com/nucleus-data/nucleus` returns 404 — no real external user can `git clone` (founder action required)
2. Postgres error path exposes raw SQLAlchemy traceback (not `NucleusError`) — error translation gap
3. Install time 6+ min on cold connection — consider `[core]` vs `[dev]` extras split

---

## Storage path and retention

| Artifact | Storage path | Retention |
|---|---|---|
| Completed feedback forms (anonymized) | `docs/poc/p5_beachhead/results/FILLED_<date>_<participant-id>.md` | 12 months from session date |
| Screen recordings (if consented) | `docs/poc/p5_beachhead/results/recordings/<date>_<participant-id>.<ext>` | 12 months from session date |
| Aggregated summary | `docs/poc/p5_beachhead/results/AGGREGATE_SUMMARY.md` | Indefinite (no PII) |
| SHA-256 warehouse fingerprints | `docs/poc/p5_beachhead/results/sha256_<date>_<participant-id>.txt` | 12 months |

All PII-linked files are deleted after 12 months per `CONSENT.md` data retention policy unless tester renews consent in writing.

---

## Outstanding gaps (before external sessions open)

| Gap | Severity | Owner | Blocker? |
|---|---|---|---|
| GitHub remote 404 — testers cannot `git clone` | **Critical** | Founder | **YES — cannot open recruitment until resolved** |
| Postgres bad-creds error exposes raw stack trace | **Critical** | Engineering | **YES — must fix before first session** |
| Install time >5 min (cold) due to heavy deps | **High** | Engineering | Borderline — acceptable if GitHub + Postgres fixed |
| `nucleus list` command does not exist | **High** | Engineering | Borderline — tester gets stuck but can work around |
| Automated walker: single OS (Windows) only | **Minor** | — | No — supplement with one macOS session |
| `SCENARIO.md` persona experience band | **Fixed** | This document | Fixed in `SCENARIO.md` — aligns with `RECRUITMENT.md` (≥3 years) |
