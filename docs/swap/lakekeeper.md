# Swap target: Lakekeeper → Apache Polaris (catalog co-default flip)

> **Tier**: 1 per `docs/specs/nucleus_architecture_v4.1.md` §3, §9.2 (Catalog).
> **Current**: Lakekeeper server `0.12.2` (Apache-2.0 Rust binary). Wrapped via `pyiceberg.RestCatalog`. v0.1 ships filesystem `SqlCatalog`; v0.3+ co-defaults Lakekeeper + Polaris per v4.1 §5.7 + ADR-002 §6. Not a Python dep — external service.
> **Swap target**: Apache Polaris (ASF top-level project 2026-02-18; Apache-2.0). Java + Quarkus. **No JVM-free guarantee** — accepted per ADR-002 §6 as the price of ASF-governance + multi-vendor signal.
> **Doc status**: INTERFACE-ONLY. Data plane is already a config-flip; full management-plane adapter on-demand per v4.1 §9.3.

## 1. Trigger conditions

Both engines co-defaulted from v0.3 per ADR-002 §6, so triggers fire when we'd want to **drop Lakekeeper entirely** (or activate Polaris pre-v0.3 GA):

- [ ] **Vendor death / license pivot** — Vakamo abandons `main` >12 mo (single-company concentration is the reason Polaris co-defaults — `docs/internal/research/lakekeeper.md` §9), OR Apache-2.0 → BSL/SSPL.
- [ ] **Performance regression** — `Catalog.commit_table()` p99 regresses >2x against PoC #3 baseline, OR Rust-binary cold-start breaks `nucleus up <10s`.
- [ ] **Community demand** — ≥30% of users request Polaris-only.
- [ ] **Constraint violation / spec-divergence** — Lakekeeper adds JVM dep, drops single-binary, relaxes the atomic-commit contract ADR-001 relies on (§5.4), OR Polaris ships Iceberg-spec-v3 (`timestamp_ns`, geo, variant) >6 mo before Lakekeeper that v0.5+ multimodal needs.

## 2. Swap interface

Data plane is **shared** (`pyiceberg.RestCatalog`). Only the management plane diverges.

```python
# Sketch — implementation lands in src/nucleus/catalog/catalog_protocol.py
# Per v4.1 §5.7. Data-plane Protocol = docs/swap/pyiceberg.md §2.

from typing import Protocol


class CatalogManagementProtocol(Protocol):
    """Used by `nucleus init --catalog {lakekeeper|polaris}` + Cloud tier
    (v0.5+). Plain HTTP via httpx; not in pyiceberg."""

    def bootstrap(self, admin: "AdminPrincipal") -> None: ...
    def create_warehouse(
        self, name: str, *, storage: "StorageProfile", credentials: "StorageCredential",
    ) -> "WarehouseHandle": ...
    def create_role(self, name: str, *, principals: list[str]) -> "RoleHandle": ...
    def health(self) -> "HealthStatus": ...
```

Data plane: identical to `docs/swap/pyiceberg.md` §2. Management plane: each method above maps to different HTTP paths + body schemas across the two engines (§5 risk 2). Out of scope: per-engine UI surfaces, Polaris two-tier role model (flattened), Lakekeeper OPA authorizer (Tier 3 escape hatch).

## 3. Smoke-test sketch (CI)

`tests/swap/test_catalog_swap.py` *(TBD — lands when Lakekeeper enters as v0.3 catalog co-default per ADR-002 §6 + ADR-004; the smoke test is a sketch in this doc rather than a current path on disk)*:

```python
import pytest


@pytest.fixture(params=["filesystem", "lakekeeper", "polaris"])
def catalog_impl(request):
    if request.param == "polaris" and not _polaris_adapter_built():
        pytest.skip("Polaris adapter not built; swap doc only (v4.1 §9.3).")
    return _load_catalog(request.param)


# Shared data plane (also in docs/swap/pyiceberg.md — re-run here against REST)
def test_create_namespace_idempotent(catalog_impl): ...
def test_append_arrow_table_produces_snapshot(catalog_impl): ...
def test_commit_conflict_raises_translatable_error(catalog_impl): ...
def test_transaction_commits_atomically(catalog_impl): ...

# REST-only + management plane (skipped for filesystem)
def test_auth_expired_translates_to_NucleusAuthError(catalog_impl): ...
def test_warehouse_not_found_translates_to_NucleusCatalogError(catalog_impl): ...
def test_bootstrap_admin_idempotent(catalog_impl): ...
def test_create_warehouse_with_s3_compat_profile(catalog_impl): ...
```

8 contract-level tests. Filesystem catalog skips management-plane fixtures. Lakekeeper container runs in every CI build at v0.3+ (default); Polaris fixture activates when the adapter exists.

