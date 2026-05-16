# 10 — Governance Scripts

> **What you're doing**: Understanding what each governance script enforces and how to fix violations.
> **Why it matters**: All governance scripts must EXIT 0 before any PR merges. CI blocks merge if any fail. These scripts are the automated safety net for the architectural constraints.
> **Location**: All scripts are in `scripts/`.
> **Time**: 5-30 minutes to fix a violation, depending on its type

---

## Run Order (CI and Local)

Run in this order; later scripts can depend on earlier ones passing:

```powershell
# Step 1: Vocabulary discipline
python scripts/check_vocabulary.py

# Step 2: Pinning discipline  
python scripts/check_pinning.py

# Step 3: LOC budget
python scripts/loc_budget.py

# Step 4: Error translation (no external classnames in user strings)
python scripts/dagster_leak_check.py

# Step 5: Error code uniqueness (NE-code mapping per ADR-006)
python scripts/check_error_codes.py

# Step 6: API stability tiers (Frozen surface unchanged per ADR-005)
python scripts/check_api_stability.py

# Step 7: Layer isolation (no cross-layer imports per architecture)
python scripts/check_layering.py

# Step 8: License compliance (ADR-007)
python scripts/check_licenses.py

# Step 9 (upgrade PRs only): Upgrade smoke + regression
python scripts/upgrade_smoke.py
```

---

## `check_vocabulary.py`

**Enforces**: `AGENTS.md §7` vocabulary discipline. No banned terms in source code user-facing strings.

**What it scans**: `src/nucleus/`, `tests/`, `docs/` for banned terms in string literals and docstrings.

**Banned terms**: "metastore", "job" (as pipeline primitive), "task" (in orchestration context), "plugin" (in v1 context), "table" (as the primary primitive), "AI-native", "Spark killer", etc.

**How to fix**:
```
FAIL: src/nucleus/cli/main.py:42 — "job" found in string "Run a job"
FIX: Change to "Run an asset materialization"
```

Vocabulary map:
| Banned | Use instead |
|---|---|
| "metastore" | "catalog" |
| "job", "task" | "asset", "materialization" |
| "table" (as primitive) | "asset" |
| "plugin" | "module" or "connector" |
| "AI-native" | "AI-assisted" |

---

## `check_pinning.py`

**Enforces**: Every runtime dependency in `pyproject.toml` has an exact `==` pin. Per Constraint #11.

**What it scans**: `pyproject.toml [project.dependencies]` and `[project.optional-dependencies]` (for runtime extras like `observability`, `lineage-advanced`).

**How to fix**:
```
FAIL: polars>=1.0 is not exactly pinned
FIX: Change to polars==1.18.0 in pyproject.toml
```

Dev deps (`[project.optional-dependencies] dev`) may use `~=` or `==`; the script enforces `==` only for runtime deps.

**After fixing**: run `pip install -e ".[dev]"` to install the exact version.

---

## `loc_budget.py`

**Enforces**: `src/nucleus/` stays under the phase LOC ceiling. Hard ceiling at v1.0: 30,000 LOC.

**What it counts**: Lines of code in `src/nucleus/` (Python files only; excludes comments and blank lines).

**Output**:
```
src/nucleus/ LOC: 4,200
v0.1 ceiling: 8,000
Status: GREEN (52.5% of ceiling)
```

**How to fix a RED status**:
- Review recently added code for speculative features that can be removed.
- Check if existing code can be simplified (less is more per Anti-Over-Engineering).
- Do NOT raise the ceiling without architectural review.

**Per-phase ceilings**:
| Phase | Ceiling |
|---|---|
| v0.1 | 8,000 |
| v0.2 | 12,000 |
| v0.3 | 16,000 |
| v0.5 | 20,000 |
| v1.0 | 28,000 |
| v1.5 | 30,000 (hard wall) |

---

## `dagster_leak_check.py`

**Enforces**: No external library classnames in user-facing strings. Per `AGENTS.md §11.7` and `docs/specs/nucleus_architecture_v4.1.md` §6.4.

**What it scans**: `src/nucleus/`, `tests/` for:
- Dagster classnames: `DagsterUserCodeExecutionError`, `OpExecutionContext`, etc.
- pyiceberg classnames: `NoSuchTableError`, `CommitFailedException`, etc.
- DuckDB classnames: `DuckDBPyConnection`, `CatalogException`, etc.
- SQLAlchemy classnames: `OperationalError`, `ProgrammingError` in user_message strings.

**How to fix**:
```
FAIL: src/nucleus/cli/main.py:450 — "DuckDB" found in user-facing string
FIX: Change "via DuckDB" to "via the embedded SQL engine"
```

Run after adding any new error handler or CLI command that mentions the underlying technology.

---

## `check_error_codes.py`

**Enforces**:
1. Every `NucleusError` subclass has a unique `error_code` ClassVar.
2. Error codes follow the NE-band numbering per ADR-006.
3. No duplicate codes across the codebase.

**What it scans**: `src/nucleus/errors.py` (primarily).

**Output**:
```
Found 32 NucleusError subclasses.
Codes: NE1001, NE1002, ..., NE5008
Status: PASS (0 duplicates, 0 missing)
```

**How to fix**:
```
FAIL: NucleusMyError has error_code = "NE1001" — duplicate of NucleusSourceConnectionError
FIX: Assign a unique code. Run: python scripts/check_error_codes.py --list-used
     to see all used codes.
```

