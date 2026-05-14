# Pattern: Secret Management

> **Cross-cutting** — every connector, catalog, external service. Per [AGENTS.md](../../AGENTS.md) §3 Hard Constraint #6, Nucleus **never** owns an identity store — we delegate to OIDC from v0.3+ ([`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) §15.1). See also [`threat_model_v0.md`](../security/threat_model_v0.md) §3, §5.1, §6, §11; [`engineering.md`](../conventions/engineering.md) §5.3, §8.3, §8.4; [`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md) §8.3. Last reviewed 2026-05-12.

> **Zero real credentials in this file.** Every example uses `<PLACEHOLDER>`. Do **not** paste real keys into edits or PRs.

---

## §1. What this pattern is

Unified discipline for every secret Nucleus touches: source-DB DSNs, S3 / MinIO keys, OIDC tokens (v0.3+), LLM API keys (v0.5+), catalog credentials vended at runtime. Precedence: CLI flag → `.env.local` → `.env` → defaults (per [`engineering.md`](../conventions/engineering.md) §8.3). Every secret is wrapped in `pydantic.SecretStr` on read — `__repr__`, `__str__`, JSON, pickle redacted (per [`engineering.md`](../conventions/engineering.md) §8.4). Identity is OIDC-delegated; we never own a user store.

---

## §2. When to apply

Every connector, catalog adapter, external service call (HTTP / S3 / LLM / telemetry), and anywhere a credential would otherwise go in cleartext (config, CLI flag, Dagster metadata, `ctx.log`, OpenLineage facet). The answer in every case is **no**; route through §3.

---

## §3. How (Nucleus wrap)

