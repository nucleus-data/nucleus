# Engineering Conventions

> **Status**: v0.1 (locked at pre-Heartbeat, Month 0)
> **Owner**: Solo founder
> **Authority**: This document overrides personal preference. PRs that violate these conventions are rejected without further review.
> **Companion docs**: [`AGENTS.md`](../../AGENTS.md), [`.cursor/rules/nucleus.mdc`](../../.cursor/rules/nucleus.mdc), [`docs/compatibility.md`](../compatibility.md)

Engineering conventions exist to make 1,000 small decisions once so we never re-debate them. Every convention here has a **Decision** and a **Why** — if you find a reason to violate it, raise an ADR in [`docs/decisions/`](../decisions/), don't just bend the rule.

---

## §1. Language & Runtime

### §1.1 Python version
- **Decision**: Python 3.11 minimum, 3.12 supported. Drop 3.11 only when 3.13 lands as production-stable.
- **Why**: 3.11 is the floor of all our wrapped deps (DuckDB, Polars, PyIceberg, Dagster). 3.10 reaches EOL Oct 2026.
- **Enforcement**: `pyproject.toml` `requires-python = ">=3.11,<3.13"`. CI tests both 3.11 and 3.12.

### §1.2 Type system
- **Decision**: **Strict mypy** on `src/`, `tests/`, `poc/`, `scripts/`. No untyped functions. No implicit `Any`.
- **Why**: Type errors at compile time = bugs not found at runtime. AI agents produce better code from typed signatures.
- **Enforcement**: `pyproject.toml` `[tool.mypy] strict = true`. CI fails on any mypy error.
- **Exception**: Third-party libs without stubs may need `# type: ignore[import-untyped]` with a comment explaining why.

### §1.3 Import organization
- **Decision**: Standard library → third-party → first-party (`nucleus`). One blank line between groups. Within a group, alphabetical.
- **Why**: `ruff` enforces it automatically; saves bikeshedding.
- **Enforcement**: `ruff check --select I`.

### §1.4 String style
- **Decision**: Double quotes (`"hello"`) for all strings, single quotes (`'inner'`) only when nested.
- **Why**: One default. PEP 8 prefers either; we pick.
- **Enforcement**: `ruff format` with `quote-style = "double"`.

### §1.5 f-strings everywhere
- **Decision**: Use f-strings. Never `%`-formatting. `.format()` only for templates passed by users.
- **Why**: Faster, clearer, type-friendly.

---

## §2. Project structure

### §2.1 `src/` layout
- **Decision**: All importable code lives under `src/nucleus/`. **No flat layout.**
- **Why**: Forces explicit packaging. Prevents accidental imports of test/poc/scripts code.
- **Reference**: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/

### §2.2 Module sizes
- **Decision**:
  - File: target ≤ 400 lines, hard limit 600.
  - Function: target ≤ 50 lines, hard limit 100.
  - Class: target ≤ 200 lines, hard limit 400.
- **Why**: Cognitive load. Reviewability. AI agents perform worse on 1000+ line files.
- **Enforcement**: `scripts/loc_budget.py` runs in CI. Files >600 lines block merge.

### §2.3 Module naming
- **Decision**: All modules and packages lowercase, underscore-separated: `error_translation.py`, not `ErrorTranslation.py` or `error-translation.py`.
- **Why**: PEP 8.

### §2.4 Package boundaries
- **Decision**: Following our 5-layer architecture, source code mirrors the layers:
  ```
  src/nucleus/
  ├── physics/        # L0 — Arrow, Iceberg, Parquet adapters
  ├── engines/        # L1 — DuckDB, Polars adapters
  ├── coordination/   # L2 — Dagster wrappers, asset materialization
  ├── intelligence/   # L3 — AI Layer (post v0.2)
  ├── ctx/            # L4 — public SDK
  ├── cli/            # L4 — CLI commands
  └── _internal/      # Shared internals; underscore prefix = NEVER import outside src/nucleus
  ```
- **Why**: Layer boundaries are enforced at the directory level. Easy to see violations.
- **Enforcement**: Dependency direction rule (see §3.1).

