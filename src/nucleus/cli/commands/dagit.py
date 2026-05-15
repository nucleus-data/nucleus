"""``nucleus dagit`` — power-user escape hatch to the embedded orchestrator UI.

This command launches the wrapped orchestrator's web UI (``dagster-webserver``)
as a subprocess, opens the user's default browser, and forwards Ctrl+C as a
graceful SIGTERM. It exists for advanced debugging only — the primary, branded
UX is :command:`nucleus workbench` per ADR-016 (Fork B custom React SPA).

Why this command exists
-----------------------
External reviewers (PoC #5) repeatedly asked "why don't you just use the
orchestrator's existing UI?" Founder ratification (2026-05-14): ship
``nucleus dagit`` as an opt-in escape hatch alongside the custom Workbench
so power users have a one-line on-ramp without forking the wrap-not-build
discipline. The carve-out is bounded: the literal token ``dagit`` is allowed
in this file, in :class:`NucleusDagitLaunchError` / :class:`NucleusPortUnavailableError`
/ :class:`NucleusDagitSubprocessError` user-facing strings, and in
ADR-018; nowhere else (per AGENTS.md §7 footnote).

Architecture refs
-----------------
- ``nucleus_architecture_v4.1.md`` §6.5 (Dagster Replaceability Mandate —
  this command is Tier 3 of the §6.6 progressive-disclosure ladder).
- ``nucleus_architecture_v4.1.md`` §6.6 (Tier 3 escape hatch tier:
  "exposes Dagster UI directly").
- ``nucleus_cli_spec.md`` §3.10 (CLI surface, Beta-tier ninth command).
- ADR-018 (escape-hatch decision + vocabulary carve-out).
- ADR-016 §"Decision" (primary UX is the custom Workbench, not this).

Subprocess wrapping discipline
------------------------------
Per AGENTS.md §11.7 + ``nucleus_architecture_v4.1.md`` §6.4: every
external exception that reaches the user is translated to a
:class:`NucleusError` subclass. The mapping for this command:

- ``FileNotFoundError`` (binary missing on PATH)
  → :class:`NucleusDagitLaunchError` (NE5009) with a fix_hint pointing
    at ``pip install dagster-webserver==<dagster pin>``.
- All ports in scan range bound
  → :class:`NucleusPortUnavailableError` (NE5010) with a fix_hint
    suggesting an explicit ``--port``.
- Any other ``subprocess.SubprocessError``
  → :class:`NucleusDagitSubprocessError` (NE5011) with the original
    cause preserved via ``__cause__``.

# Stability: Beta
"""

# Docs (per AGENTS.md §11.12):
#   - subprocess: https://docs.python.org/3/library/subprocess.html
#   - webbrowser: https://docs.python.org/3/library/webbrowser.html
#   - socket:     https://docs.python.org/3/library/socket.html
#   - signal:     https://docs.python.org/3/library/signal.html
#   - Typer:      https://typer.tiangolo.com/
#   - Rich panel: https://rich.readthedocs.io/en/stable/panel.html
# NEEDS VERIFICATION (founder review, ADR-018): the exact dagster-webserver
# CLI invocation surface (``--workspace`` / ``--port`` / ``--host``) is
# documented at https://pypi.org/project/dagster-webserver/ but the
# v1.9.5 ``--help`` output is not captured in this repo. The command
# below uses the documented flag names from the dagster-webserver
# README (Usage section); upgrade smoke must verify they remain stable
# when ``dagster-webserver`` is added to the install matrix.

from __future__ import annotations

import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Annotated

import typer

from nucleus.errors import (
    NucleusDagitLaunchError,
    NucleusDagitSubprocessError,
    NucleusError,
    NucleusPortUnavailableError,
)

# ---------------------------------------------------------------------------
# Module-level constants (kept close to the only callsite per
# .cursor/rules/nucleus.mdc Anti-Over-Engineering: inline first, abstract
# only when a second real caller appears).
# ---------------------------------------------------------------------------

# Default starting port. dagster-webserver also defaults to 3000.
# Docs: https://pypi.org/project/dagster-webserver/ (Usage section).
_DEFAULT_PORT: int = 3000
# Inclusive upper bound of the port-auto-detect window. 11-port window
# matches conventions used by frameworks like Vite (5173-5183) — wide
# enough to dodge a few collisions, narrow enough that "no port found"
# is a real signal, not a stuck loop.
_MAX_PORT: int = 3010

# Pinned dagster version used in the install fix_hint. Mirrors the pin in
# pyproject.toml (``dagster==1.9.5``) — the dagster-webserver wheel for that
# version is the only one guaranteed to load this project's Definitions
# without an internal-API mismatch.
_DAGSTER_PIN: str = "1.9.5"

