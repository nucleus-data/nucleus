# ADR-014: Postgres source via dlt wrap (Stage 1 wave) — *+ MySQL co-default (2026-05-14)*

> **Status**: ACCEPTED — 2026-05-13 (founder ratified all 5 Open Questions per recommendations; see `docs/FOUNDER_ACTION_QUEUE.md §0 2026-05-13` ratification record). **Amended 2026-05-14 — MySQL parity added** (see §"MySQL parity (2026-05-14)" below).
> **Date**: 2026-05-13 (Postgres) · **Amended**: 2026-05-14 (MySQL parity) · **Decider**: Solo founder

> **Founder ratification (2026-05-13)** — Open Questions resolved per ADR recommendations:
> 1. **Path D** (wrap `dlt.sources.sql_database`) accepted; Path A retained as documented rollback only.
> 2. **10M-row Stage 1 ceiling** accepted; covers beachhead for 6 months without PyArrow upgrade.
> 3. **libpq SSL params only** (`sslmode=`, `sslrootcert=`); SSH / IAM / Vault deferred to v0.5+ with `NucleusConfigError` fix-hints.
> 4. **`--mode append|replace`** CLI flag (terse, Nucleus-shaped per AGENTS.md §7); rejects `--write-disposition` (dlt vocabulary leak).
> 5. **+1-week effort buffer** accepted; if SQLAlchemy backend needs a JSONB / NUMERIC adapter shim, +1 week absorbs it. Stage 2 ConnectorX pre-commit deferred to evidence.
> **Tags**: connectors, ingestion, dlt, postgres, stage-1, wrap-not-build, error-translation
> **Supersedes (in part)**: portions of `nucleus_architecture_v4.1.md` §5.5.1 (Amendment 13 sized a native Postgres branch on `ctx.copy_from`; this ADR proposes dlt wrap) + `docs/research/dlt.md` §10 (placed dlt at v0.3+; Stage 1 narrows the trigger to one production-grade SQL source).
> **Related**: ADR-001 (no commit service), ADR-002 §6 (dlt deferred to v0.3+ — this ADR re-prioritizes), ADR-003 (PyIceberg `0.8.1 → 0.11.x` — **hard prerequisite**), ADR-006 (NE-codes), ADR-007 (license tier — dlt is Apache-2.0, GREEN), ADR-013 (`ctx.materialize` shape mirrored here for `ctx.copy_from_postgres`), `docs/research/dlt.md` §13, `docs/swap/dlt.md`, `nucleus_architecture_v4.1.md` §5.5 + §6.3 + §6.4, `AGENTS.md` §3 #10/#11 + §11.12 + §11.13, `src/nucleus/ctx/copy_from.py` (the SQLite parallel).

## Context

The founder greenlit a parallel 4-6 month ladder to v1.0 (target: enterprise-ready, impressive). Stage 1 must answer the first complaint a beachhead field-tester (5-20-engineer team) raises after `nucleus init`: *"my data is in Postgres, not SQLite."* `src/nucleus/ctx/copy_from.py` ships SQLite-only today (per its docstring at line 6); Postgres was sized for v0.1 in `nucleus_architecture_v4.1.md` §5.5.1 but never landed. Stage 1's most v1.0-impactful single deliverable is closing this gap.

Two architectural paths exist:

1. **Native Postgres branch on `ctx.copy_from`** — ~150 LOC of SQLAlchemy + PyIceberg, mirroring the SQLite branch verbatim. Zero new runtime deps.
2. **Wrap dlt's `sql_database` verified source** — ~80 LOC of glue, +1 runtime dep (`dlt==1.26.0`, ~30 MB closure including `pyiceberg-core`). Inherits production-grade type mapping, lazy schema reflection, and the foundation for incremental loading (Stage 2) + 100+ connectors (v0.3+).

Per `docs/research/dlt.md` §13 (the companion research note), dlt's [`sql_database`](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database) source on the [Iceberg destination](https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg) is the canonical wrap-not-build choice once we accept the dependency cost. This ADR proposes path 2 and surfaces path 1 as the alternative for founder ratification.

