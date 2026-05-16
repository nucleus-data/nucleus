"""Smoke tests for the Nucleus CLI — docs/specs/nucleus_cli_spec.md §3.

Scope of this file
------------------
Per docs/specs/nucleus_cli_spec.md §3 + ADR-015 (AI Chat MVP): every v0.1 command
must respond to ``--help`` with exit code 0 and include its name in the
help output.  All eight commands must appear in the root ``nucleus
--help`` listing.  The ``version`` command is real (not a stub) and
must report the installed package versions.  Stub commands must exit
with code 1 (NucleusError per exit-code contract §8), not an uncaught
Python traceback.

What this file does NOT cover
------------------------------
- Full integration / E2E tests (``scripts/beachhead_e2e.py``)
- Exit-code matrix testing (``tests/cli/test_exit_codes.py`` — to be
  authored at v0.1 implementation)
- ``--help`` snapshot diffs (``tests/cli/test_help_snapshot.py`` — Beta
  tier, deferred to v0.1 implementation per spec §3 stability note)

Docs refs
---------
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
  (Pinned version: typer==0.15.1, wraps click.testing.CliRunner)
- docs/specs/nucleus_cli_spec.md §3 (all seven commands)
- docs/specs/nucleus_cli_spec.md §5.4 (error format — no internal class names)
- docs/specs/nucleus_cli_spec.md §8 (exit-code contract)
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from nucleus import __version__
from nucleus.cli.main import app

# Docs: https://typer.tiangolo.com/tutorial/testing/
# CliRunner wraps click.testing.CliRunner; mix_stderr=True (default) means
# stderr is mixed into result.stdout — useful for checking error output.
runner = CliRunner()

# All eight v0.1 commands defined in docs/specs/nucleus_cli_spec.md §3 + ADR-015 (chat).
_V01_COMMANDS = ("init", "up", "down", "run", "ingest", "query", "version", "chat")


# ==============================================================================
# Root --help
# ==============================================================================


class TestRootHelp:
    """``nucleus --help`` must exit 0 and list all eight v0.1 commands."""

    def test_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0, f"nucleus --help returned {result.exit_code}"

    def test_mentions_all_v01_commands(self) -> None:
        """Every v0.1 command name must appear in the root help output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in _V01_COMMANDS:
            assert cmd in result.stdout, (
                f"Command '{cmd}' not found in 'nucleus --help' output.\n"
                f"Full output:\n{result.stdout}"
            )


# ==============================================================================
# --version global flag (docs/specs/nucleus_cli_spec.md §3.7 + root callback)
# ==============================================================================


class TestVersionFlag:
    """``nucleus --version`` (global flag) must exit 0 and print the version."""

    def test_exits_zero(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_contains_package_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout, (
            f"Expected version string '{__version__}' in output. Got: {result.stdout!r}"
        )

    def test_contains_nucleus_name(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert "nucleus" in result.stdout


# ==============================================================================
# Per-command --help smoke tests (docs/specs/nucleus_cli_spec.md §3.1 - §3.7)
# ==============================================================================


class TestCommandHelp:
    """Every v0.1 command must respond to ``--help`` with exit code 0."""

    @pytest.mark.parametrize("command", _V01_COMMANDS)
    def test_exits_zero(self, command: str) -> None:
        """``nucleus <command> --help`` exits 0."""
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, (
            f"'nucleus {command} --help' returned exit code {result.exit_code}.\n"
            f"Output:\n{result.stdout}"
        )

    @pytest.mark.parametrize("command", _V01_COMMANDS)
    def test_output_contains_command_name(self, command: str) -> None:
        """The command's ``--help`` output includes the command name itself."""
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0
        assert command in result.stdout, (
            f"Command name '{command}' not found in "
            f"'nucleus {command} --help' output.\n"
            f"Full output:\n{result.stdout}"
        )


# ==============================================================================
# nucleus version (real command — docs/specs/nucleus_cli_spec.md §3.7)
# ==============================================================================


class TestVersionCommand:
    """``nucleus version`` is a REAL command (not a stub) that reports versions."""

    def test_exits_zero(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0, (
            f"'nucleus version' returned exit code {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_includes_nucleus_version(self) -> None:
        """Output must include the nucleus package version string."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "nucleus" in result.stdout
        assert __version__ in result.stdout, (
            f"Expected '{__version__}' in 'nucleus version' output. Got:\n{result.stdout}"
        )

    @pytest.mark.parametrize(
        "pkg",
        ["duckdb", "polars", "pyarrow", "pyiceberg", "dagster"],
    )
    def test_includes_required_wrapped_dependency(self, pkg: str) -> None:
        """Output must list each required wrapped dependency per spec §3.7."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert pkg in result.stdout, (
            f"Expected '{pkg}' in 'nucleus version' output.\nFull output:\n{result.stdout}"
        )

    def test_check_updates_flag_accepted(self) -> None:
        """``--check-updates`` flag must be accepted (exit 0 in v0.1 stub)."""
        result = runner.invoke(app, ["version", "--check-updates"])
        assert result.exit_code == 0


# ==============================================================================
# Stub exit behaviour — docs/specs/nucleus_cli_spec.md §8 (exit code 1 = NucleusError)
# ==============================================================================
# All v0.1 commands now have real implementations (2026-05-14). Deferred flags
# still raise NucleusInternalError with exit code 1 — see per-command test files.
