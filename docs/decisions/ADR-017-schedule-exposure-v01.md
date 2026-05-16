# ADR-017: Schedule Exposure via `@nucleus.asset(schedule=...)` (v0.1.1 / v0.2-preview)

> **Status**: IMPLEMENTED (v0.2.1 — mini-scheduler path)
> **Date**: 2026-05-14 · **Amended**: 2026-05-15 · **Decider**: Builder (ratified by solo founder)
> **Tags**: scheduling, dagster, cron, sdk, cli, v0.1.1, v0.2.1, mini-scheduler
> **Related**: ADR-001 (wrap-not-build precedent), ADR-005 (API freeze policy — Beta tier),
> ADR-006 §Initial code assignment (NE5xxx allocations), ADR-012 (pin matrix),
> `docs/specs/nucleus_architecture_v4.1.md` §6.3 (Coordination), §6.7 (yield-to-giants),
> `docs/specs/nucleus_ctx_sdk_spec.md` §5 (decorator surface), `docs/specs/nucleus_cli_spec.md` §3.

---

## Context

The Databricks/Snowflake parity analysis flagged scheduling as the #1 production-readiness gap:
users declare `@asset(schedule=...)` in both platforms. Nucleus currently has no scheduling surface —
assets can only be triggered manually via `nucleus run <key>`.

The architecture already pins Dagster as a Tier-2 orchestration substrate hidden behind `ctx`
(per v4.1 §6.3: "Dagster remains a pinned dep for future scheduling"). Adding a thin scheduling
façade is the logical next step without violating any of the 11 hard constraints.

**Forces in tension:**
- Scheduling is classified as v0.5 in the current roadmap (v4.1 §18). Pulling it forward serves the
  beachhead metric (5-engineer startup team needs `@daily` to replace manual `nucleus run` scripts).
