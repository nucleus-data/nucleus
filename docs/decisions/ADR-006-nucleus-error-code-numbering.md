# ADR-006: NucleusError Error Code Numbering Scheme

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: errors, governance, api-stability, error-translation
> **Related**: ADR-001 (catalog-delegated commits emit `NucleusCommitConflictError` / `NucleusCommitUnknownError`), ADR-002 §8.1 L3 + §8.2 (codes are part of the data-product / MCP contract), ADR-005 (`ctx` SDK API freeze — citation only; this is its "errors" companion), AGENTS.md §11.7, `docs/specs/nucleus_architecture_v4.1.md` §3.1 + §6.4, `poc/p1_error_translation/`

## Context

PoC #1 (Dagster Error Translation Layer) is one PR from promoting `poc/p1_error_translation/translator.py` into `src/nucleus/coordination/error_translation.py`. Current shape: **17 handler paths** (baseline Dagster handler with 3 inner-cause branches + 14 wrapped-library handlers) mapping external exceptions from Dagster / Polars / DuckDB / pyiceberg + three stdlib types onto **12 distinct `NucleusError` subclasses**.

Once promotion lands the error classes become **public contract**: users grep logs, `docs_url` deep-links, AI Copilot (v0.3+) and MCP server (v0.5+, ADR-002 §4.2) map identifiers to fix steps, support tickets cite them. The v4.1.2 note in v4.1 §6.4 and `errors.py:23-28` both **defer** numeric codes to post-v0.5 because the translator catalog had not stabilized — **deferral predates PoC #1's 17-handler catalog finishing**. The first ad-hoc identifier that escapes a release becomes permanent by accident. This ADR brings the scheme forward into the promotion PR, **before any code escapes**.

## Decision

> **Hierarchical 6-character codes `NE[L][CCC]` where `NE` = Nucleus Error, `L` ∈ `1..5` = layer prefix, `CCC` ∈ `000..999` = monotonic category. Codes are PERMANENT from first release. Reusing / renumbering forbidden. Errors deprecate via a `deprecated_in` field + ADR; the code itself is never recycled.**

1. **Permanent from first release.** Once `NE3001` ships in v0.1.0 it points to `NucleusInternalError` forever.
2. **Monotonic per layer.** `NE1001`, `NE1002`, `NE1003`… No gaps reserved. Deprecation gaps stay gaps.
3. **One code per subclass.** Handlers MAY share a code by routing to the same subclass (e.g. `pyiceberg.CommitFailedException` + `duckdb.TransactionException` both → `NucleusCommitConflictError` → `NE1002`). Class docstring documents the code.
4. **Deprecation.** Add `deprecated_in: ClassVar[str | None]` + docs entry. Code stays unreused. ADR records the reason.
5. **AI-flexed errors** (`ctx.agent.*`, v0.5+) live in `NE4xxx`, follow ADR-005's Beta tier: wording MAY change until v1.5 freeze; **code-to-class binding is permanent** from first ship.

**Layer prefix mapping (cite v4.1 §3.1).** v4.1 §3.1 numbers bottom-up `L0..L4`. Codes shift **+1** so `NE0xxx` stays reserved (`NE0000` would read "null / uninitialized" in CLI output). Offset documented once here.

- `NE1xxx` = **L0 Physics** (Iceberg, Parquet, Arrow, S3, network IO)
- `NE2xxx` = **L1 Engines** (DuckDB, Polars; future DataFusion/Daft — compute, parse/bind/plan, in-engine resource limits)
- `NE3xxx` = **L2 Coordination** (asset graph, Dagster wrap, contracts, lineage, translator itself)
- `NE4xxx` = **L3 Intelligence** (AI Copilot v0.2+, `ctx.agent` v0.5+) — **range accepted 2026-05-13 via ADR-015 ratification; same-PR co-amendment per `docs/FOUNDER_ACTION_QUEUE.md §0`**
- `NE5xxx` = **L4 Experience** (`ctx` SDK, CLI, Workbench, Marimo)

**NE4xxx initial allocation (ADR-015, 2026-05-13):**

| Code | Class | Trigger |
|---|---|---|
| `NE4001` | `NucleusCopilotAuthError` | Provider auth failure (HTTP 401/403) |
| `NE4002` | `NucleusCopilotRateLimitError` | Provider rate-limit (HTTP 429) |
| `NE4003` | `NucleusCopilotProviderError` | Provider 5xx / unmapped error |
| `NE4004` | `NucleusCopilotContentFilterError` | Content policy violation |
| `NE4005` | `NucleusBudgetExceededError` | Pre-flight cost > ceiling (never reaches HTTP) |

