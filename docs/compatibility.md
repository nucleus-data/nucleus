# Component Compatibility Matrix

> **Authority**: This document is the **source of truth** for which versions of which components are tested-together and supported. It enforces Hard Constraint #11 (Upgrade-safe stack design).
> **Owner**: Solo founder
> **Last verified**: Month 0 (Pre-Heartbeat) — versions are TARGETS, not yet pip-installed and tested
> **Companion**: [`AGENTS.md`](../AGENTS.md) §3, [`pyproject.toml`](../pyproject.toml)

This file is updated **only via PR** and only after the upgrade workflow (§4) has been followed.

---

## §1. Current supported matrix (v0.0.0 / Pre-Heartbeat target)

### §1.1 Python runtime

| Component | Minimum | Tested | Maximum tested | EOL |
|-----------|---------|--------|----------------|-----|
| Python | 3.11.0 | 3.11.x, 3.12.x | 3.12.x | 3.11 EOL Oct 2027; 3.12 EOL Oct 2028 |

### §1.2 Core data stack (Tier 1 — wrapped, exact pin required)

| Library | Pinned | Docs URL | Latest tested | Last verified | Notes |
|---------|--------|----------|---------------|---------------|-------|
| `pyarrow` | `18.1.0` | https://arrow.apache.org/docs/python/ | 18.1.0 | Month 0 | Drives zero-copy between engines |
| `duckdb` | `1.1.3` | https://duckdb.org/docs/api/python/overview | 1.1.3 | Month 0 | SQL engine |
| `polars` | `1.18.0` | https://docs.pola.rs/api/python/stable/ | 1.18.0 | Month 0 | DataFrame engine |
| `pyiceberg` | `0.8.1` | https://py.iceberg.apache.org/ | 0.8.1 | Month 0 | Table format. Constraint #4. |
| `dagster` | `1.9.5` | https://docs.dagster.io/api | 1.9.5 | Month 0 | Hidden orchestrator. Constraint #2. |

### §1.3 Ingestion & connectivity

| Library | Pinned | Docs URL | Used for | Notes |
|---------|--------|----------|----------|-------|
| `sqlalchemy` | `2.0.36` | https://docs.sqlalchemy.org/en/20/ | Source connections (Postgres, MySQL) | 2.x only |
| `psycopg[binary]` | `3.2.3` | https://www.psycopg.org/psycopg3/docs/ | Postgres connector | v3, not v2 |
| `pymysql` | `1.1.1` | https://pymysql.readthedocs.io/ | MySQL connector | Pure-Python |

### §1.4 Transformation & SQL

| Library | Pinned | Docs URL | Used for |
|---------|--------|----------|----------|
| `jinja2` | `3.1.5` | https://jinja.palletsprojects.com/ | `ctx.sql` template resolution |
| `sqlglot` | `26.0.0` | https://sqlglot.com/sqlglot.html | SQL parsing for lineage extraction |

### §1.5 CLI & UX

| Library | Pinned | Docs URL | Used for |
|---------|--------|----------|----------|
| `click` | `8.1.7` | https://click.palletsprojects.com/ | CLI primitives (via typer) |
| `typer` | `0.15.1` | https://typer.tiangolo.com/ | Modern CLI framework |
| `rich` | `13.9.4` | https://rich.readthedocs.io/ | Terminal output formatting |
| `msgspec` | `0.18.6` | https://jcristharif.com/msgspec/ | Fast structured types (errors, configs) |
| `structlog` | `24.4.0` | https://www.structlog.org/ | Structured logging |

### §1.6 Observability

| Library | Pinned | Docs URL | Used for |
|---------|--------|----------|----------|
| `opentelemetry-api` | `1.29.0` | https://opentelemetry.io/docs/languages/python/ | Span emission (Constraint #7) |
| `opentelemetry-sdk` | `1.29.0` | (same) | SDK + exporters |

### §1.7 Dev tooling