### §2.5 Public API surface
- **Decision**: **Only `nucleus.ctx.*` and `nucleus.cli.*` are public.** Everything else is internal. Imports outside these from user code violate `nucleus_architecture_v4.1.md` §13.1 (ctx SDK Contract).
- **Why**: Stable surface = stable contract.
- **Enforcement**: `__all__` in `nucleus/__init__.py` lists only public names. `scripts/check_public_api.py` validates.

---

## §3. Dependency direction

### §3.1 Layers depend down, never up
- **Decision**: A module in layer N may import from layer N or below (lower number). **Never higher.**
  - ✓ `ctx/` imports from `coordination/`
  - ✓ `coordination/` imports from `engines/`
  - ✗ `engines/` imports from `ctx/`
  - ✗ `physics/` imports from `coordination/`
- **Why**: Inverts dependencies = circular madness. Pure functional core, effects at the edges.
- **Enforcement**: `scripts/check_layering.py` parses imports, fails CI on violation.

### §3.2 No cross-engine imports
- **Decision**: `engines/duckdb_engine.py` may **not** import from `engines/polars_engine.py`. Engines are isolated.
- **Why**: We swap engines via the Engine interface (§7.2), not via direct cross-reference.

### §3.3 `_internal/` is closed
- **Decision**: Anything under `_internal/` is fair game for refactor. **Never reference from outside the package it's defined in.**
- **Why**: It's our private toolbox. Stable contracts live elsewhere.

---

## §4. Error handling

### §4.1 NucleusError is the single user-facing error type
- **Decision**: All errors that reach a user must be a subclass of `nucleus.errors.NucleusError`. Internal errors translated at the boundary (per v4.1 §6.4).
- **Why**: Users debug with our vocabulary, not Dagster's. PoC #1 validates the translation layer.
- **Structure**:
  ```python
  class NucleusError(Exception):
      """Base. Always has user_message, fix_hint, docs_url."""
      def __init__(
          self,
          user_message: str,
          *,
          fix_hint: str,
          docs_url: str,
          asset: str | None = None,
          cause: Exception | None = None,
      ) -> None: ...
  ```
- **Enforcement**: `scripts/check_error_translation.py` greps `raise dagster.` outside `coordination/`.

### §4.2 Three-field error contract
- **Decision**: Every NucleusError must have:
  1. **user_message** — what went wrong in user language
  2. **fix_hint** — what to do about it
  3. **docs_url** — link to the relevant docs page
- **Why**: Errors as UX. Without a fix hint, an error is a riddle.
- **Test**: `tests/test_errors.py` enumerates every error and asserts all three fields populated.

### §4.3 Never swallow exceptions
- **Decision**: `except Exception` → either re-raise as NucleusError with `cause=`, or log + re-raise. Never bare `except:` or `except: pass`.
- **Why**: Silent failures cost more than crashes.
- **Enforcement**: `ruff` rules `B902`, `BLE001`.

### §4.4 Assertion policy
- **Decision**: `assert` only in tests. In `src/`, raise explicit errors. (asserts get optimized away with `-O`.)
- **Why**: Production code must work in `python -O` mode.

---

## §5. Logging & observability

### §5.1 Structured logging via `structlog`
- **Decision**: All logs go through `structlog`. **No `print()` statements** in `src/` outside CLI output.
- **Why**: Structured logs queryable in production. `print` is fire-and-forget.
- **Setup**: `nucleus.logging.configure()` called once at CLI/SDK entry points.
- **Convention**:
  ```python
  import structlog
  log = structlog.get_logger(__name__)
  log.info("asset.materialized", asset=name, rows=count, duration_ms=ms)
  ```

### §5.2 Log event naming
- **Decision**: Event names are `noun.verb` past-tense: `asset.materialized`, `commit.failed`, `query.executed`.
- **Why**: Searchable. Future log aggregators expect this format.

### §5.3 No PII in logs
- **Decision**: Never log raw row data, query parameters from users, or credentials. **Log shapes, not values.** ("rows=1000", not "row[0]={'email': 'a@b.com'}")
- **Why**: GDPR, SOC2, basic hygiene.

