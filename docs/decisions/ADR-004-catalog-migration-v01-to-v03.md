# ADR-004: Iceberg Catalog Migration Path v0.1 → v0.3

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder (queued by ADR-002 §4.2 P2 "Polaris co-default" amendment)
> **Tags**: catalog, iceberg, v0.3-roadmap, jvm-exemption, beachhead, oidc, composability
> **Related**: ADR-001 (no commit service), ADR-002 §4.2 + §6 + §8.1, ADR-003 (pyiceberg 0.8.1 → 0.11.x — hard prerequisite), ADR-007 (license tier), AGENTS.md §3 Constraints #1 + #6 + #9 + #11 + §7, `nucleus_architecture_v4.1.md` §5.7 + §1.5 + §9 + §10.1, `docs/research/lakekeeper.md` (Worker F), `docs/research/polaris.md` (Worker H), `docs/research/oidc_providers.md` (Worker W), `docs/research/pyiceberg.md` §5-§6, `docs/architecture/sequence_swap_drill.md`, `nucleus_cli_spec.md` §4.2.

## Context

v0.1 ships `pyiceberg.SqlCatalog` on a SQLite file — single-process, no external service, no auth — sufficient for the v4.1 §1.5 beachhead (5-engineer startup, `git clone` → BI-ready Iceberg table in **<30 min**). Past v0.3 (Mo 14-20 per `nucleus_cli_spec.md` §4.2), the bottleneck shifts to **shared multi-engine access**: atomic single-table commits across concurrent writers, OIDC-delegated identity per Constraint #6, and a REST surface for Spark / Trino / Snowflake / Databricks consumers (v4.1 §10.1 Mode 1 graduation).

ADR-002 §4.2 P2 elevated **Apache Polaris** to co-default with **Lakekeeper** at v0.3+ when Polaris graduated to ASF Top-Level Project on 2026-02-18, but **deferred which is the documented default**: v4.1 §5.7 reads "pick at `nucleus init` time" but ships no opinion. Workers F (Lakekeeper, ~28 KB) and H (Polaris, ~37 KB) returned converged research on 2026-05-13. Both are Apache-2.0 (ADR-007 Tier 1 GREEN — license not the differentiator); both implement the [Iceberg REST OpenAPI spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml); both are consumed via the same `pyiceberg.RestCatalog` (`docs/research/pyiceberg.md` §5 + §8: *"catalog swap is config-only … nothing in `src/`"*). **The choice is operational + governance, not API.**

## Decision

> **v0.3 documented default: Lakekeeper** (Rust, ~100-300 MB idle, ~1-2 s cold-start, OIDC-validation-only — never issues tokens).
> **v0.3 alternate via `nucleus enable polaris`: Apache Polaris** (JVM, ~500 MB-1.5 GB idle, ASF TLP governance signal, native federation to Snowflake / Databricks / Glue).
> **Both run identically through `pyiceberg.RestCatalog`** — swap is a `nucleus_config.toml` `[catalog]` flip; no `coordination/` code changes per Constraint #9.
> **`pyiceberg.SqlCatalog` (v0.1 filesystem) remains supported indefinitely** for solo / single-process users — no one is stranded.

### Comparison matrix (consolidated from Worker H §8 + Worker F §1 / §6 / §8 / §10)

