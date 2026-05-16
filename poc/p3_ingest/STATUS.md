# PoC #3 — `nucleus ingest` one-liner — Verification Report

**Date**: 2026-05-12 · **Status**: SCAFFOLDED, BLOCKED on PoC #1.
**Spec**: `nucleus_poc_plan.md` §3 · `nucleus_architecture_v4.1.md` §5.5.1.

## §1. File inventory

| File | Lines | Implements | Deps |
|---|---|---|---|
| `__init__.py` | 8 | docstring only | — |
| `ingest.py` | 228 | `ingest_sqlite_to_iceberg(...)` + 4 helpers + `_SQLITE_TYPE_MAP` | `pyiceberg==0.8.1`, `pyarrow==18.1.0`, `nucleus.errors`, stdlib `sqlite3` |
| `demo.py` | 79 | `main()` 5-row demo (SQLite → `raw.orders`, read-back, assert) | `poc.p3_ingest.ingest` + stdlib |
| `test_ingest.py` | 142 | 7 pytest cases | `pyiceberg`, `pyarrow`, `pytest`, `nucleus.errors` |

Total ~457 lines. **No DuckDB or Polars dep** — SQLite stdlib + PyArrow + PyIceberg only.

## §2. Acceptance criteria

- ✓ `ingest_sqlite_to_iceberg(...)` (lines 162-227).
- ✓ `test_ingest.py` has **7 cases** (≥5 required): round-trip, schema-inference, idempotency, missing-source, unsupported-type, no-pyiceberg-leak, two-appends-double-rows.
- ✓ `demo.py main()` at line 33.
- ✓ Error translation (v4.1 §6.4): all PyIceberg exceptions re-raised as `NucleusError` subclasses; test 6 enforces "no `pyiceberg.` classname in user output".
- ✓ One `# NEEDS VERIFICATION` marker (AGENTS.md §11.12) at `_open_catalog` lines 106-108 — `SqlCatalog` URI kwargs vs 0.8.1.

## §3. Blocking items

1. **`nucleus.errors` does not exist yet.** All 4 files import 5 NucleusError subclasses; test 6 calls `.rendered()`. Per AGENTS.md §11.1 phase gate, `/src/nucleus/` is forbidden until PoC #1 passes — PoC #3 is **strictly downstream of PoC #1**.
2. **No Python env installed.** `pip install -e .[dev]` required before `pytest poc/p3_ingest/` runs (Tier 0 Heartbeat per v4.1 §17.2).
3. **PyIceberg 0.11.x upgrade (ADR-003) is queued.** Currently targets 0.8.1; ADR-003 mandates re-validation on 0.11.x.

## §4. Next 3 actions (priority)

1. **Ship PoC #1** — produces `src/nucleus/errors.py` with the 5 `NucleusError` subclasses + `.rendered()` PoC #3 already imports.
2. **Verify the `_open_catalog` `# NEEDS VERIFICATION` marker** against a real PyIceberg 0.8.1 install on Win + macOS + Linux (ADR-001 cross-platform mandate). Log drift in `docs/internal/research/ai_hallucinations.md`.
3. **After ADR-003 lands**: re-run all 7 tests on 0.11.x in the upgrade smoke suite, then graduate to `src/nucleus/ctx/copy_from.py` (~200 LOC, v4.1 §5.5.1) and expand to Postgres / MySQL / CSV / Parquet / JSON per `nucleus_poc_plan.md` §3.

*Verification report only — no PoC files modified.*
