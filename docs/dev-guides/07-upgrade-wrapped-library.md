# 07 — Upgrade a Wrapped Library

> **What you're doing**: Upgrading a pinned dependency (DuckDB, Polars, pyiceberg, Dagster, dlt, etc.) from one exact version to another.
> **Why it matters**: Unpinned or bulk-upgraded dependencies are the #1 cause of mysterious "worked yesterday, broken today" failures. Per `AGENTS.md §11.13` (Hard Constraint #11).
> **Rule**: ONE component per PR. Never bulk upgrade. Never.
> **Time**: 2-6 hours depending on changelog size

---

## STOP — Before You Touch Anything

If a user (or automated tool like Dependabot) asks you to "upgrade all dependencies" in one PR:

**Refuse.**

> "Per `AGENTS.md §11.13`, we upgrade one component per PR. Which would you like first? Suggested order based on staleness: [list from `docs/compatibility.md`]"

Bulk upgrades create multi-variable debugging nightmares. One component, one PR.

---

## Step 1: Read the Changelog from Current → Target Version

**Every minor release between current and target.** Not just the target release.

```bash
# Find current pin
grep "<package>" pyproject.toml

# Example: upgrading duckdb from 1.1.3 to 1.1.5
# Read ALL release notes:
# https://github.com/duckdb/duckdb/releases/tag/v1.1.4
# https://github.com/duckdb/duckdb/releases/tag/v1.1.5
```

Look for:
- Breaking API changes (methods renamed, removed, signature changed)
- Behavioral changes (different default behavior, new error types)
- Performance changes (might affect benchmarks)
- Security fixes (always note in PR description)

Save a summary. You'll need it for the PR description.

---

## Step 2: Update the Pin in `pyproject.toml`

```toml
# pyproject.toml

[project]
dependencies = [
    ...
    "duckdb==1.1.5",   # was 1.1.3
    ...
]
```

Do NOT use ranges (`>=`, `~=`). Always exact `==` pins. Per Constraint #11.

---

## Step 3: Update `docs/compatibility.md`

Update the row for the upgraded component:

```markdown
| `duckdb` | `1.1.5` | MIT · GREEN | watch 1.2.x | SQL engine |
```

Bump the "Last verified" date in the file header.

---

## Step 4: Update `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md`

Add/update the row in the pin matrix:

```markdown
| duckdb | 1.1.5 | was 1.1.3; upgraded YYYY-MM-DD; changelog: <URL> |
```

---

## Step 5: Install the New Version

```bash
pip install -e ".[dev]"
```

Verify the new version is installed:
```bash
python -c "import duckdb; print(duckdb.__version__)"
```

---

## Step 6: Run the Upgrade Smoke Test

```bash
python scripts/upgrade_smoke.py
```

This script verifies:
- ADR-012 cross-check (all pins in pyproject.toml match compatibility.md)
- Core imports work
- Basic operations still work (depends on per-component smoke stubs)

If there's a component-specific upgrade smoke test:
```bash
python -m pytest tests/upgrade_smoke/test_duckdb.py -v
```

---

## Step 7: Run the Full Test Suite

```bash
python -m pytest tests/ -q --tb=short
```

**All must pass.** If a test that was passing before now fails: stop. Investigate. Do NOT re-run until it passes. This is the bug.

**If tests are flaky** (pass sometimes, fail other times): this IS the bug. Surface it. Do not retry to get a green.

---

## Step 8: Run the Beachhead E2E

```bash
python scripts/beachhead_e2e.py
```

All 8 gates must PASS. If any gate regresses: rollback and investigate.

---

## Step 9: Run the Benchmark Regression Check

For performance-sensitive components (DuckDB, Polars, pyiceberg):

```bash
python scripts/benchmark_regression.py
```

Acceptance criterion: no more than 10% regression vs. pre-upgrade baseline.

If a benchmark script doesn't exist yet, manually time the key operations:
```bash
time nucleus run example.greeting    # cold start
time python -c "import duckdb; duckdb.connect().execute('SELECT 1').fetchall()"
```

---

