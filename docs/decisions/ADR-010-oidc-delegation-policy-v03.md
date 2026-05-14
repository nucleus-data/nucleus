# ADR-010: OIDC Delegation Policy (v0.3+)

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: oidc, auth, security, v0.3, delegation, constraint-6
> **Related**: ADR-002 §6 (yield-to-giants), ADR-004 (catalog OIDC integration), ADR-006 (`NE5xxx` band reserved for `NucleusAuthProviderUnavailable`), ADR-007 (Authentik MIT GREEN, Keycloak Apache-2.0 GREEN, Okta + Entra ID = commercial SaaS), AGENTS.md §3 Hard Constraint #6, `nucleus_architecture_v4.1.md` §15.1, `docs/research/oidc_providers.md` (Worker W, ~32 KB), `docs/security/threat_model_v0.md` §6 + §11.

## Context

AGENTS.md §3 Hard Constraint #6: "**No custom auth system — always delegate to OIDC**." The constraint is binding architecture; this ADR makes it *policy* before v0.3 catalog work or Workbench Cloud (v0.5+) starts wiring auth ad hoc. Worker W validates four OIDC providers against the OpenID Connect Core 1.0 + Discovery 1.0 surface Nucleus consumes (Worker W §1 + §3 + §4) and confirms the Constraint #9 payoff — *swapping providers is a `nucleus_config.toml` edit, never a code change* (Worker W §8). v0.1 has no auth at all (`docs/security/threat_model_v0.md` §6 — single-user laptop, OS-account boundary, deliberate); v0.3 lights up multi-user mode through ADR-004 (Lakekeeper + Polaris both consume OIDC at the catalog layer, never at Nucleus).

## Decision

> **Nucleus delegates ALL authentication to external OIDC providers. v0.1 ships with NO auth. v0.3+ supports four providers (Authentik self-hosted default, Keycloak self-hosted alternate, Okta SaaS, Entra ID SaaS) through one uniform `[auth]` config block. Nucleus uses `PyJWT` for token *validation only*. Nucleus NEVER stores credentials, NEVER issues tokens, NEVER manages sessions. No exceptions.**

### 1. Tier 0 — never built (Constraint #6 absolute)

