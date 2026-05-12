"""PoC #1 tests — 5 cases, not 50. Iterate from here.

Verifies the ``translate()`` function:
    - Idempotent for an existing NucleusError
    - Maps a ConnectionError raised inside an asset → NucleusSourceConnectionError
    - Maps a ValueError("schema...") → NucleusSchemaError
    - Falls back to NucleusInternalError for unknown exception types
    - Renders without leaking any ``dagster`` substring (the §2.5 leak check)
"""

from __future__ import annotations

import pytest

dagster = pytest.importorskip("dagster")

from nucleus.errors import (
    NucleusInternalError,
    NucleusSchemaError,
    NucleusSourceConnectionError,
)
from poc.p1_error_translation.translator import translate


def _run_failing_asset(side_effect: BaseException) -> BaseException:
    """Helper — define an asset that raises ``side_effect``, materialize, return
    the wrapped exception."""

    @dagster.asset
    def boom() -> int:
        raise side_effect

    try:
        dagster.materialize([boom])
    except Exception as e:
        return e

    raise AssertionError("materialize() was expected to raise")


def test_idempotent_on_nucleus_error() -> None:
    existing = NucleusSchemaError("already typed")
    assert translate(existing) is existing


def test_connection_error_in_asset_translates_to_source_connection() -> None:
    captured = _run_failing_asset(ConnectionError("host unreachable"))
    out = translate(captured)

    assert isinstance(out, NucleusSourceConnectionError)
    assert "host unreachable" in out.user_message
    assert out.__cause__ is captured


def test_schema_value_error_translates_to_schema_error() -> None:
    captured = _run_failing_asset(ValueError("schema mismatch on column 'amount'"))
    out = translate(captured)

    assert isinstance(out, NucleusSchemaError)
    assert "schema mismatch" in out.user_message.lower()


def test_unknown_falls_back_to_internal_error() -> None:
    captured = _run_failing_asset(ZeroDivisionError("divide by zero"))
    out = translate(captured)

    assert isinstance(out, NucleusInternalError)
    assert out.__cause__ is captured


def test_rendered_output_has_no_dagster_leak() -> None:
    captured = _run_failing_asset(ConnectionError("host unreachable"))
    rendered = translate(captured).rendered()

    assert "dagster" not in rendered.lower(), (
        f"Dagster type leaked into rendered output:\n{rendered}"
    )
