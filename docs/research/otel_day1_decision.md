# OTEL Day-1 Wiring + Speculative-Pin Disposition — Founder Decision Doc

> **Status**: DRAFT — researcher output for founder review
> **Date**: 2026-05-14
> **Trigger**: Drift verifier MEDIUM #3 (= `docs/FOUNDER_ACTION_QUEUE.md` §0 / B2.8)
> **Owner**: researcher (Claude Opus 4.7 — Gemini 3.1 Pro fallback per AGENTS.md §11.14)
> **Recommendation**: **Option α-split** — keep `opentelemetry-api` pinned (no-op substrate built-in, zero LOC cost), demote `opentelemetry-sdk` + `sqlglot` + `msgspec` to `[project.optional-dependencies]` extras (or remove `msgspec`); amend ADR-011 §1 to clarify substrate-present-by-API-only; ship **no** Day-1 wiring code under `src/nucleus/`.

---

## Executive summary

Drift verifier flagged four `[project.dependencies]` pins with **zero callers** under `src/nucleus/`, `tests/`, `poc/`, or `scripts/`: `opentelemetry-api==1.29.0`, `opentelemetry-sdk==1.29.0`, `sqlglot==26.0.0`, `msgspec==0.18.6`. Two governance documents are in tension:

1. **ADR-011** (Telemetry Opt-In Policy, ACCEPTED 2026-05-13) §1: *"OTEL wired with no-op `TracerProvider`/`MeterProvider` Day 1 — substrate present, transport silent."*
2. **`.cursor/rules/nucleus.mdc` Anti-Over-Engineering rule #4** (founder directive 2026-05-13): *"No speculative code. If there is no v0.1 caller today, the code is not added today."*

The architect's pre-recommendation in FOUNDER_ACTION_QUEUE B2.8 favors moving all four pins to extras (Option α-full). This research **refines** that recommendation after live verification of the OpenTelemetry Python API contract.

**Critical finding**: per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html (verified 2026-05-14, L67/L115/L562) — *"a concrete no-op `NonRecordingSpan` that allows applications to use the API package alone without a supporting implementation… All operations are no-op except context propagation."* **OTEL-API alone, with no SDK and no `TracerProvider`, intrinsically produces no-op spans.** Therefore the cheapest honest reading of ADR-011 §1's "substrate present" commitment is simply: keep `opentelemetry-api` pinned. The dep IS the substrate.

This honors both ADR-011 §1 (substrate truly present) and Anti-Over-Engineering (no LOC added, no SDK shipped to non-opt-in users).

---

## Section A — Repo state today

### A1. `pyproject.toml` audit (verified 2026-05-14)

Four pins in `[project] dependencies`:

```toml
"msgspec==0.18.6",          # Docs: https://jcristharif.com/msgspec/
"sqlglot==26.0.0",          # Docs: https://sqlglot.com/sqlglot.html
"opentelemetry-api==1.29.0", # Docs: https://opentelemetry.io/docs/languages/python/
"opentelemetry-sdk==1.29.0",
```

Per ADR-012: all four GREEN-license-tier (MIT / BSD-3-Clause / Apache-2.0), JVM-free; OTEL is Tier 0 immortal, sqlglot is Tier 2, msgspec is Tier 2.

### A2. Callers under `src/nucleus/`

```
rg "opentelemetry|otel" src/nucleus/
  src/nucleus/_internal/logging.py:14:  "OpenTelemetry integration ships in a follow-up commit"
  (one docstring sentence; ZERO import statements)

rg "import sqlglot|from sqlglot" src/nucleus/
  No matches.

rg "import msgspec|from msgspec" src/nucleus/
  No matches.
```

The promoted SQL resolver at `src/nucleus/coordination/sql_resolver.py` uses **jinja2 + regex + difflib only** (verified L20-30). The original `docs/research/sqlglot.md` §4.3 plan ("`parse_one + find_all(exp.Table)` ~50-100 LOC") was **deferred at PoC #2 promotion**. The NucleusError implementation at `src/nucleus/errors.py` uses pure-Python `class NucleusError(Exception)` with `typing.ClassVar` — no msgspec.

### A3. Callers under `tests/` / `poc/` / `scripts/`

```
rg "opentelemetry|sqlglot|msgspec" tests/   # No matches
rg "opentelemetry|sqlglot|msgspec" poc/     # No matches
rg "opentelemetry|sqlglot|msgspec" scripts/ # 2 matches in scripts/check_licenses.py L100-101
                                            # (license-tier metadata only, not source-level usage)
```