Nucleus owns NEVER, in any version, in any tier (OSS / Cloud / Enterprise): user credential storage; token issuance (`jwt.encode(...)` forbidden in `src/nucleus/`); session management (provider's job, including Workbench Cloud per Worker W §5.2); MFA enforcement (Nucleus reads `acr` if present, never demands one); identity federation; password reset, account recovery, identity audit log.

### 2. Tier 1 — supported provider matrix (v0.3+)

| Provider | License (ADR-007) | Deploy | Cloud-safe? | Self-host | Idle | Role |
|---|---|---|---|---|---|---|
| **Authentik** 2026.2 | **MIT** GREEN (core) | Self-hosted | ✓ | ✓ (**v0.3 default**) | ~300 MB Python | Self-hosted default; Python aligns with Constraint #1 spirit (Worker W §6.1 + §7) |
| **Keycloak** 26.6.1 | Apache-2.0 GREEN | Self-hosted | ✓ | ✓ (alternate) | ~1 GB JVM heap | Alternate; JVM-in-own-container per ADR-002 §6 (parallels Polaris exemption per ADR-004) (Worker W §6.2) |
| **Okta** (incl. Auth0 brand) | Commercial SaaS | SaaS | ✓ | ✗ | n/a | Enterprise SaaS; Workforce ~$6/user/mo (NEEDS VERIFICATION #2) (Worker W §6.3) |
| **Entra ID** (ex-Azure AD) | Commercial SaaS | SaaS | ✓ | ✗ | n/a | Enterprise SaaS; M365/Azure tenants already paid + admins trained (Worker W §6.4) |

All four are OpenID Certified and interchangeable behind one `[auth]` block. **Authentik is documented default for self-hosted greenfield** (Worker W §7 + §11). The v0.3 `nucleus init` prompt surfaces Worker W §7's decision matrix in plain language.

### 3. Tier 2 — explicit rejections (do not add to v0.3)

- **Google Workspace OIDC** — lacks OAuth 2.0 Client Credentials grant → service-account auth into Lakekeeper / Polaris broken (Worker W §9.1).
- **Auth0 standalone** — acquired by Okta 2021 but separate dashboards / endpoints / SDKs; AI agents conflate constantly. v0.3 supports the Okta brand; revisit standalone v0.5+ on customer demand (Worker W §6.3 + §9.1).
- **Facebook / Twitter / LinkedIn social OIDC** — not enterprise; no v0.3 customer story.
- **SAML 2.0 directly** — out of scope. SAML→OIDC bridges (Authentik + Keycloak both expose) acceptable per provider config (Worker W §4).
- **Custom Nucleus identity store** — Constraint #6 absolute. No exceptions.

### 4. Integration discipline (every v0.3+ auth PR enforces)

1. **Discovery endpoint mandatory** — read `<issuer>/.well-known/openid-configuration` at startup, cache ≤ 1 h, never hardcode JWKS or token-endpoint URLs (Worker W §9.2).
2. **PKCE mandatory** for all public clients (Workbench browser, future CLI device-code). RFC 7636 S256. Implicit Flow rejected (Worker W §9.1).
3. **`offline_access` scope** required for refresh tokens — Authentik 2024.2+ silently fails without it (Worker W §6.1).
4. **Subject claim normalization** — `sub` for Authentik / Keycloak / Okta; **`oid` for Entra ID** (Entra's `sub` is pairwise-pseudonymous, rotates per app registration — Worker W §6.4 + §9.1). `nucleus init` defaults `subject_claim` correctly.
5. **Token validation only** — Nucleus uses **`PyJWT==2.8.x`** (NEEDS VERIFICATION #1) to validate signature + audience + issuer + expiration. Nucleus NEVER mints. CI: `scripts/check_no_custom_auth.py` AST-walks `src/nucleus/` and rejects `jwt.encode(`, `bcrypt.hashpw(`, `argon2.PasswordHasher`, `passlib.`, password-shaped `hashlib.sha256(`.
6. **Audience validation non-optional** — `aud` mismatch = 401. `aud` is **not** the same as `client_id` (Worker W §9.1 — common AI confusion). JWKS rotation: refresh every 24 h **or** on `kid` miss (single retry).
7. **Catalog config rendered, never hand-authored** — the single `[auth]` block templates into Lakekeeper env vars (`LAKEKEEPER__OPENID_*`) **or** Polaris Quarkus properties (`polaris.authentication.<realm>.type=external`) per Worker W §5.1 + ADR-004. Templates hard-code Polaris to `external`; CI lint rejects shipped templates setting `internal` / `mixed` (mirrors ADR-004 §Risks row 3).
8. **No PII in logs** — log only `sub` / `oid`; never `unique_name` / `preferred_username` / `email` (Worker W §9.2 + `threat_model_v0.md` §5.1).
9. **Per-provider gotchas to flag in code review** — Okta ≠ Auth0 (separate SDKs, Worker W §6.3); Keycloak default token lifetime 5 min and JVM-side CVEs need direct `keycloak.org/security` subscription (`pip-audit` blind, Worker W §6.2 + §9.2); Entra ID `nonce` REQUIRED + ID-tokens-for-app OFF by default (Worker W §6.4); Authentik reserved app slugs `authorize`/`token`/`device`/`userinfo` (Worker W §6.1).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **AI proposes custom auth** ("just a quick login form for the demo") | This ADR + AGENTS.md §3 #6 linked from `.cursor/rules/nucleus.mdc`; `scripts/check_no_custom_auth.py` fails CI on any forbidden invocation. No "demo exception" |
| **Token signing keys leak into Nucleus** | No `jwt.encode(...)` or asymmetric-key generation in `src/nucleus/auth/`; PyJWT import-allowlisted to `decode` / `get_unverified_header` only via future `tools/import-policy.toml` |
| **Provider downtime blocks runtime** | v0.1 stays auth-free → fully offline. v0.3+ runtime depends on provider availability when multi-user is active — **accepted**, surfaced in `nucleus init` |
| **Discovery endpoint unreachable at startup** | Fail fast with translated `NucleusAuthProviderUnavailable` (slot reserved in `NE5xxx` per ADR-006); v0.5+ extension PR claims the concrete code. Message includes provider + URL + remediation; never raw external classname (per ADR-006 + AGENTS.md §11.7) |
| **Authentik with Lakekeeper / Polaris untested** | Workers F + H both flag as "OIDC-compliant but not explicitly documented" (ADR-004 NEEDS VERIFICATION #3); Worker W §5 confirms OIDC discovery uniform but unproven. **Smoke test in v0.3 implementation PR** holds Authentik default for Lakekeeper specifically |

Provider lock-in is not a meaningful risk here: OIDC is a *standard*; the uniform `[auth]` block makes provider switching a 5-line `nucleus_config.toml` edit per Worker W §8. Quarterly swap drill (Constraint #9) exercises Authentik ↔ Keycloak in CI.

## Verification plan

1. **`scripts/check_no_custom_auth.py`** (~60 LOC, NEW) — AST-walks `src/nucleus/` for forbidden patterns: `jwt.encode(...)`, `bcrypt.hashpw(...)`, `argon2.PasswordHasher`, `passlib.hash.*`, password-shaped `hashlib.sha256(...)`. Fails CI on detection. Wired into `.github/workflows/ci.yml` alongside `dagster_leak_check.py`, `check_vocabulary.py`, `check_error_codes.py` (ADR-006), `check_openlineage_facets.py` (ADR-009).
2. **`tests/auth/test_oidc_validation.py`** — PyJWT roundtrip with mocked JWKS for each provider; covers `sub` vs `oid` normalization, `aud` mismatch rejection, expired-token rejection, JWKS rotation single-retry, `offline_access` scope assertion.
3. **`tests/auth/integration/test_authentik_lakekeeper.py`** (deferred to v0.3 implementation PR) — ephemeral Authentik + Lakekeeper containers; full token issue → catalog read; closes Worker W's "Authentik for Lakekeeper specifically" gap.
4. **`docs/recipes/authentik_quickstart.md`** (v0.3) — runnable `docker-compose.yml` with Authentik + Postgres + Redis + Lakekeeper + MinIO + Nucleus.

## v0.1 stance

**v0.1 has NO auth.** Single-user laptop. Authorization boundary = OS user account that owns `warehouse/`, `catalog.db`, `.dagster_home/`, `.env` (`threat_model_v0.md` §6). Deliberate per the 30-min beachhead metric (`nucleus_architecture_v4.1.md` §1.5) — adding +1 container + JWT plumbing breaks it. When v0.3 multi-user mode lights up via ADR-004, this ADR activates and the threat model graduates per `threat_model_v0.md` §11.

## Rollback

- **Authentik problematic at v0.3** (CVE cluster, Outpost reliability, Lakekeeper compat fails) → **ADR-010a** flips documented default to Keycloak. Both GREEN per ADR-007; swap is `nucleus_config.toml` + recipe-doc edit per Worker W §8.
- **PyJWT becomes a CVE liability or abandoned** → **ADR-010b** swaps to `python-jose` or `joserfc` (both also MIT, GREEN per ADR-007). One-component-per-PR per Constraint #11.
- **Custom auth is NEVER an option per Constraint #6.** Even ADR-010z cannot relax this — the constraint is architectural law.

## Docs URLs (cite at every call site per Constraint #10)

- Spec: <https://openid.net/specs/openid-connect-core-1_0.html> · Discovery: <https://openid.net/specs/openid-connect-discovery-1_0.html> · PKCE RFC 7636 · Device Grant RFC 8628
- Authentik: <https://goauthentik.io/docs/> · Keycloak: <https://www.keycloak.org/documentation> · <https://www.keycloak.org/security> (mandatory CVE subscription)
- Okta: <https://developer.okta.com/docs/concepts/oauth-openid/> · <https://www.okta.com/pricing/> (verify quarterly per NEEDS VERIFICATION #2) · Entra ID: <https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc>
- PyJWT: <https://pyjwt.readthedocs.io/> · Primary: `docs/research/oidc_providers.md` (Worker W)

## Trigger

Status flips **PROPOSED → ACCEPTED** when (1) founder reviews + signs off on the four-provider matrix and Authentik default; (2) `scripts/check_no_custom_auth.py` lands and is wired into `.github/workflows/ci.yml`; (3) the `nucleus_config.toml [auth]` block schema is sketched (one block, four providers, `subject_claim` exposed) — implementation deferred to v0.3 PR. Authentik + Lakekeeper smoke-test recipe deferred to v0.3 implementation, not blocking acceptance. **Not gated on PoC #1.** Sequentially gated only on ADR-004 reaching ACCEPTED; can ACCEPT immediately on founder review.

## Downstream consumers

| Consumer | When | Affected how |
|---|---|---|
| `nucleus enable lakekeeper` | v0.3 (ADR-004) | Renders `LAKEKEEPER__OPENID_*` env vars from the unified `[auth]` block per Worker W §5.1 |
| `nucleus enable polaris` | v0.3 (ADR-004) | Renders `polaris.authentication.<realm>.type=external` + Quarkus OIDC env vars; `internal` mode hard-disabled in shipped templates per Constraint #6 |
| Workbench (v0.5+ multi-user / Cloud) | Mo 20-28 | Browser PKCE flow; session cookie keyed off `sub`/`oid`; **triggers `threat_model_v0.md` §6 + §7 rewrite** per Worker W §5.2 |
| `ctx.secrets` refresh-token storage (v0.3+) | Mo 14-20 | OS keyring locally; AWS Secrets Manager / Azure Key Vault in cloud; never logged per Worker W §5.4 |
| `nucleus-mcp-server` (v0.5+, ADR-002 §4.2 P4) | Mo 20-28 | MCP protocol auth bridges via OIDC token forwarding; reuses `ctx.auth` |
| `nucleus deploy` device-code flow (v1.0+) | Mo 28+ | RFC 8628 — all four providers support per Worker W §5.3 |
| Cloud Copilot LLM provider auth (v0.5+) | Mo 20-28 | **Separate ADR** for AI provider auth (OpenAI / Anthropic / Mistral) — out of scope here |

## NEEDS VERIFICATION

1. **Pin `PyJWT==2.8.x` against current PyPI at v0.3 PR time.** Worker W §5.4 + §10 mark provisional. Verify (a) latest PyPI version supports Python ≥ 3.11, (b) no open Critical CVEs at pin time, (c) `decode(leeway=30)` API matches Worker W §9.2 usage. License confirmed MIT (ADR-007 GREEN). One-component-per-PR per Constraint #11.
2. **Okta Workforce pricing claim (~$6/user/month Starter, $1,500 annual minimum) provisional.** Re-verify against <https://www.okta.com/pricing/> before any external-facing copy quotes it (Worker W §6.3 + §12 — pricing churns quarterly). For ADR purposes the relative positioning (SaaS, paid, enterprise-default) holds regardless of exact dollars.

## Open questions for founder

1. **Authentik confirmed as v0.3 self-hosted default?** Worker W §7 + §11 strongly recommend (no-JVM-spirit per Constraint #1, MIT per ADR-007 GREEN, ~300 MB vs Keycloak ~1 GB on 16 GB beachhead laptop). Default position: yes, conditional on Authentik-with-Lakekeeper smoke test (ADR-004 NEEDS VERIFICATION #3) passing in v0.3 implementation PR.
2. **SaaS providers — Okta first or Entra ID first in v0.3 docs?** Default position: **both equally weighted** — let the customer choose; surface Worker W §7's decision matrix in `nucleus init`. No opinionated default for SaaS; the customer already has one.
3. **Should v0.3 ship `nucleus auth doctor`?** Validates discovery URL is reachable, JWKS fetches, scopes correct, `subject_claim` matches provider, `aud` matches catalog config. Default position: **yes** — ~30 LOC, fits ADR-005 stability tier Beta, payback enormous on the support-load axis (Worker W §9 lists ~10 ways this misconfigures silently).
4. **Pre-v0.3 ADR for AI provider auth (commercial LLM APIs)?** OpenAI / Anthropic / Mistral keys are user-side env vars, not OIDC tokens — entirely separate trust boundary. Default position: **defer to v0.5** when Cloud Copilot ships and forces the question.

---

*Consummates Worker W's research delivered 2026-05-13. Per AGENTS.md §11.13, no v0.3 OIDC implementation begins until status flips to ACCEPTED **and** ADR-004 (catalog migration) has landed. Constraint #6 is law; this ADR is its operating manual.*

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