ADR-002 §6 + ADR-003 §"Downstream consumers" already documented dlt as the v0.3+ default and PyIceberg `0.11.x` as its hard prerequisite. This ADR does not contradict that sequencing — it ratifies an *acceleration* of dlt's first wrap (Postgres only) into Stage 1 once ADR-003 lands.

## OSS / Surface Options Considered

| Option | Shape | Verdict |
|---|---|---|
| **A — Native Postgres branch on `ctx.copy_from`** | Add `ingest_postgres_to_iceberg(...)` mirroring `ingest_sqlite_to_iceberg(...)`. Pure SQLAlchemy + PyIceberg. ~150 LOC. | **REJECT for Stage 1** — duplicates work dlt already solves (type fidelity, batched reads, schema reflection); when Stage 2 incremental + Stage 3 merge land, the native branch reaches dlt's LOC anyway and we still have to wrap dlt for v0.3 connector breadth. Defer-as-fallback per Risk #1 below. |
| **B — Sling subprocess** | Per `docs/swap/dlt.md` swap target. ~500-1k LOC. | REJECT — premature swap; `docs/swap/dlt.md` §1 trigger conditions don't fire. Sling stays interface-only per v4.1 §9.3. |
| **C — Singer / Meltano** | Per-tap mixed-license catalogue. | REJECT — license audit gate (some AGPL-3.0); Meltano embeds its own scheduler (Constraint #3). |
| **D — Wrap `dlt.sources.sql_database` for Postgres only** | New `ctx.copy_from_postgres(...)` + `nucleus ingest postgres://...` CLI flag. ~80 LOC glue + `dlt==1.26.0` runtime pin. | **ACCEPT (PROPOSED)** — production-grade SQL→Iceberg path; Apache-2.0 (ADR-007 GREEN); JVM-free (Constraint #1); composability swap doc already in place (`docs/swap/dlt.md`); foundation for Stage 2 incremental + v0.3+ connector breadth without re-architecture. |

## Decision

> **Wrap dlt's `sql_database` verified source for the Postgres → Iceberg path. Pin `dlt==1.26.0` exactly per AGENTS.md §11.13. Land in Stage 1 (after ADR-003 PyIceberg upgrade clears).**

Public surface (mirroring ADR-013's `ctx.materialize` shape):

```python
# src/nucleus/ctx/copy_from_postgres.py — Stage 1 wrap, ≤200 LOC target
# Stability: Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)
def ingest_postgres_to_iceberg(
    conn_str: str,                      # "postgresql://user:pass@host:5432/db?sslmode=require"
    source_table: str,                  # "public.orders"
    *,
    warehouse_dir: str | Path,          # filesystem catalog warehouse, same as SQLite branch
    dest_namespace: str,
    dest_table: str,
    write_disposition: Literal["append", "replace"] = "append",
) -> int:
    """Read all rows from a Postgres table; write to a filesystem Iceberg table.
    Returns row count written.  Mirrors ingest_sqlite_to_iceberg(...) shape.
    """
```

CLI surface:

```bash
nucleus ingest postgresql://user:pass@host:5432/db --table public.orders --as raw.orders
```

Re-export `ingest_postgres_to_iceberg` from `src/nucleus/ctx/__init__.py` alongside the existing SQLite helper. CLI dispatch (`src/nucleus/cli/main.py`) reads the URL scheme and routes; no class hierarchy.

## Scope

**In (Stage 1):**

- Postgres source via SQLAlchemy `postgresql+psycopg://...` URL (uses our pinned `psycopg[binary]==3.2.3`); see [SQLAlchemy postgres dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).
- `dlt.sources.sql_database.sql_table(credentials=conn_str, table=source_table, backend="sqlalchemy", reflection_level="full_with_precision")` — single table per call.
- `dlt.pipeline(destination="filesystem", dataset_name=dest_namespace, pipelines_dir=".nucleus/state/dlt/", restore_from_destination=False)` running with `table_format="iceberg"` per the [Iceberg destination docs](https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg).
- `write_disposition="append"` (default) and `"replace"` (single flag).
- Atomic single-table Iceberg commit (PyIceberg per ADR-001 — no custom commit service).
- Schema auto-inference, including `NUMERIC(p,s)`, `TIMESTAMPTZ`, `JSONB→string`, `BYTEA`.
- TLS via libpq URL params (`?sslmode=require&sslrootcert=...`) per <https://www.postgresql.org/docs/current/libpq-ssl.html>.
- OpenLineage emit on the same code path as the SQLite branch (per `docs/research/openlineage.md` + ADR-009 — bookend hooks at the AMA boundary, no new emitter).
- Error translation per `docs/research/dlt.md` §13.8 — all paths route to existing NE-codes (no new allocations).

**Out (deferred):**

| Capability | Stage |
|---|---|
| Incremental cursor loading ([`dlt.sources.incremental`](https://dlthub.com/docs/general-usage/incremental/cursor)) | Stage 2 |
| Merge / upsert / SCD2 ([`merge` write disposition](https://dlthub.com/docs/general-usage/merge-loading)) | Stage 3 |
| MySQL source (same `sql_database` code path, separate ADR) | Stage 2 |
| Source filters / `included_columns` / column projection | Stage 3 |
| `pyarrow` / `connectorx` backends | Stage 2 / Stage 3+ |
| SSH tunnel, IAM, Vault, OIDC token broker | v0.5+ (alongside ADR-010) |
| Multi-table per CLI call | Stage 2 |
| Postgres `ARRAY` / `geometry` / extension types | v0.5+ (raise `NucleusUnsupportedTypeError` until then) |

## Implementation sketch (informative)

```python
# Pseudocode — final landing in src/nucleus/ctx/copy_from_postgres.py.
# Mirrors src/nucleus/ctx/copy_from.py:_open_catalog() + ingest_sqlite_to_iceberg().
# Docs: https://dlthub.com/docs/general-usage/pipeline
#       https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
#       https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database

def ingest_postgres_to_iceberg(conn_str, source_table, *, warehouse_dir,
                                dest_namespace, dest_table,
                                write_disposition="append"):
    import dlt                                                 # lazy-import per §13
    from dlt.sources.sql_database import sql_table

    # Reuse the existing filesystem catalog opener — atomic commits flow
    # through PyIceberg per ADR-001.
    catalog = _open_catalog(Path(warehouse_dir))               # from copy_from.py

    schema, table = source_table.split(".", 1) if "." in source_table else ("public", source_table)
    resource = sql_table(
        credentials=conn_str,
        table=table,
        schema=schema,
        backend="sqlalchemy",
        reflection_level="full_with_precision",
    )

    pipeline = dlt.pipeline(
        pipeline_name=f"nucleus__pg__{dest_namespace}__{dest_table}",
        destination="filesystem",
        dataset_name=dest_namespace,
        pipelines_dir=str(Path(warehouse_dir) / "_dlt_state"),
        restore_from_destination=False,                        # Stage 1: no state to restore
    )

    try:
        load_info = pipeline.run(
            resource,
            write_disposition=write_disposition,
            table_name=dest_table,
            table_format="iceberg",
        )
    except Exception as exc:                                   # translate per §13.8
        raise _translate_dlt_postgres_exception(exc) from exc

    return _row_count_from_load_info(load_info)
```

`_translate_dlt_postgres_exception` lives next to the existing PoC #1 promoted translator (`src/nucleus/coordination/error_translation.py`) and reuses its two-level `__context__` walk for `PipelineStepFailed` (per `docs/research/dlt.md` §5.4 + §13.8). No new NE-codes; no new error classes.

## Composability

dlt is **Tier 2 (wrapped capability)**. `docs/swap/dlt.md` already enumerates Sling and Singer as swap targets and documents the `SourceEngineProtocol`. This ADR does **not** modify that interface — it implements the default. Stage 1 keeps `ctx.copy_from` (SQLite branch) as the always-live in-house baseline that any future swap must satisfy (`docs/swap/dlt.md` §3).

If dlt itself becomes unviable post-Stage 1 (license pivot, dltHub fold, perf regression >2x — `docs/swap/dlt.md` §1 trigger conditions), the rollback is path A above (~150 LOC native Postgres branch on `ctx.copy_from`). That fallback is documented as Risk #1 and stays *interface-only* during Stage 1 — we do not pre-emptively build it (Anti-Over-Engineering §2: one caller = inline).

## Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **dlt minor-version churn** — 1.26.0 → 1.27.0 already in alpha (PyPI 2026-05-12); SQL-database verified source has had API churn historically. | MED | Schema-inference behavior shift = silent data corruption. | Exact pin per AGENTS.md §11.13; add `tests/upgrade_smoke/test_dlt_upgrade.py` regression-locking the 6 Postgres column types in §13.6; no auto-bump (one-component-per-PR). |
| **Postgres connection auth scope creep** — IAM, Vault, OIDC, SSH tunnel pressure mid-Stage-1. | MED | Stage 1 LOC ceiling breach + scope drift. | Hard freeze: connection-string + libpq SSL only. SSH/IAM/Vault rejected with a `NucleusConfigError` fix-hint pointing at v0.5 ADR-010 work. |
| **Large-table memory** — dlt's normalize step writes per-load Parquet to `pipelines_dir`; 1M-row Postgres table ≈ 100-500 MB temp footprint per `docs/research/dlt.md` §6. | LOW | Out-of-disk on small dev machines. | Row-count ceiling documented (10M Stage 1; §13.9); `recommended_file_size` capability override stays available; PoC #4 boot harness gains a 10M-row smoke test. |
| **Schema drift mid-ingest** — Postgres `ALTER TABLE` between reflection and read raises mid-`pipeline.run()`. | LOW | Partial commit, then failure. | Translate to `NucleusSchemaEvolutionError` (NE1004); idempotent re-run after schema settles. v4.1 §15 contracts NOT in scope for Stage 1. |
| **PyIceberg upgrade slip** — ADR-003 must land first (`dlt[pyiceberg]>=0.9.1` floor per `docs/research/dlt.md` §6/§7). | LOW | Stage 1 blocked entirely. | ADR-003 is ACCEPTED 2026-05-13; trigger condition (PoC #1 17/17 green) already cleared. Sequencing is "land ADR-003, then this." |

## Effort estimate

3-4 weeks at max velocity (founder + AI agents in Loop Mode):

| Phase | Owner | Duration |
|---|---|---|
| This research + ADR | researcher subagent | **1 day** (this PR) |
| Implementation (`copy_from_postgres.py` + CLI dispatch + 12-15 tests) | builder subagent | 1.5-2 weeks |
| Postgres testcontainer fixture + integration suite (6 column-type round-trips + 3 error-translation cases) | swarm-implementer | 3-4 days |
| Beachhead 1M-row benchmark + `tests/upgrade_smoke/test_dlt_upgrade.py` | swarm-implementer | 2-3 days |
| Founder review + verifier pass + amendments | foreground | 2-3 days |

Confidence: **MEDIUM**. Key unknown is whether dlt's SQLAlchemy backend produces clean PyIceberg-acceptable Arrow batches for the JSONB / NUMERIC edge cases without a `table_adapter_callback` per the [configuration page](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database/configuration). NEEDS VERIFICATION at the implementation PR open; if fragile, +1 week for a thin adapter shim.

## Verification plan

`tests/ctx/test_copy_from_postgres.py` (new) — minimum cases, all green on Win + macOS + Linux against a `testcontainers-python` Postgres 15 fixture:

1. **Happy path**: `CREATE TABLE public.orders` with 10 rows of mixed types (BIGINT, TEXT, NUMERIC(10,2), TIMESTAMPTZ, JSONB, BYTEA) → `ingest_postgres_to_iceberg(...)` → `iceberg_table.scan().to_arrow()` returns 10 rows with types matching §13.6 mapping.
2. **`write_disposition="append"` is idempotent in spirit**: two consecutive calls double the row count; snapshot history shows two snapshots.
3. **`write_disposition="replace"`**: second call truncates + replaces; one Iceberg snapshot per call.
4. **Error translation**: 4 cases — bad password (`NE1009`), missing host (`NE1001`), missing table (`NE1008`), unsupported `geometry` column (`NE2004`). All assert `NucleusError.cause` chains to the underlying `psycopg` / `sqlalchemy.exc` exception.
5. **CLI integration**: `nucleus ingest postgresql://... --table public.orders --as raw.orders` exits 0, prints row count, materializes table.
6. **OpenLineage emit**: `tests/coordination/test_lineage.py` extended with a Postgres-source case; START + COMPLETE events written to NDJSON; `_nucleusOutcome` facet carries snapshot ID.
7. **Upgrade smoke**: `tests/upgrade_smoke/test_dlt_upgrade.py` round-trips the 6 column types — must stay 6/6 green on every dlt minor bump per AGENTS.md §11.13.

`scripts/dagster_leak_check.py` MUST stay PASS — no `dlt`, `psycopg`, `sqlalchemy` strings reach user-facing output (`PipelineStepFailed.user_message` etc. are stripped at translation per ADR-006 §Decision).

## Sequencing (binding)

1. ADR-003 (PyIceberg `0.8.1 → 0.11.x`) — **DONE 2026-05-13**.
2. Founder ratifies this ADR.
3. Implementation PR opens; one component per PR per AGENTS.md §11.13. Adds `dlt==1.26.0` runtime dep + Postgres branch + CLI dispatch. **No other dep changes in same PR.**
4. 24-hour cool-down before any subsequent dep upgrade.
5. Stage 2 (incremental loading) opens its own ADR; this one does not pre-commit to incremental shape.

## Rollback

```bash
pip uninstall dlt
git revert <stage-1-pr>
```

User-side data: Iceberg tables remain readable (Tier 0 immortal substrate per `nucleus_architecture_v4.1.md` §4.1); user can re-ingest via path A (native Postgres branch) once that fallback exists. No data migration required — the table format is the contract, dlt is the loader.

If structural rollback (dlt unviable): ADR-014a documents the swap to path A (~150 LOC native Postgres branch on `ctx.copy_from` — pre-sized in `docs/research/dlt.md` §13 Q1).

---

## MySQL parity (2026-05-14)

> **Amendment scope**: Add MySQL as a co-default source alongside Postgres. **No new architectural decision** — this amendment ratifies the deferred row in §Scope "Out (deferred)" table (the `MySQL source (same sql_database code path, separate ADR)` line moves to In-scope and rolls under this ADR rather than spawning a new one).

### Why this is an amendment, not a new ADR

Per ADR-014 §Scope, MySQL was originally deferred to "Stage 2" with a "separate ADR". After implementation, three facts argue for amending rather than fragmenting:

1. **Same code path**. dlt's [`sql_database`](https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database) verified source is multi-dialect; the same `sql_table(credentials=..., table=..., backend="sqlalchemy")` call handles Postgres, MySQL, SQLite, and MSSQL. The MySQL helper is a verbatim mirror of `copy_from_postgres.py` differing only in (a) URL scheme prefix, (b) credential normalisation (`mysql://` → `mysql+pymysql://`), and (c) error translator (pymysql error codes 1045/1049/2003/1054/1146 vs psycopg classnames).
2. **No new runtime dependency**. `pymysql==1.1.1` is already pinned in `pyproject.toml:56` from a prior license sweep (MIT, GREEN tier per ADR-007). `dlt==1.26.0` is unchanged.
3. **Anti-Over-Engineering §2 (`.cursor/rules/nucleus.mdc`)**: "Inline first. Wrap into a dataclass / interface / helper only when a *second real caller* appears." MySQL IS the second real caller of the wrapped `sql_database` source — but the right response is *amendment-level documentation*, not a new policy ADR.

### Public surface

```python
# src/nucleus/ctx/copy_from_mysql.py — ~200 LOC mirror of copy_from_postgres.py
# Stability: Beta @ v0.2 → Stable @ v0.5 → Frozen @ v1.0  (per ADR-005 §2)
def ingest_mysql_to_iceberg(
    conn_str: str,                       # "mysql://user:pass@host:3306/db" or "mysql+pymysql://..."
    source_table: str,                   # "orders" (URL default DB) or "shop.orders" (override DB)
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    write_disposition: Literal["append", "replace"] = "append",
) -> int: ...
```

CLI surface (unchanged — same `nucleus ingest` dispatch by URL scheme):

```bash
nucleus ingest mysql://user:pass@host:3306/db --table orders --as raw.orders
nucleus ingest mysql+pymysql://user:pass@host:3306/db --table shop.orders --as raw.orders --mode replace
```

### Scope (MySQL co-default)

**In:**

- MySQL source via SQLAlchemy `mysql+pymysql://...` URL (PyMySQL driver, pure Python; satisfies Constraint #1 no-JVM).
- Bare `mysql://` alias normalised to `mysql+pymysql://` (SQLAlchemy 2.0 has no default driver for the bare scheme).
- Single-table per call; `db.table` qualifier override; URL-default DB when unqualified.
- `write_disposition="append"` (default) and `"replace"`.
- Atomic single-table Iceberg commit (PyIceberg per ADR-001; unchanged).
- 6 column-type round-trip targets: BIGINT, TEXT, DECIMAL(10,2), DATETIME(6), JSON, BLOB.
- Error translation per `src/nucleus/coordination/error_translation.py:_translate_dlt_mysql_exception()` — all paths route to existing NE-codes (no new allocations).

**Out (same deferral as Postgres path):**

| Capability | Stage |
|---|---|
| Incremental cursor loading | Stage 2 |
| Merge / upsert / SCD2 | Stage 3 |
| MSSQL source (same `sql_database` code path) | Stage 2+ |
| SSH tunnel, IAM, Vault, OIDC token broker | v0.5+ (ADR-010) |
| Multi-table per CLI call | Stage 2 |
| MySQL `GEOMETRY` / `ENUM` / `SET` types | v0.5+ (raise `NucleusUnsupportedTypeError`) |

### Error translation (NE-code map — no new codes)

| Source signal | NE-code | NucleusError subclass |
|---|---|---|
| pymysql code 1045 / "access denied" | NE1009 | `NucleusSourceAuthError` |
| pymysql code 1049 / "unknown database" | NE1001 | `NucleusSourceConnectionError` |
| pymysql code 2003 / "can't connect to" | NE1001 | `NucleusSourceConnectionError` |
| pymysql code 1146 / "table doesn't exist" | NE1008 | `NucleusSourceNotFound` |
| pymysql code 1054 / "unknown column" | NE1004 | `NucleusSchemaEvolutionError` |
| TLS/SSL handshake failure (any source) | NE1010 | `NucleusNetworkError` |
| `sqlalchemy.exc.NoSuchTableError` | NE1008 | `NucleusSourceNotFound` |
| Fallthrough | NE3001 | `NucleusInternalError` |

Same two-level `__context__` walk as the Postgres translator (`docs/research/dlt.md` §5.4 + §13.8). User-facing strings strip `pymysql`, `dlt`, `mysql`, `sqlalchemy`, `PipelineStepFailed` per AGENTS.md §11.7 (validated by `scripts/dagster_leak_check.py`).

### Cross-references

| File | Role |
|---|---|
| `src/nucleus/ctx/copy_from_mysql.py` | New helper (~200 LOC; mirror of `copy_from_postgres.py`) |
| `src/nucleus/ctx/_dispatch.py` | Extended: `mysql` + `mysql+pymysql` schemes added to `_SUPPORTED_SCHEMES` |
| `src/nucleus/coordination/error_translation.py` | New `_translate_dlt_mysql_exception()` function alongside Postgres translator |
| `tests/ctx/test_copy_from_mysql.py` | 15 unit tests (dlt + pymysql mocked) — happy path, scheme validation, 4 error-translation cases, pipeline naming, schema kwarg handling |
| `tests/ctx/test_copy_from_unified.py` | 3 new tests in `TestMySQLDispatch`; existing unsupported-scheme test moved off `mysql://` to `oracle://` |
| `tests/upgrade_smoke/test_dlt_mysql.py` | API-surface lock (always-runnable) + 6 column-type round-trip cases (SKIP-BY-DEFAULT pending MySQL testcontainer) |
| `docs/swap/dlt.md` | Updated: swap doc now describes MySQL coverage alongside Postgres |

### Verification (this amendment)

Same gate as the Postgres landing: 8 governance scripts EXIT 0 + pytest GREEN. Specifically:

- `tests/ctx/test_copy_from_mysql.py` — 15/15 unit tests pass.
- `tests/ctx/test_copy_from_unified.py` — existing tests still pass after `mysql://` → `oracle://` swap; 3 new MySQL dispatch tests pass.
- `tests/upgrade_smoke/test_dlt_mysql.py` — 5 API-surface tests pass; 6 column-type tests skipped per testcontainer deferral.
- `scripts/dagster_leak_check.py` PASS — no `pymysql` / `dlt` / `mysql` / `sqlalchemy` classnames in user-facing strings.
- `scripts/check_pinning.py` PASS — `pymysql==1.1.1` and `dlt==1.26.0` pins unchanged.
- `scripts/check_licenses.py` PASS — `pymysql` already MIT (GREEN) in license lock.
- `scripts/loc_budget.py` GREEN — ~+200 LOC for the helper + ~+150 LOC for the translator function = ~+350 LOC of src/nucleus/ growth, well under the v0.1 phase ceiling.

### Sequencing (amendment)

1. Postgres landing (already DONE 2026-05-13).
2. MySQL amendment lands as a single PR (this work) — one component per PR per AGENTS.md §11.13.
3. 24 h cool-down before the next dependency change (unchanged policy).
4. MSSQL co-default amends this ADR at Stage 2+ if/when telemetry demands it; same wrap-not-build pattern.

### Rollback (MySQL only)

```bash
# Revert just the MySQL amendment; Postgres path stays live.
git revert <mysql-amendment-pr>
```

No new dependency to uninstall — `pymysql==1.1.1` remains in `pyproject.toml` (it pre-dated this amendment). Iceberg tables already materialised remain readable per the original §Rollback section.

## Open questions for founder

1. **Wrap dlt vs extend native `ctx.copy_from`?** This ADR picks dlt (path D); architecture v4.1 §5.5.1 sized the native helper (path A). Path D adds ~30 MB closure but unblocks Stage 2/3 + v0.3 connector breadth. **Recommendation**: D, with A as documented rollback. If founder prefers minimum-deps purity, flip to A and reopen this ADR for v0.3.
2. **Stage 1 row-count ceiling — promise of correctness?** Recommend 10M rows (covers beachhead for 6 months without Stage 2 PyArrow upgrade).
3. **Connection-string auth — which knobs ship?** Recommend libpq SSL params only (`sslmode=`, `sslrootcert=`); reject `?ssh=`, `?iam=` etc. with a `NucleusConfigError` pointing at v0.5+ work. Confirm.
4. **CLI flag naming**: `--write-disposition append|replace` (verbose, dlt-aligned) vs `--mode append|replace` (terse, Nucleus-shaped). Recommend `--mode` for v0.1 — `dlt`-aligned vocabulary leaks into surface area; AGENTS.md §7 keeps user-facing names short.
5. **Effort confidence — MEDIUM not HIGH.** SQLAlchemy backend + JSONB/NUMERIC may need a thin adapter (see Effort §). Founder accepts a +1-week buffer or pre-commits to ConnectorX in Stage 2 if the adapter need materializes.

## Architecture sections touched

`nucleus_architecture_v4.1.md` **§5.5** (Ingestion — amends Amendment 13's "v0.1 native Postgres" framing to "Stage 1 wrapped Postgres"; SQLite branch unchanged) · **§5.5.2** (lifts dlt's first wrap from v0.3+ to Stage 1) · **§6.3** (Coordination — adds the dlt translator to the boundary list) · **§6.4** (Error Translation — confirms no new NE-code allocations needed). Full edit log lands on acceptance via the same pattern as ADR-013 §"Sections to update on acceptance".

## Trigger

Status flips **PROPOSED → ACCEPTED** when (1) founder resolves Open Questions 1-5 above; (2) ADR-003 (PyIceberg upgrade) is in-tree at `==0.11.x` (already ACCEPTED 2026-05-13); (3) `dlt==1.26.0` confirmed current on PyPI at PR-open time per AGENTS.md §11.12 (re-verify; 1.27.0 may have shipped). **Not calendar-gated.**

---

*Pre-implementation artifact. No code lands until this ADR ratifies. Stage 1's most v1.0-impactful single-deliverable per founder's parallel ladder; first DE complaint resolved.*
