# ADR-008: Storage Substrate Triage Post-MinIO Archival (Pre-v0.1)

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0; clears AGENTS.md §9 Stop Condition for pre-v0.1 ship)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: storage, supply-chain, license, agplv3, beachhead, stop-condition
> **Related**: ADR-002 §6 + §8.1; ADR-007 (AGPLv3 = Tier 2 YELLOW); AGENTS.md §3 Constraint #1 + §9 Stop Conditions; v4.1 §3.1 + §4.1 + §1.5 + §9; `docs/internal/research/minio.md` (Worker BB, 2026-05-13)

## Context

Worker BB's research (`docs/internal/research/minio.md`, 23.5 KB) verified two upstream facts that re-shape MinIO from "OSS YELLOW with AGPLv3 footnote" to "archived dependency with no future CVE patches": (1) `github.com/minio/minio` was **archived 2026-04-25** (Worker BB §3.2 + §11; banner at <https://github.com/minio/minio>), and (2) the terminal OSS release `RELEASE.2025-09-07T16-13-09Z` shipped [GHSA-jjjj-jwhf-8rgr](https://github.com/minio/minio/internal/security/advisories/GHSA-jjjj-jwhf-8rgr); MinIO Inc. publicly labels OSS MinIO **"unmaintained"** (Worker BB §1 — **NEEDS VERIFICATION on exact blog URL**). This trips **AGENTS.md §9 Stop Conditions** explicitly (*"A major upstream OSS we wrap breaks compatibility, hostile licenses, or dies"*) and **must be reconciled before v0.1 ships** — PoC #3, PoC #4, and PoC #5 all pin the archived release.

AGPLv3 is **secondary but still real** (ADR-007 Tier 2 YELLOW): SAFE for OSS user-on-laptop (same posture as `docker run postgres:15-alpine`); DANGER if Cloud bundles the binary or offers managed-MinIO SaaS (AGPLv3 §13 forces source release). Post-archive, supply-chain risk dominates; AGPLv3 doesn't get worse but stops being the headline. Two architectural facts make this resolvable cheaply: **S3 API is Tier 0 immortal** per v4.1 §3.1 + §4.1 (*"Universal: MinIO, SeaweedFS, R2, GCS, Azure"*) — the protocol doesn't die, only the implementation changed governance state; and **Nucleus's hot path doesn't `import minio`** (Worker BB §1 + §2.2) — every byte goes through `pyiceberg` + `s3fs` (transitive via `pyiceberg[s3fs]==0.8.1`) + DuckDB `httpfs`. Swapping is compose + docs, not code.

## Decision

> **Dual-track docker-compose templates. SeaweedFS (Apache-2.0, actively maintained — release 2025-05-04 per Worker BB §10) becomes Nucleus's documentation default; MinIO is preserved as an alternate template explicitly tagged "archived upstream" for teams with prior MinIO familiarity. Nucleus's S3-API-agnostic code works identically against either backend; no application-layer code changes are required.**

### Option matrix

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A — MinIO only** | Familiar; `mc` CLI; proven cold-start | Archived (CVE accumulation, Worker BB §3.2); AGPLv3 risk in Cloud; §9 unresolved | **REJECT** |
| **B — SeaweedFS only** | Apache-2.0; active; native Iceberg catalog (v0.3+); single Go binary | Loses Pillar #4 (familiar UX) for MinIO veterans | Viable but lossy |
| **C — Dual-track (this ADR)** | Beachhead-friendly; Apache-2.0 default removes supply-chain risk; honours Pillars #2 + #4 simultaneously | Maintain two compose templates | **ACCEPT** |
| D — Defer to v0.3 | Avoids pre-v0.1 doc churn | Ships v0.1 on archived AGPLv3 binary through Mo 4 → Mo 20; §9 says *pause and escalate* | **REJECT** |
| E — Filesystem-only | Smallest dependency surface | Breaks S3-API parity vs AWS S3; violates v4.1 §1.5 + Pillar #5 (Mode 1 graduation no longer a 3-line swap) | **REJECT** (dev-mode fallback only per Worker BB §9 row 6) |

### Pin candidates

| | Server | Python client | License | Maintained |
|---|---|---|---|---|
| **SeaweedFS** (new default) | `chrislusf/seaweedfs:<NEEDS VERIFICATION pin>` — verify at <https://github.com/seaweedfs/seaweedfs/releases>; release 2025-05-04 per Worker BB §10 | None — `s3fs` + `pyiceberg` already speak S3 (Worker BB §2.2) | **Apache-2.0** | Active — ~32 k stars |
| **MinIO** (alternate) | `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` — terminal OSS release | Not pinned (Worker BB §2.2 + §11) | **AGPLv3** (ADR-007 YELLOW) | **Archived 2026-04-25** |

**NEEDS VERIFICATION**: SeaweedFS exact docker tag + image size (~56 MB MinIO per Worker BB §7; SeaweedFS expected ~70-90 MB per Worker BB §10).

