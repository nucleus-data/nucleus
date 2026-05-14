# ADR-005: `ctx` SDK API Freeze Policy

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: api, ctx-sdk, sdk-freeze, governance, hard-constraint-9
> **Related**: ADR-001 (wrap-not-build precedent), ADR-002 §8.2 (data-product definition naming AI agents as consumption surface), ADR-003 (trigger/rollback/downstream pattern), `AGENTS.md` §0 + §3 Constraint #9, `nucleus_architecture_v4.1.md` §3 + §6 + §12 + §13.2 + §13.3 (Amendment 8 REVISED — AI APIs flex faster), `nucleus_ctx_sdk_spec.md` §12 + §16, `docs/architecture/C4_component.md` §2.1-§2.7

---

## Context

Per `AGENTS.md` §0, the `ctx` SDK is the only one of three things Nucleus owns forever that carries a *public Python signature surface*. Every downstream commitment binds to it: user `@nucleus.asset` code (`nucleus_ctx_sdk_spec.md` §15), PoC promotion targets, every wrap-not-build justification (ADR-001, ADR-003), v0.5+ surfaces (`nucleus-mcp-server` per ADR-002 §4.2), the Replaceability Mandate (v4.1 §12 — *library under `ctx` may swap; `ctx` itself must not*).

`nucleus_ctx_sdk_spec.md` §12 currently uses a binary **Frozen / Evolvable** — too coarse for v0.1 APIs that must iterate before locking (`ctx.sql` macros, `ctx.copy_from` modes, flagged open in `C4_component.md` §4); AI APIs v4.1 §13.3 carves out (*"Breaking change allowed in minor — 6-month deprecation window"*); leaked internal helpers (`ctx.dagster_context`, v4.1 §6.6); PoC code under `poc/` that must not be promised as stable.

