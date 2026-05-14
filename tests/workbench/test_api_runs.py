"""Tests for GET /api/runs and GET /api/runs/{run_id}/log.

Docs: https://fastapi.tiangolo.com/tutorial/testing/
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client():  # type: ignore[no-untyped-def]
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from nucleus.workbench.app import create_app

    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _clear_runs():  # type: ignore[no-untyped-def]
    """Ensure the run ring-buffer is empty before each test."""
    from nucleus.workbench.api.runs import _runs, _runs_by_id

    _runs.clear()
    _runs_by_id.clear()
    yield
    _runs.clear()
    _runs_by_id.clear()


def test_list_runs_empty(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_list_runs_returns_recorded_run(client) -> None:  # type: ignore[no-untyped-def]
    from nucleus.workbench.api.runs import record_run

    run_id = record_run(
        asset_key="raw.orders",
        status="success",
        duration_ms=123,
        rows_written=42,
    )
    r = client.get("/api/runs")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["run_id"] == run_id
    assert data[0]["asset_key"] == "raw.orders"
    assert data[0]["status"] == "success"


def test_run_dto_has_no_log_lines(client) -> None:  # type: ignore[no-untyped-def]
    """Log lines must not be included in the runs list response."""
    from nucleus.workbench.api.runs import record_run

    record_run(
        asset_key="staging.events",
        status="success",
        log_lines=["line1", "line2"],
    )
    r = client.get("/api/runs")
    assert r.status_code == 200
    run = r.json()[0]
    assert "log_lines" not in run


def test_log_stream_returns_lines(client) -> None:  # type: ignore[no-untyped-def]
    from nucleus.workbench.api.runs import record_run

    run_id = record_run(
        asset_key="marts.revenue",
        status="success",
        log_lines=["Starting materialization", "Written 100 rows"],
    )
    r = client.get(f"/api/runs/{run_id}/log")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "Starting materialization" in body
    assert "Written 100 rows" in body
    assert "[DONE]" in body


def test_log_stream_404_on_missing_run(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/runs/nonexistent-run-id/log")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "error_code" in detail


def test_runs_limit_param(client) -> None:  # type: ignore[no-untyped-def]
    from nucleus.workbench.api.runs import record_run

    for i in range(10):
        record_run(asset_key=f"raw.table{i}", status="success")

    r = client.get("/api/runs?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_runs_response_no_dagster_leak(client) -> None:  # type: ignore[no-untyped-def]
    from nucleus.workbench.api.runs import record_run

    record_run(asset_key="raw.test", status="running")
    r = client.get("/api/runs")
    text = r.text.lower()
    for banned in ("dagster", "opexecutioncontext", "job"):
        assert banned not in text