**Semantic over source.** When exception SOURCE and user-meaningful SEMANTIC layer differ (e.g. `duckdb.CatalogException` raised at L1 but means "asset not registered" at L2), classify by SEMANTIC layer. Subclass docstring records both.

## Initial code assignment — PoC #1 17 handlers

Source: `poc/p1_error_translation/translator.py` (handler line numbers in column 2); wording review in `poc/p1_error_translation/REVIEW_NOTES.md`. **Bold** = first allocation.

| # | `:line` | External exception (or inner-cause) | `NucleusError` subclass | Code |
|---|---|---|---|---|
| H1 | :80 | `dagster.DagsterExecutionStepExecutionError` → inner `ConnectionError` | `NucleusSourceConnectionError` | **NE1001** |
| H2 | :87 | _idem_ → inner `TypeError`/`ValueError` w/ "schema" | `NucleusSchemaError` | **NE2001** |
| H3 | :94 | _idem_ → fallback | `NucleusInternalError` | **NE3001** |
| H4 | :109 | `polars.SchemaError` | `NucleusSchemaError` | NE2001 |
| H5 | :119 | `polars.ColumnNotFoundError` | `NucleusSchemaError` | NE2001 |
| H6 | :129 | `duckdb.BinderException` | `NucleusSchemaError` | NE2001 |
| H7 | :139 | `duckdb.CatalogException` | `NucleusAssetNotFound` | **NE3002** ¹ |
| H8 | :149 | `duckdb.ParserException` | `NucleusSQLSyntaxError` | **NE2002** |
| H9 | :189 | `duckdb.OutOfMemoryException` | `NucleusResourceError` | **NE2003** |
| H10 | :199 | `duckdb.TransactionException` | `NucleusCommitConflictError` | **NE1002** ² |
| H11 | :159 | `pyiceberg.NoSuchTableError` | `NucleusAssetNotMaterialized` | **NE3003** ¹ |
| H12 | :169 | `pyiceberg.CommitFailedException` | `NucleusCommitConflictError` | NE1002 |
| H13 | :209 | `pyiceberg.CommitStateUnknownException` | `NucleusCommitUnknownError` | **NE1003** |
| H14 | :219 | `pyiceberg.ValidationError` | `NucleusSchemaEvolutionError` | **NE1004** |
| H15 | :179 | `FileNotFoundError` | `NucleusIOError` | **NE1005** |
| H16 | :229 | `PermissionError` | `NucleusPermissionError` | **NE1006** |
| H17 | :239 | `TimeoutError` | `NucleusSourceConnectionError` | NE1001 ³ |

¹ Semantic-over-source: raised at L0/L1, classification follows asset-graph (L2) concern; docstring records both.  ² NEEDS VERIFICATION #1.  ³ NEEDS VERIFICATION #2.

**Unique codes: 12** (`NE1001`–`NE1006`, `NE2001`–`NE2003`, `NE3001`–`NE3003`). **Handler rows: 17.** Five handler pairs share a subclass and therefore correctly share a code. **Handler-row distribution**: 8× `NE1xxx` · 6× `NE2xxx` · 3× `NE3xxx` · 0× `NE4xxx` · 0× `NE5xxx`.

### NEEDS VERIFICATION (founder, before promotion)

