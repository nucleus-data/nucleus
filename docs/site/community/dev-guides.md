---
title: Developer Guides
description: Step-by-step runbooks for the most common contribution tasks.
---

# Developer Guides

**Audience**: Any engineer contributing to Nucleus, regardless of experience level.

**Canonical source**: [`docs/dev-guides/` on GitHub →](https://github.com/nucleus-data/nucleus/tree/main/docs/dev-guides). Sixteen step-by-step runbooks, each following the format `What you're doing / Why it matters / Step-by-step / Verification / Common pitfalls / Rollback / References`.

## Quick reference

| I want to... | Guide |
|---|---|
| Set up my development environment for the first time | [01 — Developer onboarding](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/01-developer-onboarding.md) |
| Understand whether to wrap or build a new component | [02 — Wrap-not-build decisions](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/02-wrap-not-build-decisions.md) |
| Add a new data source connector | [03 — Add connector](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/03-add-connector.md) |
| Add a new CLI command | [04 — Add CLI command](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/04-add-cli-command.md) |
| Add a new kwarg to `@nucleus.asset(...)` | [05 — Add asset decorator kwarg](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/05-add-asset-decorator-kwarg.md) |
| Add a new `NucleusError` subclass or error code | [06 — Error translation guide](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/06-error-translation-guide.md) |
| Upgrade a wrapped library | [07 — Upgrade wrapped library](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/07-upgrade-wrapped-library.md) |
| Write an ADR | [08 — Author ADR](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/08-author-adr.md) |
| Write tests | [09 — Write tests](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/09-write-tests.md) |
| Fix a governance script failure | [10 — Governance scripts](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/10-governance-scripts.md) |
| Release a new version | [11 — Release process](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/11-release-process.md) |
| Work effectively with Cursor / AI pair programming | [12 — AI pair programming](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/12-ai-pair-programming.md) |
| Understand the most common pitfalls | [13 — Common pitfalls](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/13-common-pitfalls.md) |
| Debug a failing run / confusing error | [14 — Debugging guide](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/14-debugging-guide.md) |
| Measure performance | [15 — Performance profiling](https://github.com/nucleus-data/nucleus/blob/main/docs/dev-guides/15-performance-profiling.md) |

## Before you start

1. **Read [AGENTS.md](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md)** — mandatory. Every constraint and vocabulary rule lives there.
2. **Run the baseline check** — `pytest tests/ -q --tb=short` + `python scripts/check_vocabulary.py` + `python scripts/loc_budget.py`. If any fail before your changes, document it.
3. **Apply the 8-question gate** (from the [Roadmap overview on GitHub](https://github.com/nucleus-data/nucleus/blob/main/docs/roadmap/overview.md#the-8-question-gate)) before proposing any feature.

## Required pre-merge governance

All 11 governance scripts must EXIT 0 before merge:

```powershell
python scripts/check_vocabulary.py        # vocabulary discipline
python scripts/check_pinning.py           # all runtime deps exactly pinned
python scripts/loc_budget.py              # src/nucleus/ under ceiling
python scripts/dagster_leak_check.py      # no external classnames in user strings
python scripts/check_error_codes.py       # NE-code uniqueness + ADR-006 mapping
python scripts/check_api_stability.py     # tier-frozen surface unchanged
python scripts/check_layering.py          # no cross-layer imports
python scripts/check_licenses.py          # only GREEN + YELLOW-with-boundary
python scripts/check_install_size.py      # core install footprint
python scripts/check_lazy_imports.py      # CLI cold-boot discipline
python scripts/check_changelog.py         # release-notes hygiene
```

---

*Last updated: 2026-05-15.*
