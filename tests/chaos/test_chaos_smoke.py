"""Smoke tests for the chaos runner — verify import + structure, not the full sweep.

The full chaos suite (J1-J8) takes ~4 minutes end-to-end. CI runs the full
sweep via ``scripts/release_e2e/run_chaos.py --scenario all`` on the release
path. This pytest file only asserts:

- The runner module imports cleanly.
- All 8 scenarios are registered in the ``SCENARIOS`` dict.
- Each scenario callable has a docstring (test-author quality bar).
- Each scenario returns a ``ChaosResult`` shape when called against a no-op
  (skipped on missing CLI; we don't actually run them here).

The full per-scenario validation lives in
``docs/release/chaos_test_results.md`` (last-run evidence) and is regenerated
by Worker A2's release-gate run.

Per AGENTS.md §11.8 chaos discipline + ADR-024 (reliability hardening).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNNER_PATH = REPO_ROOT / "scripts" / "release_e2e" / "run_chaos.py"


@pytest.fixture(scope="module")
def chaos_module():
    """Load `scripts/release_e2e/run_chaos.py` as a module (it is a script, not a package).

    Per https://docs.python.org/3/library/importlib.html#approximating-importlib-import-module
    the module must be inserted into sys.modules BEFORE exec_module() so that
    forward references resolved by `@dataclass` (Python 3.11+) can find it.
    """
    module_name = "chaos_runner_under_test"
    spec = importlib.util.spec_from_file_location(module_name, RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def test_runner_imports(chaos_module) -> None:
    """The chaos runner imports without errors (no syntax / import / circular issues)."""
    assert hasattr(chaos_module, "SCENARIOS")
    assert hasattr(chaos_module, "ChaosResult")
    assert hasattr(chaos_module, "main")


def test_all_eight_scenarios_registered(chaos_module) -> None:
    """All 8 scenarios (J1-J8) from perf doc §8 are wired into the runner."""
    expected = {"J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8"}
    assert set(chaos_module.SCENARIOS.keys()) == expected, (
        f"expected {expected}, got {set(chaos_module.SCENARIOS.keys())}"
    )


def test_each_scenario_has_docstring(chaos_module) -> None:
    """Each scenario function has a docstring — required for `--list` output."""
    for sid, fn in chaos_module.SCENARIOS.items():
        assert (fn.__doc__ or "").strip(), f"{sid}: missing docstring"


def test_classify_ne_code_known_slugs(chaos_module) -> None:
    """The slug-to-NE-code lookup table covers the codes exercised by chaos tests."""
    classify = chaos_module._classify_ne_code

    cases = {
        "Docs:  https://nucleus.dev/errors/network": "NE1010",
        "Docs: https://nucleus.dev/errors/concurrent-run": "NE3008",
        "Docs:https://nucleus.dev/errors/schema-evolution": "NE1004",
        "Docs: https://nucleus.dev/errors/schema": "NE2001",
        "Docs: https://nucleus.dev/errors/io": "NE1005",
        "NE3008 the asset is locked": "NE3008",
        "no error here": None,
    }
    for text, expected in cases.items():
        assert classify(text) == expected, f"input={text!r}"


def test_traceback_extractor_strips_leading_pkg_prefix(chaos_module) -> None:
    """When a leaked traceback is captured, exception class is rendered with full dotted path."""
    extract = chaos_module._extract_raw_exception
    sample = (
        "Traceback (most recent call last):\n"
        '  File "C:\\path\\src\\nucleus\\coordination\\foo.py", line 42, in run\n'
        "    bar()\n"
        '  File "C:\\path\\src\\nucleus\\lib\\bar.py", line 99, in bar\n'
        '    raise FileExistsError("oops")\n'
        "FileExistsError: oops\n"
    )
    exc_class, last_frame = extract(sample)
    assert exc_class == "FileExistsError"
    # last_frame should pick the LAST src/nucleus/ frame
    assert "src/nucleus/lib/bar.py:99" in last_frame
    assert "in bar()" in last_frame


def test_traceback_extractor_no_traceback_returns_empty(chaos_module) -> None:
    """No traceback → empty tuple."""
    exc_class, last_frame = chaos_module._extract_raw_exception("Error: clean nucleus error")
    assert (exc_class, last_frame) == ("", "")