| Library | Pinned | Docs URL | Used for |
|---------|--------|----------|----------|
| `ruff` | `0.8.4` | https://docs.astral.sh/ruff/ | Linter + formatter |
| `mypy` | `1.13.0` | https://mypy.readthedocs.io/ | Type checking (strict mode) |
| `pytest` | `8.3.4` | https://docs.pytest.org/ | Test framework |
| `pytest-cov` | `6.0.0` | https://pytest-cov.readthedocs.io/ | Coverage |
| `pytest-xdist` | `3.6.1` | (pytest org) | Parallel tests |
| `hypothesis` | `6.123.7` | https://hypothesis.readthedocs.io/ | Property tests |
| `testcontainers` | `4.9.0` | https://testcontainers-python.readthedocs.io/ | Postgres/MinIO containers |
| `pre-commit` | `4.0.1` | https://pre-commit.com/ | Git hooks |

---

## §2. Status & validity of this matrix

| Status | Meaning |
|--------|---------|
| ✅ **Verified** | Versions installed, smoke tests passed, all docs links current |
| ⏳ **Targeted** | Versions are intended targets; not yet pip-installed in this repo |
| ⚠️ **Drift detected** | One or more versions deviated from this doc; needs reconciliation |
| 🚫 **Broken** | Known incompatibility; do not install |

**Current status of the matrix above**: **⏳ Targeted** (Month 0 — no installs yet).

