# the pattern in tests/coordination/test_asset_materialization.py).
"""Tests for :mod:`nucleus.coordination.lineage` (the OL emitter).

Validates the v0.1 asset-level OpenLineage emitter per
``nucleus_architecture_v4.1.md`` §6.2 step 4 + ``docs/research/openlineage.md``
§5.1. Coverage:

    * Output-path resolution (``NUCLEUS_LINEAGE_DIR`` env var)
    * START / COMPLETE / FAIL emit construct correct event payloads
    * Per-run NDJSON file aggregation (append, not overwrite)
    * Emission failure is logged + swallowed (best-effort contract)
    * Soft-dep degradation when ``openlineage-python`` is absent
    * Parent run-id propagation per OL spec
    * AMA bookends — :func:`nucleus.coordination.asset_materialization.materialize_asset`
      drives the emitter via dry-run path so no Iceberg / Dagster IO
      manager wiring is required for v0.1.

Tests that read serialized NDJSON depend on ``openlineage-python`` and
skip when it is absent. Soft-dep + AMA-hook + error-class tests run
unconditionally so the regression net stays useful even before a
contributor runs ``pip install -e ".[dev]"``.
"""

from __future__ import annotations

import json
import logging
import pathlib
from collections.abc import Iterator
from typing import Any

import pytest

# Dagster (and its registry) is required for the AMA-hook integration tests
# below; matches the precondition in ``tests/coordination/test_asset_materialization.py``.
pytest.importorskip("dagster")

import nucleus
from nucleus.coordination import lineage
from nucleus.coordination.asset_materialization import materialize_asset
from nucleus.errors import NucleusError, NucleusLineageEmissionError
from nucleus.sdk.decorators import _reset_registry_for_tests