| Dimension | Lakekeeper 0.12.2 | Apache Polaris 1.4.1 | Winner for v0.3 default |
|---|---|---|---|
| Governance | Single-company (Vakamo) | ASF Top-Level Project (2026-02-18) | Polaris (org-level procurement) |
| Runtime | Rust, single static binary | Java 21 + Quarkus | **Lakekeeper** (Constraint #1 spirit) |
| Idle memory | ~100-300 MB (Rust + jemalloc since 0.12.0) | ~500 MB-1.5 GB JVM heap; Helm prod 8 GiB | **Lakekeeper** (5-10x lighter → v4.1 §1.5) |
| Cold-start | ~1-2 s after Postgres ready | ~5-15 s (JVM + Quarkus + JWKS warm-up) | **Lakekeeper** (PoC #4 `<10 s` target) |
| Token issuance | **NEVER** ("Lakekeeper does not issue API-Keys or Client-Credentials itself" — Worker F §5.2) | **CAN** via internal `TokenBroker`; production REQUIRES `polaris.authentication.<realm>.type=external` (Worker H §5.2) | **Lakekeeper** (Constraint #6 default-safe) |
| `pyiceberg.RestCatalog` compat | Yes — Lakekeeper-specific stanza in pyiceberg docs (Worker F §4.1) | Yes — `scope=PRINCIPAL_ROLE:ALL` + `header.Polaris-Realm` required (Worker H §4.1) | Tie |
| Built-in federation to Snowflake / Databricks / Glue / Hive | None | Built-in — Polaris's defining feature | Polaris (Mode 1 graduation) |
| RBAC + Helm + admin tooling | Roles + grants; community Helm chart; k8s Operator in development | 2-tier delegation + OPA; Apache-official Helm chart; bundled admin CLI + admin-tool JAR | Polaris (v0.5+ multi-tenant) |
| Beachhead laptop fit (16 GB w/ MinIO + Dagster + DuckDB) | Comfortable | Marginal — JVM heap competes | **Lakekeeper** |

**Decisive dimensions**: idle memory + cold-start. Worker H §8 (echoed Worker F §10): *"the single most decisive dimension is operational footprint on the user's laptop; ASF governance is procurement-sensitive — surface as a tooltip, not the headline."* ASF governance + built-in federation surface at customer-pilot time (Mo 20+), not first-touch onboarding. JVM-in-own-container exemption for Polaris per ADR-002 §6 (Polaris is in its own process, not inside `nucleus up`); Mo 24 founder gate (ADR-002 §8.3) can flip the documented default with no code change.

### What v0.3 ships

1. `pyiceberg.SqlCatalog` (v0.1) unchanged — supported indefinitely per v4.1 §5.7 / D14.
2. `pyiceberg.RestCatalog` → Lakekeeper default; compose adds `lakekeeper/lakekeeper:0.12.2` + `postgres:15-alpine` (Worker F §5.1).
3. `pyiceberg.RestCatalog` → Polaris alternate via `nucleus enable polaris`; compose adds `apache/polaris:apache-polaris-1.4.1` + admin-tool init container + `postgres:15-alpine` (Worker H §4.2 + §5.1).
4. `nucleus catalog migrate --from filesystem --to {lakekeeper|polaris}` per `nucleus_cli_spec.md` §4.2. **Metadata-only**: Iceberg data files in MinIO / SeaweedFS / S3 stay put; only `(namespace, table) → metadata_location` moves. Canonical v4.1 §10.1 Mode 1 primitive applied internally.
5. OIDC per Constraint #6 — both `external`-only; Polaris's internal `TokenBroker` explicitly disabled + `polaris.realm-context.require-header=true` (Worker H §5.2); Lakekeeper's `LAKEKEEPER__OPENID_AUDIENCE` set (Worker F §5.2).
6. Swap-drill: `docs/architecture/sequence_swap_drill.md` §4 happy-path extended to Lakekeeper↔Polaris; `docs/swap/lakekeeper.md` already in place; `docs/swap/polaris.md` companion authored in the v0.3 PR.

Per AGENTS.md §7: user-facing copy says **catalog** uniformly. Polaris's "metastore" (its persistence backend) and Lakekeeper's "warehouse" (its per-storage-profile partition) are upstream-internal terms the Asset Materialization Adapter abstracts. <!-- banned-term: metastore -->

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Lakekeeper less mature** — single-company governance (Worker F §9); pre-1.0 with breaking minors at 0.6.0 / 0.11.0 / 0.12.0 | Polaris path preserved; Mo 24 gate can flip documented default (ADR-002 §8.3); `SqlCatalog` indefinite fallback |
| **Polaris JVM blows laptop budget** for solo dev — 500 MB-1.5 GB heap (Worker H §6); Helm prod 8 GiB | Default is Lakekeeper; opt-in only; v0.3 compose tunes `JAVA_OPTS_APPEND="-Xms512m -Xmx1g"` (Worker H §12) |
| **Polaris `internal` token-issuance accidentally enabled** — Constraint #6 violation (Polaris CAN issue tokens; Lakekeeper NEVER does) | Polaris template hard-codes `polaris.authentication.<realm>.type=external` + `polaris.realm-context.require-header=true` (Worker H §5.2); CI lint rejects `internal` / `mixed` in shipped templates |
| **pyiceberg version skew** — post-ADR-003 0.11.x against Lakekeeper 0.12.x vs Polaris 1.4.x (Worker F §7 + Worker H §7) | `pyiceberg.RestCatalog` smoke-tested against both per swap-drill (`docs/architecture/sequence_swap_drill.md` §4); `docs/compatibility.md` tracks pinned tuples |
| **OIDC syntax differs per catalog** + **AI hallucinates clients** — `principal-roles-mapper` differs (Worker W §5.1); `LakekeeperClient` / `PolarisClient` / `PolarisError` / `RestCatalog.create_warehouse()` all fabricated (Worker F §9 + Worker H §10) | Per-provider recipes tested against Worker W's 4-provider matrix; the future OIDC v0.3 auth ADR (per Worker W §11 — number TBA; ADR-008 is already taken by the storage-substrate triage) lands alongside this ADR with a unified `[auth]` block; AI agents cite Worker F §9 / Worker H §10 before importing anything beyond `pyiceberg.RestCatalog` + `httpx`; log hallucinations per AGENTS.md §11.12 |

## Verification plan

1. **PoC #4 boot harness** gains `--catalog lakekeeper` (target `<10 s` w/ Postgres init + warehouse bootstrap, Worker F §5.1 + §6) and `--catalog polaris` (informational; expected `~15-25 s` JVM warm-up — empirically confirms laptop-fit thesis).
2. **PoC #3 ingest** runs against all three catalogs (filesystem `SqlCatalog`, Lakekeeper, Polaris); 7-case suite passes on all three. Config differs only by `uri` / `warehouse` / `scope` / `header.Polaris-Realm`.
3. **Error-translation contract** (`docs/research/pyiceberg.md` §6 + Worker F §5.5 + Worker H §5.6): trigger each row on real Lakekeeper 0.12.2 AND Polaris 1.4.1. Worker H §5.6: Polaris's `501` on `/oauth/tokens` in `external`-mode is a new case → `NucleusConfigError`.
4. **Swap drill** (`docs/architecture/sequence_swap_drill.md` §4): Lakekeeper↔Polaris is a named quarterly drill; first runs before v0.3 GA. Both implement the same `pyiceberg.Catalog` Protocol.
5. **`scripts/check_jvm_in_core_path.py`** (NV — author alongside `scripts/check_licenses.py` per ADR-007): verifies Polaris runs as a separate container, never embedded → preserves Constraint #1 exemption per ADR-002 §6.
6. **`docs/compatibility.md`**: add Lakekeeper 0.12.2 + Polaris 1.4.1 rows with `tested_with_pyiceberg=0.11.x` once ADR-003 lands.

## Rollback

If Lakekeeper proves unstable at v0.3 launch (breaking minor, single-vendor risk per Worker F §8, or PoC #4 measures Lakekeeper cold-start > Polaris's): **ADR-004a** flips documented default to Polaris (swap: `nucleus_config.toml` + recipe-doc copy); **ADR-004b** elevates `pyiceberg.SqlCatalog` as explicit "minimum viable v0.3" fallback. Filesystem catalog remains indefinite fallback per ADR-001 + v4.1 §5.7 / D14. No emergency rollback for license — both are GREEN per ADR-007.

## Docs URLs (cite at every call site per Constraint #10)

- **Lakekeeper**: https://docs.lakekeeper.io/docs/nightly/ (concepts / configuration / authentication / authorization / storage) • https://github.com/lakekeeper/lakekeeper • Helm: https://github.com/lakekeeper/lakekeeper-charts. *Per Worker F §3 — URLs missing `/docs/nightly/` prefix all 404.*
- **Apache Polaris**: https://polaris.apache.org/releases/1.4.1/ (getting-started / configuration / managing-security) • https://polaris.apache.org/in-dev/unreleased/ • https://github.com/apache/polaris • Helm: https://downloads.apache.org/polaris/helm-chart. *Per Worker H §3 — `/docs/...` and `/quickstart/` all 404; use `/releases/<version>/...`.*
- **Iceberg REST OpenAPI**: https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml.
- **pyiceberg `RestCatalog`**: https://py.iceberg.apache.org/configuration/#rest-catalog (Lakekeeper stanza + Polaris OAuth2 + `scope=PRINCIPAL_ROLE:ALL` inline).

## Trigger

Status flips **PROPOSED → ACCEPTED** when (1) founder signs off on Lakekeeper-default + Polaris-opt-in; (2) `nucleus_cli_spec.md` §4.2 `nucleus catalog migrate` surface confirmed (already drafted); (3) `docs/swap/polaris.md` companion authored.

**Not gated on PoC #1** — this governs v0.3 (Mo 14-20), well-deferred; ADR can ACCEPT immediately. **Is** sequentially gated on ADR-003 reaching ACCEPTED (both catalogs target REST OpenAPI spec coverage 0.11.x exposes). If founder review prefers Polaris-default (Mo 24 customer-pilot scenario), this ADR is amended in place per ADR-004a; the architecture is unchanged.

## Downstream consumers

| Consumer | When | How affected |
|---|---|---|
| `nucleus catalog migrate` CLI (`nucleus_cli_spec.md` §4.2) | v0.3 (Mo 14-20) | ADR-004 is its governing spec |
| PoC #4 boot harness (`poc/p4_boot_time/`) | Mo 8-12 | Adds `--catalog lakekeeper` / `--catalog polaris` modes per §Verification |
| PoC #3 ingest (`poc/p3_ingest/`) | Mo 4-8 | Runs against both REST catalogs alongside filesystem `SqlCatalog` |
| ADR-003 (pyiceberg 0.8.1 → 0.11.x) | Mo 2-3 | **Hard prerequisite** — both catalogs validated against 0.11.x |
| Future OIDC v0.3 auth ADR (number TBA — ADR-008 is already storage-substrate; per Worker W §11) | Mo 14-20 | Lands alongside this ADR; unified `[auth]` block feeds both catalogs |
| `docs/architecture/sequence_swap_drill.md` | Quarterly post-v0.3 | Lakekeeper↔Polaris named drill |
| Workbench (v0.2+) + `nucleus-mcp-server` (v0.5+, ADR-002 §4.2 P4) | Mo 8-28 | Catalog-aware UI + MCP ops work against either via `ctx` |

## Open questions for founder

1. **Confirm Lakekeeper as documented default?** Worker H §8 + Worker F §10 independently recommend this split; Mo 24 gate (ADR-002 §8.3) preserves option to flip if a customer-pilot demands ASF posture.
2. **`nucleus init --catalog polaris` first-class flag, or always `nucleus enable polaris` post-init?** Default position: **enable-only** — avoids two onboarding paths, keeps 30-min beachhead honest for the documented default.
3. **Ship "lakekeeper-lite" (Lakekeeper without Postgres)?** Default position: **no** — Worker F §6 confirms Postgres ≥ 15 only; `postgres:15-alpine` adds ~30-80 MB and matches production posture. Dev-identical-to-prod (a v4.1 §1.5 pillar) is more valuable than the saved megabytes.

## NEEDS VERIFICATION

1. **Exact pyiceberg API for catalog-to-catalog metadata migration.** Worker F §5.1 cites `pyiceberg-cli register-table` (separate CLI); Worker H §5.1 cites Polaris's `POST /api/catalog/v1/<prefix>/namespaces/<ns>/register`. **No documented `Catalog.migrate(from_catalog, to_catalog, namespaces=...)`** on `pyiceberg==0.8.1` (`docs/research/pyiceberg.md` §5). Whether post-ADR-003 `0.11.x` exposes one — verify against https://py.iceberg.apache.org/api/ at PR time. Fallback: per-table loop over `Catalog.list_namespaces` + `Catalog.list_tables` + `register_table(identifier, metadata_location)`.
2. **Polaris JVM heap on a 16 GB laptop with full Nucleus co-tenant** (MinIO + Dagster + DuckDB). Worker H §6 cites 500 MB-1.5 GB; PoC #4 must measure empirically — the lower bound assumes `JAVA_OPTS_APPEND="-Xms512m -Xmx1g"`, not Polaris defaults (`JAVA_MAX_MEM_RATIO=80` consumes ~3.2 GB on 4 GB limit per Worker H §10). Verify with full stack co-running before ACCEPT.
3. **Authentik OIDC compatibility for both catalogs.** Worker F §5.2 + Worker H §5.2 flag Authentik as "OIDC-compliant but not explicitly documented." Worker W §5 confirms OIDC discovery is uniform — likely "just works" but unverified. Smoke-test in the v0.3 OIDC PR (future OIDC ADR per Worker W §11).

---

*Consummates Worker F + Worker H research delivered 2026-05-13. Per AGENTS.md §11.13, no v0.3 catalog implementation begins until status flips to ACCEPTED **and** ADR-003 (pyiceberg upgrade) has landed. Full implementation — `nucleus catalog migrate`, compose templates, OIDC recipes — is sequentially gated; this ADR is the policy gate, not the work itself.*

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
