# Risks and Mitigations — Per-Phase Playbook

> **Source**: `nucleus_architecture_v4.1.md` §19 (Risk Register) + per-phase analysis.
> **Purpose**: For each phase, the top risks and concrete mitigation playbooks. Not sugar-coated.

---

## v0.2 — Public Launch Risks

### Risk 1: PyPI Publish Failure on Launch Day

**Probability**: Low | **Impact**: High

PyPI upload failure, name conflict, or OIDC trust misconfiguration delays the public launch announcement.

**Mitigation**:
1. Publish to TestPyPI 2 weeks before launch. Validate `pip install -i https://test.pypi.org/simple/ nucleus==0.2.0rc1`.
2. Configure GitHub Actions OIDC trust for PyPI 1 month before launch (not day-of).
3. Dry-run the full release workflow (`python scripts/release.py --dry-run`) in CI on every PR.
4. Rollback: if PyPI publish fails post-tag, `git tag -d v0.2.0` locally and fix; no force-push to `main`.

### Risk 2: Slow `pip install nucleus`

**Probability**: Medium | **Impact**: Medium

With 24+ runtime dependencies, cold `pip install nucleus` could take >2 min on slow connections, undermining the "fast" brand.

**Mitigation**:
1. Track install size in CI: `pip install nucleus && du -sh $(python -c "import site; print(site.getsitepackages()[0])")`.
2. Optional deps stay in extras (`[observability]`, `[multimodal]`).
3. Target: cold install <60 s on 100 Mbps. Benchmark in CI with `time pip install nucleus`.
4. If exceeded: audit which dep is the culprit (`pip install --verbose`); consider binary wheel pre-build.

### Risk 3: Workbench Scope Expands Beyond MVP

**Probability**: High | **Impact**: High

Design instinct will push to add "just one more feature" to Workbench, delaying the launch.

**Mitigation**:
1. Hard-cut: Monaco editor + asset graph + chat panel. **Full stop.** Any other feature is v0.3+.
2. `docs/roadmap/v0.2-public-launch.md` is the spec. If it's not in that doc, it's deferred.
3. Review Workbench PR against this list: does this touch Monaco, asset graph, or chat? If not, reject.

### Risk 4: AI Copilot Economics Break

**Probability**: Medium | **Impact**: Medium

LiteLLM costs escalate faster than anticipated (token costs, per-request fees). If Copilot costs >30% of Cloud margin, the economics break.

**Mitigation**:
1. Token usage metered per-session from day 1 (`intelligence/context.py` tracks token count).
2. Hard limit: `NUCLEUS_COPILOT_TOKEN_LIMIT=10000` env var (configurable).
3. BYOK (Bring Your Own Key) as the primary model — user provides their own OpenAI/Anthropic key.
4. Copilot Pro tier captures the premium if we host keys.

### Risk 5: Scheduled Assets Daemon Conflicts with Dagster

**Probability**: Medium | **Impact**: Medium

The schedule daemon uses Dagster's internal loop; multiple daemon processes create contention.

**Mitigation**:
1. Singleton lock: `nucleus schedule daemon` writes a PID file; second invocation warns and exits.
2. Test with `tests/chaos/test_concurrent_schedule_daemon.py`.
3. If Dagster loop contention is unresolvable: accelerate `nucleus-mini-scheduler` to v0.3.

---

## v0.3 — Hardening Risks

### Risk 1: Feature Creep from Beachhead Feedback

**Probability**: High | **Impact**: Medium

After v0.2 launch, GitHub Issues will contain hundreds of "would be nice if..." requests. Each individually reasonable, collectively scope explosion.

**Mitigation**:
1. Every v0.3 Issue must pass the 8-question gate before labeling `v0.3`.
2. Monthly triage: sort Issues by empirical impact (how many users hit this?), not enthusiasm.
3. Defer list maintained in `docs/roadmap/FOLLOW_UPS.md`.

### Risk 2: Distributed Compute Pressure

**Probability**: Medium | **Impact**: High

Beachhead teams outgrow local DuckDB. Requests for distributed compute (Spark, Ray, Flink) start arriving.

**Mitigation**:
1. Response: "Use Mode 2 (`compute=databricks`) for large workloads — graduation is a feature, not a failure."
2. v0.5 `compute=` dispatch does not require Nucleus to run Spark. We dispatch, they execute.
3. If >10% of users regularly hit DuckDB memory limits: activate DataFusion swap interface, build full adapter, provide `nucleus enable datafusion`.

### Risk 3: dlt Connector Quality Variance

**Probability**: Medium | **Impact**: Medium

dlt "verified" sources have varying test coverage and community maintenance. A poorly maintained source ships with bugs.

**Mitigation**:
1. Only use dlt **verified** sources (not community-tier). Check: https://dlthub.com/docs/dlt-ecosystem/verified-sources.
2. Each connector gets 5+ tests in Nucleus's own test suite (mocked, not live).
3. Upgrade smoke test per connector (`tests/upgrade_smoke/test_dlt_<source>.py`).
4. If a dlt source becomes unmaintained: remove it from `nucleus ingest --help`; direct users to `ctx.copy_from` pattern.

### Risk 4: Lakekeeper REST Catalog Operational Complexity

**Probability**: Medium | **Impact**: Low

Lakekeeper adds a new service to `nucleus up` docker-compose. Teams forget to run it; errors are confusing.

**Mitigation**:
1. `nucleus enable lakekeeper` is opt-in. Default stays filesystem catalog.
2. `nucleus up` checks Lakekeeper health if enabled; clear error if down: `NucleusEnvironmentError` "Lakekeeper is not running. Start it with `nucleus enable lakekeeper && nucleus up`."
3. Chaos test: Lakekeeper container killed mid-run → `NucleusCommitUnknownError` with fix hint.