requires_openlineage = pytest.mark.skipif(
    not lineage._OL_AVAILABLE,
    reason="openlineage-python not installed; pin landed 2026-05-13",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


@pytest.fixture()
def lineage_dir(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Redirect lineage output to a per-test temp dir via ``NUCLEUS_LINEAGE_DIR``."""
    target = tmp_path / "lineage"
    monkeypatch.setenv("NUCLEUS_LINEAGE_DIR", str(target))
    return target


def _read_events(path: pathlib.Path) -> list[dict[str, Any]]:
    """Read an NDJSON file and return its events as parsed dicts."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


# UUID-format run_ids required by openlineage-python SDK (runid_check validates UUID format).
# Using all-hex patterns that are visually distinctive for each test group.
_RUN_ID_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_RUN_ID_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_RUN_ID_C = "cccccccc-cccc-cccc-cccc-cccccccccccc"
_RUN_ID_SHARED = "dddddddd-dddd-dddd-dddd-dddddddddddd"
_RUN_ID_CHILD = "11111111-1111-1111-1111-111111111111"
_RUN_ID_PARENT = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# Output directory resolution
# ---------------------------------------------------------------------------


class TestLineageDir:
    def test_env_var_overrides_default(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "custom"
        monkeypatch.setenv("NUCLEUS_LINEAGE_DIR", str(target))
        assert lineage._lineage_dir() == target

    def test_default_is_cwd_dot_nucleus_lineage(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("NUCLEUS_LINEAGE_DIR", raising=False)
        resolved = lineage._lineage_dir()
        assert resolved.parts[-2:] == (".nucleus", "lineage")


# ---------------------------------------------------------------------------
# Happy path — START / COMPLETE / FAIL events (require openlineage)
# ---------------------------------------------------------------------------


@requires_openlineage
class TestStartEvent:
    def test_emit_start_writes_ndjson(self, lineage_dir: pathlib.Path) -> None:
        lineage.emit_start(_RUN_ID_A, "marts.orders")
        path = lineage_dir / f"{_RUN_ID_A}.ndjson"
        assert path.exists(), "emit_start should create the per-run NDJSON file"
        events = _read_events(path)
        assert len(events) == 1
        event = events[0]
        assert event["eventType"] == "START"
        assert event["run"]["runId"] == _RUN_ID_A
        assert event["job"]["namespace"] == "nucleus"
        assert event["job"]["name"] == "marts.orders"
        assert event["producer"] == "https://nucleus.dev/v0.1"
        assert event.get("eventTime")


@requires_openlineage
class TestCompleteEvent:
    def test_emit_complete_writes_outcome_facet(self, lineage_dir: pathlib.Path) -> None:
        lineage.emit_complete(
            _RUN_ID_B,
            "marts.orders",
            snapshot_id="snap-12345",
            row_count=999,
            materialized_at="2026-05-13T12:00:00+00:00",
        )
        events = _read_events(lineage_dir / f"{_RUN_ID_B}.ndjson")
        assert len(events) == 1
        event = events[0]
        assert event["eventType"] == "COMPLETE"
        assert event["eventTime"] == "2026-05-13T12:00:00+00:00"
        facet = event["run"]["facets"]["_nucleusOutcome"]
        assert facet["snapshotId"] == "snap-12345"
        assert facet["rowCount"] == 999


@requires_openlineage
class TestFailEvent:
    def test_emit_fail_uses_standard_error_message_facet(
        self,
        lineage_dir: pathlib.Path,
    ) -> None:
        lineage.emit_fail(
            _RUN_ID_C,
            "marts.orders",
            error_code="NE2001",
            error_message="schema mismatch on column 'amount'",
        )
        events = _read_events(lineage_dir / f"{_RUN_ID_C}.ndjson")
        assert len(events) == 1
        event = events[0]
        assert event["eventType"] == "FAIL"
        em = event["run"]["facets"]["errorMessage"]
        assert em["message"] == "schema mismatch on column 'amount'"
        assert em["programmingLanguage"] == "python"
        # error_code rides as additional property per OL spec.
        assert em["errorCode"] == "NE2001"


@requires_openlineage
class TestPerRunAggregation:
    def test_start_then_complete_share_one_file(self, lineage_dir: pathlib.Path) -> None:
        run_id = _RUN_ID_SHARED
        lineage.emit_start(run_id, "marts.orders")
        lineage.emit_complete(
            run_id,
            "marts.orders",
            snapshot_id="snap-x",
            row_count=10,
            materialized_at="2026-05-13T12:00:00+00:00",
        )
        events = _read_events(lineage_dir / f"{run_id}.ndjson")
        assert [e["eventType"] for e in events] == ["START", "COMPLETE"]


# ---------------------------------------------------------------------------
# Parent run-id propagation
# ---------------------------------------------------------------------------


@requires_openlineage
class TestParentRunPropagation:
    def test_parent_run_id_attached_to_facet(self, lineage_dir: pathlib.Path) -> None:
        lineage.emit_start(_RUN_ID_CHILD, "marts.orders", parent_run_id=_RUN_ID_PARENT)
        events = _read_events(lineage_dir / f"{_RUN_ID_CHILD}.ndjson")
        assert events[0]["run"]["facets"]["parent"]["run"]["runId"] == _RUN_ID_PARENT


# ---------------------------------------------------------------------------
# Emission failure handling — best-effort, never raises (requires openlineage
# so we exercise the real construction path before forcing the failure)
# ---------------------------------------------------------------------------


@requires_openlineage
class TestEmissionFailureHandling:
    def test_unwritable_directory_logs_warning_no_raise(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def boom_mkdir(*_: Any, **__: Any) -> None:
            raise PermissionError("no write here")

        monkeypatch.setattr(pathlib.Path, "mkdir", boom_mkdir)
        with caplog.at_level(logging.WARNING, logger="nucleus.coordination.lineage"):
            lineage.emit_start("run-perm", "marts.orders")
        assert any("Lineage emission failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Soft-dep degradation — no openlineage needed; runs unconditionally
# ---------------------------------------------------------------------------


class TestSoftDependency:
    def test_emit_start_no_ol_logs_warning_no_file(
        self,
        lineage_dir: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(lineage, "_OL_AVAILABLE", False)
        with caplog.at_level(logging.WARNING, logger="nucleus.coordination.lineage"):
            lineage.emit_start("run-soft", "marts.orders")
        assert not (lineage_dir / "run-soft.ndjson").exists()
        assert any("openlineage-python not installed" in r.message for r in caplog.records)
        assert any("START" in r.message for r in caplog.records)

    def test_emit_complete_no_ol_logs_warning(
        self,
        lineage_dir: pathlib.Path,  # noqa: ARG002 -- fixture sets NUCLEUS_LINEAGE_DIR
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(lineage, "_OL_AVAILABLE", False)
        with caplog.at_level(logging.WARNING, logger="nucleus.coordination.lineage"):
            lineage.emit_complete(
                "run-soft",
                "marts.orders",
                snapshot_id="snap-x",
                row_count=1,
                materialized_at="2026-05-13T12:00:00+00:00",
            )
        assert any("COMPLETE" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AMA bookend integration — hooks fire in correct order with correct args
# (does not need openlineage thanks to monkey-patched emit functions)
# ---------------------------------------------------------------------------


class TestMaterializationHooks:
    @pytest.fixture()
    def trivial_asset_key(self) -> str:
        @nucleus.asset("staging.orders_lineage")
        def _staging_orders() -> None:
            return None

        return "staging.orders_lineage"

    def test_dry_run_emits_start_then_complete(
        self,
        trivial_asset_key: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[tuple[str, str, dict[str, Any]]] = []

        def spy(name: str):
            def fn(run_id: str, asset_key: str, **kw: Any) -> None:
                calls.append((name, run_id, {"asset_key": asset_key, **kw}))

            return fn

        monkeypatch.setattr(lineage, "emit_start", spy("start"))
        monkeypatch.setattr(lineage, "emit_complete", spy("complete"))
        monkeypatch.setattr(lineage, "emit_fail", spy("fail"))

        result = materialize_asset(trivial_asset_key, dry_run=True)

        assert [c[0] for c in calls] == ["start", "complete"]
        # Same run_id flows from START into COMPLETE.
        assert calls[0][1] == calls[1][1]
        # COMPLETE captures dry-run synthetic values per AMA convention.
        complete_kwargs = calls[1][2]
        assert complete_kwargs["snapshot_id"] == "dry-run"
        assert complete_kwargs["row_count"] == 0
        assert complete_kwargs["materialized_at"] == result.materialized_at.isoformat()

    def test_failure_emits_start_then_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, str, dict[str, Any]]] = []

        def spy(name: str):
            def fn(run_id: str, asset_key: str, **kw: Any) -> None:
                calls.append((name, run_id, {"asset_key": asset_key, **kw}))

            return fn

        monkeypatch.setattr(lineage, "emit_start", spy("start"))
        monkeypatch.setattr(lineage, "emit_complete", spy("complete"))
        monkeypatch.setattr(lineage, "emit_fail", spy("fail"))

        @nucleus.asset("staging.boom_lineage")
        def _boom() -> None:
            raise ValueError("schema mismatch on column 'amount'")

        with pytest.raises(NucleusError):
            materialize_asset("staging.boom_lineage")

        assert [c[0] for c in calls] == ["start", "fail"]
        fail_kwargs = calls[1][2]
        # error_code is the registered NE-code for NucleusSchemaError; the
        # error_message is the clean user-facing string, no Dagster classnames.
        assert fail_kwargs["error_code"] == "NE2001"
        assert "dagster" not in fail_kwargs["error_message"].lower()
        assert "schema mismatch" in fail_kwargs["error_message"].lower()

    def test_unknown_asset_does_not_emit_lineage(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(
            lineage,
            "emit_start",
            lambda *_a, **_kw: calls.append("start"),
        )
        monkeypatch.setattr(
            lineage,
            "emit_fail",
            lambda *_a, **_kw: calls.append("fail"),
        )
        with pytest.raises(NucleusError):
            materialize_asset("nope.missing")
        assert calls == []


# ---------------------------------------------------------------------------
# Error class wiring
# ---------------------------------------------------------------------------


class TestErrorClass:
    def test_lineage_emission_error_has_ne3010_code(self) -> None:
        assert NucleusLineageEmissionError.error_code == "NE3010"

    def test_lineage_emission_error_exported_from_nucleus_errors(self) -> None:
        import nucleus.errors as e

        assert "NucleusLineageEmissionError" in e.__all__
