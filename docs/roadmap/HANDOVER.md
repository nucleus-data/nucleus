# Handover — Start Here

> **For**: The next developer or the founder returning after a break.
> **Purpose**: Fastest path from zero to productive in this codebase.

---

## Day 0 — First 2 Hours

**Step 1**: Clone and set up the environment.

```bash
git clone <repo>
cd "Mordern Data Platform"
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Mac/Linux:
source .venv/bin/activate

pip install -e ".[dev,docs]"
nucleus --version   # should print 0.1.0
```

**Step 2**: Verify the environment.

```powershell
python -m pytest tests/ -q --tb=short   # baseline; some skips are OK
python scripts/beachhead_e2e.py          # 8/8 PASS means your env is correct
python scripts/check_vocabulary.py       # must EXIT 0
python scripts/loc_budget.py             # must show GREEN
```

**Step 3**: Read the mandatory docs (in order):

1. [`AGENTS.md`](../../AGENTS.md) — **mandatory, 30 min.** Governs every decision in this repo.
2. This doc (done).
3. [`docs/roadmap/overview.md`](overview.md) — 10 min; orients you in the version timeline.
4. [`docs/roadmap/v0.2-public-launch.md`](v0.2-public-launch.md) — the current phase.
5. [`docs/specs/nucleus_architecture_v4.1.md`](../specs/nucleus_architecture_v4.1.md) — 50 min; the architectural bible.

---

## Day 1 — Understand the Codebase

### "Where to find what"

| What | Where |
|---|---|
| Product identity + constraints | `AGENTS.md` §0-§4 |
| Architecture (single source of truth) | `docs/specs/nucleus_architecture_v4.1.md` |
| API surface (ctx SDK) | `docs/specs/nucleus_ctx_sdk_spec.md` |
| Asset model | `docs/specs/nucleus_asset_model_spec.md` |
| CLI commands | `docs/specs/nucleus_cli_spec.md` |
| Project layout | `docs/specs/nucleus_project_anatomy.md` |
| All ADRs (why decisions were made) | `docs/decisions/ADR-*.md` |
| What shipped (version history) | `CHANGELOG.md` |
| Dependency pins + upgrade history | `docs/compatibility.md` |
| Research notes on wrapped libs | `docs/internal/research/<lib>.md` |
| Swap interfaces + migration paths | `docs/internal/swap/<lib>.md` |
| AI hallucination log | `docs/internal/research/ai_hallucinations.md` |
| LOC budget history | `docs/budget_history.md` |
| Known open decisions | `docs/FOUNDER_ACTION_QUEUE.md` |
| Roadmap (this directory) | `docs/roadmap/` |
| Developer runbooks | `docs/dev-guides/` |
| Source code | `src/nucleus/` |
| Tests | `tests/` |
| PoC artifacts (historical) | `poc/` |
| Governance scripts | `scripts/` |
| CI configuration | `.github/workflows/ci.yml` |

### Five-Layer Architecture at a Glance

```
L4 Experience:   src/nucleus/cli/          src/nucleus/workbench/
L3 Intelligence: src/nucleus/intelligence/
L2 Coordination: src/nucleus/coordination/ src/nucleus/sdk/        src/nucleus/ctx/
L1 Engines:      src/nucleus/engines/      (DuckDB, Polars — wrapped, not implemented)
L0 Physics:      src/nucleus/physics/      (Apache Arrow, Iceberg — immortal standards)
```

Each layer ONLY imports from the layer below it. `scripts/check_layering.py` enforces this in CI.

---

## Day 2-3 — First Contribution

### Pick a task

1. Check `docs/FOUNDER_ACTION_QUEUE.md` — deferred items waiting for a PR.
2. Check GitHub Issues labeled `good-first-issue` or `v0.2`.
3. Avoid touching these files without architecture review: `src/nucleus/coordination/error_translation.py`, `src/nucleus/sdk/`, `src/nucleus/ctx/__init__.py`.

### Follow the per-feature workflow (`AGENTS.md §11.4`)

```
Step 1: WRAP vs BUILD check (5 min)
Step 2: Spec the tests first (15 min)
Step 3: AI scaffolds implementation (10 min)
Step 4: AI expands tests (15 min)
Step 5: Human review (30 min)
Step 6: Run all governance + pytest
```

### Governance scripts to run before every PR

```powershell
python scripts/check_vocabulary.py
python scripts/check_pinning.py
python scripts/loc_budget.py
python scripts/dagster_leak_check.py
python scripts/check_error_codes.py
python scripts/check_api_stability.py
python scripts/check_licenses.py
python -m pytest tests/ -q --tb=short
```

All must EXIT 0 (or be pre-existing failures documented in `FOUNDER_ACTION_QUEUE.md`).

### PR discipline

- One logical change per PR (per `AGENTS.md §11.10`)
- One dependency upgrade per PR (per Constraint #11)
- Title format: `feat:`, `fix:`, `chore:`, `adr:`, `docs:`
- Description: what changed + why + rollback command (if dep upgrade)
- All governance scripts mentioned above must pass in CI

---

## Day 4-5 — Advanced Understanding

### How error translation works

Every external library exception is caught and translated to a `NucleusError` subclass. Users NEVER see `dagster.DagsterUserCodeExecutionError` or `duckdb.CatalogException`. See `docs/dev-guides/06-error-translation-guide.md`.

### How the test suite is organized

```
tests/
  cli/          — CLI command tests
  coordination/ — Error translation, SQL resolver, AMA
  ctx/          — ctx SDK tests (copy_from, sql, read)
  intelligence/ — AI Copilot tests
  sdk/          — @nucleus.asset, @nucleus.check
  upgrade_smoke/ — one test per dependency: upgrade smoke
  chaos/        — (v0.3+) concurrent/failure tests
```

### How AI assistance works in this project

See `docs/dev-guides/12-ai-pair-programming.md`. Key rule: never trust AI output without verifying:
1. Import actually exists in the pinned library version.
2. Method call actually exists (check official docs URL).
3. No external classname in user-facing strings.

---

## Working Session Conventions

### Commits

- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `adr:`, `test:`
- Never force-push to `main`
- Tag releases only from `main` after CI passes

### Architecture decisions

- Any new dependency → ADR required (template: `docs/dev-guides/08-author-adr.md`)
- Any major version upgrade → ADR required (per Constraint #11)
- Any wrap-vs-build decision → document the OSS options considered

### When stuck

1. Re-read `AGENTS.md §12` (when in doubt).
2. Apply the 8-question gate.
3. Search `docs/internal/research/` for prior research.
4. Open a GitHub Discussion (not a PR) for architectural questions.

---

## Escalation Path

For architectural conflicts or decisions beyond the 8-question gate:

1. Write the problem in a GitHub Discussion with the tag `[architecture-decision-needed]`.
2. Propose options A, B, C using the ADR template.
3. Recommend one option with rationale.
4. Wait for founder response before writing code.

Decisions that require an ADR cannot be made autonomously. All other decisions use Anti-Over-Engineering defaults.

---

*Last updated: 2026-05-15. For the full reading order, see [`docs/roadmap/README.md`](README.md).*
