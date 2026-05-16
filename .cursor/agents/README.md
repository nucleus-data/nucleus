# Nucleus Custom Subagents

Project-scoped subagent registry per Cursor 2.4. Defines specialized roles the parent agent (typically Opus 4.7 in foreground) can delegate to.

**Authoritative reference**: [Cursor docs § Subagents](https://cursor.com/docs/context/subagents). Mechanism = `.cursor/agents/*.md` with YAML frontmatter. Project subagents take precedence over user-scoped `~/.cursor/agents/`. Cursor's parent agent IS the dispatcher; we do not define a separate dispatcher agent.

**Policy reference**: `AGENTS.md` §11.14 (Subagent Model Orchestration) — locks the role-based model stack and fallback rules.

---

## Layout

| File | Role | Tier per §11.14 | When to use |
|---|---|---|---|
| `swarm-implementer.md` | Bounded file-level coding work (PoC promotions, test scaffolds, API wiring, governance fixes) | Swarm | Single-shot scope, 25-40 min, clean DO-NOT-TOUCH boundary |
| `builder.md` | End-to-end multi-step iteration with build/test/fix loops | Builder | Multi-file feature, dependency upgrade, CI fix, refactor — needs autonomous iteration |
| `researcher.md` | Read official docs → produce a research/swap doc per AGENTS.md §11.12 | Research | Before integrating new external dep; before major version upgrade |
| `verifier.md` | Skeptical post-completion validation; read-only | Cross-tier | After any swarm-implementer or builder claims "done"; before accepting PoC promotions |
| `external-data-engineer-tester.md` | Roleplays a fresh external data engineer testing Nucleus via public docs only; PoC #5 beachhead validation | Research-tier (read-only) | Validate the 30-min beachhead metric without insider bias; periodic UX audits |

Architect role stays in foreground on the parent (Opus 4.7). We deliberately do NOT define a separate `architect.md` — duplicates the parent and creates split authority.

---

## Routing table

| Task pattern | Delegate to | Rationale |
|---|---|---|
| "Move `poc/pN_*/foo.py` to `src/nucleus/<layer>/foo.py` + tests" | `swarm-implementer` | Bounded scope, single coherent deliverable |
| "Add `<command>` to `src/nucleus/cli/main.py` + tests" | `swarm-implementer` | Bounded API wiring |
| "Wire `@nucleus.asset` decorator end-to-end (decorator + registry + tests + CLI + docs)" | `builder` | Multi-file, multi-step, needs iteration to land cleanly |
| "Upgrade `pyiceberg` 0.8.1 → 0.11.x" | `builder` | Full test sweep + migration loop |
| "CI is red — diagnose and fix" | `builder` | Debug/fix loop, may span many iterations |
| "Read `lakekeeper` docs + write `docs/internal/research/lakekeeper.md`" | `researcher` | Docs-grounded synthesis |
| "Compare Authentik vs Keycloak vs Okta for v0.3+ OIDC" | `researcher` | Ecosystem comparison |
| "Verify worker α's claim that PoC #2 is promoted cleanly" | `verifier` | Post-completion skeptical validation |
| "Confirm `nucleus up <10s` boot timing claim before merging PoC #4" | `verifier` | Performance claim verification |
| "Refactor `errors.py` to add `error_code` ClassVars per ADR-006" | foreground (architect) → may delegate execution to `builder` once design is locked | Architectural decision before implementation |
| "Decide whether to use Polars or DataFusion for the DataFrame layer" | foreground (architect) — ADR territory | 8-question gate + WRAP-vs-BUILD analysis |
| "Ratify a PROPOSED ADR" | foreground (founder + architect) | Cannot delegate ratification |
| "What's the latest version of `polars` on PyPI?" | foreground (single `WebFetch`) | Single tool call, no context needed |

---

## Escalation rules

### Bottom-up (worker → architect)

A subagent MUST escalate to foreground (architect) if:

1. **Scope ambiguity** — the prompt is unclear or the task is larger than declared
2. **Architecture invariant at risk** — any change touching `nucleus_architecture_v4.1.md` constraints (§3 in `nucleus.mdc`)
3. **8-question gate failure** — any answer "no" or "unclear" per `.cursor/rules/nucleus.mdc`
4. **Wrap-vs-build decision needed** — every BUILD requires an ADR per §11.5
5. **New dependency required** — must come through ADR per Constraint #11
6. **Failing test that was previously green** — regression introduced; STOP, don't push through
7. **External library doesn't match docs** — log hallucination per §11.12 + surface
8. **Time budget exceeded** — return with status (BLOCKED or TIMEOUT) rather than continuing
9. **Iteration ceiling reached** (Builder only) — stop and surface

### Top-down (architect → worker)

Architect (foreground) routes work based on shape:

```
Is it bounded, single-shot, <40 min, clean scope?     → swarm-implementer
Is it multi-step, iterative, may need debugging?       → builder
Is it "read docs and synthesize"?                      → researcher
Is it "validate this claim"?                           → verifier
Is it architectural / ADR / decision?                  → keep foreground
Is it a single tool call (one read, one search)?       → keep foreground
```

### Cross-worker

Subagents must NOT directly invoke other subagents in v0.1. If a worker needs follow-up work, it surfaces to the parent. The parent decides whether to launch a follow-up worker. This keeps the dependency tree shallow and debuggable.

(Cursor 2.5 supports nested subagents — we may revisit in v0.3 when workflows are more mature.)

---

## When NOT to delegate

Per Cursor docs §"When to use subagents" + AGENTS.md §11.14:

- **Single tool call tasks** — one `Read`, one `Grep`, one `WebFetch`. The startup overhead of a subagent exceeds the work.
- **Architectural decisions** — must go through 8-question gate + ADR process. Architect-only.
- **Founder ratifications** — ADR acceptance, PoC promotion sign-off, scope-creep adjudication. Founder + foreground architect.
- **Trivial edits** — typo fixes, single-line docstring tweaks, comment additions.
- **Clarification questions to the user** — handled by parent directly.

---

## Failure handling

If a worker exits with a nonzero status or surfaces a blocker:

1. **DO NOT auto-retry** — flakes are bugs (per §11.13). Surface the failure.
2. **Read the worker's final report** — usually contains the root cause
3. **Decide**:
   - **Retry with corrected scope** — if the failure was scope ambiguity
   - **Escalate to architect** — if architectural change needed
   - **Re-route to different agent type** — e.g., a swarm-implementer task that should've been a builder
   - **Accept partial success** — sometimes 80% landing is the right answer if the remaining 20% is a separate concern
4. **Run `verifier`** before accepting any nontrivial completion claim

---

## Model selection at invocation time

The `model:` field in each agent's frontmatter is `inherit` to maximize portability across plans and Max Mode settings. The parent (foreground architect) selects the actual model when launching via the Task tool, per §11.14:

- **Architect** (foreground): Claude Opus 4.7
- **Builder**: GPT-5.5 (preferred) → Sonnet 4.6 max-thinking (fallback)
- **Swarm**: Codex 5.3 (preferred) → Sonnet 4.6 max-thinking (fallback)
- **Research**: Gemini 3.1 Pro (preferred) → Opus 4.7 or Sonnet 4.6 (fallback by depth)
- **Verifier**: Sonnet 4.6 max-thinking

If a preferred model is unavailable in the current Cursor tool/runtime, the parent records the fallback choice explicitly in the subagent prompt — see §11.14 availability fallback policy.

> **Note on `model: inherit`**: per Cursor docs FAQ "Why is my subagent using a different model?", Cursor may override the configured model when (a) team admin restricts it, (b) Max Mode is required but disabled, or (c) the model isn't on the current plan. `inherit` is the most portable default; the parent explicitly overrides at Task tool invocation when role-specific routing is needed.

---

## Anti-patterns to avoid

Per Cursor docs §"Anti-patterns to avoid":

- ❌ **Dozens of generic subagents** — we have 4 focused roles. Adding more requires a clear distinct use case.
- ❌ **Vague descriptions** — every agent's `description` field is specific about when to use it. Update before adding.
- ❌ **Overly long prompts** — agents are 80-150 lines each. Anything longer dilutes focus.
- ❌ **Duplicating slash commands or skills** — if a task is single-purpose and doesn't need context isolation, use a Skill (`.cursor/skills/`) or rule (`.cursor/rules/`) instead.

---

## Cross-references

| File | Role |
|---|---|
| `AGENTS.md` §11.14 | Canonical model orchestration policy |
| `AGENTS.md` §11 (full) | Implementation workflow discipline |
| `AGENTS.md` §11.12 | Official docs verification (`researcher` discipline) |
| `AGENTS.md` §11.13 | Upgrade safety discipline (`builder` discipline for dep upgrades) |
| `.cursor/rules/nucleus.mdc` | Cursor-specific workflow tactics + 8-question gate |
| `nucleus_architecture_v4.1.md` | The architecture every subagent must respect |
| `nucleus_poc_plan.md` | What's being promoted; status of each PoC |
| `docs/FOUNDER_ACTION_QUEUE.md` | What's pending founder decision (NOT delegatable) |

---

## Versioning + maintenance

- Added: 2026-05-13 (after pre-v0.1 governance milestone)
- Owner: foreground architect (parent agent)
- Review cadence: monthly + on any major workflow incident

Adding a new agent? Update this README + add an entry in AGENTS.md §11.14 cross-reference.