User code never reads `os.environ` — `ctx.secrets` is the API (per [`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md) §8.3). `ctx.copy_from` parses the DSN, wraps the password in `SecretStr`, masks every log line.

```python
import nucleus

@nucleus.asset
def stripe_charges(ctx):
    api_key = ctx.secrets["STRIPE_API_KEY"]
    return ctx.connector.stripe(resource="charges", api_key=api_key)

@nucleus.source(name="raw.orders")
def raw_orders(ctx):
    return ctx.copy_from(
        source="postgres://<USER>:<PG_PASSWORD_ENV>@<HOST>/<DB>?sslmode=require",
        table="public.orders",
    )
```

| Release | Surface |
|---|---|
| v0.1 | **Env vars + `.env` (gitignored)**. `.gitignore` covers `.env*`, `secrets.toml`, `*.pem`, `*.key`, `credentials.json` (per [`threat_model_v0.md`](../security/threat_model_v0.md) §5.1); `detect-private-key` pre-commit on. URL passwords masked to `<REDACTED>` in logs and `NucleusError.user_message`. |
| v0.3 | `nucleus auth login` negotiates OIDC; refresh token cached in OS keychain via `keyring`. Catalog requests exchange the token for **scoped short-TTL storage credentials**. |
| v0.5+ | Backend hooks: `ctx.secrets.get("NAME", backend="vault")` resolves via Vault / AWS KMS / provider secret manager. **Hooks designed; backends wrapped, never built** ([AGENTS.md](../../AGENTS.md) §3 #9). |

---

## §4. How (underlying library)

v0.1: stdlib + `python-dotenv`. v0.3+: `keyring`. v0.5+: user's backend SDK. Nucleus owns only the thin `ctx.secrets` shim.

```python
import os
from pydantic import SecretStr
# Docs: https://docs.pydantic.dev/latest/api/types/#pydantic.types.SecretStr
# Docs (python-dotenv): https://saurabh-kumar.com/python-dotenv/

api_key = SecretStr(os.environ["STRIPE_API_KEY"])
# api_key.get_secret_value() ONLY at point of use, never logged
```

URL masking (v0.1): AMA splits DSNs via `urllib.parse.urlsplit` ([docs](https://docs.python.org/3/library/urllib.parse.html)), replaces the password with `<REDACTED>`, and re-serializes. v0.3+ OIDC wraps an existing client (library deferred to v0.3 ADR). v0.5+ backends use a `typing.Protocol` hook (per [`engineering.md`](../conventions/engineering.md) §7.2); smoke tests gate the swap.

---

## §5. Anti-patterns

- **In `nucleus.toml`** — checked into git. Use `${ENV_VAR}` interpolation.
- **In CLI flags** — visible via `ps aux` / Task Manager and shell history. Use `--secret-from-env <NAME>`.
- **In Dagster `AssetMaterialization` metadata or OpenLineage events.** Both leave the trust boundary (Dagster persists to disk and is surfaced via `nucleus enable compat-dagster` per §6.6; OpenLineage facets propagate to lineage consumers). AMA strips credential-shaped values before emission.
- **In error messages / logs / full URLs.** `SecretStr` redacts `__repr__`/`__str__` only if you don't unwrap; `.get_secret_value()` interpolated into a message defeats it. Even masked, *user* + *host* + *path* reveal infra topology — log shapes, not values (per [`engineering.md`](../conventions/engineering.md) §5.3). `NucleusError.user_message` is validated against a deny-list (per `nucleus_architecture_v4.1.md` §6.4).
- **In `git log` / `git stash`.** A `.env` accidentally added is still in the reflog. Per [`threat_model_v0.md`](../security/threat_model_v0.md) §10, any push is a rotation event. `gitleaks` / `detect-secrets` pre-commit hook is P1 (§11).
- **Long-lived static creds for OIDC catalogs (v0.3+)** — use vending.

---

## §6. Trade-offs

- **`.env` vs OS keychain.** `.env` is portable but unencrypted on disk; keychain is encrypted but harder to share. v0.1 picks `.env` for the 30-min beachhead metric (per `nucleus_architecture_v4.1.md` §1.5); v0.3+ adds keychain as a **second** path.
- **Vending vs static keys.** Vending is short-TTL, namespace-scoped, but needs an IdP for cold-start. v0.1 static; v0.3+ vending with fallback.
- **LLM keys (v0.5+) user-side, never proxied** (per [`threat_model_v0.md`](../security/threat_model_v0.md) §8 #3): no single point of compromise; cost is per-user management.

---

## §7. Cross-refs

- [AGENTS.md](../../AGENTS.md) §3 #6 + §11.12; [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) §6.4, §6.6, §15.1.
- [`threat_model_v0.md`](../security/threat_model_v0.md) §3, §5.1, §6, §8, §10, §11; [`engineering.md`](../conventions/engineering.md) §5.3, §8.3, §8.4; [`nucleus_ctx_sdk_spec.md`](../../nucleus_ctx_sdk_spec.md) §8.3.
- Research (v0.3+): [`lakekeeper.md`](../research/lakekeeper.md); [`polaris.md`](../research/polaris.md); [`openlineage.md`](../research/openlineage.md); [`dlt.md`](../research/dlt.md).

---

## §8. NEEDS VERIFICATION

Gated by code execution or policy decision; log to [`ai_hallucinations.md`](../research/ai_hallucinations.md).

- [ ] `pydantic.SecretStr` redaction in f-strings — same as `repr(secret)`? Verify on our Pydantic 2.x pin.
- [ ] `python-dotenv` precedence: `.env.local` overrides `.env` per [`engineering.md`](../conventions/engineering.md) §8.3.
- [ ] `keyring` (v0.3+) on all three target OSes; Linux headless / CI may need a passphrase-prompted file backend.
- [ ] OIDC client library choice — deferred to v0.3 ADR. **Do not pick from this doc.**
- [ ] Catalog credential vending in `pyiceberg==0.8.1` REST catalog: trigger property + expiry error type (likely `AuthorizationExpiredError` per [`pyiceberg.md`](../research/pyiceberg.md) §6).
- [ ] v0.1 secrets-leak CI hook: `gitleaks` vs `detect-secrets` (per [`threat_model_v0.md`](../security/threat_model_v0.md) §11 P1).

*Normative. When code disagrees, the doc wins. **No real secrets ever appear in this file.***
