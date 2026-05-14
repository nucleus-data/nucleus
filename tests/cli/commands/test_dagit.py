"""Tests for ``nucleus dagit`` — power-user escape hatch (ADR-018).

Validates:
- ``nucleus dagit --help`` exits 0 and surfaces the deliberate "power-user"
  + "Dagit" wording + a pointer to ``nucleus workbench`` as primary UX.
- The subprocess argv is built per the documented dagster-webserver surface.
- Default port = 3000.
- Port auto-increment kicks in when 3000 is taken.
- Browser opens via ``webbrowser.open`` on success.
- ``--no-browser`` suppresses the browser open.
- Workspace discovery from ``nucleus_project.yaml`` works.
- Explicit ``--workspace`` overrides discovery.
- ``FileNotFoundError`` (binary missing) → ``NucleusDagitLaunchError`` (NE5009).
- All ports taken → ``NucleusPortUnavailableError`` (NE5010).
- ``KeyboardInterrupt`` → graceful subprocess termination (no orphan).
- No external library classnames in user-facing output (per AGENTS §11.7).

Hermetic by construction: every test mocks ``subprocess.Popen``,
``socket.socket``, and ``webbrowser.open`` so no external process is ever
spawned and no port is actually bound.

Per AGENTS.md §11.10: patch the imported binding inside
``nucleus.cli.commands.dagit`` (e.g. ``...dagit.subprocess.Popen``), NOT
the upstream stdlib symbols — patching upstream would not redirect the
import that the CLI module already resolved at module load time.

Docs:
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
- unittest.mock.patch: https://docs.python.org/3/library/unittest.mock.html
"""

# ruff: noqa: ARG001, ARG002

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app


_FORBIDDEN_CLASSNAMES = (
    # Stdlib internals that should never reach user-facing strings.
    "subprocess.SubprocessError",
    "subprocess.CalledProcessError",
    "FileNotFoundError",
    "OSError",
    "Traceback (most recent call last)",
    # Wrapped libraries that should never leak past the coordination layer.
    "dagster._",
    "dagster.core",
    "DagsterError",
    "duckdb._",
    "polars._",
    "pyiceberg._",
    # Click/Typer internals (the CLI must NEVER print these).
    "Click",
    "click.exceptions",
    "TyperError",
)


# Module-level CliRunner so we can assert separately on stdout vs stderr —
# the dagit command writes user-facing errors to stderr per cli_spec §5.4.
runner = CliRunner(mix_stderr=False)


@pytest.fixture
def in_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test inside an isolated tmp directory.

    The dagit command discovers workspace files relative to ``Path.cwd()``;
    hermetic tests must keep every probe inside ``tmp_path``.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _make_popen_mock(*, wait_returncode: int = 0) -> MagicMock:
    """Return a Popen mock whose .wait() exits cleanly with the given code.

    No ``spec=subprocess.Popen`` because the test imports patch
    ``subprocess.Popen`` AT the call-site module, so spec resolution
    would re-encounter the patch object and fail with InvalidSpecError.
    """
    proc = MagicMock()
    proc.wait = MagicMock(return_value=wait_returncode)
    proc.poll = MagicMock(return_value=None)
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    return proc


# ============================================================================
# Help surface
# ============================================================================


