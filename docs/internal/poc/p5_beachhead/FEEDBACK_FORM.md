# PoC #5 — Internal Simulation Report (NOT a blank template)

> **⚠️ THIS IS AN INTERNAL SIMULATION — NOT THE EXTERNAL TESTER FORM**
>
> This file was filled in by a Nucleus swarm-implementer on 2026-05-14, simulating an external data engineer with no prior Nucleus access. It demonstrates what a completed feedback form looks like and documents real friction found during the simulation run.
>
> **For the blank template external testers fill in**, see: [`FEEDBACK_FORM_TEMPLATE.md`](./FEEDBACK_FORM_TEMPLATE.md)
>
> ---
>
> **Simulation date**: 2026-05-14
> **Tester persona**: External data engineer — no insider access, no prior Nucleus exposure
> **Method**: Live execution on WSL2/Ubuntu-22.04 (Windows 11), working from README + quickstart only
> **Status**: INTERNAL ONLY — do not send this file to external testers

---

## Persona

- **Role**: Senior-mid DE at an 8-person analytics startup
- **Stack today**: dbt-core + Airflow + Snowflake (existing warehouse project)
- **Why evaluating Nucleus**: Saw a reference on HN. We're starting a new analytics warehouse project greenfield. Snowflake costs are hurting. Wanted to see if something lighter + open could work.
- **Familiarity**: 5 years DE experience. Used dbt, Dagster, Airflow, a bit of Spark. Zero Nucleus exposure.

---

## Environment

- **OS**: Windows 11 (WSL2 / Ubuntu-22.04.5-LTS, kernel 6.6.87.2-WSL2)
- **Python**: 3.11.0rc1 (WSL)
- **Docker**: 29.1.5 (Docker Desktop via WSL)
- **Test start**: 2026-05-14 14:56:24 UTC+7
- **Test end**: 2026-05-14 15:03:32 UTC+7
- **Total script execution**: 428s (~7 min execution, ~15 min wall with reading)
- **Note**: GitHub URL in README returned 404. Test simulated pre-release access to local repo.

---

## Timing

| Checkpoint | Target | Actual | Status |
| ---------- | ------ | ------ | ------ |
| 1. Discovery (README + quickstart) | <5 min | ~10 min | PARTIAL — blocked by insider links + dead GitHub URL |
| 2. Install (`pip install -e ".[dev]"`) | <5 min | **381s (6.3 min)** | FAIL — over budget |
| 3. First project (`nucleus init demo-project`) | <5 min | 1s | PASS |
| 4. Boot stack (`nucleus up`) | <2 min | 16s | PASS (over 10s target) |
| 5. Ingest (`nucleus ingest sqlite://...`) | <8 min | 9s | PASS — excellent |
| 6. Query (`nucleus query`) | <3 min | 4s | PASS — excellent |
| 7. First custom asset (`nucleus run`) | <5 min | 2s (FAIL) | FAIL — discoverability gap |
| 9. Shutdown (`nucleus down`) | <1 min | 2s | PASS |
| **Total wall** | **<30 min** | **~35-40 min** (with reading + cold install) | **MISSED** (barely) |

> **Honest note**: With a warm pip cache and public GitHub URL, this would clear 30 minutes. Cold first-run on a corp laptop with proxy: easily 45+ minutes. The 6-minute install is the single biggest budget killer.

---

## Friction Findings

### 1. **[severity: Critical]** GitHub URL in README returns 404

The README install section says:
```
git clone https://github.com/nucleus-data/nucleus.git
```

**Verified**: `curl -L https://github.com/nucleus-data/nucleus.git` → HTTP 404. The repo does not exist publicly.

An external user hits a dead end immediately. There is no fallback, no "request access" link, no zip download. This is the **single hardest blocker** for PoC #5 success. The 30-minute metric cannot be validated by any real external tester until this is resolved.

---

### 2. **[severity: Critical]** Postgres error exposes full SQLAlchemy + psycopg stack trace