---

## `check_api_stability.py`

**Enforces**: Every symbol in `src/nucleus/ctx/__init__.__all__` has a `# Stability: <tier>` comment in the module where it's defined. Per ADR-005.

**Stability tiers**:
- `Frozen`: stable for 2+ years; breaking change requires deprecation cycle.
- `Beta`: may change within minor versions with `NucleusAIBreakingChange` warning.
- `Internal`: not for public use; no stability guarantee.
- `Deprecated`: scheduled for removal; shows deprecation warning.

**How to fix**:
```
FAIL: ctx.copy_from has no Stability: tag
FIX: Add "# Stability: Beta" comment above the function definition in copy_from.py
```

---

## `check_layering.py`

**Enforces**: No cross-layer imports. The architecture has 5 layers (L0-L4); each layer may only import from lower layers.

**Layer boundaries**:
```
L4 Experience (cli/, workbench/)
  → imports from: L3 Intelligence, L2 Coordination, L1 Engines, L0 Physics
L3 Intelligence (intelligence/)
  → imports from: L2 Coordination, L1 Engines, L0 Physics
L2 Coordination (coordination/, sdk/, ctx/)
  → imports from: L1 Engines, L0 Physics
L1 Engines (engines/)
  → imports from: L0 Physics
L0 Physics (physics/)
  → imports from: nothing in nucleus
```

**Forbidden example**:
```python
# FAIL: coordination importing from cli (L2 → L4, wrong direction)
from nucleus.cli.main import app

# FAIL: intelligence importing from coordination's implementation details
from nucleus.coordination.sql_resolver import _parse_refs  # private
```

**How to fix**:
- Move the shared code to the lower layer.
- Or extract to a utility module in the lower layer.
- Never "fix" by adding a flag to bypass the check.

---

## `check_licenses.py`

**Enforces**: All dependencies have permissive licenses per ADR-007.

**Tiers**:
- `GREEN`: Apache 2.0, MIT, BSD (permissive; safe for all use)
- `YELLOW`: MPL-2.0, LGPL-2.1+, LGPL-3.0 (file-level copyleft; acceptable with boundary)
- `RED`: GPL-2.0, GPL-3.0, SSPL, BSL (copyleft or source-available; block)
- `UNKNOWN`: needs manual verification; becomes a FOUNDER_ACTION_QUEUE item

**How to fix**:
```
FAIL: some-package UNKNOWN — license not recognized
FIX: Look up the actual license at https://pypi.org/project/some-package/
     Update scripts/check_licenses.py BAKED_IN_LICENSES dict with the correct SPDX identifier
     Log in docs/decisions/ADR-007 if it's a YELLOW license
```

---

## `upgrade_smoke.py`

**Enforces** (only run for dependency upgrade PRs):
1. ADR-012 cross-check: all pins in pyproject.toml match compatibility.md.
2. Per-component upgrade smoke tests pass.

**When to run**: always in upgrade PRs; optionally in regular development.

**How to fix**:
```
FAIL: ADR-012 cross-check: duckdb pin in pyproject.toml (1.1.5) != compatibility.md (1.1.3)
FIX: Update docs/compatibility.md to match the new pin
```

---

## `benchmark_regression.py` (Performance-Sensitive PRs)

**Enforces**: No more than 10% performance regression vs. pre-change baseline.

**Metrics**: boot time, `nucleus run` latency, `ctx.sql` query latency, `ctx.copy_from` throughput.

**When to run**: PRs that touch `coordination/`, `ctx/`, `cli/`, or upgrade compute-intensive deps (DuckDB, Polars).

---

## CI Run Order

In `.github/workflows/ci.yml`:

```yaml
- name: Governance - vocabulary
  run: python scripts/check_vocabulary.py

- name: Governance - pinning
  run: python scripts/check_pinning.py

- name: Governance - LOC budget
  run: python scripts/loc_budget.py

- name: Governance - error translation (dagster leak)
  run: python scripts/dagster_leak_check.py

- name: Governance - error codes
  run: python scripts/check_error_codes.py

- name: Governance - API stability
  run: python scripts/check_api_stability.py

- name: Governance - layering
  run: python scripts/check_layering.py

- name: Governance - licenses
  run: python scripts/check_licenses.py
  continue-on-error: true  # YELLOW licenses are informational

- name: Tests
  run: python -m pytest tests/ -q --tb=short

- name: Beachhead E2E
  run: python scripts/beachhead_e2e.py
```

---

## When a Script Fails Before Your Change

Before you start work, run all governance scripts. If any fail on the unmodified codebase, document it:

```bash
python scripts/check_vocabulary.py > /dev/null 2>&1 && echo PASS || echo FAIL
```

Do not fix pre-existing failures unless they block your work. Log them in `docs/FOUNDER_ACTION_QUEUE.md`.

---

## References

- ADR-005: API stability tiers — `docs/decisions/ADR-005-ctx-sdk-api-freeze-policy.md`
- ADR-006: error code numbering — `docs/decisions/ADR-006-nucleus-error-code-numbering.md`
- ADR-007: license tier policy — `docs/decisions/ADR-007-dependency-license-tier-policy.md`
- ADR-011: telemetry opt-in — `docs/decisions/ADR-011-telemetry-and-observability-opt-in-policy.md`
- `AGENTS.md §11.7` — error translation enforcement
