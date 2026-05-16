# ADR-007: Dependency License Tier Policy

> **Status**: ACCEPTED — 2026-05-13 (founder blanket approval per FOUNDER_ACTION_QUEUE.md §0)
> **Date**: 2026-05-13 · **Decider**: Solo founder
> **Tags**: licensing, dependencies, governance, cloud-readiness
> **Related**: ADR-001, ADR-002 §8.x (yield-to-giants commercial path), ADR-003, ADR-005, ADR-006, AGENTS.md §3 Hard Constraints, docs/specs/nucleus_architecture_v4.1.md §9 (composability), `docs/internal/research/minio.md` (Worker BB — AGPLv3), `docs/internal/research/soda.md` (Worker T — Apache-2.0 v3 vs Elastic v4)

## Context

Two parallel research workers (`docs/internal/research/minio.md`, `docs/internal/research/soda.md`) surfaced license-boundary findings that have real legal consequences for Nucleus's commercial path (Cloud tier per ADR-002):

| Finding | Component | License | Implication |
|---|---|---|---|
| MinIO | Tier 0 local-storage substrate | **AGPLv3** (since 2021) | SAFE for OSS (user `docker run`s themselves); DANGER if Nucleus Cloud bundles MinIO binary or offers managed-MinIO SaaS — AGPLv3 §13 forces source release of entire service |
| Soda Core v3 | v0.5+ optional contract framework | **Apache-2.0** (`soda-core==3.5.6`, last v3 release 2025-09-24) | SAFE for OSS + Cloud |
| Soda Core v4 | Same library, future major | **Elastic License 2.0** (`soda-core==4.10.0`, 2026-05-12) | **BLOCKED for Nucleus Cloud** — ELv2 prohibits providing "as a hosted or managed service" and ships runtime license-key DRM |

These are NOT one-off findings. As Nucleus wraps more OSS components (10+ already pinned, more coming), license-tier discipline must be a policy, not a per-component scramble.

This ADR locks the policy **before** the first commercial decision forces it ad hoc.

## Decision

> **Three-tier dependency license policy. License compatibility is a hard gate for adoption and for upgrades. Tier shifts (e.g., upstream relicense Apache-2.0 → BUSL) trigger an automatic ADR + freeze on that dependency version.**

### Tier 1: GREEN — adoptable anywhere (OSS + Cloud + Enterprise)

| Licenses |
|---|
| Apache-2.0 |
| MIT |
| BSD-2-Clause / BSD-3-Clause |
| ISC |
| Public Domain / CC0 (rare) |

Treatment: no special handling; pin freely, upgrade per Constraint #11 normal workflow.

### Tier 2: YELLOW — adoptable in OSS distribution; Cloud requires careful boundary

| Licenses | Examples | OSS treatment | Cloud treatment |
|---|---|---|---|
| **AGPLv3** | MinIO server, Mastodon, Grafana (some), CockroachDB before 2024 | SAFE — user runs themselves | DANGER — `bundling` or `hosted-service` triggers §13 source-release obligation |
| **GPLv3 (non-Affero)** | (rare in our stack — none known yet) | SAFE — boundary is binary distribution | SAFE — SaaS exempt; only redistribution triggers |
| **GPLv2 with classpath exception** | Some JVM tools | SAFE | SAFE — exemption blocks viral spread |
| **LGPLv3** | (rare) | SAFE | SAFE — dynamic linking exempt |
| **MPL-2.0** | Some Mozilla projects | SAFE | SAFE — file-level copyleft |

**Treatment for YELLOW**:
1. Allowed as runtime dependency (user-invoked or our process subprocess)
2. **NEVER bundled** into a Nucleus binary distribution under our license
3. **NEVER offered as managed-service** in Cloud (e.g., "Nucleus Cloud Hosted MinIO") — would force AGPLv3 §13 release of Cloud control plane
4. **For Cloud**: tier 2 dependency must run in user's account/VPC, not ours
5. ADR required before any YELLOW dependency moves into Cloud's process boundary

### Tier 3: RED — BLOCKED for Cloud; allowed in OSS only with care; never bundled

