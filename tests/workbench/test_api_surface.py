"""Backend API surface tests for Workbench (ADR-016 Week 1 scaffold).

Uses FastAPI TestClient per
https://fastapi.tiangolo.com/tutorial/testing/
"""

from __future__ import annotations

import json
import re

import pytest

from nucleus import __version__ as nucleus_version

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdagster\b", re.IGNORECASE),
    re.compile(r"\bop\b", re.IGNORECASE),
    re.compile(r"Code\s+Location", re.IGNORECASE),
    re.compile(r"\bDefinitions\b", re.IGNORECASE),
)


def _response_has_no_banned(text: str) -> bool:
    return not any(p.search(text) for p in _PATTERNS)


@pytest.fixture
def workbench_client():  # type: ignore[no-untyped-def]
    pytest.importorskip("fastapi")
    # Docs: https://fastapi.tiangolo.com/tutorial/testing/
    from fastapi.testclient import TestClient

    from nucleus.workbench.app import create_app

    return TestClient(create_app())


def test_health_ok(workbench_client) -> None:
    r = workbench_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == nucleus_version


def test_version_ok(workbench_client) -> None:
    r = workbench_client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert body["nucleus"] == nucleus_version
    assert body["workbench_api"] == "v0.2-scaffold"


def test_unknown_route_404(workbench_client) -> None:
    r = workbench_client.get("/api/does-not-exist")
    assert r.status_code == 404


def test_create_app_returns_fastapi() -> None:
    pytest.importorskip("fastapi")
    # Docs: https://fastapi.tiangolo.com/tutorial/first-steps/
    from fastapi import FastAPI

    from nucleus.workbench.app import create_app

    assert isinstance(create_app(), FastAPI)


def test_version_payload_string_free_of_orchestrator_surface_leaks(
    workbench_client,
) -> None:
    """Regression lock for v4.1 §6.5-style vocabulary at the HTTP boundary."""
    r = workbench_client.get("/api/version")
    raw = r.text
    assert _response_has_no_banned(raw)
    assert _response_has_no_banned(json.dumps(r.json()))


def test_health_includes_nucleus_version_string(workbench_client) -> None:
    r = workbench_client.get("/api/health")
    assert r.json()["version"] == nucleus_version