### §5.4 OpenTelemetry tracing
- **Decision**: Use OTel spans for any operation >100ms candidates (materialization, ingestion, query). One span per asset run.
- **Why**: Single tracing standard wins. Constraint #7.

---

## §6. Testing

### §6.1 Test framework
- **Decision**: `pytest` only. No unittest. No nose.
- **Why**: One framework. Modern. Better fixtures.

### §6.2 Test layout
- **Decision**: Mirror `src/`:
  ```
  src/nucleus/engines/duckdb_engine.py
  tests/engines/test_duckdb_engine.py
  ```
- **Why**: Easy to find. Easy for AI to scaffold.

### §6.3 Coverage thresholds
- **Decision**:
  - **70% line coverage** at Tier 0/1.
  - **80%** at Tier 2.
  - **85%+ on `ctx/` and `coordination/` always** (the boundary layers).
  - **100% on error translation paths**.
- **Why**: Coverage isn't quality but lack of coverage is a smell.
- **Enforcement**: `pytest --cov-fail-under=70`. Increase per tier.

### §6.4 Test types & markers
- **Decision**: Four test types, marked explicitly:
  - **unit** (default, no marker): pure logic, no I/O, <100ms each.
  - **integration** (`@pytest.mark.integration`): real dependencies (Postgres testcontainer, real Iceberg catalog).
  - **slow** (`@pytest.mark.slow`): >5s. Run nightly, not on every PR.
  - **poc** (`@pytest.mark.poc`): Proof-of-Concept validations. Must pass before promoting to v0.1.
- **Why**: Fast feedback. CI splits by marker.

### §6.5 Fixture conventions
- **Decision**:
  - Use `pytest-testcontainers` for Postgres, MinIO.
  - Iceberg catalog: `tmp_path` for filesystem catalog tests.
  - **No mocking of internal Nucleus code**. If you need to mock, your design is wrong.
  - Mock only external services (HTTP, S3 in unit tests).
- **Why**: Mock-heavy tests test mocks, not code.

### §6.6 Property-based testing for type mappings
- **Decision**: Use `hypothesis` for type round-trips (Postgres→Iceberg→Polars→DuckDB). See [`docs/patterns/type_mapping.md`](../patterns/type_mapping.md).
- **Why**: Type bugs are subtle. Property tests find them.

### §6.7 Snapshot tests for SQL output
- **Decision**: `ctx.sql` Jinja resolver output gets snapshot-tested via `syrupy`.
- **Why**: Regressions in resolution are silent and bad. Snapshots catch them.

---

## §7. Interfaces & abstractions

### §7.1 Protocols over ABCs
- **Decision**: Use `typing.Protocol` for interfaces. Avoid `abc.ABC` unless we need runtime registration.
- **Why**: Structural typing. No inheritance tax. Plays well with mypy.

### §7.2 Engine interface
- **Decision**: Every engine implements `nucleus.engines.Engine` Protocol:
  ```python
  class Engine(Protocol):
      name: ClassVar[str]
      def execute(self, plan: Plan, ctx: ExecContext) -> Arrow: ...
      def capabilities(self) -> EngineCapabilities: ...
  ```
- **Why**: Swap targets per Constraint #9. Smoke test (not full alt impl) keeps us honest.

### §7.3 No "convenience" methods
- **Decision**: SDK methods do **one thing**. No `ctx.sql_and_save_and_email_me(...)`.
- **Why**: Composability. Read-write split. Easy to test.

### §7.4 Keyword-only arguments past 2
- **Decision**: Functions with >2 args force keyword-only after the second:
  ```python
  def copy_from(source: str, *, table: str, target: str, ...): ...
  ```
- **Why**: Call sites stay readable. Refactor-safe.

---

## §8. Configuration

### §8.1 Config file format
- **Decision**: TOML for all project config (`nucleus.toml`, `pyproject.toml`). YAML only when an external tool demands it (Dagster, MkDocs). JSON only for inter-process payloads.
- **Why**: TOML is Python-native (PEP 680). No surprises (vs YAML).

### §8.2 Settings via Pydantic v2 or msgspec
- **Decision**: All loaded config goes through a Pydantic/msgspec model. **Never `dict[str, Any]`.**
- **Why**: Validation at the edge. Errors close to the source.

