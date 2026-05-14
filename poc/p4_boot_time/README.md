# PoC #4 — `nucleus up` <10s Cold Boot

> **Status**: Scaffolded — measurement harness drafted, not yet run end-to-end
> (requires Python env + Docker for MinIO). **Priority**: MEDIUM (per
> `nucleus_poc_plan.md` §11). **Time budget**: 1 week.
> **Companion**: [`DESIGN.md`](DESIGN.md), [`../../nucleus_poc_plan.md`](../../nucleus_poc_plan.md) §4.

## What this PoC validates

Per `nucleus_architecture_v4.1.md` §5.7 + §6.3 + `nucleus_poc_plan.md` §4:
`nucleus up` cold boot <10s on developer hardware (M1 16GB baseline), warm
boot <3s, idle RAM <500MB, all components reachable (MinIO health, pyiceberg
catalog, Dagster `Definitions`).

## Files

- [`DESIGN.md`](DESIGN.md) — phase breakdown + acceptance criteria
- [`measure.py`](measure.py) — standalone timing harness (5 phases)
- [`test_measure.py`](test_measure.py) — unit tests for the harness (no Docker required)

## Running locally

```bash
pip install -e ".[dev]"

# Optional: start MinIO. No docker-compose.yml exists yet — start manually:
docker run -d --name nucleus-minio -p 9000:9000 -p 9001:9001 \
  quay.io/minio/minio server /data --console-address ":9001"

python poc/p4_boot_time/measure.py        # the harness
pytest poc/p4_boot_time/ -v               # the unit tests (no MinIO needed)
```

Exit codes: **0** = PASS, **1** = FAIL (a phase exceeded its target),
**2** = INCOMPLETE (a phase was skipped — typically MinIO not running, or
psutil unavailable on Windows).

## What's gated

The harness can run as soon as `pip install -e ".[dev]"` works. The
`nucleus up` CLI itself is gated on PoC #1 promotion (per `AGENTS.md` §11.1
phase gate — no production code in `src/nucleus/` until then).

## NEEDS VERIFICATION

`measure.py::measure_catalog_init` uses pyiceberg `SqlCatalog` (`type='sql'`
+ SQLite URI + `file://` warehouse), mirroring `poc/p3_ingest/ingest.py`.
The task spec mentioned a `type='memory'` variant — `InMemoryCatalog` exists
upstream but its registration string in 0.8.1 is unverified. Log to
[`docs/research/ai_hallucinations.md`](../../docs/research/ai_hallucinations.md)
if a different string is required at runtime.

## Promotion target

`src/nucleus/cli/up.py` after PoC #1 promotion. Harness stays here as a
regression test CI can run nightly.
