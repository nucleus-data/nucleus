# Threat Model v0 — v0.1 Heartbeat scope

> **Status**: Pre-implementation, design phase. Authored Month 0 (Pre-Heartbeat).
> **Scope**: v0.1 ONLY — local CLI + warehouse on local disk; optional MinIO / Postgres dev services.
> **NOT in scope**: multi-tenant SaaS, RBAC, OIDC delegation (v0.3+), Cloud tier, Workbench web UI (v0.2+), `ctx.agent` (v0.5+); v0.2 has Workbench Copilot chat only.
> **Audience**: junior DE who needs v0.1's actual attack surface before opening the repo publicly.
> **Owner**: solo founder. Re-review triggers: see [§12](#12-review-cadence).

This doc is intentionally **lean**. v0.1 is a single Python process on a developer's laptop — small attack surface, kept small. Enterprise concerns (SOC2, multi-tenancy, audit logging, threat-actor modeling) belong in `threat_model_v1.md` when v0.5+ approaches. If you find yourself adding "but at scale we'd need…" content here, **stop** — capture it in [§11](#11-action-items) instead.

## §1. What we're modeling

- **In scope**: the v0.1 attack surface — what a developer running `nucleus` on their own laptop is exposed to.
- **Out of scope**: Nucleus Cloud, Nucleus Enterprise, Workbench multi-user (separate doc when v0.5+ approaches).
- **Methodology**: lightweight **STRIDE** (Spoofing / Tampering / Repudiation / Info Disclosure / DoS / Elevation of Privilege) for the "local-first developer tool" deployment shape.
- **Honesty bias**: where v0.1 has zero defense (e.g., no auth, single-user trust), we say so. False reassurance is worse than a known gap.

## §2. The v0.1 deployment shape

```
┌─────────────────── User's laptop ─────────────────────┐
│ ┌──────────────┐  in-process  ┌────────────────────┐  │
│ │ nucleus CLI  │ ───────────▶ │ ctx SDK + wrapped  │  │
│ │ (Python)     │              │ libs (DuckDB,      │  │
│ └──────┬───────┘              │ Polars, PyIceberg, │  │
│        │ filesystem r/w       │ Dagster)           │  │
│        ▼                      └─────────┬──────────┘  │
│ ┌──────────────┐  ┌─────────────────────▼──────────┐  │
│ │ .env         │  │ warehouse/ (Iceberg + Parquet) │  │
│ │ catalog.db   │  │ .dagster_home/                 │  │
│ └──────────────┘  └────────────────────────────────┘  │
└──────────────────────────┬────────────────────────────┘
              outbound only │
        ┌─────────┬─────────┴─────────┐
        ▼         ▼                   ▼
   Source DB    S3 / MinIO   Optional dev testcontainers
   (Postgres)   AWS IAM      (Postgres, MinIO)
   TLS pref'd
```

Single process. No Nucleus daemon, no background workers, **no Nucleus-served network ports** (Dagster's UI hidden by default per v4.1 §6.6). Single user — inherits the OS user's permissions. Local-first — default catalog = filesystem; default warehouse = `./warehouse/`. Outbound-only — v0.1 accepts no inbound connections.

## §3. Assets we're protecting

In rough order of "if this leaks, how bad?":

1. **Source-system credentials** — Postgres URLs, S3 keys. In env vars or `.env`. **Highest sensitivity.**
2. **Data in transit** — source DB → DuckDB / Polars → Iceberg files. May include PII, financials, secrets in row values.
3. **Data at rest** — Iceberg metadata + Parquet files in `warehouse/`. Same sensitivity as the source.
4. **Catalog metadata integrity** — `*.metadata.json` + `catalog.db`. Corruption = loss of all snapshots = unrecoverable.
5. **Build-artifact integrity** — the `nucleus` package on PyPI (relevant from v0.5+ when we publish).

We do NOT protect Nucleus internals from the user — they own the laptop and the process. Trust boundary is the OS edge.

## §4. Trust boundaries

| # | Boundary | Trust | Enforcement |
|---|---|---|---|
| 1 | User ↔ Nucleus CLI | Full (same process) | OS user account |
| 2 | Nucleus ↔ wrapped libs | Full (same process) | **Supply-chain risk** — see §5.5 |
| 3 | Nucleus ↔ source DB | Partial | DB credentials + TLS (`sslmode=require`) |
| 4 | Nucleus ↔ S3 / MinIO | Partial | AWS IAM / MinIO access keys + TLS |
| 5 | Nucleus ↔ AI providers (v0.2+) | Partial | API key per provider; user data may leave host — see §8 |

Biggest v0.1 risk is **boundary #2** (supply chain). Addressed via pinning + audit (§5.5).

## §5. STRIDE walkthrough (concrete and honest)

### §5.1 Source credentials

- **Spoofing / Tampering**: low — local CLI, file in user's home. `.gitignore` covers `.env`, `.env.*`, `secrets.toml`, `*.pem`, `*.key`, `credentials.json`.
- **Info Disclosure**: **HIGH if `.env` leaks to git.** Defenses: `.gitignore` (verified), `pre-commit-hooks` `detect-private-key` in `.pre-commit-config.yaml`. Secret-scanning hook (`gitleaks` / `detect-secrets`) is **TODO P1** (see §11).
- **Elevation**: low — credentials grant access to source / S3 only. Use least-privilege DB users in production.

In place: `engineering.md §5.3` forbids logging raw credentials; `§8.4` wraps secrets in `pydantic.SecretStr` / `msgspec` `Secret`; `§12.4` forbids `importlib.import_module` on user-supplied module names.

### §5.2 Data in transit

- **Spoofing**: source DB MITM if TLS not enforced. Document `sslmode=require` in `SETUP.md` and `nucleus.toml` examples; warn when DSN is plain `postgres://` (implement when `ctx.copy_from` ships).
- **Tampering**: TLS handles when configured.
- **Info Disclosure**: cleartext queries with PII in logs. `engineering.md §5.3` forbids PII in logs (log shapes, not values). Enforced in code review, not yet by a script.
- **DoS**: misconfigured retry hammers source. `tenacity` retry decorator (per ADR-001) uses exponential backoff. Connection pool defaults from `engineering.md §11.5`.

### §5.3 Data at rest (warehouse)

- **Tampering**: anyone with filesystem write to `warehouse/` can modify Parquet / metadata. v0.1 = filesystem permissions only (single user on own laptop = trust the OS). v0.3+: catalog with auth (Lakekeeper).
- **Info Disclosure**: `warehouse/` is unencrypted. Document "use OS-level disk encryption (BitLocker on Windows, FileVault on macOS, LUKS on Linux)" in `SETUP.md` (TODO P2). v0.3+ S3: SSE-S3 enabled by default; KMS optional.
- **DoS**: disk fill from runaway materialization is out of scope for v0.1; user notices via OS disk-full error.

### §5.4 Catalog metadata integrity

Highest **correctness** risk in v0.1 (see [ADR-001](../decisions/ADR-001-no-iceberg-commit-service.md)).

- **Tampering**: anyone with filesystem write can corrupt `*.metadata.json` → all snapshots lost. Filesystem perms only; backups are user's responsibility in v0.1.
- **Atomicity failure**: per **ADR-001**, atomicity is delegated to PyIceberg's catalog — filesystem catalog uses atomic file rename on Linux/macOS; **Windows semantics differ** and are covered by PoC #1 atomic-commit stress tests.
- **Repudiation**: no audit trail in v0.1 (single user). v0.5+: audit log to a dedicated `ops.audit` Iceberg asset.

**Honest gap**: ADR-001 explicitly delegates atomicity to the catalog. If `catalog.db` (SQLite, in the PyIceberg SQL catalog case) corrupts, **we have no recovery**. Backup strategy for v0.1 = user copies `warehouse/` and `catalog.db` to a backup location. Proper backup pattern doc planned for v0.5+ (`docs/patterns/backup.md`).

### §5.5 Package supply chain

**Most likely** non-user-error compromise vector in v0.1.

- **Tampering** (malicious release of `pyiceberg`, `duckdb`, `polars`, `dagster`, `psycopg`, `sqlalchemy`, etc.): exact pins in `pyproject.toml` (Hard Constraint #11); `pip-audit` in [`ci.yml`](../../.github/workflows/ci.yml) and weekly via [`upgrade-deps.yml`](../../.github/workflows/upgrade-deps.yml); quarterly upgrade audit (`AGENTS.md §11.13`); **no bulk upgrades** — one component per PR. Future (v0.5+): sigstore signing of Nucleus releases; SLSA attestations (v1.0+).
- **Spoofing** (typosquatting, e.g. `polrs`, `psycog`): reviewer checks dep names against [`docs/compatibility.md`](../compatibility.md) before approving any PR that adds a dep. Future: enforce a dep allowlist in `scripts/check_pinning.py`.
- **Info Disclosure** (compromised dep exfils env / data): pinning + `pip-audit` is the v0.1 defense. We cannot fully defend without a sandboxed runtime.
- **Elevation** (malicious dep with `setup.py` post-install script): we use `hatchling` (no scripts) and pin transitive resolutions where possible.

**v0.1 TODOs** (see §11): create `.github/dependabot.yml`; promote `pip-audit` from non-fatal to fatal-on-Critical-CVEs before v0.1 ship.

## §6. Authentication and authorization (v0.1)

**There is none.** Intentional and correct for v0.1. Single-user, single-process, local CLI. The authorization boundary is the **OS user account** that owns `warehouse/`, `catalog.db`, `.dagster_home/`, and `.env`. We delegate identity to whoever is logged into the laptop. **v0.3+**: OIDC delegation per Hard Constraint #6 and v4.1 §15.1 — Authentik / Keycloak / Okta / Azure AD; we will **never** own an identity store. **v0.5+ Workbench multi-user**: separate threat model required.

## §7. Logging and audit (v0.1)

- All logs go through `structlog` (`engineering.md §5.1`); no `print()` in `src/`.
- Event names follow `noun.verb` past-tense (`asset.materialized`, `commit.failed`).
- **No PII in logs** (`engineering.md §5.3`) — log shapes (`rows=1000`), not values.
- **No persistent audit log in v0.1.** Dagster's local run log is the only history. Recovery for "what did I change?" = `git log` of your asset code.
- **Future** (v0.5+): OpenTelemetry traces emitted by default; structured audit log persisted to a dedicated `ops.audit` Iceberg asset.

## §8. AI-specific threats (v0.2+)

**v0.1 has no Copilot.** This section captures the threat model we expect to publish when `ctx.agent` lands in v0.2+, so today's design choices don't paint us into a corner.

1. **User data leakage via LLM provider.** User runs Copilot → asset code + sample row → external LLM API → row data crosses our trust boundary. Mitigations: document **what we send** in the `ctx.agent` SDK (per-call user opt-in, v0.2+); local-LLM option (Ollama) for sensitive data — already wired into [`.env.example`](../../.env.example) (`NUCLEUS_LLM_BACKEND=ollama`, v0.4+).
2. **Prompt injection via user-written SQL or asset code.** Adversarial column names / docstrings could trick Copilot into generating unintended ops. Mitigation: Copilot **suggests** code; user must apply it. Never auto-runs ops on production assets.
3. **Token exfiltration.** Per `.env.example`, LLM API keys are user-side env vars. **Nucleus does NOT proxy LLM calls.** Keys never reach a Nucleus-controlled server.
4. **Cost-runaway.** Adversarial prompt could explode token usage. Mitigation: per-session token budget setting in `nucleus.toml` (planned).

**Action**: an ADR is required when Copilot ships; this section graduates into `docs/security/threat_model_v0.2.md` at that point.

## §9. Known limitations (be honest)

In v0.1 we **cannot** defend against:

- **A malicious local user** on the same OS account. (By design — they own the process.)
- **A compromised pinned release** of a wrapped library — pin discipline + `pip-audit` + quarterly audit only.
- **A compromised CI runner.** GitHub-hosted runners are a known risk; we minimize blast radius via least-privilege workflow `permissions:` blocks (`ci.yml` defaults to `contents: read`).
- **Adversarial input that crashes a wrapped library** (e.g., a malicious Parquet file). We surface the resulting `NucleusError` per v4.1 §6.4, but the underlying library handles parsing.
- **Loss of `catalog.db` or `warehouse/` from disk failure.** Backup is the user's responsibility in v0.1.
- **Concurrent multi-process writes** to the filesystem catalog. v0.1 is single-process; multi-process is a v0.3+ Lakekeeper use case.

These get fixed as we advance: **v0.3** (OIDC + Lakekeeper close most auth and concurrency gaps); **v0.5** (audit log + Workbench → full re-review); **v1.0+** (sigstore signing + SLSA attestations).

## §10. Incident response (v0.1)

- **`.env` accidentally pushed to GitHub** — (1) force-rotate every credential in the file; (2) run `gitleaks` or GitHub's secret scanning on the repo; (3) `git filter-repo` to scrub history if the repo is public; (4) **do not** assume rotation alone is enough if the leak window was >5 minutes — bots scrape new commits aggressively.
- **`warehouse/` corrupted** — restore from your filesystem backup. v0.1 has no built-in recovery (documented limitation, §9).
- **Pinned dep ships a malicious release** — exact pin protects us until *we* upgrade. If `pip-audit` flagged it, `git revert` the upgrade PR. If we already shipped on the bad version, downgrade per the rollback command in the upgrade PR (`AGENTS.md §11.13`), force a release, notify users via CHANGELOG.
- **Dagster runner compromised** — Dagster runs **in-process** with Nucleus, same trust boundary as everything else. There is no remote Dagster daemon to compromise in v0.1. If a user enables `nucleus enable compat-dagster` (v4.1 §6.6 Tier 3), they take on Dagster's full surface area; documented escape-hatch territory.
- **Suspected upstream vulnerability with no patch** — file a GitHub issue with `security` label. If exploitable, ship a `chore(security):` PR that reduces exposure (e.g., disable the affected code path behind a feature flag) while we wait for the upstream patch.

**Reporting**: file a GitHub issue with the `security` label. For sensitive reports (post-v0.5+), a `security@` contact will be published. v0.1 has no separate disclosure channel — assume issues are public-by-default until then.

## §11. Action items

| # | Pri | Action | Where |
|---|---|---|---|
| 1 | done | `.env` and friends in `.gitignore` | `.gitignore` (verified) |
| 2 | done | `pre-commit-hooks/detect-private-key` enabled | `.pre-commit-config.yaml` |
| 3 | done | Exact pins on every runtime dep | `pyproject.toml` |
| 4 | done | Weekly `pip-audit` + outdated-deps audit | `.github/workflows/upgrade-deps.yml` |
| 5 | **P1** | Add `gitleaks` or `detect-secrets` pre-commit hook | `.pre-commit-config.yaml` (target v0.2) |
| 6 | **P1** | Create `.github/dependabot.yml` for auto single-component upgrade PRs | (file does not yet exist) |
| 7 | **P1** | Promote `security` workflow step in `ci.yml` from non-fatal to fatal-on-Critical-CVEs by v0.1 ship | `.github/workflows/ci.yml` |
| 8 | P2 | Document filesystem perms + disk encryption guidance | `SETUP.md` (new section) |
| 9 | P2 | `ctx.copy_from` warns when Postgres DSN lacks `sslmode=require` | implementation, when `ctx.copy_from` lands |
| 10 | P3 | Allowlist of accepted dep names in `scripts/check_pinning.py` (typosquat defense) | `scripts/check_pinning.py` |
| 11 | v0.2 | Author full AI-specific threat doc when Copilot ships | `docs/security/threat_model_v0.2.md` |
| 12 | v0.3 | Re-review §6, §7 after OIDC + Lakekeeper land | this doc |
| 13 | v0.5 | Full Workbench multi-user threat model v1 | `docs/security/threat_model_v1.md` |

## §12. Review cadence

Re-review this document when ANY of these triggers fire:

- **Major version bump** (v0.x → v0.(x+1)) — reassess everything.
- **New library wrapped** that touches credentials, network, or storage. Add to §5 STRIDE walkthrough; check `docs/research/<lib>.md` for security notes.
- **AI Copilot ships** (v0.2+) — §8 graduates into its own document.
- **OIDC arrives** (v0.3+) — rewrite §6 and §7.
- **Public repo opens** (planned ahead of v0.5+) — re-run §11 P1 actions; ensure secret-scanning is enforced; verify Dependabot is on.
- **A reported security issue** lands with `security` label — every fix triggers a doc review.

File reviews as PRs that update this file directly.

---

*Honest is better than thorough. If something here is wrong, fix the doc — don't paper over the gap.*