## 4. Swap-cost estimate

Data plane is config-only because `pyiceberg.RestCatalog` already wraps both. Cost is concentrated in the management plane + operational footprint.

| Phase | Effort |
|---|---|
| Data-plane config-flip in `nucleus init --catalog polaris` | 1 day |
| Polaris management-plane HTTP wrapper (`httpx` → `/api/management/v1/...`) | 4 days |
| Storage-profile + role-model translation | 5 days |
| OIDC matrix re-verification + `docker-compose.yml` JVM image change | 4 days |
| Error translation + cold-start/RAM benchmark + migration guide | 6 days |
| **Total LOC** | **~800-1500** |
| **Total calendar time** | **~3 weeks** |

Lowest-LOC swap of the six docs — `pyiceberg.RestCatalog` carries 90% of the work. Expensive line is the operational footprint change (JVM runtime), not Python code.

## 5. Critical risks specific to this swap

1. **Polaris JVM cold-start + RAM regression.** Quarkus / JVM cold-start ~3-5s, default heap ~500 MB. Lakekeeper's Rust binary is sub-second with 100-300 MB jemalloc footprint (`docs/internal/research/lakekeeper.md` §6). v4.1 §11.2 budgets (`nucleus up <10s`, idle RAM <500 MB) both tighten — idle RAM violated by the catalog alone. Mitigation: `-Xmx256m`; verify under PoC #4 at trigger time.
2. **Storage-profile + management-API divergence.** Lakekeeper uses `POST /management/v1/warehouse` with its OpenAPI-specific `storage-profile` + `storage-credential` (`docs/internal/research/lakekeeper.md` §4.2); Polaris uses `POST /api/management/v1/catalogs` with a different body, plus `principal-role` + `catalog-role` two-tier vs Lakekeeper's `role`. Two concrete management clients behind one Protocol.
3. **OIDC quirks + Idempotency-Key parity.** Lakekeeper documents Keycloak / Entra-ID / Google (broken for machine auth) / k8s SA / Authentik (`NEEDS VERIFICATION`) per `docs/internal/research/lakekeeper.md` §5.2; Polaris's matrix differs — do NOT assume findings transfer. Lakekeeper 0.11.0+ ships Idempotency-Key + ETag (§5.4); Polaris compliance affects retry semantics in `coordination/asset_materialization.py`.
4. **Operational footprint + Constraint #1 nuance.** v0.3 assumes Lakekeeper + Postgres in `docker-compose.yml`; Polaris adds Java runtime; offline first-run depends on pre-caching (v4.1 §11.4 tightens). Constraint #1 ("No JVM in core path"): ADR-002 §6 accepts Polaris because Polaris-the-catalog is a *peer service*, not in the Nucleus Python process — never imply Polaris-as-Nucleus = JVM in core; the user's catalog choice is theirs.

## 6. Cited docs

- Current: https://docs.lakekeeper.io/docs/nightly/{concepts,storage,authentication}/
- Swap target: https://polaris.apache.org/ • https://github.com/apache/polaris (verify management-service path at trigger time)
- Iceberg REST + Python surface: https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml • https://py.iceberg.apache.org/configuration/#rest-catalog
- Research: `docs/internal/research/lakekeeper.md` • `docs/internal/research/pyiceberg.md` §B.3
- Related: ADR-002 §6 (co-default rationale) • ADR-001 (atomicity boundary)

## 7. NEEDS VERIFICATION

- **Polaris `pyiceberg.RestCatalog` smoke-test parity.** Run §3 data-plane suite against a Polaris container; reconcile any divergence in commit semantics, snapshot handling, or error response shape with `docs/swap/pyiceberg.md` §3. "Config-flip only" is design intent until measured — highest-priority.
- **Polaris cold-start + memory baseline.** No Nucleus benchmark yet. Repeat under PoC #4 conditions; §5 risk 1 numbers are industry-typical Quarkus, not Polaris measurements.
- **Polaris management-API + vended-credentials default.** §2 assumes `/api/management/v1/...`; verify against https://github.com/apache/polaris/tree/main/spec. Lakekeeper 0.12.0 flipped default to `vended-credentials` (`docs/internal/research/lakekeeper.md` §9); Polaris default may differ — affects `X-Iceberg-Access-Delegation` handling.
- **Polaris OIDC matrix + Idempotency-Key.** Re-verify Keycloak / Entra-ID / Okta / Authentik / Google against Polaris (Authentik against either is `NEEDS VERIFICATION`); confirm Idempotency-Key + ETag support before production swap.
- **Cross-catalog migration script.** Users flipping v0.3 Lakekeeper → Polaris need warehouse-metadata pointers re-registered. Same data, same S3 path — pure metadata migration; build a `pyiceberg-cli register-table` equivalent.