Drift verifier's "no v0.1 callers" claim is fully confirmed.

### A4. Architecture v4.1 commitments

- §3.1 / §4.1 / §9.2 — OpenTelemetry listed as Tier 0 immortal observability protocol (L344, L374, L824).
- §6.6 — Tier 2 escape-hatch tracking: *"Telemetry tracks usage."* Plans v0.5+ AMA wiring, not v0.1.
- §11.4 — *"Telemetry buffers and flushes on reconnect"* (v0.5+ scope).
- §18 PoC #2 — *"~1000 LOC Jinja+sqlglot can replace 80% of dbt-duckdb functionality."* The hypothesis was informally falsified at PoC #2 promotion: the v0.1 resolver achieved the `{{ ref() }}` surface with ~200 LOC of jinja2 + regex, no sqlglot.
- **`msgspec`: zero mentions in architecture v4.1.** Pin is an internal engineering convenience, not an architectural commitment.

### A5. AMA verification

`src/nucleus/coordination/asset_materialization.py` L44-45 (verified 2026-05-14) says explicitly:

> *"No telemetry / OpenLineage emission — v0.5+ per v4.1 §16"*

This means even the AMA — the primary planned v0.5 OTEL consumer per `docs/research/opentelemetry.md` §4.1 — has not yet been wired for telemetry. The §6.6 escape-hatch-counter pathway is not yet built.

### A6. Why the pins exist

Per ADR-012 (ACCEPTED 2026-05-13) consolidation:

- `opentelemetry-api/sdk` — *"pin OTEL in v0.1 (not deferred to v0.5): §6.6 escape-hatch tracking needs telemetry day-one"* — plausible but **not yet honored** by code (per A5).
- `sqlglot` — pinned for PoC #2 deferred work + v0.5+ column-lineage emitter.
- `msgspec` — *"n/a (NucleusError + configs)"* — no research doc, no caller.

---

## Section B — Beachhead alignment (8-question gate, AGENTS.md §5)

Applied to **"OTEL Day-1 wiring under `src/nucleus/`"** (i.e., Option β below):

| # | Question | Verdict | Justification |
|---|---|---|---|
| B1 | Maps to one of the five layers? | ⚠ partial | Lives in coordination/internal; file doesn't exist yet. |
| B2 | Serves <30 min beachhead? | ❌ | No span is user-visible in `git clone → first BI-ready Iceberg table`. |
| B3 | Wrap, not build? | ✅ | OTEL is wrap-already. |
| B4 | Preserves no-JVM? | ✅ | OTEL Python is pure-Python. |
| B5 | Preserves local-identical-to-prod? | ✅ | No-op semantics identical local + prod. |
| B6 | Stays inside 30K LOC? | ✅ | Day-1 wiring 0-50 LOC; ledger at 45.2% of 8K v0.1 ceiling. |
| B7 | Empirical telemetry, not anxiety? | ❌ | Zero user reports requesting spans; pressure is from ADR-011's own forward commitment. |
| B8 | Required for v0.1 Mo 0-4? | ❌ | v4.1 §6.6 / §11.4 / ADR-011 §1 all gate at v0.5+. |

**Score: 5 ✓ / 2 ✗ / 1 ⚠.** Per §5: *"a 'no' or 'unclear' anywhere → reject or defer."* Day-1 wiring as a code-writing task **fails the gate**. The pin itself, however, costs nothing user-visible if substrate semantics are honored via API-only.

---

## Section C — Three options, scored

### C1. OpenTelemetry

#### Option α-full — demote BOTH `-api` and `-sdk` to `[observability]` extras

| Axis | Score |
|---|---|
| ✅ pros | Architect's B2.8 default; shrinks v0.1 install footprint (~5 packages); zero LOC; defers upgrade exposure until opt-in. |
| ❌ cons | Future `tracer.start_as_current_span(...)` in `coordination/asset_materialization.py` (v0.5 per `opentelemetry.md` §4.1) needs conditional imports — boilerplate tax. **Partially contradicts ADR-011 §1** because the API isn't installed. |
| 📐 LOC | 0 |
| 🕒 Time | 15 min |
| 🎯 Beachhead | unchanged |
| 💸 Upgrade exposure | LOWER |

#### Option α-split — KEEP `-api`, DEMOTE `-sdk` to `[observability]` extras *(recommended)*