### §8.3 Env var precedence
- **Decision**: CLI flag > `.env.local` > `.env` > defaults. **No global config in `~/.nucleus/`** (v0.1).
- **Why**: Repo-portable. Reproducible. CI-friendly.

### §8.4 Secrets handling
- **Decision**: Never log, never serialize, never embed in stack traces. `pydantic.SecretStr` or `msgspec` `Secret` wrapper.
- **Why**: Constraint #5 (security). PoC #5 (external testers) will probe this.

---

## §9. Documentation

### §9.1 Docstring style
- **Decision**: Google-style docstrings. Examples in `>>>` doctest format where they fit.
- **Why**: One style. mkdocs-material renders it well. AI assistants understand Google style best.

### §9.2 Every public function has a docstring
- **Decision**: Public = not prefixed `_`. **Every public symbol in `ctx/` and `cli/` has a docstring.** Internal docstrings recommended, not required.
- **Why**: Workbench v0.2 surfaces these.
- **Enforcement**: `ruff` rule `D100`, `D102` on `src/nucleus/ctx/` and `src/nucleus/cli/`.

### §9.3 Examples in docstrings must be tested
- **Decision**: Any `>>>` example must pass under `pytest --doctest-modules`.
- **Why**: Stale examples are landmines.

### §9.4 ADRs (Architecture Decision Records)
- **Decision**: Every cross-module decision, every dependency change, every API change gets an ADR in `docs/decisions/`. Number them sequentially: `ADR-001-*.md`.
- **Why**: Future-you needs the "why".
- **Template**: [`docs/decisions/_template.md`](../decisions/_template.md).

---

## §10. Version control

