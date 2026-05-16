# Nucleus Implementation Readiness

> The master checklist. Are we ready to start writing v0.1 code? This document answers that question with a yes/no gate.
>
> Companion document tying together: `nucleus_architecture_v3.md`, `nucleus_vs_databricks.md`, `nucleus_ctx_sdk_spec.md`, `nucleus_asset_model_spec.md`, `nucleus_project_anatomy.md`, `nucleus_cli_spec.md`, `nucleus_poc_plan.md`.

---

## 0. The Question

**Are we ready to write the first line of v0.1 production code?**

Not "are we ready to prototype" — that's PoC phase, addressed in `nucleus_poc_plan.md`. Not "do we know everything" — we never will.

This checklist is the explicit gate between *design phase* and *build phase*.

---

## 1. Document Lock Status

| Doc | Status | Lock criterion |
|---|---|---|
| `nucleus_architecture_v3.md` | ✅ Locked | All 8 design laws agreed; build vs wrap finalized |
| `nucleus_vs_databricks.md` | ✅ Locked | Feature matrix reviewed; 3 caveats acknowledged |
| `nucleus_ctx_sdk_spec.md` | ✅ Locked | Frozen v1.0 API surface |
| `nucleus_asset_model_spec.md` | ✅ Locked | Asset primitive + 8 properties agreed |
| `nucleus_project_anatomy.md` | ✅ Locked | Layout standardized |
| `nucleus_cli_spec.md` | ✅ Locked | Command surface complete |
| `nucleus_poc_plan.md` | ✅ Locked | 5 PoCs defined; criteria explicit |
| `nucleus_implementation_readiness.md` | ✅ Locked (this) | Master gate |

**All 8 docs locked = design phase complete.**

---

## 2. Pre-Code Checklist

Before any v0.1 commit, every box must be checked.

### 2.1 PoC validation (from `nucleus_poc_plan.md`)

- [ ] PoC #1 — Dagster embed and hidden — **PASS** or fallback adopted
- [ ] PoC #2 — Iceberg-rust + Lakekeeper end-to-end — **PASS** or fallback adopted
- [ ] PoC #3 — DuckDB Arrow Flight concurrency — **PASS** or fallback adopted
- [ ] PoC #4 — Portal Dagster UI embed — **PASS** or fallback adopted
- [ ] PoC #5 — dlt + dbt-duckdb under `ctx` — **PASS** or fallback adopted
- [ ] Decision gate review held; outcome documented

### 2.2 Team & Resources

- [ ] At least 2 engineers committed (1 Rust/backend, 1 Python/SDK)
- [ ] 1 designer or engineer with React experience identified (for Portal)
- [ ] Compliance budget secured (Vanta/Drata + auditor for SOC2 readiness by v1.0)
- [ ] Cloud account(s) for staging/prod deployment
- [ ] CI/CD platform chosen (GitHub Actions / Buildkite / etc.)

### 2.3 Repository & Tooling

- [ ] Monorepo or polyrepo decision made and rationalized
- [ ] Rust toolchain pinned (`rust-toolchain.toml`)
- [ ] Python toolchain pinned (`uv` + `.python-version`)
- [ ] License chosen (recommend Apache 2.0 or AGPL — strategic decision)
- [ ] Code style enforced (`rustfmt`, `ruff`, `prettier`)
- [ ] Linting configured (`clippy`, `ruff`, `eslint`)
- [ ] Pre-commit hooks set up
- [ ] CI configured: build, test, lint, security scan on every PR

### 2.4 External Dependencies

Verify each is at a usable version:

