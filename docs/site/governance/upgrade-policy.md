---
title: Upgrade Policy
description: How Nucleus manages dependency upgrades — one component per PR, exact pins, mandatory rollback commands.
---

# Upgrade Policy

Per [AGENTS.md §11.13](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md#1113-upgrade-safety-discipline-hard-constraint-11):

## Rules

1. **Exact version pins.** Every runtime dependency uses `package==X.Y.Z`. No `>=`, no `~=`.
2. **One component per PR.** Never bulk-upgrade. Each PR touches exactly one dependency.
3. **Mandatory changelog summary.** PR description must include the changelog from current to target version.
4. **Mandatory rollback command.** Every upgrade PR includes the exact `pip install` to revert.
5. **Upgrade smoke tests.** `pytest -m upgrade` must pass after every upgrade.
6. **24-hour cooldown.** Wait 24 hours between merging upgrades to catch regressions.
7. **Major version requires ADR.** X.y.z → X+1.y.z always needs an Architecture Decision Record.

## Compatibility matrix

Current pinned versions are tracked in [`docs/internal/compatibility.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/compatibility.md).

## Upgrade workflow

```bash
# 1. Read the changelog
# (DuckDB example)
open https://github.com/duckdb/duckdb/releases

# 2. Update pyproject.toml
# Change: "duckdb==1.1.3"
# To:     "duckdb==1.2.0"

# 3. Run upgrade smoke tests
pip install -e ".[dev]"
pytest -m upgrade -v

# 4. Run beachhead E2E
nucleus up && nucleus run example.greeting && nucleus down

# 5. Commit with rollback documented
git commit -m "chore: upgrade duckdb 1.1.3 → 1.2.0

Rollback: pip install duckdb==1.1.3

Changelog summary: [key behavioral changes]
Upgrade smoke: PASS
Beachhead E2E: PASS
"
```

## Quarterly audit

Every 3 months, review [`docs/internal/compatibility.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/compatibility.md) for:

- Components more than 2 minor versions behind
- Security advisories
- Dependencies approaching end-of-life

Plan next quarter's upgrades based on staleness and risk.
