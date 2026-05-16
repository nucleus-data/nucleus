"""Swap smoke tests — PyIceberg → iceberg-rust (PyO3 binding).
Per AGENTS.md Hard Constraint #9 + ``docs/specs/nucleus_architecture_v4.1.md`` §9.3.
Exercises today's wrap surface (filesystem SQL catalog + the 7 ``Table``
methods consumed by ``coordination/asset_materialization.py`` and
``ctx/copy_from.py``); verifies iceberg-rust is installable OR doc'd as
a gap (no install in CI — full swap on-demand only).
Reference: ``docs/internal/swap/pyiceberg.md`` · Docs: https://py.iceberg.apache.org/api/
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pyarrow as pa
import pytest
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType

_SKIP = "swap target — full impl on-demand only per .cursor/rules/nucleus.mdc Composability Constitution"
_SWAP_DOC = Path("docs/internal/swap/pyiceberg.md")


def _open_fs_catalog(warehouse: Path):
    # Filesystem SQL catalog; Windows URI fix mirrors ctx/copy_from.py. Docs: https://py.iceberg.apache.org/api/catalog/ · /api/table/ · /configuration/#sql-catalog
    warehouse.mkdir(parents=True, exist_ok=True)
    return load_catalog(
        "default",
        type="sql",
        uri=f"sqlite:///{(warehouse / 'catalog.db').resolve().as_posix()}",
        warehouse=f"file://{warehouse.resolve().as_posix()}",
    )


def test_live_load_filesystem_catalog(tmp_path: Path) -> None:
    cat = _open_fs_catalog(tmp_path)
    assert cat is not None and hasattr(cat, "create_namespace")


def test_live_namespace_create_drop(tmp_path: Path) -> None:
    cat = _open_fs_catalog(tmp_path)
    cat.create_namespace("ns")
    assert ("ns",) in list(cat.list_namespaces())
    cat.drop_namespace("ns")


def test_live_table_append_scan_roundtrip(tmp_path: Path) -> None:
    cat = _open_fs_catalog(tmp_path)
    cat.create_namespace("ns")
    schema = Schema(
        NestedField(1, "id", LongType(), required=False),
        NestedField(2, "name", StringType(), required=False),
    )
    tbl = cat.create_table(("ns", "t"), schema=schema)
    tbl.append(pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]}))
    out = tbl.scan().to_arrow()
    assert out.num_rows == 3 and set(out.column_names) == {"id", "name"}


def test_iceberg_rust_swap_target_documented() -> None:
    assert _SWAP_DOC.exists() and "iceberg-rust" in _SWAP_DOC.read_text(encoding="utf-8")


def test_iceberg_rust_python_binding_findable() -> None:
    installable = importlib.util.find_spec("iceberg_rust") is not None
    doc_flags_gap = "NEEDS VERIFICATION" in _SWAP_DOC.read_text(encoding="utf-8")
    assert installable or doc_flags_gap, "swap target neither installable nor doc'd as gap"


def test_pyiceberg_critical_surface_present() -> None:
    from pyiceberg.table import Table  # per docs/internal/swap/pyiceberg.md §2

    for m in (
        "append",
        "overwrite",
        "scan",
        "refresh",
        "update_schema",
        "snapshots",
        "transaction",
    ):
        assert hasattr(Table, m), f"pyiceberg.table.Table.{m} missing — swap doc lies."


@pytest.mark.skip(
    reason=_SKIP
    + "; trigger: pyiceberg dormant >12mo / commit_table p99 >500ms / spec-v3 lag >12mo / JVM dep"
)
def test_full_swap_to_iceberg_rust_parity() -> None:
    """Port test_live_table_append_scan_roundtrip to iceberg-rust adapter when triggered."""


@pytest.mark.skip(
    reason="REST catalog parity deferred per docs/internal/swap/pyiceberg.md §3; filesystem is v0.1 baseline; re-enable when Lakekeeper lands in v0.3"
)
def test_rest_catalog_parity_lakekeeper_polaris() -> None:
    """Verify create/load/drop/append parity over REST when Lakekeeper integration lands."""
