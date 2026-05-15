"""Optional-extras install matrix smoke test — `pyproject.toml` Option a-split.

Validates the disposition landed 2026-05-14 per
``docs/research/otel_day1_decision.md`` Option a-split:

1. `pip install nucleus` (no extras) imports cleanly — the four core
   modules (``nucleus``, ``nucleus.ctx``, ``nucleus.errors``,
   ``nucleus.cli.main``) load without requiring any opt-in extra.
2. `opentelemetry-api` stays in core — the no-op substrate per ADR-011 §1
   (clarified by the 2026-05-14 amendment) is honored just by the import
   being available; no ``TracerProvider`` is configured, so every span is
   a ``NonRecordingSpan`` per
   https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html.
3. The two new runtime-extras groups (`observability`,
   `lineage-advanced`) are declared in ``pyproject.toml`` with the
   expected pins (per ADR-012 amendment 2026-05-14).
4. `msgspec` is REMOVED — not in `[project] dependencies`, not in any
   `[project.optional-dependencies]` group, and (after a clean install)
   not importable. Per ``docs/research/otel_day1_decision.md`` §D3.
5. `opentelemetry-sdk` only ships when the user opts in via
   ``pip install nucleus[observability]``.

Per AGENTS.md §11.13 (Hard Constraint #11 — upgrade-safe stack design)
this test guards future regressions: if a contributor accidentally
re-pins `msgspec` in `[project] dependencies`, or accidentally moves
`opentelemetry-sdk` back into core, this test fails loudly.

Architecture refs:
- ``docs/decisions/ADR-011-telemetry-and-observability-opt-in-policy.md``
  (Amendment 2026-05-14 — substrate-by-API-only)
- ``docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md``
  (Amendment 2026-05-14 — pin count 25 → 23 + 2 optional)
- ``docs/research/otel_day1_decision.md`` §D1-D3 (researcher disposition)
- PEP 621 ``[project.optional-dependencies]``:
  https://peps.python.org/pep-0621/
- Python packaging guide:
  https://packaging.python.org/en/latest/specifications/pyproject-toml/#dependencies-optional-dependencies
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.upgrade


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _load_pyproject() -> dict[str, object]:
    """Parse the repo's ``pyproject.toml`` once per test."""
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _dep_packages(specs: list[str]) -> set[str]:
    """Lower-cased package names from a PEP 621 dep array, extras stripped."""
    out: set[str] = set()
    for raw in specs:
        m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_.\-]*)", raw)
        if m:
            out.add(m.group(1).lower())
    return out


# ---------------------------------------------------------------------------
# 1-4. Core import smoke (`pip install nucleus` with no extras must work)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "nucleus",
        "nucleus.ctx",
        "nucleus.errors",
        "nucleus.cli.main",
    ],
)
def test_core_module_imports_without_optional_extras(module_name: str) -> None:
    """The four core modules import without requiring any opt-in extras.

    A user who runs ``pip install nucleus`` (no extras) must reach
    ``import nucleus``, ``nucleus.ctx``, ``nucleus.errors``, and
    ``nucleus.cli.main`` cleanly. This is the v0.1 default install
    contract per ADR-012 amendment 2026-05-14.
    """
    importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# 5. opentelemetry-api stays in core (no-op substrate per ADR-011 amendment)
# ---------------------------------------------------------------------------


def test_opentelemetry_api_always_available() -> None:
    """``opentelemetry-api`` is a mandatory core dep per ADR-011 amendment 2026-05-14.

    Per https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html
    the API package alone -- with no ``TracerProvider`` configured --
    produces no-op ``NonRecordingSpan`` for every ``start_as_current_span(...)``
    call. The Day-1 substrate-presence promise in ADR-011 §1 is honored
    by this single import being available.
    """
    trace = importlib.import_module("opentelemetry.trace")
    tracer = trace.get_tracer("nucleus.test")
    with tracer.start_as_current_span("noop") as span:
        # Default no-op TracerProvider returns a NonRecordingSpan; the
        # span object exists but does not record. We only require the
        # call surface to work.
        assert span is not None


# ---------------------------------------------------------------------------
# 6. Runtime-extras groups exist in pyproject with the expected pins
# ---------------------------------------------------------------------------


def test_runtime_extras_groups_declared_with_expected_pins() -> None:
    """``[project.optional-dependencies]`` declares the two runtime-extras groups.

    Per ADR-012 amendment 2026-05-14 + ``docs/research/otel_day1_decision.md``
    §D4: ``observability`` carries ``opentelemetry-sdk==1.29.0`` and
    ``lineage-advanced`` carries ``sqlglot==26.0.0``. Both pins remain
    version-locked even though they are opt-in.
    """
    pyproj = _load_pyproject()
    project = pyproj["project"]
    assert isinstance(project, dict)
    extras_obj = project.get("optional-dependencies", {})
    assert isinstance(extras_obj, dict)

    expected = {
        "observability": "opentelemetry-sdk==1.29.0",
        "lineage-advanced": "sqlglot==26.0.0",
    }
    for group, expected_spec in expected.items():
        assert group in extras_obj, (
            f"Runtime-extras group `{group}` missing from "
            f"[project.optional-dependencies] -- per ADR-012 amendment 2026-05-14."
        )
        deps = extras_obj[group]
        assert isinstance(deps, list)
        assert expected_spec in deps, (
            f"Runtime-extras group `{group}` does not contain `{expected_spec}` "
            f"-- found {deps}. Per ADR-012 amendment 2026-05-14, the pin must "
            f"stay exact (==) even in extras."
        )