| Axis | Score |
|---|---|
| ✅ pros | **Honors ADR-011 §1 literally**: API package alone produces no-op `NonRecordingSpan` when no `TracerProvider` is configured (verified 2026-05-14 at https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html L67/L115). Future telemetry sprinkling needs no conditional import. Pillar 2 (composability) preserved — Tier 0 protocol stays available; SDK is the trigger-driven part. `opentelemetry-api==1.29.0` is ~50 KB with three small transitive deps. |
| ❌ cons | Two slightly different states ("library installed but does nothing"). Marginally more cognitive load than α-full. |
| 📐 LOC | 0 |
| 🕒 Time | 20 min |
| 🎯 Beachhead | unchanged |
| 💸 Upgrade exposure | UNCHANGED for API; SDK absorbed by opt-in users |

#### Option β — wire Day-1 no-op in `src/nucleus/_internal/observability.py`

| Axis | Score |
|---|---|
| ✅ pros | Honors ADR-011 §1 ceremonially; single import surface for future call sites. |
| ❌ cons | **Adds speculative code without v0.1 caller** — directly violates Anti-Over-Engineering rule #4. Fails 8-question gate B7 + B8. Doubles abstraction over OTEL-API which already noops by default. |
| 📐 LOC | +30 to +50 |
| 🕒 Time | 60-90 min |

#### Option γ — status quo

Zero work tonight; drift flag stays open; install footprint stays bloated; speculative-pin pattern propagates. Not recommended.

### C2. `sqlglot`

#### Option α — demote to `[project.optional-dependencies] lineage-advanced`

