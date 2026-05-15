"""Shared pytest configuration & fixtures for the Nucleus test suite.

Conventions:
- Mirror src/ layout (engineering.md §6.2).
- Marker registration: see pyproject.toml [tool.pytest.ini_options] markers.
- No mocking of internal Nucleus code; mock only external services.
  (engineering.md §6.5)

This file is intentionally small at v0.0.0 — fixtures land here as we
add layers (e.g. ``iceberg_catalog`` fixture lands with the physics layer).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# Make ``src/nucleus`` importable for editable installs and direct runs.
# pip install -e ".[dev]" handles this normally; this guards "python -m pytest"
# without a prior install.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# ============================================================================
# Marker behavior — automatic skip when conditions not met
# ============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001 — reserved for future use
    items: list[pytest.Item],
) -> None:
    """Auto-skip ``@pytest.mark.integration`` tests when env vars are not set.

    Tests that explicitly carry ``@pytest.mark.integration`` (per the
    ``[tool.pytest.ini_options] markers`` list in ``pyproject.toml``)
    require real external services (Postgres, MinIO).  When their env
    vars are absent we skip rather than fail.

    Detection is marker-based, NOT path-based — placing a test in
    ``tests/integration/`` no longer triggers the auto-skip unless it
    also carries the marker.  This keeps in-process integration tests
    (e.g. the Dagster ⇄ mini-scheduler swap proof) runnable without
    Postgres credentials.
    """
    integration_required_env = ("NUCLEUS_TEST_PG_DSN",)
    has_integration_env = all(os.environ.get(v) for v in integration_required_env)

    skip_integration = pytest.mark.skip(
        reason="Integration env vars not set "
        f"(need: {', '.join(integration_required_env)}). "
        'Set them or run with `pytest -m "not integration"`.'
    )
    for item in items:
        has_marker = any(
            marker.name == "integration" for marker in item.iter_markers()
        )
        if has_marker and not has_integration_env:
            item.add_marker(skip_integration)


# ============================================================================
# Generic fixtures
# ============================================================================


@pytest.fixture()
def tmp_warehouse(tmp_path: Path) -> Path:
    """A clean temporary warehouse directory for an Iceberg catalog.

    Each test gets its own. Cleaned up automatically by pytest's
    ``tmp_path`` fixture.
    """
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    return warehouse


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip all ``NUCLEUS_*`` env vars for a deterministic test run."""
    for key in [k for k in os.environ if k.startswith("NUCLEUS_")]:
        monkeypatch.delenv(key, raising=False)
    yield
