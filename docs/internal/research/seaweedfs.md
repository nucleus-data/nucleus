# Research: SeaweedFS 4.23 Bundled Iceberg REST Catalog

> **Status**: Pre-research probe. **NOT** an amendment to ADR-008 (storage) or ADR-004 (catalog ladder); both stand. Records empirical findings from a 60-min live smoke probe to test whether SeaweedFS 4.23's auto-started `Iceberg REST Catalog Server at http://0.0.0.0:8181` (same `chrislusf/seaweedfs:4.23` image used for storage per ADR-008) is functional enough to **collapse** the ladder — i.e., let `nucleus up` rely on a single SeaweedFS binary for both object storage AND atomic-commit catalog, removing v0.1's `pyiceberg.SqlCatalog` and v0.3+'s Lakekeeper/Polaris dep.
> **Verdict**: **YELLOW** — protocol-layer compliance is real and verified; pyiceberg E2E round-trip blocked on a fixable auth coupling. Existing ladder stands. Re-probe at v0.3 milestone.
> **Date**: 2026-05-13 · **Owner**: Solo founder
> **Tier (if adopted)**: Iceberg REST protocol = Tier 0 (immortal) per `docs/specs/nucleus_architecture_v4.1.md` §4.1; SeaweedFS server = Tier 1 implementation, swap target alongside Lakekeeper / Polaris.
> **Used in**: nowhere yet. Probe-only artifact.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before opening any future ADR amendment proposing to collapse the ADR-004 catalog ladder onto the SeaweedFS substrate.

---

## §1. What SeaweedFS 4.23's bundled Iceberg REST Catalog is

