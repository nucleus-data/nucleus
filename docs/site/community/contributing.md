---
title: Contributing
description: How to contribute to the Nucleus project — quick start, expectations, and quality gates.
---

# Contributing

Thanks for your interest. Nucleus is small-and-deliberate: a tight scope, a small core team, and a strong bias toward **wrap, not build**. Contributions that respect those constraints land quickly; contributions that drift get conversation first.

The full canonical document is [`CONTRIBUTING.md`](https://github.com/nucleus-data/nucleus/blob/main/CONTRIBUTING.md) in the repo root. This page is the friendly summary.

## Quick start

```bash
git clone https://github.com/nucleus-data/nucleus.git
cd nucleus
python3.11 -m venv .venv
source .venv/bin/activate         # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
make check                        # all governance gates green before you start
```

If `make check` is red on a fresh clone, that's a bug — please file an issue.

## Before you submit

Read these in order. They take ~30 minutes total and prevent ~90% of "needs more context" review cycles.

1. [`AGENTS.md`](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md) — universal agent guide: vocabulary, the 11 hard constraints, the 8-question gate, workflow discipline
2. [`docs/specs/nucleus_architecture_v4.1.md`](https://github.com/nucleus-data/nucleus/blob/main/nucleus_architecture_v4.1.md) — the single source of truth (supersedes v4.0 and v3)
3. The [Architecture Decisions index](../governance/architecture-decisions.md) — every "build vs wrap" decision is logged as an ADR

## Contribution types

| Type | Notes | Issue first? |
|------|-------|--------------|
| Bug fix | Always welcome. Small fixes — straight PR. Larger fixes — file an issue first so we can confirm the diagnosis. | Larger only |
| Docs improvement | Excellent starting point. Edit under `docs/site/`; preview with `mkdocs serve`. | No |
| New feature | Must pass the [8-question gate](../philosophy/eight-question-gate.md). Most "would be nice" features defer to v0.3 or later. | **Yes** |
| Dependency upgrade | One component per PR per [upgrade policy](../governance/upgrade-policy.md). Major-version bumps require an ADR. | Yes |
| New connector | File an issue to discuss the design. We prefer thin wrappers over rich custom connectors. | **Yes** |
| New error code | Use the next free `NE[L][CCC]` slot per [error code registry](../errors/index.md). Update the page. | No |

## Quality gates

Every PR must pass these locally before opening:

```bash
make check    # vocabulary + pinning + layering + dagster-leak + LOC budget + lazy-imports
make lint     # ruff check + ruff format --check
make type     # mypy --strict
make test     # pytest (unit + smoke)
```

If you don't have `make`, the equivalent commands are in [`Makefile`](https://github.com/nucleus-data/nucleus/blob/main/Makefile). CI re-runs everything; local runs save round-trips.

The four governance gates that are hard release blockers:

- **Vocabulary** — no `metastore`, `Data OS`, `AI-native`, etc. (see [vocabulary table](https://github.com/nucleus-data/nucleus/blob/main/AGENTS.md#7-vocabulary-use-these-terms)) <!-- banned-term: multiple -->
- **Pinning** — exact `==` pins on every runtime dep
- **LOC budget** — proprietary code stays under 30,000 lines through v1.0
- **No external classnames in user-facing strings** — all errors translate to `NucleusError`

## Code review and merge

- One reviewer + green CI = mergeable for low-risk changes
- Two reviewers required for: anything in `coordination/`, error-translation handlers, schema/atomicity logic, dependency upgrades, ADR ratification
- Squash-merge by default; the commit message should be your PR title with a one-line "why"

## Where help is most welcome right now

- More **cookbook recipes** under `docs/site/cookbook/` — ingestion patterns from your real source systems
- **External-tester feedback** on the [30-minute beachhead path](../getting-started/quickstart.md) — tell us where you got stuck
- **Translations** of `docs/site/getting-started/*` into other languages (issue first)

## Ground rules

- Be kind. We follow the [Code of Conduct](code-of-conduct.md). Disagreement on architecture is normal and welcome; rudeness is not.
- Cite your sources. When proposing a change, point at the architecture section it touches.
- Defer is a valid answer. Many great ideas land in `docs/internal/FOUNDER_ACTION_QUEUE.md` for a future version.

If you're unsure whether something fits, open a [GitHub Discussion](https://github.com/nucleus-data/nucleus/discussions) — it's lower-stakes than an issue and often faster.