### §10.1 Commit message style
- **Decision**: Conventional Commits. `<type>(<scope>): <subject>` (subject ≤72 chars).
  - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`, `style`, `revert`.
  - Scope: package name (`ctx`, `cli`, `engines`, `coordination`, …).
- **Why**: Generates changelogs. Easy to skim. Allows automated semver bumps later.
- **Examples**:
  ```
  feat(ctx): add ctx.copy_from for Postgres ingestion
  fix(coordination): translate Dagster DagsterExecutionStepNotFound to NucleusAssetNotFound
  docs(adr): record decision to defer Lakekeeper to v0.3
  ```

### §10.2 Branch naming
- **Decision**: `<type>/<short-description>` — `feat/copy-from`, `fix/iceberg-commit-retry`. Lowercase, hyphenated.
- **Why**: Sortable. Searchable.

### §10.3 PR size
- **Decision**:
  - **Target**: ≤300 lines changed.
  - **Hard limit**: 600 lines (excluding tests + generated files).
  - PRs over the limit must be split or have an exception in the description.
- **Why**: Review quality dies past 300 lines. AI-generated PRs notoriously balloon.
- **Enforcement**: GitHub action warns at 300, fails at 600.

### §10.4 PR template
- **Decision**: Every PR uses `.github/PULL_REQUEST_TEMPLATE.md`. Required sections:
  - Why (link issue/ADR)
  - What changed (summary)
  - How tested
  - Constraint check (which of the 11 are touched)
  - LOC budget (cumulative module sizes after merge)
- **Why**: Forces self-review.

### §10.5 No force-push to main
- **Decision**: `main` is protected. Squash merges only. No rebase-and-merge in this repo.
- **Why**: Linear history. Easy bisect.

---

## §11. Performance & resource use

### §11.1 Memory budgets
- **Decision**: Default operations must work in **8 GB RAM**. 16 GB-only operations require an explicit `--large` flag or doc note.
- **Why**: Beachhead persona uses laptops. Local-first guarantee.

### §11.2 Cold-start budget
- **Decision**: `nucleus up` must complete in <10s on a 2020 laptop. PoC #4 enforces this.
- **Why**: Local-first means *fast* local-first. Slow local = no one uses it.

### §11.3 Streaming over loading
- **Decision**: When processing >100 MB, use streaming (Arrow RecordBatch iteration, Polars `scan_*`, Iceberg incremental reads). Never `read_all().to_pandas()`.
- **Why**: Memory bombs are the #1 source of "but it worked on my laptop".

### §11.4 Zero-copy across engines
- **Decision**: Data flowing between DuckDB ↔ Polars ↔ Arrow uses zero-copy (PyCapsule, Arrow Stream interface). Never materialize to Pandas as a hop.
- **Why**: That's the *point* of the Arrow Physics layer.

### §11.5 Connection pooling
- **Decision**: Source connections (Postgres, MySQL, …) use SQLAlchemy `QueuePool`. Default pool size 5, max 10. Surface these as `nucleus.toml` settings.
- **Why**: Default is "no pool" which kills sources under concurrent ingestion.

---

## §12. Security

### §12.1 No own auth code
- **Decision**: Never write user authentication. Use OIDC providers (Auth0, Keycloak, AWS Cognito) when needed in Workbench/Cloud. PoC #5 may surface gaps.
- **Why**: Constraint (decided in F2 review). Auth bugs are the worst bugs.

### §12.2 SQL injection prevention
- **Decision**: Use parameterized queries everywhere. Jinja resolver in `ctx.sql` produces parameterized output. **Never f-string interpolation of user values into SQL.**
- **Why**: Top-1 web vuln, still relevant for data tools.
- **Enforcement**: `ruff` rule `S608` (hardcoded SQL queries with f-strings).

### §12.3 File path safety
- **Decision**: Use `pathlib.Path`. Always `.resolve()` paths from user input. Forbid `..` traversal in catalog paths.
- **Why**: Path traversal attacks against catalog/warehouse paths are real.

### §12.4 No dynamic imports of user input
- **Decision**: `importlib.import_module` is forbidden with user-supplied module names. Use explicit allowlist (`ENGINE_REGISTRY = {"duckdb": ..., "polars": ...}`).
- **Why**: RCE.

### §12.5 Dependency vulnerability scanning
- **Decision**: `pip-audit` runs weekly via CI cron. Critical CVEs block merges to main.
- **Why**: Supply chain attacks are now baseline.

---

## §13. AI workflow

### §13.1 Human-author boundary
- **Decision**: Per AGENTS.md §11, humans (solo founder) author by hand:
  - All public API signatures in `ctx/`, `cli/`
  - The Asset Materialization Adapter (`coordination/asset_materialization.py`)
  - The Error Translation table (`coordination/error_translation.py`)
  - All security-sensitive code paths
  - All ADRs
- **AI scaffolds**:
  - Test bodies (after human writes signature + 1 example)
  - Documentation drafts
  - Boilerplate (e.g., dataclass definitions, enum values)
  - Type stubs for wrapped libraries

### §13.2 PR provenance label
- **Decision**: PRs marked with one of: `provenance:human`, `provenance:ai-assisted`, `provenance:ai-bulk`. Bulk-AI PRs require extra review.
- **Why**: Track AI failure modes. Adjust workflow over time.

### §13.3 AI-generated code review checklist
- **Decision**: Every AI-assisted PR must verify:
  1. No invented APIs (functions/classes/parameters that don't exist).
  2. Pinned versions in any dep changes.
  3. NucleusError used (not raw exceptions).
  4. Imports respect layer direction (§3.1).
  5. Module sizes within budget (§2.2).
- **Why**: AI failure modes are predictable. Checklist catches 80%.

### §13.4 Composer / multi-file edits
- **Decision**: Composer-style mass edits limited to:
  - Same-pattern refactors across <10 files (e.g., rename a function used in 8 places).
  - Boilerplate scaffolding from a template.
  - **Never** for cross-layer architectural changes.
- **Why**: Composer makes plausible-but-wrong changes at scale.

---

## §14. Tooling

### §14.1 Package manager
- **Decision**: `uv` for dev environments. `pip` for end users.
- **Why**: `uv` is fast and gets the lockfile-Python-version split right. Don't force end users onto it.

### §14.2 Pre-commit hooks
- **Decision**: `.pre-commit-config.yaml` runs:
  - `ruff check` + `ruff format`
  - `mypy` on touched files
  - `pip-audit` (manual stage)
  - End-of-file fixer, trailing whitespace, YAML/TOML syntax
- **Why**: Catches violations before CI.

### §14.3 CI runner
- **Decision**: GitHub Actions. Matrix on Python 3.11, 3.12 × Ubuntu, macOS. Windows tested on release only.
- **Why**: Solo developer on Windows; bulk users on Mac/Linux.

### §14.4 Docs site
- **Decision**: `mkdocs-material` + `mkdocstrings`. Hosted on GitHub Pages until Cloud launches.
- **Why**: Battle-tested. Looks good. Native markdown.

---

## §15. Naming & terminology

### §15.1 Forbidden terms in code & docs
- **Decision**: These words are banned (Constraint #5 + AGENTS.md §7):
  - "metastore" → use **catalog** <!-- banned-term: metastore -->
  - "data lake" → use **warehouse** or **lakehouse** <!-- banned-term: data lake -->
  - "Spark killer" / "Databricks killer" → use **graduation path** <!-- banned-term: multiple -->
  - "Data OS" → never; we're a platform, not an OS <!-- banned-term: Data OS -->
  - "AI-native" / "AI-first" → use **AI-assisted** <!-- banned-term: multiple -->
- **Enforcement**: `scripts/check_vocabulary.py`.

### §15.2 Domain term mapping
| User says | We say | Reason |
|-----------|--------|--------|
| Table | Asset (when versioned), Table (when raw Iceberg) | Asset = our primitive |
| Job | Materialization run | Dagster term hidden |
| Dag/Pipeline | Asset graph | Asset-centric |
| Worker | (don't say) | We have no workers |
| Cluster | (don't say) | We have no clusters |
| Query | Query (DuckDB), Plan (DataFusion) | Engine-specific |

### §15.3 Asset naming convention
- **Decision**: Assets named `<layer>.<entity>`. Layers: `raw`, `staging`, `marts`, `ops`.
  - `raw.orders`, `staging.customers_cleaned`, `marts.daily_revenue`
- **Why**: Mirrors dbt conventions; immediately familiar.
- **Enforcement**: The asset-name validator helper `ctx.asset_name_valid(name: str) -> bool` enforces the pattern `^(raw|staging|marts|ops)\.[a-z][a-z0-9_]*$`. (This is the validator helper; the **decorator** is `@nucleus.asset` — distinct surfaces.)

---

## §16. Deprecation

### §16.1 Deprecation lifecycle
- **Decision**: All deprecations announce → warn (2 minor versions) → remove (next major).
  - Announce in CHANGELOG and `nucleus.deprecated` decorator.
  - Warning uses `DeprecationWarning` + custom `NucleusDeprecationWarning` for filtering.
- **Why**: Predictable upgrades. Users can plan.

### §16.2 AI APIs special-case
- **Decision**: Per v4.1 §13.3, AI-related APIs (under `ctx.agent`, `ctx.copilot`) may break in minor versions with `NucleusAIBreakingChange` warning instead of full deprecation cycle.
- **Why**: AI paradigms evolve faster than data ones. Flexibility is required to incorporate new model capabilities.

---

## §17. What's NOT in scope (yet)

To keep this document focused, the following are **intentionally deferred**:

- Multi-tenancy (Tier 4+)
- Authorization model (basic ACL in v0.3+)
- Distributed execution (v0.5+ via DataFusion/Daft)
- Plugin marketplace (post-v1.0)
- i18n / l10n (post-v1.0)

When you encounter a need for one of these, raise an ADR rather than improvising.

---

## §18. How to violate this document

You may not. If you have a strong reason:

1. Open an ADR explaining the case.
2. Get approval (currently: solo founder; later: maintainer team).
3. Update this doc with the new convention.
4. Migrate existing code.
5. Then ship the new pattern.

Conventions exist because **drift is fatal at small team size**. Every exception costs more than the inconvenience it avoids.

---

## Appendix A: Version history

| Date | Version | Change | Author |
|------|---------|--------|--------|
| Month 0 (now) | 0.1 | Initial document — 18 sections | Solo founder |

---

*Last reviewed: Month 0. Next review: end of Tier 0.*