SeaweedFS 4.23 (release tag `4.23`, banner `30GB 4.23 73fc9e383`) is the same binary used as v0.1 storage substrate per ADR-008. From this release the binary auto-starts a **second HTTP listener** on `8181` (default; `-s3.port.iceberg` / `-port.iceberg`) implementing the [Apache Iceberg REST Catalog OpenAPI spec](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml). Implementation lives in `weed/s3api/iceberg/`, merged via [PR #8175](https://github.com/seaweedfs/seaweedfs/pull/8175) on top of the [PR #8147](https://github.com/seaweedfs/seaweedfs/pull/8147) S3 Tables foundation. Both are project-owner authored. Wiki pages [SeaweedFS Iceberg Catalog](https://github.com/seaweedfs/seaweedfs/wiki/SeaweedFS-Iceberg-Catalog) and [S3 Table Bucket](https://github.com/seaweedfs/seaweedfs/wiki/S3-Table-Bucket) (last edited 2026-05-04) document this as a **first-class feature** with explicit pyiceberg + DuckDB integration recipes.

Architecturally SeaweedFS positions this as **"lakehouse in a box"**: one binary collapses `engine → external catalog → object store` into `engine → SeaweedFS`. Catalog metadata and Iceberg metadata files live under `/table-buckets/<bucket>/<namespace>/<table>/` in the same Filer namespace; data writes go to the S3 endpoint at `8333`. **A "Catalog" maps 1:1 to a "Table Bucket"** — a special bucket type, distinct from a standard S3 bucket, that enforces strict Iceberg `metadata/` + `data/` layout. Empty URL prefix defaults to a table bucket named `warehouse`. Documented client integrations: PyIceberg, DuckDB, Spark, Trino, Dremio, Doris, RisingWave, Lakekeeper. Auth options: **SigV4** (Spark/Trino/RisingWave), **OAuth2** (DuckDB/Doris — `POST /v1/oauth/tokens` with S3 access key as `client_id`), **anonymous** (when started without IAM config). **OIDC delegation per Nucleus Hard Constraint #6 is not natively supported.**

---

## §2. Iceberg REST spec compliance — observed endpoint behavior

Probe against `chrislusf/seaweedfs:4.23` started via `wsl -e docker run -d --name p-seaweed-rest -p 9000:8333 -p 8181:8181 chrislusf/seaweedfs:4.23 mini -s3.port=9000`. All curl probes used `--noproxy "*"`.

| HTTP call | Status | Body |
|---|---|---|
| `GET /v1/config` | `200` | `{"defaults":{},"overrides":{}}` — canonical Iceberg REST `ConfigResponse` |
| `GET /v1/namespaces` (no warehouse) | `500` | `{"error":{"message":"...table bucket warehouse not found",...}}` |
| `POST {S3-endpoint}/` `X-Amz-Target: S3Tables.CreateTableBucket` body `{"name":"warehouse"}` | `200` | `{"arn":"arn:aws:s3tables:us-east-1:000000000000:bucket/warehouse"}` |
| `GET /v1/namespaces` (after) | `200` | `{"namespaces":[]}` |
| `POST /v1/namespaces` body `{"namespace":["nucleus_probe"]}` | `200` | `{"namespace":["nucleus_probe"],"properties":{"location":"s3://warehouse/nucleus_probe"}}` |
| `GET /v1/namespaces` | `200` | `{"namespaces":[["nucleus_probe"]]}` |
| `GET /v1/namespaces/nucleus_probe` | `200` | full `GetNamespaceResponse` |
| `HEAD /v1/namespaces/nucleus_probe` | `204` | per spec |
| `GET /v1/namespaces/nucleus_probe/tables` | `200` | `{"identifiers":[]}` |
| `POST .../tables` body `{"name":"smoke","schema":{...long+string...}}` | `200` | full `LoadTableResponse` w/ `format-version: 2`, `metadata-location`, table-uuid, schemas/specs/sort-orders |
| `GET .../tables` (after) | `200` | `{"identifiers":[{"namespace":["nucleus_probe"],"name":"smoke"}]}` |
| `GET .../tables/smoke` | `200` | identical metadata round-trip |

Errors use the `{"error":{"message","type","code"}}` envelope with proper Iceberg exception names (`NoSuchNamespaceException`, `BadRequestException`, `ForbiddenException`, `InternalServerError`). Per-protocol Iceberg REST namespace + table CRUD is **real and spec-compliant**.

---

## §3. Feature parity matrix vs. the PoC #3 baseline

PoC #3 baseline = `pyiceberg.SqlCatalog` per `docs/specs/nucleus_architecture_v4.1.md` §5.7 + Amendment 4. It validated `create_namespace → create_table → append → scan` E2E successfully.

| Capability | `SqlCatalog` (PoC #3 baseline) | SeaweedFS 4.23 REST (this probe) |
|---|---|---|
| `GET /v1/config` | n/a | ✅ |
| List / create / HEAD / drop namespace | ✅ | ✅ all four verified |
| List / create / load / drop table (catalog ops only) | ✅ | ✅ verified raw REST + pyiceberg |
| Atomic commit (single-table) | ✅ (SQLite txn) | ✅ optimistic-locking via `VersionToken` per [PR #8175](https://github.com/seaweedfs/seaweedfs/pull/8175); not concurrency-stressed |
| **`tbl.append()` (data write)** | ✅ | ❌ blocked at S3 multipart auth — see §4.2 |
| Schema evolution | (untested in PoC #3) | (untested) |
| Snapshot expiration | n/a in `pyiceberg==0.8.1` | documented via [Iceberg-Table-Maintenance wiki](https://github.com/seaweedfs/seaweedfs/wiki/Iceberg-Table-Maintenance), **NEEDS VERIFICATION** |
| Auth: anonymous | n/a | ✅ on REST; ❌ for S3 multipart writes |
| Auth: SigV4 | n/a | ✅ native on both endpoints |
| Auth: OAuth2 | n/a | ✅ via `/v1/oauth/tokens`; pyiceberg interop **NEEDS VERIFICATION** |
| Auth: OIDC (Constraint #6) | n/a | ❌ no native — must front with Lakekeeper / sidecar |

---

## §4. Live pyiceberg smoke test — first-failure analysis

Probe script in scratch (`.scratch/seaweed_probe.py`, deleted after run). Cited [pyiceberg 0.8.1 docs](https://py.iceberg.apache.org/api/) + [pyiceberg REST configuration](https://py.iceberg.apache.org/configuration/#rest-catalog).

### §4.1 Anonymous mode (no `AWS_ACCESS_KEY_ID` on container)

| Step | Result |
|---|---|
| A: `from pyiceberg.catalog.rest import RestCatalog` | **PASS** |
| B: instantiate `RestCatalog(uri=":8181", warehouse="s3://warehouse/", s3.endpoint=":9000", s3.access-key-id=any, s3.secret-access-key=any, s3.path-style-access=true)` | **PASS** |
| C: `cat.list_namespaces()` | **PASS** — `[('nucleus_probe',)]` |
| D: `cat.create_namespace("pyiceberg_probe")` | **PASS** |
| E: `cat.create_table(("pyiceberg_probe","smoke"), schema=...)` | **PASS** |
| **F: `tbl.append(arrow_batch_3_rows)`** | **FAIL** — `OSError: ... AWS Error NETWORK_CONNECTION during CreateMultipartUpload operation` |
| G: `cat.load_table(...).scan().to_arrow()` | PASS (empty — no commit) |
| H: snapshot count | PASS (`0`) |
| I-J: `drop_table` + `drop_namespace` | **PASS** — REST `DELETE` honored |

**First-failure isolation**: a direct `curl -X POST http://localhost:9000/probe-data/file.txt?uploads` returns `403 AccessDenied`. SeaweedFS denies **all** unsigned multipart-upload-init requests, even when the catalog accepts the table create. `pyarrow.fs.S3FileSystem.open_output_stream` always uses multipart (verified for a 13-byte test write), so the failure is structural, not size-related. **First-failure citation: S3-endpoint authorization model, not Iceberg REST protocol.**

### §4.2 IAM mode (container started with `-e AWS_ACCESS_KEY_ID=miniadmin -e AWS_SECRET_ACCESS_KEY=miniadmin`)

SeaweedFS log: `auth_credentials.go:412 Added admin identity from AWS environment variables: name=admin-miniadmi, accessKey=miniadmin`. With IAM enabled the **REST catalog also requires authentication**:

- `cat.list_namespaces()` against `/v1/warehouse/namespaces` → **`403 Forbidden`** from pyiceberg's unsigned `requests.Session`.
- Per [pyiceberg config §SigV4](https://py.iceberg.apache.org/configuration/#rest-catalog), `rest.sigv4-enabled=true` enables SigV4 — but the implementation imports `boto3` lazily, and `boto3` is **not** in `pyproject.toml` (verified via `python -c "import boto3"` → `ModuleNotFoundError`). Per probe constraints, no `pip install` was done.

**Auth conclusion** — two operating modes mutually exclusive for pyiceberg-out-of-the-box:
- Anonymous: REST works, S3 data writes blocked.
- IAM: both endpoints require SigV4, pyiceberg can sign IF `boto3` is added.

A third path (OAuth2 against `/v1/oauth/tokens` with S3-key-as-credentials) is documented for DuckDB/Doris but pyiceberg's OAuth2 helper is for token exchange against a generic OAuth provider. Manual `token=<bearer>` config + pre-fetch may interop — **NEEDS VERIFICATION**.

---

## §5. Comparison to the ADR-008 / ADR-004 ladder

ADR-008 already nominates `chrislusf/seaweedfs:4.23` as the documentation-default storage substrate for v0.1 (Apache-2.0, actively maintained). Adding the bundled REST catalog on top would be **architecturally consistent** — same binary, same docker-compose service, no second container. ADR-004 defines the v0.3+ catalog ladder as Lakekeeper-vs-Polaris, both behind `pyiceberg.RestCatalog`. v0.1 stays on `pyiceberg.SqlCatalog` per `docs/specs/nucleus_architecture_v4.1.md` §5.7 + Amendment 4.

**Could SeaweedFS REST collapse the ladder?**

- **For**: one Apache-2.0 binary already in the v0.1 storage layer → catalog "for free", no second service. Aligns with v4.1 Pillar #1 (high perf on minimal resources) + Pillar #4 (familiar UX — Iceberg REST is the same client surface Lakekeeper/Polaris expose).
- **Against (decisive 2026-05-13)**:
  1. **Pyiceberg E2E does not work without modification**: add `boto3` (Constraint #11 PR + ADR + smoke test) + accept SigV4, OR ask SeaweedFS for anonymous-S3-multipart dev mode (upstream feature request, no SLA), OR engineer an OAuth2 token-broker. None is zero-cost.
  2. **Auth-model gap vs. Hard Constraint #6** ("No custom auth system; always delegate to OIDC"). SeaweedFS auth is SigV4 + OAuth2 (S3-key-as-client-credential). Lakekeeper + Polaris natively integrate OIDC providers. Collapsing onto SeaweedFS REST regresses the auth story for v0.3+ shared-team use cases that are exactly the trigger to graduate from `SqlCatalog`. **For Cloud / multi-engineer deployments, an OIDC-fronted catalog is required; SeaweedFS REST would have to sit BEHIND Lakekeeper, not REPLACE it.**
  3. **Maturity**: PR #8175 merged ~2026-04-25; release `4.23` is the first carrying it. Wiki updated 2026-05-04 (9 days before this probe). Schema evolution, snapshot-expiration semantics, concurrent-commit conflict behavior, admin-UI/CLI ergonomics are **untested** here. The Iceberg-Table-Maintenance wiki page exists; the surface (Compaction / SnapshotExpiration / OrphanRemoval / ManifestRewrite) was not exercised.
  4. **PoC #3 already validated `SqlCatalog`** end-to-end. Replacing it now adds risk for zero v0.1 user-visible benefit (v0.1 beachhead is single-laptop, single-engineer; SqlCatalog is in-process and zero-deps).

**Net**: ADR-004 ladder is correct as-stated. SeaweedFS REST is a *plausible third option on the v0.3+ ladder* and merits follow-up evaluation, but it does **not** collapse the existing structure.

---

## §6. Open questions & risks

1. **OIDC delegation gap.** SeaweedFS REST does not natively delegate to OIDC (wiki shows static creds + S3 bucket policies). For Cloud + multi-team v0.3+ this is a Constraint #6 concern unless fronted with Lakekeeper or a sidecar OIDC↔SigV4 bridge.
2. **Anonymous-mode S3 write block.** SeaweedFS denies unsigned multipart-upload init even when the catalog accepts unsigned requests. Biggest barrier to "drop-in v0.1 default catalog" — investigate whether `weed mini -s3.allowAnonymousWrite` (or equivalent) exists. None surfaced in this probe.
3. **`boto3` dependency cost.** Adding `boto3` to `pyproject.toml` brings `botocore` (~6 MB) + transitives. Per Constraint #11 = one-PR ADR-required change. Counter: many users get `boto3` transitively via `pyiceberg[s3fs]` or `dlt`. **NEEDS VERIFICATION** — check transitive resolution.
4. **Concurrency / atomic-commit stress.** PR #8175 mentions `VersionToken` optimistic locking; not stressed here. Lakekeeper's `iceberg-rust` commit path is well-understood; SeaweedFS's commit path is new code from Q1-Q2 2026.
5. **Backup / DR.** SeaweedFS Filer + Volume backup is documented; combining catalog state + data files in one substrate = one backup target (good) but also one recovery scope (bad if corruption straddles both).
6. **Vendor governance.** Single-maintainer (chrislusf); mitigated by Apache-2.0 + active community but worth noting against ADR-004 alternatives that have organizational governance (Polaris = ASF, Lakekeeper = Vakamo company-backed).
7. **Vocabulary.** SeaweedFS docs use "table", "catalog", "metastore" freely. <!-- banned-term: metastore --> Nucleus copy continues to use **asset / materialization / snapshot / catalog** per AGENTS.md §7 even when wrapping SeaweedFS REST.

---

## §7. NEEDS VERIFICATION items (from this 60-min probe)

- [ ] `weed mini` / `weed s3` flag to allow anonymous S3 multipart writes (would unblock pyiceberg anonymous E2E)
- [ ] Pyiceberg OAuth2 against `POST /v1/oauth/tokens` with S3-key-as-client-credentials — does pyiceberg's OAuth2 helper or manual `token=` config interop?
- [ ] Whether `boto3` is already pulled transitively by current pinned deps (`pyiceberg[s3fs]==0.8.1`, others)
- [ ] Snapshot expiration / orphan removal via [Iceberg Table Maintenance wiki](https://github.com/seaweedfs/seaweedfs/wiki/Iceberg-Table-Maintenance) — does it work, how is it scheduled?
- [ ] Schema evolution (`UpdateTable` REST endpoint) — accept / reject behavior on add-column / promote-type
- [ ] Concurrent-commit conflict — two clients targeting the same table via `VersionToken`
- [ ] Admin-UI port (default `23646` per `mini.go:671`) — operability surface for namespaces/tables (not exposed in this probe; `weed shell s3tables.bucket -create` from inside the container hung in non-TTY stdin mode, indicating shell ergonomics need work)
- [ ] License headers on `weed/s3api/iceberg/*.go` and `weed/s3api/s3tables/*.go` confirm Apache-2.0 (overall project is Apache-2.0; per-file SPDX header check deferred)

---

## §8. Verdict & recommendation

**YELLOW — incremental win, not collapse.**

- **Iceberg REST protocol layer**: GREEN. Spec-compliant envelopes (CreateNamespaceResponse, LoadTableResponse with `format-version: 2`), proper exception types (`NoSuchNamespaceException`, `ForbiddenException`), HEAD returns 204. PyIceberg `RestCatalog.{list,create,load,drop}_namespace` and `.{create,load,drop}_table` all PASS against it.
- **Pyiceberg E2E round-trip**: RED at `tbl.append()`. Blocked at S3 multipart-upload init, downstream of any catalog protocol issue. Requires either anonymous-S3-write upstream feature, `boto3` + SigV4, or OAuth2 broker. None is in scope for the 30-min probe.
- **Auth fit for Constraint #6 (OIDC)**: RED native; GREEN if fronted by Lakekeeper.
- **Maturity vs. PoC #3 baseline**: yellow. Catalog code is ~3 months old, no 1.0 stamp, no community CVE/patch history yet.

**Recommendation**:
1. **No ADR amendment now.** ADR-008 (storage = SeaweedFS) and ADR-004 (catalog ladder = Lakekeeper-vs-Polaris) **stand unchanged**. v0.1 continues with `pyiceberg.SqlCatalog` per `docs/specs/nucleus_architecture_v4.1.md` §5.7 + Amendment 4.
2. **Re-probe at v0.3 readiness gate.** Allocate 2-4 hours: install `boto3` in a scratch venv, validate full SigV4 E2E, stress concurrent commits, exercise schema evolution + Iceberg-Table-Maintenance ops. If GREEN, open follow-up ADR amendment proposing **SeaweedFS REST as a third v0.3+ catalog option** alongside Lakekeeper and Polaris — NOT as a collapse of the ladder.
3. **One-line ADR-008 / ADR-004 amendment trigger**: **No / defer.** Probe surfaced no information that invalidates either ADR.

---

## §9. Citations

- Iceberg REST OpenAPI — https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml
- SeaweedFS 4.23 — https://github.com/seaweedfs/seaweedfs/releases/tag/4.23
- SeaweedFS wiki: [Iceberg Catalog](https://github.com/seaweedfs/seaweedfs/wiki/SeaweedFS-Iceberg-Catalog) · [S3 Table Bucket](https://github.com/seaweedfs/seaweedfs/wiki/S3-Table-Bucket) · [Bucket Commands](https://github.com/seaweedfs/seaweedfs/wiki/S3-Table-Bucket-Commands) · [Iceberg Table Maintenance](https://github.com/seaweedfs/seaweedfs/wiki/Iceberg-Table-Maintenance)
- PRs: [#8175 (Iceberg REST + admin UI)](https://github.com/seaweedfs/seaweedfs/pull/8175) · [#8147 (S3 Tables)](https://github.com/seaweedfs/seaweedfs/pull/8147)
- pyiceberg 0.8.1: [API](https://py.iceberg.apache.org/api/) · [REST configuration](https://py.iceberg.apache.org/configuration/#rest-catalog)
- Existing Nucleus research: `docs/internal/research/lakekeeper.md`, `docs/internal/research/polaris.md`, `docs/internal/research/minio.md`