- We MUST NOT roll our own scheduler (Constraint #3). Dagster already does it; we expose a façade.
- We MUST NOT expose Dagster types to users (v4.1 §6.4 Error Translation discipline).
- Adding `croniter==3.0.4` is the first new runtime dependency in this PR (latest <4 release
  compatible with `dagster==1.9.5`'s `croniter<4` constraint). One component per PR
  (Constraint #11).

---

## Decision

> **Wrap Dagster's scheduling machinery. Expose a thin façade: `@nucleus.asset(schedule=...)` kwarg
> (cron string or shorthand) + `nucleus schedule list` / `nucleus schedule preview` CLI commands.
> All schedule-on/schedule-off/trigger operations deferred to v0.2 (stubs only).**

### 1. Wrap choice: Dagster ScheduleDefinition

Dagster `ScheduleDefinition` (dagster==1.9.5) is already pinned in `pyproject.toml`. Key facts
verified in official docs at https://docs.dagster.io/api/python-api/schedules-sensors:
- `ScheduleDefinition(name, cron_schedule, job, ...)` — takes a cron string directly.
- `cron_schedule` accepts a `str` or `Sequence[str]`.
- No JVM dependency — Dagster is a Python-native scheduler.

No alternative schedulers were evaluated because Dagster is already a Tier-2 pinned dep and the
Composability Constitution (v4.1 §9) requires interface + smoke tests, not a full second impl.

### 2. Cron parsing: croniter==3.0.4

Croniter is needed for two v0.1.1 tasks the CLI needs without spinning a Dagster daemon:
1. **Validation** at decorator time: `croniter.is_valid(expr)` → bool.
2. **Preview** (`nucleus schedule preview <key>`): iterate `croniter.get_next()` N times.

Docs: https://pypi.org/project/croniter/  
Version: 3.0.4 (released 2024-10-25, MIT license, Python >=2.6)  
Version constraint: `dagster==1.9.5` requires `croniter<4,>=0.3.34`. The latest
`<4` release is 3.0.4. The API surface used (``is_valid``, ``croniter.get_next()``)
is stable across the entire 0.3.x–3.x range. croniter is already a transitive dep
via dagster; this pin makes the governance explicit.

| Alternative | Reason not chosen |
|---|---|
| Pure-Python mini-parser (hand-rolled) | Violates wrap-not-build (viable OSS exists) |
| `python-crontab` | Less-used, heavier, GPL2 |
| `schedule` (plaintext `every().day`) | Different DSL, no cron interop |
| Dagster daemon for validation | Requires full Dagster boot — kills boot-time PoC #4 result |

### 3. `@nucleus.asset(schedule=...)` surface

Accepts:
- Standard 5-field cron: `"0 2 * * *"` — validated by `croniter.is_valid()`.
- Shorthand aliases (normalized before storage):
  - `@hourly` → `"0 * * * *"`
  - `@daily` / `@midnight` → `"0 0 * * *"`
  - `@weekly` → `"0 0 * * 0"`
  - `@monthly` → `"0 0 1 * *"`
  - `@yearly` / `@annually` → `"0 0 1 1 *"`
- `None` (default) — no schedule.

Stored as normalized cron string in `_AssetDefinition.schedule`. Validated at decoration time
(import time) so errors surface immediately.

### 4. Error codes (ADR-006 NE5xxx — L4 Experience, validated at SDK boundary)

| Code | Class | Trigger |
|---|---|---|
| NE5005 | `NucleusScheduleParseError` | Invalid cron expression at decoration time |
| NE5006 | `NucleusScheduleNotFoundError` | `schedule preview` for unknown / unscheduled asset |
| NE5007 | `NucleusScheduleAlreadyActiveError` | (Reserved for v0.2 `schedule on`) |
| NE5008 | `NucleusFeatureDeferredError` | `schedule on/off/trigger` stubs raise this with v0.2 message |

NE5001-5004 are already allocated (ConfigError, AuthError, RunCancelled, EnvironmentError).

### 5. Stability tier (ADR-005 §2)

`schedule=` kwarg: **Beta @ v0.1.1 → Stable @ v0.5 → Frozen @ v1.0** — same ladder as
the rest of `@nucleus.asset`.  
`nucleus schedule list/preview`: **Beta** — governed by `docs/specs/nucleus_cli_spec.md`.  
`nucleus schedule on/off/trigger`: **deferred stub** — raises `NucleusFeatureDeferredError`.  
`coordination/schedules.py`: **Internal** — not part of public surface.

### 6. What is NOT in this PR (v0.2)

- Actual Dagster daemon scheduling (running asset bodies on a cron schedule requires the Dagster
  scheduler to be active — deferred to v0.2).
- `nucleus schedule on/off/trigger` — stubs only.
- Multi-timezone support — cron runs in UTC; timezone kwarg deferred.
- Partition-aware scheduling — deferred to v0.3+ alongside partition execution.

---

## 8-Question Gate (`.cursor/rules/nucleus.mdc` §"8-Question Gate")

| # | Question | Answer |
|---|---|---|
| 1 | Maps to one of the five architectural layers? | **Yes** — Coordination (Layer 3) hosts `schedules.py`; SDK (Layer 4/SDK side-channel) hosts the `schedule=` decorator kwarg; Experience (Layer 5) hosts the CLI. No cross-layer leakage. |
| 2 | Serves the <30 minute beachhead metric? | **Yes** — declared but not auto-running schedules let a 5-eng team replace ad-hoc `cron + nucleus run` shell scripts with a single declarative kwarg + `nucleus schedule list` for visibility. Stays inside the 30-min budget because validation is at import time only; no daemon boot. |
| 3 | Wrap possible instead of build? | **Yes** — Dagster `ScheduleDefinition` (already a Tier-2 pinned dep) + `croniter` (transitive via Dagster) cover validation, preview, and future daemon execution. Zero custom scheduler code. |
| 4 | Preserves no-JVM constraint? | **Yes** — Dagster is Python-native; croniter is pure Python. No JVM introduced. |
| 5 | Preserves local-identical-to-prod? | **Yes** — the declared `schedule=` metadata is the same in dev/CI/prod. The daemon (v0.2) will use Dagster's standard scheduling, identical to whatever the user runs in prod. |
| 6 | Stays within 30K LOC budget? | **Yes** — ~720 LOC across src+ADR added; total `src/nucleus/` now ~4,549 LOC (56.9% of v0.1's 8K ceiling; 15.2% of v1.0's 30K ceiling). |
| 7 | Triggered by empirical telemetry, not anxiety? | **Partial / Founder override** — internal Databricks/Snowflake parity analysis + PoC #5 fresh-eyes tester (Checkpoint 7 fail = no asset discoverability) are competitive-research + analog UX signals, NOT direct customer telemetry from the 5-eng beachhead. The founder is approving this as a pre-emptive feature pull-forward, accepting the risk that v0.2 daemon wiring (the actual user-visible value) is required to fully realise the ROI. Surfaced as explicit gate override. |
| 8 | Required for v0.1 Hello World, or can it defer to v0.2/0.3/0.5? | **Roadmap deviation** — Current v4.1 §18 places scheduling at v0.5. This PR pulls the **declarative surface only** forward to v0.1.1 (Beta), with the **execution daemon** still landing in v0.2 as scheduled. The 5-engineer beachhead persona uses scheduling as a "declared intent" placeholder during evaluation — the actual cron-driven runs happen post-graduation OR via v0.2 daemon. Founder accepts the surface-without-daemon gap as a manageable v0.1.1 risk; users who try `schedule on` get a clear `NucleusFeatureDeferredError` v0.2 message. |

Gate verdict: **PASS (with Q7 founder override + Q8 explicit roadmap deviation)**. Both deviations are documented above and the founder ratifies with eyes open.

---

## OSS Options Considered

| Option | Status | Reason |
|---|---|---|
| **Dagster ScheduleDefinition** (pinned) | **CHOSEN** | Already a Tier-2 dep; no JVM; Python-native |
| APScheduler | Not chosen | Not in our stack; one-component-per-PR discipline |
| Airflow | Not chosen | JVM-adjacent, breaks Constraint #1 |
| cron + subprocess | Not chosen | Custom scheduler violates Constraint #3 |
| Roll our own cron loop | Not chosen | Custom scheduler violates Constraint #3 |

---

## Consequences

- **LOC impact**: ~400-700 LOC new (coordination/schedules.py ~180 LOC + CLI adds ~130 LOC +
  test files ~200 LOC).
- **New runtime pin**: `croniter==3.0.4` (MIT, ~70M monthly downloads, Python >=2.6). Latest
  release on the `<4` line, forced by `dagster==1.9.5`'s transitive `croniter<4,>=0.3.34`
  constraint. API surface used (`is_valid`, `get_next`) is stable across 0.3.x–3.x.
- **ADR-012 amendment**: Active pin matrix gains 1 row.
- **docs/internal/compatibility.md**: +1 row (croniter).
- **API surface additive only** — existing `@nucleus.asset` callers unaffected (`schedule=None` default).
- **`nucleus schedule on/off/trigger` deferred** — users who try those commands get a clear
  `NucleusFeatureDeferredError` with a "v0.2" message.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Croniter 4.x changes API from 3.x | Version-pinned to 3.0.4; upgrade smoke test required before bumping; major bump gated on Dagster 2.x upgrade that relaxes `croniter<4` |
| Dagster ScheduleDefinition API changes in next minor | dagster pinned to 1.9.5; per Constraint #11 one-component-per-PR |
| Schedule validation false-positives | `croniter.is_valid()` + test coverage for edge cases |
| User confusion: `@nucleus.asset(schedule="@daily")` doesn't auto-run | Clear `NucleusFeatureDeferredError` on `schedule on` with "v0.2" message; docs explain the façade |
| LOC budget overshoot | Measured in the PR; coordination/schedules.py has 250-LOC hard ceiling |

---

## Verification plan

1. `pytest tests/sdk/test_schedule_kwarg.py tests/coordination/test_schedules.py tests/cli/commands/test_schedule.py`
2. All 8 governance scripts pass (see smoke-test path in task brief).
3. `nucleus schedule list` shows the declared assets in a test project.

---

## Rollback

```
pip install nucleus==<previous>   # reverts croniter and schedule surface together
git revert <PR-SHA>
```

No data migration required (schedule metadata is in-process registry only, not persisted).

---

## Docs URL

- Dagster schedules: https://docs.dagster.io/api/python-api/schedules-sensors#dagster.ScheduleDefinition
- Dagster automation: https://docs.dagster.io/guides/automate/schedules
- croniter: https://pypi.org/project/croniter/
- v4.1 §6.3 (Coordination layer + Dagster substrate)
- ADR-006 §NE5xxx allocations

---

**Proposed**: 2026-05-14 — builder wave.
**Amended**: 2026-05-15 — Wave 2 P0-1 daemon builder.

---

## Amendment: v0.2.1 Mini-Scheduler Fallback

**Status**: IMPLEMENTED

Per `AGENTS.md` §4 (no custom scheduler; Dagster wrapped OR mini-scheduler fallback by v1.0),
the active scheduling daemon lands via the **mini-scheduler path** in v0.2.1.

### Why not Dagster SchedulerDaemon?

Dagster's `SchedulerDaemon` (dagster==1.9.5) requires:
- A full `DagsterInstance` with `DAGSTER_HOME` directory configured
- A `workspace.yaml` / `Definitions` object with all jobs pre-registered
- A persistent daemon process communicating with a DagsterInstance gRPC server

This is too heavy for the beachhead (5-engineer startup team, `git clone` → running in <30min).
The `SchedulerDaemon` is not importable as a standalone component in dagster==1.9.5
(verified: no `dagster._daemon.run.SchedulerDaemon` public path).

### Mini-scheduler design

`coordination/daemon.py` implements:
- `start_daemon(project_root, foreground, max_iters)` → spawns detached subprocess
- `stop_daemon(project_root, timeout)` → SIGTERM via psutil (cross-platform)
- `trigger_asset(asset_key, warehouse_dir)` → one-shot AMA call
- `get_daemon_status(project_root)` → pid + schedule overview
- `DaemonStatus` dataclass (no Dagster types)
- `_daemon_main` loop: every 5s, `list_schedules()` + croniter + `materialize_asset`
- Pidfile at `<project_root>/.nucleus/.daemon.pid`
- Error codes: NE5012 (start), NE5013 (not running), NE5014 (already running)

Zero Dagster types cross the outbound boundary. Enforced by `scripts/dagster_leak_check.py`.

Dagster's role in Nucleus is PRESERVED for:
- `coordination/asset_materialization.py` (data-write path)
- `coordination/error_translation.py` (exception translation)
- Future Dagster daemon scheduling (v0.5+) when `DagsterInstance` wiring is justified

### CLI commands activated (v0.2.1)

- `nucleus schedule on [--foreground]` — start daemon
- `nucleus schedule off [--timeout SEC]` — stop daemon
- `nucleus schedule trigger ASSET_KEY` — one-shot run
- `nucleus schedule status` — Rich table of running state + schedules