1. **H10 — `NucleusCommitConflictError` straddles L0 and L1.** Iceberg commit conflict (H12, L0 Physics) + DuckDB `TransactionException` (H10, the engine's connection transaction, L1 Engines) both → one class → `NE1002`. Merge mirrors user-facing semantics ("concurrent write conflicted with yours") but blurs an architecturally real boundary. Options: (a) keep merged at `NE1002`, document both source layers in class docstring; (b) split `NucleusEngineTransactionError` out (new `NE2004`). Recommendation: (a) for v0.1, revisit on telemetry. `errors.py` split work out of scope here.
2. **H17 — routing already contested.** `REVIEW_NOTES.md` H14 flags that builtin `TimeoutError` fires from non-source paths; current `NucleusSourceConnectionError` route is provisional. If founder accepts `REVIEW_NOTES.md` Option B (split → `NucleusTimeoutError`), the new class claims a new code (likely `NE2004` engine or `NE3004` run-budget). Routing and code-allocation move together.

## Reserved ranges

- **`NEx900`–`NEx999`** (every layer) — **internal**, never user-facing. Surfacing one in a CLI message is a release blocker.
- **`NE4xxx`** — **Beta tier per ADR-005** until v1.5: wording MAY change between minor versions; code-to-class binding stays permanent.
- **`NE0xxx`** — never allocated. Keeps "uninitialized / null" semantics safe in tooling.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Two classes assigned same code (parallel PRs) | `scripts/check_error_codes.py` AST-walks `errors.py`, asserts `error_code: ClassVar[str]` matches `^NE[1-5]\d{3}$`, fails on duplicates. CI-enforced. |
| Layer assignment wrong (NE2 vs NE3) | Each subclass docstring cites chosen v4.1 §3.1 layer + source-exception types. Drift Detection (AGENTS.md §11.11) spot-checks quarterly. |
| Renumbering temptation during refactor | "Permanent" enshrined in §Decision. CI check diffs `git show HEAD~1:src/nucleus/errors.py`, asserts no removed-then-readded codes. |
| AI Copilot hallucinates `NE9999` in user output | Workbench (v0.2+) renders live valid-code set via runtime introspection; out-of-set flagged. CLI `nucleus errors list` (v0.2+) prints registry. |
| Premature codification (v4.1 §6.4 defers numbering to post-v0.5) | Scope minimised: only the 12 PoC #1 codes lock now; other subclasses light up codes as handlers appear. `deprecated_in` + no-renumbering means a regretted code becomes a gap, not a refactor. |

## Verification plan

1. **`scripts/check_error_codes.py`** (~80 LOC, new) — AST walk; asserts every `NucleusError` subclass has `error_code: ClassVar[str]` matching `^NE[1-5]\d{3}$`; no duplicates; no `^NEx9\d{2}$` referenced from default-emission paths. Wired into `.github/workflows/ci.yml` alongside `scripts/dagster_leak_check.py` + `scripts/check_vocabulary.py`.
2. **`docs/errors/<code>.md`** — one markdown per code (meaning, triggers, fix steps). Hand-written stubs at v0.1 for the initial 12. Generator `scripts/generate_error_docs.py` reads class docstrings — **NEEDS VERIFICATION, deferred to v0.2** when Workbench docs surface lands.
3. **`CHANGELOG.md`** — every new code logged under an "Errors" subheading (`+ NE2004 NucleusEngineTransactionError`); deprecations logged identically (`~ NE2003 → deprecated in v0.7`).
4. **`scripts/check_vocabulary.py` extension** — detect raw external classnames (`dagster.`, `duckdb.`, `polars.`, `pyiceberg.`) in any `user_message=` literal across `src/nucleus/`. Consolidates partial logic from PoC #1's `dagster_leak_check.py`.

## Rollback

If the scheme proves too rigid (e.g. telemetry shows the L0-vs-L1 boundary confuses >10% of incidents), file **ADR-006a** to relax: cross-layer `NE0xxx` band; per-class `aliases: list[str]`. **Renumbering remains forbidden under any rollback** — codes are immortal even if the scheme above them changes. Codes live in class definitions; no data migration.

## Docs URL · Trigger · Downstream

**Docs**: AGENTS.md §11.7 · v4.1 §3.1 + §6.4 (v4.1.2 deferral note amended on acceptance) · `src/nucleus/errors.py:23-28` ("NUC-XXX deferred" docstring rewritten on acceptance) · ADR-001 §Consequences · ADR-002 §8.1 L3 + §8.2 · ADR-005 (Beta-tier `NE4xxx`, citation only).

**Trigger** (PROPOSED → ACCEPTED when all three hold):

1. Founder signs off on NEEDS VERIFICATION #1 + #2.
2. `scripts/check_error_codes.py` lands + wired into `.github/workflows/ci.yml`.
3. PoC #1 promotion PR adds `error_code: ClassVar[str]` to each of the 12 subclasses, rewrites `errors.py:23-28`, amends v4.1 §6.4 v4.1.2 note.

Not a calendar date. If PoC #1 fails 17/17 (v4.1 §6.4 / Appendix C), this ADR pauses with it — no codes ship without a passing translator.

**Downstream consumers**:

| Consumer | When | Dependency |
|---|---|---|
| PoC #1 promotion PR | Mo 2-3 | Adds `error_code` `ClassVar` to 12 subclasses; only `errors.py` touch beyond translator move |
| Future `NucleusError` subclasses | Always | Inherit scheme; CI check enforces |
| `docs/errors/` stubs (hand-written) | v0.1 (Mo 4) | 12 markdown files for initial codes |
| `docs/errors/` (auto-generated) | v0.2 (Mo 4-8) | `scripts/generate_error_docs.py` replaces v0.1 stubs |
| AI Copilot (v0.3+) + MCP server (v0.5+) | Mo 14-20 | Code → fix-step lookup feeds v4.1 §7 + ADR-002 §4.2 |
| Workbench errors panel (v0.2+) | Mo 4-8 | Renders code + class + fix_hint + docs_url per `errors.py:106` `rendered()` |

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
