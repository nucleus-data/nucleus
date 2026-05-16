# Threat Model v1 — v0.1 dev loop + Cloud commercial path

> **Status**: First real threat model. Authored 2026-05-13 alongside ADR-006 / ADR-007 / ADR-008 / ADR-010 / ADR-011 acceptance.
> **Methodology**: STRIDE continued from `threat_model_v0.md` §1, layered onto the five trust boundaries in §2.
> **Owner**: solo founder. Re-review triggers in v0 §12 plus three more in [§11](#11-open-questions-for-founder).

v1 does NOT replace v0. v0 remains canonical for the v0.1 single-process deployment shape, asset list, and STRIDE walkthrough (v0 §2, §3, §5). v1 picks up where v0 deferred — Cloud (v0 §1), OIDC (v0 §6 + §11 row 12), AI surface (v0 §8), supply-chain depth (v0 §5.5) — and writes the policies the 2026-05 ADR wave locked.

## §1. Scope + posture

**Covers**: v0.1 surface as deltas only; v0.3+ multi-user catalogs + OIDC; v0.5+ Cloud control plane vs customer data plane; storage substrate (SeaweedFS default; MinIO archived alternate); telemetry + lineage emission; error-code-as-public-contract.

**Does NOT cover**: Workbench multi-user UI internals (v0.2+, separate doc per v0 §11 row 13); AI Copilot economic / abuse surface (v0.5+, separate ADR per ADR-011 §"Open questions" Q3); plugin marketplace (v1.5+, AGENTS.md §4 + §8); compliance certifications — v4.1 §15.5 explicitly says "we do **not** claim certifications until audited".

**Three hard rules** govern every decision below: (1) **never own identity** (AGENTS.md §3 Constraint #6 + v4.1 §15.1 + ADR-010 §1); (2) **privacy bedrock — opt-in for OSS, never default-on** (ADR-011 §1; Daft / Scarf precedent in `daft.md` §8 row 4); (3) **errors carry stable codes, never external classnames** (ADR-006 §Decision + AGENTS.md §11.7).

## §2. Trust boundaries

v0 §4 documents five boundaries inside the laptop. v1 expands the same numbering to span Cloud + OIDC + storage substrate.

| # | Boundary | Enforcement |
|---|---|---|
| 1 | OS user ↔ Nucleus process | Filesystem perms on `warehouse/`, `catalog.db`, `.dagster_home/`, `.env` (v0 §4 row 1) |
| 2 | Cloud control plane ↔ customer data plane (v0.5+) | Per-tenant storage prefix + IAM scope-down + customer-owned object store; control plane orchestrates, **never reads** asset rows (ADR-007 §"Standing pre-decisions" Cloud column + ADR-008 §"Future Cloud" row) |
| 3 | Nucleus ↔ OIDC provider (v0.3+) | `PyJWT.decode(...)` validation only; `jwt.encode(...)` forbidden in `src/nucleus/`; CI gate `scripts/check_no_custom_auth.py` (proposed) (ADR-010 §1 + §4 rule 5) |
| 4 | Nucleus ↔ catalog (v0.3+ Lakekeeper / Polaris) | Catalog is authoritative for snapshot atomicity (ADR-001); OIDC token-forwarding; Polaris hard-coded `external` mode (ADR-004 + ADR-010 §4 rule 7) |
| 5 | Nucleus ↔ storage substrate (SeaweedFS / MinIO / AWS S3) | S3 SigV4 access keys; endpoint pinned in `nucleus.toml`; **no Nucleus-bundled substrate in Cloud** (ADR-008 + ADR-007 §Tier 2 treatment) |

The supply-chain boundary (Nucleus ↔ wrapped libs, v0 §4 row 2 — the highest-risk v0.1 boundary) is unchanged; see v0 §5.5 + §5 below for layered defenses.

## §3. Asset confidentiality + integrity

| Tier | Posture |
|---|---|
| **Local (v0.1)** | Filesystem perms; Iceberg snapshot immutability + atomic-rename catalog commits per ADR-001 (Windows semantics in PoC #1 stress tests). Threat: disk encryption not default → OS-level guidance in `SETUP.md` (v0 §11 row 8 — P2 TODO) |
| **Cloud (v0.5+)** | OIDC + per-tenant storage prefix + encrypted-at-rest delegation to substrate (S3 SSE-S3 / R2 / GCS); catalog-owned commit atomicity (ADR-001). Threat: cross-tenant collision / substrate IAM misconfig → per-tenant prefix + IAM scope-down per ADR-008 §"Future Cloud" row; Cloud **never bundles** YELLOW / RED substrates (ADR-007 Tier 2 + 3) |
| **Lineage + telemetry** | See §6. **New v1 risk**: lineage exfiltration via `.nucleus/lineage/events.jsonl` leaks asset names + column shapes + storage URIs (structural metadata, not values). v0 §7 only planned `ops.audit` for v0.5+; ADR-009 makes lineage a v0.1 surface — filesystem perms apply now, OIDC-gated `HttpTransport` to Marquez at v0.5+ (ADR-009 §2) |

## §4. Authentication + authorization

### §4.1 Per-version stance

| Version | Mode |
|---|---|
| v0.1 | **No auth** — single OS user, deliberate (v0 §6; ADR-010 §"v0.1 stance") |
| v0.3+ | OIDC delegation: Authentik default; Keycloak alternate; Okta + Entra ID for SaaS (ADR-010 §2 + v4.1 §15.1) |
| v0.5+ Workbench Cloud | OIDC + browser PKCE (`oidc_providers.md` §5.2) |
| v0.5+ per-asset RBAC | Hierarchical Org → Domain → Project → Asset; OPA or Casbin internally — concrete impl **NEEDS VERIFICATION** beyond v0.3 catalog scope (v4.1 §15.2) |

### §4.2 Threats

| Threat | Mitigation |
|---|---|
| Token leakage in logs | Log only `sub` / `oid`; never `unique_name` / `preferred_username` / `email` (ADR-010 §4 rule 8). **NEEDS VERIFICATION**: `_internal/logging.py:11` sets the convention "log shapes, not values" but does NOT implement runtime regex-redaction; enforcement is code review only as of 2026-05-13 |
| Token replay in CI | Short-lived OIDC access tokens; refresh-token rotation back-channel; `ctx.secrets` stashes refresh tokens in OS keyring locally / Secrets Manager / Key Vault in cloud (`oidc_providers.md` §5.4) |
| Privilege escalation | Per-org-unit IdP role mapping via Lakekeeper `LAKEKEEPER__OPENID_*` env vars or Polaris Quarkus properties; CI lint forbids `internal` / `mixed` mode in shipped catalog templates (ADR-010 §4 rule 7 + ADR-004) |
| Custom auth slips in | `scripts/check_no_custom_auth.py` AST-walks `src/nucleus/` for `jwt.encode(`, `bcrypt.hashpw(`, `argon2.PasswordHasher`, `passlib.`, password-shaped `hashlib.sha256(` (**proposed; not yet landed** — ADR-010 §"Verification plan" row 1) |
| `aud` confused with `client_id` (top AI hallucination); Entra `sub` rotates per app registration | `tests/auth/test_oidc_validation.py` covers `aud` mismatch + JWKS rotation single-retry; use `oid` (not `sub`) for Entra; `nucleus init` defaults `subject_claim` per provider (ADR-010 §4 rules 4 + 6) |
| Provider downtime blocks v0.3+ runtime | Accepted residual risk; surfaced in `nucleus init`; multi-provider matrix lets enterprise carry their own (ADR-010 §"Risks" row 3) |

## §5. Supply chain

### §5.1 License-tier policy (ADR-007)

Cloud **cannot** carry RED deps (ADR-007 §Tier 3 row 3) and **cannot bundle / manage** YELLOW deps (ADR-007 §Tier 2 rows 2-4).

| Tier | Examples in pin matrix (ADR-012) | Cloud safe? |
|---|---|---|
| GREEN | DuckDB, Polars, pyiceberg, Dagster, sqlglot, OpenLineage, OpenTelemetry, SeaweedFS | yes |
| YELLOW | psycopg3 (LGPLv3+, dynamic-link exempt — **NEEDS VERIFICATION** per ADR-012 row 9); MinIO (AGPLv3, archived per ADR-008) | conditional, never bundled |
| RED | None pinned. Soda Core v4 (ELv2) blocked from any path; v3 is terminal per ADR-007 row "Soda Core v4+" | no |

**Storage substrate (ADR-008)**: SeaweedFS is v0.1 documentation default (Apache-2.0 GREEN); MinIO (AGPLv3 YELLOW, archived 2026-04-25) is preserved as a tagged alternate. Cloud uses customer-owned AWS S3 / R2 / GCS or self-hosted SeaweedFS per ADR-008 §"Downstream consumers" Future Cloud row.

### §5.2 Pin discipline (AGENTS.md §11.13 + ADR-012)

Exact pins on every runtime dep (`scripts/check_pinning.py`); one-component-per-PR (bulk refused per AGENTS.md §10 rule 12); `scripts/upgrade_smoke.py` on every dep change; major-version upgrades require ADR (e.g. ADR-003 for pyiceberg `0.8.1` → `0.11.x`).

### §5.3 Threats

| Threat | Mitigation |
|---|---|
| Typosquat (`polrs`, `psycog`) | Reviewer checks dep names against ADR-012 §"Runtime pin matrix"; future allowlist in `scripts/check_pinning.py` (v0 §5.5 + v0 §11 row 10) |
| Compromised upstream release | Exact pin protects until *we* upgrade; weekly `pip-audit` in `.github/workflows/upgrade-deps.yml`; promote `pip-audit` non-fatal → fatal-on-Critical-CVEs before v0.1 ship (v0 §11 row 7) |
| Silent license shift (Apache-2.0 → BUSL / ELv2) | `scripts/check_licenses.py` reads `pip show` per pinned dep, classifies GREEN / YELLOW / RED, fails CI on tier shift (ADR-007 §"Verification plan" + §"Upgrade detection trigger") |
| AGPLv3 §13 violation in Cloud (MinIO bundled by accident) | Cloud build pipeline carries explicit denylist; fails if MinIO etc. detected inside Cloud Docker image (ADR-007 §"Risks" row 3) |
| `setup.py` post-install script in malicious dep | `hatchling` (no scripts) + pin transitive resolutions where possible (v0 §5.5) |
| Compromised CI runner | Least-privilege workflow `permissions:` blocks (`ci.yml` defaults `contents: read`); accepted residual risk (v0 §9) |

**Known gap**: `.github/dependabot.yml` does not yet exist (v0 §11 row 6). P1 TODO.

## §6. Telemetry + observability

Per ADR-011 §1, **OSS telemetry is OFF by default through v0.5**; Cloud customers MAY be opted in via Cloud ToS. Daft / Scarf phone-home is the standing rejection (ADR-011 §"Context" + `daft.md` §8 row 4).

**Emitted only when `telemetry.opt_in=true`** (ADR-011 §2): 4 spans (`nucleus.cli.run`, `nucleus.asset.materialize`, `nucleus.ctx.sql`, `nucleus.ingest`) + 4 metrics (`nucleus.assets.materialized`, `nucleus.asset.materialization.duration`, `nucleus.errors.count` labelled by NE-code, `nucleus.escape_hatch.calls`).

**Privacy hard floor — NEVER emit** (ADR-011 §3): (1) raw SQL as attributes → emit `nucleus.sql.statement_hash` (`sha256(raw)[:16]`); (2) row counts as attributes → metric *values* only; (3) OS username / hostname / FS layout → resource attrs capped at `service.name`, `service.version`, `nucleus.project_id=<sha1>`, `nucleus_install_id=<UUIDv4>`; (4) absolute file paths → relativize to project root; (5) stack traces with local vars → use `NucleusError.user_message`, never `repr(exc.__cause__)`. CI lint enforces #1 + #4 (`scripts/check_telemetry_cardinality.py`, **proposed v0.5 work**); code review covers #2, #3, #5.

**Threats**:

| Threat | Mitigation |
|---|---|
| Cardinality explosion / PII in metric labels | ADR-011 §4 budget (≤ 50 span names, ≤ 100 metric names, ≤ 200 attr keys, ≤ 1000 values per key); `scripts/check_telemetry_cardinality.py` (proposed) |
| Telemetry endpoint compromise | OSS exports MUST go to user-controlled endpoints — NO Nucleus-Inc default OTLP collector for OSS (ADR-011 §6); HTTPS + cert pinning at v0.5+, out of scope for v0.1 |
| Lineage event leakage | OL `event_v2` schema (ADR-009 §1) carries no row values by construction; storage URI + asset name + schema only; `errorMessage` carries NE-code per ADR-006 + AGENTS.md §11.7, never raw external classnames |
| `OPENLINEAGE_DISABLED=true` activates `NoopTransport` silently | `nucleus doctor` (v0.2+) surfaces the env var (ADR-009 §"Risks" row 6) |
| Default `ConsoleTransport` swallows OL events into `structlog` INFO | AMA MUST pass explicit `transport=`; CI asserts every `OpenLineageClient(` constructor passes one (ADR-009 §"Forbidden") |

**Transparency** (ADR-011 §6 bullet 3): opted-in mode prints `Telemetry: ON (endpoint=http://...)` on `nucleus up`. Disable: remove `telemetry.opt_in`, `NUCLEUS_TELEMETRY=0`, or `nucleus disable otel` (v0.3+).

## §7. Operational threats

| Setting | Threat / mitigation |
|---|---|
| Local dev | Secrets in `nucleus.toml` instead of env vars → `engineering.md` §8.4 wraps secrets in `pydantic.SecretStr` / `msgspec` `Secret`; `docs/patterns/secret_management.md` planned (**NEEDS VERIFICATION** — not yet authored) |
| Local dev | `.env` committed to git → `.gitignore` covers `.env`, `.env.*`, `secrets.toml`, `*.pem`, `*.key`, `credentials.json` (v0 §5.1); `pre-commit-hooks/detect-private-key` enabled; **gitleaks** / **detect-secrets** still P1 TODO per v0 §11 row 5 |
| CI | Stale credentials → short-lived OIDC tokens; rotation handled by IdP, not Nucleus. Workflow `permissions:` defaults to `contents: read` (v0 §9) |
| Cloud (v0.5+) | Tenancy isolation breach (cross-tenant reads) → per-tenant storage prefix + IAM scope-down per ADR-008 §"Risk reframing" Cloud column; control plane **never reads** asset rows |
| Cloud (v0.5+) | AGPLv3 §13 source-release obligation triggered → ADR-007 §Tier 2 forbids bundling; ADR-008 §"Future Cloud" row pins customer-owned object store; build-pipeline denylist per ADR-007 §"Risks" row 3 |
| Cloud (v0.5+) | AI provider (OpenAI / Anthropic) phones home regardless of OTEL posture → separate ADR per ADR-011 §"Open questions" Q3, deferred to v0.5 Cloud Copilot ship; document as known third-party flow under Cloud ToS |

## §8. Errors as a security surface

Per ADR-006, `NucleusError` subclasses carry stable `error_code: ClassVar[str]` matching `^NE[1-5]\d{3}$` from first release. Codes are **permanent** — once `NE3001` ships in v0.1.0 it points to `NucleusInternalError` forever (ADR-006 §Decision row 1).

**Why this matters for security**: (1) stable identifier — a future CVE can cite "affects paths emitting `NE1003` (`NucleusCommitUnknownError`)" without leaking implementation detail; (2) AI Copilot (v0.3+) + MCP server (v0.5+) map codes → fix steps (ADR-006 §Context), misclassified code = wrong fix step = larger blast radius; (3) **path-redaction discipline** — `NucleusError.rendered()` (`src/nucleus/errors.py:106-146`) appends the original `__cause__` repr **only when `debug=True`**; with `debug=False` (CLI default) the cause — which may include external library or filesystem paths — is omitted. `user_message` / `fix_hint` / `docs_url` MUST be constructed path-clean by the translator at the boundary. **NEEDS VERIFICATION**: a runtime path-redaction filter is not implemented as of 2026-05-13; discipline is code-review-only.

| Threat | Mitigation |
|---|---|
| External classname in `user_message` | `scripts/dagster_leak_check.py` greps `src/nucleus/` for raw external classnames in `user_message=` literals; release blocker (AGENTS.md §11.7 + ADR-006 §"Verification plan" row 4); ADR-006 extends to `scripts/check_vocabulary.py` |
| External classname in OL `errorMessage` facet | Same script extended to grep emitted JSONL per ADR-009 §"Risks" row 5 |
| AI Copilot hallucinates `NE9999` in user output | Workbench (v0.2+) renders live valid-code set via runtime introspection; out-of-set flagged. CLI `nucleus errors list` (v0.2+) prints registry (ADR-006 §"Risks" row 4) |
| Code reused after deprecation (history-rewrite) | CI check diffs `git show HEAD~1:src/nucleus/errors.py`, asserts no removed-then-readded codes (ADR-006 §"Risks" row 3) |
| Path leak via `--verbose` cause repr | Documented opt-in trade-off (see §11.3) |

## §9. Known limitations (NEEDS VERIFICATION)

Real attack surfaces v1 does **not** yet defend against. Be honest.

1. **Container-escape vectors in SeaweedFS / MinIO**: not assessed. Standard Docker isolation applies; no focused audit. Defer to v0.5+ Cloud security review (ADR-008 §"Verification plan").
2. **Iceberg manifest tampering**: trust model assumes the **catalog is authoritative** for snapshot pointer atomicity (ADR-001). An attacker with direct S3-prefix write can mutate manifest files or `*.metadata.json`, defeating optimistic concurrency. v0.1 mitigation = filesystem perms / IAM scope-down on the prefix; no signed manifests. Track upstream.
3. **Sandbox model for `ctx.agent`** (v0.5+ per v4.1 §13.2 + ADR-005 + ADR-013): not yet defined. Frozen at v1.5 per ADR-005 §1 + ADR-006 §Decision row 5. **Out of scope** for v1.
4. **Four CI gates remain PROPOSED** (see §10): `scripts/check_no_custom_auth.py`, `scripts/check_openlineage_facets.py`, `scripts/check_telemetry_cardinality.py`, `scripts/check_no_telemetry_default.py`. Until they land in `.github/workflows/ci.yml`, the corresponding disciplines are code-review-only.
5. **`docs/patterns/secret_management.md`** referenced by §7 does not yet exist; guidance is scattered across `engineering.md` §8.4 and v0 §5.1.
6. **Runtime regex-redaction on log lines** is not implemented in `src/nucleus/_internal/logging.py`; the convention "log shapes, not values" (line 11) is code-review-only. A `structlog` processor masking `password=` / `secret=` / `token=` / `Bearer ` would tighten this — proposed v0.3+, not yet scoped.
7. **Multi-process catalog write coordination on filesystem catalog** is out-of-scope for v0.1 (v0 §9 row 6). Lakekeeper / Polaris (v0.3+ per ADR-004) close this gap.

## §10. Verification + CI gates

Status per `scripts/` listing 2026-05-13.

| Gate | Threat class | Status |
|---|---|---|
| `scripts/check_pinning.py` | Exact-pinning | LANDED |
| `scripts/check_licenses.py` | License-tier (ADR-007) | LANDED |
| `scripts/check_error_codes.py` | Error codes (ADR-006) | LANDED |
| `scripts/check_api_stability.py` | Public-API stability (ADR-005) | LANDED |
| `scripts/dagster_leak_check.py` | External classname leaks (AGENTS.md §11.7) | LANDED |
| `scripts/check_vocabulary.py` | Vocabulary drift (AGENTS.md §7) | LANDED |
| `scripts/check_layering.py` | Layering (no L0 / L1 imports skipping L2) | LANDED |
| `scripts/upgrade_smoke.py` | Upgrade safety (AGENTS.md §11.13) | LANDED |
| `scripts/loc_budget.py` | LOC budget (AGENTS.md §11.6) | LANDED |
| `scripts/beachhead_e2e.py` | Beachhead E2E (v4.1 §1.5) | LANDED |
| `scripts/check_no_custom_auth.py` | Custom-auth detection (ADR-010 §4 rule 5) | **PROPOSED** |
| `scripts/check_openlineage_facets.py` | OL facet completeness (ADR-009 §3) | **PROPOSED** |
| `scripts/check_telemetry_cardinality.py` | Telemetry cardinality (ADR-011 §4) | **PROPOSED — v0.5 work** |
| `scripts/check_no_telemetry_default.py` | Telemetry-default-off (ADR-011 §1) | **PROPOSED** |

The four PROPOSED gates are the bridge between this threat model and shipping code. Each must land before its ADR flips PROPOSED → ACCEPTED per the ADRs' `Trigger` sections.

## §11. Open questions for founder

1. **HTTPS-only S3 endpoint for Cloud?** ADR-008 §"Compose templates" pins local SeaweedFS as plain HTTP (`localhost:8333`). Should v0.3+ Cloud reject `http://` outside `localhost`? Default: require HTTPS for any non-`localhost` endpoint; opt out via `s3.allow_insecure=true` + `nucleus doctor` warning.
2. **Upstream-CVE detection + notification loop?** v0 §10 row 3 covers rollback; missing is who watches `pip-audit`, the advisory-triage SLA, and the user-notification channel. Default: GitHub `security` label + CHANGELOG + (post-v0.5) `security@nucleus.dev` list. Codify here or split into a runbook?
3. **Render `[NE3002]` prefix in CLI?** ADR-006 puts `error_code: ClassVar[str]` on every subclass. Pro: log-grep-friendly; advisories cite verbatim. Con: clutters first impression. Default: **yes** — ADR-006 §"Risks" row 4 already assumes user-visible codes.
4. **Telemetry consent UX at v0.5?** (a) CLI prompt at first `nucleus up` (breaks CI); (b) README disclaimer + explicit `nucleus enable otel`; (c) silent until user runs `nucleus enable otel` (current ADR-011 §1 default). Default: **(c)**. Cloud customers consent via Cloud ToS.
5. **`SECURITY.md` pre-v0.5?** v0 §10 says issues are public-by-default in v0.1. GitHub Security Advisories let researchers file privately without a `security@` mailbox; cost ≈ 5 minutes. Default: **yes — `SECURITY.md` lands before v0.1 ship**.

---

## Cross-references

- **Predecessor**: `docs/internal/security/threat_model_v0.md` — canonical for §2 deployment shape and §5 STRIDE walkthrough.
- **ADRs locked**: ADR-001, ADR-002, ADR-006, ADR-007, ADR-008, ADR-009, ADR-010, ADR-011, ADR-012.
- **Architecture**: `docs/specs/nucleus_architecture_v4.1.md` §3.1, §6.4, §13, §15.
- **Constraints**: AGENTS.md §3 Hard Constraints #6 + #11; §7; §11.7; §11.13.
- **Research**: `oidc_providers.md`; `minio.md` §3; `seaweedfs.md` §4.2; `openlineage.md`; `opentelemetry.md`; `observability_backends.md`; `daft.md` §8 row 4.

---

*Honest is better than thorough. NEEDS VERIFICATION items in §9 are real gaps the next round of work must close.*
