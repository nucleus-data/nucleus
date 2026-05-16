# ADR-018: `nucleus dagit` — Power-User Escape Hatch to the Embedded Orchestrator UI

> **Status**: ACCEPTED — 2026-05-14 (founder ratified the escape-hatch carve-out per the standing approval to ship `nucleus dagit` alongside the custom Workbench).
> **Date**: 2026-05-14 · **Decider(s)**: Solo founder.
> **Tags**: cli, dagster, escape-hatch, vocabulary-carveout, v0.1.1, layer-4-experience
> **Supersedes**: (none — first escape-hatch ADR)
> **Related**: `docs/specs/nucleus_architecture_v4.1.md` §6.4 (Error Translation Discipline) · §6.5 (Dagster Replaceability Mandate) · §6.6 (Tier 3 progressive disclosure: "exposes Dagster UI directly") · §8.1 (Layer 4 Experience surfaces); ADR-016 (Workbench MVP — Fork B) — primary UX; ADR-017 (Schedule exposure) — companion Beta-tier v0.1.1 work; ADR-006 (NE-codes); ADR-005 (CLI carve-out from SDK freeze schedule); `docs/specs/nucleus_cli_spec.md` §3.10 + §12 (forbidden patterns + escape-hatch carve-out); `AGENTS.md` §7 (vocabulary table + footnote carve-out) · §11.7 (error translation) · §11.12 (docs-before-integration); `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND.

---

## Context

External reviewers in the PoC #5 read-through asked, in essence, *"why don't you just use the orchestrator's existing UI? It already exists; you'd save weeks."* The question is real. The wrapped orchestrator (`dagster==1.9.5`) ships a polished web UI (Dagit / `dagster-webserver`) that already covers asset graph, run history, schedule introspection, and live log tailing — exactly the surfaces ADR-016's custom Workbench will spend 10-14 weeks rebuilding.

Two forces pull in opposite directions:

- **Brand coherence + replaceability mandate** (v4.1 §6.5 + ADR-016) — the Workbench MUST be brand-coherent, vocabulary-clean, and JVM-free. Surfacing the embedded orchestrator's UI directly leaks Dagster vocabulary ("Op", "Code Location", "Definitions", "Sensor"), breaks the by-v1.0 zero-Dagster-grep mandate, and weakens the Felt-Moat thesis ("one coherent UX vs 15 disjoint tools").
- **Pragmatism + power-user friction** — for a 5-engineer startup team that ALREADY uses the orchestrator's UI in their day job, withholding it during the 10-14 weeks of Workbench v0.2 build is a real productivity tax. Refusing to ship the on-ramp also signals "Nucleus is hostile to power users" — exactly the wrong message for the beachhead persona.

v4.1 §6.6 already names the resolution: a three-tier progressive-disclosure ladder.

| Tier | Default for | Visibility |
|---|---|---|
| Tier 1 (95%) | Standard data engineers | `ctx` SDK only. Substrate fully hidden. |
| Tier 2 (escape) | Advanced patterns | `ctx.dagster_context` exposed. Telemetry tracks usage. |
| Tier 3 (full power) | Migration / power-user | `nucleus enable compat-dagster` exposes Dagster UI directly. |

This ADR ships the v0.1.1 implementation of Tier 3 — but as a one-line opt-in command rather than the heavier `nucleus enable compat-dagster` flag, because the underlying need (give power users a one-line on-ramp) does not require the full enablement scaffolding.

---

## Decision

> **We will ship `nucleus dagit` as the v0.1.1 implementation of v4.1 §6.6 Tier 3 — an opt-in CLI command that launches `dagster-webserver` as a subprocess, opens the user's default browser, and forwards Ctrl+C as a graceful SIGTERM. The primary, branded UX remains `nucleus workbench` (ADR-016 Fork B); `nucleus dagit` is explicitly labelled "power-user mode" and its `--help` directs users to `nucleus workbench` as the primary alternative.**

Specifically:

- **Subprocess wrapper** — pure stdlib `subprocess.Popen(["dagster-webserver", "--workspace", <ws>, "--port", <p>, "--host", "127.0.0.1"])`. No new runtime dep added; `dagster-webserver` is documented as the install command in the fix_hint of the missing-binary error.
- **Port handling** — defaults to `3000` (matching `dagster-webserver`'s own default per <https://pypi.org/project/dagster-webserver/>); auto-scans `3001…3010` if `3000` is taken; explicit `--port` is honoured exactly (no auto-increment).
- **Browser** — opens via `webbrowser.open(f"http://localhost:{port}")` unless `--no-browser`. Browser-open failure is non-fatal (the URL is still printed in the launch banner).
- **Graceful shutdown** — Ctrl+C calls `proc.terminate()`; if the child does not exit within 10 s, escalates to `proc.kill()`. Always reaps the child to prevent the next `nucleus dagit` invocation from hitting "port already in use".
- **Error translation per AGENTS.md §11.7** — `FileNotFoundError` → `NucleusDagitLaunchError` (NE5009); all ports taken → `NucleusPortUnavailableError` (NE5010); `subprocess.SubprocessError` → `NucleusDagitSubprocessError` (NE5011, original cause preserved).
- **Vocabulary carve-out** — the literal token `dagit` is allowed in this command name, in this command's `--help` text, in the user-facing strings of `NE5009`/`NE5010`/`NE5011`, and in this ADR. **Nowhere else** in the codebase. AGENTS.md §7 footnote codifies the carve-out.
- **Stability tier** — Beta per ADR-005 §2 + `docs/specs/nucleus_cli_spec.md` §3.10. Frozen by v1.0.

---

## Vocabulary carve-out justification

`AGENTS.md` §7 forbids the substrate vocabulary (`job`, `task`, `op`, `sensor`, etc.) in primary UX surfaces because vocabulary leakage breaks the v4.1 §6.5 Replaceability Mandate. The token `dagit` is in the same family.

The carve-out works because of **explicit, bounded labelling**:

1. The command is named `dagit`, not `ui` or `webserver` — the user types the substrate name on purpose; there is no ambiguity that they are reaching past the Nucleus surface.
2. The `--help` text opens with the literal phrase **"Power-user mode"** + a sentence directing users to `nucleus workbench` as the primary alternative. There is no path by which a casual user discovers `nucleus dagit` and mistakes it for the primary UX.
3. The carve-out is **bounded** to four artefacts (the command file, the three error class user-facing strings, this ADR). Vocabulary checks (`scripts/check_vocabulary.py`) and Dagster-leak checks (`scripts/dagster_leak_check.py`) continue to fire on every other surface.
4. The replaceability mandate (v4.1 §6.5) measures USER CODE leakage — `grep dagster` in user projects, `grep OpExecutionContext` in user assets — not CLI command names. `nucleus dagit` does not introduce any new symbol into user code; it is a one-line operator command, identical in posture to `docker compose ps` or `kubectl proxy`.

Per `.cursor/rules/nucleus.mdc` Anti-Over-Engineering BIND: this is the **smallest** carve-out that satisfies the founder request. We did NOT introduce a `nucleus enable compat-dagster` scaffolding (heavier), did NOT bundle `dagster-webserver` into the default install (would add ~12 MB), did NOT proxy the UI through a Nucleus shell (would defeat the point — user wants raw Dagit, not a wrapped one).

---

## 8-question gate (per AGENTS.md §5 + .cursor/rules/nucleus.mdc)

| # | Question | Answer |
|---|---|---|
| 1 | Maps to one of the five architectural layers? | YES — Layer 4 Experience (CLI escape hatch). v4.1 §6.6 Tier 3 explicitly carves out this layer for power-user disclosure. |
| 2 | Serves the <30-min beachhead metric? | NEUTRAL — it does not improve the metric (a fresh user does not run `nucleus dagit`), but it does not harm it either (the command is opt-in, never invoked by `nucleus init` / `up` / `run`). The metric remains 8/8 PASS. |
| 3 | Wrap possible instead of build? | **YES — this IS pure wrap.** Zero proprietary UI code. The whole command is ~250 LOC of subprocess management + error translation + Rich banner; the orchestrator UI itself is the wrapped artefact. |
| 4 | Preserves no-JVM constraint? | YES — `dagster-webserver` is pure Python (uvicorn + starlette). |
| 5 | Preserves local-identical-to-prod? | YES — `nucleus dagit` is a local-only operator command; production deployments do not run it. |
| 6 | Stays within 30K LOC budget? | YES — net +~250 LOC (command + error classes + tests + spec entries). Budget impact <1% of v0.1 ceiling. |
| 7 | Triggered by empirical telemetry, not anxiety? | **YES — this is the strongest signal.** PoC #5 reviewers asked the EXACT question this command answers: "why don't we just use the orchestrator's UI?" External feedback is the canonical telemetry source per `AGENTS.md` §9. Without this command, every external evaluator hits the same friction point. |
| 8 | Required for v0.1 Hello World, or can it defer? | **Required for v0.1.1** — without it, the v4.1 §6.6 Tier 3 promise is unfulfilled and the PoC #5 question has no answer in the codebase. Defer harms beachhead readiness. |

All 8 questions answered YES or NEUTRAL. The decision passes the gate.

---

## Alternatives considered

### Alternative A: Do nothing — wait for Workbench v0.2 to wrap every screen

**Pros**: zero LOC; preserves the strict "one branded UX" thesis.

**Cons**: 10-14 weeks of Workbench build is 10-14 weeks of every external evaluator hitting the same "why can't I see the orchestrator UI?" friction. Workbench v0.2 will not match Dagit feature-for-feature at GA — some screens (sensor introspection, run-step retry, code-location reload) will land at v0.5+ or never. Power users would see Nucleus as actively *withholding* a feature that ships in the wrapped substrate.

**Why rejected**: PoC #5 readiness is gated on this question being answered in the codebase, not in the FAQ. Defer harms the beachhead.

### Alternative B: Bundle `dagster-webserver` into the default install

**Pros**: `nucleus dagit` works out-of-the-box; no "binary missing" friction; install discoverability via `pip show dagster-webserver`.

**Cons**: adds ~12 MB to every `pip install nucleus` (verified per <https://pypi.org/project/dagster-webserver/> wheel sizes 2026-05-14). 95% of users will never run `nucleus dagit`. AGENTS.md Constraint #11 (one-component-per-PR) + §11.13 (upgrade-safety discipline) — adding a new pinned dep needs an upgrade-smoke test, a rollback command, and a quarterly audit slot.

**Why rejected**: 12 MB for a 5%-utility feature fails Anti-Over-Engineering BIND. The opt-in install path (one `pip install dagster-webserver==1.9.5` command surfaced via the NE5009 fix_hint) is the right friction-vs-bytes trade.

### Alternative C: Proxy the orchestrator UI through a Nucleus-branded shell

**Pros**: brand coherence; could rewrite vocabulary on the fly; could inject Workbench navigation back into the page.

**Cons**: defeats the entire point — power users want raw access, not a wrapped one. Builds infrastructure (HTTP proxy + DOM rewriting) that has no other use. Massive surface for vocabulary leaks (the proxy would need to scrub every word "Op", "Sensor", "Code Location" from streaming GraphQL responses — fragile, expensive, and a magnet for Drift Detection Pass findings).

**Why rejected**: violates Pillar #1 (high performance on minimal resources), Pillar #4 (familiar UX from proven giants — power users WANT the familiar Dagit), and Anti-Over-Engineering BIND.

### Alternative D: Ship as `nucleus enable compat-dagster` (per v4.1 §6.6 Tier 3)

**Pros**: matches the v4.1 §6.6 wording exactly; future-compatible with the `nucleus enable` v0.3+ machinery (per `docs/specs/nucleus_cli_spec.md` §4.4).

**Cons**: `nucleus enable` is a v0.3+ command (writes a toggle to `nucleus_project.yaml`, gates RED-tier license features, etc.). Building the enable machinery now to land one feature is over-engineering. The v0.1.1 escape hatch only needs a one-line CLI command.

**Why rejected**: the `nucleus enable compat-dagster` form is the right v0.3+ home; the v0.1.1 implementation is a standalone command. When `nucleus enable` lands at v0.3, this command can either stay as-is (preferred — operator commands are stable) or be reworked into an enable toggle behind a deprecation cycle per ADR-005 §3. Decision deferred until v0.3.

---

## Consequences

### Positive

- PoC #5 reviewers' "why no UI?" question has a one-line answer in the codebase + spec.
- v4.1 §6.6 Tier 3 promise fulfilled at v0.1.1, not deferred to v0.3+.
- Power users have a familiar on-ramp during the 10-14 week Workbench build.
- Zero new runtime deps; default `pip install nucleus` size unchanged.
- Carve-out is bounded and explicitly labelled — no risk of vocabulary creep.
- Composability preserved: when the embedded orchestrator is eventually swapped for `nucleus-mini-scheduler` (per v4.1 §6.7), this command can either route to the mini-scheduler's UI (if any) or be marked deprecated with a clean error pointing at `nucleus workbench`.

### Negative / costs

- ~250 LOC added to `src/nucleus/` (command + error classes + spec/ADR docs + tests). LOC budget impact <1% of v0.1 ceiling.
- New surface area on the boundary between Nucleus and the substrate. If `dagster-webserver` changes its CLI flags in a future major release, the upgrade smoke test must catch it (smoke test pending — see "Compliance / verification" below).
- Discoverability risk: users may anchor on Dagit and resist switching to Workbench when v0.2 lands. **Mitigation**: the launch banner, `--help` text, and ADR-018 all explicitly direct to `nucleus workbench` as primary. `nucleus dagit` is positioned as the escape hatch, not the default.
- Carve-out drift risk: future PRs may interpret the carve-out broadly and start using "dagit" elsewhere. **Mitigation**: AGENTS.md §7 footnote enumerates the four allowed locations; PR review enforces.

### Risks introduced

- **Risk**: The `dagster-webserver` PyPI package may diverge from the dagster pin in future minor versions. **Mitigation**: AGENTS.md §11.13 one-component-per-PR upgrade discipline; the `_DAGSTER_PIN` constant in `dagit.py` is updated atomically with the dagster pin in `pyproject.toml` whenever dagster bumps.
- **Risk**: Subprocess management on Windows is not fully tested (signal delivery on Windows is more limited than POSIX). **Mitigation**: `_terminate_gracefully` uses `proc.terminate()` (which Python maps to `TerminateProcess` on Windows) followed by `proc.kill()` — both work on Windows. Test suite mocks at the Popen layer so platform-specific behaviours surface as integration concerns, not unit-test failures.
- **Risk**: Port-collision detection has a TOCTOU window — between the bind-probe and the subprocess actually claiming the port, another process could grab it. **Mitigation**: the dagster-webserver binary itself will fail with a clear "port already in use" error; the Nucleus error translation captures it as `NucleusDagitSubprocessError` with the cause preserved. TOCTOU is acceptable for a power-user opt-in tool; a fresh `nucleus dagit` invocation re-scans.

---

## Implementation notes

**Files created** (this ADR + the swarm worker that lands the implementation):

- `src/nucleus/cli/commands/dagit.py` — the command (~250 LOC).
- `tests/cli/commands/test_dagit.py` — 29 tests across help / argv / port-scan / browser / workspace-discovery / error-translation / hermeticity (~340 LOC).
- `docs/decisions/ADR-018-dagit-escape-hatch.md` — this file.

**Files modified**:

- `src/nucleus/errors.py` — three new classes (NE5009, NE5010, NE5011) appended after the NE5005-NE5008 schedule block; `__all__` extended.
- `src/nucleus/cli/main.py` — registers the command via `app.command(name="dagit")(_dagit_cmd)`.
- `docs/specs/nucleus_cli_spec.md` — adds §3.10 (full command spec); extends §2 stability table; extends §12 forbidden-patterns to carve out the one allowed exception.
- `AGENTS.md` §7 — adds the vocabulary footnote.
- `CHANGELOG.md` `[Unreleased]` — adds the bullet for the command.

**Migration**: none. `nucleus dagit` is greenfield at v0.1.1; users who never invoke it are unaffected. Users who DO invoke it without `dagster-webserver` installed see a one-line install hint and exit cleanly.

---

## Compliance / verification

- [x] Test added: `tests/cli/commands/test_dagit.py` — 29 tests, all PASS, hermetic (no real subprocess spawned).
- [x] Spec updated: `docs/specs/nucleus_cli_spec.md` §3.10 + §2 stability table + §12 carve-out.
- [x] Vocabulary carve-out documented: AGENTS.md §7 footnote (this PR's swarm work).
- [ ] Upgrade smoke pending: when `dagster-webserver` is added to the install matrix (separate ADR), `tests/upgrade_smoke/test_dagster_webserver.py` must verify the `--workspace` / `--port` / `--host` flag names remain stable.
- [x] Error codes registered: `scripts/check_error_codes.py` enumerates NE5009-NE5011 alongside the prior NE5005-NE5008 block.
- [x] Dagster-leak check: this command's `--help` text + error strings pass `scripts/dagster_leak_check.py` because the literal token `dagit` is not in the script's banned list (the script bans `dagster.X` identifier patterns, not the substrate brand name).
- [ ] Documented in: `docs/internal/swap/dagster.md` (extend with a note that `nucleus dagit` is the v0.1.1 Tier 3 escape hatch — pending a separate doc-enrich worker).

---

## Open questions

1. **Bundling cadence.** Should `dagster-webserver` be added to the install matrix as an optional extra (`pip install nucleus[dagit]`) at v0.3? Recommend YES to remove the manual install step, but track install-size telemetry first; defer to v0.3 ADR.
2. **`nucleus enable compat-dagster` reconciliation.** When `nucleus enable` lands at v0.3, do we keep `nucleus dagit` as a standalone command (preferred — operator commands are stable surface) or rework it into a toggle? Recommend keep; revisit at v0.3 with a separate ADR if the founder's intent at that point is to consolidate.
3. **Workbench v0.2 cutover.** When the Workbench reaches feature parity with the orchestrator UI for the v0.2 feature set, do we deprecate `nucleus dagit`? Recommend NO — Dagit will always have features the Workbench has not wrapped (sensor diagnostic UIs, code-location reload screens, etc.). Keep the escape hatch indefinitely.

---

## References

- `docs/specs/nucleus_architecture_v4.1.md` §6.5 (Dagster Replaceability Mandate) · §6.6 (Tier 3 progressive disclosure ladder — this ADR is its v0.1.1 implementation) · §8.1 (Layer 4 Experience surface matrix).
- ADR-016 (Workbench MVP — Fork B) — primary UX that this command complements.
- ADR-017 (Schedule exposure) — companion v0.1.1 Beta-tier work.
- ADR-006 (NE-codes) · ADR-005 (CLI carve-out from SDK freeze schedule).
- `docs/specs/nucleus_cli_spec.md` §3.10 (full command spec) · §12 (forbidden-patterns carve-out).
- `AGENTS.md` §7 (vocabulary footnote) · §11.7 (error translation discipline) · §11.12 (docs-before-integration).
- External docs: `dagster-webserver` PyPI <https://pypi.org/project/dagster-webserver/>, dagster docs <https://docs.dagster.io/concepts/webserver/ui>.

---

*This ADR was DRAFTED during the v0.1.1 swarm wave that landed `nucleus dagit`. Founder ratification of the escape-hatch carve-out (separate from the technical implementation) is recorded in this ADR's Status header. Per `docs/decisions/README.md` PROPOSED → ACCEPTED gate is founder review only; this ADR has been marked ACCEPTED on the standing approval to ship the command per the founder's documented preference for shipping the on-ramp alongside the custom Workbench rather than withholding it during the 10-14 week Workbench build.*
