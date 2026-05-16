# Developer Guides — Index

> **Audience**: Any engineer contributing to Nucleus, regardless of experience level.
> **Purpose**: Step-by-step runbooks for the most common contribution tasks. Each guide answers: what, why, how, verify, rollback.

---

## "Which guide for which task?" Quick Reference

| I want to... | Go to |
|---|---|
| Set up my development environment for the first time | [`01-developer-onboarding.md`](01-developer-onboarding.md) |
| Understand whether to wrap or build a new component | [`02-wrap-not-build-decisions.md`](02-wrap-not-build-decisions.md) |
| Add a new data source connector (`nucleus ingest <source>://`) | [`03-add-connector.md`](03-add-connector.md) |
| Add a new CLI command | [`04-add-cli-command.md`](04-add-cli-command.md) |
| Add a new kwarg to `@nucleus.asset(...)` | [`05-add-asset-decorator-kwarg.md`](05-add-asset-decorator-kwarg.md) |
| Add a new `NucleusError` subclass or error code | [`06-error-translation-guide.md`](06-error-translation-guide.md) |
| Upgrade a wrapped library (DuckDB, Polars, pyiceberg, etc.) | [`07-upgrade-wrapped-library.md`](07-upgrade-wrapped-library.md) |
| Write an ADR (Architecture Decision Record) | [`08-author-adr.md`](08-author-adr.md) |
| Write tests for new code | [`09-write-tests.md`](09-write-tests.md) |
| Understand / fix a governance script failure | [`10-governance-scripts.md`](10-governance-scripts.md) |
| Release a new version | [`11-release-process.md`](11-release-process.md) |
| Work effectively with Cursor / AI pair programming | [`12-ai-pair-programming.md`](12-ai-pair-programming.md) |
| Understand the most common pitfalls | [`13-common-pitfalls.md`](13-common-pitfalls.md) |
| Debug a failing run / confusing error | [`14-debugging-guide.md`](14-debugging-guide.md) |
| Measure boot / materialization / query performance | [`15-performance-profiling.md`](15-performance-profiling.md) |

---

## How These Guides Are Structured

Every "how-to" guide follows this format:

```
## What you're doing
## Why it matters
## Step-by-step (numbered, each ≤ 30 lines of code)
## Verification
## Common pitfalls
## Rollback
## References
```

This format is intentional: you can always verify you did it right ("Verification") and recover if you didn't ("Rollback").

---

## Before You Start Any Contribution

1. **Read [`AGENTS.md`](../../AGENTS.md)** — mandatory. Every constraint and vocabulary rule lives there.
2. **Run the baseline check**:
   ```powershell
   python -m pytest tests/ -q --tb=short
   python scripts/check_vocabulary.py
   python scripts/loc_budget.py
   ```
   If any fail before your changes, document it — you can't fix what's not yours.
3. **Apply the 8-question gate** (from [`../roadmap/overview.md`](../roadmap/overview.md)) before proposing any feature.

---

## Key Vocabulary (required reading from `AGENTS.md §7`)

| Use | Not |
|---|---|
| **asset** | "table", "job", "task" |
| **materialization** | "run output", "result" |
| **snapshot** | "version", "checkpoint" |
| **contract** | "expectation", "constraint" |
| **check** | "test", "assertion" (in asset context) |
| **source asset** | "ingestion job" |
| **catalog** | "metastore" |
| **`ctx`** | "context", "session" |
| **Copilot** | "AI helper", "assistant" |
| **graduate** | "migrate" (in graduation context) |

Violations are caught by `scripts/check_vocabulary.py` in CI.

---

## Governance Scripts Summary

All must EXIT 0 before any PR merges. Full details in [`10-governance-scripts.md`](10-governance-scripts.md).

```powershell
python scripts/check_vocabulary.py     # vocabulary discipline
python scripts/check_pinning.py        # all runtime deps exactly pinned
python scripts/loc_budget.py           # src/nucleus/ under ceiling
python scripts/dagster_leak_check.py   # no external classnames in user strings
python scripts/check_error_codes.py    # NE-code uniqueness + ADR-006 mapping
python scripts/check_api_stability.py  # tier-frozen surface unchanged
python scripts/check_layering.py       # no cross-layer imports
python scripts/check_licenses.py       # only GREEN + YELLOW-with-boundary
```

---

*Last updated: 2026-05-15. Source: `AGENTS.md §11`, `docs/specs/nucleus_architecture_v4.1.md`.*