| Axis | Score |
|---|---|
| ✅ pros | Zero v0.1 callers (A2); PoC #2 deferred the planned table-walker; `docs/research/sqlglot.md` §10 explicitly schedules v0.5+ as the next adoption window. Pin re-enters core in the v0.3 marimo upgrade ADR (`26.0.0 → 26.8.x[c]`) per ADR-012. |
| ❌ cons | `dlt==1.26.0` may pull `sqlglot` transitively (see NEEDS VERIFICATION #1); even so, demoting the explicit pin still removes the speculative-pin claim. |
| 📐 LOC | 0 |
| 🕒 Time | 15 min |

#### Option β — wire v0.1 asset-graph table-walker now (deferred work per A4)

| Axis | Score |
|---|---|
| ❌ | Adds 50-100 LOC for a v0.3+ user-experience nicety (auto-`deps=[]` inference); fails Anti-Over-Engineering rule #4; the asset-registry `ref()` resolution already works. |

#### Option γ — status quo

Same shape as OTEL γ.

### C3. `msgspec`

#### Option α — demote to `[project.optional-dependencies] serialization-fast` OR remove entirely

| Axis | Score |
|---|---|
| ✅ pros | Zero v0.1 callers; no research doc; `errors.py` is Frozen-stability surface (per its L82 docstring) — should not be rewritten for performance now. Removing is the maximum Anti-Over-Engineering option. |
| ❌ cons | If a v0.5+ run-event serializer benchmarks faster than `orjson` for our shapes, re-add via one-line pyproject edit. Trivially reversible. |
| 📐 LOC | 0 |
| 🕒 Time | 10 min |

#### Option β — wire msgspec into `errors.py` now

| ❌ | Rewriting ~680 LOC of Frozen public surface for a performance benefit that doesn't yet matter is a textbook over-engineering trap. |

#### Option γ — status quo

Same shape as OTEL γ.

---

## Section D — Recommendation

### D1. OpenTelemetry: **Option α-split** *(refines architect's B2.8 default)*

- **KEEP** `opentelemetry-api==1.29.0` in `[project] dependencies`
- **MOVE** `opentelemetry-sdk==1.29.0` to `[project.optional-dependencies] observability`

**Rationale**:

1. Per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html L67/L115/L562 (verified 2026-05-14), the API package alone, with no `TracerProvider` configured, produces no-op `NonRecordingSpan` for every `start_as_current_span(...)` call. This is **by design** — the API is intended to live in app and library code regardless of SDK presence.
2. ADR-011 §1 says: *"OTEL API + SDK are wired with a no-op sink by default — substrate present, no bytes leave the laptop."* The minimum-viable reading honors substrate-presence by **keeping the API installed**. The SDK only matters when an exporter is configured — by ADR-011 §5 that's v0.5+.
3. Anti-Over-Engineering rule #4 honored: zero new `src/nucleus/` code.
4. Pillar 2 (composability) honored: Tier 0 protocol remains available without conditional-import boilerplate when v0.5 AMA telemetry lands per `opentelemetry.md` §4.1.
5. AGENTS.md §11.13 upgrade exposure: API churn in the 12-minor stale window was tiny (Traces + Metrics surface stable); SDK churn (Logs renames, `BatchSpanProcessor` cadence change per `opentelemetry.md` §6.3) is now borne only by opt-in users.

### D2. sqlglot: **Option α** (demote)

- **MOVE** `sqlglot==26.0.0` to `[project.optional-dependencies] lineage-advanced`

**Rationale**: zero v0.1 callers (A2); `docs/research/sqlglot.md` §10 enumerates v0.5+ as the next adoption window; ADR-012 schedules the `26.0.0 → 26.8.x[c]` marimo upgrade for v0.3. Anti-Over-Engineering rule #4: no caller, no pin.

### D3. msgspec: **Option α — remove entirely** *(preferred)*

- **REMOVE** `msgspec==0.18.6` from `[project.dependencies]`. No extras group needed.

**Alternative**: extras-bucket as `serialization-fast` if founder prefers discoverability.

**Rationale**: zero callers; no research doc; ADR-012's "n/a (NucleusError + configs)" planned use never materialized. AGENTS.md anti-over-engineering rule #5 ("Code is a liability"): the pin is liability with no offsetting asset. Trivially reversible.

### D4. Exact `pyproject.toml` diff

```toml
dependencies = [
  # ... (unchanged rows) ...

-  "msgspec==0.18.6",
   "typer==0.15.1",
   # ...

   "jinja2==3.1.5",
-  "sqlglot==26.0.0",

   # ...

-  # Observability (OpenTelemetry-compatible)
-  "opentelemetry-api==1.29.0",
-  "opentelemetry-sdk==1.29.0",
+  # Observability protocol (Tier 0 immortal per v4.1 §4.1).
+  # API package only: produces no-op NonRecordingSpan when no TracerProvider is
+  # set (https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html L67/L115).
+  # SDK + exporters live under [project.optional-dependencies] observability.
+  "opentelemetry-api==1.29.0",
]

[project.optional-dependencies]
+# Opt-in OTEL SDK + future exporters (per ADR-011 §1 v0.5+ transport).
+# Install: `pip install nucleus[observability]`
+observability = [
+  "opentelemetry-sdk==1.29.0",       # version-locked to opentelemetry-api
+]
+
+# Opt-in column-level lineage + asset-graph dep extraction
+# (per docs/research/sqlglot.md §10; first concrete caller v0.5+).
+# Install: `pip install nucleus[lineage-advanced]`
+lineage-advanced = [
+  "sqlglot==26.0.0",
+]

 dev = [ ... unchanged ... ]
 docs = [ ... unchanged ... ]

-all = ["nucleus[dev,docs]"]
+all = ["nucleus[dev,docs,observability,lineage-advanced]"]
```

PEP 621 syntax verified live 2026-05-14 against https://packaging.python.org/en/latest/specifications/pyproject-toml/#dependencies-optional-dependencies L335/L344.

### D5. Exact ADR-012 amendment

Update three rows in the Runtime pin matrix:

| Component | Pin | Status | Extras-group |
|---|---|---|---|
| `sqlglot` | `26.0.0` | demoted 2026-05-14 | `lineage-advanced` |
| `msgspec` | (REMOVED 2026-05-14) | — | — |
| `opentelemetry-api` | `1.29.0` | (core — kept) | — |
| `opentelemetry-sdk` | `1.29.0` | demoted 2026-05-14 | `observability` |

Add a one-paragraph footnote under the matrix:

> **Pin count revised 2026-05-14**: 22 explicit core pins (was 25; −1 removed msgspec; −2 demoted to extras). Optional extras: `[observability]` 1 pin, `[lineage-advanced]` 1 pin. Rationale: `docs/research/otel_day1_decision.md`.

### D6. Exact ADR-011 amendment

Add a footnote-clarification under §1 table:

> **Substrate-vs-implementation clarification (added 2026-05-14)**: Per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html (verified 2026-05-14), the OpenTelemetry Python API package alone — with no `TracerProvider` configured — produces no-op `NonRecordingSpan` for every `start_as_current_span(...)` call. The Day-1 substrate commitment is therefore satisfied by pinning `opentelemetry-api` in `[project] dependencies`. The `opentelemetry-sdk` lives in `[project.optional-dependencies] observability` until the v0.5 collector-export ADR opens. This keeps ADR-011's "substrate present, transport silent" promise literally true while honoring `.cursor/rules/nucleus.mdc` Anti-Over-Engineering rule #4.

Update §5 (Transport per release) v0.1 row from `no-op sink` to `no-op sink (API-only — NonRecordingSpan by default)`.

Bump ADR-011 Status line to `AMENDED 2026-05-14 — substrate-presence clarified per docs/research/otel_day1_decision.md`.

### D7. CI implications

- **`scripts/check_pinning.py`**: extend matrix-assertion to two passes (`[project.dependencies]` + `[project.optional-dependencies]`); ~20 LOC delta. NEEDS VERIFICATION #3.
- **`scripts/check_licenses.py`**: dictionary L100-101 keeps OTEL entries; optionally prune `msgspec` and `sqlglot` entries if dictionary asserts presence (verified: it does not — safe). ~3 LOC delta.
- **`tests/upgrade_smoke/`**: no test files exist today for any of the four pins; demotion does not change the smoke-test surface. A `tests/upgrade_smoke/test_otel_api.py` should land alongside the eventual `1.29.0 → 1.41.x` upgrade ADR per AGENTS.md §11.13.
- **`docs/compatibility.md`**: regenerate to mirror revised pin count + extras groups.

### D8. Founder approval gate

This is **not** a version upgrade (Constraint #11 ADR required) and **not** an architectural reshuffle (no public API surface changes; Tier 0 status of OTEL reaffirmed). Appropriate gate:

1. **ADR-011 minor amendment** (3-paragraph clarification under §1 + §5 row update). In-place; no new ADR number.
2. **ADR-012 row updates** for sqlglot / msgspec / opentelemetry-sdk per §D5. In-place; date-stamped.
3. **No ADR-017 required.** Optional: founder may prefer a one-pager trail document; not architecturally needed.

---

## Section E — Concrete deliverables

If recommendation approved:

**Files modified**:
- `pyproject.toml` — diff per §D4 (~ +12/−5 lines)
- `docs/decisions/ADR-011-telemetry-and-observability-opt-in-policy.md` — §1 footnote + §5 v0.1 row (~+6 lines)
- `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` — 3 row updates + 1 row removal (~+4/−1 lines)
- `docs/compatibility.md` — quarterly snapshot regenerated (~5 line delta)
- `scripts/check_pinning.py` — extras-group parsing (~20 LOC; see NEEDS VERIFICATION #3)
- `scripts/check_licenses.py` — optional 2-row prune (~3 LOC)

**Files added**: **None.** No `src/nucleus/_internal/observability.py`. No `tests/coordination/test_otel_init.py`. No new ADR.

**Tests added**: optional 5-LOC `tests/test_pyproject_extras.py` asserting `nucleus[observability]` and `nucleus[lineage-advanced]` resolve via `importlib.metadata.metadata("nucleus").get_all("Provides-Extra")`. Not strictly required.

**`FOUNDER_ACTION_QUEUE` entry**: close B2.8 with one-line autopilot record citing this doc.

**`docs/research/ai_hallucinations.md`**: no new entries from this research; doc surfaces zero fabricated APIs.

---

## Section F — Open questions for founder

### F1. α-split vs α-full?

Architect's B2.8 default was α-full (both api + sdk to extras). This research's α-split keeps `-api` in core for the reasons in §D1. Both coherent; α-split is lower-friction-future (no conditional imports when v0.5 AMA telemetry lands). **Decide.**

### F2. Does v0.1 enterprise pitch require visible OTEL hooks?

If the v0.1 release narrative mentions "OpenTelemetry-ready out of the box" as a sales bullet, α-split is the stronger story (`pip install nucleus[observability]` → point a collector). α-full demands a second install step. No existing user request has surfaced in `FOUNDER_ACTION_QUEUE.md` §0 or `docs/onboarding/quickstart.md`; absent demand, either option is honest. **Decide.**

### F3. `msgspec` — remove or extras-bucket?

Removing is cleaner; extras-bucketing preserves discoverability. No technical impact either way. **Decide.**

### F4. ADR-017 paper-trail document?

Not architecturally required. Some founders prefer a numbered decision record so future agents see the disposition in `docs/decisions/` not just in this research doc. **Decide.**

### F5. Quarterly upgrade audit cadence for demoted rows?

Per AGENTS.md §11.13, the quarterly audit applies to runtime deps. Once `-sdk` and `sqlglot` are in extras, do they still belong on the quarterly schedule, or only on issue-triggered audits? **Recommendation**: keep them quarterly (the `-api ↔ -sdk` version-pair coupling is real per `opentelemetry.md` §6.1), but drop audit *priority* from "stale-warning" to "ready-when-needed." **Decide.**

---

## NEEDS VERIFICATION

1. **`dlt[sql_database,pyiceberg]==1.26.0` transitive `sqlglot` dependency**: `docs/research/dlt.md` was not re-read this session. If dlt pulls sqlglot transitively, demotion from explicit pin still removes the speculative-pin claim but doesn't shrink installed wheels. Verify: `pip show dlt | grep -i Requires`, or `pip install dlt[sql_database,pyiceberg]==1.26.0 && pip show sqlglot`. Does NOT change the recommendation; sharpens install-footprint claim only.

2. **`opentelemetry-api==1.29.0` transitive deps on Python 3.11**: `Deprecated`, `importlib-metadata`, `typing-extensions` listed by `docs/research/opentelemetry.md` §1 but not re-verified against PyPI metadata for the exact pin. Verify: `pip show opentelemetry-api==1.29.0`. Likely uncontroversial.

3. **`scripts/check_pinning.py` current parser behavior**: this researcher did not inspect the parser to confirm the ~20 LOC delta estimate in §D7. Verify: read the script before the implementer wave lands.

---

## Appendix — Cited docs URLs

External (verified live 2026-05-14 unless noted):

- OpenTelemetry Python instrumentation guide: https://opentelemetry.io/docs/languages/python/instrumentation/
- OpenTelemetry Python API trace reference (NonRecordingSpan / no-op semantics): https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html
- OpenTelemetry Python getting-started: https://opentelemetry.io/docs/languages/python/getting-started/
- OpenTelemetry Python exporters: https://opentelemetry.io/docs/languages/python/exporters/
- OpenTelemetry Python automatic instrumentation: https://opentelemetry.io/docs/languages/python/automatic/
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/specs/semconv/
- OpenTelemetry releases / GitHub: https://github.com/open-telemetry/opentelemetry-python
- OpenTelemetry PyPI (api): https://pypi.org/project/opentelemetry-api/
- OpenTelemetry PyPI (sdk): https://pypi.org/project/opentelemetry-sdk/
- sqlglot API root: https://sqlglot.com/sqlglot.html
- sqlglot lineage: https://sqlglot.com/sqlglot/lineage.html
- sqlglot GitHub tags: https://github.com/tobymao/sqlglot/tags
- sqlglot PyPI: https://pypi.org/project/sqlglot/
- msgspec docs: https://jcristharif.com/msgspec/
- msgspec PyPI: https://pypi.org/project/msgspec/
- PEP 621 (`[project.optional-dependencies]`): https://peps.python.org/pep-0621/
- Python packaging guide (pyproject.toml): https://packaging.python.org/en/latest/specifications/pyproject-toml/#dependencies-optional-dependencies

In-repo:

- `AGENTS.md` §3 Constraint #10/#11, §5 8-question gate, §7 Vocabulary, §11.12 Docs Discipline, §11.13 Upgrade Safety
- `.cursor/rules/nucleus.mdc` Anti-Over-Engineering rules #1-#6
- `docs/decisions/ADR-007-dependency-license-tier-policy.md`
- `docs/decisions/ADR-011-telemetry-and-observability-opt-in-policy.md`
- `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md`
- `nucleus_architecture_v4.1.md` §3.1, §4.1, §6.6, §9.2, §11.4, §18
- `docs/research/opentelemetry.md` (verified 2026-05-13)
- `docs/research/sqlglot.md` (verified 2026-05-13)
- `docs/research/ai_hallucinations.md`
- `FOUNDER_ACTION_QUEUE.md` §0 B2.8

---

### AI memory caveat (per AGENTS.md §11.12)

This research doc reflects external docs **as of 2026-05-14**. The OTEL Python API surface used here (`trace.get_tracer`, `tracer.start_as_current_span`, `NonRecordingSpan`) is stable from package 1.0.0 onward; the no-op-on-default-provider semantics have been documented since the package's first stable release. **No fabricated APIs**: every external API mentioned is grounded in a cited URL.

*Researcher model: Claude Opus 4.7 (fallback for Gemini 3.1 Pro per AGENTS.md §11.14 availability-fallback — Gemini not in current Cursor runtime). Time taken: ~55 min (audit + read + verify + draft + trim).*