## Step 10: Run All Governance Scripts

```bash
python scripts/check_vocabulary.py
python scripts/check_pinning.py
python scripts/loc_budget.py
python scripts/dagster_leak_check.py
python scripts/check_error_codes.py
python scripts/check_api_stability.py
python scripts/check_licenses.py
```

All must EXIT 0.

---

## Step 11: Write the PR Description

Required sections:

```markdown
## Upgrade: <package> <old-version> → <new-version>

### Changelog summary
<2-3 bullet points from the changelog; focus on breaking changes and security fixes>
- No breaking API changes for our usage pattern
- Performance improvement: ...
- Security fix: CVE-YYYY-NNNNN (affects X, we are not affected because Y)

### Behavioral changes observed
<Any differences you noticed during testing>

### Rollback command
```bash
pip install <package>==<old-version>
```

### Tests
- Upgrade smoke: PASS
- Full test suite: PASS (N passed, M skipped, 0 failed)
- Beachhead E2E: 8/8 PASS
- Benchmark: <X% change, within 10% threshold>

### Governance
- check_pinning.py: EXIT 0
- check_licenses.py: EXIT 0 (license unchanged: <SPDX identifier>)
- All other governance scripts: EXIT 0
```

---

## Step 12: Wait 24h After Merge

Per `AGENTS.md §11.13`:

> Wait 24 hours between merge and the next dependency upgrade. Catch regressions before stacking changes.

Do not stack multiple dependency upgrades on the same day.

---

## Major Version Upgrade (X.y.z → X+1.0.0)

Major version upgrades require an ADR before the upgrade PR. The ADR documents:
- Breaking changes that affect Nucleus
- Migration path
- Rollback plan if the upgrade fails
- Test plan (beyond standard upgrade smoke)

Template: see ADR-003 (pyiceberg 0.8.1 → 0.11.x) as the reference.

---

## Dependabot / Automated Upgrade Requests

When an automated PR arrives (Dependabot, Renovate, etc.):

1. Do NOT merge automatically.
2. Read the PR description; if no changelog summary: read the changelog yourself and add it.
3. Run Steps 6-10 manually.
4. If all pass: merge the automated PR.
5. If any fail: close the automated PR; open a new manual PR with the findings documented.

---

## Rollback

If the upgrade introduces a regression that can't be quickly fixed:

```bash
# 1. Update pyproject.toml back to old pin
# 2. pip install -e ".[dev]"
# 3. Update docs/compatibility.md
# 4. Update ADR-012
# 5. If already merged: git revert <merge-commit>
```

The rollback command must be in the PR description before merging (so it's trivially available in an emergency).

---

## Common Pitfalls

- **Upgrading without reading the changelog**: behavioral changes break things silently.
- **Testing only the happy path**: upgrade may have changed error behavior; test error cases too.
- **Forgetting to update `docs/compatibility.md`**: the matrix drifts from reality.
- **Multiple upgrades in one PR**: "while I was upgrading DuckDB I also bumped Polars" — always separate PRs.
- **Not updating `ADR-012`**: the ADR is the source of truth for the pin matrix.

---

## Verification Checklist

```
[ ] Only one dependency upgraded in this PR
[ ] pyproject.toml exact pin updated
[ ] docs/compatibility.md updated (new version, new Last verified date)
[ ] ADR-012 updated
[ ] upgrade_smoke.py PASS
[ ] pytest tests/ 0 failures
[ ] beachhead_e2e.py 8/8 PASS
[ ] benchmark regression < 10%
[ ] All 8 governance scripts EXIT 0
[ ] PR description has: changelog summary, behavioral changes, rollback command
[ ] 24h cool-down planned before next dep upgrade
```

---

## References

- `AGENTS.md §11.13` — upgrade safety discipline (Hard Constraint #11)
- `docs/compatibility.md` — the living compatibility matrix
- `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` — canonical pin matrix
- `docs/decisions/ADR-003-pyiceberg-upgrade-0.8.1-to-0.11.x.md` — reference major upgrade ADR
- `scripts/upgrade_smoke.py` — automated upgrade gate
