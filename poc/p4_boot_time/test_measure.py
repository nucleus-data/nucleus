"""PoC #4 tests — verify the harness without requiring real MinIO/Dagster
running. Six dry-run cases covering ``phase()`` recording semantics,
``measure_imports`` / ``measure_minio_health`` / ``measure_idle_ram``
shape, and ``main()`` exit-code on a busted cold boot."""

from __future__ import annotations

import urllib.error
from typing import Any
from unittest.mock import patch

import pytest

from poc.p4_boot_time.measure import (
    PhaseResult,
    main,
    measure_idle_ram,
    measure_imports,
    measure_minio_health,
    phase,
)


def test_phase_decorator_records_success() -> None:
    results: list[PhaseResult] = []
    with phase("clean", results, target_s=1.0):
        pass
    assert len(results) == 1
    assert results[0].name == "clean"
    assert results[0].ok is True
    assert results[0].duration_s >= 0.0
    assert results[0].passed_target is True


def test_phase_decorator_records_failure_and_reraises() -> None:
    results: list[PhaseResult] = []
    with pytest.raises(ValueError, match="kaboom"), phase("boom", results):
        raise ValueError("kaboom")
    assert len(results) == 1
    assert results[0].ok is False
    assert "kaboom" in results[0].detail
    assert results[0].passed_target is False


def test_imports_phase_returns_positive_duration() -> None:
    duration, missing = measure_imports()
    assert duration > 0.0
    # Don't assert ``missing == []`` — a fresh CI env may not have every
    # heavy dep installed yet. Shape check only.
    assert isinstance(missing, list)


def test_minio_health_handles_unreachable() -> None:
    def _boom(*_a: Any, **_kw: Any) -> Any:
        raise urllib.error.URLError("Connection refused")

    with patch("poc.p4_boot_time.measure.urllib.request.urlopen", side_effect=_boom):
        duration, healthy, detail = measure_minio_health(timeout_s=0.1)
    assert duration >= 0.0
    assert healthy is False
    assert "URLError" in detail or "Connection refused" in detail


def test_idle_ram_reports_positive_mb_or_unavailable() -> None:
    rss_mb, source = measure_idle_ram()
    # Either real measurement (>0 MB on any reasonable platform) OR the
    # documented fallback (-1.0 with a clear "no measurement available").
    assert rss_mb > 0 or source.startswith("no measurement")


def test_main_returns_nonzero_when_cold_boot_exceeds_target() -> None:
    fake = [PhaseResult(name="imports", duration_s=12.0, ok=True, target_s=3.0)]
    with (
        patch(
            "poc.p4_boot_time.measure.measure_total_cold_boot",
            return_value=(15.0, fake),
        ),
        patch(
            "poc.p4_boot_time.measure.measure_idle_ram",
            return_value=(100.0, "patched"),
        ),
    ):
        rc = main()
    assert rc == 1
