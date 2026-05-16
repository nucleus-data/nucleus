# Swap target: PyIceberg → iceberg-rust (via PyO3 binding)

> **Component status**: Tier 0 per `docs/specs/nucleus_architecture_v4.1.md` §3, §4. Iceberg the **format** is immortal; *the Python binding* is the swap unit.
> **Current default**: `pyiceberg[sql-sqlite,s3fs,duckdb]==0.11.1` per [ADR-012](../decisions/ADR-012-runtime-dependency-pin-matrix-v01.md) (the `0.8.1 → 0.11.x` migration tracked by ADR-003 landed during PoC #1 promotion).
> **Swap target**: [iceberg-rust](https://github.com/apache/iceberg-rust) via PyO3. Candidate: `iceberg>=0.4` Rust crate; Python entrypoint TBD — **NEEDS VERIFICATION** (§7).
> **Doc status**: INTERFACE-ONLY. Full adapter is built on-demand only per v4.1 §9.3.
> **Last touched**: 2026-05-14

## 1. Why swap might be needed (trigger conditions)

- [ ] **Vendor death** — Apache `iceberg-python` goes dormant (>12 mo no commits) AND iceberg-rust is the surviving Apache-governed Python path.
- [ ] **Performance regression** — `Table.append()` throughput >2x worse than 0.11.x, or `Catalog.commit_table()` p99 > ~500 ms.
- [ ] **Community demand** — ≥30% of user telemetry requests iceberg-rust.
- [ ] **Architectural constraint violation** — JVM dep, dropped Windows wheels (PoC #4 breaks), or relaxed atomic-commit contract (ADR-001).
- [ ] **Spec-v3 lag** — PyIceberg >12 mo behind spec v3 writes while iceberg-rust ships ahead, breaking the v0.5+ multimodal / `timestamp_ns` story (`docs/internal/research/pyiceberg.md` §4, §7).

(License pivot omitted: Apache-2.0 + ASF top-level governance makes it implausible.)

## 2. Swap interface

Only `coordination/asset_materialization.py` writes Iceberg (ADR-001); it calls this Protocol, never `import pyiceberg` directly.

```python
# Sketch — lands in src/nucleus/physics/iceberg_protocol.py
# Per v4.1 §4 (Physics), §6.2 (Asset Materialization Adapter), ADR-001.

from typing import Protocol, Any
import pyarrow as pa

class IcebergCatalogProtocol(Protocol):
    @classmethod
    def load(cls, name: str, **config: Any) -> "IcebergCatalogProtocol": ...
    def create_namespace(self, namespace: str, properties: dict | None = None) -> None: ...
    def create_table(self, identifier: str, schema: "IcebergSchema", **kwargs: Any) -> "IcebergTableProtocol": ...
    def load_table(self, identifier: str) -> "IcebergTableProtocol": ...
    def drop_table(self, identifier: str) -> None: ...
    def table_exists(self, identifier: str) -> bool: ...

class IcebergTableProtocol(Protocol):
    def append(self, df: pa.Table) -> None: ...
    def overwrite(self, df: pa.Table, overwrite_filter: Any = ...) -> None: ...
    def scan(self, **kwargs: Any) -> "IcebergScanProtocol": ...
    def refresh(self) -> None: ...
    def transaction(self) -> "IcebergTransactionProtocol": ...
    def update_schema(self) -> "UpdateSchemaProtocol": ...
    def snapshots(self) -> list["Snapshot"]: ...

class IcebergTransactionProtocol(Protocol):
    def append(self, df: pa.Table) -> None: ...
    def update_schema(self) -> "UpdateSchemaProtocol": ...
    def update_spec(self) -> "UpdateSpecProtocol": ...
    def commit_transaction(self) -> None: ...
```

Critical surface: `Catalog` (create/load/drop/exists + namespace), `Table.{append, overwrite, scan, refresh, update_schema, snapshots, transaction}`, `Transaction.{append, update_schema, update_spec, commit_transaction}`. Multi-table atomic commits are out of scope (ADR-001).

## 3. Smoke-test sketch (lives in CI)

`tests/swap/test_pyiceberg_swap.py` — contract-level only on a filesystem catalog (v0.1 baseline); REST-catalog parity is deferred to the on-demand full adapter.

```python
import pytest

@pytest.fixture(params=["pyiceberg", "iceberg_rust"])
def iceberg_impl(request):
    if request.param == "iceberg_rust" and not _has_iceberg_rust_adapter():
        pytest.skip("iceberg-rust adapter not built; swap doc only (v4.1 §9.3).")
    return _load_iceberg_catalog(request.param)

def test_create_namespace_idempotent(iceberg_impl): ...
def test_create_table_with_schema_roundtrip(iceberg_impl): ...
def test_append_arrow_table_produces_snapshot(iceberg_impl): ...
def test_scan_round_trip_preserves_types(iceberg_impl): ...
def test_table_refresh_sees_external_commit(iceberg_impl): ...
def test_commit_conflict_raises_translatable_error(iceberg_impl): ...
def test_transaction_commits_atomically(iceberg_impl): ...
def test_update_schema_adds_nullable_column(iceberg_impl): ...
```

## 4. Swap-cost estimate (when trigger fires)

| Phase | Effort | Owner |
|---|---|---|
| Protocol formalization + PyIceberg adapter cleanup | 3 d | platform |
| iceberg-rust PyO3 evaluation (or thin wrapper) + `IcebergCatalog` adapter | 11 d | platform |
| `Table.append` / `scan` zero-copy + transaction + schema-evolution coverage | 9 d | platform |
| REST catalog parity (Lakekeeper / Polaris, v0.3+ users) | 5 d | platform |
| Error translation + Win/macOS/Linux smoke (ADR-001 kill-9 stress) | 6 d | platform |
| Documentation + migration guide | 2 d | platform |
| **Total LOC** | **~3000-5000 LOC** | — |
| **Total calendar time** | **~7-8 weeks** | — |

**Most uncertain estimate of the three swap docs**: iceberg-rust is younger than DataFusion and far younger than the mini-scheduler in design. Every row could move ±50% once evaluation runs.

## 5. Critical risks specific to this swap

1. **Write-path maturity.** `docs/internal/research/pyiceberg.md` §3 (2026-05) tracked iceberg-rust as "fewer catalog backends, less mature write path." `Table.append` / `overwrite` parity against our partition transforms + sort-order / partition evolution (PyIceberg 0.11 per ADR-003 §1) must be re-verified at trigger time.
2. **Schema-evolution parity.** PyIceberg's `UpdateSchema` enforces ID-stable rules (add nullable, drop, rename, widen; reject narrow / nullable→required — `docs/internal/research/pyiceberg.md` §7). iceberg-rust must enforce the same — else v4.1 §6.4 contract enforcement leaks.
3. **REST catalog feature gap.** iceberg-rust's REST client may not implement every endpoint PyIceberg does (especially newer scan-planning); Lakekeeper / Polaris (v0.3+) users would feel this immediately.
4. **Python binding ergonomics + Windows atomicity.** Whether iceberg-rust has a first-class Python surface is unsettled (§7); `Table.scan().to_duckdb(name)` / `.to_polars()` (`docs/internal/research/pyiceberg.md` §5) may need re-implementation by us. Separately, `std::fs::rename` has its own Windows semantics, so the §4 kill-9 stress (per ADR-001's #1 risk) is non-optional.

## 6. Cited docs

- Current (PyIceberg): https://py.iceberg.apache.org/ • https://py.iceberg.apache.org/api/#exceptions
- Iceberg spec: https://iceberg.apache.org/spec/ • https://iceberg.apache.org/spec/#commit-concurrency (ADR-001)
- Target (iceberg-rust): https://github.com/apache/iceberg-rust • https://rust.iceberg.apache.org/ (verify at trigger time)
- Research / decisions: `docs/internal/research/pyiceberg.md` • `docs/internal/research/duckdb.md` §8 • `docs/internal/research/dlt.md` §6 • ADR-001 • ADR-003

## 7. NEEDS VERIFICATION

- **Canonical iceberg-rust Python entrypoint** — sibling PyPI package, in-tree PyO3, or none at all: TBD. If absent, §4 grows by 2-3 weeks.
- **REST catalog endpoint coverage** — whether iceberg-rust supports the scan-planning endpoint PyIceberg 0.11 added (`docs/internal/research/pyiceberg.md` §B.3); v0.3+ users otherwise regress.
- **Windows atomic commit** — re-validate with the ADR-001 kill-9 harness against `std::fs::rename` semantics before announcing the swap.
- **Exception class structure** — whether iceberg-rust surfaces `NoSuchTableError`, `CommitFailedException`, `CommitStateUnknownException`, `ValidationError` (`docs/internal/research/pyiceberg.md` §6) as distinct classes (1:1) or collapses to one `IcebergError` (lossy). Translator design depends on this.
- **PyArrow envelope + dlt blocker** — iceberg-rust must piggyback on `pyarrow==18.1.0` (else zero-copy breaks) AND satisfy `dlt[pyiceberg]`'s Iceberg destination (`docs/internal/research/dlt.md` §7). A swap before v0.3 forces the dlt ADR to be re-scoped.