**Before Tier 0 ships**, every line above must be promoted to **✅ Verified** by:
1. Running `pip install -e ".[dev]"` cleanly in a fresh venv (Python 3.11 + 3.12).
2. Running `nucleus_smoke.py` (PoC #4) and confirming `<10s` boot.
3. Re-checking every docs URL returns 200.
4. Bumping the "Last verified" date.

---

## §3. Inter-component compatibility constraints

Some pairs of components have known compatibility requirements:

### §3.1 PyArrow ↔ DuckDB
- DuckDB 1.1.x requires PyArrow **≥10.0.0**, tested with 18.x.
- DuckDB 1.0.x compatibility with PyArrow 18.x: untested by us; **do not mix**.
- Reference: https://duckdb.org/docs/api/python/data_ingestion.html#apache-arrow

### §3.2 PyArrow ↔ Polars
- Polars 1.x has zero-copy interop with PyArrow ≥11.0.0.
- Polars 0.x **not supported** (we require 1.x).
- Reference: https://docs.pola.rs/user-guide/migration/pyarrow/

### §3.3 PyArrow ↔ PyIceberg
- PyIceberg 0.8.x requires PyArrow **≥14.0.0,<19.0.0**.
- Strict pin in `pyproject.toml` keeps us in range.
- Reference: https://py.iceberg.apache.org/configuration/

### §3.4 Dagster ↔ Python
- Dagster 1.9.x supports Python 3.9–3.12.
- Dagster 2.x (announced for 2027) will drop Python 3.9; we're already on 3.11+, no concern.
- Reference: https://docs.dagster.io/getting-started/install

### §3.5 PyIceberg ↔ Catalog backends
- v0.1: Filesystem catalog only.
- v0.3+: Lakekeeper REST catalog. Requires Lakekeeper server ≥0.4.0 (confirmed compatible with PyIceberg 0.8.x via Iceberg REST spec v1).
- v1.0+: AWS Glue, Polaris, Tabular. Confirmed compatible via Iceberg REST spec v1.

---

## §4. Upgrade workflow (Hard Constraint #11)

When a component version needs to change, follow this **exact** workflow. Skipping steps = rejected PR.

### Step 1: Document the why
Open an ADR in `docs/decisions/`:
- Why upgrade this component?
- What's the new feature / bug fix we're getting?
- What's the risk?

### Step 2: One component per PR
- **A PR may upgrade exactly ONE wrapped component.**
- Exception: Security CVE forcing simultaneous upgrade of related components (e.g., `cryptography` + `requests`). Document in the ADR.

### Step 3: Read the changelog
- Read the **full changelog** for the version range from current to target. (E.g., upgrading DuckDB 1.1.3 → 1.2.0: read DuckDB 1.1.4, 1.1.5, 1.2.0 release notes.)
- Note **breaking changes** in the ADR.
- If there are breaking changes that affect our code: a separate PR fixes the breakage **before** the upgrade PR.

### Step 4: Run smoke tests
- `pytest -m smoke` — basic operations work.
- `pytest -m integration` — full integration suite passes.
- `pytest poc/` — every PoC validation still passes.
- Run on Python 3.11 AND 3.12.
- On Linux AND macOS (Windows weekly).

### Step 5: Run upgrade-specific tests
- Look in `tests/upgrade/test_<component>_upgrade.py` — if the test doesn't exist yet, add one as part of this PR.
- The test asserts: behavior we depend on still works in the new version.

### Step 6: Update this file
- Change the `Pinned` column.
- Update `Last verified` to today's date.
- Update `Latest tested` to the new version.

### Step 7: Update `pyproject.toml`
- Change the dependency pin.
- Ensure transitive deps still resolve (try `pip-compile` or `uv lock`).

### Step 8: Update `CHANGELOG.md`
- Under `[Unreleased] → Changed`:
  - `- Upgrade <component> from X.Y.Z to A.B.C (#PR_NUMBER)`.

### Step 9: PR review
- Title: `chore(deps): upgrade <component> X.Y.Z → A.B.C`.
- Body: link to ADR, summary of breaking changes (if any), smoke-test output.

### Step 10: Rollback plan
- The PR description must include explicit rollback instructions:
  ```
  ## Rollback
  If issues found post-merge:
  1. Revert this commit.
  2. `git push origin main`.
  3. Pin back to X.Y.Z in pyproject.toml.
  ```

---

## §5. Watch list (upgrades we know are coming)

Components we track for upcoming versions:

| Component | Watch for | Why we wait | Decision trigger |
|-----------|-----------|-------------|------------------|
| **DuckDB** | 1.2.x | New `FROM` syntax improvements, partitioned writes | When 1.2.0 stable + 30 days |
| **Polars** | 1.20+ | Decimal type improvements | When stable + need arises |
| **PyIceberg** | 0.9.x | Better SQL catalog support, snapshot ops | When stable + Lakekeeper testing begins (v0.3) |
| **Dagster** | 1.10.x | Asset improvements (asset key reconciliation) | When stable + tested |
| **Python** | 3.13.x | Free-threading (PEP 703) | When wrapped deps all support 3.13 |
| **PyArrow** | 19.x | Performance improvements | Major version, careful testing required |
| **Ruff** | 0.9.x | New rules | Any time (low risk) |

Updated whenever a watched component releases a new version: PR adds note here, ADR drafted if upgrade considered.

---

## §6. Pinning policy

### §6.1 Runtime dependencies
- **Exact pins** (`==X.Y.Z`) for everything users install with `pip install nucleus`.
- **Rationale**: Solo founder cannot debug "works on my machine" issues caused by transitive version drift. Exact pins = reproducible installs.

### §6.2 Dev dependencies
- **Exact pins** for tools that affect code style or CI behavior (`ruff`, `mypy`, `pytest`).
- **Compatible release pins** (`~=X.Y`) acceptable for utilities (`hypothesis`, `pre-commit`).
- **Rationale**: We want fast feedback, but dev-tool upgrades shouldn't silently break CI.

### §6.3 Transitive dependencies
- We do **not** pin transitives in `pyproject.toml`.
- We **do** ship a `requirements.lock` (uv lockfile or pip-tools compiled) in the repo for **deterministic** dev environments. Generated by `make lock` or `uv lock`.

### §6.4 Why not "any version"?
We could use `>=1.0` for everything. We don't because:
- **Reproducibility**: Same `pip install nucleus` should work in 5 years.
- **Debuggability**: When a bug report says "I'm on Nucleus 0.3.2", we know exactly what they have.
- **Constraint #11**: This document mandates pinned versions.

---

## §7. Vulnerability response

CVE handling per `docs/conventions/engineering.md` §12.5:

1. `pip-audit` runs weekly via GitHub Actions cron.
2. **Critical** CVE in a direct dep: pause feature work, ship upgrade within 48h.
3. **Critical** CVE in a transitive dep: ship pin override within 1 week.
4. **High** CVE: include in next sprint.
5. **Medium / Low** CVE: include in normal upgrade cadence.

Vulnerability tracking: GitHub Security Advisories tab + this file's "Last verified" date.

---

## §8. EOL / end-of-life policy

When a wrapped library is about to lose support:

- **6 months before EOL**: open ADR proposing migration / removal.
- **3 months before EOL**: implement migration.
- **At EOL**: drop the dep, removal recorded in CHANGELOG.

Currently no dep within 6 months of EOL.

---

## §9. Change history

| Date | Change | PR |
|------|--------|-----|
| Month 0 (now) | Initial matrix, status: ⏳ Targeted | — |

Append a row for every modification.

---

*Constraint #11 in action: read this file before installing or upgrading anything.*
