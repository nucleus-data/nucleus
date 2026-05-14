# Security Docs

Threat models and security artifacts for the Nucleus stack. Per [`AGENTS.md`](../../AGENTS.md) Hard Constraint #6 ("No custom auth system — always delegate to OIDC"), **Nucleus never owns identity** — auth delegates to Authentik / Keycloak / Okta / Entra ID per [ADR-010](../decisions/ADR-010-oidc-delegation-policy-v03.md) (v0.3+). Per [`AGENTS.md`](../../AGENTS.md) §11.7, every code path that handles secrets routes through `ctx.secrets` + `pydantic.SecretStr`; raw `os.environ` reads are caught in review.

This file is a navigation index. The threat model is the single source of truth for the v0.1 attack surface — if a CVE-shaped concern doesn't appear there, it isn't in scope yet.

---

## Threat models

| File | Scope | Status | Size |
|---|---|---|---|
| [threat_model_v0.md](./threat_model_v0.md) | v0.1 Heartbeat — local CLI + dev MinIO/Postgres | Lean STRIDE; review triggers documented in §12 | ~16 KB |

`threat_model_v1.md` is **not yet written** — it lands when v0.5+ approaches (Cloud tier, Workbench multi-user, OIDC delegation in production). Do not author it pre-emptively; capture v0.5+ concerns as `§11 Action items` rows inside `threat_model_v0.md` until the v1 file is opened.

## Related security material (lives elsewhere)

- [`../patterns/secret_management.md`](../patterns/secret_management.md) — `ctx.secrets` API + `pydantic.SecretStr` discipline (cross-cutting pattern)
- [`../decisions/ADR-006-nucleus-error-code-numbering.md`](../decisions/ADR-006-nucleus-error-code-numbering.md) — Error codes never leak credential payloads in messages
- [`../decisions/ADR-007-dependency-license-tier-policy.md`](../decisions/ADR-007-dependency-license-tier-policy.md) — License tiering (security implications of YELLOW/RED deps)
- [`../decisions/ADR-010-oidc-delegation-policy-v03.md`](../decisions/ADR-010-oidc-delegation-policy-v03.md) — OIDC provider delegation matrix (v0.3+)
- [`../decisions/ADR-011-telemetry-and-observability-opt-in-policy.md`](../decisions/ADR-011-telemetry-and-observability-opt-in-policy.md) — Telemetry opt-in policy + cardinality budget (PII surface)

---

## Conventions

- **Honesty bias.** Where v0.1 has zero defense (single-user trust, no auth), the threat model says so. False reassurance is worse than a documented gap.
- **Lean v0.1.** Enterprise concerns (SOC2, multi-tenancy, audit logging) belong in `threat_model_v1.md` — do not pollute v0.
- **No secrets in commits.** Examples use `<PLACEHOLDER>`; real keys are blocked by pre-commit hooks per [`../conventions/engineering.md`](../conventions/engineering.md) §8.4.
- **Vocabulary** per [`AGENTS.md`](../../AGENTS.md) §7: *check* / *contract* — never *test* / *expectation* in an asset-security context.
- **Supersede, never amend.** A shipped threat model is immortal at its version — open `threat_model_vN+1.md` rather than rewriting history.

---

[← `AGENTS.md` Hard Constraint #6](../../AGENTS.md) · [`AGENTS.md` §11.7 (error translation discipline)](../../AGENTS.md) · [Sibling — decisions/](../decisions/README.md) · [Sibling — patterns/](../patterns/README.md) · [Sibling — conventions/](../conventions/README.md)

*Last updated 2026-05-13. Add new threat models only at version bumps (`threat_model_vN.md`); never amend a shipped threat model in place — supersede instead.*
