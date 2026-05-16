# MinIO Research — Local S3 Storage Substrate

> **Status**: **ALTERNATE substrate per [ADR-008](../../decisions/ADR-008-storage-substrate-v01.md) (dual-track docker-compose).** SeaweedFS is now the documentation default (`docker-compose.yml`, Apache-2.0, actively maintained — release 2025-05-04); MinIO preserved as opt-in alternate via `docker-compose.minio.yml` for teams with existing MinIO tooling. Supply-chain context retained below: `github.com/minio/minio` (OSS server) was **archived 2026-04-25**; last release `RELEASE.2025-09-07T16-13-09Z` (2025-10-15). MinIO Inc. publicly labels OSS MinIO **"unmaintained"** ([blog](https://blog.min.io/blog/minio-aistor-vs-minio-oss-technical-comparison): *"13,000+ commits separating AIStor from unmaintained OSS"*). ADR-008 resolved the AGENTS.md §9 Stop Condition this research originally triggered; this file remains the archived-substrate reference for the alternate compose template.
> **Date**: 2026-05-13 · **Owner**: Solo founder
> **Tier**: **S3 API = Tier 0** (immortal) per `docs/specs/nucleus_architecture_v4.1.md` §3.1 + §4.1 + §5.8; **MinIO server = Tier 1 implementation** (swappable per Constraint #9).
> **Wrapping mode**: ZERO Python import in the hot path. Nucleus does NOT `import minio`. It speaks the S3 API via `pyiceberg`'s `PyArrowFileIO` and `s3fs` (transitive via `pyiceberg[s3fs]==0.8.1`). The MinIO **server** is a runtime dependency (docker container or single binary), not a Python pin.
> **Used in**: PoC #1 (Iceberg writes → S3-API buckets) · PoC #3 (`poc/p3_ingest/ingest.py`) · PoC #4 (`poc/p4_boot_time/measure.py` pings `/minio/health/live`) · PoC #5 beachhead.

Official-docs anchor per AGENTS.md Hard Constraint #10. Read before any `nucleus up` / docker-compose work and **before** opening the pre-v0.1 storage-substrate ADR (§3.3 + §10).

---

## §1. What MinIO is, in Nucleus terms

MinIO is a Go-implemented, single-binary, S3-API-compatible object store. Two artefacts are distinct: (a) the **OSS server** (`github.com/minio/minio`, AGPLv3, **archived 2026-04-25**) — the only one Nucleus may deploy without commercial licensing — and (b) the **Python SDK** (`minio` on PyPI, Apache-2.0), which **Nucleus does not import in v0.1** (pyiceberg + s3fs already speak S3). The commercial **MinIO AIStor** (proprietary [MinIO Software License](https://docs.min.io/license/), evaluation-only without an Enterprise Agreement) is **out of scope**. MinIO occupies the v4.1 §5.8 object-store slot, speaking the v4.1 §4.1 Tier 0 S3 protocol ("Universal: MinIO, SeaweedFS, R2, GCS, Azure"). Nucleus uses a local S3-API server for **local-identical-to-prod** (v4.1 §1.5, Pillar #5): the same byte path runs in PoC #1 / PoC #3 / PoC #5 as in production AWS S3. Mode 1 graduation (v4.1 §10.1) is a 3-line config swap — `s3.endpoint`, `s3.access-key-id`, `s3.secret-access-key`. MinIO is the *current* OSS implementation, not the *protocol* — a distinction that is decisive when the implementation goes dark (see §3).

---

## §2. Pin candidates + verification (2026-05-13)

### §2.1 Server (runtime dependency, not a Python pin)

| Field | Value | Verification |
|---|---|---|
| Last OSS release | `RELEASE.2025-09-07T16-13-09Z` (2025-09-07) | <https://github.com/minio/minio/releases> — banner: *"This repository was archived by the owner on Apr 25, 2026."* |
| Container image | `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` (~56 MB) | <https://hub.docker.com/r/minio/minio> shows "Archived · Updated 8 months ago". Quay mirror still serves images. |
| License | **GNU AGPLv3** | `raw.githubusercontent.com/minio/minio/master/LICENSE` verified 2026-05-13. Distinct from AIStor's proprietary license. |
| Build | Go 1.24.x | Satisfies Hard Constraint #1 (no JVM). |
| Default creds | `minioadmin` / `minioadmin` | Local dev only; never production. |
| Ports | `9000` (S3 API), `9001` (Console UI) | Per Docker Hub readme. |

**Pin reality**: ~7 months stale at 2026-05-13. No upstream security patches will follow. New CVEs accumulate against this frozen binary from this date forward.

### §2.2 Python pins (none required in the v0.1 hot path)

| Package | PyPI (2026-05-13) | License | Verdict |
|---|---|---|---|
| `minio` | **7.2.20** (uploaded 2025-11-27, `requires_python>=3.9`) | Apache-2.0 | **DO NOT pin in `dependencies`.** Adds 4 transitive runtime pins (`argon2-cffi`, `certifi`, `pycryptodome`, `urllib3`) for zero v0.1 hot-path value. Defer to v0.3+ if/when admin operations need a Python helper. |
| `s3fs` | **2026.4.0** (uploaded 2026-04-29, `requires_python>=3.10`, deps: `aiobotocore<4,>=2.19`, `fsspec==2026.4.0`, `aiohttp>=3.9`) | BSD-3-Clause | **Already transitive** via `pyiceberg[s3fs]==0.8.1` (`pyproject.toml` L47). Do not pin separately. |
| `boto3` | Latest on PyPI (weekly cadence; 2026-04-29 release dropped Py 3.9) | Apache-2.0 | **Not currently pinned.** Add only if v0.1 needs admin operations pyiceberg's FileIO cannot satisfy. Prefer `mc` CLI in a docker-compose init container. |

**Architectural decision**: prefer `pyiceberg` + `s3fs` (transitive) for ALL hot-path I/O. `minio`-py is opt-in admin only, deferred. <!-- banned-term: none -->

---

## §3. License + supply-chain risk (read carefully)

Two distinct risks; AI agents reading older MinIO material commonly conflate them.

### §3.1 AGPLv3 (secondary concern; still real for Cloud)

| Scenario | Obligation on Nucleus | Verdict |
|---|---|---|
| OSS docs say `docker run quay.io/minio/minio:...` and user self-deploys | None (Nucleus distributes nothing) | **SAFE** |
| Nucleus OSS docker-compose template references the image | YAML reference, not a modified binary; pull is client-side | **SAFE** |
| Nucleus Cloud bundles a MinIO binary into the control plane | AGPLv3 §13 forces source release of the entire surrounding service | **REJECT** |
| Nucleus Cloud offers managed-MinIO SaaS | Same §13 reasoning | **REJECT** |
| Nucleus forks + redistributes a modified MinIO | Full AGPLv3 obligation on the redistributor | **REJECT** |

For the v0.1 OSS user-runs-on-laptop story, AGPLv3 imposes **zero obligation** on Nucleus. We're a consumer, not a distributor — same posture as `docker run postgres:15-alpine`.

### §3.2 Upstream death (PRIMARY concern as of 2026-05-13)

- **2026-04-25**: repository archived by owner. Read-only. No PRs, no issues, no releases.
- **2025-09-07**: final OSS release `RELEASE.2025-09-07T16-13-09Z` (with [GHSA-jjjj-jwhf-8rgr](https://github.com/minio/minio/security/advisories/GHSA-jjjj-jwhf-8rgr) — "Privilege Escalation via Session Policy Bypass"). The release wording was *"All users are advised to download and upgrade their MinIO setup immediately."* That was the **final** advisory.
- **Vendor position**: OSS MinIO labelled "unmaintained" in current marketing; AIStor is the commercial successor.
- **Future CVEs**: Will not receive patches. Filed-after-2026-04-26 CVEs are permanently open unless the user forks-and-patches or migrates.

This triggers **AGENTS.md §9 Stop Condition** explicitly: *"A major upstream OSS we wrap breaks compatibility, hostile licenses, or dies."* MinIO didn't die-die, but the upstream is permanently offline and the vendor explicitly deprecates the OSS edition.

### §3.3 Combined verdict + pre-v0.1 action

- v0.1 OSS users on laptop: legally **SAFE**, operationally **STALE** (CVE exposure grows monthly).
- Nucleus Cloud: AGPLv3 + upstream death — **never route Cloud through MinIO**. Use AWS S3 / R2 / GCS direct, or self-host SeaweedFS (Apache-2.0).
- v0.1 storage default: **`docs/decisions/ADR-NNN-storage-substrate-v01.md` REQUIRED before v0.1 ships.** Options:
  1. Ship archived `RELEASE.2025-09-07T16-13-09Z` with documented sunset milestone.
  2. Skip MinIO entirely; ship SeaweedFS as v0.1 default.
  3. **Dual-track templates** — MinIO compose for familiarity; SeaweedFS compose for safety. SeaweedFS as the documentation default. **Recommended.**

---

## §4. Architecture integration points

### §4.1 PoC #4 boot harness (`poc/p4_boot_time/measure.py`)

```python
DEFAULT_MINIO_HEALTH_URL = "http://localhost:9000/minio/health/live"
PHASE_TARGETS = {..., "minio_health": 0.5, ...}
```

Per [Healthcheck Probes docs](https://docs.min.io/community/minio-object-store/operations/monitoring/healthcheck-probe.html) (verified 2026-05-13):

| HTTP | Meaning | Action |
|---|---|---|
| `200 OK` | Healthy | Phase pass |
| `429 Too Many Requests` | Thread/queue pressure (not laptop-relevant) | Healthy-but-stressed |
| `503 Service Unavailable` | Cluster health unverifiable | Unhealthy |
| Connection refused | Container not started | Unhealthy |

`measure_minio_health()` currently accepts `200` **and** `403`. **`403` is not in the documented response set** — NEEDS VERIFICATION whether older MinIOs returned it. Safe set going forward: `{200, 429}`. PoC #4 work item: tighten and let `403` fall through. Cold-start budget is the 0.5 s phase target inside the overall `nucleus up <10s` goal (v4.1 §6.3); Docker Desktop on Windows adds ~1-3 s container overhead above the binary — NEEDS VERIFICATION on the founder's machine.

### §4.2 PoC #1 + PoC #3 (Iceberg writes against MinIO)

Per [pyiceberg Configuration §FileIO §S3](https://py.iceberg.apache.org/configuration/#s3) (verified 2026-05-13):

```python
# Docs: https://py.iceberg.apache.org/configuration/#s3
from pyiceberg.catalog import load_catalog
catalog = load_catalog("nucleus", **{
    "type": "sql",
    "uri": f"sqlite:///{warehouse}/catalog.db",
    "warehouse": "s3://nucleus-warehouse/",
    "s3.endpoint": "http://localhost:9000",
    "s3.access-key-id": "minioadmin",
    "s3.secret-access-key": "minioadmin",   # local dev only
    "s3.region": "us-east-1",               # MinIO ignores; PyArrow requires
})
```

`s3.force-virtual-addressing` defaults to `False` (path-style addressing), which is what MinIO wants — leave it alone. Bucket layout (NEEDS VERIFICATION against final project anatomy): `nucleus-warehouse/` (Iceberg metadata + manifests) and `nucleus-data/` (Parquet) OR single `nucleus/` with prefixes. Single-bucket halves the bucket-cap pressure post-graduation to AWS S3.

### §4.3 PoC #5 beachhead + production graduation

Compose pin: `image: quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`, ports `9000` (S3) + `9001` (Console), env `MINIO_ROOT_USER/PASSWORD`, healthcheck on `/minio/health/live` (5 s × 6 retries). First-boot bucket-create via an `mc` sidecar: `mc alias set local http://minio:9000 minioadmin minioadmin && mc mb -p local/nucleus-warehouse`. The 56 MB pull fits the 30-min beachhead budget on a 50 Mbps connection. **Mode 1 graduation** (v4.1 §1.6, ADR-002 §8.1): 3-line swap of `s3.endpoint` + access-key + secret-key → AWS S3 / GCS / Azure / R2 / B2 / Wasabi / SeaweedFS. Iceberg metadata is byte-identical regardless of backend. Zero data movement, zero Nucleus code change.

---

## §5. APIs Nucleus actually uses

| Operation | Nucleus caller | Wire call | Verified |
|---|---|---|---|
| Liveness probe | `poc/p4_boot_time/measure.py` | `GET /minio/health/live` → `{200,429,503}` | ✓ §4.1 docs |
| Bucket create (first boot) | `mc` CLI in compose init OR `boto3.client("s3", endpoint_url=...).create_bucket(...)` | S3 `PUT /<bucket>` | ✓ S3 standard |
| Object PUT (Iceberg metadata, Parquet) | `pyiceberg.io.pyarrow.PyArrowFileIO` | S3 `PUT /<bucket>/<key>` | ✓ pyiceberg `FileIO` |
| Multipart upload (large Parquet) | `pyiceberg` + PyArrow chunk defaults | S3 multipart spec | NEEDS VERIFICATION (chunk threshold across pyiceberg 0.8.1 / PyArrow 18.1.0 / MinIO) |
| Object GET (`iceberg_scan`, Polars scan) | DuckDB `httpfs` + pyiceberg | S3 `GET /<bucket>/<key>` w/ Range | ✓ DuckDB docs |
| LIST (snapshot enumeration) | pyiceberg metadata scan | S3 `GET /<bucket>?list-type=2&prefix=...` | ✓ ListObjectsV2 |
| Signature | All calls above | AWS sigv4 (`X-Amz-Date`) | ✓ MinIO supports sigv4 default |

**Critical for DuckDB `httpfs` against MinIO** (per [duckdb.org S3 API support](https://duckdb.org/docs/current/core_extensions/httpfs/s3api.html)):

```sql
CREATE OR REPLACE SECRET minio_local (
    TYPE s3, KEY_ID 'minioadmin', SECRET 'minioadmin',
    ENDPOINT 'localhost:9000', URL_STYLE 'path', USE_SSL false
);
```

`URL_STYLE 'path'` and `USE_SSL false` are non-default; AI agents tend to omit them and emit 403 / DNS-lookup errors against MinIO. Pin these in the v0.1 secret template.

---

## §6. Known AI hallucinations to watch (per AGENTS.md §11.12)

Log new occurrences to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).

- ❌ `minio.Minio.upload_to_iceberg(...)` — does NOT exist. Iceberg writes route through `pyiceberg.Table.append()`, never the MinIO SDK.
- ❌ `from minio.fs import S3FileSystem` — does NOT exist. The class is `s3fs.S3FileSystem` (BSD-3-Clause).
- ❌ `pyiceberg.SqlCatalog(..., "s3.endpoint_url": "...")` — wrong key. pyiceberg uses dot-keyed `"s3.endpoint"` (no `_url`). `endpoint_url` is the **boto3** kwarg; pyiceberg's FileIO does not accept boto3 kwargs directly.
- ❌ `pyiceberg.SqlCatalog(..., "s3.url-style": "path")` — does NOT exist. pyiceberg/PyArrow controls URL style via `s3.force-virtual-addressing` (default `False` = path-style — correct for MinIO). Setting `True` breaks MinIO.
- ❌ DuckDB `CREATE SECRET (..., USE_SSL true)` against `http://localhost:9000` — wrong; MinIO local dev is HTTP. Must be `USE_SSL false`.
- ❌ `MinIOCatalog`, `MinIOError`, `from pyiceberg.minio import ...` — none exist. Iceberg has no per-vendor catalog class for MinIO. Use `pyiceberg.SqlCatalog` (v0.1) or `RestCatalog` (v0.3+) with S3 FileIO config.
- ❌ "Use `quay.io/minio/aistor:latest` in v0.1 compose" — AIStor is commercial / evaluation-only. Use `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`.
- ❌ "OSS MinIO ships an Iceberg catalog" — false. AIStor advertises "Iceberg V3 / Tables"; OSS does not. Catalog lives in pyiceberg in v0.1, Lakekeeper / Polaris in v0.3+.
- ❌ Suggesting `boto3>=1.40` (or any specific pin) from training memory — verify on PyPI before adding.

---

## §7. Performance + footprint

Cited from [Docker Hub readme](https://hub.docker.com/r/minio/minio) + [Healthcheck Probes docs](https://docs.min.io/community/minio-object-store/operations/monitoring/healthcheck-probe.html). **Not yet benchmarked under PoC #4** — re-measure.

- **Cold-start**: <500 ms single binary on Linux/macOS; +1-3 s on Docker Desktop (Windows / macOS WSL2). Phase budget 0.5 s for the post-up health check. NEEDS VERIFICATION on Windows + Docker Desktop.
- **Idle RAM**: ~80-150 MB binary, ~200-280 MB with Docker overhead. Comparable to Lakekeeper's 100-300 MB ([`lakekeeper.md`](./lakekeeper.md) §6); ~5-10× lighter than Polaris's JVM heap ([`polaris.md`](./polaris.md) §6).
- **Image size**: 56.6 MB (`RELEASE.2025-09-07T16-13-09Z-cpuv1` per Docker Hub).
- **Disk**: linear scaling; metadata overhead small. Single-binary / single-drive is fine for v0.1 (no erasure coding).
- **Concurrency**: Go-routine based, scales to laptop cores without tuning. 429 thread-pressure (per §4.1) is a production-cluster concern, not v0.1.

---

## §8. Compatibility matrix (verify in PoC #1 + #3 + #4)

| Component | Pinned | MinIO config | Status |
|---|---|---|---|
| `pyiceberg` | `0.8.1` (`pyiceberg[sql-sqlite,s3fs,duckdb]==0.8.1`) | `s3.endpoint`, `s3.access-key-id`, `s3.secret-access-key`, `s3.region` | NEEDS VERIFICATION (PoC #1 write + scan). |
| `pyiceberg` post-ADR-003 | `0.11.x` queued | Same S3 keys expected stable | NEEDS VERIFICATION on upgrade. |
| `s3fs` | `2026.4.0` (transitive) | `endpoint_url`, `key`, `secret` kwargs | NEEDS VERIFICATION (smoke test). |
| `boto3` | unpinned | `client("s3", endpoint_url=...)` | NEEDS VERIFICATION — pin only if v0.1 admin path requires. |
| `duckdb` | `1.1.3` | `CREATE SECRET (...URL_STYLE 'path', USE_SSL false)` | NEEDS VERIFICATION (PoC #1 `iceberg_scan`). |
| `polars` | `1.18.0` | reads `s3://` via PyArrow `S3FileSystem` (transitive) | NEEDS VERIFICATION for exact `endpoint_url` kwarg path. |
| MinIO server | `RELEASE.2025-09-07T16-13-09Z` (last OSS) | All of above end-to-end | NEEDS VERIFICATION on Windows + Docker Desktop. |

---

## §9. Swap targets (revised priority — v4.1 §9.3)

S3 API is Tier 0 immortal (v4.1 §4.1); the implementation is swappable. Given §3.2 upstream death, the priority order is:

| # | Target | License | Status (2026-05-13) | When |
|---|---|---|---|---|
| 1 | **SeaweedFS** | **Apache-2.0** (verified) | Active — release 2025-05-04; ~32 k stars; native Iceberg catalog; single Go binary | **Promoted v0.3 → v0.1 candidate.** Likely v0.1 default per §3.3 ADR. |
| 2 | AWS S3 | Commercial AWS | Production graduation; same S3 API | v0.1 user opt-in via config; Cloud default |
| 3 | Cloudflare R2 / Backblaze B2 / Wasabi | Commercial | Same S3 API + cheaper egress | Mode 1 graduation |
| 4 | Garage | AGPLv3 | Healthy Rust impl, ~5 k stars | Same legal-and-supply-chain shape as MinIO post-archive — **not a real escape hatch** |
| 5 | Apache Ozone | Apache-2.0 | Active but JVM | **REJECTED** (Hard Constraint #1) |
| 6 | `fsspec` local filesystem (`file://`) | OSS various | Dev-mode fallback only | When Docker is unavailable |
| 7 | MinIO archived release | AGPLv3 | Frozen 2026-04-25 | Backwards-compat template for users with existing MinIO familiarity |

**`docs/internal/swap/minio.md` action**: document the **MinIO → SeaweedFS** drill. Same S3 URIs, identical smoke tests (pyiceberg write + DuckDB scan + Polars read). Drill should run in CI per Constraint #9 (basic smoke tests, full adapter on-demand).

---

## §10. MinIO vs SeaweedFS for v0.1 (the pre-v0.1 ADR call)

Both satisfy the S3-API contract identically as far as Nucleus's hot path can tell.

| Dimension | MinIO `2025-09-07` | SeaweedFS `2025-05-04` | Weight |
|---|---|---|---|
| License | AGPLv3 | **Apache-2.0** | High |
| Upstream health | **Archived; "unmaintained" per vendor** | **Active; weekly-ish releases** | **Highest** |
| Future CVE coverage | None | Yes (active maintainers) | **Highest** |
| Language | Go (no JVM) | Go (no JVM) | Parity (Constraint #1) |
| S3 API completeness | Mature (10+ yr) | Mature; some edge cases NEEDS VERIFICATION | High — verify per PoC #1 |
| Native Iceberg catalog | None (OSS); AIStor only | Yes (since 2025-09) | Medium (v0.3+ relevance) |
| Image size / idle RAM / cold-start | 56 MB / 80-150 MB / <500 ms | ~70-90 MB (NEEDS VERIFICATION) / parity expected / NEEDS VERIFICATION | Parity at laptop scale |
| Familiarity (5-engineer beachhead) | High (industry default) | Lower | Medium — docs concern, not substrate |
| Vendor governance | MinIO Inc. (vendor-defected OSS) | Chris Lu + community; no pivot signal | High (Pillar #2 + #5) |

**Recommendation**: SeaweedFS as documentation default; MinIO compose preserved as an alternative for teams with existing MinIO familiarity. Honours Pillar #4 (familiar UX preserved) while putting the long-term bet on Apache-2.0 active upstream.

---

## §11. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2025-09-07 | MinIO OSS final release `RELEASE.2025-09-07T16-13-09Z` | Recorded — included GHSA-jjjj-jwhf-8rgr fix. |
| 2026-04-25 | ⚠️ `github.com/minio/minio` archived by owner | Triggers AGENTS.md §9 Stop Condition. |
| 2026-05-13 | OSS MinIO = AGPLv3 confirmed; community docs path mirrors AIStor content | Surface in `nucleus init` template to prevent accidental AIStor installs (commercial). |
| 2026-05-13 | **`minio` Python SDK NOT pinned in `pyproject.toml`** | All hot-path I/O routes through pyiceberg + s3fs. |
| 2026-05-13 | **Pre-v0.1 storage-substrate ADR REQUIRED** (`docs/decisions/ADR-NNN-storage-substrate-v01.md`) | §3.2 upstream death + §3.3 verdict. |
| 2026-05-13 | SeaweedFS (Apache-2.0, active) promoted v0.3 contingency → v0.1 candidate | §10 matrix; Pillar #2 + #5. |
| TBD (pre-v0.1) | Adopt §3.3 Option 3: dual compose templates, SeaweedFS as docs default | To be documented in pre-v0.1 ADR; smoke-tested in CI per Constraint #9. |
| TBD | Cloud architecture: never bundle or manage MinIO; use AWS S3 / R2 / GCS direct, or self-host SeaweedFS | §3.1 AGPLv3 §13 + §3.2 upstream death both contra-indicate Cloud-managed-MinIO. |
| 2026-05-13 | Worker B (ADR-008 storage smoke test) corrections to this doc: tag `RELEASE.2025-10-15T17-29-55Z` → `RELEASE.2025-09-07T16-13-09Z` throughout (Oct 15 fabricated; Sep 7 is the actual terminal OSS release, sha256:14cea493…); SeaweedFS release date `2026-05-04` → `2025-05-04` (year typo) | `docker pull quay.io/minio/minio:RELEASE.2025-10-15T17-29-55Z` returns "manifest unknown"; only Sep 7 manifest exists. See [`ai_hallucinations.md`](./ai_hallucinations.md) 2026-05-13 MinIO entry. |

---

## §12. NEEDS VERIFICATION (open ends)

- Cold-start time on Windows + Docker Desktop for `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` — PoC #4 produces.
- `measure_minio_health()` acceptance of HTTP `403` vs the documented `{200, 429}` — investigate origin; tighten the acceptance set.
- DuckDB 1.1.3 `httpfs` end-to-end against MinIO archived release with `URL_STYLE 'path'` + `USE_SSL false`.
- pyiceberg 0.8.1 `s3.endpoint` virtual-vs-path addressing behaviour on MinIO (`s3.force-virtual-addressing=False` should be correct).
- pyiceberg 0.11.x post-ADR-003: same `s3.*` config keys? Re-verify on upgrade PR.
- Multipart upload chunk-size defaults across pyiceberg / PyArrow 18.1.0 / MinIO. Watch failed uploads >5 GB (5 MiB part min, 10 000 part max).
- SeaweedFS idle RAM + cold-start on the same laptop hardware — §10 matrix assumes parity; verify before §11 ADR.
- Polars `s3://` reads against MinIO — exact kwarg path that threads `endpoint_url` through PyArrow.
- `boto3` PyPI pin candidate if v0.1 needs a Python admin path.
- CVE feed for `RELEASE.2025-09-07T16-13-09Z` going forward — subscribe to `https://github.com/advisories?query=minio` per Constraint #11 quarterly audit.

---

## §13. Useful links

- MinIO OSS source (archived) + final release + LICENSE (AGPLv3): <https://github.com/minio/minio> · <https://github.com/minio/minio/releases/tag/RELEASE.2025-09-07T16-13-09Z> · <https://raw.githubusercontent.com/minio/minio/master/LICENSE>
- Docker Hub (archived) + Quay mirror: <https://hub.docker.com/r/minio/minio> · <https://quay.io/repository/minio/minio?tab=tags>
- MinIO Python SDK (Apache-2.0; **not** in v0.1): <https://github.com/minio/minio-py> · <https://pypi.org/project/minio/>
- Community docs (mirrors AIStor) + Health-check endpoint: <https://docs.min.io/community/minio-object-store/> · <https://docs.min.io/community/minio-object-store/operations/monitoring/healthcheck-probe.html>
- AIStor commercial docs + license (out of scope): <https://docs.min.io/aistor/> · <https://docs.min.io/license/>
- pyiceberg S3 FileIO: <https://py.iceberg.apache.org/configuration/#s3> · DuckDB httpfs S3: <https://duckdb.org/docs/current/core_extensions/httpfs/s3api.html>
- **SeaweedFS** (primary swap target) + releases + LICENSE (Apache-2.0): <https://github.com/seaweedfs/seaweedfs> · <https://github.com/seaweedfs/seaweedfs/releases> · <https://raw.githubusercontent.com/seaweedfs/seaweedfs/master/LICENSE>
- Internal: [`lakekeeper.md`](./lakekeeper.md) §6, [`polaris.md`](./polaris.md) §6, [`pyiceberg.md`](./pyiceberg.md) §5, [`ai_hallucinations.md`](./ai_hallucinations.md), [`pyproject.toml`](../../../pyproject.toml), [`poc/p4_boot_time/measure.py`](../../../poc/p4_boot_time/measure.py), `docs/specs/nucleus_architecture_v4.1.md` §3.1 + §4.1 + §5.8, `AGENTS.md` §3 #1/#10/#11 + §9.

---

*Last verified 2026-05-13. Re-verify before the pre-v0.1 storage-substrate ADR (§3.3 + §11), on every pyiceberg / DuckDB upgrade per Constraint #11, on every CVE for the archived MinIO release, and when SeaweedFS publishes a swap-drill candidate. Log AI-fabricated MinIO / S3-API surface caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