This ADR replaces the binary with a four-tier ladder + per-family freeze schedule + breaking-change protocol. Forces in tension: **commitment** (dlt v0.3, `nucleus-mcp-server` v0.5, post-v1.0 enterprise adopters need stability promises) vs. **humility** (PoC #1 has not passed); **AI churn** (MCP <12 months old; v4.1 §13.3 + ADR-002 §8.2 authorise faster AI churn) vs. **solo enforcement** (must be CI-enforceable; manual shepherding fails under Mo 24 velocity pressure, ADR-002 §8.3). **Governance, not implementation** — can land before PoC #1.

---

## Decision

> **Four stability tiers. Per-API-family freeze events at v0.5 / v1.0 / v1.5. Breaking changes to Stable + Frozen tiers require deprecation cycle + ADR. AI APIs (`ctx.agent.*`, MCP server) stay Beta through v1.0 and freeze at v1.5 — explicitly authorised by `nucleus_architecture_v4.1.md` §13.3 + ADR-002 §8.2.**

### 1. Stability tiers

| Tier | Backward-compat guarantee | Removal/rename cost |
|---|---|---|
| **Frozen** | v1.x user code runs unmodified through v1.y ∀ y ≥ x | Major bump + 6-month deprecation + ADR |
| **Stable** | v0.x code runs through v0.y with documented escape hatches | Minor cycle + 3-month deprecation + ADR |
| **Beta** | Public but explicitly unstable; may break minor-to-minor | CHANGELOG entry; no ADR required |
| **Internal** | Private (`_internal_*` or omitted from `__all__`) | Anytime |

Every public name in `src/nucleus/__init__.py` `__all__` and every `ctx.*` method MUST carry `# Stability: <tier>` in its docstring (or `__stability__` class attr). Enforced by `scripts/check_api_stability.py`.

### 2. Per-API-family freeze schedule (mapped to `docs/architecture/C4_component.md` §2)

| API family | C4 component | v0.1 | v0.5 | v1.0 | v1.5 | v2.0 |
|---|---|---|---|---|---|---|
| `@nucleus.asset` | §2.1 ctx.asset | Beta | Stable | **Frozen** | Frozen | Frozen |
| `ctx.sql` Jinja resolver | §2.2 ctx.sql | Beta | Stable | **Frozen** | Frozen | Frozen |
| `ctx.read` | §2.3 | Beta | Stable | **Frozen** | Frozen | Frozen |
| `ctx.write` | §2.3 | **DEFERRED (v0.2+)** | Stable | **Frozen** | Frozen | Frozen |
| `ctx.copy_from` | §2.4 | Beta | Stable | **Frozen** | Frozen | Frozen |
| `ctx.log` · `ctx.params` | §2.5 | **DEFERRED (v0.2+)** | Stable | **Frozen** | Frozen | Frozen |
| `ctx.coordination.error_translation` | §2.6 (post-PoC #1) | Internal | Stable | **Frozen** | Frozen | Frozen |
| `NucleusError` subclasses | errors module (`AGENTS.md` §11.7) | Stable | Stable | **Frozen** | Frozen | Frozen |
| OpenLineage facets from `ctx` | lineage module (v4.1 §11) | Beta | Stable | **Frozen** | Frozen | Frozen |
| `@nucleus.check` validators | §2.5-adjacent | Beta | Stable | Stable | **Frozen** | Frozen |
| **`ctx.agent.*`** [^1] | §2.7 | n/a | Beta | Beta | **Frozen** | Frozen |
| **MCP server surface** [^1] | nucleus-mcp-server (ADR-002 §4.2) | n/a | Beta | Beta | **Frozen** | Frozen |
| CLI (`nucleus init/up/down/run/ingest`) | — | governed by `nucleus_cli_spec.md` (NEEDS VERIFICATION — may not yet exist) |

[^1]: **AI-API carve-out.** Primary authority: v4.1 §13.3 (*"Breaking change allowed in minor — 6-month deprecation window"* for AI APIs). Reinforced by ADR-002 §8.2 (data product defined as "consumable by ... AI agents via the `ctx` SDK or the MCP server"). AI surfaces lag peers by one release; freeze when upstream AI ecosystem stabilises.

The `nucleus_ctx_sdk_spec.md` §12 binary "Frozen Surface (v1.0)" framing is **superseded** by the table above; the §12 list of names stays.

### 3. Breaking-change protocol (Stable + Frozen only)

1. **Open a numbered ADR** (`ADR-NNN-breaking-<api>.md`) — what changes, why, who's affected, CHANGELOG cross-ref.
2. **Ship `DeprecationWarning`** on the old API in the next minor; document the replacement in the same release notes.
3. **Wait the window** — Stable: 1 minor *or* 3 months (longer wins). Frozen: 1 major *or* 6 months (longer wins). AI-carved APIs use the §13.3 6-month window even pre-v1.5.
4. **Remove the old API** in the next minor (Stable) or next major (Frozen).
5. **Cite ADR + migration path** in `CHANGELOG.md`.

### 4. Carve-outs

**AI APIs** — Beta through v1.0 (v4.1 §13.3 + ADR-002 §8.2); hard freeze at v1.5. **`@nucleus.check`** — Stable not Frozen until v1.5 (validator API needs production telemetry, `AGENTS.md` §11.8). **CLI surface** — governed separately; this ADR scopes the Python SDK only. **`ctx.dagster_context` escape hatch** (v4.1 §6.6) — provisionally Internal forever; never promoted.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Freezing too early** locks in poorly-chosen names (e.g., `ctx.copy_from` may be wrong shape for incremental ingestion) | Beta through v0.1 → v0.5 (one year to iterate); Beta renames freely with CHANGELOG entry. |
| **Freezing too late** — post-v1.0 enterprise adopters decline because no stability promise | v1.0 = hard Frozen line for non-AI surfaces; Workbench (v0.2+) targets the Frozen subset only. |
| **AI ecosystem upheaval** (MCP loses; LLM provider SDK breaks) forces unplanned churn | AI carve-out + freeze pushed to v1.5 per v4.1 §13.3 + ADR-002; Beta status documents breakage as expected. |
| **Solo founder cannot enforce 3-/6-month cycles** under Mo 24 velocity pressure | `scripts/check_api_stability.py` flags expired `# Deprecated since vX.Y; remove vA.B` markers + 4-weekly Drift Detection Pass. |
| **Tier annotations drift** (docstring says Stable; behaviour breaks across minors) OR **Internal leaks to public** via user discovery (`from nucleus._internal import …`) | `tests/api_stability/test_signatures.py` snapshots per tier (Frozen sig change = red CI); `_internal_*` naming + CI assert `__all__` set in every public module. |

---

## Verification plan

1. **`scripts/check_api_stability.py`** (~100 LOC) — scans `__all__` + every `ctx.*` method; missing/mismatched `# Stability:` tags = red CI. Hooked into `.github/workflows/ci.yml` alongside `check_vocabulary.py`.
2. **`tests/api_stability/test_signatures.py`** — `inspect.signature()` snapshots per tier; Frozen change = red without co-landing breaking-change ADR.
3. **`nucleus_ctx_sdk_spec.md` annotation pass** — every name in §12 + §13 gets a tier tag; binary header replaced by §2 table. Landed by v0.5 spec lock.

`CHANGELOG.md` discipline: every release notes which tier moved (e.g., `ctx.sql.macros: Beta → Stable, see ADR-NNN`) and which ADR triggered it.

---

## Rollback

- **Too strict** (6-month Frozen window blocks a security fix): `ADR-005a` *demotes* one tier (Frozen → Stable).
- **Too loose** (v1.0 not enforced rigorously): `ADR-005b` *promotes* a tier (e.g., AI APIs Beta → Stable earlier than v1.5) with 6-month notice if v1.0+ users affected.
- **No emergency rollback.** Per `AGENTS.md` §9, API governance crises are "pause and escalate" — structural, not tactical (ADR-001 + ADR-003 precedent).

---

## Docs URL

- `AGENTS.md` §0 (founding principle: we own `ctx` forever) + §3 Constraint #9 (swap interface + smoke tests)
- `nucleus_architecture_v4.1.md` §12 (Replaceability Mandate) + §13.3 (primary authority for the AI carve-out)
- ADR-002 §8.2 (data-product definition recognises AI agents + MCP server as a consumption surface)
- `nucleus_ctx_sdk_spec.md` §12 + §16 (the API catalog this ADR governs)
- `docs/architecture/C4_component.md` §2 (component-to-API-family mapping; source of §2 schedule)

---

## Trigger

Status flips **PROPOSED → ACCEPTED** when all three hold: (1) founder reviews + signs off (or amends, ADR-002 §6 pattern); (2) `scripts/check_api_stability.py` lands (~100 LOC; can ship before PoC #1); (3) `nucleus_ctx_sdk_spec.md` annotated with stability tiers (~30 min editing; may defer to v0.5 spec lock).

**Not gated on PoC #1.** If accepted pre-PoC-#1, the **Internal** tier protects `poc/*` code from being interpreted as a public API promise.

---

## Downstream consumers

| Consumer | Tier inherited | When affected |
|---|---|---|
| PoC #1 promotion → `src/nucleus/coordination/error_translation.py` | Internal @ v0.1 → Stable @ v0.5 → Frozen @ v1.0 | At promotion + each tier transition |
| PoC #2 (`ctx.sql`) / PoC #3 (`ctx.copy_from`) | Beta @ v0.1 → Stable @ v0.5 | At v0.5; macros (q#3) and mode taxonomy (q#4) finalised per `C4_component.md` §4 |
| Workbench (v0.2+) | Frozen subset only | Tests Frozen subset as its public contract |
| Cloud Copilot + `nucleus-mcp-server` (v0.5+) | Beta `ctx.agent.*` + Beta MCP | Flexes faster per v4.1 §13.3 |
| External integrations (post-v1.0) | Frozen only; Beta requires `--unstable-api` CLI flag | Hard gate at v1.0 |
| ADR-003 PyIceberg upgrade | `ctx` surface unaffected — v4.1 §12 isolates physics churn | Validates this ADR's premise |

---

## NEEDS VERIFICATION

1. **`ctx.snapshot` tier mismatch** — `nucleus_ctx_sdk_spec.md` §10+§12 list it Frozen-at-v1.0; `C4_component.md` §2 omits it (v0.3+ per v4.1 §13.2). Provisionally tiered Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0; reconcile at v0.5 spec lock.
2. **`nucleus_cli_spec.md`** — referenced as the source of CLI governance but **not found in repo** (Glob returned no match). CLI carve-out is currently rhetorical; doc should land alongside this ADR's acceptance.
3. **`ctx.agent.*` signatures** — per `C4_component.md` §2.7 + §4 q#1, signatures themselves are NEEDS VERIFICATION; this ADR tiers the family without locking signatures (lock at v0.5 design).
4. **`ctx.copy_from` mode taxonomy** — per `C4_component.md` §4 q#4, `mode="append"` v0.1-vs-v0.3 is open; Beta tier covers either outcome.
5. **`ctx.dagster_context` escape hatch** — provisionally Internal forever; may warrant an explicit "Tier 2 escape hatch" designation if user demand emerges post-v1.0.

---

*ADR-005 governs the API surface that `AGENTS.md` §0 names as one of the three things Nucleus owns forever. It binds no code yet; it binds every code-shaping decision after acceptance.*

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.

**Amended**: 2026-05-14 — `ctx.write`, `ctx.log`, and `ctx.params` are **not** part of the v0.1 exported SDK surface (`src/nucleus/ctx/__init__.py` / `__all__`). Per `nucleus_architecture_v4.1.md` §13.1 (contracted `ctx` exports), their prior §2 schedule placement next to `ctx.read` implied upcoming Beta work; **status is now DEFERRED to v0.2+** with practical substitutes already documented in the ctx module docstring: materialization return values (instead of `ctx.write`), stdlib `logging` (instead of `ctx.log`), CLI / project config (instead of `ctx.params`). The §2 table rows above are updated; freeze-track columns after v0.2 remain the target once each symbol ships.