| Licenses | Examples | OSS treatment | Cloud treatment |
|---|---|---|---|
| **Elastic License 2.0 (ELv2)** | Elasticsearch ≥ 7.11, Kibana ≥ 7.11, Soda Core ≥ 4.0, Logstash | OPTIONAL — user opt-in, isolated import path; never default | **BLOCKED** — explicit "no hosted/managed service" clause |
| **Server Side Public License (SSPL)** | MongoDB ≥ 4.0, Redis ≥ 7.4 | OPTIONAL — same as ELv2 | **BLOCKED** — broader §13 than AGPLv3 |
| **Business Source License (BUSL)** | CockroachDB ≥ 2024, MariaDB MaxScale, Sentry, Confluent CC | OPTIONAL — user opt-in only | **BLOCKED** — license restricts commercial competitive use; ambiguous SaaS boundary |
| **Proprietary / Source-available without OSI approval** | Soda Library, Soda Cloud, Databricks Connect | **NEVER WRAP** — full proprietary | **BLOCKED** |
| **Anti-Capitalist / Hippocratic / similar restricted** | (rare in data tooling) | REJECT — incompatible with most users' commercial use | REJECT |

**Treatment for RED**:
1. **Always opt-in import path** — never default; user must `pip install nucleus[soda]` knowing the implications
2. Wrapping module documents the license-tier restriction in its module docstring
3. **Cloud cannot include RED dependencies** — Cloud control plane must work without any RED import
4. ADR required to add ANY new RED dependency
5. Pin to last-GREEN version when upstream relicenses GREEN→RED (e.g., Soda Core stay on `3.5.6`, never `4.x`)

## Standing pre-decisions (apply this policy to known cases)

| Component | Current pin | License | Tier | Cloud-safe? | Action |
|---|---|---|---|---|---|
| Python 3.11 stdlib | n/a | PSF | GREEN | ✓ | none |
| DuckDB | `duckdb==1.1.3` | MIT | GREEN | ✓ | none |
| Polars | `polars==1.18.0` | MIT | GREEN | ✓ | none |
| Dagster | `dagster==1.9.5` | Apache-2.0 | GREEN | ✓ | none |
| pyiceberg | `pyiceberg==0.8.1` | Apache-2.0 | GREEN | ✓ | none |
| OpenLineage | `openlineage-python==1.47.1` | Apache-2.0 | GREEN | ✓ | none |
| OpenTelemetry | `opentelemetry-api/sdk==1.29.0` | Apache-2.0 | GREEN | ✓ | none |
| sqlglot | `sqlglot==26.0.0` | MIT | GREEN | ✓ | none |
| pyarrow | (transitive) | Apache-2.0 | GREEN | ✓ | none |
| dlt | `dlt==1.26.0` | Apache-2.0 | GREEN | ✓ | none |
| Lakekeeper | (v0.3+ runtime) | Apache-2.0 | GREEN | ✓ | none — Rust binary, no JVM |
| Polaris | (v0.3+ runtime) | Apache-2.0 | GREEN | ✓ | none — JVM-in-own-process is fine per ADR-002 §6 |
| **MinIO** | (runtime via Docker) | **AGPLv3** | **YELLOW** | **CONDITIONAL** | OSS docs say `docker run minio/minio` — user-owned. Cloud DOES NOT bundle MinIO; v0.5 Cloud-storage path defers to user-owned S3 / AWS S3 / R2 / SeaweedFS (Apache-2.0 alternative if needed) |
| **Soda Core v3** | `soda-core==3.5.6` (if adopted v0.5+) | Apache-2.0 | GREEN | ✓ | v0.5 opt-in import path allowed |
| **Soda Core v4+** | NEVER PIN | Elastic 2.0 | **RED** | ✗ | never pin; v3 is terminal for our wrap |
| dbt-duckdb v1.10.1 | (v0.3+ optional) | Apache-2.0 | GREEN | ✓ | none |
| dbt-core v1.11.x | (v0.3+ optional) | Apache-2.0 (verify per ADR-003 §...) | GREEN (verify) | ✓ | minor verify per Worker S's NV |
| Marimo | (v0.3+) | Apache-2.0 (verify Worker E) | GREEN | ✓ | none |

## Upgrade detection trigger

A **license-tier change in an upstream dependency** is automatic-ADR territory per Constraint #11:

