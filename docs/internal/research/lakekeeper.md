# Research: Lakekeeper (Rust-native Iceberg REST Catalog)

> **Component status in Nucleus**: **v0.3+ catalog co-default (alongside Apache Polaris).** Not in v0.1. v0.1 ships with the filesystem-backed `pyiceberg.SqlCatalog` per `docs/specs/nucleus_architecture_v4.1.md` §5.7 + Amendment 4. At `nucleus init` time (v0.3+), the user picks Lakekeeper or Polaris; Nucleus speaks to either via `pyiceberg.RestCatalog`. Tier 2 (wrappable, swappable) per v4.1 §9.
> **Pin candidate**: Lakekeeper server **`0.12.2`** (released **2026-05-10**, GitHub release verified 2026-05-13). **Not pinned in `pyproject.toml`** — Lakekeeper is an external service binary, not a Python dep. Python integration is **`pyiceberg==0.8.1` `RestCatalog`** (already pinned).
> **License**: **Apache-2.0**  •  **JVM-free**: **YES** — single Rust binary; no JVM, no Python runtime required by the server itself ("Single binary executable for all major platforms; no JVM or Python environment required" — https://docs.lakekeeper.io/). Hard Constraint #1 satisfied. *Polaris satisfies the ASF-governance criterion; Lakekeeper satisfies the no-JVM-trajectory criterion.*
> **Research date**: 2026-05-13
> **Used in**: nowhere (yet). Pre-research artifact for the v0.3 catalog ADR.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening the v0.3 catalog ADR. Lakekeeper is the canonical **wrap-not-build** case for the catalog layer (Pillar #2): we will never write our own atomic-commit service (Hard Constraint #5 + ADR-001).

---

## §1. At a glance

- **License**: Apache-2.0  •  **Maintainer**: Lakekeeper team (Vakamo / Christian Thiel et al.)  •  **GitHub**: https://github.com/lakekeeper/lakekeeper (~1,293 stars at research time)
- **Position**: external service in L0 (Physics), wrapped at L2 by the Asset Materialization Adapter via `pyiceberg.RestCatalog`. Users never see it.
- **Latest stable**: `0.12.2` (2026-05-10). Pre-1.0; minor releases ship breaking changes (see §7).
- **Implementation**: Rust on `iceberg-rust`. "No unsafe Code - guaranteed!" per docs landing.

**What it is**: a single Rust binary that implements the [Apache Iceberg REST Catalog OpenAPI spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml). Two HTTP surfaces — `/catalog` (data-plane Iceberg REST consumed by query engines) and `/management` (control-plane for warehouses, projects, users, roles) — plus `/ui/` and `/swagger-ui`. Owns the source of truth for "which Iceberg snapshot is current" and provides single-table atomic commits. Does **not** execute compute; DuckDB/Polars read/write Parquet directly.

---

## §2. What Lakekeeper is, in Nucleus terms

Lakekeeper occupies the **catalog** slot of v4.1 §5.7. It maps `(namespace, table) → metadata_location` and atomically swaps the pointer on commit. v0.1 does the same with `pyiceberg.SqlCatalog` against a SQLite file — single-process, single-laptop. Lakekeeper is the v0.3+ option for teams that need **shared multi-engine access** with central authorization, vended credentials, and multi-warehouse tenancy.

Entity hierarchy (per https://docs.lakekeeper.io/docs/nightly/concepts/ §Entity Hierarchy): **Server → Project → Warehouse → Namespace → Table/View** (+ Roles per Project; Users mirrored from IdP). The **Warehouse** is the connection-level handle for pyiceberg (`warehouse="<name>"`); `nucleus init` must POST to `/management/v1/warehouse` at first boot and store the name in `nucleus_config.toml`. Bootstrapping an admin user comes first (UI or `/management/v1/bootstrap`).

**Vocabulary discipline (AGENTS.md §7)**: Lakekeeper docs use both "warehouse" and "catalog" loosely; in Nucleus copy we always say **catalog** for the system and **warehouse** only for Lakekeeper's per-storage-profile partition unit. We never use "metastore". <!-- banned-term: metastore -->

---

## §3. Official documentation URLs

Every fact below cites this set. Verified by `WebFetch` 2026-05-13.

- Landing: https://docs.lakekeeper.io/  •  Getting Started: https://docs.lakekeeper.io/getting-started/
- Versioned docs root (use this prefix): `https://docs.lakekeeper.io/docs/nightly/` — pages: `concepts/`, `configuration/`, `authentication/`, `authorization/`, `storage/`
- GitHub: https://github.com/lakekeeper/lakekeeper  •  Releases: https://github.com/lakekeeper/lakekeeper/releases  •  Helm chart: https://github.com/lakekeeper/lakekeeper-charts
- Iceberg REST spec (the contract): https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml
- pyiceberg REST config (our Python surface, includes Lakekeeper-specific stanza): https://py.iceberg.apache.org/configuration/#rest-catalog

**404 / URL-gap notes (2026-05-13)** — flag for AI agents:

- User-supplied URLs `https://docs.lakekeeper.io/{concepts,configuration,authentication,storage,api}/` (no `/docs/nightly/` prefix) **all 404**. Live URLs use `/docs/nightly/...`.
- `/docs/nightly/api/` is a stub redirecting to https://github.com/lakekeeper/lakekeeper/tree/main/docs/docs/api. Use `/swagger-ui` on a running server for interactive exploration.
- `/docs/nightly/upgrade/` 404s — no central upgrade doc. Use concepts §Upgrades & Migration + per-release CHANGELOG.
- `github.com/.../blob/main/{README.md,LICENSE}` returns empty via `WebFetch` (GitHub blob-viewer issue, not a real 404). License confirmed Apache-2.0 from docs landing + repo description; verify in-repo before pinning if paranoid.

---

## §4. APIs Nucleus will use

**Lakekeeper is a server, not a Python library.** Nucleus does not `import lakekeeper` — there is **no official Python client SDK**. Two interaction surfaces only.

### §4.1 Iceberg data-plane — via `pyiceberg.RestCatalog` (already pinned)

Authoritative Lakekeeper-specific stanza from https://py.iceberg.apache.org/configuration/#rest-catalog:

```python
from pyiceberg.catalog.rest import RestCatalog
# Docs: https://py.iceberg.apache.org/configuration/#rest-catalog

catalog = RestCatalog(
    name="nucleus",
    uri="http://localhost:8181/catalog",
    warehouse="nucleus-default",
    credential="<client-id>:<client-secret>",
    scope="lakekeeper",
    **{"oauth2-server-uri": "http://idp.local/realms/<realm>/protocol/openid-connect/token"},
)
```

The catalog swap from v0.1 (`SqlCatalog`) to v0.3+ (`RestCatalog`) is **config-only**; **no `coordination/` code changes**. Standard pyiceberg surface (`create_namespace`, `create_table`, `load_table`, `Table.append`, `Table.scan().to_arrow()/.to_duckdb()/.to_polars()`) passes through unchanged — the Constraint #9 swap-without-rewrite payoff.

OAuth2 Client-Credentials flow: **Lakekeeper does NOT issue tokens itself** ("Lakekeeper does not issue API-Keys or Client-Credentials itself" — auth doc). pyiceberg fetches the token from the IdP via `credential` + `oauth2-server-uri`, sends it with each request.

### §4.2 Lakekeeper management plane — via plain HTTP

Provisioning operations (warehouse CRUD, project/role CRUD, bootstrap) are **not in pyiceberg**. v0.3 has two options:

1. **Defer to UI** — bring up containers, open `http://localhost:8181/ui/`, user clicks through. Lowest LOC; acceptable for v0.3 first cut.
2. **Embed minimal HTTP calls** — `POST /management/v1/warehouse` etc. via `httpx`. ~50-100 LOC. Probably needed for Cloud tier (v0.5+).

Endpoints we will need: `POST /management/v1/bootstrap` (first-boot admin), `POST /management/v1/warehouse` (create warehouse), `GET /management/v1/warehouse` (list), `POST /management/user` + `POST /management/v1/role` (users/roles — also auto-provisioned on `/catalog/v1/config` hit), `GET /metrics` (port 9000, Prometheus), `/swagger-ui` (live OpenAPI explorer).

Authoritative warehouse-create body for S3-compat (MinIO) per https://docs.lakekeeper.io/docs/nightly/storage/#s3-compatible:

```json
{
  "warehouse-name": "nucleus-default",
  "storage-credential": {"type": "s3", "credential-type": "access-key",
    "aws-access-key-id": "<key>", "aws-secret-access-key": "<secret>"},
  "storage-profile": {"type": "s3", "bucket": "nucleus-warehouse",
    "region": "local-01", "sts-enabled": true, "flavor": "s3-compat",
    "key-prefix": "nucleus-default"},
  "delete-profile": {"type": "hard"}
}
```

Full OpenAPI YAML: https://github.com/lakekeeper/lakekeeper/tree/main/docs/docs/api.

---

## §5. Integration points with Nucleus

### §5.1 `nucleus init --catalog lakekeeper` (v0.3 design sketch)

When the user picks Lakekeeper: (1) `docker-compose.yml` adds `lakekeeper` (port 8181) + `lakekeeper-postgres` (Postgres ≥ 15 — only supported backend per configuration §Persistence Store); (2) compose runs `lakekeeper migrate` before `lakekeeper serve` — migrations are idempotent, transactional, version-skip-safe; (3) `nucleus_config.toml` records `[catalog] type = "lakekeeper"`, `uri = "http://localhost:8181/catalog"`, `warehouse = "nucleus-default"`, plus OIDC block; (4) first boot calls `POST /management/v1/bootstrap`, then `POST /management/v1/warehouse` with an S3-compat profile pointing at MinIO; (5) `ctx` SDK constructs `RestCatalog(...)` from the toml — same `Catalog` interface as v0.1's `SqlCatalog`.

**v0.1 → v0.3 user migration**: Iceberg tables are bit-identical regardless of catalog. Users `pyiceberg-cli register-table` (or scripted equivalent) into the new Lakekeeper warehouse pointing at the same S3 path. No data movement. Per v4.1 §10.1 (Mode 1 Graduation).

### §5.2 OIDC delegation (Hard Constraint #6 — non-negotiable)

Per AGENTS.md §3 Hard Constraint #6 ("No custom auth system — always delegate to OIDC"), Lakekeeper MUST be deployed with an external OIDC provider. **Lakekeeper itself never issues credentials** — aligns perfectly with our constraint.

Documented IdPs (https://docs.lakekeeper.io/docs/nightly/authentication/):

- **Keycloak** — recommended for the v0.3 self-hosted batteries-included path; the [`access-control-advanced`](https://github.com/lakekeeper/lakekeeper/tree/main/examples/access-control-advanced) compose file ships it pre-wired.
- **Microsoft Entra-ID** — 3-app-registration pattern; v1-vs-v2 issuer claim → may need `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS`.
- **Google Identity Platform** — Lakekeeper warns (June 2025) Google lacks standard OAuth2 Client-Credentials → machine auth broken; humans only. Use Keycloak/Entra-ID for service accounts.
- **Kubernetes ServiceAccounts** — `LAKEKEEPER__ENABLE_KUBERNETES_AUTHENTICATION=true` + `system:auth-delegator` ClusterRoleBinding. For Cloud (v0.5+).
- **Authentik** — not explicitly documented by Lakekeeper but is OIDC-compliant. **NEEDS VERIFICATION**.
- **OPA** — authorization-side, not authentication-side. Out of v0.3 scope.

Key env vars (configuration §Authentication): `LAKEKEEPER__OPENID_PROVIDER_URI` (well-known config root, **without** `/.well-known/openid-configuration` suffix), `LAKEKEEPER__OPENID_AUDIENCE` (required `aud`; skipping it permits cross-app token reuse), `LAKEKEEPER__OPENID_SUBJECT_CLAIM` (`oid` for Entra-ID, `sub` elsewhere — set explicitly in production), `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS` (Entra-ID v1/v2 escape hatch).

Token validation is **local against JWKS** — no IdP round-trip per request. **Opaque (non-JWT) tokens NOT supported** (https://github.com/lakekeeper/lakekeeper/issues/620). Multi-IdP chains supported up to 3 authenticators.

### §5.3 Storage backend co-config

Lakekeeper holds the storage credentials (S3 / ADLS / GCS) **per-Warehouse** — not Nucleus. Data-plane (per https://docs.lakekeeper.io/docs/nightly/storage/): `pyiceberg.RestCatalog` calls `loadTable`; Lakekeeper returns metadata + either vended STS credentials or remote-signing endpoints (per `X-Iceberg-Access-Delegation` header: `vended-credentials` / `remote-signing` / `client-managed`); pyiceberg's FileIO reads/writes Parquet directly from S3 — **Lakekeeper is not in the data path**.

Profile model: one `storage-profile` + one `storage-credential` **per warehouse** (NOT per project, NOT global); **never share locations between warehouses** — vended-creds safety. Supported types: `s3` (`flavor: aws` or `s3-compat`), `adls` (ADLS Gen2), `gcs` (with/without HNS), Cloudflare R2. v0.1 local (MinIO): `flavor=s3-compat`, `sts-enabled=true`, access-key/secret. v0.3+ cloud: explicit keys OR `aws-system-identity` + `assume-role-arn` + `external-id` (system-identity is **disabled by default** — set `LAKEKEEPER__ENABLE_AWS_SYSTEM_CREDENTIALS=true`). Storage-layout flag controls directory structure (`default` / `full-hierarchy` / `tabular-only`); always include `{uuid}` in templates to survive renames.

### §5.4 Atomic commit semantics — the Hard Constraint #5 hinge

Per v4.1 §6.5 + ADR-001, Nucleus does not build a commit service. Lakekeeper implements the Iceberg REST `commitTable` endpoint = **single-table atomic commits** via Postgres transactions on the metadata-pointer row. Confirmed: Idempotency-Key spec (default 30-min lifetime + 5-min grace), ETag / `If-None-Match` for optimistic concurrency (release 0.11.0). **Inherited constraint**: cross-table atomic commits **NOT in the Iceberg REST spec** and **NOT in Lakekeeper** — same as v0.1's `SqlCatalog`, same as ADR-001. Sequence multi-table writes; document the inconsistency window; do not pretend.

### §5.5 Error translation contract (PoC #1 implications)

When Lakekeeper returns errors via REST, pyiceberg's `RestCatalog` raises through its REST exception hierarchy. **Verification required** at PoC #1 + before any v0.3 PR — trigger each on a real Lakekeeper instance and reconcile with `docs/internal/research/pyiceberg.md` §6.

| Lakekeeper / HTTP | pyiceberg likely raises | NucleusError target |
|---|---|---|
| 401 / 403 | `AuthorizationExpiredError` / `ForbiddenError` | `NucleusAuthError` |
| 404 (table / namespace) | `NoSuchTableError` / `NoSuchNamespaceError` | `NucleusAssetNotMaterialized` / `NucleusCatalogError` |
| 404 (warehouse) | 0.12.0 returns `NoSuchWarehouseException`; pyiceberg type **NEEDS VERIFICATION** | `NucleusCatalogError` |
| 409 (commit conflict) | `CommitFailedException` | `NucleusCommitConflictError` (retry, exp backoff, max 3) |
| 5xx mid-commit | `CommitStateUnknownException` | `NucleusCommitUnknownError` (**do NOT retry**) |
| 5xx (non-commit) | `ServerError` / `ServiceUnavailableError` | `NucleusCatalogError` |

**Hallucination flag**: do NOT invent Lakekeeper-specific exception classes. There is no `LakekeeperError`, `LakekeeperCommitConflict`, etc. — everything routes through pyiceberg. See §9.

---

## §6. Performance characteristics

Numbers from docs only; **no Nucleus benchmark yet** — repeat on real laptop hardware before quoting to users.

- **Cold-start**: Rust binary, single executable. Not quoted numerically. **NEEDS VERIFICATION** under PoC #4 (`nucleus up <10s` target). Postgres init dominates the wall-clock; Lakekeeper itself is a fraction.
- **Idle memory**: not documented. Release 0.12.0 switched from `ptmalloc` to `jemalloc` ("Reduce memory footprint by switching to jemalloc"). Budget 100-300 MB for binary + Postgres; measure during PoC #4.
- **Throughput**: not benchmarked publicly; advertised horizontal scalability ("no local state - the catalog can be scaled horizontally easily"). For v0.3 single-laptop scope this is irrelevant; matters at v0.5+ Cloud.
- **Backend**: Postgres ≥ 15 mandatory ("Lakekeeper is currently only compatible with Postgres >= 15"). Read-replica supported via separate `LAKEKEEPER__PG_DATABASE_URL_READ` / `_WRITE`. **No SQLite, no in-memory option.** v0.1 → v0.3 step-up in operational complexity.
- **Required Postgres extensions**: `uuid-ossp`, `pgcrypto`, `pg_trgm`, `btree_gin`, `btree_gist`. Auto-installed if Lakekeeper's role has `CREATE`; otherwise admin pre-creates (standard `postgresql-contrib`).
- **Request limits** (defaults): max body 2 MiB, max request time 30s.

---

## §7. Compatibility with Nucleus pins (2026-05-13)

Lakekeeper is an external service; Python deps interact only via `pyiceberg.RestCatalog`.

| Nucleus dep | Our pin | Lakekeeper interaction | Conflict? | Resolution |
|---|---|---|---|---|
| `pyiceberg` | `0.8.1` | `RestCatalog` client. Lakekeeper 0.12.x advertises Iceberg `1.5`-`1.7` compat. | **Likely fine, unverified** | Smoke-test full read/write/snapshot/refresh against Lakekeeper 0.12.2 in v0.3 PR. |
| `pyiceberg` post-ADR-003 (`0.11.x`) | (planned) | Likely better — adds Iceberg v3 features | unknown | Re-verify post-ADR-003. The 0.8.1 → 0.11.x upgrade is queued **before** v0.3. |
| Python | `>=3.11,<3.13` | not involved (server is Rust) | No | OK |
| Postgres | not a Nucleus dep | requires `>=15` + 5 extensions | n/a | Add `postgres:15-alpine` to v0.3 docker-compose; pre-create extensions if non-superuser. |
| Docker | existing | image per release | No | Pin `lakekeeper/lakekeeper:0.12.2` exactly per Constraint #11. |
| OIDC providers | — | Keycloak / Entra-ID / Okta / Google / k8s SA / Authentik | n/a | Document per-provider env-var recipes in v0.3 ADR. Authentik **NEEDS VERIFICATION**. |

**Pin candidate justification — `0.12.2`** (https://github.com/lakekeeper/lakekeeper/releases):

| Release | Date | Notes |
|---|---|---|
| **0.12.2** | 2026-05-10 | Patch: Location canonicalization, Postgres pool init, ADLS `%` encoding, STS/CEL credential hardening. **Recommended pin.** |
| 0.12.1 | 2026-05-04 | Adds **Instance Admins** (config-granted bypass for operators), audit + OPA improvements. |
| 0.12.0 | 2026-04-01 | **MAJOR — breaking**: cache metric names unified; structured log format; default delegation flipped to `vended-credentials`; deprecated endpoints removed. Read full changelog before any 0.11.x → 0.12.x bump. |
| 0.11.6 | 2026-05-10 | Security backport (RUSTSEC patches). |
| 0.11.0 | 2026-01-01 | ETag / `If-None-Match`; `vended-credentials` default. |

Pin `0.12.2`. The 0.12.0 breaking changes are documented; we'll be fresh-deploying for v0.3, so they don't bite us — but DO bite anyone migrating from 0.11.x. Document the rollback in the v0.3 ADR.

---

## §8. Swap-target analysis (v4.1 §9.3)

If Lakekeeper becomes unviable (license pivot, vendor death, perf regression >2x, deprecation):

| Candidate | License | Swap cost | Notes |
|---|---|---|---|
| **Apache Polaris** | Apache-2.0 (ASF TLP Feb 18, 2026) | **~zero** — flip URI + warehouse name | Alternate co-default per ADR-002 §6. JVM — operationally heavier, governance-stronger. |
| **Apache Gravitino** | Apache-2.0 (ASF Incubating) | Medium — broader scope (catalog-of-catalogs); REST partially compatible | JVM. Out of scope for v0.3 unless Polaris also dies. |
| **Build custom REST server** | — | High — ~3-5K LOC | **Rejected**: Hard Constraint #5. Re-open only if no viable OSS catalog exists. |
| **AWS Glue / Unity Catalog OSS / Cloudflare R2** | varied | Low (config flip) | Not OSS swap targets — **graduation targets** per v4.1 §10.1 Mode 1. |

**Verdict**: Polaris co-default makes Lakekeeper swap cost effectively zero (both consumed via `pyiceberg.RestCatalog`). Vendor-concentration risk on Lakekeeper (single-company) is the explicit reason for the Polaris co-default. Keep both swap interfaces alive in CI via the same `pyiceberg.Catalog` Protocol surface.

---

## §9. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge — log to `docs/internal/research/ai_hallucinations.md`)

- ❌ `from lakekeeper import LakekeeperClient` / `from lakekeeper.client import Catalog` — **does not exist**. No official Python client lib. Use `pyiceberg.RestCatalog` for data-plane, raw `httpx` for management API.
- ❌ `pip install lakekeeper` / `import lakekeeper` — fabricated. Lakekeeper ships as Rust binary + container image + Helm chart, **not** PyPI package.
- ❌ `RestCatalog(...).create_warehouse(...)` — fabricated. pyiceberg's `Catalog` has `create_namespace`/`create_table`, **not** `create_warehouse` (warehouses are a Lakekeeper management-plane concept above the Iceberg spec).
- ❌ `LakekeeperError`, `LakekeeperCommitConflict`, `LakekeeperAuthError` — fabricated. Errors propagate through pyiceberg's REST exception hierarchy (`AuthorizationExpiredError`, `CommitFailedException`, `RESTError`); translate at the pyiceberg layer.
- ❌ Multi-table atomic commits via Lakekeeper — fabricated. Same as ADR-001: Iceberg REST spec is single-table-atomic.
- ❌ Lakekeeper accepting **opaque** OAuth2 tokens — fabricated. JWT only.
- ❌ A SQLite / in-memory-backed Lakekeeper for local dev — fabricated. Postgres ≥ 15 only.
- ❌ Citing `https://docs.lakekeeper.io/{concepts,configuration,authentication,storage,api}/` (no `/docs/nightly/` prefix) — **all 404**.
- ❌ `pip install dlt[lakekeeper]`-style integration — fabricated. dlt's Iceberg destination uses pyiceberg + filesystem destination; underlying catalog configured at the pyiceberg layer.

### Real gotchas from official docs

- **Postgres 15+ mandatory** + 5 extensions (`uuid-ossp`, `pgcrypto`, `pg_trgm`, `btree_gin`, `btree_gist`). `postgres:15` not `postgres:13` in compose.
- **`lakekeeper migrate` MUST run before `lakekeeper serve`** on every upgrade — server fails: "Database is not up to date with binary..."
- **Bootstrap step is mandatory** for non-example deployments. First user to hit the bootstrap endpoint becomes the initial admin.
- **Identifier case-insensitive but case-preserving** (PostgreSQL ICU collation). `My_Table`, `MY_TABLE`, `my_table` all resolve to the same table. Cross-engine interop reason — Spark/Trino lowercase, Snowflake uppercases. **Surprises programmatic clients** that assume case-sensitive Iceberg semantics.
- **Soft-delete + Spark `DROP TABLE PURGE` is broken** for Java engines that don't honor `purgeRequested`. Workaround: `push-s3-delete-disabled=true`. Apache Iceberg 2.0 will fix upstream. pyiceberg path is unaffected.
- **0.12.0 default flip**: vended-credentials replaced remote-signing as default access-delegation. Some older S3 stores don't support STS → set `vended-credentials=false` per warehouse if signing fails.
- **Warehouse storage paths must NEVER overlap** — vended-credentials safety; Lakekeeper enforces.
- **OIDC `audience` MUST be set** in production — default-omitting permits cross-app token reuse.
- **`x-forwarded-*` headers respected by default**. Behind non-trusted proxy, set `LAKEKEEPER__USE_X_FORWARDED_HEADERS=false`.
- **No SCIM yet** for role provisioning (GitHub issue #497). Roles via UI or `POST /management/v1/role`.
- **Vendor concentration**: single-company-led (Vakamo). The ADR-002 §6 reason for the **Polaris co-default** (Polaris = ASF TLP, multi-vendor).
- **Pre-1.0 release**. Minor versions (0.x.0) ship breaking changes (0.6.0, 0.11.0, 0.12.0). Per Constraint #11, every minor bump = one PR + smoke test + rollback command.

---

## §10. Decision log

**Why Lakekeeper enters at v0.3, not earlier, not later, as a co-default with Polaris:**

- **Not v0.1**: Postgres 15 + 5 extensions + extra container = +30s boot, +500 MB RAM, more operational surface — blocked by the v0.1 30-min beachhead metric (v4.1 §1.5). Filesystem `SqlCatalog` is sufficient for single-process single-laptop. **Defer.**
- **At v0.3**: bottleneck shifts from "first table in 30 min" to "shared multi-engine access across the team." Lakekeeper provides REST-based catalog + RBAC + vended-creds — exactly what Spark/Trino/Snowflake federation needs. **Now.**
- **Co-default with Polaris (ADR-002 §6)**: single-catalog default ties Nucleus to one vendor's roadmap. Polaris (ASF TLP Feb 18, 2026) gives ASF-governance + multi-vendor signal; Lakekeeper gives no-JVM + single-binary + Rust-fit deployment. Both wrap behind the same `pyiceberg.RestCatalog` interface — co-default cost is near-zero.
- **Why Lakekeeper is the no-JVM trajectory choice**: Hard Constraint #1 forbids JVM in core path. Polaris IS JVM (Java + Quarkus). Lakekeeper = single binary; Polaris = JVM + heavier image. Per ADR-002 §4.2: "Lakekeeper retained for Rust-fit deployments."
- **Never**: build our own catalog (Constraint #5; ADR-001). Pillar #2 violation.

Integration ADR: `docs/decisions/ADR-NNN-lakekeeper-polaris-v03-catalog.md` (opens when v0.3 work starts).

---

## §11. Next reads when v0.3 work starts

- [ ] **Lakekeeper vs Polaris feature-parity matrix** — API surfaces, authz models, storage backends, operational footprint. Validate the co-default thesis.
- [ ] **`pyiceberg.RestCatalog` against Lakekeeper 0.12.x — full smoke test.** Trigger every error in §5.5; reconcile error-translation table; log fabricated APIs to `ai_hallucinations.md`.
- [ ] **Management-plane HTTP wrapper sketch** — decide between option (1) "browser-only provisioning" vs option (2) "embedded `httpx` calls" from §4.2. Estimate LOC; bias toward option (1) for v0.3 first cut.
- [ ] **Authentik-specific OIDC compatibility** — likely "just works" but verify with a v0.3 PoC.
- [ ] **Helm chart review** — for Nucleus Cloud v0.5+ (https://github.com/lakekeeper/lakekeeper-charts; community k8s Operator in development).
- [ ] **Lakekeeper + Cloudflare R2 / AWS S3 Tables compatibility** — for the Mode 1 graduation path. R2 documented; S3 Tables is upstream Iceberg REST so should work but needs a smoke test.
- [ ] **Idempotency-Key end-to-end** — verify pyiceberg sets the header (Lakekeeper feature; pyiceberg may or may not generate it).
- [ ] **0.11.x → 0.12.x upgrade rehearsal** — run `lakekeeper migrate`; verify cache-metric and log-format compat with our OTel pipeline.

---

## §12. Useful links

- https://docs.lakekeeper.io/ — start here. https://docs.lakekeeper.io/getting-started/ — bootstrap walkthrough.
- https://docs.lakekeeper.io/docs/nightly/concepts/ — entity hierarchy + identifier case + soft-delete + migration. **Bookmark.**
- https://docs.lakekeeper.io/docs/nightly/{authentication,authorization,storage,configuration}/ — IdP + storage + env-var references.
- https://github.com/lakekeeper/lakekeeper + /releases — source + release notes (read full changelog between current and target per Constraint #11).
- https://github.com/lakekeeper/lakekeeper/tree/main/examples/access-control-advanced — batteries-included compose (Keycloak + OpenFGA + MinIO + Jupyter + Lakekeeper). Reference for v0.3 compose.
- https://github.com/lakekeeper/lakekeeper-charts — Helm chart. https://discord.gg/jkAGG8p93B — community Discord.
- https://py.iceberg.apache.org/configuration/#rest-catalog — pyiceberg side; includes Lakekeeper-specific YAML stanza.
- https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml — the spec Lakekeeper implements.
- `docs/internal/research/pyiceberg.md` §6 — error-translation contract v0.3 inherits.
- `docs/decisions/ADR-002-positioning-decision-2026-05.md` §6 — Polaris co-default rationale.
- `docs/specs/nucleus_architecture_v4.1.md` §5.7 — catalog stage table. ADR-001 — Hard Constraint #5 anchor.

---

*Last verified: 2026-05-13 against Lakekeeper 0.12.2. Re-verify when opening the v0.3 catalog ADR, before pinning a different release, after any minor or major upstream bump (per Constraint #11), and whenever pyiceberg upgrades (the REST OpenAPI version compatibility is the leading indicator of breakage). Log any AI-fabricated Lakekeeper APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