### Risk reframing post-archival

| Risk | MinIO pre-archival | MinIO today | SeaweedFS |
|---|---|---|---|
| AGPLv3 §13 Cloud-bundling (ADR-007) | DANGER | DANGER | n/a (Tier 1 GREEN) |
| Supply-chain (future CVE patches) | OK | **CRITICAL** (no patches, Worker BB §3.2) | OK (active maintainers) |
| AI hallucinations on S3 config keys | YELLOW (Worker BB §6) | Same | Same |
| Tooling familiarity | HIGH (`mc` CLI) | HIGH | LOWER (`weed` CLI) |
| JVM exposure (Constraint #1) | OK (Go) | OK (Go) | OK (Go) |
| Vendor governance | Vendor-defected | Formally retired OSS | Community (no pivot signal) |

### Compose templates

Default `docker-compose.yml` (port `9000:8333` preserves the `localhost:9000` endpoint convention per Worker BB §4.2):

```yaml
services:
  storage:
    image: chrislusf/seaweedfs:<NEEDS VERIFICATION pin>
    command: server -s3
    ports: ["9000:8333"]
    volumes: ["./.nucleus/storage:/data"]
```

Alternate `docker-compose.minio.yml` (opt-in, archived-substrate banner in docs):

```yaml
services:
  storage:
    image: quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    volumes: ["./.nucleus/storage:/data"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
```

User picks: `docker compose up` (SeaweedFS, default) OR `docker compose -f docker-compose.minio.yml up`.

### Nucleus code changes required

**None at the application layer.** All hot-path I/O routes through `s3fs` + `pyiceberg` + DuckDB `httpfs`, all S3-API-agnostic per Worker BB §4 + §5. The pyiceberg config block (`s3.endpoint`, `s3.access-key-id`, `s3.secret-access-key`, `s3.region`, `s3.force-virtual-addressing=False`) and DuckDB `CREATE SECRET` template (`URL_STYLE 'path'`, `USE_SSL false`) remain identical. The dual-track is **purely documentation + compose YAML**.

**NEEDS VERIFICATION**: SeaweedFS S3 parity edge cases — path-style default, sigv4, multipart chunk threshold (MinIO-side NV per Worker BB §5), and absence of a `/minio/health/live`-equivalent that PoC #4 probes (`poc/p4_boot_time/measure.py:35`) — PoC #4 promotion generalizes `measure_minio_health()` → `measure_storage_health()`.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| SeaweedFS S3-API parity gap vs MinIO / AWS S3 | PoC #4 + PoC #3 verify; gaps logged in `docs/internal/research/seaweedfs.md` (v0.5 per Worker BB §10) |
| SeaweedFS less familiar to data engineers | Default + quickstart uses SeaweedFS; MinIO template tagged "archived upstream — for prior-MinIO familiarity only" |
| Dual templates = maintenance burden | Small: two YAML files; swap-drill smoke test in CI per Constraint #9 |
| Future SeaweedFS archival | Swap path in `docs/internal/swap/storage_substrate.md`; Tier-0 portability keeps future swap config-only |
| Founder familiarity bias toward MinIO | Data-driven override: ADR-007 + AGENTS.md §9 + Worker BB §3.2 force the SeaweedFS default. Documented here, not silent. |
| PoC #4 health probe is MinIO-specific (Worker BB §4.1) | PoC #4 promotion (AGENTS.md §11.1) generalizes probe + tightens `{200, 403}` to `{200, 429}` |

## Verification plan

1. **PoC #4 boot harness** against SeaweedFS on Win + macOS + Linux — <0.5 s health-check phase inside `nucleus up <10s` (v4.1 §6.3 + Worker BB §4.1).
2. **PoC #3 ingest** writes Iceberg via SeaweedFS — `pyiceberg` 0.8.1 + `s3fs` `Catalog.create_namespace` + `Table.append` + `scan().to_arrow()` parity.
3. **PoC #1 error translation** runs against SeaweedFS — `CommitFailedException` / `CommitStateUnknownException` still surface (PoC #1 is backend-agnostic per Worker BB §3 + §4.2).
4. **Swap-drill smoke test** in CI per Constraint #9: same pytest suite runs against both compose templates; divergence is a regression.
5. **README + SETUP.md** + `docs/internal/research/minio.md` cross-link + status flip in follow-up PR (not this ADR's diff per hard-constraint).

## Rollback

If SeaweedFS proves problematic: **ADR-008a** flips default back to MinIO archived (accepting §9 as knowingly-deferred risk); **ADR-008b** evaluates Garage (Rust S3, also AGPLv3 per Worker BB §9 row 4 — **not a real escape hatch**); **hard fallback** = filesystem-only `file://` per Worker BB §9 row 6 (dev-mode only, v4.1 §1.5 violation accepted). Iceberg metadata is byte-identical across S3 backends (Worker BB §4.3) so switching is data-free: `docker compose down && docker compose -f docker-compose.minio.yml up -d`. No `pyproject.toml` change.

## Docs URLs

- SeaweedFS: <https://github.com/seaweedfs/seaweedfs> · releases · LICENSE (Apache-2.0)
- MinIO archive + final release + LICENSE (AGPLv3): <https://github.com/minio/minio> · <https://github.com/minio/minio/releases/tag/RELEASE.2025-09-07T16-13-09Z>
- MinIO archival announcement: **NEEDS VERIFICATION** — Worker BB §1 cites `blog.min.io/blog/minio-aistor-vs-minio-oss-technical-comparison`
- pyiceberg S3: <https://py.iceberg.apache.org/configuration/#s3> · DuckDB httpfs: <https://duckdb.org/docs/current/core_extensions/httpfs/s3api.html>
- AGENTS.md §9 (Stop Conditions) + §3 Constraint #1; v4.1 §3.1 + §4.1 + §1.5 + §9

## Trigger

Status flips **PROPOSED → ACCEPTED** when, in a single follow-up PR (kept out of this ADR's diff per the hard-constraint): founder signs off on Option C; `docker-compose.yml` switched to SeaweedFS + `docker-compose.minio.yml` created with the SeaweedFS tag pinned + image size measured (resolves NV #1); `docs/internal/swap/storage_substrate.md` authored (interface + smoke tests per Constraint #9); `docs/internal/research/minio.md` status header → "ALTERNATE substrate per ADR-008" with cross-links in §3.3 + §10 + §11; v4.1 §5.x note added; README + SETUP.md quickstart updated; `docs/internal/research/seaweedfs.md` scheduled at v0.5 entry.

**Not gated on PoC #1.** Governance + infrastructure; **must land pre-v0.1** to clear §9 before any `src/nucleus/` production code per AGENTS.md §11.1.

## Downstream consumers

| Consumer | How affected |
|---|---|
| `poc/p4_boot_time/measure.py` | Re-baseline; `measure_minio_health()` → `measure_storage_health()` on promotion (AGENTS.md §11.1); `{200, 403}` → `{200, 429}` (Worker BB §4.1) |
| `poc/p3_ingest/ingest.py` | Verify `pyiceberg` + `s3fs` round-trip against SeaweedFS; no code change (backend-independent) |
| PoC #5 beachhead | New compose = new tester instruction; field-tested in the same pass that locks the tagline (ADR-002 §8.4) |
| `docs/internal/research/minio.md` | Status → "ALTERNATE substrate per ADR-008"; remains the archived-substrate reference |
| `docs/internal/swap/storage_substrate.md` | New on acceptance; documents MinIO ↔ SeaweedFS drill per Constraint #9 |
| v4.1 §5.x + README + SETUP.md | Cross-ref + quickstart mentions SeaweedFS default + archived-MinIO alternate |
| `pyproject.toml` | **No change** — `minio`-py was correctly not pinned (Worker BB §2.2); ADR-003's `pyiceberg==0.11.x` is independent |
| Future Cloud (v0.5+, ADR-002 §6) | Never bundle either substrate; use AWS S3 / R2 / GCS direct or self-hosted SeaweedFS per ADR-007 + Worker BB §3.3 |

## Open questions for founder

1. **Dual-track now, OR hard-cut to SeaweedFS only?** Hard-cut cost: removes the familiar option for MinIO veterans; benefit: cleaner "MinIO OSS is dead" signal. *Default: Option C.* — **RESOLVED 2026-05-13**: dual-track (SeaweedFS default, MinIO opt-in via `docker-compose.minio.yml`) per founder blanket approval (FOUNDER_ACTION_QUEUE.md §1 A1.14).
2. **Pin SeaweedFS to a specific release tag** (AGENTS.md §11.13) **OR latest-stable rolling?** *Default: pin at adoption, then Constraint #11 one-component-per-PR (ADR-003 precedent).* — **RESOLVED 2026-05-13**: pin tag (SeaweedFS 4.23, MinIO `RELEASE.2025-09-07T16-13-09Z`) per founder blanket approval; exact SeaweedFS tag still NEEDS VERIFICATION per Worker BB §10 and the §"Pin candidates" table NV #1.
3. **Add a `nucleus migrate-storage-substrate` CLI helper** (~50 LOC) **OR defer to v0.3?** *Default: defer; v0.1 users have ~0 production data on either substrate yet.* — **RESOLVED 2026-05-13**: defer (scope to future separate ADR) per founder blanket approval; do NOT implement in v0.1.

---

*Last verified 2026-05-13. Re-verify SeaweedFS pin + S3 parity against Worker BB §10 before sign-off, on every SeaweedFS release per AGENTS.md §11.13, and if the MinIO blog URL shifts (NV #3).*

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.
