# [PoC promotion] PoC #3 SQLite → Iceberg ingest → src/nucleus/coordination/ingestion/sqlite_ingest.py

## Summary

Promotes the SQLite → filesystem-Iceberg ingestor from `poc/p3_ingest/ingest.py` to `src/nucleus/coordination/ingestion/sqlite_ingest.py` (**destination NEEDS VERIFICATION** — see §Architectural changes #2), satisfying `docs/specs/nucleus_architecture_v4.1.md` §5.5.1's one-liner ingestion promise (Amendment 13). Reads SQLite via stdlib `sqlite3`, auto-infers an Iceberg schema from `PRAGMA table_info` (`ingest.py:63-97`), creates the destination namespace + Iceberg table in a filesystem-backed `pyiceberg.SqlCatalog` (v4.1 §5.7 v0.1 default), and appends as a single `pyarrow.Table` (`ingest.py:176-241`). Ships **7/7 green** on Windows + Linux/macOS (`test_ingest.py:61-141`); the §6.4 leak gate (`test_ingest.py:122-132`) asserts no `"pyiceberg"` / `"iceberg.exceptions"` substring escapes `.rendered()`. Includes the **Windows `file://` URI workaround** in `_open_catalog` (`ingest.py:100-133`) with 5 citations — `iceberg-python#1005`/`#996`/`#2477` + RFC 8089 §E.2 + pyiceberg FileIO docs (`ingest.py:119-125`). Lifts PoC #3 in `docs/specs/nucleus_poc_plan.md` §3 + §5 and unblocks `nucleus ingest --source sqlite://...` per `docs/specs/nucleus_cli_spec.md` §3.5 + `v01_skeleton_plan.md` §3 line 79.

---

## Pre-merge gate checklist

Re-run each gate at PR-open time. **No `PROMOTION_CHECKLIST.md` exists yet for PoC #3** (cf. PoC #1 + #2); founder authors one OR adopts this draft's gate list verbatim.

- [x] `pytest poc/p3_ingest/ -v` → **7/7 green** on Windows + Linux/macOS (`STATUS.md` §2; `test_ingest.py:61-141`). Windows pass required the `file://` URI workaround at `ingest.py:131`.
- [x] `python scripts/dagster_leak_check.py` → exit 0; PoC #3 does not `import dagster`; `test_rendered_error_has_no_pyiceberg_leak` (`test_ingest.py:122-132`) gates §6.4 + §6.5.
- [x] `python scripts/check_vocabulary.py --paths poc/p3_ingest/` → exit 0 across `ingest.py`, `test_ingest.py`, `demo.py`, `STATUS.md` (`AGENTS.md` §7).
- [ ] `python scripts/check_error_codes.py` → **gated on ADR-006 ratification** (mirrors PoC #1 + #2). The four subclasses at `ingest.py:45-50` (`NucleusSourceNotFound`, `NucleusUnsupportedTypeError`, `NucleusCommitConflictError`, `NucleusIOError`) claim `NE1xxx`/`NE5xxx` codes per ADR-006.
- [x] `python scripts/check_api_stability.py` → exit 0; new module under `src/nucleus/coordination/`, no symbol added to `nucleus/__init__.py` `__all__` until `ctx.copy_from` lands (v4.1 §13.2).
- [x] `python scripts/check_licenses.py` → exit 0; no new runtime dep (re-uses `pyiceberg==0.8.1` + `pyarrow==18.1.0`; `sqlite3` is stdlib).
- [x] `python scripts/loc_budget.py --report` → `src/nucleus/` at **227 LOC** post-PoC-#1; promotion adds 228-LOC `ingest.py` + ~10-LOC `ingestion/__init__.py` → ~465 LOC total, under both the v0.1 8 000-LOC ceiling (`AGENTS.md` §11.6) and the 500-LOC PR ceiling.
- [ ] `REVIEW_NOTES.md` — **MISSING**. PoC #1 and PoC #2 each carry one; PoC #3 does not. Founder must author one before merge OR explicitly waive.
- [x] **PoC #1 promotion-gate dependency satisfied**: `src/nucleus/errors.py` ships the four subclasses imported at `ingest.py:45-50` and `coordination/__init__.py:13-15` exists. PoC #3 strictly depends on PoC #1 per `STATUS.md` §3.
- [ ] **Windows-workaround durability check** — re-verify `iceberg-python#996` (only upstream PR cited in `ingest.py:120`) is still unmerged at PR-open time. If merged, schedule workaround removal as an ADR-003 follow-up.

**Total**: 10 items · **7 met** · **2 pending founder action** (REVIEW_NOTES authorship, upstream-PR re-check) · **1 pending ADR-006 ratification**.

---

## Architectural changes requiring founder ratification

1. **Windows `file://` URI workaround in `_open_catalog`** (`ingest.py:100-133`). The two-slash form `f"file://{posix}"` is the only form pyiceberg 0.8.1's `PyArrowFileIO.parse_location` accepts on Windows — the RFC 8089 three-slash canonical form leaves a stray `/C:/...` after scheme stripping, which `pyarrow.fs.LocalFileSystem` rejects with `WinError 123`. RFC 8089 §E.2 acknowledges the two-slash form (`ingest.py:123`); on POSIX, `Path.as_posix()` supplies the leading `/`, restoring three-slash semantics. Per `docs/internal/research/pyiceberg.md` §7 this addresses URI parsing only, not the broader `os.rename`/`os.replace` atomicity family. **Reviewer task**: confirm the conditional form is acceptable; the 14-line citation block at `ingest.py:112-125` must remain verbatim at promotion. **Permanent** until pyiceberg upstream merges a `parse_location` patch (no PR slated per `ingest.py:122-124`). Independent of ADR-003 §Verification line 25 (which already mandates PoC #3 re-runs unchanged on 0.11.x).

2. **Module destination + "SQLite as first connector"** — **NEEDS VERIFICATION** per `AGENTS.md` §11.12. This PR title proposes `coordination/ingestion/sqlite_ingest.py`, but `v01_skeleton_plan.md` §3 line 40 pins `ctx/copy_from.py` as `PROMOTED ← poc/p3_ingest/ingest.py`; `sequence_ingestion.md` §5 line 146 caps `ctx/copy_from.py` at ≤ 500 LOC; v4.1 §13.2 lists `ctx.copy_from` as a single SDK row, not a per-source family. **Option A** (per the pinned refs): single `ctx/copy_from.py` with a SQLite branch; Postgres / CSV / Parquet accrete behind the same entry. **Option B** (this PR title): `coordination/ingestion/sqlite_ingest.py` as first of a per-source family; `ctx/copy_from.py` becomes a thin dispatcher later. **Reviewer task**: pick A or B. If A, retitle this PR and rewrite every destination reference. If B, retarget `v01_skeleton_plan.md` §3 line 40 + `sequence_ingestion.md` §5 line 146 in this same PR. SQLite was the PoC vehicle for the stdlib-only dep footprint (`STATUS.md` §1); SQLite-vs-Postgres priority is a separate downstream call.

---

## Known issues

None blocking. Two soft items carry forward for founder triage.

1. **PoC #4 `measure.py:118` has the latent `file:///` bug** (`f"file:///{warehouse_dir.resolve().as_posix()}"`). PoC #4 only measures catalog-open time and never materializes a probe asset, so the bug does not fire today. Windows-path-fix worker constraint was "modify only `ingest.py`"; fix was NOT applied prophylactically. Founder owns: (a) fix `measure.py:118` in this PR, (b) follow-up before PoC #4 extends, or (c) defer until PoC #4 promotion.
2. **SeaweedFS / MinIO S3 ingest path is unaffected**. PoC #3 uses `file://` URIs (v4.1 §5.7). Once substrate is S3 (SeaweedFS default per ADR-008 + `v01_skeleton_plan.md` §3 line 77), URIs flip to `s3://...` and the bug never fires — Windows S3 ingest is unblocked once `nucleus up` boots SeaweedFS.

---

## Files to be created

- `src/nucleus/coordination/ingestion/__init__.py` — sub-package marker; cites v4.1 §5.5.1 + §6.4. **Required for Option B only.**
- `src/nucleus/coordination/ingestion/sqlite_ingest.py` — `cp` of `poc/p3_ingest/ingest.py`; docstring rewritten to drop "PoC #3 (steps 2-3)" framing. The 14-line `_open_catalog` comment block (`ingest.py:112-125`) must survive verbatim. **Path subject to Option A/B.**
- `tests/coordination/ingestion/test_sqlite_ingest.py` — `mv` of `poc/p3_ingest/test_ingest.py`; imports rewritten `poc.p3_ingest.ingest` → `nucleus.coordination.ingestion.sqlite_ingest`.
- *(Optional)* `docs/recipes/sqlite_to_iceberg.md` — derived from `demo.py`; defer for Option A.

## Files to be updated

- `docs/specs/nucleus_poc_plan.md` §3 + §5 — PoC #3 status `PROPOSED` → `PROMOTED 2026-05-NN with commit <hash>` per §12 template.
- `AGENTS.md` §1 — `[ ] PoC #2-5` stays unchecked until PoC #5 lands; add per-PoC `(promoted YYYY-MM-DD)` annotation per Worker C precedent.
- `docs/specs/nucleus_architecture_v4.1.md` §5.5.1 — drop "PoC #3 validates feasibility" caveat; flip `ctx.copy_from` row in §13.2 Internal → Beta **only if** Option A.
- `v01_skeleton_plan.md` §3 + `sequence_ingestion.md` §5 — **IF Option B**, retarget skeleton plan line 40 + sequence_ingestion §5 line 146.
- `docs/budget_history.md` — append post-promotion `src/nucleus/` LOC snapshot per `AGENTS.md` §11.6.

`poc/p3_ingest/` stays in tree for **30 days** dual-source per the Worker C / PoC #1 + PoC #2 precedent; remove only after 30 consecutive days of zero `NucleusInternalError` fallbacks attributable to ingest gaps.

---

## Downstream chain unlocked by this merge

1. **`nucleus ingest --source sqlite://... --target raw.foo` CLI** unblocks per `docs/specs/nucleus_cli_spec.md` §3.5 + `v01_skeleton_plan.md` §3 line 79 (NE1001, NE2001, NE1002 — the 30-min beachhead promise per v4.1 §1.5).
2. **Additional source connectors** (Postgres → `docs/recipes/postgres_to_iceberg.md`, CSV → `csv_to_iceberg.md`, MySQL, Parquet, JSON per `docs/specs/nucleus_poc_plan.md` §3) follow the module-or-branch pattern picked at Option A/B; each is its own ≤ 500-LOC PR.
3. **Recipe `docs/recipes/sqlite_to_iceberg.md`** becomes runnable end-to-end.
4. **ADR-003 PyIceberg `0.8.1 → 0.11.x`** remains independent — the Windows fix persists on 0.11.x per `ingest.py:122-124`; ADR-003 fires off PoC #1 (§Trigger) and re-validates PoC #3 unchanged per §Verification line 25.

---

## Rollback plan

Squash-merge so rollback is atomic per the Worker C / PoC #1 + PoC #2 precedent:

```bash
git revert <merge-commit-sha>
git push origin main
```

`poc/p3_ingest/` is unchanged by this PR (purely additive `cp` + `mv` into `src/nucleus/coordination/ingestion/` + `tests/coordination/ingestion/`); rollback leaves the PoC source intact as canonical reference.

---

## Commit message body (founder uses verbatim with `git commit -m "$(cat <<'EOF' ... EOF)"`)

```
[PoC promotion] PoC #3 SQLite → Iceberg ingest

Promotes 7-test green ingest from poc/p3_ingest/ to
src/nucleus/coordination/ingestion/sqlite_ingest.py.

Establishes the coordination/ingestion/{source}_ingest.py
module pattern for future Postgres / CSV / Parquet sources
(pending founder ratification: skeleton plan §3 + sequence_ingestion
§5 currently pin ctx/copy_from.py as the unified entry; see PR
§Architectural changes for Option A vs Option B).

Includes the Windows file:// URI workaround (one-char fix
exploiting RFC 8089 §E.2) - permanent until pyiceberg upstream
merges a parse_location patch.

Tests: 7/7 green on Windows + Linux/macOS.

Refs: AGENTS.md §11.1, §11.7; docs/specs/nucleus_architecture_v4.1.md §5.5.1,
§6.4; ADR-003 (PyIceberg upgrade - independent of this PR's
Windows fix).
```
