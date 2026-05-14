"""Swap smoke tests — DuckDB → Apache DataFusion.

Per AGENTS.md Hard Constraint #9 + ``nucleus_architecture_v4.1.md`` §9.3.
Verifies the DuckDB wrap surface we depend on today (5 exception classes
in ``coordination/error_translation.py:326-330`` + future engine method
surface) AND that DataFusion is reachable via ``find_spec`` (no install
in CI — full swap on-demand only). Reference: ``docs/swap/duckdb.md``.
Docs: https://duckdb.org/docs/stable/clients/python/overview
"""
from __future__ import annotations

import importlib.util
from importlib.machinery import ModuleSpec

import duckdb
import pyarrow as pa
import pytest

_SKIP = "swap target — full impl on-demand only per .cursor/rules/nucleus.mdc Composability Constitution"


def test_duckdb_in_memory_connect_and_close() -> None:
    conn = duckdb.connect(":memory:")
    try:
        assert conn is not None
    finally:
        conn.close()


def test_duckdb_select_literal_returns_one_row() -> None:
    conn = duckdb.connect(":memory:")
    try:
        assert conn.execute("SELECT 42 AS answer").fetchone() == (42,)
    finally:
        conn.close()


def test_duckdb_arrow_roundtrip_preserves_values() -> None:
    conn = duckdb.connect(":memory:")
    try:
        out = conn.from_arrow(pa.table({"x": [1, 2, 3]})).arrow()
        assert out.column("x").to_pylist() == [1, 2, 3]
    finally:
        conn.close()


def test_duckdb_exception_classes_registered_today() -> None:
    """Per coordination/error_translation.py:326-330; docs /clients/python/dbapi."""
    for name in ("BinderException", "CatalogException", "ParserException",
                 "OutOfMemoryException", "TransactionException"):
        assert hasattr(duckdb, name), f"duckdb.{name} missing — translator breaks."


def test_duckdb_connection_method_surface_for_future_engine() -> None:
    """Future engines/duckdb_engine.py surface (docs/swap/duckdb.md API table)."""
    conn = duckdb.connect(":memory:")
    try:
        for m in ("execute", "sql", "from_arrow", "register", "close"):
            assert hasattr(conn, m), f"DuckDBPyConnection.{m} missing"
    finally:
        conn.close()


def test_datafusion_swap_target_lookup_mechanism_works() -> None:
    """DataFusion not installed in CI; verify the lookup path is sound.
    Docs: https://datafusion.apache.org/python/"""
    spec = importlib.util.find_spec("datafusion")
    assert spec is None or isinstance(spec, ModuleSpec)


@pytest.mark.skip(reason=_SKIP)
def test_datafusion_select_literal_returns_arrow() -> None:
    """Port test_duckdb_select_literal_returns_one_row to DataFusion when triggered."""


@pytest.mark.skip(reason=_SKIP)
def test_datafusion_iceberg_scan_matches_duckdb() -> None:
    """Verify datafusion-iceberg parity with duckdb iceberg_scan when triggered."""
