"""Tests for GET /api/assets and GET /api/assets/{key}.

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
def _clean_registry():  # type: ignore[no-untyped-def]
    """Ensure the asset registry is empty before each test."""
    from nucleus.sdk.decorators import _reset_registry_for_tests

    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()


def test_list_assets_empty(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/assets")
    assert r.status_code == 200
    assert r.json() == []


def test_list_assets_with_registered_assets(client) -> None:  # type: ignore[no-untyped-def]
    import nucleus

    @nucleus.asset("raw.orders")
    def _raw_orders(_ctx: object) -> None:
        pass

    @nucleus.asset("staging.orders", deps=["raw.orders"])
    def _staging_orders(_ctx: object) -> None:
        pass

    r = client.get("/api/assets")
    assert r.status_code == 200
    data = r.json()
    keys = [a["key"] for a in data]
    assert "raw.orders" in keys
    assert "staging.orders" in keys


def test_asset_dto_shape(client) -> None:  # type: ignore[no-untyped-def]
    """Verify the AssetDTO structure for a registered asset."""
    import nucleus

    @nucleus.asset("raw.events", schedule="@daily")
    def _raw_events(_ctx: object) -> None:
        pass

    r = client.get("/api/assets")
    assert r.status_code == 200
    assets = {a["key"]: a for a in r.json()}
    a = assets["raw.events"]
    assert a["key"] == "raw.events"
    assert a["schedule"] == "0 0 * * *"  # @daily normalised
    assert isinstance(a["deps"], list)
    assert isinstance(a["checks"], list)
    assert isinstance(a["has_contract"], bool)


def test_get_asset_detail_ok(client) -> None:  # type: ignore[no-untyped-def]
    import nucleus

    @nucleus.asset("marts.revenue")
    def _marts_revenue(_ctx: object) -> None:
        pass

    r = client.get("/api/assets/marts.revenue")
    assert r.status_code == 200
    assert r.json()["key"] == "marts.revenue"


def test_get_asset_detail_not_found(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/assets/schema.nonexistent")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "error_code" in detail
    assert "user_message" in detail


def test_asset_response_no_dagster_leak(client) -> None:  # type: ignore[no-untyped-def]
    """No Dagster classnames in asset API responses (v4.1 §6.4)."""
    import nucleus

    @nucleus.asset("raw.test_leak")
    def _raw(_ctx: object) -> None:
        pass

    r = client.get("/api/assets")
    text = r.text.lower()
    for banned in ("dagster", "opexecutioncontext", "definitionsvalidation"):
        assert banned not in text, f"Dagster leak detected: {banned!r} in response"


def test_asset_with_check_shows_in_dto(client) -> None:  # type: ignore[no-untyped-def]
    import nucleus

    @nucleus.asset("staging.products")
    def _stg(_ctx: object) -> None:
        pass

    @nucleus.check("staging.products", severity="warn")
    def check_not_empty(_ctx: object) -> None:
        pass

    r = client.get("/api/assets/staging.products")
    assert r.status_code == 200
    asset = r.json()
    assert len(asset["checks"]) == 1
    assert asset["checks"][0]["severity"] == "warn"
    assert asset["checks"][0]["fn_name"] == "check_not_empty"
