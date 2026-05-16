# Internal Docs — Maintainer Reference Only

> **Audience**: Nucleus maintainers, founder, contributors with merge rights.
>
> **Not for HN visitors or library users.** Public-facing docs live one level up in `docs/` (or in the `docs/site/` mkdocs source) and at the project root (`README.md`, `AGENTS.md`, `CONTRIBUTING.md`, etc.).

This subtree was carved out of the public `docs/` surface during the v0.2 docs reorg (2026-05-16) so contributors browsing the repo on GitHub or pulling the source can immediately tell maintainer notes apart from user-facing material. Nothing here is required reading for building a Nucleus pipeline — it is the bookkeeping side of the project.

## Layout

| Path | What lives here |
|---|---|
| [`audits/`](audits/) | Drift checks, frozen-worker recovery audits, positioning audits |
| [`benchmarks/`](benchmarks/) | Raw benchmark JSON outputs + the `_results/` archive |
| [`FOUNDER_ACTION_QUEUE.md`](FOUNDER_ACTION_QUEUE.md) | Master per-decision history (read first when in doubt) |
| [`budget_history.md`](budget_history.md) | Monthly LOC budget snapshots (Constraint #8 evidence) |
| [`compatibility.md`](compatibility.md) | Pinned-version matrix per AGENTS.md §11.13 |
| [`NEEDS_VERIFICATION_INDEX.md`](NEEDS_VERIFICATION_INDEX.md) | Catch-all NV index |
| [`poc/`](poc/) | PoC-specific runbooks, recruitment plans, evidence (post-promotion) |
| [`release-process/`](release-process/) | Founder close-out checklists, sprint runbooks, packaging audits, raw E2E results |
| [`reorg/`](reorg/) | This-reorg planning notes + prior reorg artifacts |
| [`research/`](research/) | Official-docs research notes per Constraint #10 (one file per wrapped component); `inspiration/` + `strategic/` subdirs hold ecosystem analyses |
| [`security/`](security/) | Threat models, Dependabot dispositions |
| [`swap/`](swap/) | Swap-target migration notes for Tier 1/2 dependencies |

## Conventions

- **No external-classname leak.** Internal docs follow the same error-translation discipline as user-facing material (AGENTS.md §11.7). When a runbook MUST cite a Dagster / DuckDB / Polars classname verbatim (e.g. chaos-test output, audit trails), confine that citation to inline code or a clearly-fenced block — never a free-text user instruction.
- **Vocabulary stays canonical.** AGENTS.md §7. Audit trails and research notes legitimately quote competitor positioning (banned terms like "AI-native" / "Spark killer" appear there as quoted competitor framings, never as Nucleus self-description); those occurrences are exempt via `scripts/check_vocabulary.py` SKIP_PATTERNS for the `docs/internal/audits/`, `docs/internal/research/`, and `docs/internal/release-process/` paths. <!-- banned-term: example-mentions -->`
- **Cite the spec.** When an internal doc proposes an architectural change, cite the relevant section of [`../specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) — the locked source of truth.

## Why this exists

The public `docs/` tree grew to ~450 markdown files during the v0.1 → v0.2 sprint. About 40 % of those are maintainer-only context (founder runbooks, drift audits, research notes, raw benchmark dumps) that has zero value to a first-time visitor. Splitting them into `docs/internal/` shrinks the public surface by roughly 170 files without losing any content, and lets the GitHub repo landing page actually be useful for evaluators.

See [`reorg/2026-05-15_root_md_reorg.md`](reorg/2026-05-15_root_md_reorg.md) for the prior-reorg notes that set the precedent.

---

*Carved out 2026-05-16 by the docs reorg pass; index file added by Commit 7. Last touched: see `git log -- docs/internal/README.md`.*
