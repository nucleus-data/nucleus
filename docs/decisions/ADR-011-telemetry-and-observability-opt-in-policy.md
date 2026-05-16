# ADR-011: Telemetry & Observability Opt-In Policy

> **Status**: AMENDED — 2026-05-14 — substrate-presence clarified per `docs/internal/research/otel_day1_decision.md` (no-op via API-only; SDK demoted to `[project.optional-dependencies] observability`). Originally ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0).
> **Date**: 2026-05-13 (original) · 2026-05-14 (amendment) · **Decider**: Solo founder
> **Tags**: telemetry, observability, otel, privacy, opt-in, cardinality, v0.5
> **Related**: ADR-002 §8 (Cloud path), ADR-005 §1 (tier ladder — OTEL Internal v0.1 → Beta v0.3 → Stable v0.5), ADR-006 (`NE-codes` are the only error labels in metric attributes), ADR-007 (OTEL + VM + VL + Marquez all GREEN Apache-2.0 per Worker X §2.1), ADR-009 (OL emission — same opt-in shape), `AGENTS.md` §3 Constraint #6 + §7 (vocabulary) + §11.7 (no external classnames), `docs/specs/nucleus_architecture_v4.1.md` §6.x + §11, `docs/internal/research/opentelemetry.md` (Worker M), `docs/internal/research/observability_backends.md` (Worker X), `docs/internal/research/daft.md` §8 (Scarf trap), `docs/internal/security/threat_model_v0.md` §3 + §6

## Context

Telemetry is table stakes for v0.5+ Cloud — cost meter (v4.1 §6.3), AI Copilot run-replay (§1.3 row 17), escape-hatch usage (§6.6), SLA dashboards. It is also a privacy minefield, a CVE attractor when always-on, and an instant-distrust trigger for OSS adopters: Worker Q's Daft research (`docs/internal/research/daft.md` §8 row 4) flagged Daft's default Scarf phone-home as the explicit "do not copy" anti-pattern — *anything that pings out of the box is a no-go for Nucleus*.