Running:
```
nucleus ingest "postgresql://wrong:wrong@localhost:5555/nope" --table x --as raw.x
```

Produces a **145-line Python traceback** mentioning:
- `sqlalchemy.exc.OperationalError`
- `psycopg.OperationalError`  
- `dlt.sources.sql_database`
- `dlt.extract.resource`
- Internal source file paths: `/mnt/c/Users/GOT4HC/Mordern Data Platform/src/nucleus/cli/main.py`

This directly contradicts the promised error translation layer. As a new user, I see internal library names I've never heard of. I don't know if it's a Nucleus bug or my credentials. The `NucleusError` wrapper that's advertised in the README for Postgres does not fire for this path.

**Expected**: Clean `NucleusSourceConnectionError` with: "Cannot connect to Postgres at localhost:5555. Check that the server is running and credentials are valid."

---

### 3. **[severity: High]** 6-minute install time with ~100+ transitive packages

`pip install -e ".[dev]"` pulls in (measured):
> dagster, dlt, litellm, openai, huggingface-hub, tokenizers, tiktoken, grpcio, grpcio-health-checking, fastapi, uvicorn, opentelemetry-api, pyiceberg, pyarrow, polars, duckdb... (100+ packages total)

Install took **381 seconds** on a fast WSL2 connection. On a corporate proxy or slower connection, this is 10-15 minutes before the user can run a single command.

The README promises "ship data products from a laptop" but the dependency footprint is closer to a full MLOps platform. For a cold-eval by an external DE, this is a significant "is this worth my time?" filter.

**Suggested fix**: Separate `[core]` extras (DuckDB, Polars, pyiceberg, click) from `[ai]`, `[dev]`, `[connectors]`. Let users install `pip install nucleus-data` (~20 deps) first and experience the aha-moment before pulling in Dagster + LiteLLM.

---

### 4. **[severity: High]** Internal architecture vocabulary leaks into user-facing files

`nucleus_project.yaml` (generated by `nucleus init`) contains:
```yaml
# Spec: docs/specs/nucleus_cli_spec.md §7
```
and
```yaml
# Per docs/specs/nucleus_cli_spec.md §10 NV #5: surfaced as `filesystem` to users.
```

`assets/example.py` docstring contains:
```python
"""The Asset Materialization Adapter (v4.1 §6.2) writes the returned frame to an Iceberg snapshot."""
```

An external user has no idea what `docs/specs/nucleus_cli_spec.md`, `§7`, `NV #5`, or `v4.1 §6.2` mean. These are insider references that should be stripped from generated files. They make the project feel unfinished and confusing.

---

### 5. **[severity: High]** `nucleus list` does not exist — asset discoverability gap

After `nucleus init demo-project`, the init output says:
```
nucleus run example.greeting
```

But `nucleus run example` (natural first guess) returns:
```
Error: Asset 'example' is not defined.
Fix:   Register the asset with @nucleus.asset(<key>) ... List registered assets with `nucleus list` (v0.1+).
```

The fix hint references `nucleus list` which is marked as `(v0.1+)` but **doesn't exist yet**. The user has no way to discover what assets are registered without reading the source file. For a tool selling itself on DX, this is a gap that would frustrate any first-time user.

---

### 6. **[severity: Medium]** README is cluttered with insider document links

The README links to the following internal/insider docs in the body text:
- `docs/specs/nucleus_architecture_v4.1.md` (mentioned 5+ times)
- `AGENTS.md` (mentioned 4+ times)
- `docs/decisions/ADR-002-...` (positioning decision)
- `docs/decisions/ADR-008-...` (storage substrate)
- `docs/specs/nucleus_poc_plan.md` (PoC tracking doc)
- `docs/specs/nucleus_implementation_readiness.md` (internal checklist)

These links are meaningless to an external reader who cannot access or understand them. They signal "this project is not yet ready for external consumption." The quickstart's very first line references `docs/specs/nucleus_architecture_v4.1.md §1.5`.