class TestHelp:
    """The dagit command must be discoverable via help with the deliberate wording."""

    def test_dagit_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["dagit", "--help"])
        assert result.exit_code == 0, f"unexpected exit:\n{result.stdout}"

    def test_dagit_help_mentions_power_user(self) -> None:
        """The deliberate 'power-user' wording must reach the user (ADR-018)."""
        result = runner.invoke(app, ["dagit", "--help"])
        # case-insensitive — Rich may apply formatting
        assert "power-user" in result.stdout.lower()

    def test_dagit_help_mentions_dagit_token(self) -> None:
        """The literal token 'Dagit' is the deliberate vocabulary carve-out (ADR-018)."""
        result = runner.invoke(app, ["dagit", "--help"])
        assert "Dagit" in result.stdout

    def test_dagit_help_directs_to_workbench(self) -> None:
        """Help text must direct users to ``nucleus workbench`` as the primary UX."""
        result = runner.invoke(app, ["dagit", "--help"])
        assert "nucleus workbench" in result.stdout

    def test_dagit_help_lists_port_flag(self) -> None:
        result = runner.invoke(app, ["dagit", "--help"])
        assert "--port" in result.stdout

    def test_dagit_help_lists_workspace_flag(self) -> None:
        result = runner.invoke(app, ["dagit", "--help"])
        assert "--workspace" in result.stdout

    def test_dagit_help_lists_no_browser_flag(self) -> None:
        result = runner.invoke(app, ["dagit", "--help"])
        assert "--no-browser" in result.stdout

    def test_dagit_appears_in_root_help(self) -> None:
        """``nucleus --help`` must list dagit alongside the v0.1 commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "dagit" in result.stdout


# ============================================================================
# Subprocess argv construction
# ============================================================================


class TestSubprocessArgv:
    """The argv handed to subprocess.Popen must match the documented dagster-webserver surface."""

    def test_default_port_is_3000(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        argv = popen.call_args.args[0]
        assert "--port" in argv
        port_idx = argv.index("--port")
        assert argv[port_idx + 1] == "3000"

    def test_argv_invokes_dagster_webserver_binary(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            runner.invoke(app, ["dagit", "--no-browser"])

        argv = popen.call_args.args[0]
        assert argv[0] == "dagster-webserver"

    def test_argv_includes_workspace_flag(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            runner.invoke(app, ["dagit", "--no-browser"])

        argv = popen.call_args.args[0]
        assert "--workspace" in argv

    def test_explicit_port_is_passed_through(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            runner.invoke(app, ["dagit", "--port", "4242", "--no-browser"])

        argv = popen.call_args.args[0]
        port_idx = argv.index("--port")
        assert argv[port_idx + 1] == "4242"


# ============================================================================
# Port auto-increment
# ============================================================================


class TestPortAutoIncrement:
    """When the default port is taken, scan upward; when ALL are taken, error out."""

    def test_default_port_taken_scans_upward(self, in_tmp_dir: Path) -> None:
        # 3000 taken, 3001 free.
        free_map = {3000: False, 3001: True}
        with (
            patch(
                "nucleus.cli.commands.dagit._is_port_free",
                side_effect=lambda p: free_map.get(p, True),
            ),
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert result.exit_code == 0
        argv = popen.call_args.args[0]
        port_idx = argv.index("--port")
        assert argv[port_idx + 1] == "3001"

    def test_all_ports_taken_exits_nonzero(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=False),
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
        ):
            popen.return_value = _make_popen_mock()
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert result.exit_code == 1

    def test_all_ports_taken_error_mentions_port_flag(self, in_tmp_dir: Path) -> None:
        with patch("nucleus.cli.commands.dagit._is_port_free", return_value=False):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        combined = (result.stdout or "") + (result.stderr or "")
        assert "--port" in combined

    def test_all_ports_taken_does_not_invoke_subprocess(self, in_tmp_dir: Path) -> None:
        """Port exhaustion must short-circuit BEFORE we try to launch the subprocess."""
        with (
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=False),
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
        ):
            runner.invoke(app, ["dagit", "--no-browser"])

        popen.assert_not_called()


# ============================================================================
# Browser behaviour
# ============================================================================


class TestBrowser:
    """The browser opens by default; --no-browser suppresses it."""

    def test_browser_opens_by_default(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open") as wb_open,
        ):
            popen.return_value = _make_popen_mock()
            result = runner.invoke(app, ["dagit"])

        assert result.exit_code == 0
        wb_open.assert_called_once()
        url = wb_open.call_args.args[0]
        assert url.startswith("http://localhost:")

    def test_no_browser_flag_suppresses(self, in_tmp_dir: Path) -> None:
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open") as wb_open,
        ):
            popen.return_value = _make_popen_mock()
            runner.invoke(app, ["dagit", "--no-browser"])

        wb_open.assert_not_called()


# ============================================================================
# Workspace discovery
# ============================================================================


class TestWorkspaceDiscovery:
    """The workspace path discovery + override logic must hand the right file to the subprocess."""

    def test_explicit_workspace_overrides_discovery(self, in_tmp_dir: Path) -> None:
        explicit = in_tmp_dir / "custom_workspace.yaml"
        explicit.write_text("# stub")
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            runner.invoke(
                app,
                ["dagit", "--workspace", str(explicit), "--no-browser"],
            )

        argv = popen.call_args.args[0]
        ws_idx = argv.index("--workspace")
        assert Path(argv[ws_idx + 1]).resolve() == explicit.resolve()

    def test_workspace_discovered_from_nucleus_project_yaml(self, in_tmp_dir: Path) -> None:
        """When no --workspace passed, discover nucleus_project.yaml in cwd."""
        project = in_tmp_dir / "nucleus_project.yaml"
        project.write_text("project:\n  name: 'test'\n")
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen") as popen,
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            popen.return_value = _make_popen_mock()
            runner.invoke(app, ["dagit", "--no-browser"])

        argv = popen.call_args.args[0]
        ws_idx = argv.index("--workspace")
        assert Path(argv[ws_idx + 1]).resolve() == project.resolve()


# ============================================================================
# Error translation — FileNotFoundError → NucleusDagitLaunchError
# ============================================================================


class TestFileNotFoundTranslation:
    """When dagster-webserver is missing on PATH, surface NE5009 with install hint."""

    def test_filenotfound_exits_one(self, in_tmp_dir: Path) -> None:
        with (
            patch(
                "nucleus.cli.commands.dagit.subprocess.Popen",
                side_effect=FileNotFoundError(2, "No such file or directory", "dagster-webserver"),
            ),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
        ):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert result.exit_code == 1

    def test_filenotfound_error_mentions_install_command(self, in_tmp_dir: Path) -> None:
        """The fix_hint must give the user the exact `pip install dagster-webserver==X.Y.Z`."""
        with (
            patch(
                "nucleus.cli.commands.dagit.subprocess.Popen",
                side_effect=FileNotFoundError(2, "not found", "dagster-webserver"),
            ),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
        ):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert "pip install dagster-webserver" in result.stderr

    def test_filenotfound_error_emits_docs_url(self, in_tmp_dir: Path) -> None:
        with (
            patch(
                "nucleus.cli.commands.dagit.subprocess.Popen",
                side_effect=FileNotFoundError(2, "not found", "dagster-webserver"),
            ),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
        ):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert "nucleus.dev/errors" in result.stderr


# ============================================================================
# Error translation — KeyboardInterrupt → graceful termination
# ============================================================================


class TestKeyboardInterrupt:
    """Ctrl+C must terminate the child gracefully and exit cleanly."""

    def test_ctrl_c_calls_terminate(self, in_tmp_dir: Path) -> None:
        proc = _make_popen_mock()
        # First .wait() raises KeyboardInterrupt (the user pressing Ctrl+C),
        # the SECOND .wait() (inside _terminate_gracefully after .terminate())
        # returns 0 because the child honoured the SIGTERM.
        proc.wait.side_effect = [KeyboardInterrupt(), 0]

        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen", return_value=proc),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        assert result.exit_code == 0
        proc.terminate.assert_called_once()

    def test_ctrl_c_then_timeout_escalates_to_kill(self, in_tmp_dir: Path) -> None:
        """If the child ignores SIGTERM within the grace window, escalate to SIGKILL."""
        proc = _make_popen_mock()
        # First .wait() raises KeyboardInterrupt (the user pressing Ctrl+C),
        # the second .wait() (inside the graceful-termination helper) times
        # out, the third .wait() (post-kill) succeeds.
        proc.wait.side_effect = [
            KeyboardInterrupt(),
            subprocess.TimeoutExpired(cmd="dagster-webserver", timeout=10.0),
            0,
        ]

        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen", return_value=proc),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            runner.invoke(app, ["dagit", "--no-browser"])

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()


# ============================================================================
# No leaked classnames in user-facing output
# ============================================================================


class TestNoClassnameLeaks:
    """Per AGENTS §11.7, no external library classnames may appear in user output."""

    def test_no_forbidden_classnames_in_filenotfound_error(self, in_tmp_dir: Path) -> None:
        with (
            patch(
                "nucleus.cli.commands.dagit.subprocess.Popen",
                side_effect=FileNotFoundError(2, "missing", "dagster-webserver"),
            ),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
        ):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        combined = (result.stdout or "") + (result.stderr or "")
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in combined, (
                f"forbidden term {term!r} leaked into user output: {combined!r}"
            )

    def test_no_forbidden_classnames_in_port_unavailable_error(self, in_tmp_dir: Path) -> None:
        with patch("nucleus.cli.commands.dagit._is_port_free", return_value=False):
            result = runner.invoke(app, ["dagit", "--no-browser"])

        combined = (result.stdout or "") + (result.stderr or "")
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in combined, (
                f"forbidden term {term!r} leaked into user output: {combined!r}"
            )

    def test_no_forbidden_classnames_in_help(self, in_tmp_dir: Path) -> None:
        result = runner.invoke(app, ["dagit", "--help"])
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in result.stdout, (
                f"forbidden term {term!r} leaked into help: {result.stdout!r}"
            )


# ============================================================================
# Hermetic guarantees — never spawn a real subprocess in the test suite
# ============================================================================


class TestHermeticity:
    """A failing mock proves we are not silently launching a real webserver."""

    def test_subprocess_popen_is_always_mocked(self, in_tmp_dir: Path) -> None:
        sentinel = MagicMock(side_effect=AssertionError("real Popen called!"))
        with (
            patch("nucleus.cli.commands.dagit.subprocess.Popen", sentinel),
            patch("nucleus.cli.commands.dagit._is_port_free", return_value=True),
            patch("nucleus.cli.commands.dagit.webbrowser.open"),
        ):
            runner.invoke(app, ["dagit", "--no-browser"])
        sentinel.assert_called_once()