Worker M confirmed OTEL is **Tier 0 (immortal)** per v4.1 §4.1 (pure-Python `opentelemetry-api`/`-sdk==1.29.0` pinned; no JVM per Constraint #1; CNCF Top-Level). Worker X confirmed the v0.5+ backend bundle (VM + VL + Marquez) is wrap-not-build under standards (OTLP + OL); Marquez is the only JVM piece and runs in its own container per ADR-004 / Worker X §2.3. License-tier (ADR-007): all three GREEN. What Worker M+X did NOT lock — and what this ADR locks before the first span emits — is the **posture**: who emits, when, where, with what defaults. A one-way door (you cannot un-leak a span attribute that escaped); rhymes with ADR-009: substrate wired Day 1, transport silent Day 1, never default-on for OSS.

## Decision

> **Telemetry is OPT-IN for v0.1 → v0.5 OSS (`telemetry.opt_in=true` in `nucleus.toml` OR `NUCLEUS_TELEMETRY=1`). OTEL API + SDK are wired with a no-op sink by default — substrate present, no bytes leave the laptop. v0.5 Cloud MAY flip to OPT-OUT for Cloud customers only, governed by Cloud ToS — never for OSS users. Cardinality budget enforced in CI. No PII in span attributes. Mirrors ADR-009 lineage shape.**

### 1. Opt-in defaults per release

| Version | OSS default | Override | Cloud-specific |
|---|---|---|---|
| v0.1 | OFF (no-op `TracerProvider`/`MeterProvider`; no exporters pinned) | `telemetry.opt_in=true` in `nucleus.toml` OR `NUCLEUS_TELEMETRY=1` | n/a (no Cloud) |
| v0.3 | OFF | same; `nucleus enable otel` flips the flag + writes `nucleus.toml` | n/a |
| v0.5 OSS | OFF | same | OSS users **NEVER** auto-opt-in — bedrock |
| v0.5 Cloud | OPT-**OUT** for Cloud customers only | `telemetry.opt_in=false` in customer Cloud config | governed by Cloud ToS, not this ADR |

**Why opt-in for v0.1**: privacy bedrock (Scarf trap, Worker Q §8); 30-min beachhead per v4.1 §1.5 = `git clone → BI-ready Iceberg table` with zero outbound network; substrate-vs-transport split lets us wire OTEL day 1 (escape-hatch counters, boot-time histograms per Worker M §9) without exporting bytes. **Substrate present, transport silent.**

> **Substrate-vs-implementation clarification (added 2026-05-14)** — Per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html (verified 2026-05-14), the OpenTelemetry Python API package alone — with no `TracerProvider` configured — produces no-op `NonRecordingSpan` for every `start_as_current_span(...)` call. The Day-1 substrate commitment in §1 is therefore satisfied by pinning `opentelemetry-api==1.29.0` in `[project] dependencies` alone; **no `src/nucleus/` source code is required to honor "substrate present, transport silent."** The `opentelemetry-sdk==1.29.0` lives in `[project.optional-dependencies] observability` (install via `pip install nucleus[observability]`) until the v0.5 collector-export ADR opens. This keeps ADR-011's Day-1 promise literally true while honoring `.cursor/rules/nucleus.mdc` Anti-Over-Engineering rule #4 ("no speculative code without a v0.1 caller"). See `docs/internal/research/otel_day1_decision.md` §D1 for the empirical verifier-driven rationale.

### 2. What gets emitted (when opt-in is true)

Aligned with Worker M §4.1-§4.3 (root + child spans + mandatory metrics). All names use Nucleus dot-namespace per Worker M §4.3 + AGENTS.md §7 vocabulary.

| Signal | Name | When | Cardinality |
|---|---|---|---|
| Span | `nucleus.cli.run` | per CLI invocation | low (≤ ~50/day/user) |
| Span | `nucleus.asset.materialize` | per asset run (Worker M §4.1) | medium (≤ ~10K/day/team) |
| Span | `nucleus.ctx.sql` | per `ctx.sql()` call (Worker M §4.2) | medium |
| Span | `nucleus.ingest` | per `ctx.copy_from()` / `ingest` run | low |
| Metric | `nucleus.assets.materialized` (Counter, `unit=1`) | per materialization | `asset`, `result`, `materialization_mode` |
| Metric | `nucleus.asset.materialization.duration` (Histogram, `unit=s`) | per materialization | `asset`, `engine` |
| Metric | `nucleus.errors.count` (Counter, `unit=1`) | per `NucleusError` | labelled by `NE-code` per ADR-006 (NEVER raw external classnames per AGENTS.md §11.7) |
| Metric | `nucleus.escape_hatch.calls` (Counter, `unit=1`) | per escape-hatch use (Worker M §4.1) | drives v4.1 §6.6 replacement trigger |
| Log (v0.5+) | structured via OL `errorMessage` facet (covered by ADR-009 §3 row 11) | per failure | low |

**Total: 4 spans + 4 metrics on the always-on surface; logs ride OL per ADR-009 (no double-emission).**

### 3. NEVER emit (privacy hard floor — five rules)

| # | Signal | Why forbidden | Enforcement |
|---|---|---|---|
| 1 | Raw SQL strings as attributes | cardinality + PII in WHERE clauses | Worker M §4.2 — emit `nucleus.sql.statement_hash` (`sha256(raw)[:16]`) only |
| 2 | Asset row counts as **attributes** | small-cohort re-identification | row counts go in metric *values*, not attributes |
| 3 | OS username, hostname, FS layout | identity de-anonymization | resource attrs limited to `service.name=nucleus`, `service.version`, `nucleus.project_id=<sha1>`, `nucleus_install_id=<UUIDv4>` |
| 4 | Absolute file paths | leaks home directory layout | relativize to project root pre-emission |
| 5 | Stack traces with local var values | secrets-in-locals leak (Postgres URL, S3 keys per `threat_model_v0.md` §3) | use canonical `NucleusError.user_message` per ADR-006; never `repr(exc.__cause__)` |

CI lint enforces #1 + #4; code-review discipline covers #2, #3, #5.

### 4. Cardinality budget (per Worker M §5 + Worker X §5 row 1)

Worker X §5: VM cardinality matters more than throughput — every unique `{asset, mode, engine, project_id, env}` tuple is one time series.

| Budget | Limit | Rationale |
|---|---|---|
| Unique span names | ≤ 50 | §2 surface is 4 — 12× headroom for Logs bridge + MCP spans |
| Unique metric names | ≤ 100 | §2 surface is 4 (+ Worker M §4.3 future) |
| Unique attribute keys | ≤ 200 | OTEL semconv plus `nucleus.*` namespace |
| Unique attribute VALUES per key | ≤ 1000 | per-project ceiling; `nucleus.asset.name` capped at 1000 distinct → big projects need Cloud namespacing (v0.7+) |
| High-cardinality attrs | FORBIDDEN | no `run_id` / `snapshot_id` / `sql_hash` as **attribute keys** |

CI lint: `scripts/check_telemetry_cardinality.py` (NEEDS VERIFICATION — v0.5 work; ~80 LOC). Pre-v0.5: manual review during AMA PR suffices.

### 5. Transport per release

| Version | Local dev | OSS production | Cloud |
|---|---|---|---|
| v0.1 | no-op sink (API-only — `NonRecordingSpan` by default; SDK ships via `pip install nucleus[observability]` opt-in) | same | n/a |
| v0.3 | OTLP/HTTP `localhost:4318` (opt-in via `nucleus enable otel`; requires `[observability]` extra) | user-configured `OTEL_EXPORTER_OTLP_ENDPOINT` (requires `[observability]` extra) | n/a |
| v0.5 | same | same | OTLP/HTTP to Cloud collector + OL `HttpTransport` to Marquez per ADR-009 §2 |

**HTTP, not gRPC** (Worker M §6.3): gRPC pulls `grpcio` ~30 MB wheel for zero v0.1 beachhead value. Pin `opentelemetry-exporter-otlp-proto-http` in v0.5 ADR per Worker M §10 + Worker X §6 row 3. No exporter pin in v0.1: substrate-vs-transport split — `api`+`sdk` cover Worker M §3.2-§3.3; exporter belongs to v0.5.

### 6. Privacy posture (the bedrock)

- **No identifier collection beyond `nucleus_install_id`** — UUIDv4 at `nucleus init`, persisted at `.nucleus/install_id`; per-project, never user-tied or joined to OS username, machine UUID, or git remote URL.
- **Exports MUST go to user-controlled endpoints** — NO Nucleus-Inc default OTLP collector for OSS; we do not host an opt-in firehose. Cloud collection is governed by separate Cloud ToS (v0.5+ GA), accepted at signup.
- **`telemetry.disclose=true`** (default ON when opt-in is on) prints a one-line `nucleus up` footer `Telemetry: ON (endpoint=http://...)` so users see when bytes leave (mirrors ADR-009 transparency). Disabling is instant: remove `telemetry.opt_in`, OR `NUCLEUS_TELEMETRY=0`, OR `nucleus disable otel` (v0.3+).
- **No anonymous OSS usage stats — ever**. Daft/Scarf precedent (Worker Q §8 row 4) is the standing rejection: anything that pings out of the box is a no-go. Aggregate product metrics, if Cloud needs them, live behind Cloud ToS — never bundled with the OSS install. No `nucleus_install_id` is ever beaconed to a Nucleus-Inc endpoint by OSS.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **AI proposes always-on telemetry** | This ADR cited in `coordination/telemetry/__init__.py` docstring; `scripts/check_no_telemetry_default.py` greps for `OPT_IN_DEFAULT=True` or hard-coded exporter pins pre-v0.5 |
| **PII leak via span attributes** | Worker M §4.2 redaction (hash + first ~200 chars); attribute allowlist in cardinality lint |
| **Cardinality explosion** | §4 budget + CI lint; `nucleus.asset.name` capped at 1000 distinct |
| **Cloud opt-out confusion** | Cloud ToS handles consent; §1 table makes the OSS-vs-Cloud line bright |
| **Telemetry endpoint unreachable** | OTEL `BatchSpanProcessor` queue drops without blocking (Worker M §5; 1.36+ adds jitter per §8); AMA continues — telemetry is observability, not correctness, mirroring ADR-009 §"Risks" row 3 |

## Verification plan

1. **`scripts/check_telemetry_cardinality.py`** (~80 LOC, NEEDS VERIFICATION — v0.5 work) — span name + metric name + attribute key/value limits per §4; fails CI on overrun.
2. **`scripts/check_no_telemetry_default.py`** (~40 LOC) — greps for `OPT_IN_DEFAULT=True` or equivalent constants; greps `pyproject.toml` for any `opentelemetry-exporter-*` pin pre-v0.5. Lands alongside `scripts/check_openlineage_facets.py` from ADR-009.
3. **`tests/telemetry/test_opt_in_default.py`** — runs `nucleus init && nucleus up && nucleus run <asset>`; asserts zero spans, zero metrics, zero outbound packets in default mode; verifies opt-in flips behaviour.
4. **`nucleus.toml` schema** documents `telemetry.opt_in` (bool, default `false`), `telemetry.endpoint` (URL, default `null`), `telemetry.disclose` (bool, default `true` when opt-in true). README + SETUP.md mention "no telemetry by default" prominently in install / first-boot sections (mirrors ADR-009 transparency principle).

## Rollback

- **ADR-011a**: if cardinality lint proves brittle (false positives on long-tail asset graphs), relax per-key value budget or move to advisory-only on the `nucleus.asset.*` keys.
- **ADR-011z** (no-rollback bedrock): NEVER allows opt-out → opt-in for OSS. Once a release ships with opt-in default, a future minor cannot silently flip. Same shape as ADR-009's "no rollback for the dead `openlineage-dagster` bridge."

## Docs URLs

- OTEL Python: <https://opentelemetry.io/docs/languages/python/> · Semconv: <https://opentelemetry.io/docs/specs/semconv/general/metrics/>
- VM OTLP receiver: <https://docs.victoriametrics.com/victoriametrics/integrations/opentelemetry/>
- VL OTLP receiver: <https://docs.victoriametrics.com/victorialogs/data-ingestion/opentelemetry/>
- Worker M: `docs/internal/research/opentelemetry.md` · Worker X: `docs/internal/research/observability_backends.md` · Daft/Scarf: `docs/internal/research/daft.md` §8 row 4
- ADR-009 parallel: `docs/decisions/ADR-009-openlineage-event-schema-policy.md`

### NEEDS VERIFICATION

1. **`scripts/check_telemetry_cardinality.py` exact lint surface** — Worker M §5 says cardinality is "the worry, not per-call cost" but does not specify static (grep `meter.create_*` sites) vs runtime (count emitted series). Default: static grep + manual review pre-v0.5; runtime verification deferred to v0.7+ Cloud collector-side limits.
2. **`opentelemetry-exporter-otlp-proto-http` pin choice for v0.5** — Worker M §10 lists candidate; Worker X §6 row 3 confirms VM/VL accept HTTP. Exact version needs fresh PyPI fetch when v0.5 observability ADR opens; 1.29.0 → 1.41.x sequence per Worker M §6.3 still applies.

## Trigger

Status flips **PROPOSED → ACCEPTED** when all three hold: (1) founder reviews + signs off (or amends per ADR-002 §6); (2) `scripts/check_no_telemetry_default.py` lands in CI; (3) `nucleus.toml` schema documents the three telemetry flags.

**Not gated on PoC #1.** Governance with v0.5+ implementation surface; can ACCEPT immediately to lock the privacy posture before any AMA telemetry code is written.

## Downstream consumers

| Consumer | When | Affected how |
|---|---|---|
| AMA (`src/nucleus/coordination/asset_materialization.py`) | Post-PoC #1 (Mo 2-3) | Wraps span emission per Worker M §4.1; obeys §1 opt-in flag; passes `nucleus_install_id` resource attr |
| `nucleus enable otel` CLI (v0.3+) | Mo 8-14 | Wraps this policy as a `nucleus.toml` flag flip + endpoint config; mirrors `nucleus enable marquez` from ADR-009 |
| Cloud Copilot + `nucleus-mcp-server` (v0.5+) | Mo 14-20 | Obey §4 cardinality + §3 NEVER-emit budgets; MCP emits tool-call spans (still opt-in per §1 OSS bedrock); W3C Trace Context per Worker M §10; AI-provider telemetry separate per open Q 3 |
| Workbench + `nucleus doctor` (v0.2+) | Mo 4-8 | Show "Telemetry: OFF / ON (endpoint=…)" per §6 disclose; surface `NUCLEUS_TELEMETRY` env state, mirroring ADR-009 `OPENLINEAGE_DISABLED` |
| Enterprise customers | v0.7+ | Get Cloud ToS DPA; never opted-in via OSS install path |

## Open questions for founder

1. **`nucleus_install_id` cadence** — at `nucleus init` (per-project, persisted to `.nucleus/install_id`) or per-CLI-invocation (ephemeral)? **Default**: per-project at `nucleus init`, persisted. Lets the user join their own metrics across runs without joining across users.
2. **Top-level `nucleus telemetry disable` CLI command** alongside `nucleus enable otel` (v0.3+)? **Default**: yes; ~10 LOC; fits Beta tier per ADR-005 §1; symmetric with `nucleus enable / disable marquez` from ADR-009.
3. **Pre-v0.5 ADR for AI-provider telemetry** — OpenAI / Anthropic SDKs phone home regardless of our OTEL posture. **Default**: defer to v0.5 Cloud Copilot launch ADR; document in `docs/specs/nucleus_ctx_sdk_spec.md` as a known third-party flow under Cloud ToS, separate from OTEL.

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.

---

### Amendment 2026-05-14 — Option α-split per `docs/internal/research/otel_day1_decision.md`

Trigger: drift-detection verifier MEDIUM #3 (`docs/FOUNDER_ACTION_QUEUE.md` §0 / B2.8) flagged four `[project.dependencies]` pins with **zero callers** under `src/nucleus/`, `tests/`, `poc/`, `scripts/`. Researcher's Option α-split disposition (founder-approved blanket — "approve all recommendations and proposals", 2026-05-14) lands as follows:

- `opentelemetry-api==1.29.0` — **KEEP** in `[project] dependencies` (no-op substrate honored without `src/` source code; ADR-011 §1 Day-1 promise satisfied via `NonRecordingSpan` per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html).
- `opentelemetry-sdk==1.29.0` — **MOVE** to `[project.optional-dependencies] observability`. Install via `pip install nucleus[observability]`. SDK pin only matters once an exporter is configured (per §5 v0.5+ scope).
- `sqlglot==26.0.0` — **MOVE** to `[project.optional-dependencies] lineage-advanced` (PoC #2 promoted with jinja2 + regex + difflib only; the planned v0.5+ column-lineage walker per `docs/internal/research/sqlglot.md` §10 is the first concrete caller). Note: `dlt[sql_database,pyiceberg]==1.26.0` already pulls `sqlglot` transitively (verified 2026-05-14 via `pip show dlt`), so the default install still receives `sqlglot` indirectly; the explicit pin remains version-locked for projects that import it directly without depending on dlt.
- `msgspec==0.18.6` — **REMOVE** entirely. Zero callers under `src/`, `tests/`, `poc/`, `scripts/`; no research doc; the planned `NucleusError + configs` use never materialized (the Frozen `errors.py` surface uses pure-Python `class NucleusError(Exception)` per ADR-005). Pure-stdlib substitutes (`json`, `dataclasses`, `tomllib`) suffice. Reversible with a one-line pyproject edit if a v0.5+ run-event serializer benchmark warrants reintroduction.

Rationale: empirical drift-verifier MEDIUM #3 + researcher §B 8-question gate failure for "Day-1 wiring as code" (B7 `empirical telemetry, not anxiety` ✗ + B8 `required for v0.1 Mo 0-4` ✗ per `docs/internal/research/otel_day1_decision.md` §B). Honors `.cursor/rules/nucleus.mdc` Anti-Over-Engineering rule #4 ("no speculative code") + AGENTS.md §5 Q3 ("wrap, not build"; here the wrap is "the dep IS the substrate, no source code needed"). Install size for the default `pip install nucleus` shrinks ~2-3 MB (OTEL SDK + `opentelemetry-semantic-conventions` ≈ 1.5 MB; `msgspec` ≈ 0.5 MB). No source code changes required (zero callers per researcher §A2). See `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` 2026-05-14 amendment for the matrix-row updates and updated pin count.