**Suggested fix**: External-facing README should link ONLY to `docs/onboarding/quickstart.md`, `docs/errors/`, and `docs/recipes/`. All internal doc links should be in a separate `CONTRIBUTING.md` or stripped.

---

### 7. **[severity: Medium]** Boot time is 16s (target: <10s)

`nucleus up` took 16 seconds, over the stated 10s target. This is with Docker already running and MinIO pulled. On a first run (Docker pull), it would be much longer.

The PoC #4 measured 5.82s — unclear if that was with MinIO running already or without. Either way, 16s actual vs 5.82s claimed is a discrepancy to investigate.

---

### 8. **[severity: Medium]** `nucleus version` shows `0.0.0` not `0.1.0`

```
package    version
------------------
nucleus    0.0.0
```

Minor but signals incomplete packaging. A user evaluating the tool expects a real version number.

---

### 9. **[severity: Low]** `nucleus.dev/quickstart` URL in init output is probably a placeholder

`nucleus init` output says:
```
Quickstart: https://nucleus.dev/quickstart
```

But `nucleus.dev` doesn't appear to be a live domain yet. First-time users may try to follow this link and find nothing, compounding the confusion from the broken GitHub URL.

---

### 10. **[severity: Low]** Missing table query error partially leaks DuckDB internals

`nucleus query "SELECT * FROM missing.table"` returns:
```
Error: SQL referenced an unknown object: Catalog Error: Table with name table does not exist!
Did you mean "temp.information_schema.tables"?
LINE 1: SELECT * FROM missing.table LIMIT 100
                      ^
```

The "Catalog Error:" prefix and the DuckDB-style "Did you mean..." suggestion leak internal engine wording. The fix hint (`nucleus list`) doesn't exist. The docs link routes to `asset-not-found` when this is really a SQL/query error — wrong bucket.

---

## Doc Gaps

1. **No "getting started without Docker" path.** The quickstart says `nucleus up` wraps Docker, but `nucleus up` ran fine with filesystem-only mode. There's no clear "what if I don't have Docker?" path for users who just want to try the SQLite → query path without any containers.

2. **No `nucleus run` tutorial.** The quickstart walks through `nucleus init`, `nucleus up`, `nucleus ingest`, `nucleus query` — but there's no working walkthrough of writing and running your first `@nucleus.asset`. The example in the quickstart requires editing code, and there's no "here's what your first custom asset file should look like."

3. **No dependency explanation.** Why does `nucleus` pull in `dagster`, `dlt`, `litellm`, `openai`? As a new user, I have no idea. Is this needed for basic usage? Can I use `nucleus` without an OpenAI key? (Yes, apparently, but nowhere says so.) The quickstart says "AI Copilot is v0.2" but litellm installs anyway.

4. **No error recovery guide.** After the `nucleus ingest postgres://wrong...` crash, I have no idea where to look. The docs link in the error message didn't fire (raw traceback, no error wrapper).

5. **The recipes page (`docs/recipes/sqlite_to_iceberg.md`) is linked from the quickstart** — I read it and it duplicated much of the quickstart without adding clarity. Feels like content was written twice.

---

## Error-message UX

| Error case | Verdict | Verbatim quote (trimmed) |
| ---------- | ------- | ------------------------ |
| Postgres wrong creds | **CRITICAL FAIL — raw traceback** | `sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 5555 failed: server closed the connection unexpectedly... (Background on this error at: https://sqlalche.me/e/20/e3q8)` |
| Missing table query | Partial — DuckDB wording leaks | `Error: SQL referenced an unknown object: Catalog Error: Table with name table does not exist! Did you mean "temp.information_schema.tables"?` |
| Nonexistent asset | PASS — clean | `Error: Asset 'nonexistent_asset' is not defined. Fix: Register the asset with @nucleus.asset(<key>) ...` |
| nucleus init no name | PASS — clean | `Error: A project name is required for 'nucleus init'. Fix: Pass a name as the first argument, e.g. 'nucleus init my-stack'.` |
| Postgres → missing schema error (not tested) | UNKNOWN | — |

---

## Score (1–10 per pillar, no rounding up)