---

## v0.5 — Multimodal Risks

### Risk 1: Identity Confusion — "Are you an AI Platform?"

**Probability**: High | **Impact**: High

Adding `ctx.agent`, Lance, Daft, and MCP server makes it easy for journalists and analysts to frame Nucleus as an AI platform.

**Mitigation**:
1. **Framing discipline**: AI features are always described as "AI-assisted data engineering" not "AI platform". Per ADR-002.
2. Marketing copy reviewed for banned terms before every blog post.
3. `ctx.agent` is sandboxed — requires human approval for every commit. This distinguishes Nucleus from autonomous AI agents.
4. MCP server is described as "thin adapter" not "agent substrate."

### Risk 2: Lance Ecosystem Maturity

**Probability**: Medium | **Impact**: Medium

Lance is Tier 0 but newer than Iceberg. API instability or breaking changes could require significant rework.

**Mitigation**:
1. Per Composability Constitution: Lance is Tier 0 (immortal) — no swap target needed.
2. Follow Lance releases closely: https://github.com/lancedb/lance/releases.
3. Pin exact version; upgrade one-component-per-PR per Constraint #11.
4. If Lance breaks compatibility: freeze at last known-good version; wait for stable release.

### Risk 3: LLM Cost at Agent Runtime Scale

**Probability**: Medium | **Impact**: High

`ctx.agent` generates code via LLM calls. If many engineers use it daily, token costs could exceed margins.

**Mitigation**:
1. `ctx.agent` always BYOK — never bundle API key costs.
2. Local model support: `NUCLEUS_COPILOT_PROVIDER=ollama/codellama` for cost-sensitive teams.
3. Token meter + cost limit enforced before every agent call.

---

## v0.7 — Cloud Tier Risks

### Risk 1: Mo 24 Decision Gate Fires Negative

**Probability**: Medium | **Impact**: Critical

If the Mo 24 gate triggers (no paying customers after 3 months beta, or founder velocity drops), v0.7 cloud tier may be deferred or pivoted.

**Mitigation**:
1. Track Mo 24 gate conditions from Mo 12 onward (not wait until Mo 24 to look).
2. If gate fires negative: OSS-only pivot (no cloud tier); extend beachhead focus; reduce scope to v0.5 features.
3. "Friendly to giants" posture means Databricks/Snowflake partners are always an alternative path.

### Risk 2: OIDC/Security Vulnerability in Cloud Tier

**Probability**: Low | **Impact**: Critical

A security bug in the OIDC flow exposes tenant data across tenants.

**Mitigation**:
1. Security review by external engineer before v0.7 GA.
2. `SECURITY.md` response SLA: CRITICAL = 14-day fix.
3. Bug bounty program (even informal) from v0.7 launch.
4. Multi-tenant isolation: tenant_id propagated to every storage path; S3 bucket policy enforced at AWS level.

---

## v1.0 — Production-Ready Risks

### Risk 1: Dagster License Pivot

**Probability**: Medium | **Impact**: High

Dagster Labs changes license from Apache 2.0 to BSL or similar (as HashiCorp, Redis, Elastic have done).

**Mitigation**:
1. `nucleus-mini-scheduler` must be buildable in 30 days (interface ready from v0.1; implementation triggered on event).
2. Monitor Dagster Labs fundraising, acquisition rumors quarterly.
3. Community fork: If Dagster Labs pivots, Nucleus contributes to the Apache-licensed fork.
4. Per Composability Constitution §9.5: "If a Tier 1 component goes hostile, activate swap target immediately."

### Risk 2: 30K LOC Ceiling Reached Before Key Features Land

**Probability**: Low | **Impact**: Medium

Code bloat in earlier phases consumes LOC budget; v1.0 features can't land without exceeding ceiling.

**Mitigation**:
1. Monthly LOC check (`scripts/loc_budget.py`). If >85% of phase ceiling: stop all non-critical features.
2. Active refactoring: replace verbose implementations with tighter ones.
3. Extract to separate packages early (vertical packs, connector plugins).

---

## Persistent Risks (All Phases)

### Risk: AI Hallucination in Production Code

**Probability**: High (if controls lax) | **Impact**: High

AI-generated code uses fabricated APIs that fail silently or late.

**Mitigation**:
1. `docs/internal/research/ai_hallucinations.md` log — every caught hallucination is recorded.
2. AI Output Verification Checklist (per `.cursor/rules/nucleus.mdc`) run after every AI generation.
3. CI verifies that all external library calls match pinned-version docs.
4. `# NEEDS VERIFICATION` annotation required whenever AI suggests an unfamiliar API.

### Risk: Vocabulary Drift

**Probability**: High (over time) | **Impact**: Medium

Contributors use "table" instead of "asset", "metastore" instead of "catalog", etc. User-facing confusion accumulates.

**Mitigation**:
1. `scripts/check_vocabulary.py` runs in CI; EXIT 1 blocks merge.
2. New contributors read `AGENTS.md §7` before first PR.
3. Drift Detection Pass every 4 weeks (per `.cursor/rules/nucleus.mdc`).

### Risk: Composability Interfaces Drift Over Time

**Probability**: Medium | **Impact**: Medium

Swap interfaces (DuckDB/DataFusion, Dagster/mini-scheduler) drift as the default evolves; interfaces become stale.

**Mitigation**:
1. Quarterly swap drill in CI: interface compiles + 5-10 smoke tests pass.
2. Any PR touching a Tier 1/2 component: contributor runs `pytest tests/swap/<component>_smoke.py`.
3. `scripts/check_layering.py` prevents cross-layer imports that would bind implementations together.

---

*Source: `nucleus_architecture_v4.1.md` §19 (Risk Register). Per-phase analysis by architect, 2026-05-15.*
