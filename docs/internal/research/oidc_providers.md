# Research: OIDC Providers — Authentik, Keycloak, Okta, Microsoft Entra ID

> **Component status in Nucleus**: Hard Constraint #6 — **always delegate to OIDC; never own identity** (AGENTS.md §3 + `docs/specs/nucleus_architecture_v4.1.md` §15.1 + Amendment 9 / D17). v0.1 has **no auth** (single-user laptop — `docs/security/threat_model_v0.md` §6); v0.3+ Lakekeeper / Polaris catalogs delegate to OIDC; v0.5+ Workbench Cloud delegates to OIDC; post-v1.0 CLI remote ops use OIDC device-code flow.
> **Self-hosted candidates**: **Authentik 2026.2** (Python / Django, **MIT**), **Keycloak 26.6.1** (JVM / Quarkus, **Apache-2.0**).
> **Hosted SaaS candidates**: **Okta** (incl. Auth0 / Customer Identity), **Microsoft Entra ID** (formerly Azure AD).
> **Spec**: OpenID Connect Core 1.0 — https://openid.net/specs/openid-connect-core-1_0.html. All four are OpenID Certified (https://openid.net/certification/).
> **Research date**: 2026-05-13. **Not pinned** anywhere in `pyproject.toml` today — providers are external services. Provisional client-side pin: `PyJWT==2.8.x` (v0.3 ADR decides).

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before any v0.3+ PR that touches auth. **One doc covers four providers deliberately**: OIDC is a standardized spec; Nucleus's integration surface is uniform; only deployment + UX differ. The canonical **wrap-not-build** case for the identity layer (Pillar #2): we will never write a custom auth system, never store a password, never run a session table.

---

## §1. At a glance

| Provider | License | Latest stable (2026-05-13) | Hosting | JVM-free? | Role in Nucleus |
|---|---|---|---|---|---|
| **Authentik** | MIT (core) + source-available Enterprise | **2026.2** (CalVer) | Self-hosted (Docker / k8s) | **YES** — Python (Django + Go reverse-proxy) | **v0.3 self-hosted default** |
| **Keycloak** | **Apache-2.0** | **26.6.1** (April 2026) | Self-hosted (Docker / k8s / bare) | **NO** — Java 21 + Quarkus | v0.3 self-hosted alternate |
| **Okta** (incl. Auth0) | Commercial SaaS | n/a (SaaS) | Hosted by Okta | n/a | v1.0+ enterprise customer choice |
| **Microsoft Entra ID** (ex-Azure AD) | Commercial SaaS | n/a (SaaS) | Hosted by Microsoft | n/a | v1.0+ enterprise customer choice |

**What every provider is**: an OpenID Provider (OP) that authenticates a user, issues a signed **ID Token** (JWT) attesting to identity, plus an **Access Token** for downstream APIs. All four expose the same wire-level surface: `/authorize`, `/token`, `/userinfo`, `/.well-known/openid-configuration`, `jwks_uri`, `end_session_endpoint`. **The Relying Party (Nucleus) never sees a password.**

---

## §2. What OIDC is, in Nucleus terms