### High performance on minimal resources: **6/10**

The DuckDB + Polars query path is genuinely fast (4s for a GROUP BY on 10 rows; extrapolates well). Boot time at 16s is acceptable once Docker is running but exceeds the stated 10s target. The install weight (100+ packages, 381 seconds) is the single biggest drag on this score. For a tool claiming "high performance on minimal resources," pulling in `openai`, `huggingface-hub`, `grpcio`, and full Dagster on first install contradicts the promise. Once installed, it's snappy.

### Composable by constitution: **5/10**

As a user I can't test swap drills. What I can observe: there's no user-facing way to choose engines. The README says "DuckDB vs DataFusion" but there's no `--engine` flag. The `nucleus_project.yaml` has a `catalog.type: filesystem` key, suggesting composability, but there's no documentation on how to change it. The "friendly to giants" claim (point Databricks at the Iceberg files) is intellectually compelling but I have no way to verify it in 30 minutes.

### AI-assisted by design: **3/10**

The AI Copilot (`nucleus chat`) appears in `nucleus --help` but the quickstart says it's "v0.2 / not in v0.1." I have no API key to test it anyway. The error messages (when they fire correctly) are written with clear fix hints and docs links — that's the AI-readiness design showing through. But the raw Postgres traceback destroys the experience: AI can't help a user who sees 50 lines of SQLAlchemy. Score deferred to v0.2 when copilot ships.

### Familiar UX from proven giants: **7/10**

The strongest pillar for me:
- `{{ ref('bronze.orders') }}` is instant recognition for any dbt user
- `@nucleus.asset("key")` feels like Dagster's asset decorator
- `nucleus ingest ... --table x --as y` is clean and ergonomic
- The rich terminal tables (ingest summary + preview, up table, query results) are genuinely delightful
- The error messages that work have the right shape (Error + Fix + Docs)

Drag: `nucleus list` doesn't exist, which breaks the mental model of "I decorated my function, now what?" And the internal vocab leaking into generated files (v4.1 §6.2, NV #5) breaks the "familiar UX" promise.

### Friendly to giants: **7/10**

The positioning is clear: "you'll outgrow us, your Iceberg tables come with you." I believe it structurally. The data I ingested is in a real Iceberg-backed format. The graduation story to Databricks/Snowflake is spelled out clearly in the README. No obvious lock-in at the v0.1 surface.

---

### Overall recommendation

> **Would you bring this to your team Monday?**  
> **Not yet — but come back in 4 weeks.**

The core is genuinely compelling. The `ingest → query` 30-second demo is something I'd show my team right now. But **three blockers** prevent a "yes" today:

1. The GitHub URL is 404. No real external user can install this.
2. The Postgres error traceback is embarrassing. If my team hits that on their first real ingest, they walk away.
3. The install weight (6 min, 100 deps) makes cold evals painful.

Fix those three and this clears the bar for "serious eval." The table-stakes competitive question — "why Nucleus instead of dbt + DuckDB?" — is answered well in the README. But the answer doesn't matter if the tester bounces in the first 15 minutes.

---

## What would make me a paying user

1. **Public PyPI package** (`pip install nucleus-data` in <60 seconds, <20 core deps). Let me try the SQLite → query path in one minute before committing to a full install.

2. **Postgres error translation that actually fires.** I tried the bad-creds path expecting "Connection refused — check your host/port." I got SQLAlchemy internals. Fix this one error path and the "production-grade error UX" promise becomes credible.

3. **`nucleus list` as a real command** that shows me all registered asset keys, their status, and last snapshot. The missing command breaks the "familiar DX" claim — both dbt (`dbt ls`) and Dagster (asset catalog) have this.

4. **A working `nucleus.dev` domain** with the quickstart, error docs, and a minimal install page. Currently `nucleus.dev/quickstart` (linked from init output) is presumably dead. The docs as Markdown in the repo are fine for contributors — a user landing page that isn't GitHub readme would convert evaluators.

