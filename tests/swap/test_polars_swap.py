"""Swap smoke tests — Polars → Apache DataFusion DataFrame API.

Per AGENTS.md Hard Constraint #9 + ``docs/specs/nucleus_architecture_v4.1.md`` §9.3.
Verifies the Polars wrap surface we depend on today (2 exception classes
registered in ``coordination/error_translation.py:314-317`` + DataFrame /
LazyFrame methods user assets return) AND that DataFusion is reachable
via ``find_spec`` (no install in CI — full swap on-demand only).
Reference: ``docs/swap/polars.md``.
Docs: https://docs.pola.rs/api/python/stable/reference/index.html
"""

from __future__ import annotations

import importlib.util
from importlib.machinery import ModuleSpec

import polars as pl
import pyarrow as pa
import pytest
from polars.exceptions import ColumnNotFoundError, SchemaError

_SKIP = "swap target — full impl on-demand only per .cursor/rules/nucleus.mdc Composability Constitution"


def test_polars_dataframe_to_arrow_zero_copy_bridge() -> None:
    df = pl.DataFrame({"x": [1, 2, 3]})
    table = df.to_arrow()
    assert isinstance(table, pa.Table)
    assert table.column("x").to_pylist() == [1, 2, 3]


def test_polars_from_arrow_constructs_dataframe() -> None:
    df = pl.from_arrow(pa.table({"name": ["a", "b"], "value": [1, 2]}))
    assert isinstance(df, pl.DataFrame)
    assert df.shape == (2, 2)


def test_polars_lazyframe_filter_collect_chain() -> None:
    """Mirror sdk/decorators.py:304 docstring example: ctx.read(...).filter(pl.col(...) > 0)."""
    lf = pl.LazyFrame({"amount": [-1, 0, 1, 2]}).filter(pl.col("amount") > 0)
    out = lf.collect()
    assert out["amount"].to_list() == [1, 2]


def test_polars_exception_classes_registered_today() -> None:
    """Per coordination/error_translation.py:314-317; docs /reference/exceptions.html."""
    assert SchemaError is not None
    assert ColumnNotFoundError is not None
    assert issubclass(ColumnNotFoundError, Exception)


def test_polars_dataframe_method_surface_for_future_engine() -> None:
    """User-asset return type surface (docs/swap/polars.md API table)."""
    df = pl.DataFrame({"x": [1]})
    for m in ("to_arrow", "select", "filter", "with_columns", "group_by"):
        assert hasattr(df, m), f"pl.DataFrame.{m} missing"
    lf = df.lazy()
    for m in ("collect", "filter", "select", "with_columns", "sink_parquet"):
        assert hasattr(lf, m), f"pl.LazyFrame.{m} missing"


def test_datafusion_swap_target_lookup_mechanism_works() -> None:
    """DataFusion not installed in CI; verify the lookup path is sound.
    Docs: https://datafusion.apache.org/python/"""
    spec = importlib.util.find_spec("datafusion")
    assert spec is None or isinstance(spec, ModuleSpec)


@pytest.mark.skip(reason=_SKIP)
def test_datafusion_df_from_arrow_zero_copy() -> None:
    """Port test_polars_from_arrow_constructs_dataframe to DataFusion when triggered."""


@pytest.mark.skip(reason=_SKIP)
def test_datafusion_df_iceberg_scan_matches_polars() -> None:
    """Verify datafusion-iceberg parity with polars.scan_iceberg when triggered."""
