"""Regression tests for the CLI lazy-import discipline.

Per ``docs/internal/research/performance_reliability_targets.md`` §10 #4 +
``scripts/check_lazy_imports.py``: heavy libraries (litellm, dlt,
dagster, pyiceberg, polars, duckdb, s3fs, psycopg, fastapi, uvicorn,
sqlalchemy, croniter) must NOT be loaded simply by importing
``nucleus.cli.main``. They are lazy-loaded inside the command handler
that needs them.

These tests cover:

* In-process: ``import nucleus.cli.main`` does not pull any banned
  module into ``sys.modules``.
* Subprocess: a fresh interpreter that imports ``nucleus.cli.main``
  also has none of the banned modules loaded.
* Subprocess: ``nucleus --version`` completes well under one second
  on the reference hardware (a sanity check; the strict 500 ms gate
  lives in ``scripts/benchmark_cli_cold_boot.py``).

The subprocess variants are the source of truth — in-process tests
share interpreter state with pytest itself, so they can give a false
PASS if pytest already imported the heavy module via a fixture.

Docs:
    https://docs.python.org/3.11/library/sys.html#sys.modules
    https://docs.python.org/3.11/library/subprocess.html#subprocess.run
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Source of truth for the banned set is ``scripts/check_lazy_imports.py``.
# We re-import it here so the two stay in lockstep — adding a module to
# the banned list automatically tightens these tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "check_lazy_imports.py"


def _load_banned_set() -> frozenset[str]:
    """Re-export ``BANNED_TOP_LEVEL`` from the governance script.

    Loaded by file path because ``scripts/`` is intentionally not on the
    importable path (it's an ops folder, not a package). The module MUST
    be registered in ``sys.modules`` *before* ``exec_module`` runs so
    ``@dataclass`` can resolve ``cls.__module__`` back to its host
    module — without that registration Python hits an AttributeError
    (https://docs.python.org/3.11/library/dataclasses.html — see issue
    https://github.com/python/cpython/issues/95300 for context).
    """
    spec = importlib.util.spec_from_file_location("_nucleus_check_lazy_imports", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_nucleus_check_lazy_imports"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("_nucleus_check_lazy_imports", None)
        raise
    return frozenset(module.BANNED_TOP_LEVEL)


_BANNED = _load_banned_set()


# ============================================================================
# Test 1 — in-process import
# ============================================================================


class TestInProcessImport:
    """``import nucleus.cli.main`` must not pull any banned module.

    Caveat: pytest shares one Python interpreter across the whole test
    session, so a different test file (e.g. ``test_schedule_daemon.py``
    which exercises the croniter-dependent scheduler) may have already
    imported a banned library before this test runs. We snapshot
    ``sys.modules`` BEFORE the cli.main import and only assert that
    *no NEW* banned module entered the cache as a result of this
    specific import. The authoritative session-independent check is
    :class:`TestSubprocessImport` below.
    """

    @pytest.mark.parametrize("banned", sorted(_BANNED))
    def test_banned_module_not_pulled_by_cli_main_import(self, banned: str) -> None:
        """Importing ``nucleus.cli.main`` MUST NOT *newly* load ``banned``.

        If the module is already in ``sys.modules`` because an earlier
        test imported it, this test skips — the subprocess variant
        below (running in a fresh interpreter) is the source of truth.
        """
        if banned in sys.modules:
            pytest.skip(
                f"{banned!r} already loaded by an earlier test in this session "
                "(see TestSubprocessImport for the authoritative cold-start check)"
            )
        importlib.import_module("nucleus.cli.main")
        assert banned not in sys.modules, (
            f"`import nucleus.cli.main` newly loaded banned module {banned!r}. "
            f"Move the `{banned}` import inside the command handler that needs it. "
            f"See scripts/check_lazy_imports.py for the governance gate."
        )


# ============================================================================
# Test 2 — subprocess (true cold-start)
# ============================================================================


class TestSubprocessImport:
    """A fresh interpreter must also have zero banned modules after the import.

    Subprocess wrapping is the authoritative test: in-process measurements
    can be polluted by pytest fixtures or other test files that already
    forced a heavy module into ``sys.modules`` before this test ran.
    """

    def test_no_banned_modules_loaded(self) -> None:
        """``python -c 'import nucleus.cli.main'`` leaves banned set empty."""
        banned_repr = json.dumps(sorted(_BANNED))
        program = (
            "import nucleus.cli.main; import json, sys; "
            f"banned = set({banned_repr}); "
            "loaded = sorted(m for m in sys.modules if m in banned); "
            "print(json.dumps(loaded))"
        )
        # Docs: https://docs.python.org/3.11/library/subprocess.html#subprocess.run
        result = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, (
            "Subprocess failed to import nucleus.cli.main:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        loaded = json.loads(result.stdout.strip().splitlines()[-1])
        assert loaded == [], (
            f"Banned modules leaked into a fresh interpreter: {loaded}. "
            "Each name must be moved inside its command handler."
        )


# ============================================================================
# Test 3 — workbench lazy import is wired correctly
# ============================================================================


class TestLazyImportsActuallyExecute:
    """Lazy imports are only valuable if the lazy path *can* execute.

    The negative tests above (1 and 2) prove ``import nucleus.cli.main``
    leaves the banned set untouched. This positive test proves the lazy
    paths still resolve correctly when invoked — i.e. we did not break
    the workbench wiring while moving ``uvicorn``/``fastapi`` off the
    module top.

    The two we exercise:

    * ``nucleus.workbench.create_app`` — PEP 562 ``__getattr__`` proxy
      added 2026-05-15; resolving it MUST load ``fastapi``.
    * ``import litellm`` happens inside :func:`nucleus.intelligence.copilot.chat`
      AFTER several config / opt-in / cost gates — too much state to
      drive in unit tests without real config + credentials. We check
      the literal ``import litellm`` appears in the source as the lazy
      gate (regression catches anyone who promotes the import to module
      top without updating BANNED_TOP_LEVEL).
    """

    def test_workbench_create_app_resolves_via_pep562(self) -> None:
        """Accessing ``nucleus.workbench.create_app`` must load ``fastapi``.

        Per ``src/nucleus/workbench/__init__.py`` the symbol is exposed
        through PEP 562 ``__getattr__``; the resolution path imports
        ``nucleus.workbench.app`` which in turn imports ``fastapi``.
        """
        # Force a clean state for the assertion to be meaningful.
        if "fastapi" in sys.modules:
            pytest.skip("fastapi already loaded by an earlier test; cannot verify lazy load")
        import nucleus.workbench  # noqa: F401  # re-import is fine — sys.modules cached.

        # PEP 562 hook fires here.
        create_app = nucleus.workbench.create_app
        assert callable(create_app), "create_app proxy must be callable"
        assert "fastapi" in sys.modules, (
            "fastapi was not loaded after accessing nucleus.workbench.create_app. "
            "The PEP 562 __getattr__ hook in workbench/__init__.py is broken."
        )

    def test_copilot_module_keeps_litellm_import_inside_function(self) -> None:
        """Source-level guard — ``import litellm`` must live inside the chat body.

        We grep the source file (vs. relying on side effects) so the test
        is deterministic regardless of whether earlier tests imported
        litellm via integration paths.
        """
        copilot_src = (_REPO_ROOT / "src" / "nucleus" / "intelligence" / "copilot.py").read_text(
            encoding="utf-8"
        )
        # Heuristic: the literal ``import litellm`` must NOT appear at
        # column 0 (top-level); it MUST appear with leading whitespace
        # (inside a function body).
        for lineno, line in enumerate(copilot_src.splitlines(), start=1):
            if line.strip() == "import litellm" and not line.startswith(" "):
                pytest.fail(
                    f"copilot.py line {lineno}: `import litellm` at column 0 — "
                    "must live inside a function body for the CLI to stay fast."
                )


# ============================================================================
# Test 4 — `nucleus --version` is fast (sanity, not strict gate)
# ============================================================================


class TestNucleusVersionFast:
    """End-to-end ``nucleus --version`` completes quickly.

    The strict 500 ms cold-boot gate lives in
    ``scripts/benchmark_cli_cold_boot.py`` — it runs N=10 fresh
    subprocesses and reports min/median/p95. This test is the
    catastrophic-regression catch: if ``nucleus --version`` takes
    longer than two seconds, something is seriously wrong (a heavy
    eager import, a failed shebang, etc.).
    """

    def test_completes_under_two_seconds(self) -> None:
        """``nucleus --version`` must return in under 2 seconds.

        Two seconds is intentionally lax — the perf-doc target is 500 ms
        and the benchmark harness enforces that. This test only flags
        regressions of the order of 5x or worse.
        """
        # Docs: https://docs.python.org/3.11/library/subprocess.html#subprocess.run
        try:
            result = subprocess.run(
                ["nucleus", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                "nucleus --version did not complete within 2 seconds — "
                "a banned module is likely being imported eagerly. Run "
                "`python scripts/check_lazy_imports.py` to localise."
            )
        except FileNotFoundError:
            pytest.skip("nucleus console-script not on PATH for this test session.")
            return
        assert result.returncode == 0, (
            f"nucleus --version exited {result.returncode}: {result.stderr}"
        )
        assert "nucleus" in result.stdout.lower()