5. **Separate `[core]` and `[ai]` / `[dev]` install groups** so I can evaluate the data plane (ingest/query) without pulling Dagster + LiteLLM on first `pip install`.

---

## What would make me close the tab in the first 5 minutes

1. **The broken GitHub URL.** I tried to `git clone` and got a 404. If I didn't have a pre-release copy, I'd be done. This is the single biggest risk to the 30-minute beachhead metric.

2. **The SQLAlchemy traceback on bad Postgres creds.** If my first real-world ingest (against a real Postgres server with a typo in the URL) produces 50 lines of Python internals with `psycopg.OperationalError` and a link to `sqlalche.me/e/20/e3q8`, I assume this is an early-stage hobby project and stop. The error translation layer exists but doesn't protect the Postgres path.

3. **The internal doc links everywhere in the README.** When a README links to `AGENTS.md`, `docs/specs/nucleus_poc_plan.md`, `docs/specs/nucleus_architecture_v4.1.md`, and ADRs in the body text — I read that as "this project is still in architectural design phase." It signals "not ready for users." Moving those links to a `CONTRIBUTING.md` or an `## Internals` section at the bottom would immediately make the README feel more external-facing.

---

## Appendix: Verbatim test log

**nucleus --help output:**
```
Usage: nucleus [OPTIONS] COMMAND [ARGS]...

Nucleus — ship data products from a laptop. Local-first Python SDK + CLI for Iceberg-native pipelines.

Options:
  --version    Show version and exit.
  --help       Show this message and exit.

Commands:
  init     Scaffold a new Nucleus project.
  up       Boot the local Nucleus runtime (warehouse, catalog, and Compose stack).
  down     Stop the Compose stack shipped with this project.
  run      Materialize one or more assets and commit Iceberg snapshots.
  ingest   Ingest a source into an Iceberg asset — the 30-minute beachhead one-liner.
  query    Execute a SQL query against the warehouse via the embedded SQL engine.
  version  Report installed Nucleus version and all pinned dependency versions.
  chat     Ask the AI Copilot a question about your project (Beta).
```

**nucleus version output:**
```
package    version
------------------
nucleus    0.0.0
duckdb     1.1.3
polars     1.18.0
pyarrow    18.1.0
pyiceberg  0.11.1
dagster    1.9.5
```

**nucleus init demo-project output:**
```
Created Nucleus project at /tmp/nucleus-poc5-tester/demo-project (7 files).

Next steps:
  cd demo-project
  nucleus up
  nucleus run example.greeting

Optional: initialize git via `git init` inside the new directory.

Quickstart: https://nucleus.dev/quickstart
```

**nucleus up output:**
```
Warehouse: /tmp/nucleus-poc5-tester/demo-project/data/warehouse
Catalog:   filesystem (SQLite at /tmp/nucleus-poc5-tester/demo-project/data/warehouse/catalog.db)
                Local stack                
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ service         ┃ endpoint              ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ minio (S3 API)  │ http://127.0.0.1:9000 │
│ minio (console) │ http://127.0.0.1:9001 │
└─────────────────┴───────────────────────┘

Nucleus up.
```

**nucleus ingest output:**
```
                Ingest summary                
┏━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ asset         ┃ rows ┃ snapshot            ┃
┡━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ bronze.orders │ 10   │ 7060783907785484660 │
└───────────────┴──────┴─────────────────────┘
       Preview (first 10 rows)        
┏━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ id ┃ customer    ┃ amount ┃ region ┃
... [10 rows preview] ...
```

**nucleus query output (correct results):**
```
┏━━━━━━━━┳━━━━━━━━━┓
┃ region ┃ revenue ┃
┡━━━━━━━━╇━━━━━━━━━┩
│ US     │ 2200.0  │
│ EU     │ 1500.0  │
│ APAC   │ 1800.0  │
└────────┴─────────┘
```

**nucleus down output:**
```
Docker volumes preserved (warehouse files on disk always remain).

Nucleus down.
```

---

*Report generated: 2026-05-14 15:20 UTC+7. Total wall time including report writing: ~40 minutes.*