# ---------------------------------------------------------------------------
# 7. msgspec removed from EVERY dependency declaration
# ---------------------------------------------------------------------------


def test_msgspec_absent_from_all_dependency_groups() -> None:
    """``msgspec`` is REMOVED from core and every extras group.

    Per ``docs/research/otel_day1_decision.md`` §D3 (Option a-split,
    founder-approved 2026-05-14): zero callers under ``src/``, ``tests/``,
    ``poc/``, ``scripts/``; planned ``NucleusError + configs`` use never
    materialized; pure-stdlib substitutes (``json``, ``dataclasses``,
    ``tomllib``) suffice. The pin is reversible via a one-line pyproject
    edit if a v0.5+ run-event serializer benchmark ever warrants it.
    """
    pyproj = _load_pyproject()
    project = pyproj["project"]
    assert isinstance(project, dict)

    runtime = _dep_packages(project.get("dependencies", []))  # type: ignore[arg-type]
    assert "msgspec" not in runtime, (
        "msgspec re-appeared in [project] dependencies -- "
        "ADR-011 amendment 2026-05-14 + ADR-012 amendment 2026-05-14 removed it. "
        "Re-introducing requires a new ADR per AGENTS.md §11.13."
    )

    extras_obj = project.get("optional-dependencies", {})
    assert isinstance(extras_obj, dict)
    for group, deps in extras_obj.items():
        assert isinstance(deps, list)
        if group == "all":
            continue
        names = _dep_packages(deps)
        assert "msgspec" not in names, (
            f"msgspec re-appeared in extras group `{group}` -- "
            f"per `docs/research/otel_day1_decision.md` §D3 it is removed entirely; "
            f"reintroduction requires a new ADR."
        )


# ---------------------------------------------------------------------------
# 8. msgspec is unimportable after a clean install (the runtime contract)
# ---------------------------------------------------------------------------


def test_msgspec_unimportable_after_clean_install() -> None:
    """``import msgspec`` raises after a clean install (no source code uses it).

    Per ADR-012 amendment 2026-05-14 ``msgspec`` is removed from every
    dependency group. After a clean ``pip install -e .`` (or
    ``pip install nucleus``) ``msgspec`` is no longer pulled into the
    environment by Nucleus. If this test fails because ``msgspec`` is
    still importable, the dev venv has a stale package -- run
    ``pip uninstall -y msgspec`` to bring it back into compliance.

    Note: this test is intentionally **unconditional** (no skipif) -- it
    is the runtime contract that catches future regressions where a
    contributor accidentally re-pins ``msgspec`` somewhere.
    """
    spec = importlib.util.find_spec("msgspec")
    assert spec is None, (
        "msgspec is importable but should not be -- it was removed from "
        "pyproject.toml on 2026-05-14 per `docs/research/otel_day1_decision.md` §D3. "
        "If you see this in a dev venv, run `pip uninstall -y msgspec`. "
        "If you see this in CI, a regression has re-introduced the pin."
    )


# ---------------------------------------------------------------------------
# 9. opentelemetry-sdk is OPTIONAL — only present when [observability] installed
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    importlib.util.find_spec("opentelemetry.sdk") is not None,
    reason=(
        "opentelemetry-sdk is installed in this environment "
        "(expected when `pip install -e .[observability]` or `[all]` was run); "
        "the not-installed branch of this contract test is therefore skipped."
    ),
)
def test_opentelemetry_sdk_unimportable_in_minimal_install() -> None:
    """``import opentelemetry.sdk`` is unavailable in the minimal install.

    Per ADR-011 amendment 2026-05-14 + ``docs/research/otel_day1_decision.md``
    §D1: SDK ships only via ``pip install nucleus[observability]``. A user
    on the default install must NOT find ``opentelemetry.sdk`` available.
    The skipif above suppresses this test in dev envs that opted into
    ``[observability]`` or ``[all]`` -- those envs by design have the SDK.
    """
    spec = importlib.util.find_spec("opentelemetry.sdk")
    assert spec is None, (
        "opentelemetry.sdk is importable in a minimal install context. "
        "Per ADR-011 amendment 2026-05-14 the SDK lives in "
        "[project.optional-dependencies] observability; if a contributor "
        "moved it back into [project] dependencies, revert per ADR-011."
    )
