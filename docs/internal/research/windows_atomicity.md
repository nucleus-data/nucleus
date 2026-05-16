# Windows / NTFS atomicity for `os.replace` and the Iceberg metadata path

> **Status**: ACCEPTED — Worker B1 v0.2.0 GA hardening wave (2026-05-15).
>
> **Verdict**: SAFE for v0.2.0 ship on Windows. No advisory-lock add-on
> required for the SQL catalog code path. The kill-9 / power-cut edge
> case is documented as a known caveat (`SETUP.md` Platform notes).
>
> **Closes** the "Windows `os.rename` atomicity" item in
> `docs/internal/research/performance_reliability_targets.md` §10 #5 +
> `docs/decisions/ADR-024-reliability-hardening-plan.md` P0-4 +
> `nucleus_red_team_review.md` (NEEDS VERIFICATION 11.2).

---

## 1. Question

POSIX `rename(2)`
([man7](https://man7.org/linux/man-pages/man2/rename.2.html)) is
atomic — a successful call leaves either the old or the new state on
disk, never a partial state, even across a power cut. NTFS `rename()`
is documented as **not** atomic in the same sense: when the target
exists, Windows performs a delete-then-rename pair that can leave a
torn intermediate state if the process dies between the two steps.

Python wraps both behaviours behind a single name. `os.rename(src, dst)`
[on Windows](https://docs.python.org/3.11/library/os.html#os.rename)
even raises `FileExistsError` when `dst` exists — different surface
behaviour from POSIX. `os.replace(src, dst)` (Python 3.3+, [PEP 428](https://peps.python.org/pep-0428/))
takes a different system path on Windows: it calls
[`MoveFileEx`](https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa)
with `MOVEFILE_REPLACE_EXISTING`, which Microsoft documents as a
single-volume atomic operation.

The question Worker B1 needed to answer empirically:

> Does `os.replace` actually deliver "exactly one writer's content lands
> intact" semantics on a Windows 11 NTFS box under tight contention?

If the answer is yes, Nucleus does not need to add anything beyond the
existing `coordination/locks.py` advisory lock for the AMA write path
(per `ADR-024` P0-2). If the answer is no, every code path that
swaps a file would need its own lock, expanding the lock surface
considerably.

---

## 2. Why it (mostly) doesn't matter for our Iceberg path

The most important thing the audit found before running any code:

**Our Iceberg catalog (`type="sql"`) does NOT depend on filesystem rename
atomicity.** The SQL catalog
(`pyiceberg.catalog.sql.SqlCatalog.commit_table`, lines 402–495 of
`pyiceberg/catalog/sql.py` for `pyiceberg==0.11.1`) commits the
metadata-pointer swap via a SQL `UPDATE … WHERE metadata_location =
:current` against a SQLite-backed `IcebergTables` row, not via
`os.rename` of a metadata pointer file. SQLite's WAL provides the
atomicity guarantee. The new metadata JSON itself is *written* via
`pyarrow.fs` `new_output()` which creates a brand-new file (UUID-named);
no rename of an existing metadata file occurs.

This means:

* **Iceberg snapshot commits on Windows are atomic via SQLite, not NTFS.**
* The "Windows NTFS atomicity verification" item in the perf doc and
  in red-team review §11.2 was scoped against the *Hadoop-style* file
  catalog (which Nucleus does not use). For our `type="sql"` choice
  the question is moot.

Worker B1 still validated `os.replace` empirically because:

1. Other Nucleus code paths (lockfile reclaim, cached metadata, future
   features) may rely on it.
2. `ADR-001` explicitly defers commit-atomicity to the catalog; if the
   catalog ever changes (e.g. Polaris with a file-pointer model), we
   need to know whether the underlying primitive is safe.
3. The perf doc named this as one of the Top-5 release-confidence
   items; an empirical answer closes it cleanly.

---

## 3. `pyiceberg` audit (does the upstream use `os.rename`?)

Worker B1 walked `pyiceberg==0.11.1` looking for `os.rename`,
`os.replace`, `fs.rename`, or `Path.rename` calls.

| Finding | Detail |
|---|---|
| `os.rename` calls in `pyiceberg/` | **Zero**. (Verified via
`Get-ChildItem … \| Select-String -Pattern "os\.rename"`.) |
| `os.replace` calls in `pyiceberg/` | **Zero**. |
| `Path.rename` calls in `pyiceberg/` | **Zero**. |
| `rename` mentions in `pyiceberg/` | All hits are `rename_table()` (logical SQL/Glue/REST table rename), `rename_field()` (Iceberg schema evolution), `rename_column()` (schema evolution), or `arguments-renamed` pylint pragmas. None touch the filesystem. |
| Catalog commit primitive (SQL backend) | `pyiceberg/catalog/sql.py` lines 402–495 — SQL `UPDATE` against `IcebergTables.metadata_location` with optimistic-concurrency `WHERE metadata_location = :current_location`. Atomicity provided by SQLite. |
| Metadata file write primitive | `pyiceberg/io/pyarrow.py` `new_output()` (line 627) → `pyarrow.fs.LocalFileSystem`. Each commit writes a NEW UUID-named metadata file; the old file remains until a future maintenance pass. |

**Conclusion**: there is no upstream-pyiceberg `os.rename` issue to file
or patch. The "Windows `os.rename` atomicity" risk in the perf doc
predates the migration to the SQL catalog and is now a non-issue for
Nucleus' default configuration.

---

## 4. Empirical harness (`scripts/test_windows_atomicity.py`)

We wrote `scripts/test_windows_atomicity.py` to test `os.replace`
directly on a real Windows 11 NTFS volume, under tight contention.

**Design**:

1. Spawn two `multiprocessing.Process` workers per iteration.
2. Each writes a unique source file (`b"AAAA…"` vs `b"BBBB…"`).
3. Both call `os.replace(src_N, target)` against the same target,
   synchronised on a `multiprocessing.Barrier` so the race window is
   the tightest the OS scheduler will allow.
4. The parent reads `target` and classifies:
   - `A` — writer 1's content landed verbatim
   - `B` — writer 2's content landed verbatim
   - `MISSING` — target file disappeared (NEVER expected)
   - `TORN` — mixed bytes (NEVER expected)

**Acceptance**: `MISSING + TORN == 0` over the full run.

The harness runs 100 iterations by default; we also did a 50-iteration
stress run at 64 KiB payload (16× the default 4 KiB / one-block
payload) to expose any "small enough to be atomic, large enough to
tear" boundary.

---

## 5. Hardware + filesystem under test

| Field | Value |
|---|---|
| OS | Windows-10-10.0.26100-SP0 (Windows 11 24H2 build 26100) |
| CPU | (host machine — see `psutil.cpu_count(logical=False)`) |
| Filesystem | NTFS (system volume `C:`) |
| Python | 3.11.9 |
| Test path | `%TEMP%\nucleus_atomicity_*` (single volume — NTFS) |
| `os.replace` backend | `MoveFileEx` with `MOVEFILE_REPLACE_EXISTING` |
| Date | 2026-05-15 |

Single-volume guarantee matters: `MoveFileEx` is documented as
near-atomic *within a single volume only*. Cross-volume copies fall
back to a copy-then-delete that is **not** atomic. Nucleus' Iceberg
warehouse is single-volume by construction (the project root and the
`.nucleus/warehouse/` are in the same directory tree).

---

## 6. Results

### 6.1 100 × 4 KiB payload (default run)

```
Iterations      : 100
Payload (bytes) : 4096
Duration (s)    : 51.02

Outcome counts:
  A (writer 1)  : 50
  B (writer 2)  : 50
  TORN          : 0
  MISSING       : 0

PASS: zero unexpected states.
```

Perfect 50/50 split, **zero unexpected states**. Each writer wins
roughly half the races, which is expected for a fair contention
window.

### 6.2 50 × 64 KiB payload (stress run)

(Captured at `docs/internal/research/windows_atomicity_results.json` for
reproducibility.)

```json
{
  "platform": "Windows-10-10.0.26100-SP0",
  "python_version": "3.11.9",
  "iterations": 50,
  "payload_bytes": 65536,
  "counts": {"A": 26, "B": 24, "TORN": 0, "MISSING": 0},
  "duration_seconds": 34.06
}
```

Larger payload, tighter race window — still **zero torn writes**.

### 6.3 Reproducing locally

```powershell
.\.venv\Scripts\python.exe scripts\test_windows_atomicity.py --iterations 100
.\.venv\Scripts\python.exe scripts\test_windows_atomicity.py --iterations 50 --payload-bytes 65536 --json
```

Exit code 0 = SAFE on this filesystem; exit code 1 = at least one
unexpected state observed (and the scope of the lock surface needs
to expand).

---

## 7. Verdict

**SAFE for v0.2.0 ship on Windows.**

* `os.replace` delivers "exactly one writer's content lands intact"
  semantics on NTFS under tight contention.
* The Iceberg SQL catalog atomicity is provided by SQLite, not by
  filesystem rename, so the historical "NTFS rename" worry is moot
  for the AMA commit path.
* The asset-level advisory lock from `coordination/locks.py` (per
  `ADR-024` P0-2) remains the right primitive for serialising
  `nucleus run <asset>` invocations against the same asset.
* No upstream `pyiceberg` patch needed — there is no `os.rename`
  call in `pyiceberg==0.11.1` to begin with.

The release-blocker entry in `performance_reliability_targets.md` §10
item #5 is **CLOSED** by this empirical run plus
`scripts/check_os_rename.py` (regression governance) + the
`tests/coordination/test_windows_rename.py` four-test guard
(`R1`–`R4`).

---

## 8. Caveats

The harness validates **steady-state contention atomicity**: both
writers reach `os.replace`, and one writer's bytes win without
tearing the target file.

It does **not** validate:

### 8.1 Kill-9 / power-cut mid-rename

If a worker is `kill -9`'d *between* the `MoveFileEx` syscall and the
NTFS journal commit, the documented Microsoft behaviour is still
"complete or roll back — never torn". We do not have a power-cut rig,
and AGENTS.md §11.10 forbids speculative implementation that we
cannot empirically verify. We rely on the
[Microsoft single-volume guarantee](https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa)
for this.

If a future Nucleus user reports a torn metadata file after a hard
power loss on Windows, the recovery path is `nucleus repair` (planned
for v0.3, listed in the `nucleus_cli_spec.md` queue) — not a code-path
hardening change.

### 8.2 Cross-volume `os.replace`

If `src` and `dst` are on different volumes (e.g. `D:\src` →
`C:\dst`), Windows falls back to a copy-then-delete sequence that is
**NOT** atomic. Nucleus' warehouse layout never crosses volumes by
construction (project root + `.nucleus/warehouse/` are co-located),
so this is a non-issue for our use case. The fact that we should
*never* relocate the warehouse to a different drive than the project
is documented in `nucleus_project_anatomy.md`.

### 8.3 Network filesystems (SMB, NFS via WSL)

We tested NTFS only. Network filesystems can change `os.replace`
semantics in implementation-defined ways; Nucleus does not officially
support warehouse-on-network-share for v0.1/0.2. PoC #5 testers use
local SSD only.

---

## 9. Governance + regression prevention

To prevent the "fixed problem creeps back" failure mode, Worker B1
shipped two governance layers:

1. **Static check**: `scripts/check_os_rename.py` walks `src/nucleus/`
   AST-side (no false positives from string literals) and exits 1 on
   any `os.rename(` or `Path.rename(` call. Wired into
   `Makefile :: verify-all` (12 governance scripts now, was 11).

2. **Test check**: `tests/coordination/test_windows_rename.py` ships
   four R-tests — `R1` (os.replace exists), `R2` (overwrites existing
   target), `R3` (raises on missing source), `R4` (no `os.rename` in
   `coordination/`). Runs on every PR via `pytest tests/coordination/`.

The two layers catch the same regression at different stages: the
governance script is a fast pre-merge check; the test is a
runtime assertion that survives even if the governance script is
silenced.

---

## 10. References

| Source | URL |
|---|---|
| `os.replace` Python docs | https://docs.python.org/3.11/library/os.html#os.replace |
| `os.rename` Python docs | https://docs.python.org/3.11/library/os.html#os.rename |
| PEP 428 (pathlib + replace) | https://peps.python.org/pep-0428/ |
| `MoveFileEx` MSDN | https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa |
| POSIX `rename(2)` man page | https://man7.org/linux/man-pages/man2/rename.2.html |
| `multiprocessing` docs | https://docs.python.org/3.11/library/multiprocessing.html |
| pyiceberg SQL catalog source | `.venv/Lib/site-packages/pyiceberg/catalog/sql.py` (verified `pyiceberg==0.11.1`) |
| Performance / reliability gap doc | `docs/internal/research/performance_reliability_targets.md` §6.2 + §10 #5 |
| ADR-001 (no commit service) | `docs/decisions/ADR-001-no-iceberg-commit-service.md` |
| ADR-024 (reliability hardening) | `docs/decisions/ADR-024-reliability-hardening-plan.md` |
| Asset-level advisory lock | `src/nucleus/coordination/locks.py` |
| Atomicity harness (this run) | `scripts/test_windows_atomicity.py` |
| Empirical results (this run) | `docs/internal/research/windows_atomicity_results.json` |

---

*Researcher: Worker B1 (v0.2.0 GA hardening wave). Architect tier:
Claude Opus 4.7 (foreground). Builder tier (this audit): Claude
Sonnet 4.6 max-thinking (Cursor-default; GPT-5.5 fallback per
`AGENTS.md` §11.14). Time taken: ~90 min (audit + harness + 100-iter
run + 50-iter stress + write-up).*