**OpenID Connect = identity layer on top of OAuth 2.0.** OAuth 2.0 (RFC 6749) defines *authorization* — a scoped access token. OIDC adds *authentication* — the **ID Token** says "the user is Alice, signed by provider P." They are **not interchangeable** (per Okta `/docs/concepts/oauth-openid/`: "OIDC extends OAuth 2.0 with user authentication and SSO"). Nucleus does not store passwords (Hard Constraint #6), runs no session table, issues no JWTs — we **consume** JWTs minted by one of the four providers. OIDC owns Trust Boundary #1 in `docs/security/threat_model_v0.md` §4 — currently the OS user account (v0.1), eventually the provider's `sub` claim (v0.3+).

| OIDC term | Nucleus term | Notes |
|---|---|---|
| OpenID Provider (OP) | **identity provider** | configured in `nucleus_config.toml [auth]` |
| Relying Party (RP) | **Nucleus + downstream catalog** | Lakekeeper / Polaris / Workbench |
| `sub` claim | **stable user ID** | persisted by catalog, NOT by Nucleus. **Entra ID uses `oid`** — see §6.4 |
| `aud` claim | **audience** | catalog validates; ≠ `client_id` (common AI confusion — §9) |
| `groups` / `roles` claim | **role-claim → RBAC scope** | mapped at catalog layer, not in Nucleus |
| `access_token` | **bearer token** | passed through pyiceberg `RestCatalog` |
| `refresh_token` | (stored in `ctx.secrets` v0.3+) | per §5.4 |
| `/.well-known/openid-configuration` | **discovery URL** | only fact Nucleus stores per provider |

**Key architectural insight**: every OIDC provider exposes the same discovery URL + the same `/token` / `/userinfo` semantics, so **switching providers is a configuration change, never a code change** — the Constraint #9 "Composability by Constitution" payoff in its purest form.

---

## §3. Spec compliance + official documentation URLs

Every fact below cites this set. Verified via `WebFetch` 2026-05-13.

**The spec**: OpenID Connect Core 1.0 (Nov 8 2014, last errata 2023) — https://openid.net/specs/openid-connect-core-1_0.html. Read §3 + §5 + §16 minimum before any v0.3+ ADR. Companions: **Discovery 1.0** (https://openid.net/specs/openid-connect-discovery-1_0.html) • **RP-Initiated Logout** (https://openid.net/specs/openid-connect-rpinitiated-1_0.html) • **OAuth 2.0 RFC 6749** • **PKCE RFC 7636** • **Device Grant RFC 8628** • **JWT/JWS/JWK** (RFC 7519/7515/7517).

| Provider | Landing | OIDC config | Releases |
|---|---|---|---|
| Authentik | https://goauthentik.io/docs/ | https://docs.goauthentik.io/docs/add-secure-apps/providers/oauth2/ | https://docs.goauthentik.io/docs/releases (CalVer; `2026.2`) |
| Keycloak | https://www.keycloak.org/documentation | https://www.keycloak.org/docs/latest/server_admin/ | https://github.com/keycloak/keycloak/releases (`26.6.1`) |
| Okta | https://developer.okta.com/docs/ | https://developer.okta.com/docs/concepts/oauth-openid/ | n/a (SaaS) |
| Entra ID | https://learn.microsoft.com/en-us/entra/identity-platform/ | https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc | n/a (SaaS) |

**Naming hygiene**: Microsoft renamed Azure AD → Microsoft Entra ID in 2023. Nucleus copy says **Entra ID**; "Azure AD" is tolerable in error messages for retrocompat. URLs (`login.microsoftonline.com`) did not rename.

---

## §4. Nucleus's OIDC integration surface

Minimum capabilities every provider must offer for Nucleus's wrapper to delegate without forks. **All four pass.**

**Required (v0.3+)**: Authorization Code Flow with **PKCE** (RFC 7636) • `/.well-known/openid-configuration` discovery • **JWKS** (`jwks_uri`) with RS256/ES256 • `/userinfo` • **Refresh tokens** (`offline_access` scope) • `end_session_endpoint` • Standard claims `sub`/`iss`/`aud`/`exp`/`iat`/`nonce`.

**Optional (use if available; degrade gracefully)**: Group/role claims (Authentik/Keycloak `groups`; Okta `roles`; Entra `groups` via Microsoft Graph) — mapped to RBAC at the catalog layer, not Nucleus (`docs/internal/research/lakekeeper.md` §5.2; `docs/internal/research/polaris.md` §5.4) • Federated identity (corporate AD/LDAP → OIDC; all four) • MFA / step-up auth (`acr` claim inherited) • **Device Authorization Grant** (RFC 8628) for `nucleus deploy` post-v1.0 • Back-channel logout (Authentik + Keycloak; Entra has front-channel only).

**Deliberately NOT consumed**: Dynamic Client Registration (v0.5+ Cloud only) • SAML 2.0 (customers route through their IdP's OIDC bridge; we will **not** wrap two protocols) • Token Introspection (RFC 7662 — Lakekeeper / Polaris are JWT-only; opaque tokens unsupported) • Implicit Flow (deprecated by OAuth 2.0 Security BCP) • `client_secret_basic` over plain HTTP.

---

## §5. Integration points with Nucleus

### §5.1 Lakekeeper / Polaris catalog auth (v0.3+)

Both v0.3 co-default catalogs consume OIDC at the **catalog**, not at Nucleus. Nucleus's job: (a) configure the catalog with discovery URL + audience + subject-claim, (b) carry the user's bearer token across `pyiceberg.RestCatalog` calls — pyiceberg already handles this via `credential=...` + `oauth2-server-uri=...`.

**Lakekeeper env-var recipe** (per `docs/internal/research/lakekeeper.md` §5.2):

```bash
LAKEKEEPER__OPENID_PROVIDER_URI=https://idp.example/realms/nucleus   # well-known root, NO /.well-known/openid-configuration suffix
LAKEKEEPER__OPENID_AUDIENCE=nucleus-catalog                           # MUST be set in production
LAKEKEEPER__OPENID_SUBJECT_CLAIM=sub                                  # 'oid' for Entra ID; 'sub' elsewhere
# LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS=...                            # Entra ID v1-vs-v2 escape hatch only
```

**Polaris Quarkus OIDC recipe** (per `docs/internal/research/polaris.md` §5.2):

```bash
polaris.authentication.<realm>.type=external                          # production default — NEVER 'internal' per Hard Constraint #6
quarkus.oidc.auth-server-url=https://idp.example/realms/nucleus
quarkus.oidc.client-id=nucleus
polaris.oidc.principal-mapper.id-claim-path=sub                       # 'oid' for Entra ID
polaris.oidc.principal-roles-mapper.filter=...                        # claim → 'PRINCIPAL_ROLE:<name>' translation
```

v0.3 ADR opens with **one** OIDC config block in `nucleus_config.toml`; Nucleus renders provider-specific env vars for the chosen catalog. Block is identical regardless of catalog, with one exception: Polaris's `internal` token mode is disabled in Nucleus templates per Hard Constraint #6.

### §5.2 Workbench auth (v0.5+ multi-user only)

v0.2 Workbench is single-user, local — **no OIDC**. v0.5+ Workbench Cloud is multi-tenant — **OIDC mandatory**. Standard PKCE Authorization Code: browser → provider → redirect URI → Workbench session cookie keyed off `sub`. No password stored. Session cookie lifetime = provider's `id_token` (typically 1h), refreshes back-channel. **Triggers `docs/security/threat_model_v0.md` §6 + §7 rewrite per §12 review cadence.**

### §5.3 CLI auth (v0.3+ remote ops; v1.0+ for `nucleus deploy`)

v0.1 / v0.3 CLI is local-only: no auth, OS-user-account boundary. Post-v1.0 `nucleus deploy` uses **OAuth 2.0 Device Authorization Grant** (RFC 8628) — supported by all four providers (Authentik `oauth2/device_code/`; Keycloak `server_admin/#con-oauth2-device-authorization-grant`; Okta `/docs/guides/device-authorization-grant/`; Entra `/v2-oauth2-device-code`):

```text
$ nucleus deploy --catalog production
nucleus: To sign in, visit https://idp.example/device and enter code WXYZ-9876.
✓ Signed in as alice@example.com.
```

### §5.4 `ctx.secrets` + token refresh (v0.3+)

Refresh token stashed in `ctx.secrets` (v4.1 §15.3) — OS keyring locally, AWS Secrets Manager / Azure Key Vault in cloud. Access-token refresh **before** the catalog request — check `exp - now > 60s`, refresh if not; retry once on 401. **Never log either token** (`docs/security/threat_model_v0.md` §5.1 + `engineering.md §5.3`).

**JWT library candidates**: **PyJWT** (https://pyjwt.readthedocs.io/, MIT — fewer transitive deps, better JWKS handling) vs **python-jose** (https://python-jose.readthedocs.io/, MIT — fuller JWE/JWS we won't need). **Provisional pin `PyJWT==2.8.x`** — decision deferred to v0.3 ADR; **NEEDS VERIFICATION** of current PyPI version at pin time.

---

## §6. Per-provider deep notes

### §6.1 Authentik — recommended v0.3 self-hosted default

**Why default**: Python-native (aligns with the *spirit* of Hard Constraint #1 — Nucleus core path stays no-JVM); **MIT license** (https://github.com/goauthentik/authentik/blob/main/LICENSE verified 2026-05-13: "Content outside of [enterprise/]... is available under the MIT license"); Docker Compose minimums: 2 CPU cores + 2 GB RAM.

**Versioning**: **CalVer** (`YYYY.M[.N]`). Latest stable per https://docs.goauthentik.io/docs/releases: **2026.2** (`2026.2.2` cherry-pick on GitHub Releases 2026-05-11). Major ~every 2 months. Notes: `authentik/enterprise/` is source-available (separate license); `website/` is CC-BY-SA-4.0; built JS is MIT Expat. OIDC provider = **core, MIT**.

**Setup** (per `docs.goauthentik.io/install-config/install/docker-compose`): `wget https://docs.goauthentik.io/compose.yml` → generate `PG_PASS` + `AUTHENTIK_SECRET_KEY` → `docker compose up -d` → UI at http://localhost:9000. Backing stack: PostgreSQL + Redis + worker. Default `worker` mounts `/var/run/docker.sock` for Outpost management (security-sensitive — Authentik's own docs flag); Nucleus templates should remove the mount or proxy it.

**OIDC endpoints** (per `add-secure-apps/providers/oauth2/`): `/application/o/{authorize,token,userinfo}/` + `/application/o/<app-slug>/{jwks,end-session,.well-known/openid-configuration}`. **Per-application discovery URL** — deliberate hardening over Keycloak's per-realm model.

**Real gotchas (in docs)**:

- **2024.2 changed refresh-token behavior**: apps MUST request `offline_access` scope to get a refresh token (`add-secure-apps/providers/oauth2/`). Nucleus catalog config MUST include it.
- **2025.10 changed `email_verified` default**: was always `True`, now `False` to avoid lying to RPs. Property-mapping override available.
- **Reserved app slugs**: never name an app `authorize`/`token`/`device`/`userinfo`/`introspect`/`revoke` — collides with global endpoints.
- **WebSockets required**: HTTP/1.0 reverse proxies don't work (Outpost communication).

### §6.2 Keycloak — alternative self-hosted, broadest ecosystem

**Why alternative, not default**: JVM (Java 21 + Quarkus). Hard Constraint #1 permits Keycloak as an *external service* — same exception as Polaris (`docs/internal/research/polaris.md` headline). But on a 16 GB laptop, Keycloak + Polaris stacks JVM heap. **Default Authentik for v0.3 self-hosted; offer Keycloak for shops already running it or wanting broadest ecosystem.**

**Versioning**: SemVer-ish. Latest stable: **26.6.1** (per `keycloak.org/documentation` landing 2026-05-13; April 2026 release notes cite 26.6.0 + CVE-2026-4366 SSRF + CVE-2026-4633 user-enumeration fixes). License: **Apache-2.0**.

**Setup** (per `keycloak.org/guides#getting-started`):

```bash
docker run -p 8080:8080 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:26.6.1 start-dev
```

`start-dev` = dev only; production uses `start` with Postgres + TLS (`keycloak.org/server/configuration`).

**OIDC endpoints** (per `server_admin/#_oidc-clients`): `/realms/<realm>/protocol/openid-connect/{auth,token,userinfo,certs,logout}` + `/realms/<realm>/.well-known/openid-configuration`. **Realms** are the multi-tenant primitive — one realm per Nucleus project.

**Real gotchas (in docs + release notes)**:

- **Default JVM heap ~512 MB**; production tuning at `keycloak.org/server/configuration-production`.
- **Major breaking changes ship in minor versions** (26.x dropped Wildfly for Quarkus). Per Constraint #11 every minor bump = ADR + smoke test.
- **CVE cadence**: actively patched. `pip-audit` does NOT catch Java-side CVEs — subscribe to `keycloak.org/security`.
- **`step-up-authentication-saml`** in preview as of 26.6.0 — don't depend on it.
- **Front- + back-channel logout both supported** — prefer back-channel for reliability.

### §6.3 Okta (incl. Auth0 / Customer Identity) — enterprise SaaS default

**Why include**: industry default for mid-large North-American enterprises. Auth0 (acquired by Okta in 2021) is the developer-first SaaS variant. OpenID Certified per `developer.okta.com/docs/concepts/oauth-openid/`.

**Setup**: Okta org (free for ≤10 users via Okta Integrator Free Plan — https://developer.okta.com/signup/) → create OIDC app integration → record `Client ID`, `Client secret`, Issuer URL (= `https://<org>.okta.com/oauth2/default`) → paste into `nucleus_config.toml`.

**OIDC endpoints**: `https://<org>.okta.com/oauth2/default/v1/{authorize,token,userinfo,keys,logout}` + `.../.well-known/openid-configuration`. `default` is the org's default AS; custom servers require the API Access Management add-on.

**Pricing — NEEDS VERIFICATION** (Okta pricing churns quarterly; re-fetch https://www.okta.com/pricing/ before quoting):

- **Workforce Identity**: from **$6/user/month** (Starter, annual, $1,500 min) → **$17/user/month** (Essentials) → custom (Professional / Enterprise).
- **Customer Identity (CIAM)**: base **$3,000/month** (annual) + per-MAU.
- **Free**: Okta Integrator Free Plan — ≤10 active users, no expiration (deactivates after 180 idle days).

5-engineer Nucleus beachhead ~$30/month Workforce = plausible; 1000-user CIAM = $3K + per-MAU.

**Real gotchas (in docs)**:

- **Okta ≠ Auth0** despite the acquisition: two dashboards (`<org>.okta.com` vs `manage.auth0.com`), two endpoint patterns, two SDK families. Configs **NOT** transferable.
- **Authorization Server**: `default` auto-created; custom ones cost extra.
- **Token format**: opaque by default; switch to JWT in AS settings to match Lakekeeper / Polaris JWT-only requirement.
- **Identity Engine vs Classic Engine**: new orgs are Identity Engine; legacy may be Classic. Nucleus supports both via standard discovery URL.
- **Interaction Code flow** (Okta-specific, Identity Engine only): **do NOT use**. Authorization Code + PKCE is universal.

### §6.4 Microsoft Entra ID (ex-Azure AD) — corporate Microsoft option

**Why include**: default for Microsoft 365 / Azure shops. OIDC Core 1.0 + Discovery 1.0 compliant per `learn.microsoft.com/.../v2-protocols-oidc`.

**Setup** (per `quickstart-register-app`): register app in Entra admin center → pick platform (Web for Workbench, Mobile/Desktop for CLI) → set redirect URI → enable ID tokens under "Authentication > Implicit grant and hybrid flows" → record `Application (client) ID`, `Directory (tenant) ID` → create client secret OR use certificate auth.

**OIDC endpoints** (per fetched config 2026-05-13): `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/{authorize,token,logout}` • `https://graph.microsoft.com/oidc/userinfo` • `.../discovery/v2.0/keys` (JWKS) • `.../v2.0/.well-known/openid-configuration`. `{tenant}` = `common` | `organizations` | `consumers` | `<tenant-guid>`. **Always specify tenant GUID in production** — `common` allows cross-tenant token reuse if `aud` is loose.

**Real gotchas (in docs)**:

- **Claim names differ from spec**: Entra uses **`oid`** (Object ID — tenant-stable user ID) instead of `sub`. The `sub` claim IS present but pairwise-pseudonymous (`subject_types_supported: ["pairwise"]` in discovery). For catalog RBAC stability, **set `SUBJECT_CLAIM=oid`** (per `docs/internal/research/lakekeeper.md` §5.2).
- **v1.0 vs v2.0 endpoints**: two parallel API versions. **Always v2.0** (`/oauth2/v2.0/...`). Legacy apps may issue v1.0 tokens; if both, use `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS`.
- **`response_mode=form_post`** recommended for web flows — `fragment` mode is subject to a 2,048-char URL length limit which can truncate large tokens.
- **Multi-tenant apps require admin consent** before non-admin users can sign in to `common`/`organizations` audiences.
- **`nonce` is REQUIRED** for ID token requests (Entra enforces; spec only says RECOMMENDED).
- **ID tokens for app are OFF by default** — opt in via the app registration's Authentication blade. Forgetting = `unsupported_response` error.
- **3-app-registration pattern for service-to-service** (per `docs/internal/research/lakekeeper.md` §5.2). Not a Nucleus problem unless we run a Cloud control plane (v0.5+).

---

## §7. Decision matrix for the founder

The v0.3 `nucleus init` auth prompt should surface this in plain language.

| Scenario | Recommendation | Why |
|---|---|---|
| Solo founder, dev only (v0.1 / v0.2) | **None** | v0.1 is intentionally auth-less (`docs/security/threat_model_v0.md` §6). |
| Small team (5-20), self-hosted (v0.3) | **Authentik** | MIT, no-JVM, Docker-friendly, smallest footprint, matches Nucleus posture. |
| Small team, wants maximum maturity / breadth | **Keycloak** | Apache-2.0, broadest ecosystem, JVM caveat acceptable as external service. |
| Mid-market customer already on SSO | Customer's existing provider | If they have Okta → Okta. Entra → Entra. Never make them install a second IdP. |
| Microsoft-heavy organization | **Entra ID** | Already paid for via M365/Azure; admin already trained. |
| Open-source-first non-Microsoft enterprise | **Okta** or **Authentik** (cloud-managed) | Most OSS shops have one already. |
| Heavy regulatory (SOC2 / HIPAA / FedRAMP) | **Okta** or **Entra ID** | Pre-existing compliance attestations; self-hosting shifts compliance burden to customer. |

**Single decisive question for v0.3 self-hosted default**: *"On a 16 GB laptop, Authentik (~300 MB Python) or Keycloak (~1 GB JVM)?"* Memory wins — **Authentik default.** Parallels Lakekeeper-vs-Polaris memory decision (`docs/internal/research/polaris.md` §8).

---

## §8. Swap analysis (v4.1 §9.3)

**OIDC is a standard, not a product.** Switching providers is a config change, never a code change.

```bash
# Drill: swap from Authentik to Keycloak (or any pair)
nucleus auth set --provider keycloak \
  --discovery-url https://keycloak.example/realms/nucleus/.well-known/openid-configuration \
  --client-id nucleus-catalog --client-secret-env NUCLEUS_OIDC_CLIENT_SECRET \
  --audience nucleus-catalog --subject-claim sub          # 'oid' for Entra ID
nucleus restart catalog
nucleus query "SELECT count(*) FROM raw.orders"           # verify bearer-token read
```

Changes: 5 lines in `nucleus_config.toml [auth]`. Does NOT change: any Nucleus code, any Iceberg table, any catalog row, any user data, any role binding. **This is Constraint #9's payoff in its purest form.**

Swap-drill failure modes (catch in CI per Constraint #9 smoke test):

| Failure | Cause | Fix |
|---|---|---|
| 401 from catalog after switch | Old JWKS cached | Restart catalog; verify new `jwks_uri` |
| Group/role claim absent | New provider names claims differently | Adjust `principal-roles-mapper` (Polaris) / role-mapping (Lakekeeper) |
| `sub` differs for same user | Entra's `sub` is pairwise; use `oid` | Set `SUBJECT_CLAIM=oid` |
| Refresh token rejected | Authentik 2024.2+ requires `offline_access` scope | Add to requested scopes |

CI smoke-test target: nightly drill against an ephemeral Keycloak container — token issued, validated by Lakekeeper, table read succeeds. ~200 LOC harness; budget against `scripts/beachhead_e2e.py`-style infra.

---

## §9. Known gotchas + AI hallucination risks

### §9.1 Likely AI hallucinations (verify before merge — log to `docs/internal/research/ai_hallucinations.md`)

- ❌ **"OIDC and OAuth 2.0 are interchangeable."** Wrong. OAuth 2.0 = authorization; OIDC = authentication on top of OAuth 2.0. Bare OAuth 2.0 has no `id_token` and no `sub` (per Okta `/docs/concepts/oauth-openid/`).
- ❌ **Fabricating provider endpoints from memory** (e.g., `https://okta.com/v1/oidc`, `https://entra.microsoft.com/oauth/token`). Only trustworthy source: `GET <issuer>/.well-known/openid-configuration`. Always.
- ❌ **`from oidc import OIDCClient` / `import oidc`** — no canonical Python library. Use **PyJWT** (validation) + **httpx** (discovery / token endpoint) + **authlib** if higher-level needed.
- ❌ **Assuming `sub` is universally stable.** Wrong for Entra ID — `sub` is pairwise-pseudonymous; stable ID is `oid`. Lakekeeper docs call this out (`docs/internal/research/lakekeeper.md` §5.2).
- ❌ **Confusing Okta with Auth0.** Okta acquired Auth0 in 2021; two dashboards, two endpoint patterns, two SDK families. Configs NOT transferable. AI agents conflate constantly.
- ❌ **"Azure AD" as current naming.** Renamed to **Microsoft Entra ID** in 2023. URLs (`login.microsoftonline.com`) survived; docs + admin UI use Entra exclusively.
- ❌ **Assuming Google Workspace is viable for Nucleus catalog auth.** Lakekeeper docs: Google Identity Platform lacks standard OAuth 2.0 Client Credentials → service-account auth broken; only browser auth works. **Recommend against Google** until verified otherwise.
- ❌ **Fabricating RP-Initiated Logout patterns.** Spec is real; per-provider differs — Keycloak requires `id_token_hint`; Entra accepts `post_logout_redirect_uri`; Okta uses `/v1/logout`. Always read `end_session_endpoint` from discovery.
- ❌ **Inventing "OIDC RBAC."** OIDC has no RBAC primitive — it ships **claims**; RBAC happens **at the RP** (catalog). Lakekeeper / Polaris consume claims → roles; Nucleus never sees a role.
- ❌ **Confusing `aud` claim with `client_id`.** Different concepts. `client_id` identifies the RP to the OP; `aud` is whom the token is for. Lakekeeper / Polaris check `aud`; misconfigure → every request 401s.
- ❌ **Citing Implicit Flow as current best practice.** Deprecated by OAuth 2.0 Security BCP and explicitly by Authentik's docs. Authorization Code + PKCE is the only spec-compliant browser flow in 2026.
- ❌ **Mixing up the licenses**: **Authentik = MIT**, **Keycloak = Apache-2.0**. Both permissive OSI-approved; ADRs require the correct one.

### §9.2 Real cross-provider gotchas (from official docs)

- **Discovery URL is single source of truth.** Hardcoding endpoint paths = drift. Read from `<issuer>/.well-known/openid-configuration` at startup, cache ≤ 1h, retry on miss.
- **JWKS rotation happens silently.** Catalog MUST refetch JWKS on signature-validation failure before raising (see https://learn.microsoft.com/en-us/entra/identity-platform/signing-key-rollover).
- **Audience validation is non-optional in production.** Skipping `aud` = any token from the same provider works against Nucleus's catalog.
- **Clock skew tolerance**: spec ≤ 5 min; configure ~30 s leeway (`PyJWT.decode(leeway=30)`).
- **Token lifetimes vary**: Authentik default 6h; Okta 1h; Entra 60-90 min; **Keycloak default 5 min**. Refresh logic per §5.4 MUST tolerate the shortest.
- **PII in claims**: Entra emits `unique_name` / `preferred_username` containing UPN (often = email). Threat model §5.2 ("no PII in logs") → these claims MUST NOT be logged. Only `sub` / `oid`.
- **TLS required in production.** `http://` discovery URL = JWKS over cleartext = MITM-replayable signing keys.

---

## §10. Compatibility with Nucleus pins (2026-05-13)

OIDC providers are external services. Python deps interact via JWT libraries + HTTP client.

| Nucleus dep | Our pin | OIDC interaction | Conflict? |
|---|---|---|---|
| `pyiceberg` | `0.8.1` | `RestCatalog(credential=..., oauth2-server-uri=...)` — fetches & passes bearer token | No (provider-agnostic OAuth2 client-creds) |
| Python | `>=3.11,<3.13` | not a constraint | No |
| **PyJWT** (provisional v0.3 pin) | **not pinned yet** | JWT signature + claims validation in `ctx.auth` (~200 LOC, v0.3+) | n/a — pin `PyJWT==2.8.x` at v0.3 ADR time (verify current PyPI) |
| `httpx` | (already used) | Discovery doc + token endpoint + JWKS fetch | No |
| Lakekeeper / Polaris | external `0.12.2` / `1.4.1` | OIDC env vars; JWT-only | No (per their §5.2) |
| Self-hosted IdP (Authentik / Keycloak) | external | Adds 1-2 containers to v0.3 compose | No (document RAM cost in `nucleus init` prompt) |

**No Nucleus-side OIDC pin exists yet.** PyJWT opens with v0.3 auth ADR — one component per PR per Constraint #11.

---

## §11. Decision log

**Why all four providers, and why none is "the" Nucleus default:**

- **Authentik** = self-hosted recommended default for v0.3 (matches Nucleus posture: Python, MIT, small footprint, no JVM, Docker-friendly).
- **Keycloak** = self-hosted alternate for shops already running it / wanting broadest ecosystem. JVM caveat acceptable as external service (parallels Polaris's exception per `docs/internal/research/polaris.md`).
- **Okta** (incl. Auth0) = enterprise SaaS default for North-American mid-large customers. Pre-existing SOC2 / FedRAMP attestations matter more than open-source posture for procurement.
- **Microsoft Entra ID** = enterprise SaaS default for Microsoft-shop customers. Already paid for; admin already trained.

**Per Hard Constraint #6**: we never replace these; we **integrate with whichever the user has**. Nucleus's job = discovery URL + bearer-token plumbing; the provider does everything else.

**Why bundling four in one doc**: OIDC is a *standard*, not four products. Integration surface is uniform; per-provider differences confined to §6.1-§6.4. Four parallel docs invite drift on the 90% they share.

**Why deferring to v0.3+**: per `docs/security/threat_model_v0.md` §6, v0.1 has no auth (intentional, documented). Adding OIDC to v0.1 = +1 container + ~500 MB RAM + JWT lib + claim mapping = blocks the 30-min beachhead metric (v4.1 §1.5). **Defer.** When v0.3 catalogs (Lakekeeper / Polaris) land they bring OIDC; our work is the wrapper.

**Never**: build a custom auth system. Hard Constraint #6. Pillar #2 + Pillar #5 violation (every IdP graduation target hostile-ifies). No exceptions.

Integration ADR: `docs/decisions/ADR-NNN-oidc-v03-auth.md` — opens with v0.3 catalog work; bundle with or companion to Lakekeeper / Polaris ADR.

---

## §12. Next reads when v0.3 auth work starts

- [ ] **Authentik docker-compose template** for `nucleus_template_project/` — bundle with v0.3 catalog template; default ports + secret-key generation + Postgres + Redis sized for laptop fit (<500 MB RAM idle).
- [ ] **PKCE flow implementation in `ctx.auth`** (~200 LOC, v0.3+) — code verifier, S256 challenge, `/authorize` redirect, `/token` exchange. Reference RFC 7636.
- [ ] **JWT validation library pin** — PyJWT vs python-jose head-to-head. Provisional: **PyJWT**.
- [ ] **Token refresh + session management UX** — `ctx.secrets` integration; refresh-before-expiry; 401 retry-once.
- [ ] **Device Authorization Grant for CLI** (RFC 8628) — verify all four providers; design `nucleus deploy`; target v1.0+.
- [ ] **Claim → role mapping at catalog layer** — Lakekeeper's `groups` recipe vs Polaris's `principal-roles-mapper` regex. Reconcile in catalog ADR.
- [ ] **Entra ID `oid` vs `sub` test fixture** — multi-provider claim normalization in CI smoke test.
- [ ] **Threat model rewrite** — `docs/security/threat_model_v0.md` §6 + §7 graduate per §11 action item v0.3.
- [ ] **Okta pricing refresh** — re-verify https://www.okta.com/pricing/ before any external claim.
- [ ] **OpenFGA / OPA integration sketch** — fine-grained authz above OIDC (Lakekeeper OpenFGA; Polaris OPA-based External PDP). v0.5+ multi-tenant.
- [ ] **`ctx.secrets` refresh-token storage** — OS-keyring (Linux/macOS), Credential Manager (Windows); encrypted-SQLite fallback for headless CI.

---

## §13. Useful links

- **Spec**: https://openid.net/specs/openid-connect-core-1_0.html • Discovery: https://openid.net/specs/openid-connect-discovery-1_0.html • PKCE RFC 7636 • Device Grant RFC 8628 • RP-Initiated Logout: https://openid.net/specs/openid-connect-rpinitiated-1_0.html • Certification: https://openid.net/certification/
- **Authentik** (MIT): https://goauthentik.io/docs/ • https://docs.goauthentik.io/docs/install-config/install/docker-compose • https://docs.goauthentik.io/docs/add-secure-apps/providers/oauth2/ • https://docs.goauthentik.io/docs/releases • https://github.com/goauthentik/authentik
- **Keycloak** (Apache-2.0): https://www.keycloak.org/documentation • https://www.keycloak.org/docs/latest/server_admin/ • https://github.com/keycloak/keycloak/releases • https://www.keycloak.org/security
- **Okta**: https://developer.okta.com/docs/ • https://developer.okta.com/docs/concepts/oauth-openid/ • https://www.okta.com/pricing/ • https://developer.okta.com/signup/ (free integrator)
- **Microsoft Entra ID**: https://learn.microsoft.com/en-us/entra/identity-platform/ • https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc • https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app • https://learn.microsoft.com/en-us/entra/identity-platform/signing-key-rollover
- **Companion Nucleus docs**: `docs/internal/research/lakekeeper.md` §5.2 • `docs/internal/research/polaris.md` §5.2 • `docs/security/threat_model_v0.md` §6 • `docs/decisions/ADR-002-positioning-decision-2026-05.md` §8 • `docs/specs/nucleus_architecture_v4.1.md` §15.

---

*Last verified: 2026-05-13 against Authentik 2026.2 + Keycloak 26.6.1 + OIDC Core 1.0 + Okta + Entra ID v2.0. Re-verify when opening the v0.3 auth ADR; before pinning PyJWT; after any Lakekeeper or Polaris OIDC behavior change; after every Okta pricing refresh (quarterly); after any Microsoft naming rebrand. Log any AI-fabricated OIDC APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
