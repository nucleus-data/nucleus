# Recipes

End-to-end runnable walkthroughs that turn the v0.1 beachhead promise — *"5-engineer team, `git clone` → BI-ready Iceberg asset on a laptop in <30 minutes"* per [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) §1.5 — into copy-pasteable Python and shell. The connector scope (Postgres / CSV / file URLs at v0.1; dlt at v0.3+) is locked by [ADR-002 §8](../decisions/ADR-002-positioning-decision-2026-05.md) and [v4.1 §5.5.1](../../nucleus_architecture_v4.1.md); the agent-runtime walkthrough is a hedged v0.5+ preview per [ADR-002 §4.2](../decisions/ADR-002-positioning-decision-2026-05.md).

This file is a navigation index. Each recipe states **time, difficulty, prerequisites, and current implementation status** in its header — every CLI line that depends on un-shipped code is marked `<!-- pre-v0.1 -->` or `NEEDS VERIFICATION` per [`AGENTS.md`](../../AGENTS.md) §11.12.

---

## v0.1 beachhead (Mo 0-4)

| File | Time | Difficulty | Status | Size |
|---|---|---|---|---|
| [postgres_to_iceberg.md](./postgres_to_iceberg.md) | ~25 min | Junior DE | Pre-v0.1 (PoC #1 + #3 + #4 gate) | ~8 KB |
| [csv_to_iceberg.md](./csv_to_iceberg.md) | ~15 min | Junior DE | Pre-v0.1 (no Docker variant) | ~6 KB |

The Postgres recipe is the canonical PoC #5 external-tester walkthrough — the one that *defines* whether v0.1 ships per [`nucleus_poc_plan.md`](../../nucleus_poc_plan.md) §5. The CSV recipe is its no-Docker cousin for "I just have a file" first-contact.

## v0.5+ preview (north-star, not runnable)

| File | Time (when shipped) | Difficulty | Status | Size |
|---|---|---|---|---|
| [slack_bot_on_data.md](./slack_bot_on_data.md) | ~30 min | Senior | v0.5+ preview, gated on Mo 24 founder decision per [ADR-002 §8.3](../decisions/ADR-002-positioning-decision-2026-05.md) | ~8 KB |

Demonstrates `ctx.agent` + `nucleus-mcp-server` (~500 LOC, v0.5 per [v4.1 §18.4](../../nucleus_architecture_v4.1.md)). Read for direction, not to run.

---

## Conventions

- **Beachhead first.** Recipes that don't serve the 30-minute Postgres → Iceberg metric are deferred or marked preview.
- **Status is honest.** `<!-- pre-v0.1 -->` and `NEEDS VERIFICATION` markers stay in until the underlying code ships; never silently delete them.
- **Patterns vs. recipes.** The *why* lives in [`../patterns/`](../patterns/); the *what to type* lives here. A recipe never re-explains a pattern — it links.
- **Recipes break first.** When a wrapped pin moves in [`../compatibility.md`](../compatibility.md), recipes are the first artifact re-run — they are the user contract.
- **No invented invocations.** Every `nucleus <verb>` line must trace to [`nucleus_cli_spec.md`](../../nucleus_cli_spec.md); every `ctx.<method>` to [`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md).

---

[← `nucleus_architecture_v4.1.md` §1.5 (beachhead)](../../nucleus_architecture_v4.1.md) · [ADR-002 (connector scope)](../decisions/ADR-002-positioning-decision-2026-05.md) · [Sibling — patterns/](../patterns/README.md) · [Sibling — research/](../research/README.md) · [Sibling — onboarding/](../onboarding/README.md)

*Last updated 2026-05-13. Add new recipes only when they serve a documented v0.1 / v0.3 / v0.5+ scope line — invented use cases without spec backing are rejected.*
