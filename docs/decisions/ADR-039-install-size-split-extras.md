# ADR-039: Split install size — core / postgres / mysql / snowflake / s3 / gcs / ai / workbench / observability / lineage-advanced / all extras

**Status**: ACCEPTED — 2026-05-15 (ratified retroactively; code shipped 2026-05-15)
**Date**: 2026-05-15
**Author**: Worker B4 (install-size split) + v0.2 close-out checklist §1.4
**Priority**: P0 (PoC #5 blocker)
**Target phase**: v0.2
**Related**: ADR-012 §Tier 2 extras pattern · ADR-014 Postgres connector · ADR-015 AI Copilot · ADR-016 Workbench

---

## Context

PoC #5 R2 finding (2026-05-14, external-tester simulator) flagged that
`pip install -e .` shipped **100+ transitive dependencies** and took
**~6 minutes** on a cold pip cache — both well outside the beachhead
30-minute target (`AGENTS.md` §11.8) and the "5-engineer team builds
first BI-ready Iceberg table from `git clone` in <30 minutes" promise.

Root cause: the v0.1 install bundled the **union** of every connector,
the AI Copilot stack, and the Workbench HTTP UI into a single mandatory
install — most of which a first-time tester does not need to run
`nucleus init demo && nucleus up && nucleus run example.greeting`.

Before this ADR's code landed, the `pyproject.toml` `[project]
dependencies` list included `psycopg`, `pymysql`, `snowflake-connector`,
`gcsfs`, `litellm`, `fastapi`, `uvicorn`, `dlt[*]` and their transitive
SDKs — every PoC #5 tester paid the full install cost on first run.

Per `AGENTS.md` Anti-Over-Engineering Discipline (2026-05-13 founder
directive): **defer not yet needed, ship lean default**. Per
`AGENTS.md` Constraint #11 (one component per PR, exact pins): each
extra group is independently versioned and rollback-tested.

---

## Decision

**Adopt a layered-extras pattern** matching the `pip install pkg[a,b]`
syntax. The default `pip install nucleus` produces a lean core (≤30
top-level deps, target <60 s clean install on a warm pip cache); every
optional capability lights up via an additive opt-in extra.

### Extras taxonomy

| Group | Purpose | Sample deps | Boundary |
|---|---|---|---|
| **(core)** (`[project.dependencies]`) | Run `init`/`up`/`down`/`run`/`query`/`list`/`version` against SQLite + filesystem Iceberg | `duckdb`, `polars`, `pyarrow`, `pyiceberg[sql-sqlite,s3fs,duckdb]`, `s3fs`, `dagster`, `croniter`, `jinja2`, `click`, `typer`, `structlog`, `rich`, `pyyaml`, `opentelemetry-api`, `openlineage-python`, `httpx` | ≤30 entries hard limit (enforced by `scripts/check_install_size.py`) |
| `postgres` | Postgres source connector (ADR-014) | `sqlalchemy`, `psycopg[binary]`, `dlt[sql_database,pyiceberg]` | YELLOW for `psycopg` LGPLv3 (dynamic-link exempt per ADR-007 §Tier 2) |
| `mysql` | MySQL source connector (ADR-014 amendment) | `sqlalchemy`, `pymysql`, `dlt[sql_database,pyiceberg]` | GREEN |
| `snowflake` | Snowflake source connector (ADR-019) | `sqlalchemy`, `snowflake-sqlalchemy`, `snowflake-connector-python`, `dlt[sql_database,pyiceberg]` | GREEN |
| `s3` | Raw S3 helpers beyond pyiceberg's pinned `s3fs` | (s3fs already pinned in core) | GREEN |
| `gcs` | GCS source connector | `gcsfs`, `google-cloud-storage`, `dlt[filesystem,pyiceberg]` | GREEN |
| `ai` | AI Copilot (`nucleus chat`) | `litellm`, `tiktoken` | GREEN (litellm Apache-2.0; tiktoken MIT) |
| `workbench` | Workbench HTTP UI (`nucleus workbench start`) | `fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `httpx` | GREEN |
| `observability` | OTEL SDK + exporters (ADR-011 amendment) | `opentelemetry-sdk`, `opentelemetry-exporter-otlp` | GREEN |
| `lineage-advanced` | sqlglot for column-lineage walker (ADR-032 gate) | `sqlglot` | GREEN (MIT) |
| `all` | Every runtime extra above | union of the runtime groups | (LIST-only — does not include `dev`) |
| `dev` | Contributor tooling (test/lint/type/docs) | `pytest`, `ruff`, `mypy`, `pre-commit`, `mkdocs-material`, ... | `==` or `~=` accepted (linters can minor-flex per Constraint #11 carve-out) |

### Per-module ownership matrix (boundary rule)

Modules under `src/nucleus/` reachable from **core** code paths MUST
NOT do a module-top `import psycopg / fastapi / litellm / dlt /
snowflake / gcsfs`. The CLI uses lazy imports inside command bodies;
module-level imports of optional libs would crash users who installed
core only. Validated by:

- `scripts/check_install_size.py` — runs `python -c "from nucleus.cli.main import app"` against `pip install nucleus[core]` and confirms a clean import without optional deps installed.
- `scripts/check_lazy_imports.py` — AST-walks `src/nucleus/` for any top-level `import` of the optional libraries above and exits non-zero if found.
- `tests/test_install_extras.py` — smoke-installs `nucleus[core]`, `nucleus[postgres]`, `nucleus[ai]`, `nucleus[workbench]`, `nucleus[all]` in clean venvs and asserts only the expected deps land.

### Empirical install time (target & actuals)

| Install | Target | Actual (2026-05-15, warm pip cache) |
|---|---|---|
| `pip install nucleus` (core) | <60 s | TBD — measured by `scripts/release_e2e/install_size.py` |
| `pip install nucleus[postgres]` | <90 s | TBD |
| `pip install nucleus[ai]` | <90 s | TBD |
| `pip install nucleus[workbench]` | <90 s | TBD |
| `pip install nucleus[all]` | <180 s | TBD |

PoC #5 testers will report empirical numbers on first-run; v0.2.1
patch landing if any exceed budget by >25 %.

---

## Options considered

| Option | Description | Why rejected / chosen |
|---|---|---|
| **A — Layered extras (selected)** | Lean core + per-capability extras + `[all]` aggregate | ✅ SELECTED — matches PyPI ecosystem convention (`pandas[excel,html]`, `httpx[http2,socks]`); minimal user friction once docs explain the pattern; smallest blast radius. |
| B — Monolithic install (status quo before this ADR) | One install includes everything | ❌ REJECTED — directly violates the PoC #5 R2 finding; ships dead code for 80 % of testers. |
| C — Sub-packages on PyPI (`nucleus-postgres`, `nucleus-ai`) | Each extra published as its own distribution | ❌ REJECTED — invokes Constraint #2 (no public plugin SDK in v1) and triples the release ceremony for every minor version bump. |
| D — Lazy-only (no extras, all deps optional at runtime) | Install only `nucleus`, deps resolved at first call | ❌ REJECTED — invites the "Polars not found, install with `pip install polars`" UX trap that pandas-vs-numpy users actively dislike; layered extras give an explicit upfront contract. |

---

## Consequences

### Pros

- **Beachhead protection**: PoC #5 testers install `nucleus` and get to the
  first Iceberg snapshot in <30 minutes (`AGENTS.md` §11.8).
- **License surface shrinks for default install**: `psycopg` LGPLv3 (YELLOW)
  no longer in the default install path; only enters when a tester opts into
  `[postgres]`.
- **Faster CI**: `pip install -e ".[dev]"` shrinks; `pip install -e
  ".[dev,all]"` only used for full-coverage jobs.
- **Encourages connector experimentation**: a Snowflake tester does not pay
  the Postgres install cost; an AI Copilot tester does not pay the Workbench
  install cost.

### Cons

- **One more concept to teach**: `README.md` quickstart needs a paragraph on
  extras; `docs/onboarding/quickstart.md` shows the pattern up front.
- **Lock-step risk**: a future feature that crosses two extras (e.g., AI
  Copilot reading from Postgres) needs both extras installed; the test
  matrix grows. Mitigated by `tests/test_install_extras.py` covering the
  most-likely combinations.

### LOC budget impact

- `pyproject.toml`: +75 LOC (new `[project.optional-dependencies]` block)
- `scripts/check_install_size.py`: ~250 LOC (new governance script)
- `scripts/check_lazy_imports.py`: ~200 LOC (new governance script)
- `tests/test_install_extras.py`: ~240 LOC (new)
- `src/nucleus/cli/main.py`: ~20 LOC delta (move imports inside command bodies)

Total: ~785 LOC, well within the v0.2 phase ceiling.

### Affected files

| File | Change |
|---|---|
| `pyproject.toml` lines 41-49 + 105-107 + 140-300 | Core dep list trimmed; extras block added; ADR-039 footnote referenced |
| `scripts/check_install_size.py` | New governance script (≤30 core deps; lean core import check) |
| `scripts/check_lazy_imports.py` | New governance script (AST-walks `src/nucleus/`) |
| `tests/test_install_extras.py` | New smoke test (`pip install nucleus[core/postgres/ai/workbench/all]`) |
| `src/nucleus/cli/main.py` | Lazy-imported `psycopg`, `fastapi`, `litellm`, `dlt`, `httpx` (in command bodies) |
| `docs/onboarding/quickstart.md` | Install patterns section |
| `docs/internal/compatibility.md` | Per-extra version pin rows |
| `README.md` | Install section shows extras |

---

## Verification

Run after install:

```powershell
# Confirm lean core import works without optional deps
python -c "from nucleus.cli.main import app; print('OK')"

# Smoke each extra (clean venv)
python -m venv .venv-smoke
.\.venv-smoke\Scripts\Activate.ps1
pip install -e ".[core]"      # default extras = the core install path
pip install -e ".[postgres]"  # additive
pip install -e ".[ai]"        # additive
pip install -e ".[workbench]" # additive
pip install -e ".[all]"       # union

# Governance gates
python scripts/check_install_size.py
python scripts/check_lazy_imports.py
python scripts/check_pinning.py
pytest tests/test_install_extras.py -v
```

---

## Rollback

If a critical extra-boundary regression appears post-tag:

1. `git revert <commit-that-applied-this-ADR>` (single commit, mechanical).
2. Re-run `pip install -e ".[dev]"` to confirm pre-split behaviour.
3. Cut v0.2.1 patch with the rollback; do NOT amend v0.2.0.

The split is fully reversible because every extra is additive — uninstalling an extra is `pip uninstall <its deps>`.

---

## Architecture sections touched

- `docs/specs/nucleus_architecture_v4.1.md` §3 Pillar 1 (high performance on minimal resources) — install time is part of perf.
- `docs/specs/nucleus_architecture_v4.1.md` §4 (wrapped dependencies — each Tier 1/2 lib is now opt-in).
- `AGENTS.md` §11.13 (one component per PR, exact pins — every extra is its own upgrade lane).
- `AGENTS.md` §11.8 (beachhead 30-min metric — install time is the long-pole).

---

## Open questions

None as of 2026-05-15 ratification. PoC #5 empirical install-time numbers
land via the recruitment-plan cohort; v0.2.1 patches any extra that
exceeds budget.
