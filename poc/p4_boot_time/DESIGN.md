# PoC #4 — `nucleus up` <10s Cold Boot

> Validates: MinIO + filesystem catalog + Dagster in-process boot in <10s on
> developer hardware (per `docs/specs/nucleus_poc_plan.md` §4 + `docs/specs/nucleus_architecture_v4.1.md`
> §5.7 / §6.3).

## What "boot" means

A `nucleus up` invocation must produce a working state where:

1. Dagster `Definitions` is loaded and the asset graph is queryable.
2. Filesystem-backed pyiceberg catalog is initialized and read/writable.
3. MinIO is reachable on `localhost:9000` (or skipped if user already has an
   S3-compatible target wired in).
4. A trivial asset can materialize end-to-end (deferred to a follow-up PoC;
   not in this harness's boot budget).

## Phases measured (must total <10s cold)

| Phase | Target (cold) | Target (warm) | Critical path? |
|---|---|---|---|
| Python imports (`dagster`, `pyiceberg`, `polars`, `duckdb`) | <3.0s | <0.5s | YES |
| MinIO container start (`docker compose up -d minio`) | <4.0s | n/a (running) | YES if not running |
| MinIO healthcheck (`/minio/health/live` returns 200) | <0.5s | <0.1s | YES |
| pyiceberg `load_catalog(type='sql', ...)` (filesystem) | <0.5s | <0.1s | YES |
| Dagster `Definitions(assets=[...])` construction | <1.5s | <0.5s | YES |
| First asset materialization | (not in budget) | (not in budget) | NO — separate PoC |

## Acceptance criteria (mirror `docs/specs/nucleus_poc_plan.md` §4)

- [ ] Cold boot (fresh git clone, fresh docker): <10s
- [ ] Warm boot (subsequent invocation): <3s
- [ ] Idle RAM (post-boot, no queries): <500MB
- [ ] All components reachable (MinIO health, catalog read/write, Dagster
      `Definitions` constructed without exceptions)

**Out of scope**: actual `nucleus up` CLI (doesn't exist yet — promotes
post-PoC-#1 per `AGENTS.md` §11.1); Workbench UI boot (v0.2); first query
latency (separate PoC); multi-user contention (v0.5+).

## Fallback plan + hardware baseline

Per `docs/specs/nucleus_poc_plan.md` §4 + §13: >10s but <15s → optimize startup order,
lazy-init non-critical components. >15s → investigate Dagster startup
overhead; may need to lazy-init Dagster on first asset run rather than at
`up` time. Target hardware: M1 MacBook Pro 16GB. Acceptable degradation:
+20% on Windows-with-WSL2; +50% on Windows-native (filesystem `os.replace`
overhead, antivirus interference).

## Risks

1. **Dagster import cost** — known to be 2-3s; risk that v0.1 transitive deps
   push us over the 3s phase budget. Lazy-import wrapper already planned in
   `coordination/` (per `docs/internal/research/dagster.md` §7).
2. **Docker cold-start variance** — first MinIO start can be 5-15s depending on
   disk + image cache. We measure post-first-start; uncached `docker pull` is
   out of scope.
3. **pyiceberg + filesystem warm-cache** — second `load_catalog` hits OS page
   cache. Measure cold via `sync; echo 3 > /proc/sys/vm/drop_caches` on Linux
   only; macOS/Windows accept warm-cache reading.
4. **Windows `os.replace` semantics** — per `docs/internal/research/pyiceberg.md` §7,
   filesystem-catalog atomic-pointer-swap differs on Windows. Boot itself
   doesn't exercise this; only first commit does.

## Promotion target

When this PoC passes the harness folds into `src/nucleus/cli/up.py`
(post-PoC-#1 promotion per `AGENTS.md` §11.1). The harness stays in
`poc/p4_boot_time/` as a regression test that CI can run nightly.