1. CI script `scripts/check_licenses.py` (NEEDS VERIFICATION — to be authored) scans `pip show` of pinned deps, reads LICENSE field
2. Tier classification per the GREEN/YELLOW/RED tables above
3. Fail CI if any pinned dependency moves tiers (e.g., GREEN→YELLOW, YELLOW→RED) compared to previous lock file
4. Open ADR for the tier-shift; freeze on last-GREEN/YELLOW version pending decision

This script is **release-blocker discipline** for v0.5 (Cloud preview phase). Pre-v0.5, manual `Worker T`-style audits suffice.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| **AI proposes a RED dependency without flagging tier** | This ADR linked in `AGENTS.md §11.12`; AI prompts must include license check |
| **Upstream silent relicense** (Apache → BUSL mid-version) | CI lint detects on next upgrade; lock at last-GREEN version + open ADR |
| **YELLOW (AGPLv3) Cloud accidental bundling** | Cloud build pipeline contains explicit denylist; build fails if MinIO/etc. detected inside Cloud Docker image |
| **Founder forgets policy during fast-paced PR** | PR template (`.github/PULL_REQUEST_TEMPLATE.md`) adds license-tier checkbox |
| **License-tier wrong** (e.g., PyPI metadata empty as Soda v3's was) | Always verify against GitHub LICENSE file when PyPI field blank |
| **Multi-license dependency** (dual-licensed) | Default to most restrictive option; document in research doc |

## Verification plan

1. **`scripts/check_licenses.py`** (~80 LOC) — v0.5 release blocker; reads `pip show` for every pinned dep, classifies per this ADR, fails on tier shift
2. **`.github/PULL_REQUEST_TEMPLATE.md`** — add license-tier checkbox to existing constraints list (already mirrors AGENTS.md §3)
3. **`docs/internal/compatibility.md`** — extend matrix with License column + tier classification
4. **CHANGELOG.md** — every dependency add/upgrade notes its license tier
5. **Research doc template** — going forward, every `docs/internal/research/<lib>.md` MUST have a §License + §Tier-classification section (Worker T and Worker BB both did this; codify)

## Rollback

If this policy proves too strict:
- ADR-007a relaxes specific tier rules (e.g., allow YELLOW in Cloud if behind feature flag) — requires ADR + legal review
- If too loose (license violation discovered post-ship): emergency relicense the affected Cloud component OR remove the dependency; cite Constraint #11 single-component-per-PR

No emergency rollback path for license violations themselves — once shipped, AGPLv3/ELv2 obligations are irreversible. Hence the strict gate.

## Docs URLs

- Apache-2.0 full text: https://www.apache.org/licenses/LICENSE-2.0
- AGPLv3: https://www.gnu.org/licenses/agpl-3.0.html
- Elastic License 2.0: https://www.elastic.co/licensing/elastic-license
- SSPL: https://www.mongodb.com/licensing/server-side-public-license
- BUSL: https://mariadb.com/bsl11
- SPDX license list (canonical): https://spdx.org/licenses/

## Trigger

Status flips **PROPOSED → ACCEPTED** when:
- Founder reviews + signs off
- `scripts/check_licenses.py` script exists (v0.5 release blocker, deferred-OK pre-v0.5)
- PR template updated with license-tier checkbox
- This ADR linked from AGENTS.md §3 (no edit yet; pending founder direction)

Not gated on any PoC or v0.1 implementation. This is governance; can land immediately.

## Downstream consumers

| Consumer | When affected |
|---|---|
| Any new dependency add (post-acceptance) | Must classify tier in research doc + ADR if not GREEN |
| ADR-002 Cloud commercial path | This ADR is a hard prerequisite — Cloud cannot launch without license-tier discipline |
| Worker T's Soda research | Codifies Worker T's v3-only finding as standing policy |
| Worker BB's MinIO research | Codifies Worker BB's AGPLv3-conditional finding |
| Future research workers | Template `§License` section now mandatory |
| Workbench dependency tree (v0.2+) | Must transitively satisfy this policy |
| Cloud Copilot LLM provider choice (v0.5+) | OpenAI/Anthropic/etc. ToS treated as Tier 1 (commercial license, not OSS) — separate ADR on AI provider policy may follow |

## Open questions for founder

1. Is YELLOW (AGPLv3) **acceptable** in Cloud if isolated to user's AWS account (e.g., bring-your-own-MinIO)? Default ADR position: yes, because Cloud doesn't bundle the binary. — **RESOLVED 2026-05-13**: yes (with isolation requirement — runs in user account/VPC, never inside Nucleus Cloud control plane) per founder blanket approval (FOUNDER_ACTION_QUEUE.md §1 A1.13).
2. Should we **proactively migrate** off MinIO to SeaweedFS (Apache-2.0) before v0.5 Cloud launch to eliminate AGPLv3 ambiguity? Default ADR position: defer; OSS use case is safe today. — **RESOLVED 2026-05-13**: defer; let users opt out via SeaweedFS default per ADR-008 (already shipped dual-track). MinIO alternate stays available for prior-familiarity users.
3. Should there be a "Tier 4 — STRATEGIC PARTNER" for proprietary commercial licenses we choose to embed (e.g., Databricks Connect, Snowflake driver) per the yield-to-giants strategy? Default ADR position: yes; cover in separate ADR if/when partner integration concretely launches. — **RESOLVED 2026-05-13**: yes (scope to separate ADR when first partner integration concretely launches); do NOT define Tier 4 in this ADR.

---

**Ratified**: 2026-05-13 — founder blanket approval of recommendations per FOUNDER_ACTION_QUEUE.md §0.

---

## License Resolution (2026-05-14)

Human-verified license strings for packages where `importlib.metadata` previously surfaced `UNKNOWN` or an ambiguous BSD label, plus boundary notes for standing YELLOW pins. Sources are PyPI JSON (`/pypi/<dist>/<ver>/json`), GitHub `LICENSE` / `LICENSE.txt`, or SPDX-classifier text — not guessed from vague wheel tags.

| Package | Version | License string (canonical) | Tier | Rationale + source |
|---|---|---|---|---|
| `openlineage-python` | `1.47.1` | `Apache-2.0` | **GREEN** | PyPI `license_expression` + classifier `License :: OSI Approved :: Apache Software License` — https://pypi.org/pypi/openlineage-python/1.47.1/json · corroborated by Apache-2.0 root license in the OpenLineage monorepo — https://raw.githubusercontent.com/OpenLineage/OpenLineage/main/LICENSE |
| `s3fs` | `2026.4.0` | `BSD-3-Clause` | **GREEN** | PyPI classifies `License :: OSI Approved :: BSD License` with `license: BSD` (ambiguous variant); upstream `LICENSE.txt` is the 3-clause BSD text — https://raw.githubusercontent.com/fsspec/s3fs/main/LICENSE.txt · project — https://pypi.org/project/s3fs/2026.4.0/ |
| `orjson` | `3.11.9` | `MPL-2.0 AND (Apache-2.0 OR MIT)` | **YELLOW** | PyPI `license_expression` + multi-classifier (Apache / MIT / MPL-2.0) — https://pypi.org/pypi/orjson/3.11.9/json · project README license section — https://github.com/ijl/orjson#license **Boundary:** MPL-2.0 is file-level copyleft. Nucleus consumes `orjson` only as a published wheel via `pip`; we do **not** maintain a fork or ship modified `orjson` sources, so file-level obligations do not attach to Nucleus-authored code (ADR-007 Tier 2 MPL row). |
| `psycopg` | `3.2.3` | `LGPL-3.0-only` (PyPI: “GNU Lesser General Public License v3 (LGPLv3)”) | **YELLOW** | PyPI `license` field + `License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)` — https://pypi.org/pypi/psycopg/3.2.3/json · project links — https://github.com/psycopg/psycopg **Boundary:** LGPLv3 is library copyleft affecting derivative works of the library itself. Nucleus uses `psycopg[binary]` as a normal Python dependency (dynamic link / wheel install), not a statically linked or vendor-patched embed, so the LGPL boundary matches ADR-007 Tier 2 “LGPLv3 (dynamic-link exempt)” intent. |

**CI note:** `scripts/check_licenses.py` uses PyPI metadata when resolvable; when the normalized tier is **UNKNOWN** but ADR-007 documents a verified `BAKED_IN_LICENSES` string (2026-05-14 amendment), `collect()` substitutes the baked value so CI matches policy.
