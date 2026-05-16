# Research: Apache Polaris (JVM-native Iceberg REST Catalog)

> **Component status in Nucleus**: **v0.3+ catalog co-default (alongside Lakekeeper).** Not in v0.1. v0.1 ships with the filesystem-backed `pyiceberg.SqlCatalog` per `docs/specs/nucleus_architecture_v4.1.md` §5.7 + Amendment 4. At `nucleus init` time (v0.3+), the user picks Lakekeeper or Polaris; Nucleus speaks to either via `pyiceberg.RestCatalog`. Tier 2 (wrappable, swappable) per v4.1 §9.
> **Pin candidate**: Polaris server **`1.4.1`** (released **2026-05-01**, downloads page + GitHub release verified 2026-05-13). **Not pinned in `pyproject.toml`** — Polaris is an external JVM service, not a Python dep. Python integration is **`pyiceberg==0.8.1` `RestCatalog`** (already pinned). Docker image: `apache/polaris:apache-polaris-1.4.1`; admin: `apache/polaris-admin-tool:apache-polaris-1.4.1`. Helm chart: `polaris/polaris` from `https://downloads.apache.org/polaris/helm-chart`.
> **License**: **Apache-2.0** (Apache Software Foundation Top-Level Project — ALL ASF TLPs are Apache-2.0 by policy: https://www.apache.org/licenses/). GitHub blob viewer returns empty for `LICENSE.md` (same `WebFetch` quirk as Lakekeeper's repo); verify in-repo before pinning if paranoid.
> **JVM-free**: **NO** — Polaris is Java 21 + Quarkus. Hard Constraint #1 explicit exception per `docs/decisions/ADR-002-positioning-decision-2026-05.md` §6: the constraint forbids JVM in **Nucleus's core path**; the catalog is an external service in its own process, identical to talking to a Postgres binary. JVM lives outside `nucleus up` startup. *Polaris is the ASF-governance / enterprise-trust trajectory; Lakekeeper is the no-JVM / single-binary trajectory.*
> **Research date**: 2026-05-13
> **Used in**: nowhere (yet). Pre-research artifact for the v0.3 catalog ADR — companion to `docs/internal/research/lakekeeper.md`.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening the v0.3 catalog ADR. Polaris is the canonical **wrap-not-build** case for the ASF-governance catalog trajectory (Pillar #2, Pillar #5): we will never write our own commit service (Hard Constraint #5 + ADR-001) and we will never compete on catalog governance with the Apache Software Foundation.

---

## §1. At a glance

- **License**: Apache-2.0 (ASF TLP)  •  **Maintainer**: Apache Software Foundation (origin: Snowflake-built; ASF Incubator 2024-08 → graduated TLP **2026-02-18** per ADR-002 §6)  •  **GitHub**: https://github.com/apache/polaris (~1,935 stars at research time)
- **Position**: external service in L0 (Physics), wrapped at L2 by the Asset Materialization Adapter via `pyiceberg.RestCatalog`. Users never see it.
- **Latest stable**: `1.4.1` (2026-05-01); `1.4.0` (2026-04-21, first post-incubation release); `1.3.0-incubating` (2026-01-16, last pre-TLP). The `-incubating` suffix dropped at `1.4.0`.
- **Implementation**: Java 21 + Quarkus. Repo description: "Apache Polaris, the interoperable, open source catalog for Apache Iceberg."
- **Runtime artefact**: executable JAR (`bin/server`) or Docker image or Helm chart. JVM heap typically 4-8 GiB in production, ~512 MB-1.5 GB tunable for laptop.

**What it is**: a Quarkus-based JVM service that implements the [Apache Iceberg REST Catalog OpenAPI spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml). Two HTTP surfaces — `/api/catalog/v1/...` (data-plane Iceberg REST consumed by query engines) and `/api/management/v1/...` (control-plane for catalogs, namespaces, principals, roles, grants, policies) — plus `/q/health` / `/q/metrics` on the Quarkus management port (8182). Owns the source of truth for "which Iceberg snapshot is current" and provides single-table atomic commits backed by JDBC PostgreSQL (production) or in-memory (test) persistence. Does **not** execute compute; DuckDB/Polars read/write Parquet directly.

---

## §2. What Polaris is, in Nucleus terms

Polaris occupies the **catalog** slot of v4.1 §5.7 — the same slot Lakekeeper occupies on the other co-default trajectory. It maps `(catalog, namespace, table) → metadata_location` and atomically swaps the pointer on commit. v0.1 does the same with `pyiceberg.SqlCatalog` against a SQLite file. Polaris is the v0.3+ option for teams that prefer **ASF-governed catalog with native Snowflake/Databricks/Glue federation, built-in policy framework, and broader table-format support** (Iceberg + Delta + Hudi via "generic tables").

Entity hierarchy (per https://polaris.apache.org/in-dev/unreleased/entities/ + `releases/latest/` §Key concepts): **Realm → Catalog → Namespace (nestable) → Table / View / Policy**. Security axis: **Principal → Principal Role → Catalog Role → Privilege**. The **realm** (`Polaris-Realm` HTTP header) is Polaris's multi-tenancy primitive — a logical partition inside a single deployment. Nucleus v0.3 uses one realm per project; v0.5+ Cloud may use one realm per tenant.

**Vocabulary discipline (AGENTS.md §7)**: Polaris docs use "metastore" for the persistence backend (Postgres / MongoDB storing Polaris's own data). We never use that term in Nucleus copy — we say **persistence backend** for Polaris's Postgres/MongoDB, and reserve **catalog** for the top-level entity (which Polaris also calls "catalog" — terms align cleanly there). When `pyiceberg.RestCatalog(warehouse="X", ...)` connects to Polaris, the `warehouse` parameter resolves to a Polaris **catalog** name — a vocabulary clash with Lakekeeper, where `warehouse` is Lakekeeper's own term. The Asset Materialization Adapter abstracts this away; users see only "catalog". <!-- banned-term: metastore -->

---

## §3. Official documentation URLs

Every fact below cites this set. Verified by `WebFetch` 2026-05-13.

Use `https://polaris.apache.org/releases/1.4.1/...` for stable docs and `https://polaris.apache.org/in-dev/unreleased/...` for `main`-branch docs. Sections referenced below: **`getting-started/{quick-start,binary-distribution}/`**, **`configuration/{configuring-polaris,configuring-polaris-for-production,configuration-reference}/`** (the last is 53 KB; full property list), **`managing-security/{access-control,external-idp,external-pdp}/`**, **`{entities,realm,metastores,policy,admin-tool,command-line-interface,evolution,helm-chart/production}/`**, **`getting-started/using-polaris/keycloak-idp/`** (end-to-end OIDC example). <!-- banned-term: metastore -->

Other anchors: https://polaris.apache.org/  •  https://polaris.apache.org/downloads/ (release dates)  •  https://github.com/apache/polaris + /releases  •  https://hub.docker.com/r/apache/polaris  •  https://downloads.apache.org/polaris/helm-chart  •  Iceberg REST spec: https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml  •  Polaris Management OpenAPI: https://github.com/apache/polaris/blob/main/spec/polaris-management-service.yml  •  pyiceberg REST stanza: https://py.iceberg.apache.org/configuration/#rest-catalog

**URL gaps / 404s on 2026-05-13** — flag for AI agents:

- **All four user-supplied URLs 404**: `https://polaris.apache.org/{quickstart,docs/configuring-polaris-for-production,docs/iceberg-rest-service,docs/access-control}/`. Polaris uses `/releases/<version>/...` (stable) or `/in-dev/unreleased/...` (dev) — never `/docs/...` or bare `/quickstart/`. Map: `quickstart` → `releases/1.4.1/getting-started/quick-start/`; production config → `releases/1.4.1/configuration/configuring-polaris-for-production/`; access-control → `in-dev/unreleased/managing-security/access-control/`; iceberg-rest-service has **no dedicated page** (it's implicit in the Iceberg REST spec link).
- `https://polaris.apache.org/in-dev/unreleased/{authentication,deploying-polaris,iceberg-rest-service,api-spec}/` all 404. Authentication lives at `.../managing-security/external-idp/`.
- `https://github.com/apache/polaris/blob/main/{README.md,LICENSE}` returns empty body via `WebFetch` (same GitHub blob-viewer quirk as Lakekeeper's repo, not a real 404). License is Apache-2.0 by ASF TLP policy + trademarked release-artefact wording.
- `https://polaris.apache.org/blog/2026-04-21-polaris-1.4.0-release/` and similar release-blog URLs 404. Use Downloads page + GitHub Releases for changelogs.

---

## §4. APIs Nucleus will use

**Polaris is a server, not a Python library.** There is **no `pip install polaris`** package usable as a Nucleus client. (Polaris ships a bundled admin **CLI** — a separate Python program — but it is not a library we import.) Two interaction surfaces only.

### §4.1 Iceberg data-plane — via `pyiceberg.RestCatalog` (already pinned)

Polaris implements the Iceberg REST spec at `/api/catalog/v1/`. The pyiceberg client is identical to the Lakekeeper case at the API surface; differences are in OAuth2 flow and scope syntax:

```python
from pyiceberg.catalog.rest import RestCatalog
# Docs: https://py.iceberg.apache.org/configuration/#rest-catalog

catalog = RestCatalog(
    name="nucleus",
    uri="http://localhost:8181/api/catalog",   # Polaris Iceberg REST base
    warehouse="quickstart_catalog",            # pyiceberg term → Polaris "catalog" name
    credential="<client-id>:<client-secret>",  # Polaris principal credentials OR external-IdP client
    scope="PRINCIPAL_ROLE:ALL",                # Polaris-specific scope syntax; required
    **{
        # Optional — defaults to <uri>/v1/oauth/tokens, which for Polaris becomes
        # http://localhost:8181/api/catalog/v1/oauth/tokens (internal-auth realms only)
        "oauth2-server-uri": "http://localhost:8181/api/catalog/v1/oauth/tokens",
        "header.Polaris-Realm": "POLARIS",     # realm context header; required in multi-realm setups
        "header.X-Iceberg-Access-Delegation": "vended-credentials",
    },
)
```

The catalog swap from v0.1 (`SqlCatalog`) to v0.3+ (`RestCatalog`) is **config-only**; **no `coordination/` code changes**. Standard pyiceberg surface (`create_namespace`, `create_table`, `load_table`, `Table.append`, `Table.scan().to_arrow()/.to_duckdb()/.to_polars()`) passes through unchanged — the Constraint #9 swap-without-rewrite payoff.

**OAuth2 — DIFFERENT from Lakekeeper, critical for the v0.3 ADR.** Polaris supports three modes per realm (`polaris.authentication.<realm>.type`):

- `internal` (default) — Polaris **issues tokens itself** via its built-in `TokenBroker` (rsa-key-pair or symmetric-key). Endpoint: `POST /api/catalog/v1/oauth/tokens` with `grant_type=client_credentials`.
- `external` — Quarkus OIDC validates tokens from an external IdP. Polaris's internal token endpoint returns **HTTP 501** in this mode.
- `mixed` — try internal first, fall back to OIDC.

Per Hard Constraint #6 ("delegate to OIDC"), Nucleus's v0.3 default for Polaris realms is **`external`** with Quarkus OIDC against the user-chosen IdP. The `internal` mode is a dev convenience (the quickstart compose uses it) but ships disabled in production-targeted `nucleus init --catalog polaris` templates.

### §4.2 Polaris management plane — via plain HTTP or the bundled CLI

Provisioning (catalog/principal/role/grant/policy CRUD) is **not in pyiceberg**. Three options ordered by LOC cost: (1) **defer to the bundled Polaris CLI** (a separate Python program — `polaris catalogs create ...` — that we run via subprocess, NOT embed); (2) **embed minimal `httpx` calls** to `/api/management/v1/{catalogs,principals,principal-roles,catalog-roles,grants}` (~100-200 LOC; needed for Cloud v0.5+ and consistent first-boot UX across Lakekeeper / Polaris); (3) **generate a typed client from `polaris-management-service.yml`** (overkill for v0.3).

Polaris also ships an `admin-tool` JAR / Docker image (`apache/polaris-admin-tool:apache-polaris-1.4.1`) for *one-time* bootstrap (realm creation, root-principal seeding, NoSQL maintenance) — runs **once per realm** before `polaris server` first serves traffic. Nucleus's v0.3 docker-compose runs it as an init container with `bootstrap -r nucleus -c nucleus,root,$ROOT_SECRET` plus Postgres env vars (per `admin-tool/`). Full Management OpenAPI: https://github.com/apache/polaris/blob/main/spec/polaris-management-service.yml.

---

## §5. Integration points with Nucleus

### §5.1 `nucleus init --catalog polaris` (v0.3 design sketch)

When the user picks Polaris: (1) compose adds `polaris-server` (8181), `polaris-postgres` (≥ 15 for `polaris.persistence.type=relational-jdbc`), and an init container running `polaris-admin-tool bootstrap`; (2) `nucleus_config.toml` records `[catalog] type = "polaris"`, `uri = "http://localhost:8181/api/catalog"`, `warehouse = "nucleus-default"`, `realm = "POLARIS"`, plus OIDC block (or internal-auth bootstrap creds for laptop-only); (3) first boot `POST`s a catalog (with S3 storage profile pointing at MinIO) + a service-principal to `/api/management/v1/`; (4) `ctx` SDK constructs `RestCatalog(...)` from the toml — same `Catalog` interface as v0.1's `SqlCatalog`.

**v0.1 → v0.3 user migration**: Iceberg tables are bit-identical regardless of catalog. Users register existing S3 metadata files via `POST /api/catalog/v1/<prefix>/namespaces/<ns>/register`. No data movement. Per v4.1 §10.1 (Mode 1 Graduation).

### §5.2 OIDC delegation (Hard Constraint #6 — non-negotiable)

Per AGENTS.md §3 Hard Constraint #6, Polaris realms in Nucleus production MUST use `polaris.authentication.<realm>.type=external` with Quarkus OIDC plugged into an external IdP. Documented IdPs (per `external-idp/` + Keycloak example): **Keycloak** (Polaris ships end-to-end compose at `.../using-polaris/keycloak-idp/` — recommended for v0.3 self-hosted), **Okta / Microsoft Entra-ID / Auth0** (standard Quarkus OIDC; per-provider gotchas **NEEDS VERIFICATION** — Lakekeeper's docs are more detailed here), **Google Identity Platform** (supported by Quarkus; Polaris docs don't explicitly cover — **NEEDS VERIFICATION**), **Authentik** (OIDC-compliant; not explicitly documented — **NEEDS VERIFICATION**). OPA is authorization-side via External PDP, separate from authentication.

Key config keys (full reference in §3): `polaris.authentication.<realm>.type` per-realm override; `quarkus.oidc.{auth-server-url,client-id}`; `polaris.oidc.principal-mapper.{id-claim-path,name-claim-path}` for JWT-claim → Polaris-principal mapping; `polaris.oidc.principal-roles-mapper.{filter,mappings[i].{regex,replacement}}` for JWT-claim → `PRINCIPAL_ROLE:<name>` translation; `polaris.realm-context.{realms,require-header=true}` (**`require-header=true` mandatory in production** — default-permissive header omission can leak between realms).

**Token validation**: local against JWKS via Quarkus OIDC — no IdP round-trip per request. **JWT only** by default ("The default implementation of PrincipalMapper can only work with JWT tokens" — `external-idp/`). Same constraint as Lakekeeper.

### §5.3 Storage backend co-config — credential vending is Polaris's defining feature

Polaris holds storage credentials (S3 / Azure / GCS) **per-catalog**. Data-plane: `pyiceberg.RestCatalog` calls `loadTable`; Polaris returns metadata + **vended short-lived credentials** (per `releases/latest/` §Credential vending); pyiceberg's FileIO reads/writes Parquet directly — **Polaris is not in the data path**.

Supported storage types per `polaris.features."SUPPORTED_CATALOG_STORAGE_TYPES"`: `S3`, `Azure`, `GCS`, plus `FILE` (test only — **disable in production** by setting the list to `[ "S3", "Azure" ]`). v0.1 local (MinIO): `s3` flavor with access-key/secret. v0.3+ cloud: explicit keys OR `assume-role-arn` / Azure tenant ID / GCS-default-credentials. **Storage-boundary safety**: keep `ALLOW_UNSTRUCTURED_TABLE_LOCATION`, `ALLOW_EXTERNAL_TABLE_LOCATION`, `ALLOW_EXTERNAL_METADATA_FILE_LOCATION`, `ALLOW_TABLE_LOCATION_OVERLAP`, `ALLOW_WILDCARD_LOCATION` OFF in Nucleus templates (per `configuring-polaris-for-production` §Review Location Compatibility Flags).

### §5.4 RBAC model — richer than Lakekeeper

Polaris RBAC (per `managing-security/access-control/`): **Principal → Principal Role → Catalog Role → Privilege** (2-tier delegation). Privileges scoped on Securable Objects (Catalog / Namespace / Iceberg Table / View / Policy). Privilege families: **Table** (10 — `TABLE_{CREATE,DROP,LIST,READ_PROPERTIES,WRITE_PROPERTIES,READ_DATA,WRITE_DATA,FULL_METADATA,ATTACH_POLICY,DETACH_POLICY}`); **View** (6); **Namespace** (8); **Catalog** (7 — incl. `CATALOG_MANAGE_CONTENT` superset); **Policy** (8). v0.3 single-team mode provisions one `nucleus_writer` catalog role with `CATALOG_MANAGE_CONTENT` + one `nucleus_reader` with `TABLE_READ_DATA` + `TABLE_FULL_METADATA`. v0.5+ multi-tenant (Cloud): per-tenant catalog + scoped principal roles.

⚠️ Polaris docs warn explicitly: **table / view / namespace / catalog properties are readable metadata.** Never store passwords, tokens, access keys — anyone with `*_READ_PROPERTIES` or `*_FULL_METADATA` can read them. Surface in `docs/security/threat_model_v0.md`.

### §5.5 Atomic commit semantics — the Hard Constraint #5 hinge

Per v4.1 §6.5 + ADR-001, Nucleus does not build a commit service. Polaris implements `commitTable` = **single-table atomic commits** via JDBC transactions on the metadata-pointer row. Docs explicitly cite the Iceberg-spec requirement ("Performing atomic operations so that you can update the current metadata pointer" — `releases/latest/` §Catalog).

**Inherited constraint**: cross-table atomic commits **NOT in the Iceberg REST spec** and **NOT in Polaris** — same as v0.1's `SqlCatalog`, same as Lakekeeper, same as ADR-001. Sequence multi-table writes; document the inconsistency window; do not pretend. <!-- banned-term: none -->

### §5.6 Error translation contract (PoC #1 implications)

Polaris errors propagate through pyiceberg's `RestCatalog` exception hierarchy — **identical translation path to Lakekeeper** because pyiceberg is the translator. The HTTP-status → pyiceberg exception → `NucleusError` mapping is **identical** to `docs/internal/research/lakekeeper.md` §5.5 + `docs/internal/research/pyiceberg.md` §6. Verification required at PoC #1; key Polaris-specific cases:

| Polaris / HTTP | pyiceberg likely raises | NucleusError target |
|---|---|---|
| 401 / 403 | `AuthorizationExpiredError` / `ForbiddenError` | `NucleusAuthError` |
| 404 (table / namespace) | `NoSuchTableError` / `NoSuchNamespaceError` | `NucleusAssetNotMaterialized` / `NucleusCatalogError` |
| 404 (Polaris "catalog" entity) | type **NEEDS VERIFICATION**; likely `RESTError` / `BadRequestError` | `NucleusCatalogError` |
| 409 (commit conflict) | `CommitFailedException` | `NucleusCommitConflictError` (retry, exp backoff, max 3) |
| 5xx mid-commit | `CommitStateUnknownException` | `NucleusCommitUnknownError` (**do NOT retry**) |
| 501 on `/oauth/tokens` (realm in `external` mode) | `RESTError` | `NucleusConfigError` ("realm is external-auth only; use IdP token") |

**Hallucination flag**: do NOT invent `PolarisError`, `PolarisCommitConflict`, `PolarisRBACError`, etc. — they don't exist on the Python side. Everything routes through pyiceberg. See §10.

---

## §6. Performance characteristics

Numbers from docs only; **no Nucleus benchmark yet** — repeat on real laptop hardware before quoting to users. **Polaris's JVM nature is the single biggest performance difference from Lakekeeper** and the principal reason both are co-defaults.

- **Cold-start**: JVM + Quarkus startup (Postgres pool init + JWKS warm-up + realm validation). Budget **5-15s** vs Lakekeeper's ~1-2s. **NEEDS VERIFICATION** under PoC #4 (`nucleus up <10s` target).
- **Idle memory**: Helm production guide recommends `8Gi` requests/limits. Real lower bound on a dev laptop with 1 small catalog: **~500 MB-1.5 GB JVM heap** (default `JAVA_MAX_MEM_RATIO=80`, plus container overhead) vs Lakekeeper's 100-300 MB. **Biggest user-facing trade-off** — surface in the `nucleus init` chooser.
- **Persistence backend**: **Postgres** (`relational-jdbc`) production-ready; **MongoDB NoSQL** (`nosql`) **beta**; **in-memory** test-only (data lost on restart). **No SQLite**. H2 may be supported for dev (per Quarkus datasource note in production-config) — **NEEDS VERIFICATION**.
- **JVM**: Java SE **21+** required (`binary-distribution`). Container image bundles `ubi9/openjdk-21-runtime`; users never install Java directly.
- **Quarkus caching + HA**: `polaris.persistence.cache.*` (default 40% of heap; reference-TTL `PT15M`); distributed-cache-invalidation for multi-replica; Helm `replicaCount` / `autoscaling`. Irrelevant for v0.3 single-laptop.
- **Ports**: 8181 = HTTP API (data + management); 8182 = Quarkus management port (`/q/health`, `/q/metrics`). Request limit (default): max body 10 MiB.

---

## §7. Compatibility with Nucleus pins (2026-05-13)

Polaris is an external service; Python deps interact only via `pyiceberg.RestCatalog`.

| Nucleus dep | Our pin | Polaris interaction | Conflict? | Resolution |
|---|---|---|---|---|
| `pyiceberg` | `0.8.1` | `RestCatalog` client. Polaris 1.4.x targets Iceberg REST spec; exact spec-version compat **NEEDS VERIFICATION** against 1.4.1 release notes. | **Likely fine, unverified** | Smoke-test full read/write/snapshot/refresh against Polaris 1.4.1 in v0.3 PR. |
| `pyiceberg` post-ADR-003 (`0.11.x`) | (planned) | Likely better — Polaris evolves with Iceberg REST spec. | unknown | Re-verify post-ADR-003. 0.8.1 → 0.11.x upgrade queued **before** v0.3. |
| Python | `>=3.11,<3.13` | not involved (server is JVM); only matters for the bundled `polaris` admin CLI which we don't embed. | No | OK |
| Postgres | not a Nucleus dep | requires `>=15` per Quarkus; H2 for dev (verify); MongoDB (beta) | n/a | Add `postgres:15-alpine` to v0.3 docker-compose. |
| Java | external | bundled in Docker image (`ubi9/openjdk-21-runtime`) | n/a | Image-pinned. |
| Docker | existing | image per release | No | Pin `apache/polaris:apache-polaris-1.4.1` exactly per Constraint #11. |
| OIDC providers | — | Keycloak / Okta / Entra-ID / Google / Authentik | n/a | Document per-provider recipes in v0.3 ADR — **NEEDS VERIFICATION** per provider. |

**Pin candidate justification — `1.4.1`** (https://github.com/apache/polaris/releases + https://polaris.apache.org/downloads/):

| Release | Date | Notes |
|---|---|---|
| **1.4.1** | 2026-05-01 | Patch: S3 + GCS URI handling; locations handling; staged-table handling; doc fixes. **Recommended pin.** |
| 1.4.0 | 2026-04-21 | First post-incubation release (no more `-incubating` suffix). Hudi integration; OPA event metadata; KMS for S3; Quarkus 3.30.x. |
| 1.3.0-incubating | 2026-01-16 | Last `-incubating`. Pre-ASF-TLP-graduation. Helm install required `--devel`. |
| 1.2.0 / 1.1.0 / 1.0.0 / 0.9.0 | 2025-10-23 / 2025-09-19 / 2025-07-09 / 2025-03-11 | Pre-graduation history. |

Pin `1.4.1`. Fresh-deploying for v0.3, so the 1.3.0-incubating → 1.4.0 graduation transition (Helm `--devel` quirk) doesn't bite us — but DO note it for anyone migrating from pre-graduation incubator deployments.

**Polaris Evolution / SemVer** (`evolution/`): SemVer for REST APIs (beta/experimental excepted), Policies, and user-facing `polaris.*` configuration. Major = breaking (e.g., Quarkus major bump). Backward-compatible: new optional Iceberg REST features; new URI prefixes (`v2`). Per Constraint #11, every minor bump = one PR + smoke test + rollback command. **Iceberg-spec coverage is not "always latest"** per evolution doc — smoke-test specific features per minor.

---

## §8. Polaris vs Lakekeeper decision matrix — the v0.3 `nucleus init` prompt's intelligence

This is the single most important section in this doc. The two catalogs are wrapped behind the **same** `pyiceberg.RestCatalog` interface; the user's choice is operational + governance, not API. The v0.3 `nucleus init --catalog ...` prompt must surface these dimensions in plain language.

| Dimension | Lakekeeper 0.12.2 | Apache Polaris 1.4.1 | Decision weight |
|---|---|---|---|
| **Implementation / runtime** | Rust, single static binary | Java 21 + Quarkus JVM | **High** — operational footprint differs by an order of magnitude |
| **Cold-start (`nucleus up`)** | ~1-2s (verify) | ~5-15s (verify; JVM warm-up) | **High** — directly affects PoC #4 30-min beachhead |
| **Idle memory** | 100-300 MB | 500 MB-1.5 GB JVM heap (8 GiB recommended for production Helm) | **High** — biggest laptop-fit differentiator |
| **Persistence backend** | Postgres ≥ 15 ONLY | Postgres (relational-jdbc), MongoDB (beta), H2 (verify) | Medium — both require Postgres in practice |
| **Governance** | Single-company (Vakamo) | Apache Software Foundation TLP (since 2026-02-18) | **High for enterprise procurement**; medium for solo dev |
| **Multi-vendor commit signal** | Lower (one company) | Higher (ASF + Snowflake + Dremio + ~50 contributors per release notes) | **High** — Pillar #5 (Apache + multi-vendor) |
| **Iceberg-spec coverage** | Catalog REST; Iceberg 1.5-1.7 advertised | Catalog REST; latest-spec-not-guaranteed per Evolution doc | Medium — practical parity for our use cases |
| **Native catalog federation** | None (separate Lakekeeper per catalog) | Built-in: external catalogs from Snowflake, Glue, Dremio Arctic, Hive | **High for Mode 1 graduation** — `compute=databricks` user already has a Glue catalog Polaris can federate |
| **Multi-format support** | Iceberg only | Iceberg + Delta + Hudi (generic tables) | Medium — Nucleus is Iceberg-only by Constraint #4; relevant for users with legacy Delta tables |
| **Authentication model** | External OIDC ONLY (never issues tokens) | Internal token broker + External OIDC + Mixed | **High** — Lakekeeper is a tighter Hard Constraint #6 fit; Polaris requires explicit `external` mode |
| **RBAC granularity** | Roles + grants on namespace/table; OpenFGA optional for ReBAC | Principal → Principal Role → Catalog Role → Privilege (2-tier delegation); + external PDP via OPA | **High for multi-tenant** — Polaris's 2-tier delegation models real org structures cleanly |
| **Credential vending** | Yes (`X-Iceberg-Access-Delegation`) | Yes, built-in and Polaris's defining marketing feature | Parity at API level |
| **Policy framework** | None | Built-in: `system.{data-compaction,snapshot-expiry,orphan-file-removal,metadata-compaction}` | **High at v0.5+** — automates Iceberg housekeeping users would otherwise script |
| **Storage backends** | S3 (incl. R2 + S3-compat), Azure ADLS Gen2, GCS | S3, Azure, GCS (no explicit R2 callout — likely works via S3-compat) | Parity for v0.3 |
| **Helm chart maturity** | Community chart; k8s Operator in development | Apache-official Helm chart at `downloads.apache.org/polaris/helm-chart` | **High for Cloud (v0.5+)** — Polaris's official chart is procurement-friendly |
| **Admin CLI** | None (UI + REST only) | Bundled Polaris Python CLI + separate `polaris-admin-tool` JAR for bootstrap | Medium |
| **Best for** | Laptop / dev / cost-sensitive / no-JVM-trajectory / OSS-only shops | Production / multi-tenant / enterprise / Snowflake-Databricks-Glue federation / procurement-sensitive | **Decisive** — pick the trajectory, then ship |

**The single most decisive dimension for the v0.3 `nucleus init` prompt**: **idle memory + cold-start** (operational footprint on the user's laptop). Polaris's 500 MB-1.5 GB JVM heap vs Lakekeeper's 100-300 MB is friction a 5-engineer team feels every `nucleus up`. ASF governance is procurement-sensitive (matters at the org level, not the dev level) — surface as a tooltip, not the headline. The prompt should ask, in plain language: *"Do you prefer (a) lightest-laptop-fit (Lakekeeper) or (b) Apache-governance and native cloud-catalog federation (Polaris)?"*

---

## §9. Swap-target analysis (v4.1 §9.3)

Polaris and Lakekeeper are **mutual swap targets** by design (ADR-002 §6). Both implement the Iceberg REST spec and Nucleus consumes both via `pyiceberg.RestCatalog` — swap cost is **near-zero**: flip `[catalog] uri` + `warehouse` in `nucleus_config.toml`, re-register existing Iceberg tables via the REST `register` endpoint, no data movement.

If both Polaris **and** Lakekeeper become unviable: **Apache Gravitino** (Apache-2.0, ASF Incubating; JVM; out of scope for v0.3) or **Unity Catalog OSS** (Apache-2.0, Databricks-led; existing v0.5+ target per v4.1 §5.7). **AWS Glue / Cloudflare R2 / Snowflake-managed Polaris** = Mode 1 graduation targets (v4.1 §10.1), not OSS swap targets. **Build custom REST server** — rejected (Constraint #5; ADR-001).

**Verdict**: Polaris co-default with Lakekeeper makes overall catalog-bus risk effectively zero for v0.3. Both feed the same downstream code path; swap drills run nightly in CI via the `pyiceberg.Catalog` Protocol surface; `docs/swap/catalog.md` documents the drill steps.

---

## §10. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge — log to `docs/internal/research/ai_hallucinations.md`)

- ❌ `from polaris import PolarisClient` / `from apache_polaris import Catalog` / `polaris.create_catalog(...)` — **does not exist** as a Nucleus-usable Python data-plane library. **No `pip install polaris` package** for our use. Polaris's bundled admin **CLI** is a separate Python program we don't embed. Data-plane = `pyiceberg.RestCatalog`. Management-plane = raw `httpx` against `/api/management/v1/...`.
- ❌ `RestCatalog(...).create_catalog(...)` — **fabricated**. pyiceberg's `Catalog` has `create_namespace` / `create_table`, NOT `create_catalog`. Polaris "catalogs" are a management-plane concept above the Iceberg spec; create via `POST /api/management/v1/catalogs`.
- ❌ `PolarisError`, `PolarisCommitConflict`, `PolarisAuthError`, `PolarisRBACError` — **fabricated**. Errors propagate through pyiceberg's REST hierarchy (`AuthorizationExpiredError`, `CommitFailedException`, `RESTError`, ...). Translate at the pyiceberg layer.
- ❌ Multi-table atomic commits via Polaris — **fabricated**. Same as Lakekeeper / ADR-001: Iceberg REST spec is single-table-atomic.
- ❌ Polaris accepting **opaque** OAuth2 tokens — **fabricated**. JWT only via the default `PrincipalMapper`; custom impls require Java code.
- ❌ A SQLite-backed Polaris for local dev — **fabricated**. Backends are `in-memory` (test only), `relational-jdbc` (Postgres / possibly H2), `nosql` (MongoDB beta).
- ❌ Citing `https://polaris.apache.org/{quickstart,docs/...}/` — **all 404**. Use `/releases/<version>/...` or `/in-dev/unreleased/...`.
- ❌ `polaris.set_oidc_provider("keycloak", ...)` or similar high-level helper — **fabricated**. OIDC is server-side Quarkus properties only.
- ❌ Pre-graduation API stability — APIs marked "beta" / "experimental" in `evolution/` are outside SemVer; pin to post-graduation versions (1.4.0+) for v0.3.

### Real gotchas from official docs

- **Polaris's "metastore" ≠ Nucleus's "catalog"** — in Polaris docs "metastore" is the persistence backend (Postgres / MongoDB). Our copy says **persistence backend**; "catalog" terms align cleanly. <!-- banned-term: metastore -->
- **`relational-jdbc` requires Postgres ≥ 15**. H2 supported for tests (verify). SQLite **NOT** supported.
- **`polaris-admin-tool bootstrap` MUST run before `polaris server`** on every fresh persistence backend. Idempotent. Run as init container in v0.3 compose.
- **In-memory persistence is the default** — production WILL lose state on restart unless `polaris.persistence.type=relational-jdbc` is set.
- **`FILE` storage type enabled by default** — disable in production by setting `SUPPORTED_CATALOG_STORAGE_TYPES = [ "S3", "Azure" ]`.
- **`polaris.realm-context.require-header=true` mandatory in production** — default-permissive header omission can leak between realms.
- **Internal-mode token validation fails across replicas with auto-generated keys** — pre-configure RSA keys mounted identically on every replica. Moot for our external-OIDC default.
- **Table / view / namespace / catalog properties are readable metadata** (per warnings on every entity page) — never store secrets there.
- **Cross-realm tokens are rejected with 401** — `realm-internal` tokens cannot access `realm-mixed` resources and vice versa. Pre-cite in Nucleus error messages.
- **501 from `/api/catalog/v1/oauth/tokens` is intentional** in `external`-mode realms. Translate to `NucleusConfigError` ("realm is external-auth only; obtain token from the IdP").
- **JVM heap defaults to 80% of container memory** (`JAVA_MAX_MEM_RATIO=80`). On a 16 GB laptop with `mem_limit: 4g`, Polaris uses ~3.2 GB. v0.3 compose tunes this DOWN.
- **Quarkus management port** = 8182 (`/q/health`, `/q/metrics`), distinct from data port 8181. Compose exposes both.
- **Generic tables (Delta/Hudi) is opt-in** per `entities/` — by default Polaris catalogs serve Iceberg only.
- **Helm chart `-incubating` workaround** — Polaris ≤ 1.3.0-incubating requires `helm install --devel`. 1.4.x+ does not.

---

## §11. Decision log

**Why Polaris enters at v0.3, not earlier, not later, as a co-default with Lakekeeper:**

- **Not v0.1**: Postgres 15 + Java 21 + ~1 GB JVM heap + extra container = +30s boot, +1 GB RAM, more operational surface — blocked by the v0.1 30-min beachhead metric (v4.1 §1.5). Filesystem `SqlCatalog` is sufficient for single-process single-laptop. **Defer.**
- **At v0.3**: bottleneck shifts from "first table in 30 min" to "shared multi-engine access + procurement-friendly Apache governance + native federation to Snowflake/Databricks/Glue." Polaris provides REST-based catalog + 2-tier RBAC + vended-creds + ASF-TLP governance + built-in catalog federation. **Now.**
- **Co-default with Lakekeeper (ADR-002 §6 + §8.1)**: single-catalog default ties Nucleus to one vendor's roadmap. Polaris (ASF TLP 2026-02-18) gives ASF-governance + multi-vendor signal + native cloud-catalog federation. Lakekeeper gives no-JVM + single-binary + ~10x smaller memory footprint. Both wrap behind the same `pyiceberg.RestCatalog` interface — co-default cost near-zero.
- **Polaris is the ASF-governance + Snowflake/Databricks federation trajectory.** Pillar #5 ("Friendly to giants, hostile to no-one"). Apache Polaris lands easier in enterprise procurement than "Lakekeeper" for many shops; born at Snowflake, so native interop with Snowflake-managed Polaris + Databricks Unity + AWS Glue is the smoothest Mode 1 graduation path (v4.1 §10.1). Lakekeeper has no equivalent built-in federation.
- **Never**: build our own catalog (Constraint #5; ADR-001). Pillar #2 violation.

Integration ADR: `docs/decisions/ADR-NNN-lakekeeper-polaris-v03-catalog.md` (one ADR covers both; they share interface).

---

## §12. Next reads when v0.3 work starts

- [ ] **Polaris vs Lakekeeper feature-parity matrix** — validate the §8 decision matrix on real instances.
- [ ] **`pyiceberg.RestCatalog` against Polaris 1.4.x — full smoke test.** Trigger every error in §5.6; reconcile error-translation table; log fabricated APIs to `ai_hallucinations.md`.
- [ ] **Management-plane HTTP wrapper sketch** — decide between option (1) "browser/CLI-only", (2) "embedded `httpx`", (3) "OpenAPI codegen" from §4.2. Bias toward option (1) for v0.3 first cut.
- [ ] **Per-IdP OIDC recipes** — Keycloak (Polaris ships example), Okta, Entra-ID, Google, Authentik. Document Quarkus-OIDC env-var blocks.
- [ ] **JVM heap tuning for laptop fit** — verify `JAVA_OPTS_APPEND="-Xms512m -Xmx1g"` keeps a 1-realm, 1-catalog, ~100-table Polaris responsive. Critical for PoC #4.
- [ ] **Polaris + Snowflake-managed-Polaris / AWS Glue / Cloudflare R2 compatibility** — for the Mode 1 graduation path. Snowflake-managed Polaris is the literal commercial graduation target.
- [ ] **Helm chart review for Nucleus Cloud (v0.5+)** — official Apache chart at `downloads.apache.org/polaris/helm-chart`.
- [ ] **Policy framework + External PDP (OPA)** — out of v0.3 scope; relevant for v0.5+ enterprise tier.

---

## §13. Useful links

- https://polaris.apache.org/ — start here. https://polaris.apache.org/releases/latest/ — latest-stable docs alias.
- https://polaris.apache.org/in-dev/unreleased/entities/ — entity hierarchy. **Bookmark.**
- https://polaris.apache.org/in-dev/unreleased/managing-security/{access-control,external-idp,external-pdp}/ — RBAC + OIDC + OPA.
- https://polaris.apache.org/releases/1.4.1/configuration/{configuring-polaris,configuration-reference,configuring-polaris-for-production}/ — every Polaris property.
- https://polaris.apache.org/in-dev/unreleased/getting-started/using-polaris/keycloak-idp/ — end-to-end OIDC working example; closest thing to a "v0.3 reference compose."
- https://github.com/apache/polaris + /releases  •  https://hub.docker.com/r/apache/polaris  •  https://downloads.apache.org/polaris/helm-chart
- https://github.com/apache/polaris/blob/main/spec/polaris-management-service.yml — Management OpenAPI YAML.
- https://py.iceberg.apache.org/configuration/#rest-catalog — pyiceberg side; OAuth2 + `scope=PRINCIPAL_ROLE:ALL`.
- https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml — the spec Polaris implements.
- `docs/internal/research/lakekeeper.md` — parallel doc; §8 matrix here mirrors §8 there.  •  `docs/internal/research/pyiceberg.md` §6 — error-translation v0.3 inherits.  •  `docs/decisions/ADR-002-positioning-decision-2026-05.md` §6 — co-default rationale.  •  `docs/specs/nucleus_architecture_v4.1.md` §5.7 — catalog stage table.

---

*Last verified: 2026-05-13 against Polaris 1.4.1. Re-verify when opening the v0.3 catalog ADR, before pinning a different release, after any minor or major upstream bump (per Constraint #11), and whenever pyiceberg upgrades (the REST OpenAPI version compatibility is the leading indicator of breakage). Log any AI-fabricated Polaris APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