# How long we wait for the subprocess to honour SIGTERM before escalating
# to SIGKILL. 10s is the same envelope ``docker compose down`` uses.
_TERMINATE_GRACE_SECONDS: float = 10.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_workspace_file(explicit: str | None) -> Path:
    """Resolve which workspace file to hand to the embedded orchestrator UI.

    The escape hatch is deliberately tolerant: if the user passes
    ``--workspace`` we trust them; otherwise we walk up to three parents
    looking for ``nucleus_project.yaml`` and use *that path* as the
    workspace pointer (the embedded orchestrator reads any YAML file
    that resolves to a Dagster workspace; nucleus_project.yaml is what
    every Nucleus project ships, so it is the natural anchor).

    No filesystem error is raised here when the file is missing — we
    surface a :class:`NucleusDagitLaunchError` later when the subprocess
    fails to start, so the user sees one consistent error path.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents)[:4]:
        config = candidate / "nucleus_project.yaml"
        if config.is_file():
            return config
    # No project on disk; fall back to the cwd anchor. The subprocess
    # will surface the actual "no such file" error and we translate it.
    return here / "nucleus_project.yaml"


def _is_port_free(port: int) -> bool:
    """Return ``True`` if a TCP server can bind ``localhost:port`` right now.

    We bind a stdlib socket rather than calling ``netstat`` so the probe
    is portable across Windows / macOS / Linux. ``SO_REUSEADDR`` is left
    OFF on purpose — we want the bind to fail when the port is held by
    a TIME_WAIT socket too, so users do not hit a confusing
    "port already in use" *after* we said it was free.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _select_port(start: int, end: int) -> int:
    """Walk ``[start, end]`` returning the first free port; raise on exhaustion."""
    for candidate in range(start, end + 1):
        if _is_port_free(candidate):
            return candidate
    raise NucleusPortUnavailableError(
        user_message=(
            f"All ports in the range {start}-{end} are already in use; "
            "could not pick a free port for the embedded orchestrator UI."
        ),
        fix_hint=(
            "Pass an explicit --port (e.g. --port 4000), or stop whatever "
            f"is currently bound to ports {start}-{end} and retry."
        ),
    )


def _build_subprocess_argv(workspace_file: Path, port: int) -> list[str]:
    """Construct the ``dagster-webserver`` argv per its documented surface.

    Docs: https://pypi.org/project/dagster-webserver/ (Usage section).
    Flag names verified against the v1.9.5 README. The ``-w`` / ``--workspace``
    pair both work; we use the long form for grep-ability in user logs.
    """
    return [
        "dagster-webserver",
        "--workspace",
        str(workspace_file),
        "--port",
        str(port),
        "--host",
        "127.0.0.1",
    ]


def _terminate_gracefully(proc: subprocess.Popen[bytes]) -> None:
    """Send SIGTERM, wait :data:`_TERMINATE_GRACE_SECONDS`, then SIGKILL.

    The escape hatch must always reap its child — leaking a webserver
    process between Ctrl+C and the next ``nucleus dagit`` run produces
    the exact "port already in use" friction users invoked us to escape.
    """
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        # Final wait so we don't leave a zombie behind on POSIX.
        try:
            proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _print_banner(url: str) -> None:
    """Render the launch banner. Falls back to plain ``typer.echo`` if Rich missing."""
    try:
        # Rich is a hard runtime dep (pinned in pyproject.toml), but we keep
        # the import inside the function so help-text rendering stays cheap.
        # Docs: https://rich.readthedocs.io/en/stable/panel.html
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                "[bold yellow]Power-user mode[/bold yellow]: opening the embedded "
                "orchestrator's web UI (Dagit).\n\n"
                f"  URL:        [link={url}]{url}[/link]\n"
                "  Primary UX: [bold]nucleus workbench[/bold] "
                "(branded Nucleus UI per ADR-016)\n\n"
                "  [dim]Press Ctrl+C to stop the embedded orchestrator UI.[/dim]",
                title="[bold]nucleus dagit[/bold]",
                border_style="yellow",
            )
        )
    except ImportError:
        typer.echo("Power-user mode: opening the embedded orchestrator's web UI (Dagit).")
        typer.echo(f"  URL:        {url}")
        typer.echo("  Primary UX: nucleus workbench (branded Nucleus UI per ADR-016)")
        typer.echo("  Press Ctrl+C to stop the embedded orchestrator UI.")


