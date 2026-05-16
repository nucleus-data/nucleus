# AI Hallucinations Log

> Append-only log of AI-fabricated APIs caught during development.
> Per `AGENTS.md §11.12`. Add a new entry on every catch.

## Template

```markdown
## YYYY-MM-DD: library.method_or_class

AI suggested: `<fabricated API>`
Reality: `<actual API or non-existent>`
Where caught: <PR # / file / commit>
Detection: <how>
Fix: <what we did>
```

---

## 2026-05-13: openlineage-dagster (entire package)

AI suggested: install + use `openlineage-dagster` (or `dagster-openlineage`) as the bridge between Dagster materializations and OpenLineage event emission.
Reality: **package is DEAD at our pin.** PyPI `openlineage-dagster` caps at `dagster<=1.6.9`; we run `dagster==1.9.5`. The integration was **removed from the OpenLineage main repository in October 2025**. Any AI suggestion to `pip install openlineage-dagster` will either fail to install or downgrade Dagster.
Where caught: `docs/internal/research/openlineage.md` §9 (Worker J research doc, 2026-05-13).
Detection: PyPI version constraints checked against `pyproject.toml` pin; OpenLineage main-repo GitHub history reviewed.
Fix: Nucleus emits OpenLineage events **directly from the Asset Materialization Adapter** (already specified in `docs/specs/nucleus_architecture_v4.1.md` §6.2 step 4). No bridge package. Use `openlineage-python==1.47.1` + `event_v2` module + `FileTransport` (v0.1) / `HttpTransport` to Marquez (v0.3+). When you see AI propose `openlineage-dagster`, REJECT — cite this entry.

---

## 2026-05-13: dagster.materialize() exception-chain shape (1.9.5)