- [ ] DuckDB ≥ 1.1 (Iceberg extension stable)
- [ ] Polars ≥ 1.0
- [ ] iceberg-rust at acceptable spec coverage (per PoC #2)
- [ ] Lakekeeper at acceptable maturity (per PoC #2)
- [ ] Dagster ≥ 1.8 (embedded library mode tested)
- [ ] dlt ≥ 1.0 (verified source coverage matches our needs)
- [ ] dbt-duckdb at compatible Python version
- [ ] Marimo at production-grade UX (≥ 0.10)

### 2.5 Design Coverage

- [ ] `ctx` SDK has complete API surface defined (§12 of `nucleus_ctx_sdk_spec.md`)
- [ ] Asset model has 8 properties defined (§15 of `nucleus_asset_model_spec.md`)
- [ ] Project layout matches `nucleus_project_anatomy.md`
- [ ] Every CLI command from `nucleus_cli_spec.md` has a stub or implementation plan
- [ ] Portal page-by-page wireframes exist (low-fi acceptable)

### 2.6 Brand & Naming

- [ ] Product name finalized ("Nucleus" or alternative — verify trademark availability)
- [ ] Domain registered
- [ ] GitHub org reserved
- [ ] Logo placeholder exists

### 2.7 Risk Mitigation Acknowledged

For each High-severity risk in `nucleus_architecture_v3.md` §16:

- [ ] Portal UI effort risk → mitigation plan (start with Dagster embed)
- [ ] Compliance certifications timeline → budget approved
- [ ] DuckDB concurrency → fallback to chDB documented

---

## 3. The Six Hard Constraints (Re-Affirmation)

Before writing code, the team reaffirms commitment to these constraints from `nucleus_architecture_v3.md`:

1. **No JVM in core path.** Period.
2. **No public plugin SDK in v1.** Internal interfaces only.
3. **No custom scheduler.** Dagster wrapped.
4. **No ML platform.** Out of scope.
5. **No AI/Agent platform.** Out of scope.
6. **Proprietary code budget: ≤ 25K LOC by v1.0.** Tracked monthly.

If any team member or stakeholder cannot commit to all six, return to design phase.

---

## 4. Decision Framework for New Features

Once building starts, *every* proposed feature must answer 7 questions (from `nucleus_architecture_v3.md` §18). For convenience reproduced here:

1. Does it map to one of the four lines of architecture §2?
2. Does it serve the < 15-minute onboarding target?
3. Can we wrap it instead of building it?
4. Does it preserve the no-JVM constraint?
5. Does it preserve local-identical-to-prod?
6. Does it remain inside the < 25K LOC proprietary budget?
7. Is it triggered by empirical user telemetry, or by anxiety?

**A "no" or "unclear" on any question = feature is rejected or deferred.**

Anchor this framework in PR templates.

---

## 5. v0.1 Definition of Done

What does "we shipped v0.1" mean?

A single user can:

1. Run `nucleus init demo-project`
2. Run `nucleus up` (boots in < 30s)
3. Edit `assets/raw/sample.py` with one `@nucleus.source` and one `@nucleus.asset`
4. Run `nucleus build` and see both assets materialize to local Iceberg
5. Run `nucleus sql "SELECT * FROM analytics.daily_revenue"` and get results
6. Open Portal (`http://localhost:3000`) and see:
   - Asset graph (Dagster-backed)
   - SQL editor with one query
   - Asset details page
7. Run `nucleus run analytics.daily_revenue --force` to re-materialize
8. Run `nucleus snapshot list analytics.daily_revenue` and see ≥ 2 snapshots

That's v0.1. No notebook, no auth, no scheduler running by default, no observability, no production deploy — those come later.

This is the minimum viable demonstration of the architecture working.

---

## 6. Initial Milestone Targets

Per `nucleus_architecture_v3.md` §15. Reaffirmed:

| Milestone | ETA from build start | Gating criterion |
|---|---|---|
| v0.1 alpha | 2–3 mo | §5 above |
| v0.3 design partner | 4–5 mo | Dagster embed working, dbt + dlt integrated, Portal alpha |
| v0.5 closed beta | 7–9 mo | Multi-user, k3s deploy, lineage UI |
| v0.8 open beta | 10–12 mo | `obs` + `auth` modules, snapshot tooling |
| **v1.0 GA** | 14–18 mo | HA, RBAC, alerting, runbooks, SOC2 readiness |

Slippage signal: if a milestone is more than **20%** late, hold an explicit review. Do not silently extend timelines.

---

## 7. Team Composition (v0.1 → v1.0)

| Role | When needed | Why |
|---|---|---|
| **Rust backend engineer** (CLI, Asset Registry, integrations) | Day 1 | Core platform code |
| **Python SDK engineer** (`ctx`, Dagster wrap, dlt/dbt integration) | Day 1 | The product surface |
| **Frontend / Portal engineer** | Month 2 | Portal alpha at v0.3 |
| **Design / UX** (part-time) | Month 2 | Portal wireframes, brand |
| **DevRel / Docs** | Month 6 | Beta launch needs docs |
| **DevOps / SRE** | Month 8 | Production deploy story |
| **Compliance / Security lead** (part-time consultant) | Month 6 | SOC2 prep |
| **Sales/PM** | Month 10 | Design partner conversion |

Minimum viable team: **2 engineers (1 Rust, 1 Python) + 1 designer-engineer** through v0.5. Scale up after closed beta validates demand.

---

## 8. Stop Conditions

Pause and revisit architecture if:

- More than 2 PoCs require fallback plans
- v0.1 ships > 3 months late
- Proprietary LOC exceeds 25K before v1.0
- Internal interfaces (Layer 2 swap points) become a maintenance burden
- "We should also build X" appears in any planning doc where X is in §13 of `nucleus_architecture_v3.md`
- User feedback in design partner phase says "I just want Dagster + dbt + dlt directly" — meaning the integration isn't delivering coherence
- A major upstream OSS we wrap breaks compatibility and we can't keep up

These aren't failures — they're invitations to learn and adjust. But they must trigger an *explicit* pause, not silent drift.

---

## 9. Things Explicitly NOT in Scope of v0.1

(Reaffirming so we don't drift)

- Authentication / multi-user (v0.5)
- Observability stack (v0.8)
- Production k8s deploy (v0.5)
- Streaming / CDC (v1.5)
- ML / MLflow / AI (out of scope)
- Notebooks tab (v0.3 with Marimo embed)
- Lineage column-level UI (v0.8)
- Backup/restore tooling (v0.8)
- Data marketplace (v3.0)
- Plugin SDK (v3.0)

If any of these creep into v0.1 planning, push back.

---

## 10. Reading Order for New Team Members

Onboarding sequence for any engineer joining the project:

1. `nucleus_architecture_v3.md` — the entire philosophy in one file
2. `nucleus_vs_databricks.md` — what we are and aren't
3. `nucleus_ctx_sdk_spec.md` — the product
4. `nucleus_asset_model_spec.md` — the data primitive
5. `nucleus_project_anatomy.md` — how user projects look
6. `nucleus_cli_spec.md` — the CLI contract
7. `nucleus_poc_plan.md` — what's been validated and how
8. `nucleus_implementation_readiness.md` (this) — current state

Total reading time: ~2 hours. Required before any commit.

---

## 11. The Go/No-Go Gate

A single explicit meeting before v0.1 implementation starts. Attendees: all current engineers + founder.

### Agenda

1. Walk the PoC results table (§2.1).
2. Walk the pre-code checklist (§2).
3. Re-affirm the six hard constraints (§3).
4. Confirm team composition through v0.5 (§7).
5. Vote: GO / NO-GO.

### Recording

The decision is recorded in this document as:

```
## Go/No-Go Decision

Date: YYYY-MM-DD
Attendees: <names>
Decision: GO | NO-GO | DEFERRED (re-review on YYYY-MM-DD)

Notes:
- <key concerns raised>
- <commitments made>
- <follow-ups required>
```

(Empty until the meeting happens.)

---

## 12. After v0.1 Ships

This document is **not retired** after v0.1. It becomes the quarterly review template:

- Re-run §1 (doc lock status)
- Re-run §2 (anything new that needs validating?)
- Re-run §3 (still committed to the six constraints?)
- Re-run §8 (any stop conditions tripped?)

Every quarter, every milestone. Discipline is recursive.

---

## 13. Final Statement

**Build phase begins only when every checkbox in §2 is ticked and the Go/No-Go in §11 records GO.**

Not when we feel ready. Not when we're impatient. Not when investors ask. Not when an upstream OSS releases a new feature.

When the boxes are ticked.

This is the only way to ensure perfect implementation: not by being smarter than other teams, but by being more *honest* about what we know and don't know before we start.

---

## Appendix — Document Map

```
nucleus_architecture_v3.md             ← the philosophy & locked architecture
├── nucleus_vs_databricks.md           ← feature parity validation
├── nucleus_ctx_sdk_spec.md            ← THE product API
├── nucleus_asset_model_spec.md        ← the data primitive
├── nucleus_project_anatomy.md         ← user-facing layout
├── nucleus_cli_spec.md                ← operator-facing surface
├── nucleus_poc_plan.md                ← pre-build technical validation
└── nucleus_implementation_readiness.md ← THIS doc, the gate
```

8 documents. ~2500 lines total. Read in order; locked individually.

This is the complete pre-implementation toolkit.

---

*Honest preparation is the only way to perfect execution.*