def _exit_dagit_error(err: NucleusError, code: int = 1) -> None:
    """Render a NucleusError to stderr — mirrors the pattern used by chat / schedule."""
    typer.echo(f"Error: {err.user_message}", err=True)
    if err.fix_hint:
        typer.echo(f"Fix:   {err.fix_hint}", err=True)
    typer.echo(f"Docs:  {err.docs_url}", err=True)
    raise typer.Exit(code=code)


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def dagit(
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help=(
                f"Port to bind. Defaults to {_DEFAULT_PORT}; if taken, scans up "
                f"to {_MAX_PORT} for a free one."
            ),
        ),
    ] = _DEFAULT_PORT,
    workspace: Annotated[
        str | None,
        typer.Option(
            "--workspace",
            help=(
                "Path to a workspace file (defaults to the discovered "
                "nucleus_project.yaml in the current directory or its parents)."
            ),
        ),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="Do not open the system browser after launch.",
        ),
    ] = False,
) -> None:
    """[bold]Power-user mode[/bold] — launch the embedded orchestrator's web UI (Dagit).

    [yellow]This is an opt-in escape hatch.[/yellow] The primary, branded UX is
    [bold]nucleus workbench[/bold] (custom React SPA per ADR-016). Use this command
    only when you need raw access to the embedded orchestrator's debugger, run
    history, or schedule/sensor introspection screens that the Workbench has not
    yet wrapped.

    Per [bold]ADR-018[/bold] (escape-hatch decision) +
    [bold]nucleus_architecture_v4.1.md §6.6[/bold] (Tier 3 progressive disclosure).
    Wraps the [bold]dagster-webserver[/bold] PyPI package. If the binary is not on
    PATH the command fails fast with a one-line install command; nothing else in
    the stack is affected.

    [bold]Examples[/bold]

        nucleus dagit                        # default port 3000, browser opens
        nucleus dagit --port 4000            # override port
        nucleus dagit --no-browser           # CI / headless invocation
        nucleus dagit --workspace ./other.yaml

    [bold]Stability[/bold] — Beta (ADR-005 §2). The flag taxonomy is expected to
    stay stable through v1.0; the underlying [bold]dagster-webserver[/bold]
    surface is owned upstream and may evolve faster.
    """
    try:
        chosen_port = port if port != _DEFAULT_PORT else _select_port(_DEFAULT_PORT, _MAX_PORT)
        # When the user passed an explicit port we honour it as-is (no
        # auto-increment) so an explicit ``--port`` is always exact.
        # When the user accepted the default and that one is taken, we scan.
        if chosen_port == _DEFAULT_PORT and not _is_port_free(_DEFAULT_PORT):
            chosen_port = _select_port(_DEFAULT_PORT + 1, _MAX_PORT)

        workspace_file = _find_workspace_file(workspace)
        argv = _build_subprocess_argv(workspace_file, chosen_port)
        url = f"http://localhost:{chosen_port}"

        _print_banner(url)

        try:
            # Docs: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            # We let the child inherit our stdio so the user can read the
            # webserver's startup banner directly. No shell=True (security).
            proc: subprocess.Popen[bytes] = subprocess.Popen(
                argv,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        except FileNotFoundError as exc:
            raise NucleusDagitLaunchError(
                user_message=(
                    "The embedded orchestrator's web UI binary is not installed "
                    "in this Python environment."
                ),
                fix_hint=(
                    f"Install the optional Dagit web UI: "
                    f"`pip install dagster-webserver=={_DAGSTER_PIN}` "
                    "(must match the pinned dagster version)."
                ),
                cause=exc,
            ) from exc
        except OSError as exc:
            # Other OS-level failures (PermissionError on the binary, etc).
            raise NucleusDagitSubprocessError(
                user_message=("Failed to start the embedded orchestrator's web UI subprocess."),
                fix_hint=(
                    f"Verify `dagster-webserver=={_DAGSTER_PIN}` is installed and "
                    "executable, then retry."
                ),
                cause=exc,
            ) from exc

        if not no_browser:
            try:
                # Docs: https://docs.python.org/3/library/webbrowser.html
                webbrowser.open(url)
            except webbrowser.Error:
                # Browser unavailable (CI, headless container) is not fatal —
                # the server is still running on the printed URL.
                pass

        try:
            proc.wait()
        except KeyboardInterrupt:
            _terminate_gracefully(proc)
            typer.echo("Embedded orchestrator UI stopped.")
            return
        except subprocess.SubprocessError as exc:
            _terminate_gracefully(proc)
            raise NucleusDagitSubprocessError(
                user_message=(
                    "The embedded orchestrator's web UI subprocess failed during execution."
                ),
                fix_hint=(
                    "Re-run with --port <new> to rule out a port collision, or "
                    f"reinstall dagster-webserver=={_DAGSTER_PIN}."
                ),
                cause=exc,
            ) from exc
    except NucleusError as err:
        _exit_dagit_error(err)