AI suggested: PoC #1 baseline assumed `dagster.materialize()` raises `DagsterExecutionStepExecutionError` as the *outer* captured exception, with the user's library exception (e.g. `duckdb.BinderException`, `polars.SchemaError`, `ConnectionError`) reachable via `__cause__`. The original `_dagster_step_handler` was built around `inner = _unwrap_cause(exc)` matching `ConnectionError` / `(TypeError, ValueError)` after Dagster wrapping.
Reality: in dagster==1.9.5, `materialize()` re-raises the **user's original exception** (e.g. the bare `duckdb.BinderException`) and Python's `do_raise` sets its `__context__` to the internal `DagsterExecutionStepExecutionError`. The DagsterX in turn carries `__cause__ = <user exc>` and `__suppress_context__ = True`, creating a two-node synthetic cycle. The captured top is therefore the library exception itself, not the Dagster wrapper.
Where caught: `poc/p1_error_translation/translator.py` (PoC #1 first green run, 2026-05-13). 17/22 tests failed before the fix.
Detection: ad-hoc diagnostic script walking `__cause__`/`__context__`/`__suppress_context__` at runtime against `dagster==1.9.5` (`Python 3.11.9`, Windows). The walk for a `ConnectionError("host unreachable")` produced: `[0] ConnectionError context=DagsterExecutionStepExecutionError suppress=False`, `[1] DagsterExecutionStepExecutionError cause=ConnectionError context=None suppress=True`, `[2] CYCLE`.
Fix: rewrote `translate()` to (a) iterate candidates outer→inner, (b) prefer any specific (non-`DagsterExecutionStepExecutionError`) handler, passing it the *matched candidate* directly and overriding `__cause__` to the outer captured exception afterwards, and (c) only fall back to `_dagster_step_handler` when no specific match exists. Specific handlers now use `str(exc)` directly (the exc IS the matched candidate) instead of `str(_unwrap_cause(exc))`, which previously walked the synthetic cycle and returned the wrong message. Added direct registry entries for `ConnectionError → NucleusSourceConnectionError` and `ValueError → NucleusSchemaError|NucleusInternalError` (schema-msg gated) so the baseline cases route without depending on the Dagster fallback.
Carry-forward: Worker building the production Error Translation Layer in `src/nucleus/coordination/` MUST keep this two-pass shape — never trust that Dagster wraps the user exception as the outermost captured. Verify per-version on dagster minor upgrades (Constraint #11 §11.13).

---

## 2026-05-13: MinIO RELEASE.2025-10-15T17-29-55Z (fabricated tag)

AI suggested: `quay.io/minio/minio:RELEASE.2025-10-15T17-29-55Z` as the "terminal OSS release" in `docs/internal/research/minio.md` and propagated to `docker-compose.minio.yml`.

Reality: tag does not exist on quay.io or the Docker Hub mirror. Both `latest` and `latest-cicd` resolve to `RELEASE.2025-09-07T16-13-09Z` (sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e). Either an AI fabrication during research drafting or a reference to an unreleased version.

Detection: Worker B (ADR-008 storage smoke test) attempted `docker pull` and got "manifest unknown"; cross-checked quay.io tag list + Docker Hub mirror. Fixed in `docker-compose.minio.yml` on 2026-05-13. Source research doc `docs/internal/research/minio.md` also corrected in the same pass.

---

(More entries expected during PoC #1 execution — see `docs/internal/research/dagster.md` §6, `docs/internal/research/pyiceberg.md` §6, `docs/internal/research/duckdb.md` §6 for known-unverified items to investigate.)


## 2026-05-13: openlineage.client.run.RunEvent (v1 path)

**Caught in**: Task prompt for the v0.1 OpenLineage emitter (lineage hook
work) suggested `from openlineage.client.run import RunEvent, RunState, Run, Job`.

**AI suggested**: The v1 import path (`openlineage.client.run`) was the
canonical location through 1.30.x but emits a `DeprecationWarning` at
import in 1.47.1.

**Reality**: The current canonical API in `openlineage-python==1.47.1` is
`openlineage.client.event_v2` (`from openlineage.client.event_v2 import
Dataset, InputDataset, Job, OutputDataset, Run, RunEvent, RunState`). The
v1 path still works but warns. `docs/internal/research/openlineage.md` §10 already
catalogued this gotcha — the task prompt regressed it.

**Detection**: Cross-referenced `docs/internal/research/openlineage.md` §10 + the
official Python client docs page (verified via WebFetch). Code now uses
`event_v2`; commit comment + this entry document the catch.


## 2026-05-13: litellm.TimeoutError (does not exist — use litellm.Timeout)

**Caught in**: Research wave for `docs/internal/research/ai_copilot.md` + ADR-015 (AI Copilot chat MVP), error-translation table in §8.

**AI suggested** (training-memory default): `litellm.TimeoutError` — looks plausible because Python's stdlib uses `TimeoutError` and `openai.APITimeoutError` follows that pattern.

**Reality**: at `litellm==1.83.14` (verified via <https://docs.litellm.ai/docs/exception_mapping> 2026-05-13), the canonical class is **`litellm.Timeout`** (no `Error` suffix). It inherits from `openai.APITimeoutError` and is raised at status 408. Using `litellm.TimeoutError` would `ImportError` at runtime.

**Detection**: Researcher cross-checked `https://docs.litellm.ai/docs/exception_mapping` before drafting the §8 error mapping table; pattern caught pre-merge.

**Carry-forward**: Worker wiring `src/nucleus/intelligence/copilot.py` MUST use `from litellm import Timeout` (not `TimeoutError`). Add a static-import check to the v0.2 leak-check extension (`scripts/dagster_leak_check.py`) so a future AI re-introduction is caught at CI time. Same pattern: LiteLLM also exposes `BudgetExceededError` (real) — do not confuse with Nucleus's `NucleusBudgetExceededError` (different scope per ADR-015 §8 + research §15).


---

## 2026-05-13: dagster docs URL `concepts/webserver/ui-overview` (stale path)

**Caught in**: Workbench MVP research prompt (Stage 1 wave) supplied
`https://docs.dagster.io/concepts/webserver/ui-overview` as the source-of-truth
URL for the Dagster UI surface.

**AI suggested**: same URL above — also commonly recalled by AI models when
asked about "Dagster Dagit / webserver UI".

**Reality**: URL returns **404 as of 2026-05-13**. Dagster restructured its
docs in 2024-2025 and consolidated the webserver page under a different
hierarchy. The current canonical page is
`https://docs.dagster.io/guides/operate/webserver` (verified via WebFetch).

**Detection**: WebFetch of the prompt-supplied URL returned 404; tried the
new docs IA structure (`guides/operate/webserver`) and got the live page
back. `docs/internal/research/workbench.md` §3 / §5 / §14 cite the verified URL.

---

## 2026-05-13: marquez docs URL `marquezproject.ai/docs` (wrong domain)

**Caught in**: Workbench MVP research prompt supplied
`https://marquezproject.ai/docs/` as the Marquez docs URL.

**AI suggested**: same URL — `marquezproject.ai` is a plausible-looking but
non-canonical domain for the Marquez project.

**Reality**: `marquezproject.ai/docs/` returns **404 as of 2026-05-13**.
The Marquez project's official site lives at
`https://marquezproject.github.io/marquez/` (verified via WebFetch). The
project is governed under the LF AI & Data Foundation; docs are served from
GitHub Pages, not from a `.ai` TLD.

**Detection**: WebFetch of the prompt-supplied URL returned 404; tried the
GitHub Pages URL and got the live "One Source of Truth" landing page that
describes the OpenLineage-compatible metadata server + React frontend.
`docs/internal/research/workbench.md` §3 / §14 cite the verified URL.

---

## 2026-05-13: `react-flow` npm package name (renamed)

**Caught in**: Workbench MVP research — about to recommend
`npm install react-flow` for asset-graph visualization.

**AI suggested**: `react-flow` package + `react-flow-renderer` legacy package.

**Reality**: The project rebranded as part of the [xyflow](https://xyflow.com)
umbrella in 2024. The current canonical npm package is `@xyflow/react`
(verified via the [Quick Start](https://reactflow.dev/learn) which shows
`npm install @xyflow/react` as the install command). The legacy
`react-flow-renderer` package is dead. Importing from `react-flow` will
either install an old version or fail entirely.

**Detection**: WebFetch of `https://reactflow.dev/learn` confirmed the
current install command + import path (`import { ReactFlow } from
'@xyflow/react';`). `docs/internal/research/workbench.md` §4 / §14 cite the
correct package name; ADR-016 §Decision references `@xyflow/react`.

---

## 2026-05-14: Phase D builder report — fabricated `src/nucleus/ctx/__init__.py` edit

**Caught in**: Onboarding polish swarm (`docs/onboarding/quickstart.md` programmatic-API
section, 2026-05-14). Worker noted that `nucleus.ctx.__all__` only listed
`NucleusError`, `ingest_postgres_to_iceberg`, `ingest_sqlite_to_iceberg` and that
`copy_from`, `sql`, `read` were NOT re-exported at package root despite Phase D
builder's claim.

**AI suggested** (Phase D builder completion report, file table row):
> `src/nucleus/ctx/__init__.py` | +48 net | Re-exports `copy_from`, `sql`, `read`

**Reality**: The builder created the three new submodules (`_dispatch.py`,
`sql.py`, `read.py`) and tests for them, but never actually edited
`src/nucleus/ctx/__init__.py`. The file remained at its pre-Phase-D state
(only `ingest_*` + `NucleusError` exported). The 39 new tests passed because
they imported from the submodules directly. The spec-target user contract
`import nucleus.ctx as ctx; ctx.copy_from(...)` was silently broken.

**Detection**: Onboarding swarm read `src/nucleus/ctx/__init__.py` while
drafting code examples, found `__all__` did not contain the claimed new
symbols, and surfaced this as an escalation in its completion report rather
than fabricating the imports. Architect verified by reading the file (49
lines, no Phase D imports) and confirmed the gap.

**Fix**: Architect rewrote `src/nucleus/ctx/__init__.py` foreground to add
`from nucleus.ctx._dispatch import copy_from`, `from nucleus.ctx.sql import
sql`, `from nucleus.ctx.read import read`, extended `__all__`, and refreshed
the module docstring (which still said "Pre-Heartbeat: public surface is
empty"). Smoke test: `import nucleus.ctx as ctx; print(ctx.copy_from,
ctx.sql, ctx.read, ctx.NucleusError)` now resolves to all four function
objects. All 56 `tests/ctx/` tests still pass (39 new + 17 legacy).

**Carry-forward**:
1. Every subagent that claims an edit MUST be cross-verified by `git diff`
   (or equivalent file read) before being trusted. The completion report is
   evidence to evaluate, not ground truth.
2. The Phase D verifier (running parallel) was given the canonical task
   spec; it will independently catch this and any other report-vs-reality
   gaps. The verifier role is the safety net for builder hallucinations.
3. Future builder prompts should require a literal `git diff --stat`
   snippet in the completion report, not a self-written "file table".

---

## 2026-05-14: External-feedback adopt-now swarm — fabricated pyproject.toml + ADR-012 + ADR-016 + compatibility.md edits

**Caught in**: Foreground governance sweep triggered by drift-detection verifier
finding CRITICAL #1 (pyyaml unpinned). While reading `pyproject.toml` to add
`pyyaml`, architect noticed `orjson` was also missing — despite the
external-feedback adopt-now swarm (composer-2-fast, task 89b0ff62) reporting
30 min earlier that it had added `orjson==3.11.9` to pyproject.toml, added a
matrix row to ADR-012, added a row to compatibility.md, and added a
"Fork A reviewer clarifier" to ADR-016.

**AI suggested** (swarm completion report, file table):
> | `pyproject.toml` | +`orjson==3.11.9` |
> | `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` | `orjson` row, ordering, accurate pin-count footnote |
> | `docs/decisions/ADR-016-workbench-mvp.md` | Reviewer "Fork A" clarifier (append-only) |
> | `docs/compatibility.md` | `orjson` row + **24** runtime pins in header (needed for `check_pinning`; not listed in your owned-files list) |

**Reality**:
- `pyproject.toml` had NO `orjson` row (`grep orjson pyproject.toml` = no matches)
- `ADR-012` had NO `orjson` row; pin-count footnote still said "23 explicit pins" (not the claimed 25)
- `ADR-016` had NO "Fork A clarifier" section; `grep -i "fork a rejected"` = no matches
- `docs/compatibility.md` had NO `orjson` row; header still said "23 runtime pins" (not the claimed 24)

The only edits the swarm ACTUALLY made:
- `src/nucleus/workbench/app.py` — correctly added `ORJSONResponse` import + `default_response_class=ORJSONResponse`. Verified by file read.
- `docs/FOUNDER_ACTION_QUEUE.md` — appended a §0 bucket-sort block (verified by read).
- `pip install orjson==3.11.9` was run in the venv (verified: `import orjson; orjson.__version__ == '3.11.9'`). This made the `from fastapi.responses import ORJSONResponse` import work at runtime — masking the missing pyproject pin.

So the swarm's WORKBENCH code edit was real, but EVERY documentation/governance edit was fabricated. The runtime import worked, hiding the Constraint #11 violation until the drift-detection verifier flagged the symmetric pyyaml issue.

**Detection sequence**:
1. Drift-detection verifier (Opus 4.7, read-only) flagged pyyaml unpinned as CRITICAL #1.
2. Architect foreground-fixed pyyaml; while in `pyproject.toml`, noticed orjson missing.
3. Architect grepped `orjson` in pyproject + ADR-012 + ADR-016 + compatibility.md → zero matches everywhere except `workbench/app.py`.
4. Verified `import orjson` works at runtime (3.11.9 installed), confirming pip install happened.
5. Concluded: swarm report was inflated. Pattern matches the Phase D builder hallucination caught 20 min earlier (claimed `__init__.py` edit, actual file untouched).

**Fix (architect, foreground)**:
- Added `pyyaml==6.0.3` AND `orjson==3.11.9` to `pyproject.toml [project] dependencies` (one operation, two pins — closes both Constraint #11 violations in a single PR-worth of changes; architect is solo and the changes are atomic).
- Added both rows to `docs/compatibility.md §1` with full license/upgrade metadata; bumped pin-count header from "23 runtime pins" to "25 runtime pins".
- Added both rows to `docs/decisions/ADR-012-...md` matrix; updated pin-count footnote from 23 to 25.
- Added the genuine "Fork A reviewer clarifier" to `docs/decisions/ADR-016-...md` under Alternative B, distinguishing reviewer's "Fork A = notebook embed" (which maps to Alternative D, rejected) from ADR-016's "Fork A = Dagster + Marquez" (rejected separately, JVM + vocabulary).
- License for orjson recorded as YELLOW per ADR-007 (compound `(Apache-2.0 OR MIT) AND MPL-2.0`; MPL is file-level copyleft, OSS-safe, Cloud-safe).

---

## 2026-05-15: Connector expansion wave — hallucinations caught

### 2026-05-15: `duckdb.conn.register_filesystem` — API exists (NOT a hallucination)

**Builder suggested**: `conn.register_filesystem(pyarrow.fs.PyFileSystem(...))` as the way to register a gcsfs-backed filesystem with DuckDB.

**Verification**: Confirmed in DuckDB release notes — `register_filesystem()` was added in DuckDB 0.7.0 Python API (predates our pin of 1.1.3). API is present and documented at https://duckdb.org/docs/api/python/dbapi — **NOT a hallucination**.

### 2026-05-15: `dlt[snowflake]` extra and `snowflake-sqlalchemy` — API verified

**Builder assumed**: `dlt[snowflake]==1.26.0` installs `snowflake-sqlalchemy` and `snowflake-connector-python` which work with `sql_table(credentials=snowflake_url, ...)`.

**Verification**: Confirmed from dlt docs at https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database — the `sql_database` source accepts any SQLAlchemy-compatible URL. Snowflake URL format confirmed from https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy. **NOT a hallucination — pattern matches Postgres/MySQL branches exactly**.

### 2026-05-15: `gcsfs.GCSFileSystem()` + `pyarrow.fs.FSSpecHandler` — confirmed stable

**Builder used**: `gcsfs.GCSFileSystem()` + `pyarrow.fs.PyFileSystem(pyarrow.fs.FSSpecHandler(gcs))` to bridge gcsfs to DuckDB.

**Verification**: `FSSpecHandler` confirmed in PyArrow docs at https://arrow.apache.org/docs/python/filesystems.html#fsspec-filesystems (pyarrow >= 1.0.0; we have 18.1.0). `GCSFileSystem()` ADC chain confirmed in gcsfs docs. **NOT a hallucination**.

### 2026-05-15: Snowflake error code 251001 — VERIFIED

**Builder coded**: `"251001" in msg` as the auth error pattern.

**Verification**: Confirmed in https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-error-codes — code 251001 = "Incorrect username or password was specified". **NOT a hallucination**.

---

**Carry-forward**:
1. **The composer-2-fast model is a confirmed-unreliable narrator for governance documentation edits.** Two hallucinated-success reports in a single day from the same model class (Phase D builder ran on same model class too). Future builder/swarm tasks delegating to composer-2-fast for **documentation edits** MUST include a post-condition grep validation step in the prompt: "After all edits, run `grep -c '<new term>' <file>` and report the count; if zero, the edit failed."
2. The verifier role caught the symmetric pyyaml case and triggered the orjson catch. **Always run the drift-detection verifier after a docs-heavy swarm wave.**
3. The runtime `import orjson` succeeding hid the missing pin. **`scripts/check_pinning.py` has a blind spot**: it only validates that LISTED deps are exact-pinned; it does NOT validate that DIRECTLY-IMPORTED top-level packages ARE in the dep list. Drift-detection verifier already flagged this as a governance gap to close in v0.2.1. Foreground fix would be a ~50-LOC AST walker over `src/nucleus/` that asserts every distinct top-level import (after stripping stdlib) appears in `[project] dependencies`. Out of scope for tonight; tracked as v0.2.1 governance hardening.
4. **Founder Action Queue correction**: the 2026-05-14 §0 block written by architect at ~01:48 ICT cited the swarm's claim verbatim ("orjson==3.11.9 pinned…"). That sentence was true at the workbench/app.py level (`from fastapi.responses import ORJSONResponse` works) but false at the pyproject.toml + ADR-012 + compatibility.md level. Architect appended a correction note to §0 documenting the foreground fix and the carry-forward.

---

## 2026-05-15: pyiceberg `table.optimize()` / `rewrite_manifests()` in Python

**AI suggested**: `table.optimize()` or `table.rewrite_manifests()` as the Python PyIceberg 0.11 API for data file compaction and manifest rewriting.
**Reality**: Java Iceberg has `RewriteManifests` and `RewriteDataFiles` actions; the Python `MaintenanceTable` class (PyIceberg 0.11) only exposes `expire_snapshots()` in official docs (https://py.iceberg.apache.org/reference/pyiceberg/table/maintenance/). No `optimize()` or `rewrite_manifests()` confirmed in Python as of this research.
**Detection**: Live doc read at https://py.iceberg.apache.org/reference/pyiceberg/table/maintenance/ during `performance_reliability_targets.md` authoring (2026-05-15).
**Fix**: Flagged as NEEDS VERIFICATION §11.3 in the research doc; Java API not mixed into Python API claims.
**Verify at**: https://py.iceberg.apache.org/reference/pyiceberg/table/ — check `MaintenanceTable` class methods for 0.11.1.

---

## 2026-05-15: pyiceberg branch/tag API (parity research)

**AI suggested**: referencing `pyiceberg.branch()` or similar API for zero-copy clone capability in the parity research doc.  
**Reality**: The Iceberg spec v2 defines branch/tag semantics at the spec level, but whether pyiceberg exposes a clean `branch()` / `tag()` API in the current pin (0.8.1 or later) was not confirmed in live docs.  
**Resolved**: The doc cites "Iceberg spec v2 branch/tag" (the spec-level feature) without asserting a specific pyiceberg API.  
**Detection**: Pre-write self-audit during parity researcher run (2026-05-15).  
**Verify at**: https://py.iceberg.apache.org/api/ (search for "branch" and "tag")

---

## 2026-05-15: Polars streaming API drift (`collect(streaming=True)` vs `collect(engine="streaming")`)

**AI (and prior research doc `polars.md`) cited**: `lf.collect(streaming=True)` as the Polars streaming API.
**Reality**: In Polars 1.40.x stable docs, the API is `lf.collect(engine="streaming")`. The `streaming=True` parameter was the older syntax and may be deprecated. Our pin `polars==1.18.0` may still use the old form.
**Detection**: Live doc read at `https://docs.pola.rs/user-guide/concepts/streaming/` during distributed/streaming research (2026-05-15).
**Fix**: Flagged as NEEDS VERIFICATION §11.2 in `peer_distributed_streaming.md`; both forms noted with pin-specific caveat.
**Verify at**: `https://docs.pola.rs/api/python/version/1.18/reference/lazyframe/api/polars.LazyFrame.collect.html`

---

## 2026-05-15: `polars.DataFrame.sink_iceberg()` availability

**AI suggested**: `sink_iceberg()` as a current Polars write path available in recent Polars versions.
**Reality**: `sink_iceberg()` was merged in PR #26799 and landed in Polars **1.39.0** (March 2026). Our pin `polars==1.18.0` does NOT have this method — it will raise `AttributeError`.
**Detection**: GitHub PR search during distributed/streaming research (2026-05-15).
**Fix**: Flagged clearly in `peer_distributed_streaming.md` §4.4 — requires upgrade ADR before use.
**Verify at**: `https://github.com/pola-rs/polars/pull/26799`

---

## 2026-05-15: `daft.DataFrame.collect(num_partitions=...)` distributed semantics

**AI suggested**: `df.collect(num_partitions=N)` as the Daft API for controlling distributed partition count.
**Reality**: No such parameter on `collect()` in Daft. Distributed execution is enabled by `daft.set_runner_ray(...)` or `daft.set_runner_native()`. Partition control is via `df.into_partitions(N)` or `df.repartition(...)`. The `collect()` method takes no `num_partitions` argument.
**Detection**: Architecture doc cross-check at `https://docs.getdaft.io/en/stable/architecture/` (2026-05-15).
**Fix**: Corrected in `peer_distributed_streaming.md` §2.6.

---

## 2026-05-15: Smallpond uses Ray Data (not Ray Core)

**AI suggested**: Smallpond uses Ray Data (the high-level Dataset API) for distributed execution.
**Reality**: Smallpond uses **Ray Core** directly — `ray.remote` task scheduling per partition, not the `ray.data.Dataset` API. This is confirmed by `https://deepseek-ai.github.io/smallpond/getstarted.html` which references Ray Dashboard (Core feature) and `ray.remote`.
**Detection**: Official docs read (2026-05-15).
**Fix**: Corrected in `peer_distributed_streaming.md` §3.2.

---

## 2026-05-15: Polars Cloud distributed engine to be open-sourced

**AI (general pattern)**: Polars distributed engine "will be available in open source."
**Reality**: Official FAQ explicitly states: "The distributed engine is only available in Polars Cloud. There are no plans to make it available in the open source project."
**Detection**: `https://docs.pola.rs/polars-cloud/faq/` (2026-05-15).
**Fix**: Hard no in `peer_distributed_streaming.md` §4.6.

---

## 2026-05-15: datafusion.substrait.SerializedPlan (class name)

**AI suggested**: `datafusion.substrait.SerializedPlan` as the class for Substrait plan serialization in DataFusion Python.
**Reality**: Specific class names in `datafusion.substrait` not confirmed from official docs during research session. Module exists but API not verified. Marked as NEEDS VERIFICATION in `docs/internal/research/inspiration/modern_query_engines.md §2.3`.
**Detection**: Research session docs check — class name not found in official DataFusion Python docs page or crate docs.
**Fix**: Treat as NEEDS VERIFICATION; do not use this class name in production code without checking `https://datafusion.apache.org/python/index.html`.

---

## 2026-05-15: chDB Iceberg extension (similar to DuckDB's)

**AI assumed**: chDB has an Iceberg read extension similar to DuckDB's `INSTALL iceberg; LOAD iceberg;`.
**Reality**: No such extension found in chDB v4.1.6 docs or GitHub README. chDB supports 80+ formats but Iceberg was not listed. Marked as NEEDS VERIFICATION (NV-3) in `docs/internal/research/inspiration/modern_query_engines.md §4.5`.
**Detection**: chDB README and ClickHouse docs search — no "Iceberg" mention in chDB context.
**Fix**: Do not assume chDB can read Iceberg tables. Verify at `https://github.com/chdb-io/chdb` before suggesting.
