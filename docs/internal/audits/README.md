# Audits

Drift-detection and governance-audit reports. Per [`AGENTS.md`](../../../AGENTS.md) §11.11, a **Drift Detection Pass** runs every 4 weeks — flags wrap-not-build violations, scope creep beyond current version, composability violations, error-translation gaps, vocabulary drift, LOC budget overruns, hallucinated API usage, and unpinned dependency versions. Each pass produces a dated audit file here.

This file is a navigation index. Audits are append-only artifacts: they record reality at a point in time and never re-write history. Auto-fix logs at the bottom of each audit document the patches that landed; un-fixed findings flow forward to the next pass as carry-over rows.

---

## Audit log

| File | Date | Scope | Verdict | Size |
|---|---|---|---|---|
| [positioning_drift_2026-05-12.md](./positioning_drift_2026-05-12.md) | 2026-05-12 | v4.1.3 patches sweep — `"AI-native"`, `"agent data substrate"`, `"modern composable data engineering platform"`, etc. | 2 DRIFT findings (1 patch-introduced, 1 pre-existing); 22 LEGITIMATE matches | ~4 KB |

---

## Conventions

- **Filename = `<topic>_<YYYY-MM-DD>.md`.** Sortable, searchable, immortal — same way ADRs are numbered (per [`../../decisions/README.md`](../../decisions/README.md) "Numbers are immortal").
- **Method line is mandatory.** Every audit declares the `rg` query, script, or manual procedure used so the next pass can reproduce.
- **DRIFT vs. LEGITIMATE.** Group findings by classification; never delete a LEGITIMATE row to "tidy up" — the next reviewer needs the trail.
- **Auto-fix log at the bottom.** When findings are patched, append to an `Auto-fix log` section — never silently mutate the findings table.
- **Founder accepts.** AI agents may draft audits; only the founder closes a finding as fixed.

---

## Cadence

- **Monthly** — Drift Detection Pass per [`AGENTS.md`](../../../AGENTS.md) §11.11 (sweeps the last 4 weeks of commits across all listed concerns).
- **Quarterly** — Composability swap drill per [`../../architecture/sequence_swap_drill.md`](../../architecture/sequence_swap_drill.md) + v4.1 §9.3. Drill results land here as `swap_drill_<component>_<YYYY-MM-DD>.md`.
- **On stop-condition** — Per [`AGENTS.md`](../../../AGENTS.md) §9, any of the nine stop conditions triggers an immediate audit, scope-tagged in the filename.
- **On positioning amendment** — Whenever an ADR amends `docs/specs/nucleus_architecture_v4.1.md` §1, run a positioning-drift sweep (template: `positioning_drift_2026-05-12.md`).

---

[← `AGENTS.md` §11.11](../../../AGENTS.md) · [`AGENTS.md` §9 (stop conditions)](../../../AGENTS.md) · [Sibling — decisions/](../../decisions/README.md) · [Sibling — architecture/](../../architecture/README.md) · [Sibling — conventions/](../../conventions/README.md)

*Last updated 2026-05-13. Add new audits by appending a row to the log; never re-order — chronological order is the contract.*
