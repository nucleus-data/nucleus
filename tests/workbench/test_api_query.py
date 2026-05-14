"""Tests for POST /api/query.

Docs: https://fastapi.tiangolo.com/tutorial/testing/

Note: The query endpoint delegates to ``nucleus.ctx.sql`` which requires a
valid warehouse directory.  Tests that need a real warehouse use a temp dir
with a minimal Iceberg catalog (via pyiceberg filesystem catalog).
Tests that only need API surface validation use SQL that DuckDB handles
without catalog lookup (e.g. ``SELECT 1``).
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client():  # type: ignore[no-untyped-def]
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from nucleus.workbench.app import create_app

    return TestClient(create_app())


def test_query_empty_sql_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/query", json={"sql": "", "warehouse_dir": "/tmp/nonexistent"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "error_code" in detail


def test_query_whitespace_only_sql_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/query", json={"sql": "   ", "warehouse_dir": "/tmp/nonexistent"})
    assert r.status_code == 422


def test_query_missing_sql_field_returns_422(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/query", json={"warehouse_dir": "/tmp"})
    assert r.status_code == 422


def test_query_limit_validation(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Limit above 1000 is rejected by Pydantic."""
    r = client.post("/api/query", json={"sql": "SELECT 1", "limit": 9999, "warehouse_dir": str(tmp_path)})
    # Pydantic v2 returns 422 for constraint violations
    assert r.status_code == 422


def test_query_returns_structured_error_on_bad_sql(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A DuckDB parse error must come back as a NucleusError JSON, not a raw exception."""
    pytest.importorskip("duckdb")
    r = client.post("/api/query", json={"sql": "SELECT !! bad SQL", "warehouse_dir": str(tmp_path)})
    assert r.status_code in (400, 500)
    body = r.json()
    detail = body.get("detail", {})
    assert "error_code" in detail
    assert "user_message" in detail
    # Must NOT contain raw Python/DuckDB class names in the response.
    raw_text = str(body).lower()
    assert "duckdbpyconnection" not in raw_text
    assert "traceback" not in raw_text


def test_query_response_no_dagster_leak(client, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Error responses must not leak Dagster internals."""
    r = client.post("/api/query", json={"sql": "SELECT 1 / 0", "warehouse_dir": str(tmp_path)})
    text = r.text.lower()
    for banned in ("dagster", "opexecutioncontext", "definitionsvalidation"):
        assert banned not in text
